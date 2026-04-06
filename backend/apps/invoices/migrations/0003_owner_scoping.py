from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0003_client_owner"),
        ("contractors", "0002_contractor_owner"),
        ("invoices", "0002_phase2_billing_features"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="invoices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="recurringinvoice",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="recurring_invoices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
