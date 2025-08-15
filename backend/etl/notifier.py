from __future__ import annotations
import datetime as dt
from typing import Dict, Any, List
from django.utils import timezone
from django.conf import settings
from celery import shared_task

from metrics.models import RemediationTicket, RemediationStatus, Board
from .models import NotificationChannel
from .teams import post_teams_card, remediation_card

APP_BASE_URL = getattr(settings, "APP_BASE_URL", "http://localhost:8000/admin/metrics/remediationticket/")

def _should_include(rule: str, channel: NotificationChannel) -> bool:
    rules = channel.rules or []
    return (rule in rules) if rules else True  # empty = all rules

def _collect_for_board(board: Board, channel: NotificationChannel, window_minutes: int = 60) -> Dict[str, Any]:
    """
    Collect newly created or still-open violations (last window) to avoid spam.
    We also include unresolved older ones but summarize them.
    """
    now = timezone.now()
    since = now - dt.timedelta(minutes=window_minutes)

    open_qs = RemediationTicket.objects.filter(board=board).exclude(status=RemediationStatus.DONE)

    # Recently created/updated or never notified
    recent = open_qs.filter(created_at__gte=since) | open_qs.filter(updated_at__gte=since)
    recent = recent.order_by("-created_at")

    grouped: Dict[str, Dict[str, Any]] = {}
    for rt in recent:
        if not _should_include(rt.rule_code, channel): continue
        g = grouped.setdefault(rt.rule_code, {"rule": rt.rule_code, "count": 0, "samples": []})
        g["count"] += 1
        # sample string
        tag = f"{(rt.work_item.source_id if rt.work_item else 'n/a')}"
        if tag not in g["samples"]:
            g["samples"].append(tag)

    # If nothing recent, include a small summary of still-open tickets (top rules)
    if not grouped:
        counts: Dict[str,int] = {}
        for rt in open_qs:
            if not _should_include(rt.rule_code, channel): continue
            counts[rt.rule_code] = counts.get(rt.rule_code, 0) + 1
        for rule, cnt in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]:
            grouped[rule] = {"rule": rule, "count": cnt, "samples": []}

    return grouped

@shared_task(queue="default")
def notify_remediation_tickets(board_id: int | None = None, window_minutes: int = 60) -> int:
    """
    Batch send summaries to Teams per-board for active channels.
    Marks tickets as 'last_notified_at' in meta to reduce noise (best effort).
    """
    boards = Board.objects.filter(id=board_id) if board_id else Board.objects.all()
    sent = 0

    for board in boards:
        channels = NotificationChannel.objects.filter(board=board, is_active=True, channel_type="teams")
        if not channels: continue

        grouped = _collect_for_board(board, channels.first(), window_minutes)  # same content for all channels
        if not grouped: continue

        # Build card
        summary = f"{sum(g['count'] for g in grouped.values())} remediation alert(s)"
        admin_url = f"{APP_BASE_URL}?board__id__exact={board.id}"
        tickets = list(grouped.values())
        payload = remediation_card(board.name, summary, tickets, admin_url=admin_url)

        for ch in channels:
            url = ch.get_webhook()
            if not url: continue
            ok = post_teams_card(url, payload)
            if ok: sent += 1

        # mark meta.last_notified_at on the recent tickets
        now = timezone.now()
        recent_qs = RemediationTicket.objects.filter(board=board).exclude(status=RemediationStatus.DONE).filter(updated_at__gte=now - dt.timedelta(minutes=window_minutes))
        for rt in recent_qs:
            meta = rt.meta or {}
            meta["last_notified_at"] = now.isoformat()
            rt.meta = meta
            rt.save(update_fields=["meta"])
    return sent
