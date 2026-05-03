from celery import shared_task

from apps.invoices.services import process_due_recurring_invoices, recalculate_invoice_totals

from .services import (
    ReminderChannel,
    deliver_manual_invoice_reminder,
    get_overdue_invoices,
    get_upcoming_due_invoices,
    send_invoice_reminder,
    send_recurring_invoice_created_email,
)


@shared_task
def enqueue_manual_invoice_reminder(invoice_id: int, channel: str = ReminderChannel.EMAIL) -> None:
    deliver_manual_invoice_reminder(invoice_id, channel)


@shared_task
def send_automatic_invoice_reminders() -> None:
    for invoice in get_upcoming_due_invoices():
        recalculate_invoice_totals(invoice)
        send_invoice_reminder(
            invoice,
            "emails/upcoming_due.txt",
            f"Upcoming due date for invoice {invoice.invoice_number}",
            channel=ReminderChannel.EMAIL,
        )

    for invoice in get_overdue_invoices():
        recalculate_invoice_totals(invoice)
        send_invoice_reminder(
            invoice,
            "emails/overdue.txt",
            f"Invoice {invoice.invoice_number} is overdue",
            channel=ReminderChannel.EMAIL,
        )


@shared_task
def generate_recurring_invoices() -> None:
    for invoice in process_due_recurring_invoices():
        recalculate_invoice_totals(invoice)
        send_recurring_invoice_created_email(invoice)
