from django.conf import settings
from django.db import models


class RolePermissionScope(models.TextChoices):
    ALL = "all", "全部数据"
    DEPARTMENT = "department", "本部门数据"
    SELF = "self", "本人相关数据"


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    permissions = models.ManyToManyField(
        "auth.Permission",
        through="RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        db_table = "roles"

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        "auth.Permission",
        on_delete=models.PROTECT,
        related_name="role_permissions",
    )
    scope = models.CharField(
        max_length=20,
        choices=RolePermissionScope.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="uniq_role_permission",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    scope__in=RolePermissionScope.values
                ),
                name="valid_role_permission_scope",
            ),
        ]


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="profile"
    )
    department = models.ForeignKey(
        "departments.Department", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="members"
    )
    roles = models.ManyToManyField(Role, through="UserRole", related_name="users")
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_profiles"
        permissions = [
            (
                "assign_user_department",
                "Can assign user department",
            ),
        ]

class UserRole(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        db_table = "user_roles"
        permissions = [
            (
                "manage_user_roles",
                "Can manage user roles",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user_profile", "role"], name="uniq_user_profile_role"
            )
        ]
