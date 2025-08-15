from __future__ import annotations
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from metrics.models import Team
from metrics.serializers import DateRangeSerializer
from metrics.sql_team import team_timeseries, team_summary

class TeamTimeseriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id: int):
        get_object_or_404(Team, pk=team_id, is_active=True)
        s = DateRangeSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = team_timeseries(team_id, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response({"results": data})

class TeamSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, team_id: int):
        get_object_or_404(Team, pk=team_id, is_active=True)
        s = DateRangeSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = team_summary(team_id, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response(data)