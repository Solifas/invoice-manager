from django.contrib import admin

from .models import Invoice, InvoiceLineItem, InvoicePayment, RecurringInvoice


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0


class InvoicePaymentInline(admin.TabularInline):
    model = InvoicePayment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "client", "status", "issue_date", "due_date", "total_amount", "payment_page_enabled")
    list_filter = ("status", "currency")
    search_fields = ("invoice_number", "client__name", "client__email")
    inlines = [InvoiceLineItemInline, InvoicePaymentInline]


@admin.register(RecurringInvoice)
class RecurringInvoiceAdmin(admin.ModelAdmin):
    list_display = ("template_name", "client", "frequency", "status", "next_run_date")
    list_filter = ("frequency", "status")
    search_fields = ("template_name", "client__name")
