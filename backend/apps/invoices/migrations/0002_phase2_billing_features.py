import decimal
import secrets

import apps.invoices.models
import django.db.models.deletion
from django.db import migrations, models


def populate_invoice_public_tokens(apps, schema_editor):
    Invoice = apps.get_model("invoices", "Invoice")
    for invoice in Invoice.objects.filter(public_token__isnull=True):
        token = secrets.token_urlsafe(32)
        while Invoice.objects.filter(public_token=token).exists():
            token = secrets.token_urlsafe(32)
        invoice.public_token = token
        invoice.save(update_fields=["public_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0002_client_phone_number"),
        ("contractors", "0001_initial"),
        ("invoices", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecurringInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("template_name", models.CharField(max_length=255)),
                ("frequency", models.CharField(choices=[("weekly", "Weekly"), ("monthly", "Monthly"), ("quarterly", "Quarterly")], max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("next_run_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("paused", "Paused"), ("cancelled", "Cancelled")], default="active", max_length=20)),
                ("currency", models.CharField(default="USD", max_length=8)),
                ("payment_terms_days", models.PositiveIntegerField(default=14)),
                ("tax_type", models.CharField(choices=[("none", "No tax"), ("percentage", "Percentage")], default="none", max_length=20)),
                ("tax_rate", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=5)),
                ("notes", models.TextField(blank=True)),
                ("line_items_template", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recurring_invoices", to="clients.client")),
                ("contractor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recurring_invoices", to="contractors.contractor")),
            ],
            options={"ordering": ("template_name", "id")},
        ),
        migrations.CreateModel(
            name="InvoicePayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("payment_date", models.DateField()),
                ("payment_method", models.CharField(blank=True, max_length=50)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="invoices.invoice")),
            ],
            options={"ordering": ("-payment_date", "-created_at")},
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_page_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="invoice",
            name="public_token",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="eft_account_holder_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="invoice",
            name="eft_bank_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="invoice",
            name="eft_account_number",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="invoice",
            name="eft_account_type",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="invoice",
            name="eft_branch_code",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_reference",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="invoice",
            name="recurring_invoice",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_invoices", to="invoices.recurringinvoice"),
        ),
        migrations.RunPython(populate_invoice_public_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="invoice",
            name="public_token",
            field=models.CharField(default=apps.invoices.models.generate_invoice_public_token, max_length=64, unique=True),
        ),
    ]
