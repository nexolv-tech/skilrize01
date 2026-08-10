"use client";

/**
 * Marketing surfaces.
 *
 * Photography carries this page, the way it carries every marketplace at this
 * size — a catalogue that shows no work does not read as a catalogue. Images
 * live in `web/public/img`, are served from our own origin (the CSP allows
 * `img-src 'self'` and nothing else), and go through `next/image` so each one
 * ships as AVIF/WebP at the size actually requested, lazily, in a box whose
 * height is reserved before it loads.
 *
 * The organising idea underneath: this platform carries two hiring models that
 * the competitors carry one of each, so the choice between them is the hero's
 * primary control rather than a line of copy further down.
 */

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Icon, Money, cn, type IconName } from "@/components/ui";

/* -------------------------------------------------------------------------- */
/* Hero media                                                                 */
/* -------------------------------------------------------------------------- */

/**
 * The hero backdrop: a still photograph with a video laid over it.
 *
 * Three things this has to get right, none of them optional.
 *
 * **The photograph is always rendered**, underneath. It is the first paint, it
 * covers the seconds before the video has buffered, and it is the whole
 * backdrop for anyone the video never loads for.
 *
 * **Reduced motion is honoured before the download, not after it.** Hiding the
 * video in CSS would still pull four megabytes over the wire for somebody who
 * asked the operating system for less movement. The element is not rendered at
 * all until we have checked, which is also why the check lives in an effect —
 * `matchMedia` does not exist during the server render.
 *
 * **It can be stopped.** WCAG 2.2.2 requires a control for anything that moves
 * for more than five seconds, and a looping hero moves forever.
 */
export function HeroMedia({
  poster,
  video,
  alt = "",
}: {
  poster: string;
  video: string;
  alt?: string;
}) {
  const [motionOk, setMotionOk] = React.useState(false);
  const [playing, setPlaying] = React.useState(true);
  const ref = React.useRef<HTMLVideoElement>(null);

  React.useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setMotionOk(!query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  function toggle() {
    const element = ref.current;
    if (!element) return;
    if (element.paused) {
      void element.play();
      setPlaying(true);
    } else {
      element.pause();
      setPlaying(false);
    }
  }

  return (
    <>
      <Image src={poster} alt={alt} fill priority sizes="100vw" className="-z-30 object-cover" />

      {motionOk && (
        <>
          <video
            ref={ref}
            autoPlay
            muted
            loop
            playsInline
            preload="metadata"
            aria-hidden
            className="absolute inset-0 -z-20 size-full object-cover"
          >
            <source src={video} type="video/mp4" />
          </video>

          <button
            type="button"
            onClick={toggle}
            aria-label={playing ? "Pause background video" : "Play background video"}
            className={cn(
              "absolute bottom-24 right-5 z-10 grid size-11 cursor-pointer place-items-center",
              "rounded-full border border-white/25 bg-black/40 text-white backdrop-blur-md",
              "transition-colors duration-200 hover:bg-black/60",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white",
            )}
          >
            {playing ? (
              <svg viewBox="0 0 24 24" className="size-4" fill="currentColor" aria-hidden>
                <rect x="6" y="5" width="4" height="14" rx="1" />
                <rect x="14" y="5" width="4" height="14" rx="1" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="size-4" fill="currentColor" aria-hidden>
                <path d="M8 5.5v13l11-6.5z" />
              </svg>
            )}
          </button>
        </>
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Track                                                                      */
/* -------------------------------------------------------------------------- */

export type Track = "services" | "projects";

export const TRACKS: Record<
  Track,
  { label: string; placeholder: string; action: string; suggestions: string[] }
> = {
  services: {
    label: "Buy a service",
    placeholder: "Try “logo design” or “landing page”",
    action: "Search",
    suggestions: ["Logo design", "Landing page", "Video editing", "SEO audit"],
  },
  projects: {
    label: "Post a brief",
    placeholder: "Describe what you need built",
    action: "Get proposals",
    suggestions: ["Mobile app", "Data pipeline", "Brand identity", "Tech writing"],
  },
};

/**
 * The track switch. A tablist rather than links: it re-renders the search and
 * the suggestions beside it, so it is a control, not navigation. Roving
 * `tabIndex` keeps it to one tab stop with arrow keys inside.
 */
export function TrackSwitch({
  value,
  onChange,
  tone = "light",
}: {
  value: Track;
  onChange: (next: Track) => void;
  tone?: "light" | "dark";
}) {
  const order: Track[] = ["services", "projects"];

  return (
    <div
      role="tablist"
      aria-label="How you want to hire"
      className={cn(
        "inline-flex rounded-full p-1",
        tone === "dark"
          ? "border border-white/20 bg-black/35 backdrop-blur-md"
          : "border border-line bg-raised shadow-e1",
      )}
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
              /* 44px, not the 40px this would otherwise want to be: it is the
                 first control on the page and the smallest reliable touch
                 target. */
              "min-h-11 cursor-pointer rounded-full px-5 text-[13.5px] font-medium",
              "transition-colors duration-200",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white",
              active
                ? "bg-white text-ink-900 shadow-e1"
                : tone === "dark"
                  ? "text-white/70 hover:text-white"
                  : "text-muted hover:text-fg",
            )}
          >
            {TRACKS[track].label}
          </button>
        );
      })}
    </div>
  );
}

