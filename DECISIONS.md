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
devices is a one-line change if that friction proves too high.

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

## Not mine to take

These need a legal identity, a signature, or a personal relationship. Nothing
here has moved since the log was opened, and all of it now sits on the critical
path rather than ahead of it — Phase 3 is deferred *because* of items 1–3, and
Phase 4 has shipped without the cohort in item 6.

1. **Engage a corporate lawyer** on the escrow question in D8. Slowest item on
   the board, and now the binding constraint: everything built after Phase 2 is
   sitting on a marketplace that cannot take money.
2. **Register the company.** Gates the merchant accounts, which gate Phase 3.
3. **Choose the payment rails.** The report assumed JazzCash and Easypaisa.
   Stripe was raised later and researched: **Stripe does not operate in
   Pakistan**, and the product that makes escrow legally simple (Connect) cannot
   pay Pakistani sellers at all. Global Payouts can reach Pakistan but pushes
   the licensing burden back onto us. Three routes — local rails, a foreign
   entity, or a hybrid — and the choice changes the architecture, not just the
   adapter.
4. **Buy the domain** in D1.
5. **Confirm or override the launch campus** in D4.
6. **Recruit the seed cohort** — roughly 30 committed student sellers and one
   moderator at one campus. Phase 4 shipped the portals; this is what puts
   anybody inside them, and it remains the single highest-risk item in the
   whole plan.

---

## Engineering debt worth naming

Not decisions, but known gaps recorded so they are not rediscovered as
surprises:

- **An admin cannot enrol 2FA through the product.** Administrative roles
  cannot hold a session without a second factor, and cannot reach enrolment
  without a session. A locked-out admin currently needs a database-level fix.
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
