from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import UserBankingProfile
from apps.clients.models import Client
from apps.contractors.models import Contractor
from apps.invoices.models import CurrencyCode, Invoice, InvoicePayment, InvoiceStatus, RecurringInvoice, TaxType
from apps.invoices.services import (
    attach_manual_eft_details_to_invoice,
    attach_saved_banking_profile_to_invoice,
    recalculate_invoice_totals,
)


class Command(BaseCommand):
    help = "Seed sample clients, contractors, invoices, payments, and recurring templates for local development."

    def handle(self, *args, **options):
        User = get_user_model()
        seeded_owners = [
            {
                "email": "demo@example.com",
                "first_name": "Demo",
                "last_name": "Owner",
                "invoice_prefix": "DEMO",
                "contractor_email": "nora@example.test",
                "contractor_name": "Nora Dev",
                "contractor_phone": "+27111222333",
                "contractor_address": "44 Workshop Street",
            },
            {
                "email": "solifas@extratrx.com",
                "first_name": "Solifas",
                "last_name": "Salimu",
                "invoice_prefix": "SOL",
                "contractor_email": "solifas.contractor@example.test",
                "contractor_name": "Mila Ops",
                "contractor_phone": "+27119888777",
                "contractor_address": "19 Cedar Close",
            },
        ]

        for owner_config in seeded_owners:
            owner, _ = User.objects.get_or_create(
                email=owner_config["email"],
                defaults={
                    "username": owner_config["email"],
                    "first_name": owner_config["first_name"],
                    "last_name": owner_config["last_name"],
                },
            )
            owner.username = owner_config["email"]
            owner.first_name = owner_config["first_name"]
            owner.last_name = owner_config["last_name"]
            owner.set_password("StrongPass123!")
            owner.save()

            contractor, _ = Contractor.objects.update_or_create(
                owner=owner,
                email=owner_config["contractor_email"],
                defaults={
                    "owner": owner,
                    "name": owner_config["contractor_name"],
                    "contact_number": owner_config["contractor_phone"],
                    "address": owner_config["contractor_address"],
                },
            )

            primary_profile, _ = UserBankingProfile.objects.update_or_create(
                user=owner,
                profile_name="Primary operating account",
                defaults={
                    "account_holder_name": f"{owner.first_name} {owner.last_name} Trading",
                    "bank_name": "FNB",
                    "account_number": "12345678901",
                    "account_type": "Business Cheque",
                    "branch_code": "250655",
                    "default_payment_reference": f"{owner_config['invoice_prefix']}-PAY",
                    "is_default": True,
                    "is_active": True,
                },
            )
            UserBankingProfile.objects.filter(user=owner).exclude(id=primary_profile.id).update(is_default=False)

            sample_rows = [
                {
                    "client": {
                        "name": "Northwind Studio",
                        "email": "accounts@northwind.test",
                        "address": "12 Kingfisher Avenue",
                        "phone_number": "+27123456789",
                    },
                    "invoice_number": f"INV-{owner_config['invoice_prefix']}-2026-001",
                    "status": InvoiceStatus.SENT,
                    "currency": CurrencyCode.USD,
                    "tax_type": TaxType.PERCENTAGE,
                    "tax_rate": Decimal("15.00"),
                    "issue_offset": -5,
                    "due_offset": 5,
                    "payment_page_enabled": True,
                    "eft_mode": "saved_profile",
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
                    "invoice_number": f"INV-{owner_config['invoice_prefix']}-2026-002",
                    "status": InvoiceStatus.OVERDUE,
                    "currency": CurrencyCode.ZAR,
                    "tax_type": TaxType.NONE,
                    "tax_rate": Decimal("0.00"),
                    "issue_offset": -30,
                    "due_offset": -10,
                    "payment_page_enabled": True,
                    "eft_mode": "manual",
                    "payment_reference": f"INV-{owner_config['invoice_prefix']}-2026-002",
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
                    "invoice_number": f"INV-{owner_config['invoice_prefix']}-2026-003",
                    "status": InvoiceStatus.PAID,
                    "currency": CurrencyCode.ZAR,
                    "tax_type": TaxType.PERCENTAGE,
                    "tax_rate": Decimal("20.00"),
                    "issue_offset": -20,
                    "due_offset": -6,
                    "payment_page_enabled": False,
                    "eft_mode": "",
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
                    owner=owner,
                    email=row["client"]["email"],
                    defaults={**row["client"], "owner": owner},
                )
                invoice, _ = Invoice.objects.update_or_create(
                    invoice_number=row["invoice_number"],
                    defaults={
                        "owner": owner,
                        "client": client,
                        "issue_date": date.today() + timedelta(days=row["issue_offset"]),
                        "due_date": date.today() + timedelta(days=row["due_offset"]),
                        "status": row["status"],
                        "notes": "Seeded example invoice.",
                        "currency": row["currency"],
                        "tax_type": row["tax_type"],
                        "tax_rate": row["tax_rate"],
                        "payment_page_enabled": row["payment_page_enabled"],
                        "eft_source_type": "",
                        "eft_source_profile": None,
                        "eft_profile_name": "",
                        "eft_account_holder_name": "",
                        "eft_bank_name": "",
                        "eft_account_number": "",
                        "eft_account_type": "",
                        "eft_branch_code": "",
                        "payment_reference": "",
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

                if row["payment_page_enabled"]:
                    if row["eft_mode"] == "saved_profile":
                        attach_saved_banking_profile_to_invoice(
                            invoice,
                            primary_profile,
                            payment_reference=row["payment_reference"],
                        )
                    elif row["eft_mode"] == "manual":
                        attach_manual_eft_details_to_invoice(
                            invoice,
                            profile_name="Manual one-off account",
                            account_holder_name=f"{owner.first_name} {owner.last_name} Projects",
                            bank_name="ABSA",
                            account_number="4096150463",
                            account_type="Business Cheque",
                            branch_code="632005",
                            payment_reference=row["payment_reference"],
                        )

            RecurringInvoice.objects.update_or_create(
                owner=owner,
                template_name="Monthly Design Retainer",
                defaults={
                    "owner": owner,
                    "client": Client.objects.get(owner=owner, email="accounts@northwind.test"),
                    "contractor": contractor,
                    "frequency": "monthly",
                    "start_date": date.today(),
                    "next_run_date": date.today(),
                    "status": "active",
                    "currency": CurrencyCode.ZAR,
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

        self.stdout.write(self.style.SUCCESS("Seed data created or updated for demo@example.com and solifas@extratrx.com."))
