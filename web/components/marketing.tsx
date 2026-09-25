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

import { Avatar, Badge, Icon, Money, cn } from "@/components/ui";
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
const STEP_AT = [0.3, 0.9, 1.5, 2.1] as const;

/** One pass: the last stamp lands at about 2.7s, and the finished slip then
 *  holds for two seconds before it fades and starts again. */
const CYCLE_MS = 4700;
const FADE_MS = 300;

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(onChange: () => void) {
  const query = window.matchMedia(REDUCED_MOTION);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** True while `ref` is at least partly on screen — a loop nobody can see is
 *  wasted work, and restarting where the visitor is not looking is pointless. */
function useOnScreen(ref: React.RefObject<HTMLElement | null>) {
  const [visible, setVisible] = React.useState(true);
  React.useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => setVisible(Boolean(entry?.isIntersecting)));
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref]);
  return visible;
}

export function EscrowTicket({ className }: { className?: string }) {
  const [run, setRun] = React.useState(0);
  const [fading, setFading] = React.useState(false);
  const figureRef = React.useRef<HTMLElement>(null);
  const visible = useOnScreen(figureRef);
  // Reduced motion shows the finished slip at once (globals.css), so there
  // is nothing to loop.
  const reducedMotion = React.useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia(REDUCED_MOTION).matches,
    () => false,
  );
  const price = 18000;
  const fee = Math.round((price * BUSINESS.commissionPercent) / 100);

  // Each pass schedules the next: fade the finished slip out, then remount it
  // (the `key` below) so every CSS animation starts again from zero.
  React.useEffect(() => {
    if (reducedMotion || !visible) return;
    const fade = window.setTimeout(() => setFading(true), CYCLE_MS - FADE_MS);
    const next = window.setTimeout(() => {
      setFading(false);
      setRun((value) => value + 1);
    }, CYCLE_MS);
    return () => {
      window.clearTimeout(fade);
      window.clearTimeout(next);
    };
  }, [run, reducedMotion, visible]);

  return (
    <figure ref={figureRef} className={cn("relative", className)}>
      <div
        key={run}
        className={cn(
          "ticket-edge relative rounded-t-xl border border-b-0 border-line bg-raised px-6 pt-6 pb-9 shadow-e3",
          "transition-opacity duration-300",
          fading && "opacity-0",
        )}
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
                animationDelay: `0.35s, ${STEP_AT[3] - 0.1}s`,
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

      <figcaption className="mt-5 text-[12.5px] text-subtle">
        How every order on SkilRize moves money.
      </figcaption>
    </figure>
  );
}

/* -------------------------------------------------------------------------- */
/* Track and search                                                           */
/* -------------------------------------------------------------------------- */

/** The two sides of one account: buying work, and selling it. */
export type Track = "hire" | "earn";

export const TRACKS: Record<
  Track,
  {
    label: string;
    placeholder: string;
    action: string;
    /** Where a search on this side lands. */
    searchPath: string;
    suggestions: string[];
    /** The other way in, for someone who does not want to search. */
    alternative: { text: string; link: string; href: string };
  }
> = {
  hire: {
    label: "I want to hire",
    placeholder: "Search services, e.g. “business website”",
    action: "Search",
    searchPath: "/gigs",
    suggestions: ["Business website", "Mobile app", "Logo design", "AI chatbot"],
    alternative: { text: "Prefer quotes?", link: "Post a brief and compare proposals", href: "/projects/new" },
  },
  earn: {
    label: "I want to earn",
    placeholder: "Your skill, e.g. “web design”",
    action: "Find work",
    searchPath: "/projects",
    suggestions: ["Web development", "Graphic design", "Video editing", "Tutoring"],
    alternative: { text: "Have a service to sell?", link: "List it for free", href: "/gigs/new" },
  },
};

/**
 * The track switch. A tablist rather than links: it changes what the search
 * beside it does, so it is a control, not navigation. Roving `tabIndex` keeps
 * it to one tab stop with arrow keys inside.
 */
export function TrackSwitch({ value, onChange }: { value: Track; onChange: (next: Track) => void }) {
  const order: Track[] = ["hire", "earn"];

  return (
    <div
      role="tablist"
      aria-label="What you want to do"
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
    router.push(term ? `${config.searchPath}?q=${encodeURIComponent(term)}` : config.searchPath);
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
          href={`${TRACKS[track].searchPath}?q=${encodeURIComponent(term)}`}
          className="inline-flex min-h-9 items-center rounded-full border border-line-strong px-3.5 text-[13px] font-medium text-fg transition-colors duration-150 hover:border-fg/40 hover:bg-sunken"
        >
          {term}
        </Link>
      ))}
    </div>
  );
}

