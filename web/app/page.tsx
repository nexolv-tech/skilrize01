"use client";

/**
 * The landing page.
 *
 * Its job is to get a visitor to trust the platform with money. So the hero
 * does not describe the product in the abstract; it shows the escrow slip —
 * an order moving from paid, to delivered, to approved, to released — with
 * the fee printed on it. The rest of the page answers the next questions in
 * the order people ask them: what can I buy, how does it work, where is my
 * money, and who is behind this.
 *
 * **Nothing here claims traction the platform has not earned.** No invented
 * reviews, no borrowed logos, no listing counts: the services shown are the
 * live catalogue, fetched from the API, and the section hides itself when the
 * catalogue is empty. An earlier version carried six hard-coded "featured"
 * services with made-up ratings, linking to gigs that did not exist.
 */

import * as React from "react";
import Image from "next/image";
import Link from "next/link";

import {
  CategoryTile,
  EscrowTicket,
  FaqItem,
  GigCard,
  HeroSearch,
  SectionHead,
  SuggestionPills,
  TrackSwitch,
  type Track,
} from "@/components/marketing";
import { MarketingHeader } from "@/components/shell";
import { SiteFooter } from "@/components/site-footer";
import { ButtonLink, Icon, Skeleton, type IconName } from "@/components/ui";
import { gigs } from "@/lib/api";
import { BUSINESS } from "@/lib/business";
import { useLoader } from "@/lib/session";

const CATEGORIES: Array<{ slug: string; name: string; icon: IconName; examples: string }> = [
  { slug: "development-it", name: "Development & IT", icon: "code", examples: "Websites, mobile apps, APIs, DevOps" },
  { slug: "design-creative", name: "Design & Creative", icon: "palette", examples: "Logos, UI/UX, illustration" },
  { slug: "writing-translation", name: "Writing & Translation", icon: "pen", examples: "Copywriting, documentation, translation" },
  { slug: "video-animation", name: "Video & Animation", icon: "video", examples: "Editing, motion graphics, subtitles" },
  { slug: "marketing-sales", name: "Marketing & Sales", icon: "megaphone", examples: "SEO, social media, paid ads" },
  { slug: "data-analytics", name: "Data & Analytics", icon: "chart", examples: "Dashboards, analysis, machine learning" },
  { slug: "business-admin", name: "Business & Admin", icon: "briefcase", examples: "Virtual assistance, bookkeeping" },
  { slug: "academic-support", name: "Academic Support", icon: "book", examples: "Tutoring, research help, study notes" },
];

const FACTS: Array<{ icon: IconName; title: string; body: string }> = [
  { icon: "shield", title: "Payment held in escrow", body: "Released only when you approve" },
  { icon: "wallet", title: "Full refund on cancellation", body: "Sent back to your account" },
  { icon: "id", title: "Verified identities", body: "Email and CNIC checked" },
  { icon: "building", title: "Campus portals", body: "Private to verified students" },
];

const STEPS: Record<"hire" | "sell", Array<{ title: string; body: string }>> = {
  hire: [
    { title: "Choose a service, or post a brief", body: "Services have fixed prices and delivery times. Briefs collect proposals you can compare." },
    { title: "Pay into escrow", body: "Your payment is held by SkilRize. The freelancer can see it is secured before starting." },
    { title: "Share what's needed", body: "Answer the seller's questions. The delivery clock starts only once you have." },
    { title: "Approve, and the payment is released", body: "Accept the delivery or ask for a revision. Nothing is released until you approve." },
  ],
  sell: [
    { title: "Create a free account and verify it", body: "Confirm your email and CNIC once. Buyers see you are verified." },
    { title: "List a service or send proposals", body: "Price your work in three packages, or bid on briefs that match your skills." },
    { title: "Deliver the work", body: "Every order is funded before you start, so you never work on a promise." },
    { title: "Get paid to your bank account", body: "When the client approves, your payment is released minus the platform fee." },
  ],
};

const noSubscription = () => () => {};

/** Shown once, after Settings → Privacy & data erased the account and sent
 *  the visitor here. */
