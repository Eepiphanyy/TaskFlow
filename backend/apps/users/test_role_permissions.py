from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from .models import Role, RolePermission, RolePermissionScope


class RolePermissionModelTests(TestCase):
    def setUp(self):
        self.content_type = ContentType.objects.get_for_model(Role)
        self.permission = Permission.objects.create(
            name="Test permission",
            content_type=self.content_type,
            codename="test_permission",
        )
        self.role = Role.objects.create(
            name="测试角色",
            code="test_role",
        )

    def test_can_create_role_permission(self):
        relation = RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )

        self.assertEqual(relation.role, self.role)
        self.assertEqual(relation.permission, self.permission)
        self.assertEqual(relation.scope, RolePermissionScope.ALL)

    def test_role_permissions_many_to_many_lookup(self):
        self.role.permissions.add(
            self.permission,
            through_defaults={"scope": RolePermissionScope.DEPARTMENT},
        )

        self.assertEqual(
            list(self.role.permissions.all()),
            [self.permission],
        )

    def test_permission_roles_reverse_lookup(self):
        self.role.permissions.add(
            self.permission,
            through_defaults={"scope": RolePermissionScope.SELF},
        )

        self.assertEqual(
            list(self.permission.roles.all()),
            [self.role],
        )

    def test_role_permission_pair_is_unique(self):
        RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RolePermission.objects.create(
                    role=self.role,
                    permission=self.permission,
                    scope=RolePermissionScope.SELF,
                )

    def test_different_roles_can_share_permission(self):
        other_role = Role.objects.create(
            name="另一个角色",
            code="other_role",
        )

        RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )
        RolePermission.objects.create(
            role=other_role,
            permission=self.permission,
            scope=RolePermissionScope.SELF,
        )

        self.assertEqual(
            RolePermission.objects.filter(
                permission=self.permission
            ).count(),
            2,
        )

    def test_role_can_have_multiple_permissions(self):
        second_permission = Permission.objects.create(
            name="Second permission",
            content_type=self.content_type,
            codename="second_permission",
        )

        RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )
        RolePermission.objects.create(
            role=self.role,
            permission=second_permission,
            scope=RolePermissionScope.DEPARTMENT,
        )

        self.assertEqual(self.role.role_permissions.count(), 2)

    def test_all_supported_scopes_can_be_saved(self):
        for index, scope in enumerate((
            RolePermissionScope.ALL,
            RolePermissionScope.DEPARTMENT,
            RolePermissionScope.SELF,
        ), start=1):
            permission = Permission.objects.create(
                name=f"Scope permission {index}",
                content_type=self.content_type,
                codename=f"scope_permission_{index}",
            )
            RolePermission.objects.create(
                role=self.role,
                permission=permission,
                scope=scope,
            )

        self.assertEqual(
            set(
                self.role.role_permissions.values_list(
                    "scope",
                    flat=True,
                )
            ),
            {"all", "department", "self"},
        )

    def test_invalid_scope_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RolePermission.objects.create(
                    role=self.role,
                    permission=self.permission,
                    scope="invalid",
                )

    def test_deleting_role_cascades_role_permission(self):
        RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )

        self.role.delete()

        self.assertEqual(RolePermission.objects.count(), 0)
        self.assertTrue(
            Permission.objects.filter(pk=self.permission.pk).exists()
        )

    def test_deleting_permission_is_protected(self):
        RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )

        with self.assertRaises(ProtectedError):
            self.permission.delete()

        self.assertTrue(Permission.objects.filter(pk=self.permission.pk).exists())

    def test_deleting_association_keeps_role(self):
        relation = RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )

        relation.delete()

        self.assertTrue(Role.objects.filter(pk=self.role.pk).exists())

    def test_deleting_association_keeps_permission(self):
        relation = RolePermission.objects.create(
            role=self.role,
            permission=self.permission,
            scope=RolePermissionScope.ALL,
        )

        relation.delete()

        self.assertTrue(
            Permission.objects.filter(pk=self.permission.pk).exists()
        )
