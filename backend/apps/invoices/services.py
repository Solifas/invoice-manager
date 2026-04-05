import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Invoice,
    InvoiceLineItem,
    InvoicePayment,
    InvoiceStatus,
    RecurringInvoice,
    RecurringInvoiceFrequency,
    RecurringInvoiceStatus,
    TaxType,
    generate_invoice_public_token,
)

MONEY_QUANTIZE = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP)


def get_invoice_amount_paid(invoice: Invoice) -> Decimal:
    total = invoice.payments.aggregate(total=Sum("amount")).get("total") or Decimal("0.00")
    return quantize_money(total)


def get_invoice_outstanding_amount(invoice: Invoice, amount_paid: Decimal | None = None) -> Decimal:
    paid_total = amount_paid if amount_paid is not None else get_invoice_amount_paid(invoice)
    outstanding = quantize_money(invoice.total_amount - paid_total)
    return outstanding if outstanding > Decimal("0.00") else Decimal("0.00")


def can_invoice_expose_payment_page(invoice: Invoice, amount_paid: Decimal | None = None) -> bool:
    if not invoice.payment_page_enabled:
        return False
    if invoice.status in {InvoiceStatus.PAID, InvoiceStatus.CANCELLED}:
        return False
    outstanding_amount = get_invoice_outstanding_amount(invoice, amount_paid=amount_paid)
    return outstanding_amount > Decimal("0.00")


def resolve_invoice_status(invoice: Invoice, amount_paid: Decimal | None = None) -> str:
    if invoice.status == InvoiceStatus.CANCELLED:
        return InvoiceStatus.CANCELLED

    paid_total = amount_paid if amount_paid is not None else get_invoice_amount_paid(invoice)
    if invoice.total_amount > Decimal("0.00") and paid_total >= invoice.total_amount:
        return InvoiceStatus.PAID
    if invoice.status == InvoiceStatus.DRAFT:
        return InvoiceStatus.DRAFT
    if invoice.due_date < timezone.localdate():
        return InvoiceStatus.OVERDUE
    return InvoiceStatus.SENT


def ensure_payments_fit_invoice_total(invoice: Invoice, total_amount: Decimal) -> None:
    paid_total = get_invoice_amount_paid(invoice)
    if paid_total > total_amount:
        raise ValidationError({"total_amount": "Invoice total cannot be less than the payments already recorded."})


@transaction.atomic
def sync_invoice_status(invoice: Invoice) -> Invoice:
    amount_paid = get_invoice_amount_paid(invoice)
    next_status = resolve_invoice_status(invoice, amount_paid=amount_paid)
    if next_status != invoice.status:
        invoice.status = next_status
        invoice.full_clean()
        invoice.save()
    return invoice


@transaction.atomic
def sync_invoices_status(invoices: list[Invoice]) -> list[Invoice]:
    for invoice in invoices:
        sync_invoice_status(invoice)
    return invoices


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

    total_amount = quantize_money(subtotal + tax_amount)
    ensure_payments_fit_invoice_total(invoice, total_amount)

    invoice.subtotal = subtotal
    invoice.tax_amount = tax_amount
    invoice.total_amount = total_amount
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


@transaction.atomic
def create_invoice_payment(invoice: Invoice, **payment_data) -> InvoicePayment:
    payment = InvoicePayment(invoice=invoice, **payment_data)
    payment.full_clean()
    payment.save()
    sync_invoice_status(invoice)
    return payment


@transaction.atomic
def update_invoice_payment(payment: InvoicePayment, **payment_data) -> InvoicePayment:
    for attr, value in payment_data.items():
        setattr(payment, attr, value)
    payment.full_clean()
    payment.save()
    sync_invoice_status(payment.invoice)
    return payment


@transaction.atomic
def regenerate_invoice_public_token(invoice: Invoice) -> Invoice:
    if not can_invoice_expose_payment_page(invoice):
        raise ValidationError({"payment_page": "A payment link is only available for unpaid active invoices."})
    invoice.public_token = generate_invoice_public_token()
    invoice.save(update_fields=["public_token", "updated_at"])
    return invoice


