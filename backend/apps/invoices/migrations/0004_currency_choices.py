from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0003_owner_scoping"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="currency",
            field=models.CharField(
                choices=[("ZAR", "South African rand"), ("USD", "US dollar")],
                default="ZAR",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="recurringinvoice",
            name="currency",
            field=models.CharField(
                choices=[("ZAR", "South African rand"), ("USD", "US dollar")],
                default="ZAR",
                max_length=8,
            ),
        ),
    ]
