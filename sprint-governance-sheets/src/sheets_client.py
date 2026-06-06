import json
import os
from typing import List, Optional

import gspread
from google.oauth2.service_account import Credentials

from src.config import AppConfig


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class SheetsClient:
    def __init__(self, config: AppConfig):
        self.config = config
        env_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
        if env_json:
            info = json.loads(env_json)
            self.creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            key_path = config.sheets.service_account_key
            self.creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        self.client = gspread.authorize(self.creds)
        self.spreadsheet = None

    def open_or_create(self, title: str):
        try:
            self.spreadsheet = self.client.open(title)
            return "opened"
        except gspread.SpreadsheetNotFound:
            self.spreadsheet = self.client.create(title)
            return "created"

    def ensure_tab(self, tab_name: str) -> int:
        existing = {ws.title: i for i, ws in enumerate(self.spreadsheet.worksheets())}
        if tab_name in existing:
            ws = self.spreadsheet.worksheet(tab_name)
            ws.clear()
            return existing[tab_name]
        else:
            ws = self.spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=15)
            return len(existing)

    def write_stacked(self, tab_name: str, sections: List[dict]):
        ws = self.spreadsheet.worksheet(tab_name)
        ws.clear()

        rows = []
        bold_ranges = []

        current_row = 1
        for section in sections:
            title = section.get("title")
            headers = section.get("headers", [])
            data = section.get("data", [])

            if title:
                rows.append([title])
                bold_ranges.append((current_row, 1, current_row, len(headers) if headers else 1))
                current_row += 1

            if headers:
                rows.append(headers)
                bold_ranges.append((current_row, 1, current_row, len(headers)))
                current_row += 1

            for row in data:
                rows.append(row)
                current_row += 1

            rows.append([])
            current_row += 1

        if not rows:
            return

        ws.update(rows, value_input_option="USER_ENTERED")

        requests = []
        for r_start, c_start, r_end, c_end in bold_ranges:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": r_start - 1,
                        "endRowIndex": r_end,
                        "startColumnIndex": c_start - 1,
                        "endColumnIndex": c_end,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {
                                "red": 0.9,
                                "green": 0.9,
                                "blue": 0.9,
                            },
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            })

        if requests:
            self.spreadsheet.batch_update({"requests": requests})

    def url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet.id}"
