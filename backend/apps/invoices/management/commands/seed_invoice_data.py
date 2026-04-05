from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.clients.models import Client
from apps.contractors.models import Contractor
from apps.invoices.models import Invoice, InvoicePayment, InvoiceStatus, RecurringInvoice, TaxType
from apps.invoices.services import recalculate_invoice_totals


class Command(BaseCommand):
    help = "Seed sample clients, contractors, invoices, payments, and recurring templates for local development."

    def handle(self, *args, **options):
        contractor, _ = Contractor.objects.update_or_create(
            email="nora@example.test",
            defaults={
                "name": "Nora Dev",
                "contact_number": "+27111222333",
                "address": "44 Workshop Street",
            },
        )

        sample_rows = [
            {
                "client": {
                    "name": "Northwind Studio",
                    "email": "accounts@northwind.test",
                    "address": "12 Kingfisher Avenue",
                    "phone_number": "+27123456789",
                },
                "invoice_number": "INV-2026-001",
                "status": InvoiceStatus.SENT,
                "currency": "USD",
                "tax_type": TaxType.PERCENTAGE,
                "tax_rate": Decimal("15.00"),
                "issue_offset": -5,
                "due_offset": 5,
                "payment_page_enabled": True,
                "payment_reference": "",
                "items": [
                    ("Brand refresh", Decimal("1"), Decimal("800.00")),
                    ("Landing page build", Decimal("1"), Decimal("1200.00")),
                ],
                "payments": [],
            },
            {
                "client": {
                    "name": "Marlow Consulting",
                    "email": "finance@marlow.test",
                    "address": "88 Cedar Road",
                    "phone_number": "+27129876543",
                },
                "invoice_number": "INV-2026-002",
                "status": InvoiceStatus.OVERDUE,
                "currency": "USD",
                "tax_type": TaxType.NONE,
                "tax_rate": Decimal("0.00"),
                "issue_offset": -30,
                "due_offset": -10,
                "payment_page_enabled": True,
                "payment_reference": "INV-2026-002",
                "items": [
                    ("Advisory retainer", Decimal("1"), Decimal("1500.00")),
                ],
                "payments": [
                    {
                        "amount": Decimal("500.00"),
                        "payment_date": date.today() - timedelta(days=7),
                        "payment_method": "eft",
                        "reference": "MLW-DEP-001",
                        "notes": "Partial deposit received.",
                    }
                ],
            },
            {
                "client": {
                    "name": "Bluebird Labs",
                    "email": "ops@bluebird.test",
                    "address": "4 Dockside Lane",
                    "phone_number": "+27125550000",
                },
                "invoice_number": "INV-2026-003",
                "status": InvoiceStatus.PAID,
                "currency": "EUR",
                "tax_type": TaxType.PERCENTAGE,
                "tax_rate": Decimal("20.00"),
                "issue_offset": -20,
                "due_offset": -6,
                "payment_page_enabled": False,
                "payment_reference": "",
                "items": [
                    ("Monthly maintenance", Decimal("2"), Decimal("300.00")),
                    ("Reporting", Decimal("1"), Decimal("150.00")),
                ],
                "payments": [],
            },
        ]

        for row in sample_rows:
            client, _ = Client.objects.update_or_create(
                email=row["client"]["email"],
                defaults=row["client"],
            )
            invoice, _ = Invoice.objects.update_or_create(
                invoice_number=row["invoice_number"],
                defaults={
                    "client": client,
                    "issue_date": date.today() + timedelta(days=row["issue_offset"]),
                    "due_date": date.today() + timedelta(days=row["due_offset"]),
                    "status": row["status"],
                    "notes": "Seeded example invoice.",
                    "currency": row["currency"],
                    "tax_type": row["tax_type"],
                    "tax_rate": row["tax_rate"],
                    "payment_page_enabled": row["payment_page_enabled"],
                    "eft_account_holder_name": "Invoice Manager Pty Ltd",
                    "eft_bank_name": "Example Bank",
                    "eft_account_number": "1234567890",
                    "eft_account_type": "Business",
                    "eft_branch_code": "250655",
                    "payment_reference": row["payment_reference"],
                },
            )
            invoice.line_items.all().delete()
            invoice.payments.all().delete()
            for description, quantity, unit_price in row["items"]:
                invoice.line_items.create(
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                )
            recalculate_invoice_totals(invoice)
            for payment in row["payments"]:
                InvoicePayment.objects.create(invoice=invoice, **payment)
            if row["status"] == InvoiceStatus.PAID and not row["payments"]:
                InvoicePayment.objects.create(
                    invoice=invoice,
                    amount=invoice.total_amount,
                    payment_date=invoice.due_date,
                    payment_method="eft",
                    reference=f"{invoice.invoice_number}-PAID",
                    notes="Seeded paid invoice.",
                )
            recalculate_invoice_totals(invoice)

        RecurringInvoice.objects.update_or_create(
            template_name="Monthly Design Retainer",
            defaults={
                "client": Client.objects.get(email="accounts@northwind.test"),
                "contractor": contractor,
                "frequency": "monthly",
                "start_date": date.today(),
                "next_run_date": date.today(),
                "status": "active",
                "currency": "USD",
                "payment_terms_days": 14,
                "tax_type": TaxType.PERCENTAGE,
                "tax_rate": Decimal("15.00"),
                "notes": "Automatically generated recurring invoice.",
                "line_items_template": [
                    {"description": "Retainer", "quantity": "1", "unit_price": "950.00"},
                    {"description": "Reporting", "quantity": "1", "unit_price": "150.00"},
                ],
            },
        )

        self.stdout.write(self.style.SUCCESS("Seed data created or updated."))
