from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from kombu.exceptions import OperationalError as KombuOperationalError
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserBankingProfile
from apps.clients.models import Client
from apps.contractors.models import Contractor
from apps.invoices.models import (
    CurrencyCode,
    Invoice,
    InvoiceEftSourceType,
    InvoiceStatus,
    RecurringInvoice,
    RecurringInvoiceFrequency,
    RecurringInvoiceStatus,
    TaxType,
)
from apps.invoices.currencies import CURRENCY_CATALOG
from apps.invoices.services import process_due_recurring_invoices, recalculate_invoice_totals
from apps.invoices.services import add_months
from apps.reminders.tasks import generate_recurring_invoices


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
        self.other_user = User.objects.create_user(
            username="other@example.test",
            email="other@example.test",
            password="StrongPass123!",
        )
        self.client.force_authenticate(self.user)
        self.client_record = Client.objects.create(
            owner=self.user,
            name="Acme Co",
            email="billing@acme.test",
            address="1 Main Street",
            phone_number="+27123456789",
        )
        self.contractor = Contractor.objects.create(
            owner=self.user,
            name="Nora Dev",
            email="nora@example.test",
            contact_number="+27111222333",
            address="44 Workshop Street",
        )
        self.banking_profile = UserBankingProfile.objects.create(
            user=self.user,
            profile_name="Primary Business Account",
            account_holder_name="Invoice Manager Pty Ltd",
            bank_name="FNB",
            account_number="1234567890",
            account_type="Business",
            branch_code="250655",
            default_payment_reference="DEFAULT-REF",
            is_default=True,
        )

    def create_invoice(self, **overrides) -> Invoice:
        invoice = Invoice.objects.create(
            owner=overrides.pop("owner", self.user),
            client=self.client_record,
            invoice_number=overrides.pop("invoice_number", "INV-1001"),
            issue_date=overrides.pop("issue_date", date.today()),
            due_date=overrides.pop("due_date", date.today() + timedelta(days=14)),
            status=overrides.pop("status", InvoiceStatus.SENT),
            currency=overrides.pop("currency", CurrencyCode.USD),
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
            "currency": CurrencyCode.USD,
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
        self.assertEqual(Invoice.objects.get(id=response.data["id"]).owner, self.user)
        self.assertEqual(Client.objects.get(email="accounts@nova.test", owner=self.user).owner, self.user)

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
            "currency": CurrencyCode.USD,
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

    def test_invoice_create_accepts_currency_from_catalog(self):
        payload = {
            "invoice_number": "INV-1010",
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=7)),
            "status": InvoiceStatus.DRAFT,
            "notes": "Catalog currency should pass.",
            "currency": "EUR",
            "tax_type": TaxType.NONE,
            "tax_rate": "0.00",
            "payment_page_enabled": False,
            "client": {
                "name": "Nova Studio",
                "email": "accounts-eur@nova.test",
                "address": "20 Market Road",
                "phone_number": "+27123456789",
            },
            "line_items": [
                {"description": "Consulting", "quantity": "1", "unit_price": "120.00"},
            ],
        }

        response = self.client.post(reverse("invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["currency"], "EUR")

    def test_invoice_create_rejects_unknown_currency(self):
        payload = {
            "invoice_number": "INV-1010B",
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=7)),
            "status": InvoiceStatus.DRAFT,
            "notes": "Unknown currency should fail.",
            "currency": "INVALID",
            "tax_type": TaxType.NONE,
            "tax_rate": "0.00",
            "payment_page_enabled": False,
            "client": {
                "name": "Nova Studio",
                "email": "accounts-invalid@nova.test",
                "address": "20 Market Road",
                "phone_number": "+27123456789",
            },
            "line_items": [
                {"description": "Consulting", "quantity": "1", "unit_price": "120.00"},
            ],
        }

        response = self.client.post(reverse("invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("currency", response.data)

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

    def test_collections_summary_covers_overdue_upcoming_paid_cancelled_and_draft_invoices(self):
        today = timezone.localdate()
        overdue_old = self.create_invoice(
            invoice_number="INV-COL-001",
            issue_date=today - timedelta(days=40),
            due_date=today - timedelta(days=30),
            status=InvoiceStatus.SENT,
        )
        overdue_new = self.create_invoice(
            invoice_number="INV-COL-002",
            issue_date=today - timedelta(days=20),
            due_date=today - timedelta(days=5),
            status=InvoiceStatus.SENT,
        )
        upcoming = self.create_invoice(
            invoice_number="INV-COL-003",
            issue_date=today - timedelta(days=2),
            due_date=today + timedelta(days=4),
            status=InvoiceStatus.SENT,
        )
        paid = self.create_invoice(
            invoice_number="INV-COL-004",
            issue_date=today - timedelta(days=5),
            due_date=today + timedelta(days=5),
            status=InvoiceStatus.SENT,
        )
        cancelled = self.create_invoice(
            invoice_number="INV-COL-005",
            issue_date=today - timedelta(days=40),
            due_date=today - timedelta(days=20),
            status=InvoiceStatus.CANCELLED,
        )
        draft = self.create_invoice(
            invoice_number="INV-COL-006",
            issue_date=today - timedelta(days=10),
            due_date=today - timedelta(days=3),
            status=InvoiceStatus.DRAFT,
        )

        self.client.post(
            reverse("invoice-payments", args=[overdue_old.id]),
            {"amount": "87.50", "payment_date": str(today)},
            format="json",
        )
        self.client.post(
            reverse("invoice-payments", args=[paid.id]),
            {"amount": "287.50", "payment_date": str(today)},
            format="json",
        )
        self.client.post(
            reverse("invoice-payments", args=[cancelled.id]),
            {"amount": "50.00", "payment_date": str(today)},
            format="json",
        )

        response = self.client.get(reverse("invoice-dashboard-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_amount_outstanding"], "1062.50")
        self.assertEqual(response.data["total_overdue_amount"], "487.50")
        self.assertEqual(response.data["overdue_invoices"], 2)
        self.assertEqual(response.data["due_next_7_days_invoices"], 1)
        self.assertEqual(response.data["paid_invoices_this_month"], 2)
        self.assertEqual(response.data["collected_amount_this_month"], "375.00")
        self.assertEqual(response.data["oldest_overdue_invoice"]["invoice_number"], overdue_old.invoice_number)
        self.assertEqual(
            [invoice["invoice_number"] for invoice in response.data["overdue_invoice_table"]],
            [overdue_old.invoice_number, overdue_new.invoice_number],
        )
        self.assertNotIn(draft.invoice_number, [invoice["invoice_number"] for invoice in response.data["overdue_invoice_table"]])
        self.assertNotIn(cancelled.invoice_number, [invoice["invoice_number"] for invoice in response.data["overdue_invoice_table"]])

    def test_collections_analytics_calculates_recovery_metrics_ageing_and_risk(self):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        month_unpaid = self.create_invoice(
            invoice_number="INV-AN-001",
            issue_date=month_start,
            due_date=today + timedelta(days=7),
            status=InvoiceStatus.SENT,
        )
        paid = self.create_invoice(
            invoice_number="INV-AN-002",
            issue_date=month_start,
            due_date=today,
            status=InvoiceStatus.SENT,
        )
        overdue_1_to_7 = self.create_invoice(
            invoice_number="INV-AN-003",
            issue_date=today - timedelta(days=14),
            due_date=today - timedelta(days=3),
            status=InvoiceStatus.SENT,
        )
        overdue_8_to_14 = self.create_invoice(
            invoice_number="INV-AN-004",
            issue_date=today - timedelta(days=24),
            due_date=today - timedelta(days=10),
            status=InvoiceStatus.SENT,
        )
        overdue_15_to_30 = self.create_invoice(
            invoice_number="INV-AN-005",
            issue_date=today - timedelta(days=35),
            due_date=today - timedelta(days=20),
            status=InvoiceStatus.SENT,
        )
        overdue_15_to_30.reminder_sent_count = 2
        overdue_15_to_30.save(update_fields=["reminder_sent_count", "updated_at"])
        overdue_31_plus = self.create_invoice(
            invoice_number="INV-AN-006",
            issue_date=today - timedelta(days=55),
            due_date=today - timedelta(days=40),
            status=InvoiceStatus.SENT,
        )
        cancelled = self.create_invoice(
            invoice_number="INV-AN-007",
            issue_date=month_start,
            due_date=today,
            status=InvoiceStatus.CANCELLED,
        )

        self.client.post(
            reverse("invoice-payments", args=[paid.id]),
            {"amount": "287.50", "payment_date": str(today)},
            format="json",
        )
        self.client.post(
            reverse("invoice-payments", args=[overdue_15_to_30.id]),
            {"amount": "87.50", "payment_date": str(today)},
            format="json",
        )

        response = self.client.get(reverse("invoice-collections-analytics"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_invoiced_this_month"], "575.00")
        self.assertEqual(response.data["total_collected_this_month"], "375.00")
        self.assertEqual(response.data["total_outstanding"], "1350.00")
        self.assertEqual(response.data["total_overdue"], "1062.50")
        self.assertEqual(response.data["collection_rate_percentage"], "65.22")
        self.assertEqual(response.data["average_days_to_payment"], float((today - month_start).days))
        self.assertEqual(response.data["overdue_ageing_buckets"]["one_to_seven_days"], {"count": 1, "amount": "287.50"})
        self.assertEqual(response.data["overdue_ageing_buckets"]["eight_to_fourteen_days"], {"count": 1, "amount": "287.50"})
        self.assertEqual(response.data["overdue_ageing_buckets"]["fifteen_to_thirty_days"], {"count": 1, "amount": "200.00"})
        self.assertEqual(response.data["overdue_ageing_buckets"]["thirty_one_plus_days"], {"count": 1, "amount": "287.50"})
        high_risk_numbers = {invoice["invoice_number"] for invoice in response.data["high_risk_invoices"]}
        self.assertIn(overdue_15_to_30.invoice_number, high_risk_numbers)
        self.assertIn(overdue_31_plus.invoice_number, high_risk_numbers)
        self.assertNotIn(overdue_8_to_14.invoice_number, high_risk_numbers)
        self.assertNotIn(cancelled.invoice_number, high_risk_numbers)
        self.assertNotIn(month_unpaid.invoice_number, high_risk_numbers)

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
        invoice.eft_profile_name = "Primary Business Account"
        invoice.eft_source_type = InvoiceEftSourceType.SAVED_PROFILE
        invoice.eft_source_profile = self.banking_profile
        invoice.save(update_fields=["eft_profile_name", "eft_source_type", "eft_source_profile", "updated_at"])
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
        self.assertEqual(response.data["eft_details"]["profile_name"], "Primary Business Account")
        self.assertEqual(response.data["eft_details"]["bank_name"], "Example Bank")

    def test_public_payment_page_open_updates_link_activity(self):
        invoice = self.create_invoice(invoice_number="INV-3001A")
        self.assertEqual(invoice.payment_page_open_count, 0)
        self.assertIsNone(invoice.payment_page_first_opened_at)
        self.assertIsNone(invoice.payment_page_last_opened_at)

        first_response = self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))
        invoice.refresh_from_db()
        first_opened_at = invoice.payment_page_first_opened_at
        first_last_opened_at = invoice.payment_page_last_opened_at

        second_response = self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))
        invoice.refresh_from_db()

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(invoice.payment_page_open_count, 2)
        self.assertIsNotNone(first_opened_at)
        self.assertIsNotNone(first_last_opened_at)
        self.assertEqual(invoice.payment_page_first_opened_at, first_opened_at)
        self.assertGreaterEqual(invoice.payment_page_last_opened_at, first_last_opened_at)

    def test_public_payment_page_returns_not_found_for_invalid_or_disabled_tokens(self):
        invoice = self.create_invoice(invoice_number="INV-3002", payment_page_enabled=False)

        invalid_response = self.client.get(reverse("public-invoice-payment", args=["missing-token"]))
        disabled_response = self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))

        self.assertEqual(invalid_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(disabled_response.status_code, status.HTTP_404_NOT_FOUND)
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_page_open_count, 0)

    def test_invoice_owner_can_view_payment_link_activity(self):
        invoice = self.create_invoice(invoice_number="INV-3002A")
        self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))

        response = self.client.get(reverse("invoice-payment-link-activity", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["payment_page_enabled"])
        self.assertEqual(response.data["public_token"], invoice.public_token)
        self.assertTrue(response.data["public_payment_url"].endswith(invoice.public_token))
        self.assertEqual(response.data["payment_page_open_count"], 1)
        self.assertIsNotNone(response.data["payment_page_first_opened_at"])
        self.assertIsNotNone(response.data["payment_page_last_opened_at"])
        self.assertIn("reminder_last_sent_at", response.data)

    def test_other_user_cannot_view_payment_link_activity(self):
        invoice = self.create_invoice(invoice_number="INV-3002AA")
        other_client = Client.objects.create(
            owner=self.other_user,
            name="Other Co",
            email="other-payment-activity@example.test",
            address="2 Side Street",
        )
        other_invoice = Invoice.objects.create(
            owner=self.other_user,
            client=other_client,
            invoice_number="INV-OTHER-ACTIVITY",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency=CurrencyCode.ZAR,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            payment_page_enabled=True,
        )

        own_response = self.client.get(reverse("invoice-payment-link-activity", args=[invoice.id]))
        other_response = self.client.get(reverse("invoice-payment-link-activity", args=[other_invoice.id]))

        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regenerating_payment_token_records_date_resets_current_link_activity_and_invalidates_old_token(self):
        invoice = self.create_invoice(invoice_number="INV-3002AB")
        old_token = invoice.public_token
        self.client.get(reverse("public-invoice-payment", args=[old_token]))

        response = self.client.post(reverse("invoice-regenerate-payment-page-token", args=[invoice.id]), {}, format="json")
        invoice.refresh_from_db()

        old_token_response = self.client.get(reverse("public-invoice-payment", args=[old_token]))
        new_token_response = self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(invoice.public_token, old_token)
        self.assertIsNotNone(invoice.public_token_regenerated_at)
        self.assertEqual(response.data["public_token"], invoice.public_token)
        self.assertEqual(invoice.payment_page_open_count, 0)
        self.assertIsNone(invoice.payment_page_first_opened_at)
        self.assertIsNone(invoice.payment_page_last_opened_at)
        self.assertEqual(old_token_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(new_token_response.status_code, status.HTTP_200_OK)

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
            owner=self.user,
            client=self.client_record,
            contractor=self.contractor,
            template_name="Monthly Retainer",
            frequency=RecurringInvoiceFrequency.MONTHLY,
            start_date=date.today(),
            next_run_date=date.today(),
            status=RecurringInvoiceStatus.ACTIVE,
            currency=CurrencyCode.USD,
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
        self.assertEqual(generated_invoice.status, InvoiceStatus.SENT)
        self.assertTrue(generated_invoice.payment_page_enabled)
        self.assertEqual(generated_invoice.eft_source_profile, self.banking_profile)
        self.assertEqual(generated_invoice.eft_bank_name, self.banking_profile.bank_name)

        recurring_invoice.refresh_from_db()
        self.assertEqual(recurring_invoice.next_run_date, add_months(date.today(), 1))

    def test_recurring_invoice_generation_avoids_duplicates(self):
        recurring_invoice = RecurringInvoice.objects.create(
            owner=self.user,
            client=self.client_record,
            template_name="Weekly Support",
            frequency=RecurringInvoiceFrequency.WEEKLY,
            start_date=date.today(),
            next_run_date=date.today(),
            status=RecurringInvoiceStatus.ACTIVE,
            currency=CurrencyCode.USD,
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

    def test_recurring_invoice_task_emails_generated_invoice(self):
        today = timezone.localdate()
        recurring_invoice = RecurringInvoice.objects.create(
            owner=self.user,
            client=self.client_record,
            template_name="Monthly Email Retainer",
            frequency=RecurringInvoiceFrequency.MONTHLY,
            start_date=today,
            next_run_date=today,
            status=RecurringInvoiceStatus.ACTIVE,
            currency=CurrencyCode.USD,
            payment_terms_days=7,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            line_items_template=[
                {"description": "Support", "quantity": "1", "unit_price": "250.00"},
            ],
        )

        generate_recurring_invoices()

        generated_invoice = Invoice.objects.get(recurring_invoice=recurring_invoice)
        self.assertEqual(generated_invoice.status, InvoiceStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.client_record.email])
        self.assertIn(generated_invoice.invoice_number, mail.outbox[0].subject)
        self.assertIn(f"/pay/{generated_invoice.public_token}", mail.outbox[0].body)

    def test_recurring_invoice_api_create_and_soft_delete(self):
        payload = {
            "template_name": "Quarterly Audit",
            "client_id": self.client_record.id,
            "contractor_id": self.contractor.id,
            "frequency": "quarterly",
            "start_date": str(date.today()),
            "next_run_date": str(date.today()),
            "status": "active",
            "currency": CurrencyCode.USD,
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
            "currency": CurrencyCode.USD,
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

    def test_recurring_invoice_api_accepts_currency_from_catalog(self):
        payload = {
            "template_name": "Quarterly Audit",
            "client_id": self.client_record.id,
            "frequency": "quarterly",
            "start_date": str(date.today()),
            "status": "active",
            "currency": "EUR",
            "payment_terms_days": 14,
            "tax_type": "none",
            "tax_rate": "0.00",
            "notes": "Quarterly recurring work.",
            "line_items_template": [
                {"description": "Audit", "quantity": "1", "unit_price": "900.00"},
            ],
        }

        response = self.client.post(reverse("recurring-invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["currency"], "EUR")

    def test_recurring_invoice_api_rejects_unknown_currency(self):
        payload = {
            "template_name": "Quarterly Audit",
            "client_id": self.client_record.id,
            "frequency": "quarterly",
            "start_date": str(date.today()),
            "status": "active",
            "currency": "INVALID",
            "payment_terms_days": 14,
            "tax_type": "none",
            "tax_rate": "0.00",
            "notes": "Quarterly recurring work.",
            "line_items_template": [
                {"description": "Audit", "quantity": "1", "unit_price": "900.00"},
            ],
        }

        response = self.client.post(reverse("recurring-invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("currency", response.data)

    def test_recurring_invoice_api_computes_next_run_date_from_schedule(self):
        payload = {
            "template_name": "Weekly Support",
            "client_id": self.client_record.id,
            "frequency": "weekly",
            "start_date": str(date.today() - timedelta(days=7)),
            "status": "active",
            "currency": CurrencyCode.USD,
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
            owner=self.user,
            client=self.client_record,
            template_name="Weekly Support",
            frequency=RecurringInvoiceFrequency.WEEKLY,
            start_date=date.today() - timedelta(days=21),
            next_run_date=date.today() - timedelta(days=21),
            status=RecurringInvoiceStatus.ACTIVE,
            currency=CurrencyCode.USD,
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

    def test_contractor_endpoint_creates_and_updates_owner_scoped_contractors(self):
        create_response = self.client.post(
            reverse("contractor-list"),
            {
                "name": "Solifas Salimu",
                "email": "solifas@extratrx.com",
                "contact_number": "0812344514",
                "address": "Johannesburg",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        contractor = Contractor.objects.get(id=create_response.data["id"])
        self.assertEqual(contractor.owner, self.user)
        self.assertEqual(contractor.email, "solifas@extratrx.com")

        update_response = self.client.patch(
            reverse("contractor-detail", args=[contractor.id]),
            {"contact_number": "0812344515"},
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        contractor.refresh_from_db()
        self.assertEqual(contractor.contact_number, "0812344515")

        other_contractor = Contractor.objects.create(owner=self.other_user, name="Hidden Contractor")
        blocked_response = self.client.patch(
            reverse("contractor-detail", args=[other_contractor.id]),
            {"name": "Should not update"},
            format="json",
        )

        self.assertEqual(blocked_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_currency_list_endpoint_returns_catalog(self):
        response = self.client.get(reverse("currency-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 100)
        self.assertEqual(response.data[0], {"code": "AED", "name": CURRENCY_CATALOG["AED"]})
        self.assertIn({"code": "ZAR", "name": CURRENCY_CATALOG["ZAR"]}, response.data)

    def test_user_only_sees_their_own_invoices_and_dashboard_data(self):
        other_client = Client.objects.create(
            owner=self.other_user,
            name="Other Co",
            email="other-client@example.test",
            address="2 Side Street",
            phone_number="+27110000000",
        )
        other_invoice = Invoice.objects.create(
            owner=self.other_user,
            client=other_client,
            invoice_number="INV-OTHER-001",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency=CurrencyCode.USD,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
        )
        other_invoice.line_items.create(description="Other work", quantity=1, unit_price=Decimal("200.00"))
        recalculate_invoice_totals(other_invoice)

        own_invoice = self.create_invoice(invoice_number="INV-OWN-001")

        list_response = self.client.get(reverse("invoice-list"))
        summary_response = self.client.get(reverse("invoice-dashboard-summary"))

        invoice_numbers = {result["invoice_number"] for result in list_response.data["results"]}
        self.assertIn(own_invoice.invoice_number, invoice_numbers)
        self.assertNotIn(other_invoice.invoice_number, invoice_numbers)
        self.assertEqual(summary_response.data["total_invoices"], 1)

    def test_user_cannot_access_another_users_invoice_or_recurring_template(self):
        other_client = Client.objects.create(
            owner=self.other_user,
            name="Other Co",
            email="other-client-2@example.test",
            address="2 Side Street",
            phone_number="+27110000001",
        )
        other_invoice = Invoice.objects.create(
            owner=self.other_user,
            client=other_client,
            invoice_number="INV-OTHER-002",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency=CurrencyCode.USD,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
        )
        other_invoice.line_items.create(description="Other work", quantity=1, unit_price=Decimal("200.00"))
        recalculate_invoice_totals(other_invoice)

        other_contractor = Contractor.objects.create(owner=self.other_user, name="Other Contractor")
        other_recurring = RecurringInvoice.objects.create(
            owner=self.other_user,
            client=other_client,
            contractor=other_contractor,
            template_name="Other Retainer",
            frequency=RecurringInvoiceFrequency.MONTHLY,
            start_date=date.today(),
            next_run_date=date.today(),
            status=RecurringInvoiceStatus.ACTIVE,
            currency=CurrencyCode.USD,
            payment_terms_days=14,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            line_items_template=[{"description": "Retainer", "quantity": "1", "unit_price": "500.00"}],
        )

        invoice_response = self.client.get(reverse("invoice-detail", args=[other_invoice.id]))
        recurring_response = self.client.get(reverse("recurring-invoice-detail", args=[other_recurring.id]))

        self.assertEqual(invoice_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(recurring_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_attach_saved_banking_profile_to_invoice_creates_snapshot(self):
        invoice = self.create_invoice(invoice_number="INV-5001")

        response = self.client.put(
            reverse("invoice-eft-details", args=[invoice.id]),
            {
                "mode": "saved_profile",
                "banking_profile_id": self.banking_profile.id,
                "payment_reference": "INV-5001-REF",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.eft_source_type, InvoiceEftSourceType.SAVED_PROFILE)
        self.assertEqual(invoice.eft_source_profile, self.banking_profile)
        self.assertEqual(invoice.eft_profile_name, self.banking_profile.profile_name)
        self.assertEqual(invoice.eft_account_holder_name, self.banking_profile.account_holder_name)
        self.assertEqual(invoice.payment_reference, "INV-5001-REF")

    def test_attach_manual_eft_details_to_invoice_creates_snapshot(self):
        invoice = self.create_invoice(invoice_number="INV-5002", payment_page_enabled=False)

        response = self.client.put(
            reverse("invoice-eft-details", args=[invoice.id]),
            {
                "mode": "manual",
                "profile_name": "One-off settlement account",
                "account_holder_name": "Manual Holder Pty Ltd",
                "bank_name": "ABSA",
                "account_number": "9999999999",
                "account_type": "Business Cheque",
                "branch_code": "632005",
                "payment_reference": "MANUAL-5002",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.eft_source_type, InvoiceEftSourceType.MANUAL)
        self.assertIsNone(invoice.eft_source_profile)
        self.assertEqual(invoice.eft_profile_name, "One-off settlement account")
        self.assertEqual(invoice.eft_bank_name, "ABSA")
        self.assertEqual(invoice.payment_reference, "MANUAL-5002")

    def test_switching_banking_profile_source_does_not_change_existing_snapshot_when_profile_updates(self):
        invoice = self.create_invoice(invoice_number="INV-5003")
        self.client.put(
            reverse("invoice-eft-details", args=[invoice.id]),
            {
                "mode": "saved_profile",
                "banking_profile_id": self.banking_profile.id,
                "payment_reference": "INV-5003-REF",
            },
            format="json",
        )

        self.banking_profile.bank_name = "Nedbank"
        self.banking_profile.account_holder_name = "Changed Holder Pty Ltd"
        self.banking_profile.save(update_fields=["bank_name", "account_holder_name", "updated_at"])
        invoice.refresh_from_db()

        self.assertEqual(invoice.eft_bank_name, "FNB")
        self.assertEqual(invoice.eft_account_holder_name, "Invoice Manager Pty Ltd")

    def test_switching_between_saved_profile_and_manual_updates_snapshot(self):
        invoice = self.create_invoice(invoice_number="INV-5004")
        self.client.put(
            reverse("invoice-eft-details", args=[invoice.id]),
            {
                "mode": "saved_profile",
                "banking_profile_id": self.banking_profile.id,
            },
            format="json",
        )

        response = self.client.put(
            reverse("invoice-eft-details", args=[invoice.id]),
            {
                "mode": "manual",
                "profile_name": "Manual fallback",
                "account_holder_name": "Fallback Holder Pty Ltd",
                "bank_name": "Capitec",
                "account_number": "1111111111",
                "account_type": "Business",
                "branch_code": "470010",
                "payment_reference": "INV-5004-MANUAL",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.eft_source_type, InvoiceEftSourceType.MANUAL)
        self.assertIsNone(invoice.eft_source_profile)
        self.assertEqual(invoice.eft_bank_name, "Capitec")

    def test_user_cannot_attach_another_users_banking_profile(self):
        other_profile = UserBankingProfile.objects.create(
            user=self.other_user,
            profile_name="Other account",
            account_holder_name="Other Pty Ltd",
            bank_name="FNB",
            account_number="7777777777",
            is_default=True,
        )
        invoice = self.create_invoice(invoice_number="INV-5005")

        response = self.client.put(
            reverse("invoice-eft-details", args=[invoice.id]),
            {
                "mode": "saved_profile",
                "banking_profile_id": other_profile.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("banking_profile_id", response.data)

    def test_public_payment_page_not_found_when_snapshot_missing(self):
        invoice = self.create_invoice(invoice_number="INV-5006")
        invoice.eft_account_holder_name = ""
        invoice.eft_bank_name = ""
        invoice.eft_account_number = ""
        invoice.save(update_fields=["eft_account_holder_name", "eft_bank_name", "eft_account_number", "updated_at"])

        response = self.client.get(reverse("public-invoice-payment", args=[invoice.public_token]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LegacyOwnerBackfillCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner@example.test",
            email="owner@example.test",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="other@example.test",
            email="other@example.test",
            password="StrongPass123!",
        )

    def test_dry_run_does_not_persist_changes(self):
        client = Client.objects.create(name="Legacy Client", email="legacy-client@example.test")
        contractor = Contractor.objects.create(name="Legacy Contractor")
        invoice = Invoice.objects.create(
            client=client,
            invoice_number="INV-LEGACY-001",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency=CurrencyCode.ZAR,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
        )
        recurring = RecurringInvoice.objects.create(
            client=client,
            contractor=contractor,
            template_name="Legacy Template",
            frequency=RecurringInvoiceFrequency.MONTHLY,
            start_date=date.today(),
            next_run_date=date.today(),
            status=RecurringInvoiceStatus.ACTIVE,
            currency=CurrencyCode.ZAR,
            payment_terms_days=14,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            line_items_template=[{"description": "Support", "quantity": "1", "unit_price": "100.00"}],
        )

        out = StringIO()
        call_command("backfill_legacy_owners", owner_email=self.user.email, stdout=out)

        client.refresh_from_db()
        contractor.refresh_from_db()
        invoice.refresh_from_db()
        recurring.refresh_from_db()

        self.assertIsNone(client.owner)
        self.assertIsNone(contractor.owner)
        self.assertIsNone(invoice.owner)
        self.assertIsNone(recurring.owner)
        self.assertIn("Dry run only", out.getvalue())

    def test_apply_assigns_ownerless_records_to_selected_owner(self):
        client = Client.objects.create(name="Legacy Client", email="legacy-client-2@example.test")
        contractor = Contractor.objects.create(name="Legacy Contractor")
        invoice = Invoice.objects.create(
            client=client,
            invoice_number="INV-LEGACY-002",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency=CurrencyCode.ZAR,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
        )
        recurring = RecurringInvoice.objects.create(
            client=client,
            contractor=contractor,
            template_name="Legacy Template 2",
            frequency=RecurringInvoiceFrequency.MONTHLY,
            start_date=date.today(),
            next_run_date=date.today(),
            status=RecurringInvoiceStatus.ACTIVE,
            currency=CurrencyCode.ZAR,
            payment_terms_days=14,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            line_items_template=[{"description": "Support", "quantity": "1", "unit_price": "100.00"}],
        )

        call_command("backfill_legacy_owners", owner_email=self.user.email, apply=True)

        client.refresh_from_db()
        contractor.refresh_from_db()
        invoice.refresh_from_db()
        recurring.refresh_from_db()

        self.assertEqual(client.owner, self.user)
        self.assertEqual(contractor.owner, self.user)
        self.assertEqual(invoice.owner, self.user)
        self.assertEqual(recurring.owner, self.user)

    def test_apply_skips_records_that_point_to_other_owners_data(self):
        owned_client = Client.objects.create(
            owner=self.other_user,
            name="Other Client",
            email="other-legacy-client@example.test",
        )
        invoice = Invoice.objects.create(
            client=owned_client,
            invoice_number="INV-LEGACY-003",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency=CurrencyCode.ZAR,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
        )

        out = StringIO()
        call_command("backfill_legacy_owners", owner_email=self.user.email, apply=True, stdout=out)

        invoice.refresh_from_db()
        self.assertIsNone(invoice.owner)
        self.assertIn("skipped because client", out.getvalue())
