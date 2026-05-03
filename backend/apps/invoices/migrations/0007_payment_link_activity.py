from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0006_expand_supported_currencies"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="public_token_regenerated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_page_first_opened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_page_last_opened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="payment_page_open_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
