import base64
import json
import logging
from datetime import timedelta
from urllib import error, parse, request

from kombu.exceptions import OperationalError as KombuOperationalError
from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceStatus

logger = logging.getLogger(__name__)


class ReminderChannel(models.TextChoices):
    EMAIL = "email", "Email"
    WHATSAPP = "whatsapp", "WhatsApp"


class ReminderDeliveryError(Exception):
    pass


class EmailReminderProvider:
    def send(self, invoice: Invoice, subject: str, body: str) -> None:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.client.email],
        )


def get_client_invoice_url(invoice: Invoice) -> str:
    from apps.invoices.services import can_invoice_expose_payment_page

    if can_invoice_expose_payment_page(invoice):
        return f"{settings.FRONTEND_URL}/pay/{invoice.public_token}"
    return f"{settings.FRONTEND_URL}/invoices/{invoice.id}"


class ConsoleWhatsAppProvider:
    def send(self, phone_number: str, body: str) -> None:
        logger.info("WhatsApp reminder to %s: %s", phone_number, body)


class TwilioWhatsAppProvider:
    def send(self, phone_number: str, body: str) -> None:
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        from_number = settings.TWILIO_WHATSAPP_FROM
        if not account_sid or not auth_token or not from_number:
            raise ReminderDeliveryError("Twilio WhatsApp settings are incomplete.")

        payload = parse.urlencode(
            {
                "From": from_number,
                "To": phone_number,
                "Body": body,
            }
        ).encode("utf-8")
        req = request.Request(
            url=f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Basic {base64.b64encode(f'{account_sid}:{auth_token}'.encode()).decode()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with request.urlopen(req, timeout=10) as response:
                if response.status >= 400:
                    raise ReminderDeliveryError("Twilio rejected the WhatsApp reminder request.")
        except error.URLError as exc:
            raise ReminderDeliveryError(f"Unable to send WhatsApp reminder: {exc.reason}") from exc


def render_invoice_reminder(invoice: Invoice, template_name: str) -> str:
    context = {
        "invoice": invoice,
        "client": invoice.client,
        "frontend_url": settings.FRONTEND_URL,
        "invoice_url": get_client_invoice_url(invoice),
    }
    return render_to_string(template_name, context)


def get_whatsapp_provider():
    provider_name = (settings.WHATSAPP_PROVIDER or "").strip().lower()
    if not provider_name:
        raise ReminderDeliveryError("WhatsApp reminders are not configured.")
    if provider_name == "console":
        return ConsoleWhatsAppProvider()
    if provider_name == "twilio":
        return TwilioWhatsAppProvider()
    raise ReminderDeliveryError(f"Unsupported WhatsApp provider '{settings.WHATSAPP_PROVIDER}'.")


def validate_manual_invoice_reminder(invoice: Invoice, channel: str) -> None:
    if channel == ReminderChannel.WHATSAPP:
        if not invoice.client.phone_number:
            raise ReminderDeliveryError("This client does not have a phone number for WhatsApp reminders.")
        get_whatsapp_provider()


def deliver_manual_invoice_reminder(invoice_id: int, channel: str = ReminderChannel.EMAIL) -> None:
    invoice = Invoice.objects.select_related("client").prefetch_related("line_items", "payments").get(id=invoice_id)
    from apps.invoices.services import recalculate_invoice_totals

    recalculate_invoice_totals(invoice)
    send_invoice_reminder(
        invoice,
        "emails/manual_reminder.txt",
        f"Reminder: invoice {invoice.invoice_number} is awaiting payment",
        channel=channel,
    )


def send_recurring_invoice_created_email(invoice: Invoice) -> None:
    body = render_invoice_reminder(invoice, "emails/recurring_invoice_created.txt")
    EmailReminderProvider().send(
        invoice=invoice,
        subject=f"Invoice {invoice.invoice_number} is ready",
        body=body,
    )


def dispatch_manual_invoice_reminder(invoice: Invoice, channel: str = ReminderChannel.EMAIL) -> str:
    validate_manual_invoice_reminder(invoice, channel)
    from .tasks import enqueue_manual_invoice_reminder

    try:
        enqueue_manual_invoice_reminder.delay(invoice.id, channel)
        return "queued"
    except KombuOperationalError:
        logger.warning(
            "Celery broker unavailable; sending %s reminder inline for invoice %s.",
            channel,
            invoice.invoice_number,
        )
        deliver_manual_invoice_reminder(invoice.id, channel)
        return "sent"


def send_invoice_reminder(invoice: Invoice, template_name: str, subject: str, channel: str = ReminderChannel.EMAIL) -> None:
    body = render_invoice_reminder(invoice, template_name)
    if channel == ReminderChannel.EMAIL:
        EmailReminderProvider().send(invoice=invoice, subject=subject, body=body)
    elif channel == ReminderChannel.WHATSAPP:
        if not invoice.client.phone_number:
            raise ReminderDeliveryError("This client does not have a phone number for WhatsApp reminders.")
        provider = get_whatsapp_provider()
        provider.send(phone_number=invoice.client.phone_number, body=body)
    else:
        raise ReminderDeliveryError(f"Unsupported reminder channel '{channel}'.")

    invoice.reminder_last_sent_at = timezone.now()
    invoice.reminder_sent_count += 1
    invoice.save(update_fields=["reminder_last_sent_at", "reminder_sent_count"])


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
