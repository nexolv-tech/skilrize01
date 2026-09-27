# Decision log

Founder-level calls taken under delegated authority from Ibad Ahmed (CEO),
4 August 2026. Every one is reversible — say the word and I change it and note
the reversal here.

Anything that commits real money, signs a contract, or requires a legal
identity is **not** taken here. Those are listed at the bottom.

---

## D1 · Product name and domain

**SkilRize.** Primary domain `skilrize.com`; university portals on
`campus.skilrize.com/<code>`.

*Why:* Already in use across the report and the codebase. The subdomain split
keeps portal content off the indexable marketing domain, which Section 15.1
requires anyway.

*Reversing:* Cheap now, expensive after launch. Decide before public launch.

---

## D2 · Commission and fees

| Fee | Rate |
| --- | --- |
| Freelancer commission | **10%**, falling to **7%** at Top Rated |
| Client service fee | **4%** on each funding event |
| Withdrawal fee | **At cost** — gateway charge passed through, no margin |
| University portal commission | **0% during the growth phase** |

*Why:* A flat rate is simpler than Upwork's sliding scale and materially below
Fiverr's 20% — that difference is a reason to choose us, so it should be easy
to state. 4% sits mid-range of the report's 3–5% suggestion. Profiting on
withdrawals damages trust for trivial revenue.

The portal carve-out is the important one: portals exist to manufacture trusted
supply, not revenue (Section 2.3). Taxing a student's first Rs 800 order costs
us the exact behaviour we are trying to create. Revenue comes when those users
graduate into the global marketplace.

*Reversing:* Rates are configuration, not code. Changeable per tier and per
portal from the admin console at any time.

---

## D3 · Operating entity

**Pakistan-only to start.** Revisit at Phase 6, once there is evidence of
international client demand.

*Why:* Stripe and PayPal cannot receive funds into Pakistan regardless, so a
foreign entity buys nothing until cross-border volume exists. It costs real
money and permanent accounting overhead.

*Accepting:* First clients are domestic. The ledger is multi-currency from the
first line of code (D7), so adding a second rail later is an integration, not a
rewrite.

---

## D4 · Launch university

**COMSATS Islamabad**, as the default of record.

*Why:* Named in the report as a reference campus, large, tech-heavy, and in the
same city as the operating base. One campus executed densely beats five
executed thinly.

*This one I am least qualified to make.* The deciding factor is not campus size
— it is whether the founder can personally hand-recruit the first ~30 sellers
and one moderator. That depends on a personal network I have no visibility
into. **Override this if a different campus is where you actually know people.**

---

## D5 · Portal monetisation

**Free to students, permanently.** No commission, no subscription, no listing
fees inside university portals.

*Why:* The portals are the acquisition and trust engine. Monetising them
directly undercuts the strategic bet. If portals ever earn, it should be
through institutional partnerships and career-services licensing sold to the
university, never charged to the student.

---

## D6 · Free-tier limits

Per Section 21.1, adopted as written: **5 active gigs and 30 outstanding
proposals** on the global free plan; **8 active gigs and 50 outstanding
proposals** for verified students inside their portal. Caps apply to active,
not lifetime, counts. Hitting a cap shows an upgrade prompt, never a silent
block.

---

## D7 · Currency and ledger

**PKR as the primary currency, multi-currency double-entry ledger from day one.**

*Why:* Retrofitting currency into a single-currency ledger is a rewrite, and
this is the one system where a defect is least forgivable. Costs almost nothing
to build correctly the first time.

---

## D8 · Escrow architecture under legal uncertainty

**Build Phase 3 so that custody is an adapter choice, not an assumption.**

Whether SkilRize may hold client funds directly, or must sit behind a licensed
payment partner as instruction-giver, is an open legal question (Section 18.7).
Rather than wait for the answer or guess it, the escrow state machine will be
written against a custody interface with two implementations — platform-held
and gateway-held.

*Why:* This removes the legal question from the critical path entirely. Either
answer becomes a configuration change instead of a redesign, and Phase 3 can
proceed before the lawyer reports back.

---

## D9 · Session and token handling

**Both access and refresh tokens in Secure/HttpOnly/SameSite cookies**, with
rotation and family-wide revocation on reuse. Mobile uses the same API with
bearer headers and the platform keystore.

*Why:* Neither token is reachable from JavaScript, so cross-site scripting
cannot exfiltrate a session — a stronger position than the common
"access token in memory" pattern, and it still satisfies the rule that access
tokens never touch localStorage. *Already implemented in Phase 0.*

---

## D10 · Tenancy model

**One database, row-level scoping**, enforced at the data-access layer by a
manager that refuses to run without a scope context.

*Why:* Onboarding a university becomes a configuration record rather than an
infrastructure project, and reputation, wallet, and portfolio stay shared
across a student's two surfaces without synchronising the exact data that must
never diverge. The trade-off — isolation enforced by code rather than
infrastructure — is answered by making the cross-tenant leakage suite a release
gate. *Already implemented in Phase 0.*

---

## D11 · Brand voice and competitor naming

**No competitor is named anywhere in the product.** Not in copy, not in
metadata, not in a CSS comment.

Positioning line: **“Find the right talent. Or become it.”** It speaks to both
sides of the marketplace in one breath, and the second half carries the student
story — someone arrives to hire and leaves able to earn.

*Why:* Defining ourselves as "X plus Y" makes us sound like a derivative of
both and cedes the category to them. The dual-track model is described in our
own terms — "some work needs a conversation, some just needs doing" — which is
the actual insight, stated without borrowing anyone's name.

*Founder instruction, 4 August 2026.*

---

## D12 · Manual funding until the gateway lands

**Milestone funding in Phase 1 is an explicit client action, recorded and
audited, standing in for a gateway capture.**

*Why:* The full contract lifecycle — fund, deliver, release, auto-complete — is
worth building and testing now, and it is the same state machine either way.
Phase 3 replaces the trigger, not the design. This also keeps the escrow work
off the critical path of the legal question in D8.

*Reversing:* Not a reversal so much as a completion. The `fund()` method on
`Milestone` is the single seam a webhook will call.

---

## D13 · Gig orders run on the contract system

**An order creates a `Contract` with one funded milestone and drives it**,
rather than growing its own escrow, message thread, and review system.

*Why:* "One account, one wallet, one reputation" only means something if it is
literally true in the data. A review from a purchased gig and one from a won
proposal are the same row in the same table, so reputation cannot drift between
the two tracks. It also means every protection built in Phase 1 — the audit
trail, the release rules, double-blind reviews — applies to gigs on day one
without being rewritten.

*Reversing:* Expensive. This is the structural bet that keeps the two tracks
from becoming two products.

---

## D14 · Generated cover art instead of stock photography

**Every listing renders deterministic vector art derived from its id and
category.** A seller's uploaded cover replaces it automatically.

*Why:* A catalogue is mostly pictures, and every listing needs one the moment it
is published — before any seller has uploaded anything. Generated art means an
empty marketplace still looks like a real product, with no licensing question,
no network requests, no layout shift, and no stock photo of a smiling stranger
who has nothing to do with the work. It also follows the light/dark theme,
which photography cannot.

The hero uses an animated gradient field rather than background video for the
same reasons: nothing to download, no autoplay policy to fight, and
reduced-motion respected for free. Real footage is a drop-in — see
`web/public/README.md`.

*What this does not replace:* real photography of real work, once there is any.
The generated layer is the floor, not the ceiling.

---

## D15 · Password composition rules, against the usual advice

**Twelve characters, all four character classes, and no runs or keyboard
walks** — taken at the CEO's explicit direction, overriding the report's
length-over-composition position.

*Why the original advice existed:* composition rules push people toward
predictable shapes. Demand an uppercase, a digit and a symbol and a large share
of users produce `Password1!`.

*Why it is still defensible as built:* the composition rule is the weakest of
four checks, not the only one. It sits on top of a 12-character floor, the
breach corpus, and a pattern rule that rejects exactly the shapes composition
requirements produce — `aaaa`, `1234`, `qwer`. Composition alone would have
closed the "twelve lowercase letters" hole while opening the `Xxxxxxxx1!` one;
stacked, it closes both.

*Reversal:* drop `ComplexityValidator` from `AUTH_PASSWORD_VALIDATORS` and
raise `PASSWORD_MIN_LENGTH`. No migration, no effect on existing passwords.

---

## D16 · New-device verification, and a hold rather than a block

**An unrecognised device must pass a second proof — the authenticator if one is
enrolled, otherwise a code emailed to the account. Either way the device then
holds off on money-adjacent actions for two hours.**

*Why not block the session outright:* signing in from a new laptop is
overwhelmingly ordinary, and blocking it is hostile to the majority to catch
the minority. Full read access with a hold on spending costs a real user
nothing they notice and costs a thief the only thing they came for.

*Why the two proofs are mutually exclusive and server-chosen:* an enrolled
account must never be admissible by an email code, or its second factor has
been quietly downgraded to whatever the inbox is worth. The client never picks
— letting it pick is letting an attacker pick.

*Known cost:* the hold stacks with the emailed code rather than replacing it,
at the CEO's direction. A user who has just proved inbox control still waits
two hours before bidding. Setting `DEVICE_COOLOFF_SECONDS=0` for OTP-verified
devices is a one-line change if that friction proves too high. (Superseded in
part by D52: the hold is now 30 minutes, and never applies to the device an
account is created on.)

---

## D17 · Two gates for money, not one

**`CanTransact` guards participation; `CanMoveMoney` adds an enrolled second
factor and guards only payment.**

*Why not one gate:* requiring an authenticator before a freelancer can submit
their first proposal costs sign-ups to protect money that is not yet in play.
Requiring nothing until money moves protects nobody. Splitting them means the
wall arrives at the moment it is obviously worth it — checkout — and enrolment
is offered inline there rather than as a link to Settings, because a user
stopped mid-payment who is sent elsewhere mostly does not come back.

---

## D18 · PostgreSQL full-text search before a search engine

**Search is Postgres FTS with weighted vectors, GIN indexes, and a trigram
fallback for misspellings.**

*Why:* a dedicated engine introduces a second datastore to keep in sync, and
every stale-index bug that follows is a listing a seller swears they published.
With Postgres the index updates in the same transaction as the row. It stops
being the right answer somewhere north of a few million listings — and the
catalogue will say so long before that.

*One non-obvious rule that came out of building it:* the fuzzy matcher is
switched off whenever the query contains operators. ORing similarity back in
resurrects exactly the rows a `-exclusion` just removed, and an exclusion that
does not exclude is worse than no exclusion at all.

---

## D19 · Promoted placement is additive, and never beats an explicit sort

**Promotion is a bounded term in the ranking formula, always labelled in the
API payload, and it is discarded entirely when the user picks a sort order.
Briefs cannot be promoted at all.**

*Why:* a search whose top result is simply whoever paid most is a search people
stop trusting, and a marketplace nobody trusts has nothing left to sell. A bad
listing with a budget still loses to a good one without.

*Why briefs are excluded:* a client paying to rank above other clients would be
auctioning the freelancer's attention. That is the wrong side of this
marketplace to sell, and selling it would make every freelancer's feed an
advertisement.

*Also not an auction.* A second-price auction is the right answer at scale, but
it needs enough bidders per query for the clearing price to mean anything; on a
thin marketplace it just charges the only bidder their maximum. Flat daily rate
until there is competition to clear.

---

## D20 · Reputation weights are stated, not fitted

**The Job Success Score weights and the seller-level thresholds are named
constants with their reasoning attached, not numbers derived from data.**

*Why they cannot be fitted yet:* fitting needs a body of completed, paid
contracts with known outcomes, and Phase 3 is deferred. Pretending otherwise
would be worse than admitting it.

*What was done instead:* every weight is in one module
(`accounts/reputation.py`), and `discovery.SearchLog` records search terms and
result counts so demand data accumulates from now rather than from whenever
somebody remembers to start collecting it. Zero-result queries in particular
are a free list of things buyers want and nobody is selling.

*One threshold is not up for tuning:* seller levels require tenure alongside
volume. Any ladder counting only completions can be climbed in a weekend by a
ring of accounts trading tiny contracts. Time is the one input that cannot be
bought.

---

## D21 · Review integrity never acts on a single signal

**Six weighted fraud signals accumulate; a review is flagged for a human above
one threshold and excluded from scoring above a second. Nothing is ever
deleted.**

*Why weights rather than rules:* two freelancers who genuinely hire each other,
a shared campus network, and a fast reviewer are each perfectly innocent alone.
It is their co-occurrence that is not. Every individual weight sits below the
flag threshold, and there is a test asserting exactly that.

*Why suppressed rather than removed:* the first question a support agent asks
about a suppressed review is "why", and the second is "show me". Deleting the
row destroys the evidence the decision was based on.

*Why "unchecked" is a distinct state from "clean":* otherwise a backlog in the
checker silently reads as a clean bill of health.

---

## D22 · Entitlements are read from one resolver, never cached on the user

**`professional.entitlements.for_user` is the only thing that answers "what may
this account do", and a missing or expired subscription resolves to Free rather
than to unlimited.**

*Why one reader:* the failure every subscription system eventually has is a
limit enforced in three places that disagree — a Pro user who is Pro on the
proposals page and Free at the endpoint that counts them.

*Why not denormalised onto `User`:* a plan copied onto the account makes every
expiry a second write that can fail independently, and a stale "unlimited" is a
hole nobody notices until it is audited.

*Why absence means Free:* the failure mode of a bug here should be somebody
getting something they were not charged for, not everybody getting everything.

*Reversal:* if entitlement reads ever show up in profiling, cache them by user
id with an explicit invalidation on subscribe and expiry. Do not move them onto
the user row.

---

## D23 · A paywall answers with the fix, not just a refusal

**A blocked action returns 402 with `code: "upgrade_required"` — deliberately
distinct from a plain permission denial — and the client renders it as an offer
inline rather than a red banner.**

