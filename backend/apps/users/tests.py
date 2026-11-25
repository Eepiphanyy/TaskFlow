from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.departments.models import Department

from .models import (
    Role,
    RolePermission,
    RolePermissionScope,
    UserProfile,
    UserRole,
)
from .rbac_matrix import REQUIRED_PERMISSIONS

User = get_user_model()


class UserProfileSignalTests(APITestCase):
    def test_regular_user_creation_creates_one_profile(self):
        user = User.objects.create_user(
            username="profile_user",
            email="profile_user@example.com",
            password="TaskFlow#2026",
        )

        self.assertEqual(
            UserProfile.objects.filter(user=user).count(),
            1,
        )

    def test_superuser_creation_creates_one_profile(self):
        user = User.objects.create_superuser(
            username="profile_superuser",
            email="profile_superuser@example.com",
            password="TaskFlow#2026",
        )

        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(
            UserProfile.objects.filter(user=user).count(),
            1,
        )

    def test_same_user_cannot_have_duplicate_profile(self):
        user = User.objects.create_user(
            username="idempotent_profile_user",
            email="idempotent_profile_user@example.com",
            password="TaskFlow#2026",
        )

        UserProfile.objects.get_or_create(user=user)
        UserProfile.objects.get_or_create(user=user)

        self.assertEqual(
            UserProfile.objects.filter(user=user).count(),
            1,
        )

    def test_saving_existing_user_does_not_create_duplicate_profile(self):
        user = User.objects.create_user(
            username="existing_profile_user",
            email="existing_profile_user@example.com",
            password="TaskFlow#2026",
        )
        user.first_name = "Updated"
        user.save()

        self.assertEqual(
            UserProfile.objects.filter(user=user).count(),
            1,
        )

    @patch(
        "apps.users.signals.UserProfile.objects.get_or_create",
        side_effect=RuntimeError("Profile creation failed"),
    )
    def test_registration_rolls_back_when_profile_creation_fails(
        self,
        mocked_get_or_create,
    ):
        client = self.client_class()

        with self.assertRaises(RuntimeError):
            client.post(
                reverse("users:register"),
                {
                    "username": "rollback_user",
                    "email": "rollback_user@example.com",
                    "password": "TaskFlow#2026",
                    "password_confirm": "TaskFlow#2026",
                },
                format="json",
            )

        self.assertFalse(
            User.objects.filter(username="rollback_user").exists()
        )
        self.assertFalse(
            UserProfile.objects.filter(user__username="rollback_user").exists()
        )
        mocked_get_or_create.assert_called_once()


class RegisterAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("users:register")
        self.payload = {
            "username": "new_user",
            "email": "new_user@example.com",
            "password": "TaskFlow#2026",
            "password_confirm": "TaskFlow#2026",
        }

    def test_register_success(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "注册成功")
        self.assertEqual(response.data["data"]["username"], "new_user")
        self.assertEqual(response.data["data"]["email"], "new_user@example.com")
        self.assertNotIn("password", response.data["data"])
        self.assertNotIn("password_confirm", response.data["data"])
        self.assertTrue(User.objects.filter(username="new_user").exists())

    def test_duplicate_username_rejected(self):
        User.objects.create_user(
            username=self.payload["username"],
            email="existing@example.com",
            password="TaskFlow#2026",
        )

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data["errors"])
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_email_rejected_case_insensitively(self):
        User.objects.create_user(
            username="existing_user",
            email="NEW_USER@example.com",
            password="TaskFlow#2026",
        )

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["errors"])
        self.assertEqual(User.objects.count(), 1)

    def test_password_mismatch_rejected(self):
        self.payload["password_confirm"] = "Different#2026"

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data["errors"])
        self.assertFalse(User.objects.filter(username="new_user").exists())

    def test_required_fields_rejected(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ("username", "email", "password", "password_confirm"):
            self.assertIn(field, response.data["errors"])

    def test_password_is_hashed(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="new_user")
        self.assertNotEqual(user.password, self.payload["password"])
        self.assertTrue(user.check_password(self.payload["password"]))

    def test_user_profile_is_created(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="new_user")
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)


class LoginAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("users:login")
        self.password = "Test123456"
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password=self.password,
        )
        self.payload = {
            "username": self.user.username,
            "password": self.password,
        }

    def test_login_success(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "登录成功")
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])
        self.assertNotIn("password", response.data["data"])

    def test_login_returns_access_and_refresh_tokens(self):
        response = self.client.post(self.url, self.payload, format="json")

        access = AccessToken(response.data["data"]["access"])
        refresh = RefreshToken(response.data["data"]["refresh"])
        self.assertEqual(access["token_type"], "access")
        self.assertEqual(refresh["token_type"], "refresh")
        self.assertEqual(access["user_id"], str(self.user.pk))
        self.assertEqual(refresh["user_id"], str(self.user.pk))

    def test_wrong_password_rejected(self):
        self.payload["password"] = "WrongPassword123"

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("data", response.data)

    def test_unknown_username_rejected(self):
        self.payload["username"] = "missing_user"

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["message"], "用户名或密码错误，或账号不可用。")

    def test_inactive_user_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("data", response.data)

    def test_access_token_is_valid_for_drf_authentication(self):
        login_response = self.client.post(self.url, self.payload, format="json")
        access = login_response.data["data"]["access"]

        request = APIRequestFactory().get(
            self.url,
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        authenticated_user, validated_token = JWTAuthentication().authenticate(
            Request(request)
        )

        self.assertEqual(authenticated_user, self.user)
        self.assertEqual(validated_token["user_id"], str(self.user.pk))

    def test_tokens_do_not_contain_plaintext_password(self):
        response = self.client.post(self.url, self.payload, format="json")

        access = response.data["data"]["access"]
        refresh = response.data["data"]["refresh"]
        access_payload = AccessToken(access).payload
        refresh_payload = RefreshToken(refresh).payload

        self.assertNotIn(self.password, access)
        self.assertNotIn(self.password, refresh)
        self.assertNotIn("password", access_payload)
        self.assertNotIn("password", refresh_payload)


class CurrentUserAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("users:me")
        self.user_a = User.objects.create_user(
            username="user_a",
            email="user_a@example.com",
            password="TaskFlow#2026",
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            email="user_b@example.com",
            password="TaskFlow#2026",
        )
        self.access = str(AccessToken.for_user(self.user_a))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def assign_role(self, role, user=None):
        return UserRole.objects.create(
            user_profile=(user or self.user_a).profile,
            role=role,
        )

    def grant_permission(
        self,
        role,
        app_label,
        codename,
        scope=RolePermissionScope.ALL,
    ):
        permission = Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
        return RolePermission.objects.create(
            role=role,
            permission=permission,
            scope=scope,
        )

    def test_valid_access_token_returns_current_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "获取当前用户成功")
        self.assertEqual(response.data["data"]["id"], self.user_a.pk)
        self.assertEqual(response.data["data"]["username"], "user_a")
        self.assertEqual(response.data["data"]["email"], "user_a@example.com")
        self.assertIsNone(response.data["data"]["department"])
        self.assertEqual(response.data["data"]["roles"], [])
        self.assertEqual(response.data["data"]["permissions"], [])
        self.assertNotIn("password", response.data["data"])
        self.assertNotIn("profile", response.data["data"])

    def test_missing_token_returns_401(self):
        self.client.credentials()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["message"], "身份认证失败")

    def test_invalid_token_returns_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_returns_401(self):
        expired_token = AccessToken.for_user(self.user_a)
        expired_token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {expired_token}",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_returns_401(self):
        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_user_a_token_cannot_return_user_b(self):
        response = self.client.get(
            self.url,
            {"user_id": self.user_b.pk},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.user_a.pk)
        self.assertNotEqual(response.data["data"]["id"], self.user_b.pk)
        self.assertEqual(response.data["data"]["username"], "user_a")

    def test_current_user_returns_department(self):
        department = Department.objects.create(
            name="研发部",
            description="负责研发",
        )
        self.user_a.profile.department = department
        self.user_a.profile.save(update_fields=["department"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["department"], {
            "id": department.pk,
            "name": "研发部",
        })

    def test_current_user_without_department_returns_null(self):
        response = self.client.get(self.url)

        self.assertIsNone(response.data["data"]["department"])

    def test_current_user_returns_one_role(self):
        role = Role.objects.create(
            name="普通员工",
            code="employee",
        )
        UserRole.objects.create(
            user_profile=self.user_a.profile,
            role=role,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.data["data"]["roles"], [{
            "id": role.pk,
            "name": "普通员工",
            "code": "employee",
        }])

    def test_current_user_returns_all_roles(self):
        employee = Role.objects.create(
            name="普通员工",
            code="employee",
        )
        handler = Role.objects.create(
            name="工单处理人员",
            code="ticket_handler",
        )
        UserRole.objects.bulk_create([
            UserRole(user_profile=self.user_a.profile, role=employee),
            UserRole(user_profile=self.user_a.profile, role=handler),
        ])

        response = self.client.get(self.url)

        self.assertEqual(
            [role["code"] for role in response.data["data"]["roles"]],
            ["employee", "ticket_handler"],
        )

    def test_current_user_without_roles_returns_empty_list(self):
        response = self.client.get(self.url)

        self.assertEqual(response.data["data"]["roles"], [])

    def test_current_user_response_has_only_expected_fields(self):
        response = self.client.get(self.url)

        self.assertEqual(
            set(response.data["data"].keys()),
            {
                "id",
                "username",
                "email",
                "department",
                "roles",
                "permissions",
            },
        )
        self.assertNotIn("password", response.data["data"])
        self.assertNotIn("is_staff", response.data["data"])
        self.assertNotIn("is_superuser", response.data["data"])
        self.assertNotIn("user_permissions", response.data["data"])

    def test_current_user_returns_custom_role_permissions(self):
        role = Role.objects.create(
            name="自定义工单操作员",
            code="custom_ticket_operator",
        )
        self.assign_role(role)
        self.grant_permission(role, "tickets", "assign_ticket")
        self.grant_permission(role, "tickets", "process_ticket")

        response = self.client.get(self.url)

        self.assertEqual(
            response.data["data"]["permissions"],
            [
                "tickets.assign_ticket",
                "tickets.process_ticket",
            ],
        )

    def test_current_user_merges_permissions_from_multiple_roles(self):
        assign_role = Role.objects.create(
            name="工单分配员",
            code="custom_assigner",
        )
        close_role = Role.objects.create(
            name="工单关闭员",
            code="custom_closer",
        )
        self.assign_role(assign_role)
        self.assign_role(close_role)
        self.grant_permission(assign_role, "tickets", "assign_ticket")
        self.grant_permission(close_role, "tickets", "close_ticket")

        response = self.client.get(self.url)

        self.assertEqual(
            response.data["data"]["permissions"],
            [
                "tickets.assign_ticket",
                "tickets.close_ticket",
            ],
        )

    def test_current_user_without_grants_returns_empty_permissions(self):
        role = Role.objects.create(
            name="无权限角色",
            code="custom_no_permission",
        )
        self.assign_role(role)

        response = self.client.get(self.url)

        self.assertEqual(response.data["data"]["permissions"], [])

    def test_admin_returns_every_registered_business_permission(self):
        admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )
        self.assign_role(admin_role)

        response = self.client.get(self.url)

        expected_permissions = sorted(
            f"{app_label}.{codename}"
            for app_label, codename in REQUIRED_PERMISSIONS
        )
        self.assertEqual(
            response.data["data"]["permissions"],
            expected_permissions,
        )

    def test_current_user_does_not_leak_non_business_permissions(self):
        role = Role.objects.create(
            name="受限自定义角色",
            code="custom_limited_operator",
        )
        self.assign_role(role)
        self.grant_permission(role, "tickets", "process_ticket")

        django_admin_permission = Permission.objects.get(
            content_type__app_label="auth",
            codename="add_user",
        )
        RolePermission.objects.create(
            role=role,
            permission=django_admin_permission,
            scope=RolePermissionScope.ALL,
        )
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
            role=role,
            permission=third_party_permission,
            scope=RolePermissionScope.ALL,
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.data["data"]["permissions"],
            ["tickets.process_ticket"],
        )

    def test_current_user_does_not_return_another_users_permissions(self):
        user_a_role = Role.objects.create(
            name="用户 A 分配角色",
            code="user_a_assigner",
        )
        user_b_role = Role.objects.create(
            name="用户 B 关闭角色",
            code="user_b_closer",
        )
        self.assign_role(user_a_role)
        self.assign_role(user_b_role, user=self.user_b)
        self.grant_permission(user_a_role, "tickets", "assign_ticket")
        self.grant_permission(user_b_role, "tickets", "close_ticket")

        response = self.client.get(self.url)

        self.assertEqual(
            response.data["data"]["permissions"],
            ["tickets.assign_ticket"],
        )
        self.assertNotIn(
            "tickets.close_ticket",
            response.data["data"]["permissions"],
        )

    def test_current_user_query_does_not_scale_with_roles(self):
        roles = [
            Role.objects.create(name=f"角色{index}", code=f"role_{index}")
            for index in range(1, 8)
        ]
        UserRole.objects.bulk_create([
            UserRole(user_profile=self.user_a.profile, role=role)
            for role in roles
        ])

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]["roles"]), 7)
        self.assertLessEqual(len(queries), 5)


