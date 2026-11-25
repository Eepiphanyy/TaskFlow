from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from django.test import TransactionTestCase

from apps.departments.models import Department

from .models import Role, UserProfile, UserRole

User = get_user_model()


class UserRoleAPIViewTests(APITestCase):
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
            username="role_admin",
            email="role_admin@example.com",
            password="AdminPassword#2026",
        )
        self.second_admin = User.objects.create_user(
            username="second_admin",
            email="second_admin@example.com",
            password="SecondAdmin#2026",
        )
        self.ordinary_user = User.objects.create_user(
            username="role_user",
            email="role_user@example.com",
            password="UserPassword#2026",
        )
        self.staff_without_role = User.objects.create_user(
            username="role_staff",
            email="role_staff@example.com",
            password="StaffPassword#2026",
            is_staff=True,
        )
        self.target_user = User.objects.create_user(
            username="role_target",
            email="role_target@example.com",
            password="TargetPassword#2026",
        )
        UserRole.objects.create(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        )
        UserRole.objects.create(
            user_profile=self.second_admin.profile,
            role=self.admin_role,
        )
        UserRole.objects.create(
            user_profile=self.target_user.profile,
            role=self.employee_role,
        )
        self.list_url = reverse(
            "user-management:roles",
            args=[self.target_user.pk],
        )
        self.detail_url = reverse(
            "user-management:role-detail",
            args=[self.target_user.pk, self.handler_role.pk],
        )

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_anonymous_user_cannot_query_or_modify_roles(self):
        responses = [
            self.client.get(self.list_url),
            self.client.post(
                self.list_url,
                {"role_id": self.handler_role.pk},
                format="json",
            ),
            self.client.delete(self.detail_url),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
            )

    def test_ordinary_user_cannot_query_other_user_roles(self):
        self.authenticate(self.ordinary_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ordinary_user_cannot_assign_admin_to_self(self):
        self.authenticate(self.ordinary_user)
        url = reverse(
            "user-management:roles",
            args=[self.ordinary_user.pk],
        )

        response = self.client.post(
            url,
            {"role_id": self.admin_role.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            UserRole.objects.filter(
                user_profile=self.ordinary_user.profile,
                role=self.admin_role,
            ).exists()
        )

    def test_staff_without_admin_role_cannot_assign_roles(self):
        self.authenticate(self.staff_without_role)

        response = self.client.post(
            self.list_url,
            {"role_id": self.handler_role.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_query_user_roles(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "获取用户角色成功")
        self.assertEqual(response.data["data"]["user_id"], self.target_user.pk)
        self.assertEqual(response.data["data"]["username"], "role_target")
        self.assertEqual(response.data["data"]["roles"], [{
            "id": self.employee_role.pk,
            "name": "普通员工",
            "code": "employee",
        }])

    def test_admin_can_assign_role(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            self.list_url,
            {"role_id": self.handler_role.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "用户角色分配成功")
        self.assertEqual(response.data["data"]["role"]["code"], "ticket_handler")
        self.assertTrue(UserRole.objects.filter(
            user_profile=self.target_user.profile,
            role=self.handler_role,
        ).exists())

    def test_repeated_role_assignment_is_idempotent(self):
        self.authenticate(self.admin_user)
        self.client.post(
            self.list_url,
            {"role_id": self.handler_role.pk},
            format="json",
        )

        response = self.client.post(
            self.list_url,
            {"role_id": self.handler_role.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "用户角色已存在")
        self.assertEqual(
            UserRole.objects.filter(
                user_profile=self.target_user.profile,
                role=self.handler_role,
            ).count(),
            1,
        )

    def test_admin_can_remove_role_without_deleting_role(self):
        detail_url = reverse(
            "user-management:role-detail",
            args=[self.target_user.pk, self.employee_role.pk],
        )
        self.authenticate(self.admin_user)

        response = self.client.delete(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "用户角色移除成功")
        self.assertFalse(UserRole.objects.filter(
            user_profile=self.target_user.profile,
            role=self.employee_role,
        ).exists())
        self.assertTrue(Role.objects.filter(pk=self.employee_role.pk).exists())

    def test_removing_missing_assignment_returns_404(self):
        detail_url = reverse(
            "user-management:role-detail",
            args=[self.target_user.pk, self.handler_role.pk],
        )
        self.authenticate(self.admin_user)

        response = self.client.delete(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "用户未分配该角色")

    def test_missing_user_and_role_errors(self):
        self.authenticate(self.admin_user)

        missing_user_list = reverse(
            "user-management:roles",
            args=[999999],
        )
        missing_role = self.client.post(
            self.list_url,
            {"role_id": 999999},
            format="json",
        )

        self.assertEqual(
            self.client.get(missing_user_list).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            missing_role.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(missing_role.data["message"], "角色不存在")

    def test_missing_profile_returns_404_without_creating_profile(self):
        UserProfile.objects.filter(user=self.target_user).delete()
        self.authenticate(self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "用户资料不存在")
        self.assertFalse(
            UserProfile.objects.filter(user=self.target_user).exists()
        )

    def test_role_payload_rejects_extra_fields_and_preserves_data(self):
        department = Department.objects.create(name="研发部")
        self.target_user.profile.department = department
        self.target_user.profile.save(update_fields=["department"])
        self.authenticate(self.admin_user)

        response = self.client.post(
            self.list_url,
            {
                "role_id": self.handler_role.pk,
                "name": "伪造角色",
                "code": "forged",
                "password": "ChangedPassword#2026",
                "department_id": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.handler_role.refresh_from_db()
        self.target_user.refresh_from_db()
        self.target_user.profile.refresh_from_db()
        self.assertEqual(self.handler_role.name, "工单处理人员")
        self.assertEqual(self.handler_role.code, "ticket_handler")
        self.assertTrue(
            self.target_user.check_password("TargetPassword#2026")
        )
        self.assertEqual(self.target_user.profile.department, department)
        self.assertFalse(UserRole.objects.filter(
            user_profile=self.target_user.profile,
            role=self.handler_role,
        ).exists())

    def test_removed_admin_role_affects_subsequent_admin_requests(self):
        self.authenticate(self.second_admin)
        self.assertEqual(
            self.client.get(self.list_url).status_code,
            status.HTTP_200_OK,
        )

        detail_url = reverse(
            "user-management:role-detail",
            args=[self.second_admin.pk, self.admin_role.pk],
        )
        self.authenticate(self.admin_user)
        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)

        self.authenticate(self.second_admin)
        denied_response = self.client.get(self.list_url)
        self.assertEqual(
            denied_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_last_admin_role_cannot_be_removed(self):
        second_admin_url = reverse(
            "user-management:role-detail",
            args=[self.second_admin.pk, self.admin_role.pk],
        )
        own_admin_url = reverse(
            "user-management:role-detail",
            args=[self.admin_user.pk, self.admin_role.pk],
        )
        self.authenticate(self.admin_user)

        first_response = self.client.delete(second_admin_url)
        last_admin_response = self.client.delete(own_admin_url)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            last_admin_response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            last_admin_response.data["message"],
            "不能移除最后一个 admin 角色",
        )
        self.assertEqual(
            UserRole.objects.filter(role=self.admin_role).count(),
            1,
        )
        self.assertTrue(UserRole.objects.filter(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        ).exists())

    def test_admin_can_remove_own_role_when_another_admin_exists(self):
        own_admin_url = reverse(
            "user-management:role-detail",
            args=[self.admin_user.pk, self.admin_role.pk],
        )
        self.authenticate(self.admin_user)

        response = self.client.delete(own_admin_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            UserRole.objects.filter(role=self.admin_role).count(),
            1,
        )
        self.assertTrue(UserRole.objects.filter(
            user_profile=self.second_admin.profile,
            role=self.admin_role,
        ).exists())

        denied_response = self.client.get(self.list_url)
        self.assertEqual(
            denied_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_current_user_and_department_apis_still_work(self):
        department = Department.objects.create(name="测试部门")
        self.target_user.profile.department = department
        self.target_user.profile.save(update_fields=["department"])
        self.authenticate(self.target_user)

        me_response = self.client.get(reverse("users:me"))
        department_response = self.client.get(
            reverse("departments:detail", args=[department.pk])
        )

        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [role["code"] for role in me_response.data["data"]["roles"]],
            ["employee"],
        )
        self.assertEqual(
            department_response.data["id"],
            department.pk,
        )

    def test_unsupported_methods_return_405(self):
        self.authenticate(self.admin_user)

        collection_responses = [
            self.client.put(self.list_url, {}, format="json"),
            self.client.patch(self.list_url, {}, format="json"),
            self.client.delete(self.list_url),
        ]
        detail_responses = [
            self.client.get(self.detail_url),
            self.client.post(self.detail_url, {}, format="json"),
            self.client.put(self.detail_url, {}, format="json"),
            self.client.patch(self.detail_url, {}, format="json"),
        ]

        for response in collection_responses + detail_responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            )


class ConcurrentAdminRemovalTests(TransactionTestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )
        self.admin_a = User.objects.create_user(
            username="concurrent_admin_a",
            email="concurrent_admin_a@example.com",
            password="AdminPassword#2026",
        )
        self.admin_b = User.objects.create_user(
            username="concurrent_admin_b",
            email="concurrent_admin_b@example.com",
            password="AdminPassword#2026",
        )
        UserRole.objects.create(
            user_profile=self.admin_a.profile,
            role=self.admin_role,
        )
        UserRole.objects.create(
            user_profile=self.admin_b.profile,
            role=self.admin_role,
        )
        self.token_a = str(AccessToken.for_user(self.admin_a))
        self.token_b = str(AccessToken.for_user(self.admin_b))

    def remove_admin(self, token, target_user_id, barrier):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        barrier.wait(timeout=10)

        try:
            response = client.delete(reverse(
                "user-management:role-detail",
                args=[target_user_id, self.admin_role.pk],
            ))
            return response.status_code
        finally:
            connections.close_all()

    def test_concurrent_removals_never_leave_zero_admins(self):
        barrier = Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self.remove_admin,
                    self.token_a,
                    self.admin_b.pk,
                    barrier,
                ),
                executor.submit(
                    self.remove_admin,
                    self.token_b,
                    self.admin_a.pk,
                    barrier,
                ),
            ]
            statuses = sorted(future.result(timeout=15) for future in futures)

        self.assertEqual(
            UserRole.objects.filter(role=self.admin_role).count(),
            1,
        )
        self.assertIn(status.HTTP_200_OK, statuses)
        self.assertTrue(any(
            status_code in (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_409_CONFLICT,
            )
            for status_code in statuses
        ))
