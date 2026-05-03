import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.clients.models import Client


def generate_invoice_public_token() -> str:
    return secrets.token_urlsafe(32)


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"
    CANCELLED = "cancelled", "Cancelled"


class TaxType(models.TextChoices):
    NONE = "none", "No tax"
    PERCENTAGE = "percentage", "Percentage"


class CurrencyCode(models.TextChoices):
    ZAR = "ZAR", "South African rand"
    USD = "USD", "US dollar"


class InvoiceEftSourceType(models.TextChoices):
    SAVED_PROFILE = "saved_profile", "Saved profile"
    MANUAL = "manual", "Manual"


class RecurringInvoiceFrequency(models.TextChoices):
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"


class RecurringInvoiceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    CANCELLED = "cancelled", "Cancelled"


class Invoice(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
        blank=True,
        null=True,
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    recurring_invoice = models.ForeignKey(
        "RecurringInvoice",
        on_delete=models.SET_NULL,
        related_name="generated_invoices",
        blank=True,
        null=True,
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    notes = models.TextField(blank=True)
    currency = models.CharField(max_length=8, default=CurrencyCode.ZAR)
    tax_type = models.CharField(max_length=20, choices=TaxType.choices, default=TaxType.NONE)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_page_enabled = models.BooleanField(default=False)
    public_token = models.CharField(max_length=64, unique=True, default=generate_invoice_public_token)
    public_token_regenerated_at = models.DateTimeField(blank=True, null=True)
    payment_page_first_opened_at = models.DateTimeField(blank=True, null=True)
    payment_page_last_opened_at = models.DateTimeField(blank=True, null=True)
    payment_page_open_count = models.PositiveIntegerField(default=0)
    eft_source_type = models.CharField(max_length=20, choices=InvoiceEftSourceType.choices, blank=True)
    eft_source_profile = models.ForeignKey(
        "accounts.UserBankingProfile",
        on_delete=models.SET_NULL,
        related_name="invoice_snapshots",
        blank=True,
        null=True,
    )
    eft_profile_name = models.CharField(max_length=255, blank=True)
    eft_account_holder_name = models.CharField(max_length=255, blank=True)
    eft_bank_name = models.CharField(max_length=255, blank=True)
    eft_account_number = models.CharField(max_length=64, blank=True)
    eft_account_type = models.CharField(max_length=50, blank=True)
    eft_branch_code = models.CharField(max_length=32, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    reminder_last_sent_at = models.DateTimeField(blank=True, null=True)
    reminder_sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-issue_date", "-created_at")

    def clean(self) -> None:
        if self.owner_id and self.client_id and self.client.owner_id and self.client.owner_id != self.owner_id:
            raise ValidationError({"client": "Client must belong to the same owner as the invoice."})
        if (
            self.owner_id
            and self.recurring_invoice_id
            and self.recurring_invoice.owner_id
            and self.recurring_invoice.owner_id != self.owner_id
        ):
            raise ValidationError({"recurring_invoice": "Recurring template must belong to the same owner as the invoice."})
        if (
            self.owner_id
            and self.eft_source_profile_id
            and self.eft_source_profile.user_id != self.owner_id
        ):
            raise ValidationError({"eft_source_profile": "Banking profile must belong to the same owner as the invoice."})
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValidationError({"due_date": "Due date cannot be before issue date."})
        if self.tax_type == TaxType.NONE and self.tax_rate != Decimal("0.00"):
            raise ValidationError({"tax_rate": "Tax rate must be zero when tax is disabled."})
        if self.tax_rate < 0:
            raise ValidationError({"tax_rate": "Tax rate cannot be negative."})
        eft_fields = {
            "eft_account_holder_name": self.eft_account_holder_name,
            "eft_bank_name": self.eft_bank_name,
            "eft_account_number": self.eft_account_number,
        }
        has_any_eft_value = bool(
            self.eft_source_type
            or self.eft_source_profile_id
            or self.eft_profile_name
            or any(eft_fields.values())
            or self.payment_reference
        )
        if has_any_eft_value:
            missing_fields = [field for field, value in eft_fields.items() if not value]
            if missing_fields:
                raise ValidationError(
                    {field: "This field is required when invoice EFT details are configured." for field in missing_fields}
                )
        if self.eft_source_type == InvoiceEftSourceType.MANUAL and not self.eft_profile_name:
            raise ValidationError({"eft_profile_name": "Profile name is required for manual invoice EFT details."})

    @property
    def resolved_payment_reference(self) -> str:
        return self.payment_reference or self.invoice_number

    @property
    def amount_paid(self):
        from .services import get_invoice_amount_paid

        return get_invoice_amount_paid(self)

    @property
    def outstanding_amount(self):
        from .services import get_invoice_outstanding_amount

        return get_invoice_outstanding_amount(self)

    def __str__(self) -> str:
        return self.invoice_number


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ("id",)

    def clean(self) -> None:
        if self.quantity < 0:
            raise ValidationError({"quantity": "Quantity cannot be negative."})
        if self.quantity != self.quantity.to_integral_value():
            raise ValidationError({"quantity": "Quantity must be a whole number."})
        if self.unit_price < 0:
            raise ValidationError({"unit_price": "Unit price cannot be negative."})

    def __str__(self) -> str:
        return self.description


class InvoicePayment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-payment_date", "-created_at")

    def clean(self) -> None:
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "Payment amount must be greater than zero."})

        invoice_total = self.invoice.total_amount or Decimal("0.00")
        existing_total = (
            self.invoice.payments.exclude(pk=self.pk).aggregate(total=models.Sum("amount")).get("total") or Decimal("0.00")
        )
        if existing_total + self.amount > invoice_total:
            raise ValidationError({"amount": "Total payments cannot exceed the invoice total."})

    def __str__(self) -> str:
        return f"{self.invoice.invoice_number} payment {self.amount}"


class RecurringInvoice(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_invoices",
        blank=True,
        null=True,
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="recurring_invoices")
    contractor = models.ForeignKey(
        "contractors.Contractor",
        on_delete=models.SET_NULL,
        related_name="recurring_invoices",
        blank=True,
        null=True,
    )
    template_name = models.CharField(max_length=255)
    frequency = models.CharField(max_length=20, choices=RecurringInvoiceFrequency.choices)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    next_run_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=RecurringInvoiceStatus.choices, default=RecurringInvoiceStatus.ACTIVE)
    currency = models.CharField(max_length=8, default=CurrencyCode.ZAR)
    payment_terms_days = models.PositiveIntegerField(default=14)
    tax_type = models.CharField(max_length=20, choices=TaxType.choices, default=TaxType.NONE)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    line_items_template = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("template_name", "id")

    def clean(self) -> None:
        if self.owner_id and self.client_id and self.client.owner_id and self.client.owner_id != self.owner_id:
            raise ValidationError({"client": "Client must belong to the same owner as the recurring invoice."})
        if (
            self.owner_id
            and self.contractor_id
            and self.contractor.owner_id
            and self.contractor.owner_id != self.owner_id
        ):
            raise ValidationError({"contractor": "Contractor must belong to the same owner as the recurring invoice."})
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})
        if self.next_run_date and self.next_run_date < self.start_date:
            raise ValidationError({"next_run_date": "Next run date cannot be before the start date."})
        if self.tax_type == TaxType.NONE and self.tax_rate != Decimal("0.00"):
            raise ValidationError({"tax_rate": "Tax rate must be zero when tax is disabled."})
        if self.tax_rate < 0:
            raise ValidationError({"tax_rate": "Tax rate cannot be negative."})
        if self.payment_terms_days < 0:
            raise ValidationError({"payment_terms_days": "Payment terms cannot be negative."})
        for index, item in enumerate(self.line_items_template):
            quantity = Decimal(str(item.get("quantity", "0")))
            if quantity != quantity.to_integral_value():
                raise ValidationError({"line_items_template": f"Line item {index + 1} quantity must be a whole number."})

    def __str__(self) -> str:
        return self.template_name
