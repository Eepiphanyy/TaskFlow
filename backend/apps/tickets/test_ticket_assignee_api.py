from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department
from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

User = get_user_model()


class TicketAssigneeListAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("tickets:assignees")
        self.department_a = Department.objects.create(name="研发部")
        self.department_b = Department.objects.create(name="市场部")

        self.admin_role = self.create_role("admin", "系统管理员")
        self.manager_role = self.create_role(
            "department_manager",
            "部门负责人",
        )
        self.employee_role = self.create_role("employee", "普通员工")
        self.handler_role = self.create_role(
            "ticket_handler",
            "工单处理人员",
        )
        self.grant_assign_permission(self.manager_role)

        self.admin_user = self.create_user(
            "assignee_api_admin",
            None,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "assignee_api_manager",
            self.department_a,
            [self.manager_role],
        )
        self.manager_without_department = self.create_user(
            "assignee_api_manager_no_department",
            None,
            [self.manager_role],
        )
        self.employee_user = self.create_user(
            "assignee_api_employee",
            self.department_a,
            [self.employee_role],
        )
        self.active_handler = self.create_user(
            "assignee_api_handler",
            self.department_a,
            [self.handler_role],
        )
        self.cross_department_handler = self.create_user(
            "assignee_api_handler_b",
            self.department_b,
            [self.handler_role],
        )
        self.handler_without_department = self.create_user(
            "assignee_api_handler_no_department",
            None,
            [self.handler_role],
        )
        self.inactive_handler = self.create_user(
            "assignee_api_handler_inactive",
            self.department_a,
            [self.handler_role],
        )
        self.inactive_handler.is_active = False
        self.inactive_handler.save(update_fields=["is_active"])
        self.handler_without_profile = self.create_user(
            "assignee_api_handler_no_profile",
            self.department_a,
            [self.handler_role],
        )
        self.handler_without_profile.profile.delete()

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_assign_permission(self, role):
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="assign_ticket",
        )
        RolePermission.objects.create(
            role=role,
            permission=permission,
            scope=RolePermissionScope.DEPARTMENT,
        )

    def create_user(self, username, department, roles):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="TaskFlow#2026",
        )
        profile = user.profile
        profile.department = department
        profile.save(update_fields=["department"])
        for role in roles:
            UserRole.objects.create(
                user_profile=profile,
                role=role,
            )
        return user

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_anonymous_user_returns_401(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list_assignees(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertIn(self.active_handler.pk, ids)
        self.assertIn(self.cross_department_handler.pk, ids)

    def test_manager_can_list_cross_department_handlers(self):
        self.authenticate(self.manager_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data],
            [
                self.active_handler.pk,
                self.cross_department_handler.pk,
                self.handler_without_department.pk,
            ],
        )

    def test_non_handler_users_are_excluded(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        ids = {item["id"] for item in response.data}
        self.assertNotIn(self.employee_user.pk, ids)
        self.assertNotIn(self.manager_user.pk, ids)

    def test_inactive_handler_is_excluded(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertNotIn(
            self.inactive_handler.pk,
            {item["id"] for item in response.data},
        )

    def test_handler_without_profile_is_excluded(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertNotIn(
            self.handler_without_profile.pk,
            {item["id"] for item in response.data},
        )

    def test_handler_without_department_is_returned_with_null_department(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)
        candidate = next(
            item
            for item in response.data
            if item["id"] == self.handler_without_department.pk
        )

        self.assertIsNone(candidate["department"])

    def test_response_contains_only_minimal_fields(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertTrue(response.data)
        for candidate in response.data:
            self.assertEqual(
                set(candidate),
                {"id", "username", "department"},
            )
            self.assertNotIn("password", candidate)
            self.assertNotIn("email", candidate)
            self.assertNotIn("is_staff", candidate)
            self.assertNotIn("is_superuser", candidate)

    def test_user_without_assign_permission_returns_403(self):
        self.authenticate(self.employee_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_handler_without_assign_permission_returns_403(self):
        self.authenticate(self.active_handler)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_without_effective_scope_returns_403(self):
        self.authenticate(self.manager_without_department)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
