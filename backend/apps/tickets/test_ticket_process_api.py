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


class TicketProcessAPITests(APITestCase):
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
        self.grant_process_permission(
            self.manager_role,
            RolePermissionScope.DEPARTMENT,
        )
        self.grant_process_permission(
            self.handler_role,
            RolePermissionScope.SELF,
        )

        self.admin_user = self.create_user(
            "process_admin",
            self.department_a,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "process_manager",
            self.department_a,
            [self.manager_role],
        )
        self.employee_user = self.create_user(
            "process_employee",
            self.department_a,
            [self.employee_role],
        )
        self.staff_user = User.objects.create_user(
            username="process_staff",
            email="process_staff@example.com",
            password="TaskFlow#2026",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="process_superuser",
            email="process_superuser@example.com",
            password="TaskFlow#2026",
        )
        self.colleague = self.create_user(
            "process_colleague",
            self.department_a,
            [self.employee_role],
        )
        self.handler = self.create_user(
            "process_handler",
            self.department_b,
            [self.handler_role],
        )
        self.second_handler = self.create_user(
            "process_handler_second",
            self.department_a,
            [self.handler_role],
        )
        self.multi_role_user = self.create_user(
            "process_multi_role",
            self.department_a,
            [self.manager_role, self.handler_role],
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
            Ticket.Priority.HIGH,
            self.department_a,
            assignee=self.handler,
        )
        self.other_department_ticket = self.create_ticket(
            "其他部门工单",
            Ticket.Status.PENDING,
            Ticket.Priority.LOW,
            self.department_b,
            assignee=self.second_handler,
        )
        self.resolved_ticket = self.create_ticket(
            "已解决工单",
            Ticket.Status.RESOLVED,
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

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_process_permission(self, role, scope):
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="process_ticket",
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

    def process_url(self, ticket):
        return reverse("tickets:process", args=[ticket.pk])

    def patch_status(self, ticket, target_status):
        return self.client.patch(
            self.process_url(ticket),
            {"status": target_status},
            format="json",
        )

    def test_anonymous_request_returns_401(self):
        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_process_permission_returns_403(self):
        self.authenticate(self.employee_user)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_process_any_department(self):
        self.authenticate(self.admin_user)

        response = self.patch_status(
            self.other_department_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.other_department_ticket.refresh_from_db()
        self.assertEqual(
            self.other_department_ticket.status,
            Ticket.Status.PROCESSING,
        )

    def test_department_manager_can_process_own_department(self):
        self.authenticate(self.manager_user)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.status,
            Ticket.Status.PROCESSING,
        )

    def test_department_manager_cannot_process_other_department(self):
        self.authenticate(self.manager_user)

        response = self.patch_status(
            self.other_department_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ticket_handler_can_process_assigned_ticket(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.status,
            Ticket.Status.PROCESSING,
        )

    def test_ticket_handler_cannot_process_other_assignee_ticket(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.other_department_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ticket_handler_creator_is_not_enough_without_assignment(self):
        creator_ticket = self.create_ticket(
            "创建人未分给自己的工单",
            Ticket.Status.PENDING,
            Ticket.Priority.MEDIUM,
            self.department_b,
            assignee=self.second_handler,
            creator=self.handler,
        )
        self.authenticate(self.handler)

        response = self.patch_status(
            creator_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        creator_ticket.refresh_from_db()
        self.assertEqual(creator_ticket.status, Ticket.Status.PENDING)

    def test_multi_role_user_gets_role_permission_union(self):
        self.pending_ticket.assignee = self.second_handler
        self.pending_ticket.save(update_fields=["assignee"])
        self.authenticate(self.multi_role_user)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.status,
            Ticket.Status.PROCESSING,
        )

    def test_staff_is_not_business_admin(self):
        self.authenticate(self.staff_user)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_is_not_business_admin(self):
        self.authenticate(self.superuser)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_process_ticket(self):
        self.authenticate(self.employee_user)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pending_to_processing_succeeds(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.status,
            Ticket.Status.PROCESSING,
        )

    def test_processing_to_resolved_succeeds(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.processing_ticket,
            Ticket.Status.RESOLVED,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.processing_ticket.refresh_from_db()
        self.assertEqual(
            self.processing_ticket.status,
            Ticket.Status.RESOLVED,
        )

    def test_pending_to_resolved_returns_409(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.RESOLVED,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.status,
            Ticket.Status.PENDING,
        )

    def test_pending_to_closed_is_rejected(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.CLOSED,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_processing_to_closed_is_rejected(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.processing_ticket,
            Ticket.Status.CLOSED,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resolved_to_processing_returns_409(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.resolved_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_closed_to_processing_returns_409(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.closed_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_resolved_ticket_cannot_be_resolved_again(self):
        self.authenticate(self.admin_user)

        response = self.patch_status(
            self.resolved_ticket,
            Ticket.Status.RESOLVED,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_invalid_transition_does_not_change_database(self):
        before_status = self.pending_ticket.status
        self.authenticate(self.handler)

        self.patch_status(
            self.pending_ticket,
            Ticket.Status.RESOLVED,
        )

        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.status, before_status)

    def test_processing_does_not_change_assignee(self):
        original_assignee_id = self.pending_ticket.assignee_id
        self.authenticate(self.handler)

        self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.assignee_id,
            original_assignee_id,
        )

    def test_processing_does_not_change_creator(self):
        original_creator_id = self.pending_ticket.creator_id
        self.authenticate(self.handler)

        self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.creator_id,
            original_creator_id,
        )

    def test_processing_does_not_change_department(self):
        original_department_id = self.pending_ticket.department_id
        self.authenticate(self.handler)

        self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.department_id,
            original_department_id,
        )

    def test_processing_does_not_change_priority(self):
        original_priority = self.pending_ticket.priority
        self.authenticate(self.handler)

        self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.priority,
            original_priority,
        )

    def test_unknown_field_returns_400(self):
        self.authenticate(self.handler)

        response = self.client.patch(
            self.process_url(self.pending_ticket),
            {
                "status": Ticket.Status.PROCESSING,
                "priority": Ticket.Priority.URGENT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("priority", response.data)

    def test_other_ticket_fields_cannot_be_modified(self):
        self.authenticate(self.handler)

        response = self.client.patch(
            self.process_url(self.pending_ticket),
            {
                "status": Ticket.Status.PROCESSING,
                "assignee": self.second_handler.pk,
                "department": self.department_b.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assignee", response.data)
        self.assertIn("department", response.data)

    def test_scope_parameters_cannot_be_forged(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            (
                f"{self.process_url(self.other_department_ticket)}"
                f"?user_id={self.admin_user.pk}"
                f"&department_id={self.department_b.pk}"
            ),
            {"status": Ticket.Status.PROCESSING},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_success_response_uses_ticket_read_structure(self):
        self.authenticate(self.handler)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

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
        self.assertEqual(
            response.data["status"],
            Ticket.Status.PROCESSING,
        )

    def test_updated_at_is_updated(self):
        old_updated_at = timezone.now() - timedelta(days=1)
        Ticket.objects.filter(pk=self.pending_ticket.pk).update(
            updated_at=old_updated_at
        )
        self.authenticate(self.handler)

        response = self.patch_status(
            self.pending_ticket,
            Ticket.Status.PROCESSING,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertGreater(
            self.pending_ticket.updated_at,
            old_updated_at,
        )

    def test_missing_ticket_returns_404(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            reverse("tickets:process", args=[999999]),
            {"status": Ticket.Status.PROCESSING},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_failure_does_not_partially_update_ticket(self):
        self.processing_ticket.assignee = self.handler
        self.processing_ticket.save(update_fields=["assignee"])
        self.authenticate(self.handler)

        response = self.patch_status(
            self.processing_ticket,
            Ticket.Status.CLOSED,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.processing_ticket.refresh_from_db()
        self.assertEqual(
            self.processing_ticket.status,
            Ticket.Status.PROCESSING,
        )


class TicketProcessConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.department = Department.objects.create(name="并发测试部门")
        self.admin_role = Role.objects.create(
            name="系统管理员",
            code="admin",
        )
        self.admin_user = User.objects.create_user(
            username="process_concurrent_admin",
            email="process_concurrent_admin@example.com",
            password="TaskFlow#2026",
        )
        self.admin_user.profile.department = self.department
        self.admin_user.profile.save(update_fields=["department"])
        UserRole.objects.create(
            user_profile=self.admin_user.profile,
            role=self.admin_role,
        )
        self.creator = User.objects.create_user(
            username="process_concurrent_creator",
            email="process_concurrent_creator@example.com",
            password="TaskFlow#2026",
        )
        self.creator.profile.department = self.department
        self.creator.profile.save(update_fields=["department"])
        self.ticket = Ticket.objects.create(
            title="并发处理工单",
            description="并发处理测试",
            department=self.department,
            creator=self.creator,
            status=Ticket.Status.PENDING,
        )
        self.url = reverse("tickets:process", args=[self.ticket.pk])
        self.access_token = str(AccessToken.for_user(self.admin_user))

    def test_concurrent_requests_cannot_both_apply_transition(self):
        barrier = Barrier(2)

        def send_request():
            close_old_connections()
            client = APIClient()
            client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
            )
            barrier.wait()
            response = client.patch(
                self.url,
                {"status": Ticket.Status.PROCESSING},
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
        self.assertEqual(
            self.ticket.status,
            Ticket.Status.PROCESSING,
        )
