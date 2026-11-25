import logging

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.db.models import Prefetch
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import (
    TokenBlacklistSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from apps.departments.models import Department

from .models import Role, UserProfile, UserRole
from .permissions import (
    ADMIN_ROLE_CODE,
    HasUserDepartmentAssignPermission,
    IsTaskFlowAdmin,
)
from .serializers import (
    CurrentUserSerializer,
    CurrentUserRoleSerializer,
    LoginSerializer,
    RegisteredUserSerializer,
    RegisterSerializer,
    UserDepartmentUpdateSerializer,
    UserRoleAssignSerializer,
)
from .services.user_department import (
    UserDepartmentDepartmentMissing,
    UserDepartmentPermissionDenied,
    UserDepartmentProfileMissing,
    UserDepartmentScopeDenied,
    UserDepartmentUserMissing,
    update_user_department,
)
from .services.permission_resolver import resolve_user_permissions

User = get_user_model()
logger = logging.getLogger(__name__)


class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = (
            User.objects
            .select_related("profile__department")
            .prefetch_related(
                Prefetch(
                    "profile__roles",
                    queryset=Role.objects.order_by("id"),
                )
            )
            .get(pk=request.user.pk)
        )
        resolved_permissions = resolve_user_permissions(user)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "获取当前用户成功",
            "data": CurrentUserSerializer(
                user,
                context={"resolved_permissions": resolved_permissions},
            ).data,
        })

    def handle_exception(self, exc):
        if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
            return Response(
                {
                    "code": status.HTTP_401_UNAUTHORIZED,
                    "message": "身份认证失败",
                    "errors": {"detail": str(exc.detail)},
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return super().handle_exception(exc)


class UserDepartmentUpdateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasUserDepartmentAssignPermission,
    ]

    def patch(self, request, user_id):
        serializer = UserDepartmentUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "用户部门分配请求校验失败",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = update_user_department(
                user_id=user_id,
                department_id=serializer.validated_data["department_id"],
                operator=request.user,
            )
        except UserDepartmentUserMissing:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": "用户不存在",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except UserDepartmentProfileMissing:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": "用户资料不存在",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except UserDepartmentDepartmentMissing:
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "部门不存在",
                    "errors": {
                        "department_id": ["该部门不存在。"]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except UserDepartmentPermissionDenied:
            return Response(
                {
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "无权修改用户部门。",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except UserDepartmentScopeDenied as exc:
            return Response(
                {
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": str(exc),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except DatabaseError:
            logger.exception(
                "Failed to update department for user_id=%s operator_id=%s",
                user_id,
                request.user.pk,
            )
            return Response(
                {
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "用户部门更新失败，请稍后重试。",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "code": status.HTTP_200_OK,
            "message": "用户部门更新成功",
            "data": {
                "user_id": result.user_id,
                "username": result.username,
                "department": (
                    {
                        "id": result.department_id,
                        "name": result.department_name,
                    }
                    if result.department_id is not None
                    else None
                ),
            },
        })


class UserRoleListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsTaskFlowAdmin]

    def get(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": "用户不存在",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return Response(
                {
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": "用户资料不存在",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        roles = profile.roles.order_by("id")
        return Response({
            "code": status.HTTP_200_OK,
            "message": "获取用户角色成功",
            "data": {
                "user_id": user.pk,
                "username": user.username,
                "roles": CurrentUserRoleSerializer(roles, many=True).data,
            },
        })

    def post(self, request, user_id):
        serializer = UserRoleAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "用户角色分配请求校验失败",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                role = Role.objects.select_for_update().get(
                    pk=serializer.validated_data["role_id"]
                )
            except Role.DoesNotExist:
                return Response(
                    {
                        "code": status.HTTP_400_BAD_REQUEST,
                        "message": "角色不存在",
                        "errors": {
                            "role_id": ["该角色不存在。"]
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                user = User.objects.select_for_update().get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {
                        "code": status.HTTP_404_NOT_FOUND,
                        "message": "用户不存在",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            try:
                profile = UserProfile.objects.select_for_update().get(
                    user=user
                )
            except UserProfile.DoesNotExist:
                return Response(
                    {
                        "code": status.HTTP_404_NOT_FOUND,
                        "message": "用户资料不存在",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            _, created = UserRole.objects.get_or_create(
                user_profile=profile,
                role=role,
            )

        response_status = (
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        )
        return Response(
            {
                "code": response_status,
                "message": (
                    "用户角色分配成功"
                    if created
                    else "用户角色已存在"
                ),
                "data": {
                    "user_id": user.pk,
                    "username": user.username,
                    "role": CurrentUserRoleSerializer(role).data,
                },
            },
            status=response_status,
        )


class UserRoleDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, IsTaskFlowAdmin]

    def delete(self, request, user_id, role_id):
        with transaction.atomic():
            try:
                role = Role.objects.select_for_update().get(pk=role_id)
            except Role.DoesNotExist:
                return Response(
                    {
                        "code": status.HTTP_404_NOT_FOUND,
                        "message": "角色不存在",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            try:
                user = User.objects.select_for_update().get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {
                        "code": status.HTTP_404_NOT_FOUND,
                        "message": "用户不存在",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            try:
                profile = UserProfile.objects.select_for_update().get(
                    user=user
                )
            except UserProfile.DoesNotExist:
                return Response(
                    {
                        "code": status.HTTP_404_NOT_FOUND,
                        "message": "用户资料不存在",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            assignment_exists = UserRole.objects.filter(
                user_profile=profile,
                role=role,
            ).exists()
            if not assignment_exists:
                return Response(
                    {
                        "code": status.HTTP_404_NOT_FOUND,
                        "message": "用户未分配该角色",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if role.code == ADMIN_ROLE_CODE:
                admin_count = UserRole.objects.filter(role=role).count()
                if admin_count <= 1:
                    return Response(
                        {
                            "code": status.HTTP_409_CONFLICT,
                            "message": "不能移除最后一个 admin 角色",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            UserRole.objects.filter(
                user_profile=profile,
                role=role,
            ).delete()

        return Response({
            "code": status.HTTP_200_OK,
            "message": "用户角色移除成功",
            "data": {
                "user_id": user.pk,
                "username": user.username,
                "role": CurrentUserRoleSerializer(role).data,
            },
        })


class LoginAPIView(TokenObtainPairView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            is_valid = serializer.is_valid()
        except AuthenticationFailed:
            return Response(
                {
                    "code": status.HTTP_401_UNAUTHORIZED,
                    "message": "用户名或密码错误，或账号不可用。",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not is_valid:
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "登录信息校验失败",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "code": status.HTTP_200_OK,
            "message": "登录成功",
            "data": serializer.validated_data,
        })


class RefreshAPIView(TokenRefreshView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            is_valid = serializer.is_valid()
        except (TokenError, AuthenticationFailed):
            return Response(
                {
                    "code": status.HTTP_401_UNAUTHORIZED,
                    "message": "Refresh Token 无效、已过期或已被拉黑",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not is_valid:
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "刷新 Token 请求校验失败",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "code": status.HTTP_200_OK,
            "message": "Token 刷新成功",
            "data": serializer.validated_data,
        })


class LogoutAPIView(TokenBlacklistView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = TokenBlacklistSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            is_valid = serializer.is_valid()
        except (TokenError, AuthenticationFailed):
            return Response(
                {
                    "code": status.HTTP_401_UNAUTHORIZED,
                    "message": "Refresh Token 无效、已过期或已被拉黑",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not is_valid:
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "退出登录请求校验失败",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "code": status.HTTP_200_OK,
            "message": "退出登录成功",
            "data": None,
        })


class RegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "注册信息校验失败",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        return Response(
            {
                "code": status.HTTP_201_CREATED,
                "message": "注册成功",
                "data": RegisteredUserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )
