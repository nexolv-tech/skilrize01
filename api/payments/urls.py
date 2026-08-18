from django.urls import path

from . import views

urlpatterns = [
    path(
        "payments/bank-transfer-instructions/",
        views.bank_transfer_instructions,
        name="bank-transfer-instructions",
    ),
    path("payments/payout-profile/", views.PayoutProfileView.as_view(), name="payout-profile"),
    path("payments/payouts/", views.MyPayoutsView.as_view(), name="my-payouts"),
]
