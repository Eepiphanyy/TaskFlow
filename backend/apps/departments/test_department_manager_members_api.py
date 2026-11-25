from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

from .models import Department

User = get_user_model()


class DepartmentManagerMemberListAPITests(APITestCase):
    def setUp(self):
        self.department_a = Department.objects.create(name="部门 A")
        self.department_b = Department.objects.create(name="部门 B")
        self.admin_role = self.create_role("admin", "系统管理员")
        self.manager_role = self.create_role(
            "department_manager",
            "部门负责人",
        )
        self.employee_role = self.create_role("employee", "普通员工")
        self.grant_member_view_permission(self.manager_role)

        self.admin_user = self.create_user(
            "member_fix_admin",
            self.department_a,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "member_fix_manager",
            self.department_a,
            [self.manager_role],
        )
        self.manager_without_department = self.create_user(
            "member_fix_manager_no_dept",
            None,
            [self.manager_role],
        )
        self.manager_without_profile = self.create_user(
            "member_fix_manager_no_profile",
            self.department_a,
            [self.manager_role],
        )
        self.manager_without_profile.profile.delete()
        self.employee_user = self.create_user(
            "member_fix_employee",
            self.department_a,
            [self.employee_role],
        )
        self.department_a_member = self.create_user(
            "member_fix_a_member",
            self.department_a,
            [self.employee_role],
        )
        self.department_b_member = self.create_user(
            "member_fix_b_member",
            self.department_b,
            [self.employee_role],
        )

        self.department_a_url = reverse(
            "departments:members",
            args=[self.department_a.pk],
        )
        self.department_b_url = reverse(
            "departments:members",
            args=[self.department_b.pk],
        )

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_member_view_permission(self, role):
        permission = Permission.objects.get(
            content_type__app_label="departments",
            codename="view_department_members",
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

    def result_usernames(self, response):
        return {
            member["username"]
            for member in response.data["data"]["results"]
        }

    def test_admin_can_view_any_department_members(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.department_b_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            self.department_b_member.username,
            self.result_usernames(response),
        )

    def test_manager_can_view_own_department_members(self):
        self.authenticate(self.manager_user)

        response = self.client.get(self.department_a_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            self.department_a_member.username,
            self.result_usernames(response),
        )
        self.assertNotIn(
            self.department_b_member.username,
            self.result_usernames(response),
        )

    def test_manager_cannot_view_other_department_members(self):
        self.authenticate(self.manager_user)

        response = self.client.get(self.department_b_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            str(response.data["detail"]),
            "只能查看自己所属部门的成员。",
        )

    def test_employee_cannot_view_department_members(self):
        self.authenticate(self.employee_user)

        response = self.client.get(self.department_a_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_without_department_cannot_view_members(self):
        self.authenticate(self.manager_without_department)

        response = self.client.get(self.department_a_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_without_profile_cannot_view_members(self):
        self.authenticate(self.manager_without_profile)

        response = self.client.get(self.department_a_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
