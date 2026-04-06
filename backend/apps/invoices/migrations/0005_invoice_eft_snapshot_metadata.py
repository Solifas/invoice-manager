from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_userbankingprofile"),
        ("invoices", "0004_currency_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="eft_profile_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="invoice",
            name="eft_source_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoice_snapshots",
                to="accounts.userbankingprofile",
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="eft_source_type",
            field=models.CharField(
                blank=True,
                choices=[("saved_profile", "Saved profile"), ("manual", "Manual")],
                max_length=20,
            ),
        ),
    ]
