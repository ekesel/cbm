# etl/connectors/github.py
from __future__ import annotations
import time
import datetime as dt
from typing import List, Dict, Any, Optional, Iterable, Tuple

import requests
from django.utils import timezone
from django.conf import settings

from metrics.models import Board
from etl.models import BoardCredential


class GitHubConnector:
    """
    GitHub PR connector (REST v3).
    - Incremental via Search API (PRs updated since ts)
    - PR details via /repos/{owner}/{repo}/pulls/{number}
    - Reviews via /repos/{owner}/{repo}/pulls/{number}/reviews
    Emits:
      { "object_type": "pr", "external_id": "<owner/repo>#<number>", "payload": { "repo":{...}, "pr":{...}, "reviews":[...] } }
    """

    SEARCH_PAGE_SIZE = 100  # max for /search
    REQUESTS_PER_MINUTE_BACKOFF = 60  # crude backoff when rate-limited

    def __init__(self, board: Board):
        if board.source != "github":
            raise ValueError("GitHubConnector only supports boards with source='github'")
        self.board = board
        self.cred: Optional[BoardCredential] = getattr(board, "credential", None)
        if not self.cred:
            raise RuntimeError(f"No credentials found for board {board}")

        self.base = (self.cred.api_base_url or "https://api.github.com").rstrip("/")
        self.session = requests.Session()
        token = self.cred.get_token()
        if not token:
            raise RuntimeError("GitHub credential token is missing")
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self.timeout = (10, 60)

        # resolve repos to scan
        self.org, self.repos = self._resolve_scope()

    # ----------------------------- Public entry ------------------------------
    def fetch_since(self, since_ts: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
        """
        Return list of dicts shaped for RawPayload creation by ETL.
        """
        items: List[Dict[str, Any]] = []
        if not self.repos:
            return items

        for repo in self.repos:
            owner, name = repo.split("/", 1)
            pr_numbers = self._search_pr_numbers_updated_since(owner, name, since_ts)
            for num in pr_numbers:
                pr = self._get_pr(owner, name, num)
                if not pr:
                    continue
                reviews = self._get_reviews(owner, name, num)
                items.append({
                    "object_type": "pr",
                    "external_id": f"{owner}/{name}#{num}",
                    "payload": {
                        "repo": {"owner": owner, "name": name},
                        "pr": pr,
                        "reviews": reviews,
                    }
                })
        return items

    # ----------------------------- Search -----------------------------------
    def _search_pr_numbers_updated_since(self, owner: str, repo: str, since_ts: Optional[dt.datetime]) -> List[int]:
        """
        Use the Search API to find PR numbers updated since ts.
        Query: repo:<owner>/<repo> is:pr updated:>=YYYY-MM-DDTHH:MM:SSZ
        """
        if not since_ts:
            # default small lookback to avoid huge scans
            lookback_days = int(getattr(settings, "GITHUB_LOOKBACK_DAYS", 14))
            since_ts = timezone.now() - dt.timedelta(days=lookback_days)

        ts = self._to_iso_z(since_ts)
        query = f"repo:{owner}/{repo} is:pr updated:>={ts}"
        page = 1
        numbers: List[int] = []

        while True:
            data = self._request_json(
                "GET",
                f"/search/issues",
                params={"q": query, "per_page": self.SEARCH_PAGE_SIZE, "page": page}
            )
            items = data.get("items", [])
            for it in items:
                if it.get("pull_request"):  # ensure it's a PR result
                    # URL like https://api.github.com/repos/<owner>/<repo>/issues/<number>
                    numbers.append(int(it["number"]))
            if len(items) < self.SEARCH_PAGE_SIZE or len(numbers) >= 1000:
                break
            page += 1

        # de-dup and sort ascending (oldest first)
        numbers = sorted(list(set(numbers)))
        return numbers

    # ----------------------------- Details & reviews -------------------------
    def _get_pr(self, owner: str, repo: str, number: int) -> Optional[Dict[str, Any]]:
        return self._request_json("GET", f"/repos/{owner}/{repo}/pulls/{number}")

    def _get_reviews(self, owner: str, repo: str, number: int) -> List[Dict[str, Any]]:
        page = 1
        out: List[Dict[str, Any]] = []
        while True:
            rows = self._request_json(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{number}/reviews",
                params={"per_page": 100, "page": page}
            )
            if not isinstance(rows, list):
                break
            out.extend(rows)
            if len(rows) < 100:
                break
            page += 1
        return out

    # ----------------------------- Helpers -----------------------------------
    def _resolve_scope(self) -> Tuple[Optional[str], List[str]]:
        """
        Returns (org, [owner/repo, ...])
        Priority: meta.repos -> board_id as "owner/repo"
        Optionally meta.org can prefix repos (if repos given without owner).
        """
        meta = self.board.meta or {}
        org = meta.get("org")
        repos = meta.get("repos") or []

        # If repos are given without owner and org is present, prefix
        normalized = []
        for r in repos:
            if "/" in r:
                normalized.append(r)
            elif org:
                normalized.append(f"{org}/{r}")
        if not normalized:
            # fallback to board_id if it looks like owner/repo
            if self.board.board_id and "/" in str(self.board.board_id):
                normalized = [str(self.board.board_id)]
        return org, normalized

    def _to_iso_z(self, ts: dt.datetime) -> str:
        if timezone.is_naive(ts):
            ts = timezone.make_aware(ts, timezone.get_current_timezone())
        return ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _request_json(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json: Any = None):
        url = f"{self.base}{path}"
        while True:
            resp = self.session.request(method, url, params=params, json=json, timeout=self.timeout)
            # Basic rate-limit handling
            if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
                reset = resp.headers.get("X-RateLimit-Reset")
                sleep_for = self.REQUESTS_PER_MINUTE_BACKOFF
                try:
                    if reset:
                        # sleep until reset (seconds since epoch)
                        reset_ts = int(reset)
                        now = int(time.time())
                        sleep_for = max(1, reset_ts - now + 1)
                except Exception:
                    pass
                time.sleep(min(sleep_for, 120))
                continue
            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                detail = ""
                try:
                    detail = f" | body={resp.text[:500]}"
                except Exception:
                    pass
                raise requests.HTTPError(f"GitHub API error {resp.status_code} at {resp.url}{detail}") from e
            data = resp.json()
            return data
