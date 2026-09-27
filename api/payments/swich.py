"""
Swich Pay In: the hosted checkout buyers pay on (D55).

Restored from the adapter built and checked against Swich's real sandbox in
D41 and removed in D42; the endpoints and checksum formulas are Swich's own
published ones (`https://api-docs.swichnow.com/`), unchanged. Only the Pay
In half is here: freelancer payouts are sent by an operator and recorded in
the admin console, until Swich Payouts is enabled on the merchant account.

**Hosted checkout, so no card data here.** The buyer's browser goes to
Swich's page, where they choose a card, Easypaisa, JazzCash or 1Bill.
SkilRize never sees a card number or wallet PIN and stays out of PCI scope.
The redirect is authenticated with the merchant's `clientId` and a checksum,
not a bearer token, because the customer's browser makes that request.

**The callback decides, never the redirect.** Swich calls
`payments/swich/callback/` server to server with the outcome and a checksum
only the merchant's SecretKey can produce. The buyer's return to the site
changes nothing; it only shows what the callback already recorded.

**Environments.** `SWICH_ENV` selects Swich's sandbox or production hosts,
independently of this server's own `ENVIRONMENT`. The production hostnames
follow Swich's `sandbox-x` to `x` naming and have not yet been called with
a live merchant account: confirm them with Swich when the account opens.
"""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

from django.conf import settings

_PAYIN_HOSTS = {
    "sandbox": "https://sandbox-payin-pwa.swichnow.com",
    "production": "https://payin-pwa.swichnow.com",
}

#: The ways to pay on Swich's page, as buyers know them.
METHODS = [
    {"id": "card", "label": "Debit or credit card", "detail": "Visa, Mastercard, UnionPay"},
    {"id": "easypaisa", "label": "Easypaisa", "detail": "Mobile wallet"},
    {"id": "jazzcash", "label": "JazzCash", "detail": "Mobile wallet"},
    {"id": "1bill", "label": "1Bill", "detail": "Pay by voucher from any bank app or agent"},
]


class SwichUnavailable(Exception):
    """Swich is not configured on this server: no payment can be started."""


def is_enabled() -> bool:
    return bool(settings.SWICH_ENABLED and settings.SWICH_CLIENT_ID and settings.SWICH_SECRET_KEY)


def _hex_hmac(message: str) -> str:
    return hmac.new(
        settings.SWICH_SECRET_KEY.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def checkout_checksum(*, customer_transaction_id: str, item: str, amount: str) -> str:
    """`HMACSHA256("Swich:{customerTransactionId}:{item}:{amount}", SecretKey)`,
    Swich's documented formula for the hosted checkout redirect."""
    return _hex_hmac(f"Swich:{customer_transaction_id}:{item}:{amount}")


def build_checkout_url(
    *,
    customer_transaction_id: str,
    amount: str,
    item: str,
    description: str,
    payee_name: str,
    email: str,
    msisdn: str = "",
    currency: str = "PKR",
    success_redirect_url: str | None = None,
) -> str:
    """Where to send the buyer's browser to pay. No network call: the URL
    carries the checksum Swich's own page verifies. `channel=0` offers every
    method the merchant account has enabled."""
    if not is_enabled():
        raise SwichUnavailable("Swich is not enabled on this server.")
    params = {
        "clientId": settings.SWICH_CLIENT_ID,
        "customerTransactionId": customer_transaction_id,
        "item": item,
        "amount": amount,
        "channel": 0,
        "description": description,
        "PayeeName": payee_name,
        "Email": email,
        "MSISDN": msisdn,
        "currency": currency,
        "checksum": checkout_checksum(
            customer_transaction_id=customer_transaction_id, item=item, amount=amount
        ),
    }
    if success_redirect_url:
        params["successRedirectUrl"] = success_redirect_url
    host = _PAYIN_HOSTS.get(settings.SWICH_ENV, _PAYIN_HOSTS["sandbox"])
    return f"{host}/?{urlencode(params)}"


def callback_checksum(
    *, customer_transaction_id: str, order_id: str, amount: str, status: str
) -> str:
    """`HMACSHA256("SWCallback:{CustomerTransactionId}:{OrderId}:{Amount}:{Status}",
    SecretKey)`, Swich's documented Pay In callback formula."""
    return _hex_hmac(f"SWCallback:{customer_transaction_id}:{order_id}:{amount}:{status}")


def verify_callback_checksum(
    *, customer_transaction_id: str, order_id: str, amount: str, status: str, checksum: str
) -> bool:
    """Constant-time comparison: a checksum check is a security boundary."""
    if not settings.SWICH_SECRET_KEY:
        return False
    expected = callback_checksum(
        customer_transaction_id=customer_transaction_id,
        order_id=order_id,
        amount=amount,
        status=status,
    )
    return hmac.compare_digest(expected, checksum)
