from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.db.models import QuerySet
from django.test import TestCase

from apps.departments.models import Department
from apps.users.models import Role, RolePermission, RolePermissionScope, UserRole

from .models import Ticket
from .services.ticket_scope import get_ticket_queryset_for_permission

User = get_user_model()


class TicketScopeTests(TestCase):
    def setUp(self):
        self.department_a = Department.objects.create(
            name="工单部门 A",
            description="Scope 测试 A",
        )
        self.department_b = Department.objects.create(
            name="工单部门 B",
            description="Scope 测试 B",
        )
        self.creator = self.create_user(
            "scope_creator",
            self.department_a,
        )
        self.assignee = self.create_user(
            "scope_assignee",
            self.department_b,
        )
        self.colleague = self.create_user(
            "scope_colleague",
            self.department_a,
        )
        self.outsider = self.create_user(
            "scope_outsider",
            self.department_b,
        )

    def create_user(self, username, department=None):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="TaskFlow#2026",
        )
        if department is not None:
            profile = user.profile
            profile.department = department
            profile.save(update_fields=["department"])
        return user

    def create_ticket(
        self,
        title,
        *,
        department,
        creator,
        assignee=None,
    ):
        return Ticket.objects.create(
            title=title,
            description=f"{title} 描述",
            department=department,
            creator=creator,
            assignee=assignee,
        )

    def grant_permission(
        self,
        user,
        *,
        role_code,
        permission_codename,
        scope,
    ):
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": f"角色 {role_code}"},
        )
        permission = Permission.objects.get(
            content_type__app_label="tickets",
            codename=permission_codename,
        )
        RolePermission.objects.get_or_create(
            role=role,
            permission=permission,
            defaults={"scope": scope},
        )
        UserRole.objects.get_or_create(
            user_profile=user.profile,
            role=role,
        )
        return role

    def visible_ids(self, user, permission_key="tickets.view_ticket"):
        return set(
            get_ticket_queryset_for_permission(
                user,
                permission_key,
            ).values_list("id", flat=True)
        )

    def test_creator_can_query_own_ticket_in_self_scope(self):
        own_ticket = self.create_ticket(
            "创建人的工单",
            department=self.department_a,
            creator=self.creator,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_self_creator",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )

        self.assertEqual(
            self.visible_ids(self.creator),
            {own_ticket.pk},
        )

    def test_assignee_can_query_assigned_ticket_in_self_scope(self):
        assigned_ticket = self.create_ticket(
            "分配给处理人的工单",
            department=self.department_a,
            creator=self.colleague,
            assignee=self.assignee,
        )
        self.grant_permission(
            self.assignee,
            role_code="scope_self_assignee",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )

        self.assertEqual(
            self.visible_ids(self.assignee),
            {assigned_ticket.pk},
        )

    def test_unrelated_user_cannot_query_ticket_in_self_scope(self):
        self.create_ticket(
            "其他人的工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.outsider,
            role_code="scope_self_outsider",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )

        self.assertEqual(self.visible_ids(self.outsider), set())

    def test_null_assignee_is_safe_for_self_scope(self):
        own_ticket = self.create_ticket(
            "无处理人工单",
            department=self.department_a,
            creator=self.creator,
            assignee=None,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_self_null_assignee",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )

        self.assertEqual(
            self.visible_ids(self.creator),
            {own_ticket.pk},
        )

    def test_creator_and_assignee_do_not_duplicate_ticket(self):
        ticket = self.create_ticket(
            "创建人兼处理人",
            department=self.department_a,
            creator=self.creator,
            assignee=self.creator,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_self_both",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )

        ids = list(
            get_ticket_queryset_for_permission(
                self.creator,
                "tickets.view_ticket",
            ).values_list("id", flat=True)
        )

        self.assertEqual(ids, [ticket.pk])

    def test_department_scope_returns_only_current_department(self):
        department_ticket = self.create_ticket(
            "A 部门工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.create_ticket(
            "B 部门工单",
            department=self.department_b,
            creator=self.outsider,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_department_a",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )

        self.assertEqual(
            self.visible_ids(self.creator),
            {department_ticket.pk},
        )

    def test_department_scope_does_not_leak_other_departments(self):
        self.create_ticket(
            "B 部门机密工单",
            department=self.department_b,
            creator=self.outsider,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_department_no_leak",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )

        self.assertEqual(self.visible_ids(self.creator), set())

    def test_creator_department_change_keeps_ticket_department_filter(self):
        historical_ticket = self.create_ticket(
            "历史 A 部门工单",
            department=self.department_a,
            creator=self.creator,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_department_history",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )
        profile = self.creator.profile
        profile.department = self.department_b
        profile.save(update_fields=["department"])

        self.assertEqual(self.visible_ids(self.creator), set())
        historical_ticket.refresh_from_db()
        self.assertEqual(
            historical_ticket.department_id,
            self.department_a.pk,
        )

    def test_cross_department_assignee_does_not_move_ticket(self):
        ticket = self.create_ticket(
            "跨部门处理工单",
            department=self.department_a,
            creator=self.colleague,
            assignee=self.assignee,
        )
        self.grant_permission(
            self.assignee,
            role_code="scope_cross_dept_assignee",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )

        self.assertEqual(self.visible_ids(self.assignee), set())
        self.assertEqual(ticket.department_id, self.department_a.pk)

    def test_user_without_profile_gets_empty_queryset(self):
        self.create_ticket(
            "有部门工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_no_profile",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )
        self.creator.profile.delete()

        self.assertEqual(self.visible_ids(self.creator), set())

    def test_department_scope_is_denied_without_department(self):
        self.create_ticket(
            "有部门工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_no_department",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )
        profile = self.creator.profile
        profile.department = None
        profile.save(update_fields=["department"])

        self.assertEqual(self.visible_ids(self.creator), set())

    def test_self_scope_works_without_department(self):
        own_ticket = self.create_ticket(
            "无部门用户的工单",
            department=self.department_a,
            creator=self.creator,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_self_without_department",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )
        profile = self.creator.profile
        profile.department = None
        profile.save(update_fields=["department"])

        self.assertEqual(
            self.visible_ids(self.creator),
            {own_ticket.pk},
        )

    def test_self_and_department_scopes_form_union(self):
        own_ticket = self.create_ticket(
            "本人 A 部门工单",
            department=self.department_a,
            creator=self.creator,
        )
        department_ticket = self.create_ticket(
            "同部门其他工单",
            department=self.department_a,
            creator=self.colleague,
        )
        other_department_ticket = self.create_ticket(
            "本人身份但 B 部门工单",
            department=self.department_b,
            creator=self.creator,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_union_self",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_union_department",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )

        self.assertEqual(
            self.visible_ids(self.creator),
            {
                own_ticket.pk,
                department_ticket.pk,
                other_department_ticket.pk,
            },
        )

    def test_all_scope_returns_every_ticket(self):
        ticket_a = self.create_ticket(
            "A 部门全部工单",
            department=self.department_a,
            creator=self.colleague,
        )
        ticket_b = self.create_ticket(
            "B 部门全部工单",
            department=self.department_b,
            creator=self.outsider,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_all",
            permission_codename="view_ticket",
            scope=RolePermissionScope.ALL,
        )

        self.assertEqual(
            self.visible_ids(self.creator),
            {ticket_a.pk, ticket_b.pk},
        )

    def test_all_and_self_scope_keeps_all_semantics(self):
        ticket_a = self.create_ticket(
            "A 部门工单",
            department=self.department_a,
            creator=self.colleague,
        )
        ticket_b = self.create_ticket(
            "B 部门工单",
            department=self.department_b,
            creator=self.outsider,
        )
        role = self.grant_permission(
            self.creator,
            role_code="scope_all_and_self_all",
            permission_codename="view_ticket",
            scope=RolePermissionScope.ALL,
        )
        second_role = Role.objects.create(
            name="Scope ALL Self 第二角色",
            code="scope_all_and_self_second",
        )
        RolePermission.objects.create(
            role=second_role,
            permission=Permission.objects.get(
                content_type__app_label="tickets",
                codename="view_ticket",
            ),
            scope=RolePermissionScope.SELF,
        )
        UserRole.objects.create(
            user_profile=self.creator.profile,
            role=second_role,
        )

        self.assertEqual(
            self.visible_ids(self.creator),
            {ticket_a.pk, ticket_b.pk},
        )
        self.assertNotEqual(role, second_role)

    def test_all_for_one_permission_does_not_grant_another(self):
        self.create_ticket(
            "全部可见工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_all_view_only",
            permission_codename="view_ticket",
            scope=RolePermissionScope.ALL,
        )

        self.assertNotEqual(
            self.visible_ids(self.creator, "tickets.view_ticket"),
            set(),
        )
        self.assertEqual(
            self.visible_ids(self.creator, "tickets.close_ticket"),
            set(),
        )

    def test_scopes_for_different_permissions_do_not_pollute(self):
        own_ticket = self.create_ticket(
            "本人查看工单",
            department=self.department_a,
            creator=self.creator,
        )
        other_ticket = self.create_ticket(
            "全部门处理工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_view_self",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_process_department",
            permission_codename="process_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )

        self.assertEqual(
            self.visible_ids(self.creator, "tickets.view_ticket"),
            {own_ticket.pk},
        )
        self.assertEqual(
            self.visible_ids(self.creator, "tickets.process_ticket"),
            {own_ticket.pk, other_ticket.pk},
        )

    def test_anonymous_user_gets_empty_queryset(self):
        self.create_ticket(
            "匿名用户不可见工单",
            department=self.department_a,
            creator=self.colleague,
        )

        self.assertEqual(
            self.visible_ids(AnonymousUser(), "tickets.view_ticket"),
            set(),
        )

    def test_forged_user_id_is_not_accepted(self):
        with self.assertRaises(TypeError):
            get_ticket_queryset_for_permission(
                self.creator,
                "tickets.view_ticket",
                user_id=self.outsider.pk,
            )

    def test_forged_department_id_is_not_accepted(self):
        with self.assertRaises(TypeError):
            get_ticket_queryset_for_permission(
                self.creator,
                "tickets.view_ticket",
                department_id=self.department_b.pk,
            )

    def test_unregistered_permission_gets_empty_queryset(self):
        self.create_ticket(
            "不可越权工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_registered_only",
            permission_codename="view_ticket",
            scope=RolePermissionScope.ALL,
        )

        self.assertEqual(
            self.visible_ids(self.creator, "tickets.unknown_permission"),
            set(),
        )
        self.assertEqual(
            self.visible_ids(
                self.creator,
                "departments.view_department",
            ),
            set(),
        )

    def test_missing_permission_gets_empty_queryset(self):
        self.create_ticket(
            "无权限工单",
            department=self.department_a,
            creator=self.colleague,
        )

        self.assertEqual(
            self.visible_ids(self.creator, "tickets.view_ticket"),
            set(),
        )

    def test_empty_ticket_database_returns_empty_queryset(self):
        self.grant_permission(
            self.creator,
            role_code="scope_empty_database",
            permission_codename="view_ticket",
            scope=RolePermissionScope.ALL,
        )

        queryset = get_ticket_queryset_for_permission(
            self.creator,
            "tickets.view_ticket",
        )

        self.assertEqual(list(queryset), [])

    def test_different_users_have_isolated_self_results(self):
        creator_ticket = self.create_ticket(
            "创建人自己的工单",
            department=self.department_a,
            creator=self.creator,
        )
        colleague_ticket = self.create_ticket(
            "同事自己的工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_self_creator_isolated",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )
        self.grant_permission(
            self.colleague,
            role_code="scope_self_colleague_isolated",
            permission_codename="view_ticket",
            scope=RolePermissionScope.SELF,
        )

        self.assertEqual(
            self.visible_ids(self.creator),
            {creator_ticket.pk},
        )
        self.assertEqual(
            self.visible_ids(self.colleague),
            {colleague_ticket.pk},
        )

    def test_service_returns_queryset(self):
        queryset = get_ticket_queryset_for_permission(
            self.creator,
            "tickets.view_ticket",
        )

        self.assertIsInstance(queryset, QuerySet)

    def test_queryset_supports_additional_filter_and_ordering(self):
        first_ticket = self.create_ticket(
            "Z 工单",
            department=self.department_a,
            creator=self.colleague,
        )
        second_ticket = self.create_ticket(
            "A 工单",
            department=self.department_a,
            creator=self.colleague,
        )
        self.grant_permission(
            self.creator,
            role_code="scope_queryset_chain",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )

        queryset = get_ticket_queryset_for_permission(
            self.creator,
            "tickets.view_ticket",
        ).filter(title__endswith="工单").order_by("title")

        self.assertEqual(
            list(queryset.values_list("id", flat=True)),
            [second_ticket.pk, first_ticket.pk],
        )

    def test_queries_do_not_duplicate_per_role_or_permission(self):
        ticket = self.create_ticket(
            "查询次数工单",
            department=self.department_a,
            creator=self.colleague,
        )
        role = self.grant_permission(
            self.creator,
            role_code="scope_query_count",
            permission_codename="view_ticket",
            scope=RolePermissionScope.DEPARTMENT,
        )
        extra_roles = [
            Role.objects.create(
                name=f"查询次数角色 {index}",
                code=f"scope_query_count_{index}",
            )
            for index in range(1, 4)
        ]
        for extra_role in extra_roles:
            RolePermission.objects.create(
                role=extra_role,
                permission=Permission.objects.get(
                    content_type__app_label="tickets",
                    codename="view_ticket",
                ),
                scope=RolePermissionScope.DEPARTMENT,
            )
            UserRole.objects.create(
                user_profile=self.creator.profile,
                role=extra_role,
            )

        with self.assertNumQueries(4):
            ids = list(
                get_ticket_queryset_for_permission(
                    self.creator,
                    "tickets.view_ticket",
                ).values_list("id", flat=True)
            )

        self.assertEqual(ids, [ticket.pk])
        self.assertEqual(role.code, "scope_query_count")
