from django.urls import path

from .views import TicketCategoryListAPIView

app_name = "ticket-categories"

urlpatterns = [
    path(
        "",
        TicketCategoryListAPIView.as_view(),
        name="list",
    ),
]