*Why a distinct code:* a paywall the user cannot act on from where they hit it
is a paywall most of them simply leave. Conflating "your plan does not include
this" with "you are not allowed" costs the sale and misinforms the user.

*Why not just redirect to pricing:* it discards what they were trying to do.

*Reversal:* none expected; the code is additive and old clients that ignore it
still show the message.

---

## D24 · Seats are counted against the agency owner's plan

**An agency's seat limit comes from the owner's entitlements, not the
inviter's.**

*Why:* the agency is the owner's, and it is the owner who paid. Checking the
inviter would let an admin on a free plan grow a team past what was bought —
the classic privilege-boundary bug where the *actor's* rights are checked
instead of the *resource's*.

*Related:* self-removal is exempt from the admin check, because leaving and
declining an invitation are the same operation and neither should require
permission from the team you are trying to leave.

---

## D25 · The test suite runs the shipped settings, and names its exceptions

**CI runs with `DEBUG=False`. Where a production setting is incompatible with a
plain-http test client, `conftest.py` turns off that one setting explicitly,
with the reason written down — the suite is never run under `DEBUG=True` to
make it pass.**

*Why this exists:* it was written after the whole suite passed locally and
failed in CI with 144 failures and 57 errors. `SECURE_SSL_REDIRECT` turns on
whenever `DEBUG` is off, so every request in CI became a 301 to
`https://testserver/` — a green local run proving nothing about the
configuration that ships.

*Why not set `DEBUG=True` in CI:* that is the fix that hides the next one.
`REQUIRE_FILE_SCANNER`, `COOKIE_SECURE`, and `CELERY_TASK_ALWAYS_EAGER` are all
keyed off `DEBUG` too, and running the suite in development mode means none of
their production behaviour is ever exercised.

*The rule:* verify against CI's environment before claiming a suite is green,
and when a setting has to be relaxed for the harness, relax exactly that
setting and say why in the fixture.

---

## D26 · The marketing pages never claim traction we do not have

**No testimonials, no client logos, no listing or contract counts, until there
are real ones. The slots those occupy on a competitor's page are filled with
capabilities of the software instead.**

*Why:* an earlier revision of the landing page carried four invented customer
quotes — names, roles, five-star ratings — for a platform with no users and no
live payment rails. Fabricated social proof is the one category of marketing
copy that cannot be corrected later: by the time anyone checks, it has already
done its work on someone deciding whether to trust the escrow with their money.

*What replaced it:* "escrow on every contract", "sealed two-way reviews",
"campus scoping enforced in the database". Every line is a behaviour with code
behind it, so the claim and the product cannot drift apart.

*When this reverses:* the moment there are real customers willing to be quoted
and real numbers worth printing. The slots are designed and waiting.

---

## D27 · Photography on marketing, generated art in the product

**The landing page is carried by real photographs. Listings inside the product
render deterministic vector art instead.**

*Why photographs outside:* two earlier attempts at this page used only vector
art and typography, on the reasoning that stock photography of a stranger at a
laptop says nothing about the product. That reasoning is right about the
photograph and wrong about the page — every marketplace at this size is carried
by imagery, and a catalogue that shows no work does not read as a catalogue.

*Why not photographs inside:* a listing's cover has to exist before the seller
has uploaded one, and it has to be different for every listing. A stock image
repeated across the catalogue reads as a placeholder, which is exactly what it
is. Art derived from the listing's own id never repeats and never lies about
what it is.

*Licence:* Unsplash — free for commercial use, no attribution required. Files
live in `web/public/img` and are served from our own origin, so the CSP needs no
third-party exception.

---

## D28 · Two-factor setup is idempotent while enrolment is pending

**`POST /auth/2fa/setup/` returns the same secret on every call until the
authenticator confirms it. It no longer mints a fresh one per request.**

*The failure this closes:* a user would scan a QR, type the six-digit code
their app showed, and be told it was wrong. The client starts enrolment from a
`useEffect`, React runs effects twice under StrictMode in development, and the
second call to setup silently replaced the secret behind the QR the first call
had already rendered — so the code was correct for a secret the server had
already discarded. It was not only a development artefact: a remount, a
back-navigation, or a second click on "set up" reproduced it in production too.
Found because a real account hit it and every scan failed.

*Why rotating on every call felt safe and was not:* the reasoning had been
"never let a secret sit still, in case it leaked before enrolment." But an
unconfirmed secret is reachable only by the session that just requested it —
there is nothing yet to leak it *to*. The actual risk boundary is
`two_factor_confirm`, which is where the secret goes from provisional to real;
rotating before that point protects nothing and breaks the one flow it exists
to support.

*Verified live, not only by the added test* (`test_setup_reuses_the_pending_
secret_across_calls`): signed up an account through the real HTTP API, called
setup twice, confirmed with the code from the first response's secret, and the
account enrolled. Repeated once more end-to-end after the fix to prove the
exact scanned-QR-then-typed-code path a user takes now succeeds.

---

## D29 · Local email is a file, not a console line

**`EMAIL_BACKEND` defaults to Django's file-based backend, writing each message
into `api/.mail/` as an openable `.log` file, rather than to the console.**

*Why the console backend was worse than it looked:* it is the Django default
and reads as the obvious dev choice, but it only helps if you are watching the
exact terminal the request landed in. A signup that reaches the server through
a background process — or simply a second terminal — sends the confirmation
link somewhere nobody is looking. Reported as "the email is not sending", which
was true in effect if not in mechanism: nothing was broken, but nothing
reachable had received it either.

*Why not fix it by promising it "sends":* it does not, and claiming otherwise
until a real SMTP account is configured would be the more dishonest failure.
The file backend is the answer that tells the truth about what happens locally
while still making the link something a person can actually click.

*Not touched:* SMS. Phone verification still logs its OTP
(`accounts.views: phone_otp user=... code=...`) rather than sending one,
because no equivalent "write it somewhere openable" backend exists for SMS the
way `filebased.EmailBackend` does for mail — wiring a real provider is Twilio-
or-equivalent work, not a local-dev convenience fix.

---

## D30 · Sort by an aggregate, never by a raw to-many field

**`?sort=price` on gig search orders by `Min("packages__price")` — an
annotated aggregate — never by the raw related field `packages__price`.**

*What ordering by the raw field actually did:* a gig carries several
packages, so `.order_by("packages__price")` joins the packages table again for
ordering purposes. Postgres requires an ORDER BY column used with SELECT
DISTINCT to appear in the select list, so Django pulls that package price into
the row tuple — and a gig with three packages then produces three
distinguishable rows sharing one id, which `.distinct()` has nothing left to
collapse.

*Why it was worse than a visible duplicate:* DRF's paginator sizes the page by
calling `.count()`, and Django's count optimisation for this exact query shape
reports the *true* distinct-gig count — 2, say — while the row fetch for
`results` still runs the undeduplicated query underneath it. The paginator
then slices `[0:2]` against the 4-row set the count didn't describe, not a
2-row one. Where in sort order the duplicate rows land decides what happens:
sometimes a duplicate id, sometimes a legitimate gig silently missing from a
results page whose own `count` field said it should be there. Confirmed live,
both ways, before writing the fix.

*Why `Min()` and not restructuring the join:* it is an aggregate, so Django
groups by every other selected column instead of adding the related field to
the row. One row per gig comes back regardless of how many packages it has,
and the count Django reports matches the rows it actually returns.

*The general rule this sets:* never order a queryset by a field reached
through a to-many relation. If the sort needs a value from the many side,
aggregate it into an annotation first — `Min`, `Max`, `Count`, whichever the
sort means — and order by that.

*Caught by:* a real user's browser reporting a duplicate React key, not by the
test suite — there was no test for `sort=price` at all before this. The
regression test added deliberately prices the multi-package gig at the cheap
end, because a naive version priced in the middle and passed against the
unfixed code by accident: the truncation happened to land after the
duplicate rather than before it, so nothing looked wrong. Asserting the exact
returned id set, not just "no duplicate in what came back," is what makes the
test catch the missing-result half of the bug too.

---

## D31 · Two phases added: hire-after-trial, then proof-of-work challenges

**The roadmap grows from 12 phases (0–11) to 14 (0–13). Phase 12 is a paid
trial task that converts into a full contract's first milestone. Phase 13 is
timed, scored skill challenges that badge onto a profile. Trial is sequenced
first.**

*What each one is:* a trial lets a client buy a small, cheap deliverable —
say Rs 5,000 against a Rs 150,000 project — before committing to the whole
engagement, with the trial fee credited toward the first milestone if they
proceed. Challenges are periodic, timed briefs — "build this dashboard from
this Figma file in 24 hours" — graded by a mix of automated checks (tests,
Lighthouse) and human review, with the result ("Top 8%, React Dashboard
Challenge") attached to the freelancer's profile as evidence rather than
claim.

*Why trial is Phase 12 and challenges is Phase 13, not the order they were
proposed in:* trial needs nothing this codebase does not already have. It is
a small order riding the same `Contract` spine that already unifies gigs and
projects (decision, Phase 2) — no new infrastructure category, just a new
shape of order and a conversion path. Challenges need a new infrastructure
category entirely: something has to execute freelancer-submitted code to run
Lighthouse and unit tests against it, which is a sandboxing problem on the
order of the escrow work, not a UI feature. Building the cheaper, lower-risk
one first is the same reasoning that put Phase 2 before Phase 3.

*What trial cannot do until Phase 3 exists:* "the trial fee automatically
becomes part of the first milestone" is a ledger operation — crediting one
payment against another — and there is no ledger yet (D-gap in Phase 3).
The trial-then-convert *workflow* — order, approve, invite to a full
contract — can ship on the current contract state machine. Automatically
applying the fee cannot honestly ship before Phase 3 does; until then it is
a manual adjustment, and the product should say so rather than imply an
automation that is not real, the same call made for Phase 8's subscriptions
elsewhere in this log.

*What challenges depend on that does not exist yet:* the reputation
weighting to make a badge mean something is more credible once Phase 6's
Job Success Score has real transaction history behind it, which itself
waits on Phase 3. A challenge system launched before that has nothing to
calibrate "top 8%" against except the challenge pool itself — workable, but
worth knowing the number is provisional in exactly the way search ranking's
weights already are (D20).

---

## D32 · Production deployment infrastructure (`deploy/`)

**A complete, standalone production path exists now: gunicorn + whitenoise
instead of the dev servers, a Caddy reverse proxy with automatic HTTPS, a
real ClamAV sidecar, off-server backups to Backblaze B2, and a one-command
deploy script. Target is a single Oracle Cloud "Always Free" ARM instance,
but nothing here is Oracle-specific.**

*Why a standalone compose file instead of an override merged with the dev
one:* the dev `docker-compose.yml`'s env defaults
(`SECRET_KEY:-dev-only-change-me`) exist specifically to make local setup
painless, and Compose's list-merge semantics for keys like `ports:` make it
easy to accidentally keep a host port published that production means to
remove. `deploy/docker-compose.prod.yml` duplicates some structure, but
nothing in it can silently inherit a dev default — every secret is
`${VAR:?message}`, which fails the deploy loudly instead of booting with a
placeholder.

*Why two domains, not one path-split:* the app already treats the API as a
separate CORS origin — `web/proxy.ts` reads `NEXT_PUBLIC_API_URL` as a full
origin, and the CSP's `connect-src` names it explicitly. `api.<domain>` as
its own Caddy site block matches that design instead of fighting it with a
path rewrite that would also require touching CORS, CSRF, and CSP.

*Caught by actually booting the stack, not by reading the YAML* — three bugs
that config validation and `docker compose config` both missed entirely,
because none of them are syntax errors:

1. **Volume collision.** The prod compose file was first named `skilrize`,
   same as the dev one. Compose project names prefix volume names, so both
   stacks pointed at the same Postgres volume. A prod container started
   against a database already initialized with the *dev* stack's
   credentials failed to authenticate with its own. Renamed the prod project
   to `skilrize-prod`.
2. **Startup race.** `worker` depended only on `db`/`redis`/`clamav` being
   healthy, not on `api` having finished `migrate`. On a genuinely fresh
   database, Celery Beat queried `django_celery_beat`'s tables before `api`
   had created them and crashed. Fixed by giving `api` a real healthcheck
   (gunicorn only starts serving after `migrate` and `collectstatic`
   succeed in its command chain) and making `worker` and `caddy` both wait
   on `api: condition: service_healthy` instead of just "container started."
3. **Self-inflicted version of D25.** That healthcheck, once added, failed
   for the same underlying reason 144 CI tests failed in D25:
   `SECURE_SSL_REDIRECT` is correctly on whenever `DEBUG` is off, and the
   healthcheck talks to gunicorn directly over plain HTTP instead of through
   Caddy, so Django 301'd it to `https://` and there was nothing on the
   other end to follow it to. Caddy normally prevents this by setting
   `X-Forwarded-Proto: https` on every request it proxies — the healthcheck
   has to fake that header itself, plus a `Host` header matching
   `ALLOWED_HOSTS`, since it never passes through the proxy that would
   normally supply both.

*The general lesson this sets, again:* D25 already established "verify
against CI's exact environment, not local" for the test suite. This extends
the same rule to infrastructure — `docker compose config` proves the YAML
parses, not that the stack boots. All three bugs above only surfaced once
the full stack was actually brought up fresh, end to end, with `DEBUG=False`
and no dev fallbacks available to paper over a missing value.

---

## D33 · Phase 13 built as "submit a URL," not "submit code"

**The client's brief for proof-of-work challenges described grading with
"automated tests, Lighthouse, unit tests, predefined test cases." What
shipped: a freelancer submits a live deployed URL, and automated grading runs
Lighthouse against that public page. Running submitted *source code*
server-side — the "unit tests" and "predefined test cases" half of the
brief — was scoped out.**

*Why:* executing arbitrary freelancer-submitted code on the platform's own
infrastructure is a sandboxing problem — gVisor, Firecracker, or an isolated
Docker-in-Docker runner, with all the resource-limit and network-isolation
work that implies. That is a project on the order of Phase 3's payment rails,
not a Celery task bolted onto a feature PR. Lighthouse against a submitted
URL gets most of the "prove you can actually build it" value the brief was
after, with none of that risk: it is a page fetch, not a code execution.

*What is real, not a stub:* the full challenge lifecycle. Joining starts an
individual deadline capped at the challenge's own close (not a shared clock
everyone races). Submission is SSRF-guarded — `challenges/url_safety.py`
resolves the hostname and rejects private/loopback/link-local addresses
(cloud metadata endpoints included), checked once at submission for fast
feedback and again immediately before any server-side fetch, because DNS
resolved publicly at submission time is not a guarantee it still is by
grading time. Scoring is weighted between the automated and human sides,
ranking is percentile-based across a challenge's graded field, and badges
render on the profile that earned them. All of it is covered by 24 tests
that exercise the API, not just the model layer.

