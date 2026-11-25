from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tickets.models import TicketCategory

DEFAULT_TICKET_CATEGORIES = (
    ("系统问题", "系统故障或异常"),
    ("账号权限", "登录、账号及权限相关问题"),
    ("网络问题", "网络连接及访问异常"),
    ("软件问题", "软件安装、使用及功能异常"),
    ("硬件问题", "电脑、打印机及其他设备故障"),
    ("其他问题", "暂时无法归入上述类别的问题"),
)


class Command(BaseCommand):
    help = "幂等初始化 TaskFlow 默认工单分类。"

    def handle(self, *args, **options):
        results = []

        try:
            with transaction.atomic():
                for name, description in DEFAULT_TICKET_CATEGORIES:
                    category, created = (
                        TicketCategory.objects.get_or_create(
                            name=name,
                            defaults={"description": description},
                        )
                    )
                    results.append((category, created))
        except Exception as exc:
            raise CommandError(
                f"初始化默认工单分类失败，事务已回滚：{exc}"
            ) from exc

        created_count = 0
        existed_count = 0

        for category, created in results:
            status = "新建" if created else "已存在"
            if created:
                created_count += 1
            else:
                existed_count += 1
            self.stdout.write(f"{status}：{category.name}")

        total = TicketCategory.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                "默认工单分类初始化完成："
                f"新建 {created_count} 个，"
                f"已存在 {existed_count} 个，"
                f"分类总数 {total}。"
            )
        )
