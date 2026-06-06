from datetime import datetime
from typing import Dict, List

from src.models import SprintReport, Ticket


def _date_str(d) -> str:
    return d.strftime("%b %d") if d else ""


def _team_str(t: Ticket) -> str:
    return ", ".join(t.teams) if t.teams else ""


def build_sections(report: SprintReport) -> List[dict]:
    sprint = report.sprint
    overdue_count = len(report.overdue)

    sections = []

    sections.append({
        "title": f"Sprint Dashboard — {sprint.name}",
        "data": [
            ["Sprint", sprint.name, "Delivery %", f"{report.delivery_pct}%"],
            ["Start", _date_str(sprint.start_date), "Planned SP", f"{report.total_planned_sp:.1f}"],
            ["End", _date_str(sprint.end_date), "Delivered SP", f"{report.total_delivered_sp:.1f}"],
            ["Status", "Active" if sprint.state == "active" else "Closed", "Pending SP", f"{report.total_pending_sp:.1f}"],
            ["", "", "Planned Tickets", str(report.total_planned_tickets)],
            ["", "", "Delivered Tickets", str(report.total_delivered_tickets)],
            ["", "", "Pending Tickets", str(report.total_pending_tickets)],
            ["", "", "Ad-hoc SP", f"{report.adhoc_sp:.1f}"],
            ["", "", "Final Scope SP", f"{report.final_scope_sp:.1f}"],
            ["", "", "Overdue", str(overdue_count)],
            ["", "", "Carry-Forward", str(len(report.carry_forward))],
        ],
    })

    sections.append({
        "title": "Sprint Delivery Tracker",
        "headers": ["Key", "Type", "Summary", "Platform", "Team", "SP", "Assignee", "Status", "Due Date"],
        "data": [
            [
                t.key, t.issuetype, t.summary, t.platform,
                _team_str(t), t.story_points, t.assignee or "Unassigned",
                t.status, _date_str(t.due_date),
            ]
            for t in report.tickets
        ],
    })

    if report.adhoc_tickets:
        sections.append({
            "title": f"Ad-hoc Work ({len(report.adhoc_tickets)} tickets, {report.adhoc_sp:.1f} SP)",
            "headers": ["Key", "Summary", "Team", "Assignee", "SP", "Added"],
            "data": [
                [
                    t.key, t.summary, _team_str(t),
                    t.assignee or "Unassigned", t.story_points, _date_str(t.created),
                ]
                for t in report.adhoc_tickets
            ],
        })

    if report.carry_forward:
        sections.append({
            "title": f"Carry-Forward ({len(report.carry_forward)} tickets)",
            "headers": ["Key", "Type", "Summary", "Platform", "Team", "SP", "Assignee", "Status"],
            "data": [
                [
                    t.key, t.issuetype, t.summary, t.platform,
                    _team_str(t), t.story_points, t.assignee or "Unassigned", t.status,
                ]
                for t in report.carry_forward
            ],
        })

    if report.assignee_metrics:
        sections.append({
            "title": "Performance by Assignee",
            "headers": ["Assignee", "Planned Tickets", "Delivered Tickets", "Planned SP", "Delivered SP", "Pending SP"],
            "data": [
                [
                    am.assignee, am.planned_tickets, am.delivered_tickets,
                    am.planned_sp, am.delivered_sp, am.pending_sp,
                ]
                for am in sorted(report.assignee_metrics.values(), key=lambda x: x.assignee)
            ],
        })

    if report.team_metrics:
        sections.append({
            "title": "Performance by Team",
            "headers": ["Team", "Planned SP", "Delivered SP", "Pending SP", "Delivery %"],
            "data": [
                [tm.team, tm.planned_sp, tm.delivered_sp, tm.pending_sp, f"{tm.delivery_pct}%"]
                for tm in sorted(report.team_metrics.values(), key=lambda x: x.team)
            ],
        })

    return sections
