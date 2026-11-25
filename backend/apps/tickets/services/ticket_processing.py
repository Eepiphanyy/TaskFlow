from __future__ import annotations

from django.db import transaction

from apps.tickets.models import Ticket
from apps.tickets.services.ticket_scope import (
    get_ticket_queryset_for_permission,
)
from apps.users.models import UserProfile
from apps.users.services.permission_resolver import (
    UserLike,
    resolve_user_permissions,
)

PROCESS_PERMISSION_KEY = "tickets.process_ticket"
ADMIN_ROLE_CODE = "admin"
DEPARTMENT_MANAGER_ROLE_CODE = "department_manager"
TICKET_HANDLER_ROLE_CODE = "ticket_handler"

ALLOWED_STATUS_TRANSITIONS = {
    Ticket.Status.PENDING: frozenset({
        Ticket.Status.PROCESSING,
    }),
    Ticket.Status.PROCESSING: frozenset({
        Ticket.Status.RESOLVED,
    }),
}


class TicketProcessError(ValueError):
    """Base error for a rejected Ticket processing request."""


class TicketProcessNotFound(TicketProcessError):
    """Raised when object-level access cannot be confirmed."""


class TicketProcessPermissionDenied(TicketProcessError):
    """Raised when the business processing permission is no longer valid."""


class TicketProcessStateConflict(TicketProcessError):
    """Raised when the requested status transition is not allowed."""


def can_operate_ticket_by_role(
    *,
    role_codes: frozenset[str],
    operator_id: int,
    operator_department_id: int | None,
    ticket: Ticket,
) -> bool:
    if ADMIN_ROLE_CODE in role_codes:
        return True

    if (
        DEPARTMENT_MANAGER_ROLE_CODE in role_codes
        and operator_department_id is not None
        and ticket.department_id == operator_department_id
    ):
        return True

    return (
        TICKET_HANDLER_ROLE_CODE in role_codes
        and ticket.assignee_id == operator_id
    )


def process_ticket(
    *,
    ticket_id: int,
    target_status: str,
    operator: UserLike,
) -> Ticket:
    """Apply one allowed status transition with row-level concurrency safety.

    SELF Scope alone is insufficient for ``ticket_handler`` because its
    Ticket query includes both creator and assignee. The object-level role
    check therefore requires the handler to be the current assignee, while a
    department manager is checked against the Ticket's department. Multi-role
    users receive the union of their eligible role branches.
    """

    with transaction.atomic():
        scoped_tickets = get_ticket_queryset_for_permission(
            operator,
            PROCESS_PERMISSION_KEY,
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
            raise TicketProcessNotFound(
                "工单不存在或无权处理。"
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
            raise TicketProcessNotFound("工单不存在或无权处理。")

        resolved_permissions = resolve_user_permissions(operator)
        grant = resolved_permissions.permissions.get(
            PROCESS_PERMISSION_KEY
        )
        if grant is None:
            raise TicketProcessPermissionDenied(
                "缺少处理工单的业务权限。"
            )

        if not can_operate_ticket_by_role(
            role_codes=grant.role_codes,
            operator_id=operator.pk,
            operator_department_id=profile.department_id,
            ticket=ticket,
        ):
            raise TicketProcessNotFound("工单不存在或无权处理。")

        allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(
            ticket.status,
            frozenset(),
        )
        if target_status not in allowed_targets:
            raise TicketProcessStateConflict(
                "不允许执行该工单状态转换。"
            )

        ticket.status = target_status
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
