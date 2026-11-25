from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import PROTECT
from django.db.models.deletion import ProtectedError
from django.db.models.signals import post_save
from django.test import TestCase

from apps.departments.models import Department

from .models import Ticket, TicketCategory
from .services.ticket_creation import (
    TicketCreatorDepartmentMissing,
    TicketCreatorProfileMissing,
    create_ticket,
)

User = get_user_model()


class TicketDepartmentTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="工单归属部门",
            description="Ticket 创建测试",
        )
        self.other_department = Department.objects.create(
            name="跨部门",
            description="处理人部门",
        )
        self.creator = User.objects.create_user(
            username="ticket_creator",
            email="ticket_creator@example.com",
            password="TaskFlow#2026",
        )
        self.creator.profile.department = self.department
        self.creator.profile.save(update_fields=["department"])
        self.assignee = User.objects.create_user(
            username="ticket_assignee",
            email="ticket_assignee@example.com",
            password="TaskFlow#2026",
        )
        self.assignee.profile.department = self.other_department
        self.assignee.profile.save(update_fields=["department"])
        self.category = TicketCategory.objects.create(
            name="系统问题",
            description="测试分类",
        )

    def create_for_creator(self, **overrides):
        data = {
            "creator": self.creator,
            "title": "测试工单",
            "description": "测试工单描述",
        }
        data.update(overrides)
        return create_ticket(**data)

    def test_department_foreign_key_configuration(self):
        field = Ticket._meta.get_field("department")

        self.assertEqual(field.remote_field.model, Department)
        self.assertEqual(field.remote_field.related_name, "tickets")
        self.assertEqual(field.remote_field.on_delete, PROTECT)
        self.assertFalse(field.null)

    def test_department_cannot_be_null(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Ticket.objects.create(
                    title="无部门工单",
                    description="数据库约束测试",
                    department=None,
                    creator=self.creator,
                )

    def test_department_with_tickets_is_protected(self):
        self.create_for_creator()

        with self.assertRaises(ProtectedError):
            self.department.delete()

        self.assertTrue(
            Department.objects.filter(pk=self.department.pk).exists()
        )

    def test_department_without_tickets_can_be_deleted(self):
        department = Department.objects.create(name="可删除部门")

        department.delete()

        self.assertFalse(
            Department.objects.filter(pk=department.pk).exists()
        )

    def test_service_preserves_existing_ticket_field_behavior(self):
        ticket = self.create_for_creator(
            category=self.category,
            assignee=self.assignee,
            status=Ticket.Status.PROCESSING,
            priority=Ticket.Priority.URGENT,
        )

        self.assertEqual(ticket.title, "测试工单")
        self.assertEqual(ticket.description, "测试工单描述")
        self.assertEqual(ticket.category, self.category)
        self.assertEqual(ticket.creator, self.creator)
        self.assertEqual(ticket.assignee, self.assignee)
        self.assertEqual(ticket.status, Ticket.Status.PROCESSING)
        self.assertEqual(ticket.priority, Ticket.Priority.URGENT)

    def test_service_reads_department_from_creator_profile(self):
        ticket = self.create_for_creator()

        self.assertEqual(ticket.department_id, self.department.pk)

    def test_service_persists_department(self):
        ticket = self.create_for_creator()
        stored_ticket = Ticket.objects.get(pk=ticket.pk)

        self.assertEqual(stored_ticket.department_id, self.department.pk)

    def test_creator_department_change_does_not_change_history(self):
        ticket = self.create_for_creator()
        profile = self.creator.profile
        profile.department = self.other_department
        profile.save(update_fields=["department"])
        ticket.refresh_from_db()

        self.assertEqual(ticket.department_id, self.department.pk)

    def test_cross_department_assignee_does_not_change_department(self):
        ticket = self.create_for_creator(assignee=self.assignee)

        self.assertNotEqual(
            self.assignee.profile.department_id,
            ticket.department_id,
        )
        self.assertEqual(ticket.department_id, self.department.pk)

    def test_missing_profile_rejects_creation(self):
        self.creator.profile.delete()

        with self.assertRaises(TicketCreatorProfileMissing):
            self.create_for_creator()

        self.assertEqual(Ticket.objects.count(), 0)

    def test_missing_creator_department_rejects_creation(self):
        profile = self.creator.profile
        profile.department = None
        profile.save(update_fields=["department"])

        with self.assertRaises(TicketCreatorDepartmentMissing):
            self.create_for_creator()

        self.assertEqual(Ticket.objects.count(), 0)

    def test_department_id_argument_is_rejected(self):
        with self.assertRaises(TypeError):
            self.create_for_creator(
                department_id=self.other_department.pk,
            )

        self.assertEqual(Ticket.objects.count(), 0)

    def test_failed_creation_leaves_no_ticket(self):
        profile = self.creator.profile
        profile.department = None
        profile.save(update_fields=["department"])

        with self.assertRaises(TicketCreatorDepartmentMissing):
            self.create_for_creator()

        self.assertFalse(
            Ticket.objects.filter(title="测试工单").exists()
        )

    def test_creation_rolls_back_when_ticket_creation_fails(self):
        def fail_after_ticket_save(sender, instance, **kwargs):
            raise RuntimeError("模拟工单保存后异常")

        post_save.connect(
            fail_after_ticket_save,
            sender=Ticket,
            weak=False,
            dispatch_uid="test_ticket_creation_rollback",
        )
        try:
            with self.assertRaisesMessage(
                RuntimeError,
                "模拟工单保存后异常",
            ):
                self.create_for_creator()
        finally:
            post_save.disconnect(
                sender=Ticket,
                dispatch_uid="test_ticket_creation_rollback",
            )

        self.assertEqual(Ticket.objects.count(), 0)

    def test_ticket_department_can_differ_from_creator_current_department(self):
        ticket = self.create_for_creator()
        profile = self.creator.profile
        profile.department = self.other_department
        profile.save(update_fields=["department"])
        ticket.refresh_from_db()

        self.assertNotEqual(
            ticket.department_id,
            self.creator.profile.department_id,
        )

    def test_ticket_department_can_differ_from_assignee_department(self):
        ticket = self.create_for_creator(assignee=self.assignee)

        self.assertNotEqual(
            ticket.department_id,
            self.assignee.profile.department_id,
        )

    def test_profile_department_update_does_not_cascade(self):
        ticket = self.create_for_creator()
        original_department_id = ticket.department_id
        profile = self.creator.profile
        profile.department = self.other_department
        profile.save(update_fields=["department"])

        self.assertEqual(
            Ticket.objects.get(pk=ticket.pk).department_id,
            original_department_id,
        )
