from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from .models import Role, RolePermission, RolePermissionScope, UserRole
from .rbac_matrix import (
    DEFAULT_ROLE_CODES,
    DEFAULT_ROLE_GRANTS,
    REQUIRED_PERMISSIONS,
)

User = get_user_model()


class SyncRBACPermissionsCommandTests(TestCase):
    def setUp(self):
        call_command("init_default_roles", stdout=StringIO())

    def get_permission(self, app_label, codename):
        return Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )

    def test_custom_permissions_are_created_by_migrations(self):
        custom_permissions = (
            ("departments", "view_department_members"),
            ("users", "assign_user_department"),
            ("users", "manage_user_roles"),
            ("tickets", "assign_ticket"),
            ("tickets", "process_ticket"),
            ("tickets", "close_ticket"),
        )

        for app_label, codename in custom_permissions:
            self.assertTrue(Permission.objects.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).exists())

    def test_required_standard_permissions_exist(self):
        for app_label, codename in REQUIRED_PERMISSIONS:
            self.assertTrue(Permission.objects.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).exists())

    def test_same_app_extra_codename_is_not_included(self):
        ticket_content_type = ContentType.objects.get(
            app_label="tickets",
            model="ticket",
        )
        extra_permission = Permission.objects.create(
            name="Extra ticket permission with matrix codename",
            content_type=ticket_content_type,
            codename="manage_user_roles",
        )
        output = StringIO()

        call_command("sync_rbac_permissions", stdout=output)

        self.assertIn("找到 Permission：13 个", output.getvalue())
        self.assertEqual(
            RolePermission.objects.count(),
            len(DEFAULT_ROLE_GRANTS),
        )
        self.assertFalse(RolePermission.objects.filter(
            permission=extra_permission
        ).exists())

    def test_cross_app_same_codename_is_not_included(self):
        role_content_type = ContentType.objects.get(
            app_label="users",
            model="role",
        )
        extra_permission = Permission.objects.create(
            name="Extra role permission named like ticket view",
            content_type=role_content_type,
            codename="view_ticket",
        )
        output = StringIO()

        call_command("sync_rbac_permissions", stdout=output)

        self.assertIn("找到 Permission：13 个", output.getvalue())
        self.assertEqual(
            RolePermission.objects.count(),
            len(DEFAULT_ROLE_GRANTS),
        )
        self.assertFalse(RolePermission.objects.filter(
            permission=extra_permission
        ).exists())

    def test_unrelated_extra_permission_does_not_affect_matrix(self):
        group_content_type = ContentType.objects.get(
            app_label="auth",
            model="group",
        )
        extra_permission = Permission.objects.create(
            name="Unrelated permission",
            content_type=group_content_type,
            codename="unrelated_matrix_permission",
        )
        output = StringIO()

        call_command("sync_rbac_permissions", stdout=output)

        self.assertIn("找到 Permission：13 个", output.getvalue())
        self.assertEqual(
            RolePermission.objects.count(),
            len(DEFAULT_ROLE_GRANTS),
        )
        self.assertFalse(RolePermission.objects.filter(
            permission=extra_permission
        ).exists())

    def test_all_default_roles_are_found(self):
        output = StringIO()

        call_command("sync_rbac_permissions", stdout=output)

        self.assertIn("找到角色：4 个", output.getvalue())
        self.assertEqual(
            set(Role.objects.filter(
                code__in=DEFAULT_ROLE_CODES
            ).values_list("code", flat=True)),
            set(DEFAULT_ROLE_CODES),
        )

    def test_first_execution_creates_complete_default_matrix(self):
        output = StringIO()

        call_command("sync_rbac_permissions", stdout=output)

        self.assertEqual(
            RolePermission.objects.count(),
            len(DEFAULT_ROLE_GRANTS),
        )
        expected = {
            (
                role_code,
                f"{app_label}.{codename}",
                scope,
            )
            for role_code, app_label, codename, scope in DEFAULT_ROLE_GRANTS
        }
        actual = {
            (
                relation.role.code,
                (
                    f"{relation.permission.content_type.app_label}."
                    f"{relation.permission.codename}"
                ),
                relation.scope,
            )
            for relation in RolePermission.objects.select_related(
                "role",
                "permission__content_type",
            )
        }
        self.assertEqual(actual, expected)
        self.assertIn("新增 32 个", output.getvalue())

    def test_second_execution_is_idempotent(self):
        call_command("sync_rbac_permissions", stdout=StringIO())
        output = StringIO()

        call_command("sync_rbac_permissions", stdout=output)

        self.assertEqual(
            RolePermission.objects.count(),
            len(DEFAULT_ROLE_GRANTS),
        )
        self.assertIn("新增 0 个", output.getvalue())
        self.assertIn("已存在 32 个", output.getvalue())

    def test_scope_conflict_is_not_overwritten_without_force(self):
        call_command("sync_rbac_permissions", stdout=StringIO())
        relation = RolePermission.objects.get(
            role__code="admin",
            permission__content_type__app_label="departments",
            permission__codename="view_department",
        )
        relation.scope = RolePermissionScope.SELF
        relation.save(update_fields=["scope"])
        output = StringIO()

        call_command("sync_rbac_permissions", stdout=output)

        relation.refresh_from_db()
        self.assertEqual(relation.scope, RolePermissionScope.SELF)
        self.assertIn("Scope 冲突", output.getvalue())
        self.assertEqual(
            RolePermission.objects.count(),
            len(DEFAULT_ROLE_GRANTS),
        )

    def test_force_updates_conflicting_scope(self):
        call_command("sync_rbac_permissions", stdout=StringIO())
        relation = RolePermission.objects.get(
            role__code="admin",
            permission__content_type__app_label="departments",
            permission__codename="view_department",
        )
        relation.scope = RolePermissionScope.SELF
        relation.save(update_fields=["scope"])
        output = StringIO()

        call_command(
            "sync_rbac_permissions",
            force=True,
            stdout=output,
        )

        relation.refresh_from_db()
        self.assertEqual(relation.scope, RolePermissionScope.ALL)
        self.assertIn("准备更新 Scope", output.getvalue())
        self.assertIn("更新 1 个", output.getvalue())

    def test_force_does_not_create_duplicate_relations(self):
        call_command("sync_rbac_permissions", stdout=StringIO())
        relation = RolePermission.objects.get(
            role__code="employee",
            permission__content_type__app_label="tickets",
            permission__codename="view_ticket",
        )
        relation.scope = RolePermissionScope.ALL
        relation.save(update_fields=["scope"])

        call_command(
            "sync_rbac_permissions",
            force=True,
            stdout=StringIO(),
        )

        self.assertEqual(
            RolePermission.objects.count(),
            len(DEFAULT_ROLE_GRANTS),
        )

    def test_missing_role_raises_clear_error(self):
        Role.objects.filter(code="employee").delete()
        output = StringIO()

        with self.assertRaisesMessage(CommandError, "缺少角色"):
            call_command("sync_rbac_permissions", stdout=output)

        self.assertIn("找到角色：3 个", output.getvalue())
        self.assertEqual(RolePermission.objects.count(), 0)

    def test_missing_permission_raises_clear_error(self):
        permission = self.get_permission("tickets", "assign_ticket")
        permission.delete()
        output = StringIO()

        with self.assertRaisesMessage(CommandError, "缺少 Permission"):
            call_command("sync_rbac_permissions", stdout=output)

        self.assertIn("找到 Permission：12 个", output.getvalue())
        self.assertEqual(RolePermission.objects.count(), 0)

    def test_sync_failure_rolls_back_created_relations(self):
        original = RolePermission.objects.get_or_create
        calls = 0

        def flaky_get_or_create(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return original(*args, **kwargs)
            raise RuntimeError("simulated failure")

        with patch(
            "apps.users.management.commands.sync_rbac_permissions."
            "RolePermission.objects.get_or_create",
            side_effect=flaky_get_or_create,
        ):
            with self.assertRaisesMessage(
                CommandError,
                "事务已回滚",
            ):
                call_command(
                    "sync_rbac_permissions",
                    stdout=StringIO(),
                )

        self.assertEqual(RolePermission.objects.count(), 0)

    def test_sync_does_not_modify_user_roles_or_users(self):
        user = User.objects.create_user(
            username="rbac_user",
            email="rbac_user@example.com",
            password="TaskFlow#2026",
        )
        employee_role = Role.objects.get(code="employee")
        UserRole.objects.create(
            user_profile=user.profile,
            role=employee_role,
        )
        before_user_count = User.objects.count()
        before_user_roles = set(
            UserRole.objects.values_list(
                "user_profile_id",
                "role_id",
            )
        )

        call_command("sync_rbac_permissions", stdout=StringIO())

        self.assertEqual(User.objects.count(), before_user_count)
        self.assertEqual(
            set(
                UserRole.objects.values_list(
                    "user_profile_id",
                    "role_id",
                )
            ),
            before_user_roles,
        )

    def test_superuser_is_not_assigned_admin_role(self):
        superuser = User.objects.create_superuser(
            username="rbac_superuser",
            email="rbac_superuser@example.com",
            password="TaskFlow#2026",
        )

        call_command("sync_rbac_permissions", stdout=StringIO())

        self.assertFalse(UserRole.objects.filter(
            user_profile=superuser.profile,
            role__code="admin",
        ).exists())

    def test_rolepermission_default_model_permissions_are_not_in_matrix(self):
        call_command("sync_rbac_permissions", stdout=StringIO())
        model_permissions = Permission.objects.filter(
            content_type__app_label="users",
            content_type__model="rolepermission",
        )

        self.assertEqual(model_permissions.count(), 4)
        self.assertFalse(
            RolePermission.objects.filter(
                permission__in=model_permissions
            ).exists()
        )
