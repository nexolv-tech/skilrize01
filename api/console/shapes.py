"""
How the admin console sees each record.

Plain functions rather than DRF serializers: every shape here is read-only,
built for one screen, and several reach across two or three models (a
transfer is a funding, a milestone, a contract and maybe an order). A dict
built in one place is easier to read than three nested serializer classes.
"""

from __future__ import annotations

from core.files import signed_url


def person(user) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.pk,
        "name": user.display_name,
        "email": user.email,
        "handle": user.handle,
    }


def _money(value) -> str | None:
    return None if value is None else str(value)


def _gig_order(contract):
    """The gig order a contract belongs to, or None for a brief's contract."""
    try:
        return contract.gig_order
    except Exception:  # noqa: BLE001 — RelatedObjectDoesNotExist has no public import path
        return None


def transfer(funding) -> dict:
    milestone = funding.milestone
    contract = milestone.contract
    order = _gig_order(contract)
    return {
        "id": funding.pk,
        "amount": _money(funding.amount),
        "currency": funding.currency,
        "reference_note": funding.reference_note,
        "reported_at": funding.created_at,
        "confirmed_at": funding.confirmed_at,
        "confirmed_by": person(funding.confirmed_by),
        "payer": person(funding.funded_by),
        "payee": person(contract.freelancer),
        "title": contract.title,
        "milestone": milestone.title,
        "milestone_status": milestone.status,
        "contract_id": contract.pk,
        "order_id": order.pk if order else None,
    }


def plan_payment(payment) -> dict:
    subscription = payment.subscription
    return {
        "id": payment.pk,
        "amount": _money(payment.amount),
        "currency": payment.currency,
        "reference_note": payment.reference_note,
        "reported_at": payment.created_at,
        "confirmed_at": payment.confirmed_at,
        "confirmed_by": person(payment.confirmed_by),
        "payer": person(payment.paid_by),
        "plan": subscription.plan.name,
        "interval": subscription.interval,
        "subscription_status": subscription.status,
    }


def payout(item) -> dict:
    milestone = item.milestone
    contract = milestone.contract
    order = _gig_order(contract)
    profile = getattr(item.freelancer, "payout_profile", None)
    return {
        "id": item.pk,
        "status": item.status,
        "gross_amount": _money(item.gross_amount),
        "commission_percent": _money(item.commission_percent),
        "commission_amount": _money(item.commission_amount),
        "net_amount": _money(item.net_amount),
        "currency": item.currency,
        "created_at": item.created_at,
        "paid_at": item.paid_at,
        "paid_by": person(item.paid_by),
        "note": item.note,
        "freelancer": person(item.freelancer),
        "bank_details_ready": bool(profile and profile.is_complete),
        "swich_ready": bool(profile and profile.swich_ready),
        "destination": profile.bank_name if profile else "",
        "last_error": item.last_error,
        "swich_reference": item.swich_reference,
        "title": contract.title,
        "milestone": milestone.title,
        "contract_id": contract.pk,
        "order_id": order.pk if order else None,
    }


def refund(item) -> dict:
    milestone = item.milestone
    contract = milestone.contract
    order = _gig_order(contract)
    profile = getattr(item.client, "payout_profile", None)
    return {
        "id": item.pk,
        "status": item.status,
        "amount": _money(item.amount),
        "currency": item.currency,
        "reason": item.reason,
        "created_at": item.created_at,
        "refunded_at": item.refunded_at,
        "refunded_by": person(item.refunded_by),
        "note": item.note,
        "client": person(item.client),
        "bank_details_ready": bool(profile and profile.is_complete),
        "last_error": item.last_error,
        "title": contract.title,
        "milestone": milestone.title,
        "contract_id": contract.pk,
        "order_id": order.pk if order else None,
    }


def bank_details(profile) -> dict:
    """What the operator types into their bank's transfer form. The CNIC is
    masked to its last four digits: it identifies the holder when a bank
    asks, and nothing here needs the whole number on screen."""
    if profile is None:
        return {"complete": False}
    cnic = profile.cnic or ""
    return {
        "complete": profile.is_complete,
        "bank_name": profile.bank_name,
        "account_title": profile.account_title,
        "account_number": profile.account_number,
        "cnic_last4": cnic[-4:] if cnic else "",
        "mobile_wallet": profile.msisdn,
    }


def identity_case(user) -> dict:
    document = user.identity_document
    return {
        "user": person(user),
        "status": user.identity_status,
        "submitted_at": document.created_at if document else None,
        "document_url": signed_url(document, ttl=600)
        if document and document.is_downloadable
        else None,
        "document_scan": document.scan_status if document else None,
        "email_verified": user.email_verified,
        "phone_verified": user.phone_verified,
        "joined_at": user.created_at,
    }


def gig(item) -> dict:
    images = item.images()
    cover = next((image for image in images if image.is_downloadable), None)
    return {
        "id": item.pk,
        "title": item.title,
        "status": item.status,
        "seller": person(item.seller),
        "category": item.category.name if item.category else None,
        "visibility": item.visibility,
        "created_at": item.created_at,
        "orders": getattr(item, "order_total", 0),
        "cover_url": signed_url(cover) if cover else None,
    }


def project(item) -> dict:
    return {
        "id": item.pk,
        "title": item.title,
        "status": item.status,
        "client": person(item.client),
        "category": item.category.name if item.category else None,
        "visibility": item.visibility,
        "project_type": item.project_type,
        "budget_max": _money(item.budget_max or item.rate_max),
        "created_at": item.created_at,
        "proposals": getattr(item, "proposal_total", 0),
    }


def order(item) -> dict:
    funding = None
    contract = item.contract
    if contract is not None:
        milestone = next(iter(contract.milestones.all()), None)
        funding = getattr(milestone, "funding", None) if milestone else None
    return {
        "id": item.pk,
        "title": item.gig.title,
        "gig_id": item.gig_id,
        "status": item.status,
        "price": _money(item.price),
        "buyer": person(item.buyer),
        "seller": person(item.seller),
        "created_at": item.created_at,
        "due_at": item.due_at,
        "contract_id": contract.pk if contract else None,
        "payment": (
            "confirmed" if funding and funding.confirmed_at else "reported" if funding else "none"
        ),
    }


def category(item) -> dict:
    return {
        "id": item.pk,
        "name": item.name,
        "slug": item.slug,
        "description": item.description,
        "parent_id": item.parent_id,
        "order": item.order,
        "is_active": item.is_active,
        "services": getattr(item, "gig_total", 0),
        "briefs": getattr(item, "project_total", 0),
    }
