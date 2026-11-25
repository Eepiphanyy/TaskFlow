from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department
from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

from .models import Ticket, TicketCategory

User = get_user_model()


class TicketCategoryListAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("ticket-categories:list")
        self.user = User.objects.create_user(
            username="category_api_user",
            email="category_api_user@example.com",
            password="TaskFlow#2026",
        )

    def authenticate(self, user=None):
        access = str(AccessToken.for_user(user or self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_anonymous_user_returns_401(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_list_categories(self):
        self.authenticate()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_category_list_structure_and_order(self):
        first = TicketCategory.objects.create(
            name="系统问题",
            description="系统故障",
        )
        second = TicketCategory.objects.create(
            name="网络问题",
            description="网络故障",
        )
        self.authenticate()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "id": first.pk,
                    "name": first.name,
                    "description": first.description,
                },
                {
                    "id": second.pk,
                    "name": second.name,
                    "description": second.description,
                },
            ],
        )

    def test_empty_category_database_returns_empty_list(self):
        self.authenticate()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_category_endpoint_has_no_write_methods(self):
        self.authenticate()

        responses = [
            self.client.post(
                self.url,
                {"name": "不应创建"},
                format="json",
            ),
            self.client.put(
                self.url,
                {"name": "不应修改"},
                format="json",
            ),
            self.client.patch(
                self.url,
                {"name": "不应修改"},
                format="json",
            ),
            self.client.delete(self.url),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        self.assertEqual(TicketCategory.objects.count(), 0)

    def test_existing_ticket_query_api_still_returns_category(self):
        role = Role.objects.create(
            name="分类查询测试员工",
            code="category_api_employee",
        )
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="view_ticket",
        )
        RolePermission.objects.create(
            role=role,
            permission=permission,
            scope=RolePermissionScope.SELF,
        )
        UserRole.objects.create(
            user_profile=self.user.profile,
            role=role,
        )
        department = Department.objects.create(name="分类测试部门")
        profile = self.user.profile
        profile.department = department
        profile.save(update_fields=["department"])
        category = TicketCategory.objects.create(name="系统问题")
        Ticket.objects.create(
            title="分类关联工单",
            description="分类查询回归测试",
            category=category,
            department=department,
            creator=self.user,
        )
        self.authenticate()

        response = self.client.get(reverse("tickets:list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["category"],
            {
                "id": category.pk,
                "name": category.name,
            },
        )
