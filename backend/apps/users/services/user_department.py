from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.departments.models import Department
from apps.users.models import RolePermissionScope, UserProfile
from apps.users.services.permission_resolver import (
    UserLike,
    resolve_user_permissions,
)
from apps.users.services.scope_resolver import resolve_user_scope_context

User = get_user_model()

DEPARTMENT_MANAGER_ROLE_CODE = "department_manager"
ASSIGN_DEPARTMENT_PERMISSION = "users.assign_user_department"


class UserDepartmentAssignmentError(ValueError):
    """Base error for an invalid user department assignment."""


class UserDepartmentUserMissing(UserDepartmentAssignmentError):
    """Raised when the target user does not exist."""


class UserDepartmentProfileMissing(UserDepartmentAssignmentError):
    """Raised when the target user has no UserProfile."""


class UserDepartmentDepartmentMissing(UserDepartmentAssignmentError):
    """Raised when the requested department does not exist."""


class UserDepartmentPermissionDenied(UserDepartmentAssignmentError):
    """Raised when the operator lacks the required business permission."""


class UserDepartmentScopeDenied(UserDepartmentAssignmentError):
    """Raised when a manager targets data outside their own department."""


@dataclass(frozen=True, slots=True)
class UserDepartmentAssignmentResult:
    user_id: int
    username: str
    department_id: int | None
    department_name: str | None


def update_user_department(
    *,
    user_id: int,
    department_id: int | None,
    operator: UserLike,
) -> UserDepartmentAssignmentResult:
    """Assign a user department with permission and race-safe validation."""

    with transaction.atomic():
        requested_department = None
        if department_id is not None:
            requested_department = (
                Department.objects.select_for_update()
                .filter(pk=department_id)
                .first()
            )
            if requested_department is None:
                raise UserDepartmentDepartmentMissing("部门不存在")

        involved_user_ids = sorted({operator.pk, user_id})
        locked_users = {
            user.pk: user
            for user in (
                User.objects.select_for_update()
                .filter(pk__in=involved_user_ids)
                .order_by("pk")
            )
        }
        if user_id not in locked_users:
            raise UserDepartmentUserMissing("用户不存在")
        if operator.pk not in locked_users:
            raise UserDepartmentPermissionDenied("无权修改用户部门。")

        locked_profiles = {
            profile.user_id: profile
            for profile in (
                UserProfile.objects.select_for_update()
                .filter(user_id__in=involved_user_ids)
                .only("id", "user_id", "department_id")
                .order_by("user_id")
            )
        }
        target_profile = locked_profiles.get(user_id)
        if target_profile is None:
            raise UserDepartmentProfileMissing("用户资料不存在")

        resolved_permissions = resolve_user_permissions(operator)
        grant = resolved_permissions.permissions.get(
            ASSIGN_DEPARTMENT_PERMISSION
        )
        if grant is None:
            raise UserDepartmentPermissionDenied("无权修改用户部门。")

        if not resolved_permissions.is_admin:
            if DEPARTMENT_MANAGER_ROLE_CODE not in grant.role_codes:
                raise UserDepartmentPermissionDenied("无权修改用户部门。")

            context = resolve_user_scope_context(operator)
            resolution = context.get_permission(
                ASSIGN_DEPARTMENT_PERMISSION
            )
            if (
                resolution is None
                or RolePermissionScope.DEPARTMENT
                not in resolution.effective_scopes
                or context.department_id is None
            ):
                raise UserDepartmentScopeDenied(
                    "无权操作该部门用户。"
                )

            if target_profile.department_id != context.department_id:
                raise UserDepartmentScopeDenied(
                    "只能操作自己部门的用户。"
                )
            if department_id != context.department_id:
                raise UserDepartmentScopeDenied(
                    "只能将用户保留在自己所属部门。"
                )

        target_profile.department = requested_department
        target_profile.save(update_fields=["department"])
        target_user = locked_users[user_id]
        return UserDepartmentAssignmentResult(
            user_id=target_user.pk,
            username=target_user.username,
            department_id=target_profile.department_id,
            department_name=(
                requested_department.name
                if requested_department is not None
                else None
            ),
        )
