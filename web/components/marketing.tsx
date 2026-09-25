"use client";

/**
 * Marketing surfaces.
 *
 * The page is built around the one thing that makes a stranger willing to pay
 * another stranger online: knowing where the money is. The escrow ticket is
 * that idea made visible — an order slip that shows the payment held, the work
 * delivered, the approval, and the release, with the fee arithmetic printed on
 * it. Everything else on the page stays quiet around it.
 */

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Cover, motifFor } from "@/components/artwork";
import { Icon, Money, cn, type IconName } from "@/components/ui";
import type { GigSummary } from "@/lib/api";
import { BUSINESS } from "@/lib/business";

/* -------------------------------------------------------------------------- */
/* The escrow ticket — the page's signature                                   */
/* -------------------------------------------------------------------------- */

const TICKET_STEPS: Array<{ label: string; detail: string }> = [
  { label: "You pay into escrow", detail: "Held by SkilRize" },
  { label: "Work delivered", detail: "Files and notes on the record" },
  { label: "You approve the work", detail: "Or ask for a revision" },
  { label: "Released to the freelancer", detail: "Sent to their bank account" },
];

/** Seconds at which each step inks in. The stamp changes after the last. */
const STEP_AT = [0.5, 1.4, 2.3, 3.2] as const;

export function EscrowTicket({ className }: { className?: string }) {
  const [run, setRun] = React.useState(0);
  const price = 18000;
  const fee = Math.round((price * BUSINESS.commissionPercent) / 100);

  return (
    <figure className={cn("relative", className)}>
      {/* Remounted on replay so every CSS animation starts again from zero. */}
      <div
        key={run}
        className="ticket-edge relative rounded-t-xl border border-b-0 border-line bg-raised px-6 pt-6 pb-9 shadow-e3"
      >
        <div className="flex items-baseline justify-between gap-4">
          <p className="eyebrow">Example order</p>
          <p className="figure text-[12px] text-subtle">SR-10482</p>
        </div>
        <p className="mt-3 text-[19px] font-bold leading-tight tracking-[-0.01em] text-fg">
          Logo &amp; brand identity
        </p>
        <p className="mt-1 text-[13px] text-muted">Standard package · 5-day delivery</p>

        <div className="perforation my-5" aria-hidden />

        <ol className="space-y-3.5" aria-label="How this order's payment moves">
          {TICKET_STEPS.map((step, index) => (
            <li key={step.label} className="flex items-start gap-3">
              <span
                aria-hidden
                className={cn(
                  "mt-1 size-3 shrink-0 rounded-full border-2",
                  index === TICKET_STEPS.length - 1
                    ? "border-positive text-positive"
                    : "border-accent text-accent",
                )}
                style={{
                  animation: "step-on 0.35s var(--ease-out-quint) both",
                  animationDelay: `${STEP_AT[index]}s`,
                }}
              />
              <span className="min-w-0 flex-1">
                <span
                  className="block text-[14px] font-semibold"
                  style={{
                    animation: "step-label 0.35s ease both",
                    animationDelay: `${STEP_AT[index]}s`,
                  }}
                >
                  {step.label}
                </span>
                <span className="block text-[12px] text-subtle">{step.detail}</span>
              </span>
              {index === 0 && (
                <Money amount={price} className="figure shrink-0 text-[13px] font-semibold text-fg" />
              )}
              {index === TICKET_STEPS.length - 1 && (
                <Money
                  amount={price - fee}
                  className="figure shrink-0 text-[13px] font-semibold text-positive"
                />
              )}
            </li>
          ))}
        </ol>

        <div className="perforation my-5" aria-hidden />

        <div className="flex items-end justify-between gap-4">
          <div className="text-[12px] leading-relaxed text-subtle">
            <p>
              Platform fee ({BUSINESS.commissionPercent}%):{" "}
              <Money amount={fee} className="figure text-muted" />
            </p>
            <p>Paid by the freelancer, from the release.</p>
          </div>

          <div className="relative grid h-12 w-40 shrink-0 place-items-center">
            <span
              className="stamp absolute text-accent"
              style={{
                animation:
                  "stamp-in 0.42s var(--ease-out-quint) both, stamp-out 0.3s ease forwards",
                animationDelay: `0.6s, ${STEP_AT[3] - 0.1}s`,
              }}
            >
              Held in escrow
            </span>
            <span
              className="stamp absolute text-positive"
              style={{ animation: "stamp-in 0.42s var(--ease-out-quint) both", animationDelay: `${STEP_AT[3] + 0.15}s` }}
            >
              <Icon name="check" strokeWidth={3} className="size-3.5" />
              Released
            </span>
          </div>
        </div>
      </div>

      <figcaption className="mt-5 flex items-center justify-between gap-3 text-[12.5px] text-subtle">
        <span>How every order on SkilRize moves money.</span>
        <button
          type="button"
          onClick={() => setRun((value) => value + 1)}
          className="inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-md px-2 font-medium text-accent underline-offset-4 hover:underline"
        >
          <Icon name="clock" className="size-3.5" />
          Replay
        </button>
      </figcaption>
    </figure>
  );
}

