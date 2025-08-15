# etl/connectors/jira.py
from __future__ import annotations
import datetime as dt
from typing import List, Dict, Any, Optional, Iterable, Tuple
import requests
from requests.auth import HTTPBasicAuth

from django.utils import timezone
from django.conf import settings

from metrics.models import Board
from etl.models import BoardCredential


class JiraConnector:
    """
    Jira Cloud/Server connector.
    Supports:
      - Incremental issue fetch via JQL 'updated >= "<ISO>"'
      - Sprint list via Agile API (if board_id is numeric Agile board id)
    Returns items in the ETL-orchestration format:
      [{ "object_type": "issue", "external_id": "<key>", "payload": {...}}, ...]
      [{ "object_type": "sprint", "external_id": "<id>",  "payload": {...}}, ...]
    """

    ISSUE_PAGE_SIZE = 100
    # Default fields to request from /rest/api/3/search
    DEFAULT_FIELDS = getattr(settings, "JIRA_DEFAULT_FIELDS", [
        "summary", "issuetype", "status", "assignee", "reporter", "created",
        "updated", "resolutiondate", "customfield_10016",  # Story Points for many Jira Cloud instances
        "parent", "labels", "priority", "project", "sprint", "fixVersions"
    ])
    DEFAULT_EXPAND = getattr(settings, "JIRA_DEFAULT_EXPAND", ["changelog"])

    def __init__(self, board: Board):
        if board.source != "jira":
            raise ValueError("JiraConnector only supports boards with source='jira'")
        self.board = board
        self.cred: Optional[BoardCredential] = getattr(board, "credential", None)
        if not self.cred:
            raise RuntimeError(f"No credentials found for board {board}")

        self.base = self.cred.api_base_url.rstrip("/")
        self.session = requests.Session()
        if self.cred.auth_type == "pat":
            self.session.auth = HTTPBasicAuth(self.cred.username or "", self.cred.get_token())
        else:
            # Extend for OAuth if needed
            self.session.auth = HTTPBasicAuth(self.cred.username or "", self.cred.get_token())

        # Timeouts & headers
        self.session.headers.update({
            "Accept": "application/json"
        })
        self.timeout = (10, 60)  # (connect, read)

    # -----------------------------
    # Public API (used by ETL tasks)
    # -----------------------------
    def fetch_since(self, since_ts: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch issues updated since 'since_ts' + sprints for the board (if board_id numeric).
        Returns a list of dicts suitable for RawPayload creation by the ETL task.
        """
        items: List[Dict[str, Any]] = []

        # 1) Issues (JQL incremental)
        jql, using_project = self._build_incremental_jql(since_ts)
        for issue in self._search_issues_paginated(jql=jql, fields=self.DEFAULT_FIELDS, expand=self.DEFAULT_EXPAND):
            key = issue.get("key") or issue.get("id")
            items.append({
                "object_type": "issue",
                "external_id": str(key),
                "payload": issue,
            })

        # 2) Sprints (if we have a numeric Agile board id)
        if self._is_numeric_board_id(self.board.board_id):
            for sprint in self._list_sprints(board_id=int(self.board.board_id)):
                items.append({
                    "object_type": "sprint",
                    "external_id": str(sprint.get("id")),
                    "payload": sprint,
                })

        return items

    # -----------------------------
    # Issue search helpers
    # -----------------------------
    def _build_incremental_jql(self, since_ts: Optional[dt.datetime]) -> Tuple[str, bool]:
        """
        Build JQL for incremental sync.
        If Board.meta['project_key'] is set, or board_id looks like a KEY (not numeric), use project scope.
        Otherwise, fall back to updated >= without project filter (works but heavier).
        Returns (jql, using_project_scope)
        """
        # Format Jira datetime string: "YYYY/MM/DD HH:MM"
        def fmt(ts: dt.datetime) -> str:
            # ensure timezone-aware, convert to UTC for Jira
            if timezone.is_naive(ts):
                ts = timezone.make_aware(ts, timezone.get_current_timezone())
            ts_utc = ts.astimezone(dt.timezone.utc)
            return ts_utc.strftime("%Y/%m/%d %H:%M")

        updated_clause = f'updated >= "{fmt(since_ts)}"' if since_ts else None

        project_key = (self.board.meta or {}).get("project_key")
        if not project_key and not self._is_numeric_board_id(self.board.board_id):
            # likely a project key in board_id
            project_key = self.board.board_id

        clauses = []
        if project_key:
            clauses.append(f'project = "{project_key}"')
        if updated_clause:
            clauses.append(updated_clause)

        jql = " AND ".join(clauses) if clauses else (updated_clause or "order by updated desc")
        return jql, bool(project_key)

    def _search_issues_paginated(self, jql: str, fields: Iterable[str], expand: Iterable[str]) -> Iterable[Dict[str, Any]]:
        start_at = 0
        while True:
            batch = self._search_issues(jql=jql, fields=fields, expand=expand, start_at=start_at, max_results=self.ISSUE_PAGE_SIZE)
            issues = batch.get("issues", [])
            for it in issues:
                yield it
            if len(issues) < self.ISSUE_PAGE_SIZE:
                break
            start_at += self.ISSUE_PAGE_SIZE

    def _search_issues(self, jql: str, fields: Iterable[str], expand: Iterable[str], start_at: int, max_results: int) -> Dict[str, Any]:
        url = f"{self.base}/rest/api/3/search"
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": ",".join(fields) if fields else None,
            "expand": ",".join(expand) if expand else None,
        }
        resp = self.session.get(url, params=params, timeout=self.timeout)
        self._raise_for_status(resp)
        return resp.json()

    # -----------------------------
    # Sprints (Agile API)
    # -----------------------------
    def _list_sprints(self, board_id: int) -> List[Dict[str, Any]]:
        """
        List sprints for an Agile board (Scrum/Kanban). Paginates until done.
        GET /rest/agile/1.0/board/{boardId}/sprint
        """
        url = f"{self.base}/rest/agile/1.0/board/{board_id}/sprint"
        start_at = 0
        per_page = 50
        all_rows: List[Dict[str, Any]] = []

        while True:
            params = {"startAt": start_at, "maxResults": per_page, "state": "active,future,closed"}
            resp = self.session.get(url, params=params, timeout=self.timeout)
            self._raise_for_status(resp)
            data = resp.json() or {}
            values = data.get("values", [])
            all_rows.extend(values)
            if len(values) < per_page:
                break
            start_at += per_page

        return all_rows

    # -----------------------------
    # Utils
    # -----------------------------
    def _is_numeric_board_id(self, value: str) -> bool:
        try:
            int(value)
            return True
        except (TypeError, ValueError):
            return False

    def _raise_for_status(self, resp: requests.Response):
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = f" | body={resp.text[:500]}"
            except Exception:
                pass
            raise requests.HTTPError(f"Jira API error {resp.status_code} at {resp.url}{detail}") from e
