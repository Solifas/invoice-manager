from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.clients.models import Client


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"
    CANCELLED = "cancelled", "Cancelled"


class TaxType(models.TextChoices):
    NONE = "none", "No tax"
    PERCENTAGE = "percentage", "Percentage"


class Invoice(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    notes = models.TextField(blank=True)
    currency = models.CharField(max_length=8, default="USD")
    tax_type = models.CharField(max_length=20, choices=TaxType.choices, default=TaxType.NONE)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reminder_last_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-issue_date", "-created_at")

    def clean(self) -> None:
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValidationError({"due_date": "Due date cannot be before issue date."})
        if self.tax_type == TaxType.NONE and self.tax_rate != Decimal("0.00"):
            raise ValidationError({"tax_rate": "Tax rate must be zero when tax is disabled."})
        if self.tax_rate < 0:
            raise ValidationError({"tax_rate": "Tax rate cannot be negative."})

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
        if self.unit_price < 0:
            raise ValidationError({"unit_price": "Unit price cannot be negative."})

    def __str__(self) -> str:
        return self.description