/* -------------------------------------------------------------------------- */
/* Track and search                                                           */
/* -------------------------------------------------------------------------- */

export type Track = "services" | "projects";

export const TRACKS: Record<
  Track,
  { label: string; placeholder: string; action: string; suggestions: string[] }
> = {
  services: {
    label: "Buy a service",
    placeholder: "Search services, e.g. “business website”",
    action: "Search",
    suggestions: ["Business website", "Mobile app", "Logo design", "AI chatbot"],
  },
  projects: {
    label: "Post a brief",
    placeholder: "Describe what you need done",
    action: "Get proposals",
    suggestions: ["Mobile app", "Data dashboard", "Brand identity", "Thesis editing"],
  },
};

/**
 * The track switch. A tablist rather than links: it changes what the search
 * beside it does, so it is a control, not navigation. Roving `tabIndex` keeps
 * it to one tab stop with arrow keys inside.
 */
export function TrackSwitch({ value, onChange }: { value: Track; onChange: (next: Track) => void }) {
  const order: Track[] = ["services", "projects"];

  return (
    <div
      role="tablist"
      aria-label="How you want to hire"
      className="inline-flex rounded-lg border border-line-strong bg-raised p-1"
    >
      {order.map((track) => {
        const active = track === value;
        return (
          <button
            key={track}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(track)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
              event.preventDefault();
              onChange(order[(order.indexOf(value) + 1) % order.length]!);
            }}
            className={cn(
              "min-h-10 cursor-pointer rounded-md px-4 text-[14px] font-semibold transition-colors duration-150",
              active ? "bg-fg text-surface" : "text-muted hover:text-fg",
            )}
          >
            {TRACKS[track].label}
          </button>
        );
      })}
    </div>
  );
}

/** The hero search. Submits into whichever track is selected. */
export function HeroSearch({ track }: { track: Track }) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const config = TRACKS[track];

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const term = query.trim();
    if (track === "projects") {
      router.push(term ? `/projects/new?title=${encodeURIComponent(term)}` : "/projects/new");
      return;
    }
    router.push(term ? `/gigs?q=${encodeURIComponent(term)}` : "/gigs");
  }

  return (
    <form
      onSubmit={submit}
      role="search"
      className="flex items-center gap-2 rounded-xl border border-line-strong bg-raised p-1.5 shadow-e2 focus-within:border-fg/50"
    >
      <Icon name="search" className="ml-3 size-5 shrink-0 text-subtle" />
      <label htmlFor="hero-search" className="sr-only">
        {config.placeholder}
      </label>
      <input
        id="hero-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={config.placeholder}
        className="h-12 min-w-0 flex-1 bg-transparent text-[15.5px] text-fg placeholder:text-subtle focus:outline-none"
      />
      <button
        type="submit"
        aria-label={config.action}
        className="grid h-12 w-12 shrink-0 cursor-pointer place-items-center rounded-lg bg-action text-on-action transition-colors duration-150 hover:bg-action-hover sm:w-auto sm:px-6"
      >
        <Icon name="arrowRight" className="size-5 sm:hidden" />
        <span className="hidden text-[14.5px] font-semibold sm:inline">{config.action}</span>
      </button>
    </form>
  );
}

