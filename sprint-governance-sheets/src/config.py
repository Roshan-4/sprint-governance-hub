from pathlib import Path
from typing import List, Optional, Dict
from pydantic import BaseModel
import yaml


class ConfluenceConfig(BaseModel):
    url: str
    space_key: str
    hub_parent_title: str


class BoardConfig(BaseModel):
    id: int
    name: str


class SheetsConfig(BaseModel):
    spreadsheet_title: str
    spreadsheet_id: str = ""
    service_account_key: str


class JiraConfig(BaseModel):
    url: str
    boards: dict
    projects: List[str]
    ticket_filters: dict
    fields: dict
    done_statuses: List[str]
    adhoc_label: str

    @property
    def primary_board(self) -> BoardConfig:
        b = self.boards.get("primary", {})
        return BoardConfig(**b)


class AppConfig(BaseModel):
    confluence: ConfluenceConfig
    jira: JiraConfig
    sheets: SheetsConfig


def load_config(path: str = "config.yml") -> AppConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return AppConfig(**raw)
