from __future__ import annotations
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from celery.result import AsyncResult
from celery.app.control import Control
from django.conf import settings

from users.permissions import HasRole
from users.models import Roles
from metrics.models import Board
from etl.models import ETLJobRun  # created earlier in B-04
from .serializers_admin import (
    RunETLSerializer, StatusQuerySerializer, JobsListQuerySerializer, CancelTaskSerializer
)
from .pipeline import etl_pipeline

# ---------- Run ETL pipeline ----------
class AdminRunETLView(APIView):
    permission_classes = [IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        s = RunETLSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        board_id = s.validated_data["board_id"]
        stages = s.validated_data["stages"]
        mapping_version = s.validated_data["mapping_version"]
        date_iso = s.validated_data.get("date_for_snapshot")
        # ensure board exists
        get_object_or_404(Board, pk=board_id)
        # enqueue
        async_res = etl_pipeline.apply_async(args=[board_id, stages, mapping_version, (date_iso.isoformat() if date_iso else None)])
        return Response({"ok": True, "task_id": async_res.id, "board_id": board_id, "stages": stages}, status=202)

# ---------- Check Celery task status ----------
class AdminETLStatusView(APIView):
    permission_classes = [IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def get(self, request):
        s = StatusQuerySerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        tid = s.validated_data["task_id"]
        ar = AsyncResult(tid)
        # Try to render info safely
        info = None
        try:
            i = ar.info
            if isinstance(i, dict):
                info = {k: (str(v)[:500]) for k, v in i.items()}
            else:
                info = str(i)[:500]
        except Exception:
            info = None
        return Response({"task_id": tid, "state": ar.state, "ready": ar.ready(), "successful": ar.successful(), "info": info})

# ---------- List ETL job runs (DB) ----------
class AdminETLJobsListView(APIView):
    permission_classes = [IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def get(self, request):
        s = JobsListQuerySerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        q = ETLJobRun.objects.all().select_related("board").order_by("-created_at")
        v = s.validated_data
        if v.get("board_id"): q = q.filter(board_id=v["board_id"])
        if v.get("stage"):    q = q.filter(stage__iexact=v["stage"])
        if v.get("status"):   q = q.filter(status__iexact=v["status"])
        total = q.count()
        offset = v["offset"]; limit = v["limit"]
        rows = q[offset: offset+limit]
        def row_dict(r):
            return {
                "id": r.id,
                "board_id": getattr(r.board, "id", None),
                "board": getattr(r.board, "name", None),
                "stage": getattr(r, "stage", None),
                "status": getattr(r, "status", None),
                "task_id": getattr(r, "task_id", None),
                "created_at": getattr(r, "created_at", None),
                "started_at": getattr(r, "started_at", None),
                "finished_at": getattr(r, "finished_at", None),
                "meta": getattr(r, "meta", None),
                "error": getattr(r, "error", None),
            }
        return Response({"total": total, "results": [row_dict(r) for r in rows]})

# ---------- Job detail ----------
class AdminETLJobDetailView(APIView):
    permission_classes = [IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def get(self, request, job_id: int):
        r = get_object_or_404(ETLJobRun.objects.select_related("board"), pk=job_id)
        out = {
            "id": r.id,
            "board_id": getattr(r.board, "id", None),
            "board": getattr(r.board, "name", None),
            "stage": getattr(r, "stage", None),
            "status": getattr(r, "status", None),
            "task_id": getattr(r, "task_id", None),
            "created_at": getattr(r, "created_at", None),
            "started_at": getattr(r, "started_at", None),
            "finished_at": getattr(r, "finished_at", None),
            "meta": getattr(r, "meta", None),
            "error": getattr(r, "error", None),
        }
        # If we have a task_id, include live Celery state too
        if out["task_id"]:
            ar = AsyncResult(out["task_id"])
            out["celery_state"] = ar.state
            try:
                out["celery_info"] = str(ar.info)[:1000]
            except Exception:
                out["celery_info"] = None
        return Response(out)

# ---------- (Optional) cancel/revoke a Celery task ----------
class AdminETLCancelView(APIView):
    permission_classes = [IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        s = CancelTaskSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        tid = s.validated_data["task_id"]
        terminate = s.validated_data["terminate"]
        from celery.task.control import revoke
        try:
            revoke(tid, terminate=terminate, signal="SIGTERM")
            return Response({"ok": True, "task_id": tid, "terminated": terminate})
        except Exception as e:
            return Response({"ok": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
