from django.contrib import admin

from .models import Contractor


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "contact_number")
    search_fields = ("name", "email", "contact_number")
