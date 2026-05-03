from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BankingProfileViewSet, BusinessProfileView

router = DefaultRouter()
router.register("banking-profiles", BankingProfileViewSet, basename="banking-profile")

urlpatterns = [
    path("business-profile/", BusinessProfileView.as_view(), name="business-profile"),
    path("", include(router.urls)),
]
