from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import UserBankingProfile
from apps.clients.models import Client
from apps.contractors.models import Contractor
from apps.reminders.services import ReminderChannel

from .models import CurrencyCode, Invoice, InvoiceEftSourceType, InvoiceLineItem, InvoicePayment, RecurringInvoice
from .services import (
    attach_manual_eft_details_to_invoice,
    attach_saved_banking_profile_to_invoice,
    can_invoice_expose_payment_page,
    create_invoice_payment,
    get_invoice_amount_paid,
    get_invoice_eft_snapshot,
    get_invoice_outstanding_amount,
    recalculate_invoice_totals,
    resolve_recurring_next_run_date,
    replace_invoice_line_items,
    update_invoice_payment,
)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ("id", "name", "email", "address", "phone_number")
        extra_kwargs = {
            "email": {"validators": []},
        }


class ContractorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contractor
        fields = ("id", "name", "email", "contact_number", "address")


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    def validate_quantity(self, value):
        if value != value.to_integral_value():
            raise serializers.ValidationError("Quantity must be a whole number.")
        return value

    class Meta:
        model = InvoiceLineItem
        fields = ("id", "description", "quantity", "unit_price", "line_total")
        read_only_fields = ("id", "line_total")


class InvoicePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoicePayment
        fields = (
            "id",
            "invoice",
            "amount",
            "payment_date",
            "payment_method",
            "reference",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "invoice", "created_at", "updated_at")

    def create(self, validated_data):
        invoice = self.context["invoice"]
        try:
            return create_invoice_payment(invoice, **validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

    def update(self, instance, validated_data):
        try:
            return update_invoice_payment(instance, **validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc


class InvoiceSerializer(serializers.ModelSerializer):
    client = ClientSerializer()
    line_items = InvoiceLineItemSerializer(many=True)
    payments = InvoicePaymentSerializer(many=True, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    public_payment_url = serializers.SerializerMethodField()
    payment_link_available = serializers.SerializerMethodField()
    eft_snapshot = serializers.SerializerMethodField()

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
            "amount_paid",
            "outstanding_amount",
            "payment_page_enabled",
            "public_token",
            "public_payment_url",
            "payment_link_available",
            "eft_snapshot",
            "eft_source_type",
            "eft_source_profile",
            "eft_profile_name",
            "eft_account_holder_name",
            "eft_bank_name",
            "eft_account_number",
            "eft_account_type",
            "eft_branch_code",
            "payment_reference",
            "line_items",
            "payments",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "subtotal",
            "tax_amount",
            "total_amount",
            "amount_paid",
            "outstanding_amount",
            "public_token",
            "public_payment_url",
            "eft_snapshot",
            "eft_source_type",
            "eft_source_profile",
            "eft_profile_name",
            "created_at",
            "updated_at",
        )

    def validate_line_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one line item is required.")
        return value

    def validate_currency(self, value):
        normalized = value.upper()
        if normalized not in CurrencyCode.values:
            raise serializers.ValidationError("Currency must be either ZAR or USD.")
        return normalized

    def validate(self, attrs):
        request = self.context.get("request")
        owner = request.user if request and request.user.is_authenticated else None
        client_data = attrs.get("client")
        if self.instance and client_data is None:
            client = self.instance.client
            if owner and client.owner_id and client.owner_id != owner.id:
                raise serializers.ValidationError({"client": "Client must belong to the authenticated owner."})
        return attrs

    def _upsert_client(self, client_data: dict) -> Client:
        request = self.context.get("request")
        owner = request.user if request and request.user.is_authenticated else None
        email = client_data["email"]
        client, _ = Client.objects.update_or_create(
            owner=owner,
            email=email,
            defaults={
                "owner": owner,
                "name": client_data["name"],
                "address": client_data.get("address", ""),
                "phone_number": client_data.get("phone_number", ""),
            },
        )
        return client

    def get_public_payment_url(self, obj: Invoice) -> str:
        if not can_invoice_expose_payment_page(obj):
            return ""
        return f"{settings.FRONTEND_URL}/pay/{obj.public_token}"

    def get_payment_link_available(self, obj: Invoice) -> bool:
        return can_invoice_expose_payment_page(obj)

    def get_eft_snapshot(self, obj: Invoice) -> dict:
        return get_invoice_eft_snapshot(obj)

    @transaction.atomic
    def create(self, validated_data):
        client_data = validated_data.pop("client")
        items_data = validated_data.pop("line_items")
        request = self.context.get("request")
        owner = request.user if request and request.user.is_authenticated else None
        client = self._upsert_client(client_data)
        invoice = Invoice.objects.create(owner=owner, client=client, **validated_data)
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
        if not instance.owner_id:
            request = self.context.get("request")
            if request and request.user.is_authenticated:
                instance.owner = request.user
        instance.save()

        if items_data is not None:
            replace_invoice_line_items(instance, items_data)
        else:
            recalculate_invoice_totals(instance)

        instance.refresh_from_db()
        return instance


class InvoiceListSerializer(serializers.ModelSerializer):
    client = ClientSerializer()
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

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
            "amount_paid",
            "outstanding_amount",
        )

class InvoiceEftSnapshotSerializer(serializers.Serializer):
    mode = serializers.CharField(allow_blank=True)
    banking_profile_id = serializers.IntegerField(allow_null=True)
    profile_name = serializers.CharField(allow_blank=True)
    account_holder_name = serializers.CharField(allow_blank=True)
    bank_name = serializers.CharField(allow_blank=True)
    account_number = serializers.CharField(allow_blank=True)
    account_type = serializers.CharField(allow_blank=True)
    branch_code = serializers.CharField(allow_blank=True)
    payment_reference = serializers.CharField()
    has_snapshot = serializers.BooleanField()


class InvoiceEftDetailsUpdateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=InvoiceEftSourceType.choices)
    banking_profile_id = serializers.PrimaryKeyRelatedField(
        queryset=UserBankingProfile.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    profile_name = serializers.CharField(required=False, allow_blank=True)
    account_holder_name = serializers.CharField(required=False, allow_blank=True)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    account_number = serializers.CharField(required=False, allow_blank=True)
    account_type = serializers.CharField(required=False, allow_blank=True)
    branch_code = serializers.CharField(required=False, allow_blank=True)
    payment_reference = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["banking_profile_id"].queryset = UserBankingProfile.objects.filter(
                user=request.user, is_active=True
            )

    def validate(self, attrs):
        mode = attrs["mode"]
        if mode == InvoiceEftSourceType.SAVED_PROFILE:
            if not attrs.get("banking_profile_id"):
                raise serializers.ValidationError({"banking_profile_id": "Choose a saved banking profile."})
            return attrs

        required_fields = ("profile_name", "account_holder_name", "bank_name", "account_number")
        missing_fields = [field for field in required_fields if not attrs.get(field)]
        if missing_fields:
            raise serializers.ValidationError({field: "This field is required for manual EFT details." for field in missing_fields})
        return attrs

    def save(self, **kwargs):
        invoice = self.context["invoice"]
        if self.validated_data["mode"] == InvoiceEftSourceType.SAVED_PROFILE:
            return attach_saved_banking_profile_to_invoice(
                invoice,
                self.validated_data["banking_profile_id"],
                payment_reference=self.validated_data.get("payment_reference", ""),
            )

        return attach_manual_eft_details_to_invoice(
            invoice,
            profile_name=self.validated_data.get("profile_name", ""),
            account_holder_name=self.validated_data.get("account_holder_name", ""),
            bank_name=self.validated_data.get("bank_name", ""),
            account_number=self.validated_data.get("account_number", ""),
            account_type=self.validated_data.get("account_type", ""),
            branch_code=self.validated_data.get("branch_code", ""),
            payment_reference=self.validated_data.get("payment_reference", ""),
        )


class PublicInvoicePaymentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name")
    total = serializers.DecimalField(max_digits=12, decimal_places=2, source="total_amount")
    tax = serializers.DecimalField(max_digits=12, decimal_places=2, source="tax_amount")
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_reference = serializers.CharField(source="resolved_payment_reference")
    eft_details = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "invoice_number",
            "client_name",
            "issue_date",
            "due_date",
            "status",
            "subtotal",
            "tax",
            "total",
            "amount_paid",
            "outstanding_amount",
            "eft_details",
            "payment_reference",
        )

    def get_eft_details(self, obj: Invoice) -> dict:
        return {
            "profile_name": obj.eft_profile_name,
            "account_holder_name": obj.eft_account_holder_name,
            "bank_name": obj.eft_bank_name,
            "account_number": obj.eft_account_number,
            "account_type": obj.eft_account_type,
            "branch_code": obj.eft_branch_code,
        }


class ReminderRequestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=ReminderChannel.choices, default=ReminderChannel.EMAIL)


class DashboardSummarySerializer(serializers.Serializer):
    total_invoices = serializers.IntegerField()
    unpaid_invoices = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    total_amount_outstanding = serializers.DecimalField(max_digits=12, decimal_places=2)


class RecurringInvoiceLineItemTemplateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_quantity(self, value):
        if value != value.to_integral_value():
            raise serializers.ValidationError("Quantity must be a whole number.")
        return value


class RecurringInvoiceSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(queryset=Client.objects.all(), source="client", write_only=True)
    contractor = ContractorSerializer(read_only=True)
    contractor_id = serializers.PrimaryKeyRelatedField(
        queryset=Contractor.objects.all(),
        source="contractor",
        write_only=True,
        allow_null=True,
        required=False,
    )
    line_items_template = RecurringInvoiceLineItemTemplateSerializer(many=True)

    class Meta:
        model = RecurringInvoice
        fields = (
            "id",
            "template_name",
            "client",
            "client_id",
            "contractor",
            "contractor_id",
            "frequency",
            "start_date",
            "end_date",
            "next_run_date",
            "status",
            "currency",
            "payment_terms_days",
            "tax_type",
            "tax_rate",
            "notes",
            "line_items_template",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "next_run_date", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        owner = request.user if request and request.user.is_authenticated else None
        if owner:
            self.fields["client_id"].queryset = Client.objects.filter(owner=owner)
            self.fields["contractor_id"].queryset = Contractor.objects.filter(owner=owner)

    def validate_line_items_template(self, value):
        if not value:
            raise serializers.ValidationError("At least one line item template is required.")
        return value

    def validate_currency(self, value):
        normalized = value.upper()
        if normalized not in CurrencyCode.values:
            raise serializers.ValidationError("Currency must be either ZAR or USD.")
        return normalized

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        frequency = attrs.get("frequency", getattr(self.instance, "frequency", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        status = attrs.get("status", getattr(self.instance, "status", None))

        schedule_fields = {"start_date", "frequency", "end_date"}
        schedule_changed = self.instance is None or any(field in attrs for field in schedule_fields)
        status_changed = self.instance is not None and "status" in attrs and attrs["status"] != self.instance.status

        if status == "cancelled":
            attrs["next_run_date"] = None
            return attrs

        if start_date and frequency:
            if self.instance and not schedule_changed and not status_changed:
                attrs["next_run_date"] = self.instance.next_run_date
            else:
                next_run_date = resolve_recurring_next_run_date(start_date, frequency)
                if end_date and next_run_date > end_date:
                    raise serializers.ValidationError(
                        {"end_date": "End date must allow at least one future scheduled invoice."}
                    )
                attrs["next_run_date"] = next_run_date
        return attrs

    def _normalize_line_items_template(self, line_items_template: list[dict]) -> list[dict]:
        return [
            {
                "description": item["description"],
                "quantity": str(item["quantity"]),
                "unit_price": str(item["unit_price"]),
            }
            for item in line_items_template
        ]

    def create(self, validated_data):
        validated_data["line_items_template"] = self._normalize_line_items_template(validated_data["line_items_template"])
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["owner"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "line_items_template" in validated_data:
            validated_data["line_items_template"] = self._normalize_line_items_template(validated_data["line_items_template"])
        if not instance.owner_id:
            request = self.context.get("request")
            if request and request.user.is_authenticated:
                validated_data["owner"] = request.user
        return super().update(instance, validated_data)
