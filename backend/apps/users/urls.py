from django.urls import path

from .views import (
    CurrentUserAPIView,
    LoginAPIView,
    LogoutAPIView,
    RefreshAPIView,
    RegisterAPIView,
)

app_name = "users"

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("me/", CurrentUserAPIView.as_view(), name="me"),
    path(
        "token/refresh/",
        RefreshAPIView.as_view(),
        name="token-refresh",
    ),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
]