class RefreshAPIViewTests(APITestCase):
    def setUp(self):
        self.login_url = reverse("users:login")
        self.refresh_url = reverse("users:token-refresh")
        self.me_url = reverse("users:me")
        self.user = User.objects.create_user(
            username="refresh_user",
            email="refresh_user@example.com",
            password="TaskFlow#2026",
        )
        login_response = self.client.post(
            self.login_url,
            {
                "username": self.user.username,
                "password": "TaskFlow#2026",
            },
            format="json",
        )
        self.refresh = login_response.data["data"]["refresh"]

    def refresh_token(self, token):
        return self.client.post(
            self.refresh_url,
            {"refresh": token},
            format="json",
        )

    def test_valid_refresh_returns_new_access_and_refresh_tokens(self):
        response = self.refresh_token(self.refresh)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Token 刷新成功")
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])
        self.assertNotEqual(response.data["data"]["refresh"], self.refresh)

    def test_new_access_token_can_access_current_user(self):
        refresh_response = self.refresh_token(self.refresh)
        access = refresh_response.data["data"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.user.pk)

    def test_rotation_returns_a_new_refresh_token(self):
        old_token = RefreshToken(self.refresh)
        old_jti = old_token["jti"]

        response = self.refresh_token(self.refresh)

        new_token = RefreshToken(response.data["data"]["refresh"])
        self.assertNotEqual(old_jti, new_token["jti"])
        self.assertEqual(new_token["user_id"], str(self.user.pk))

    def test_old_refresh_token_is_blacklisted_after_rotation(self):
        first_response = self.refresh_token(self.refresh)
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.refresh_token(self.refresh)

        self.assertEqual(
            second_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            second_response.data["code"],
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_invalid_refresh_token_returns_401(self):
        response = self.refresh_token("invalid-refresh-token")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_expired_refresh_token_returns_401(self):
        expired = RefreshToken(self.refresh)
        expired.set_exp(lifetime=timedelta(seconds=-1))

        response = self.refresh_token(str(expired))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_blacklisted_refresh_token_returns_401(self):
        blacklisted = RefreshToken(self.refresh)
        blacklisted.blacklist()

        response = self.refresh_token(str(blacklisted))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_cannot_access_current_user(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.refresh}",
        )

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)


