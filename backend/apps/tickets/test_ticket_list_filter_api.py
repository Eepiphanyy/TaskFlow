from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department
from apps.users.models import (
    Role,
    RolePermission,
    RolePermissionScope,
    UserRole,
)

from .models import Ticket, TicketCategory

User = get_user_model()
SHANGHAI = ZoneInfo("Asia/Shanghai")


class TicketListFilterAPITests(APITestCase):
    def setUp(self):
        self.department_a = Department.objects.create(name="研发部")
        self.department_b = Department.objects.create(name="市场部")
        self.category_a = TicketCategory.objects.create(name="系统问题")
        self.category_b = TicketCategory.objects.create(name="网络问题")

        self.admin_role = self.create_role("admin", "系统管理员")
        self.manager_role = self.create_role(
            "department_manager",
            "部门负责人",
        )
        self.employee_role = self.create_role("employee", "普通员工")
        self.grant_view_permission(
            self.manager_role,
            RolePermissionScope.DEPARTMENT,
        )
        self.grant_view_permission(
            self.employee_role,
            RolePermissionScope.SELF,
        )

        self.admin_user = self.create_user(
            "filter_admin",
            None,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "filter_manager",
            self.department_a,
            [self.manager_role],
        )
        self.employee_user = self.create_user(
            "filter_employee",
            self.department_a,
            [self.employee_role],
        )
        self.colleague = self.create_user(
            "filter_colleague",
            self.department_a,
            [self.employee_role],
        )
        self.other_department_user = self.create_user(
            "filter_other_department",
            self.department_b,
            [self.employee_role],
        )

        self.ticket_pending = self.create_ticket(
            "网络待处理",
            self.department_a,
            self.employee_user,
            self.category_a,
            Ticket.Status.PENDING,
            Ticket.Priority.LOW,
            datetime(2026, 11, 20, 10, 0, tzinfo=SHANGHAI),
        )
        self.ticket_processing = self.create_ticket(
            "网络故障处理",
            self.department_a,
            self.employee_user,
            self.category_b,
            Ticket.Status.PROCESSING,
            Ticket.Priority.HIGH,
            datetime(2026, 11, 21, 10, 0, tzinfo=SHANGHAI),
        )
        self.ticket_resolved = self.create_ticket(
            "系统问题已解决",
            self.department_a,
            self.colleague,
            self.category_a,
            Ticket.Status.RESOLVED,
            Ticket.Priority.URGENT,
            datetime(2026, 11, 22, 10, 0, tzinfo=SHANGHAI),
        )
        self.ticket_closed_other_department = self.create_ticket(
            "市场部已关闭",
            self.department_b,
            self.other_department_user,
            self.category_b,
            Ticket.Status.CLOSED,
            Ticket.Priority.MEDIUM,
            datetime(2026, 11, 23, 0, 0, tzinfo=SHANGHAI),
        )
        self.ticket_end_boundary = self.create_ticket(
            "网络边界待处理",
            self.department_a,
            self.colleague,
            self.category_a,
            Ticket.Status.PENDING,
            Ticket.Priority.LOW,
            datetime(2026, 11, 23, 23, 59, 59, tzinfo=SHANGHAI),
        )
        self.ticket_next_day = self.create_ticket(
            "网络延迟排查",
            self.department_a,
            self.employee_user,
            self.category_b,
            Ticket.Status.PROCESSING,
            Ticket.Priority.HIGH,
            datetime(2026, 11, 24, 10, 0, tzinfo=SHANGHAI),
        )
        self.list_url = reverse("tickets:list")

    def create_role(self, code, name):
        return Role.objects.create(code=code, name=name)

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

    def create_ticket(
        self,
        title,
        department,
        creator,
        category,
        ticket_status,
        priority,
        created_at,
    ):
        ticket = Ticket.objects.create(
            title=title,
            description=f"{title} 描述",
            department=department,
            creator=creator,
            category=category,
            status=ticket_status,
            priority=priority,
        )
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=created_at
        )
        ticket.refresh_from_db()
        return ticket

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}"
        )

    def get_results(self, params=None):
        response = self.client.get(self.list_url, params or {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response, {
            item["id"]
            for item in response.data["results"]
        }

    def all_ticket_ids(self):
        return {
            self.ticket_pending.pk,
            self.ticket_processing.pk,
            self.ticket_resolved.pk,
            self.ticket_closed_other_department.pk,
            self.ticket_end_boundary.pk,
            self.ticket_next_day.pk,
        }

    def test_no_filter_keeps_existing_list_behavior(self):
        self.authenticate(self.admin_user)

        response, ids = self.get_results()

        self.assertEqual(response.data["count"], 6)
        self.assertEqual(ids, self.all_ticket_ids())

    def test_filter_by_each_status(self):
        self.authenticate(self.admin_user)
        expected = {
            Ticket.Status.PENDING: {
                self.ticket_pending.pk,
                self.ticket_end_boundary.pk,
            },
            Ticket.Status.PROCESSING: {
                self.ticket_processing.pk,
                self.ticket_next_day.pk,
            },
            Ticket.Status.RESOLVED: {
                self.ticket_resolved.pk,
            },
            Ticket.Status.CLOSED: {
                self.ticket_closed_other_department.pk,
            },
        }

        for ticket_status, expected_ids in expected.items():
            _, ids = self.get_results({"status": ticket_status})
            self.assertEqual(ids, expected_ids)

    def test_filter_by_priority(self):
        self.authenticate(self.admin_user)

        _, ids = self.get_results({"priority": Ticket.Priority.HIGH})

        self.assertEqual(
            ids,
            {
                self.ticket_processing.pk,
                self.ticket_next_day.pk,
            },
        )

    def test_filter_by_category(self):
        self.authenticate(self.admin_user)

        _, ids = self.get_results({"category": self.category_a.pk})

        self.assertEqual(
            ids,
            {
                self.ticket_pending.pk,
                self.ticket_resolved.pk,
                self.ticket_end_boundary.pk,
            },
        )

    def test_filter_by_created_after(self):
        self.authenticate(self.admin_user)

        _, ids = self.get_results({"created_after": "2026-11-23"})

        self.assertEqual(
            ids,
            {
                self.ticket_closed_other_department.pk,
                self.ticket_end_boundary.pk,
                self.ticket_next_day.pk,
            },
        )

    def test_filter_by_created_before_includes_end_date(self):
        self.authenticate(self.admin_user)

        _, ids = self.get_results({"created_before": "2026-11-23"})

        self.assertEqual(
            ids,
            {
                self.ticket_pending.pk,
                self.ticket_processing.pk,
                self.ticket_resolved.pk,
                self.ticket_closed_other_department.pk,
                self.ticket_end_boundary.pk,
            },
        )

    def test_multiple_filters_are_combined_with_and(self):
        self.authenticate(self.admin_user)

        _, ids = self.get_results({
            "status": Ticket.Status.PROCESSING,
            "priority": Ticket.Priority.HIGH,
            "category": self.category_b.pk,
            "created_after": "2026-11-22",
            "created_before": "2026-11-24",
        })

        self.assertEqual(ids, {self.ticket_next_day.pk})

    def test_invalid_status_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"status": "unknown"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("status", response.data)

    def test_invalid_priority_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"priority": "critical"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("priority", response.data)

    def test_invalid_category_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {"category": 999999},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("category", response.data)

    def test_invalid_date_returns_400(self):
        self.authenticate(self.admin_user)

        for field in ("created_after", "created_before"):
            response = self.client.get(
                self.list_url,
                {field: "2026-13-40"},
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
            )
            self.assertIn(field, response.data)

    def test_created_after_later_than_created_before_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.client.get(
            self.list_url,
            {
                "created_after": "2026-11-24",
                "created_before": "2026-11-23",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("created_before", response.data)

    def test_search_and_filter_are_combined(self):
        self.authenticate(self.admin_user)

        _, ids = self.get_results({
            "search": "网络",
            "status": Ticket.Status.PROCESSING,
        })

        self.assertEqual(
            ids,
            {
                self.ticket_processing.pk,
                self.ticket_next_day.pk,
            },
        )

    def test_ordering_and_filter_are_combined(self):
        self.authenticate(self.admin_user)

        response, _ = self.get_results({
            "status": Ticket.Status.PENDING,
            "ordering": "-id",
        })

        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [
                self.ticket_end_boundary.pk,
                self.ticket_pending.pk,
            ],
        )

    def test_pagination_and_filter_are_combined(self):
        self.authenticate(self.admin_user)

        response, ids = self.get_results({
            "status": Ticket.Status.PENDING,
            "page_size": 1,
        })

        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(ids), 1)
        self.assertIsNotNone(response.data["next"])

    def test_manager_scope_cannot_be_expanded_by_filter(self):
        self.authenticate(self.manager_user)

        response, ids = self.get_results({
            "status": Ticket.Status.CLOSED,
        })

        self.assertEqual(response.data["count"], 0)
        self.assertEqual(ids, set())

    def test_employee_scope_applies_before_filter(self):
        self.authenticate(self.employee_user)

        _, ids = self.get_results({
            "status": Ticket.Status.PENDING,
        })

        self.assertEqual(ids, {self.ticket_pending.pk})
        self.assertNotIn(self.ticket_end_boundary.pk, ids)

    def test_forged_scope_parameters_do_not_expand_results(self):
        self.authenticate(self.employee_user)

        _, ids = self.get_results({
            "department_id": self.department_b.pk,
            "user_id": self.admin_user.pk,
            "status": Ticket.Status.CLOSED,
        })

        self.assertEqual(ids, set())
