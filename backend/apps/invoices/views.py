from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from rest_framework import decorators, mixins, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clients.models import Client
from apps.contractors.models import Contractor
from apps.reminders.services import ReminderDeliveryError, dispatch_manual_invoice_reminder

from .models import Invoice, InvoiceLineItem, InvoicePayment, InvoiceStatus, RecurringInvoice
from .pdf import build_invoice_pdf
from .selectors import get_dashboard_summary
from .serializers import (
    ClientSerializer,
    ContractorSerializer,
    DashboardSummarySerializer,
    InvoiceEftDetailsUpdateSerializer,
    InvoiceEftSnapshotSerializer,
    InvoiceLineItemSerializer,
    InvoiceListSerializer,
    InvoicePaymentSerializer,
    InvoiceSerializer,
    PublicInvoicePaymentSerializer,
    RecurringInvoiceSerializer,
    ReminderRequestSerializer,
)
from .services import (
    get_invoice_eft_snapshot,
    has_invoice_eft_snapshot,
    recalculate_invoice_totals,
    regenerate_invoice_public_token,
    sync_invoice_status,
    sync_invoices_status,
)


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("client", "recurring_invoice").prefetch_related("line_items", "payments").all()
    filterset_fields = ("status",)
    search_fields = ("invoice_number", "client__name")
    ordering_fields = ("issue_date", "due_date", "total_amount", "invoice_number")

    def get_queryset(self):
        queryset = super().get_queryset().filter(owner=self.request.user)
        status_group = self.request.query_params.get("status_group")
        if status_group == "unpaid":
            queryset = queryset.exclude(status=InvoiceStatus.CANCELLED).exclude(status=InvoiceStatus.PAID)
        elif status_group == "overdue":
            queryset = queryset.filter(status=InvoiceStatus.OVERDUE)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return InvoiceListSerializer
        return InvoiceSerializer

    def get_object(self):
        invoice = super().get_object()
        sync_invoice_status(invoice)
        return invoice

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        invoices = list(page) if page is not None else list(queryset)
        sync_invoices_status(invoices)
        serializer = self.get_serializer(invoices, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @decorators.action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):
        serializer = DashboardSummarySerializer(get_dashboard_summary(owner=request.user))
        return Response(serializer.data)

    @decorators.action(detail=True, methods=["post"], url_path="send-reminder")
    def send_reminder(self, request, pk=None):
        invoice = self.get_object()
        try:
            result = dispatch_manual_invoice_reminder(invoice, "email")
        except ReminderDeliveryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        detail = "Email reminder queued." if result == "queued" else "Email reminder sent."
        return Response({"detail": detail}, status=status.HTTP_202_ACCEPTED)

    @decorators.action(detail=True, methods=["post"], url_path="remind")
    def remind(self, request, pk=None):
        invoice = self.get_object()
        serializer = ReminderRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        channel = serializer.validated_data["channel"]
        try:
            result = dispatch_manual_invoice_reminder(invoice, channel)
        except ReminderDeliveryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        detail = f"{channel.title()} reminder queued." if result == "queued" else f"{channel.title()} reminder sent."
        return Response({"detail": detail}, status=status.HTTP_202_ACCEPTED)

    @decorators.action(detail=True, methods=["get", "post"], url_path="payments")
    def payments(self, request, pk=None):
        invoice = self.get_object()
        if request.method == "GET":
            serializer = InvoicePaymentSerializer(invoice.payments.all(), many=True)
            return Response(serializer.data)

        serializer = InvoicePaymentSerializer(data=request.data, context={"invoice": invoice})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(InvoicePaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"], url_path="payment-page/regenerate-token")
    def regenerate_payment_page_token(self, request, pk=None):
        invoice = self.get_object()
        try:
            regenerate_invoice_public_token(invoice)
        except ValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        invoice.refresh_from_db()
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)

    @decorators.action(detail=True, methods=["get", "put"], url_path="eft-details")
    def eft_details(self, request, pk=None):
        invoice = self.get_object()
        if request.method == "GET":
            return Response(InvoiceEftSnapshotSerializer(get_invoice_eft_snapshot(invoice)).data)

        serializer = InvoiceEftDetailsUpdateSerializer(data=request.data, context={"request": request, "invoice": invoice})
        serializer.is_valid(raise_exception=True)
        updated_invoice = serializer.save()
        return Response(InvoiceEftSnapshotSerializer(get_invoice_eft_snapshot(updated_invoice)).data)

    @decorators.action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        recalculate_invoice_totals(invoice)
        invoice.refresh_from_db()
        pdf_bytes = build_invoice_pdf(invoice)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.pdf"'
        return response


class PublicInvoicePaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        try:
            invoice = Invoice.objects.select_related("client").prefetch_related("payments").get(
                public_token=token,
                payment_page_enabled=True,
            )
        except Invoice.DoesNotExist as exc:
            raise Http404 from exc

        sync_invoice_status(invoice)
        if not has_invoice_eft_snapshot(invoice):
            raise Http404
        serializer = PublicInvoicePaymentSerializer(invoice)
        return Response(serializer.data)


class InvoiceLineItemViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = InvoiceLineItem.objects.select_related("invoice").all()
    serializer_class = InvoiceLineItemSerializer
    filterset_fields = ("invoice",)

    def get_queryset(self):
        return super().get_queryset().filter(invoice__owner=self.request.user)


class ClientLookupViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class ContractorLookupViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Contractor.objects.all()
    serializer_class = ContractorSerializer
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class InvoicePaymentViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = InvoicePayment.objects.select_related("invoice", "invoice__client").all()
    serializer_class = InvoicePaymentSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().filter(invoice__owner=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in {"partial_update", "update"}:
            context["invoice"] = self.get_object().invoice
        return context


class RecurringInvoiceViewSet(viewsets.ModelViewSet):
    queryset = RecurringInvoice.objects.select_related("client", "contractor").all()
    serializer_class = RecurringInvoiceSerializer

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def perform_destroy(self, instance):
        instance.status = "cancelled"
        instance.next_run_date = None
        instance.save(update_fields=["status", "next_run_date", "updated_at"])
