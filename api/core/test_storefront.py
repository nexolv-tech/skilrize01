"""Tests for `create_storefront` — the operator's own listings."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from accounts.models import User, VerificationStatus
from gigs.models import Gig


@pytest.mark.django_db
def test_the_storefront_drafts_complete_services_and_is_rerunnable():
    """Drafts, not live listings: a service needs a picture to go live, and
    only the owner has pictures of their own work."""
    call_command("seed")
    call_command("create_storefront", "--email", "Studio@Example.com")
    call_command("create_storefront", "--email", "studio@example.com")

    seller = User.objects.get(email="studio@example.com")
    gigs = Gig.objects.unscoped().filter(seller=seller)
    assert gigs.count() == 4
    assert all(gig.status == Gig.Status.DRAFT and not gig.is_orderable for gig in gigs)
    assert all(
        gig.publish_blockers() == ["Add at least one picture of your work before publishing."]
        for gig in gigs
    )
    assert all(gig.packages.count() == 3 for gig in gigs)
    assert all(gig.faq and gig.requirements for gig in gigs)


@pytest.mark.django_db
def test_the_storefront_account_is_neither_verified_nor_usable_until_the_owner_acts():
    """The command lists services; it does not vouch for the account. The
    owner verifies and sets a password the same way every seller does."""
    call_command("seed")
    call_command("create_storefront", "--email", "studio@example.com")

    seller = User.objects.get(email="studio@example.com")
    assert not seller.has_usable_password()
    assert not seller.email_verified
    assert seller.identity_status == VerificationStatus.UNVERIFIED


@pytest.mark.django_db
def test_the_storefront_refuses_to_run_before_the_taxonomy():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="taxonomy"):
        call_command("create_storefront", "--email", "studio@example.com")


@pytest.mark.django_db
def test_publish_puts_each_service_live_with_the_studios_cover():
    """Swich's reviewers found nothing to check out (D57). With --publish each
    service gets its cover, a picture of the studio's own work, and goes live;
    running it again adds nothing twice."""
    call_command("seed")
    call_command("create_storefront", "--email", "studio@example.com", "--publish")
    call_command("create_storefront", "--email", "studio@example.com", "--publish")

    gigs = Gig.objects.unscoped().filter(seller__email="studio@example.com")
    assert gigs.count() == 4
    assert all(gig.status == Gig.Status.ACTIVE and gig.is_orderable for gig in gigs)
    assert all(len(gig.images()) == 1 for gig in gigs)
    assert {gig.images()[0].content_type for gig in gigs} == {"image/jpeg"}
