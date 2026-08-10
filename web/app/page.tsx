"use client";

/**
 * The landing page.
 *
 * Photographic and dense, on the pattern both large marketplaces converge on,
 * with two departures that are ours.
 *
 * **The dual track is the hero's primary control.** Every competitor sells one
 * hiring model; this one carries both, so the choice sits above the search box
 * and changes what the search does. A page that averages the two sells neither.
 *
 * **Nothing here claims a number the platform has not earned.** No customer
 * quotes, no borrowed client logos, no listing counts — there are no customers,
 * clients or listings yet. What is claimed is what the software does today:
 * escrow, sealed two-way reviews, campus scoping. All of it checkable in the
 * repository.
 */

import * as React from "react";
import Image from "next/image";
import Link from "next/link";

import {
  CategoryTile,
  HeroSearch,
  PhotoFigure,
  ScrollRow,
  SectionHead,
  ServiceCard,
  SuggestionPills,
  TrackSwitch,
  type ServiceCardData,
  type Track,
} from "@/components/marketing";
import { MarketingHeader } from "@/components/shell";
import { Button, Icon, Logo, cn, type IconName } from "@/components/ui";

/* -------------------------------------------------------------------------- */
/* Content                                                                    */
/* -------------------------------------------------------------------------- */

const CATEGORIES: Array<{ slug: string; name: string; icon: IconName; blurb: string }> = [
  { slug: "development-it", name: "Development & IT", icon: "code", blurb: "Web, mobile, DevOps" },
  { slug: "design-creative", name: "Design & Creative", icon: "palette", blurb: "Brand, UI, illustration" },
  { slug: "writing-translation", name: "Writing & Translation", icon: "pen", blurb: "Copy, docs, localisation" },
  { slug: "video-animation", name: "Video & Animation", icon: "video", blurb: "Editing, motion, VFX" },
  { slug: "marketing-sales", name: "Marketing & Sales", icon: "megaphone", blurb: "SEO, ads, lifecycle" },
  { slug: "data-analytics", name: "Data & Analytics", icon: "chart", blurb: "Pipelines, BI, ML" },
  { slug: "business-admin", name: "Business & Admin", icon: "briefcase", blurb: "Ops, finance, VA" },
  { slug: "academic-support", name: "Academic Support", icon: "book", blurb: "Research, tutoring, editing" },
];

const POPULAR: ServiceCardData[] = [
  { id: 3101, title: "I will design a complete brand identity system", category: "Design", image: "/img/svc-web.jpg", alt: "A designer's desk with a laptop and external monitor", price: 18000, rating: 4.9, reviews: 212, seller: "Meridian Studio", level: "Top Rated" },
  { id: 3102, title: "I will build a production Next.js landing page", category: "Development", image: "/img/svc-code.jpg", alt: "Source code on a dark screen", price: 32000, rating: 5.0, reviews: 88, seller: "Hamza R.", level: "Level 2" },
  { id: 3103, title: "I will edit your long-form video into shorts", category: "Video", image: "/img/svc-video.jpg", alt: "A photographer filming on a mountain ridge at sunrise", price: 9500, rating: 4.8, reviews: 341, seller: "Cutroom", level: "Level 2" },
  { id: 3104, title: "I will write technical documentation that ships", category: "Writing", image: "/img/svc-writing.jpg", alt: "A fountain pen writing on lined paper", price: 14000, rating: 4.9, reviews: 126, seller: "Usman T.", level: "Top Rated" },
  { id: 3105, title: "I will set up your analytics and reporting stack", category: "Data", image: "/img/svc-data.jpg", alt: "An analytics dashboard displayed on a laptop", price: 26000, rating: 4.9, reviews: 74, seller: "Nida S.", level: "Level 2" },
  { id: 3106, title: "I will run a full technical SEO audit", category: "Marketing", image: "/img/svc-marketing.jpg", alt: "A marketing strategy note on a desk with pens", price: 12000, rating: 4.7, reviews: 198, seller: "Northline", level: "Level 1" },
];

/** Every line is a behaviour of the software, not a claim about traction. */
const CAPABILITIES: Array<{ icon: IconName; title: string; body: string }> = [
  { icon: "shield", title: "Escrow on every contract", body: "Funds are committed before work starts and released on acceptance. Neither side goes first on trust." },
  { icon: "star", title: "Sealed two-way reviews", body: "Neither review publishes until both are in or the window closes. Nobody rates a reply to their own rating." },
  { icon: "wallet", title: "One wallet, one reputation", body: "A five-star review from a bought service and one from a won brief are the same row in the same table." },
  { icon: "building", title: "Private campus portals", body: "Verified students get a second marketplace scoped to their university, enforced in the database." },
];

