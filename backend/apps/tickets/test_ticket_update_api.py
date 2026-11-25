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


class TicketUpdateAPITests(APITestCase):
    def setUp(self):
        self.department_a = Department.objects.create(name="研发部")
        self.department_b = Department.objects.create(name="市场部")
        self.category_a = TicketCategory.objects.create(
            name="系统问题",
            description="系统故障",
        )
        self.category_b = TicketCategory.objects.create(
            name="网络问题",
            description="网络异常",
        )

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
        self.grant_change_permission(
            self.manager_role,
            RolePermissionScope.DEPARTMENT,
        )
        self.grant_change_permission(
            self.employee_role,
            RolePermissionScope.SELF,
        )
        # ticket_handler receives the Permission only to prove that the
        # object-level edit rule still rejects it.
        self.grant_change_permission(
            self.handler_role,
            RolePermissionScope.SELF,
        )

        self.admin_user = self.create_user(
            "update_admin",
            self.department_a,
            [self.admin_role],
        )
        self.manager_user = self.create_user(
            "update_manager",
            self.department_a,
            [self.manager_role],
        )
        self.employee_user = self.create_user(
            "update_employee",
            self.department_a,
            [self.employee_role],
        )
        self.colleague = self.create_user(
            "update_colleague",
            self.department_a,
            [self.employee_role],
        )
        self.other_department_employee = self.create_user(
            "update_other_department",
            self.department_b,
            [self.employee_role],
        )
        self.handler = self.create_user(
            "update_handler",
            self.department_a,
            [self.handler_role],
        )
        self.multi_role_user = self.create_user(
            "update_multi_role",
            self.department_a,
            [self.manager_role, self.employee_role],
        )
        self.staff_user = User.objects.create_user(
            username="update_staff",
            email="update_staff@example.com",
            password="TaskFlow#2026",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="update_superuser",
            email="update_superuser@example.com",
            password="TaskFlow#2026",
        )

        self.pending_ticket = self.create_ticket(
            "普通员工待处理工单",
            self.employee_user,
            self.department_a,
            Ticket.Status.PENDING,
            assignee=self.handler,
        )
        self.processing_ticket = self.create_ticket(
            "普通员工处理中工单",
            self.employee_user,
            self.department_a,
            Ticket.Status.PROCESSING,
        )
        self.resolved_ticket = self.create_ticket(
            "普通员工已解决工单",
            self.employee_user,
            self.department_a,
            Ticket.Status.RESOLVED,
        )
        self.closed_ticket = self.create_ticket(
            "普通员工已关闭工单",
            self.employee_user,
            self.department_a,
            Ticket.Status.CLOSED,
        )
        self.colleague_ticket = self.create_ticket(
            "同事创建的工单",
            self.colleague,
            self.department_a,
            Ticket.Status.PENDING,
        )
        self.other_department_ticket = self.create_ticket(
            "其他部门工单",
            self.other_department_employee,
            self.department_b,
            Ticket.Status.PENDING,
        )
        self.multi_role_processing_ticket = self.create_ticket(
            "多角色处理中工单",
            self.multi_role_user,
            self.department_b,
            Ticket.Status.PROCESSING,
        )

    def create_role(self, code, name):
        return Role.objects.create(name=name, code=code)

    def grant_change_permission(self, role, scope):
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename="change_ticket",
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
        creator,
        department,
        ticket_status,
        assignee=None,
    ):
        return Ticket.objects.create(
            title=title,
            description=f"{title} 描述",
            category=self.category_a,
            department=department,
            creator=creator,
            assignee=assignee,
            status=ticket_status,
            priority=Ticket.Priority.MEDIUM,
        )

    def authenticate(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}"
        )

    def detail_url(self, ticket):
        return reverse("tickets:detail", args=[ticket.pk])

    def patch_ticket(self, ticket, data):
        return self.client.patch(
            self.detail_url(ticket),
            data,
            format="json",
        )

    def test_anonymous_user_cannot_edit_ticket(self):
        response = self.patch_ticket(
            self.pending_ticket,
            {"title": "未授权修改"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_admin_can_edit_pending_ticket(self):
        self.authenticate(self.admin_user)

        response = self.patch_ticket(
            self.pending_ticket,
            {
                "title": "管理员修改标题",
                "description": "管理员修改描述",
                "category": self.category_b.pk,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.title, "管理员修改标题")
        self.assertEqual(
            self.pending_ticket.description,
            "管理员修改描述",
        )
        self.assertEqual(
            self.pending_ticket.category_id,
            self.category_b.pk,
        )
        self.assertEqual(
            response.data["title"],
            "管理员修改标题",
        )

    def test_admin_can_edit_processing_ticket(self):
        self.authenticate(self.admin_user)

        response = self.patch_ticket(
            self.processing_ticket,
            {"title": "处理中工单新标题"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_cannot_edit_resolved_or_closed_ticket(self):
        self.authenticate(self.admin_user)

        for ticket in (self.resolved_ticket, self.closed_ticket):
            response = self.patch_ticket(
                ticket,
                {"title": "不应保存"},
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_409_CONFLICT,
            )

    def test_manager_can_edit_own_department_ticket(self):
        self.authenticate(self.manager_user)

        response = self.patch_ticket(
            self.colleague_ticket,
            {"description": "部门负责人修改"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.colleague_ticket.refresh_from_db()
        self.assertEqual(
            self.colleague_ticket.description,
            "部门负责人修改",
        )

    def test_manager_cannot_edit_other_department_ticket(self):
        self.authenticate(self.manager_user)

        response = self.patch_ticket(
            self.other_department_ticket,
            {"title": "越权修改"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_manager_cannot_edit_resolved_own_department_ticket(self):
        self.authenticate(self.manager_user)

        response = self.patch_ticket(
            self.resolved_ticket,
            {"title": "不允许修改"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_employee_can_edit_own_pending_ticket(self):
        self.authenticate(self.employee_user)

        response = self.patch_ticket(
            self.pending_ticket,
            {"title": "员工修改自己的工单"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.title,
            "员工修改自己的工单",
        )

    def test_employee_cannot_edit_colleague_ticket(self):
        self.authenticate(self.employee_user)

        response = self.patch_ticket(
            self.colleague_ticket,
            {"title": "员工越权修改"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_cannot_edit_own_processing_ticket(self):
        self.authenticate(self.employee_user)

        response = self.patch_ticket(
            self.processing_ticket,
            {"title": "已开始后不允许修改"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_employee_branch_does_not_gain_manager_edit_scope(self):
        self.authenticate(self.multi_role_user)

        response = self.patch_ticket(
            self.multi_role_processing_ticket,
            {"title": "不应修改"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_ticket_handler_cannot_edit_even_with_permission(self):
        self.authenticate(self.handler)

        response = self.patch_ticket(
            self.pending_ticket,
            {"title": "处理人修改"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_staff_and_superuser_without_business_role_are_forbidden(self):
        for user in (self.staff_user, self.superuser):
            self.authenticate(user)
            response = self.patch_ticket(
                self.pending_ticket,
                {"title": "不应修改"},
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_403_FORBIDDEN,
            )

    def test_nonexistent_ticket_returns_404(self):
        self.authenticate(self.admin_user)

        response = self.client.patch(
            reverse("tickets:detail", args=[999999]),
            {"title": "不存在"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_invalid_category_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.patch_ticket(
            self.pending_ticket,
            {"category": 999999},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("category", response.data)

    def test_protected_fields_are_rejected_and_unchanged(self):
        self.authenticate(self.admin_user)
        original = {
            "creator_id": self.pending_ticket.creator_id,
            "department_id": self.pending_ticket.department_id,
            "assignee_id": self.pending_ticket.assignee_id,
            "status": self.pending_ticket.status,
            "priority": self.pending_ticket.priority,
        }

        response = self.patch_ticket(
            self.pending_ticket,
            {
                "title": "标题不应保存",
                "creator": self.manager_user.pk,
                "department": self.department_b.pk,
                "assignee": self.employee_user.pk,
                "status": Ticket.Status.CLOSED,
                "priority": Ticket.Priority.URGENT,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.title,
            "普通员工待处理工单",
        )
        self.assertEqual(
            {
                "creator_id": self.pending_ticket.creator_id,
                "department_id": self.pending_ticket.department_id,
                "assignee_id": self.pending_ticket.assignee_id,
                "status": self.pending_ticket.status,
                "priority": self.pending_ticket.priority,
            },
            original,
        )

    def test_partial_title_only_update_preserves_other_fields(self):
        self.authenticate(self.admin_user)
        original_description = self.pending_ticket.description
        original_category_id = self.pending_ticket.category_id

        response = self.patch_ticket(
            self.pending_ticket,
            {"title": "仅修改标题"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(self.pending_ticket.title, "仅修改标题")
        self.assertEqual(
            self.pending_ticket.description,
            original_description,
        )
        self.assertEqual(
            self.pending_ticket.category_id,
            original_category_id,
        )

    def test_partial_description_only_update_preserves_title(self):
        self.authenticate(self.admin_user)
        original_title = self.pending_ticket.title

        response = self.patch_ticket(
            self.pending_ticket,
            {"description": "仅修改描述"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.title,
            original_title,
        )
        self.assertEqual(
            self.pending_ticket.description,
            "仅修改描述",
        )

    def test_partial_category_only_update_accepts_null(self):
        self.authenticate(self.admin_user)

        response = self.patch_ticket(
            self.pending_ticket,
            {"category": None},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertIsNone(self.pending_ticket.category_id)

    def test_department_snapshot_does_not_follow_creator_department(self):
        original_department_id = self.pending_ticket.department_id
        profile = self.employee_user.profile
        profile.department = self.department_b
        profile.save(update_fields=["department"])
        self.authenticate(self.admin_user)

        response = self.patch_ticket(
            self.pending_ticket,
            {"title": "部门快照保持不变"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_ticket.refresh_from_db()
        self.assertEqual(
            self.pending_ticket.department_id,
            original_department_id,
        )

    def test_empty_payload_returns_400(self):
        self.authenticate(self.admin_user)

        response = self.patch_ticket(self.pending_ticket, {})

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("non_field_errors", response.data)

    def test_put_is_not_supported(self):
        self.authenticate(self.admin_user)

        response = self.client.put(
            self.detail_url(self.pending_ticket),
            {"title": "PUT"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
