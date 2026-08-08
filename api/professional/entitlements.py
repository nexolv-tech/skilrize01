"""
What a user's plan actually lets them do.

One resolver, read by every caller. The failure this exists to prevent is the
one every subscription system eventually has: a limit enforced in three places
that disagree, so a Pro user is Pro on the proposals page and Free at the
endpoint that counts them.

Two rules hold throughout:

* **Absence resolves to Free, never to unlimited.** A missing subscription, an
  expired one, a database the seed never ran against — all of them land on the
  free tier. The failure mode of a bug here should be "someone was charged for
  something they got anyway", not "everyone got everything".

* **Entitlements are read, never cached on the user.** Denormalising a plan
  onto `User` would make every expiry a second write that can fail
  independently, and a stale copy of "unlimited proposals" is a hole nobody
  notices.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone


@dataclass(frozen=True, slots=True)
class Entitlements:
    """The resolved capability set for one user."""

    tier: str
    plan_name: str
    proposal_quota: int
    team_seats: int
    crm_contact_limit: int
    search_boost: bool
    advanced_analytics: bool
    can_sell_retainers: bool
    can_create_agency: bool
    priority_support: bool
    #: None on the free tier, which has nothing to renew.
    renews_at: object | None = None

    def allows(self, count: int, limit: int) -> bool:
        """Whether ``count`` is still within ``limit``, treating -1 as no cap."""
        from .models import Plan

        return limit == Plan.UNLIMITED or count < limit

    @property
    def is_paid(self) -> bool:
        from .models import Plan

        return self.tier != Plan.Tier.FREE


def for_user(user) -> Entitlements:
    """Resolve the live plan for ``user``.

    Anonymous and unauthenticated callers get the free tier rather than an
    error: read-only surfaces render limits for logged-out visitors, and
    raising there would mean the pricing page needs a session.
    """
    from .models import Plan, Subscription

    subscription = None
    if user is not None and getattr(user, "is_authenticated", False):
        subscription = (
            Subscription.objects.filter(
                user=user,
                status__in=Subscription.LIVE_STATUSES,
                current_period_end__gt=timezone.now(),
            )
            .select_related("plan")
            .first()
        )

    plan = subscription.plan if subscription else Plan.free()

    # Students keep the larger free quota they already had. A paid plan should
    # never be a downgrade for anybody — if a tier's number is lower than what
    # the user gets for nothing, the higher one wins.
    quota = plan.proposal_quota
    if user is not None and getattr(user, "is_verified_student", False):
        from marketplace.models import Proposal

        quota = max(quota, Proposal.FREE_PLAN_STUDENT_QUOTA)

    return Entitlements(
        tier=plan.tier,
        plan_name=plan.name,
        proposal_quota=quota,
        team_seats=plan.team_seats,
        crm_contact_limit=plan.crm_contact_limit,
        search_boost=plan.search_boost,
        advanced_analytics=plan.advanced_analytics,
        can_sell_retainers=plan.can_sell_retainers,
        can_create_agency=plan.can_create_agency,
        priority_support=plan.priority_support,
        renews_at=subscription.current_period_end if subscription else None,
    )


def seed_default_plans() -> list:
    """Create the three shipping tiers if they are absent.

    Idempotent, and safe to call from a migration, a management command, or a
    test. Prices are the ones already published on the marketing page — the
    pricing table and the enforcement must not be able to disagree, and the way
    to guarantee that is for there to be one source.
    """
    from decimal import Decimal

    from .models import Plan

    specs = [
        {
            "tier": Plan.Tier.FREE,
            "name": "Free",
            "tagline": "Everything you need to hire or get hired.",
            "monthly_price": Decimal("0"),
            "yearly_price": Decimal("0"),
            "order": 0,
            "proposal_quota": 30,
            "crm_contact_limit": 25,
            "features": [
                "Post projects and publish services",
                "Escrow on every contract",
                "Contract messaging and file sharing",
                "Two-way reviews and a public profile",
                "Standard proposal allowance",
            ],
        },
        {
            "tier": Plan.Tier.PRO,
            "name": "Pro",
            "tagline": "For freelancers who are earning and want to earn more.",
            "monthly_price": Decimal("1500"),
            "yearly_price": Decimal("15000"),
            "order": 1,
            "proposal_quota": 90,
            "crm_contact_limit": Plan.UNLIMITED,
            "search_boost": True,
            "advanced_analytics": True,
            "can_sell_retainers": True,
            "features": [
                "Everything in Free",
                "Triple the monthly proposals",
                "Profile boost in search results",
                "Unlimited CRM contacts and pipeline",
                "Sell services as monthly retainers",
                "Advanced earnings and funnel analytics",
            ],
        },
        {
            "tier": Plan.Tier.ELITE,
            "name": "Elite",
            "tagline": "For teams and agencies running work at volume.",
            "monthly_price": Decimal("4500"),
            "yearly_price": Decimal("45000"),
            "order": 2,
            "proposal_quota": Plan.UNLIMITED,
            "crm_contact_limit": Plan.UNLIMITED,
            "team_seats": 10,
            "search_boost": True,
            "advanced_analytics": True,
            "can_sell_retainers": True,
            "can_create_agency": True,
            "priority_support": True,
            "features": [
                "Everything in Pro",
                "Team and agency workspaces",
                "Up to 10 seats",
                "Shared client CRM and pipelines",
                "Unlimited proposals",
                "Priority support",
            ],
        },
    ]

    plans = []
    for spec in specs:
        plan, _ = Plan.objects.update_or_create(tier=spec["tier"], defaults=spec)
        plans.append(plan)
    return plans