/** The hero search. Submits into whichever surface the track points at. */
export function HeroSearch({ track }: { track: Track }) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const config = TRACKS[track];

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const term = query.trim();
    if (track === "projects") {
      router.push(term ? `/projects?q=${encodeURIComponent(term)}` : "/projects/new");
      return;
    }
    router.push(term ? `/search?q=${encodeURIComponent(term)}` : "/gigs");
  }

  return (
    <form
      onSubmit={submit}
      role="search"
      className="flex items-center gap-2 rounded-xl bg-white p-2 shadow-e3"
    >
      <Icon name="search" className="ml-2.5 size-5 shrink-0 text-ink-400" />
      <label htmlFor="hero-search" className="sr-only">
        {config.action}
      </label>
      <input
        id="hero-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={config.placeholder}
        className={cn(
          "h-12 min-w-0 flex-1 bg-transparent text-[15px] text-ink-900",
          "placeholder:text-ink-400 focus:outline-none",
        )}
      />
      {/* Icon-only on phones. At 375px a worded button leaves the input about
          nine characters wide, which is narrower than the placeholder asking
          the question — the label is the first thing that should give way. */}
      <button
        type="submit"
        aria-label={config.action}
        className={cn(
          "grid h-12 shrink-0 cursor-pointer place-items-center rounded-lg bg-ink-900",
          "w-12 text-white transition-colors duration-200 hover:bg-ink-800 sm:w-auto sm:px-6",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        )}
      >
        <Icon name="arrowRight" className="size-5 sm:hidden" />
        <span className="hidden text-[14px] font-medium sm:inline">{config.action}</span>
      </button>
    </form>
  );
}

