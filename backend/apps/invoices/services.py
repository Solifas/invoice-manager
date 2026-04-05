from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import Invoice, InvoiceLineItem, InvoiceStatus, TaxType

MONEY_QUANTIZE = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def resolve_invoice_status(invoice: Invoice) -> str:
    if invoice.status in {InvoiceStatus.CANCELLED, InvoiceStatus.PAID}:
        return invoice.status
    if invoice.due_date < timezone.localdate() and invoice.status != InvoiceStatus.DRAFT:
        return InvoiceStatus.OVERDUE
    return invoice.status


@transaction.atomic
def recalculate_invoice_totals(invoice: Invoice) -> Invoice:
    subtotal = Decimal("0.00")
    line_items = list(invoice.line_items.all())

    for item in line_items:
        item.line_total = quantize_money(item.quantity * item.unit_price)
        item.full_clean()
        item.save(update_fields=["line_total"])
        subtotal += item.line_total

    subtotal = quantize_money(subtotal)
    if invoice.tax_type == TaxType.PERCENTAGE:
        tax_amount = quantize_money(subtotal * (invoice.tax_rate / Decimal("100")))
    else:
        tax_amount = Decimal("0.00")
        invoice.tax_rate = Decimal("0.00")

    invoice.subtotal = subtotal
    invoice.tax_amount = tax_amount
    invoice.total_amount = quantize_money(subtotal + tax_amount)
    invoice.status = resolve_invoice_status(invoice)
    invoice.full_clean()
    invoice.save()
    return invoice


@transaction.atomic
def replace_invoice_line_items(invoice: Invoice, items_data: list[dict]) -> None:
    invoice.line_items.all().delete()
    InvoiceLineItem.objects.bulk_create(
        [
            InvoiceLineItem(
                invoice=invoice,
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                line_total=Decimal("0.00"),
            )
            for item in items_data
        ]
    )
    recalculate_invoice_totals(invoice)
