import hmac
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services, telegram_bot
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "icon", "title", "body", "url", "is_read", "created_at"]


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    filterset_fields = ["is_read"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        return Response({"updated": services.mark_all_read(request.user)})


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """Telegram serveridan keladigan yangilanishlar. Maxfiy token sarlavhasi tekshiriladi."""
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not hmac.compare_digest(expected, received):
        return HttpResponseForbidden()
    try:
        update = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    telegram_bot.handle_update(update)
    return HttpResponse("ok")
