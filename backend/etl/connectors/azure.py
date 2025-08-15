# etl/connectors/azure.py
from __future__ import annotations
import datetime as dt
from typing import List, Dict, Any, Optional, Iterable

import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
from django.utils import timezone

from metrics.models import Board
from etl.models import BoardCredential


class AzureConnector:
    """
    Azure DevOps Boards connector.
    - Incremental Work Items via WIQL on ChangedDate
    - Work Item details via workitemsbatch (chunked)
    - Team Iterations (Sprints) via teamsettings API (optional; requires 'team' in meta)
    Returns objects shaped for RawPayload creation:
      {"object_type": "work_item", "external_id": "<id>", "payload": {...}}
      {"object_type": "iteration", "external_id": "<id>", "payload": {...}}
    """

    def __init__(self, board: Board):
        if board.source != "azure":
            raise ValueError("AzureConnector only supports boards with source='azure'")
        self.board = board
        self.cred: Optional[BoardCredential] = getattr(board, "credential", None)
        if not self.cred:
            raise RuntimeError(f"No credentials found for board {board}")

        self.base = self.cred.api_base_url.rstrip("/")  # e.g., https://dev.azure.com/<org>
        self.session = requests.Session()
        # PAT over Basic: username arbitrary, PAT as password
        self.session.auth = HTTPBasicAuth(self.cred.username or "pat", self.cred.get_token())
        self.session.headers.update({
            "Accept": "application/json;api-version=7.0",
            "Content-Type": "application/json",
        })
        self.timeout = (10, 60)

        # config defaults
        self.fields = getattr(settings, "AZURE_DEFAULT_FIELDS", [
            "System.Id", "System.Title", "System.WorkItemType", "System.State",
            "System.AssignedTo", "System.CreatedDate", "System.ChangedDate",
            "Microsoft.VSTS.Scheduling.StoryPoints",
            "Microsoft.VSTS.Scheduling.OriginalEstimate",
            "Microsoft.VSTS.Scheduling.RemainingWork",
        ])
        self.lookback_days = int(getattr(settings, "AZURE_LOOKBACK_DAYS", 14))
        self.batch_size = int(getattr(settings, "AZURE_BATCH_SIZE", 200))

        # scope
        meta = board.meta or {}
        self.org = meta.get("organization") or self._infer_org_from_base()
        self.project = meta.get("project")
        self.team = meta.get("team")

        if not self.org:
            raise RuntimeError("Azure organization is required (set meta.organization or api_base_url as https://dev.azure.com/<org>)")

    # -----------------------------
    # Public entry point
    # -----------------------------
    def fetch_since(self, since_ts: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        # 1) Work Items (incremental by ChangedDate)
        wi_ids = self._wiql_ids_since(since_ts)
        if wi_ids:
            for batch in self._chunks(wi_ids, self.batch_size):
                workitems = self._get_work_items_batch(batch)
                for wi in workitems:
                    wid = wi.get("id")
                    items.append({
                        "object_type": "work_item",
                        "external_id": str(wid),
                        "payload": wi,
                    })

        # 2) Iterations (sprints) if team known
        if self.project and self.team:
            for it in self._list_iterations(self.project, self.team):
                items.append({
                    "object_type": "iteration",
                    "external_id": str(it.get("id") or it.get("name")),
                    "payload": it,
                })

        return items

    # -----------------------------
    # WIQL & Work Items
    # -----------------------------
    def _wiql_ids_since(self, since_ts: Optional[dt.datetime]) -> List[int]:
        """
        Query by ChangedDate (UTC). If no since_ts, use lookback window.
        """
        if since_ts is None:
            since_ts = timezone.now() - dt.timedelta(days=self.lookback_days)

        changed_iso = self._to_azure_iso(since_ts)

        clauses = [f"[System.ChangedDate] >= '{changed_iso}'"]
        if self.project:
            clauses.insert(0, f"[System.TeamProject] = '{self.project}'")

        query = "SELECT [System.Id] FROM WorkItems WHERE " + " AND ".join(clauses) + " ORDER BY [System.ChangedDate] ASC"
        url = f"{self.base}/{self.org}"
        if self.project:
            url += f"/{self.project}"
        url += "/_apis/wit/wiql?api-version=7.0"

        resp = self.session.post(url, json={"query": query}, timeout=self.timeout)
        self._raise_for_status(resp)
        data = resp.json() or {}
        work_items = data.get("workItems") or []
        return [w.get("id") for w in work_items if w.get("id") is not None]

    def _get_work_items_batch(self, ids: List[int]) -> List[Dict[str, Any]]:
        """
        Use workitemsbatch to retrieve fields in bulk.
        POST {org}/{project}/_apis/wit/workitemsbatch?api-version=7.0
        """
        url = f"{self.base}/{self.org}"
        if self.project:
            url += f"/{self.project}"
        url += "/_apis/wit/workitemsbatch?api-version=7.0"

        payload = {
            "ids": ids,
            "$expand": "Relations",
            "fields": self.fields,
        }
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        self._raise_for_status(resp)
        data = resp.json() or {}
        return data.get("value") or data.get("workItems") or []

    # -----------------------------
    # Iterations (Team Sprints)
    # -----------------------------
    def _list_iterations(self, project: str, team: str) -> List[Dict[str, Any]]:
        """
        GET {org}/{project}/{team}/_apis/work/teamsettings/iterations?api-version=7.0
        Fetch all frames (current, future, past).
        """
        url = f"{self.base}/{self.org}/{project}/{team}/_apis/work/teamsettings/iterations?api-version=7.0"
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code == 404:
            # Team not configured for iterations; skip gracefully
            return []
        self._raise_for_status(resp)
        data = resp.json() or {}
        # 'value' is list of iterations
        return data.get("value") or []

    # -----------------------------
    # Helpers
    # -----------------------------
    def _infer_org_from_base(self) -> Optional[str]:
        # expects base like https://dev.azure.com/<org>
        try:
            parts = self.base.split("/")
            return parts[-1] if parts else None
        except Exception:
            return None

    def _to_azure_iso(self, ts: dt.datetime) -> str:
        # Azure WIQL expects ISO8601 UTC
        if timezone.is_naive(ts):
            ts = timezone.make_aware(ts, timezone.get_current_timezone())
        ts_utc = ts.astimezone(dt.timezone.utc)
        return ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _chunks(self, seq: List[int], size: int) -> Iterable[List[int]]:
        for i in range(0, len(seq), size):
            yield seq[i : i + size]

    def _raise_for_status(self, resp: requests.Response):
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            body = ""
            try:
                body = f" | body={resp.text[:500]}"
            except Exception:
                pass
            raise requests.HTTPError(f"Azure DevOps API error {resp.status_code} at {resp.url}{body}") from e
