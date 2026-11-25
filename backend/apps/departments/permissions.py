from rest_framework.permissions import BasePermission

from apps.users.models import RolePermissionScope, UserProfile
from apps.users.services.permission_resolver import (
    has_permission,
    is_taskflow_admin,
)
from apps.users.services.scope_resolver import resolve_user_scope_context

DEPARTMENT_MANAGER_ROLE_CODE = "department_manager"


class HasDepartmentChangePermission(BasePermission):
    """Allow change_department within the manager's own department."""

    permission_denied_message = "无权修改部门信息。"
    scope_denied_message = "只能修改自己所属的部门。"
    message = permission_denied_message

    def has_permission(self, request, view):
        allowed = has_permission(
            request.user,
            "departments.change_department",
        )
        self.message = (
            self.scope_denied_message
            if allowed
            else self.permission_denied_message
        )
        return allowed

    def has_object_permission(self, request, view, obj):
        self.message = self.scope_denied_message
        user = request.user
        if is_taskflow_admin(user):
            return True

        profile = (
            UserProfile.objects
            .filter(user=user)
            .only("id", "user_id", "department_id")
            .first()
        )
        if profile is None or profile.department_id is None:
            return False

        is_department_manager = profile.roles.filter(
            code=DEPARTMENT_MANAGER_ROLE_CODE,
        ).exists()
        return (
            is_department_manager
            and obj.pk == profile.department_id
        )


class HasDepartmentMemberViewPermission(BasePermission):
    """Allow department members to be viewed by admins and own managers."""

    permission_denied_message = "无权查看部门成员。"
    scope_denied_message = "只能查看自己所属部门的成员。"
    message = permission_denied_message

    def has_permission(self, request, view):
        allowed = has_permission(
            request.user,
            "departments.view_department_members",
        )
        self.message = (
            self.scope_denied_message
            if allowed
            else self.permission_denied_message
        )
        return allowed

    def has_object_permission(self, request, view, obj):
        self.message = self.scope_denied_message
        user = request.user
        if is_taskflow_admin(user):
            return True

        context = resolve_user_scope_context(user)
        resolution = context.get_permission(
            "departments.view_department_members"
        )
        return (
            resolution is not None
            and RolePermissionScope.DEPARTMENT
            in resolution.effective_scopes
            and context.department_id == obj.pk
        )
