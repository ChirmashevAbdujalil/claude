from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagement

from .services import dashboard


class DashboardView(APIView):
    """Rektorat va dekanat paneli."""

    permission_classes = [IsManagement]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(dashboard(request.user))
