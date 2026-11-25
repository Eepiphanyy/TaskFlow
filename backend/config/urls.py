from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.common.urls")),
    path("api/auth/", include("apps.users.urls")),
    path("api/users/", include("apps.users.user_urls")),
    path("api/departments/", include("apps.departments.urls")),
    path("api/tickets/", include("apps.tickets.urls")),
    path(
        "api/ticket-categories/",
        include("apps.tickets.category_urls"),
    ),
]
