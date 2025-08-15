from rest_framework import viewsets
from users.permissions import HasRole
from users.models import Roles
from .models import Board
from .serializers import BoardSerializer, DateRangeSerializer, LeaderboardParamsSerializer
from __future__ import annotations
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .sql import timeseries_board, wip_board, timeseries_review, user_leaderboard

class BoardViewSet(viewsets.ModelViewSet):
    queryset = Board.objects.all().order_by("name")
    serializer_class = BoardSerializer
    permission_classes = [HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

class BoardTimeseriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id: int):
        s = DateRangeSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = timeseries_board(board_id, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response({"results": data})

class BoardWIPView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id: int):
        return Response(wip_board(board_id))

class BoardReviewTimeseriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id: int):
        s = DateRangeSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = timeseries_review(board_id, s.validated_data.get("start"), s.validated_data.get("end"))
        return Response({"results": data})

class UserLeaderboardView(APIView):
    permission_classes = [IsAuthenticated, HasRole]
    required_roles = {Roles.PROCESS, Roles.CTO, Roles.ADMIN}

    def get(self, request, board_id: int):
        s = LeaderboardParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        data = user_leaderboard(
            board_id,
            v.get("start"),
            v.get("end"),
            v["limit"],
            v["sort"])
        return Response({"results": data})