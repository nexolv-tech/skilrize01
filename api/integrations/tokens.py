"""A connection's access token, renewed first when it has run out.

Zoom and Google access tokens last an hour and Figma's ninety days, so a
token stored at connect time is soon useless on its own. Every provider call
asks for its token here rather than reading `connection.access_token`, and a
token that has expired, or is about to, is exchanged for a fresh one using
the connection's refresh token. GitHub and Notion tokens do not expire and
pass straight through.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import IntegrationConnection
from .providers import registry
from .providers.base import IntegrationError

#: Renew a little early, so a token cannot lapse between this check and the
#: provider call it is about to make.
_MARGIN = timedelta(minutes=2)


def _fresh(connection: IntegrationConnection) -> bool:
    return connection.expires_at is None or connection.expires_at > timezone.now() + _MARGIN


def access_token(connection: IntegrationConnection) -> str:
    """A token the provider will accept, refreshing and saving it if needed.

    Raises `IntegrationError` with a reconnect instruction when the token
    cannot be renewed: no refresh token was issued, or the provider refused
    it because the user revoked access on their side.
    """
    if _fresh(connection):
        return connection.access_token

    reconnect = IntegrationError(
        f"Your {connection.get_provider_display()} connection has expired. "
        f"Reconnect it under Settings → Connected accounts."
    )
    module = registry.get(connection.provider)
    if not hasattr(module, "refresh"):
        raise reconnect

    # Locked, because Zoom rotates the refresh token on every use: two
    # requests renewing at once would each spend the same refresh token, and
    # the loser's failure would look like a revoked connection.
    with transaction.atomic():
        locked = IntegrationConnection.objects.select_for_update().get(pk=connection.pk)
        if not _fresh(locked):
            if not locked.refresh_token:
                raise reconnect
            try:
                result = module.refresh(locked.refresh_token)
            except IntegrationError as exc:
                raise reconnect from exc
            locked.access_token = result["access_token"]
            if result.get("refresh_token"):
                locked.refresh_token = result["refresh_token"]
            locked.expires_at = (
                timezone.now() + timedelta(seconds=result["expires_in"])
                if result.get("expires_in")
                else None
            )
            locked.save(update_fields=["access_token", "refresh_token", "expires_at", "updated_at"])

    connection.access_token = locked.access_token
    connection.refresh_token = locked.refresh_token
    connection.expires_at = locked.expires_at
    return connection.access_token
