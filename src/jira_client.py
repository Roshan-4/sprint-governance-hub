import os
import re
from datetime import datetime
from typing import List, Optional

from atlassian import Jira

from src.config import AppConfig
from src.models import Sprint, SprintState, Ticket

PIPE_ESCAPED = "ESCAPED_PIPE_12345"
TJ_PATTERN = re.compile(r"TJ\s*\|\s*Web\s*\|", re.IGNORECASE)
TG_PATTERN = re.compile(r"TG\s*\|\s*Web\s*\|", re.IGNORECASE)


def _jql_escape_pipe(phrase: str) -> str:
    return phrase.replace("|", PIPE_ESCAPED)


def _jql_unescape_pipe(phrase: str) -> str:
    return phrase.replace(PIPE_ESCAPED, "|")


def _detect_platform(summary: str, labels: List[str]) -> str:
    if "TJ_WEB" in labels:
        return "TJ_WEB"
    if "TG_WEB" in labels:
        return "TG_WEB"
    if TJ_PATTERN.search(summary):
        return "TJ_WEB"
    if TG_PATTERN.search(summary):
        return "TG_WEB"
    return ""


class JiraClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.jira = Jira(
            url=config.jira.url,
            username=os.environ["JIRA_EMAIL"],
            password=os.environ["JIRA_API_TOKEN"],
            cloud=True,
        )

    def get_active_sprint(self) -> Optional[Sprint]:
        sprints = self.jira.get_all_sprints_from_board(
            board_id=self.config.jira.primary_board.id,
            state="active",
        )
        values = sprints.get("values", [])
        if not values:
            return None
        s = values[0]
        return Sprint(
            id=s["id"],
            name=s["name"],
            state=SprintState.ACTIVE,
            start_date=self._parse_date(s.get("startDate")),
            end_date=self._parse_date(s.get("endDate")),
            goal=s.get("goal", ""),
        )

    def get_sprint_issues(self, sprint_id: int) -> List[Ticket]:
        jql = (
            f'sprint = {sprint_id} AND '
            f'({self.config.jira.ticket_filters["jql"]})'
        )
        fields = [
            "summary",
            self.config.jira.fields["story_points"],
            "assignee",
            "status",
            "labels",
            "created",
            "duedate",
            "issuetype",
            "parent",
        ]
        tickets = []
        start = 0
        while True:
            result = self.jira.jql(jql, fields=fields, start=start, limit=100)
            issues = result.get("issues", [])
            if not issues:
                break
            for issue in issues:
                ticket = self._parse_ticket(issue)
                if ticket:
                    tickets.append(ticket)
            if len(issues) < 100:
                break
            start += 100
        return tickets

    def get_board_sprints(self, board_id: int, state: str = None) -> List[Sprint]:
        result = self.jira.get_all_sprints_from_board(
            board_id=board_id,
            state=state,
            limit=100,
        )
        sprints = []
        for s in result.get("values", []):
            sprints.append(
                Sprint(
                    id=s["id"],
                    name=s["name"],
                    state=s["state"],
                    start_date=self._parse_date(s.get("startDate")),
                    end_date=self._parse_date(s.get("endDate")),
                    goal=s.get("goal", ""),
                )
            )
        return sprints

    def get_sprint_history(self, max_sprints: int = 50) -> List[Sprint]:
        all_sprints = []
        start = 0
        while True:
            result = self.jira.get_all_sprints_from_board(
                board_id=self.config.jira.primary_board.id,
                state="closed",
                start=start,
                limit=50,
            )
            values = result.get("values", [])
            if not values:
                break
            for s in values:
                if s.get("originBoardId") == self.config.jira.primary_board.id:
                    all_sprints.append(
                        Sprint(
                            id=s["id"],
                            name=s["name"],
                            state=SprintState.CLOSED,
                            start_date=self._parse_date(s.get("startDate")),
                            end_date=self._parse_date(s.get("endDate")),
                            goal=s.get("goal", ""),
                        )
                    )
            if not result.get("isLast", True):
                start += len(values)
            else:
                break
            if len(all_sprints) >= max_sprints:
                break
        return all_sprints

    def get_subtasks_team_labels(self, parent_key: str) -> List[str]:
        jql = f'parent = {parent_key} AND issuetype = Sub-task'
        fields = ["labels", "summary"]
        result = self.jira.jql(jql, fields=fields, limit=50)
        teams = set()
        team_labels = set(self.config.jira.fields["team_labels"])
        for issue in result.get("issues", []):
            labels = issue.get("fields", {}).get("labels", [])
            for label in labels:
                if label in team_labels:
                    teams.add(label)
        return sorted(teams)

    def _parse_ticket(self, issue: dict) -> Optional[Ticket]:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        summary = fields.get("summary", "")
        sp_field = self.config.jira.fields["story_points"]
        story_points = float(fields.get(sp_field) or 0)
        assignee_raw = fields.get("assignee")
        assignee = assignee_raw.get("displayName") if assignee_raw else None
        status = fields.get("status", {}).get("name", "Unknown")
        labels = fields.get("labels", [])
        created = self._parse_date(fields.get("created"))
        due_date = self._parse_date(fields.get("duedate"))
        issuetype = fields.get("issuetype", {}).get("name", "")
        is_subtask = issuetype == "Sub-task"
        parent_raw = fields.get("parent")
        parent_key = parent_raw.get("key") if parent_raw else None
        platform = _detect_platform(summary, labels)

        return Ticket(
            key=key,
            summary=summary,
            story_points=story_points,
            assignee=assignee,
            status=status,
            platform=platform,
            labels=labels,
            created=created,
            due_date=due_date,
            is_subtask=is_subtask,
            parent_key=parent_key,
            teams=[],
        )

    @staticmethod
    def _parse_date(value) -> Optional[datetime]:
        if not value:
            return None
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
        ]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