/** The other way in on each side, under the search. */
export function TrackAlternative({ track }: { track: Track }) {
  const { text, link, href } = TRACKS[track].alternative;
  return (
    <p className="text-[13.5px] text-muted">
      {text}{" "}
      <Link href={href} className="font-medium text-accent underline-offset-4 hover:underline">
        {link} →
      </Link>
    </p>
  );
}

/* -------------------------------------------------------------------------- */
/* One account, both sides — the hero's picture                               */
/* -------------------------------------------------------------------------- */

const SIDE_LABEL: Record<Track, string> = { hire: "Buying", earn: "Selling" };

/** A week in one example account: orders going both ways. Loops. */
const ACTIVITY: Array<{ side: Track; title: string; note: string; amount: number }> = [
  { side: "earn", title: "New order · Landing page in Webflow", note: "Paid into escrow", amount: 40000 },
  { side: "hire", title: "You ordered · Product copy for 12 listings", note: "Held in escrow", amount: 12000 },
  { side: "earn", title: "You delivered · Portfolio website", note: "Waiting for the client’s approval", amount: 25000 },
  { side: "hire", title: "Logo refresh delivered", note: "Your review is due in 3 days", amount: 8500 },
  { side: "earn", title: "Portfolio website approved", note: "Released to you, after the 10% fee", amount: 22500 },
  { side: "hire", title: "You approved · Product copy", note: "Released to the freelancer", amount: 12000 },
];

const FEED_ROW = 64; // px — every row the same height, so the feed can slide by one
const FEED_VISIBLE = 3;
const FEED_EVERY_MS = 2400;

/**
 * The account's activity, scrolling up one row at a time. Built as a ticker:
 * one extra row sits below the visible window, the list slides up by a row,
 * and then the window moves on and the slide resets unseen — so the motion is
 * continuous without rendering an ever-growing list.
 */