def add_months(source_date: date, months: int) -> date:
    year = source_date.year + ((source_date.month - 1 + months) // 12)
    month = ((source_date.month - 1 + months) % 12) + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def calculate_next_run_date(current_run_date: date, frequency: str) -> date:
    if frequency == RecurringInvoiceFrequency.WEEKLY:
        return current_run_date + timedelta(days=7)
    if frequency == RecurringInvoiceFrequency.MONTHLY:
        return add_months(current_run_date, 1)
    if frequency == RecurringInvoiceFrequency.QUARTERLY:
        return add_months(current_run_date, 3)
    raise ValidationError({"frequency": "Unsupported recurring invoice frequency."})


def resolve_recurring_next_run_date(start_date: date, frequency: str, reference_date: date | None = None) -> date:
    next_run_date = start_date
    effective_reference_date = reference_date or timezone.localdate()
    while next_run_date < effective_reference_date:
        next_run_date = calculate_next_run_date(next_run_date, frequency)
    return next_run_date


def advance_recurring_schedule(recurring_invoice: RecurringInvoice, scheduled_date: date) -> None:
    next_run_date = calculate_next_run_date(scheduled_date, recurring_invoice.frequency)
    if recurring_invoice.end_date and next_run_date > recurring_invoice.end_date:
        recurring_invoice.status = RecurringInvoiceStatus.CANCELLED
        recurring_invoice.next_run_date = None
    else:
        recurring_invoice.next_run_date = next_run_date
    recurring_invoice.full_clean()
    recurring_invoice.save()


def build_recurring_invoice_number(recurring_invoice: RecurringInvoice, issue_date: date) -> str:
    base_number = f"REC-{recurring_invoice.id}-{issue_date:%Y%m%d}"
    candidate = base_number
    suffix = 1
    while Invoice.objects.filter(invoice_number=candidate).exists():
        suffix += 1
        candidate = f"{base_number}-{suffix}"
    return candidate


@transaction.atomic
def generate_invoice_from_recurring(recurring_invoice: RecurringInvoice, run_date: date | None = None) -> Invoice | None:
    if recurring_invoice.status != RecurringInvoiceStatus.ACTIVE or not recurring_invoice.next_run_date:
        return None

    scheduled_date = recurring_invoice.next_run_date
    effective_run_date = run_date or timezone.localdate()
    if scheduled_date > effective_run_date:
        return None
    if recurring_invoice.end_date and scheduled_date > recurring_invoice.end_date:
        recurring_invoice.status = RecurringInvoiceStatus.CANCELLED
        recurring_invoice.next_run_date = None
        recurring_invoice.save(update_fields=["status", "next_run_date", "updated_at"])
        return None

    existing_invoice = Invoice.objects.filter(recurring_invoice=recurring_invoice, issue_date=scheduled_date).first()
    if existing_invoice:
        advance_recurring_schedule(recurring_invoice, scheduled_date)
        return None

    invoice = Invoice.objects.create(
        client=recurring_invoice.client,
        recurring_invoice=recurring_invoice,
        invoice_number=build_recurring_invoice_number(recurring_invoice, scheduled_date),
        issue_date=scheduled_date,
        due_date=scheduled_date + timedelta(days=recurring_invoice.payment_terms_days),
        status=InvoiceStatus.DRAFT,
        notes=recurring_invoice.notes,
        currency=recurring_invoice.currency,
        tax_type=recurring_invoice.tax_type,
        tax_rate=recurring_invoice.tax_rate,
    )
    replace_invoice_line_items(invoice, recurring_invoice.line_items_template)
    advance_recurring_schedule(recurring_invoice, scheduled_date)
    return invoice


@transaction.atomic
def process_due_recurring_invoices(run_date: date | None = None) -> list[Invoice]:
    effective_run_date = run_date or timezone.localdate()
    created_invoices: list[Invoice] = []
    recurring_invoices = RecurringInvoice.objects.select_related("client", "contractor").filter(
        status=RecurringInvoiceStatus.ACTIVE,
        next_run_date__isnull=False,
        next_run_date__lte=effective_run_date,
    )
    for recurring_invoice in recurring_invoices:
        recurring_invoice.refresh_from_db()
        while recurring_invoice.status == RecurringInvoiceStatus.ACTIVE and recurring_invoice.next_run_date:
            if recurring_invoice.next_run_date > effective_run_date:
                break
            invoice = generate_invoice_from_recurring(recurring_invoice, run_date=effective_run_date)
            if invoice:
                created_invoices.append(invoice)
            recurring_invoice.refresh_from_db()
    return created_invoices
