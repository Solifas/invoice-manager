from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from kombu.exceptions import OperationalError as KombuOperationalError
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.clients.models import Client
from apps.contractors.models import Contractor
from apps.invoices.models import (
    Invoice,
    InvoiceStatus,
    RecurringInvoice,
    RecurringInvoiceFrequency,
    RecurringInvoiceStatus,
    TaxType,
)
from apps.invoices.services import process_due_recurring_invoices, recalculate_invoice_totals
from apps.invoices.services import add_months


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class InvoicePhaseTwoTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner@example.test",
            email="owner@example.test",
            password="StrongPass123!",
        )
        self.client.force_authenticate(self.user)
        self.client_record = Client.objects.create(
            name="Acme Co",
            email="billing@acme.test",
            address="1 Main Street",
            phone_number="+27123456789",
        )
        self.contractor = Contractor.objects.create(
            name="Nora Dev",
            email="nora@example.test",
            contact_number="+27111222333",
            address="44 Workshop Street",
        )

    def create_invoice(self, **overrides) -> Invoice:
        invoice = Invoice.objects.create(
            client=self.client_record,
            invoice_number=overrides.pop("invoice_number", "INV-1001"),
            issue_date=overrides.pop("issue_date", date.today()),
            due_date=overrides.pop("due_date", date.today() + timedelta(days=14)),
            status=overrides.pop("status", InvoiceStatus.SENT),
            currency=overrides.pop("currency", "USD"),
            tax_type=overrides.pop("tax_type", TaxType.PERCENTAGE),
            tax_rate=overrides.pop("tax_rate", Decimal("15.00")),
            payment_page_enabled=overrides.pop("payment_page_enabled", True),
            eft_account_holder_name=overrides.pop("eft_account_holder_name", "Invoice Manager Pty Ltd"),
            eft_bank_name=overrides.pop("eft_bank_name", "Example Bank"),
            eft_account_number=overrides.pop("eft_account_number", "1234567890"),
            eft_account_type=overrides.pop("eft_account_type", "Business"),
            eft_branch_code=overrides.pop("eft_branch_code", "250655"),
            payment_reference=overrides.pop("payment_reference", ""),
            **overrides,
        )
        invoice.line_items.create(description="Design", quantity=2, unit_price=Decimal("100.00"))
        invoice.line_items.create(description="Hosting", quantity=1, unit_price=Decimal("50.00"))
        recalculate_invoice_totals(invoice)
        invoice.refresh_from_db()
        return invoice

    def test_invoice_create_api_recalculates_totals_and_exposes_payment_summary(self):
        payload = {
            "invoice_number": "INV-1002",
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=7)),
            "status": InvoiceStatus.DRAFT,
            "notes": "Thanks",
            "currency": "USD",
            "tax_type": TaxType.PERCENTAGE,
            "tax_rate": "10.00",
            "payment_page_enabled": True,
            "eft_account_holder_name": "Invoice Manager Pty Ltd",
            "eft_bank_name": "Example Bank",
            "eft_account_number": "1234567890",
            "eft_account_type": "Business",
            "eft_branch_code": "250655",
            "payment_reference": "",
            "client": {
                "name": "Nova Studio",
                "email": "accounts@nova.test",
                "address": "20 Market Road",
                "phone_number": "+27123456789",
            },
            "line_items": [
                {"description": "Consulting", "quantity": "3", "unit_price": "120.00"},
                {"description": "Support", "quantity": "1", "unit_price": "40.00"},
            ],
        }

        response = self.client.post(reverse("invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subtotal"], "400.00")
        self.assertEqual(response.data["tax_amount"], "40.00")
        self.assertEqual(response.data["total_amount"], "440.00")
        self.assertEqual(response.data["amount_paid"], "0.00")
        self.assertEqual(response.data["outstanding_amount"], "440.00")
        self.assertTrue(response.data["public_payment_url"].endswith(response.data["public_token"]))

    def test_partial_payments_update_invoice_amounts_and_status(self):
        invoice = self.create_invoice(invoice_number="INV-2001")

        first_response = self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {
                "amount": "100.00",
                "payment_date": str(date.today()),
                "payment_method": "eft",
                "reference": "PAY-001",
                "notes": "Deposit received",
            },
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        invoice.refresh_from_db()
        detail_response = self.client.get(reverse("invoice-detail", args=[invoice.id]))
        self.assertEqual(detail_response.data["amount_paid"], "100.00")
        self.assertEqual(detail_response.data["outstanding_amount"], "187.50")
        self.assertEqual(invoice.status, InvoiceStatus.SENT)
        self.assertEqual(len(detail_response.data["payments"]), 1)

        payment_id = first_response.data["id"]
        second_response = self.client.patch(
            reverse("payment-detail", args=[payment_id]),
            {"amount": "287.50", "payment_method": "eft"},
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

    def test_multiple_payments_mark_invoice_paid_when_total_is_fully_settled(self):
        invoice = self.create_invoice(invoice_number="INV-2001B")

        first_response = self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {"amount": "100.00", "payment_date": str(date.today())},
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {"amount": "187.50", "payment_date": str(date.today())},
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        detail_response = self.client.get(reverse("invoice-detail", args=[invoice.id]))

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["status"], InvoiceStatus.PAID)
        self.assertEqual(detail_response.data["amount_paid"], "287.50")
        self.assertEqual(detail_response.data["outstanding_amount"], "0.00")

    def test_payment_cannot_exceed_invoice_total(self):
        invoice = self.create_invoice(invoice_number="INV-2002")
        response = self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {
                "amount": "300.00",
                "payment_date": str(date.today()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)

    def test_invoice_create_rejects_decimal_quantity(self):
        payload = {
            "invoice_number": "INV-1009",
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=7)),
            "status": InvoiceStatus.DRAFT,
            "notes": "Decimal quantity should fail.",
            "currency": "USD",
            "tax_type": TaxType.NONE,
            "tax_rate": "0.00",
            "payment_page_enabled": False,
            "client": {
                "name": "Nova Studio",
                "email": "accounts-decimal@nova.test",
                "address": "20 Market Road",
                "phone_number": "+27123456789",
            },
            "line_items": [
                {"description": "Consulting", "quantity": "1.50", "unit_price": "120.00"},
            ],
        }

        response = self.client.post(reverse("invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("line_items", response.data)

    def test_dashboard_summary_uses_outstanding_amount_after_partial_payment(self):
        invoice = self.create_invoice(invoice_number="INV-2003")
        self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {"amount": "50.00", "payment_date": str(date.today())},
            format="json",
        )

        response = self.client.get(reverse("invoice-dashboard-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_invoices"], 1)
        self.assertEqual(response.data["unpaid_invoices"], 1)
        self.assertEqual(response.data["total_amount_outstanding"], "237.50")

    def test_invoice_list_supports_unpaid_status_group_filter(self):
        unpaid_invoice = self.create_invoice(invoice_number="INV-2003D", status=InvoiceStatus.SENT)
        paid_invoice = self.create_invoice(invoice_number="INV-2003E", status=InvoiceStatus.SENT)
        self.client.post(
            reverse("invoice-payments", args=[paid_invoice.id]),
            {"amount": "287.50", "payment_date": str(date.today())},
            format="json",
        )

        response = self.client.get(f"{reverse('invoice-list')}?status_group=unpaid")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice_numbers = {result["invoice_number"] for result in response.data["results"]}
        self.assertIn(unpaid_invoice.invoice_number, invoice_numbers)
        self.assertNotIn(paid_invoice.invoice_number, invoice_numbers)

    def test_invoice_detail_syncs_sent_invoice_to_overdue_when_past_due(self):
        invoice = self.create_invoice(
            invoice_number="INV-2003B",
            issue_date=date.today() - timedelta(days=14),
            due_date=date.today() - timedelta(days=2),
            status=InvoiceStatus.SENT,
        )
        Invoice.objects.filter(id=invoice.id).update(status=InvoiceStatus.SENT)

        response = self.client.get(reverse("invoice-detail", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], InvoiceStatus.OVERDUE)

    def test_cancelled_invoice_status_is_preserved_on_reads(self):
        invoice = self.create_invoice(
            invoice_number="INV-2003C",
            issue_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=10),
            status=InvoiceStatus.CANCELLED,
        )

        response = self.client.get(reverse("invoice-detail", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], InvoiceStatus.CANCELLED)

    def test_invoice_pdf_endpoint_returns_pdf(self):
        invoice = self.create_invoice(invoice_number="INV-2004")

        response = self.client.get(reverse("invoice-pdf", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(b"%PDF", response.content[:10])

    def test_public_payment_page_returns_expected_payload(self):
        invoice = self.create_invoice(invoice_number="INV-3001")
        self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {"amount": "87.50", "payment_date": str(date.today())},
            format="json",
        )

        response = self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["invoice_number"], "INV-3001")
        self.assertEqual(response.data["client_name"], self.client_record.name)
        self.assertEqual(response.data["amount_paid"], "87.50")
        self.assertEqual(response.data["outstanding_amount"], "200.00")
        self.assertEqual(response.data["payment_reference"], "INV-3001")
        self.assertEqual(response.data["eft_details"]["bank_name"], "Example Bank")

    def test_public_payment_page_returns_not_found_for_invalid_or_disabled_tokens(self):
        invoice = self.create_invoice(invoice_number="INV-3002", payment_page_enabled=False)

        invalid_response = self.client.get(reverse("public-invoice-payment", args=["missing-token"]))
        disabled_response = self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))

        self.assertEqual(invalid_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(disabled_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_paid_invoice_does_not_expose_public_payment_url(self):
        invoice = self.create_invoice(invoice_number="INV-3002B")
        self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {"amount": "287.50", "payment_date": str(date.today())},
            format="json",
        )

        response = self.client.get(reverse("invoice-detail", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], InvoiceStatus.PAID)
        self.assertEqual(response.data["public_payment_url"], "")
        self.assertFalse(response.data["payment_link_available"])

    def test_paid_invoice_cannot_regenerate_payment_page_token(self):
        invoice = self.create_invoice(invoice_number="INV-3002C")
        self.client.post(
            reverse("invoice-payments", args=[invoice.id]),
            {"amount": "287.50", "payment_date": str(date.today())},
            format="json",
        )

        response = self.client.post(reverse("invoice-regenerate-payment-page-token", args=[invoice.id]), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_page", response.data)

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_remind_endpoint_dispatches_whatsapp_when_configured(self):
        invoice = self.create_invoice(invoice_number="INV-4001")

        response = self.client.post(
            reverse("invoice-remind", args=[invoice.id]),
            {"channel": "whatsapp"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        invoice.refresh_from_db()
        self.assertIsNotNone(invoice.reminder_last_sent_at)

    def test_remind_endpoint_rejects_whatsapp_when_phone_missing(self):
        self.client_record.phone_number = ""
        self.client_record.save(update_fields=["phone_number"])
        invoice = self.create_invoice(invoice_number="INV-4002")

        response = self.client.post(
            reverse("invoice-remind", args=[invoice.id]),
            {"channel": "whatsapp"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "This client does not have a phone number for WhatsApp reminders.")

    def test_send_reminder_endpoint_preserves_email_compatibility(self):
        invoice = self.create_invoice(invoice_number="INV-4003")

        response = self.client.post(reverse("invoice-send-reminder", args=[invoice.id]), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invoice.invoice_number, mail.outbox[0].subject)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False, CELERY_TASK_EAGER_PROPAGATES=False)
    @patch("apps.reminders.tasks.enqueue_manual_invoice_reminder.delay", side_effect=KombuOperationalError("redis offline"))
    def test_remind_endpoint_falls_back_to_inline_email_when_broker_is_unavailable(self, mocked_delay):
        invoice = self.create_invoice(invoice_number="INV-4004")

        response = self.client.post(
            reverse("invoice-remind", args=[invoice.id]),
            {"channel": "email"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["detail"], "Email reminder sent.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invoice.invoice_number, mail.outbox[0].subject)
        mocked_delay.assert_called_once_with(invoice.id, "email")

    def test_recurring_invoice_generation_creates_invoice_and_advances_schedule(self):
        recurring_invoice = RecurringInvoice.objects.create(
            client=self.client_record,
            contractor=self.contractor,
            template_name="Monthly Retainer",
            frequency=RecurringInvoiceFrequency.MONTHLY,
            start_date=date.today(),
            next_run_date=date.today(),
            status=RecurringInvoiceStatus.ACTIVE,
            currency="USD",
            payment_terms_days=7,
            tax_type=TaxType.PERCENTAGE,
            tax_rate=Decimal("10.00"),
            notes="Generated automatically.",
            line_items_template=[
                {"description": "Retainer", "quantity": "1", "unit_price": "500.00"},
                {"description": "Reporting", "quantity": "1", "unit_price": "100.00"},
            ],
        )

        created = process_due_recurring_invoices(run_date=date.today())

        self.assertEqual(len(created), 1)
        generated_invoice = created[0]
        self.assertEqual(generated_invoice.recurring_invoice_id, recurring_invoice.id)
        self.assertEqual(generated_invoice.subtotal, Decimal("600.00"))
        self.assertEqual(generated_invoice.tax_amount, Decimal("60.00"))
        self.assertEqual(generated_invoice.total_amount, Decimal("660.00"))

        recurring_invoice.refresh_from_db()
        self.assertEqual(recurring_invoice.next_run_date, add_months(date.today(), 1))

    def test_recurring_invoice_generation_avoids_duplicates(self):
        recurring_invoice = RecurringInvoice.objects.create(
            client=self.client_record,
            template_name="Weekly Support",
            frequency=RecurringInvoiceFrequency.WEEKLY,
            start_date=date.today(),
            next_run_date=date.today(),
            status=RecurringInvoiceStatus.ACTIVE,
            currency="USD",
            payment_terms_days=7,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            line_items_template=[
                {"description": "Support", "quantity": "1", "unit_price": "250.00"},
            ],
        )

        first_run = process_due_recurring_invoices(run_date=date.today())
        second_run = process_due_recurring_invoices(run_date=date.today())

        self.assertEqual(len(first_run), 1)
        self.assertEqual(len(second_run), 0)
        self.assertEqual(Invoice.objects.filter(recurring_invoice=recurring_invoice).count(), 1)

    def test_recurring_invoice_api_create_and_soft_delete(self):
        payload = {
            "template_name": "Quarterly Audit",
            "client_id": self.client_record.id,
            "contractor_id": self.contractor.id,
            "frequency": "quarterly",
            "start_date": str(date.today()),
            "next_run_date": str(date.today()),
            "status": "active",
            "currency": "USD",
            "payment_terms_days": 14,
            "tax_type": "none",
            "tax_rate": "0.00",
            "notes": "Quarterly recurring work.",
            "line_items_template": [
                {"description": "Audit", "quantity": "1", "unit_price": "900.00"},
            ],
        }

        create_response = self.client.post(reverse("recurring-invoice-list"), payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        recurring_id = create_response.data["id"]
        delete_response = self.client.delete(reverse("recurring-invoice-detail", args=[recurring_id]))
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        recurring = RecurringInvoice.objects.get(id=recurring_id)
        self.assertEqual(recurring.status, RecurringInvoiceStatus.CANCELLED)
        self.assertIsNone(recurring.next_run_date)

    def test_recurring_invoice_api_rejects_decimal_quantity(self):
        payload = {
            "template_name": "Quarterly Audit",
            "client_id": self.client_record.id,
            "frequency": "quarterly",
            "start_date": str(date.today()),
            "next_run_date": str(date.today()),
            "status": "active",
            "currency": "USD",
            "payment_terms_days": 14,
            "tax_type": "none",
            "tax_rate": "0.00",
            "notes": "Quarterly recurring work.",
            "line_items_template": [
                {"description": "Audit", "quantity": "1.50", "unit_price": "900.00"},
            ],
        }

        response = self.client.post(reverse("recurring-invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("line_items_template", response.data)

    def test_recurring_invoice_api_computes_next_run_date_from_schedule(self):
        payload = {
            "template_name": "Weekly Support",
            "client_id": self.client_record.id,
            "frequency": "weekly",
            "start_date": str(date.today() - timedelta(days=7)),
            "status": "active",
            "currency": "USD",
            "payment_terms_days": 14,
            "tax_type": "none",
            "tax_rate": "0.00",
            "notes": "Weekly recurring work.",
            "line_items_template": [
                {"description": "Support", "quantity": "1", "unit_price": "250.00"},
            ],
        }

        response = self.client.post(reverse("recurring-invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["next_run_date"], str(date.today()))

    def test_process_due_recurring_invoices_catches_up_missed_runs(self):
        recurring_invoice = RecurringInvoice.objects.create(
            client=self.client_record,
            template_name="Weekly Support",
            frequency=RecurringInvoiceFrequency.WEEKLY,
            start_date=date.today() - timedelta(days=21),
            next_run_date=date.today() - timedelta(days=21),
            status=RecurringInvoiceStatus.ACTIVE,
            currency="USD",
            payment_terms_days=7,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            line_items_template=[
                {"description": "Support", "quantity": "1", "unit_price": "250.00"},
            ],
        )

        created = process_due_recurring_invoices(run_date=date.today())

        self.assertEqual(len(created), 4)
        recurring_invoice.refresh_from_db()
        self.assertEqual(recurring_invoice.next_run_date, date.today() + timedelta(days=7))

    def test_lookup_endpoints_return_clients_and_contractors(self):
        client_response = self.client.get(reverse("client-list"))
        contractor_response = self.client.get(reverse("contractor-list"))

        self.assertEqual(client_response.status_code, status.HTTP_200_OK)
        self.assertEqual(contractor_response.status_code, status.HTTP_200_OK)
        self.assertEqual(client_response.data[0]["name"], self.client_record.name)
        self.assertEqual(contractor_response.data[0]["name"], self.contractor.name)
