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
| 7 · Mobile | ❌ | Flutter parity app |
| 8 · Professional layer | ✅ | CRM, subscriptions, retainers, agencies, workspaces |
| 9 · Admin console | ✅ | Role-gated operator tooling: verification review, contract operations, users, audit log — see below |
| 10 · Integrations | ✅ | Zoom/Google Meet meeting scheduling, GitHub/Figma/Notion read-only activity feeds — every provider real, all off by default, see below |
| 11 · Hardening | ❌ | Not started |
| 12 · Hire after trial | ✅ | A paid trial task before the full project — see below for what "converts" does and does not mean yet |
| 13 · Proof-of-work challenges | ✅ | Timed briefs, human-reviewed scoring, ranked badges — automated Lighthouse grading built but off by default, see below |

**315 backend tests pass.** Migration check and production build are clean.
Lint and format are clean on every file this session touched; `api/challenges`
and `api/core/tasks.py` carry pre-existing lint debt from Phase 13, unrelated
to Phase 10, tracked separately rather than folded into this commit.
`tsc --noEmit` run standalone currently fails on Next's own auto-generated
`.next/types/validator.ts` — a typed-routes quirk that appeared with Phase 9's
nested `admin/layout.tsx` (the first nested layout under `(app)/`), not an
error in any file this repo owns. `next build`'s own internal type-check,
which is what actually gates a real build, passes clean on the identical
route tree.

### The gap in the middle

Phase 3 is deferred at the client's direction, and it is worth being plain
about what that means: **no money actually moves.** `fund` and `release` change
contract state and nothing else. Everything built after it — portals,
communities, search, reputation — sits on a marketplace that cannot yet
transact for real.

By phase count the project is 11 of 14. By revenue capability it is at zero
until Phase 3 lands. The state machine those payments will plug into is
already the real one (decision D12), so this is a substitution rather than a
rewrite.

Phase 8's subscriptions inherit the same deferral. A plan change applies its
new limits immediately and bills nothing, and both the pricing page and the
retainer catalogue say so rather than presenting a checkout that silently
charges zero.

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

### Phase 8 — Professional layer

| Delivered | Where |
| --- | --- |
| Free/Pro/Elite plans, one live subscription per account | `api/professional/models.py` |
| **One entitlements reader**, never a copy cached on the user | `api/professional/entitlements.py` |
| CRM — contacts, deals, pipeline stages, interactions, follow-ups | `api/professional/models.py` |
| Sellable monthly retainers, scoped like any other listing | `api/professional/models.py` |
| Agencies with per-member revenue share and seat limits | `api/professional/views.py` |
| Shared workspaces with a separate client view | `api/professional/models.py` |
| Pricing, CRM, teams and retainer surfaces | `web/app/(app)/{pricing,crm,teams,retainers}` |

**Absence resolves to Free, never to unlimited.** A missing subscription, an
expired one, a database the seed never ran against — all land on the free
tier. The failure mode of a bug here should be somebody getting something
they were not charged for, not everybody getting everything.

A blocked action answers **402 with `upgrade_required`**, a distinct code from
a plain permission denial, so the client can offer the upgrade inline. A
paywall the user cannot act on from where they hit it is a paywall most of
them simply leave.

Seat limits are checked against the **agency owner's** plan rather than the
inviter's — otherwise an admin on a free plan could grow a team past what was
paid for.

### Phase 9 — Admin console

| Delivered | Where |
| --- | --- |
| Seven admin roles (`User.AdminRole`), enforced for the first time — defined since Phase 0, never previously read anywhere | `accounts/auth.py` (`require_admin_role`) |
| Verification review queue — approve/reject with a reason, same `StudentVerification.approve()`/`.reject()` the student-facing flow already uses | `api/accounts/views.py`, `web/app/(app)/admin/verifications` |
| Contract operations — every contract, not scoped to the caller, plus force-funding a milestone as an audited stand-in for a gateway | `api/contracts/views.py` (`AdminContractViewSet`) |
| User search, suspend, and reactivate — reversible, audited, and refuses to suspend another admin account | `api/accounts/views.py`, `web/app/(app)/admin/users` |
| Audit log viewer — read-only, Super Admin only, filterable by action/actor/target | `api/accounts/views.py` (`admin_audit_log`) |

