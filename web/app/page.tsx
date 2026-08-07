import Link from "next/link";

import {
  CategoryTile,
  HeroBackdrop,
  HeroComposition,
  HeroSearch,
  ScrollRow,
  ServiceCard,
  type ServiceCardData,
} from "@/components/marketing";
import { MarketingHeader } from "@/components/shell";
import { Badge, Icon, Logo, Stars, cn, type IconName } from "@/components/ui";

/** A representative slice of the catalogue, shown as real listing cards. */
const POPULAR: ServiceCardData[] = [
  {
    title: "Design a modern logo and full brand identity kit",
    slug: "design-creative",
    motif: "design",
    seller: "Sana M.",
    level: "Top Rated",
    rating: 4.9,
    reviews: 214,
    from: "8,000",
  },
  {
    title: "Build a production React and Django web application",
    slug: "development-it",
    motif: "code",
    seller: "Bilal A.",
    level: "Level 2",
    rating: 5.0,
    reviews: 96,
    from: "25,000",
  },
  {
    title: "Edit short-form video for TikTok, Reels and Shorts",
    slug: "video-animation",
    motif: "video",
    seller: "Hira Z.",
    level: "Level 2",
    rating: 4.8,
    reviews: 341,
    from: "4,500",
  },
  {
    title: "SEO audit and a content strategy that actually ranks",
    slug: "marketing-sales",
    motif: "marketing",
    seller: "Ahmed R.",
    level: "Top Rated",
    rating: 4.9,
    reviews: 158,
    from: "6,000",
  },
  {
    title: "Clean, analyse and visualise your business data",
    slug: "data-analytics",
    motif: "data",
    seller: "Fatima N.",
    level: "Level 1",
    rating: 4.9,
    reviews: 72,
    from: "5,500",
  },
  {
    title: "Write and edit long-form articles in English and Urdu",
    slug: "writing-translation",
    motif: "writing",
    seller: "Usman T.",
    level: "Level 2",
    rating: 4.8,
    reviews: 187,
    from: "3,000",
  },
];

const PROOF: Array<{ icon: IconName; label: string }> = [
  { icon: "lock", label: "Escrow on every contract" },
  { icon: "id", label: "Government ID verified" },
  { icon: "star", label: "Double-blind two-way reviews" },
  { icon: "clock", label: "Auditable hourly time logs" },
  { icon: "building", label: "Private campus marketplaces" },
  { icon: "wallet", label: "Released only when you accept" },
];

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
  {
    quote:
      "The work diary settled an hourly dispute in about four minutes. Both of us could see exactly what was logged.",
    name: "Usman T.",
    role: "Technical writer",
    work: "Documentation retainer",
    rating: 5,
  },
];

/**
 * Membership tiers.
 *
 * The paid tiers are marked as not yet available rather than quietly presented
 * as buyable. Pre-launch pricing on a landing page is ordinary; an order button
 * for something that cannot be ordered is not.
 */
