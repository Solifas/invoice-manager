from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Invoice, InvoicePayment, InvoiceStatus
from .services import quantize_money


def _annotate_outstanding(queryset):
    paid_amount = Coalesce(Sum("payments__amount"), Decimal("0.00"))
    annotated_outstanding_amount = ExpressionWrapper(
        F("total_amount") - paid_amount,
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    return queryset.annotate(
        amount_paid_total=paid_amount,
        annotated_outstanding_amount=annotated_outstanding_amount,
        latest_payment_date=Max("payments__payment_date"),
    )


def get_dashboard_summary(owner=None) -> dict:
    today = timezone.localdate()
    month_start = today.replace(day=1)
    invoices = _annotate_outstanding(Invoice.objects.select_related("client").prefetch_related("payments"))
    if owner is not None:
        invoices = invoices.filter(owner=owner)

    active_invoices = invoices.exclude(status=InvoiceStatus.CANCELLED)
    collection_invoices = list(active_invoices)
    overdue_invoice_rows = []
    total_overdue_amount = Decimal("0.00")
    due_next_7_days_invoices = 0
    total_amount_outstanding = Decimal("0.00")

    for invoice in collection_invoices:
        invoice_outstanding = quantize_money(invoice.annotated_outstanding_amount or Decimal("0.00"))
        if invoice_outstanding <= Decimal("0.00"):
            continue

        total_amount_outstanding += invoice_outstanding
        is_collectable = invoice.status != InvoiceStatus.DRAFT
        if is_collectable and invoice.due_date < today:
            total_overdue_amount += invoice_outstanding
            overdue_invoice_rows.append(
                {
                    "id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "client_name": invoice.client.name,
                    "due_date": invoice.due_date,
                    "outstanding_amount": invoice_outstanding,
                    "status": InvoiceStatus.OVERDUE,
                }
            )
        elif is_collectable and today <= invoice.due_date <= today + timedelta(days=7):
            due_next_7_days_invoices += 1

    overdue_invoice_rows.sort(key=lambda item: (item["due_date"], item["invoice_number"]))

    monthly_payment_records = InvoicePayment.objects.exclude(invoice__status=InvoiceStatus.CANCELLED).filter(
        payment_date__gte=month_start,
        payment_date__lte=today,
    )
    if owner is not None:
        monthly_payment_records = monthly_payment_records.filter(invoice__owner=owner)
    monthly_payments = monthly_payment_records.aggregate(
        paid_invoices_this_month=Count("invoice_id", distinct=True),
        collected_amount_this_month=Coalesce(Sum("amount"), Decimal("0.00")),
    )

    aggregates = invoices.aggregate(
        total_invoices=Count("id", filter=~Q(status=InvoiceStatus.CANCELLED), distinct=True),
        unpaid_invoices=Count(
            "id",
            filter=~Q(status=InvoiceStatus.CANCELLED) & Q(annotated_outstanding_amount__gt=Value(Decimal("0.00"))),
            distinct=True,
        ),
        overdue_invoices=Count(
            "id",
            filter=~Q(status__in=[InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]) & Q(annotated_outstanding_amount__gt=Value(Decimal("0.00"))) & Q(due_date__lt=today),
            distinct=True,
        ),
    )
    return {
        "total_invoices": aggregates["total_invoices"],
        "unpaid_invoices": aggregates["unpaid_invoices"],
        "overdue_invoices": aggregates["overdue_invoices"],
        "total_amount_outstanding": quantize_money(total_amount_outstanding),
        "total_overdue_amount": quantize_money(total_overdue_amount),
        "due_next_7_days_invoices": due_next_7_days_invoices,
        "paid_invoices_this_month": monthly_payments["paid_invoices_this_month"],
        "collected_amount_this_month": quantize_money(monthly_payments["collected_amount_this_month"]),
        "oldest_overdue_invoice": overdue_invoice_rows[0] if overdue_invoice_rows else None,
        "overdue_invoice_table": overdue_invoice_rows,
    }


def get_collections_analytics(owner) -> dict:
    today = timezone.localdate()
    month_start = today.replace(day=1)
    invoices = _annotate_outstanding(
        Invoice.objects.select_related("client").prefetch_related("payments").filter(owner=owner).exclude(
            status=InvoiceStatus.CANCELLED
        )
    )

    total_invoiced_this_month = invoices.filter(issue_date__gte=month_start, issue_date__lte=today).aggregate(
        total=Coalesce(Sum("total_amount"), Decimal("0.00"))
    )["total"]
    total_collected_this_month = InvoicePayment.objects.filter(
        invoice__owner=owner,
        payment_date__gte=month_start,
        payment_date__lte=today,
    ).exclude(invoice__status=InvoiceStatus.CANCELLED).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"]

    total_outstanding = Decimal("0.00")
    total_overdue = Decimal("0.00")
    paid_days = []
    ageing_buckets = {
        "one_to_seven_days": {"count": 0, "amount": Decimal("0.00")},
        "eight_to_fourteen_days": {"count": 0, "amount": Decimal("0.00")},
        "fifteen_to_thirty_days": {"count": 0, "amount": Decimal("0.00")},
        "thirty_one_plus_days": {"count": 0, "amount": Decimal("0.00")},
    }
    high_risk_invoices = []

    for invoice in invoices:
        outstanding = quantize_money(invoice.annotated_outstanding_amount or Decimal("0.00"))
        if outstanding > Decimal("0.00"):
            total_outstanding += outstanding

        if invoice.total_amount > Decimal("0.00") and invoice.amount_paid_total >= invoice.total_amount and invoice.latest_payment_date:
            paid_days.append((invoice.latest_payment_date - invoice.issue_date).days)

        if invoice.status == InvoiceStatus.DRAFT or outstanding <= Decimal("0.00") or invoice.due_date >= today:
            continue

        days_overdue = (today - invoice.due_date).days
        total_overdue += outstanding
        if days_overdue <= 7:
            bucket_key = "one_to_seven_days"
        elif days_overdue <= 14:
            bucket_key = "eight_to_fourteen_days"
        elif days_overdue <= 30:
            bucket_key = "fifteen_to_thirty_days"
        else:
            bucket_key = "thirty_one_plus_days"
        ageing_buckets[bucket_key]["count"] += 1
        ageing_buckets[bucket_key]["amount"] += outstanding

        if days_overdue > 14 or invoice.reminder_sent_count >= 2:
            high_risk_invoices.append(
                {
                    "id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "client_name": invoice.client.name,
                    "due_date": invoice.due_date,
                    "days_overdue": days_overdue,
                    "outstanding_amount": outstanding,
                    "reminder_sent_count": invoice.reminder_sent_count,
                    "status": InvoiceStatus.OVERDUE,
                }
            )

    collection_rate_percentage = Decimal("0.00")
    if total_invoiced_this_month > Decimal("0.00"):
        collection_rate_percentage = quantize_money((total_collected_this_month / total_invoiced_this_month) * Decimal("100"))

    average_days_to_payment = 0
    if paid_days:
        average_days_to_payment = round(sum(paid_days) / len(paid_days), 1)

    for bucket in ageing_buckets.values():
        bucket["amount"] = quantize_money(bucket["amount"])

    high_risk_invoices.sort(key=lambda item: (-item["days_overdue"], item["invoice_number"]))

    return {
        "total_invoiced_this_month": quantize_money(total_invoiced_this_month),
        "total_collected_this_month": quantize_money(total_collected_this_month),
        "total_outstanding": quantize_money(total_outstanding),
        "total_overdue": quantize_money(total_overdue),
        "average_days_to_payment": average_days_to_payment,
        "collection_rate_percentage": collection_rate_percentage,
        "overdue_ageing_buckets": ageing_buckets,
        "high_risk_invoices": high_risk_invoices,
    }
