import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import load_config
from src.jira_client import JiraClient
from src.analytics import AnalyticsEngine
from src.confluence_client import ConfluenceClient
from src.models import SprintReport, SprintState
from src import templates


def sync():
    config = load_config()
    jira = JiraClient(config)
    analytics = AnalyticsEngine(config)
    confluence = ConfluenceClient(config)

    sprint = jira.get_active_sprint()
    if not sprint:
        print("No active sprint found on board 49. Exiting.")
        return

    print(f"Active sprint: {sprint.name} ({sprint.start_date} → {sprint.end_date})")

    print("Fetching sprint issues...")
    tickets = jira.get_sprint_issues(sprint.id)
    print(f"  Found {len(tickets)} matching tickets (excluding sub-tasks)")

    print("Resolving team labels from sub-tasks...")
    for ticket in tickets:
        if ticket.key.startswith("FJPL-"):
            ticket.teams = jira.get_subtasks_team_labels(ticket.key)

    report = analytics.compute(sprint, tickets)
    _print_summary(report)

    print("Syncing Confluence pages...")
    hub_id = confluence.get_page_id()
    if not hub_id:
        print("  Creating Sprint Governance Hub root page...")
        hub_id = confluence.create_page(
            title=config.confluence.hub_parent_title,
            body=templates.build_hub_index(sprint.name),
        )

    _sync_current_sprint(confluence, sprint, report)
    _sync_archive(confluence, jira, config)
    _sync_performance(confluence, jira, analytics, config)

    print("Sync complete.")


def _sync_current_sprint(
    confluence: ConfluenceClient,
    sprint,
    report: SprintReport,
):
    title = "Current Sprint"
    body = templates.build_sprint_dashboard(sprint, report)
    page_id = confluence.get_page_id(title)
    if page_id:
        confluence.update_page(page_id, title, body)
        print(f"  Updated '{title}' page")
    else:
        confluence.create_page(
            title=title,
            body=body,
            parent_id=confluence.get_page_id(),
        )
        print(f"  Created '{title}' page")


def _sync_archive(confluence, jira, config):
    archive_title = "Sprint Archive"
    archive_id = confluence.get_page_id(archive_title)
    if not archive_id:
        archive_id = confluence.create_page(
            title=archive_title,
            body="<h1>Sprint Archive</h1><p>Historical sprint records.</p>"
                 "<ac:structured-macro ac:name='children'/>",
            parent_id=confluence.get_page_id(),
        )
        print(f"  Created '{archive_title}' page")


def _sync_performance(confluence, jira, analytics, config):
    title = "Performance Reports"
    page_id = confluence.get_page_id(title)
    if not page_id:
        page_id = confluence.create_page(
            title=title,
            body="<h1>Performance Reports</h1><p>Historical sprint analytics.</p>",
            parent_id=confluence.get_page_id(),
        )

    sprints = jira.get_sprint_history(max_sprints=50)
    history = []
    for s in sprints:
        tickets = jira.get_sprint_issues(s.id)
        for t in tickets:
            if t.key.startswith("FJPL-"):
                t.teams = jira.get_subtasks_team_labels(t.key)
        report = analytics.compute(s, tickets)
        history.append({
            "sprint": s.name,
            "planned_sp": report.total_planned_sp,
            "delivered_sp": report.total_delivered_sp,
            "adhoc_sp": report.adhoc_sp,
            "carry_forward_sp": report.total_pending_sp,
            "delivery_pct": report.delivery_pct,
        })

    body = templates.build_performance_history(history)
    confluence.update_page(page_id, title, body)
    print(f"  Updated '{title}' page ({len(history)} sprints)")


def _print_summary(report: SprintReport):
    print(f"\n=== Sprint: {report.sprint.name} ===")
    print(f"  Planned: {report.total_planned_sp:.1f} SP ({report.total_planned_tickets} tickets)")
    print(f"  Delivered: {report.total_delivered_sp:.1f} SP ({report.total_delivered_tickets} tickets)")
    print(f"  Pending: {report.total_pending_sp:.1f} SP ({report.total_pending_tickets} tickets)")
    print(f"  Delivery: {report.delivery_pct}%")
    print(f"  Ad-hoc: {report.adhoc_sp:.1f} SP ({len(report.adhoc_tickets)} tickets)")
    print(f"  Carry Forward: {len(report.carry_forward)} tickets")
    print(f"  Overdue: {len(report.overdue)} tickets")
    if report.team_metrics:
        print("  Teams:")
        for tm in sorted(report.team_metrics.values(), key=lambda x: x.team):
            print(f"    {tm.team}: {tm.delivered_sp:.1f}/{tm.planned_sp:.1f} ({tm.delivery_pct}%)")
    print()


if __name__ == "__main__":
    sync()
