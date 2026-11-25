from django.urls import path

from .views import (
    DepartmentDetailAPIView,
    DepartmentListAPIView,
    DepartmentMemberListAPIView,
)

app_name = "departments"

urlpatterns = [
    path("", DepartmentListAPIView.as_view(), name="list"),
    path("<int:pk>/", DepartmentDetailAPIView.as_view(), name="detail"),
    path(
        "<int:department_id>/members/",
        DepartmentMemberListAPIView.as_view(),
        name="members",
    ),
]
