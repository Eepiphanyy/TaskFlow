from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department
from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

from .models import Ticket

User = get_user_model()


class TicketCloseAPITests(APITestCase):
    def setUp(self):
        self.department_a = Department.objects.create(name="研发部")
        self.department_b = Department.objects.create(name="市场部")

        self.admin_role = self.create_role("admin", "系统管理员")
        self.manager_role = self.create_role(
            "department_manager",
            "部门负责人",
        )
        self.employee_role = self.create_role("employee", "普通员工")
        self.handler_role = self.create_role(
            "ticket_handler",
            "工单处理人员",
        )
        self.grant_close_permission(
            self.manager_role,
            RolePermissionScope.DEPARTMENT,
        )
        self.grant_close_permission(
            self.handler_role,
            RolePermissionScope.SELF,
        )

        self.admin_user = self.create_user(
            "close_admin",
            self.department_a,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "close_manager",
            self.department_a,
            [self.manager_role],
        )
        self.employee_user = self.create_user(
            "close_employee",
            self.department_a,
            [self.employee_role],
        )
        self.staff_user = User.objects.create_user(
            username="close_staff",
            email="close_staff@example.com",
            password="TaskFlow#2026",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="close_superuser",
            email="close_superuser@example.com",
            password="TaskFlow#2026",
        )
        self.colleague = self.create_user(
            "close_colleague",
            self.department_a,
            [self.employee_role],
        )
        self.handler = self.create_user(
            "close_handler",
            self.department_b,
            [self.handler_role],
        )
        self.second_handler = self.create_user(
            "close_handler_second",
            self.department_a,
            [self.handler_role],
        )
        self.multi_role_user = self.create_user(
            "close_multi_role",
            self.department_a,
            [self.manager_role, self.handler_role],
        )

        self.resolved_ticket = self.create_ticket(
            "已解决工单",
            Ticket.Status.RESOLVED,
            Ticket.Priority.HIGH,
            self.department_a,
            assignee=self.handler,
        )
        self.pending_ticket = self.create_ticket(
            "待处理工单",
            Ticket.Status.PENDING,
            Ticket.Priority.MEDIUM,
            self.department_a,
            assignee=self.handler,
        )
        self.processing_ticket = self.create_ticket(
            "处理中工单",
            Ticket.Status.PROCESSING,
            Ticket.Priority.MEDIUM,
            self.department_a,
            assignee=self.handler,
        )
        self.closed_ticket = self.create_ticket(
            "已关闭工单",
            Ticket.Status.CLOSED,
            Ticket.Priority.MEDIUM,
            self.department_a,
            assignee=self.handler,
        )
        self.other_department_ticket = self.create_ticket(
            "其他部门已解决工单",
            Ticket.Status.RESOLVED,
            Ticket.Priority.LOW,
            self.department_b,
            assignee=self.second_handler,
        )

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_close_permission(self, role, scope):
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="close_ticket",
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
        ticket_status,
        priority,
        department,
        assignee=None,
        creator=None,
    ):
        return Ticket.objects.create(
            title=title,
            description=f"{title} 描述",
            department=department,
            creator=creator or self.colleague,
            assignee=assignee,
            status=ticket_status,
            priority=priority,
        )

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def close_url(self, ticket):
        return reverse("tickets:close", args=[ticket.pk])

    def close_ticket(self, ticket, data=None):
        return self.client.post(
            self.close_url(ticket),
            data or {},
            format="json",
        )

    def test_anonymous_request_returns_401(self):
        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employee_cannot_close_ticket(self):
        self.authenticate(self.employee_user)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_close_without_business_permission(self):
        self.authenticate(self.staff_user)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_cannot_close_without_business_permission(self):
        self.authenticate(self.superuser)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_close_any_department_ticket(self):
        self.authenticate(self.admin_user)

        response = self.close_ticket(self.other_department_ticket)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.other_department_ticket.refresh_from_db()
        self.assertEqual(
            self.other_department_ticket.status,
            Ticket.Status.CLOSED,
        )

    def test_department_manager_can_close_own_department_ticket(self):
        self.authenticate(self.manager_user)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.status,
            Ticket.Status.CLOSED,
        )

    def test_department_manager_cannot_close_other_department_ticket(self):
        self.authenticate(self.manager_user)

        response = self.close_ticket(self.other_department_ticket)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ticket_handler_can_close_assigned_ticket(self):
        self.authenticate(self.handler)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.status,
            Ticket.Status.CLOSED,
        )

    def test_ticket_handler_cannot_close_other_assignee_ticket(self):
        self.authenticate(self.handler)

        response = self.close_ticket(self.other_department_ticket)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ticket_handler_creator_is_not_enough(self):
        creator_ticket = self.create_ticket(
            "创建人不是当前处理人",
            Ticket.Status.RESOLVED,
            Ticket.Priority.MEDIUM,
            self.department_b,
            assignee=self.second_handler,
            creator=self.handler,
        )
        self.authenticate(self.handler)

        response = self.close_ticket(creator_ticket)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        creator_ticket.refresh_from_db()
        self.assertEqual(
            creator_ticket.status,
            Ticket.Status.RESOLVED,
        )

    def test_multi_role_user_gets_role_permission_union(self):
        self.resolved_ticket.assignee = self.second_handler
        self.resolved_ticket.save(update_fields=["assignee"])
        self.authenticate(self.multi_role_user)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.status,
            Ticket.Status.CLOSED,
        )

    def test_resolved_to_closed_succeeds(self):
        self.authenticate(self.handler)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.status,
            Ticket.Status.CLOSED,
        )

    def test_pending_to_closed_returns_409(self):
        self.authenticate(self.handler)

        response = self.close_ticket(self.pending_ticket)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_processing_to_closed_returns_409(self):
        self.authenticate(self.handler)

        response = self.close_ticket(self.processing_ticket)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_closed_to_closed_returns_409(self):
        self.authenticate(self.handler)

        response = self.close_ticket(self.closed_ticket)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_invalid_state_does_not_change_database(self):
        original_status = self.processing_ticket.status
        self.authenticate(self.handler)

        self.close_ticket(self.processing_ticket)

        self.processing_ticket.refresh_from_db()
        self.assertEqual(self.processing_ticket.status, original_status)

    def test_repeated_close_returns_409(self):
        self.authenticate(self.handler)

        first_response = self.close_ticket(self.resolved_ticket)
        second_response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)

    def test_close_does_not_change_creator(self):
        original_creator_id = self.resolved_ticket.creator_id
        self.authenticate(self.handler)

        self.close_ticket(self.resolved_ticket)

        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.creator_id,
            original_creator_id,
        )

    def test_close_does_not_change_assignee(self):
        original_assignee_id = self.resolved_ticket.assignee_id
        self.authenticate(self.handler)

        self.close_ticket(self.resolved_ticket)

        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.assignee_id,
            original_assignee_id,
        )

    def test_close_does_not_change_department(self):
        original_department_id = self.resolved_ticket.department_id
        self.authenticate(self.handler)

        self.close_ticket(self.resolved_ticket)

        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.department_id,
            original_department_id,
        )

    def test_close_does_not_change_priority(self):
        original_priority = self.resolved_ticket.priority
        self.authenticate(self.handler)

        self.close_ticket(self.resolved_ticket)

        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.priority,
            original_priority,
        )

    def test_close_sets_status_to_closed(self):
        self.authenticate(self.handler)

        self.close_ticket(self.resolved_ticket)

        self.resolved_ticket.refresh_from_db()
        self.assertEqual(
            self.resolved_ticket.status,
            Ticket.Status.CLOSED,
        )

    def test_close_updates_updated_at(self):
        old_updated_at = timezone.now() - timedelta(days=1)
        Ticket.objects.filter(pk=self.resolved_ticket.pk).update(
            updated_at=old_updated_at
        )
        self.authenticate(self.handler)

        response = self.close_ticket(self.resolved_ticket)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resolved_ticket.refresh_from_db()
        self.assertGreater(
            self.resolved_ticket.updated_at,
            old_updated_at,
        )

    def test_status_field_is_rejected(self):
        self.authenticate(self.handler)

        response = self.close_ticket(
            self.resolved_ticket,
            {"status": Ticket.Status.CLOSED},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_other_ticket_fields_are_rejected(self):
        self.authenticate(self.handler)

        response = self.close_ticket(
            self.resolved_ticket,
            {
                "priority": Ticket.Priority.URGENT,
                "assignee_id": self.second_handler.pk,
                "department": self.department_b.pk,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("priority", response.data)
        self.assertIn("assignee_id", response.data)
        self.assertIn("department", response.data)

    def test_scope_parameters_cannot_be_forged(self):
        self.authenticate(self.manager_user)

        response = self.client.post(
            (
                f"{self.close_url(self.other_department_ticket)}"
                f"?user_id={self.admin_user.pk}"
                f"&department_id={self.department_b.pk}"
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_success_response_uses_ticket_read_structure(self):
        self.authenticate(self.handler)

        response = self.close_ticket(self.resolved_ticket)

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
        self.assertEqual(response.data["status"], Ticket.Status.CLOSED)

    def test_closed_ticket_is_persisted(self):
        self.authenticate(self.handler)

        self.close_ticket(self.resolved_ticket)

        stored_ticket = Ticket.objects.get(pk=self.resolved_ticket.pk)
        self.assertEqual(stored_ticket.status, Ticket.Status.CLOSED)

    def test_missing_ticket_returns_404(self):
        self.authenticate(self.admin_user)

        response = self.client.post(
            reverse("tickets:close", args=[999999]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_failure_does_not_partially_update_ticket(self):
        original_status = self.processing_ticket.status
        original_updated_at = self.processing_ticket.updated_at
        self.authenticate(self.handler)

        response = self.close_ticket(self.processing_ticket)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.processing_ticket.refresh_from_db()
        self.assertEqual(self.processing_ticket.status, original_status)
        self.assertEqual(
            self.processing_ticket.updated_at,
            original_updated_at,
        )


class TicketCloseConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.department = Department.objects.create(name="关闭并发测试部门")
        self.admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )
        self.admin_user = User.objects.create_user(
            username="close_concurrent_admin",
            email="close_concurrent_admin@example.com",
            password="TaskFlow#2026",
        )
        self.admin_user.profile.department = self.department
        self.admin_user.profile.save(update_fields=["department"])
        UserRole.objects.create(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        )
        self.creator = User.objects.create_user(
            username="close_concurrent_creator",
            email="close_concurrent_creator@example.com",
            password="TaskFlow#2026",
        )
        self.creator.profile.department = self.department
        self.creator.profile.save(update_fields=["department"])
        self.ticket = Ticket.objects.create(
            title="并发关闭工单",
            description="并发关闭测试",
            department=self.department,
            creator=self.creator,
            status=Ticket.Status.RESOLVED,
        )
        self.url = reverse("tickets:close", args=[self.ticket.pk])
        self.access_token = str(AccessToken.for_user(self.admin_user))

    def test_concurrent_requests_cannot_both_close_ticket(self):
        barrier = Barrier(2)

        def send_request():
            close_old_connections()
            client = APIClient()
            client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
            )
            barrier.wait()
            response = client.post(
                self.url,
                {},
                format="json",
            )
            close_old_connections()
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _: send_request(),
                range(2),
            ))

        self.assertEqual(
            sorted(results),
            [
                status.HTTP_200_OK,
                status.HTTP_409_CONFLICT,
            ],
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.CLOSED)
