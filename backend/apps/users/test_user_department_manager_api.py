from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import close_old_connections, transaction
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department
from apps.users.models import (
    Role,
    RolePermission,
    RolePermissionScope,
    UserProfile,
    UserRole,
)

User = get_user_model()


class UserDepartmentManagerAPITests(APITestCase):
    def setUp(self):
        self.department_a = Department.objects.create(name="部门 A")
        self.department_b = Department.objects.create(name="部门 B")
        self.admin_role = self.create_role("admin", "系统管理员")
        self.manager_role = self.create_role(
            "department_manager",
            "部门负责人",
        )
        self.employee_role = self.create_role("employee", "普通员工")
        self.grant_assign_permission(self.manager_role)

        self.admin_user = self.create_user(
            "department_assign_admin",
            self.department_a,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "department_assign_manager",
            self.department_a,
            [self.manager_role],
        )
        self.manager_without_department = self.create_user(
            "department_assign_no_dept",
            None,
            [self.manager_role],
        )
        self.manager_without_profile = self.create_user(
            "department_assign_no_profile",
            self.department_a,
            [self.manager_role],
        )
        self.manager_without_profile.profile.delete()
        self.employee_user = self.create_user(
            "department_assign_employee",
            self.department_a,
            [self.employee_role],
        )
        self.target_in_a = self.create_user(
            "department_target_a",
            self.department_a,
            [self.employee_role],
        )
        self.target_in_b = self.create_user(
            "department_target_b",
            self.department_b,
            [self.employee_role],
        )

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_assign_permission(self, role):
        permission = Permission.objects.get(
            content_type__app_label="users",
            codename="assign_user_department",
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

    def assign_url(self, user):
        return reverse("user-management:department", args=[user.pk])

    def patch_department(self, user, department):
        return self.client.patch(
            self.assign_url(user),
            {
                "department_id": (
                    department.pk
                    if department is not None
                    else None
                )
            },
            format="json",
        )

    def test_admin_can_move_user_across_departments(self):
        self.authenticate(self.admin_user)

        response = self.patch_department(
            self.target_in_a,
            self.department_b,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_in_a.profile.refresh_from_db()
        self.assertEqual(
            self.target_in_a.profile.department_id,
            self.department_b.pk,
        )

    def test_manager_can_operate_user_in_own_department(self):
        self.authenticate(self.manager_user)

        response = self.patch_department(
            self.target_in_a,
            self.department_a,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_in_a.profile.refresh_from_db()
        self.assertEqual(
            self.target_in_a.profile.department_id,
            self.department_a.pk,
        )

    def test_manager_cannot_operate_other_department_user(self):
        self.authenticate(self.manager_user)

        response = self.patch_department(
            self.target_in_b,
            self.department_b,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.target_in_b.profile.refresh_from_db()
        self.assertEqual(
            self.target_in_b.profile.department_id,
            self.department_b.pk,
        )

    def test_manager_cannot_move_own_department_user_out(self):
        self.authenticate(self.manager_user)

        response = self.patch_department(
            self.target_in_a,
            self.department_b,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.target_in_a.profile.refresh_from_db()
        self.assertEqual(
            self.target_in_a.profile.department_id,
            self.department_a.pk,
        )

    def test_manager_cannot_move_other_department_user_in(self):
        self.authenticate(self.manager_user)

        response = self.patch_department(
            self.target_in_b,
            self.department_a,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.target_in_b.profile.refresh_from_db()
        self.assertEqual(
            self.target_in_b.profile.department_id,
            self.department_b.pk,
        )

    def test_employee_cannot_assign_department(self):
        self.authenticate(self.employee_user)

        response = self.patch_department(
            self.target_in_a,
            self.department_b,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_without_department_cannot_assign_department(self):
        self.authenticate(self.manager_without_department)

        response = self.patch_department(
            self.target_in_a,
            self.department_a,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_without_profile_cannot_assign_department(self):
        self.authenticate(self.manager_without_profile)

        response = self.patch_department(
            self.target_in_a,
            self.department_a,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserDepartmentConcurrentScopeTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.department_a = Department.objects.create(name="并发部门 A")
        self.department_b = Department.objects.create(name="并发部门 B")
        self.manager_role = Role.objects.create(
            name="部门负责人",
            code="department_manager",
        )
        permission = Permission.objects.get(
            content_type__app_label="users",
            codename="assign_user_department",
        )
        RolePermission.objects.create(
            role=self.manager_role,
            permission=permission,
            scope=RolePermissionScope.DEPARTMENT,
        )
        self.manager = User.objects.create_user(
            username="department_concurrent_manager",
            email="department_concurrent_manager@example.com",
            password="TaskFlow#2026",
        )
        self.manager.profile.department = self.department_a
        self.manager.profile.save(update_fields=["department"])
        UserRole.objects.create(
            user_profile=self.manager.profile,
            role=self.manager_role,
        )
        self.target = User.objects.create_user(
            username="department_concurrent_target",
            email="department_concurrent_target@example.com",
            password="TaskFlow#2026",
        )
        self.target.profile.department = self.department_a
        self.target.profile.save(update_fields=["department"])
        self.url = reverse(
            "user-management:department",
            args=[self.target.pk],
        )
        self.access_token = str(AccessToken.for_user(self.manager))

    def test_locked_department_recheck_prevents_stale_scope_write(self):
        request_started = Event()
        executor = ThreadPoolExecutor(max_workers=1)

        def send_request():
            close_old_connections()
            request_started.set()
            client = APIClient()
            client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
            )
            response = client.patch(
                self.url,
                {"department_id": self.department_a.pk},
                format="json",
            )
            close_old_connections()
            return response

        with transaction.atomic():
            list(
                User.objects.select_for_update()
                .filter(pk__in=[self.manager.pk, self.target.pk])
                .order_by("pk")
            )
            target_profile = (
                UserProfile.objects.select_for_update()
                .get(user=self.target)
            )
            target_profile.department = self.department_b
            target_profile.save(update_fields=["department"])

            future = executor.submit(send_request)
            request_started.wait(timeout=2)
            sleep(0.3)

        try:
            response = future.result(timeout=10)
        finally:
            executor.shutdown(wait=True)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.target.profile.refresh_from_db()
        self.assertEqual(
            self.target.profile.department_id,
            self.department_b.pk,
        )
