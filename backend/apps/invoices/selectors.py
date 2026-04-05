from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Invoice, InvoiceStatus


def get_dashboard_summary() -> dict:
    today = timezone.localdate()
    paid_amount = Coalesce(Sum("payments__amount"), Decimal("0.00"))
    outstanding_amount = ExpressionWrapper(
        F("total_amount") - paid_amount,
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    invoices = Invoice.objects.annotate(outstanding_amount=outstanding_amount)
    aggregates = invoices.aggregate(
        total_invoices=Count("id", distinct=True),
        unpaid_invoices=Count(
            "id",
            filter=~Q(status=InvoiceStatus.CANCELLED) & Q(outstanding_amount__gt=Value(Decimal("0.00"))),
            distinct=True,
        ),
        overdue_invoices=Count(
            "id",
            filter=~Q(status__in=[InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]) & Q(outstanding_amount__gt=Value(Decimal("0.00"))) & Q(due_date__lt=today),
            distinct=True,
        ),
        total_amount_outstanding=Coalesce(
            Sum("outstanding_amount", filter=~Q(status=InvoiceStatus.CANCELLED) & Q(outstanding_amount__gt=Value(Decimal("0.00")))),
            Decimal("0.00"),
        ),
    )
    return {
        "total_invoices": aggregates["total_invoices"],
        "unpaid_invoices": aggregates["unpaid_invoices"],
        "overdue_invoices": aggregates["overdue_invoices"],
        "total_amount_outstanding": aggregates["total_amount_outstanding"],
    }
