from django.urls import path

from .views import (
    TicketAssignAPIView,
    TicketAssigneeListAPIView,
    TicketCloseAPIView,
    TicketDetailAPIView,
    TicketListAPIView,
    TicketProcessAPIView,
)

app_name = "tickets"

urlpatterns = [
    path("", TicketListAPIView.as_view(), name="list"),
    path(
        "assignees/",
        TicketAssigneeListAPIView.as_view(),
        name="assignees",
    ),
    path("<int:pk>/assign/", TicketAssignAPIView.as_view(), name="assign"),
    path("<int:pk>/process/", TicketProcessAPIView.as_view(), name="process"),
    path("<int:pk>/close/", TicketCloseAPIView.as_view(), name="close"),
    path("<int:pk>/", TicketDetailAPIView.as_view(), name="detail"),
]
