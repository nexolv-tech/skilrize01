from django.urls import path

from . import views

urlpatterns = [
    path(
        "payments/callbacks/swich/payin/",
        views.swich_payin_callback,
        name="swich-payin-callback",
    ),
    path("payments/payout-profile/", views.PayoutProfileView.as_view(), name="payout-profile"),
    path(
        "payments/payout-profile/verify-title/",
        views.VerifyPayoutTitleView.as_view(),
        name="payout-profile-verify-title",
    ),
    path("payments/payouts/", views.MyPayoutsView.as_view(), name="my-payouts"),
]
