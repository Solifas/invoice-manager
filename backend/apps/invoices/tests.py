from decimal import Decimal
from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.clients.models import Client
from apps.invoices.models import Invoice, InvoiceStatus, TaxType
from apps.invoices.services import recalculate_invoice_totals


class InvoiceCalculationTests(APITestCase):
    def setUp(self):
        self.client_record = Client.objects.create(
            name="Acme Co",
            email="billing@acme.test",
            address="1 Main Street",
        )

    def test_recalculate_totals_with_percentage_tax(self):
        invoice = Invoice.objects.create(
            client=self.client_record,
            invoice_number="INV-1001",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            status=InvoiceStatus.SENT,
            currency="USD",
            tax_type=TaxType.PERCENTAGE,
            tax_rate=Decimal("15.00"),
        )
        invoice.line_items.create(description="Design", quantity=2, unit_price=Decimal("100.00"))
        invoice.line_items.create(description="Hosting", quantity=1, unit_price=Decimal("50.00"))

        recalculate_invoice_totals(invoice)
        invoice.refresh_from_db()

        self.assertEqual(invoice.subtotal, Decimal("250.00"))
        self.assertEqual(invoice.tax_amount, Decimal("37.50"))
        self.assertEqual(invoice.total_amount, Decimal("287.50"))

    def test_invoice_create_api_recalculates_totals(self):
        payload = {
            "invoice_number": "INV-1002",
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=7)),
            "status": InvoiceStatus.DRAFT,
            "notes": "Thanks",
            "currency": "USD",
            "tax_type": TaxType.PERCENTAGE,
            "tax_rate": "10.00",
            "client": {
                "name": "Nova Studio",
                "email": "accounts@nova.test",
                "address": "20 Market Road",
            },
            "line_items": [
                {"description": "Consulting", "quantity": "3.00", "unit_price": "120.00"},
                {"description": "Support", "quantity": "1.00", "unit_price": "40.00"},
            ],
        }

        response = self.client.post(reverse("invoice-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subtotal"], "400.00")
        self.assertEqual(response.data["tax_amount"], "40.00")
        self.assertEqual(response.data["total_amount"], "440.00")

    def test_dashboard_summary_endpoint(self):
        invoice = Invoice.objects.create(
            client=self.client_record,
            invoice_number="INV-1003",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=3),
            status=InvoiceStatus.SENT,
            currency="USD",
        )
        invoice.line_items.create(description="Retainer", quantity=1, unit_price=Decimal("300.00"))
        recalculate_invoice_totals(invoice)

        response = self.client.get(reverse("invoice-dashboard-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_invoices"], 1)
        self.assertEqual(response.data["unpaid_invoices"], 1)

    def test_invoice_pdf_endpoint_returns_pdf(self):
        invoice = Invoice.objects.create(
            client=self.client_record,
            invoice_number="INV-1004",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=10),
            status=InvoiceStatus.SENT,
            currency="USD",
        )
        invoice.line_items.create(description="Build", quantity=1, unit_price=Decimal("500.00"))
        recalculate_invoice_totals(invoice)

        response = self.client.get(reverse("invoice-pdf", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(b"%PDF", response.content[:10])