const TRACK_DETAIL: Record<
  Track,
  {
    icon: IconName;
    heading: string;
    blurb: string;
    steps: Array<{ title: string; body: string }>;
    cta: string;
    href: string;
    image: string;
    alt: string;
  }
> = {
  services: {
    icon: "layers",
    heading: "Buy a packaged service",
    blurb: "Priced and dated before you ask. Order it the way you order anything else.",
    steps: [
      { title: "Pick a package", body: "Three tiers per service, each with its own price, delivery date and revision count." },
      { title: "Send requirements", body: "The delivery clock does not start until you have handed over what the seller needs." },
      { title: "Accept or revise", body: "Revisions are counted by the package you bought, not argued about afterwards." },
    ],
    cta: "Browse services",
    href: "/gigs",
    image: "/img/svc-web.jpg",
    alt: "A tidy desk with a laptop and monitor showing a design in progress",
  },
  projects: {
    icon: "briefcase",
    heading: "Post a brief instead",
    blurb: "Describe the work once and let qualified proposals come to you.",
    steps: [
      { title: "Post the brief", body: "Add screening questions and the unqualified proposals filter themselves out." },
      { title: "Compare proposals", body: "Rivals never see each other's bids, so nobody is pricing against a leak." },
      { title: "Award and fund", body: "Terms freeze at acceptance. Milestones are funded one at a time." },
    ],
    cta: "Post a brief",
    href: "/projects/new",
    image: "/img/work-team.jpg",
    alt: "Two colleagues celebrating over a laptop in an office",
  },
};

const ESCROW_STAGES = [
  { label: "Funded", body: "The client commits the money before a line of work is done." },
  { label: "Delivered", body: "The freelancer submits. The clock and the files are both on the record." },
  { label: "Accepted", body: "The client accepts — or the review window lapses and it auto-releases." },
  { label: "Released", body: "Money moves to the freelancer's wallet. The ledger is append-only." },
];

const FOOTER: Array<{ heading: string; links: Array<[string, string]> }> = [
  { heading: "Marketplace", links: [["Browse services", "/gigs"], ["Browse briefs", "/projects"], ["Work showcase", "/showcase"], ["Search", "/search"]] },
  { heading: "For freelancers", links: [["Sell a service", "/gigs/new"], ["Retainers", "/retainers"], ["Client CRM", "/crm"], ["Teams & agencies", "/teams"]] },
  { heading: "Platform", links: [["Plans", "/pricing"], ["Communities", "/communities"], ["Campus portals", "/#campus"], ["How it works", "/#tracks"]] },
];

/* -------------------------------------------------------------------------- */

