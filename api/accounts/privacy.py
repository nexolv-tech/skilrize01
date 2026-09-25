"""
Data-subject rights: acceptance records, export, and erasure.

Three obligations from the GDPR, implemented once:

* **Accountability (Art. 7(1))** — `record_legal_acceptance` stores which
  version of the Terms and Privacy Policy each user accepted, and when.
* **Access and portability (Arts. 15, 20)** — `export_user_data` returns every
  row in the database that points at the user, as machine-readable JSON. It
  discovers those rows itself by walking every model's relations to `User`,
  the same way the cross-tenant leakage gate discovers every scoped model — so
  a model added later is included automatically instead of being forgotten.
* **Erasure (Art. 17)** — `erase_user` removes or anonymises personal data.
  What it keeps, and why, is stated in `RETAINED` and shown to the user before
  they confirm: financial records the law requires the platform to keep, and
  content that now belongs to other people's history (a review someone earned,
  a conversation someone else was part of).
"""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.crypto import EncryptedTextField
from core.models import AuditLog, client_ip

#: Fields never included in an export: credentials and internal plumbing that
#: identify nothing about the person and would only be a liability in a file
#: sitting in someone's Downloads folder.
_OMIT_FIELDS = {
    "password",
    "token_hash",
    "recovery_code_hashes",
    "secret",
    "key",
    "checksum",
    "fingerprint",
    "search_vector",
    "family",
}

#: Encrypted fields that are exported masked rather than omitted — the user
#: should be able to see *which* account their payouts go to.
_MASKED_FIELDS = {"account_number", "cnic"}

#: What erasure deliberately keeps, in the words shown to the user.
RETAINED = [
    "Orders, contracts, payments, payouts and refunds — Pakistani tax law requires business "
    "records to be kept for six years. They stay, attributed to “Deleted user”.",
    "Reviews you wrote or received — they are part of the other person's record on the "
    "platform. They stay, attributed to “Deleted user”.",
    "Messages and community posts you sent — they are part of other people's conversations. "
    "They stay, attributed to “Deleted user”. Delete individual posts first if you want them gone.",
    "The security audit log — kept to investigate fraud and abuse, and never shown publicly.",
]


# --- Acceptance --------------------------------------------------------------


def record_legal_acceptance(user, request=None) -> None:
    """Record acceptance of the current Terms and Privacy Policy versions."""
    from .models import LegalAcceptance

    ip = client_ip(request) if request is not None else None
    agent = request.META.get("HTTP_USER_AGENT", "")[:400] if request is not None else ""
    for document, version in (
        (LegalAcceptance.Document.TERMS, settings.LEGAL_TERMS_VERSION),
        (LegalAcceptance.Document.PRIVACY, settings.LEGAL_PRIVACY_VERSION),
    ):
        LegalAcceptance.objects.get_or_create(
            user=user,
            document=document,
            version=version,
            defaults={"ip_address": ip, "user_agent": agent},
        )


# --- Export ------------------------------------------------------------------


def _plain(value):
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, Decimal | uuid.UUID):
        return str(value)
    if isinstance(value, bytes | memoryview):
        return None
    return value


def _mask(value) -> str:
    text = str(value or "")
    return f"•••• {text[-4:]}" if len(text) > 4 else ("••••" if text else "")


def _serialize(instance) -> dict:
    row = {}
    for field in instance._meta.concrete_fields:
        if field.name in _OMIT_FIELDS:
            continue
        if isinstance(field, EncryptedTextField):
            if field.name in _MASKED_FIELDS:
                row[field.name] = _mask(getattr(instance, field.attname))
            continue
        row[field.name if not field.is_relation else field.attname] = _plain(
            getattr(instance, field.attname)
        )
    return row


def _manager(model):
    """Every row, across every surface. A person's own data is theirs wherever
    it was posted, so the export deliberately reaches past the tenancy scope —
    through `unscoped()`, the one greppable way across, where the model has it."""
    manager = model._default_manager
    return manager.unscoped() if hasattr(manager, "unscoped") else manager.all()


