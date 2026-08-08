# SkilRize

A unified freelance marketplace — everything Fiverr does and everything Upwork
does under one account, one wallet, and one reputation — with a second surface
neither has: private, verified portals scoped to a single university.

Built to the specification in *Platform Requirements & Technical Architecture*
(v1.0). Section references throughout the code point back to it.

---

## Status

| Phase | | |
| --- | --- | --- |
| 0 · Foundations | ✅ | Auth, security, tenancy, files, notifications |
| 1 · Projects & bidding | ✅ | Post a brief, compare proposals, award, contract |
| 2 · Gigs | ✅ | Productised services, packages, order lifecycle |
| 3 · Payments & escrow | ⏭️ | **Deferred** — see "The gap in the middle" |
| 4 · Student portals | ✅ | Verification, surface switching, leakage gate |
| 5 · Communities & social | ✅ | Discussion, chat, events, resources, messaging, feed |
| 6 · Search, reputation & trust | ✅ | FTS, ranking, JSS, seller levels, integrity, promotion |
| 7–11 | ❌ | Mobile, professional layer, integrations, admin console, hardening |

**223 backend tests pass.** Lint, format, migration check, `check --deploy`,
type-check, and production build are all clean.

### The gap in the middle

Phase 3 is deferred at the client's direction, and it is worth being plain
about what that means: **no money actually moves.** `fund` and `release` change
contract state and nothing else. Everything built after it — portals,
communities, search, reputation — sits on a marketplace that cannot yet
transact for real.

By phase count the project is 6 of 12. By revenue capability it is at zero
until Phase 3 lands. The state machine those payments will plug into is
already the real one (decision D12), so this is a substitution rather than a
rewrite.

---

## What is built

### Phase 0 — Foundations

| Delivered | Where |
| --- | --- |
| Docker environment, CI, environment-driven config | `docker-compose.yml`, `.github/workflows/ci.yml` |
| Core data model, timestamps, append-only audit log | `api/core/models.py` |
| **Tenancy scope enforcement** (Section 4.4) | `api/core/scope.py` |
| Secure file pipeline — magic bytes, re-encode, signed URLs, AV scan | `api/core/files.py`, `api/core/tasks.py` |
| Field-level encryption (AES-256-GCM) | `api/core/crypto.py` |
| Notification framework with per-channel preferences | `api/core/notify.py` |
| Custom user, both profile faces, universities | `api/accounts/models.py` |
| Argon2id, JWT rotation + reuse detection, TOTP 2FA, step-up | `api/accounts/auth.py` |
| Design system, app shell, auth + settings screens | `web/` |

### Phase 1 — Projects & bidding

| Delivered | Where |
| --- | --- |
| Category and skill taxonomy, seeded | `api/marketplace/models.py` |
| Projects — fixed and hourly, screening questions, draft/open/closed | `api/marketplace/models.py` |
| Proposals with **outstanding-bid quota**, self-bid block, edit window | `api/marketplace/` |
| Contracts with **terms frozen at acceptance** | `api/contracts/models.py` |
| Milestones — fund → deliver → release | `api/contracts/views.py` |
| Work diary with the **tracked-vs-manual asymmetry** and weekly cap | `api/contracts/models.py` |
| **Double-blind two-way reviews** | `api/contracts/models.py` |

### Phase 2 — Gigs

| Delivered | Where |
| --- | --- |
| Gigs with gallery, FAQ, tags, requirements form | `api/gigs/models.py` |
| Three-tier packages with enforced price laddering | `api/gigs/serializers.py` |
| Paid extras adjusting price and delivery time | `api/gigs/models.py` |
| Order lifecycle **gated by the requirements form** | `api/gigs/views.py` |
| Vacation mode, buyer requests, custom offers | `api/gigs/views.py` |

**Orders run on Phase 1's contract.** An order creates a `Contract` with one
funded milestone and drives it, so escrow, messaging, and reviews are shared
across both tracks. A five-star review from a purchased gig and one from a won
proposal are the same row in the same table — which is what makes "one
reputation" true instead of aspirational.

### Phase 4 — Student portals

| Delivered | Where |
| --- | --- |
| Three-gate verification: university email → OTP → ID card → human review | `api/accounts/views.py`, `api/accounts/models.py` |
| `StudentVerification.approve()` — the **only** writer of `User.university` | `api/accounts/models.py` |
| One-click surface switching, sent on every request from one place | `web/lib/api.ts`, `web/components/shell.tsx` |
| **Cross-tenant leakage suite — a release gate** | `api/core/test_tenancy.py` |
| Admin review queue with per-view audit of ID documents | `api/accounts/admin.py` |

The verification code goes to the **claimed** address, not the account address
— sending it to the account would prove nothing about the claim.

### Phase 5 — Communities & social

| Delivered | Where |
| --- | --- |
| Communities — open, approval-gated, invite-only | `api/communities/models.py` |
| Threaded discussion, depth-capped, soft-deleted | `api/communities/models.py` |
| Group chat per community | `api/communities/views.py` |
| Events with capacity and RSVP | `api/communities/models.py` |
| Resource library on signed URLs | `api/communities/views.py` |
| Peer messaging (deliberately unscoped) | `api/communities/models.py` |
| Activity feed, written on the event | `api/communities/models.py` |
| Moderation: pin, lock, remove, report queue | `api/communities/views.py` |

### Phase 6 — Search, reputation & trust

