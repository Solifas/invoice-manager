from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0007_payment_link_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="reminder_sent_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
