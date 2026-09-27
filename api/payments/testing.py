"""
Test helpers for payments: play Swich's part in a checkout (D55).

`swich_pays` sends the callback Swich would, signed with the test SecretKey
the suite runs with (`conftest._payments_open`), so a test pays for an order
through the same checksum-verified path production uses rather than by
setting a milestone funded directly.
"""

from __future__ import annotations

from rest_framework.test import APIClient

from .models import Charge
from .swich import callback_checksum


def swich_says(reference: str, status: str = "Success", *, amount: str | None = None):
    """Deliver Swich's callback for a charge and return the response."""
    charge = Charge.objects.get(reference=reference)
    amount = amount if amount is not None else f"{charge.amount:.2f}"
    order_id = f"SW-{reference[-6:]}"
    params = {
        "CustomerTransactionId": reference,
        "OrderId": order_id,
        "Amount": amount,
        "Status": status,
        "checksum": callback_checksum(
            customer_transaction_id=reference, order_id=order_id, amount=amount, status=status
        ),
    }
    return APIClient().get("/api/v1/payments/swich/callback/", params)


def swich_pays(response):
    """Complete the payment a "pay" endpoint just started. Takes that
    endpoint's response and returns Swich's callback response."""
    assert response.status_code in (200, 201), getattr(response, "data", response)
    return swich_says(response.data["payment_reference"])