function ActivityFeed({ active }: { active: Track }) {
  const [start, setStart] = React.useState(0);
  const [sliding, setSliding] = React.useState(false);
  const feedRef = React.useRef<HTMLDivElement>(null);
  const visible = useOnScreen(feedRef);
  const reducedMotion = React.useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia(REDUCED_MOTION).matches,
    () => false,
  );

  React.useEffect(() => {
    if (reducedMotion || !visible || sliding) return;
    const timer = window.setTimeout(() => setSliding(true), FEED_EVERY_MS);
    return () => window.clearTimeout(timer);
  }, [start, sliding, reducedMotion, visible]);

  const rows = Array.from({ length: FEED_VISIBLE + 1 }, (_, offset) => {
    const index = start + offset;
    return { key: index, event: ACTIVITY[index % ACTIVITY.length]! };
  });

  return (
    <div
      ref={feedRef}
      className="relative overflow-hidden"
      style={{
        height: FEED_ROW * FEED_VISIBLE,
        maskImage: "linear-gradient(to bottom, transparent, #000 14%, #000 86%, transparent)",
      }}
    >
      <ul
        aria-label="Example account activity"
        style={{
          transform: sliding ? `translateY(-${FEED_ROW}px)` : "none",
          transition: sliding ? "transform 700ms var(--ease-out-quint)" : "none",
        }}
        onTransitionEnd={() => {
          setSliding(false);
          setStart((value) => value + 1);
        }}
      >
        {rows.map(({ key, event }) => (
          <li
            key={key}
            className={cn(
              "flex items-center gap-3 px-6 transition-opacity duration-300",
              event.side !== active && "opacity-45",
            )}
            style={{ height: FEED_ROW }}
          >
            <span
              aria-hidden
              className={cn(
                "size-2 shrink-0 rounded-full",
                event.side === "hire" ? "bg-brand-500" : "bg-positive",
              )}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13.5px] font-semibold text-fg">{event.title}</span>
              <span className="block truncate text-[12px] text-muted">
                {SIDE_LABEL[event.side]} · {event.note}
              </span>
            </span>
            <Money amount={event.amount} className="figure shrink-0 text-[13px] font-semibold text-fg" />
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * One person's account, hiring and selling at once: who they are, what each
 * side of the account is doing, and its activity scrolling past — orders in,
 * deliveries out, money released both ways. The side matching the hero's
 * hire/earn switch is highlighted, so the control and the picture say the
 * same thing: the switch changes what you are doing, not which account.
 */
export function DualAccountCard({ active, className }: { active: Track; className?: string }) {
  const summary: Record<Track, { figure: string; caption: string }> = {
    hire: { figure: "2 orders", caption: "in escrow, waiting on freelancers" },
    earn: { figure: "Rs 62,500", caption: "earned from 3 clients this month" },
  };

  return (
    <figure className={cn("relative", className)}>
      <div className="overflow-hidden rounded-xl border border-line bg-raised shadow-e3">
        <div className="flex items-center justify-between gap-3 px-6 pt-5">
          <p className="eyebrow">Example account</p>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-positive-soft px-2.5 py-1 text-[11.5px] font-semibold text-positive">
            <Icon name="check" strokeWidth={2.6} className="size-3" />
            CNIC verified
          </span>
        </div>

        <div className="flex items-center gap-3.5 px-6 pt-4 pb-5">
          <span
            aria-hidden
            className="grid size-12 shrink-0 place-items-center rounded-full bg-brand-100 text-[16px] font-bold text-brand-900"
          >
            AK
          </span>
          <div className="min-w-0">
            <p className="text-[17px] font-bold leading-tight text-fg">Ayesha Khan</p>
            <p className="mt-0.5 text-[13px] text-muted">Lahore · Web designer · 4.9 from 23 reviews</p>
          </div>
        </div>

        <div className="grid grid-cols-2 border-y border-line">
          {(["hire", "earn"] as const).map((side) => {
            const on = side === active;
            return (
              <div
                key={side}
                className={cn(
                  "px-6 py-4 transition-colors duration-300",
                  side === "earn" && "border-l border-line",
                  on && "bg-accent-soft",
                )}
              >
                <p className={cn("eyebrow", on && "text-accent")}>{SIDE_LABEL[side]}</p>
                <p className="figure mt-1.5 text-[20px] font-semibold text-fg">{summary[side].figure}</p>
                <p className="mt-0.5 text-[12px] leading-snug text-muted">{summary[side].caption}</p>
              </div>
            );
          })}
        </div>

        <div className="flex items-center justify-between px-6 pt-4 pb-1">
          <p className="eyebrow">Activity</p>
          <span className="inline-flex items-center gap-3 text-[11.5px] text-subtle">
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden className="size-1.5 rounded-full bg-brand-500" />
              Buying
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden className="size-1.5 rounded-full bg-positive" />
              Selling
            </span>
          </span>
        </div>
        <ActivityFeed active={active} />

        <p className="border-t border-line px-6 py-3.5 text-[12.5px] text-muted">
          One profile · one set of reviews · payouts to one bank account
        </p>
      </div>
      <figcaption className="mt-5 text-[12.5px] text-subtle">
        Hire and sell from the same account — no second profile needed.
      </figcaption>
    </figure>
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

/** One field in the category grid: its name and the jobs people order in it. */
export function CategoryLink({
  slug,
  name,
  tasks,
}: {
  slug: string;
  name: string;
  tasks: string[];
}) {
  return (
    <Link href={`/gigs?category=${slug}`} className="group block border-t border-line pt-4">
      <span className="flex items-center justify-between gap-3 text-[16px] font-semibold text-fg">
        <span className="underline-offset-4 group-hover:underline">{name}</span>
        <Icon
          name="arrowRight"
          className="size-4 text-subtle transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-fg"
        />
      </span>
      <span className="mt-1.5 block text-[14px] leading-relaxed text-muted">{tasks.join(", ")}</span>
    </Link>
  );
}

/**
 * A listing card. Plain on purpose: what it is, who sells it, what it costs.
 * A seller's own photo shows when they have uploaded one; otherwise there is
 * no stand-in picture at all.
 */
export function GigCard({ gig }: { gig: GigSummary }) {
  return (
    <article className="group relative flex flex-col rounded-lg border border-line bg-raised p-5 transition-[border-color,box-shadow] duration-200 hover:border-line-strong hover:shadow-e2">
      {gig.cover_url && (
        <div className="-mx-5 -mt-5 mb-4 aspect-[16/10] overflow-hidden rounded-t-lg bg-sunken">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={gig.cover_url} alt="" loading="lazy" className="size-full object-cover" />
        </div>
      )}

      {gig.category_name && <p className="text-[12.5px] text-subtle">{gig.category_name}</p>}
      <h3 className="mt-1.5 line-clamp-2 text-[15.5px] font-semibold leading-snug text-fg">
        {/* The whole card is the link's hit area; the title is its name. */}
        <Link
          href={`/gigs/${gig.id}`}
          className="rounded-sm underline-offset-4 after:absolute after:inset-0 group-hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {gig.title}
        </Link>
      </h3>

      <div className="mt-3 flex items-center gap-2 text-[13px]">
        <Avatar name={gig.seller_name} src={gig.seller_avatar} size={22} />
        <span className="truncate text-muted">{gig.seller_name}</span>
        {gig.seller_is_student && <Badge tone="accent">Student</Badge>}
      </div>

      <div className="mt-auto flex items-end justify-between gap-3 pt-5">
        <span className="text-[12.5px] text-subtle">
          {gig.rating_count > 0 ? `★ ${gig.rating_average} (${gig.rating_count})` : "New"}
        </span>
        <span className="text-right">
          <span className="block text-[11.5px] text-subtle">Starting at</span>
          <Money amount={gig.starting_price} className="text-[16px] font-semibold text-fg" />
        </span>
      </div>
    </article>
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
