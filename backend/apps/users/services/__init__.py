"""Reusable TaskFlow business services."""

from .permission_resolver import (
    PermissionGrant,
    UserPermissions,
    get_permission_scopes,
    has_permission,
    is_taskflow_admin,
    resolve_user_permissions,
)
from .scope_resolver import (
    PermissionScopeResolution,
    ResourceScopeQueryBuilder,
    UserScopeContext,
    build_scope_query,
    merge_permission_scopes,
    resolve_user_scope_context,
)
from .user_department import (
    UserDepartmentAssignmentError,
    UserDepartmentAssignmentResult,
    UserDepartmentDepartmentMissing,
    UserDepartmentPermissionDenied,
    UserDepartmentProfileMissing,
    UserDepartmentScopeDenied,
    UserDepartmentUserMissing,
    update_user_department,
)

__all__ = [
    "PermissionGrant",
    "PermissionScopeResolution",
    "ResourceScopeQueryBuilder",
    "UserPermissions",
    "UserScopeContext",
    "UserDepartmentAssignmentError",
    "UserDepartmentAssignmentResult",
    "UserDepartmentDepartmentMissing",
    "UserDepartmentPermissionDenied",
    "UserDepartmentProfileMissing",
    "UserDepartmentScopeDenied",
    "UserDepartmentUserMissing",
    "build_scope_query",
    "get_permission_scopes",
    "has_permission",
    "is_taskflow_admin",
    "merge_permission_scopes",
    "resolve_user_permissions",
    "resolve_user_scope_context",
    "update_user_department",
]
