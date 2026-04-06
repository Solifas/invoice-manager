from django.conf import settings
from django.db import models


class Contractor(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contractors",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name
