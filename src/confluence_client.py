import os
from typing import Optional

from atlassian import Confluence

from src.config import AppConfig


class ConfluenceClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.confluence = Confluence(
            url=config.confluence.url,
            username=os.environ["CONFLUENCE_USERNAME"],
            password=os.environ["CONFLUENCE_API_TOKEN"],
            cloud=True,
        )
        self.space_key = config.confluence.space_key

    def get_page_id(self, title: Optional[str] = None) -> Optional[int]:
        title = title or self.config.confluence.hub_parent_title
        result = self.confluence.get_page_by_title(
            space=self.space_key, title=title
        )
        if result:
            return result.get("id")
        return None

    def create_page(
        self, title: str, body: str, parent_id: Optional[int] = None
    ) -> int:
        result = self.confluence.create_page(
            space=self.space_key,
            title=title,
            body=body,
            parent_id=parent_id,
            representation="storage",
        )
        return result["id"]

    def update_page(
        self, page_id: int, title: str, body: str
    ) -> None:
        self.confluence.update_page(
            page_id=page_id,
            title=title,
            body=body,
            representation="storage",
        )

    def find_or_create_hierarchy(
        self, parent_title: str, children: list
    ) -> dict:
        parent_id = self.get_page_id(parent_title)
        if not parent_id:
            parent_id = self.create_page(
                title=parent_title,
                body=self._hub_index_body(),
            )
        hierarchy = {"parent_id": parent_id, "children": {}}
        for child_title in children:
            child_id = self.get_page_id(child_title)
            hierarchy["children"][child_title] = child_id
        return hierarchy

    def page_exists(self, title: str) -> bool:
        return self.get_page_id(title) is not None

    def get_child_pages(self, parent_id: int) -> list:
        return self.confluence.get_child_pages(parent_id) or []

    def _hub_index_body(self) -> str:
        return (
            "<h1>Sprint Governance Hub</h1>"
            "<p>Welcome to the centralized Sprint Governance &amp; Delivery Analytics Hub.</p>"
            "<ul>"
            "<li><a href='#current'>Current Sprint</a></li>"
            "<li><a href='#archive'>Sprint Archive</a></li>"
            "<li><a href='#performance'>Performance Reports</a></li>"
            "<li><a href='#executive'>Executive Dashboard</a></li>"
            "</ul>"
            "<ac:structured-macro ac:name='children'/>"
        )
