from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrPublisher

from . import services
from .models import Application, Opportunity, Redemption, Reward
from .serializers import (
    ApplicationSerializer,
    ApplySerializer,
    OpportunitySerializer,
    RedemptionSerializer,
    RewardSerializer,
)


class OpportunityViewSet(viewsets.ModelViewSet):
    queryset = Opportunity.objects.none()
    serializer_class = OpportunitySerializer
    permission_classes = [ReadOnlyOrPublisher]
    filterset_fields = ["kind", "min_level"]
    search_fields = ["title", "description", "organization"]

    def get_queryset(self):
        qs = Opportunity.objects.all()
        user = self.request.user
        if user.is_management:
            return qs
        if user.role == user.Role.PARTNER:
            return qs.filter(created_by=user)
        return qs.filter(is_active=True).filter(Q(deadline__isnull=True) | Q(deadline__gte=timezone.now()))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["applied_ids"] = set(
            Application.objects.filter(user=self.request.user).values_list("opportunity_id", flat=True)
        )
        return context

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=ApplySerializer, responses=ApplicationSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def apply(self, request, pk=None):
        serializer = ApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            application = services.apply(self.get_object(), request.user, serializer.validated_data["motivation"])
        except services.OpportunityError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ApplicationSerializer(application).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=ApplicationSerializer(many=True))
    @action(detail=True)
    def applications(self, request, pk=None):
        opportunity = self.get_object()
        if not (request.user.is_management or opportunity.created_by_id == request.user.id):
            return Response({"detail": "Ruxsat yo'q"}, status=status.HTTP_403_FORBIDDEN)
        qs = opportunity.applications.select_related("user", "user__faculty")
        return Response(ApplicationSerializer(qs, many=True).data)


class MyApplicationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Application.objects.none()
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        return Application.objects.filter(user=self.request.user).select_related("opportunity", "user")


class RewardViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Reward.objects.none()
    serializer_class = RewardSerializer
    pagination_class = None

    def get_queryset(self):
        return Reward.objects.filter(is_active=True)

    @extend_schema(request=None, responses=RedemptionSerializer)
    @action(detail=True, methods=["post"])
    def redeem(self, request, pk=None):
        try:
            redemption = services.redeem(self.get_object(), request.user)
        except services.OpportunityError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RedemptionSerializer(redemption).data, status=status.HTTP_201_CREATED)


class MyRedemptionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Redemption.objects.none()
    serializer_class = RedemptionSerializer

    def get_queryset(self):
        return Redemption.objects.filter(user=self.request.user).select_related("reward")
