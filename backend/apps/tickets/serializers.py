from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.departments.models import Department

from .models import Ticket, TicketCategory

User = get_user_model()


class TicketUserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = fields


class TicketCategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketCategory
        fields = ("id", "name")
        read_only_fields = fields


class TicketCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketCategory
        fields = ("id", "name", "description")
        read_only_fields = fields


class TicketDepartmentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name")
        read_only_fields = fields


class TicketAssigneeSerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "department")
        read_only_fields = fields

    def get_department(self, user):
        profile = getattr(user, "profile", None)
        department = getattr(profile, "department", None)
        if department is None:
            return None
        return TicketDepartmentSummarySerializer(department).data


class TicketReadSerializer(serializers.ModelSerializer):
    category = TicketCategorySummarySerializer(read_only=True)
    creator = TicketUserSummarySerializer(read_only=True)
    assignee = TicketUserSummarySerializer(read_only=True)
    department = TicketDepartmentSummarySerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "title",
            "description",
            "category",
            "creator",
            "assignee",
            "department",
            "status",
            "priority",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class TicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    category = serializers.PrimaryKeyRelatedField(
        queryset=TicketCategory.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        unknown_fields = sorted(
            set(self.initial_data.keys()) - set(self.fields)
        )
        if unknown_fields:
            raise serializers.ValidationError({
                field: "创建工单时不支持指定该字段。"
                for field in unknown_fields
            })
        return attrs


class TicketUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=200,
        required=False,
    )
    description = serializers.CharField(required=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=TicketCategory.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        unknown_fields = sorted(
            set(self.initial_data.keys()) - set(self.fields)
        )
        if unknown_fields:
            raise serializers.ValidationError({
                field: "编辑工单时不支持指定该字段。"
                for field in unknown_fields
            })
        if not attrs:
            raise serializers.ValidationError({
                "non_field_errors": [
                    "至少需要提供一个可编辑字段。"
                ]
            })
        return attrs


class TicketAssignSerializer(serializers.Serializer):
    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee",
        queryset=User.objects.all(),
        required=True,
        allow_null=True,
    )

    def validate(self, attrs):
        unknown_fields = sorted(
            set(self.initial_data.keys()) - set(self.fields)
        )
        if unknown_fields:
            raise serializers.ValidationError({
                field: "分配工单时不支持指定该字段。"
                for field in unknown_fields
            })
        return attrs


class TicketProcessSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(
            Ticket.Status.PROCESSING,
            Ticket.Status.RESOLVED,
        ),
        required=True,
    )

    def validate(self, attrs):
        unknown_fields = sorted(
            set(self.initial_data.keys()) - set(self.fields)
        )
        if unknown_fields:
            raise serializers.ValidationError({
                field: "处理工单时不支持指定该字段。"
                for field in unknown_fields
            })
        return attrs


class TicketCloseSerializer(serializers.Serializer):
    def validate(self, attrs):
        unknown_fields = sorted(
            set(self.initial_data.keys()) - set(self.fields)
        )
        if unknown_fields:
            raise serializers.ValidationError({
                field: "关闭工单时不支持指定该字段。"
                for field in unknown_fields
            })
        return attrs
