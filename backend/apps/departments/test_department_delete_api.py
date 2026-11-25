from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.tickets.models import Ticket
from apps.users.models import Role, UserRole

from .models import Department

User = get_user_model()


class DepartmentDeleteAPITests(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )
        self.admin_user = User.objects.create_user(
            username="department_delete_admin",
            email="department_delete_admin@example.com",
            password="TaskFlow#2026",
        )
        UserRole.objects.create(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        )
        self.creator = User.objects.create_user(
            username="department_delete_creator",
            email="department_delete_creator@example.com",
            password="TicketFlow#2026",
        )
        self.access = str(AccessToken.for_user(self.admin_user))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access}"
        )

    def test_department_without_tickets_can_be_deleted(self):
        department = Department.objects.create(name="可删除部门")
        url = reverse("departments:detail", args=[department.pk])

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Department.objects.filter(pk=department.pk).exists()
        )

    def test_department_with_tickets_returns_409_and_keeps_data(self):
        department = Department.objects.create(name="受保护部门")
        ticket = Ticket.objects.create(
            title="部门关联工单",
            description="删除保护测试",
            department=department,
            creator=self.creator,
        )
        url = reverse("departments:detail", args=[department.pk])

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data["message"],
            "部门仍有关联工单，无法删除。",
        )
        self.assertTrue(
            Department.objects.filter(pk=department.pk).exists()
        )
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
