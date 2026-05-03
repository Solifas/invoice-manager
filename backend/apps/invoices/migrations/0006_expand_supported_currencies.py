from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0005_invoice_eft_snapshot_metadata"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="currency",
            field=models.CharField(default="ZAR", max_length=8),
        ),
        migrations.AlterField(
            model_name="recurringinvoice",
            name="currency",
            field=models.CharField(default="ZAR", max_length=8),
        ),
    ]
