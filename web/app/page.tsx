import Link from "next/link";

import { CoverArt, type Motif } from "@/components/artwork";
import { CategoryTile, HeroBackdrop, HeroSearch, ScrollRow } from "@/components/marketing";
import { MarketingHeader } from "@/components/shell";
import { Badge, Card, Icon, Logo, Stars, cn, type IconName } from "@/components/ui";

/** The hero's catalogue slice. Representative of the eight top categories. */
const SHOWCASE: Array<{ title: string; slug: string; motif: Motif; rating: string; from: string }> =
  [
    { title: "Logo & brand identity", slug: "design-creative", motif: "design", rating: "4.9", from: "8,000" },
    { title: "React & Django builds", slug: "development-it", motif: "code", rating: "5.0", from: "25,000" },
    { title: "Short-form video editing", slug: "video-animation", motif: "video", rating: "4.8", from: "4,500" },
    { title: "SEO & content strategy", slug: "marketing-sales", motif: "marketing", rating: "4.9", from: "6,000" },
  ];

const PROOF: Array<{ icon: IconName; label: string }> = [
  { icon: "lock", label: "Escrow on every contract" },
  { icon: "id", label: "Government ID verified" },
  { icon: "star", label: "Double-blind two-way reviews" },
  { icon: "clock", label: "Auditable hourly time logs" },
  { icon: "building", label: "Private campus marketplaces" },
  { icon: "wallet", label: "Released only when you accept" },
];

/* -------------------------------------------------------------------------- */
/* Page content                                                               */
/* -------------------------------------------------------------------------- */

const CATEGORIES: Array<{ slug: string; name: string; icon: IconName; count: string }> = [
  { slug: "development-it", name: "Development & IT", icon: "code", count: "Web, mobile, cloud" },
  { slug: "design-creative", name: "Design & Creative", icon: "palette", count: "Brand & product" },
  { slug: "writing-translation", name: "Writing & Translation", icon: "pen", count: "Words that land" },
  { slug: "video-animation", name: "Video & Animation", icon: "video", count: "Edit & motion" },
  { slug: "marketing-sales", name: "Marketing & Sales", icon: "megaphone", count: "Growth & demand" },
  { slug: "data-analytics", name: "Data & Analytics", icon: "chart", count: "Insight & models" },
  { slug: "business-admin", name: "Business & Admin", icon: "briefcase", count: "Ops & finance" },
  { slug: "academic-support", name: "Academic Support", icon: "book", count: "Tutoring & research" },
];

const HOW_IT_WORKS = [
  {
    icon: "file" as IconName,
    title: "Say what you need",
    body: "Post a brief with a budget and a few screening questions, or search ready-made services and buy one outright.",
  },
  {
    icon: "users" as IconName,
    title: "Choose who does it",
    body: "Compare proposals, read verified reviews from both sides of past contracts, and interview before you commit.",
  },
  {
    icon: "shield" as IconName,
    title: "Pay only for accepted work",
    body: "Your money is held securely from the moment work starts and released when you accept the delivery.",
  },
];

const STORIES = [
  {
    quote:
      "I posted the brief on a Tuesday and had seven proposals by Thursday. The screening questions did most of the filtering for me.",
    name: "Ayesha K.",
    role: "Founder · Logistics",
    work: "Internal ops dashboard",
    rating: 5,
  },
  {
    quote:
      "Milestones meant I never worked more than two weeks ahead of a payment. That changed how I price entirely.",
    name: "Bilal A.",
    role: "Full-stack developer",
    work: "React and Django build",
    rating: 5,
  },
  {
    quote:
      "My first three clients were from my own campus. By the time I opened up to the global side I had real reviews.",
    name: "Sana M.",
    role: "Brand designer · Verified student",
    work: "Fintech identity",
    rating: 5,
  },
];

const TRUST = [
  {
    icon: "lock" as IconName,
    title: "Money held until you accept",
    body: "Funds are secured before work begins and released on acceptance. Neither side has to trust the other first.",
  },
  {
    icon: "id" as IconName,
    title: "Everyone is identity-verified",
    body: "Email, phone, and government ID — checked before anyone can post, sell, or buy.",
  },
  {
    icon: "clock" as IconName,
    title: "Hourly work you can audit",
    body: "Time is logged against the contract with a weekly cap you agree up front, so an invoice is never a surprise.",
  },
  {
    icon: "star" as IconName,
    title: "Reviews that cut both ways",
    body: "Clients are reviewed too, and neither review appears until both are written. No retaliation, no inflation.",
  },
];