| Delivered | Where |
| --- | --- |
| PostgreSQL FTS — weighted vectors, GIN indexes, trigram fallback | `api/core/search.py`, `api/core/indexing.py` |
| Faceted filtering with counts computed **before** the user's own filters | `api/discovery/views.py` |
| Ranking: relevance + reputation + freshness + promotion | `api/core/search.py` |
| Job Success Score and the seller-level ladder | `api/accounts/reputation.py` |
| Review integrity — six weighted fraud signals | `api/contracts/integrity.py` |
| Promoted placement, always labelled | `api/discovery/models.py` |
| Global work showcase, published on both parties' consent | `api/discovery/models.py` |

### Visual layer

Every listing renders deterministic vector cover art derived from its id and
category (`web/components/artwork.tsx`), so the catalogue looks like a real
product from the first listing, with no stock photography and no network
requests. A seller's uploaded cover replaces it automatically.

The hero is a full-bleed dark panel built from layered colour rather than
photography. To use real footage, drop it in `web/public/` and set
`NEXT_PUBLIC_HERO_VIDEO` — see `web/public/README.md`.

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

```bash
cd api && .venv/Scripts/python manage.py migrate && .venv/Scripts/python manage.py runserver
```

```bash
cd web && npm install && npm run dev
```

### Demo data

```bash
cd api && .venv/Scripts/python manage.py seed --demo
```

Creates the taxonomy plus sample accounts. The command prints the sign-in
credentials it used.

### Tests

```bash
cd api && .venv/Scripts/python -m pytest
```

The cross-tenant leakage gate runs separately in CI and can be run alone:

```bash
cd api && .venv/Scripts/python -m pytest core/test_tenancy.py
```

---

## Architecture

```
SKILRIZE/
├─ api/                     Django REST API — all business logic and authorisation
│  ├─ config/               Settings, URLs, Celery, ASGI/WSGI
│  ├─ core/                 Scope, files, crypto, audit, notifications, search
│  ├─ accounts/             Identity, universities, 2FA, devices, reputation
│  ├─ marketplace/          Track A — projects, proposals, invitations
│  ├─ contracts/            Shared spine — contracts, milestones, reviews, integrity
│  ├─ gigs/                 Track B — gigs, packages, orders
│  ├─ communities/          Communities, discussion, events, messaging, feed
│  └─ discovery/            Search, showcase, promoted placement
└─ web/                     Next.js — presentation only, enforces nothing
   ├─ app/                  Routes: marketing, (auth), (app)
   ├─ components/           Design system primitives + app chrome
   └─ lib/                  API client, session and theme context
```

No client is trusted to enforce a rule. Every endpoint authorises
independently; the web app's route guard is a convenience, not a control.

### Five decisions worth knowing

**Tenancy is enforced at the data layer, not the view layer.** A missed scope
filter is a data breach — one university seeing another's private content. So
`ScopedModel`'s default manager *raises* when queried with no scope context
rather than returning unfiltered rows, and the only way across surfaces is the
explicit, greppable `Model.objects.unscoped()`.

The leakage suite discovers every `ScopedModel` automatically, so a model added
later without a scope test fails the gate rather than slipping through. It
currently covers **10 models across four apps** and runs as its own CI step.

**Scope is resolved on first query, not in middleware.** This API authenticates
with a JWT *inside* DRF, downstream of every middleware, so `request.user` at
middleware time is always anonymous — resolving there meant no account could
ever reach a university surface. `core.scope.defer_scope` registers the
requested surface and resolves it when a scopeable model is first touched.

**Both tokens live in HttpOnly cookies.** JavaScript cannot read either one, so
XSS cannot exfiltrate a session. Refresh tokens rotate, and presenting an
already-rotated token revokes the entire family.

**Two gates guard money, and they are not the same gate.** `CanTransact` covers
participation — a complete profile and a device past its cool-off. `CanMoveMoney`
adds an enrolled second factor and guards only payment. A freelancer wins work
before meeting an authenticator wall.

**Search ranking is stated, not fitted.** Tuning the weights needs completed,
paid contracts to measure against, which Phase 3 has not produced. Every weight
is a named constant with its reasoning attached, and `discovery.SearchLog`
records terms and result counts (deliberately with no user id) so the eventual
argument is about the numbers rather than where they live.

---

## Security posture

| Control | Detail |
| --- | --- |
| Password policy | 12 characters, all four character classes, no runs or keyboard walks |
| Hashing | Argon2id, cost factors **pinned** rather than inherited from Django defaults |
| Brute force | 5 failures locks an account 30 min; 10 failures from one address blocks it 1 hour |
| New devices | Emailed OTP when no authenticator is enrolled; 2-hour hold on transactions either way |
| 2FA | TOTP with server-rendered QR, replay-protected; **required before money moves** |
| Transport | Nonce-based CSP, HSTS preload, COOP/CORP, strict Permissions-Policy |
| Uploads | Magic-byte validation, re-encoding, ClamAV — **fails closed** if no scanner |
| Tenancy | Enforced at the data layer, covered by a release gate |

Enumeration is treated as a leak throughout: account lockout applies to
addresses that do not exist, and content on a surface you cannot see returns
404 rather than 403.

---

## Notes

- `eslint` is pinned to 9.x: `eslint-config-next@16` bundles an
  `eslint-plugin-react` that calls APIs removed in ESLint 10.
- SMS and push providers are not connected. The queue contract and retry
  behaviour are in place; the send call is a log line until a provider is added.
- Group chat is polled, not pushed. The read model is what a socket would need,
  so adding one is a delivery change rather than a schema change.
- Escrow is regulated activity. Per Section 18.7, legal review is required
  before holding customer funds at scale.
- **Known gap:** an admin role cannot enrol 2FA through the product — they
  cannot hold a session without it, and cannot reach enrolment without a
  session. A locked-out admin currently needs a database-level fix.

---

Built by **NEXOLV.TECH**
