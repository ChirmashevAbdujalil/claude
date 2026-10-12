from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Faculty
from .serializers import FacultySerializer, MeSerializer, TelegramAuthSerializer, TokenPairSerializer
from .telegram import TelegramAuthError, get_or_create_telegram_user, verify_init_data


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
            user, created = get_or_create_telegram_user(tg_user)
        except TelegramAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

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
