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
| 3 · Payments & escrow | ✅ | Custodial escrow — client transfers to the platform's own bank account, admin-fulfilled payout on release, commission split — see below |
| 4 · Student portals | ✅ | Verification, surface switching, leakage gate |
| 5 · Communities & social | ✅ | Discussion, chat, events, resources, messaging, feed |
| 6 · Search, reputation & trust | ✅ | FTS, ranking, JSS, seller levels, integrity, promotion |
| 7 · Mobile | ✅ | Flutter client, full parity with the web app's signed-in surface — marketplace, money-moving contract/gig actions, messaging, communities, search, the professional layer, challenges, integrations, admin console, student verification, settings, feed/showcase — behind a 5-tab shell; see below |
| 8 · Professional layer | ✅ | CRM, subscriptions, retainers, agencies, workspaces — plan billing wired to the same custodial bank-transfer model as Phase 3, see below |
| 9 · Admin console | ✅ | Role-gated operator tooling: verification review, contract operations, users, audit log — see below |
| 10 · Integrations | ✅ | Zoom/Google Meet meeting scheduling, GitHub/Figma/Notion read-only activity feeds — every provider real, all off by default, see below |
| 11 · Hardening | ✅ | Rate limiting, HSTS, error tracking, a wired Celery beat schedule, retry/backoff, a DB index audit, and the admin 2FA enrolment fix — see below |
| 12 · Hire after trial | ✅ | A paid trial task before the full project — see below for what "converts" does and does not mean yet |
| 13 · Proof-of-work challenges | ✅ | Timed briefs, human-reviewed scoring, ranked badges — automated Lighthouse grading built but off by default, see below |

**364 backend tests pass (19 of them the cross-tenant leakage gate), plus 11
Dart tests and a 4-test live suite for the mobile client** (`flutter analyze`
clean across all ~32 screens; the live suite runs against a real stack — see
`mobile/README.md`). Migration check and production build are clean.
`ruff check`/`ruff format --check` are clean across every file in `api/` —
the `api/challenges`/`api/core/tasks.py` debt from Phase 13 that earlier
sessions tracked separately rather than fix inline is gone, closed once CI
actually surfaced it (13 `E501`/`S607`/`B015` findings, none behavioural:
long lines wrapped, a `noqa` moved onto the line ruff actually anchors
`S607` to, and one test's dangling `is None` comparison turned into a plain
assertion of "doesn't raise"). `tsc --noEmit` run standalone is clean too —
the typed-routes quirk against `.next/types/validator.ts` a prior session
hit does not reproduce.

### Phase 3, rebuilt: custodial escrow, not a gateway

