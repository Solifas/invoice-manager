from django.contrib import admin

from .models import Invoice, InvoiceLineItem


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "client", "status", "issue_date", "due_date", "total_amount")
    list_filter = ("status", "currency")
    search_fields = ("invoice_number", "client__name", "client__email")
    inlines = [InvoiceLineItemInline]
