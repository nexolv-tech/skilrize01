"""
Swich Pay In: the hosted checkout buyers pay on (D55).

Restored from the adapter built and checked against Swich's real sandbox in
D41 and removed in D42; the endpoints and checksum formulas are Swich's own
published ones (`https://api-docs.swichnow.com/`), unchanged.

The second half (D56) is server to server, with an OAuth2 bearer token:
paying freelancers by IBFT to a bank account or an Easypaisa/JazzCash
wallet, refunding a Pay In payment, and asking where either stands. Swich
requires the calling server's IP address to be whitelisted for these.

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
import logging
import time
from decimal import Decimal
from urllib.parse import urlencode

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

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


_API_HOSTS = {
    "sandbox": "https://sandbox-api.swichnow.com",
    "production": "https://api.swichnow.com",
}
_AUTH_HOSTS = {
    "sandbox": "https://sandbox-auth.swichnow.com",
    "production": "https://auth.swichnow.com",
}
_TIMEOUT = 25


class SwichUnavailable(Exception):
    """Swich is not configured on this server: no payment can be started."""


class SwichError(Exception):
    """Swich refused a call or could not be reached. `code` is Swich's own
    response code when it gave one ("0000" is success)."""

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code


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


# --- Server to server: payouts and refunds (D56) --------------------------------

#: One HTTP session, deliberately without automatic retries: resending a
#: payout because a response was slow could pay someone twice. Callers ask
#: Swich where a payout stands (`inquire_payout`) before ever sending again.
_http = requests.Session()
_token: dict = {"value": "", "expires": 0.0}


def payouts_enabled() -> bool:
    """Payouts and refunds need the client secret for a bearer token, and the
    owner's say-so: Swich must whitelist this server's IP and the payout
    balance must be funded before they can work."""
    return bool(is_enabled() and settings.SWICH_PAYOUTS_ENABLED and settings.SWICH_CLIENT_SECRET)


def _env() -> str:
    return settings.SWICH_ENV if settings.SWICH_ENV in _API_HOSTS else "sandbox"


def _bearer() -> str:
    if _token["value"] and time.time() < _token["expires"]:
        return _token["value"]
    try:
        response = _http.post(
            f"{_AUTH_HOSTS[_env()]}/connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.SWICH_CLIENT_ID,
                "client_secret": settings.SWICH_CLIENT_SECRET,
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SwichError(f"Could not reach Swich to sign in: {exc}") from exc
    if response.status_code != 200:
        raise SwichError(f"Swich refused the sign-in ({response.status_code}).")
    data = response.json()
    _token["value"] = data["access_token"]
    # Renewed a minute early, so a call never starts with a dying token.
    _token["expires"] = time.time() + int(data.get("expires_in", 3600)) - 60
    return _token["value"]


def _call(method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
    """One server-to-server call. Returns Swich's JSON on success; raises
    `SwichError` with Swich's own message and code otherwise."""
    if not payouts_enabled():
        raise SwichUnavailable("Swich payouts are not enabled on this server.")
    try:
        response = _http.request(
            method,
            f"{_API_HOSTS[_env()]}{path}",
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {_bearer()}"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SwichError(f"Could not reach Swich: {exc}") from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code == 401:
        _token["value"] = ""
    if response.status_code != 200 or str(data.get("status", "")).lower() != "success":
        message = data.get("message") or data.get("error_description") or response.reason
        raise SwichError(f"Swich: {message}", str(data.get("code", response.status_code)))
    return data


def _amount(value: Decimal) -> str:
    return f"{value:.2f}"


def fetch_title(
    *, bank_code: str, bank_name: str, account_number: str, msisdn: str, amount: Decimal
) -> str:
    """The name the bank or wallet holds for an account, checked before
    paying it so a mistyped number is caught by a name, not by money going
    to a stranger."""
    data = _call(
        "GET",
        "/gateway/payout/transaction/fetch/title",
        params={
            "version": "v1.0",
            "BankCode": bank_code,
            "BankName": bank_name,
            "AccountNumber": account_number,
            "MSISDN": msisdn,
            "Amount": _amount(amount),
            "countryCode": "92",
        },
    )
    return str((data.get("data") or {}).get("accountTitleTo") or "")


def send_ibft(
    *,
    reference: str,
    bank_code: str,
    bank_name: str,
    account_number: str,
    account_title: str,
    name: str,
    cnic: str,
    msisdn: str,
    amount: Decimal,
) -> str:
    """Pay a bank account or wallet. Returns Swich's transaction id."""
    data = _call(
        "POST",
        "/gateway/payout/transaction/ibft",
        params={"version": "v1.0"},
        body={
            "customerTransactionId": reference,
            "accountNumber": account_number,
            "accountTitle": account_title,
            "bankCode": bank_code,
            "bankName": bank_name,
            "name": name,
            "cnic": cnic,
            "msisdn": msisdn,
            "amount": _amount(amount),
            "currency": "PKR",
            "countryCode": "92",
        },
    )
    return str(data.get("transactionId") or "")


def inquire_payout(reference: str) -> dict | None:
    """Where a payout stands, by our reference: `{"id", "status_text"}`, or
    None when Swich has no record of it (it was never received)."""
    try:
        data = _call(
            "GET",
            "/gateway/payout/transaction/inquire",
            params={"version": "v1.0", "CustomerTransactionId": reference},
        )
    except SwichError as exc:
        if "not found" in str(exc).lower() or exc.code in ("0007", "00007"):
            return None
        raise
    record = data.get("data") or {}
    if not record:
        return None
    return {"id": str(record.get("id") or ""), "status_text": str(record.get("statusText") or "")}


def payout_balance() -> Decimal:
    data = _call("GET", "/gateway/payout/balance", params={"version": "v1.0"})
    return Decimal(str((data.get("data") or {}).get("balance") or 0))


def refund_payin(*, swich_order_id: str, amount: Decimal, reason: str) -> None:
    """Return a Pay In payment to the card or wallet it came from. Swich
    refuses methods it cannot refund; the caller falls back to an operator."""
    _call(
        "POST",
        "/gateway/payin/v2.0/purchase/refund",
        body={"OrderId": swich_order_id, "Amount": _amount(amount), "Reason": reason[:500]},
    )
