from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department
from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

from .models import Ticket, TicketCategory

User = get_user_model()


class TicketQueryAPITests(APITestCase):
    def setUp(self):
        self.department_a = Department.objects.create(name="研发部")
        self.department_b = Department.objects.create(name="市场部")
        self.category = TicketCategory.objects.create(name="系统问题")

        self.self_role = self.create_role("ticket_api_self")
        self.department_role = self.create_role("ticket_api_department")
        self.all_role = self.create_role("ticket_api_all")
        self.admin_role = self.create_role("admin", "系统管理员")
        self.grant_view_permission(
            self.self_role,
            RolePermissionScope.SELF,
        )
        self.grant_view_permission(
            self.department_role,
            RolePermissionScope.DEPARTMENT,
        )
        self.grant_view_permission(
            self.all_role,
            RolePermissionScope.ALL,
        )

        self.self_user = self.create_user(
            "ticket_self_user",
            self.department_a,
            [self.self_role],
        )
        self.department_user = self.create_user(
            "ticket_department_user",
            self.department_a,
            [self.department_role],
        )
        self.both_user = self.create_user(
            "ticket_both_user",
            self.department_a,
            [self.self_role, self.department_role],
        )
        self.all_user = self.create_user(
            "ticket_all_user",
            self.department_a,
            [self.all_role],
        )
        self.no_permission_user = self.create_user(
            "ticket_no_permission",
            self.department_a,
        )
        self.colleague = self.create_user(
            "ticket_colleague",
            self.department_a,
        )
        self.other_department_user = self.create_user(
            "ticket_other_department",
            self.department_b,
        )
        self.staff_user = User.objects.create_user(
            username="ticket_staff_user",
            email="ticket_staff_user@example.com",
            password="TaskFlow#2026",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="ticket_superuser",
            email="ticket_superuser@example.com",
            password="TaskFlow#2026",
        )
        self.admin_user = self.create_user(
            "ticket_admin_user",
            None,
            [self.admin_role],
        )

        self.own_created_ticket = self.create_ticket(
            "A 本人创建研发工单",
            self.department_a,
            self.self_user,
        )
        self.assigned_ticket = self.create_ticket(
            "B 分配本人研发工单",
            self.department_a,
            self.colleague,
            assignee=self.self_user,
        )
        self.department_ticket = self.create_ticket(
            "C 部门其他研发工单",
            self.department_a,
            self.colleague,
        )
        self.other_department_ticket = self.create_ticket(
            "D 市场部工单",
            self.department_b,
            self.other_department_user,
        )

        self.list_url = reverse("tickets:list")
        self.detail_url = reverse(
            "tickets:detail",
            args=[self.own_created_ticket.pk],
        )

    def create_role(self, code, name=None):
        return Role.objects.create(
            name=name or f"角色 {code}",
            code=code,
        )

    def grant_view_permission(self, role, scope):
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="view_ticket",
        )
        RolePermission.objects.create(
            role=role,
            permission=permission,
            scope=scope,
        )

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

    def create_ticket(
        self,
        title,
        department,
        creator,
        assignee=None,
    ):
        return Ticket.objects.create(
            title=title,
            description=f"{title} 描述",
            category=self.category,
            department=department,
            creator=creator,
            assignee=assignee,
        )

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def result_ids(self, response):
        return {
            item["id"]
            for item in response.data["results"]
        }

    def test_anonymous_list_returns_401(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_detail_returns_401(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logged_in_user_can_list_tickets(self):
        self.authenticate(self.self_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
            },
        )

    def test_logged_in_user_can_view_ticket_detail(self):
        self.authenticate(self.self_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["id"],
            self.own_created_ticket.pk,
        )

    def test_user_without_permission_cannot_list(self):
        self.authenticate(self.no_permission_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_permission_cannot_view_detail(self):
        self.authenticate(self.no_permission_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_view_all_tickets(self):
        self.authenticate(self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
                self.department_ticket.pk,
                self.other_department_ticket.pk,
            },
        )

    def test_staff_is_not_taskflow_admin(self):
        self.authenticate(self.staff_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_is_not_taskflow_admin(self):
        self.authenticate(self.superuser)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_self_scope_returns_created_and_assigned_tickets(self):
        self.authenticate(self.self_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
            },
        )

    def test_department_scope_returns_only_current_department(self):
        self.authenticate(self.department_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
                self.department_ticket.pk,
            },
        )

    def test_self_and_department_scopes_return_union(self):
        own_other_department_ticket = self.create_ticket(
            "E 本人历史市场部工单",
            self.department_b,
            self.both_user,
        )
        self.authenticate(self.both_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
                self.department_ticket.pk,
                own_other_department_ticket.pk,
            },
        )

    def test_all_scope_returns_all_tickets(self):
        self.authenticate(self.all_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 4)
        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
                self.department_ticket.pk,
                self.other_department_ticket.pk,
            },
        )

    def test_list_does_not_leak_other_departments(self):
        self.authenticate(self.department_user)

        response = self.client.get(self.list_url)

        self.assertNotIn(
            self.other_department_ticket.pk,
            self.result_ids(response),
        )

    def test_detail_does_not_leak_other_departments(self):
        self.authenticate(self.department_user)

        response = self.client.get(reverse(
            "tickets:detail",
            args=[self.other_department_ticket.pk],
        ))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthorized_detail_returns_404(self):
        unrelated_ticket = self.create_ticket(
            "F 无关工单",
            self.department_b,
            self.other_department_user,
        )
        self.authenticate(self.self_user)

        response = self.client.get(reverse(
            "tickets:detail",
            args=[unrelated_ticket.pk],
        ))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_detail_returns_404(self):
        self.authenticate(self.all_user)

        response = self.client.get(
            reverse("tickets:detail", args=[999999])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_creator_department_change_uses_ticket_department(self):
        self.authenticate(self.department_user)
        profile = self.department_user.profile
        profile.department = self.department_b
        profile.save(update_fields=["department"])

        old_department_response = self.client.get(reverse(
            "tickets:detail",
            args=[self.own_created_ticket.pk],
        ))
        new_department_response = self.client.get(reverse(
            "tickets:detail",
            args=[self.other_department_ticket.pk],
        ))

        self.assertEqual(
            old_department_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            new_department_response.status_code,
            status.HTTP_200_OK,
        )

    def test_cross_department_assignee_does_not_move_ticket(self):
        self.authenticate(self.department_user)
        cross_department_ticket = self.create_ticket(
            "G 跨部门处理研发工单",
            self.department_a,
            self.colleague,
            assignee=self.other_department_user,
        )

        response = self.client.get(reverse(
            "tickets:detail",
            args=[cross_department_ticket.pk],
        ))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["department"]["id"],
            self.department_a.pk,
        )

    def test_forged_user_id_does_not_change_scope(self):
        self.authenticate(self.self_user)

        response = self.client.get(
            self.list_url,
            {"user_id": self.admin_user.pk},
        )

        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
            },
        )

    def test_forged_department_id_does_not_change_scope(self):
        self.authenticate(self.self_user)

        response = self.client.get(
            self.list_url,
            {"department_id": self.department_b.pk},
        )

        self.assertEqual(
            self.result_ids(response),
            {
                self.own_created_ticket.pk,
                self.assigned_ticket.pk,
            },
        )

    def test_list_supports_pagination(self):
        self.authenticate(self.all_user)

        response = self.client.get(
            self.list_url,
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_list_supports_title_search(self):
        self.authenticate(self.all_user)

        response = self.client.get(
            self.list_url,
            {"search": "研发"},
        )

        self.assertEqual(response.data["count"], 3)
        self.assertTrue(all(
            "研发" in item["title"]
            for item in response.data["results"]
        ))

    def test_list_supports_ordering(self):
        self.authenticate(self.all_user)

        response = self.client.get(
            self.list_url,
            {"ordering": "title"},
        )

        titles = [
            item["title"]
            for item in response.data["results"]
        ]
        self.assertEqual(titles, sorted(titles))

    def test_search_ordering_and_pagination_keep_scope(self):
        self.authenticate(self.department_user)

        response = self.client.get(
            self.list_url,
            {
                "search": "研发",
                "ordering": "-title",
                "page_size": 1,
            },
        )

        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.department_ticket.pk,
        )
        self.assertNotIn(
            self.other_department_ticket.pk,
            {
                ticket["id"]
                for ticket in response.data["results"]
            },
        )

    def test_empty_ticket_database_returns_empty_list(self):
        Ticket.objects.all().delete()
        self.authenticate(self.self_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_serializer_does_not_expose_sensitive_fields(self):
        self.authenticate(self.self_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            set(response.data),
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
        for user_field in ("creator",):
            self.assertEqual(
                set(response.data[user_field]),
                {"id", "username", "email"},
            )
            self.assertNotIn("password", response.data[user_field])
            self.assertNotIn("is_staff", response.data[user_field])
            self.assertNotIn("is_superuser", response.data[user_field])
        self.assertIsNone(response.data["assignee"])

    def test_related_objects_have_expected_structure(self):
        self.authenticate(self.self_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.data["category"],
            {
                "id": self.category.pk,
                "name": self.category.name,
            },
        )
        self.assertEqual(
            response.data["creator"],
            {
                "id": self.self_user.pk,
                "username": self.self_user.username,
                "email": self.self_user.email,
            },
        )
        self.assertIsNone(response.data["assignee"])
        self.assertEqual(
            response.data["department"],
            {
                "id": self.department_a.pk,
                "name": self.department_a.name,
            },
        )

    def test_list_query_count_does_not_grow_with_ticket_count(self):
        self.authenticate(self.all_user)

        with CaptureQueriesContext(connection) as baseline_queries:
            baseline_response = self.client.get(
                self.list_url,
                {"page_size": 2},
            )

        for index in range(1, 7):
            self.create_ticket(
                f"H 查询数量工单 {index}",
                self.department_a,
                self.colleague,
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                self.list_url,
                {"page_size": 2},
            )

        self.assertEqual(baseline_response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 10)
        self.assertEqual(len(queries), len(baseline_queries))
