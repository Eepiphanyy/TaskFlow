from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

from .models import Department

User = get_user_model()


class DepartmentManagerUpdateAPITests(APITestCase):
    def setUp(self):
        self.own_department = Department.objects.create(
            name="测试研发部",
            description="原始说明",
        )
        self.other_department = Department.objects.create(
            name="测试市场部",
            description="其他部门",
        )

        self.admin_role = self.create_role("admin", "系统管理员")
        self.manager_role = self.create_role(
            "department_manager",
            "部门负责人",
        )
        self.employee_role = self.create_role("employee", "普通员工")
        self.grant_change_permission(self.manager_role)

        self.admin_user = self.create_user(
            "department_fix_admin",
            self.own_department,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "department_fix_manager",
            self.own_department,
            [self.manager_role],
        )
        self.manager_without_department = self.create_user(
            "department_fix_no_department",
            None,
            [self.manager_role],
        )
        self.employee_user = self.create_user(
            "department_fix_employee",
            self.own_department,
            [self.employee_role],
        )
        self.user_without_profile = self.create_user(
            "department_fix_no_profile",
            self.own_department,
            [self.manager_role],
        )
        self.user_without_profile.profile.delete()
        self.own_url = reverse(
            "departments:detail",
            args=[self.own_department.pk],
        )
        self.other_url = reverse(
            "departments:detail",
            args=[self.other_department.pk],
        )
        self.list_url = reverse("departments:list")

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_change_permission(self, role):
        permission = Permission.objects.get(
            content_type__app_label="departments",
            codename="change_department",
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

    def test_admin_can_patch_any_department(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.other_url,
            {"description": "管理员修改"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.other_department.refresh_from_db()
        self.assertEqual(
            self.other_department.description,
            "管理员修改",
        )

    def test_manager_can_patch_own_department(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            self.own_url,
            {"description": "负责人修改"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_department.refresh_from_db()
        self.assertEqual(
            self.own_department.description,
            "负责人修改",
        )

    def test_manager_cannot_patch_other_department(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            self.other_url,
            {"description": "不应修改"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            str(response.data["detail"]),
            "只能修改自己所属的部门。",
        )
        self.other_department.refresh_from_db()
        self.assertEqual(
            self.other_department.description,
            "其他部门",
        )

    def test_employee_cannot_patch_any_department(self):
        self.authenticate(self.employee_user)

        response = self.client.patch(
            self.own_url,
            {"description": "员工不应修改"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            str(response.data["detail"]),
            "无权修改部门信息。",
        )
        self.own_department.refresh_from_db()
        self.assertEqual(
            self.own_department.description,
            "原始说明",
        )

    def test_manager_cannot_delete_department(self):
        self.authenticate(self.manager_user)

        response = self.client.delete(self.own_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            Department.objects.filter(pk=self.own_department.pk).exists()
        )

    def test_manager_cannot_create_department(self):
        self.authenticate(self.manager_user)

        response = self.client.post(
            self.list_url,
            {"name": "负责人创建部门"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Department.objects.filter(name="负责人创建部门").exists()
        )

    def test_anonymous_cannot_patch_department(self):
        response = self.client.patch(
            self.own_url,
            {"description": "匿名修改"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_without_department_cannot_patch_department(self):
        self.authenticate(self.manager_without_department)

        response = self.client.patch(
            self.own_url,
            {"description": "无部门修改"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            str(response.data["detail"]),
            "只能修改自己所属的部门。",
        )
        self.own_department.refresh_from_db()
        self.assertEqual(
            self.own_department.description,
            "原始说明",
        )

    def test_user_without_profile_cannot_patch_department(self):
        self.authenticate(self.user_without_profile)

        response = self.client.patch(
            self.own_url,
            {"description": "无 Profile 修改"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            str(response.data["detail"]),
            "无权修改部门信息。",
        )

    def test_admin_create_department_still_returns_201(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            self.list_url,
            {"name": "新建部门"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_list_and_detail_remain_available(self):
        self.authenticate(self.manager_user)

        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(self.own_url)

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            detail_response.data["id"],
            self.own_department.pk,
        )
