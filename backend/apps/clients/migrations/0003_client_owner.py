from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0002_client_phone_number"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="client",
            name="email",
            field=models.EmailField(max_length=254),
        ),
        migrations.AddField(
            model_name="client",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="clients",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="client",
            constraint=models.UniqueConstraint(fields=("owner", "email"), name="unique_client_email_per_owner"),
        ),
    ]
