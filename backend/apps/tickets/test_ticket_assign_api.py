from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.departments.models import Department
from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

from .models import Ticket

User = get_user_model()


class TicketAssignAPITests(APITestCase):
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
        self.grant_assign_permission(
            self.manager_role,
            RolePermissionScope.DEPARTMENT,
        )

        self.admin_user = self.create_user(
            "assign_admin",
            self.department_a,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "assign_manager",
            self.department_a,
            [self.manager_role],
        )
        self.manager_without_department = self.create_user(
            "assign_manager_no_dept",
            None,
            [self.manager_role],
        )
        self.employee_user = self.create_user(
            "assign_employee",
            self.department_a,
            [self.employee_role],
        )
        self.staff_user = User.objects.create_user(
            username="assign_staff",
            email="assign_staff@example.com",
            password="TaskFlow#2026",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="assign_superuser",
            email="assign_superuser@example.com",
            password="TaskFlow#2026",
        )
        self.colleague = self.create_user(
            "assign_colleague",
            self.department_a,
            [self.employee_role],
        )
        self.handler = self.create_user(
            "assign_handler",
            self.department_b,
            [self.handler_role],
        )
        self.second_handler = self.create_user(
            "assign_handler_second",
            self.department_a,
            [self.handler_role],
        )
        self.employee_assignee = self.create_user(
            "assign_employee_assignee",
            self.department_a,
            [self.employee_role],
        )
        self.inactive_handler = self.create_user(
            "assign_handler_inactive",
            self.department_a,
            [self.handler_role],
        )
        self.inactive_handler.is_active = False
        self.inactive_handler.save(update_fields=["is_active"])
        self.multi_role_handler = self.create_user(
            "assign_handler_multi",
            self.department_a,
            [self.employee_role, self.handler_role],
        )
        self.user_without_profile = self.create_user(
            "assign_handler_no_profile",
            self.department_a,
            [self.handler_role],
        )
        self.user_without_profile.profile.delete()

        self.pending_ticket = self.create_ticket(
            "待分配工单",
            Ticket.Status.PENDING,
            Ticket.Priority.MEDIUM,
            self.department_a,
        )
        self.processing_ticket = self.create_ticket(
            "处理中工单",
            Ticket.Status.PROCESSING,
            Ticket.Priority.HIGH,
            self.department_a,
        )
        self.other_department_ticket = self.create_ticket(
            "其他部门工单",
            Ticket.Status.PENDING,
            Ticket.Priority.LOW,
            self.department_b,
        )
        self.resolved_ticket = self.create_ticket(
            "已解决工单",
            Ticket.Status.RESOLVED,
            Ticket.Priority.MEDIUM,
            self.department_a,
        )
        self.closed_ticket = self.create_ticket(
            "已关闭工单",
            Ticket.Status.CLOSED,
            Ticket.Priority.MEDIUM,
            self.department_a,
        )

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_assign_permission(self, role, scope):
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="assign_ticket",
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

    def create_ticket(self, title, ticket_status, priority, department):
        return Ticket.objects.create(
            title=title,
            description=f"{title} 描述",
            department=department,
            creator=self.colleague,
            status=ticket_status,
            priority=priority,
        )

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def assign_url(self, ticket):
        return reverse("tickets:assign", args=[ticket.pk])

    def patch_assignment(self, ticket, assignee):
        return self.client.patch(
            self.assign_url(ticket),
            {
                "assignee_id": (
                    assignee.pk
                    if assignee is not None
                    else None
                )
            },
            format="json",
        )

    def assert_assignment_unchanged(self, ticket):
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assignee_id)

    def test_anonymous_request_returns_401(self):
        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_assign_permission_returns_403(self):
        self.authenticate(self.employee_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_assign_ticket(self):
        self.authenticate(self.admin_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.assignee, self.handler)

    def test_department_manager_can_assign_own_department_ticket(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.assignee, self.handler)

    def test_department_manager_cannot_assign_other_department_ticket(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.other_department_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_assignment_unchanged(self.other_department_ticket)

    def test_manager_without_department_gets_empty_scope(self):
        self.authenticate(self.manager_without_department)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_staff_cannot_assign_without_business_permission(self):
        self.authenticate(self.staff_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_cannot_assign_without_business_permission(self):
        self.authenticate(self.superuser)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_cannot_assign_ticket(self):
        self.authenticate(self.employee_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_active_ticket_handler_can_be_assigned(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["assignee"]["id"],
            self.handler.pk,
        )

    def test_nonexistent_assignee_returns_400(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            self.assign_url(self.pending_ticket),
            {"assignee_id": 999999},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_active_employee_cannot_be_assigned(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.employee_assignee,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ticket_handler", response.data["message"])
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_inactive_ticket_handler_cannot_be_assigned(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.inactive_handler,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("未启用", response.data["message"])
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_assignee_without_profile_cannot_be_assigned(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.user_without_profile,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("UserProfile", response.data["message"])
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_multi_role_user_with_handler_role_can_be_assigned(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.multi_role_handler,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.assignee,
            self.multi_role_handler,
        )

    def test_cross_department_assignment_keeps_ticket_department(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.assignee, self.handler)
        self.assertEqual(
            self.pending_ticket.department_id,
            self.department_a.pk,
        )

    def test_creator_cannot_be_changed_by_request(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            self.assign_url(self.pending_ticket),
            {
                "assignee_id": self.handler.pk,
                "creator": self.admin_user.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("creator", response.data)
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_department_cannot_be_changed_by_request(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            self.assign_url(self.pending_ticket),
            {
                "assignee_id": self.handler.pk,
                "department": self.department_b.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", response.data)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.department_id,
            self.department_a.pk,
        )

    def test_unassigned_ticket_can_be_assigned(self):
        self.assertIsNone(self.pending_ticket.assignee_id)
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.assignee, self.handler)

    def test_assigned_ticket_can_be_reassigned(self):
        self.pending_ticket.assignee = self.second_handler
        self.pending_ticket.save(update_fields=["assignee"])
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.assignee, self.handler)

    def test_assignment_can_be_cancelled_with_null(self):
        self.pending_ticket.assignee = self.handler
        self.pending_ticket.save(update_fields=["assignee"])
        self.authenticate(self.manager_user)

        response = self.patch_assignment(self.pending_ticket, None)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertIsNone(self.pending_ticket.assignee)

    def test_cancelling_assignment_keeps_ticket(self):
        self.pending_ticket.assignee = self.handler
        self.pending_ticket.save(update_fields=["assignee"])
        self.authenticate(self.manager_user)

        self.patch_assignment(self.pending_ticket, None)

        self.assertTrue(
            Ticket.objects.filter(pk=self.pending_ticket.pk).exists()
        )

    def test_assignment_does_not_change_status(self):
        original_status = self.pending_ticket.status
        self.authenticate(self.manager_user)

        self.patch_assignment(self.pending_ticket, self.handler)

        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.status, original_status)

    def test_assignment_does_not_change_priority(self):
        original_priority = self.pending_ticket.priority
        self.authenticate(self.manager_user)

        self.patch_assignment(self.pending_ticket, self.handler)

        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.priority, original_priority)

    def test_assignment_does_not_change_department(self):
        original_department_id = self.pending_ticket.department_id
        self.authenticate(self.manager_user)

        self.patch_assignment(self.pending_ticket, self.handler)

        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.department_id,
            original_department_id,
        )

    def test_assignment_does_not_change_creator(self):
        original_creator_id = self.pending_ticket.creator_id
        self.authenticate(self.manager_user)

        self.patch_assignment(self.pending_ticket, self.handler)

        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.creator_id,
            original_creator_id,
        )

    def test_out_of_scope_ticket_returns_404(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.other_department_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_assignment_unchanged(self.other_department_ticket)

    def test_missing_ticket_returns_404(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            reverse("tickets:assign", args=[999999]),
            {"assignee_id": self.handler.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_forged_scope_parameters_do_not_change_scope(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            (
                f"{self.assign_url(self.other_department_ticket)}"
                f"?user_id={self.admin_user.pk}"
                f"&department_id={self.department_b.pk}"
            ),
            {"assignee_id": self.handler.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_assignment_unchanged(self.other_department_ticket)

    def test_unknown_field_returns_400(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            self.assign_url(self.pending_ticket),
            {
                "assignee_id": self.handler.pk,
                "status": Ticket.Status.CLOSED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_missing_assignee_id_returns_400(self):
        self.authenticate(self.manager_user)

        response = self.client.patch(
            self.assign_url(self.pending_ticket),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assignee_id", response.data)
        self.assert_assignment_unchanged(self.pending_ticket)

    def test_pending_ticket_can_be_assigned_and_cancelled(self):
        self.authenticate(self.manager_user)

        assigned_response = self.patch_assignment(
            self.pending_ticket,
            self.handler,
        )
        cancelled_response = self.patch_assignment(
            self.pending_ticket,
            None,
        )

        self.assertEqual(assigned_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancelled_response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertIsNone(self.pending_ticket.assignee)

    def test_processing_ticket_can_be_reassigned_and_cancelled(self):
        self.processing_ticket.assignee = self.handler
        self.processing_ticket.save(update_fields=["assignee"])
        self.authenticate(self.manager_user)

        reassigned_response = self.patch_assignment(
            self.processing_ticket,
            self.second_handler,
        )
        cancelled_response = self.patch_assignment(
            self.processing_ticket,
            None,
        )

        self.assertEqual(reassigned_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancelled_response.status_code, status.HTTP_200_OK)
        self.processing_ticket.refresh_from_db()
        self.assertIsNone(self.processing_ticket.assignee)

    def test_resolved_ticket_cannot_be_assigned(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.resolved_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assert_assignment_unchanged(self.resolved_ticket)

    def test_resolved_ticket_cannot_cancel_assignment(self):
        self.resolved_ticket.assignee = self.handler
        self.resolved_ticket.save(update_fields=["assignee"])
        self.authenticate(self.manager_user)

        response = self.patch_assignment(self.resolved_ticket, None)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.resolved_ticket.refresh_from_db()
        self.assertEqual(self.resolved_ticket.assignee, self.handler)

    def test_closed_ticket_cannot_be_assigned(self):
        self.authenticate(self.manager_user)

        response = self.patch_assignment(
            self.closed_ticket,
            self.handler,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assert_assignment_unchanged(self.closed_ticket)

    def test_closed_ticket_cannot_cancel_assignment(self):
        self.closed_ticket.assignee = self.handler
        self.closed_ticket.save(update_fields=["assignee"])
        self.authenticate(self.manager_user)

        response = self.patch_assignment(self.closed_ticket, None)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.closed_ticket.refresh_from_db()
        self.assertEqual(self.closed_ticket.assignee, self.handler)
