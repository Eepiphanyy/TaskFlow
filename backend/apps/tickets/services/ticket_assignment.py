from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction

from apps.tickets.models import Ticket
from apps.tickets.services.ticket_scope import (
    get_ticket_queryset_for_permission,
)
from apps.users.models import UserProfile
from apps.users.services.permission_resolver import UserLike

User = get_user_model()

ASSIGNABLE_STATUSES = frozenset({
    Ticket.Status.PENDING,
    Ticket.Status.PROCESSING,
})
HANDLER_ROLE_CODE = "ticket_handler"


class TicketAssignmentError(ValueError):
    """Base error for a rejected Ticket assignment."""


class TicketAssignmentNotFound(TicketAssignmentError):
    """Raised when a Ticket is missing or outside the operator's scope."""


class TicketAssignmentStateConflict(TicketAssignmentError):
    """Raised when the Ticket status does not allow assignment changes."""


class TicketAssignmentAssigneeInvalid(TicketAssignmentError):
    """Raised when the requested assignee is not eligible."""


def _validate_assignee(assignee: AbstractBaseUser) -> AbstractBaseUser:
    fresh_assignee = (
        User.objects.select_for_update()
        .filter(pk=assignee.pk)
        .only("id", "is_active")
        .first()
    )
    if fresh_assignee is None:
        raise TicketAssignmentAssigneeInvalid("指定的处理人不存在。")
    if not fresh_assignee.is_active:
        raise TicketAssignmentAssigneeInvalid(
            "处理人账号未启用，不能分配工单。"
        )

    profile = (
        UserProfile.objects.select_for_update()
        .filter(user_id=fresh_assignee.pk)
        .only("id", "user_id")
        .first()
    )
    if profile is None:
        raise TicketAssignmentAssigneeInvalid(
            "处理人缺少 UserProfile，不能分配工单。"
        )
    if not profile.roles.filter(code=HANDLER_ROLE_CODE).exists():
        raise TicketAssignmentAssigneeInvalid(
            "处理人缺少 ticket_handler 业务角色。"
        )
    return fresh_assignee


def assign_ticket(
    *,
    ticket_id: int,
    assignee: AbstractBaseUser | None,
    operator: UserLike,
) -> Ticket:
    """Assign, reassign, or clear a Ticket assignee.

    Scope and Permission are resolved from the current operator. The Ticket
    row is locked before checking status so concurrent assignment requests
    cannot act on stale state. Only ``assignee`` and ``updated_at`` change.
    """

    with transaction.atomic():
        scoped_tickets = get_ticket_queryset_for_permission(
            operator,
            "tickets.assign_ticket",
        )
        try:
            ticket = (
                scoped_tickets
                .select_for_update()
                .only("id", "status", "assignee_id", "updated_at")
                .get(pk=ticket_id)
            )
        except Ticket.DoesNotExist as exc:
            raise TicketAssignmentNotFound(
                "工单不存在或无权访问。"
            ) from exc

        if ticket.status not in ASSIGNABLE_STATUSES:
            raise TicketAssignmentStateConflict(
                "只有待处理或处理中的工单允许分配或取消分配。"
            )

        fresh_assignee = (
            _validate_assignee(assignee)
            if assignee is not None
            else None
        )
        ticket.assignee = fresh_assignee
        ticket.save(update_fields=["assignee", "updated_at"])

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
