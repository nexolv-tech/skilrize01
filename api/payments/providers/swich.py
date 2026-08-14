"""
Swich adapter — Phase 3, D41.

Every endpoint, field name, and checksum formula here is taken from Swich's
own published reference (`https://api-docs.swichnow.com/`), not guessed —
the one place in this codebase where a wrong guess would mean real money
moving incorrectly, so nothing here shipped without being checked against
the actual documentation first, and the auth call has been run against the
real sandbox before this adapter's tests were written.

**Two directions, two auth schemes.** Pay In (the client funding a
milestone) uses Swich's *hosted* checkout — SkilRize never sees a card
number, never enters PCI scope, and authenticates the redirect with a
`clientId` + checksum rather than a bearer token, because the customer's
browser is the one making that request, not our server. Payout (IBFT,
paying the freelancer) is a server-to-server call authenticated with the
same OAuth2 client-credentials bearer token used everywhere else in this
adapter — a fundamentally different trust boundary for a fundamentally
different kind of call.

**Why IBFT and not Remittance.** Swich's "Remittance" product is inbound —
it requires a beneficiary CNIC and pays into a Pakistani account for
someone receiving money *from abroad*, not a general-purpose way to send
money out of Pakistan. It cannot pay a freelancer outside Pakistan, and
this platform's freelancer base is Pakistan-based (student portals scoped
to Pakistani universities), so IBFT — domestic bank transfer — is the
correct product, not a fallback chosen for lack of a better one.

**Environments.** Swich's *own* environment (sandbox vs production) is a
separate axis from this app's `DEBUG`/`ENVIRONMENT` — `SWICH_ENV` exists so
a production SkilRize deployment can still point at Swich's sandbox until
the real merchant account is approved. The production hostnames below
follow Swich's documented `sandbox-x.swichnow.com` → `x.swichnow.com`
naming pattern but have not been called for real (this environment has no
production Swich account yet) — confirm them with Swich integration
support before the first live cutover, the same caveat every adapter in
this codebase carries for its production path.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from django.conf import settings

from .base import SwichError, SwichUnavailable, session

_TIMEOUT = 15

_HOSTS = {
    "sandbox": {
        "auth": "https://sandbox-auth.swichnow.com",
        "api": "https://sandbox-api.swichnow.com",
        "payin_pwa": "https://sandbox-payin-pwa.swichnow.com",
    },
    # Not yet exercised against a real production Swich account — see the
    # module docstring's "Environments" note.
    "production": {
        "auth": "https://auth.swichnow.com",
        "api": "https://api.swichnow.com",
        "payin_pwa": "https://payin-pwa.swichnow.com",
    },
}

#: A bearer token per process, refreshed a little before its real 3600s
#: expiry so a request never races an expiring token. Module-level rather
#: than per-request, the same trade `core.push._credentials` makes for FCM:
#: this is called from request-handling and Celery tasks alike, and neither
#: needs its own thread-safety story for a value this cheap to refetch on a
#: cache miss.
_token_cache: dict[str, object] = {"token": None, "expires_at": 0.0}


def is_enabled() -> bool:
    return bool(
        settings.SWICH_ENABLED
        and settings.SWICH_CLIENT_ID
        and settings.SWICH_CLIENT_SECRET
        and settings.SWICH_SECRET_KEY
    )


def _hosts() -> dict[str, str]:
    return _HOSTS.get(settings.SWICH_ENV, _HOSTS["sandbox"])


def get_token() -> str:
    """A bearer token for every server-to-server call. Raises
    `SwichUnavailable` when Swich is not configured, `SwichError` when the
    token exchange itself fails."""
    if not is_enabled():
        raise SwichUnavailable("Swich is not enabled in this environment.")

    cached = _token_cache["token"]
    if cached and time.time() < _token_cache["expires_at"]:
        return cached  # type: ignore[return-value]

    try:
        response = session.post(
            f"{_hosts()['auth']}/connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.SWICH_CLIENT_ID,
                "client_secret": settings.SWICH_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_TIMEOUT,
        )
    except Exception as exc:  # network failure, DNS, timeout
        raise SwichError(f"Could not reach Swich auth: {exc}") from exc

    if response.status_code != 200:
        raise SwichError(
            f"Swich token exchange failed ({response.status_code}): {response.text[:300]}"
        )

    data = response.json()
    token = data["access_token"]
    # Refresh 60s early rather than exactly at expiry, so a request that
    # starts just before the deadline does not get a token that dies
    # mid-flight on Swich's side.
    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + int(data.get("expires_in", 3600)) - 60
    return token


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}


def _hex_hmac(message: str) -> str:
    return hmac.new(
        settings.SWICH_SECRET_KEY.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


# --- Pay In: hosted checkout ------------------------------------------------


def checkout_checksum(*, customer_transaction_id: str, item: str, amount: str) -> str:
    """`checksum = HMACSHA256("Swich:{customer_transaction_id}:{item}:{amount}",
    SecretKey)` — Swich's documented formula for the Landing Page redirect,
    verbatim."""
    return _hex_hmac(f"Swich:{customer_transaction_id}:{item}:{amount}")


def build_checkout_url(
    *,
    customer_transaction_id: str,
    amount: str,
    item: str,
    description: str,
    payee_name: str,
    email: str,
    msisdn: str,
    currency: str = "PKR",
    success_redirect_url: str | None = None,
) -> str:
    """The URL to send a client's browser to for Swich's hosted checkout —
    every Pay In channel (card, e-wallet, bank, QR, RTP) from one surface.
    Not a server-to-server call: no bearer token, no network request here,
    just the checksum Swich's own redirect handler will verify.

    Raises `SwichUnavailable` when Swich is not configured — checked here
    even though this builds a URL rather than calling out, so a caller
    cannot accidentally hand a client a checkout link for a disabled
    provider.
    """
    if not is_enabled():
        raise SwichUnavailable("Swich is not enabled in this environment.")

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
    return f"{_hosts()['payin_pwa']}/?{urlencode(params)}"


def verify_callback_checksum(
    *, customer_transaction_id: str, order_id: str, amount: str, status: str, checksum: str
) -> bool:
    """`HMACSHA256("SWCallback:CustomerTransactionId:OrderId:Amount:Status",
    SecretKey)` — Swich's documented Pay In callback formula. `hmac.compare_digest`
    rather than `==`, the same discipline `accounts.auth` uses for every
    other signature comparison in this codebase: a checksum check is a
    security boundary, and `==` on a hex string is timing-attackable."""
    expected = _hex_hmac(f"SWCallback:{customer_transaction_id}:{order_id}:{amount}:{status}")
    return hmac.compare_digest(expected, checksum)


# --- Payout: IBFT (domestic bank transfer) ----------------------------------


def fetch_title(
    *,
    bank_code: str,
    bank_name: str,
    account_number: str,
    msisdn: str,
    amount: str,
    country_code: str = "92",
) -> dict:
    """Look up the account holder's name for a bank account before paying
    it — lets a freelancer's payout profile show "you're about to be paid
    at: <name>" so a mistyped account number is caught by a name mismatch,
    not by money going to a stranger."""
    if not is_enabled():
        raise SwichUnavailable("Swich is not enabled in this environment.")

    try:
        response = session.get(
            f"{_hosts()['api']}/gateway/payout/transaction/fetch/title",
            headers=_auth_headers(),
            params={
                "BankCode": bank_code,
                "BankName": bank_name,
                "AccountNumber": account_number,
                "MSISDN": msisdn,
                "Amount": amount,
                "countryCode": country_code,
            },
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        raise SwichError(f"Could not reach Swich payout: {exc}") from exc

    if response.status_code != 200:
        raise SwichError(
            f"Swich title fetch failed ({response.status_code}): {response.text[:300]}"
        )
    return response.json()


def create_payout(
    *,
    customer_transaction_id: str,
    account_number: str,
    account_title: str,
    amount: str,
    bank_code: str,
    bank_name: str,
    cnic: str,
    msisdn: str,
    name: str,
    currency: str = "PKR",
    country_code: str = "92",
) -> dict:
    """Disburse funds to a freelancer's bank account via IBFT. Raises
    `SwichError` on anything but a 200 — the caller (`Payout.status`) is
    what records the outcome; this function never silently swallows a
    failed payout."""
    if not is_enabled():
        raise SwichUnavailable("Swich is not enabled in this environment.")

    try:
        response = session.post(
            f"{_hosts()['api']}/gateway/payout/transaction/ibft",
            headers=_auth_headers(),
            json={
                "customerTransactionId": customer_transaction_id,
                "accountNumber": account_number,
                "accountTitle": account_title,
                "amount": amount,
                "bankCode": bank_code,
                "bankName": bank_name,
                "cnic": cnic,
                "countryCode": country_code,
                "currency": currency,
                "msisdn": msisdn,
                "name": name,
            },
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        raise SwichError(f"Could not reach Swich payout: {exc}") from exc

    data = response.json() if response.content else {}
    if response.status_code != 200:
        raise SwichError(
            f"Swich IBFT payout failed ({response.status_code}): {response.text[:300]}"
        )
    return data


def inquire_payout(customer_transaction_id: str) -> dict:
    """Status of a previously submitted IBFT payout — used to reconcile a
    payout whose original request timed out on our side but may have
    succeeded on Swich's."""
    if not is_enabled():
        raise SwichUnavailable("Swich is not enabled in this environment.")

    try:
        response = session.get(
            f"{_hosts()['api']}/gateway/payout/transaction/inquire",
            headers=_auth_headers(),
            params={"customerTransactionId": customer_transaction_id},
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        raise SwichError(f"Could not reach Swich payout: {exc}") from exc

    if response.status_code != 200:
        raise SwichError(
            f"Swich payout inquiry failed ({response.status_code}): {response.text[:300]}"
        )
    return response.json()


def get_balance() -> dict:
    """The merchant's own Swich float balance — checked before a payout
    batch large enough to matter, and worth surfacing on the admin console
    (Task #52) so a low balance is visible before it starts failing
    payouts."""
    if not is_enabled():
        raise SwichUnavailable("Swich is not enabled in this environment.")

    try:
        response = session.get(
            f"{_hosts()['api']}/gateway/payout/balance", headers=_auth_headers(), timeout=_TIMEOUT
        )
    except Exception as exc:
        raise SwichError(f"Could not reach Swich payout: {exc}") from exc

    if response.status_code != 200:
        raise SwichError(
            f"Swich balance check failed ({response.status_code}): {response.text[:300]}"
        )
    return response.json()
