from __future__ import annotations

from django.db import transaction

from apps.tickets.models import Ticket
from apps.tickets.services.ticket_processing import (
    can_operate_ticket_by_role,
)
from apps.tickets.services.ticket_scope import (
    get_ticket_queryset_for_permission,
)
from apps.users.models import UserProfile
from apps.users.services.permission_resolver import (
    UserLike,
    resolve_user_permissions,
)

CLOSE_PERMISSION_KEY = "tickets.close_ticket"


class TicketCloseError(ValueError):
    """Base error for a rejected Ticket close request."""


class TicketCloseNotFound(TicketCloseError):
    """Raised when object-level access cannot be confirmed."""


class TicketClosePermissionDenied(TicketCloseError):
    """Raised when the business close permission is no longer valid."""


class TicketCloseStateConflict(TicketCloseError):
    """Raised when the Ticket is not in the resolved state."""


def close_ticket(
    *,
    ticket_id: int,
    operator: UserLike,
) -> Ticket:
    """Close one resolved Ticket with row-level concurrency safety."""

    with transaction.atomic():
        scoped_tickets = get_ticket_queryset_for_permission(
            operator,
            CLOSE_PERMISSION_KEY,
        )
        try:
            ticket = (
                scoped_tickets
                .select_for_update()
                .only(
                    "id",
                    "status",
                    "assignee_id",
                    "department_id",
                    "updated_at",
                )
                .get(pk=ticket_id)
            )
        except Ticket.DoesNotExist as exc:
            raise TicketCloseNotFound(
                "工单不存在或无权关闭。"
            ) from exc

        profile = (
            UserProfile.objects.select_for_update()
            .select_related("department")
            .filter(user=operator)
            .only(
                "id",
                "user_id",
                "department_id",
                "department__id",
            )
            .first()
        )
        if profile is None:
            raise TicketCloseNotFound("工单不存在或无权关闭。")

        resolved_permissions = resolve_user_permissions(operator)
        grant = resolved_permissions.permissions.get(
            CLOSE_PERMISSION_KEY
        )
        if grant is None:
            raise TicketClosePermissionDenied(
                "缺少关闭工单的业务权限。"
            )

        if not can_operate_ticket_by_role(
            role_codes=grant.role_codes,
            operator_id=operator.pk,
            operator_department_id=profile.department_id,
            ticket=ticket,
        ):
            raise TicketCloseNotFound("工单不存在或无权关闭。")

        if ticket.status != Ticket.Status.RESOLVED:
            raise TicketCloseStateConflict(
                "只有已解决的工单允许关闭。"
            )

        ticket.status = Ticket.Status.CLOSED
        ticket.save(update_fields=["status", "updated_at"])
        return (
            Ticket.objects
            .select_related(
                "category",
                "creator",
                "assignee",
                "department",
            )
            .get(pk=ticket.pk)
        )