*What is a stub, and says so:* automated Lighthouse grading itself.
`LIGHTHOUSE_ENABLED` defaults to `False` — the worker image has no Node or
headless Chromium — so `grading.py`'s adapter raises `GradingUnavailable`
rather than fabricate a score, and a challenge runs on human review alone
until that changes. Same shape as the `CLAMAV_HOST` adapter (Phase 0, predates this log): the
surrounding contract is real, the engine behind it is a configuration change
away, not a rewrite.

*Caught while testing it, not designed in from the start:* two bugs the test
suite alone would not have found because they only show up when a *second*
model's state depends on the *first* one's timing. `ChallengeCreateSerializer`
initially had no `id`/`slug` in its response fields — a caller could create a
challenge and have no way to navigate to what it just made, since nothing
outside the serializer's own field list is visible in the API response
regardless of what the database actually stored. Caught by a test asserting
on `response.data["id"]`, not by inspection. Separately, the participant
detail page's "N joined" count went stale after joining, because the join
action updated the participation but never re-fetched the challenge —
harmless, but exactly the kind of small trust-eroding staleness that is
cheap to fix in the same session it's found and easy to leave for a bug
report otherwise.

---

## D34 · Phase 12 built exactly as scoped in D31

**"Hire after trial" shipped as D31 already said it would: a small order
riding the existing `Contract`/`Milestone` spine, with the trial-fee credit
left manual because there is no ledger to automate it against. Nothing in
the build changed that plan — this entry is the implementation record, and
the one real bug it surfaced along the way.**

*The shape:* a client proposes a trial on a specific proposal — a brief, a
price, a number of days. The freelancer accepts or declines. Accepting opens
a one-milestone `Contract` for just the trial amount, and from there it is
funded, delivered, and released through `ContractViewSet` exactly as any
other contract is — no new payment-adjacent endpoints exist anywhere in this
feature. Once that trial contract is `COMPLETED`, the client can "continue
with this freelancer," which awards the full project using the same
`Contract.create_from_proposal` the normal award path uses.

*The one modelling decision worth naming:* the trial's own contract does
**not** set `Contract.proposal` — it stays `null`. `proposal` is a
`OneToOneField`, and the *real* contract (the one `convert()` creates) is
the one meant to occupy that slot once the trial succeeds. A trial contract
that claimed it first would make its own originating proposal permanently
un-awardable, which is close to the same failure class as the zombie-contract
bug below — a `OneToOneField` treated as available when something is already
quietly sitting in it.

*The bug this build found, unrelated to trials specifically:* refactoring
`award`'s contract-creation logic into `Contract.create_from_proposal` (so a
trial conversion and a normal award share one implementation instead of two
that can drift) surfaced that the original code created the `Contract` row
*before* validating milestone amounts. A rejected 400 for a bad milestone
split still left a real `Contract` behind, and because of the same
`OneToOneField`, that row permanently blocked every later award attempt on
the proposal — correct amounts or not. Fixed by validating first. This
predates Phase 12 and had nothing to do with trials; it was found only
because building this feature meant reading that code closely enough to
reuse it correctly.

*What "convert" still cannot do — restated from D31, because it is easy to
forget once the feature exists:* the trial fee is not credited toward the
new contract's first milestone. That is a ledger operation Phase 3 has not
shipped. The amount stays visible on the `Trial` row precisely so nobody —
client, freelancer, or a future engineer reading this code — mistakes the
absence of automation for the platform having simply forgotten a payment.

---

## D35 · Admin console scoped to four roles, not seven

**Phase 9 had no prior scoping decision — the roadmap carried only the
placeholder "admin console," and `User.AdminRole` has defined seven values
since Phase 0 with nothing anywhere reading them. Asked which surface to
build first, the answer was "all of it," which here means four of the seven
roles: Verification Officer, Support Agent, Finance Admin, Super Admin.
Moderator, Dispute Officer, and University Moderator are not wired to
anything yet — their surfaces are community moderation and dispute
resolution, and dispute resolution specifically has nothing to resolve (see
below), so building consoles for them now would be UI ahead of the feature
it operates.**

*Why this is the first thing in the codebase to actually read `admin_role`:*
every existing admin surface is generic Django admin, which checks
`is_staff`/`is_superuser`, not the seven-value role field. `require_admin_role`
(`accounts/auth.py`) is a permission-class factory — Super Admin bypasses
every check, everyone else needs the exact role an endpoint names — and nothing
before this phase needed that distinction because nothing before this phase
had more than one kind of admin action to gate.

*The `Contract.create_from_proposal` refactor from D34 paid for itself again
here:* `AdminContractViewSet`'s force-fund action reuses the same
`ContractType`/`Milestone` machinery, and building it surfaced a real gap the
party-scoped `fund_milestone` already guards against and mine initially did
not — an admin could force-fund a milestone on a contract the freelancer had
not even accepted yet, because I had copied the "milestone must be PENDING"
check but not the "contract must be ACTIVE" one sitting right next to it in
the original. Fixed before it shipped, caught by writing the test for the
unhappy path rather than only the happy one — `test_cannot_force_fund_before_the_contract_is_active`.

*Two things this deliberately does not do, both already true before this
phase and both worth being explicit about rather than quietly working
around:*

1. **Resolve a contract dispute.** `Contract.Status.DISPUTED` has existed
   since Phase 1's `ContractType`/`Status` enum with no code path that ever
   sets it — there is no "raise a dispute" endpoint anywhere in the product.
   A "resolve" screen in the admin console would be a UI control wired to a
   state nothing can reach. `AdminContractViewSet`'s docstring says so
   directly rather than silently omitting the action.
2. **Impersonate a user.** `AuditLog.Action.IMPERSONATE` has been a defined
   choice since `core.models` was first written (Phase 0) with nothing that
   ever writes it. Signing in *as* another account is a materially different
   risk class than anything else in this console — session-hijacking-adjacent
   by design — and deserves a security review of its own, not a feature
   bolted onto a Support Agent's suspend button because the enum entry was
   sitting there unused.

*A test-infrastructure trap worth naming for whoever writes the next admin
test:* `User.requires_two_factor` is mandatory for every account with any
`admin_role` set, without exception (documented, tested, pre-existing). That
means a naive test fixture — `User.objects.create_user(email, password,
admin_role=...)` followed by the ordinary one-step login helper every other
test in this codebase uses — logs in *nothing*: the account correctly
demands a second factor it was never enrolled in, and every test built on
top of that fixture fails several steps downstream in a way that looks like
a permissions bug rather than a fixture gap. `accounts.tests._make_admin`
enrols a confirmed `TwoFactorDevice` at creation and
`accounts.tests._login_admin` completes the real two-step challenge, so the
test still exercises actual enforcement rather than bypassing it — but the
failure mode this replaces (cascading "Forbidden" errors with no obvious
cause) cost real time to trace and is worth remembering next time a fixture
needs an admin account.

---

## D36 · Phase 10 scoped to meetings + read-only activity feeds, not "integrations" in general

**The roadmap carried only "Integrations, hardening" for Phase 10–11, with no
prior scoping decision — the same blank state Phase 9 was in before D35.
Asked what it should cover, the answer split it in two: Zoom/Google Meet
meeting scheduling, and GitHub/Figma/Notion read-only activity feeds — "high
perceived value, safely deferrable, doesn't block anything else." Hardening
(Phase 11) stays unscoped; this decision covers Phase 10 only.**

*Same gating pattern as Lighthouse (D33), applied to five providers instead
of one.* No Zoom/Google/GitHub/Figma/Notion OAuth app has real credentials
issued anywhere near this environment, so `ZOOM_ENABLED` and its four
siblings all default to `False` in `config/settings.py`. What is real
regardless: `integrations/providers/*.py` are genuine OAuth flows and API
calls (Zoom Meetings v2, Google Calendar's `conferenceData`, GitHub's repo
events timeline, Figma's file version history, Notion's page object) — not
five stubs waiting to be written later. Flipping a flag and setting a client
id/secret is the entire remaining step, exactly like Lighthouse and
`api/Dockerfile`.

*OAuth needed a shape decision this codebase had never made before:* nothing
here uses Django sessions for the API — auth is JWT in HttpOnly cookies
(`accounts/`). A provider's OAuth callback can't rely on a session either, so
`authorize` hands the caller a signed, 10-minute `state` token (their user id
+ provider, via `django.core.signing`) instead of storing anything
server-side, and the frontend's own `/integrations/callback/<provider>` page
POSTs `code` + `state` back to an *authenticated* `connect` endpoint while
the user is still signed in normally. `connect` verifies the signature and
that the token was minted for the calling user before ever touching the
provider — a `state` stolen off one user's redirect cannot be replayed by
another; covered by
`test_connect_rejects_a_state_issued_for_a_different_user`.

*Meetings and activity sources attach to `contracts.Contract` by string FK
from a new app, not the other way round* — the same shape Phase 13's
`Participation` used to attach to `marketplace.Skill`, chosen there for the
same reason: a feature app should reach into an existing spine, not have the
spine reach out to every feature that might attach to it later.

*Notion's activity signal is honestly coarser than GitHub's or Figma's,
and says so in its own docstring rather than pretending otherwise.* The
public Notion API has no per-edit timeline outside the Enterprise-only Audit
Log API. `fetch_activity` for Notion returns at most one synthetic
"page last edited at T" event per sync, not a real feed — a real limitation
of the surface it wraps, not a shortcut taken while building it.

*What this deliberately does not do: poll on a schedule.* A "sync now" action
covers the immediate need, and `sweep_activity_sources`
(`integrations/tasks.py`) is a complete, correct periodic task — but it is
not wired to `CELERY_BEAT_SCHEDULE`, because nothing in this codebase is yet.
`core.tasks.sweep_promotions` and `sweep_challenge_deadlines` already carry
the identical, pre-existing gap; this is the same missing piece of
infrastructure surfacing a third time, not a new one.

---

## D37 · Phase 11 (hardening) scoped to four buildable areas, with pen testing, load testing, and compliance review named as not mine to take

**"Hardening" carried no prior scoping decision either — same blank state
D35 and D36 both started from. Asked what it should cover, the answer split
into four areas: security hardening (rate limiting, CSP/security headers, a
pass over auth/2FA edges), ops hardening (error tracking, the unwired Celery
beat schedule), reliability hardening (retry/backoff on external calls, a DB
index audit), and — named directly rather than silently dropped — a fourth
area (penetration testing, load testing, legal/compliance review, external
monitoring) that needs an authorized third party, real traffic infrastructure,
or a lawyer, not an engineering session. That fourth area moved to "Not mine
to take" below rather than being quietly skipped.**

*The most consequential finding wasn't a gap — it was a bug already in
production shape.* Auditing rate limiting before extending it (rather than
just extending it) surfaced that `signup`, `login`, `otp`, and
`password_reset`'s named throttle rates — 5/hour, 10/min, 5/min, 5/hour, each
looking exactly like real protection in `settings.py` — had been silent
no-ops since they were written. `accounts/views.py`'s `_throttled(scope)`
helper set `view.throttle_scope = scope` on the function *before*
`@api_view` wrapped it into a class, and DRF's `api_view()` copies
`throttle_classes`/`permission_classes`/a fixed list of other attributes
from that function onto the class it builds — never `throttle_scope`.
`ScopedRateThrottle.allow_request` returns `True` unconditionally whenever
`getattr(view, 'throttle_scope', None)` is falsy, which it always was on
these four endpoints; only the blanket 60/min-anon and 240/min-user rates
the whole API carries were ever actually enforced on them. Fixed in
`core/throttling.py`'s `scoped_throttle()`, which sets the scope on the
*dispatched view instance* inside `allow_request` itself rather than trying
to get it onto the class beforehand — works identically for a function view
and a class-based one, and is now the one throttling helper the whole
codebase shares. `test_signup_is_throttled_at_the_named_scope_rate`
(`accounts/tests.py`) proves the fix at the real production rate, not a
relaxed one.

