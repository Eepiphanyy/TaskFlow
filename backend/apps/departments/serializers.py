from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.users.serializers import CurrentUserRoleSerializer

from .models import Department

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name", "description", "created_at")
        read_only_fields = ("id", "created_at")


class DepartmentMemberSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "roles")
        read_only_fields = fields

    def get_roles(self, user):
        profile = getattr(user, "profile", None)
        if profile is None:
            return []
        return CurrentUserRoleSerializer(
            profile.roles.all(),
            many=True,
        ).data
