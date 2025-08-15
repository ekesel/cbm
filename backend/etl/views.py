from rest_framework import viewsets
from users.permissions import HasRole
from users.models import Roles
from .models import MappingVersion, BoardCredential, NotificationChannel, MappingVersion
from .serializers import MappingVersionSerializer, BoardCredentialSerializer, NotificationChannelSerializer
from .raw_storage import offload_rawpayloads, rawpayload_retention
from rest_framework.views import APIView
from rest_framework.response import Response
from .tasks import run_etl_for_board, run_all_boards, etl_validate
from .notifier import notify_remediation_tickets
from .mapping_validator import validate_mapping_config
from .snapshotter import run_daily_snapshot
from .sla import sla_check_blocked, backfill_blocked_since


class MappingVersionViewSet(viewsets.ModelViewSet):
    queryset = MappingVersion.objects.all().order_by("-created_at")
    serializer_class = MappingVersionSerializer
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

class BoardCredentialViewSet(viewsets.ModelViewSet):
    queryset = BoardCredential.objects.select_related("board").all().order_by("-updated_at")
    serializer_class = BoardCredentialSerializer
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}


class ETLTriggerView(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        board_id = request.data.get("board_id")
        mapping_version = request.data.get("mapping_version", "v1")
        if board_id:
            run_etl_for_board.delay(int(board_id), mapping_version=mapping_version)
            return Response({"ok": True, "message": f"ETL started for board {board_id}"})
        else:
            count = run_all_boards.delay(mapping_version=mapping_version)
            return Response({"ok": True, "message": "ETL started for all boards"})
        
        
class RawStorageOpsView(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        board_id = request.data.get("board_id")
        op = request.data.get("op", "offload")
        if op == "offload":
            offload_rawpayloads.delay(int(board_id)) if board_id else offload_rawpayloads.delay()
            return Response({"ok": True, "message": "Offload started"})
        if op == "retention":
            rawpayload_retention.delay(int(board_id)) if board_id else rawpayload_retention.delay()
            return Response({"ok": True, "message": "Retention started"})
        return Response({"ok": False, "error": "Unknown op"}, status=400)
    
    
class ValidatorTriggerView(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        board_id = int(request.data.get("board_id"))
        etl_validate.delay(board_id)
        return Response({"ok": True, "message": f"Validation started for board {board_id}"})
    

class NotificationChannelViewSet(viewsets.ModelViewSet):
    queryset = NotificationChannel.objects.select_related("board").all().order_by("board__name","name")
    serializer_class = NotificationChannelSerializer
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}
    

class RemediationNotifyTriggerView(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        board_id = request.data.get("board_id")
        window = int(request.data.get("window_minutes", 60))
        if board_id:
            notify_remediation_tickets.delay(int(board_id), window)
        else:
            notify_remediation_tickets.delay(None, window)
        return Response({"ok": True, "message": "Notifier started"})
    
class MappingMatrixValidateView(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        """
        POST body:
          { "config": { ... }, "save": false }
        If save=true and validation passes (no errors), persists to the active MappingVersion.config
        """
        payload = request.data or {}
        cfg = payload.get("config") or {}
        save = bool(payload.get("save", False))

        result = validate_mapping_config(cfg)
        if save and result["ok"]:
            mv = MappingVersion.objects.filter(active=True).order_by("-created_at").first()
            if not mv:
                return Response({"ok": False, "errors": [{"path":"mapping","msg":"No active MappingVersion"}]}, status=400)
            mv.config = result["normalized"]
            mv.save(update_fields=["config"])
        status_code = 200 if result["ok"] else 400
        return Response(result, status=status_code)
    
    
class SnapshotTriggerView(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def post(self, request):
        board_id = request.data.get("board_id")
        date_iso = request.data.get("date")
        run_daily_snapshot.delay(int(board_id)) if board_id else run_daily_snapshot.delay(None, date_iso)
        return Response({"ok": True, "message": "Snapshot job enqueued"})
    
    

class SLABlockedCheckTrigger(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}
    def post(self, request):
        board_id = request.data.get("board_id")
        sla_check_blocked.delay(int(board_id)) if board_id else sla_check_blocked.delay()
        return Response({"ok": True})

class SLABlockedBackfillTrigger(APIView):
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}
    def post(self, request):
        board_id = request.data.get("board_id")
        backfill_blocked_since.delay(int(board_id)) if board_id else backfill_blocked_since.delay()
        return Response({"ok": True})