import logging

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import TicketListFilterBackend
from .models import TicketCategory
from .pagination import TicketPagination
from .permissions import (
    HasTicketAddPermission,
    HasTicketAssignCandidatePermission,
    HasTicketAssignPermission,
    HasTicketChangePermission,
    HasTicketClosePermission,
    HasTicketProcessPermission,
    HasTicketViewPermission,
)
from .serializers import (
    TicketAssignSerializer,
    TicketAssigneeSerializer,
    TicketCategorySerializer,
    TicketCloseSerializer,
    TicketCreateSerializer,
    TicketProcessSerializer,
    TicketReadSerializer,
    TicketUpdateSerializer,
)
from .services.ticket_assignment import (
    TicketAssignmentAssigneeInvalid,
    TicketAssignmentNotFound,
    TicketAssignmentStateConflict,
    assign_ticket,
)
from .services.ticket_creation import TicketCreationError, create_ticket
from .services.ticket_editing import (
    TicketEditNotFound,
    TicketEditPermissionDenied,
    TicketEditStateConflict,
    update_ticket,
)
from .services.ticket_closing import (
    TicketCloseNotFound,
    TicketClosePermissionDenied,
    TicketCloseStateConflict,
    close_ticket,
)
from .services.ticket_processing import (
    TicketProcessNotFound,
    TicketProcessPermissionDenied,
    TicketProcessStateConflict,
    process_ticket,
)
from .services.ticket_scope import get_ticket_queryset_for_permission

TICKET_VIEW_PERMISSION = "tickets.view_ticket"
logger = logging.getLogger(__name__)


class TicketScopedQueryMixin:
    permission_classes = [IsAuthenticated, HasTicketViewPermission]

    def get_queryset(self):
        return (
            get_ticket_queryset_for_permission(
                self.request.user,
                TICKET_VIEW_PERMISSION,
            )
            .select_related(
                "category",
                "creator",
                "assignee",
                "department",
            )
        )


class TicketListAPIView(
    TicketScopedQueryMixin,
    generics.ListCreateAPIView,
):
    serializer_class = TicketReadSerializer
    pagination_class = TicketPagination
    filter_backends = [
        TicketListFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["title"]
    ordering_fields = [
        "id",
        "title",
        "status",
        "priority",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at", "-id"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), HasTicketAddPermission()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketCreateSerializer
        return TicketReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket = create_ticket(
                creator=request.user,
                **serializer.validated_data,
            )
        except TicketCreationError as exc:
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = TicketReadSerializer(
            ticket,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class TicketDetailAPIView(TicketScopedQueryMixin, generics.RetrieveAPIView):
    serializer_class = TicketReadSerializer

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [
                IsAuthenticated(),
                HasTicketChangePermission(),
            ]
        return super().get_permissions()

    def patch(self, request, pk):
        serializer = TicketUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket = update_ticket(
                ticket_id=pk,
                fields=serializer.validated_data,
                operator=request.user,
            )
        except TicketEditNotFound as exc:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": str(exc),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except TicketEditPermissionDenied as exc:
            return Response(
                {
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": str(exc),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except TicketEditStateConflict as exc:
            return Response(
                {
                    "code": status.HTTP_409_CONFLICT,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except DatabaseError:
            logger.exception(
                "Failed to edit Ticket id=%s operator_id=%s",
                pk,
                request.user.pk,
            )
            return Response(
                {
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "工单编辑失败，请稍后重试。",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            TicketReadSerializer(
                ticket,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class TicketCategoryListAPIView(generics.ListAPIView):
    queryset = TicketCategory.objects.order_by("id")
    serializer_class = TicketCategorySerializer
    permission_classes = [IsAuthenticated]


class TicketAssigneeListAPIView(generics.ListAPIView):
    serializer_class = TicketAssigneeSerializer
    permission_classes = [
        IsAuthenticated,
        HasTicketAssignCandidatePermission,
    ]
    pagination_class = None

    def get_queryset(self):
        return (
            get_user_model().objects
            .filter(
                is_active=True,
                profile__isnull=False,
                profile__roles__code="ticket_handler",
            )
            .select_related("profile__department")
            .order_by("id")
            .distinct()
        )


class TicketAssignAPIView(APIView):
    permission_classes = [IsAuthenticated, HasTicketAssignPermission]

    def patch(self, request, pk):
        serializer = TicketAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket = assign_ticket(
                ticket_id=pk,
                assignee=serializer.validated_data["assignee"],
                operator=request.user,
            )
        except TicketAssignmentNotFound as exc:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": str(exc),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except TicketAssignmentStateConflict as exc:
            return Response(
                {
                    "code": status.HTTP_409_CONFLICT,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except TicketAssignmentAssigneeInvalid as exc:
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError:
            logger.exception(
                "Failed to assign Ticket id=%s operator_id=%s",
                pk,
                request.user.pk,
            )
            return Response(
                {
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "工单分配失败，请稍后重试。",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            TicketReadSerializer(
                ticket,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class TicketProcessAPIView(APIView):
    permission_classes = [IsAuthenticated, HasTicketProcessPermission]

    def patch(self, request, pk):
        serializer = TicketProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket = process_ticket(
                ticket_id=pk,
                target_status=serializer.validated_data["status"],
                operator=request.user,
            )
        except TicketProcessNotFound as exc:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": str(exc),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except TicketProcessPermissionDenied as exc:
            return Response(
                {
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": str(exc),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except TicketProcessStateConflict as exc:
            return Response(
                {
                    "code": status.HTTP_409_CONFLICT,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except DatabaseError:
            logger.exception(
                "Failed to process Ticket id=%s operator_id=%s",
                pk,
                request.user.pk,
            )
            return Response(
                {
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "工单处理失败，请稍后重试。",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            TicketReadSerializer(
                ticket,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class TicketCloseAPIView(APIView):
    permission_classes = [IsAuthenticated, HasTicketClosePermission]

    def post(self, request, pk):
        serializer = TicketCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket = close_ticket(
                ticket_id=pk,
                operator=request.user,
            )
        except TicketCloseNotFound as exc:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": str(exc),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except TicketClosePermissionDenied as exc:
            return Response(
                {
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": str(exc),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except TicketCloseStateConflict as exc:
            return Response(
                {
                    "code": status.HTTP_409_CONFLICT,
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except DatabaseError:
            logger.exception(
                "Failed to close Ticket id=%s operator_id=%s",
                pk,
                request.user.pk,
            )
            return Response(
                {
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "工单关闭失败，请稍后重试。",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            TicketReadSerializer(
                ticket,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )
