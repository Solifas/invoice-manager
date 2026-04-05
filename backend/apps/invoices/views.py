from django.http import HttpResponse
from rest_framework import decorators, mixins, status, viewsets
from rest_framework.response import Response

from apps.reminders.tasks import enqueue_manual_invoice_reminder

from .models import Invoice, InvoiceLineItem
from .pdf import build_invoice_pdf
from .selectors import get_dashboard_summary
from .serializers import (
    DashboardSummarySerializer,
    InvoiceLineItemSerializer,
    InvoiceListSerializer,
    InvoiceSerializer,
)
from .services import recalculate_invoice_totals


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("client").prefetch_related("line_items").all()
    filterset_fields = ("status",)
    search_fields = ("invoice_number", "client__name")
    ordering_fields = ("issue_date", "due_date", "total_amount", "invoice_number")

    def get_serializer_class(self):
        if self.action == "list":
            return InvoiceListSerializer
        return InvoiceSerializer

    @decorators.action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):
        serializer = DashboardSummarySerializer(get_dashboard_summary())
        return Response(serializer.data)

    @decorators.action(detail=True, methods=["post"], url_path="send-reminder")
    def send_reminder(self, request, pk=None):
        invoice = self.get_object()
        enqueue_manual_invoice_reminder.delay(invoice.id)
        return Response({"detail": "Reminder queued."}, status=status.HTTP_202_ACCEPTED)

    @decorators.action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        recalculate_invoice_totals(invoice)
        invoice.refresh_from_db()
        pdf_bytes = build_invoice_pdf(invoice)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.pdf"'
        return response


class InvoiceLineItemViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = InvoiceLineItem.objects.select_related("invoice").all()
    serializer_class = InvoiceLineItemSerializer
    filterset_fields = ("invoice",)
