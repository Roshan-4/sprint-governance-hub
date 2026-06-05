from datetime import datetime
from typing import Dict, List

from src.config import AppConfig
from src.models import (
    AssigneeMetrics,
    Sprint,
    SprintReport,
    TeamMetrics,
    Ticket,
)


class AnalyticsEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self.done_statuses = set(config.jira.done_statuses)
        self.adhoc_label = config.jira.adhoc_label

    def compute(self, sprint: Sprint, tickets: List[Ticket]) -> SprintReport:
        report = SprintReport(sprint=sprint, tickets=tickets)

        for ticket in tickets:
            is_done = ticket.status in self.done_statuses
            is_adhoc = self._is_adhoc(ticket, sprint)

            if is_adhoc:
                report.adhoc_sp += ticket.story_points
                report.adhoc_tickets.append(ticket)

            if is_done:
                report.total_delivered_sp += ticket.story_points
                report.total_delivered_tickets += 1
            else:
                report.total_pending_sp += ticket.story_points
                report.total_pending_tickets += 1

            report.total_planned_sp += ticket.story_points
            report.total_planned_tickets += 1

            if ticket.due_date and ticket.due_date < datetime.now(
                ticket.due_date.tzinfo
            ) and not is_done:
                report.overdue.append(ticket)

            if not is_done:
                report.carry_forward.append(ticket)

            self._accumulate_team_metrics(report, ticket, is_done)
            self._accumulate_assignee_metrics(report, ticket, is_done)

        return report

    def _is_adhoc(self, ticket: Ticket, sprint: Sprint) -> bool:
        if self.adhoc_label and self.adhoc_label in ticket.labels:
            return True
        if sprint.start_date and ticket.created:
            if ticket.created > sprint.start_date:
                return True
        return False

    def _accumulate_team_metrics(
        self, report: SprintReport, ticket: Ticket, is_done: bool
    ):
        for team in ticket.teams:
            if team not in report.team_metrics:
                report.team_metrics[team] = TeamMetrics(team=team)
            tm = report.team_metrics[team]
            tm.planned_sp += ticket.story_points
            if is_done:
                tm.delivered_sp += ticket.story_points
            else:
                tm.pending_sp += ticket.story_points

    def _accumulate_assignee_metrics(
        self, report: SprintReport, ticket: Ticket, is_done: bool
    ):
        name = ticket.assignee or "Unassigned"
        if name not in report.assignee_metrics:
            report.assignee_metrics[name] = AssigneeMetrics(assignee=name)
        am = report.assignee_metrics[name]
        am.planned_tickets += 1
        am.planned_sp += ticket.story_points
        if is_done:
            am.delivered_tickets += 1
            am.delivered_sp += ticket.story_points
        else:
            am.pending_sp += ticket.story_points
