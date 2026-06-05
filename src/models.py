from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel
from enum import Enum


class SprintState(str, Enum):
    ACTIVE = "active"
    FUTURE = "future"
    CLOSED = "closed"


class Sprint(BaseModel):
    id: int
    name: str
    state: SprintState
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    goal: str = ""


class Ticket(BaseModel):
    key: str
    summary: str
    story_points: float = 0.0
    assignee: Optional[str] = None
    status: str
    platform: str = ""  # TJ_WEB or TG_WEB
    labels: List[str] = []
    created: Optional[datetime] = None
    due_date: Optional[datetime] = None
    is_subtask: bool = False
    parent_key: Optional[str] = None
    teams: List[str] = []  # UI, DEV, QA, SEO — derived from sub-tasks


class TeamMetrics(BaseModel):
    team: str
    planned_sp: float = 0.0
    delivered_sp: float = 0.0
    pending_sp: float = 0.0

    @property
    def delivery_pct(self) -> float:
        if self.planned_sp == 0:
            return 0.0
        return round((self.delivered_sp / self.planned_sp) * 100, 1)


class AssigneeMetrics(BaseModel):
    assignee: str
    planned_tickets: int = 0
    delivered_tickets: int = 0
    planned_sp: float = 0.0
    delivered_sp: float = 0.0
    pending_sp: float = 0.0


class SprintReport(BaseModel):
    sprint: Sprint
    total_planned_sp: float = 0.0
    total_delivered_sp: float = 0.0
    total_pending_sp: float = 0.0
    total_planned_tickets: int = 0
    total_delivered_tickets: int = 0
    total_pending_tickets: int = 0
    adhoc_sp: float = 0.0
    adhoc_tickets: List[Ticket] = []
    carry_forward: List[Ticket] = []
    overdue: List[Ticket] = []
    team_metrics: Dict[str, TeamMetrics] = {}
    assignee_metrics: Dict[str, AssigneeMetrics] = {}
    tickets: List[Ticket] = []

    @property
    def delivery_pct(self) -> float:
        if self.total_planned_sp == 0:
            return 0.0
        return round((self.total_delivered_sp / self.total_planned_sp) * 100, 1)

    @property
    def final_scope_sp(self) -> float:
        return self.total_planned_sp + self.adhoc_sp