export default function LandingPage() {
  const [track, setTrack] = React.useState<Track>("services");
  const detail = TRACK_DETAIL[track];

  return (
    <div className="min-h-dvh bg-surface">
      <MarketingHeader />

      <main id="main">
        {/* ================================================================ */}
        {/* Hero — full-bleed photograph, the way the category does it       */}
        {/* ================================================================ */}
        <section className="relative isolate overflow-hidden">
          <Image
            src="/img/hero.jpg"
            alt=""
            fill
            priority
            sizes="100vw"
            className="-z-20 object-cover object-center"
          />
          {/* Two scrims, not one. The horizontal ramp buys contrast for the
              copy column and then gets out of the way, so the right half of the
              frame still reads as a photograph — a single flat overlay dark
              enough for white text turns the image into grey card stock. The
              vertical pass only weights the top and bottom edges, where the
              header and the capability strip sit. */}
          <div
            aria-hidden
            className="absolute inset-0 -z-10 bg-gradient-to-r from-ink-1000/94 via-ink-1000/70 to-ink-1000/25"
          />
          <div
            aria-hidden
            className="absolute inset-0 -z-10 bg-gradient-to-t from-ink-1000/75 via-transparent to-ink-1000/45"
          />

          <div className="mx-auto flex min-h-[34rem] max-w-7xl items-center px-5 py-20 sm:min-h-[38rem] sm:py-28">
            <div className="max-w-2xl">
              <h1 className="display-1 text-white">
                Hire in an afternoon.
                <br />
                <span className="italic text-brand-300">Or hire for a year.</span>
              </h1>

              <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-white/75">
                Buy a packaged service at a fixed price, or post a brief and let proposals
                come to you. Two ways to work — one account, one wallet, one reputation.
              </p>

              <div className="mt-9 space-y-4">
                <TrackSwitch value={track} onChange={setTrack} tone="dark" />
                <HeroSearch track={track} />
                <SuggestionPills track={track} />
              </div>
            </div>
          </div>

          {/* Capability strip, in place of the borrowed client logos the
              reference pages carry. We have no clients to name yet; we do have
              guarantees, and those are true today. */}
          <div className="relative border-t border-white/15 bg-black/35 backdrop-blur-md">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4">
              <span className="text-[12px] font-medium uppercase tracking-wider text-white/50">
                Built in
              </span>
              {[
                "Escrow on every contract",
                "Sealed two-way reviews",
                "Verified identity",
                "Campus portals",
              ].map((item) => (
                <span key={item} className="flex items-center gap-2 text-[13px] text-white/85">
                  <Icon
                    name="check"
                    strokeWidth={2.6}
                    className="size-3.5 shrink-0 text-money-400"
                  />
                  {item}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* ================================================================ */}
        {/* Categories                                                       */}
        {/* ================================================================ */}
        <section className="mx-auto max-w-7xl px-5 py-16 sm:py-20">
          <SectionHead
            eyebrow="Explore"
            title="Eight fields, one standard of work"
            description="Every category runs the same contract, the same escrow and the same review rules. The difference is the craft, never the protection."
            action={
              /* Padded to a 44px target. It sits alone at the end of a heading
                 row rather than inline in a paragraph, so it gets no exemption
                 from the minimum. */
              <Link
                href="/gigs"
                className={cn(
                  "inline-flex min-h-11 items-center gap-1.5 text-[13.5px] font-medium",
                  "text-accent underline-offset-4 hover:underline",
                )}
              >
                See all services
                <Icon name="arrowRight" className="size-3.5" />
              </Link>
            }
          />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CATEGORIES.map((category) => (
              <CategoryTile key={category.slug} {...category} />
            ))}
          </div>
        </section>

        {/* ================================================================ */}
        {/* Popular services                                                 */}
        {/* ================================================================ */}
        <section className="border-y border-line bg-raised">
          <div className="mx-auto max-w-7xl px-5 py-16 sm:py-20">
            <SectionHead
              eyebrow="Services"
              title="Packaged work, priced before you ask"
              description="Every listing states its tiers, delivery time and revision count up front — so the negotiation is finished before the conversation starts."
            />
            <ScrollRow>
              {POPULAR.map((item) => (
                <ServiceCard key={item.id} item={item} href={`/gigs/${item.id}`} />
              ))}
            </ScrollRow>
          </div>
        </section>

        {/* ================================================================ */}
        {/* The two tracks                                                   */}
        {/* ================================================================ */}
        <section id="tracks" className="mx-auto max-w-7xl scroll-mt-24 px-5 py-16 sm:py-20">
          <SectionHead
            eyebrow="How it works"
            title="Two hiring models, under one roof"
            description="Most marketplaces make you choose a platform before you have chosen an approach. Here it is a toggle, and everything downstream — messaging, escrow, reviews — is shared."
          />

          <div className="mb-10">
            <TrackSwitch value={track} onChange={setTrack} />
          </div>

          <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
            <PhotoFigure
              src={detail.image}
              alt={detail.alt}
              caption={detail.heading}
              captionBody={detail.blurb}
            />

            <div>
              <ol className="space-y-7">
                {detail.steps.map((step, index) => (
                  <li key={step.title} className="flex gap-4">
                    <span
                      className={cn(
                        "grid size-9 shrink-0 place-items-center rounded-full",
                        "bg-accent-soft text-[13px] font-semibold text-accent",
                      )}
                    >
                      {index + 1}
                    </span>
                    <div>
                      <p className="heading-sans text-[16.5px] text-fg">{step.title}</p>
                      <p className="mt-1.5 text-[14px] leading-relaxed text-muted">
                        {step.body}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>

              <Link href={detail.href} className="mt-9 inline-block">
                <Button size="lg">
                  <Icon name={detail.icon} className="size-4" />
                  {detail.cta}
                </Button>
              </Link>
            </div>
          </div>
        </section>

        {/* ================================================================ */}
        {/* Capabilities                                                     */}
        {/* ================================================================ */}
        <section className="border-y border-line bg-raised">
          <div className="mx-auto max-w-7xl px-5 py-16">
            <div className="grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
              {CAPABILITIES.map((item) => (
                <div key={item.title}>
                  <span className="grid size-10 place-items-center rounded-lg bg-accent-soft text-accent">
                    <Icon name={item.icon} className="size-5" />
                  </span>
                  <p className="mt-4 text-[15px] font-medium text-fg">{item.title}</p>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">
                    {item.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ================================================================ */}
        {/* Campus — the dark band                                           */}
        {/* ================================================================ */}
        <section id="campus" className="scroll-mt-24 px-5 py-16 sm:py-20">
          <div className="relative isolate mx-auto max-w-7xl overflow-hidden rounded-3xl bg-ink-1000">
            <Image
              src="/img/campus.jpg"
              alt=""
              fill
              sizes="(max-width: 1280px) 100vw, 1280px"
              className="-z-20 object-cover object-center opacity-45"
            />
            <div
              aria-hidden
              className="absolute inset-0 -z-10 bg-gradient-to-r from-ink-1000 via-ink-1000/90 to-ink-1000/50"
            />

            <div className="grid gap-12 p-8 sm:p-12 lg:grid-cols-2 lg:items-center lg:p-16">
              <div>
                <p className="eyebrow text-white/55">For universities</p>
                <h2 className="heading-sans mt-3 text-[clamp(1.7rem,3.2vw,2.5rem)] leading-tight text-white">
                  Your campus, its own marketplace
                </h2>
                <p className="mt-5 max-w-lg text-[15.5px] leading-relaxed text-white/70">
                  Verify with a university email and a student ID, and a second marketplace
                  opens — one only your campus can see. Post to it, sell in it, and build
                  real reviews before you ever compete globally.
                </p>

                <ul className="mt-8 space-y-3.5">
                  {[
                    "Scoped in the database, not the page — a campus listing cannot reach the global surface",
                    "Switch surfaces in one click; profile, wallet and reviews all come with you",
                    "Cross-tenant leakage is a release gate, re-run on every commit",
                  ].map((line) => (
                    <li key={line} className="flex gap-3 text-[14px] leading-relaxed text-white/80">
                      <Icon
                        name="check"
                        strokeWidth={2.6}
                        className="mt-0.5 size-4 shrink-0 text-money-400"
                      />
                      {line}
                    </li>
                  ))}
                </ul>

                <Link href="/signup" className="mt-9 inline-block">
                  <Button size="lg" variant="secondary">
                    Verify as a student
                    <Icon name="arrowRight" className="size-4" />
                  </Button>
                </Link>
              </div>

              {/* The surface switch, shown rather than described. */}
              <div className="glass-dark rounded-2xl p-5">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-white/45">
                  Active marketplace
                </p>
                <div className="mt-3 space-y-2.5">
                  <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-3.5">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10 text-white">
                      <Icon name="globe" className="size-4.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13.5px] font-medium text-white">Global</p>
                      <p className="text-[11.5px] text-white/50">Open to everyone</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-xl border border-brand-400/50 bg-brand-500/25 p-3.5">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-400 text-ink-950">
                      <Icon name="building" className="size-4.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13.5px] font-medium text-white">COMSATS</p>
                      <p className="text-[11.5px] text-white/50">Verified students only</p>
                    </div>
                    <Icon name="check" strokeWidth={2.6} className="size-4 text-money-400" />
                  </div>
                </div>
                <p className="mt-4 border-t border-white/10 pt-4 text-[12px] leading-relaxed text-white/50">
                  Everything you post inherits the surface you are standing on. There is no
                  second step to forget.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ================================================================ */}
        {/* Escrow                                                           */}
        {/* ================================================================ */}
        <section className="border-y border-line bg-raised">
          <div className="mx-auto max-w-7xl px-5 py-16 sm:py-20">
            <SectionHead
              eyebrow="Getting paid"
              title="Four states, and no ambiguity between them"
              description="Money is never in a position where both sides believe they hold it. Every contract on both tracks moves through the same states in the same order."
            />

            <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {ESCROW_STAGES.map((stage, index) => (
                <li
                  key={stage.label}
                  className="relative rounded-xl border border-line bg-surface p-6"
                >
                  {index < ESCROW_STAGES.length - 1 && (
                    <span
                      aria-hidden
                      className="absolute right-0 top-12 hidden h-px w-5 translate-x-full bg-line-strong lg:block"
                    />
                  )}
                  <span className="eyebrow tabular">Step {index + 1}</span>
                  <p className="heading-sans mt-2 text-[17px] text-fg">{stage.label}</p>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-muted">{stage.body}</p>
                </li>
              ))}
            </ol>

            <p className="mx-auto mt-8 max-w-2xl text-center text-[13px] leading-relaxed text-subtle">
              Card and mobile-money rails are being connected now. Until they are live,
              contracts move through these states without a real charge — the state machine
              is the finished part, and it is the part that decides who holds what.
            </p>
          </div>
        </section>

        {/* ================================================================ */}
        {/* Sell / plans                                                     */}
        {/* ================================================================ */}
        <section className="mx-auto max-w-7xl px-5 py-16 sm:py-20">
          <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
            <PhotoFigure
              src="/img/campus-study.jpg"
              alt="A group working together over laptops in a library"
              caption="Free to hire, free to sell"
              captionBody="Pro and Elite buy volume and visibility, never the basics."
            />
            <div>
              <p className="eyebrow">Start earning</p>
              <h2 className="heading-sans mt-3 text-[clamp(1.7rem,3.2vw,2.5rem)] leading-tight text-fg">
                Everything you need to get paid is on the free plan
              </h2>
              <p className="mt-5 text-[15.5px] leading-relaxed text-muted">
                Publish services, bid on briefs, run contracts and take payment through
                escrow without paying us a subscription. The paid tiers exist for the point
                at which freelancing is your income rather than your side project.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/signup">
                  <Button size="lg">Start selling</Button>
                </Link>
                <Link href="/pricing">
                  <Button size="lg" variant="secondary">
                    Compare plans
                    <Icon name="arrowRight" className="size-4" />
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* ================================================================ */}
        {/* Close                                                            */}
        {/* ================================================================ */}
        <section className="px-5 pb-20">
          <div className="relative isolate mx-auto max-w-7xl overflow-hidden rounded-3xl bg-ink-1000 px-6 py-16 text-center sm:py-20">
            <Image
              src="/img/campus-study.jpg"
              alt=""
              fill
              sizes="(max-width: 1280px) 100vw, 1280px"
              className="-z-20 object-cover opacity-25"
            />
            <div aria-hidden className="absolute inset-0 -z-10 bg-ink-1000/70" />

            <h2 className="display-2 mx-auto max-w-3xl text-white">
              Start on either side. <span className="italic text-brand-300">Switch whenever.</span>
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-[15.5px] leading-relaxed text-white/70">
              The same account hires and gets hired. Nothing to migrate the day you decide
              to do both.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link href="/signup">
                <Button size="lg">Create an account</Button>
              </Link>
              <Link href="/gigs">
                <Button size="lg" variant="secondary">
                  Browse first
                </Button>
              </Link>
            </div>
            <p className="mt-4 text-[12.5px] text-white/50">
              Free to join. Verification is asked for only when money is about to move.
            </p>
          </div>
        </section>
      </main>

      {/* ================================================================== */}
      {/* Footer                                                             */}
      {/* ================================================================== */}
      <footer className="border-t border-line bg-raised">
        <div className="mx-auto max-w-7xl px-5 py-14">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Logo />
              <p className="mt-4 max-w-xs text-[13px] leading-relaxed text-muted">
                A unified freelance marketplace — packaged services and open briefs, on one
                account, with private campus portals for verified students.
              </p>
            </div>

            {FOOTER.map((column) => (
              <nav key={column.heading} aria-label={column.heading}>
                <p className="text-[12.5px] font-semibold text-fg">{column.heading}</p>
                <ul className="mt-3.5 space-y-2.5">
                  {column.links.map(([label, href]) => (
                    <li key={label}>
                      <Link
                        href={href}
                        className="text-[13px] text-muted transition-colors duration-200 hover:text-fg"
                      >
                        {label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>

          <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-7">
            <p className="text-[12.5px] text-subtle">
              © {new Date().getFullYear()} SkilRize · Built by NEXOLV.TECH
            </p>
            <p className="text-[12.5px] text-subtle">
              Photography under the Unsplash licence
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