def _user_relations():
    """(model, field) for every relation in the project that points at User."""
    user_model = apps.get_model(settings.AUTH_USER_MODEL)
    project_apps = {
        "accounts",
        "challenges",
        "communities",
        "contracts",
        "core",
        "discovery",
        "gigs",
        "integrations",
        "marketplace",
        "payments",
        "professional",
    }
    for model in apps.get_models():
        if model._meta.app_label not in project_apps or model is user_model:
            continue
        for field in model._meta.get_fields():
            if not field.is_relation or field.related_model is not user_model:
                continue
            # Forward relations only. A many-to-many field has no column of its
            # own, so Django reports it as not `concrete` — it is identified by
            # not being the auto-created reverse side instead.
            forward_fk = getattr(field, "concrete", False) and (
                field.many_to_one or field.one_to_one
            )
            forward_m2m = field.many_to_many and not field.auto_created
            if forward_fk or forward_m2m:
                yield model, field


_ACCOUNT_FIELDS = [
    "email",
    "handle",
    "full_name",
    "headline",
    "bio",
    "country",
    "city",
    "timezone_name",
    "languages",
    "email_verified",
    "phone_number",
    "phone_verified",
    "identity_status",
    "student_verification_status",
    "student_verified_at",
    "profile_visibility",
    "created_at",
    "last_active_at",
]


def export_user_data(user) -> dict:
    """Everything the platform holds about `user`, as plain JSON."""
    records: dict[str, list] = {}
    for model, field in _user_relations():
        rows = _manager(model).filter(**{field.name: user})
        serialized = [_serialize(row) for row in rows]
        if serialized:
            label = f"{model._meta.app_label}.{model._meta.model_name} ({field.name})"
            records[label] = serialized

    return {
        "generated_at": timezone.now().isoformat(),
        "controller": "NEXOLV.TECH — operator of SkilRize (skilrize.com)",
        "note": (
            "This file contains the personal data SkilRize holds about you. Bank account and "
            "identity-card numbers are masked; passwords, two-factor secrets and security "
            "tokens are never included."
        ),
        "account": {name: _plain(getattr(user, name)) for name in _ACCOUNT_FIELDS},
        "university": user.university.name if user.university_id else None,
        "records": records,
    }


# --- Erasure -----------------------------------------------------------------


def erasure_blockers(user) -> list[str]:
    """What must be settled before the account can be erased.

    Everything here is money that is still moving, or something other people
    still depend on. Deleting an account in the middle of either would lose
    someone their money or their work, so the user resolves it first.
    """
    from contracts.models import Milestone
    from gigs.models import Order
    from payments.models import Payout, Refund
    from professional.models import Agency, AgencyMember, RetainerSubscription

    blockers: list[str] = []

    if user.is_staff or user.is_superuser or user.admin_role:
        blockers.append("Administrator accounts are closed by another administrator, not here.")

    open_orders = Order.objects.filter(models.Q(buyer=user) | models.Q(seller=user)).exclude(
        status__in=[Order.Status.COMPLETED, Order.Status.CANCELLED]
    )
    if count := open_orders.count():
        blockers.append(
            f"You have {count} open order{'s' if count != 1 else ''}. Complete or cancel "
            f"{'them' if count != 1 else 'it'} first."
        )

    held = (
        Milestone.objects.filter(
            status__in=[
                Milestone.Status.FUNDED,
                Milestone.Status.IN_PROGRESS,
                Milestone.Status.DELIVERED,
            ]
        )
        .filter(models.Q(contract__client=user) | models.Q(contract__freelancer=user))
        .filter(contract__gig_order__isnull=True)
    )
    if count := held.values("contract").distinct().count():
        blockers.append(
            f"{count} contract{'s have' if count != 1 else ' has'} money held in escrow. "
            "Release or cancel the funded milestones first."
        )

    pending_payouts = Payout.objects.filter(freelancer=user, status=Payout.Status.PENDING)
    if pending_payouts.exists():
        total = pending_payouts.aggregate(total=models.Sum("net_amount"))["total"]
        blockers.append(
            f"Rs {total:,.0f} in payouts has not been sent to you yet. Wait until it arrives."
        )

    pending_refunds = Refund.objects.filter(client=user, status=Refund.Status.PENDING)
    if pending_refunds.exists():
        total = pending_refunds.aggregate(total=models.Sum("amount"))["total"]
        blockers.append(
            f"Rs {total:,.0f} in refunds has not been returned to you yet. Wait until it arrives."
        )

    live_retainers = RetainerSubscription.objects.filter(
        models.Q(buyer=user) | models.Q(plan__seller=user),
        status__in=[RetainerSubscription.Status.ACTIVE, RetainerSubscription.Status.PAST_DUE],
    )
    if live_retainers.exists():
        blockers.append("You have active retainers. Cancel them and let them run out first.")

    for agency in Agency.objects.filter(owner=user, is_active=True):
        others = (
            AgencyMember.objects.filter(agency=agency, status=AgencyMember.Status.ACTIVE)
            .exclude(user=user)
            .exists()
        )
        if others:
            blockers.append(
                f"You own the agency “{agency.name}”, which still has members. Hand it over "
                "or remove them first."
            )

    return blockers


