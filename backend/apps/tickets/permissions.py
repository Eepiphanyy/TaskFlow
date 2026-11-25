from rest_framework.permissions import BasePermission

from apps.users.services.permission_resolver import has_permission
from apps.users.services.scope_resolver import resolve_user_scope_context


class HasTicketViewPermission(BasePermission):
    """Require the TaskFlow ``tickets.view_ticket`` business permission."""

    message = "缺少查看工单的业务权限。"

    def has_permission(self, request, view):
        return has_permission(
            request.user,
            "tickets.view_ticket",
        )


class HasTicketAddPermission(BasePermission):
    """Require the TaskFlow ``tickets.add_ticket`` business permission."""

    message = "缺少创建工单的业务权限。"

    def has_permission(self, request, view):
        return has_permission(
            request.user,
            "tickets.add_ticket",
        )


class HasTicketChangePermission(BasePermission):
    """Require the TaskFlow ``tickets.change_ticket`` business permission."""

    message = "缺少编辑工单的业务权限。"

    def has_permission(self, request, view):
        return has_permission(
            request.user,
            "tickets.change_ticket",
        )


class HasTicketAssignPermission(BasePermission):
    """Require the TaskFlow ``tickets.assign_ticket`` business permission."""

    message = "缺少分配工单的业务权限。"

    def has_permission(self, request, view):
        return has_permission(
            request.user,
            "tickets.assign_ticket",
        )


class HasTicketAssignCandidatePermission(BasePermission):
    """Require assign permission with at least one effective data scope."""

    message = "缺少查询工单处理人的业务权限。"

    def has_permission(self, request, view):
        permission_key = "tickets.assign_ticket"
        if not has_permission(request.user, permission_key):
            return False

        context = resolve_user_scope_context(request.user)
        resolution = context.get_permission(permission_key)
        return bool(resolution and resolution.effective_scopes)


class HasTicketProcessPermission(BasePermission):
    """Require the TaskFlow ``tickets.process_ticket`` business permission."""

    message = "缺少处理工单的业务权限。"

    def has_permission(self, request, view):
        return has_permission(
            request.user,
            "tickets.process_ticket",
        )


class HasTicketClosePermission(BasePermission):
    """Require the TaskFlow ``tickets.close_ticket`` business permission."""

    message = "缺少关闭工单的业务权限。"

    def has_permission(self, request, view):
        return has_permission(
            request.user,
            "tickets.close_ticket",
        )
