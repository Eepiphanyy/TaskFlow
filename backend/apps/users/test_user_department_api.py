from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department

from .models import Role, UserProfile, UserRole

User = get_user_model()


class UserDepartmentUpdateAPIViewTests(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )
        self.employee_role = Role.objects.create(
            name="普通员工",
            code="employee",
        )
        self.admin_user = User.objects.create_user(
            username="department_admin",
            email="department_admin@example.com",
            password="AdminPassword#2026",
        )
        self.ordinary_user = User.objects.create_user(
            username="ordinary_user",
            email="ordinary_user@example.com",
            password="UserPassword#2026",
        )
        self.staff_without_role = User.objects.create_user(
            username="staff_without_role",
            email="staff_without_role@example.com",
            password="StaffPassword#2026",
            is_staff=True,
        )
        self.target_user = User.objects.create_user(
            username="target_user",
            email="target_user@example.com",
            password="TargetPassword#2026",
        )
        UserRole.objects.create(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        )
        UserRole.objects.create(
            user_profile=self.target_user.profile,
            role=self.employee_role,
        )
        self.department_a = Department.objects.create(name="研发部")
        self.department_b = Department.objects.create(name="市场部")
        self.url = reverse(
            "user-management:department",
            args=[self.target_user.pk],
        )

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_anonymous_user_cannot_update_department(self):
        response = self.client.patch(
            self.url,
            {"department_id": self.department_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ordinary_user_cannot_update_other_user_department(self):
        self.authenticate(self.ordinary_user)

        response = self.client.patch(
            self.url,
            {"department_id": self.department_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.target_user.profile.refresh_from_db()
        self.assertIsNone(self.target_user.profile.department)

    def test_staff_without_admin_role_cannot_update_department(self):
        self.authenticate(self.staff_without_role)

        response = self.client.patch(
            self.url,
            {"department_id": self.department_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_assign_department(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.url,
            {"department_id": self.department_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "用户部门更新成功")
        self.assertEqual(response.data["data"], {
            "user_id": self.target_user.pk,
            "username": "target_user",
            "department": {
                "id": self.department_a.pk,
                "name": "研发部",
            },
        })
        self.target_user.profile.refresh_from_db()
        self.assertEqual(
            self.target_user.profile.department,
            self.department_a,
        )

    def test_admin_can_change_department(self):
        self.authenticate(self.admin_user)
        self.client.patch(
            self.url,
            {"department_id": self.department_a.pk},
            format="json",
        )

        response = self.client.patch(
            self.url,
            {"department_id": self.department_b.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.profile.refresh_from_db()
        self.assertEqual(
            self.target_user.profile.department,
            self.department_b,
        )

    def test_admin_can_clear_department(self):
        self.target_user.profile.department = self.department_a
        self.target_user.profile.save(update_fields=["department"])
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.url,
            {"department_id": None},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["data"]["department"])
        self.target_user.profile.refresh_from_db()
        self.assertIsNone(self.target_user.profile.department)

    def test_missing_user_returns_404(self):
        self.authenticate(self.admin_user)
        response = self.client.patch(
            reverse("user-management:department", args=[999999]),
            {"department_id": self.department_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "用户不存在")

    def test_missing_department_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.url,
            {"department_id": 999999},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "部门不存在")
        self.assertIn("department_id", response.data["errors"])

    def test_missing_profile_returns_404_without_creating_profile(self):
        UserProfile.objects.filter(user=self.target_user).delete()
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.url,
            {"department_id": self.department_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "用户资料不存在")
        self.assertFalse(
            UserProfile.objects.filter(user=self.target_user).exists()
        )

    def test_missing_department_id_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department_id", response.data["errors"])

    def test_invalid_department_id_type_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.url,
            {"department_id": "not-an-integer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department_id", response.data["errors"])

    def test_department_update_does_not_change_roles_or_password(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.url,
            {"department_id": self.department_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            list(
                self.target_user.profile.roles
                .values_list("code", flat=True)
            ),
            ["employee"],
        )
        self.target_user.refresh_from_db()
        self.assertTrue(
            self.target_user.check_password("TargetPassword#2026")
        )
        self.assertFalse(self.target_user.is_staff)
        self.assertFalse(self.target_user.is_superuser)

    def test_extra_fields_cannot_modify_account_or_roles(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.url,
            {
                "department_id": self.department_a.pk,
                "is_staff": True,
                "is_superuser": True,
                "password": "ChangedPassword#2026",
                "roles": ["admin"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.target_user.refresh_from_db()
        self.target_user.profile.refresh_from_db()
        self.assertFalse(self.target_user.is_staff)
        self.assertFalse(self.target_user.is_superuser)
        self.assertTrue(
            self.target_user.check_password("TargetPassword#2026")
        )
        self.assertEqual(
            list(
                self.target_user.profile.roles
                .values_list("code", flat=True)
            ),
            ["employee"],
        )

    def test_unsupported_methods_return_405(self):
        self.authenticate(self.admin_user)

        responses = [
            self.client.get(self.url),
            self.client.post(self.url, {}, format="json"),
            self.client.put(self.url, {}, format="json"),
            self.client.delete(self.url),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            )
