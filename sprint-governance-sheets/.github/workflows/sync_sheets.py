import os
import sys

from src.config import load_config
from src.jira_client import JiraClient
from src.analytics import AnalyticsEngine
from src.sheets_client import SheetsClient
from src.sheets_templates import build_sections


def sync():
    config = load_config()

    jira = JiraClient(config)
    sprint = jira.get_active_sprint()
    if not sprint:
        print("No active sprint found.")
        sys.exit(1)

    print(f"Active sprint: {sprint.name}")
    print("Fetching sprint issues...")

    tickets = jira.get_sprint_issues(sprint.id)
    print(f"  Found {len(tickets)} parent tickets")

    analytics = AnalyticsEngine(config)
    report = analytics.compute(sprint, tickets)

    print(f"\n  Planned: {report.total_planned_sp:.1f} SP ({report.total_planned_tickets} tickets)")
    print(f"  Delivered: {report.total_delivered_sp:.1f} SP ({report.total_delivered_tickets} tickets)")
    print(f"  Pending: {report.total_pending_sp:.1f} SP ({report.total_pending_tickets} tickets)")
    print(f"  Delivery: {report.delivery_pct}%")

    title = config.sheets.spreadsheet_title
    tab_name = sprint.name
    print(f"\nSyncing to Google Sheets: \"{title}\" → tab \"{tab_name}\"")

    sheets = SheetsClient(config)
    status = sheets.open_or_create(title)
    print(f"  Spreadsheet {status}")

    sheets.ensure_tab(tab_name)
    sections = build_sections(report)
    sheets.write_stacked(tab_name, sections)

    total_rows = sum(len(s.get("data", [])) + 2 for s in sections)
    print(f"  Updated '{tab_name}' ({total_rows} rows across {len(sections)} sections)")

    print(f"\nSpreadsheet URL: {sheets.url()}")
    print("Sync complete.")


if __name__ == "__main__":
    sync()
