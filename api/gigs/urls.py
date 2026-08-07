from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("gigs", views.GigViewSet, basename="gig")
router.register("orders", views.OrderViewSet, basename="order")
router.register("buyer-requests", views.BuyerRequestViewSet, basename="buyer-request")
router.register("custom-offers", views.CustomOfferViewSet, basename="custom-offer")

urlpatterns = [
    path("seller/dashboard/", views.seller_dashboard, name="seller-dashboard"),
    path("", include(router.urls)),
]
