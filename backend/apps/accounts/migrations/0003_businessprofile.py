from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_userbankingprofile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("business_name", models.CharField(max_length=255)),
                ("business_type", models.CharField(max_length=100)),
                ("registration_number", models.CharField(blank=True, max_length=100)),
                ("vat_number", models.CharField(blank=True, max_length=100)),
                ("trading_name", models.CharField(blank=True, max_length=255)),
                ("contact_email", models.EmailField(max_length=254)),
                ("contact_phone_number", models.CharField(max_length=50)),
                ("business_address", models.TextField()),
                (
                    "verification_status",
                    models.CharField(
                        choices=[
                            ("not_started", "Not started"),
                            ("pending", "Pending"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                        ],
                        default="not_started",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("business_name", "id"),
            },
        ),
    ]