**Role-gated, not just admin-gated.** A Verification Officer reaches the
verification queue and nothing else; a Support Agent reaches user search and
nothing else. The frontend nav only *shows* what a role covers — the actual
boundary is `require_admin_role` on every endpoint, matching the same
"client guard is a convenience, not the control" rule the rest of the app
already follows. Super Admin bypasses every specific role check.

**Two things this deliberately does not do.** Resolve a contract dispute —
`Contract.Status.DISPUTED` has existed since Phase 1 with nothing in the
product that ever sets it, so a "resolve" screen would be UI for a state
nothing can reach. And impersonation — `AuditLog.Action.IMPERSONATE` has
sat unused since Phase 0 for the same reason; acting *as* another user is a
materially riskier feature than anything else in this console and deserves
its own review, not a bolt-on. See D35.

### Phase 10 — Integrations

| Delivered | Where |
| --- | --- |
| Account-wide connect/disconnect for five providers — Zoom, Google Meet, GitHub, Figma, Notion | `api/integrations/models.py` (`IntegrationConnection`), `web/app/(app)/settings/integrations` |
| OAuth is API-only, no server-side session — a signed, 10-minute `state` token carries the caller's id, verified on the callback rather than trusted from it | `api/integrations/views.py` (`authorize`, `connect`) |
| Meeting scheduling on a contract — a real Zoom or Google Meet call, not a placeholder link | `api/integrations/models.py` (`Meeting`), `providers/zoom.py`, `providers/google_meet.py` |
| Read-only activity feed on a contract — GitHub repo events, Figma file versions, a Notion page's last-edited signal | `api/integrations/models.py` (`ActivityFeedSource`, `ActivityEvent`), `providers/github.py`, `providers/figma.py`, `providers/notion.py` |
| Contract page panels: Meetings, Linked activity | `web/components/integrations.tsx` |

**Every provider is real, and every provider is off by default.** Same
pattern as `LIGHTHOUSE_ENABLED` (D33): `ZOOM_ENABLED`, `GOOGLE_MEET_ENABLED`,
`GITHUB_ENABLED`, `FIGMA_ENABLED`, `NOTION_ENABLED` all default to `False`
because no OAuth app has real credentials issued in this environment yet.
This is not five stubs — `authorize_url`, `exchange_code`, and each
provider's action (`create_meeting` / `fetch_activity`) are genuine API v2/v3
calls against Zoom, Google Calendar, GitHub, Figma, and Notion. The day a
client id and secret exist for a provider, connecting it starts working with
zero further code changes; until then, the UI shows "Not available yet," not
a broken button.

**Tokens are encrypted at rest**, the same `EncryptedTextField` treatment
Section 7.3 already requires for OTP secrets and payout credentials
(`core/crypto.py`) — reused rather than re-derived.

**Notion's activity signal is honestly coarser than the other two.** The
public Notion API has no per-edit timeline outside the Enterprise-only Audit
Log API, which most connected workspaces will not carry. `fetch_activity`
therefore returns at most one synthetic "page last edited at T" event per
sync rather than a real feed — documented plainly in
`providers/notion.py`'s module docstring rather than silently shipped as if
it behaved like GitHub's.

**What this deliberately does not do: poll on a schedule yet.** A "sync now"
action exists on every activity source, and `sweep_activity_sources`
(`integrations/tasks.py`) syncs every source with a connected party — but
it is not wired to `CELERY_BEAT_SCHEDULE`, because nothing in this codebase
is yet; `core.tasks.sweep_promotions` and `sweep_challenge_deadlines` carry
the identical gap. Automatic polling is the same piece of missing
infrastructure in all three cases, not a Phase 10 shortcut.

### Phase 12 — Hire after trial

| Delivered | Where |
| --- | --- |
| A client offers a small paid task on a specific proposal, before awarding the full project | `api/contracts/models.py` (`Trial`), `marketplace/views.py` |
| Accepting opens the trial's own one-milestone contract — funded, delivered, and released through the exact same endpoints every other contract already uses | `Trial.accept()` |
| "Continue with this freelancer" awards the full project once the trial is delivered and approved | `Trial.convert()` |
| Contract creation refactored into `Contract.create_from_proposal()`, shared by a normal award and a trial conversion | `api/contracts/models.py` |