def _delete_files(queryset) -> None:
    from core.files import get_storage

    storage = get_storage()
    for record in queryset:
        storage.delete(record.key)
    queryset.delete()


@transaction.atomic
def erase_user(user, *, request=None) -> None:
    """Remove or anonymise everything personal about `user`.

    Callers must check `erasure_blockers` first; this does not re-check,
    because it is also the function an administrator's tooling would call
    after resolving those blockers by hand.
    """
    from challenges.models import Badge, Participation
    from communities.models import EventRSVP, FeedItem, Membership
    from contracts.models import Contract, Milestone
    from core.models import Notification, NotificationPreference, PushDevice, StoredFile
    from discovery.models import Promotion, ShowcaseItem
    from gigs.models import BuyerRequest, CustomOffer, Gig
    from integrations.models import IntegrationConnection
    from marketplace.models import Invitation, Project, Proposal
    from payments.models import PayoutProfile
    from professional.models import (
        Agency,
        AgencyMember,
        Contact,
        Deal,
        Interaction,
        RetainerPlan,
        Subscription,
        Task,
        WorkspaceMember,
    )

    from . import auth as tokens
    from .models import (
        BuyerProfile,
        KnownDevice,
        RefreshSession,
        SecurityToken,
        SellerProfile,
        StudentVerification,
        TwoFactorDevice,
        VerificationStatus,
    )

    now = timezone.now()
    tokens.revoke_all(user, reason="account_erased")

    # Identity documents, the avatar and portfolio images are the person's own
    # files. Deliverables and contract attachments are not deleted: they are
    # work another party paid for.
    _delete_files(
        StoredFile.objects.filter(
            owner=user,
            purpose__in=[
                StoredFile.Purpose.AVATAR,
                StoredFile.Purpose.IDENTITY,
                StoredFile.Purpose.PORTFOLIO,
            ],
        )
    )

    # Purely personal records: removed outright.
    for queryset in (
        SecurityToken.objects.filter(user=user),
        RefreshSession.objects.filter(user=user),
        KnownDevice.objects.filter(user=user),
        TwoFactorDevice.objects.filter(user=user),
        StudentVerification.objects.filter(user=user),
        PayoutProfile.objects.filter(user=user),
        NotificationPreference.objects.filter(user=user),
        Notification.objects.filter(user=user),
        PushDevice.objects.filter(user=user),
        IntegrationConnection.objects.filter(user=user),
        # A CRM holds other people's personal data that this user collected.
        # With the account gone there is nobody left entitled to it.
        Interaction.objects.filter(author=user),
        Task.objects.filter(owner=user),
        Deal.objects.filter(owner=user),
        Contact.objects.filter(owner=user),
        AgencyMember.objects.filter(user=user),
        WorkspaceMember.objects.filter(user=user),
        Membership.objects.filter(user=user),
        EventRSVP.objects.filter(user=user),
        FeedItem.objects.unscoped().filter(actor=user),
        Participation.objects.filter(user=user),
        Badge.objects.filter(user=user),
        BuyerRequest.objects.unscoped().filter(buyer=user),
        ShowcaseItem.objects.unscoped().filter(seller=user),
    ):
        queryset.delete()
    Contact.objects.filter(linked_user=user).update(linked_user=None)

    # Anything still offered to others is withdrawn, but kept: orders and
    # contracts elsewhere point at these rows.
    Gig.objects.unscoped().filter(seller=user).update(status=Gig.Status.PAUSED, updated_at=now)
    Project.objects.unscoped().filter(
        client=user,
        status__in=[Project.Status.DRAFT, Project.Status.OPEN, Project.Status.PAUSED],
    ).update(status=Project.Status.CLOSED, updated_at=now)
    Proposal.objects.filter(
        freelancer=user, status__in=[Proposal.Status.SUBMITTED, Proposal.Status.SHORTLISTED]
    ).update(status=Proposal.Status.WITHDRAWN, updated_at=now)
    Invitation.objects.filter(
        freelancer=user, status__in=[Invitation.Status.SENT, Invitation.Status.VIEWED]
    ).update(status=Invitation.Status.DECLINED, updated_at=now)
    CustomOffer.objects.filter(
        models.Q(seller=user) | models.Q(buyer=user), status=CustomOffer.Status.SENT
    ).update(status=CustomOffer.Status.DECLINED, updated_at=now)
    RetainerPlan.objects.unscoped().filter(seller=user).update(is_active=False, updated_at=now)
    Promotion.objects.filter(
        seller=user, status__in=[Promotion.Status.SCHEDULED, Promotion.Status.ACTIVE]
    ).update(status=Promotion.Status.COMPLETED, updated_at=now)
    Subscription.objects.filter(
        user=user, status__in=[Subscription.Status.TRIALING, Subscription.Status.ACTIVE]
    ).update(status=Subscription.Status.CANCELLED, updated_at=now)
    Agency.objects.filter(owner=user).update(is_active=False, updated_at=now)

    # Offers that were never accepted or funded simply lapse.
    unfunded = Contract.objects.unscoped().filter(
        models.Q(client=user) | models.Q(freelancer=user), status=Contract.Status.PENDING
    )
    Milestone.objects.filter(contract__in=unfunded).update(
        status=Milestone.Status.CANCELLED, updated_at=now
    )
    unfunded.update(status=Contract.Status.CANCELLED, ended_at=now, updated_at=now)

    SellerProfile.objects.filter(user=user).update(
        overview="", skills=[], hourly_rate=None, hours_per_week=None, updated_at=now
    )
    BuyerProfile.objects.filter(user=user).update(
        company_name="", industry="", company_size="", updated_at=now
    )

    # Finally the account itself. The row stays — contracts, orders and
    # payments keep pointing at it — but nothing on it identifies anyone.
    user.email = f"erased-{user.pk}-{secrets.token_hex(4)}@erased.invalid"
    user.handle = f"erased-{user.pk}"
    user.full_name = "Deleted user"
    user.headline = ""
    user.bio = ""
    user.country = ""
    user.city = ""
    user.languages = []
    user.avatar = None
    user.phone_number = ""
    user.phone_verified = False
    user.email_verified = False
    user.identity_status = VerificationStatus.UNVERIFIED
    user.identity_document = None
    user.university = None
    user.student_verification_status = VerificationStatus.UNVERIFIED
    user.student_verified_at = None
    user.profile_visibility = user.Visibility.PRIVATE
    user.is_active = False
    user.deleted_at = now
    user.set_unusable_password()
    user.save()

    AuditLog.record(
        actor=user,
        action=AuditLog.Action.DELETE,
        target=user,
        request=request,
        justification="Account erased at the user's own request (GDPR Art. 17).",
    )
