import inspect

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.db import DatabaseError
from django.db.models import Q
from django.test import TestCase
from unittest.mock import patch

from apps.departments.models import Department

from .models import Role, RolePermission, RolePermissionScope, UserRole
from .services.scope_resolver import (
    build_scope_query,
    merge_permission_scopes,
    resolve_user_scope_context,
)

User = get_user_model()


class RecordingScopeQueryBuilder:
    def __init__(self, self_field="owner_id", department_field="department_id"):
        self.self_field = self_field
        self.department_field = department_field
        self.calls = []

    def department_scope_q(self, department_id):
        self.calls.append(("department", department_id))
        return Q(**{self.department_field: department_id})

    def self_scope_q(self, user_id):
        self.calls.append(("self", user_id))
        return Q(**{self.self_field: user_id})


class TicketScopeQueryBuilder(RecordingScopeQueryBuilder):
    def __init__(self):
        super().__init__(department_field="department_id")

    def self_scope_q(self, user_id):
        self.calls.append(("self", user_id))
        return (
            Q(creator_id=user_id)
            | Q(assignee_id=user_id)
        )


class ScopeResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="scope_user",
            email="scope_user@example.com",
            password="TaskFlow#2026",
        )
        self.department = Department.objects.create(
            name="解析测试部",
            description="Scope 服务测试部门",
        )

    def create_role(self, code, name=None):
        return Role.objects.create(
            name=name or f"角色 {code}",
            code=code,
        )

    def assign_role(self, role):
        UserRole.objects.create(
            user_profile=self.user.profile,
            role=role,
        )

    def set_department(self, department):
        profile = self.user.profile
        profile.department = department
        profile.save(update_fields=["department"])

    def grant_permission(self, role, app_label, codename, scope):
        permission = Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
        return RolePermission.objects.create(
            role=role,
            permission=permission,
            scope=scope,
        )

    def test_all_scope_remains_all(self):
        scopes = merge_permission_scopes([RolePermissionScope.ALL])

        self.assertEqual(scopes, frozenset({RolePermissionScope.ALL}))

    def test_department_scope_remains_department(self):
        scopes = merge_permission_scopes([
            RolePermissionScope.DEPARTMENT,
        ])

        self.assertEqual(
            scopes,
            frozenset({RolePermissionScope.DEPARTMENT}),
        )

    def test_self_scope_remains_self(self):
        scopes = merge_permission_scopes([RolePermissionScope.SELF])

        self.assertEqual(scopes, frozenset({RolePermissionScope.SELF}))

    def test_self_and_department_scopes_are_merged(self):
        scopes = merge_permission_scopes([
            RolePermissionScope.SELF,
            RolePermissionScope.DEPARTMENT,
        ])

        self.assertEqual(
            scopes,
            {
                RolePermissionScope.SELF,
                RolePermissionScope.DEPARTMENT,
            },
        )

    def test_all_and_self_scopes_are_merged_without_priority_loss(self):
        scopes = merge_permission_scopes([
            RolePermissionScope.ALL,
            RolePermissionScope.SELF,
        ])

        self.assertEqual(
            scopes,
            {RolePermissionScope.ALL, RolePermissionScope.SELF},
        )

    def test_all_three_scopes_are_merged(self):
        scopes = merge_permission_scopes([
            RolePermissionScope.ALL,
            RolePermissionScope.DEPARTMENT,
            RolePermissionScope.SELF,
        ])

        self.assertEqual(
            scopes,
            {
                RolePermissionScope.ALL,
                RolePermissionScope.DEPARTMENT,
                RolePermissionScope.SELF,
            },
        )

    def test_duplicate_scopes_are_deduplicated(self):
        scopes = merge_permission_scopes([
            RolePermissionScope.SELF,
            RolePermissionScope.SELF,
            "self",
        ])

        self.assertEqual(scopes, {RolePermissionScope.SELF})
        self.assertIsInstance(scopes, frozenset)

    def test_department_scope_is_denied_without_profile(self):
        self.user.profile.delete()

        context = resolve_user_scope_context(self.user)

        self.assertTrue(context.is_authenticated)
        self.assertFalse(context.profile_exists)
        self.assertIsNone(context.department_id)
        self.assertEqual(context.permission_scopes, {})

    def test_department_scope_is_denied_without_department(self):
        role = self.create_role(
            "scope_department_manager",
            "Scope 部门负责人",
        )
        self.assign_role(role)
        self.grant_permission(
            role,
            "tickets",
            "view_ticket",
            RolePermissionScope.DEPARTMENT,
        )

        context = resolve_user_scope_context(self.user)
        resolution = context.get_permission("tickets.view_ticket")

        self.assertIsNotNone(resolution)
        self.assertEqual(
            resolution.source_scopes,
            {RolePermissionScope.DEPARTMENT},
        )
        self.assertEqual(resolution.effective_scopes, frozenset())
        self.assertEqual(
            resolution.denied_scopes,
            {RolePermissionScope.DEPARTMENT},
        )
        self.assertFalse(resolution.is_allowed)

    def test_unauthenticated_user_is_rejected(self):
        context = resolve_user_scope_context(AnonymousUser())

        self.assertFalse(context.is_authenticated)
        self.assertFalse(context.profile_exists)
        self.assertIsNone(context.department_id)
        self.assertEqual(context.permission_scopes, {})

    def test_department_context_comes_from_current_user_profile(self):
        other_department = Department.objects.create(
            name="另一部门",
            description="不应被选择",
        )
        self.set_department(self.department)

        context = resolve_user_scope_context(self.user)
        parameters = inspect.signature(
            resolve_user_scope_context
        ).parameters

        self.assertEqual(context.department_id, self.department.pk)
        self.assertNotEqual(context.department_id, other_department.pk)
        self.assertEqual(list(parameters), ["user"])

    def test_all_scope_does_not_grant_another_permission(self):
        role = self.create_role("scope_employee", "Scope 普通员工")
        self.assign_role(role)
        self.grant_permission(
            role,
            "tickets",
            "view_ticket",
            RolePermissionScope.ALL,
        )

        context = resolve_user_scope_context(self.user)

        self.assertEqual(
            context.get_effective_scopes("tickets.view_ticket"),
            {RolePermissionScope.ALL},
        )
        self.assertFalse(
            context.get_effective_scopes("tickets.close_ticket")
        )

    def test_unknown_scope_is_rejected(self):
        with self.assertRaisesMessage(
            ValueError,
            "不支持的 Scope",
        ):
            merge_permission_scopes(["invalid_scope"])

    def test_scopes_from_multiple_permissions_do_not_pollute(self):
        employee = self.create_role(
            "scope_employee",
            "Scope 普通员工",
        )
        manager = self.create_role(
            "scope_department_manager",
            "Scope 部门负责人",
        )
        self.assign_role(employee)
        self.assign_role(manager)
        self.set_department(self.department)
        self.grant_permission(
            employee,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )
        self.grant_permission(
            manager,
            "departments",
            "change_department",
            RolePermissionScope.DEPARTMENT,
        )

        context = resolve_user_scope_context(self.user)

        self.assertEqual(
            context.get_effective_scopes("tickets.view_ticket"),
            {RolePermissionScope.SELF},
        )
        self.assertEqual(
            context.get_effective_scopes("departments.change_department"),
            {RolePermissionScope.DEPARTMENT},
        )

    def test_resource_specific_self_query_is_delegated(self):
        employee = self.create_role(
            "scope_employee",
            "Scope 普通员工",
        )
        self.assign_role(employee)
        self.grant_permission(
            employee,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )
        context = resolve_user_scope_context(self.user)
        ticket_builder = TicketScopeQueryBuilder()
        document_builder = RecordingScopeQueryBuilder(
            self_field="owner_id",
            department_field="group_id",
        )

        ticket_query = build_scope_query(
            context,
            "tickets.view_ticket",
            ticket_builder,
        )
        document_query = build_scope_query(
            context,
            "tickets.view_ticket",
            document_builder,
        )

        self.assertEqual(
            ticket_query,
            Q(creator_id=self.user.pk) | Q(assignee_id=self.user.pk),
        )
        self.assertEqual(
            document_query,
            Q(owner_id=self.user.pk),
        )
        self.assertEqual(
            set(ticket_builder.calls),
            {("self", self.user.pk)},
        )
        self.assertEqual(
            set(document_builder.calls),
            {("self", self.user.pk)},
        )

    def test_self_and_department_query_conditions_use_or(self):
        employee = self.create_role(
            "scope_employee",
            "Scope 普通员工",
        )
        manager = self.create_role(
            "scope_department_manager",
            "Scope 部门负责人",
        )
        self.assign_role(employee)
        self.assign_role(manager)
        self.set_department(self.department)
        self.grant_permission(
            employee,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )
        self.grant_permission(
            manager,
            "tickets",
            "view_ticket",
            RolePermissionScope.DEPARTMENT,
        )
        context = resolve_user_scope_context(self.user)
        builder = TicketScopeQueryBuilder()

        query = build_scope_query(
            context,
            "tickets.view_ticket",
            builder,
        )

        self.assertEqual(
            query,
            (
                Q(creator_id=self.user.pk)
                | Q(assignee_id=self.user.pk)
                | Q(department_id=self.department.pk)
            ),
        )
        self.assertEqual(
            set(builder.calls),
            {
                ("self", self.user.pk),
                ("department", self.department.pk),
            },
        )

    def test_all_scope_builds_unrestricted_query(self):
        employee = self.create_role(
            "scope_employee",
            "Scope 普通员工",
        )
        self.assign_role(employee)
        self.grant_permission(
            employee,
            "tickets",
            "view_ticket",
            RolePermissionScope.ALL,
        )
        context = resolve_user_scope_context(self.user)
        builder = TicketScopeQueryBuilder()

        query = build_scope_query(
            context,
            "tickets.view_ticket",
            builder,
        )

        self.assertEqual(query, Q())
        self.assertEqual(builder.calls, [])

    def test_missing_permission_builds_deny_all_query(self):
        context = resolve_user_scope_context(self.user)
        builder = TicketScopeQueryBuilder()

        query = build_scope_query(
            context,
            "tickets.close_ticket",
            builder,
        )

        self.assertEqual(query, Q(pk__in=[]))
        self.assertEqual(builder.calls, [])

    def test_profile_context_is_loaded_without_duplicate_queries(self):
        role = self.create_role(
            "scope_department_manager",
            "Scope 部门负责人",
        )
        self.assign_role(role)
        self.set_department(self.department)
        self.grant_permission(
            role,
            "tickets",
            "view_ticket",
            RolePermissionScope.DEPARTMENT,
        )

        with self.assertNumQueries(3):
            context = resolve_user_scope_context(self.user)

        self.assertEqual(context.department_id, self.department.pk)

    def test_database_error_is_not_converted_to_empty_context(self):
        with patch(
            "apps.users.services.scope_resolver._resolve_department_context",
            side_effect=DatabaseError("database unavailable"),
        ):
            with self.assertRaisesMessage(
                DatabaseError,
                "database unavailable",
            ):
                resolve_user_scope_context(self.user)
