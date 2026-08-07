# SkilRize

A unified freelance marketplace — everything Fiverr does and everything Upwork
does under one account, one wallet, and one reputation — with a second surface
neither has: private, verified portals scoped to a single university.

Built to the specification in *Platform Requirements & Technical Architecture*
(v1.0). Section references throughout the code point back to it.

---

## Status: Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅

**122 backend tests pass. Lint, format, type-check and production build are clean.**

### Phase 0 — Foundations

The layer everything else is built on: the account system, the security
posture, and the tenancy machinery the marketplace plugs into.

| Delivered | Where |
| --- | --- |
| Docker environment, CI, environment-driven config | `docker-compose.yml`, `.github/workflows/ci.yml` |
| Core data model, timestamps, append-only audit log | `api/core/models.py` |
| **Tenancy scope enforcement** (Section 4.4) | `api/core/scope.py` |
| Secure file pipeline — magic bytes, re-encode, signed URLs, AV hook | `api/core/files.py` |
| Field-level encryption (AES-256-GCM) | `api/core/crypto.py` |
| Notification framework with per-channel preferences | `api/core/notify.py`, `api/core/tasks.py` |
| Custom user, both profile faces, universities | `api/accounts/models.py` |
| Argon2id, JWT rotation + reuse detection, TOTP 2FA, step-up | `api/accounts/auth.py` |
| Design system, app shell, auth + settings screens | `web/` |

### Phase 1 — Projects & bidding

The Upwork-equivalent track in full: a client posts a brief, freelancers
compete with proposals, the client awards, and work runs under a contract with
staged payments.

| Delivered | Where |
| --- | --- |
| Category and skill taxonomy, seeded | `api/marketplace/models.py`, `api/core/management/commands/seed.py` |
| Projects — fixed and hourly, scope, screening questions, draft/open/closed | `api/marketplace/models.py` |
| Proposals with **outstanding-bid quota**, self-bid block, edit window | `api/marketplace/` |
| Invitations that bypass the quota | `api/marketplace/views.py` |
| Contracts with **terms frozen at acceptance** | `api/contracts/models.py` |
| Milestones — fund → deliver → release, auto-complete when none outstanding | `api/contracts/views.py` |
| Work diary with the **tracked-vs-manual protection asymmetry** and weekly cap | `api/contracts/models.py` |
| Unified contract timeline (messages, deliveries, payments) | `api/contracts/models.py` |
| **Double-blind two-way reviews** | `api/contracts/models.py` |
| Browse with filters, brief detail, post-a-project, proposals, contract workspace | `web/app/(app)/` |

Payments are still manual: a client funds a milestone explicitly, standing in
for the gateway capture that arrives in Phase 3. The state machine it will plug
into is already the real one.

### Phase 2 — Gigs

The productised-service track: a seller publishes a fixed price, a buyer
purchases it outright, and the requirements form — not the payment — starts the
delivery clock.

| Delivered | Where |
| --- | --- |
| Gigs with gallery, FAQ, tags, and a requirements form | `api/gigs/models.py` |
| Three-tier packages with enforced price laddering, single-tier mode | `api/gigs/serializers.py` |
| Paid extras that adjust both price and delivery time | `api/gigs/models.py` |
| Order lifecycle **gated by the requirements form** | `api/gigs/views.py` |
| Revision entitlement per package, with a reason required | `api/gigs/views.py` |
| Vacation mode, buyer requests, custom offers | `api/gigs/views.py` |
| Catalogue, gig detail with package picker, order workspace | `web/app/(app)/gigs`, `web/app/(app)/orders` |

**Orders run on Phase 1's contract.** An order creates a `Contract` with one
funded milestone and drives it, so escrow, messaging, and reviews are shared
across both tracks rather than duplicated. A five-star review from a purchased
gig and one from a won proposal are the same row in the same table — which is
what makes "one reputation" true instead of aspirational.

### Visual layer

Every listing renders deterministic vector cover art derived from its id and
category (`web/components/artwork.tsx`), so the catalogue looks like a real
product from the first listing, with no stock photography and no network
requests. A seller's uploaded cover replaces it automatically.

The hero uses an animated gradient field rather than video by default. To use
real footage, drop it in `web/public/` and set `NEXT_PUBLIC_HERO_VIDEO` — see
`web/public/README.md`.

### What is not built yet

No real payment gateway or ledger, and no student portals — Phases 3 and 4.
Funding is still an explicit action standing in for a gateway capture (decision
D12). Every marketplace model already inherits `ScopedModel`, and every
money-adjacent endpoint already attaches `CanTransact`.

---

## Quick start

### Docker (everything at once)

```bash
cp .env.example .env && docker compose up
```

API on `:8000`, web on `:3000`, Postgres on `:5432`, Redis on `:6379`.

### Local

```bash
cd api && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

Then create the database, apply migrations, and run:

```bash
cd api && .venv/Scripts/python manage.py migrate && .venv/Scripts/python manage.py runserver
```

```bash
cd web && npm install && npm run dev
```

### Tests

```bash
cd api && .venv/Scripts/python -m pytest
```

---

## Architecture

```
SKILRIZE/
├─ api/                     Django REST API — all business logic and authorisation
│  ├─ config/               Settings, URLs, Celery, ASGI/WSGI
│  ├─ core/                 Foundations: scope, files, crypto, audit, notifications
│  └─ accounts/             Identity: users, universities, profiles, auth, 2FA
└─ web/                     Next.js — presentation only, enforces nothing
   ├─ app/                  Routes: marketing, (auth), (app)
   ├─ components/           Design system primitives + app chrome
   └─ lib/                  API client, session and theme context
```

No client is trusted to enforce a rule. Every endpoint authorises independently;
the web app's route guard is a convenience, not a control.

### Three decisions worth knowing

**Tenancy is enforced at the data layer, not the view layer.** A missed scope
filter is a data breach — one university seeing another's private content. So
`ScopedModel`'s default manager *raises* when queried with no scope context
rather than returning unfiltered rows, and the only way across surfaces is the
explicit, greppable `Model.objects.unscoped()`. The cross-tenant leakage suite
in `core/tests.py` is the seed of what Section 4.4 makes a release gate.

**Both tokens live in HttpOnly cookies.** JavaScript cannot read either one, so
XSS cannot exfiltrate a session. Refresh tokens rotate, and presenting an
already-rotated token revokes the entire token family — a stolen token and the
real user cannot both keep the session. Mobile uses the same API with bearer
headers and the platform keystore.

**The profile gate is one rule in one place.** Email, phone, and national
identity must all be verified before a user can transact. It is exposed as
`User.can_transact` and as the `CanTransact` permission class, so no future
phase re-derives it and gets it subtly wrong.

---

## Notes

- `eslint` is pinned to 9.x: `eslint-config-next@16` bundles an
  `eslint-plugin-react` that calls APIs removed in ESLint 10.
- The antivirus scanner in `core/tasks.py` is an adapter with the surrounding
  contract implemented (pending → clean/quarantined, retry on failure). Point
  `_scan_bytes` at ClamAV before handling real uploads.
- SMS and push providers are not connected. The queue contract and retry
  behaviour are in place; the send call is a log line until a provider is added.
- Escrow is regulated activity. Per Section 18.7, legal review is required
  before holding customer funds at scale.

---

Built by **NEXOLV.TECH**
