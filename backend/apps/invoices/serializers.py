from django.db import transaction
from rest_framework import serializers

from apps.clients.models import Client

from .models import Invoice, InvoiceLineItem
from .services import recalculate_invoice_totals, replace_invoice_line_items


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ("id", "name", "email", "address")
        extra_kwargs = {
            "email": {"validators": []},
        }


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ("id", "description", "quantity", "unit_price", "line_total")
        read_only_fields = ("id", "line_total")


class InvoiceSerializer(serializers.ModelSerializer):
    client = ClientSerializer()
    line_items = InvoiceLineItemSerializer(many=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
            "invoice_number",
            "client",
            "issue_date",
            "due_date",
            "status",
            "notes",
            "currency",
            "tax_type",
            "tax_rate",
            "subtotal",
            "tax_amount",
            "total_amount",
            "line_items",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("subtotal", "tax_amount", "total_amount", "created_at", "updated_at")

    def validate_line_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one line item is required.")
        return value

    def _upsert_client(self, client_data: dict) -> Client:
        email = client_data["email"]
        client, _ = Client.objects.update_or_create(
            email=email,
            defaults={
                "name": client_data["name"],
                "address": client_data.get("address", ""),
            },
        )
        return client

    @transaction.atomic
    def create(self, validated_data):
        client_data = validated_data.pop("client")
        items_data = validated_data.pop("line_items")
        client = self._upsert_client(client_data)
        invoice = Invoice.objects.create(client=client, **validated_data)
        replace_invoice_line_items(invoice, items_data)
        invoice.refresh_from_db()
        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        client_data = validated_data.pop("client", None)
        items_data = validated_data.pop("line_items", None)

        if client_data:
            instance.client = self._upsert_client(client_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            replace_invoice_line_items(instance, items_data)
        else:
            recalculate_invoice_totals(instance)

        instance.refresh_from_db()
        return instance


class InvoiceListSerializer(serializers.ModelSerializer):
    client = ClientSerializer()

    class Meta:
        model = Invoice
        fields = (
            "id",
            "invoice_number",
            "client",
            "issue_date",
            "due_date",
            "status",
            "currency",
            "total_amount",
            "subtotal",
        )


class DashboardSummarySerializer(serializers.Serializer):
    total_invoices = serializers.IntegerField()
    unpaid_invoices = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    total_amount_outstanding = serializers.DecimalField(max_digits=12, decimal_places=2)
