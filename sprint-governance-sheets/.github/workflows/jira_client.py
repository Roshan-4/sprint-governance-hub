import os
import re
from datetime import datetime
from typing import List, Optional

from atlassian import Jira

from src.config import AppConfig
from src.models import Sprint, SprintState, Ticket

TJ_PATTERN = re.compile(r"TJ\s*\|\s*Web\s*\|", re.IGNORECASE)
TG_PATTERN = re.compile(r"TG\s*\|\s*Web\s*\|", re.IGNORECASE)
PARENT_TYPES = {"Task", "Story", "Bug", "Improvement", "Production Bug", "New Feature"}
EPIC_TYPE = "Epic"
SUBTASK_TYPE = "Sub-task"


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
        jql_parents = (
            f'sprint = {sprint_id} AND '
            f'({self.config.jira.ticket_filters["jql"]}) AND '
            f'issuetype NOT IN (Epic, Sub-task)'
        )
        parent_fields = [
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

        parent_issues = self._jql_search(jql_parents, parent_fields)

        jql_epics = (
            f'sprint = {sprint_id} AND '
            f'({self.config.jira.ticket_filters["jql"]}) AND '
            f'issuetype = Epic'
        )
        epic_issues = self._jql_search(jql_epics, parent_fields)

        sub_fields = [
            "summary",
            self.config.jira.fields["story_points"],
            "labels",
            "issuetype",
            "status",
            "created",
            "duedate",
            "parent",
        ]

        team_labels = set(self.config.jira.fields["team_labels"])
        tickets = []
        processed_keys = set()
        for parent_issue in parent_issues:
            parent_key = parent_issue["key"]

            r = self.jira.enhanced_jql(
                f'parent = {parent_key}',
                fields=sub_fields,
                limit=100,
            )
            sub_issues = r.get("issues", [])

            sub_sp = 0.0
            sub_teams = set()
            for si in sub_issues:
                sf = si["fields"]
                sub_sp += float(sf.get(self.config.jira.fields["story_points"]) or 0)
                for label in sf.get("labels", []):
                    if label in team_labels:
                        sub_teams.add(label)

            ticket = self._parse_ticket(
                parent_issue,
                story_points_override=sub_sp,
                teams_override=sorted(sub_teams),
            )
            if ticket:
                tickets.append(ticket)
                processed_keys.add(parent_key)

        for epic_issue in epic_issues:
            epic_key = epic_issue["key"]
            r = self.jira.enhanced_jql(
                f'parent = {epic_key}',
                fields=sub_fields,
                limit=100,
            )
            sub_issues = r.get("issues", [])
            for si in sub_issues:
                if si["key"] in processed_keys:
                    continue
                sf = si["fields"]
                sub_teams = set()
                for label in sf.get("labels", []):
                    if label in team_labels:
                        sub_teams.add(label)
                ticket = self._parse_ticket(
                    si,
                    teams_override=sorted(sub_teams),
                )
                if ticket:
                    tickets.append(ticket)

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
        board_id = self.config.jira.primary_board.id
        while True:
            result = self.jira.get_all_sprints_from_board(
                board_id=board_id,
                state="closed",
                start=start,
                limit=50,
            )
            values = result.get("values", [])
            if not values:
                break
            for s in values:
                if s.get("originBoardId") == board_id:
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

    def get_history_sprint_issues(self, sprint_id: int) -> List[Ticket]:
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
        all_issues = self._jql_search(jql, fields)
        parents = {}
        subtask_map = {}

        for issue in all_issues:
            itype = issue["fields"]["issuetype"]["name"]
            if itype == EPIC_TYPE:
                continue
            if itype == SUBTASK_TYPE:
                parent_raw = issue["fields"].get("parent")
                parent_key = parent_raw["key"] if parent_raw else None
                if parent_key:
                    subtask_map.setdefault(parent_key, []).append(issue)
                continue
            if itype in PARENT_TYPES:
                parents[issue["key"]] = issue

        tickets = []
        for parent_key, parent_issue in parents.items():
            f = parent_issue["fields"]
            sp_field = self.config.jira.fields["story_points"]
            sub_issues = subtask_map.get(parent_key, [])
            sub_sp = sum(
                float(si["fields"].get(sp_field) or 0) for si in sub_issues
            )
            ticket = self._parse_ticket(
                parent_issue, story_points_override=sub_sp
            )
            if ticket:
                tickets.append(ticket)
        return tickets

    def _jql_search(self, jql: str, fields: List[str]) -> list:
        issues = []
        next_token = None
        while True:
            result = self.jira.enhanced_jql(
                jql, fields=fields, nextPageToken=next_token, limit=100
            )
            chunk = result.get("issues", [])
            if not chunk:
                break
            issues.extend(chunk)
            next_token = result.get("nextPageToken")
            if not next_token:
                break
        return issues

    def _parse_ticket(
        self,
        issue: dict,
        story_points_override: Optional[float] = None,
        teams_override: Optional[List[str]] = None,
    ) -> Optional[Ticket]:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        summary = fields.get("summary", "")
        story_points = (
            story_points_override
            if story_points_override is not None
            else float(fields.get(self.config.jira.fields["story_points"]) or 0)
        )
        assignee_raw = fields.get("assignee")
        assignee = assignee_raw.get("displayName") if assignee_raw else None
        status = fields.get("status", {}).get("name", "Unknown")
        labels = fields.get("labels", [])
        created = self._parse_date(fields.get("created"))
        due_date = self._parse_date(fields.get("duedate"))
        issuetype = fields.get("issuetype", {}).get("name", "")
        is_subtask = issuetype == SUBTASK_TYPE
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
            issuetype=issuetype,
            teams=teams_override or [],
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
