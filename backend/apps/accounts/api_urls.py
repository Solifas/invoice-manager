from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BankingProfileViewSet

router = DefaultRouter()
router.register("banking-profiles", BankingProfileViewSet, basename="banking-profile")

urlpatterns = [
    path("", include(router.urls)),
]
