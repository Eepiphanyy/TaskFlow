from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import Role, UserProfile, UserRole

User = get_user_model()


class Command(BaseCommand):
    help = "为单个指定用户分配一个已存在的 TaskFlow 业务角色。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help="要分配角色的用户名",
        )
        parser.add_argument(
            "--role",
            required=True,
            help="要分配的角色 code",
        )

    def handle(self, *args, **options):
        username = options["username"]
        role_code = options["role"]

        try:
            with transaction.atomic():
                try:
                    role = Role.objects.select_for_update().get(
                        code=role_code
                    )
                except Role.DoesNotExist as exc:
                    raise CommandError(
                        f"角色不存在：{role_code}"
                    ) from exc

                try:
                    user = User.objects.select_for_update().get(
                        username=username
                    )
                except User.DoesNotExist as exc:
                    raise CommandError(
                        f"用户不存在：{username}"
                    ) from exc

                try:
                    profile = UserProfile.objects.get(user=user)
                except UserProfile.DoesNotExist as exc:
                    raise CommandError(
                        f"用户 {username} 没有 UserProfile，无法分配角色。"
                    ) from exc

                _, created = UserRole.objects.get_or_create(
                    user_profile=profile,
                    role=role,
                )
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f"用户角色分配失败，事务已回滚：{exc}"
            ) from exc

        action = "已分配" if created else "关系已存在"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}：用户 {user.username}，"
                f"角色 {role.name} ({role.code})"
            )
        )
