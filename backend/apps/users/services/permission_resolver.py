from __future__ import annotations

import logging
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser, Permission
from django.db.models import Q

from apps.users.models import Role, RolePermission, RolePermissionScope
from apps.users.rbac_matrix import REQUIRED_PERMISSIONS

UserLike = AbstractBaseUser | AnonymousUser | None

ADMIN_ROLE_CODE = "admin"
REQUIRED_PERMISSION_KEYS = frozenset(
    f"{app_label}.{codename}"
    for app_label, codename in REQUIRED_PERMISSIONS
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    """A resolved TaskFlow permission without exposing Django model objects."""

    app_label: str
    codename: str
    scopes: frozenset[str]
    role_codes: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scopes", frozenset(self.scopes))
        object.__setattr__(self, "role_codes", frozenset(self.role_codes))

    @property
    def key(self) -> str:
        return f"{self.app_label}.{self.codename}"


@dataclass(frozen=True, slots=True)
class UserPermissions:
    """Immutable permission snapshot for one user."""

    is_authenticated: bool
    is_admin: bool
    role_codes: frozenset[str]
    permissions: Mapping[str, PermissionGrant]

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_codes", frozenset(self.role_codes))
        object.__setattr__(
            self,
            "permissions",
            MappingProxyType(dict(self.permissions)),
        )

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.permissions

    def get_scopes(self, permission_key: str) -> frozenset[str]:
        grant = self.permissions.get(permission_key)
        return grant.scopes if grant is not None else frozenset()


@dataclass(slots=True)
class _PermissionAccumulator:
    app_label: str
    codename: str
    scopes: set[str]
    role_codes: set[str]


def _empty_permissions(is_authenticated: bool) -> UserPermissions:
    return UserPermissions(
        is_authenticated=is_authenticated,
        is_admin=False,
        role_codes=frozenset(),
        permissions={},
    )


def _is_authenticated(user: UserLike) -> bool:
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
    )


def _is_registered_permission_key(permission_key: str) -> bool:
    return (
        isinstance(permission_key, str)
        and permission_key in REQUIRED_PERMISSION_KEYS
    )


def _load_user_roles(user: AbstractBaseUser) -> list[Role]:
    return list(
        Role.objects.filter(users__user=user)
        .only("id", "code")
        .order_by("code")
    )


def _required_permission_query() -> Q:
    query = Q()
    for app_label, codename in REQUIRED_PERMISSIONS:
        query |= Q(
            content_type__app_label=app_label,
            codename=codename,
        )
    return query


def _load_existing_required_permission_keys() -> set[tuple[str, str]]:
    return set(
        Permission.objects.filter(_required_permission_query())
        .values_list("content_type__app_label", "codename")
    )


def _build_admin_permissions(
    role_codes: frozenset[str],
) -> UserPermissions:
    existing_keys = _load_existing_required_permission_keys()
    permission_map = {
        f"{app_label}.{codename}": PermissionGrant(
            app_label=app_label,
            codename=codename,
            scopes=frozenset({RolePermissionScope.ALL}),
            role_codes=frozenset({ADMIN_ROLE_CODE}),
        )
        for app_label, codename in REQUIRED_PERMISSIONS
        if (app_label, codename) in existing_keys
    }
    return UserPermissions(
        is_authenticated=True,
        is_admin=True,
        role_codes=role_codes,
        permissions=permission_map,
    )


def _build_role_permissions(
    roles: list[Role],
    role_codes: frozenset[str],
) -> UserPermissions:
    role_permissions = (
        RolePermission.objects.filter(
            role_id__in=[role.pk for role in roles]
        )
        .select_related("role", "permission__content_type")
        .order_by(
            "permission__content_type__app_label",
            "permission__codename",
            "role__code",
        )
    )

    grouped: dict[str, _PermissionAccumulator] = {}
    for relation in role_permissions:
        app_label = relation.permission.content_type.app_label
        codename = relation.permission.codename
        permission_key = f"{app_label}.{codename}"
        if permission_key not in REQUIRED_PERMISSION_KEYS:
            continue

        group = grouped.setdefault(
            permission_key,
            _PermissionAccumulator(
                app_label=app_label,
                codename=codename,
                scopes=set(),
                role_codes=set(),
            ),
        )
        group.scopes.add(relation.scope)
        group.role_codes.add(relation.role.code)

    permission_map = {
        permission_key: PermissionGrant(
            app_label=group.app_label,
            codename=group.codename,
            scopes=frozenset(group.scopes),
            role_codes=frozenset(group.role_codes),
        )
        for permission_key, group in grouped.items()
    }
    return UserPermissions(
        is_authenticated=True,
        is_admin=False,
        role_codes=role_codes,
        permissions=permission_map,
    )


def resolve_user_permissions(user: UserLike) -> UserPermissions:
    """Resolve all registered TaskFlow permissions for a Django user.

    Only permissions listed in ``REQUIRED_PERMISSIONS`` are considered.
    A TaskFlow admin bypasses RolePermission rows and receives ``ALL`` for
    every registered permission that exists in the database. Database errors
    are logged and re-raised so callers cannot mistake system failures for a
    normal authorization denial.
    """

    if not _is_authenticated(user):
        return _empty_permissions(is_authenticated=False)

    try:
        roles = _load_user_roles(user)
        if not roles:
            return _empty_permissions(is_authenticated=True)

        role_codes = frozenset(role.code for role in roles)
        if ADMIN_ROLE_CODE in role_codes:
            return _build_admin_permissions(role_codes)

        return _build_role_permissions(roles, role_codes)
    except Exception:
        logger.exception(
            "Failed to resolve TaskFlow permissions for user_id=%s",
            getattr(user, "pk", None),
        )
        raise


def has_permission(user: UserLike, permission_key: str) -> bool:
    """Return whether a user has one registered TaskFlow permission."""

    if not _is_registered_permission_key(permission_key):
        return False
    return resolve_user_permissions(user).has_permission(permission_key)


def get_permission_scopes(
    user: UserLike,
    permission_key: str,
) -> frozenset[str]:
    """Return every resolved scope for one registered TaskFlow permission."""

    if not _is_registered_permission_key(permission_key):
        return frozenset()
    return resolve_user_permissions(user).get_scopes(permission_key)


def is_taskflow_admin(user: UserLike) -> bool:
    """Return whether the user has the TaskFlow ``admin`` business role."""

    if not _is_authenticated(user):
        return False

    try:
        return any(
            role.code == ADMIN_ROLE_CODE
            for role in _load_user_roles(user)
        )
    except Exception:
        logger.exception(
            "Failed to resolve TaskFlow admin role for user_id=%s",
            getattr(user, "pk", None),
        )
        raise
