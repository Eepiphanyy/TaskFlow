from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.users.management.commands.init_default_roles import DEFAULT_ROLES
from apps.users.models import Role, UserProfile, UserRole

User = get_user_model()


class InitDefaultRolesCommandTests(TestCase):
    def test_first_execution_creates_all_default_roles(self):
        output = StringIO()

        call_command("init_default_roles", stdout=output)

        self.assertEqual(Role.objects.count(), 4)
        self.assertEqual(
            set(Role.objects.values_list("code", flat=True)),
            {role["code"] for role in DEFAULT_ROLES},
        )
        self.assertIn("新建：系统管理员 (admin)", output.getvalue())
        self.assertIn("角色总数 4", output.getvalue())
        self.assertEqual(UserRole.objects.count(), 0)

    def test_repeated_execution_is_idempotent(self):
        call_command("init_default_roles", stdout=StringIO())
        output = StringIO()

        call_command("init_default_roles", stdout=output)

        self.assertEqual(Role.objects.count(), 4)
        self.assertEqual(Role.objects.filter(code="admin").count(), 1)
        self.assertIn("已存在：系统管理员 (admin)", output.getvalue())
        self.assertIn("新建 0 个，已存在 4 个，角色总数 4", output.getvalue())

    def test_existing_role_description_is_not_overwritten(self):
        Role.objects.create(
            name="自定义管理员",
            code="admin",
            description="保留现有描述",
        )

        call_command("init_default_roles", stdout=StringIO())

        role = Role.objects.get(code="admin")
        self.assertEqual(role.name, "自定义管理员")
        self.assertEqual(role.description, "保留现有描述")
        self.assertEqual(Role.objects.count(), 4)

    def test_initialization_error_rolls_back_all_roles(self):
        calls = 0

        def flaky_get_or_create(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return Role.objects.create(
                    code=kwargs["code"],
                    **kwargs["defaults"],
                ), True
            raise RuntimeError("simulated database failure")

        with patch(
            "apps.users.management.commands.init_default_roles."
            "Role.objects.get_or_create",
            side_effect=flaky_get_or_create,
        ):
            with self.assertRaisesMessage(
                CommandError,
                "初始化默认角色失败，事务已回滚",
            ):
                call_command("init_default_roles", stdout=StringIO())

        self.assertEqual(Role.objects.count(), 0)


class AssignUserRoleCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="role_user",
            email="role_user@example.com",
            password="TaskFlow#2026",
        )
        self.other_user = User.objects.create_user(
            username="other_role_user",
            email="other_role_user@example.com",
            password="TaskFlow#2026",
        )
        self.role = Role.objects.create(
            name="普通员工",
            code="employee",
            description="负责日常工单与任务协作",
        )

    def test_assigns_existing_role_to_user(self):
        output = StringIO()

        call_command(
            "assign_user_role",
            username=self.user.username,
            role="employee",
            stdout=output,
        )

        self.assertTrue(UserRole.objects.filter(
            user_profile=self.user.profile,
            role=self.role,
        ).exists())
        self.assertIn("用户 role_user", output.getvalue())
        self.assertIn("角色 普通员工 (employee)", output.getvalue())

    def test_repeated_assignment_is_idempotent(self):
        call_command(
            "assign_user_role",
            username=self.user.username,
            role="employee",
            stdout=StringIO(),
        )
        output = StringIO()

        call_command(
            "assign_user_role",
            username=self.user.username,
            role="employee",
            stdout=output,
        )

        self.assertEqual(UserRole.objects.count(), 1)
        self.assertIn("关系已存在", output.getvalue())

    def test_missing_user_fails_without_creating_user(self):
        user_count = User.objects.count()

        with self.assertRaisesMessage(CommandError, "用户不存在"):
            call_command(
                "assign_user_role",
                username="missing_user",
                role="employee",
                stdout=StringIO(),
            )

        self.assertEqual(User.objects.count(), user_count)
        self.assertEqual(UserRole.objects.count(), 0)

    def test_missing_role_fails_without_creating_role(self):
        role_count = Role.objects.count()

        with self.assertRaisesMessage(CommandError, "角色不存在"):
            call_command(
                "assign_user_role",
                username=self.user.username,
                role="missing_role",
                stdout=StringIO(),
            )

        self.assertEqual(Role.objects.count(), role_count)
        self.assertEqual(UserRole.objects.count(), 0)

    def test_missing_profile_fails_without_creating_profile(self):
        UserProfile.objects.filter(user=self.user).delete()

        with self.assertRaisesMessage(
            CommandError,
            "没有 UserProfile",
        ):
            call_command(
                "assign_user_role",
                username=self.user.username,
                role="employee",
                stdout=StringIO(),
            )

        self.assertFalse(
            UserProfile.objects.filter(user=self.user).exists()
        )
        self.assertEqual(UserRole.objects.count(), 0)

    def test_assignment_does_not_affect_other_users(self):
        call_command(
            "assign_user_role",
            username=self.user.username,
            role="employee",
            stdout=StringIO(),
        )

        self.assertEqual(
            UserRole.objects.filter(
                user_profile=self.user.profile
            ).count(),
            1,
        )
        self.assertEqual(
            UserRole.objects.filter(
                user_profile=self.other_user.profile
            ).count(),
            0,
        )