function AccountDeletedNotice() {
  const deleted = React.useSyncExternalStore(
    noSubscription,
    () => new URLSearchParams(window.location.search).get("account") === "deleted",
    () => false,
  );
  if (!deleted) return null;
  return (
    <div role="status" className="border-b border-line bg-positive-soft">
      <p className="mx-auto max-w-7xl px-5 py-3 text-[14px] text-fg">
        Your account has been deleted and you have been signed out. Thank you for using SkilRize.
      </p>
    </div>
  );
}

export default function LandingPage() {
  const [track, setTrack] = React.useState<Track>("services");
  const { data: live, loading } = useLoader(() => gigs.list({ sort: "newest", page_size: 8 }), []);
  const services = live?.results ?? [];

  return (
    <div className="min-h-dvh bg-surface">
      <MarketingHeader />
      <AccountDeletedNotice />

      <main id="main">
        {/* ============================================================ */}
        {/* Hero                                                          */}
        {/* ============================================================ */}
        <section className="border-b border-line">
          <div className="mx-auto grid max-w-7xl items-center gap-14 px-5 py-16 sm:py-20 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16 lg:py-24">
            <div className="animate-rise">
              <p className="eyebrow">Freelance marketplace · Pakistan</p>
              <h1 className="display-xl mt-5 max-w-[13ch]">
                Hire skilled freelancers. Pay only when the work is approved.
              </h1>
              <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-muted">
                Buy a fixed-price service, or post a brief and compare proposals. Your payment
                waits in escrow until you accept the delivery — and comes back to you if the order
                is cancelled.
              </p>

              <div className="mt-9 max-w-xl space-y-4">
                <TrackSwitch value={track} onChange={setTrack} />
                <HeroSearch track={track} />
                <SuggestionPills track={track} />
              </div>
            </div>

            <EscrowTicket className="mx-auto w-full max-w-md lg:mx-0" />
          </div>

          <div className="border-t border-line bg-raised">
            <ul className="mx-auto grid max-w-7xl gap-px bg-line sm:grid-cols-2 lg:grid-cols-4">
              {FACTS.map((fact) => (
                <li key={fact.title} className="flex items-start gap-3 bg-raised px-5 py-5">
                  <Icon name={fact.icon} className="mt-0.5 size-5 shrink-0 text-accent" />
                  <span>
                    <span className="block text-[14px] font-semibold text-fg">{fact.title}</span>
                    <span className="block text-[13px] text-subtle">{fact.body}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ============================================================ */}
        {/* Live services                                                 */}
        {/* ============================================================ */}
        {(loading || services.length > 0) && (
          <section className="mx-auto max-w-7xl px-5 py-16 sm:py-20">
            <SectionHead
              eyebrow="Available now"
              title="Services you can order today"
              description="Every listing states its price, delivery time and number of revisions before you order — so there is nothing left to negotiate."
              action={
                <ButtonLink href="/gigs" variant="secondary">
                  Browse all services
                  <Icon name="arrowRight" className="size-4" />
                </ButtonLink>
              }
            />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {loading
                ? Array.from({ length: 4 }, (_, index) => (
                    <Skeleton key={index} className="aspect-[4/5] w-full rounded-lg" />
                  ))
                : services.map((gig) => <GigCard key={gig.id} gig={gig} />)}
            </div>
          </section>
        )}

        {/* ============================================================ */}
        {/* Categories                                                    */}
        {/* ============================================================ */}
        <section className="border-y border-line bg-raised">
          <div className="mx-auto max-w-7xl px-5 py-16 sm:py-20">
            <SectionHead
              eyebrow="Categories"
              title="What you can get done"
              description="Eight fields, one set of rules: every order in every category is funded in escrow and released on approval."
            />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {CATEGORIES.map((category) => (
                <CategoryTile key={category.slug} {...category} />
              ))}
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/* How it works                                                  */}
        {/* ============================================================ */}
        <section id="how-it-works" className="mx-auto max-w-7xl scroll-mt-24 px-5 py-16 sm:py-20">
          <SectionHead
            eyebrow="How it works"
            title="Four steps, whichever side you are on"
          />
          <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
            {(
              [
                ["hire", "If you're hiring"],
                ["sell", "If you're freelancing"],
              ] as const
            ).map(([key, heading]) => (
              <div key={key}>
                <h3 className="text-[18px] font-bold text-fg">{heading}</h3>
                <ol className="mt-6 space-y-6 border-l-2 border-line pl-6">
                  {STEPS[key].map((step, index) => (
                    <li key={step.title} className="relative">
                      <span
                        aria-hidden
                        className="figure absolute -left-[37px] grid size-6 place-items-center rounded-full border-2 border-line bg-surface text-[11px] font-semibold text-fg"
                      >
                        {index + 1}
                      </span>
                      <p className="text-[15.5px] font-semibold text-fg">{step.title}</p>
                      <p className="mt-1 text-[14.5px] leading-relaxed text-muted">{step.body}</p>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </section>

        {/* ============================================================ */}
        {/* Where the money is                                            */}
        {/* ============================================================ */}
        <section id="payments" className="scroll-mt-24 border-y border-line bg-raised">
          <div className="mx-auto max-w-7xl px-5 py-16 sm:py-20">
            <SectionHead
              eyebrow="Payments"
              title="Where your money is, at every step"
              description="The same rules apply to every order and every contract. Nobody can spend a payment while it is in escrow."
            />
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full min-w-[40rem] border-collapse text-left text-[14.5px]">
                <thead className="bg-sunken">
                  <tr>
                    <th scope="col" className="eyebrow px-5 py-3.5 font-medium">When</th>
                    <th scope="col" className="eyebrow px-5 py-3.5 font-medium">Where the money is</th>
                    <th scope="col" className="eyebrow px-5 py-3.5 font-medium">What happens next</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {[
                    ["You place an order", "Held by SkilRize in escrow", "The freelancer starts once you share your requirements."],
                    ["The work is delivered", "Still held in escrow", `You have ${BUSINESS.orderReviewDays} days (services) or ${BUSINESS.contractReviewDays} days (projects) to accept it or ask for a revision.`],
                    ["You accept the work", "Released to the freelancer", `They receive it minus the ${BUSINESS.commissionPercent}% platform fee. You pay nothing extra.`],
                    ["You don't respond in time", "Released automatically", "A delivery nobody answers is accepted when the review window closes, so no payment is held hostage."],
                    ["The order is cancelled", "Refunded to you in full", "Sent back to the account you paid from."],
                  ].map(([when, where, next]) => (
                    <tr key={when}>
                      <th scope="row" className="px-5 py-4 font-semibold text-fg">{when}</th>
                      <td className="px-5 py-4 font-medium text-fg">{where}</td>
                      <td className="px-5 py-4 leading-relaxed text-muted">{next}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-5 max-w-3xl text-[13.5px] leading-relaxed text-subtle">
              Today you pay by bank transfer to {BUSINESS.operator}&apos;s business account. Card,
              JazzCash, easypaisa and Raast payments are being added. Full details are in the{" "}
              <Link href="/refunds" className="font-medium text-accent underline underline-offset-2">
                Refund &amp; Cancellation Policy
              </Link>
              .
            </p>
          </div>
        </section>

        {/* ============================================================ */}
        {/* Campus portals                                                */}
        {/* ============================================================ */}
        <section id="campus" className="scroll-mt-24 px-5 py-16 sm:py-20">
          <div className="mx-auto grid max-w-7xl gap-10 rounded-2xl bg-campus-900 p-8 text-white sm:p-12 lg:grid-cols-[1.2fr_1fr] lg:items-center lg:p-16">
            <div>
              <p className="font-mono text-[11px] font-medium tracking-[0.06em] text-campus-100 uppercase">For university students</p>
              <h2 className="display-lg mt-4">Your university, its own marketplace.</h2>
              <p className="mt-5 max-w-lg text-[16px] leading-relaxed text-campus-100">
                Verify with your university email and student ID, and a second marketplace opens
                that only students of your university can see. Take on your first projects among
                people you can trust, and build real reviews before you compete globally.
              </p>
              <div className="mt-8">
                <ButtonLink href="/signup" size="lg">
                  Create an account
                  <Icon name="arrowRight" className="size-4" />
                </ButtonLink>
              </div>
            </div>
            <ul className="space-y-4">
              {[
                "Listings posted in your campus portal are visible only to verified students of your university.",
                "Your profile, reviews and payments are the same account on both marketplaces.",
                "Students are verified by university email and student ID before they get access.",
              ].map((line) => (
                <li key={line} className="flex gap-3 border-t border-white/15 pt-4 text-[15px] leading-relaxed text-campus-50">
                  <Icon name="check" strokeWidth={2.6} className="mt-1 size-4 shrink-0 text-campus-400" />
                  {line}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ============================================================ */}
        {/* FAQ                                                           */}
        {/* ============================================================ */}
        <section className="mx-auto max-w-4xl px-5 pb-16 sm:pb-20">
          <SectionHead eyebrow="Questions" title="Before you pay anyone" />
          <div className="border-t border-line">
            <FaqItem question="How do payments work?">
              You pay the listed price when you order. SkilRize holds it in escrow — the freelancer
              cannot touch it — until you approve the delivered work. Then it is released to them.
            </FaqItem>
            <FaqItem question="What does SkilRize charge?">
              Buyers pay the listed price with no added fees. Freelancers pay a{" "}
              {BUSINESS.commissionPercent}% platform fee, taken from the payment when it is
              released. Creating an account and listing services is free.
            </FaqItem>
            <FaqItem question="When do I get a refund?">
              If the freelancer cancels, if you cancel before sending your requirements, or if the
              order passes its due date without being delivered, you are refunded in full. See the{" "}
              <Link href="/refunds" className="font-medium text-accent underline underline-offset-2">
                Refund &amp; Cancellation Policy
              </Link>{" "}
              for every case.
            </FaqItem>
            <FaqItem question="How long does delivery take?">
              Every package states its delivery time before you order. The clock starts when you
              submit the freelancer&apos;s requirements, so nobody is held to a deadline they could
              not start on.
            </FaqItem>
            <FaqItem question="Is my personal information safe?">
              Your identity-card and bank details are encrypted, sign-in is protected with optional
              two-factor authentication, and you can download or delete your data at any time from
              your account settings. See the{" "}
              <Link href="/privacy" className="font-medium text-accent underline underline-offset-2">
                Privacy Policy
              </Link>
              .
            </FaqItem>
            <FaqItem question="Who runs SkilRize?">
              SkilRize is operated by {BUSINESS.operator}, a software studio based in{" "}
              {BUSINESS.address.city}, {BUSINESS.address.country}. You can reach us at{" "}
              <a href={`mailto:${BUSINESS.email}`} className="font-medium text-accent underline underline-offset-2">
                {BUSINESS.email}
              </a>{" "}
              or on {BUSINESS.phone}.
            </FaqItem>
          </div>
        </section>

        {/* ============================================================ */}
        {/* Close                                                         */}
        {/* ============================================================ */}
        <section className="px-5 pb-16 sm:pb-20">
          <div className="relative isolate mx-auto max-w-7xl overflow-hidden rounded-2xl border border-white/10 bg-ink-950 px-6 py-16 text-center sm:py-20">
            <Image
              src="/img/campus-study.jpg"
              alt=""
              fill
              sizes="(max-width: 1280px) 100vw, 1280px"
              className="-z-20 object-cover opacity-30 grayscale"
            />
            <div aria-hidden className="absolute inset-0 -z-10 bg-ink-950/75" />

            <h2 className="display-lg mx-auto max-w-3xl text-white">
              Start on either side. <span className="text-brand-400">Switch whenever.</span>
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-[16px] leading-relaxed text-white/75">
              The same account hires and gets hired. Nothing to migrate the day you decide to do
              both.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <ButtonLink href="/signup" size="lg">
                Create an account
              </ButtonLink>
              <ButtonLink href="/gigs" size="lg" variant="inverse">
                Browse first
              </ButtonLink>
            </div>
            <p className="mt-5 text-[12.5px] text-white/55">
              Free to join. Browse without an account; you verify your identity once, when you are
              ready to buy or sell.
            </p>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
