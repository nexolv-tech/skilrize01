"use client";

/**
 * Interactive pieces of the marketing pages.
 *
 * Kept as a small client island so the landing page itself stays a server
 * component — category and brief pages are the primary organic search-engine
 * landing surface, and forfeiting server rendering there would cost the main
 * acquisition channel.
 */

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { CoverArt, type Motif } from "@/components/artwork";
import { Icon, Stars, cn, type IconName } from "@/components/ui";

/**
 * The hero backdrop.
 *
 * Set `NEXT_PUBLIC_HERO_VIDEO` to a file in `public/` and this plays it —
 * muted, looping, inline, with `poster` covering the gap before the first
 * frame. With no video configured it falls back to an animated gradient field,
 * which is the default rather than a placeholder: it costs no download, cannot
 * be blocked by an autoplay policy, and respects reduced-motion for free.
 */
export function HeroBackdrop() {
  const video = process.env.NEXT_PUBLIC_HERO_VIDEO;
  const poster = process.env.NEXT_PUBLIC_HERO_POSTER;

  if (!video) {
    // The `.hero-dark` surface underneath already carries the colour field;
    // this only adds the masked grid that gives it a sense of scale.
    return <div className="hero-grid absolute inset-0" aria-hidden />;
  }

  return (
    <>
      <video
        className="absolute inset-0 size-full object-cover opacity-45"
        src={video}
        poster={poster}
        autoPlay
        muted
        loop
        playsInline
        // Decorative: it carries no information the copy does not.
        aria-hidden
        tabIndex={-1}
      />
      {/* Scrim, so headline contrast never depends on what the footage shows.
          The hero copy is white on near-black, and that has to hold whatever
          frame the video happens to be paused on. */}
      <div
        className="absolute inset-0 bg-linear-to-br from-ink-1000/92 via-ink-1000/75 to-ink-950/92"
        aria-hidden
      />
      <div className="hero-grid absolute inset-0" aria-hidden />
    </>
  );
}

type Intent = "hire" | "work";

const SUGGESTIONS: Record<Intent, string[]> = {
  hire: ["Web development", "Logo design", "Video editing", "SEO", "Data analysis"],
  work: ["React", "Figma", "Copywriting", "Python", "Motion graphics"],
};

/**
 * The hero search, on the dark hero surface.
 *
 * Built against `white/x` rather than the semantic tokens on purpose: this sits
 * on a fixed near-black panel that does not flip with the theme, so resolving
 * `--fg` here would make the control invert into illegibility in light mode.
 * A surface that is deliberately one colour in both themes has to be styled
 * that way too.
 */
export function HeroSearch() {
  const router = useRouter();
  const [intent, setIntent] = React.useState<Intent>("hire");
  const [query, setQuery] = React.useState("");

  function submit(term: string) {
    const trimmed = term.trim();
    // "Hire" browses ready-made services; "work" browses open briefs. The two
    // intents genuinely want different catalogues, so they route apart.
    const base = intent === "hire" ? "/gigs" : "/projects";
    router.push(trimmed ? `${base}?q=${encodeURIComponent(trimmed)}` : base);
  }

  return (
    <div className="w-full">
      <div
        role="tablist"
        aria-label="What brings you here"
        className="inline-flex items-center gap-1 rounded-full border border-white/12 bg-white/8 p-1 backdrop-blur"
      >
        {(
          [
            { value: "hire", label: "I want to hire", icon: "briefcase" },
            { value: "work", label: "I want to work", icon: "user" },
          ] as const
        ).map((option) => {
          const active = option.value === intent;
          return (
            <button
              key={option.value}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() => setIntent(option.value)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13.5px] font-medium",
                "transition-colors duration-200",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white",
                active ? "bg-white text-ink-950" : "text-white/70 hover:text-white",
              )}
            >
              <Icon name={option.icon} className="size-3.5" />
              {option.label}
            </button>
          );
        })}
      </div>

      <form
        role="search"
        className="mt-5"
        onSubmit={(event) => {
          event.preventDefault();
          submit(query);
        }}
      >
        <label htmlFor="hero-search" className="sr-only">
          {intent === "hire" ? "Search for a service" : "Search for work"}
        </label>
        <div
          className={cn(
            "flex items-center gap-2 rounded-2xl bg-white p-2 shadow-[0_24px_60px_-12px_rgb(0_0_0_/_0.6)]",
            "ring-1 ring-white/20 transition-shadow duration-300",
            "focus-within:ring-2 focus-within:ring-brand-400",
          )}
        >
          <Icon name="search" className="ml-3 size-5 shrink-0 text-ink-500" />
          <input
            id="hero-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={
              intent === "hire"
                ? "What do you need done?"
                : "What kind of work are you looking for?"
            }
            className="h-13 min-w-0 flex-1 bg-transparent text-[16px] text-ink-950 outline-none placeholder:text-ink-400"
          />
          <button
            type="submit"
            className={cn(
              "inline-flex h-13 shrink-0 items-center gap-2 rounded-xl bg-ink-950 px-7",
              "text-[15px] font-medium text-white transition-colors duration-150",
              "hover:bg-ink-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400",
            )}
          >
            <Icon name="search" className="size-4 sm:hidden" />
            <span className="hidden sm:inline">Search</span>
          </button>
        </div>
      </form>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="text-[12.5px] text-white/50">Popular:</span>
        {SUGGESTIONS[intent].map((term) => (
          <button
            key={term}
            type="button"
            onClick={() => submit(term)}
            className={cn(
              "rounded-full border border-white/15 px-3.5 py-1.5 text-[12.5px] text-white/75 backdrop-blur",
              "transition-colors duration-150 hover:border-white/40 hover:bg-white/10 hover:text-white",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white",
            )}
          >
            {term}
          </button>
        ))}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Carousel                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * A horizontally scrollable row that keeps keyboard and touch behaviour intact
 * — no custom drag handling, just a scroll container with snap points and
 * buttons that nudge it.
 *
 * The arrows sit beside the section heading rather than floating over the
 * content: overlaid arrows have to cover a card to be reachable, and on a
 * touch device they cover it for no benefit at all.
 */
