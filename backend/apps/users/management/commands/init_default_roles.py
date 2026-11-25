from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import Role

DEFAULT_ROLES = (
    {
        "name": "系统管理员",
        "code": "admin",
        "description": "负责 TaskFlow 系统管理与权限管理",
    },
    {
        "name": "部门负责人",
        "code": "department_manager",
        "description": "负责部门成员及部门业务管理",
    },
    {
        "name": "普通员工",
        "code": "employee",
        "description": "负责日常工单与任务协作",
    },
    {
        "name": "工单处理人员",
        "code": "ticket_handler",
        "description": "负责工单处理与跟进",
    },
)


class Command(BaseCommand):
    help = "幂等初始化 TaskFlow 默认业务角色，不分配任何用户。"

    def handle(self, *args, **options):
        results = []

        try:
            with transaction.atomic():
                for role_data in DEFAULT_ROLES:
                    role, created = Role.objects.get_or_create(
                        code=role_data["code"],
                        defaults={
                            "name": role_data["name"],
                            "description": role_data["description"],
                        },
                    )
                    results.append((role, created))
        except Exception as exc:
            raise CommandError(
                f"初始化默认角色失败，事务已回滚：{exc}"
            ) from exc

        created_count = 0
        existed_count = 0

        for role, created in results:
            status = "新建" if created else "已存在"
            if created:
                created_count += 1
            else:
                existed_count += 1
            self.stdout.write(
                f"{status}：{role.name} ({role.code})"
            )

        total = Role.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                "默认角色初始化完成："
                f"新建 {created_count} 个，"
                f"已存在 {existed_count} 个，"
                f"角色总数 {total}。"
            )
        )
