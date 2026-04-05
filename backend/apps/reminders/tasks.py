from celery import shared_task

from apps.invoices.models import Invoice
from apps.invoices.services import recalculate_invoice_totals

from .services import get_overdue_invoices, get_upcoming_due_invoices, send_invoice_reminder


@shared_task
def enqueue_manual_invoice_reminder(invoice_id: int) -> None:
    invoice = Invoice.objects.select_related("client").prefetch_related("line_items").get(id=invoice_id)
    recalculate_invoice_totals(invoice)
    send_invoice_reminder(
        invoice,
        "emails/manual_reminder.txt",
        f"Reminder: invoice {invoice.invoice_number} is awaiting payment",
    )


@shared_task
def send_automatic_invoice_reminders() -> None:
    for invoice in get_upcoming_due_invoices():
        recalculate_invoice_totals(invoice)
        send_invoice_reminder(
            invoice,
            "emails/upcoming_due.txt",
            f"Upcoming due date for invoice {invoice.invoice_number}",
        )

    for invoice in get_overdue_invoices():
        recalculate_invoice_totals(invoice)
        send_invoice_reminder(
            invoice,
            "emails/overdue.txt",
            f"Invoice {invoice.invoice_number} is overdue",
        )