*Fixing it broke nine other tests, and the fix for that had its own trap.*
Making the rate real meant tests that call `sign_in()` several times in one
run — award a contract as the client, deliver as the freelancer, review as
the client again, all from one test process's `127.0.0.1` — started hitting
`login`'s 10/minute cap for real. The fix (`conftest.py`'s
`_generous_scoped_throttles`) widens the rate for the suite without touching
what ships, matching `_tasks_run_inline`/`_no_device_cooloff`'s existing
pattern — except a first attempt at it used `settings.REST_FRAMEWORK = {...
}` (the `settings` fixture's normal reassignment idiom) and silently did
nothing: `SimpleRateThrottle.THROTTLE_RATES` is bound, once, at import time,
to the *same dict object* `settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
pointed to then. Reassigning `settings.REST_FRAMEWORK` to a new dict breaks
that aliasing invisibly — the throttle class keeps reading the old dict
forever, while `settings.REST_FRAMEWORK` itself looks correctly overridden
to anything that reads it directly. The working fix mutates
`SimpleRateThrottle.THROTTLE_RATES` in place and restores the exact values
on teardown; `core/throttling.py`'s module docstring and the fixture's own
say why at length, so the next person extending a scope does not lose a
morning to the same discovery.

*Two new scopes, applied only to genuinely new attack surface.* Marketplace
proposal spam is already defended by the existing per-account quota
(Section 10.2, D6); contract money actions are already gated by
`CanTransact` and mandatory 2FA. Neither needed a throttle bolted on for its
own sake. `integrations/` (D36) had no domain-level defence at all and
triggers real third-party API calls, so `integration_connect` (10/hour) and
`meeting_schedule`/`activity_sync` (20–30/hour) were added there —
`meeting_schedule` and `activity_sync` are `writes_only` (`core/
throttling.py`'s `scoped_throttle(..., writes_only=True)`), so browsing a
contract's own meeting list is not capped at the same rate as actually
creating one.

*Six periodic tasks, wired for the first time.* `sweep_promotions`,
`sweep_challenge_deadlines`, and `sweep_activity_sources` (D36) each said in
their own docstring that nothing called them on a schedule;
`reindex_search`, `refresh_reputation`, and `assess_review_integrity` carried
the identical gap without saying so — same missing piece of infrastructure,
found by checking rather than trusting the comments. `core/migrations/
0004_seed_beat_schedule.py` is the first place this codebase has ever
created `PeriodicTask`/`CrontabSchedule` rows — `CELERY_BEAT_SCHEDULER` was
already set to `django_celery_beat`'s `DatabaseScheduler`, just never fed
anything. Cadence is chosen per task (5 minutes for promotions that are
literally paid for by the minute, 30 minutes for activity sources whose
providers have their own rate limits to respect), not one blanket interval.

*HSTS was the one header `SecurityHeadersMiddleware` didn't set.* Added
under the same `if not DEBUG` block as `SECURE_SSL_REDIRECT` — a year,
every subdomain, eligible for preload. `SecurityMiddleware` only emits the
header on a request it believes is actually secure, so this is inert for
the plain-http CI client regardless of `DEBUG`; nothing in `conftest.py`
needed to change alongside it, unlike `SECURE_SSL_REDIRECT` itself.

*Error tracking is real, and honestly half of what "error tracking" usually
means.* `sentry-sdk` is wired into `config/settings.py`, gated behind
`SENTRY_DSN` exactly like `LIGHTHOUSE_ENABLED`/`ZOOM_ENABLED` before it —
`sentry_sdk.init()` with no DSN is itself the inert state, proved both ways
by a subprocess test (`core/tests.py`) since the init runs once, at import
time, and cannot be toggled by a `settings` fixture on an already-imported
process. What is deliberately **not** built: the browser-side half.
`@sentry/nextjs` needs source-map upload credentials and build-time
wiring this session did not have a safe way to add without risking the
production build; frontend error tracking stays a named gap rather than a
half-wired one — see Engineering debt below.

*Retry/backoff lives at the HTTP layer, not the task layer, for
`sweep_activity_sources`.* Every `integrations/providers/*.py` call now
goes through `integrations/providers/base.py`'s shared `session` — a
`requests.Session` with a mounted `Retry` (3 attempts, exponential backoff,
retries 429/5xx) — proved against a real flaky local HTTP server in
`integrations/tests.py`, not just by inspecting the `Retry` object's
config. `sweep_activity_sources` itself deliberately did *not* get the
`@shared_task(bind=True, max_retries=N)` treatment `scan_file`/
`deliver_notification`/`grade_challenge_submission` each have: those each
act on one row, so retrying the task is retrying the one thing that failed.
`sweep_activity_sources` acts on every source in one pass — retrying the
*task* over one source's failure would re-sync every source that already
succeeded. The transient-failure problem that actually exists (one flaky
HTTP call) is handled a layer down, where it belongs.

*One missing index, found by checking what a hot-path query actually
filters on, not by guessing.* `Proposal.remaining_quota()` — the check
standing between a freelancer and their plan's proposal cap, run on every
submission — filtered on `(freelancer, status)` with only a
`(project, freelancer)` unique constraint to lean on. `marketplace/
migrations/0003_...` adds the index the query pattern actually needed.

*The admin 2FA enrolment gap (named as debt since D35) is closed, not
patched around.* An admin-role account cannot hold a session without 2FA
already confirmed, and had no way to reach the (authenticated) settings
page that starts enrolment — a genuine dead end needing a database fix.
The close reuses the exact challenge-token shape `login_two_factor`/
`login_device_verify` already established: `login()`'s enrolment-required
branch now mints a signed, 10-minute `{"uid", "enrol": True}` token instead
of returning nothing, and two new `AllowAny` endpoints
(`login_two_factor_enrol_setup`/`_confirm`) redeem it to run the same
device-creation and TOTP-confirmation logic `two_factor_setup`/
`two_factor_confirm` already had — extracted into `_begin_two_factor_
enrolment`/`_finish_two_factor_enrolment` so the authenticated and
challenge-token paths cannot drift apart. `enrol` is checked explicitly so
this challenge can never be redeemed as a real second factor, and a real
2FA challenge is rejected here the same way (covered both directions in
`accounts/tests.py`). Confirming ends the request already signed in — the
password was proven a few requests ago and the authenticator was just
proven too, so asking a third time would be friction with no additional
security.

*Found while wiring the frontend for that fix, not before:* the enrolment-
required response originally kept its pre-existing `403` status while
gaining a `challenge` field. `web/lib/api.ts`'s client throws on any
non-2xx response, so the challenge never reached the login page's own
branching logic — a bug caught only by actually driving the flow in a
browser, not by the type checker or the backend test suite, both of which
were satisfied by a 403 with the right JSON shape. Fixed by matching the
sibling `two_factor_required`/`device_verification_required` responses:
200, an actionable next step, not a terminal error.

---

## D38 · Phase 7 split into a backend half and an app half, and only the backend half is built

**Asked to build Phase 7 ("Mobile — Flutter parity app"), the honest state
of this machine mattered before any scoping question did: no Flutter SDK,
no Dart, no Java, no Android toolchain, and — for iOS specifically — no
macOS, which nothing short of different hardware fixes. Flutter is not in
winget either; every result under that tag is an app *built with* Flutter,
not the SDK itself. Asked how to proceed, the user did not answer before
the next message arrived, so the call was made directly: build the half of
Phase 7 that is unambiguously backend work, fully real, and verifiable the
same way every other phase this session was — with the toolchain question
left open rather than guessed at.**

*"Parity" was never going to fit in one pass regardless of tooling.* The
web app is 35 routes across every phase built so far — auth with mandatory
2FA for some roles, projects and bidding, gigs and orders, contracts and
milestones, student portals, communities and messaging, search, the
professional layer, admin, integrations, trials, challenges. A genuine
parity client is the largest single phase on the roadmap by any honest
estimate, toolchain or not.

*What "the backend half" turned out to mean, concretely:* `Channel.PUSH`
has been a defined notification channel since Phase 0, and
`deliver_notification` (`core/tasks.py`) has logged `pending_provider` and
stopped for exactly as long, with a comment saying so directly — "connected
in the phase that needs them." This is that phase. `PushDevice`
(`core/models.py`) is new; FCM delivery (`core/push.py`) and the two
registration endpoints (`core/views.py`) are new; `_deliver_push` replaces
the stub. None of it needed a mobile client to exist first — a device can
register its token the moment *any* client, web included, wants to ask a
browser or a future app for permission and hand the token over.

*Same off-by-default shape as every adapter this codebase has built —
Lighthouse (D33), the five OAuth providers (D36), Sentry (D37) — extended
to a fifth kind of external call.* `FCM_ENABLED` defaults to `False`
because no Firebase project exists for this environment; `core/push.py`'s
`send()` is a real FCM HTTP v1 call regardless, using `google-auth` for the
service-account OAuth2 exchange rather than hand-rolled JWT signing — the
first genuinely asymmetric-crypto dependency this codebase has taken on,
and the module docstring says why that crossed the line the ClamAV
adapter's raw-socket protocol didn't.

*A registration token is not a secret, and treating it like the OTP secrets
and OAuth tokens elsewhere in this codebase would have been wrong, not just
inconsistent.* `PushDevice.token` is a plain `CharField`, not
`EncryptedTextField` — it identifies a device, sending to it requires
credentials that never enter the database, and it has to be looked up by
value on every registration to dedupe, which `EncryptedTextField`'s own
docstring says it is deliberately unsuited for. Reasoned through in the
model's docstring rather than left for someone later to wonder if it was an
oversight.

*Fan-out is per-device and failure-isolated, and dead tokens are pruned as
they're found, not left to accumulate.* A token identifies a handset, not a
person — one account can hold several, and a stale token from an
uninstalled app should stop being tried without taking any of the others
down with it. `_deliver_push` sends to every active device independently,
prunes on FCM's `UNREGISTERED`/`INVALID_ARGUMENT` verdicts specifically,
and leaves a merely-failed send (a 503, a timeout) untouched — that
distinction is the entire reason `PushTokenInvalid` and `PushFailed` are
separate exceptions rather than one.

*A registration token also outlives a sign-in, which shapes what
"register" means.* If one person signs out of a phone and another signs
in, FCM hands the app back the same token — a phone is the unit of
identity FCM tracks, not an account. Registration is `update_or_create` on
the token, reassigning an existing row to the new account rather than
leaving two, covered directly by
`test_re_registering_a_token_moves_it_to_the_new_account`.

*What was not built at the time this was written:* the Flutter application
itself. That has since changed — see D39.

---

## D39 · The Flutter client, built as a foundation rather than parity

**Superseded by D40** — asked directly why the phase wasn't complete, the
scope line this decision draws was rebuilt out to full parity. The
reasoning below (bearer auth, the three bugs, the verification split, the
web build's memory-only tokens) all still stands; only the "foundation, not
parity" scope claim in its opening paragraph does not.

**Asked to build the phase completely, the toolchain question from D38 was
settled by settling it: Flutter 3.47.0 / Dart 3.13.0 installed (a 1.9GB
download), and the client built, analyzed, tested, and run against the live
API. What "completely" honestly means here is the slice that makes a phone
useful — sign-in with both second-factor paths, verification status, project
search, contracts and milestones, the notification centre, and push
registration — not a route-for-route mirror of a web app that is ~35 routes
deep across twelve phases. That distinction was stated before starting
rather than discovered at the end.**

*Bearer auth, and the gap that made it necessary.* `accounts/auth.py` has
said since Phase 0 that "Web sends cookies; mobile sends `Authorization:
Bearer`", and `CookieJWTAuthentication` genuinely falls back to the header —
but no endpoint ever *gave* a non-browser client a token to send. `login`
and every path through `_authenticated_response` set cookies and nothing
else; `refresh` accepted a body token but returned only cookies. The
documented mobile path was unreachable. Closed by having a client identify
itself with `X-Skilrize-Client: native`, which is safe *for the sign-in
paths specifically* because reaching them costs a correct password, a
correct second factor, or a valid enrolment challenge — none of which
injected script has. `refresh` could not use the same gate: script cannot
read the HttpOnly refresh cookie, but the endpoint falls back to it, so a
header-gated version would have let an XSS turn a session it only
transiently controls into a long-lived exfiltrated token. It is gated on
*source* instead — the rotated pair is returned in the body only when the
old one arrived in the body, i.e. only to something that already held it.
`test_refresh_returns_tokens_only_to_a_caller_that_supplied_one` is that
rule.

*Three real bugs, each found by running rather than reading.* Writing the
Dart was the easy part; every genuine defect came from execution. The
bearer gap above surfaced the moment the live suite ran and login returned
no token. `package:http` decodes a response body with no charset as
**latin-1**, and DRF sends `application/json` with no charset — so every
non-ASCII character in the entire API would have arrived mangled, caught by
a widget test that happened to use the masked `m•••r@example.com` hint and
failed on encoding it. And `X-Skilrize-Surface` had never been in the CORS
allow-list: the app found it by sending its own header, but the web client
sends the surface header only when the surface is *not* global, so no
cross-origin request had ever carried it and the first student switching
into a campus portal would have found it instead.

*Verification is the point, so it is done twice.* Eleven widget/unit tests
cover the client's own logic against mocked HTTP — the three auth branches,
refresh-once-on-401, the refusal to loop when refresh fails, push gating.
Those prove the client is internally correct and prove nothing about
whether Django agrees with it. A second suite (`test/live_api_test.dart`,
tagged `live` and skipped by default since CI has no stack) drives the real
client against a running API: real sign-in, the issued bearer token
accepted back on `/auth/me/`, real JSON parsed into the models, real push
registration round-tripped, real sign-out revoking server-side. Both of the
first two bugs above were caught by exactly one of those halves and would
have been invisible to the other.

*The web build is a verification tool, not a shipping target, and its token
storage says so.* Android and iOS get `flutter_secure_storage`; the browser
gets `MemoryTokenStore`, which does not persist and signs out on reload.
The alternative was `localStorage`, readable by any injected script —
precisely what the Next.js app's HttpOnly cookies exist to prevent. A real
web client should use the cookie path that app already uses. This one
exists so the app can be *run* on a machine with no Android emulator and no
Mac, which is what made the live verification above possible at all.

*What remains unbuilt, and honestly so.* iOS needs macOS — no code change
reaches it. Push registration is wired, gated, and tested, but obtaining
the FCM token needs a Firebase project this environment does not have; one
`TODO` in `push_settings.dart` marks the single call, in the same spirit as
`LIGHTHOUSE_ENABLED` and the five OAuth providers before it. And the money
actions are deliberately absent rather than half-present: funding and
releasing sit behind `CanMoveMoney`, a confirmed second factor, and a
device cool-off, and a partial money flow on a phone is worse than none.

---

## D40 · The Flutter client, rebuilt out to full parity

**Told plainly that a foundation was not what was asked for, the "not a
route-for-route mirror" scope line D39 drew was the wrong line, and every
domain the web app covers got a real screen against the real API: gigs and
orders, contract money actions, messaging, communities, unified search, the
professional layer, challenges, integrations, a role-gated admin console,
student verification, account settings, and the activity feed/showcase.
Around ninety new `SkilrizeApi` methods and roughly twenty new screens
later, the nav itself needed rebuilding to hold it.**

*Five tabs, not four, and everything else one tap deeper.* The old
four-destination bottom bar (Home/Projects/Contracts/Alerts) had no room for
fifteen-plus new destinations, and a bottom bar that tries anyway stops
being navigable. The new shell is Home/Work/Messages/Contracts/More: "Work"
groups search, projects, proposals, gigs, orders, communities, and
challenges (`work_hub_screen.dart`); "More" groups the professional layer,
integrations, settings, student verification, the admin console (rendered
only when `user.adminRole` is non-empty — the server enforces the real gate
regardless, so this is a UI convenience, not a boundary), and the feed
(`more_screen.dart`). This mirrors how the web app itself separates the
everyday work loop from account/business surfaces; it does not invent a new
information architecture.

*Money-moving and plan-entitlement refusals, one banner.* `CanTransact` and
`CanMoveMoney` answer 403 with `profile_incomplete` / `device_cooloff` /
`two_factor_required`; the professional layer's entitlement checks answer
402 with `upgrade_required`. Different HTTP status, different subsystem,
same shape of user-facing failure — "you can't do that yet, and here is the
one thing that unblocks it." `MoneyGateBanner` (already built for gig
ordering and contract funding) got a fourth branch rather than a sibling
widget, so subscribing to a plan, creating an agency, and selling a
retainer all render the same refusal UI gig ordering already had.

*The one screen still carrying a `TODO`, and why it is the honest one.*
Every other domain is real end to end — including the student ID card
upload, which needed a genuine new dependency (`image_picker`) and a new
`ApiClient.uploadFile` multipart path, both added rather than stubbed.
Provider "Connect" in Integrations is the exception: completing an OAuth
redirect needs a web view or an external-browser launch, and wiring that up
against providers with no real credentials in this environment would be
exercising code with no way to prove it works. The `TODO` is scoped to
exactly that hop — everything before it (the provider list, the
`authorize_url` fetch) and after it (disconnect, meetings, activity sync)
is real.

*Verified the same way as before, plus a rebuilt image.* `flutter analyze`
is clean across every new file. The mocked suite (11 tests, unchanged) and
the live suite (4 tests) both pass against a running stack. The live suite
needed a seeded account that no longer existed in the dev database — created
directly rather than adding seed-data machinery for one test fixture. The
backend's own 345-test suite surfaced two failures unrelated to this work
(`sentry_sdk` missing from a stale API container image, from Phase 11's
`requirements.txt` addition never being rebuilt into the running container);
rebuilding the image was the honest fix, not skipping those two tests.

---

## D41 · Phase 3, built: escrow via Swich, not Stripe, not Safepay alone

**Item 3 on "Not mine to take" — choosing a payment rail — was the last
blocker on Phase 3, and it took three wrong turns before landing on the
right one. Recording all three, because the wrong turns are exactly what a
future reader needs to not repeat them.**

*Turn one: Stripe was never actually a choice.* Stripe does not operate in
Pakistan at all — a Pakistan-registered company cannot open an account,
full stop. Once the client confirmed the company was registered in Pakistan
(2026-08-14), every option requiring a foreign entity was eliminated in one
step, not weighed against Stripe as an alternative.

*Turn two: defaulting to Safepay plus a manual admin payout.* Safepay's
Pay In side is real and well-documented — a Stripe-like checkout API for a
Pakistan entity. But nothing in its public docs showed a payout API for
paying a third party, and the recommendation was to ship the confirmed
half (collect) and hand-wave the other half (an admin wires the freelancer
by hand). Told directly this wasn't good enough, and it wasn't: an escrow
platform that can take money but not automatically pay it out isn't
escrow, it's a deposit box.

*Turn three: chasing Rapyd, hitting the same wall as Stripe.* Rapyd's
`Escrow`/`Disburse`/split-payment products are genuinely real and exactly
the shape wanted — but Rapyd's Business Account is only available to
companies registered in the UK and Hong Kong. Same blocker as Stripe, a
different vendor. Airwallex, checked at the same time, has the identical
problem: business accounts only from ~50 approved jurisdictions, Pakistan
not among them. **Every full-featured marketplace-escrow platform
(Stripe Connect, Rapyd, Airwallex, Mangopay) requires a foreign-registered
entity.** That is the actual state of the market, not a research gap.

*What actually closed it: reading Swich's homepage instead of stopping at
"Safepay-shaped."* The client pasted Swich's own product page, which lists
three separate products — Payment Gateway, **Payouts API** ("disburse …
to gig economy workers, vendors, and partners"), and Cross-Border
Transfers. "Gig economy workers" in a payout product's own description,
for a Pakistan-native platform, was the signal worth actually verifying
rather than taking as marketing copy. It held up: Swich's real API
reference (`api-docs.swichnow.com`) documents `Payout` (domestic IBFT) and
`Remittance` (international, but *inbound* — a beneficiary CNIC and a
Pakistani IBAN, for money arriving in Pakistan from abroad, not the
reverse) as genuinely separate, fully-specified products, alongside a
complete Pay In surface (card, e-wallet, bank, QR, RTP, a hosted checkout).
One vendor, both halves, no second company needed.

*Verified against the real sandbox before a line of adapter code shipped.*
The client supplied real sandbox credentials
(`client_id`/`client_secret`/`SecretKey`, account "Nexolv.tech"). Before
building anything: exchanged them for a real bearer token
(`POST /connect/token`), pulled a real account balance
(`GET /gateway/payout/balance` → `0.0 PKR, status Enabled`), and — the
test that mattered most — built a real checkout URL with the documented
checksum formula and GET it, getting back an actual 37 KB Swich-hosted
checkout page, not an error. `fetch_title` also round-tripped correctly:
it returned a real, specific business error (`"No bank found 'Test
Bank'"`) rather than an auth or format failure, proving the request shape
is right even though the exact bank code/name IBFT expects couldn't be
resolved from public docs (see "what's still open" below).

*The architecture, briefly.* A new `payments` app: `EscrowCharge` tracks
one Pay In attempt (a milestone can retry a failed checkout, so it's a
`ForeignKey`, not `OneToOne`); `PayoutProfile` is a freelancer's verified
bank destination, with `account_number`/`cnic` behind `EncryptedTextField`
the same way OTP secrets are; `Payout` tracks one IBFT attempt. `fund_milestone`
no longer funds anything directly — it creates a checkout session and
returns `checkout_url`; only `payments.views.swich_payin_callback`, once it
independently recomputes and compares the callback's checksum
(`hmac.compare_digest`, not `==`), calls `Milestone.fund()`. A callback that
arrives twice (Swich's own retry behaviour) is a no-op on the second
delivery, not a double-fund. `release_milestone` still executes on the
client's approval alone, but the automated payout it triggers
(`payments.tasks.process_payout`, run via Celery so an IBFT round-trip
never blocks the release request) refuses to start without a complete
`PayoutProfile` — an IBFT call missing a bank code or CNIC is not a
transaction to retry, it's one that should never have been attempted.

*A second bug this pass found, not just Swich integration.* Gig ordering
(`gigs.views.GigViewSet.order`) turned out to fund its own milestone
directly and had done so since Phase 2 — a purchase was never actually
charged, only recorded as funded. Fixed the same way: the order is created,
but its milestone starts `AWAITING_PAYMENT`, and the same callback that
confirms contract milestones now also recognises a gig order (via
`Order.contract`'s `gig_order` reverse relation) and fires the "order
received" notification and `orders_count` increment only once payment is
confirmed — not at checkout-session creation. Finding this cost fixing a
second, unrelated landmine: `order()` is `@transaction.atomic`, and an
early `return` inside an atomic block does **not** roll back rows already
written in that request — the exact bug `Contract.create_from_proposal`
was fixed for once already (the milestone-total validation test in
`contracts/tests.py`). The `swich.is_enabled()` check now runs before any
row is created, not after.

*What's still open, honestly.* The exact bank code/name pairing Swich's
IBFT payout endpoint (`fetch_title`/`create_payout`) expects is not the
same list as `/gateway/payin/get/banks` and is not published anywhere
public — confirmed by testing both the human-readable name Swich's own
Pay-In bank list returned ("Test Bank") and getting the same "no bank
found" response either way. Closing this needs a support ticket to Swich
integration support, not another round of guessing; the module docstring
in `payments/providers/swich.py` says so directly rather than presenting
the payout path as fully proven. Everything else — Pay In checkout,
checksum verification, the payout profile flow, the release-gate — is
proven against the real sandbox, not only mocked.

*Verification.* 17 new tests in `payments/tests.py` plus the existing
contract/gig/marketplace suites updated to route fund/release through a
real checksum-verified callback rather than the old direct `Milestone.fund()`
call — 362 backend tests pass. `flutter analyze` clean on the mobile
payout-profile screen and the `url_launcher`-based checkout hand-off
(added as a new dependency, the same reasoning as `image_picker` for the
student ID card: one genuine external-browser need, one dependency).
`next build` and `eslint` clean on the web payout-profile page and both
checkout redirects (gig order, milestone fund).

**Superseded by D42.** Everything above stayed true through Phase 3's
first build and real sandbox verification — the removal that follows is
not because any of this was wrong, but because Swich's *production*
merchant account turned out to need something the client will not
currently provide.

---

## D42 · Swich removed: custodial escrow instead, at the client's direction

**D41 built Phase 3 for real, against a real sandbox. This decision tears
that integration out and replaces it with something structurally simpler,
on explicit client instruction — not because Swich broke, but because of
what its production account requires.**

*The trigger.* The client asked for an alternative "where I don't have to
give an NTN number." NTN (Pakistan's National Tax Number) is not a line
item in Swich's onboarding that a different vendor sidesteps — SBP/FBR
requires it of any licensed payment gateway operating in Pakistan as a
condition of a *production* (not sandbox) merchant account. Asked to
clarify whether this meant "register a company but skip the NTN
paperwork" or "no real gateway at all right now," the client answered with
the second, and specified the replacement directly: the client's own bank
account collects the money, a human releases it to the freelancer by hand
minus a platform cut, and the product still presents the whole thing to
users as escrow.

*What came out.* `payments/providers/` (the Swich adapter — checkout URL
construction, checksum verification, token caching, IBFT payout) and
`payments/tasks.py` (`process_payout`, the Celery-async payout call) are
deleted, not disabled behind a flag. `EscrowCharge` (a Pay In attempt,
`ForeignKey` because a checkout could retry) is gone; so is the
`swich_payin_callback` webhook view and the `AWAITING_PAYMENT` milestone
status that existed only to mark time between checkout-session creation
and webhook confirmation. `SWICH_ENABLED`/`SWICH_CLIENT_ID`/
`SWICH_CLIENT_SECRET`/`SWICH_SECRET_KEY` are gone from settings.

*What replaced it.* `EscrowFunding` — a client's own declaration that
they've transferred a milestone's money to the platform's bank account,
`OneToOne` on `Milestone` rather than `ForeignKey` (unlike a gateway
charge, there is nothing here to retry — it is a fact, not an attempt).
`Payout` keeps the same shape D41 gave it (bank/CNIC behind
`EncryptedTextField`) but drops everything Swich-specific
(`customer_transaction_id`, `swich_response`, `failure_reason`) in favour
of a commission split computed once and snapshotted:
`Payout.compute(milestone, freelancer, commission_percent)` returns
`gross_amount`/`commission_amount`/`net_amount`, quantized to the cent,
never recomputed later even if the platform's commission rate changes.
`bank_transfer_instructions` is the one new endpoint — it just echoes
`PLATFORM_BANK_NAME`/`PLATFORM_BANK_ACCOUNT_TITLE`/
`PLATFORM_BANK_ACCOUNT_NUMBER`/`PLATFORM_COMMISSION_PERCENT` from
settings. `fund_milestone` and `gigs.order` both create an `EscrowFunding`
and call `milestone.fund()` synchronously, in the same request, before
returning — no checkout redirect, no webhook, no polling loop on the
frontend waiting for one. `release_milestone` still executes on the
client's approval alone (unconditional, same as D41), but refuses to
queue a `Payout` without a complete `PayoutProfile` on file — a `Payout`
with nowhere to send the money is worse than one that doesn't exist yet,
so this half of the D41 gate carries over even though nothing downstream
of it is automated anymore. On release, an admin (`payments.admin.PayoutAdmin`,
`mark_paid` action) sends the transfer by hand and marks it paid — the
`Payout.Status.PENDING`/`PAID` pair replaces D41's automated
`PENDING`/`PAID`/`FAILED` triggered by `process_payout`.

*Presented as escrow, not as "we'll pay you eventually."* Every UI surface
that touched Swich language now talks about the platform's own account
instead, without softening what's actually true: `BankTransferPanel` (web)
and `showBankTransferDialog` (mobile) show the account details and a
reference-note field, both labelled "into escrow"; `ReleaseEstimate` shows
the freelancer's net amount and the commission taken before the client
confirms release, labelled "from escrow." Notifications and
`ContractEvent` log entries say "funded — held in escrow" and "released
from escrow," matching what a client relying only on the UI would already
believe. Nothing claims automation that isn't there — the payout history
screens say plainly that a released amount is *pending* until paid, not
that it has been sent.

*A second bug found in this pass, not introduced by it.* `gigs.OrderViewSet.accept`
(the buyer accepting a gig delivery) calls `milestone.release()` directly,
bypassing `contracts.views.release_milestone` entirely — which means it
never created a `Payout` row, in the original pre-Phase-3 code *and*
throughout the entire D41 Swich build. Nobody caught it because nothing
in either payments implementation asserted on it. Fixed here by adding
the same `Payout.compute(...)` call directly into `accept()`, deliberately
*not* gated on the seller's `PayoutProfile` being complete — the buyer
accepting their own delivery should not be blocked by a gap that is the
seller's to close, so the `Payout` row is created regardless and simply
sits `PENDING` until there is somewhere to send it.

*What stays true from D41, and what doesn't.* The market research — Stripe
and Rapyd need a foreign-registered entity, Airwallex the same, Safepay's
public docs show no payout API — is still accurate context for why no
drop-in gateway currently fits, and stays relevant if a real integration
is revisited later. What no longer holds: the automated collection and
automated payout D41 delivered are both gone. This is a deliberate step
back from that automation, done at the client's explicit request, not a
regression to paper over — re-adding a real gateway later means wiring
`fund_milestone`/`release_milestone`/`gigs.order` to it again; the
`EscrowFunding`/`Payout` bookkeeping shape barely has to change to support
it.

*Verification.* `payments/tests.py` rewritten from scratch (17 Swich tests
— checksums, callback replay/forgery, token caching — replaced with 17
new ones covering `Payout.compute` arithmetic, `PayoutProfile.is_complete`,
`bank_transfer_instructions`, fund/release through the new endpoints, and
the fund-twice/release-before-delivery/no-payout-profile refusal paths).
`contracts/tests.py`, `gigs/tests.py`, and `marketplace/tests.py` (the
trial-lifecycle test) updated off the old `_fund_via_swich`/
`override_settings(**_SWICH_TEST_SETTINGS)` pattern onto a plain `_fund`
helper that just POSTs and asserts 200 — no checksum, no callback
simulation, because there is nothing left to simulate. The gig-order
`accept()` fix is asserted directly: `test_the_full_delivery_and_acceptance_loop`
now checks a `Payout` exists with the right split after a buyer accepts.
**359 backend tests pass** (19 of them the cross-tenant leakage gate, run
again on its own as its own CI step), migrations regenerated cleanly
(`payments.0001_initial` dropped and rebuilt against the new model shape,
plus a `contracts` migration for dropping the now-unused
`AWAITING_PAYMENT` milestone status), `ruff check`/`ruff format --check`
clean on every touched file. `flutter analyze` and `flutter test` clean
on mobile (`url_launcher`, added for Swich's checkout hand-off, removed
again — nothing else in the app needs an external browser launch).
`next build`, `eslint`, and `tsc --noEmit`-via-build clean on web. Beyond
the test suite: the full fund → deliver → release loop was run against a
live local stack in an actual browser — sign in, confirm a bank transfer,
sign in as the freelancer, deliver, sign in as the client, and release —
and the `Payout` row it produced (`gross 5000.00, commission 500.00 (10%),
net 4500.00, status pending`) matched the UI's own pre-release estimate
exactly.

---

## D43 · Plan billing wired to the same custodial model as D42

**D42 rebuilt Phase 3's escrow around the platform's own bank account.
Phase 8's `subscribe` was never touched by that pass — it still activated
a paid tier for free, and the pricing page said so outright ("Card
payments arrive with the wallet in the next release... bills nothing").
This decision closes that gap the same way, not a different one.**

*The trigger.* No client ask this time — this was the one piece of "14 of
14 phases built" that the previous session's own README explicitly
flagged as still open: "Phase 8's subscriptions are a separate,
still-unwired integration." That sentence was accurate and became the
next thing to build once D42 landed, since D42 had already established
the exact pattern a fix needed to follow.

*What changed.* `professional.views.subscribe` used to create an `ACTIVE`
`Subscription` with nothing behind it — its own docstring said "Phase 3
replaces the body of this with a gateway charge," which had already
stopped being true the moment D42 shipped a bank-transfer model instead
of a gateway. A paid tier now runs on exactly the trust basis
`contracts.fund_milestone` and `gigs.order` do: the caller has already
transferred the plan's price to `GET
/payments/bank-transfer-instructions/`'s account, and the `subscribe`
call is them confirming that. Gated by `CanMoveMoney` — the same
permission `fund_milestone`/`release_milestone`/`gigs.order` use — checked
inline (`subscribe` is a bare `@api_view`, not a viewset action, so there
is no `permission_classes` list to attach it to at the decorator level;
it only applies to the paid branch, since switching to Free is not a
declaration of anything and stays ungated, unchanged from before this
decision).

*What's new.* `SubscriptionPayment` (`api/payments/models.py`) — one row
per period, `ForeignKey` to `professional.Subscription`, `amount`,
`reference_note`, `paid_by`. Deliberately not shaped like `EscrowFunding`
plus a matching `Payout`: a milestone's escrowed money has a release half
that sends most of it to someone else, but a subscription payment is the
platform's in full the moment it exists, so there is nothing to queue and
`payments.admin` has no `mark_paid` action for it — `SubscriptionPaymentAdmin`
is read-only, for reconciliation only. `subscribe` creates one alongside
the `Subscription` it always created, inside the same
`@transaction.atomic` view.

*Reused rather than rebuilt.* The web pricing page and mobile
`SubscriptionScreen` both route a paid choice through the same
bank-transfer UI Phase 3 already has — `BankTransferPanel` (web) shown in
place of the "Choose" button until confirmed or cancelled,
`showBankTransferDialog` (mobile) as a dialog. The mobile dialog's title
was hardcoded to "Fund into escrow," which reads wrong over a plan
purchase, so it gained an optional `title` parameter (default unchanged,
so the contract and gig call sites needed no edits) and the subscription
screen passes `"Confirm your {plan.name} payment"`. Neither `web/lib/api.ts`
nor `mobile/lib/src/api/endpoints.dart` needed a new endpoint — `subscribe`
just gained a `reference_note`/`referenceNote` parameter alongside `tier`
and `interval`.

*What stays true from D42, and what's new here.* The framing principle —
present the real mechanism honestly rather than simulate automation that
doesn't exist — carries over unchanged; the pricing page's stale "bills
nothing" alert is deleted rather than reworded, since there is now
something real behind the button it used to caveat. Retainers
(seller-to-buyer, a different money flow entirely) are untouched by this
decision and still carry their own "arrives with the wallet" notice on
`web/app/(app)/retainers` — D43 is Phase 8's account-to-platform billing
specifically, not every unbuilt payment surface in the professional
layer.

*Verification.* Three new tests in `professional/tests.py`: a paid
`subscribe` records a `SubscriptionPayment` with the exact plan price for
the chosen interval and the reference note the caller sent; an
unenrolled account gets `403`/`two_factor_required` with no `Subscription`
left behind; switching to Free creates no `SubscriptionPayment` at all.
**362 backend tests pass** (359 from D42 plus these 3; the cross-tenant
gate is unaffected and still passes standalone at 19), `makemigrations
--check` clean, `ruff check`/`ruff format --check` clean on every touched
file (`payments/models.py`, `payments/admin.py`, `professional/views.py`,
`professional/tests.py` — the migration itself is excluded from lint the
same way every migration in this repo is). `flutter analyze` and `flutter
test` clean on mobile, plus a `flutter build web` smoke build since three
Dart files changed. `next build`, `eslint`, and `tsc --noEmit` clean on
web. Beyond the test suite: seeded all three plan tiers in the local
stack (only Free existed — `plans()` only calls `seed_default_plans()`
when zero rows exist, and a prior session's `for_user()` call had already
created a bare `Plan.get_free()` row, so Pro/Elite were silently never
seeded; a pre-existing quirk, not something this decision introduces),
signed in as a fresh verified-and-2FA-enrolled account, chose Pro monthly
in the browser, confirmed a bank transfer with reference note
`IBFT-LIVE-TEST-001`, and read back a `Subscription` (`pro`, `active`,
`current_period_end` 30 days out) and a `SubscriptionPayment` (`1500.00
PKR`, same reference note, `paid_by` the signed-in account) that matched
the UI exactly. Test fixtures (the account, its `Subscription`, and its
`SubscriptionPayment`) deleted afterward; the seeded Pro/Elite plan rows
were left in place as the real reference data they are, not test fixtures.

---

## D44 · A free test deployment path, separate from D32's real one

**Asked for a way to put the whole platform somewhere free "just for
testing." Wix was the platform actually named, and it can't run this —
it has no path to arbitrary backend code, Docker, Postgres, or a task
queue at any price point, so there was no configuration of it that would
have worked. What follows instead is the closest thing to "free and
complete" that a real host can offer.**

*Why not Railway or Fly.io.* Checked current terms (August 2026) rather
than assumed: Railway's free tier is a one-time $5 trial credit that
expires in 30 days, after which it reverts to $1/month of credit — not
enough to keep a multi-service app running. Fly.io removed its free
allowance for new accounts in 2024 entirely; a card is required after a
2-hour trial and even the smallest always-on machine runs about
$1.94/month. Neither is "free," just free-for-a-while or free-until-a-card.
Render's free web service and free Postgres are genuinely free with no
card, which is why it's the one this targets — at the cost of two real
limits: the free database is deleted 90 days after creation, and there is
no free tier for a background worker anywhere, on any of these platforms.
That last point isn't a Render gap to shop around for a fix to — a
worker is compute that has to run continuously, and continuous compute is
what every free tier draws its line in front of.

*What makes "no worker" survivable rather than disqualifying:* Section
24's "notifications are always queued, never sent inline" already runs
through Celery's `.delay()`, and `config/settings.py` already had a
`CELERY_TASK_ALWAYS_EAGER` flag (defaulting to `DEBUG`) for exactly this
kind of environment — eager mode runs a task's body synchronously inside
the caller, no broker involved. The one piece that didn't already have an
escape hatch was the cache: `CACHES` pointed at `REDIS_URL` unconditionally,
which would fail outright with no Redis at all. Fixed by making `REDIS_URL`
itself optional (default `""` instead of `redis://localhost:6379/0`) and
branching `CACHES` between `RedisCache` and Django's built-in `LocMemCache`
depending on whether it's set — and tying `CELERY_TASK_ALWAYS_EAGER`'s
default to `DEBUG or not REDIS_URL` rather than `DEBUG` alone, so a
deployment with no Redis gets eager mode automatically instead of needing
a second env var to remember. Every real environment this repo runs
(`docker-compose.yml`, `.env`, `deploy/docker-compose.prod.yml`) sets
`REDIS_URL` explicitly, so none of them notice this branch exists — it
only activates when the variable is genuinely absent, which was true of
no environment before this decision.

*What still doesn't run without a worker, named rather than glossed
over:* `CELERY_BEAT_SCHEDULER`'s periodic tasks — search reindexing,
reputation refresh, promotion sweeps, challenge-deadline sweeps — need an
actual `celery worker -B` process to fire on a schedule, and eager mode
doesn't substitute for that; it only covers tasks a request triggers
directly. A workerless deploy is for clicking through the product, not
for testing anything that depends on a cron-like sweep having run.

*`render.yaml`, at the repo root:* a Render Blueprint — one free web
service (Docker build, `migrate && collectstatic && gunicorn` as the
start command, matching D32's production command apart from Redis) and
one free Postgres, wired together with `fromDatabase` references so no
connection string has to be copied by hand. `SECRET_KEY`, `FILE_SIGNING_KEY`,
and `FIELD_ENCRYPTION_KEY` all get `generateValue: true` rather than
sharing one secret three ways. `ALLOWED_HOSTS` is set to `.onrender.com`
(Django's leading-dot syntax, matching any subdomain) since the exact
hostname isn't known until Render assigns it; `FRONTEND_URL` and
`CORS_ALLOWED_ORIGINS` are left as placeholders with a comment, since
`django-cors-headers`' `CORS_ALLOWED_ORIGINS` is an exact-match list, not
a pattern, and the real Vercel URL doesn't exist until after the web
frontend's own deploy — a two-step dance documented in the file itself,
not assumed obvious. `DEVICE_COOLOFF_SECONDS` is shortened from the real
7200-second default to 60, called out explicitly as a testing-only
convenience so a solo tester isn't blocked for two hours after their
first sign-in before they can try funding a milestone — not a claim that
60 seconds is the right value anywhere else.

*This is not D32.* The real production path — Redis, a Celery worker,
ClamAV, Caddy, backups — is unchanged and still the only one meant to
serve real users. `render.yaml` exists next to it, not instead of it, and
says so in its own header comment.

*Verification, and its honest limit.* The Redis-optional branch is
verified for real: `python manage.py check`, the full 362-test suite, and
the cross-tenant gate all pass identically with `REDIS_URL` unset, and a
cache round-trip plus an eager Celery task (`sweep_promotions`) were both
run by hand against that configuration and behaved correctly — same
362-test pass count with `REDIS_URL` set, so nothing in the normal path
regressed either. What is **not** verified is `render.yaml` itself
against Render's actual blueprint parser — that requires a Render account
to apply it, which is not something to sign up for or connect on someone
else's behalf. The file is correct against everything checkable without
one: valid YAML, every `config()` call in `settings.py` with no default
accounted for, `ALLOWED_HOSTS`/CORS reasoning checked against the exact
matching logic `django-cors-headers` and Django actually use.

---

## D45 · The CSRF double-submit cookie never worked across two real domains

**Deploying D44's test path surfaced a real bug that had nothing to do
with the test deployment itself: the web client's CSRF handling only
ever worked because every environment that had exercised it so far
happened to put the web app and the API on the same hostname. Two
genuinely different domains — exactly what D44 requires — broke it
outright, and D32's real production deployment was never actually
proven safe from the same failure.**

*The symptom.* First sign-in after a fresh deploy would succeed. Every
attempt after that — including just trying to sign in again — failed
with "CSRF check failed: rejected." Not intermittent, not a caching
artifact: deterministic, and it got worse (locked out entirely) exactly
once a session had ever been established.

*The mechanism.* `web/lib/api.ts` read the CSRF token by calling
`document.cookie` for `csrftoken` before every unsafe request. That
cookie is set by the API (`accounts.views.csrf`, via
`@ensure_csrf_cookie`) with no `CSRF_COOKIE_DOMAIN` configured anywhere
in `config/settings.py` — so it defaults to Django's own behaviour of
scoping the cookie to the exact host that set it. `document.cookie`
itself only ever exposes the *current page's own* cookies, regardless of
CORS or `credentials: "include"` — that isn't a Django setting to tune,
it's how cookies work. A page on `skilrize01.vercel.app` can no more
read a cookie `skilrize-api.onrender.com` set than it could read one set
by a website it has never visited.

`accounts.auth.CookieJWTAuthentication._enforce_csrf` only runs once an
access-token cookie is present on the request — which is exactly why the
*first* request after a fresh session ever worked: no access cookie yet,
so the check never ran. The moment login succeeded and set that cookie,
every subsequent unsafe request (another login attempt with the stale
cookie still attached, funding a milestone, anything) hit the check —
and `document.cookie` had never been able to supply a token to answer it
with, ever, on this deployment shape. The `X-CSRFToken` header the
client sent was silently empty the entire time.

*Why this was never caught before D44.* Every prior test of this path —
local dev, the Docker Compose stack, D32's own verification —
ran the web app and the API on `localhost` at two different *ports*.
Cookies are scoped by host, not port, so `localhost:3000` and
`localhost:8000` share a cookie jar for anything neither side explicitly
domain-scopes — the exact case that made this look like it worked. D32's
real deployment puts the two on subdomains of one domain
(`api.skilrize.com` / the marketing domain), which is a **different**
host from the API's own perspective too, and `CSRF_COOKIE_DOMAIN` was
never set to the shared parent domain there either. Nothing in this repo
had ever actually exercised an authenticated write against that
deployment from a real browser before this pass — D32's own verification
was infrastructure-level (the stack boots, TLS works), not this. This
was latent in the real production path as much as the test one; D44's
deploy just happened to be what finally ran the write.

*The fix, chosen to work for both topologies rather than patched around
D44 specifically.* Scoping the cookie to a shared parent domain
(`CSRF_COOKIE_DOMAIN=.skilrize.com`) would fix D32's subdomain case but
does nothing for D44's — Vercel and Render share no parent domain to
scope to at all, cross-domain cookie sharing via the `Domain` attribute
is not something any setting can produce. So the fix stops depending on
`document.cookie` for the token value entirely: `accounts.views.csrf`
now returns the token in the JSON body (`get_token(request)`) as well as
setting the cookie, and `web/lib/api.ts` reads it from there instead —
held in a module-level variable (`csrfToken`), populated once by
`primeCsrf()` and reused, rather than re-read from a cookie before every
request. This works identically regardless of whether the web app and
API share a host, share a parent domain, or share nothing at all. Fixed
the same bug `refreshSession` had independently: it read the CSRF cookie
directly without ever calling `primeCsrf()` first, so a silent
token-refresh triggered before any other CSRF-priming call would have
sent no header even in the working, same-host case.

*Verification, deliberately built to fail on the old code first.* The
`client` fixture used throughout `accounts/tests.py` is `APIClient()`
with `enforce_csrf_checks` at its default (`False`) — Django's test
client bypasses CSRF checking entirely unless told not to, which means
every existing test in the suite, including the login tests, would have
kept passing against the broken version of this code without noticing
anything was wrong. Two new tests close that gap:
`test_the_csrf_endpoint_returns_the_token_in_the_body` (the endpoint
actually returns a `csrfToken` in the JSON, not just the cookie) and
`test_an_unsafe_cookie_authenticated_request_needs_the_csrf_header`,
built against a dedicated `APIClient(enforce_csrf_checks=True)` so it
exercises the real path — it logs in, confirms a subsequent write
(`logout`) is refused without a `X-CSRFToken` header despite a valid
access cookie (the exact failure the live bug produced), then confirms
the token taken from the `/csrf/` body — never read back off a cookie —
un-refuses it. 364 backend tests pass (362 plus these two), `ruff`
clean, `eslint`/`tsc --noEmit` clean on web, a full `VERCEL=1` build
still succeeds. Not yet verified at the point of writing this: the
actual deployed pair, `skilrize01.vercel.app` against
`skilrize-api.onrender.com` — that happens after this pushes and Render
redeploys, the same two-step dance every change to this path requires.

## D46 · Settlement: every cancellation refunds, every unanswered delivery releases

**Two holes in the escrow model where money went missing from the books.
A cancelled order simply closed — nothing recorded that the buyer's
transfer was owed back to them. And a delivery nobody answered held the
seller's money forever, even though notifications had promised both
sides a review window.**

*Refunds.* `payments.Refund` is the mirror image of `Payout`: one per
milestone, `pending` until an admin sends the transfer back by hand and
marks it `refunded` (Django admin, "Mark as refunded"). Every path that
returns escrowed money creates one through `payments.settlement.
queue_refund` — a seller cancelling an order, a buyer cancelling before
sending requirements or after a missed due date, a freelancer walking
away from a funded contract. The refund is always the full amount; no fee
is kept on cancelled work. Buyers see it on the order page and at
`GET /payments/refunds/`.

*Who may cancel* lives on the model, `Order.cancellation_allowed_for`, so
the endpoint and the `can_cancel` / `cancel_blocked_reason` fields the
client renders its button from can never disagree. A seller may cancel
anything undelivered. A buyer may cancel before sending requirements, or
once the order is late — not while the seller is working on time, because
the seller started on the buyer's word. Nobody cancels delivered work;
that is a review or a support case. On contracts, a freelancer may cancel
a funded contract unless a delivery is awaiting review; a client may not
cancel while money is held.

*Auto-release.* `settlement.auto_release_lapsed` accepts deliveries whose
window has passed — 3 days for a service order (`Order.accept_by`), 7 days
for a contract milestone — and queues the payout. It runs hourly from the
`auto-release-deliveries` periodic task, which a data migration
(`core/0006`) creates, so the schedule exists on every database the moment
it migrates rather than depending on someone adding it by hand. Release
arithmetic moved into `settlement.queue_payout`, which is idempotent: a
second release of the same milestone returns the existing `Payout`.

*No bank account, no funding.* Every funding endpoint takes the client's
word that they transferred money. With `PLATFORM_BANK_*` unset — as the
production server was at the time of writing — the checkout showed a blank
account and still accepted "I've sent the payment". Funding (orders,
milestones, paid plans) now refuses with `503 payments_unavailable` until
the account is configured, and `bank-transfer-instructions` reports
`available` so the UI says so instead of showing empty fields.

*Payment never received.* An order starts on the buyer's word, and the
Terms let the platform cancel one whose transfer has not arrived after
three business days. Doing that through the ordinary cancel would record
a refund for money that never came in, so `settlement.void_unpaid_order`
closes the order and its contract with nothing owed either way, and tells
both sides why. It is a Django admin action on Orders ("Cancel — buyer's
payment never received"), and it refuses delivered or finished orders:
by then the question is a dispute, not a missing payment.

## D47 · GDPR as the privacy baseline, for every user

**Taken as the standard to build to because it is the strictest widely
recognised one, not because SkilRize is obliged to follow it: it gives a
concrete, checkable answer to "is this handled properly" for every piece
of personal data, which Pakistani law alone does not yet.**

What that meant in code:

- *Consent records (Art. 7(1)).* Sign-up requires `accept_terms`; each
  acceptance is stored as a `LegalAcceptance` row with the document
  version (`LEGAL_TERMS_VERSION`, `LEGAL_PRIVACY_VERSION`), IP and user
  agent, so the platform can show which version someone agreed to.
- *Access and portability (Arts. 15, 20).* `POST /auth/me/export/` returns
  everything held about the caller as JSON. Discovery is generic — every
  model with a foreign key to the user is found through `_meta` — so a new
  model cannot be forgotten; secrets are omitted by name and encrypted
  bank/CNIC fields are masked to their last four digits. Step-up is
  required: a stolen session alone must not be able to walk off with
  someone's history. The request is written to the audit log.
- *Erasure (Art. 17).* `POST /auth/me/delete/` anonymises the account
  rather than deleting the row — orders, payments and payouts must be kept
  for tax purposes, and reviews and messages are part of other people's
  records too — and deletes everything that is only the user's: identity
  and portfolio files, payout details, sessions, devices, 2FA, tokens,
  notifications, integrations. Listings are paused, open briefs closed,
  proposals withdrawn. It refuses while money is still moving (open
  orders, held milestones, pending payouts or refunds). `GET` on the same
  endpoint says what would block it and what is kept, before a password is
  ever asked for. Settings → Privacy & data is the UI for both.
- *Cookies (ePrivacy 5(3)).* Only strictly necessary cookies are set, so a
  notice — not a consent banner — is what the law asks for. A "reject all"
  button that changed nothing would be a dark pattern of its own.
- *Transparency.* A Privacy Policy with a legal basis for each purpose,
  retention periods, processors (Oracle Cloud, Google, Backblaze),
  transfers, automated decisions and rights; a Cookie Policy listing every
  cookie and storage key by name.

The policies were drafted from what the code actually does and checked
against it line by line, but **they were not written by a lawyer** — see
"Not mine to take".

## D48 · Launch surfaces a payment provider can review

**Swich's reviewers reported they could not reach a checkout from any
service. The cause was not one bug but four: the production database had
no categories and no services at all; the landing page's "featured"
services were hard-coded and linked to gigs that did not exist; there was
no checkout page — ordering happened inside a panel on the service page,
behind sign-in; and search was login-walled.**

- *Checkout* (`/checkout/<gig>`) is public. It shows the package, extras,
  total, delivery time, policies and payment methods before asking anyone
  to sign in; the selection lives in the query string, so signing in
  mid-checkout returns to the same order. Bank transfer is the one live
  method; card and wallets are listed as coming, which is where a gateway
  slots in. Placing an order requires ticking the Terms and Refund policy.
  The order page now has the cancel control and shows refund status.
- *Business identity.* Payment networks require a merchant site to show
  its legal operator, address and contact details, and every policy names
  the data controller. They all read from `web/lib/business.ts`. Seven
  pages carry them: Terms, Privacy, Refunds & Cancellation, Service
  Delivery (the start-to-finish order flow a reviewer asks for), Cookies,
  Contact and About, all linked from a footer on every public page.
- *Content.* `seed` now runs on every deploy (it is idempotent), and
  `create_storefront --email …` lists the operator's own four services
  (websites, apps, AI automation, UI/UX) under a real account. The landing
  page shows the live catalogue and hides the section when it is empty —
  nothing claims traction the platform has not earned. The storefront's
  prices are placeholders for the founder to set.
- *Phone verification off until SMS exists.* No SMS provider is
  configured, so a phone code could never arrive and every account was
  blocked from transacting. `PHONE_VERIFICATION_REQUIRED` (default off)
  removes phone from the profile requirements; the code path stays for
  when a provider is added, and `set_phone` says plainly that no SMS was
  sent instead of pretending.

## D49 · The redesign: an escrow slip, not a gradient

**The previous interface read as generated: a violet gradient accent,
glowing orbs, and a serif-italic headline over a stock photo — the look
most AI-built landing pages share. The redesign takes its identity from
the one thing that makes a stranger trust a marketplace with money:
knowing where the money is.**

The signature is the *escrow ticket* — an order slip on the landing and
sign-in pages that inks in each step (paid, delivered, approved, released)
with the fee arithmetic printed on it; the checkout's order summary uses
the same perforated slip. Colour is marigold (`#f2a10f`) for actions with
ink text on it, a darker ochre for links and focus, near-neutral greys,
and *firozi* — the turquoise of Multan tilework — reserved for campus
portals so the student surface is recognisable at a glance. Type is
Archivo at a condensed width for display and Martian Mono for labels and
every figure, so amounts line up. Motion is limited to the ticket's
sequence. It waits on its first frame until the slip is in view — the
slip sits below the fold, so a pass begun on page load would be over
before anyone reached it — then plays at once and replays after a
two-second hold for as long as it stays on screen. The owner chose a
continuous loop without a Pause control, which departs from WCAG 2.2.2
(motion lasting over five seconds should be stoppable); under
`prefers-reduced-motion` it shows the finished slip and never loops. Remaining gradient and
"sparkle" treatments in the app were removed rather than restyled.

## D50 · Every service shows the work: a required picture, an optional video

**A marketplace buyer decides with their eyes first, and a catalogue of
text cards reads as empty. Publishing a service now needs at least one
picture (up to three; the first is the cover), and one short MP4 is
optional.** The rule lives in `Gig.publish_blockers`, so the API refuses
an imageless publish whatever client sends it; the publish form checks
first so nothing is created by a refused attempt. The video is capped at
20 MB because ClamAV's default stream limit is 25 MB and a file the
scanner cannot read whole is never released. Video is served in byte
ranges, which Safari needs in order to play it at all.

Building it exposed two older bugs. The gallery endpoint had its request
parsers disabled and no test, so it could never accept a file. And every
uploaded file, profile photos included, came back as a relative
`/files/<token>/` address that the website resolved against itself and
404ed; the API's `Cross-Origin-Resource-Policy: same-origin` and the
site's `img-src 'self'` would have blocked the API's own address too.
Files are now served from the website's domain: Caddy routes `/files/*`
to the API in production, and a Next rewrite does it locally and on the
test deploy. That was the first Caddyfile change since launch, and it
showed that `deploy.sh` never applied one: Caddy mounts the file on its
own, keeps the copy it started with when `git reset` replaces it, and is
not restarted by `up -d`. The script now restarts Caddy whenever the
file it is running differs from the one on disk.

Sellers also had no way to see their own services after publishing. The
service page carries a Manage your service panel for its owner
(pictures, video, publish, pause), and `/gigs?mine=true` lists a
seller's services including drafts. Cards gain a thin ink outline, dark
in the light theme and light in the dark, at the owner's request.

---

## D51 · Connected accounts made ready to switch on

Asked to enable the five connected accounts, the first finding was that
nothing on our side could: each one needs a developer app registered with
Zoom, Google, GitHub, Figma or Notion under the operator's own account, and
that app's keys. Step 10 of `deploy/README.md` now walks through each
registration with its exact redirect URL and scopes, and
`production.env.example` carries the settings block.

Readying them for real use surfaced three defects that would have shown
only after launch:

- **Tokens were never renewed.** Zoom and Google access tokens last an
  hour, so scheduling a call would have failed an hour after connecting.
  Every provider call now takes its token from `integrations/tokens.py`,
  which refreshes it first when it is within two minutes of expiry. The
  renewal holds a row lock because Zoom rotates the refresh token on every
  use, and two renewals racing would spend the same one. A token that
  cannot be renewed produces a "reconnect" message, not a raw HTTP error.
  `is_expired` now means "must reconnect", not "access token past its hour".
- **Figma asked for a deprecated scope.** `file_read` is no longer
  accepted for OAuth apps; the adapter asks for `file_versions:read`, the
  one scope its version-history call needs, and authenticates to the token
  endpoint with HTTP Basic as Figma now documents.
- **Zoom start times were labelled UTC without being converted to it.**
  Harmless while `TIME_ZONE` is UTC, wrong the day it is not.

Some limits stay on the providers' side. Zoom lets only the operator's own
Zoom account connect until its Marketplace review passes. Google limits an
unverified app to 100 named test users. A private Figma app works only for
the operator's team. GitHub's `repo:status` scope reads public
repositories only; private ones would need a GitHub App with read-only
contents permission rather than the all-or-nothing `repo` scope. The
disabled state reads "Coming soon", and each row says what connecting it
does.

---

## D52 · A device is what it keeps, and a new account is not held

The owner asked for the new-device hold to apply only to a sign-in from a
new device, and for 30 minutes rather than two hours. Checking it turned up
why it appeared more often than that:

- **Signing up counted as a new device.** The account's first device was
  held like any other, so a person who had just registered could not buy or
  bid for two hours. The device an account is created on is now trusted at
  once; a new account has no history or money to protect.
- **A device was its user agent.** Chrome's version is in that string, so
  every monthly update made the same laptop a new device: an emailed code,
  an alert and a fresh hold. And two people on the same browser version
  shared one "device". A device is now a random id it keeps: an HttpOnly
  cookie (`skilrize_device`, 400 days, renewed at each sign-in) in a
  browser, secure storage in the app, sent as `X-Skilrize-Device`. The
  stored fingerprint is a keyed hash of that id.

Existing rows are keyed by user agent. A sign-in whose agent still matches
one is recognised and re-keyed to the new id on the spot, and a browser
already signed in is given its id the next time it loads `/auth/me/`, so
nobody is locked out by the switch. The fallback keeps the old weakness (a
matching agent is enough) only for rows no one has signed in with since.
An app build too old to send the header is still known by its agent, and is
never minted an id it would not keep.

The hold itself is 30 minutes (`DEVICE_COOLOFF_SECONDS=1800`). It still
applies after the emailed code, as D16 chose, and the alert now states the
wait in minutes. The cookie is listed in the Cookie Policy as strictly
necessary.

---

## D53 · A Buying/Selling switch in the header

The owner asked for a way to switch between the buyer and the seller
profile from the top bar. From the start one account has been both (signup
creates both profiles), so this is a switch of view, not of account or
permission: `web/lib/mode.ts` keeps the choice per browser, and the server
never reads it. Anything on either side stays reachable from the account
menu, and a URL works whichever side is selected.

What it changes:

- **The header leads with that side's work.** Buying: Services, Your
  briefs, Orders, Contracts, Messages, and "Post a brief". Selling: Find
  work, Your services, Proposals, Orders, Contracts, Messages, and
  "Publish a service". Before, all ten destinations shared one bar and the
  last of them were always cut off at laptop width; each side now fits
  from 1280px, and the edge fades only when something is actually cut off.
  Search, Showcase, Activity, Challenges and Communities moved to the
  account menu.
- **Switching lands on the dashboard**, which now opens with that side's
  summary: briefs and orders placed when buying; services, orders
  received and proposals sent when selling.
- **The pages each side needed.** `/projects?mine=true` is "Your briefs"
  (the API already filtered by owner; the page did not), with each brief's
  status. The Orders filter lives in the URL, so the header's Orders link
  opens on the right side.

The switch is filled in ink rather than raised like the Global/Campus
control beside it, so the two are not read as one control. On phones it
sits at the top of the account menu. The stored choice is listed in the
Cookie Policy.

---

## D54 · One admin console for the whole platform

The owner asked for an admin panel that controls everything. The console
from D35 covered student checks, users, contracts and the audit log; the
daily work of running SkilRize happened in Django's own admin, a developer
tool, or could not happen at all:

- **Identity (CNIC) checks had no review screen.** A member's upload set
  them to pending, and only editing the field in Django's admin could
  approve them. Nobody can transact until it is approved.
- **Incoming payments were never checked.** A buyer's "I have paid" funds
  the order at once (D42). `EscrowFunding` and `SubscriptionPayment` gain
  `confirmed_at`/`confirmed_by`: the console lists unconfirmed ones oldest
  first, to be matched against the bank statement. "Not received" voids a
  gig order (no refund, as nothing arrived), returns a brief's milestone to
  awaiting funding, or cancels a plan. It is refused once work is
  delivered, when it has become a dispute.
- **Payouts and refunds** were Django admin bulk actions with no bank
  details in view and no message to the person paid. The console shows
  the recipient's bank details only on request, logs each view as a
  sensitive read with the CNIC masked to its last four digits, requires the
  bank's transfer reference to mark one sent, and tells the recipient.

Also added: every service and brief with remove, restore and close;
categories; a platform-wide queue of community reports (community
moderators still see their own); all service orders with their payment
state; an account summary, "sign out everywhere" and role changes on
users; and a read-only view of the server's configuration. Configuration
stays in `production.env`: a settings page that could change the bank
account payments go to would be the most valuable page on the site to
hijack.

Rules the whole console keeps: each endpoint answers to its roles through
`require_admin_role`, Super Admin to all; each change records the reason
in the audit log and notifies the person affected; nothing moves money,
because the money moves at the bank and the console records that it did.
Roles are granted only by a Super Admin, never to oneself, and granting
one ends the account's sessions so the next sign-in meets the two-factor
rule every admin role carries. The first Super Admin comes from
`manage.py set_admin_role`. A Django superuser is reported to the web app
as a Super Admin, matching what the API already allowed.

The console's API is its own app, `api/console`, rather than more views on
each model's app. The older admin endpoints stay where D35 put them.

---

## D55 · Payments through Swich; bank transfer removed

The operator has an NTN and is opening a Swich merchant account, and asked
for bank transfer to go: buyers pay by debit or credit card, Easypaisa,
JazzCash or 1Bill, and the site should say so everywhere before Swich
reviews it.

**The adapter came back from D41, not rewritten.** The Pay In half of the
Swich adapter built and checked against Swich's real sandbox in D41 (hosted
checkout URL, checksum formulas, callback verification) was restored from
git history as `payments/swich.py`, with its documented formulas unchanged.
Its Payout half was not: the IBFT bank-code question D41 left open is still
open, so payouts and refunds stay operator-sent and are recorded in the
admin console (D54).

**The callback is the only thing that funds.** Paying now creates a
`Charge` (one attempt; a declined card is retried with a new one) and sends
the buyer to Swich. Nothing is held until Swich's server-to-server callback
arrives with a checksum only the merchant SecretKey can produce, compared in
constant time. It then funds the milestone (an `EscrowFunding` created
already confirmed), opens the order to its seller, raises the gig's order
count, or starts the plan, once: a repeated callback is a no-op, a
different amount is logged and funds nothing, and money arriving for an
order cancelled in the meantime is recorded as a refund owed. The page the
buyer returns to only reads that record.

**Orders now wait to be paid.** `Order.Status.AWAITING_PAYMENT` holds an
order between checkout and Swich's confirmation. Its seller does not see
it; its buyer can pay again or cancel with nothing to refund; the hourly
sweep closes it after `UNPAID_ORDER_HOURS` (48). Milestones keep their
existing `pending` state for the same wait, and a plan simply starts on
payment.

**Off until the merchant account is live.** `SWICH_ENABLED`, the keys and
`SWICH_ENV` (Swich's own sandbox or production, independent of this
server's environment) gate everything. With them unset, checkout lists the
methods and says card and wallet payments are opening shortly; no order is
placed and nothing is charged. That is what the live site shows until the
keys are added.

**What changed around it.** The platform bank account settings and the
bank-transfer panel are gone. Terms, Refund, Delivery, Privacy (Swich named
as the payment processor) and Contact pages say how payment works now, and
the legal documents move to version 2026-09-27, so existing members accept
them again. Refunds go back to the card or wallet paid with. The admin
console's Payments in lists Swich payments as received automatically; its
to-do queue now holds only payments an admin recorded by hand. The mobile
app still speaks the old bank-transfer API and needs its pay screens
pointed at the Swich checkout before its next release.

Tests pay the way production does, by delivering a correctly signed
callback with a test key (`payments/testing.py`), so every order, milestone
and plan in the suite goes through the real verification path.

---

## Not mine to take

These need a legal identity, a signature, a personal relationship, or an
external engagement neither of us can substitute for.

1. ~~**Engage a corporate lawyer** on the escrow question in D8.~~ **Done** —
   confirmed by the client (2026-08-14). No engineering artifact exists for
   this; it is a business/legal fact taken on the client's word, not
   something verified from this repo.
2. ~~**Register the company.**~~ **Done, in Pakistan** — confirmed by the
   client (2026-08-14). This narrows item 3: Stripe does not operate in
   Pakistan at all, so Stripe Connect is off the table unless a *second*,
   foreign entity is registered specifically to route payment through it.
3. ~~**Choose the payment rails.**~~ **Done — Swich**, a Pakistan-native
   platform whose `Payouts API` and `Payment Gateway` cover both halves of
   escrow without a second entity (D41) — **then removed at the client's
   direction** over its production account's NTN requirement, replaced
   with a custodial bank-transfer model that automates neither collection
   nor payout (D42). **Revisited (2026-09):** the operator now has an NTN
   and is re-applying to Swich; D48's public checkout and policy pages
   are what its review asked for. Wiring the gateway back in waits on
   that merchant account.
4. ~~**Buy the domain** in D1.~~ **Done** — `skilrize.com`, live on
   Oracle Cloud.
5. **Confirm or override the launch campus** in D4.
6. **Recruit the seed cohort** — roughly 30 committed student sellers and one
   moderator at one campus. Phase 4 shipped the portals; this is what puts
   anybody inside them, and it remains the single highest-risk item in the
   whole plan.
7. **Penetration testing, load testing, and a legal/compliance review of
   what Phase 11 hardened** (D37). A pen test needs an authorized third
   party engaged to attack the live system, not a self-review; a load test
   needs real traffic infrastructure and a target concurrency figure nobody
   has set yet; a compliance review needs the lawyer engaged in item 1,
   now that they exist. External monitoring dashboards (uptime, on-call
   paging) are the same shape — configuring an account with a provider,
   not a code change. `SENTRY_DSN`, `SECURE_HSTS_SECONDS`, and the rest of
   D37 are the code-side half of "hardened"; this is the half that was
   never going to be.
8. **Have a lawyer review the Terms, Privacy, Refund and Delivery
   policies** (D47, D48). They describe what the code does accurately, but
   liability limits, governing law and consumer-protection wording are a
   lawyer's call, not an engineer's.
9. **Configure the production bank account and set real prices.**
   `PLATFORM_BANK_NAME`, `PLATFORM_BANK_ACCOUNT_TITLE` and
   `PLATFORM_BANK_ACCOUNT_NUMBER` in the server's `production.env` —
   funding refuses until they exist (D46) — and the storefront's
   placeholder package prices (D48).

---

## Engineering debt worth naming

Not decisions, but known gaps recorded so they are not rediscovered as
surprises:

- **Ranking and reputation weights are unfitted** (D20), and will stay that way
  until Phase 3 produces transaction history.
- **Group chat is polled, not pushed.** The read model is what a socket would
  need, so this is a delivery change rather than a schema change.
- **Liveness check** for student verification was specified as optional in the
  roadmap and is not built.
- **Elite advertises workspaces that are not gated.** `WorkspaceViewSet`
  applies no entitlement check, so any account can open a shared workspace
  while the tier copy sells it. The copy and the enforcement should agree —
  which way is a pricing call, not an engineering one.
- **A "coming in a future phase" UI label is a debt the moment the phase
  ships.** The dashboard's campus card read "Arriving in Phase 4" as a
  disabled button well after Phase 4's verification flow was live at
  `/settings` — found only because a real account went looking for it and hit
  a dead end. Fixed here by linking through, but the general failure mode is
  worth naming: nothing in the build re-checks a phase-gated label against
  what has actually shipped, so the next one will drift the same way unless
  someone happens to notice.
- **No browser-side error tracking** (D37). `sentry-sdk` covers the API and
  the Celery worker; `@sentry/nextjs` needs source-map upload credentials
  and build-time config this session did not have a safe way to add without
  risking the production build. A client-side exception today is visible
  only if the person hitting it reports it.
- **`api/challenges/admin.py`, `grading.py`, `models.py`, `tests.py`,
  `views.py`, and `core/tasks.py` fail `ruff check .` as written** — found
  verifying Phase 10 (D36) against CI-exact settings, still true after
  Phase 11. Pre-existing lint debt from the Phase 13 build, in files neither
  phase touched; flagged as its own task rather than folded into an
  unrelated commit twice now.
- **No `CELERY_BEAT_SCHEDULE` exists anywhere in this codebase.**
  `sweep_promotions`, `sweep_challenge_deadlines`, and now
  `sweep_activity_sources` (D36) are each complete, correct periodic tasks
  with nothing that ever calls them on a timer — `django_celery_beat` is
  installed and configured as the scheduler, but no `PeriodicTask`/
  `IntervalSchedule` rows exist. One piece of missing infrastructure, not
  three separate gaps.
- **`api/challenges` and `api/core/tasks.py` fail the CI lint step as
  written**, discovered while verifying Phase 10 against CI-exact settings
  (D36) — `ruff check .` reports pre-existing `E501`/`S607`/`B015` violations
  in files this phase never touched. Not fixed here to keep the commit to its
  own scope; flagged as a separate task.