export function ScrollRow({
  children,
  controls = "below",
}: {
  children: React.ReactNode;
  controls?: "below" | "none";
}) {
  const ref = React.useRef<HTMLDivElement>(null);

  const nudge = (direction: 1 | -1) => {
    ref.current?.scrollBy({ left: direction * 340, behavior: "smooth" });
  };

  return (
    <div className="relative">
      <div
        ref={ref}
        className="no-bar flex snap-x snap-mandatory gap-5 overflow-x-auto pb-2"
      >
        {children}
      </div>
      {controls === "below" && (
        <div className="mt-4 flex justify-end gap-2">
          {([-1, 1] as const).map((direction) => (
            <button
              key={direction}
              type="button"
              onClick={() => nudge(direction)}
              aria-label={direction === -1 ? "Scroll left" : "Scroll right"}
              className="grid size-9 place-items-center rounded-full border border-line bg-raised text-muted transition-colors hover:border-line-strong hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              <Icon
                name="chevronLeft"
                className={cn("size-4", direction === 1 && "rotate-180")}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Cards                                                                      */
/* -------------------------------------------------------------------------- */

export function CategoryTile({
  href,
  icon,
  name,
  count,
}: {
  href: string;
  icon: IconName;
  name: string;
  count: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "lift group flex flex-col gap-4 rounded-xl border border-line bg-raised p-5",
        "hover:border-accent/40",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
      )}
    >
      <span className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent transition-colors duration-200 group-hover:bg-accent group-hover:text-on-accent">
        <Icon name={icon} className="size-5" />
      </span>
      <span>
        <span className="block text-[14.5px] font-medium text-fg">{name}</span>
        <span className="mt-1 block text-[12.5px] text-subtle">{count}</span>
      </span>
    </Link>
  );
}

export interface ServiceCardData {
  title: string;
  slug: string;
  motif: Motif;
  seller: string;
  level: string;
  rating: number;
  reviews: number;
  from: string;
}

/**
 * A catalogue listing as it appears in a browse row.
 *
 * The shape mirrors the real gig card used inside the app rather than being a
 * marketing-only invention — what a visitor sees on the landing page is what
 * they get after signing up, which is the cheapest kind of trust to earn.
 */
export function ServiceCard({ item, href }: { item: ServiceCardData; href: string }) {
  return (
    <Link
      href={href}
      className={cn(
        "lift group flex w-[min(82vw,20.5rem)] shrink-0 snap-start flex-col overflow-hidden",
        "rounded-2xl border border-line bg-raised shadow-e1 hover:border-accent/40",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
      )}
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-sunken">
        <CoverArt
          seed={item.title}
          motif={item.motif}
          rounded={false}
          className="transition-transform duration-[700ms] ease-out group-hover:scale-[1.07]"
        />
        {/* Base scrim: the artwork palette is seeded per listing, so a chip
            placed on it needs its own contrast floor rather than trusting
            whatever colour happened to land underneath. */}
        <div
          className="absolute inset-x-0 bottom-0 h-20 bg-linear-to-t from-black/55 to-transparent"
          aria-hidden
        />
        <span className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-black/45 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
          {item.level}
        </span>
      </div>

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-center gap-2">
          <span className="grid size-7 shrink-0 place-items-center rounded-full bg-linear-to-br from-brand-400 to-brand-600 text-[11px] font-semibold text-white">
            {item.seller.slice(0, 1)}
          </span>
          <span className="truncate text-[13px] font-medium text-fg">{item.seller}</span>
          <span className="ml-auto flex shrink-0 items-center gap-1">
            <Icon name="star" className="size-3.5 fill-warn-500 text-warn-500" strokeWidth={0} />
            <span className="text-[12.5px] font-semibold text-fg">{item.rating.toFixed(1)}</span>
            <span className="text-[12px] text-subtle">({item.reviews})</span>
          </span>
        </div>

        <p className="mt-3.5 line-clamp-2 min-h-[2.8em] text-[15px] font-medium leading-snug text-fg transition-colors group-hover:text-accent">
          {item.title}
        </p>

        <div className="mt-auto flex items-baseline justify-between border-t border-line pt-4">
          <span className="text-[11px] uppercase tracking-[0.06em] text-subtle">Starting at</span>
          <span className="tabular text-[17px] font-semibold text-fg">Rs {item.from}</span>
        </div>
      </div>
    </Link>
  );
}

/* -------------------------------------------------------------------------- */
/* Hero composition                                                           */
/* -------------------------------------------------------------------------- */

/**
 * The product, drawn rather than photographed.
 *
 * Marketplaces of this kind normally anchor a hero on stock photography of
 * someone at a laptop, which says nothing and licenses badly. This shows the
 * three moments that actually distinguish the platform — a listing, money held
 * in escrow, and a release — as a stack of real interface cards. It ships as
 * markup, so it is theme-aware, sharp at any density, and costs no download.
 */
export function HeroComposition() {
  return (
    <div className="relative w-full select-none" aria-hidden>
      {/* Listing — the widest card, and the entry point of the story. */}
      <div className="glass-dark rounded-2xl p-4 text-white">
        <div className="flex items-center gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-linear-to-br from-brand-400 to-brand-600 text-[14px] font-semibold">
            S
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[14px] font-medium">React &amp; Django web app</p>
            <p className="text-[12px] text-white/55">Sana M. · Top Rated Seller</p>
          </div>
          <span className="tabular shrink-0 text-[15px] font-semibold">Rs 45,000</span>
        </div>
        <div className="mt-3.5 flex items-center gap-1.5 border-t border-white/10 pt-3.5">
          <Stars value={5} size={12} />
          <span className="text-[12px] text-white/65">5.0 · 128 reviews</span>
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-money-500/15 px-2 py-0.5 text-[11px] font-medium text-money-400">
            <Icon name="check" className="size-3" strokeWidth={3} />
            ID verified
          </span>
        </div>
      </div>

      {/* Escrow — offset right, the middle beat. */}
      <div className="glass-dark ml-auto mt-4 w-[88%] rounded-2xl p-4 text-white">
        <div className="flex items-center gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-500/25 text-brand-200">
            <Icon name="lock" className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium">Milestone 2 funded</p>
            <p className="text-[11.5px] text-white/50">Held in escrow until you accept</p>
          </div>
          <span className="tabular text-[14px] font-semibold">Rs 15,000</span>
        </div>
        <div className="mt-3.5 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div className="h-full w-2/3 rounded-full bg-linear-to-r from-brand-400 to-brand-200" />
        </div>
        <p className="mt-2 text-[11px] text-white/45">2 of 3 milestones complete</p>
      </div>

      {/* Release — offset left, the payoff. */}
      <div className="glass-dark mt-4 w-[76%] rounded-2xl p-4 text-white">
        <div className="flex items-center gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-money-500/20 text-money-400">
            <Icon name="wallet" className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium">Payment released</p>
            <p className="text-[11.5px] text-white/50">Cleared to your wallet</p>
          </div>
          <span className="tabular text-[14px] font-semibold text-money-400">+ Rs 15,000</span>
        </div>
      </div>
    </div>
  );
}
