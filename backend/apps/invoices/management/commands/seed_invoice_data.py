from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.clients.models import Client
from apps.invoices.models import Invoice, InvoiceStatus, TaxType
from apps.invoices.services import recalculate_invoice_totals


class Command(BaseCommand):
    help = "Seed sample clients and invoices for local development."

    def handle(self, *args, **options):
        sample_rows = [
            {
                "client": {
                    "name": "Northwind Studio",
                    "email": "accounts@northwind.test",
                    "address": "12 Kingfisher Avenue",
                },
                "invoice_number": "INV-2026-001",
                "status": InvoiceStatus.SENT,
                "currency": "USD",
                "tax_type": TaxType.PERCENTAGE,
                "tax_rate": Decimal("15.00"),
                "issue_offset": -5,
                "due_offset": 5,
                "items": [
                    ("Brand refresh", Decimal("1.00"), Decimal("800.00")),
                    ("Landing page build", Decimal("1.00"), Decimal("1200.00")),
                ],
            },
            {
                "client": {
                    "name": "Marlow Consulting",
                    "email": "finance@marlow.test",
                    "address": "88 Cedar Road",
                },
                "invoice_number": "INV-2026-002",
                "status": InvoiceStatus.OVERDUE,
                "currency": "USD",
                "tax_type": TaxType.NONE,
                "tax_rate": Decimal("0.00"),
                "issue_offset": -30,
                "due_offset": -10,
                "items": [
                    ("Advisory retainer", Decimal("1.00"), Decimal("1500.00")),
                ],
            },
            {
                "client": {
                    "name": "Bluebird Labs",
                    "email": "ops@bluebird.test",
                    "address": "4 Dockside Lane",
                },
                "invoice_number": "INV-2026-003",
                "status": InvoiceStatus.PAID,
                "currency": "EUR",
                "tax_type": TaxType.PERCENTAGE,
                "tax_rate": Decimal("20.00"),
                "issue_offset": -20,
                "due_offset": -6,
                "items": [
                    ("Monthly maintenance", Decimal("2.00"), Decimal("300.00")),
                    ("Reporting", Decimal("1.00"), Decimal("150.00")),
                ],
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
                },
            )
            invoice.line_items.all().delete()
            for description, quantity, unit_price in row["items"]:
                invoice.line_items.create(
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                )
            recalculate_invoice_totals(invoice)

        self.stdout.write(self.style.SUCCESS("Seed data created or updated."))
