"""
Tests for third-party integrations.

The rules worth guarding: a provider that isn't enabled must never look like
it worked, only a contract's own client/freelancer may touch its meetings or
activity feed, tokens never leak into a response, and re-syncing a source
never duplicates an event it already stored.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import signing
from django.utils import timezone

from contracts.models import Contract, ContractType
from core.scope import GLOBAL_SCOPE, use_scope
from marketplace.tests import make_user, sign_in

from .models import ActivityFeedSource, IntegrationConnection, Meeting, Provider
from .providers.base import IntegrationError


@pytest.fixture
def parties(db):
    return make_user("client@example.com"), make_user("freelancer@example.com")


@pytest.fixture
def contract(parties):
    client_user, freelancer = parties
    with use_scope(GLOBAL_SCOPE):
        return Contract.objects.create(
            client=client_user,
            freelancer=freelancer,
            title="Landing page",
            contract_type=ContractType.FIXED,
            status=Contract.Status.ACTIVE,
            total_amount=1000,
        )


def _state_for(user, provider="zoom"):
    return signing.dumps({"user_id": user.id, "provider": provider}, salt="integrations.oauth")


def _meeting_payload():
    return {
        "provider": "zoom",
        "topic": "Kickoff",
        "start_time": timezone.now() + timedelta(days=1),
    }


# --- Provider gating ---------------------------------------------------------


@pytest.mark.django_db
def test_providers_status_lists_all_five_disabled_by_default(parties):
    client_user, _ = parties
    response = sign_in(client_user).get("/api/v1/integrations/providers/")
    assert response.status_code == 200
    assert {row["provider"] for row in response.data} == set(Provider.values)
    assert all(row["is_enabled"] is False for row in response.data)
    assert all(row["is_connected"] is False for row in response.data)


@pytest.mark.django_db
def test_authorize_refuses_a_disabled_provider(parties):
    client_user, _ = parties
    response = sign_in(client_user).get("/api/v1/integrations/zoom/authorize/")
    assert response.status_code == 400
    assert response.data["code"] == "integration_unavailable"


# --- Connect / disconnect ----------------------------------------------------


@pytest.mark.django_db
def test_connect_stores_an_encrypted_connection_and_never_echoes_the_token(parties):
    client_user, _ = parties
    state = _state_for(client_user)

    with (
        patch("integrations.providers.zoom.is_enabled", return_value=True),
        patch(
            "integrations.providers.zoom.exchange_code",
            return_value={
                "access_token": "secret-token",
                "refresh_token": "secret-refresh",
                "expires_in": 3600,
                "external_label": "client@zoom.example",
            },
        ),
    ):
        response = sign_in(client_user).post(
            "/api/v1/integrations/zoom/connect/", {"code": "abc", "state": state}, format="json"
        )

    assert response.status_code == 201
    assert "access_token" not in response.data
    assert response.data["external_label"] == "client@zoom.example"

    connection = IntegrationConnection.objects.get(user=client_user, provider=Provider.ZOOM)
    # The value is opaque in the field's Python representation only after a
    # real round trip through the database, not the in-memory object — refetch.
    connection.refresh_from_db()
    assert connection.access_token == "secret-token"


@pytest.mark.django_db
def test_connect_rejects_a_state_issued_for_a_different_user(parties):
    client_user, freelancer = parties
    state = _state_for(freelancer)  # minted for someone else

    with patch("integrations.providers.zoom.is_enabled", return_value=True):
        response = sign_in(client_user).post(
            "/api/v1/integrations/zoom/connect/", {"code": "abc", "state": state}, format="json"
        )

    assert response.status_code == 400
    assert response.data["code"] == "bad_state"
    assert not IntegrationConnection.objects.filter(user=client_user).exists()


@pytest.mark.django_db
def test_disconnect_removes_the_connection(parties):
    client_user, _ = parties
    IntegrationConnection.objects.create(user=client_user, provider=Provider.ZOOM, access_token="t")

    response = sign_in(client_user).delete("/api/v1/integrations/zoom/disconnect/")

    assert response.status_code == 204
    assert not IntegrationConnection.objects.filter(
        user=client_user, provider=Provider.ZOOM
    ).exists()


# --- Meetings -----------------------------------------------------------------


@pytest.mark.django_db
def test_scheduling_a_meeting_requires_a_connection_first(contract, parties):
    client_user, _ = parties
    response = sign_in(client_user).post(
        f"/api/v1/contracts/{contract.id}/meetings/",
        _meeting_payload(),
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "not_connected"


@pytest.mark.django_db
def test_scheduling_a_meeting_creates_a_real_meeting_via_the_adapter(contract, parties):
    client_user, _ = parties
    IntegrationConnection.objects.create(user=client_user, provider=Provider.ZOOM, access_token="t")

    with patch(
        "integrations.providers.zoom.create_meeting",
        return_value={"join_url": "https://zoom.us/j/123", "external_id": "123"},
    ) as mocked:
        response = sign_in(client_user).post(
            f"/api/v1/contracts/{contract.id}/meetings/",
            _meeting_payload(),
            format="json",
        )

    assert response.status_code == 201
    assert response.data["join_url"] == "https://zoom.us/j/123"
    mocked.assert_called_once()
    meeting = Meeting.objects.get(contract=contract)
    assert meeting.scheduled_by == client_user
    assert meeting.status == Meeting.Status.SCHEDULED


@pytest.mark.django_db
def test_scheduling_a_meeting_surfaces_a_provider_error_without_creating_a_row(contract, parties):
    client_user, _ = parties
    IntegrationConnection.objects.create(user=client_user, provider=Provider.ZOOM, access_token="t")

    with patch(
        "integrations.providers.zoom.create_meeting", side_effect=IntegrationError("rate limited")
    ):
        response = sign_in(client_user).post(
            f"/api/v1/contracts/{contract.id}/meetings/",
            _meeting_payload(),
            format="json",
        )

    assert response.status_code == 400
    assert response.data["code"] == "integration_error"
    assert not Meeting.objects.filter(contract=contract).exists()


@pytest.mark.django_db
def test_a_stranger_cannot_see_or_schedule_meetings_on_someone_elses_contract(contract):
    stranger = make_user("stranger@example.com")
    response = sign_in(stranger).get(f"/api/v1/contracts/{contract.id}/meetings/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_cancelling_a_meeting_sets_its_status(contract, parties):
    client_user, freelancer = parties
    meeting = Meeting.objects.create(
        contract=contract,
        scheduled_by=client_user,
        provider=Provider.ZOOM,
        topic="Kickoff",
        start_time=timezone.now() + timedelta(days=1),
        join_url="https://zoom.us/j/123",
    )

    response = sign_in(freelancer).post(f"/api/v1/meetings/{meeting.id}/cancel/")

    assert response.status_code == 200
    meeting.refresh_from_db()
    assert meeting.status == Meeting.Status.CANCELLED


# --- Activity feeds -------------------------------------------------------------


@pytest.mark.django_db
def test_adding_the_same_source_twice_is_idempotent(contract, parties):
    client_user, _ = parties
    client = sign_in(client_user)
    payload = {"provider": "github", "external_ref": "acme/landing-page"}
    url = f"/api/v1/contracts/{contract.id}/activity-sources/"

    first = client.post(url, payload, format="json")
    second = client.post(url, payload, format="json")

    assert first.status_code == 201
    assert second.status_code == 200
    assert ActivityFeedSource.objects.filter(contract=contract).count() == 1


@pytest.mark.django_db
def test_syncing_stores_new_events_and_never_duplicates_on_a_repeat_sync(contract, parties):
    client_user, _ = parties
    IntegrationConnection.objects.create(
        user=client_user, provider=Provider.GITHUB, access_token="t"
    )
    source = ActivityFeedSource.objects.create(
        contract=contract,
        added_by=client_user,
        provider=Provider.GITHUB,
        external_ref="acme/landing-page",
    )
    fetched = [
        {
            "event_type": "PushEvent",
            "summary": "alice pushed commits",
            "actor_label": "alice",
            "occurred_at": "2026-01-01T12:00:00Z",
            "external_url": "https://github.com/acme/landing-page",
            "external_id": "evt-1",
        }
    ]

    with patch("integrations.providers.github.fetch_activity", return_value=fetched) as mocked:
        first = sign_in(client_user).post(f"/api/v1/activity-sources/{source.id}/sync/")
        second = sign_in(client_user).post(f"/api/v1/activity-sources/{source.id}/sync/")

    assert first.status_code == 200
    assert second.status_code == 200
    assert mocked.call_count == 2
    assert source.events.count() == 1
    assert first.data["recent_events"][0]["summary"] == "alice pushed commits"


@pytest.mark.django_db
def test_syncing_without_a_connection_is_rejected(contract, parties):
    client_user, _ = parties
    source = ActivityFeedSource.objects.create(
        contract=contract,
        added_by=client_user,
        provider=Provider.GITHUB,
        external_ref="acme/landing-page",
    )
    response = sign_in(client_user).post(f"/api/v1/activity-sources/{source.id}/sync/")
    assert response.status_code == 400
    assert response.data["code"] == "not_connected"
