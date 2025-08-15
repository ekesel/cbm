from __future__ import annotations
from datetime import datetime, timedelta, timezone as pytz
from collections import defaultdict

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Q
from django.utils import timezone

from users.permissions import HasRole
from users.models import Roles
from .models import RemediationTicket, RemediationStatus
from .serializers_remediation import (
    RemediationTicketSerializer, RemediationTicketUpdateSerializer,
    RemediationTicketBulkActionSerializer, ComplianceQuerySerializer
)
from .filters_remediation import RemediationTicketFilter

# ---------- List & detail ----------
class RemediationTicketListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RemediationTicketSerializer
    filterset_class = RemediationTicketFilter
    search_fields = ["message", "rule_code", "owner"]
    ordering_fields = ["created_at","updated_at","resolved_at","rule_code","status","owner"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        return RemediationTicket.objects.select_related("board","work_item").all().order_by("-updated_at")

class RemediationTicketDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RemediationTicketSerializer
    queryset = RemediationTicket.objects.select_related("board","work_item").all()

# ---------- Update single ----------
class RemediationTicketUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def patch(self, request, pk: int):
        try:
            rt = RemediationTicket.objects.get(pk=pk)
        except RemediationTicket.DoesNotExist:
            return Response({"error":"Not found"}, status=404)

        s = RemediationTicketUpdateSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        changed = False
        if "status" in data and data["status"]:
            rt.status = data["status"]; changed = True
            if rt.status == RemediationStatus.DONE:
                rt.resolved_at = timezone.now()
        if "owner" in data:
            rt.owner = data["owner"] or None; changed = True
        if "message" in data:
            rt.message = data["message"]; changed = True
        if "snoozed_until" in data:
            rt.snoozed_until = data["snoozed_until"]; changed = True
        if "append_note" in data and data["append_note"] is not None:
            meta = rt.meta or {}
            notes = list(meta.get("notes") or [])
            notes.append({"at": timezone.now().isoformat(), "by": str(request.user), "text": data["append_note"]})
            meta["notes"] = notes
            rt.meta = meta
            changed = True

        if changed:
            rt.save()
        return Response(RemediationTicketSerializer(rt).data)

# ---------- Bulk actions ----------
class RemediationTicketBulkActionView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        s = RemediationTicketBulkActionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ids = s.validated_data["ids"]
        action = s.validated_data["action"]
        owner = s.validated_data.get("owner")
        note = s.validated_data.get("note")
        snoozed_until = s.validated_data.get("snoozed_until")

        qs = RemediationTicket.objects.filter(id__in=ids)
        n = 0
        now = timezone.now()

        for rt in qs:
            if action == "ack":
                if not rt.acknowledged_at:
                    rt.acknowledged_at = now
                if owner: rt.owner = owner
            elif action == "resolve":
                rt.status = RemediationStatus.DONE
                rt.resolved_at = now
            elif action == "assign":
                rt.owner = owner
            elif action == "snooze":
                rt.snoozed_until = snoozed_until
            elif action == "note":
                meta = rt.meta or {}
                notes = list(meta.get("notes") or [])
                if note:
                    notes.append({"at": now.isoformat(), "by": str(request.user), "text": note})
                meta["notes"] = notes
                rt.meta = meta
            elif action == "reopen":
                rt.status = RemediationStatus.OPEN
                rt.resolved_at = None
            else:
                continue
            rt.save()
            n += 1

        return Response({"ok": True, "updated": n})

# ---------- Compliance summary ----------
class ComplianceSummaryView(APIView):
    """
    GET board compliance snapshot (open tickets) + aging buckets and rule breakdown.
    Optional window: start/end filter by created_at for trend views.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        s = ComplianceQuerySerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        board_id = s.validated_data["board_id"]
        start = s.validated_data.get("start")
        end = s.validated_data.get("end")

        base = RemediationTicket.objects.filter(board_id=board_id)
        if start: base = base.filter(created_at__date__gte=start)
        if end:   base = base.filter(created_at__date__lte=end)

        # Only consider unresolved for compliance status; also return totals
        open_q = base.exclude(status=RemediationStatus.DONE)

        total_open = open_q.count()
        by_rule = (open_q.values("rule_code")
                          .annotate(count=Count("id"))
                          .order_by("-count","rule_code"))

        # Aging buckets based on created_at (days)
        now = timezone.now()
        buckets = {"0_2d":0, "3_5d":0, "6_10d":0, "gt_10d":0}
        for r in open_q.only("created_at"):
            age_days = ((now - r.created_at).total_seconds()) / 86400.0 if r.created_at else 0
            if age_days <= 2: buckets["0_2d"] += 1
            elif age_days <= 5: buckets["3_5d"] += 1
            elif age_days <= 10: buckets["6_10d"] += 1
            else: buckets["gt_10d"] += 1

        # Current “silenced” items (snoozed future)
        silenced = open_q.filter(snoozed_until__isnull=False, snoozed_until__gt=now).count()

        # Recently resolved (past 7d) for momentum
        recent_resolved = base.filter(status=RemediationStatus.DONE, resolved_at__gte=now - timedelta(days=7)).count()

        return Response({
            "board_id": board_id,
            "total_open": total_open,
            "by_rule": [{"rule_code": r["rule_code"], "count": r["count"]} for r in by_rule],
            "aging_buckets": buckets,
            "silenced_open": silenced,
            "recent_resolved_7d": recent_resolved
        })
