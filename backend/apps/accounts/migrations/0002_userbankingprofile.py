from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_user_email_unique_index"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserBankingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("profile_name", models.CharField(max_length=255)),
                ("account_holder_name", models.CharField(max_length=255)),
                ("bank_name", models.CharField(max_length=255)),
                ("account_number", models.CharField(max_length=64)),
                ("account_type", models.CharField(blank=True, max_length=50)),
                ("branch_code", models.CharField(blank=True, max_length=32)),
                ("default_payment_reference", models.CharField(blank=True, max_length=100)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="banking_profiles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("profile_name", "id")},
        ),
        migrations.AddConstraint(
            model_name="userbankingprofile",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True, is_default=True),
                fields=("user",),
                name="unique_default_banking_profile_per_user",
            ),
        ),
    ]
