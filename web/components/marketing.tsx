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

import { Icon, Segmented, cn } from "@/components/ui";

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
    return (
      <>
        <div className="bg-aurora-live absolute inset-0" aria-hidden />
        <div className="bg-grid absolute inset-0 opacity-50" aria-hidden />
      </>
    );
  }

  return (
    <>
      <video
        className="absolute inset-0 size-full object-cover"
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
      {/* Scrim, so headline contrast never depends on what the footage shows. */}
      <div
        className="absolute inset-0 bg-linear-to-b from-surface/85 via-surface/70 to-surface"
        aria-hidden
      />
    </>
  );
}

type Intent = "hire" | "work";

const SUGGESTIONS: Record<Intent, string[]> = {
  hire: ["Web development", "Logo design", "Video editing", "SEO", "Data analysis"],
  work: ["React", "Figma", "Copywriting", "Python", "Motion graphics"],
};

export function HeroSearch() {
  const router = useRouter();
  const [intent, setIntent] = React.useState<Intent>("hire");
  const [query, setQuery] = React.useState("");

  function submit(term: string) {
    const trimmed = term.trim();
    // Both intents land on the brief browser for now; the gig catalogue that
    // "hire" will eventually point at arrives with Track B.
    const path = trimmed ? `/projects?q=${encodeURIComponent(trimmed)}` : "/projects";
    router.push(path);
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="flex justify-center">
        <Segmented
          label="What brings you here"
          value={intent}
          onChange={setIntent}
          options={[
            { value: "hire", label: "I want to hire", icon: "briefcase" },
            { value: "work", label: "I want to work", icon: "user" },
          ]}
        />
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
            "group flex items-center gap-2 rounded-xl border border-line bg-raised p-2 shadow-e2",
            "transition-shadow duration-200 focus-within:border-accent focus-within:shadow-e3",
          )}
        >
          <Icon name="search" className="ml-2 size-5 shrink-0 text-subtle" />
          <input
            id="hero-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={
              intent === "hire"
                ? "What do you need done?"
                : "What kind of work are you looking for?"
            }
            className="h-11 min-w-0 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-subtle"
          />
          <button
            type="submit"
            className={cn(
              "inline-flex h-11 shrink-0 items-center gap-1.5 rounded-lg bg-accent px-5",
              "text-sm font-medium text-on-accent transition-colors duration-150",
              "hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            )}
          >
            Search
          </button>
        </div>
      </form>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        <span className="text-[12.5px] text-subtle">Popular:</span>
        {SUGGESTIONS[intent].map((term) => (
          <button
            key={term}
            type="button"
            onClick={() => submit(term)}
            className={cn(
              "rounded-full border border-line bg-raised/70 px-3 py-1 text-[12.5px] text-muted backdrop-blur",
              "transition-colors duration-150 hover:border-line-strong hover:text-fg",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            )}
          >
            {term}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * A horizontally scrollable row that keeps keyboard and touch behaviour intact
 * — no custom drag handling, just a scroll container with snap points and
 * buttons that nudge it.
 */
export function ScrollRow({ children }: { children: React.ReactNode }) {
  const ref = React.useRef<HTMLDivElement>(null);

  const nudge = (direction: 1 | -1) => {
    ref.current?.scrollBy({ left: direction * 320, behavior: "smooth" });
  };

  return (
    <div className="relative">
      <div
        ref={ref}
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {children}
      </div>
      <div className="mt-1 flex justify-end gap-2">
        {([-1, 1] as const).map((direction) => (
          <button
            key={direction}
            type="button"
            onClick={() => nudge(direction)}
            aria-label={direction === -1 ? "Scroll left" : "Scroll right"}
            className="grid size-8 place-items-center rounded-full border border-line bg-raised text-muted transition-colors hover:border-line-strong hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <Icon
              name="chevronLeft"
              className={cn("size-4", direction === 1 && "rotate-180")}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

export function CategoryTile({
  href,
  icon,
  name,
  count,
}: {
  href: string;
  icon: Parameters<typeof Icon>[0]["name"];
  name: string;
  count: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex flex-col gap-3 rounded-xl border border-line bg-raised p-5",
        "transition-[border-color,box-shadow,transform] duration-200",
        "hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-e2",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
      )}
    >
      <span className="grid size-10 place-items-center rounded-lg bg-accent-soft text-accent transition-colors duration-200 group-hover:bg-accent group-hover:text-on-accent">
        <Icon name={icon} className="size-5" />
      </span>
      <span>
        <span className="block text-[14px] font-medium text-fg">{name}</span>
        <span className="mt-0.5 block text-[12px] text-subtle">{count}</span>
      </span>
    </Link>
  );
}
