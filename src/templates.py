from typing import List

from src.models import Sprint, SprintReport, Ticket


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _status_class(status: str) -> str:
    low = status.lower()
    if low in ("live", "closed", "done"):
        return "status-done"
    if "progress" in low or "review" in low:
        return "status-in-progress"
    if low in ("to do", "backlog"):
        return "status-todo"
    return "status-default"


def build_sprint_dashboard(sprint: Sprint, report: SprintReport) -> str:
    lines = [_sprint_info(sprint), _health_dashboard(report)]
    lines.append(_delivery_tracker(report.tickets))
    if report.adhoc_tickets:
        lines.append(_adhoc_table(report.adhoc_tickets, report.adhoc_sp))
    if report.team_metrics:
        lines.append(_team_summary(report))
    if report.assignee_metrics:
        lines.append(_assignee_summary(report))
    if report.carry_forward:
        lines.append(_carry_forward_table(report.carry_forward))
    if report.overdue:
        lines.append(_overdue_table(report.overdue))
    lines.append(_grooming_section())
    return "\n".join(lines)


def build_closure_report(sprint: Sprint, report: SprintReport) -> str:
    lines = [
        f"<h1>Sprint Closure: {_escape(sprint.name)}</h1>",
        _sprint_info(sprint),
        _health_dashboard(report),
        _team_summary(report),
    ]
    if report.adhoc_tickets:
        lines.append(_adhoc_table(report.adhoc_tickets, report.adhoc_sp))
    if report.carry_forward:
        lines.append(_carry_forward_table(report.carry_forward))
    if report.overdue:
        lines.append(_overdue_table(report.overdue))
    lines.append(_rovo_section(sprint))
    return "\n".join(lines)


