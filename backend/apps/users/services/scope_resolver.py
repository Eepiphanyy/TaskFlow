from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import Q

from apps.users.models import RolePermissionScope, UserProfile
from apps.users.services.permission_resolver import (
    UserLike,
    resolve_user_permissions,
)

logger = logging.getLogger(__name__)


class ResourceScopeQueryBuilder(Protocol):
    """Build resource-specific ``Q`` objects for non-admin scopes.

    The generic Scope service deliberately does not know which model fields
    represent a department or a self-related resource. Each resource supplies
    those details through this adapter.
    """

    def department_scope_q(self, department_id: int) -> Q:
        """Return the resource condition for one department."""
        ...

    def self_scope_q(self, user_id: int) -> Q:
        """Return the resource-specific self condition for one user."""
        ...


@dataclass(frozen=True, slots=True)
class PermissionScopeResolution:
    """Resolved scopes for one permission without Django model objects."""

    permission_key: str
    user_id: int | None
    department_id: int | None
    source_scopes: frozenset[RolePermissionScope]
    effective_scopes: frozenset[RolePermissionScope]
    denied_scopes: frozenset[RolePermissionScope]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_scopes",
            frozenset(self.source_scopes),
        )
        object.__setattr__(
            self,
            "effective_scopes",
            frozenset(self.effective_scopes),
        )
        object.__setattr__(
            self,
            "denied_scopes",
            frozenset(self.denied_scopes),
        )

    @property
    def is_allowed(self) -> bool:
        return bool(self.effective_scopes)


@dataclass(frozen=True, slots=True)
class UserScopeContext:
    """Immutable user context for resolving and applying permission scopes."""

    user_id: int | None
    is_authenticated: bool
    profile_exists: bool
    department_id: int | None
    permission_scopes: Mapping[str, PermissionScopeResolution]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "permission_scopes",
            MappingProxyType(dict(self.permission_scopes)),
        )

    @property
    def has_department_context(self) -> bool:
        return (
            self.is_authenticated
            and self.profile_exists
            and self.department_id is not None
        )

    def get_permission(
        self,
        permission_key: str,
    ) -> PermissionScopeResolution | None:
        return self.permission_scopes.get(permission_key)

    def get_effective_scopes(
        self,
        permission_key: str,
    ) -> frozenset[RolePermissionScope]:
        resolution = self.get_permission(permission_key)
        return (
            resolution.effective_scopes
            if resolution is not None
            else frozenset()
        )


def merge_permission_scopes(
    scopes: Iterable[str | RolePermissionScope],
) -> frozenset[RolePermissionScope]:
    """Normalize and deduplicate scopes without selecting one maximum scope."""

    if isinstance(scopes, str):
        scopes = (scopes,)

    normalized_scopes: set[RolePermissionScope] = set()
    for scope in scopes:
        try:
            normalized_scopes.add(RolePermissionScope(scope))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"不支持的 Scope：{scope!r}") from exc
    return frozenset(normalized_scopes)


def _empty_scope_context(
    *,
    user_id: int | None = None,
    is_authenticated: bool = False,
    profile_exists: bool = False,
    department_id: int | None = None,
) -> UserScopeContext:
    return UserScopeContext(
        user_id=user_id,
        is_authenticated=is_authenticated,
        profile_exists=profile_exists,
        department_id=department_id,
        permission_scopes={},
    )


def _resolve_department_context(
    user: AbstractBaseUser,
) -> tuple[bool, int | None]:
    profile = (
        UserProfile.objects.filter(user=user)
        .select_related("department")
        .only("user_id", "department_id", "department__id")
        .first()
    )
    if profile is None:
        return False, None

    department_id = (
        profile.department.pk
        if profile.department is not None
        else None
    )
    return True, department_id


def _build_permission_scope_resolution(
    permission_key: str,
    user_id: int | None,
    department_id: int | None,
    source_scopes: Iterable[str],
) -> PermissionScopeResolution:
    normalized_scopes = merge_permission_scopes(source_scopes)
    department_denied = (
        frozenset({RolePermissionScope.DEPARTMENT})
        if department_id is None
        else frozenset()
    )
    denied_scopes = normalized_scopes & department_denied
    effective_scopes = normalized_scopes - denied_scopes
    return PermissionScopeResolution(
        permission_key=permission_key,
        user_id=user_id,
        department_id=department_id,
        source_scopes=normalized_scopes,
        effective_scopes=effective_scopes,
        denied_scopes=denied_scopes,
    )


def resolve_user_scope_context(user: UserLike) -> UserScopeContext:
    """Resolve trusted department context and scoped TaskFlow permissions.

    Department context comes only from the authenticated user's database
    profile. A DEPARTMENT scope without a valid department is denied rather
    than converted to ALL or SELF.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return _empty_scope_context()

    try:
        profile_exists, department_id = _resolve_department_context(user)
        if not profile_exists:
            return _empty_scope_context(
                user_id=user.pk,
                is_authenticated=True,
                profile_exists=False,
            )

        resolved_permissions = resolve_user_permissions(user)
        permission_scopes = {
            permission_key: _build_permission_scope_resolution(
                permission_key=permission_key,
                user_id=user.pk,
                department_id=department_id,
                source_scopes=grant.scopes,
            )
            for permission_key, grant
            in resolved_permissions.permissions.items()
        }
        return UserScopeContext(
            user_id=user.pk,
            is_authenticated=True,
            profile_exists=True,
            department_id=department_id,
            permission_scopes=permission_scopes,
        )
    except Exception:
        logger.exception(
            "Failed to resolve TaskFlow scope context for user_id=%s",
            getattr(user, "pk", None),
        )
        raise


def build_scope_query(
    context: UserScopeContext,
    permission_key: str,
    resource_builder: ResourceScopeQueryBuilder,
) -> Q:
    """Convert effective scopes into a resource-specific ``Q`` object.

    ``ALL`` produces an unconstrained ``Q``. Other scopes are delegated to the
    resource builder and combined with OR, which represents the union of all
    authorized data sets. Missing context or permission produces a deny-all
    condition.
    """

    resolution = context.get_permission(permission_key)
    if resolution is None or not resolution.effective_scopes:
        return Q(pk__in=[])

    if RolePermissionScope.ALL in resolution.effective_scopes:
        return Q()

    conditions: list[Q] = []
    if (
        RolePermissionScope.SELF in resolution.effective_scopes
        and resolution.user_id is not None
    ):
        conditions.append(
            resource_builder.self_scope_q(resolution.user_id)
        )

    if (
        RolePermissionScope.DEPARTMENT in resolution.effective_scopes
        and resolution.department_id is not None
    ):
        conditions.append(
            resource_builder.department_scope_q(
                resolution.department_id
            )
        )

    if not conditions:
        return Q(pk__in=[])

    combined = conditions[0]
    for condition in conditions[1:]:
        combined |= condition
    return combined
