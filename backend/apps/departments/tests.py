from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.users.models import Role, UserRole

from .models import Department

User = get_user_model()


class DepartmentAPIViewTests(APITestCase):
    def setUp(self):
        self.list_url = reverse("departments:list")
        self.ordinary_user = User.objects.create_user(
            username="department_user",
            email="department_user@example.com",
            password="TaskFlow#2026",
        )
        self.other_user = User.objects.create_user(
            username="other_department_user",
            email="other_department_user@example.com",
            password="TaskFlow#2026",
        )
        self.admin_user = User.objects.create_user(
            username="department_admin",
            email="department_admin@example.com",
            password="TaskFlow#2026",
        )
        self.staff_without_role = User.objects.create_user(
            username="staff_without_role",
            email="staff_without_role@example.com",
            password="TaskFlow#2026",
            is_staff=True,
        )
        self.admin_role = Role.objects.create(
            name="管理员",
            code="admin",
            description="TaskFlow 业务管理员",
        )
        UserRole.objects.create(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        )
        self.department = Department.objects.create(
            name="研发部",
            description="负责产品研发",
        )
        self.detail_url = reverse(
            "departments:detail",
            args=[self.department.pk],
        )

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_unauthenticated_list_returns_401(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_detail_returns_401(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_list_departments(self):
        self.authenticate(self.ordinary_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.department.pk,
        )

    def test_authenticated_user_can_view_department_detail(self):
        self.authenticate(self.ordinary_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.department.pk)
        self.assertEqual(response.data["name"], "研发部")
        self.assertEqual(response.data["description"], "负责产品研发")

    def test_missing_department_returns_404(self):
        self.authenticate(self.ordinary_user)

        response = self.client.get(
            reverse("departments:detail", args=[999999])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_department_list_is_paginated(self):
        Department.objects.bulk_create([
            Department(name=f"分页部门{index}")
            for index in range(1, 6)
        ])
        self.authenticate(self.ordinary_user)

        response = self.client.get(
            self.list_url,
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 6)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_department_list_searches_by_name(self):
        Department.objects.create(
            name="市场部",
            description="负责市场业务",
        )
        self.authenticate(self.ordinary_user)

        response = self.client.get(
            self.list_url,
            {"search": "研发"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "研发部")

    def test_different_authenticated_users_can_query_departments(self):
        self.authenticate(self.ordinary_user)
        first_response = self.client.get(self.list_url)

        self.authenticate(self.other_user)
        second_response = self.client.get(self.list_url)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            first_response.data["results"][0]["id"],
            second_response.data["results"][0]["id"],
        )

    def test_anonymous_user_cannot_create_department(self):
        response = self.client.post(
            self.list_url,
            {"name": "匿名创建部门", "description": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(
            Department.objects.filter(name="匿名创建部门").exists()
        )

    def test_ordinary_user_cannot_create_department(self):
        self.authenticate(self.ordinary_user)

        response = self.client.post(
            self.list_url,
            {"name": "普通用户创建部门", "description": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Department.objects.filter(name="普通用户创建部门").exists()
        )

    def test_staff_without_admin_role_cannot_create_department(self):
        self.authenticate(self.staff_without_role)

        response = self.client.post(
            self.list_url,
            {"name": "Staff 创建部门", "description": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_department(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            self.list_url,
            {
                "name": "产品部",
                "description": "负责产品规划",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "产品部")
        self.assertTrue(Department.objects.filter(name="产品部").exists())

    def test_duplicate_department_name_cannot_be_created(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            self.list_url,
            {
                "name": "研发部",
                "description": "重复名称",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertEqual(
            Department.objects.filter(name="研发部").count(),
            1,
        )

    def test_admin_can_patch_department(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.detail_url,
            {"description": "新的部门说明"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.department.refresh_from_db()
        self.assertEqual(self.department.description, "新的部门说明")

    def test_admin_can_put_department(self):
        self.authenticate(self.admin_user)

        response = self.client.put(
            self.detail_url,
            {
                "name": "研发中心",
                "description": "负责技术研发",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.department.refresh_from_db()
        self.assertEqual(self.department.name, "研发中心")

    def test_duplicate_department_name_cannot_be_updated(self):
        Department.objects.create(name="市场部")
        self.authenticate(self.admin_user)

        response = self.client.patch(
            self.detail_url,
            {"name": "市场部"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_ordinary_user_cannot_update_department(self):
        self.authenticate(self.ordinary_user)

        put_response = self.client.put(
            self.detail_url,
            {"name": "不应修改", "description": ""},
            format="json",
        )
        patch_response = self.client.patch(
            self.detail_url,
            {"name": "不应修改"},
            format="json",
        )

        self.assertEqual(
            put_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            patch_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_delete_department_without_deleting_members(self):
        self.ordinary_user.profile.department = self.department
        self.ordinary_user.profile.save(update_fields=["department"])
        profile_id = self.ordinary_user.profile.pk
        user_id = self.ordinary_user.pk
        self.authenticate(self.admin_user)

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Department.objects.filter(pk=self.department.pk).exists())
        self.assertTrue(User.objects.filter(pk=user_id).exists())
        profile = self.ordinary_user.profile
        profile.refresh_from_db()
        self.assertEqual(profile.pk, profile_id)
        self.assertIsNone(profile.department)

    def test_ordinary_user_cannot_delete_department(self):
        self.authenticate(self.ordinary_user)

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Department.objects.filter(pk=self.department.pk).exists())

    def test_admin_update_and_delete_missing_department_returns_404(self):
        self.authenticate(self.admin_user)
        missing_url = reverse("departments:detail", args=[999999])

        patch_response = self.client.patch(
            missing_url,
            {"name": "不存在"},
            format="json",
        )
        delete_response = self.client.delete(missing_url)

        self.assertEqual(
            patch_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            delete_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_id_and_created_at_cannot_be_forged(self):
        self.authenticate(self.admin_user)
        original_id = self.department.pk
        original_created_at = self.department.created_at

        response = self.client.patch(
            self.detail_url,
            {
                "id": 999999,
                "name": "研发中心",
                "created_at": "2000-01-01T00:00:00Z",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.department.refresh_from_db()
        self.assertEqual(self.department.pk, original_id)
        self.assertEqual(self.department.created_at, original_created_at)

    def test_unsupported_methods_return_405(self):
        self.authenticate(self.admin_user)

        list_put = self.client.put(
            self.list_url,
            {"name": "错误路径"},
            format="json",
        )
        list_patch = self.client.patch(
            self.list_url,
            {"name": "错误路径"},
            format="json",
        )
        list_delete = self.client.delete(self.list_url)
        detail_post = self.client.post(
            self.detail_url,
            {"name": "错误路径"},
            format="json",
        )

        for response in (
            list_put,
            list_patch,
            list_delete,
            detail_post,
        ):
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            )

    def test_department_response_does_not_expose_sensitive_models(self):
        self.authenticate(self.ordinary_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            set(response.data.keys()),
            {"id", "name", "description", "created_at"},
        )
        self.assertNotIn("members", response.data)
        self.assertNotIn("user", response.data)
