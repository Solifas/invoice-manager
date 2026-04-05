from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from .models import Invoice, InvoiceStatus


def get_dashboard_summary() -> dict:
    aggregates = Invoice.objects.aggregate(
        total_invoices=Count("id"),
        unpaid_invoices=Count("id", filter=Q(status__in=[InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.DRAFT])),
        overdue_invoices=Count("id", filter=Q(status=InvoiceStatus.OVERDUE)),
        total_amount_outstanding=Coalesce(
            Sum("total_amount", filter=Q(status__in=[InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.DRAFT])),
            Decimal("0.00"),
        ),
    )
    return {
        "total_invoices": aggregates["total_invoices"],
        "unpaid_invoices": aggregates["unpaid_invoices"],
        "overdue_invoices": aggregates["overdue_invoices"],
        "total_amount_outstanding": aggregates["total_amount_outstanding"],
    }
