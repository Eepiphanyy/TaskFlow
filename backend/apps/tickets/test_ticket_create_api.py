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


class TicketCreateAPITests(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(name="研发部")
        self.other_department = Department.objects.create(name="市场部")
        self.category = TicketCategory.objects.create(name="系统问题")

        self.add_role = Role.objects.create(
            name="工单创建人员",
            code="ticket_api_creator",
        )
        add_permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="add_ticket",
        )
        RolePermission.objects.create(
            role=self.add_role,
            permission=add_permission,
            scope=RolePermissionScope.ALL,
        )
        self.admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )

        self.creator = self.create_user(
            "ticket_create_user",
            self.department,
            [self.add_role],
        )
        self.normal_user = self.create_user(
            "ticket_create_no_permission",
            self.department,
        )
        self.admin_user = self.create_user(
            "ticket_create_admin",
            self.department,
            [self.admin_role],
        )
        self.staff_user = User.objects.create_user(
            username="ticket_create_staff",
            email="ticket_create_staff@example.com",
            password="TaskFlow#2026",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="ticket_create_superuser",
            email="ticket_create_superuser@example.com",
            password="TaskFlow#2026",
        )
        self.url = reverse("tickets:list")

    def create_user(self, username, department, roles=None):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="TaskFlow#2026",
        )
        profile = user.profile
        profile.department = department
        profile.save(update_fields=["department"])
        for role in roles or []:
            UserRole.objects.create(
                user_profile=profile,
                role=role,
            )
        return user

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def payload(self, **overrides):
        data = {
            "title": "创建接口工单",
            "description": "创建接口工单描述",
        }
        data.update(overrides)
        return data

    def test_anonymous_user_returns_401(self):
        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_user_without_add_permission_returns_403(self):
        self.authenticate(self.normal_user)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_user_with_add_permission_can_create(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_admin_can_create(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            self.url,
            self.payload(title="管理员创建工单"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Ticket.objects.filter(title="管理员创建工单").exists()
        )

    def test_staff_without_business_permission_cannot_create(self):
        self.authenticate(self.staff_user)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_superuser_without_business_permission_cannot_create(self):
        self.authenticate(self.superuser)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_creator_is_always_current_user(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        ticket = Ticket.objects.get()
        self.assertEqual(response.data["creator"]["id"], self.creator.pk)
        self.assertEqual(ticket.creator, self.creator)

    def test_forged_creator_is_rejected(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(creator=self.admin_user.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("creator", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_forged_department_is_rejected(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(department=self.other_department.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_department_comes_from_creator_profile(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            response.data["department"],
            {
                "id": self.department.pk,
                "name": self.department.name,
            },
        )
        self.assertEqual(
            Ticket.objects.get().department_id,
            self.department.pk,
        )

    def test_creator_without_profile_is_rejected(self):
        self.creator.profile.delete()
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_creator_without_department_returns_400(self):
        profile = self.creator.profile
        profile.department = None
        profile.save(update_fields=["department"])
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("未分配部门", response.data["message"])
        self.assertEqual(Ticket.objects.count(), 0)

    def test_failed_creation_leaves_no_ticket(self):
        profile = self.creator.profile
        profile.department = None
        profile.save(update_fields=["department"])
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(title="应失败工单"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Ticket.objects.filter(title="应失败工单").exists()
        )

    def test_title_is_required(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            {"description": "缺少标题"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_description_is_required(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            {"title": "缺少描述"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_valid_category_is_associated(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(category=self.category.pk),
            format="json",
        )

        ticket = Ticket.objects.get()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ticket.category, self.category)
        self.assertEqual(
            response.data["category"],
            {
                "id": self.category.pk,
                "name": self.category.name,
            },
        )

    def test_missing_category_returns_400(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(category=999999),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_status_cannot_be_set_by_client(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(status=Ticket.Status.CLOSED),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_priority_cannot_be_set_by_client(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(priority=Ticket.Priority.URGENT),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("priority", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_assignee_cannot_be_set_by_client(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(assignee=self.normal_user.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assignee", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_creator_and_department_cannot_be_modified(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(
                creator=self.admin_user.pk,
                department=self.other_department.pk,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("creator", response.data)
        self.assertIn("department", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_unknown_field_is_rejected(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(is_superuser=True),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_superuser", response.data)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_creation_returns_201(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_response_uses_ticket_read_structure(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(
            set(response.data.keys()),
            {
                "id",
                "title",
                "description",
                "category",
                "creator",
                "assignee",
                "department",
                "status",
                "priority",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(
            set(response.data["creator"]),
            {"id", "username", "email"},
        )
        self.assertIsNone(response.data["assignee"])
        self.assertEqual(
            response.data["status"],
            Ticket.Status.PENDING,
        )
        self.assertEqual(
            response.data["priority"],
            Ticket.Priority.MEDIUM,
        )

    def test_creation_persists_exactly_one_ticket(self):
        self.authenticate(self.creator)

        response = self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(
            Ticket.objects.get().title,
            "创建接口工单",
        )

    def test_department_snapshot_is_saved(self):
        self.authenticate(self.creator)

        self.client.post(
            self.url,
            self.payload(),
            format="json",
        )

        ticket = Ticket.objects.get()
        self.assertEqual(ticket.department_id, self.department.pk)

    def test_creator_department_change_does_not_change_created_ticket(self):
        self.authenticate(self.creator)
        self.client.post(
            self.url,
            self.payload(),
            format="json",
        )
        ticket = Ticket.objects.get()
        profile = self.creator.profile
        profile.department = self.other_department
        profile.save(update_fields=["department"])
        ticket.refresh_from_db()

        self.assertEqual(ticket.department_id, self.department.pk)
