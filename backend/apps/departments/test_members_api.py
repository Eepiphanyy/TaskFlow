from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.users.models import Role, UserRole

from .models import Department

User = get_user_model()


class DepartmentMemberListAPIViewTests(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )
        self.employee_role = Role.objects.create(
            name="普通员工",
            code="employee",
        )
        self.handler_role = Role.objects.create(
            name="工单处理人员",
            code="ticket_handler",
        )
        self.admin_user = User.objects.create_user(
            username="member_admin",
            email="member_admin@example.com",
            password="AdminPassword#2026",
        )
        self.ordinary_user = User.objects.create_user(
            username="ordinary_requester",
            email="ordinary_requester@example.com",
            password="UserPassword#2026",
        )
        self.staff_without_role = User.objects.create_user(
            username="staff_requester",
            email="staff_requester@example.com",
            password="StaffPassword#2026",
            is_staff=True,
        )
        UserRole.objects.create(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        )
        self.department = Department.objects.create(name="研发部")
        self.other_department = Department.objects.create(name="市场部")
        self.member_one = self.create_member(
            "member_one",
            "member_one@example.com",
            self.department,
            [self.employee_role],
        )
        self.member_two = self.create_member(
            "member_two",
            "member_two@example.com",
            self.department,
            [self.employee_role, self.handler_role],
        )
        self.member_without_role = self.create_member(
            "member_without_role",
            "member_without_role@example.com",
            self.department,
            [],
        )
        self.other_member = self.create_member(
            "other_member",
            "other_member@example.com",
            self.other_department,
            [self.employee_role],
        )
        self.user_without_department = User.objects.create_user(
            username="no_department",
            email="no_department@example.com",
            password="NoDepartment#2026",
        )
        self.url = reverse(
            "departments:members",
            args=[self.department.pk],
        )

    def create_member(self, username, email, department, roles):
        user = User.objects.create_user(
            username=username,
            email=email,
            password="MemberPassword#2026",
        )
        user.profile.department = department
        user.profile.save(update_fields=["department"])
        for role in roles:
            UserRole.objects.create(
                user_profile=user.profile,
                role=role,
            )
        return user

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_anonymous_user_returns_401(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ordinary_user_returns_403(self):
        self.authenticate(self.ordinary_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_without_admin_role_returns_403(self):
        self.authenticate(self.staff_without_role)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_view_members(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "获取部门成员成功")
        self.assertEqual(response.data["data"]["department"], {
            "id": self.department.pk,
            "name": "研发部",
        })
        self.assertEqual(response.data["data"]["count"], 3)
        usernames = {
            member["username"]
            for member in response.data["data"]["results"]
        }
        self.assertEqual(
            usernames,
            {"member_one", "member_two", "member_without_role"},
        )

    def test_missing_department_returns_404(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            reverse("departments:members", args=[999999])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "部门不存在")

    def test_department_without_members_returns_empty_list(self):
        empty_department = Department.objects.create(name="空部门")
        self.authenticate(self.admin_user)

        response = self.client.get(
            reverse("departments:members", args=[empty_department.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 0)
        self.assertEqual(response.data["data"]["results"], [])

    def test_other_department_and_users_without_department_are_excluded(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)
        usernames = {
            member["username"]
            for member in response.data["data"]["results"]
        }

        self.assertNotIn(self.other_member.username, usernames)
        self.assertNotIn(self.user_without_department.username, usernames)

    def test_member_roles_are_returned(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)
        member = next(
            item
            for item in response.data["data"]["results"]
            if item["username"] == "member_two"
        )

        self.assertEqual(
            [role["code"] for role in member["roles"]],
            ["employee", "ticket_handler"],
        )

    def test_member_without_roles_returns_empty_list(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)
        member = next(
            item
            for item in response.data["data"]["results"]
            if item["username"] == "member_without_role"
        )

        self.assertEqual(member["roles"], [])

    def test_sensitive_fields_are_not_returned(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)
        member = response.data["data"]["results"][0]

        self.assertEqual(
            set(member.keys()),
            {"id", "username", "email", "roles"},
        )
        self.assertNotIn("password", member)
        self.assertNotIn("is_staff", member)
        self.assertNotIn("is_superuser", member)
        self.assertNotIn("phone", member)

    def test_member_list_supports_search(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url, {"search": "member_one@"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(
            response.data["data"]["results"][0]["username"],
            "member_one",
        )

    def test_member_list_supports_pagination(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url, {"page_size": 1})

        self.assertEqual(response.data["data"]["count"], 3)
        self.assertEqual(len(response.data["data"]["results"]), 1)
        self.assertIsNotNone(response.data["data"]["next"])

    def test_member_roles_do_not_create_n_plus_one_queries(self):
        self.authenticate(self.admin_user)

        with CaptureQueriesContext(connection) as baseline_queries:
            baseline_response = self.client.get(
                self.url,
                {"page_size": 100},
            )

        for index in range(1, 8):
            self.create_member(
                f"query_member_{index}",
                f"query_member_{index}@example.com",
                self.department,
                [self.employee_role, self.handler_role],
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url, {"page_size": 100})

        self.assertEqual(baseline_response.status_code, status.HTTP_200_OK)
        self.assertEqual(baseline_response.data["data"]["count"], 3)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["count"], 10)
        self.assertEqual(len(baseline_queries), len(queries))
