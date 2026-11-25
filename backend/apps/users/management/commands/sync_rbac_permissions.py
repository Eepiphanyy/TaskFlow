from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.users.models import Role, RolePermission
from apps.users.rbac_matrix import (
    DEFAULT_ROLE_CODES,
    DEFAULT_ROLE_GRANTS,
    REQUIRED_PERMISSIONS,
)


class Command(BaseCommand):
    help = "幂等同步 TaskFlow 默认角色权限矩阵。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="将已有但 Scope 不一致的授权更新为默认矩阵 Scope",
        )

    def handle(self, *args, **options):
        force = options["force"]
        created_count = 0
        existing_count = 0
        conflict_count = 0
        updated_count = 0

        try:
            with transaction.atomic():
                roles = {
                    role.code: role
                    for role in Role.objects.filter(
                        code__in=DEFAULT_ROLE_CODES
                    )
                }
                required_permission_keys = set(REQUIRED_PERMISSIONS)
                permission_query = Q()
                for app_label, codename in REQUIRED_PERMISSIONS:
                    permission_query |= Q(
                        content_type__app_label=app_label,
                        codename=codename,
                    )

                permissions = Permission.objects.select_related(
                    "content_type"
                ).filter(permission_query)
                permission_map = {
                    (
                        permission.content_type.app_label,
                        permission.codename,
                    ): permission
                    for permission in permissions
                    if (
                        permission.content_type.app_label,
                        permission.codename,
                    ) in required_permission_keys
                }

                missing_roles = [
                    code
                    for code in DEFAULT_ROLE_CODES
                    if code not in roles
                ]
                missing_permissions = [
                    f"{app_label}.{codename}"
                    for app_label, codename in REQUIRED_PERMISSIONS
                    if (app_label, codename) not in permission_map
                ]

                self.stdout.write(f"找到角色：{len(roles)} 个")
                self.stdout.write(
                    f"找到 Permission：{len(permission_map)} 个"
                )

                if missing_roles or missing_permissions:
                    details = []
                    if missing_roles:
                        details.append(
                            f"缺少角色：{', '.join(missing_roles)}"
                        )
                    if missing_permissions:
                        details.append(
                            "缺少 Permission："
                            f"{', '.join(missing_permissions)}"
                        )
                    raise CommandError("；".join(details))

                for role_code, app_label, codename, scope in DEFAULT_ROLE_GRANTS:
                    role = roles[role_code]
                    permission = permission_map[(app_label, codename)]
                    relation, created = RolePermission.objects.get_or_create(
                        role=role,
                        permission=permission,
                        defaults={"scope": scope},
                    )

                    if created:
                        created_count += 1
                        continue

                    if relation.scope == scope:
                        existing_count += 1
                        continue

                    conflict_count += 1
                    if not force:
                        self.stdout.write(
                            "Scope 冲突："
                            f"{role.code} / {app_label}.{codename} "
                            f"（现有 {relation.scope}，默认 {scope}）"
                        )
                        continue

                    self.stdout.write(
                        "准备更新 Scope："
                        f"{role.code} / {app_label}.{codename} "
                        f"{relation.scope} -> {scope}"
                    )
                    relation.scope = scope
                    relation.save(update_fields=["scope", "updated_at"])
                    updated_count += 1
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f"同步角色权限失败，事务已回滚：{exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "权限矩阵同步完成："
                f"新增 {created_count} 个，"
                f"已存在 {existing_count} 个，"
                f"Scope 冲突 {conflict_count} 个，"
                f"更新 {updated_count} 个。"
            )
        )