/** The pill rail under the hero search, mirroring the reference marketplaces. */
export function SuggestionPills({ track }: { track: Track }) {
  return (
    <div className="flex flex-wrap gap-2.5">
      {TRACKS[track].suggestions.map((term) => (
        <Link
          key={term}
          href={
            track === "projects"
              ? `/projects?q=${encodeURIComponent(term)}`
              : `/search?q=${encodeURIComponent(term)}`
          }
          className={cn(
            "inline-flex min-h-11 items-center gap-2 rounded-full border border-white/30",
            "bg-white/10 px-4 text-[13px] text-white backdrop-blur-md",
            "transition-colors duration-200 hover:bg-white/20",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white",
          )}
        >
          {term}
          <Icon name="arrowRight" className="size-3.5" />
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
    <div className="flex flex-wrap items-end justify-between gap-5 pb-8">
      <div className="max-w-2xl space-y-2.5">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2 className="heading-sans text-[clamp(1.6rem,3vw,2.3rem)] leading-tight text-fg">
          {title}
        </h2>
        {description && (
          <p className="text-[15px] leading-relaxed text-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/** A horizontally scrollable rail with keyboard-reachable arrows. */
export function ScrollRow({ children }: { children: React.ReactNode }) {
  const ref = React.useRef<HTMLDivElement>(null);

  function nudge(direction: 1 | -1) {
    ref.current?.scrollBy({ left: direction * 340, behavior: "smooth" });
  }

  return (
    <div className="relative">
      <div
        ref={ref}
        className="no-bar -mx-5 flex snap-x snap-mandatory gap-5 overflow-x-auto px-5 pb-2"
      >
        {children}
      </div>
      <div className="mt-6 flex justify-end gap-2">
        {([-1, 1] as const).map((direction) => (
          <button
            key={direction}
            type="button"
            onClick={() => nudge(direction)}
            aria-label={direction === -1 ? "Scroll left" : "Scroll right"}
            className={cn(
              "grid size-11 cursor-pointer place-items-center rounded-full border border-line",
              "bg-raised text-muted transition-colors duration-200",
              "hover:border-line-strong hover:text-fg",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            )}
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

/**
 * Category tiles stay iconographic while service cards carry photographs.
 * That split is deliberate and both reference marketplaces make it: a category
 * is an abstraction and any single photo misrepresents it, whereas a service is
 * a specific piece of work and a photo is the most honest thing you can show.
 */
export function CategoryTile({
  slug,
  name,
  icon,
  blurb,
}: {
  slug: string;
  name: string;
  icon: IconName;
  blurb: string;
}) {
  return (
    <Link
      href={`/gigs?category=${slug}`}
      className={cn(
        "lift group flex flex-col justify-between gap-7 rounded-xl border border-line",
        "bg-raised p-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "grid size-11 place-items-center rounded-lg bg-accent-soft text-accent",
          "transition-colors duration-200 group-hover:bg-accent group-hover:text-on-accent",
        )}
      >
        <Icon name={icon} className="size-5" />
      </span>
      <span>
        <span className="block text-[14.5px] font-medium text-fg">{name}</span>
        <span className="mt-0.5 block text-[12.5px] text-subtle">{blurb}</span>
      </span>
    </Link>
  );
}

export interface ServiceCardData {
  id: number;
  title: string;
  category: string;
  image: string;
  alt: string;
  price: number;
  rating: number;
  reviews: number;
  seller: string;
  level: string;
}

export function ServiceCard({ item, href }: { item: ServiceCardData; href: string }) {
  return (
    <Link
      href={href}
      className={cn(
        "lift group flex w-[19.5rem] shrink-0 snap-start flex-col overflow-hidden rounded-xl",
        "border border-line bg-raised",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
      )}
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-sunken">
        <Image
          src={item.image}
          alt={item.alt}
          fill
          sizes="320px"
          className="object-cover transition-transform duration-500 group-hover:scale-[1.04]"
        />
        <span className="absolute left-3 top-3 rounded-full bg-black/60 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
          {item.level}
        </span>
      </div>

      <div className="flex flex-1 flex-col p-4">
        <p className="text-[11px] font-medium uppercase tracking-wider text-subtle">
          {item.category}
        </p>
        <p className="mt-1.5 line-clamp-2 text-[14.5px] font-medium leading-snug text-fg">
          {item.title}
        </p>

        <div className="mt-2 flex items-center gap-1.5 text-[12px]">
          <Icon name="star" className="size-3.5 text-warn-500" />
          <span className="tabular font-medium text-fg">{item.rating.toFixed(1)}</span>
          <span className="text-subtle">({item.reviews})</span>
        </div>

        <div className="mt-auto flex items-end justify-between gap-3 border-t border-line pt-3.5">
          <span className="truncate text-[12px] text-muted">{item.seller}</span>
          <span className="text-right">
            <span className="block text-[10.5px] uppercase tracking-wide text-subtle">
              From
            </span>
            <Money amount={item.price} className="text-[15px] font-semibold text-fg" />
          </span>
        </div>
      </div>
    </Link>
  );
}

/** A photograph with a caption card overlapping it, used to anchor a band. */
export function PhotoFigure({
  src,
  alt,
  caption,
  captionBody,
  priority = false,
  className,
}: {
  src: string;
  alt: string;
  caption?: string;
  captionBody?: string;
  priority?: boolean;
  className?: string;
}) {
  return (
    <figure className={cn("relative", className)}>
      <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-sunken">
        <Image
          src={src}
          alt={alt}
          fill
          priority={priority}
          sizes="(max-width: 1024px) 100vw, 560px"
          className="object-cover"
        />
      </div>
      {caption && (
        <figcaption
          className={cn(
            "absolute -bottom-5 left-5 right-10 rounded-xl border border-line bg-raised",
            "p-4 shadow-e3 sm:right-16",
          )}
        >
          <p className="text-[13.5px] font-semibold text-fg">{caption}</p>
          {captionBody && (
            <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{captionBody}</p>
          )}
        </figcaption>
      )}
    </figure>
  );
}