**Deliberately not new infrastructure.** The whole feature is "a new shape of
order and a conversion path," per the roadmap's own framing when this phase
was scoped (D31) — a trial rides the same fund → deliver → release machinery
a gig order already reuses. The only genuinely new surface is proposing the
trial and converting it afterwards; everything in between is the existing
`/contracts/<id>/milestones/<id>/...` API, untouched.

**What "convert" does not do: credit the trial fee toward the new
contract.** That is a ledger operation — crediting one payment against
another — and there is no ledger until Phase 3 ships. The trial amount is
recorded on the `Trial` row so the client sees it plainly instead of the
platform silently forgetting a payment it already collected; applying it is
a manual adjustment today, not an automation. See D31 and D34.

**Found while building it, not before:** the original `award` endpoint
created its `Contract` row *before* validating that milestone amounts added
up to the agreed price. A rejected 400 still left that row behind — and
since `Contract.proposal` is a `OneToOneField`, the zombie row occupied the
slot permanently, making the proposal un-awardable on every later attempt
regardless of whether the amounts were now correct. Fixed by validating
before creating anything; covered by a regression test that asserts a
second, correct attempt succeeds.

### Phase 13 — Proof-of-work challenges

| Delivered | Where |
| --- | --- |
| Timed briefs — join starts your own clock, capped at the challenge's own close | `api/challenges/models.py` |
| Submission by **live URL**, not uploaded code — see "What this is not" below | `api/challenges/views.py` |
| SSRF-safe URL validation, checked at submission and again immediately before any server-side fetch | `api/challenges/url_safety.py` |
| Automated grading adapter — Lighthouse against the submitted URL | `api/challenges/grading.py` |
| Weighted scoring (automated + human), percentile ranking, badge award | `api/challenges/models.py` |
| Interim admin console for authoring briefs and reviewing submissions | `api/challenges/admin.py` |
| Browse, join, submit, and result surfaces; badges on the dashboard | `web/app/(app)/challenges`, dashboard's `BadgesCard` |

**What this deliberately is not: a code sandbox.** The pitch this phase came
from describes grading with "automated tests, Lighthouse, unit tests,
predefined test cases." Running freelancer-submitted *source code* server-side
needs real sandboxing (gVisor, Firecracker, or an isolated Docker-in-Docker
runner) — genuinely new infrastructure, comparable in scope and risk to the
payment rails Phase 3 is waiting on, not something to bolt onto a Celery task.
What shipped instead: a freelancer submits a **live deployed URL**, and
Lighthouse audits that public page over the network — a page fetch, not code
execution. It gets most of the automated-grading value with none of the
"executing a stranger's code on our infrastructure" risk. See D33.

**Automated grading is real code, gated off by default.** `LIGHTHOUSE_ENABLED`
defaults to `False` — the worker image does not carry Node and headless
Chromium yet, so `lighthouse` would not be on `PATH` even with this on. A
challenge can be run entirely human-reviewed today (`automated_weight=0`); the
day Chromium lands in `api/Dockerfile`, automated scoring works with zero
further code changes. Same adapter shape as `CLAMAV_HOST`.

### Visual layer

