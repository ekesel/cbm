from __future__ import annotations
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from users.permissions import HasRole
from users.models import Roles
from django.contrib.auth import get_user_model

from .serializers import UserMetricParamsSerializer, UserWIPParamsSerializer
from .sql_user import user_summary, user_timeseries, user_wip

User = get_user_model()

def _identity_set(user) -> set[str]:
    ids = set()
    if getattr(user, "email", None):
        ids.add(user.email.lower())
    uname = getattr(user, "username", None)
    if uname:
        ids.add(uname)
    return ids

def _ensure_can_view(request, uid: str) -> bool:
    """Allow if uid is one of the caller's identities, or caller has privileged role."""
    ids = _identity_set(request.user)
    if uid.lower() in {i.lower() for i in ids}:
        return True
    # privileged roles
    if hasattr(request.user, "role"):
        if request.user.role in {Roles.PROCESS, Roles.CTO, Roles.ADMIN}:
            return True
    # or HasRole via groups/perm (if you used that elsewhere)
    return False

# ---------- /self helpers ----------
class UserSelfSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s = UserMetricParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        uid = (request.user.email or request.user.username)
        if not uid:
            return Response({"error": "User has no identity (email/username) to match"}, status=400)
        data = user_summary(s.validated_data["board_id"], uid, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response({"user_id": uid, "results": data})

class UserSelfTimeseriesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s = UserMetricParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        uid = (request.user.email or request.user.username)
        if not uid:
            return Response({"error": "User has no identity (email/username) to match"}, status=400)
        data = user_timeseries(s.validated_data["board_id"], uid, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response({"user_id": uid, "results": data})

class UserSelfWIPView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s = UserWIPParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        uid = (request.user.email or request.user.username)
        if not uid:
            return Response({"error": "User has no identity (email/username) to match"}, status=400)
        data = user_wip(s.validated_data["board_id"], uid)
        return Response({"user_id": uid, **data})

# ---------- Arbitrary user (private) ----------
class UserSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, uid: str):
        if not _ensure_can_view(request, uid):
            return Response({"error":"Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        s = UserMetricParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = user_summary(s.validated_data["board_id"], uid, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response({"user_id": uid, "results": data})

class UserTimeseriesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, uid: str):
        if not _ensure_can_view(request, uid):
            return Response({"error":"Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        s = UserMetricParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = user_timeseries(s.validated_data["board_id"], uid, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response({"user_id": uid, "results": data})

class UserWIPView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, uid: str):
        if not _ensure_can_view(request, uid):
            return Response({"error":"Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        s = UserWIPParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = user_wip(s.validated_data["board_id"], uid)
        return Response({"user_id": uid, **data})
