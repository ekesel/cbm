# etl/connectors/clickup.py
from __future__ import annotations
import time
import datetime as dt
from typing import List, Dict, Any, Optional, Iterable, Tuple

import requests
from django.utils import timezone

from metrics.models import Board
from etl.models import BoardCredential


class ClickUpConnector:
    """
    ClickUp connector (API v2).
    Supports incremental task fetch using `date_updated_gt` (ms since epoch).
    Returns items in the ETL-orchestration format expected by etl.tasks.etl_fetch_raw:
      [{ "object_type": "task", "external_id": "<task_id>", "payload": {...}}, ...]
    """

    PAGE_LIMIT = 100

    def __init__(self, board: Board):
        if board.source != "clickup":
            raise ValueError("ClickUpConnector only supports boards with source='clickup'")
        self.board = board
        self.cred: Optional[BoardCredential] = getattr(board, "credential", None)
        if not self.cred:
            raise RuntimeError(f"No credentials found for board {board}")

        self.base = (self.cred.api_base_url or "https://api.clickup.com/api/v2").rstrip("/")
        self.session = requests.Session()
        token = self.cred.get_token()
        if not token:
            raise RuntimeError("ClickUp credential token is missing")
        self.session.headers.update({
            "Authorization": token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self.timeout = (10, 60)  # (connect, read)

    # -----------------------------
    # Public entry point
    # -----------------------------
    def fetch_since(self, since_ts: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        scope_type, scope_id = self._resolve_scope()
        for task in self._list_tasks(scope_type=scope_type, scope_id=scope_id, since_ts=since_ts):
            items.append({
                "object_type": "task",
                "external_id": str(task.get("id") or ""),
                "payload": task,
            })

        # (Optional) You could add list/folder metadata fetches here if needed
        return items

    # -----------------------------
    # Core: list tasks (paginated)
    # -----------------------------
    def _list_tasks(self, scope_type: str, scope_id: str, since_ts: Optional[dt.datetime]) -> Iterable[Dict[str, Any]]:
        """
        Paginates over tasks for a given scope.
        Supports scopes: list, folder, space, team (workspace).
        """
        page = 0
        while True:
            url = self._tasks_url(scope_type, scope_id)
            params = {
                "page": page,
                "limit": self.PAGE_LIMIT,
                "include_subtasks": "true",
                "subtasks": "true",
                "archived": "false",
                "include_closed": "true",
                "order_by": "updated",
                "reverse": "false",
                "custom_fields": "true",
            }
            if since_ts:
                params["date_updated_gt"] = str(self._to_ms_since_epoch(since_ts))

            resp = self.session.get(url, params=params, timeout=self.timeout)
            self._raise_for_status(resp)
            data = resp.json() or {}
            rows = data.get("tasks", []) or data.get("items", []) or []

            for row in rows:
                yield row

            # Stop when < limit returned (ClickUp pagination)
            if len(rows) < self.PAGE_LIMIT:
                break
            page += 1

    # -----------------------------
    # Helpers
    # -----------------------------
    def _resolve_scope(self) -> Tuple[str, str]:
        """
        Determine ClickUp scope from Board.meta or board_id.
        Priority: list_id > folder_id > space_id > team_id > board.board_id as list_id
        """
        meta = self.board.meta or {}
        if meta.get("list_id"):
            return "list", str(meta["list_id"])
        if meta.get("folder_id"):
            return "folder", str(meta["folder_id"])
        if meta.get("space_id"):
            return "space", str(meta["space_id"])
        if meta.get("team_id"):
            return "team", str(meta["team_id"])
        # fallback: treat board_id as list_id
        return "list", str(self.board.board_id)

    def _tasks_url(self, scope_type: str, scope_id: str) -> str:
        if scope_type == "list":
            return f"{self.base}/list/{scope_id}/task"
        if scope_type == "folder":
            return f"{self.base}/folder/{scope_id}/task"
        if scope_type == "space":
            return f"{self.base}/space/{scope_id}/task"
        if scope_type == "team":
            return f"{self.base}/team/{scope_id}/task"
        raise NotImplementedError(f"Unsupported ClickUp scope_type={scope_type}")

    def _to_ms_since_epoch(self, ts: dt.datetime) -> int:
        if timezone.is_naive(ts):
            ts = timezone.make_aware(ts, timezone.get_current_timezone())
        ms = int(ts.timestamp() * 1000)
        # ClickUp docs often recommend +1ms to avoid duplicates on same timestamp
        return ms + 1

    def _raise_for_status(self, resp: requests.Response):
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = f" | body={resp.text[:500]}"
            except Exception:
                pass
            raise requests.HTTPError(f"ClickUp API error {resp.status_code} at {resp.url}{detail}") from e
