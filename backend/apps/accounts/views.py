from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Faculty, User
from .serializers import FacultySerializer, MeSerializer, TelegramAuthSerializer, TokenPairSerializer
from .telegram import TelegramAuthError, verify_init_data


class TelegramAuthView(APIView):
    """Telegram Mini App orqali kirish: birinchi marta kirganda hisob avtomatik yaratiladi."""

    permission_classes = [AllowAny]

    @extend_schema(request=TelegramAuthSerializer, responses=TokenPairSerializer)
    def post(self, request):
        serializer = TelegramAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tg_user = verify_init_data(
                serializer.validated_data["init_data"],
                settings.TELEGRAM_BOT_TOKEN,
                settings.TELEGRAM_AUTH_MAX_AGE,
            )
        except TelegramAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                telegram_id=tg_user["id"],
                defaults={
                    "username": f"tg{tg_user['id']}",
                    "first_name": tg_user.get("first_name", "")[:150],
                    "last_name": tg_user.get("last_name", "")[:150],
                },
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])

        if not user.is_active:
            return Response({"detail": "Hisob bloklangan"}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh), "created": created})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


class FacultyListView(generics.ListAPIView):
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer
    pagination_class = None
