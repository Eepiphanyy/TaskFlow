from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser
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

EDIT_PERMISSION_KEY = "tickets.change_ticket"
ADMIN_ROLE_CODE = "admin"
DEPARTMENT_MANAGER_ROLE_CODE = "department_manager"
EMPLOYEE_ROLE_CODE = "employee"
EDITABLE_FIELDS = frozenset({"title", "description", "category"})
EDITABLE_STATUSES = frozenset({
    Ticket.Status.PENDING,
    Ticket.Status.PROCESSING,
})


class TicketEditError(ValueError):
    """Base error for a rejected Ticket edit."""


class TicketEditNotFound(TicketEditError):
    """Raised when a Ticket is missing or outside the edit scope."""


class TicketEditPermissionDenied(TicketEditError):
    """Raised when the business edit permission is no longer valid."""


class TicketEditStateConflict(TicketEditError):
    """Raised when the Ticket status or role rules forbid editing."""


def _get_edit_role_access(
    *,
    role_codes: frozenset[str],
    operator_id: int,
    operator_department_id: int | None,
    ticket: Ticket,
) -> tuple[bool, bool, bool]:
    admin_access = ADMIN_ROLE_CODE in role_codes
    manager_access = (
        DEPARTMENT_MANAGER_ROLE_CODE in role_codes
        and operator_department_id is not None
        and ticket.department_id == operator_department_id
    )
    employee_access = (
        EMPLOYEE_ROLE_CODE in role_codes
        and ticket.creator_id == operator_id
    )
    return admin_access, manager_access, employee_access


def update_ticket(
    *,
    ticket_id: int,
    fields: dict,
    operator: UserLike | AbstractBaseUser,
) -> Ticket:
    """Update one editable Ticket while preserving protected ownership fields."""

    invalid_fields = set(fields) - EDITABLE_FIELDS
    if invalid_fields:
        raise TicketEditError("包含不允许编辑的字段。")

    with transaction.atomic():
        resolved_permissions = resolve_user_permissions(operator)
        grant = resolved_permissions.permissions.get(
            EDIT_PERMISSION_KEY
        )
        if grant is None:
            raise TicketEditPermissionDenied(
                "缺少编辑工单的业务权限。"
            )

        scoped_tickets = get_ticket_queryset_for_permission(
            operator,
            EDIT_PERMISSION_KEY,
        )
        try:
            ticket = (
                scoped_tickets
                .select_for_update()
                .only(
                    "id",
                    "title",
                    "description",
                    "category_id",
                    "creator_id",
                    "department_id",
                    "assignee_id",
                    "status",
                    "priority",
                    "updated_at",
                )
                .get(pk=ticket_id)
            )
        except Ticket.DoesNotExist as exc:
            raise TicketEditNotFound(
                "工单不存在或无权编辑。"
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
            raise TicketEditNotFound("工单不存在或无权编辑。")

        admin_access, manager_access, employee_access = (
            _get_edit_role_access(
                role_codes=grant.role_codes,
                operator_id=operator.pk,
                operator_department_id=profile.department_id,
                ticket=ticket,
            )
        )
        if not any((admin_access, manager_access, employee_access)):
            raise TicketEditNotFound("工单不存在或无权编辑。")

        if ticket.status not in EDITABLE_STATUSES:
            raise TicketEditStateConflict(
                "已解决或已关闭的工单不允许编辑。"
            )
        if (
            employee_access
            and not (admin_access or manager_access)
            and ticket.status != Ticket.Status.PENDING
        ):
            raise TicketEditStateConflict(
                "普通员工只能编辑待处理工单。"
            )

        update_fields = []
        for field_name in fields:
            setattr(ticket, field_name, fields[field_name])
            update_fields.append(field_name)
        update_fields.append("updated_at")
        ticket.save(update_fields=update_fields)

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
