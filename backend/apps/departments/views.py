from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.db.models.deletion import ProtectedError
from rest_framework import filters, generics
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsTaskFlowAdmin
from apps.users.models import Role

from .models import Department
from .pagination import DepartmentPagination
from .permissions import (
    HasDepartmentChangePermission,
    HasDepartmentMemberViewPermission,
)
from .serializers import DepartmentMemberSerializer, DepartmentSerializer

User = get_user_model()


class DepartmentListAPIView(generics.ListCreateAPIView):
    queryset = Department.objects.order_by("id")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DepartmentPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsTaskFlowAdmin()]
        # Department list access is intentionally available to every
        # authenticated user as shared enterprise reference data.
        return [IsAuthenticated()]


class DepartmentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Department.objects.order_by("id")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [
                IsAuthenticated(),
                HasDepartmentChangePermission(),
            ]
        if self.request.method == "DELETE":
            return [IsAuthenticated(), IsTaskFlowAdmin()]
        # Department detail is intentionally readable by every authenticated
        # user; write operations above use RBAC or admin-only checks.
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "code": status.HTTP_409_CONFLICT,
                    "message": "部门仍有关联工单，无法删除。",
                },
                status=status.HTTP_409_CONFLICT,
            )


class DepartmentMemberListAPIView(generics.ListAPIView):
    serializer_class = DepartmentMemberSerializer
    permission_classes = [
        IsAuthenticated,
        HasDepartmentMemberViewPermission,
    ]
    pagination_class = DepartmentPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "email"]

    def get_queryset(self):
        return (
            User.objects
            .filter(profile__department_id=self.kwargs["department_id"])
            .select_related("profile")
            .prefetch_related(
                Prefetch(
                    "profile__roles",
                    queryset=Role.objects.order_by("id"),
                )
            )
            .order_by("id")
        )

    def list(self, request, *args, **kwargs):
        try:
            department = Department.objects.get(
                pk=self.kwargs["department_id"]
            )
        except Department.DoesNotExist:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": "部门不存在",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request, department)
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)

        return Response({
            "code": status.HTTP_200_OK,
            "message": "获取部门成员成功",
            "data": {
                "department": {
                    "id": department.pk,
                    "name": department.name,
                },
                "count": self.paginator.page.paginator.count,
                "next": self.paginator.get_next_link(),
                "previous": self.paginator.get_previous_link(),
                "results": serializer.data,
            },
        })
