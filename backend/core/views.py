from django.conf import settings
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "time": now().isoformat(),
            "debug": bool(getattr(settings, "DEBUG", False)),
            "app": "sldp-metrics",
        })

class PingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, "role", None)
        return Response({
            "ok": True,
            "user": user.username if user.is_authenticated else None,
            "role": role,
        })
