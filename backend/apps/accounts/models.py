from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class BusinessVerificationStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class BusinessProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business_profile")
    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=100)
    registration_number = models.CharField(max_length=100, blank=True)
    vat_number = models.CharField(max_length=100, blank=True)
    trading_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField()
    contact_phone_number = models.CharField(max_length=50)
    business_address = models.TextField()
    verification_status = models.CharField(
        max_length=20,
        choices=BusinessVerificationStatus.choices,
        default=BusinessVerificationStatus.NOT_STARTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("business_name", "id")

    @property
    def completeness_percentage(self) -> int:
        fields = (
            "business_name",
            "business_type",
            "contact_email",
            "contact_phone_number",
            "business_address",
            "registration_number",
            "vat_number",
            "trading_name",
        )
        completed = sum(1 for field in fields if getattr(self, field))
        return round((completed / len(fields)) * 100)

    def __str__(self):
        return f"{self.business_name} ({self.user.email})"


class UserBankingProfile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="banking_profiles")
    profile_name = models.CharField(max_length=255)
    account_holder_name = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=64)
    account_type = models.CharField(max_length=50, blank=True)
    branch_code = models.CharField(max_length=32, blank=True)
    default_payment_reference = models.CharField(max_length=100, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("profile_name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(is_default=True, is_active=True),
                name="unique_default_banking_profile_per_user",
            ),
        ]

    def clean(self):
        if self.is_default and not self.is_active:
            raise ValidationError({"is_default": "A default banking profile must be active."})

    def __str__(self):
        return f"{self.profile_name} ({self.user.email})"
