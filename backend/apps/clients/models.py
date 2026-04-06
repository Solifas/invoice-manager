from django.conf import settings
from django.db import models


class Client(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clients",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("owner", "email"), name="unique_client_email_per_owner"),
        ]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"
