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

from apps.clients.models import Client
from apps.invoices.models import Invoice, InvoiceStatus, TaxType
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
            name="Northwind Studio",
            email="billing@northwind.test",
            address="54 Main Road",
            phone_number="+27123456789",
        )
        self.invoice = Invoice.objects.create(
            client=self.invoice_client,
            invoice_number="INV-AUTH-001",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.SENT,
            currency="USD",
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
