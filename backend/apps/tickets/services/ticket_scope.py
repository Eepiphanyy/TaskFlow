from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.tickets.models import Ticket
from apps.users.rbac_matrix import REQUIRED_PERMISSIONS
from apps.users.services.permission_resolver import UserLike
from apps.users.services.scope_resolver import (
    build_scope_query,
    resolve_user_scope_context,
)

TICKET_PERMISSION_KEYS = frozenset(
    f"{app_label}.{codename}"
    for app_label, codename in REQUIRED_PERMISSIONS
    if app_label == "tickets"
)


class TicketScopeQueryBuilder:
    """Translate generic scopes into Ticket-specific ORM conditions."""

    def self_scope_q(self, user_id: int) -> Q:
        return (
            Q(creator_id=user_id)
            | Q(assignee_id=user_id)
        )

    def department_scope_q(self, department_id: int) -> Q:
        return Q(department_id=department_id)


def get_ticket_queryset_for_permission(
    user: UserLike,
    permission_key: str,
) -> QuerySet[Ticket]:
    """Return Ticket rows visible for one independently-authorized permission.

    Only registered Ticket permissions are accepted. The user and department
    context is always derived from the supplied authenticated user, never from
    request-supplied identifiers. The returned QuerySet remains lazy and can
    be further filtered, ordered, paginated, or prefetched by API services.
    """

    if (
        not isinstance(permission_key, str)
        or permission_key not in TICKET_PERMISSION_KEYS
    ):
        return Ticket.objects.none()

    context = resolve_user_scope_context(user)
    scope_query = build_scope_query(
        context=context,
        permission_key=permission_key,
        resource_builder=TicketScopeQueryBuilder(),
    )
    return Ticket.objects.filter(scope_query)