export function SuggestionPills({ track }: { track: Track }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[13px] text-subtle">Popular:</span>
      {TRACKS[track].suggestions.map((term) => (
        <Link
          key={term}
          href={
            track === "projects"
              ? `/projects/new?title=${encodeURIComponent(term)}`
              : `/gigs?q=${encodeURIComponent(term)}`
          }
          className="inline-flex min-h-9 items-center rounded-full border border-line-strong px-3.5 text-[13px] font-medium text-fg transition-colors duration-150 hover:border-fg/40 hover:bg-sunken"
        >
          {term}
        </Link>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Blocks                                                                     */
/* -------------------------------------------------------------------------- */

export function SectionHead({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-5 pb-9">
      <div className="max-w-2xl">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2 className="display-lg mt-3">{title}</h2>
        {description && (
          <p className="mt-4 text-[16px] leading-relaxed text-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function CategoryTile({
  slug,
  name,
  icon,
  examples,
}: {
  slug: string;
  name: string;
  icon: IconName;
  examples: string;
}) {
  return (
    <Link
      href={`/gigs?category=${slug}`}
      className="lift group flex items-start gap-4 rounded-lg border border-line bg-raised p-5"
    >
      <span
        aria-hidden
        className="grid size-10 shrink-0 place-items-center rounded-md bg-accent-soft text-accent"
      >
        <Icon name={icon} className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2 text-[15px] font-semibold text-fg">
          {name}
          <Icon
            name="arrowRight"
            className="size-4 text-subtle transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-fg"
          />
        </span>
        <span className="mt-1 block text-[13px] leading-snug text-subtle">{examples}</span>
      </span>
    </Link>
  );
}

/** A live listing from the catalogue. */
export function GigCard({ gig }: { gig: GigSummary }) {
  return (
    <Link
      href={`/gigs/${gig.id}`}
      className="lift group flex flex-col overflow-hidden rounded-lg border border-line bg-raised"
    >
      <div className="aspect-[16/10] overflow-hidden bg-sunken">
        <Cover
          src={gig.cover_url}
          seed={gig.slug || gig.id}
          motif={motifFor(gig.category_name)}
          className="rounded-none transition-transform duration-500 group-hover:scale-[1.03]"
        />
      </div>
      <div className="flex flex-1 flex-col p-4">
        {gig.category_name && <p className="eyebrow">{gig.category_name}</p>}
        <p className="mt-1.5 line-clamp-2 text-[15px] font-semibold leading-snug text-fg">
          {gig.title}
        </p>
        <p className="mt-1.5 text-[13px] text-muted">by {gig.seller_name}</p>
        <div className="mt-auto flex items-end justify-between gap-3 border-t border-line pt-3.5">
          <span className="text-[12px] text-subtle">
            {gig.rating_count > 0 ? `${gig.rating_average} ★ (${gig.rating_count})` : "New service"}
          </span>
          <span className="text-right">
            <span className="block text-[11px] text-subtle">From</span>
            <Money amount={gig.starting_price} className="figure text-[15px] font-semibold text-fg" />
          </span>
        </div>
      </div>
    </Link>
  );
}

export function FaqItem({ question, children }: { question: string; children: React.ReactNode }) {
  return (
    <details className="group border-b border-line py-5 [&_summary::-webkit-details-marker]:hidden">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-[16px] font-semibold text-fg">
        {question}
        <Icon
          name="plus"
          className="mt-1 size-4 shrink-0 text-subtle transition-transform duration-200 group-open:rotate-45"
        />
      </summary>
      <div className="mt-3 max-w-3xl text-[15px] leading-relaxed text-muted">{children}</div>
    </details>
  );
}