const PLANS = [
  {
    name: "Free",
    price: "Rs 0",
    cadence: "always",
    lede: "Everything you need to hire or get hired.",
    features: [
      "Post projects and publish services",
      "Escrow on every contract",
      "Contract messaging and file sharing",
      "Two-way reviews and a public profile",
      "Standard proposal allowance",
    ],
    cta: "Get started free",
    href: "/signup",
    featured: false,
    available: true,
  },
  {
    name: "Pro",
    price: "Rs 1,500",
    cadence: "per month",
    lede: "For freelancers who are earning and want to earn more.",
    features: [
      "Everything in Free",
      "Triple the monthly proposals",
      "Profile boost in search results",
      "Advanced earnings and funnel analytics",
      "Priority dispute review",
    ],
    cta: "Notify me",
    href: "/signup",
    featured: true,
    available: false,
  },
  {
    name: "Elite",
    price: "Rs 4,500",
    cadence: "per month",
    lede: "For teams and agencies running work at volume.",
    features: [
      "Everything in Pro",
      "Team and agency workspaces",
      "Shared client CRM and pipelines",
      "Sellable subscription services",
      "Dedicated account support",
    ],
    cta: "Notify me",
    href: "/signup",
    featured: false,
    available: false,
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

function SectionHeading({
  eyebrow,
  title,
  lede,
  action,
  className,
}: {
  eyebrow?: string;
  title: string;
  lede?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="max-w-2xl">
        {eyebrow && <p className="eyebrow mb-2.5">{eyebrow}</p>}
        <h2 className="display-2 text-fg">{title}</h2>
        {lede && <p className="mt-3 text-[15.5px] leading-relaxed text-muted">{lede}</p>}
      </div>
      {action}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-dvh">
      {/* Announcement rail. */}
      <div className="border-b border-line bg-accent-soft">
        <div className="mx-auto flex max-w-7xl items-center justify-center gap-2 px-5 py-2.5 text-center">
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
        {/* A fixed dark surface in both themes. The page's most important
            frame should not change character because someone flipped a
            toggle — and white-on-near-black is the contrast the headline was
            composed for. */}
        <section className="hero-dark texture-grain relative overflow-hidden">
          <HeroBackdrop />

          <div className="relative z-10 mx-auto max-w-7xl px-5 pb-20 pt-20 sm:pt-28">
            <div className="grid items-center gap-16 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="animate-rise">
                <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/8 px-3.5 py-1.5 text-[12px] font-medium text-white/80 backdrop-blur">
                  <span className="size-1.5 rounded-full bg-money-400" aria-hidden />
                  Two marketplaces, one account
                </span>

                <h1 className="display-1 mt-6 max-w-[16ch] text-white">
                  Find the right talent.{" "}
                  <span className="bg-linear-to-r from-brand-300 via-brand-200 to-money-400 bg-clip-text text-transparent">
                    Or become it.
                  </span>
                </h1>

                <p className="mt-7 max-w-xl text-[17.5px] leading-relaxed text-white/65">
                  Hire for a one-off task or a long build. Sell a service or win a contract. One
                  account, one wallet, one reputation — whichever side of the work you are on.
                </p>

                <div className="mt-10 max-w-2xl">
                  <HeroSearch />
                </div>
              </div>

              {/* The product itself, as a stack of interface cards. Hidden on
                  small screens where it would push the search below the fold. */}
              <div className="animate-rise hidden lg:block">
                <HeroComposition />
              </div>
            </div>
          </div>

          {/* Guarantee rail. Where a marketplace of this kind would run a row of
              client logos, we run the promises the platform actually enforces —
              a logo wall we have not earned yet would be the wrong kind of
              social proof, and this is the claim the product can back. */}
          <div className="relative z-10 border-t border-white/10 py-5">
            <p className="mb-4 text-center text-[11px] font-semibold uppercase tracking-[0.14em] text-white/35">
              Protected end to end
            </p>
            <div className="overflow-hidden">
              <div className="marquee gap-12">
                {[0, 1].map((copy) => (
                  <div key={copy} className="flex shrink-0 gap-12 pr-12" aria-hidden={copy === 1}>
                    {PROOF.map((claim) => (
                      <span
                        key={claim.label}
                        className="flex shrink-0 items-center gap-2.5 text-[13.5px] font-medium text-white/60"
                      >
                        <Icon name={claim.icon} className="size-4 text-brand-300" />
                        {claim.label}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Popular services                                                 */}
        {/* ---------------------------------------------------------------- */}
        <section className="mx-auto max-w-7xl px-5 py-20">
          <SectionHeading
            eyebrow="Ready to buy"
            title="Popular services"
            lede="Fixed scope, fixed price, delivered on a clock that starts when you have handed over what the seller needs."
            action={
              <Link
                href="/gigs"
                className="inline-flex items-center gap-1.5 text-[14px] font-medium text-accent underline-offset-4 hover:underline"
              >
                Browse all services
                <Icon name="arrowRight" className="size-4" />
              </Link>
            }
            className="mb-9"
          />

          <ScrollRow>
            {POPULAR.map((item) => (
              <ServiceCard key={item.title} item={item} href={`/gigs?category=${item.slug}`} />
            ))}
          </ScrollRow>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Categories                                                       */}
        {/* ---------------------------------------------------------------- */}
        <section className="border-y border-line bg-sunken">
          <div className="mx-auto max-w-7xl px-5 py-20">
            <SectionHeading
              eyebrow="Explore"
              title="Browse by category"
              lede="Eight fields, hundreds of specialisms underneath them."
              className="mb-10"
            />

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
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Two ways to work                                                 */}
        {/* ---------------------------------------------------------------- */}
        <section id="tracks" className="mx-auto max-w-7xl scroll-mt-24 px-5 py-20">
          <SectionHeading
            eyebrow="Two ways to work"
            title="Some work needs a conversation. Some just needs doing."
            lede="Forcing every job through one model loses half the work. So we run both, over the same payments, messaging, reviews, and search."
            className="mb-10"
          />

          <div className="grid gap-6 lg:grid-cols-2">
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
              <div
                key={track.title}
                className="lift group relative overflow-hidden rounded-2xl border border-line bg-raised p-8 shadow-e1"
              >
                <div
                  className="absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-accent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                  aria-hidden
                />
                <Badge tone="accent">{track.tag}</Badge>
                <h3 className="display-3 mt-4 text-fg">{track.title}</h3>
                <p className="mt-2.5 text-[14.5px] leading-relaxed text-muted">{track.lede}</p>

                <ul className="mt-7 space-y-3.5">
                  {track.points.map((point) => (
                    <li key={point} className="flex gap-3 text-[14px] text-fg">
                      <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-positive-soft text-positive">
                        <Icon name="check" className="size-3" strokeWidth={2.8} />
                      </span>
                      {point}
                    </li>
                  ))}
                </ul>

                <div className="mt-7 flex items-center justify-between border-t border-line pt-5">
                  <p className="text-[12.5px] text-subtle">{track.footer}</p>
                  <Link
                    href={track.href}
                    className="inline-flex items-center gap-1.5 text-[13.5px] font-medium text-accent underline-offset-4 hover:underline"
                  >
                    {track.cta}
                    <Icon name="arrowRight" className="size-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* How it works                                                     */}
        {/* ---------------------------------------------------------------- */}
        <section className="border-y border-line bg-sunken">
          <div className="reveal mx-auto max-w-7xl px-5 py-20">
            <SectionHeading eyebrow="The flow" title="How it works" className="mb-10" />
            <div className="grid gap-6 md:grid-cols-3">
              {HOW_IT_WORKS.map((step, index) => (
                <div
                  key={step.title}
                  className="relative overflow-hidden rounded-2xl border border-line bg-raised p-7"
                >
                  <span className="absolute right-6 top-5 text-[56px] font-semibold leading-none text-line">
                    {index + 1}
                  </span>
                  <span className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent">
                    <Icon name={step.icon} className="size-5" />
                  </span>
                  <h3 className="mt-5 text-[16px] font-semibold text-fg">{step.title}</h3>
                  <p className="mt-2 text-[14px] leading-relaxed text-muted">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Membership                                                       */}
        {/* ---------------------------------------------------------------- */}
        <section className="mx-auto max-w-7xl px-5 py-20">
          <SectionHeading
            eyebrow="Membership"
            title="Free to work. Paid only if it pays you back."
            lede="Hiring and selling never cost a subscription. The paid tiers buy reach and tooling on top — and they arrive with the professional layer, not before."
            className="mb-11"
          />

          <div className="grid items-start gap-6 lg:grid-cols-3">
            {PLANS.map((plan) => (
              <div
                key={plan.name}
                className={cn(
                  "relative flex h-full flex-col rounded-2xl border p-8 transition-shadow duration-300",
                  plan.featured
                    ? "border-accent/50 bg-raised shadow-e3 lg:-my-3 lg:py-11"
                    : "border-line bg-raised shadow-e1 hover:shadow-e2",
                )}
              >
                {plan.featured && (
                  <span className="absolute -top-3 left-8 rounded-full bg-accent px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-on-accent">
                    Most popular
                  </span>
                )}

                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="text-[17px] font-semibold text-fg">{plan.name}</h3>
                  {!plan.available && <Badge tone="caution">Coming soon</Badge>}
                </div>

                <p className="mt-4 flex items-baseline gap-1.5">
                  <span className="tabular text-[34px] font-semibold tracking-[-0.03em] text-fg">
                    {plan.price}
                  </span>
                  <span className="text-[13px] text-subtle">{plan.cadence}</span>
                </p>

                <p className="mt-3 text-[14px] leading-relaxed text-muted">{plan.lede}</p>

                <ul className="mt-7 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex gap-2.5 text-[13.5px] text-fg">
                      <span className="mt-0.5 grid size-4.5 shrink-0 place-items-center rounded-full bg-positive-soft text-positive">
                        <Icon name="check" className="size-2.5" strokeWidth={3.2} />
                      </span>
                      {feature}
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.href}
                  className={cn(
                    "mt-8 inline-flex h-11 items-center justify-center rounded-xl px-5 text-[14px] font-medium",
                    "transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                    plan.featured
                      ? "bg-accent text-on-accent hover:bg-accent-hover"
                      : "border border-line-strong bg-raised text-fg hover:bg-sunken",
                  )}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Campus — the differentiator, given a dark surface of its own      */}
        {/* ---------------------------------------------------------------- */}
        <section id="campus" className="scroll-mt-24 px-5 py-12">
          <div className="mx-auto max-w-7xl overflow-hidden rounded-3xl border border-line bg-ink-950 text-white">
            <div className="grid items-center gap-12 p-9 lg:grid-cols-2 lg:p-14">
              <div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-[12px] font-medium text-white/90">
                  <Icon name="sparkles" className="size-3" />
                  Only on SkilRize
                </span>
                <h2 className="display-2 mt-5">A private marketplace for your campus.</h2>
                <p className="mt-5 max-w-lg text-[15.5px] leading-relaxed text-white/70">
                  Verify with your university email and student ID, and a portal opens for your
                  university alone. Your campus sees it. No one else does — not other universities,
                  not the open market.
                </p>

                <ul className="mt-8 space-y-5">
                  {[
                    ["Verified peers only", "Everyone proved their university affiliation."],
                    ["Priced for your market", "You compete with your campus, not the global floor."],
                    ["Reputation you keep", "Work there, then carry the reviews into the open market."],
                  ].map(([title, body]) => (
                    <li key={title} className="flex gap-3.5">
                      <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-white/15">
                        <Icon name="check" className="size-3" strokeWidth={2.8} />
                      </span>
                      <div>
                        <p className="text-[14px] font-medium">{title}</p>
                        <p className="mt-0.5 text-[13.5px] leading-relaxed text-white/60">{body}</p>
                      </div>
                    </li>
                  ))}
                </ul>

                <Link
                  href="/signup"
                  className="mt-9 inline-flex h-12 items-center gap-2 rounded-xl bg-white px-6 text-[15px] font-medium text-ink-950 transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                >
                  Verify as a student
                  <Icon name="arrowRight" className="size-4" />
                </Link>
              </div>

              {/* A representative portal frame rather than a stock photograph. */}
              <div className="rounded-2xl border border-white/10 bg-white/5 p-2 backdrop-blur">
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

                <div className="space-y-2.5 rounded-xl bg-ink-1000/60 p-4">
                  {[
                    { seller: "Ahmed R.", title: "Poster & flyer design", price: "Rs 1,500" },
                    { seller: "Sana M.", title: "Final-year project help — React", price: "Rs 6,000" },
                    { seller: "Bilal K.", title: "Lecture notes → clean PDF", price: "Rs 800" },
                    { seller: "Hira Z.", title: "Thesis formatting & citations", price: "Rs 2,200" },
                  ].map((listing) => (
                    <div
                      key={listing.title}
                      className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-3 transition-colors hover:bg-white/10"
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
        <section className="mx-auto max-w-7xl px-5 py-20">
          <SectionHeading
            eyebrow="In practice"
            title="What working here looks like"
            lede="Illustrative scenarios from the workflows the platform is built around."
            className="mb-10"
          />

          <ScrollRow>
            {STORIES.map((story) => (
              <div
                key={story.name}
                className="lift flex w-[min(88vw,23rem)] shrink-0 snap-start flex-col rounded-2xl border border-line bg-raised p-7 shadow-e1"
              >
                <Icon name="quote" className="size-6 text-line-strong" />
                <p className="mt-4 flex-1 text-[14.5px] leading-relaxed text-fg">{story.quote}</p>
                <div className="mt-6 flex items-center gap-3 border-t border-line pt-5">
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-linear-to-br from-brand-400 to-brand-600 text-[13px] font-semibold text-white">
                    {story.name.slice(0, 1)}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-[13.5px] font-medium text-fg">{story.name}</p>
                    <p className="truncate text-[12px] text-subtle">{story.role}</p>
                  </div>
                  <div className="ml-auto shrink-0 text-right">
                    <Stars value={story.rating} size={12} />
                    <p className="mt-0.5 text-[11px] text-subtle">{story.work}</p>
                  </div>
                </div>
              </div>
            ))}
          </ScrollRow>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Trust                                                            */}
        {/* ---------------------------------------------------------------- */}
        <section id="trust" className="scroll-mt-24 border-y border-line bg-sunken">
          <div className="mx-auto max-w-7xl px-5 py-20">
            <SectionHeading
              eyebrow="Why this is safe to use"
              title="Money and identity, handled properly."
              lede="A marketplace holds strangers' money and strangers' documents. That makes security a product feature, and it is the part we built first."
              className="mb-11"
            />

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {TRUST.map((item) => (
                <div
                  key={item.title}
                  className="lift rounded-2xl border border-line bg-raised p-7 hover:border-accent/40"
                >
                  <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent">
                    <Icon name={item.icon} className="size-5" />
                  </span>
                  <h3 className="mt-5 text-[15px] font-semibold text-fg">{item.title}</h3>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-muted">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* CTA                                                              */}
        {/* ---------------------------------------------------------------- */}
        <section className="px-5 py-20">
          <div className="hero-dark texture-grain relative mx-auto max-w-7xl overflow-hidden rounded-3xl px-6 py-20 text-center">
            <div className="hero-grid absolute inset-0" aria-hidden />
            <div className="relative">
              <h2 className="display-1 mx-auto max-w-[18ch] text-white">
                Start where you are.
              </h2>
              <p className="mx-auto mt-6 max-w-lg text-[17px] leading-relaxed text-white/65">
                Free to join, free to browse. Verify when you are ready to hire or get paid.
              </p>
              <div className="mt-10 flex flex-wrap justify-center gap-3">
                <Link
                  href="/signup"
                  className="inline-flex h-13 items-center gap-2 rounded-xl bg-white px-8 text-[15px] font-medium text-ink-950 shadow-[0_16px_40px_-12px_rgb(0_0_0_/_0.6)] transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                >
                  Create your account
                  <Icon name="arrowRight" className="size-4" />
                </Link>
                <Link
                  href="/projects"
                  className="inline-flex h-13 items-center rounded-xl border border-white/20 bg-white/8 px-8 text-[15px] font-medium text-white backdrop-blur transition-colors hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                >
                  Browse open work
                </Link>
              </div>
              <p className="mt-7 text-[13px] text-white/40">
                No card required · Escrow on every contract · Cancel any time
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* ------------------------------------------------------------------ */}
      {/* Footer                                                             */}
      {/* ------------------------------------------------------------------ */}
      <footer className="border-t border-line bg-sunken">
        <div className="mx-auto max-w-7xl px-5 py-16">
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:grid-cols-5">
            {FOOTER.map((column) => (
              <div key={column.heading}>
                <h3 className="text-[13px] font-semibold text-fg">{column.heading}</h3>
                <ul className="mt-4 space-y-2.5">
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

          <div className="mt-14 flex flex-col items-center justify-between gap-4 border-t border-line pt-8 sm:flex-row">
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
