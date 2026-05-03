from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import BusinessProfile, UserBankingProfile
from apps.clients.models import Client
from apps.invoices.models import CurrencyCode, Invoice, InvoiceStatus, TaxType
from apps.invoices.services import recalculate_invoice_totals


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:3000",
)
class AuthenticationApiTests(APITestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="owner@example.test",
            email="owner@example.test",
            password=self.password,
            first_name="Owner",
            last_name="User",
        )

        self.invoice_client = Client.objects.create(
            owner=self.user,
            name="Northwind Studio",
            email="billing@northwind.test",
            address="54 Main Road",
            phone_number="+27123456789",
        )
        self.invoice = Invoice.objects.create(
            owner=self.user,
            client=self.invoice_client,
            invoice_number="INV-AUTH-001",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency=CurrencyCode.USD,
            tax_type=TaxType.NONE,
            tax_rate=Decimal("0.00"),
            payment_page_enabled=True,
            eft_account_holder_name="Invoice Manager Pty Ltd",
            eft_bank_name="Example Bank",
            eft_account_number="1234567890",
            eft_account_type="Business",
            eft_branch_code="250655",
        )
        self.invoice.line_items.create(description="Retainer", quantity=1, unit_price=Decimal("500.00"))
        recalculate_invoice_totals(self.invoice)
        self.invoice.refresh_from_db()

    def test_register_creates_session_and_returns_user(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "email": "newuser@example.test",
                "password": "AnotherStrong123!",
                "confirm_password": "AnotherStrong123!",
                "first_name": "New",
                "last_name": "User",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "newuser@example.test")
        me_response = self.client.get(reverse("auth-me"))
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["email"], "newuser@example.test")

    def test_register_optionally_creates_default_banking_profile(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "email": "banked@example.test",
                "password": "AnotherStrong123!",
                "confirm_password": "AnotherStrong123!",
                "first_name": "Banked",
                "last_name": "User",
                "banking_profile": {
                    "profile_name": "Primary business account",
                    "account_holder_name": "Banked User Pty Ltd",
                    "bank_name": "FNB",
                    "account_number": "12345678901",
                    "account_type": "Business Cheque",
                    "branch_code": "250655",
                    "default_payment_reference": "BANKED-001",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="banked@example.test")
        profile = UserBankingProfile.objects.get(user=user)
        self.assertEqual(profile.profile_name, "Primary business account")
        self.assertTrue(profile.is_default)

    def test_register_rejects_invalid_partial_optional_banking_details(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "email": "partial-bank@example.test",
                "password": "AnotherStrong123!",
                "confirm_password": "AnotherStrong123!",
                "banking_profile": {
                    "profile_name": "Incomplete profile",
                    "bank_name": "FNB",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("banking_profile", response.data)

    def test_register_rejects_duplicate_email(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "email": self.user.email,
                "password": "AnotherStrong123!",
                "confirm_password": "AnotherStrong123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_succeeds_with_email_and_password(self):
        response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        me_response = self.client.get(reverse("auth-me"))
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["email"], self.user.email)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"][0], "Invalid email or password.")

    def test_logout_clears_authenticated_session(self):
        self.client.post(reverse("auth-login"), {"email": self.user.email, "password": self.password}, format="json")

        logout_response = self.client.post(reverse("auth-logout"), {}, format="json")
        me_response = self.client.get(reverse("auth-me"))

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(me_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_forgot_password_returns_safe_message_for_unknown_email(self):
        response = self.client.post(
            reverse("auth-forgot-password"),
            {"email": "missing@example.test"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "If an account exists for that email, a password reset link has been sent.",
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_allows_login_with_new_password(self):
        forgot_response = self.client.post(
            reverse("auth-forgot-password"),
            {"email": self.user.email},
            format="json",
        )

        self.assertEqual(forgot_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        reset_response = self.client.post(
            reverse("auth-reset-password"),
            {
                "uid": uid,
                "token": token,
                "password": "FreshStrong123!",
                "confirm_password": "FreshStrong123!",
            },
            format="json",
        )

        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
        self.assertIn("/reset-password?uid=", mail.outbox[0].body)

        old_login_response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        new_login_response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": "FreshStrong123!"},
            format="json",
        )

        self.assertEqual(old_login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(new_login_response.status_code, status.HTTP_200_OK)

    def test_password_reset_rejects_invalid_token(self):
        response = self.client.post(
            reverse("auth-reset-password"),
            {
                "uid": "bad",
                "token": "bad-token",
                "password": "FreshStrong123!",
                "confirm_password": "FreshStrong123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)

    def test_internal_endpoints_are_blocked_when_unauthenticated(self):
        anonymous_client = APIClient()

        list_response = anonymous_client.get(reverse("invoice-list"))
        detail_response = anonymous_client.get(reverse("invoice-detail", args=[self.invoice.id]))

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(detail_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_payment_page_remains_accessible_without_auth(self):
        anonymous_client = APIClient()

        response = anonymous_client.get(reverse("public-invoice-payment", args=[self.invoice.public_token]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["invoice_number"], self.invoice.invoice_number)

    def test_banking_profile_crud_and_default_switching(self):
        self.client.force_authenticate(self.user)

        create_response = self.client.post(
            reverse("banking-profile-list"),
            {
                "profile_name": "Primary account",
                "account_holder_name": "Owner User Pty Ltd",
                "bank_name": "FNB",
                "account_number": "12345678901",
                "account_type": "Business Cheque",
                "branch_code": "250655",
                "default_payment_reference": "OWNER-001",
                "is_default": True,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        first_profile_id = create_response.data["id"]

        second_response = self.client.post(
            reverse("banking-profile-list"),
            {
                "profile_name": "Secondary account",
                "account_holder_name": "Owner User Pty Ltd",
                "bank_name": "ABSA",
                "account_number": "22222222222",
                "account_type": "Business Cheque",
                "branch_code": "632005",
                "default_payment_reference": "OWNER-002",
                "is_default": False,
            },
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        set_default_response = self.client.post(
            reverse("banking-profile-set-default", args=[second_response.data["id"]]),
            {},
            format="json",
        )
        self.assertEqual(set_default_response.status_code, status.HTTP_200_OK)

        first_profile = UserBankingProfile.objects.get(id=first_profile_id)
        second_profile = UserBankingProfile.objects.get(id=second_response.data["id"])
        self.assertFalse(first_profile.is_default)
        self.assertTrue(second_profile.is_default)

        patch_response = self.client.patch(
            reverse("banking-profile-detail", args=[second_profile.id]),
            {"bank_name": "Nedbank"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["bank_name"], "Nedbank")

    def test_banking_profile_access_is_user_scoped(self):
        other_profile = UserBankingProfile.objects.create(
            user=self.user,
            profile_name="Primary account",
            account_holder_name="Owner User Pty Ltd",
            bank_name="FNB",
            account_number="12345678901",
            account_type="Business Cheque",
            branch_code="250655",
            default_payment_reference="OWNER-001",
            is_default=True,
        )
        other_user = User.objects.create_user(
            username="other-banking@example.test",
            email="other-banking@example.test",
            password="StrongPass123!",
        )
        self.client.force_authenticate(other_user)

        detail_response = self.client.get(reverse("banking-profile-detail", args=[other_profile.id]))
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_business_profile_create_and_update(self):
        self.client.force_authenticate(self.user)

        create_response = self.client.post(
            reverse("business-profile"),
            {
                "business_name": "Owner User Consulting",
                "business_type": "sole_proprietor",
                "registration_number": "",
                "vat_number": "",
                "trading_name": "Owner Consulting",
                "contact_email": "hello@owner.test",
                "contact_phone_number": "+27123456789",
                "business_address": "12 Main Road, Johannesburg",
                "verification_status": "not_started",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["business_name"], "Owner User Consulting")
        self.assertEqual(create_response.data["verification_status"], "not_started")
        self.assertEqual(create_response.data["completeness_percentage"], 75)

        update_response = self.client.patch(
            reverse("business-profile"),
            {
                "vat_number": "4123456789",
                "verification_status": "pending",
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["vat_number"], "4123456789")
        self.assertEqual(update_response.data["verification_status"], "pending")
        self.assertEqual(update_response.data["completeness_percentage"], 88)

    def test_business_profile_is_user_scoped(self):
        BusinessProfile.objects.create(
            user=self.user,
            business_name="Owner Business",
            business_type="company",
            contact_email="owner@example.test",
            contact_phone_number="+27123456789",
            business_address="Owner address",
        )
        other_user = User.objects.create_user(
            username="other-business@example.test",
            email="other-business@example.test",
            password="StrongPass123!",
        )
        self.client.force_authenticate(other_user)

        missing_response = self.client.get(reverse("business-profile"))
        create_response = self.client.post(
            reverse("business-profile"),
            {
                "business_name": "Other Business",
                "business_type": "company",
                "contact_email": "other@example.test",
                "contact_phone_number": "+27111111111",
                "business_address": "Other address",
            },
            format="json",
        )

        self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["business_name"], "Other Business")

    def test_business_profile_completeness_calculation(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            reverse("business-profile"),
            {
                "business_name": "Completeness Pty Ltd",
                "business_type": "company",
                "registration_number": "2024/123456/07",
                "vat_number": "4123456789",
                "trading_name": "Completeness",
                "contact_email": "complete@example.test",
                "contact_phone_number": "+27123456789",
                "business_address": "100 Complete Street",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["completeness_percentage"], 100)

    def test_business_profile_rejects_invalid_verification_status(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            reverse("business-profile"),
            {
                "business_name": "Invalid Status Pty Ltd",
                "business_type": "company",
                "contact_email": "invalid@example.test",
                "contact_phone_number": "+27123456789",
                "business_address": "1 Invalid Road",
                "verification_status": "approved",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("verification_status", response.data)
