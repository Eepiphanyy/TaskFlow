from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.departments.models import Department

from .models import Role, UserProfile
from .services.permission_resolver import resolve_user_permissions

User = get_user_model()


class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        "no_active_account": "用户名或密码错误，或账号不可用。",
    }


class RegisteredUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = fields


class CurrentUserDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name")
        read_only_fields = fields


class CurrentUserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "name", "code")
        read_only_fields = fields


class CurrentUserSerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "department",
            "roles",
            "permissions",
        )
        read_only_fields = fields

    def get_department(self, user):
        profile = getattr(user, "profile", None)
        department = getattr(profile, "department", None)
        if department is None:
            return None
        return CurrentUserDepartmentSerializer(department).data

    def get_roles(self, user):
        profile = getattr(user, "profile", None)
        if profile is None:
            return []
        return CurrentUserRoleSerializer(
            profile.roles.all(),
            many=True,
        ).data

    def get_permissions(self, user):
        resolved_permissions = self.context.get("resolved_permissions")
        if resolved_permissions is None:
            resolved_permissions = resolve_user_permissions(user)
        return sorted(resolved_permissions.permissions)


class UserDepartmentUpdateSerializer(serializers.Serializer):
    department_id = serializers.IntegerField(
        required=True,
        allow_null=True,
        min_value=1,
    )

    def validate(self, attrs):
        unknown_fields = sorted(
            set(self.initial_data.keys()) - set(self.fields)
        )
        if unknown_fields:
            raise serializers.ValidationError({
                field: "不支持修改该字段。"
                for field in unknown_fields
            })
        return attrs


class UserRoleAssignSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(
        required=True,
        min_value=1,
    )

    def validate(self, attrs):
        unknown_fields = sorted(
            set(self.initial_data.keys()) - set(self.fields)
        )
        if unknown_fields:
            raise serializers.ValidationError({
                field: "不支持修改该字段。"
                for field in unknown_fields
            })
        return attrs


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("该用户名已被使用。")
        return value

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("该邮箱已被使用。")
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "两次输入的密码不一致。",
            })

        candidate_user = User(
            username=attrs["username"],
            email=attrs["email"],
        )
        try:
            validate_password(attrs["password"], user=candidate_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "password": list(exc.messages),
            }) from exc
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
            )
            UserProfile.objects.get_or_create(user=user)
        return user