def build_performance_history(history: List[dict]) -> str:
    rows = [
        "<table>",
        "<tr>"
        "<th>Sprint</th><th>Planned SP</th><th>Delivered SP</th>"
        "<th>Ad-hoc SP</th><th>Carry Forward SP</th><th>Delivery %</th>"
        "</tr>",
    ]
    for h in history:
        rows.append(
            "<tr>"
            f"<td>{_escape(h['sprint'])}</td>"
            f"<td>{h['planned_sp']}</td>"
            f"<td>{h['delivered_sp']}</td>"
            f"<td>{h['adhoc_sp']}</td>"
            f"<td>{h['carry_forward_sp']}</td>"
            f"<td>{h['delivery_pct']}%</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def build_hub_index(active_sprint_name: str) -> str:
    return (
        "<h1>Sprint Governance Hub</h1>"
        f"<p>Active Sprint: <strong>{_escape(active_sprint_name)}</strong></p>"
        "<ul>"
        "<li><ac:link><ri:page ri:content-title='Current Sprint'/>"
        "<ac:plain-text-link-body>Current Sprint</ac:plain-text-link-body>"
        "</ac:link></li>"
        "<li><ac:link><ri:page ri:content-title='Sprint Archive'/>"
        "<ac:plain-text-link-body>Sprint Archive</ac:plain-text-link-body>"
        "</ac:link></li>"
        "<li><ac:link><ri:page ri:content-title='Performance Reports'/>"
        "<ac:plain-text-link-body>Performance Reports</ac:plain-text-link-body>"
        "</ac:link></li>"
        "<li><ac:link><ri:page ri:content-title='Executive Dashboard'/>"
        "<ac:plain-text-link-body>Executive Dashboard</ac:plain-text-link-body>"
        "</ac:link></li>"
        "</ul>"
        "<ac:structured-macro ac:name='children'/>"
    )


def _sprint_info(sprint: Sprint) -> str:
    start = sprint.start_date.strftime("%b %d, %Y") if sprint.start_date else "TBD"
    end = sprint.end_date.strftime("%b %d, %Y") if sprint.end_date else "TBD"
    return (
        f"<h1>{_escape(sprint.name)}</h1>"
        f"<p><strong>Start:</strong> {start} &nbsp;|&nbsp; "
        f"<strong>End:</strong> {end}</p>"
        f"<p><strong>Goal:</strong> {_escape(sprint.goal) or '—'}</p>"
    )


def _health_dashboard(report: SprintReport) -> str:
    return (
        "<h2>Sprint Health Dashboard</h2>"
        "<table>"
        "<tr>"
        "<th>Metric</th><th>Planned</th><th>Delivered</th>"
        "<th>Pending</th><th>Delivery %</th>"
        "</tr>"
        "<tr>"
        "<td><strong>Story Points</strong></td>"
        f"<td>{report.total_planned_sp:.1f}</td>"
        f"<td>{report.total_delivered_sp:.1f}</td>"
        f"<td>{report.total_pending_sp:.1f}</td>"
        f"<td>{report.delivery_pct}%</td>"
        "</tr>"
        "<tr>"
        "<td><strong>Tickets</strong></td>"
        f"<td>{report.total_planned_tickets}</td>"
        f"<td>{report.total_delivered_tickets}</td>"
        f"<td>{report.total_pending_tickets}</td>"
        "<td>—</td>"
        "</tr>"
        "</table>"
        f"<p><strong>Final Scope:</strong> {report.final_scope_sp:.1f} SP "
        f"(Planned: {report.total_planned_sp:.1f} + "
        f"Ad-hoc: {report.adhoc_sp:.1f})</p>"
    )


def _delivery_tracker(tickets: List[Ticket]) -> str:
    rows = [
        "<h2>Sprint Delivery Tracker</h2>"
        "<table>"
        "<tr>"
        "<th>Key</th><th>Summary</th><th>Platform</th><th>Team</th>"
        "<th>SP</th><th>Assignee</th><th>Status</th><th>Due Date</th>"
        "</tr>"
    ]
    for t in tickets:
        due = t.due_date.strftime("%b %d") if t.due_date else "—"
        team_str = ", ".join(t.teams) if t.teams else "—"
        rows.append(
            "<tr>"
            f"<td>{_escape(t.key)}</td>"
            f"<td>{_escape(t.summary)}</td>"
            f"<td>{_escape(t.platform)}</td>"
            f"<td>{_escape(team_str)}</td>"
            f"<td>{t.story_points:.1f}</td>"
            f"<td>{_escape(t.assignee or 'Unassigned')}</td>"
            f"<td class='{_status_class(t.status)}'>{_escape(t.status)}</td>"
            f"<td>{due}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def _adhoc_table(tickets: List[Ticket], total_sp: float) -> str:
    rows = [
        "<h2>Ad-hoc Work</h2>"
        f"<p>Total Ad-hoc SP: {total_sp:.1f}</p>"
        "<table>"
        "<tr><th>Key</th><th>Summary</th><th>Team</th>"
        "<th>Assignee</th><th>SP</th><th>Added</th></tr>"
    ]
    for t in tickets:
        added = t.created.strftime("%b %d") if t.created else "—"
        team_str = ", ".join(t.teams) if t.teams else "—"
        rows.append(
            "<tr>"
            f"<td>{_escape(t.key)}</td>"
            f"<td>{_escape(t.summary)}</td>"
            f"<td>{_escape(team_str)}</td>"
            f"<td>{_escape(t.assignee or 'Unassigned')}</td>"
            f"<td>{t.story_points:.1f}</td>"
            f"<td>{added}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def _team_summary(report: SprintReport) -> str:
    rows = [
        "<h2>Team Delivery Summary</h2>"
        "<table>"
        "<tr><th>Team</th><th>Planned SP</th><th>Delivered SP</th>"
        "<th>Pending SP</th><th>Delivery %</th></tr>"
    ]
    for tm in sorted(report.team_metrics.values(), key=lambda x: x.team):
        rows.append(
            "<tr>"
            f"<td><strong>{_escape(tm.team)}</strong></td>"
            f"<td>{tm.planned_sp:.1f}</td>"
            f"<td>{tm.delivered_sp:.1f}</td>"
            f"<td>{tm.pending_sp:.1f}</td>"
            f"<td>{tm.delivery_pct}%</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def _assignee_summary(report: SprintReport) -> str:
    rows = [
        "<h2>Assignee Delivery Summary</h2>"
        "<table>"
        "<tr><th>Assignee</th><th>Planned Tickets</th><th>Delivered Tickets</th>"
        "<th>Planned SP</th><th>Delivered SP</th><th>Pending SP</th></tr>"
    ]
    for am in sorted(
        report.assignee_metrics.values(), key=lambda x: x.assignee
    ):
        rows.append(
            "<tr>"
            f"<td>{_escape(am.assignee)}</td>"
            f"<td>{am.planned_tickets}</td>"
            f"<td>{am.delivered_tickets}</td>"
            f"<td>{am.planned_sp:.1f}</td>"
            f"<td>{am.delivered_sp:.1f}</td>"
            f"<td>{am.pending_sp:.1f}</td>"
            "</tr>"
        )
    rows.append("</table>"
                "<p><em>Note: This data is for sprint governance and delivery tracking only.</em></p>")
    return "\n".join(rows)


def _carry_forward_table(tickets: List[Ticket]) -> str:
    rows = [
        "<h2>Carry Forward</h2>"
        "<table>"
        "<tr><th>Key</th><th>Assignee</th><th>SP</th><th>Status</th></tr>"
    ]
    for t in tickets:
        rows.append(
            "<tr>"
            f"<td>{_escape(t.key)}</td>"
            f"<td>{_escape(t.assignee or 'Unassigned')}</td>"
            f"<td>{t.story_points:.1f}</td>"
            f"<td>{_escape(t.status)}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def _overdue_table(tickets: List[Ticket]) -> str:
    rows = [
        "<h2>Overdue Tickets</h2>"
        "<table>"
        "<tr><th>Key</th><th>Assignee</th><th>SP</th><th>Due Date</th><th>Status</th></tr>"
    ]
    for t in tickets:
        due = t.due_date.strftime("%b %d, %Y") if t.due_date else "—"
        rows.append(
            "<tr>"
            f"<td>{_escape(t.key)}</td>"
            f"<td>{_escape(t.assignee or 'Unassigned')}</td>"
            f"<td>{t.story_points:.1f}</td>"
            f"<td>{due}</td>"
            f"<td>{_escape(t.status)}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)


def _grooming_section() -> str:
    return (
        "<h2>Grooming Status</h2>"
        "<p><em>Update manually during sprint.</em></p>"
        "<table>"
        "<tr><th>Ticket</th><th>Grooming Status</th><th>Remarks</th></tr>"
        "<tr><td>—</td><td>Not Started</td><td>—</td></tr>"
        "</table>"
    )


def _rovo_section(sprint: Sprint) -> str:
    return (
        "<h2>Risks &amp; Blockers</h2>"
        "<p><em>AI-generated summary — Rovo will populate this section.</em></p>"
        "<hr/>"
        "<h2>Key Achievements</h2>"
        "<p><em>AI-generated summary — Rovo will populate this section.</em></p>"
        "<hr/>"
        "<h2>Recommendations</h2>"
        "<p><em>AI-generated summary — Rovo will populate this section.</em></p>"
    )
