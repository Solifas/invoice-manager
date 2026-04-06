from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import UserBankingProfile


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name")


class BankingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBankingProfile
        fields = (
            "id",
            "profile_name",
            "account_holder_name",
            "bank_name",
            "account_number",
            "account_type",
            "branch_code",
            "default_payment_reference",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def validate(self, attrs):
        if attrs.get("is_default") and self.instance and self.instance.is_active is False:
            raise serializers.ValidationError({"is_default": "A default banking profile must stay active."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        requested_default = validated_data.pop("is_default", False)
        is_default = requested_default or not UserBankingProfile.objects.filter(
            user=user, is_active=True
        ).exists()
        if is_default:
            UserBankingProfile.objects.filter(user=user).update(is_default=False)
        return UserBankingProfile.objects.create(user=user, is_default=is_default, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        is_default = validated_data.get("is_default", instance.is_default)
        if is_default:
            UserBankingProfile.objects.filter(user=instance.user).exclude(id=instance.id).update(is_default=False)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()
        instance.save()
        return instance


class RegistrationBankingProfileSerializer(serializers.Serializer):
    profile_name = serializers.CharField()
    account_holder_name = serializers.CharField()
    bank_name = serializers.CharField()
    account_number = serializers.CharField()
    account_type = serializers.CharField(required=False, allow_blank=True)
    branch_code = serializers.CharField(required=False, allow_blank=True)
    default_payment_reference = serializers.CharField(required=False, allow_blank=True)

    def create_for_user(self, user, validated_data=None):
        return UserBankingProfile.objects.create(
            user=user,
            is_default=True,
            **(validated_data or self.validated_data),
        )


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    banking_profile = RegistrationBankingProfileSerializer(required=False)

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        banking_profile_data = validated_data.pop("banking_profile", None)
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        user = User(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save()
        if banking_profile_data:
            RegistrationBankingProfileSerializer().create_for_user(user, validated_data=banking_profile_data)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            email=attrs["email"].strip().lower(),
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError({"detail": "Invalid email or password."})
        attrs["user"] = user
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    default_error_messages = {
        "invalid_token": "This password reset link is invalid or has expired.",
    }

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        user = self._get_user(attrs["uid"])
        if user is None or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": self.error_messages["invalid_token"]})

        validate_password(attrs["password"], user=user)
        attrs["user"] = user
        return attrs

    def _get_user(self, uid):
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            return User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        return user
