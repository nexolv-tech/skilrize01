from django.urls import path

from . import views

urlpatterns = [
    path("payments/options/", views.payment_options, name="payment-options"),
    path("payments/payout-institutions/", views.payout_institutions, name="payout-institutions"),
    path("payments/swich/callback/", views.swich_callback, name="swich-callback"),
    path("payments/charges/<str:reference>/", views.charge_status, name="charge-status"),
    path("payments/payout-profile/", views.PayoutProfileView.as_view(), name="payout-profile"),
    path("payments/payouts/", views.MyPayoutsView.as_view(), name="my-payouts"),
    path("payments/refunds/", views.MyRefundsView.as_view(), name="my-refunds"),
]