Phase 3 originally landed on **Swich** (D41) — a real Pakistan-native
payment gateway, verified against its actual sandbox. That integration was
torn out at the client's explicit direction (D42): Swich's *production*
merchant account requires an NTN (Pakistan's business tax number), which
the client does not have and does not want to register for right now. NTN
is not a Swich quirk — it is an SBP/FBR requirement on every licensed
payment gateway operating in Pakistan, so no drop-in gateway replacement
would have avoided it.

What runs now instead: the platform's own bank account **is** the escrow
account. A client funding a milestone sees that account's details in the
UI and transfers the money directly to it, then confirms in the app that
they've sent it — the same trust basis the pre-Phase-3 code always ran on,
just framed honestly rather than hidden behind gateway language. Releasing
a milestone computes a transparent commission split (freelancer's net,
platform's cut, both shown before the client confirms) and queues a
`Payout` row; a human on the platform side sends that transfer by hand and
marks it paid. Nothing here is faked as automated — the UI still calls it
"escrow" throughout, because structurally it is: money sits in the
platform's account, held, until a release decision moves it out.

**This is a deliberate step back from D41's automation, not a hidden
regression.** The Swich integration code, its checksum verification, and
its automated IBFT payout are gone, not disabled behind a flag — the
client asked for Swich removed, not parked. D41's market research (why
Stripe/Rapyd/Airwallex don't work for a Pakistan-registered entity, why
Safepay alone wasn't enough) stays valid context for *why* nothing
automated currently sits in this gap; it just is not wired to anything
right now. Re-adding a real gateway later is a matter of wiring
`fund_milestone`/`release_milestone`/`gigs.order` to it again — the
`EscrowFunding`/`Payout` bookkeeping shape barely has to change.

By phase count the project is 14 of 14 phases built. Phase 8's plan
billing was the one gap this left: `subscribe` used to activate a paid
tier with no money changing hands, and the pricing page said so outright
rather than presenting a checkout that silently charged zero. D43 closes
that gap the same way D42 closed Phase 3's — a paid tier now declares a
bank transfer to the platform's own account, the same trust basis every
other money-adjacent endpoint in this codebase runs on, gated by
`CanMoveMoney` like funding a milestone or ordering a gig. Retainers
(seller-to-buyer, not account-to-platform) are a separate mechanism and
still say so on their own catalogue.

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

### Phase 3 — Payments & escrow

| Delivered | Where |
| --- | --- |
| `EscrowFunding` — a client's own declaration that they've transferred a milestone's money to the platform's bank account | `api/payments/models.py` |
| `Payout` / `PayoutProfile` — the commission split computed and snapshotted at release, and where a freelancer's money actually goes | `api/payments/models.py` |
| `bank_transfer_instructions` — the one real piece of payment infrastructure this phase has: the platform's own account details | `api/payments/views.py`, `api/payments/urls.py` |
| Contract milestone funding is an immediate, client-confirmed declaration — no checkout redirect, no webhook | `api/contracts/views.py` (`fund_milestone`) |
| Gig ordering funds the same way, synchronously, before any contract/order rows are created | `api/gigs/views.py` (`order`) |
| Milestone release computes the commission split and queues a `Payout`, refusing to start without a complete payout profile — fulfilled by hand, marked paid in the admin | `api/contracts/views.py` (`release_milestone`), `api/payments/admin.py` (`mark_paid`) |
| Freelancer payout profile — bank/CNIC, encrypted at rest, nothing echoed back through the API | `api/payments/views.py`, `web/app/(app)/settings/payouts/`, `mobile/lib/src/screens/payouts_screen.dart` |
| Gig-order acceptance (`OrderViewSet.accept`) creates its `Payout` on its own release path — a gap that existed since before Phase 3 even under Swich, caught and fixed in this pass | `api/gigs/views.py` (`OrderViewSet.accept`) |

**Framed as escrow throughout the product, because structurally it still
is one.** A client funding a milestone or buying a gig sees the platform's
bank details and confirms once they've sent the transfer — `EscrowFunding`
records that declaration, and nothing downstream pretends a gateway
verified it. Releasing a milestone is unconditional on the client's
approval; the `Payout` it queues is not — release refuses outright without
a complete `PayoutProfile` on file, since a `Payout` row with nowhere to
send the money is worse than one that doesn't exist yet. The commission
split (`Payout.compute`) is the one place that arithmetic lives, so the
web/mobile "you'll receive Rs X after our Y% fee" estimate and what
actually gets recorded at release can never drift apart — confirmed by
running the whole fund → deliver → release loop against a live local
stack, not only the test suite.

See D42 for why Swich (D41's real, sandbox-verified gateway) was removed
rather than kept running: an NTN requirement on its production merchant
account, which applies to any licensed Pakistani gateway, not a Swich
defect.

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

### Phase 7 — Mobile

| Delivered | Where |
| --- | --- |
| Flutter client — sign-in with both second-factor paths, dashboard, project search, contracts and milestones, notification centre | `mobile/lib/` |
| Bearer auth, the path `CookieJWTAuthentication` documented since Phase 0 but that nothing could reach — no endpoint ever handed a non-browser client a token | `mobile/lib/src/api/client.dart`, `api/accounts/views.py` |
| Device registration — upsert on token, not per-user, so a phone that changes hands doesn't keep the previous account's notifications | `api/core/models.py` (`PushDevice`) |
| Real Firebase Cloud Messaging delivery, gated off by default like every provider before it | `api/core/push.py` |
| `Channel.PUSH` actually wired — `deliver_notification` fans out to every active device instead of logging `pending_provider`, and prunes tokens FCM reports dead | `api/core/tasks.py` (`_deliver_push`) |
| A client bootstrap flag so the app never asks for the OS push permission on a deployment that can't deliver on it | `api/core/views.py` (`config`) |
| **Full-parity build**: marketplace proposals, gig ordering/orders, contract money actions (fund/release/deliver/review), messaging, communities, unified search, the professional layer (CRM/subscriptions/retainers/agencies/workspaces), proof-of-work challenges, integrations (provider connect + contract meetings/activity), role-gated admin console, student verification with real ID-card photo upload, account/2FA settings, activity feed and showcase | `mobile/lib/src/screens/`, `mobile/lib/src/api/endpoints.dart` (~90 API methods) |
| Five-tab shell (Home/Work/Messages/Contracts/More) replacing the four-tab foundation, since a phone nav bar cannot hold ~35 routes | `mobile/lib/src/screens/home_shell.dart`, `work_hub_screen.dart`, `more_screen.dart` |

**Full parity with the web app's signed-in surface**, not the earlier
foundation slice. Every domain from every phase built so far is a real,
working screen against the real API — including every money-moving action,
gated exactly as the API gates it (`CanTransact`/`CanMoveMoney`/403 vs the
professional layer's `upgrade_required`/402, both routed through one
`MoneyGateBanner` rather than each screen reimplementing the branch). The
one deliberate gap: OAuth-style integration "Connect" needs a web view or
external-browser hop that stays a `TODO` until a provider has real
credentials to test the redirect against — everything before and after that
hop is real.

**Three real bugs came out of building it**, each found by running the thing
rather than reading it:

* The bearer path was documented and unreachable — `login` and `refresh` only
  ever set cookies. Fixed so a client identifying itself with
  `X-Skilrize-Client: native` gets its tokens, with `refresh` returning them
  only to a caller that supplied one in the body, so injected script in a
  browser can never lift a token it cannot already read.
* `package:http` decodes a body with no charset as **latin-1**, and DRF sends
  `application/json` with no charset. Every non-ASCII character — an Urdu
  project title, an accented name — would have been mangled. Caught by a test
  using the masked `m•••r@example.com` hint.
* `X-Skilrize-Surface` was never in the CORS allow-list. The app found it via
  its own header; the web app would have hit the same wall the first time a
  student switched into a campus portal.

**Verified by running it, not just compiling it.** `flutter analyze` clean,
11 mocked tests, and a separate `live` suite that drives the real client
against a running Django stack — real sign-in, real bearer token accepted
back, real push registration. See `mobile/README.md`.

**Push still has no token source.** Registration, gating, and unregistration
are real; obtaining the FCM token needs a Firebase project that does not
exist for this environment. One `TODO` marks the single call. iOS is also
unbuilt — it needs macOS, which no amount of code changes.

**Same off-by-default shape as every provider in this codebase.**
`FCM_ENABLED` defaults to `False` — no Firebase project exists for this
environment — and `core/push.py`'s `send()` is a genuine FCM HTTP v1 call,
not a stub. The day a service-account key exists, push starts working with
zero further code changes.

**A token is not a secret, and is stored accordingly.** Unlike the OAuth
tokens in `api/integrations/` or the OTP secrets in `accounts/models.py`,
an FCM registration token identifies a device, not a credential — sending
to it needs the service-account key, which never enters the database at
all. `PushDevice.token` is a plain, unique, lookup-friendly column rather
than `EncryptedTextField`, and the reasoning is in the model's own
docstring rather than assumed obvious.

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
| `SubscriptionPayment` — a paid tier's price, reported as transferred to the platform's own bank account (D43) | `api/payments/models.py` |

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

**Billing, wired to Phase 3's custodial model (D43).** `subscribe` used to
activate a paid tier for free — a real gap the pricing page said so about
outright. Now a paid tier runs on the same trust basis `fund_milestone` and
`gigs.order` do: the caller has already transferred the plan's price to
`GET /payments/bank-transfer-instructions/`'s account, and confirming that
creates a `SubscriptionPayment` alongside the `Subscription`, gated by
`CanMoveMoney` the same way any other money-adjacent endpoint is. Switching
to Free needs no declaration, since nothing is being paid for — `cancel()`
is the whole story there, unchanged from before D43. Unlike `Payout`,
`SubscriptionPayment` has no release half: the whole amount is the
platform's the moment the row exists, so there is nothing to queue and
nothing for `payments.admin` to mark paid. The web pricing page and mobile
`SubscriptionScreen` both reuse the existing bank-transfer UI
(`BankTransferPanel`/`showBankTransferDialog`) rather than building a
second one — the mobile dialog gained an optional `title` so "Fund into
escrow" doesn't show up over a plan purchase.

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

A "sync now" action exists on every activity source for the moment fresh
data is needed immediately; `sweep_activity_sources` now also runs on its
own every 30 minutes — wired in Phase 11, see below.

### Phase 11 — Hardening

| Delivered | Where |
| --- | --- |
| Six periodic tasks — three that said so, three that didn't — actually wired to a schedule for the first time | `core/migrations/0004_seed_beat_schedule.py` |
| A real, pre-existing bug: `signup`/`login`/`otp`/`password_reset`'s named rate limits were silent no-ops | `api/core/throttling.py` |
| Two new throttle scopes on genuinely new attack surface (`integrations/`), `writes_only` so browsing isn't capped like writing | `api/integrations/views.py` |
| HSTS — the one security header the codebase hadn't set | `api/config/settings.py` |
| Error tracking, gated off by default like every provider before it | `api/config/settings.py` (`SENTRY_DSN`) |
| Retry/backoff on every outbound provider call, proved against a real flaky server | `api/integrations/providers/base.py` |
| The one hot-path DB index that was missing | `api/marketplace/models.py` (`Proposal`) |
| Dependabot, weekly, grouped | `.github/dependabot.yml` |
| The admin 2FA enrolment dead end (named as debt since Phase 9) — closed | `api/accounts/views.py` (`login_two_factor_enrol_setup`/`_confirm`) |

**The rate-limiting bug is the finding that mattered most.** Reading
`DEFAULT_THROTTLE_RATES` in `settings.py`, four endpoints looked protected —
5/hour on signup, 10/minute on login, 5/minute on OTP, 5/hour on password
reset. None of it was enforced. `@api_view`'s wrapping never copied
`throttle_scope` from the pre-wrap function onto the class it built, so
`ScopedRateThrottle` silently allowed every request through; only the
blanket anon/user rates the whole API carries were ever real on these four.
Rewritten as `core/throttling.py`'s `scoped_throttle()`, which sets the
scope on the dispatched view instance instead of trying to get it there
beforehand — proven at the real production rate by a regression test, not
a relaxed one used only for the suite's own convenience. See D37 for the
second bug this one's fix surfaced, in how DRF caches its own rate table.

**Every provider before this one gets the same off-by-default treatment,
and this one is no exception.** `SENTRY_DSN` unset is the SDK's own inert
state — proven both ways by a subprocess test, since the init runs once at
import time. What isn't built: the browser-side half. `@sentry/nextjs`
needs source-map credentials this session didn't have a safe way to add;
named directly in DECISIONS.md rather than shipped half-wired.

**What this deliberately does not do: penetration testing, load testing, a
legal/compliance review, or external monitoring dashboards.** Each needs an
authorized third party, real traffic infrastructure, or a lawyer — not an
engineering session. Named in DECISIONS.md's "Not mine to take" rather than
silently dropped from the four areas the phase was scoped to. See D37.

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

The infrastructure above gets a live, reachable site with working auth,
email, uploads, and 2FA; see D32. Phase 3's custodial escrow (D42) adds one
more production requirement on top of it: `PLATFORM_BANK_NAME`,
`PLATFORM_BANK_ACCOUNT_TITLE`, and `PLATFORM_BANK_ACCOUNT_NUMBER` in
`production.env` have to point at a real account the platform controls
before launch — every other setting in this list has a safe default or
can stay disabled, but a blank bank account here means the bank-transfer
panel shows nothing to transfer to.

### Free test deploy (not production)

`render.yaml` at the repo root is a second, much smaller deployment
path — a Render Blueprint that fits Render's free web-service tier plus a
free Postgres, for kicking the tyres on a real deployment without paying
anything. No platform gives a free background worker, so this drops
Redis and Celery's worker process entirely: `config/settings.py` already
falls back to Django's in-process cache and Celery's synchronous "eager"
mode whenever `REDIS_URL` is unset, which is exactly the condition
`render.yaml` sets up. What that trades away — no periodic sweeps
(reindexing, reputation refresh, promotion, challenge deadlines), an idle
service that sleeps after 15 minutes and takes under a minute to wake,
a free database Render deletes after 90 days, and uploads that don't
survive a redeploy — is documented in comments at the top of the file
itself, not just here.

Render can't be signed up for or connected on anyone's behalf, so the
steps from here are manual: push to GitHub, create a Render Blueprint
pointed at this repo (it reads `render.yaml` on its own), deploy `web/`
to Vercel with `NEXT_PUBLIC_API_URL` set to the Render URL, then go back
and point the API's `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS` at the real
Vercel URL. `render.yaml`'s own comments walk through this in order.

Email verification and password-reset links deliver for real, through
Gmail SMTP — a free Google Account App Password, set by hand in Render's
dashboard rather than committed to this file (`EMAIL_HOST_USER`/
`EMAIL_HOST_PASSWORD`/`DEFAULT_FROM_EMAIL` are `sync: false` in
`render.yaml` for exactly that reason). Phone OTP has no equivalent:
every real SMS provider only sends free-trial messages to a number
pre-verified in that provider's own console, and sending to an arbitrary
number a user actually types in costs real money at every provider —
not a gap specific to this deployment, a fact about how SMS is priced
everywhere. The code still logs (`ENVIRONMENT=test` unlocks the same log
line `DEBUG` does locally), readable from Render's Logs tab.

Actually deploying this surfaced a real bug that has nothing to do with
free tiers specifically: the web client read its CSRF token from
`document.cookie`, which only ever works when the web app and the API
share a hostname — true of every environment that had exercised this
path before (`localhost` at two ports locally, subdomains of one domain
in D32's real deployment, neither of which actually tests two genuinely
different domains reading each other's cookies). Vercel and Render broke
it outright: the first request after a fresh session works, then every
one after that fails CSRF, permanently, because a page on one domain
can never read a cookie a different domain set. Fixed in D45 by having
the API hand back the token in the response body instead of relying on
the client reading it off a cookie — works the same regardless of
whether the two sides share a domain, a subdomain, or nothing at all.

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
├─ web/                     Next.js — presentation only, enforces nothing
│  ├─ app/                  Routes: marketing, (auth), (app)
│  ├─ components/           Design system primitives + app chrome
│  └─ lib/                  API client, session and theme context
└─ mobile/                  Flutter client — bearer auth, a slice of the web app
   ├─ lib/src/api/          Client, typed endpoints, token storage
   ├─ lib/src/screens/      Sign-in, dashboard, projects, contracts, alerts
   └─ test/                 Mocked suite + a `live` suite against a real stack
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
