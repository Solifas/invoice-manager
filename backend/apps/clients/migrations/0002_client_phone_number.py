from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="phone_number",
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
