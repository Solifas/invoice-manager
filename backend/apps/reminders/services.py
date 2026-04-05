from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceStatus


def send_invoice_reminder(invoice: Invoice, template_name: str, subject: str) -> None:
    context = {
        "invoice": invoice,
        "client": invoice.client,
        "frontend_url": settings.FRONTEND_URL,
    }
    body = render_to_string(template_name, context)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invoice.client.email],
    )
    invoice.reminder_last_sent_at = timezone.now()
    invoice.save(update_fields=["reminder_last_sent_at"])


def get_upcoming_due_invoices():
    today = timezone.localdate()
    due_limit = today + timedelta(days=settings.REMINDER_LEAD_DAYS)
    return Invoice.objects.select_related("client").filter(
        status__in=[InvoiceStatus.SENT, InvoiceStatus.OVERDUE],
        due_date__gte=today,
        due_date__lte=due_limit,
    )


def get_overdue_invoices():
    today = timezone.localdate()
    return Invoice.objects.select_related("client").filter(
        status__in=[InvoiceStatus.SENT, InvoiceStatus.OVERDUE],
        due_date__lt=today,
    )
