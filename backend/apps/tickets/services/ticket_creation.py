from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction

from apps.tickets.models import Ticket, TicketCategory
from apps.users.models import UserProfile


class TicketCreationError(ValueError):
    """Base error for rejected Ticket creation."""


class TicketCreatorProfileMissing(TicketCreationError):
    """Raised when the creator has no UserProfile."""


class TicketCreatorDepartmentMissing(TicketCreationError):
    """Raised when the creator's profile has no department."""


def create_ticket(
    *,
    creator: AbstractBaseUser,
    title: str,
    description: str,
    category: TicketCategory | None = None,
    assignee: AbstractBaseUser | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> Ticket:
    """Create a Ticket using the creator's persisted department.

    The department is always derived from the creator's UserProfile inside
    the transaction. Callers cannot provide a department ID. Assignment does
    not affect the Ticket's department.
    """

    if (
        creator is None
        or not getattr(creator, "is_authenticated", False)
    ):
        raise TicketCreationError("创建工单前必须提供已认证的创建人。")

    with transaction.atomic():
        profile = (
            UserProfile.objects.filter(user=creator)
            .select_related("department")
            .only("user_id", "department_id", "department__id")
            .first()
        )
        if profile is None:
            raise TicketCreatorProfileMissing(
                "创建人缺少 UserProfile，无法确定工单部门。"
            )
        if profile.department is None:
            raise TicketCreatorDepartmentMissing(
                "创建人未分配部门，无法创建工单。"
            )

        return Ticket.objects.create(
            title=title,
            description=description,
            category=category,
            department_id=profile.department.pk,
            creator=creator,
            assignee=assignee,
            status=status or Ticket.Status.PENDING,
            priority=priority or Ticket.Priority.MEDIUM,
        )
