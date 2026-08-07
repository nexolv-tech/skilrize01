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

## Not mine to take

These need a legal identity, a signature, or a personal relationship:

1. **Engage a corporate lawyer** on the escrow question in D8. Slowest item on
   the board; start regardless of how far away Phase 3 feels.
2. **Register the company.** Gates the merchant accounts, which gate Phase 3.
3. **Open JazzCash and Easypaisa merchant accounts.** Weeks of lead time, and
   they require the registered entity to exist first.
4. **Buy the domain** in D1.
5. **Confirm or override the launch campus** in D4.
6. **Recruit the seed cohort** — roughly 30 committed student sellers and one
   moderator at one campus, before Phase 4 opens. This is relationship work,
   and it is the single highest-risk item in the whole plan.
