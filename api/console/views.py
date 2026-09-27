"""
The admin console's API (D54): what an operator does to run SkilRize.

Each area answers to the roles in `User.AdminRole` that own it, and Super
Admin to all of them (`require_admin_role`). Every action that changes
something writes an `AuditLog` row with the operator's reason and tells the
person it happened to; every read of bank details or identity documents is
logged as a sensitive read. Nothing here can move money on its own: payouts
and refunds are sent by hand from the bank, and the console records that
they were.

The older admin endpoints (student verification, users, contracts, the
audit log) live with their models in `accounts` and `contracts`; this app
adds the rest rather than moving those.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts import auth as tokens
from accounts.auth import require_admin_role
from accounts.models import RefreshSession, StudentVerification, User, VerificationStatus
from communities.models import ChatMessage, Community, Reply, Report, Resource, Thread
from contracts.models import Contract, ContractEvent, Milestone
from core.models import AuditLog, NotificationCategory
from core.notify import dispatch
from core.pagination import StandardPagination
from gigs.models import Gig, Order
from marketplace.models import Category, Project
from payments import settlement, swich
from payments.models import EscrowFunding, Payout, PayoutProfile, Refund, SubscriptionPayment
from professional.models import Subscription

from . import shapes

R = User.AdminRole
ANY_ADMIN = tuple(role for role in R.values if role)
FINANCE = (R.FINANCE_ADMIN,)
ORDERS = (R.FINANCE_ADMIN, R.SUPPORT_AGENT, R.DISPUTE_OFFICER)
VERIFY = (R.VERIFICATION_OFFICER,)
MODERATE = (R.MODERATOR,)
SUPPORT = (R.SUPPORT_AGENT,)


def _bad(message: str, code: str = "invalid") -> Response:
    return Response({"detail": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


def _text(request, field: str, *, required: bool, label: str) -> tuple[str, Response | None]:
    value = str(request.data.get(field, "") or "").strip()[:500]
    if required and len(value) < 3:
        return "", _bad(f"{label} is required.", f"{field}_required")
    return value, None


def _page(request, queryset, shape) -> Response:
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([shape(item) for item in page])


def _role(user) -> str:
    return R.SUPER_ADMIN if user.is_superuser else user.admin_role


def _money(value) -> str:
    return str(value or Decimal("0"))


# --- Overview ---------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*ANY_ADMIN)])
def overview(request):
    """What needs someone today, and how the platform is doing.

    Queues and money figures are included only for the roles that act on
    them, so the page each admin sees is theirs.
    """
    role = _role(request.user)

    def can(*roles: str) -> bool:
        return role == R.SUPER_ADMIN or role in roles

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    queues: dict = {}
    figures: dict = {
        "users": User.objects.filter(deleted_at__isnull=True).count(),
        "users_this_week": User.objects.filter(created_at__gte=week_ago).count(),
        "services_live": Gig.objects.unscoped().filter(status=Gig.Status.ACTIVE).count(),
        "briefs_open": Project.objects.unscoped().filter(status=Project.Status.OPEN).count(),
        "orders_in_progress": Order.objects.filter(
            status__in=(
                Order.Status.PENDING_REQUIREMENTS,
                Order.Status.ACTIVE,
                Order.Status.DELIVERED,
                Order.Status.REVISION,
            )
        ).count(),
        "contracts_active": Contract.objects.unscoped()
        .filter(status=Contract.Status.ACTIVE)
        .count(),
    }

    if can(*VERIFY):
        queues["identity"] = User.objects.filter(identity_status=VerificationStatus.PENDING).count()
        queues["students"] = StudentVerification.objects.filter(
            status=StudentVerification.Status.UNDER_REVIEW
        ).count()
    if can(*FINANCE):
        queues["transfers"] = _unconfirmed_transfers().count() + _unconfirmed_plans().count()
        pending_payouts = Payout.objects.filter(status=Payout.Status.PENDING).aggregate(
            n=Count("id"), total=Sum("net_amount")
        )
        pending_refunds = Refund.objects.filter(status=Refund.Status.PENDING).aggregate(
            n=Count("id"), total=Sum("amount")
        )
        queues["payouts"] = pending_payouts["n"]
        queues["payouts_total"] = _money(pending_payouts["total"])
        queues["refunds"] = pending_refunds["n"]
        queues["refunds_total"] = _money(pending_refunds["total"])
        figures["escrow_held"] = _money(
            Milestone.objects.filter(
                status__in=(
                    Milestone.Status.FUNDED,
                    Milestone.Status.IN_PROGRESS,
                    Milestone.Status.DELIVERED,
                    Milestone.Status.APPROVED,
                )
            ).aggregate(total=Sum("amount"))["total"]
        )
        figures["paid_in_this_month"] = _money(
            EscrowFunding.objects.filter(created_at__gte=month_start).aggregate(
                total=Sum("amount")
            )["total"]
        )
        figures["commission_this_month"] = _money(
            Payout.objects.filter(created_at__gte=month_start).aggregate(
                total=Sum("commission_amount")
            )["total"]
        )
        figures["commission_all_time"] = _money(
            Payout.objects.aggregate(total=Sum("commission_amount"))["total"]
        )
    if can(*MODERATE):
        queues["reports"] = Report.objects.filter(status=Report.Status.OPEN).count()

    return Response({"role": role, "queues": queues, "figures": figures})


# --- Payments: money in ------------------------------------------------------


def _unconfirmed_transfers():
    return EscrowFunding.objects.filter(confirmed_at__isnull=True).exclude(
        milestone__status=Milestone.Status.CANCELLED
    )


def _unconfirmed_plans():
    return SubscriptionPayment.objects.filter(
        confirmed_at__isnull=True, subscription__status__in=Subscription.LIVE_STATUSES
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def transfers(request):
    """Escrow payments buyers reported sending, to check against the bank
    statement. Unconfirmed ones come oldest first: a queue, not a feed."""
    state = request.query_params.get("state", "unconfirmed")
    if state == "confirmed":
        queryset = EscrowFunding.objects.filter(confirmed_at__isnull=False).order_by(
            "-confirmed_at"
        )
    else:
        queryset = _unconfirmed_transfers().order_by("created_at")
    queryset = queryset.select_related(
        "funded_by", "confirmed_by", "milestone__contract__freelancer"
    )
    return _page(request, queryset, shapes.transfer)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def transfer_confirm(request, pk):
    funding = get_object_or_404(EscrowFunding.objects.select_related("milestone__contract"), pk=pk)
    if funding.confirmed_at:
        return _bad("This transfer is already confirmed.", "already_confirmed")
    funding.confirmed_at = timezone.now()
    funding.confirmed_by = request.user
    funding.save(update_fields=["confirmed_at", "confirmed_by", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=funding,
        request=request,
        justification="Escrow transfer found on the bank statement.",
    )
    dispatch(
        funding.funded_by,
        NotificationCategory.PAYMENT,
        "Payment received",
        f"We received your payment of Rs {funding.amount:,.0f} for "
        f"“{funding.milestone.contract.title}”. It is held in escrow until you approve the work.",
        data={"contract_id": funding.milestone.contract_id},
    )
    return Response(shapes.transfer(funding))


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def transfer_not_received(request, pk):
    """The money never arrived. A gig order is voided (no refund, since
    nothing was paid); a brief's milestone goes back to awaiting funding.
    Refused once work has been delivered: by then it is a dispute."""
    note, _ = _text(request, "note", required=False, label="A note")
    funding = get_object_or_404(
        EscrowFunding.objects.select_related("milestone__contract", "funded_by"), pk=pk
    )
    if funding.confirmed_at:
        return _bad("This transfer was already confirmed as received.", "already_confirmed")
    milestone = funding.milestone
    contract = milestone.contract
    order = shapes._gig_order(contract)

    with transaction.atomic():
        if order is not None:
            if not settlement.void_unpaid_order(order, actor=request.user, note=note):
                return _bad(
                    "This order has been delivered or closed, so it cannot be voided for "
                    "non-payment. Treat it as a dispute.",
                    "order_not_voidable",
                )
        else:
            if milestone.status != Milestone.Status.FUNDED:
                return _bad(
                    "Work on this milestone has started or finished, so its funding cannot "
                    "be reversed here. Treat it as a dispute.",
                    "milestone_not_reversible",
                )
            milestone.status = Milestone.Status.PENDING
            milestone.funded_at = None
            milestone.save(update_fields=["status", "funded_at", "updated_at"])
            funding.delete()
            ContractEvent.log(
                contract,
                ContractEvent.Kind.STATUS,
                actor=request.user,
                body=f"Payment for “{milestone.title}” was not received; it needs funding again.",
            )
            AuditLog.record(
                actor=request.user,
                action=AuditLog.Action.UPDATE,
                target=milestone,
                request=request,
                justification=("Funding reversed, payment not received. " + note).strip(),
            )
            for party, text in (
                (
                    contract.client,
                    f"We did not receive your payment for “{milestone.title}”. Fund it "
                    "again to continue.",
                ),
                (
                    contract.freelancer,
                    f"The client's payment for “{milestone.title}” never arrived. Please "
                    "pause work on it until it is funded again.",
                ),
            ):
                dispatch(
                    party,
                    NotificationCategory.PAYMENT,
                    "Payment not received",
                    text,
                    data={"contract_id": contract.pk},
                )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def plan_payments(request):
    state = request.query_params.get("state", "unconfirmed")
    if state == "confirmed":
        queryset = SubscriptionPayment.objects.filter(confirmed_at__isnull=False).order_by(
            "-confirmed_at"
        )
    else:
        queryset = _unconfirmed_plans().order_by("created_at")
    queryset = queryset.select_related("paid_by", "confirmed_by", "subscription__plan")
    return _page(request, queryset, shapes.plan_payment)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def plan_payment_confirm(request, pk):
    payment = get_object_or_404(SubscriptionPayment.objects.select_related("subscription"), pk=pk)
    if payment.confirmed_at:
        return _bad("This payment is already confirmed.", "already_confirmed")
    payment.confirmed_at = timezone.now()
    payment.confirmed_by = request.user
    payment.save(update_fields=["confirmed_at", "confirmed_by", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=payment,
        request=request,
        justification="Plan payment found on the bank statement.",
    )
    return Response(shapes.plan_payment(payment))


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def plan_payment_not_received(request, pk):
    note, _ = _text(request, "note", required=False, label="A note")
    payment = get_object_or_404(
        SubscriptionPayment.objects.select_related("subscription__plan", "paid_by"), pk=pk
    )
    if payment.confirmed_at:
        return _bad("This payment was already confirmed as received.", "already_confirmed")
    payment.subscription.cancel(immediately=True)
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=payment.subscription,
        request=request,
        justification=("Plan cancelled, payment not received. " + note).strip(),
    )
    dispatch(
        payment.paid_by,
        NotificationCategory.PAYMENT,
        "Plan cancelled — payment not received",
        f"We did not receive your payment for {payment.subscription.plan.name}, so the plan "
        "was cancelled. If you did pay, reply with your payment reference.",
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


# --- Payments: money out -----------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def payouts(request):
    wanted = request.query_params.get("status", Payout.Status.PENDING)
    queryset = Payout.objects.filter(status=wanted).select_related(
        "freelancer__payout_profile", "paid_by", "milestone__contract"
    )
    queryset = queryset.order_by("created_at" if wanted == Payout.Status.PENDING else "-paid_at")
    return _page(request, queryset, shapes.payout)


def _read_bank_details(request, owner, *, why: str) -> Response:
    profile = PayoutProfile.objects.filter(user=owner).first()
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.READ_SENSITIVE,
        target=profile or owner,
        request=request,
        justification=why,
    )
    return Response(shapes.bank_details(profile))


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def payout_bank_details(request, pk):
    item = get_object_or_404(Payout.objects.select_related("freelancer"), pk=pk)
    return _read_bank_details(
        request, item.freelancer, why=f"Bank details read to send payout #{pk}."
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def payout_mark_paid(request, pk):
    reference, error = _text(request, "reference", required=True, label="The transfer reference")
    if error:
        return error
    item = get_object_or_404(
        Payout.objects.select_related("freelancer", "milestone__contract"), pk=pk
    )
    if item.status == Payout.Status.PAID:
        return _bad("This payout is already marked as paid.", "already_paid")
    item.status = Payout.Status.PAID
    item.paid_by = request.user
    item.paid_at = timezone.now()
    item.note = reference
    item.save(update_fields=["status", "paid_by", "paid_at", "note", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=item,
        request=request,
        justification=f"Payout sent. Reference: {reference}",
    )
    dispatch(
        item.freelancer,
        NotificationCategory.PAYMENT,
        "Payment sent",
        f"Rs {item.net_amount:,.0f} for “{item.milestone.contract.title}” has been sent to "
        f"your bank account (reference {reference}). Allow a working day for it to arrive.",
        data={"contract_id": item.milestone.contract_id},
    )
    return Response(shapes.payout(item))


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def refunds(request):
    wanted = request.query_params.get("status", Refund.Status.PENDING)
    queryset = Refund.objects.filter(status=wanted).select_related(
        "client__payout_profile", "refunded_by", "milestone__contract"
    )
    queryset = queryset.order_by(
        "created_at" if wanted == Refund.Status.PENDING else "-refunded_at"
    )
    return _page(request, queryset, shapes.refund)


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def refund_bank_details(request, pk):
    item = get_object_or_404(Refund.objects.select_related("client"), pk=pk)
    return _read_bank_details(request, item.client, why=f"Bank details read to send refund #{pk}.")


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def refund_mark_sent(request, pk):
    reference, error = _text(request, "reference", required=True, label="The transfer reference")
    if error:
        return error
    item = get_object_or_404(Refund.objects.select_related("client", "milestone__contract"), pk=pk)
    if item.status == Refund.Status.REFUNDED:
        return _bad("This refund is already marked as sent.", "already_refunded")
    item.status = Refund.Status.REFUNDED
    item.refunded_by = request.user
    item.refunded_at = timezone.now()
    item.note = reference
    item.save(update_fields=["status", "refunded_by", "refunded_at", "note", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=item,
        request=request,
        justification=f"Refund sent. Reference: {reference}",
    )
    dispatch(
        item.client,
        NotificationCategory.PAYMENT,
        "Refund sent",
        f"Rs {item.amount:,.0f} for “{item.milestone.contract.title}” has been sent back to "
        f"your bank account (reference {reference}).",
        data={"contract_id": item.milestone.contract_id},
    )
    return Response(shapes.refund(item))


# --- Identity (CNIC) ---------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*VERIFY)])
def identity_queue(request):
    """Identity documents awaiting a decision, oldest first. Each page hands
    out short-lived links to ID card images, so reading it is logged."""
    wanted = request.query_params.get("status", VerificationStatus.PENDING)
    queryset = (
        User.objects.filter(identity_status=wanted, identity_document__isnull=False)
        .select_related("identity_document")
        .order_by("identity_document__created_at")
    )
    response = _page(request, queryset, shapes.identity_case)
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.READ_SENSITIVE,
        request=request,
        target_type="IdentityQueue",
        justification=f"Identity documents viewed ({len(response.data['results'])} on the page).",
    )
    return response


def _identity_subject(pk):
    return get_object_or_404(User.objects.select_related("identity_document"), pk=pk)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*VERIFY)])
def identity_approve(request, pk):
    user = _identity_subject(pk)
    if user.identity_status != VerificationStatus.PENDING:
        return _bad("This identity check has already been decided.", "already_decided")
    user.identity_status = VerificationStatus.VERIFIED
    user.save(update_fields=["identity_status", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=user,
        request=request,
        justification="Identity document approved.",
    )
    dispatch(
        user,
        NotificationCategory.VERIFICATION,
        "Identity verified",
        "Your identity is verified. Once your email and phone are confirmed too, you can "
        "buy, sell and get paid.",
    )
    return Response(shapes.identity_case(user))


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*VERIFY)])
def identity_reject(request, pk):
    reason, error = _text(request, "reason", required=True, label="A reason")
    if error:
        return error
    user = _identity_subject(pk)
    if user.identity_status != VerificationStatus.PENDING:
        return _bad("This identity check has already been decided.", "already_decided")
    user.identity_status = VerificationStatus.REJECTED
    user.save(update_fields=["identity_status", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=user,
        request=request,
        justification=f"Identity document rejected: {reason}",
    )
    dispatch(
        user,
        NotificationCategory.VERIFICATION,
        "Identity check not approved",
        f"{reason} Upload a new photo of your CNIC from your dashboard to try again.",
    )
    return Response(shapes.identity_case(user))


# --- Catalogue: services and briefs -----------------------------------------


def _search(queryset, query: str, *fields: str):
    if not query:
        return queryset
    condition = Q()
    for field in fields:
        condition |= Q(**{f"{field}__icontains": query})
    return queryset.filter(condition)


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def gigs(request):
    queryset = (
        Gig.objects.unscoped()
        .select_related("seller", "category")
        .prefetch_related("gallery")
        .annotate(order_total=Count("orders", distinct=True))
        .order_by("-created_at")
    )
    if wanted := request.query_params.get("status"):
        queryset = queryset.filter(status=wanted)
    queryset = _search(
        queryset,
        request.query_params.get("q", "").strip(),
        "title",
        "seller__email",
        "seller__handle",
        "seller__full_name",
    )
    return _page(request, queryset, shapes.gig)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def gig_remove(request, pk):
    reason, error = _text(request, "reason", required=True, label="A reason")
    if error:
        return error
    item = get_object_or_404(Gig.objects.unscoped().select_related("seller"), pk=pk)
    if item.status == Gig.Status.DENIED:
        return _bad("This service is already removed.", "already_removed")
    item.status = Gig.Status.DENIED
    item.save(update_fields=["status", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=item,
        request=request,
        justification=f"Service removed: {reason}",
    )
    dispatch(
        item.seller,
        NotificationCategory.ANNOUNCEMENT,
        "Your service was removed",
        f"“{item.title}” was taken down by SkilRize. {reason} Existing orders are not "
        "affected. Reply to this message if you think this was a mistake.",
        data={"url": f"/gigs/{item.pk}"},
    )
    return Response(shapes.gig(item))


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def gig_restore(request, pk):
    item = get_object_or_404(Gig.objects.unscoped().select_related("seller"), pk=pk)
    if item.status != Gig.Status.DENIED:
        return _bad("Only a removed service can be restored.", "not_removed")
    # Straight back to live when nothing blocks it; otherwise to draft, where
    # the seller sees what is missing.
    item.status = Gig.Status.DRAFT if item.publish_blockers() else Gig.Status.ACTIVE
    item.save(update_fields=["status", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=item,
        request=request,
        justification="Service restored.",
    )
    dispatch(
        item.seller,
        NotificationCategory.ANNOUNCEMENT,
        "Your service is back",
        f"“{item.title}” has been restored"
        + (" and is live again." if item.status == Gig.Status.ACTIVE else " as a draft."),
        data={"url": f"/gigs/{item.pk}"},
    )
    return Response(shapes.gig(item))


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def projects(request):
    queryset = (
        Project.objects.unscoped()
        .select_related("client", "category")
        .annotate(proposal_total=Count("proposals", distinct=True))
        .order_by("-created_at")
    )
    if wanted := request.query_params.get("status"):
        queryset = queryset.filter(status=wanted)
    queryset = _search(
        queryset,
        request.query_params.get("q", "").strip(),
        "title",
        "client__email",
        "client__handle",
        "client__full_name",
    )
    return _page(request, queryset, shapes.project)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def project_close(request, pk):
    reason, error = _text(request, "reason", required=True, label="A reason")
    if error:
        return error
    item = get_object_or_404(Project.objects.unscoped().select_related("client"), pk=pk)
    if item.status not in (Project.Status.DRAFT, Project.Status.OPEN, Project.Status.PAUSED):
        return _bad("Only a draft, open or paused brief can be closed.", "not_closable")
    item.status = Project.Status.CLOSED
    item.save(update_fields=["status", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=item,
        request=request,
        justification=f"Brief closed: {reason}",
    )
    dispatch(
        item.client,
        NotificationCategory.ANNOUNCEMENT,
        "Your brief was closed",
        f"“{item.title}” was closed by SkilRize and no longer takes proposals. {reason}",
        data={"url": f"/projects/{item.pk}"},
    )
    return Response(shapes.project(item))


# --- Orders ------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*ORDERS)])
def orders(request):
    queryset = (
        Order.objects.select_related("gig", "buyer", "seller", "contract")
        .prefetch_related("contract__milestones__funding")
        .order_by("-created_at")
    )
    if wanted := request.query_params.get("status"):
        queryset = queryset.filter(status=wanted)
    query = request.query_params.get("q", "").strip()
    if query.isdigit():
        queryset = queryset.filter(pk=int(query))
    else:
        queryset = _search(
            queryset,
            query,
            "gig__title",
            "buyer__email",
            "buyer__full_name",
            "seller__email",
            "seller__full_name",
        )
    return _page(request, queryset, shapes.order)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*FINANCE)])
def order_void(request, pk):
    note, _ = _text(request, "note", required=False, label="A note")
    item = get_object_or_404(Order, pk=pk)
    with transaction.atomic():
        if not settlement.void_unpaid_order(item, actor=request.user, note=note):
            return _bad(
                "Only an order that has not been delivered can be cancelled for non-payment.",
                "order_not_voidable",
            )
    item.refresh_from_db()
    return Response(shapes.order(item))


# --- Reports -----------------------------------------------------------------


def _reported(report) -> tuple[object | None, dict]:
    """The reported object and what a moderator needs to judge it."""
    kind = report.kind
    if kind == Report.Kind.THREAD:
        item = Thread.all_objects.select_related("author").filter(pk=report.object_id).first()
        if item:
            return item, {
                "text": f"{item.title}\n\n{item.body}"[:600],
                "author": shapes.person(item.author),
                "url": f"/communities/{item.community_id}/threads/{item.pk}",
            }
    elif kind == Report.Kind.REPLY:
        item = Reply.objects.select_related("author", "thread").filter(pk=report.object_id).first()
        if item:
            return item, {
                "text": item.visible_body[:600],
                "author": shapes.person(item.author),
                "url": f"/communities/{item.thread.community_id}/threads/{item.thread_id}",
            }
    elif kind == Report.Kind.CHAT:
        item = ChatMessage.all_objects.select_related("author").filter(pk=report.object_id).first()
        if item:
            return item, {
                "text": ("[removed by a moderator]" if item.is_deleted else item.body)[:600],
                "author": shapes.person(item.author),
                "url": f"/communities/{item.community_id}",
            }
    elif kind == Report.Kind.RESOURCE:
        item = Resource.all_objects.filter(pk=report.object_id).first()
        if item:
            return item, {
                "text": f"{item.title}\n\n{item.description}"[:600],
                "author": None,
                "url": f"/communities/{item.community_id}",
            }
    elif kind == Report.Kind.COMMUNITY:
        item = Community.all_objects.filter(pk=report.object_id).first()
        if item:
            return item, {
                "text": f"{item.name}\n\n{item.description}"[:600],
                "author": None,
                "url": f"/communities/{item.pk}",
            }
    return None, {"text": "", "author": None, "url": None}


def _report_shape(report) -> dict:
    _, content = _reported(report)
    return {
        "id": report.pk,
        "kind": report.kind,
        "status": report.status,
        "reason": report.reason,
        "reporter": shapes.person(report.reporter),
        "community": report.community.name if report.community else None,
        "created_at": report.created_at,
        "resolved_at": report.resolved_at,
        "resolution_note": report.resolution_note,
        "content": content,
        "content_exists": bool(content["text"]),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def reports(request):
    wanted = request.query_params.get("status", Report.Status.OPEN)
    queryset = Report.objects.filter(status=wanted).select_related("reporter", "community")
    queryset = queryset.order_by("created_at" if wanted == Report.Status.OPEN else "-resolved_at")
    return _page(request, queryset, _report_shape)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def report_resolve(request, pk):
    """`remove` takes the content down and closes every open report on it;
    `dismiss` closes this report and leaves the content."""
    decision = request.data.get("decision")
    if decision not in ("remove", "dismiss"):
        return _bad("Choose whether to remove the content or dismiss the report.")
    note, _ = _text(request, "note", required=False, label="A note")
    report = get_object_or_404(Report, pk=pk)
    if report.status != Report.Status.OPEN:
        return _bad("This report has already been resolved.", "already_resolved")

    now = timezone.now()
    if decision == "dismiss":
        affected = Report.objects.filter(pk=report.pk)
        outcome = Report.Status.DISMISSED
    else:
        if report.kind == Report.Kind.COMMUNITY:
            return _bad(
                "A whole community cannot be removed from here. Dismiss the report, or "
                "contact the community's owner.",
                "not_removable",
            )
        item, content = _reported(report)
        if item is not None:
            if isinstance(item, (Reply, ChatMessage)):
                item.is_deleted = True
                item.save(update_fields=["is_deleted", "updated_at"])
            else:
                item.delete()
            if content["author"]:
                dispatch(
                    User.objects.get(pk=content["author"]["id"]),
                    NotificationCategory.COMMUNITY,
                    "Your post was removed",
                    "A moderator removed something you posted for breaking the community "
                    f"guidelines. {note}".strip(),
                )
        affected = Report.objects.filter(
            kind=report.kind, object_id=report.object_id, status=Report.Status.OPEN
        )
        outcome = Report.Status.UPHELD

    affected.update(
        status=outcome,
        resolution_note=note,
        resolved_by=request.user,
        resolved_at=now,
        updated_at=now,
    )
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=report,
        request=request,
        justification=f"Report {outcome}. {note}".strip(),
    )
    report.refresh_from_db()
    return Response(_report_shape(report))


# --- Categories ----------------------------------------------------------------


def _categories():
    return Category.objects.annotate(
        gig_total=Count("gigs", distinct=True), project_total=Count("projects", distinct=True)
    ).order_by("order", "name")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def categories(request):
    if request.method == "GET":
        return Response([shapes.category(item) for item in _categories()])

    name = str(request.data.get("name", "")).strip()[:100]
    if len(name) < 2:
        return _bad("Give the category a name.", "name_required")
    parent_id = request.data.get("parent_id") or None
    if parent_id and not Category.objects.filter(pk=parent_id).exists():
        return _bad("That parent category does not exist.", "bad_parent")
    base = slugify(name)[:110] or "category"
    slug, suffix = base, 2
    while Category.objects.filter(slug=slug).exists():
        slug, suffix = f"{base}-{suffix}", suffix + 1
    item = Category.objects.create(
        name=name,
        slug=slug,
        description=str(request.data.get("description", "")).strip()[:200],
        parent_id=parent_id,
        order=int(request.data.get("order") or 0),
    )
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.CREATE,
        target=item,
        request=request,
        justification=f"Category created: {name}",
    )
    return Response(shapes.category(_categories().get(pk=item.pk)), status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, require_admin_role(*MODERATE)])
def category_update(request, pk):
    item = get_object_or_404(Category, pk=pk)
    before = shapes.category(item)
    fields = []
    if "name" in request.data:
        name = str(request.data["name"]).strip()[:100]
        if len(name) < 2:
            return _bad("Give the category a name.", "name_required")
        item.name = name
        fields.append("name")
    if "description" in request.data:
        item.description = str(request.data["description"]).strip()[:200]
        fields.append("description")
    if "is_active" in request.data:
        item.is_active = bool(request.data["is_active"])
        fields.append("is_active")
    if "order" in request.data:
        item.order = int(request.data["order"] or 0)
        fields.append("order")
    if fields:
        item.save(update_fields=[*fields, "updated_at"])
        AuditLog.record(
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            target=item,
            request=request,
            before=before,
            after=shapes.category(item),
            justification=f"Category edited: {', '.join(fields)}",
        )
    return Response(shapes.category(_categories().get(pk=item.pk)))


# --- Users ---------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*SUPPORT)])
def user_summary(request, pk):
    """Everything support needs on one account without opening five screens."""
    user = get_object_or_404(User, pk=pk)
    subscription = (
        Subscription.objects.filter(user=user, status__in=Subscription.LIVE_STATUSES)
        .select_related("plan")
        .first()
    )
    return Response(
        {
            "services": dict(
                Gig.objects.unscoped()
                .filter(seller=user)
                .values_list("status")
                .annotate(n=Count("id"))
            ),
            "briefs": Project.objects.unscoped().filter(client=user).count(),
            "orders_bought": Order.objects.filter(buyer=user).count(),
            "orders_sold": Order.objects.filter(seller=user).count(),
            "contracts": Contract.objects.unscoped()
            .filter(Q(client=user) | Q(freelancer=user))
            .count(),
            "payouts_pending": _money(
                Payout.objects.filter(freelancer=user, status=Payout.Status.PENDING).aggregate(
                    total=Sum("net_amount")
                )["total"]
            ),
            "refunds_pending": _money(
                Refund.objects.filter(client=user, status=Refund.Status.PENDING).aggregate(
                    total=Sum("amount")
                )["total"]
            ),
            "plan": subscription.plan.name if subscription else None,
            "two_factor": user.has_two_factor,
            "active_sessions": RefreshSession.objects.filter(
                user=user, revoked_at__isnull=True, expires_at__gt=timezone.now()
            ).count(),
            "devices": user.devices.count(),
            "last_active_at": user.last_active_at,
            "identity_status": user.identity_status,
            "deleted": user.deleted_at is not None,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(R.SUPER_ADMIN)])
def user_set_role(request, pk):
    """Grant or withdraw an admin role. Super Admin only, never on oneself,
    and every session of the account is ended so the next sign-in meets the
    role's two-factor requirement (`User.requires_two_factor`)."""
    role = request.data.get("role", "")
    if role not in R.values:
        return _bad("Choose a role from the list.", "bad_role")
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        return _bad("You cannot change your own role.", "own_role")
    if user.deleted_at is not None:
        return _bad("This account was deleted by its owner.", "account_erased")
    before = user.admin_role
    if before == role:
        return _bad("The account already has that role.", "unchanged")
    user.admin_role = role
    user.save(update_fields=["admin_role", "updated_at"])
    tokens.revoke_all(user, reason="admin role changed")
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=user,
        request=request,
        before={"admin_role": before},
        after={"admin_role": role},
        justification=f"Admin role changed from {before or 'none'} to {role or 'none'}.",
    )
    dispatch(
        user,
        NotificationCategory.SECURITY,
        "Your SkilRize access changed",
        (
            f"You are now {R(role).label} on SkilRize. Sign in again; you will be asked to "
            "set up an authenticator app."
            if role
            else "Your administrator access has been removed."
        ),
    )
    from accounts.serializers import AdminUserSerializer

    return Response(AdminUserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*SUPPORT)])
