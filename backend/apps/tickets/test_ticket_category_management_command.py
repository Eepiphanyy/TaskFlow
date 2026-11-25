from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .management.commands.init_default_ticket_categories import (
    DEFAULT_TICKET_CATEGORIES,
)
from .models import TicketCategory

User = get_user_model()


class InitDefaultTicketCategoriesCommandTests(APITestCase):
    def test_first_execution_creates_all_default_categories(self):
        output = StringIO()

        call_command(
            "init_default_ticket_categories",
            stdout=output,
        )

        self.assertEqual(
            set(TicketCategory.objects.values_list("name", flat=True)),
            {name for name, _description in DEFAULT_TICKET_CATEGORIES},
        )
        self.assertEqual(TicketCategory.objects.count(), 6)
        self.assertIn("新建 6 个", output.getvalue())
        self.assertIn("已存在 0 个", output.getvalue())

    def test_second_execution_is_idempotent(self):
        call_command(
            "init_default_ticket_categories",
            stdout=StringIO(),
        )
        output = StringIO()

        call_command(
            "init_default_ticket_categories",
            stdout=output,
        )

        self.assertEqual(TicketCategory.objects.count(), 6)
        self.assertIn("新建 0 个", output.getvalue())
        self.assertIn("已存在 6 个", output.getvalue())

    def test_existing_description_is_not_overwritten(self):
        existing = TicketCategory.objects.create(
            name="系统问题",
            description="已有自定义描述",
        )

        call_command(
            "init_default_ticket_categories",
            stdout=StringIO(),
        )

        existing.refresh_from_db()
        self.assertEqual(existing.description, "已有自定义描述")
        self.assertEqual(TicketCategory.objects.count(), 6)

    def test_initialization_failure_rolls_back_all_categories(self):
        original_get_or_create = TicketCategory.objects.get_or_create
        calls = 0

        def flaky_get_or_create(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return original_get_or_create(*args, **kwargs)
            raise RuntimeError("simulated category failure")

        with patch(
            "apps.tickets.management.commands."
            "init_default_ticket_categories."
            "TicketCategory.objects.get_or_create",
            side_effect=flaky_get_or_create,
        ):
            with self.assertRaisesMessage(
                CommandError,
                "事务已回滚",
            ):
                call_command(
                    "init_default_ticket_categories",
                    stdout=StringIO(),
                )

        self.assertEqual(TicketCategory.objects.count(), 0)

    def test_initialized_categories_are_available_from_api(self):
        call_command(
            "init_default_ticket_categories",
            stdout=StringIO(),
        )
        user = User.objects.create_user(
            username="category_command_api_user",
            email="category_command_api_user@example.com",
            password="TaskFlow#2026",
        )
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}"
        )

        response = client.get(reverse("ticket-categories:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 6)
        self.assertEqual(
            {item["name"] for item in response.data},
            {name for name, _description in DEFAULT_TICKET_CATEGORIES},
        )