const FOOTER: Array<{ heading: string; links: string[] }> = [
  {
    heading: "Categories",
    links: [
      "Development & IT", "Design & Creative", "Writing & Translation",
      "Video & Animation", "Marketing & Sales", "Data & Analytics",
      "Business & Admin", "Academic Support",
    ],
  },
  {
    heading: "For clients",
    links: [
      "How to hire", "Post a project", "Browse talent", "Payment protection",
      "Enterprise", "Success stories",
    ],
  },
  {
    heading: "For talent",
    links: [
      "How to find work", "Create a profile", "Proposal tips", "Getting paid",
      "Freelancer guide", "Community",
    ],
  },
  {
    heading: "Campus",
    links: [
      "Student portals", "Verify as a student", "For universities",
      "Campus moderators", "Academic integrity",
    ],
  },
  {
    heading: "Company",
    links: [
      "About SkilRize", "Careers", "Trust & safety", "Terms of Service",
      "Privacy Policy", "Contact",
    ],
  },
];

/* -------------------------------------------------------------------------- */

export default function LandingPage() {
  return (
    <div className="min-h-dvh">
      {/* Announcement rail. */}
      <div className="border-b border-line bg-accent-soft">
        <div className="mx-auto flex max-w-6xl items-center justify-center gap-2 px-5 py-2 text-center">
          <Icon name="sparkles" className="size-3.5 shrink-0 text-accent" />
          <p className="text-[12.5px] text-fg">
            Students: verify with your university email to unlock your campus marketplace.{" "}
            <Link href="/signup" className="font-medium text-accent underline-offset-2 hover:underline">
              Get started
            </Link>
          </p>
        </div>
      </div>

      <MarketingHeader />

      <main id="main">
        {/* ---------------------------------------------------------------- */}
        {/* Hero                                                             */}
        {/* ---------------------------------------------------------------- */}
        <section className="texture-grain relative overflow-hidden border-b border-line">
          <HeroBackdrop />

          <div className="relative z-10 mx-auto max-w-6xl px-5 pb-14 pt-16 sm:pt-20">
            <div className="animate-rise text-center">
              <h1 className="mx-auto max-w-4xl text-[clamp(2.3rem,5.6vw,4rem)] font-semibold leading-[1.06] tracking-[-0.035em] text-fg">
                Find the right talent.
                <br />
                <span className="text-gradient">Or become it.</span>
              </h1>
              <p className="mx-auto mt-5 max-w-xl text-[16px] leading-relaxed text-muted">
                Hire for a one-off task or a long build. Sell a service or win a contract. One
                account, one wallet, one reputation — whichever side of the work you are on.
              </p>

              <div className="mt-9">
                <HeroSearch />
              </div>
            </div>

            {/* A live slice of the catalogue, so the hero shows the product
                rather than describing it. */}
            <div className="mt-14 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {SHOWCASE.map((item, index) => (
                <Link
                  key={item.title}
                  href={`/gigs?category=${item.slug}`}
                  className={cn(
                    "group glass edge-light overflow-hidden rounded-xl border border-line shadow-e2",
                    "transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-e3",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                    // A gentle stagger so the row reads as a composition.
                    index % 2 === 1 && "sm:translate-y-5",
                  )}
                >
                  <div className="aspect-[16/11] overflow-hidden">
                    <CoverArt
                      seed={item.title}
                      motif={item.motif}
                      rounded={false}
                      className="transition-transform duration-500 group-hover:scale-105"
                    />
                  </div>
                  <div className="p-3">
                    <p className="truncate text-[12.5px] font-medium text-fg">{item.title}</p>
                    <p className="mt-0.5 flex items-center gap-1 text-[11.5px] text-subtle">
                      <Icon name="star" className="size-3 text-warn-500" />
                      {item.rating} · from Rs {item.from}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          {/* Proof rail, scrolling. */}
          <div className="relative z-10 overflow-hidden border-t border-line/60 py-4">
            <div className="marquee gap-10">
              {[0, 1].map((copy) => (
                <div key={copy} className="flex shrink-0 gap-10 pr-10" aria-hidden={copy === 1}>
                  {PROOF.map((claim) => (
                    <span
                      key={claim.label}
                      className="flex shrink-0 items-center gap-2 text-[13px] text-muted"
                    >
                      <Icon name={claim.icon} className="size-3.5 text-accent" />
                      {claim.label}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Categories                                                       */}
        {/* ---------------------------------------------------------------- */}
        <section className="mx-auto max-w-6xl px-5 py-16">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-[26px] font-semibold tracking-[-0.025em] text-fg">
                Browse by category
              </h2>
              <p className="mt-1 text-[14px] text-muted">
                Eight fields, hundreds of specialisms underneath them.
              </p>
            </div>
            <Link
              href="/gigs"
              className="inline-flex items-center gap-1 text-[13.5px] font-medium text-accent underline-offset-4 hover:underline"
            >
              Browse all services
              <Icon name="arrowRight" className="size-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {CATEGORIES.map((category) => (
              <CategoryTile
                key={category.slug}
                href={`/gigs?category=${category.slug}`}
                icon={category.icon}
                name={category.name}
                count={category.count}
              />
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Two ways to work                                                 */}
        {/* ---------------------------------------------------------------- */}
        <section className="border-y border-line bg-sunken">
          <div className="mx-auto max-w-6xl px-5 py-16">
            <div className="mb-9 max-w-2xl">
              <Badge tone="accent">Two ways to work</Badge>
              <h2 className="mt-3 text-[clamp(1.65rem,3.2vw,2.3rem)] font-semibold tracking-[-0.03em] text-fg">
                Some work needs a conversation. Some just needs doing.
              </h2>
              <p className="mt-3 text-[15px] leading-relaxed text-muted">
                Forcing every job through one model loses half the work. So we run both, over the
                same payments, messaging, reviews, and search.
              </p>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              {[
                {
                  tag: "Post a project",
                  title: "For work that needs scoping",
                  lede: "Describe the brief, compare proposals, interview, and award.",
                  points: [
                    "Screening questions filter out low-effort applications",
                    "Fixed price, staged milestones, or hourly with a time log",
                    "Each stage funded and released on its own",
                  ],
                  footer: "Custom, ambiguous, or long-running work",
                  href: "/projects/new",
                  cta: "Post a project",
                },
                {
                  tag: "Sell a service",
                  title: "For work you already understand",
                  lede: "Publish a fixed price with a clear scope, and buyers purchase it outright.",
                  points: [
                    "Tiered packages with optional paid add-ons",
                    "A requirements form starts the clock, not the seller",
                    "Defined revisions, then release on acceptance",
                  ],
                  footer: "Standardised, repeatable, well-understood work",
                  href: "/gigs/new",
                  cta: "Publish a service",
                },
              ].map((track) => (
                <Card
                  key={track.title}
                  className="group relative overflow-hidden p-7 transition-shadow duration-200 hover:shadow-e2"
                >
                  <div
                    className="absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-accent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                    aria-hidden
                  />
                  <Badge tone="accent">{track.tag}</Badge>
                  <h3 className="mt-4 text-xl font-semibold tracking-[-0.02em] text-fg">
                    {track.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{track.lede}</p>

                  <ul className="mt-6 space-y-3">
                    {track.points.map((point) => (
                      <li key={point} className="flex gap-3 text-[13.5px] text-fg">
                        <span className="mt-0.5 grid size-4.5 shrink-0 place-items-center rounded-full bg-positive-soft text-positive">
                          <Icon name="check" className="size-3" strokeWidth={2.6} />
                        </span>
                        {point}
                      </li>
                    ))}
                  </ul>

                  <div className="mt-6 flex items-center justify-between border-t border-line pt-4">
                    <p className="text-[12.5px] text-subtle">{track.footer}</p>
                    <Link
                      href={track.href}
                      className="inline-flex items-center gap-1 text-[13px] font-medium text-accent underline-offset-4 hover:underline"
                    >
                      {track.cta}
                      <Icon name="arrowRight" className="size-3.5" />
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* How it works                                                     */}
        {/* ---------------------------------------------------------------- */}
        <section className="reveal mx-auto max-w-6xl px-5 py-16">
          <h2 className="text-[26px] font-semibold tracking-[-0.025em] text-fg">How it works</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {HOW_IT_WORKS.map((step, index) => (
              <div key={step.title} className="relative rounded-xl border border-line bg-raised p-6">
                <span className="absolute right-5 top-5 text-[42px] font-semibold leading-none text-line">
                  {index + 1}
                </span>
                <span className="grid size-10 place-items-center rounded-lg bg-accent-soft text-accent">
                  <Icon name={step.icon} className="size-5" />
                </span>
                <h3 className="mt-4 text-[15.5px] font-semibold text-fg">{step.title}</h3>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">{step.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Campus — the differentiator, given a dark surface of its own      */}
        {/* ---------------------------------------------------------------- */}
        <section className="px-5 py-8">
          <div className="mx-auto max-w-6xl overflow-hidden rounded-2xl border border-line bg-ink-950 text-white">
            <div className="grid items-center gap-10 p-8 lg:grid-cols-2 lg:p-12">
              <div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-[12px] font-medium text-white/90">
                  <Icon name="sparkles" className="size-3" />
                  Only on SkilRize
                </span>
                <h2 className="mt-4 text-[clamp(1.6rem,3vw,2.2rem)] font-semibold leading-tight tracking-[-0.03em]">
                  A private marketplace for your campus.
                </h2>
                <p className="mt-4 text-[15px] leading-relaxed text-white/70">
                  Verify with your university email and student ID, and a portal opens for your
                  university alone. Your campus sees it. No one else does — not other universities,
                  not the open market.
                </p>

                <ul className="mt-7 space-y-4">
                  {[
                    ["Verified peers only", "Everyone proved their university affiliation."],
                    ["Priced for your market", "You compete with your campus, not the global floor."],
                    ["Reputation you keep", "Work there, then carry the reviews into the open market."],
                  ].map(([title, body]) => (
                    <li key={title} className="flex gap-3">
                      <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-white/15">
                        <Icon name="check" className="size-3" strokeWidth={2.6} />
                      </span>
                      <div>
                        <p className="text-[13.5px] font-medium">{title}</p>
                        <p className="mt-0.5 text-[13px] leading-relaxed text-white/60">{body}</p>
                      </div>
                    </li>
                  ))}
                </ul>

                <Link
                  href="/signup"
                  className="mt-8 inline-flex h-11 items-center gap-2 rounded-lg bg-white px-5 text-sm font-medium text-ink-950 transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                >
                  Verify as a student
                  <Icon name="arrowRight" className="size-4" />
                </Link>
              </div>

              {/* A representative portal frame rather than a stock photograph. */}
              <div className="rounded-xl border border-white/10 bg-white/5 p-1.5 backdrop-blur">
                <div className="flex items-center gap-2 px-3 py-2.5">
                  <span className="flex gap-1.5" aria-hidden>
                    {[0, 1, 2].map((dot) => (
                      <span key={dot} className="size-2.5 rounded-full bg-white/20" />
                    ))}
                  </span>
                  <span className="ml-2 inline-flex items-center gap-1.5 rounded-md bg-white/10 px-2 py-1 text-[11px] text-white/70">
                    <Icon name="lock" className="size-3" />
                    campus · COMSATS
                  </span>
                </div>

                <div className="space-y-2.5 rounded-lg bg-ink-1000/60 p-4">
                  {[
                    { seller: "Ahmed R.", title: "Poster & flyer design", price: "Rs 1,500" },
                    { seller: "Sana M.", title: "Final-year project help — React", price: "Rs 6,000" },
                    { seller: "Bilal K.", title: "Lecture notes → clean PDF", price: "Rs 800" },
                    { seller: "Hira Z.", title: "Thesis formatting & citations", price: "Rs 2,200" },
                  ].map((listing) => (
                    <div
                      key={listing.title}
                      className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3"
                    >
                      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-linear-to-br from-brand-400 to-brand-600 text-[11px] font-semibold">
                        {listing.seller.slice(0, 1)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium">{listing.title}</p>
                        <p className="text-[11.5px] text-white/50">{listing.seller}</p>
                      </div>
                      <span className="tabular shrink-0 text-[13px] font-semibold text-money-400">
                        {listing.price}
                      </span>
                    </div>
                  ))}
                  <p className="pt-1 text-center text-[11px] text-white/40">
                    Visible only to verified COMSATS students
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Stories                                                          */}
        {/* ---------------------------------------------------------------- */}
        <section className="mx-auto max-w-6xl px-5 py-16">
          <div className="mb-8 max-w-2xl">
            <h2 className="text-[26px] font-semibold tracking-[-0.025em] text-fg">
              What working here looks like
            </h2>
            <p className="mt-1 text-[14px] text-muted">
              Illustrative scenarios from the workflows the platform is built around.
            </p>
          </div>

          <ScrollRow>
            {STORIES.map((story) => (
              <Card
                key={story.name}
                className="w-[min(88vw,22rem)] shrink-0 snap-start p-6 transition-shadow duration-200 hover:shadow-e2"
              >
                <Icon name="quote" className="size-5 text-line-strong" />
                <p className="mt-3 text-[14px] leading-relaxed text-fg">{story.quote}</p>
                <div className="mt-5 flex items-center gap-3 border-t border-line pt-4">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-linear-to-br from-brand-400 to-brand-600 text-[12px] font-semibold text-white">
                    {story.name.slice(0, 1)}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-fg">{story.name}</p>
                    <p className="truncate text-[12px] text-subtle">{story.role}</p>
                  </div>
                  <div className="ml-auto text-right">
                    <Stars value={story.rating} size={12} />
                    <p className="mt-0.5 text-[11px] text-subtle">{story.work}</p>
                  </div>
                </div>
              </Card>
            ))}
          </ScrollRow>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Trust                                                            */}
        {/* ---------------------------------------------------------------- */}
        <section className="border-y border-line bg-sunken">
          <div className="mx-auto max-w-6xl px-5 py-16">
            <div className="max-w-2xl">
              <Badge>Why this is safe to use</Badge>
              <h2 className="mt-3 text-[clamp(1.65rem,3.2vw,2.3rem)] font-semibold tracking-[-0.03em] text-fg">
                Money and identity, handled properly.
              </h2>
              <p className="mt-3 text-[15px] leading-relaxed text-muted">
                A marketplace holds strangers&apos; money and strangers&apos; documents. That makes
                security a product feature, and it is the part we built first.
              </p>
            </div>

            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {TRUST.map((item) => (
                <div
                  key={item.title}
                  className="rounded-xl border border-line bg-raised p-6 transition-colors duration-200 hover:border-line-strong"
                >
                  <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent">
                    <Icon name={item.icon} className="size-[18px]" />
                  </span>
                  <h3 className="mt-4 text-[14.5px] font-semibold text-fg">{item.title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* CTA                                                              */}
        {/* ---------------------------------------------------------------- */}
        <section className="px-5 py-16">
          <div className="bg-aurora relative mx-auto max-w-5xl overflow-hidden rounded-2xl border border-line px-6 py-14 text-center">
            <div className="bg-grid absolute inset-0 opacity-40" aria-hidden />
            <div className="relative">
              <h2 className="text-[clamp(1.6rem,3vw,2.25rem)] font-semibold tracking-[-0.03em] text-fg">
                Start where you are.
              </h2>
              <p className="mx-auto mt-3 max-w-md text-[15px] text-muted">
                Free to join, free to browse. Verify when you are ready to hire or get paid.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link
                  href="/signup"
                  className="inline-flex h-12 items-center gap-2 rounded-lg bg-accent px-7 text-[15px] font-medium text-on-accent shadow-e1 transition-colors hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  Create your account
                  <Icon name="arrowRight" className="size-4" />
                </Link>
                <Link
                  href="/projects"
                  className="inline-flex h-12 items-center rounded-lg border border-line-strong bg-raised px-7 text-[15px] font-medium text-fg shadow-e1 transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  Browse open work
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ------------------------------------------------------------------ */}
      {/* Footer                                                             */}
      {/* ------------------------------------------------------------------ */}
      <footer className="border-t border-line bg-sunken">
        <div className="mx-auto max-w-6xl px-5 py-14">
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:grid-cols-5">
            {FOOTER.map((column) => (
              <div key={column.heading}>
                <h3 className="text-[13px] font-semibold text-fg">{column.heading}</h3>
                <ul className="mt-3 space-y-2">
                  {column.links.map((link) => (
                    <li key={link}>
                      <span className="cursor-default text-[13px] text-muted transition-colors hover:text-fg">
                        {link}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-line pt-8 sm:flex-row">
            <Logo />
            <p className="text-[12.5px] text-subtle">
              © {new Date().getFullYear()} SkilRize · Built by NEXOLV.TECH
            </p>
            <div className="flex items-center gap-2 text-[12.5px] text-subtle">
              <Icon name="globe" className="size-3.5" />
              Pakistan · English
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
