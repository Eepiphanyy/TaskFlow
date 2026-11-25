from django.urls import path

from .views import (
    UserDepartmentUpdateAPIView,
    UserRoleDeleteAPIView,
    UserRoleListCreateAPIView,
)

app_name = "user-management"

urlpatterns = [
    path(
        "<int:user_id>/department/",
        UserDepartmentUpdateAPIView.as_view(),
        name="department",
    ),
    path(
        "<int:user_id>/roles/",
        UserRoleListCreateAPIView.as_view(),
        name="roles",
    ),
    path(
        "<int:user_id>/roles/<int:role_id>/",
        UserRoleDeleteAPIView.as_view(),
        name="role-detail",
    ),
]
