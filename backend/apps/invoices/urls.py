from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InvoiceLineItemViewSet, InvoiceViewSet

router = DefaultRouter()
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("line-items", InvoiceLineItemViewSet, basename="line-item")

urlpatterns = [
    path("", include(router.urls)),
]
