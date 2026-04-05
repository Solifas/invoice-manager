from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClientLookupViewSet,
    ContractorLookupViewSet,
    InvoiceLineItemViewSet,
    InvoicePaymentViewSet,
    InvoiceViewSet,
    PublicInvoicePaymentView,
    RecurringInvoiceViewSet,
)

router = DefaultRouter()
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("line-items", InvoiceLineItemViewSet, basename="line-item")
router.register("payments", InvoicePaymentViewSet, basename="payment")
router.register("clients", ClientLookupViewSet, basename="client")
router.register("contractors", ContractorLookupViewSet, basename="contractor")
router.register("recurring-invoices", RecurringInvoiceViewSet, basename="recurring-invoice")

urlpatterns = [
    path("public/pay/<str:token>/", PublicInvoicePaymentView.as_view(), name="public-invoice-payment"),
    path("", include(router.urls)),
]
