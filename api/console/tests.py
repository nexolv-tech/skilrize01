"""
Tests for the admin console API (D54).

What matters most: each area answers only to its roles, nothing changes
without a record of who did it and why, and the money actions do exactly
what the bank statement says happened, no more.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from accounts.models import RefreshSession, User, VerificationStatus
from communities.models import Community, Report, Thread
from contracts.models import Milestone
from contracts.tests import _activate, _fund
from core.models import AuditLog, Notification, StoredFile
from core.scope import GLOBAL_SCOPE, use_scope
from gigs.models import Gig, Order
from gigs.tests import _active_order
from marketplace.models import Category, Project
from marketplace.tests import make_user, sign_in
from payments.models import EscrowFunding, Payout, PayoutProfile, Refund
from payments.settlement import queue_refund

R = User.AdminRole


def admin(role: str, email: str | None = None):
    user = make_user(email or f"{role}@skilrize.test", admin_role=role)
    return user, sign_in(user)


# --- Access ------------------------------------------------------------------


@pytest.mark.django_db
def test_a_member_cannot_open_the_console(buyer):
    assert sign_in(buyer).get("/api/v1/admin/overview/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "path", "allowed"),
    [
        (R.FINANCE_ADMIN, "/api/v1/admin/payments/transfers/", True),
        (R.MODERATOR, "/api/v1/admin/payments/transfers/", False),
        (R.VERIFICATION_OFFICER, "/api/v1/admin/identity/", True),
        (R.FINANCE_ADMIN, "/api/v1/admin/identity/", False),
        (R.MODERATOR, "/api/v1/admin/gigs/", True),
        (R.SUPPORT_AGENT, "/api/v1/admin/gigs/", False),
        (R.SUPPORT_AGENT, "/api/v1/admin/orders/", True),
        (R.MODERATOR, "/api/v1/admin/orders/", False),
        (R.FINANCE_ADMIN, "/api/v1/admin/settings/", False),
        (R.SUPER_ADMIN, "/api/v1/admin/settings/", True),
    ],
)
def test_each_area_answers_only_to_its_roles(role, path, allowed):
    _, api = admin(role)
    assert (api.get(path).status_code == 200) is allowed


@pytest.mark.django_db
def test_the_overview_shows_each_role_its_own_queues():
    _, finance = admin(R.FINANCE_ADMIN)
    _, moderator = admin(R.MODERATOR)

    money = finance.get("/api/v1/admin/overview/").data
    moderation = moderator.get("/api/v1/admin/overview/").data

    assert "transfers" in money["queues"] and "escrow_held" in money["figures"]
    assert "reports" in moderation["queues"]
    assert "transfers" not in moderation["queues"]
    assert "escrow_held" not in moderation["figures"]


@pytest.mark.django_db
def test_a_superuser_is_a_super_admin_to_the_web_app():
    user = make_user("root@skilrize.test", is_superuser=True)
    assert sign_in(user).get("/api/v1/auth/me/").data["admin_role"] == R.SUPER_ADMIN


# --- Money in ------------------------------------------------------------------


@pytest.mark.django_db
def test_confirming_a_transfer_records_it_and_tells_the_buyer(gig, buyer):
    order = _active_order(gig, buyer)
    officer, api = admin(R.FINANCE_ADMIN)

    queue = api.get("/api/v1/admin/payments/transfers/").data["results"]
    assert [row["order_id"] for row in queue] == [order.pk]

    response = api.post(f"/api/v1/admin/payments/transfers/{queue[0]['id']}/confirm/")

    assert response.status_code == 200
    funding = EscrowFunding.objects.get(pk=queue[0]["id"])
    assert funding.confirmed_by == officer
    assert Notification.objects.filter(user=buyer, title="Payment received").exists()
    assert AuditLog.objects.filter(actor=officer, target_type="EscrowFunding").exists()
    assert api.get("/api/v1/admin/payments/transfers/").data["count"] == 0


@pytest.mark.django_db
def test_a_transfer_that_never_arrived_voids_the_order(gig, buyer):
    order = _active_order(gig, buyer)
    _, api = admin(R.FINANCE_ADMIN)
    funding = EscrowFunding.objects.get(milestone__contract=order.contract)

    response = api.post(
        f"/api/v1/admin/payments/transfers/{funding.pk}/not-received/",
        {"note": "Nothing on the statement after 3 days."},
        format="json",
    )

    assert response.status_code == 204
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert not Refund.objects.exists()
    assert api.get("/api/v1/admin/payments/transfers/").data["count"] == 0


@pytest.mark.django_db
def test_a_brief_milestone_that_was_never_paid_goes_back_to_awaiting_funding(awarded, parties):
    client_user, freelancer = parties
    milestone = _activate(awarded, freelancer)
    _fund(sign_in(client_user), awarded, milestone, "ref 123")
    _, api = admin(R.FINANCE_ADMIN)
    funding = EscrowFunding.objects.get(milestone=milestone)

    response = api.post(f"/api/v1/admin/payments/transfers/{funding.pk}/not-received/")

    assert response.status_code == 204
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.PENDING
    assert not EscrowFunding.objects.filter(pk=funding.pk).exists()
    assert Notification.objects.filter(user=freelancer, title="Payment not received").exists()


# --- Money out ----------------------------------------------------------------


def _payout(gig, buyer, seller) -> Payout:
    PayoutProfile.objects.create(
        user=seller,
        bank_name="Meezan",
        account_title="Seller Name",
        account_number="01234567890123",
        cnic="3520212345671",
    )
    order = _active_order(gig, buyer)
    sign_in(seller).post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "Done."}, format="json")
    sign_in(buyer).post(f"/api/v1/orders/{order.pk}/accept/")
    return Payout.objects.get(freelancer=seller)


@pytest.mark.django_db
def test_reading_bank_details_is_logged_and_masks_the_cnic(gig, buyer, seller):
    payout = _payout(gig, buyer, seller)
    officer, api = admin(R.FINANCE_ADMIN)

    details = api.get(f"/api/v1/admin/payments/payouts/{payout.pk}/bank-details/").data

    assert details["account_number"] == "01234567890123"
    assert details["cnic_last4"] == "5671"
    assert "cnic" not in details
    assert AuditLog.objects.filter(actor=officer, action=AuditLog.Action.READ_SENSITIVE).exists()


@pytest.mark.django_db
def test_a_payout_is_marked_paid_only_with_a_transfer_reference(gig, buyer, seller):
    payout = _payout(gig, buyer, seller)
    _, api = admin(R.FINANCE_ADMIN)
    url = f"/api/v1/admin/payments/payouts/{payout.pk}/mark-paid/"

    assert api.post(url, {}, format="json").status_code == 400
    response = api.post(url, {"reference": "IBFT 88213"}, format="json")

    assert response.status_code == 200
    payout.refresh_from_db()
    assert payout.status == Payout.Status.PAID
    assert payout.note == "IBFT 88213"
    assert Notification.objects.filter(user=seller, title="Payment sent").exists()


@pytest.mark.django_db
def test_a_refund_is_marked_sent(gig, buyer):
    order = _active_order(gig, buyer)
    refund = queue_refund(order.contract.milestones.first(), reason="Seller cancelled.")
    _, api = admin(R.FINANCE_ADMIN)

    response = api.post(
        f"/api/v1/admin/payments/refunds/{refund.pk}/mark-sent/",
        {"reference": "IBFT 1"},
        format="json",
    )

    assert response.status_code == 200
    refund.refresh_from_db()
    assert refund.status == Refund.Status.REFUNDED
    assert Notification.objects.filter(user=buyer, title="Refund sent").exists()


# --- Identity --------------------------------------------------------------------


def _applicant(email="applicant@example.com") -> User:
    user = make_user(email, transactable=False)
    user.identity_document = StoredFile.objects.create(
        owner=user,
        purpose=StoredFile.Purpose.IDENTITY,
        key=f"t/{email}.png",
        original_name="cnic.png",
        content_type="image/png",
        size_bytes=10,
        checksum="x" * 64,
        scan_status=StoredFile.ScanStatus.CLEAN,
    )
    user.identity_status = VerificationStatus.PENDING
    user.save()
    return user


@pytest.mark.django_db
def test_an_identity_check_is_approved_from_the_queue():
    applicant = _applicant()
    officer, api = admin(R.VERIFICATION_OFFICER)

    queue = api.get("/api/v1/admin/identity/").data["results"]
    assert queue[0]["user"]["id"] == applicant.pk
    assert queue[0]["document_url"].startswith("/files/")
    # Handing out links to ID cards is itself a sensitive read.
    assert AuditLog.objects.filter(actor=officer, action=AuditLog.Action.READ_SENSITIVE).exists()

    assert api.post(f"/api/v1/admin/identity/{applicant.pk}/approve/").status_code == 200
    applicant.refresh_from_db()
    assert applicant.identity_status == VerificationStatus.VERIFIED
    assert Notification.objects.filter(user=applicant, title="Identity verified").exists()


@pytest.mark.django_db
def test_rejecting_an_identity_check_needs_a_reason_the_user_is_told():
    applicant = _applicant()
    _, api = admin(R.VERIFICATION_OFFICER)
    url = f"/api/v1/admin/identity/{applicant.pk}/reject/"

    assert api.post(url, {}, format="json").status_code == 400
    assert api.post(url, {"reason": "The photo is blurred."}, format="json").status_code == 200

    applicant.refresh_from_db()
    assert applicant.identity_status == VerificationStatus.REJECTED
    note = Notification.objects.get(user=applicant, title="Identity check not approved")
    assert "blurred" in note.body


# --- Catalogue -------------------------------------------------------------------


@pytest.mark.django_db
def test_a_removed_service_leaves_the_catalogue_and_can_come_back(gig, seller):
    _, api = admin(R.MODERATOR)

    removed = api.post(
        f"/api/v1/admin/gigs/{gig.pk}/remove/", {"reason": "Stock photos."}, format="json"
    )
    assert removed.data["status"] == Gig.Status.DENIED
    assert Notification.objects.filter(user=seller, title="Your service was removed").exists()

    restored = api.post(f"/api/v1/admin/gigs/{gig.pk}/restore/")
    assert restored.data["status"] == Gig.Status.ACTIVE


@pytest.mark.django_db
def test_a_brief_can_be_closed_with_a_reason(parties):
    client_user, _ = parties
    with use_scope(GLOBAL_SCOPE):
        brief = Project.objects.create(
            client=client_user,
            title="Scrape a competitor",
            description="Not allowed here.",
            budget_max=1000,
            status=Project.Status.OPEN,
        )
    _, api = admin(R.MODERATOR)

    response = api.post(
        f"/api/v1/admin/projects/{brief.pk}/close/", {"reason": "Against the rules."}, format="json"
    )

    assert response.data["status"] == Project.Status.CLOSED
    assert Notification.objects.filter(user=client_user, title="Your brief was closed").exists()


@pytest.mark.django_db
def test_categories_are_added_and_hidden():
    _, api = admin(R.MODERATOR)

    created = api.post(
        "/api/v1/admin/categories/", {"name": "Video & Animation"}, format="json"
    ).data
    hidden = api.patch(
        f"/api/v1/admin/categories/{created['id']}/", {"is_active": False}, format="json"
    ).data

    assert created["slug"] == "video-animation"
    assert hidden["is_active"] is False
    assert not Category.objects.get(pk=created["id"]).is_active


# --- Reports -----------------------------------------------------------------------


@pytest.mark.django_db
def test_removing_reported_content_closes_every_report_on_it():
    author = make_user("author@example.com")
    with use_scope(GLOBAL_SCOPE):
        community = Community.objects.create(name="Makers", slug="makers", created_by=author)
        thread = Thread.objects.create(
            community=community, author=author, title="Buy followers", body="Cheap followers here."
        )
    for email in ("a@example.com", "b@example.com"):
        Report.objects.create(
            reporter=make_user(email),
            community=community,
            kind=Report.Kind.THREAD,
            object_id=thread.pk,
            reason="Spam selling followers.",
        )
    _, api = admin(R.MODERATOR)
    first = api.get("/api/v1/admin/reports/").data["results"][0]
    assert "Cheap followers" in first["content"]["text"]

    response = api.post(
        f"/api/v1/admin/reports/{first['id']}/resolve/",
        {"decision": "remove", "note": "Spam."},
        format="json",
    )

    assert response.data["status"] == Report.Status.UPHELD
    assert not Thread.all_objects.filter(pk=thread.pk).exists()
    assert not Report.objects.filter(status=Report.Status.OPEN).exists()
    assert Notification.objects.filter(user=author, title="Your post was removed").exists()


# --- Users ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_only_a_super_admin_grants_roles_and_never_to_themselves(buyer):
    boss, api = admin(R.SUPER_ADMIN)
    _, support = admin(R.SUPPORT_AGENT)
    url = f"/api/v1/admin/users/{buyer.pk}/role/"

    assert support.post(url, {"role": R.FINANCE_ADMIN}, format="json").status_code == 403
    assert (
        api.post(f"/api/v1/admin/users/{boss.pk}/role/", {"role": ""}, format="json").status_code
        == 400
    )
    response = api.post(url, {"role": R.FINANCE_ADMIN}, format="json")

    assert response.status_code == 200
    buyer.refresh_from_db()
    assert buyer.admin_role == R.FINANCE_ADMIN
    # Signed out, so the next sign-in meets the role's two-factor rule.
    assert not RefreshSession.objects.filter(user=buyer, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_support_can_sign_an_account_out_everywhere(buyer):
    sign_in(buyer)
    _, api = admin(R.SUPPORT_AGENT)

    response = api.post(f"/api/v1/admin/users/{buyer.pk}/sign-out/")

    assert response.data["sessions_ended"] >= 1
    assert not RefreshSession.objects.filter(user=buyer, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_the_first_super_admin_comes_from_the_command_line(buyer):
    call_command("set_admin_role", buyer.email, "super_admin")

    buyer.refresh_from_db()
    assert buyer.admin_role == R.SUPER_ADMIN
