from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clients.models import Client
from apps.contractors.models import Contractor
from apps.invoices.models import Invoice, RecurringInvoice


class Command(BaseCommand):
    help = "Assign ownerless legacy billing records to a specific authenticated owner."

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner-email",
            required=True,
            help="Email address of the user who should own ownerless legacy records.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes. Without this flag, the command only performs a dry run.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        owner_email = options["owner_email"].strip().lower()
        apply_changes = options["apply"]

        try:
            owner = User.objects.get(email__iexact=owner_email)
        except User.DoesNotExist as exc:
            raise CommandError(f"No user found for email '{owner_email}'.") from exc

        summary = self._build_summary(owner)

        if not apply_changes:
            self._print_summary(owner.email, summary, dry_run=True)
            self.stdout.write(self.style.WARNING("Dry run only. Re-run with --apply to persist these changes."))
            return

        with transaction.atomic():
            applied = self._apply(owner, summary)

        self._print_summary(owner.email, applied, dry_run=False)
        self.stdout.write(self.style.SUCCESS("Legacy owner backfill completed."))

    def _build_summary(self, owner):
        clients = list(Client.objects.filter(owner__isnull=True).order_by("id"))
        contractors = list(Contractor.objects.filter(owner__isnull=True).order_by("id"))

        assignable_invoices = []
        skipped_invoices = []
        for invoice in Invoice.objects.filter(owner__isnull=True).select_related("client", "recurring_invoice").order_by("id"):
            if invoice.client.owner_id not in (None, owner.id):
                skipped_invoices.append(
                    f"Invoice {invoice.invoice_number} skipped because client {invoice.client_id} belongs to another owner."
                )
                continue
            if invoice.recurring_invoice_id and invoice.recurring_invoice.owner_id not in (None, owner.id):
                skipped_invoices.append(
                    f"Invoice {invoice.invoice_number} skipped because recurring template {invoice.recurring_invoice_id} belongs to another owner."
                )
                continue
            assignable_invoices.append(invoice)

        assignable_recurring = []
        skipped_recurring = []
        recurring_queryset = RecurringInvoice.objects.filter(owner__isnull=True).select_related("client", "contractor").order_by("id")
        for recurring in recurring_queryset:
            if recurring.client.owner_id not in (None, owner.id):
                skipped_recurring.append(
                    f"Recurring template {recurring.template_name} skipped because client {recurring.client_id} belongs to another owner."
                )
                continue
            if recurring.contractor_id and recurring.contractor.owner_id not in (None, owner.id):
                skipped_recurring.append(
                    f"Recurring template {recurring.template_name} skipped because contractor {recurring.contractor_id} belongs to another owner."
                )
                continue
            assignable_recurring.append(recurring)

        return {
            "clients": clients,
            "contractors": contractors,
            "invoices": assignable_invoices,
            "recurring": assignable_recurring,
            "skipped_invoices": skipped_invoices,
            "skipped_recurring": skipped_recurring,
        }

    def _apply(self, owner, summary):
        for client in summary["clients"]:
            client.owner = owner
            client.save(update_fields=["owner"])

        for contractor in summary["contractors"]:
            contractor.owner = owner
            contractor.save(update_fields=["owner"])

        for invoice in summary["invoices"]:
            invoice.owner = owner
            invoice.save(update_fields=["owner"])

        for recurring in summary["recurring"]:
            recurring.owner = owner
            recurring.save(update_fields=["owner"])

        return summary

    def _print_summary(self, owner_email, summary, *, dry_run):
        mode = "Dry run" if dry_run else "Applied"
        self.stdout.write(f"{mode} for owner {owner_email}")
        self.stdout.write(f"Clients to assign: {len(summary['clients'])}")
        self.stdout.write(f"Contractors to assign: {len(summary['contractors'])}")
        self.stdout.write(f"Invoices to assign: {len(summary['invoices'])}")
        self.stdout.write(f"Recurring templates to assign: {len(summary['recurring'])}")

        skipped = summary["skipped_invoices"] + summary["skipped_recurring"]
        if skipped:
            self.stdout.write(self.style.WARNING(f"Skipped records: {len(skipped)}"))
            for message in skipped:
                self.stdout.write(f" - {message}")
