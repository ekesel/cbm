from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import UserSerializer
from .permissions import HasRole, require_roles
from .models import Roles

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

@require_roles(Roles.PROCESS, Roles.CTO, Roles.CEO, Roles.ADMIN)
class ProcessOnlyPing(APIView):
    permission_classes = [HasRole]

    def get(self, request):
        return Response({"ok": True, "msg": "process/leadership-only endpoint"})
