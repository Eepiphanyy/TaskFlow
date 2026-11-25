from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend

from .models import Ticket, TicketCategory


class TicketListFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Ticket.Status.values,
        required=False,
    )
    priority = serializers.ChoiceField(
        choices=Ticket.Priority.values,
        required=False,
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=TicketCategory.objects.all(),
        required=False,
    )
    created_after = serializers.DateField(required=False)
    created_before = serializers.DateField(required=False)

    def validate(self, attrs):
        created_after = attrs.get("created_after")
        created_before = attrs.get("created_before")
        if (
            created_after is not None
            and created_before is not None
            and created_after > created_before
        ):
            raise serializers.ValidationError({
                "created_before": [
                    "created_before 不能早于 created_after。"
                ]
            })
        return attrs


def _start_of_local_day(value):
    current_timezone = timezone.get_current_timezone()
    return timezone.make_aware(
        datetime.combine(value, time.min),
        current_timezone,
    )


class TicketListFilterBackend(BaseFilterBackend):
    """Apply validated Ticket list filters to an already-scoped QuerySet."""

    def filter_queryset(self, request, queryset, view):
        serializer = TicketListFilterSerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        filters = dict(serializer.validated_data)

        category = filters.pop("category", None)
        if category is not None:
            filters["category"] = category

        created_after = filters.pop("created_after", None)
        if created_after is not None:
            filters["created_at__gte"] = _start_of_local_day(
                created_after
            )

        created_before = filters.pop("created_before", None)
        if created_before is not None:
            filters["created_at__lt"] = _start_of_local_day(
                created_before + timedelta(days=1)
            )

        if not filters:
            return queryset
        return queryset.filter(**filters)
