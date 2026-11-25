from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError
from django.test import TestCase
from unittest.mock import patch

from .models import Role, RolePermission, RolePermissionScope, UserRole
from .rbac_matrix import REQUIRED_PERMISSIONS
from .services.permission_resolver import (
    PermissionGrant,
    UserPermissions,
    get_permission_scopes,
    has_permission,
    is_taskflow_admin,
    resolve_user_permissions,
)

User = get_user_model()


class PermissionResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="resolver_user",
            email="resolver_user@example.com",
            password="TaskFlow#2026",
        )

    def create_role(self, code, name=None):
        return Role.objects.create(
            name=name or f"角色 {code}",
            code=code,
        )

    def assign_role(self, user, role):
        UserRole.objects.create(
            user_profile=user.profile,
            role=role,
        )

    def get_permission(self, app_label, codename):
        return Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )

    def grant_permission(self, role, app_label, codename, scope):
        return RolePermission.objects.create(
            role=role,
            permission=self.get_permission(app_label, codename),
            scope=scope,
        )

    def test_anonymous_user_is_denied(self):
        result = resolve_user_permissions(AnonymousUser())

        self.assertFalse(result.is_authenticated)
        self.assertFalse(result.is_admin)
        self.assertEqual(result.role_codes, frozenset())
        self.assertEqual(result.permissions, {})
        self.assertFalse(has_permission(
            AnonymousUser(),
            "tickets.view_ticket",
        ))

    def test_user_without_profile_is_denied(self):
        self.user.profile.delete()

        result = resolve_user_permissions(self.user)

        self.assertTrue(result.is_authenticated)
        self.assertEqual(result.permissions, {})
        self.assertFalse(is_taskflow_admin(self.user))

    def test_user_without_business_role_has_no_permissions(self):
        result = resolve_user_permissions(self.user)

        self.assertTrue(result.is_authenticated)
        self.assertFalse(result.is_admin)
        self.assertEqual(result.role_codes, frozenset())
        self.assertEqual(result.permissions, {})

    def test_single_role_and_single_permission_are_resolved(self):
        role = self.create_role("resolver_employee", "解析员工")
        self.assign_role(self.user, role)
        self.grant_permission(
            role,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )

        result = resolve_user_permissions(self.user)

        grant = result.permissions["tickets.view_ticket"]
        self.assertIsInstance(result, UserPermissions)
        self.assertIsInstance(grant, PermissionGrant)
        self.assertEqual(grant.app_label, "tickets")
        self.assertEqual(grant.codename, "view_ticket")
        self.assertEqual(grant.scopes, {RolePermissionScope.SELF})
        self.assertEqual(grant.role_codes, {role.code})
        self.assertNotIsInstance(grant, RolePermission)

    def test_multiple_roles_are_resolved(self):
        employee = self.create_role("resolver_employee", "解析员工")
        handler = self.create_role("resolver_handler", "解析处理员")
        self.assign_role(self.user, employee)
        self.assign_role(self.user, handler)
        self.grant_permission(
            employee,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )
        self.grant_permission(
            handler,
            "tickets",
            "process_ticket",
            RolePermissionScope.SELF,
        )

        result = resolve_user_permissions(self.user)

        self.assertEqual(
            result.role_codes,
            {employee.code, handler.code},
        )
        self.assertEqual(
            set(result.permissions),
            {"tickets.view_ticket", "tickets.process_ticket"},
        )

    def test_same_permission_keeps_self_and_department_scopes(self):
        employee = self.create_role("resolver_employee", "解析员工")
        manager = self.create_role(
            "resolver_department_manager",
            "解析部门负责人",
        )
        self.assign_role(self.user, employee)
        self.assign_role(self.user, manager)
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

        result = resolve_user_permissions(self.user)

        self.assertEqual(
            result.get_scopes("tickets.view_ticket"),
            {
                RolePermissionScope.SELF,
                RolePermissionScope.DEPARTMENT,
            },
        )

    def test_duplicate_scopes_across_roles_are_deduplicated(self):
        first_role = self.create_role("resolver_employee", "解析员工")
        second_role = self.create_role("resolver_handler", "解析处理员")
        self.assign_role(self.user, first_role)
        self.assign_role(self.user, second_role)
        self.grant_permission(
            first_role,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )
        self.grant_permission(
            second_role,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )

        scopes = get_permission_scopes(
            self.user,
            "tickets.view_ticket",
        )

        self.assertEqual(scopes, frozenset({RolePermissionScope.SELF}))
        self.assertIsInstance(scopes, frozenset)

    def test_admin_receives_all_registered_business_permissions(self):
        admin_role = self.create_role("admin", "系统管理员")
        self.assign_role(self.user, admin_role)

        result = resolve_user_permissions(self.user)

        expected_keys = {
            f"{app_label}.{codename}"
            for app_label, codename in REQUIRED_PERMISSIONS
        }
        self.assertTrue(result.is_admin)
        self.assertEqual(set(result.permissions), expected_keys)
        self.assertTrue(all(
            grant.scopes == {RolePermissionScope.ALL}
            for grant in result.permissions.values()
        ))

    def test_admin_does_not_receive_django_admin_permission(self):
        admin_role = self.create_role("admin", "系统管理员")
        self.assign_role(self.user, admin_role)

        result = resolve_user_permissions(self.user)

        self.assertNotIn("auth.add_user", result.permissions)
        self.assertFalse(has_permission(self.user, "auth.add_user"))

    def test_admin_does_not_receive_third_party_permission(self):
        admin_role = self.create_role("admin", "系统管理员")
        self.assign_role(self.user, admin_role)
        session_content_type = ContentType.objects.get(
            app_label="sessions",
            model="session",
        )
        third_party_permission = Permission.objects.create(
            name="Third party permission",
            content_type=session_content_type,
            codename="third_party_permission",
        )
        RolePermission.objects.create(
            role=admin_role,
            permission=third_party_permission,
            scope=RolePermissionScope.ALL,
        )

        result = resolve_user_permissions(self.user)

        self.assertNotIn(
            "sessions.third_party_permission",
            result.permissions,
        )

    def test_staff_user_is_not_business_admin(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        employee = self.create_role(
            "resolver_employee",
            "解析员工",
        )
        self.assign_role(self.user, employee)
        self.grant_permission(
            employee,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )

        result = resolve_user_permissions(self.user)

        self.assertFalse(is_taskflow_admin(self.user))
        self.assertFalse(result.is_admin)
        self.assertEqual(
            set(result.permissions),
            {"tickets.view_ticket"},
        )

    def test_superuser_is_not_business_admin(self):
        superuser = User.objects.create_superuser(
            username="resolver_superuser",
            email="resolver_superuser@example.com",
            password="TaskFlow#2026",
        )

        result = resolve_user_permissions(superuser)

        self.assertTrue(superuser.is_superuser)
        self.assertFalse(is_taskflow_admin(superuser))
        self.assertFalse(result.is_admin)
        self.assertEqual(result.permissions, {})

    def test_nonexistent_permission_is_denied(self):
        self.assertFalse(has_permission(
            self.user,
            "tickets.permission_that_does_not_exist",
        ))
        self.assertEqual(
            get_permission_scopes(
                self.user,
                "tickets.permission_that_does_not_exist",
            ),
            frozenset(),
        )

    def test_unregistered_existing_permission_is_denied(self):
        role = self.create_role("resolver_employee", "解析员工")
        self.assign_role(self.user, role)
        unregistered_permission = Permission.objects.get(
            content_type__app_label="auth",
            codename="add_user",
        )
        RolePermission.objects.create(
            role=role,
            permission=unregistered_permission,
            scope=RolePermissionScope.ALL,
        )

        result = resolve_user_permissions(self.user)

        self.assertEqual(result.permissions, {})
        self.assertFalse(has_permission(self.user, "auth.add_user"))

    def test_role_without_role_permission_is_denied(self):
        role = self.create_role("resolver_employee", "解析员工")
        self.assign_role(self.user, role)

        self.assertFalse(has_permission(
            self.user,
            "tickets.view_ticket",
        ))
        self.assertEqual(
            resolve_user_permissions(self.user).role_codes,
            {role.code},
        )

    def test_permissions_from_different_roles_do_not_pollute_each_other(self):
        viewer = self.create_role("resolver_viewer", "解析只读角色")
        department_viewer = self.create_role(
            "resolver_department_viewer",
            "解析部门查询角色",
        )
        self.assign_role(self.user, viewer)
        self.assign_role(self.user, department_viewer)
        self.grant_permission(
            viewer,
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )
        self.grant_permission(
            department_viewer,
            "departments",
            "view_department",
            RolePermissionScope.DEPARTMENT,
        )

        result = resolve_user_permissions(self.user)

        self.assertEqual(
            result.get_scopes("tickets.view_ticket"),
            {RolePermissionScope.SELF},
        )
        self.assertEqual(
            result.get_scopes("departments.view_department"),
            {RolePermissionScope.DEPARTMENT},
        )
        self.assertFalse(
            result.has_permission("tickets.close_ticket")
        )

    def test_resolution_does_not_produce_n_plus_one_queries(self):
        roles = [
            self.create_role(f"resolver_role_{index}", f"解析角色{index}")
            for index in range(1, 4)
        ]
        for role in roles:
            self.assign_role(self.user, role)
        self.grant_permission(
            roles[0],
            "departments",
            "view_department",
            RolePermissionScope.ALL,
        )
        self.grant_permission(
            roles[1],
            "tickets",
            "view_ticket",
            RolePermissionScope.SELF,
        )
        self.grant_permission(
            roles[2],
            "tickets",
            "process_ticket",
            RolePermissionScope.SELF,
        )

        with self.assertNumQueries(2):
            result = resolve_user_permissions(self.user)

        self.assertEqual(len(result.permissions), 3)

    def test_database_error_is_not_converted_to_denial(self):
        with patch(
            "apps.users.services.permission_resolver._load_user_roles",
            side_effect=DatabaseError("database unavailable"),
        ):
            with self.assertRaisesMessage(
                DatabaseError,
                "database unavailable",
            ):
                resolve_user_permissions(self.user)
