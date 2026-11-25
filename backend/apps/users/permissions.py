from rest_framework.permissions import BasePermission

from apps.users.services.permission_resolver import has_permission

ADMIN_ROLE_CODE = "admin"


class IsTaskFlowAdmin(BasePermission):
    message = "仅 TaskFlow 管理员可以执行此操作。"

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        profile = getattr(user, "profile", None)
        if profile is None:
            return False

        return profile.roles.filter(code=ADMIN_ROLE_CODE).exists()


class HasUserDepartmentAssignPermission(BasePermission):
    """Require the TaskFlow user-department assignment permission."""

    message = "无权修改用户部门。"

    def has_permission(self, request, view):
        return has_permission(
            request.user,
            "users.assign_user_department",
        )