class LogoutAPIViewTests(APITestCase):
    def setUp(self):
        self.login_url = reverse("users:login")
        self.logout_url = reverse("users:logout")
        self.refresh_url = reverse("users:token-refresh")
        self.me_url = reverse("users:me")
        self.user_a = User.objects.create_user(
            username="logout_user_a",
            email="logout_user_a@example.com",
            password="TaskFlow#2026",
        )
        self.user_b = User.objects.create_user(
            username="logout_user_b",
            email="logout_user_b@example.com",
            password="TaskFlow#2026",
        )
        login_a = self.login(self.user_a)
        login_b = self.login(self.user_b)
        self.access_a = login_a["access"]
        self.refresh_a = login_a["refresh"]
        self.refresh_b = login_b["refresh"]

    def login(self, user):
        response = self.client.post(
            self.login_url,
            {
                "username": user.username,
                "password": "TaskFlow#2026",
            },
            format="json",
        )
        return response.data["data"]

    def logout(self, refresh):
        return self.client.post(
            self.logout_url,
            {"refresh": refresh},
            format="json",
        )

    def test_logout_success(self):
        response = self.logout(self.refresh_a)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "退出登录成功")
        self.assertIsNone(response.data["data"])

    def test_logout_adds_refresh_token_to_blacklist(self):
        refresh_token = RefreshToken(self.refresh_a)
        jti = refresh_token["jti"]

        response = self.logout(self.refresh_a)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=jti).exists()
        )

    def test_blacklisted_refresh_token_cannot_refresh(self):
        self.logout(self.refresh_a)

        response = self.client.post(
            self.refresh_url,
            {"refresh": self.refresh_a},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_refresh_token_returns_401(self):
        response = self.logout("invalid-refresh-token")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_expired_refresh_token_returns_401(self):
        expired = RefreshToken(self.refresh_a)
        expired.set_exp(lifetime=timedelta(seconds=-1))

        response = self.logout(str(expired))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], status.HTTP_401_UNAUTHORIZED)

    def test_blacklisted_refresh_token_cannot_logout_again(self):
        first_response = self.logout(self.refresh_a)
        second_response = self.logout(self.refresh_a)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_refresh_field_returns_400(self):
        response = self.client.post(self.logout_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], status.HTTP_400_BAD_REQUEST)
        self.assertIn("refresh", response.data["errors"])

    def test_logout_ignores_access_token_from_another_user(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_a}",
        )

        response = self.logout(self.refresh_b)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        refresh_b_response = self.client.post(
            self.refresh_url,
            {"refresh": self.refresh_b},
            format="json",
        )
        refresh_a_response = self.client.post(
            self.refresh_url,
            {"refresh": self.refresh_a},
            format="json",
        )
        self.assertEqual(
            refresh_b_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(refresh_a_response.status_code, status.HTTP_200_OK)

    def test_valid_refresh_token_can_logout_with_expired_access_token(self):
        expired_access = AccessToken.for_user(self.user_a)
        expired_access.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {expired_access}",
        )

        response = self.logout(self.refresh_a)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_access_token_remains_valid_after_logout(self):
        self.logout(self.refresh_a)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_a}",
        )

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.user_a.pk)