**Marketing pages use photography.** The landing page is built on ten photos in
`web/public/img`, served from our own origin — the CSP allows `img-src 'self'`
and nothing else — and rendered through `next/image`, so each one ships as
AVIF/WebP at the requested size, lazily, in a box whose height is reserved
before it loads. All ten are under the
[Unsplash licence](https://unsplash.com/license): free for commercial use, no
attribution required. Replacing one is a file swap; the paths are listed in
`web/app/page.tsx`.

**Application pages do not.** Every listing without a seller-uploaded cover
renders deterministic vector art derived from its id and category
(`web/components/artwork.tsx`), so a catalogue with two listings in it still
looks like a product. A seller's own image replaces it automatically.

Headlines are set in Instrument Serif, self-hosted at build time by
`next/font`. It is confined to marketing display type — the application chrome
is Geist throughout, because a display serif under about 20px stops being
elegant and starts being hard to read.

**Nothing on the marketing pages claims traction the platform has not earned.**
No customer quotes, no borrowed client logos, no listing counts. An earlier
revision of the landing page carried four invented testimonials, complete with
names and five-star ratings, for a platform with no users and no payment rails;
they are gone. What replaced them is a list of things the software actually
does, each of which is checkable in this repository.

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

CI runs with `DEBUG=False`, which is the configuration that ships. The suite is
written to behave identically either way — `conftest.py` turns off the two
settings a plain-http test client cannot satisfy — but if you are chasing a
failure that only appears in CI, reproduce it with the same environment:

```bash
cd api && DEBUG=False SECRET_KEY=ci-secret-key FILE_SIGNING_KEY=ci-file-signing-key .venv/Scripts/python -m pytest -q
```

---

## Deployment

`deploy/` holds a complete production path: gunicorn + whitenoise instead of
the dev servers, a Caddy reverse proxy with automatic HTTPS, a real ClamAV
sidecar, nightly off-server backups, and a one-command deploy script. Written
for a single Oracle Cloud "Always Free" ARM instance, but nothing in it is
Oracle-specific — any VPS running Docker works.

**[deploy/README.md](deploy/README.md) is the full step-by-step runbook.**
Everything below is what exists, not how to use it.

| Piece | File |
| --- | --- |
| Reverse proxy, automatic HTTPS | `deploy/Caddyfile` |
| Production stack (own project, own volumes — never shares state with the dev `docker-compose.yml`) | `deploy/docker-compose.prod.yml` |
| Secrets template (copy to `production.env`, gitignored, never commit the real one) | `deploy/production.env.example` |
| OS firewall — the other half is a manual step in Oracle's console, documented at the top of the script | `deploy/setup-firewall.sh` |
| Nightly DB + upload backups to Backblaze B2 | `deploy/backup.sh`, `deploy/crontab.example` |
| The only command that should ever update the live site | `deploy/deploy.sh` |

Payments (Phase 3) are not part of this — the infrastructure above gets a
live, reachable site with working auth, email, uploads, and 2FA. Don't
advertise it as open for business until Phase 3 ships; see D32.

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
│  ├─ discovery/            Search, showcase, promoted placement
│  ├─ professional/         Plans, entitlements, CRM, retainers, agencies
│  ├─ challenges/           Proof-of-work challenges, grading, badges
│  └─ integrations/         Zoom/Google Meet, GitHub/Figma/Notion adapters
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
currently covers **12 models across six apps** and runs as its own CI step —
Phase 8's `RetainerPlan` was picked up by it without a line of test code.

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
- Email is real locally: the default backend writes each message as a `.log`
  file into `api/.mail/` rather than to a real inbox, so signup confirmations,
  password resets, and campus verification links can be opened and clicked
  without an SMTP account. Point `EMAIL_BACKEND` at real SMTP for anything
  beyond a laptop — see `.env.example`.
- SMS and push are not connected — no backend fills the file-based role email
  has. The OTP is logged (`accounts.views: phone_otp user=... code=...`)
  rather than sent, so phone verification is testable but not usable by
  someone who cannot read the server's own log.
- Group chat is polled, not pushed. The read model is what a socket would need,
  so adding one is a delivery change rather than a schema change.
- Escrow is regulated activity. Per Section 18.7, legal review is required
  before holding customer funds at scale.
- **Known gap:** an admin role cannot enrol 2FA through the product — they
  cannot hold a session without it, and cannot reach enrolment without a
  session. A locked-out admin currently needs a database-level fix.
- **Open pricing question:** the Elite tier lists "team and agency
  workspaces", but only *agencies* are gated — `WorkspaceViewSet` applies no
  entitlement check, so any user can open a shared workspace. Erring toward
  giving away more than was paid for is the intended direction, but the copy
  and the enforcement should agree. Either gate workspaces to Elite or drop
  them from the tier's feature list.
- **Known gap:** periodic sweeps (`sweep_promotions`, `reindex_search`,
  `refresh_reputation`, `assess_review_integrity`, and now
  `sweep_challenge_deadlines`) are defined as real Celery tasks but nothing
  seeds a `django_celery_beat` schedule for any of them yet — they run only
  when invoked by hand. Not new to this phase; challenges just makes it a
  fifth instance of a gap already worth closing once.

---

Built by **NEXOLV.TECH**