def user_sign_out(request, pk):
    """End every session, for an account that may be in someone else's
    hands. The owner signs in again with their password."""
    user = get_object_or_404(User, pk=pk)
    ended = tokens.revoke_all(user, reason="signed out by support")
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=user,
        request=request,
        justification=f"Signed out of every device ({ended} sessions).",
    )
    dispatch(
        user,
        NotificationCategory.SECURITY,
        "You were signed out everywhere",
        "SkilRize support signed your account out of every device. Sign in again; if you "
        "did not ask for this, change your password.",
    )
    return Response({"sessions_ended": ended})


# --- Settings --------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(R.SUPER_ADMIN)])
def platform_settings(request):
    """How this server is configured, read-only. These live in
    `deploy/production.env` on the server; changing one is an edit there and
    a deploy, which is deliberately not a button."""
    from integrations.models import Provider
    from integrations.providers import registry

    backend = settings.EMAIL_BACKEND.rsplit(".", 1)[-1]
    return Response(
        {
            "environment": settings.ENVIRONMENT,
            "commission_percent": str(settlement.commission_percent()),
            "payments": {
                "available": swich.is_enabled(),
                "provider": "Swich",
                "environment": settings.SWICH_ENV,
                "callback_url": request.build_absolute_uri("/api/v1/payments/swich/callback/"),
            },
            "email": {
                "backend": backend,
                "from": settings.DEFAULT_FROM_EMAIL,
                "sending": backend not in ("ConsoleEmailBackend", "LocMemEmailBackend")
                and (backend != "EmailBackend" or bool(settings.EMAIL_HOST)),
            },
            "security": {
                "device_hold_minutes": settings.DEVICE_COOLOFF_SECONDS // 60,
                "new_device_email_code": settings.REQUIRE_NEW_DEVICE_VERIFICATION,
                "phone_verification_required": settings.PHONE_VERIFICATION_REQUIRED,
                "virus_scanner_required": settings.REQUIRE_FILE_SCANNER,
            },
            "integrations": [
                {"provider": value, "label": label, "enabled": registry.get(value).is_enabled()}
                for value, label in Provider.choices
            ],
            "error_reporting": bool(getattr(settings, "SENTRY_DSN", "")),
        }
    )
