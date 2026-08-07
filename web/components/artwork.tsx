/**
 * Generated cover art.
 *
 * A marketplace catalogue is mostly pictures, and every listing needs one from
 * the moment it is published — long before a seller has uploaded anything. So
 * every gig gets a deterministic piece of vector art derived from its id and
 * category: the same listing always looks the same, related listings share a
 * visual family, and an empty catalogue still reads as a real product.
 *
 * Vector rather than photography is a deliberate trade. It costs no network
 * requests, has no licensing question, stays crisp at any size, follows the
 * light/dark theme, and never shows a stock photo of a smiling stranger who has
 * nothing to do with the work. When a seller uploads a real cover, that wins —
 * this is the floor, not the ceiling.
 */
import * as React from "react";

import { cn } from "./ui";

/** Stable small hash, so the same input always yields the same artwork. */
function hash(seed: string): number {
  let value = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    value ^= seed.charCodeAt(index);
    value = Math.imul(value, 16777619);
  }
  return Math.abs(value);
}

/** Six palettes, chosen to sit together in a grid without clashing. */
const PALETTES: Array<[string, string, string]> = [
  ["#5B41EC", "#8F80FD", "#E6E3FF"], // indigo
  ["#0E7C86", "#22C1CC", "#D4F5F7"], // teal
  ["#B4418E", "#EE7FC9", "#FBE3F3"], // magenta
  ["#C2560F", "#F59E0B", "#FEF0DA"], // amber
  ["#1F6B45", "#34D399", "#DCFCE7"], // emerald
  ["#3B3F8F", "#7C82E8", "#E4E6FB"], // periwinkle
];

export type Motif =
  | "code"
  | "design"
  | "writing"
  | "video"
  | "marketing"
  | "data"
  | "business"
  | "academic";

const MOTIF_BY_CATEGORY: Record<string, Motif> = {
  "Development & IT": "code",
  "Design & Creative": "design",
  "Writing & Translation": "writing",
  "Video & Animation": "video",
  "Marketing & Sales": "marketing",
  "Data & Analytics": "data",
  "Business & Admin": "business",
  "Academic Support": "academic",
};

export function motifFor(categoryName?: string | null): Motif {
  if (!categoryName) return "design";
  return MOTIF_BY_CATEGORY[categoryName] ?? "design";
}

/* -------------------------------------------------------------------------- */
/* Motif compositions                                                         */
/* -------------------------------------------------------------------------- */

/**
 * Each motif draws a loose abstraction of the work itself — a code window, a
 * palette of swatches, a video timeline — rather than a literal icon. Enough to
 * read at a glance in a grid, quiet enough not to shout over the title.
 */
function Composition({
  motif,
  seed,
  ink,
  light,
}: {
  motif: Motif;
  seed: number;
  ink: string;
  light: string;
}) {
  const jitter = (index: number, spread: number) => ((seed >> (index * 3)) % spread) - spread / 2;

  switch (motif) {
    case "code":
      return (
        <g>
          <rect x="70" y="52" width="180" height="116" rx="10" fill={light} opacity="0.9" />
          <rect x="70" y="52" width="180" height="20" rx="10" fill={ink} opacity="0.28" />
          {[0, 1, 2].map((dot) => (
            <circle key={dot} cx={84 + dot * 13} cy="62" r="3.5" fill={light} opacity="0.85" />
          ))}
          {[0, 1, 2, 3, 4].map((line) => (
            <rect
              key={line}
              x={84 + (line % 2 === 0 ? 0 : 14)}
              y={86 + line * 15}
              width={Math.max(34, 118 - (line * 17 + Math.abs(jitter(line, 30))))}
              height="7"
              rx="3.5"
              fill={ink}
              opacity={0.18 + (line % 3) * 0.12}
            />
          ))}
        </g>
      );

    case "design":
      return (
        <g>
          {[0, 1, 2, 3].map((swatch) => (
            <rect
              key={swatch}
              x={72 + swatch * 42}
              y={64 + Math.abs(jitter(swatch, 22))}
              width="34"
              height="66"
              rx="8"
              fill={swatch % 2 === 0 ? light : ink}
              opacity={swatch % 2 === 0 ? 0.92 : 0.34}
            />
          ))}
          <circle cx="176" cy="150" r="24" fill={light} opacity="0.85" />
          <circle cx="204" cy="150" r="24" fill={ink} opacity="0.3" />
        </g>
      );

    case "writing":
      return (
        <g>
          <rect x="76" y="48" width="168" height="124" rx="10" fill={light} opacity="0.9" />
          {[0, 1, 2, 3, 4, 5].map((line) => (
            <rect
              key={line}
              x="94"
              y={70 + line * 17}
              width={line === 5 ? 62 : 132 - Math.abs(jitter(line, 40))}
              height="6"
              rx="3"
              fill={ink}
              opacity={line === 0 ? 0.42 : 0.2}
            />
          ))}
        </g>
      );

    case "video":
      return (
        <g>
          <rect x="70" y="52" width="180" height="96" rx="10" fill={ink} opacity="0.3" />
          <path d="M148 84 L178 100 L148 116 Z" fill={light} opacity="0.95" />
          {[0, 1, 2, 3, 4, 5, 6, 7].map((frame) => (
            <rect
              key={frame}
              x={72 + frame * 22.5}
              y="156"
              width="18"
              height={12 + Math.abs(jitter(frame, 16))}
              rx="3"
              fill={light}
              opacity={0.5 + (frame % 3) * 0.18}
            />
          ))}
        </g>
      );

    case "marketing":
      return (
        <g>
          {[0, 1, 2, 3, 4].map((bar) => {
            const height = 32 + ((seed >> (bar * 2)) % 70);
            return (
              <rect
                key={bar}
                x={78 + bar * 34}
                y={168 - height}
                width="22"
                height={height}
                rx="6"
                fill={bar === 3 ? light : ink}
                opacity={bar === 3 ? 0.95 : 0.32}
              />
            );
          })}
          <path
            d="M84 96 L118 74 L152 88 L186 56 L220 66"
            stroke={light}
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
            opacity="0.9"
          />
        </g>
      );

    case "data":
      return (
        <g>
          <circle cx="118" cy="110" r="46" fill={ink} opacity="0.28" />
          <path d="M118 64 A46 46 0 0 1 164 110 L118 110 Z" fill={light} opacity="0.95" />
          {[0, 1, 2, 3].map((row) => (
            <rect
              key={row}
              x="186"
              y={76 + row * 20}
              width={Math.max(24, 64 - row * 12)}
              height="9"
              rx="4.5"
              fill={light}
              opacity={0.75 - row * 0.14}
            />
          ))}
        </g>
      );

    case "business":
      return (
        <g>
          {[0, 1, 2].map((sheet) => (
            <rect
              key={sheet}
              x={82 + sheet * 16}
              y={58 + sheet * 12}
              width="132"
              height="104"
              rx="9"
              fill={sheet === 2 ? light : ink}
              opacity={sheet === 2 ? 0.94 : 0.22 + sheet * 0.1}
            />
          ))}
          {[0, 1, 2].map((line) => (
            <rect
              key={line}
              x="130"
              y={92 + line * 18}
              width={line === 2 ? 44 : 82}
              height="6"
              rx="3"
              fill={ink}
              opacity="0.28"
            />
          ))}
        </g>
      );

    case "academic":
      return (
        <g>
          <path d="M76 70 Q160 50 244 70 L244 158 Q160 138 76 158 Z" fill={light} opacity="0.92" />
          <path d="M160 60 L160 148" stroke={ink} strokeWidth="4" opacity="0.3" />
          {[0, 1, 2].map((line) => (
            <React.Fragment key={line}>
              <rect x="96" y={88 + line * 18} width="48" height="5" rx="2.5" fill={ink} opacity="0.24" />
              <rect x="176" y={88 + line * 18} width="48" height="5" rx="2.5" fill={ink} opacity="0.24" />
            </React.Fragment>
          ))}
        </g>
      );
  }
}

/* -------------------------------------------------------------------------- */

export function CoverArt({
  seed,
  motif = "design",
  className,
  rounded = true,
}: {
  /** Anything stable and unique — a gig id, a slug. */
  seed: string | number;
  motif?: Motif;
  className?: string;
  rounded?: boolean;
}) {
  const value = hash(String(seed));
  const palette = PALETTES[value % PALETTES.length]!;
  const [deep, mid, light] = palette;
  const id = `art-${value.toString(36)}`;
  const angle = value % 4;

  return (
    <svg
      viewBox="0 0 320 220"
      className={cn("h-full w-full", rounded && "rounded-lg", className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
    >
      <defs>
        <linearGradient
          id={id}
          x1={angle % 2 === 0 ? "0" : "1"}
          y1="0"
          x2={angle < 2 ? "1" : "0"}
          y2="1"
        >
          <stop offset="0%" stopColor={deep} />
          <stop offset="100%" stopColor={mid} />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx="0.7" cy="0.2" r="0.9">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.32" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect width="320" height="220" fill={`url(#${id})`} />
      <rect width="320" height="220" fill={`url(#${id}-glow)`} />

      {/* Two soft orbs, positioned from the seed, to break up the field. */}
      <circle cx={40 + (value % 60)} cy={190 - (value % 40)} r="70" fill="#ffffff" opacity="0.07" />
      <circle cx={280 - (value % 50)} cy={30 + (value % 30)} r="52" fill="#000000" opacity="0.06" />

      <Composition motif={motif} seed={value} ink={deep} light={light} />
    </svg>
  );
}

/**
 * A cover slot: shows the seller's uploaded image when there is one, and falls
 * back to generated art when there is not. Every catalogue surface uses this so
 * the two cases are never handled differently by accident.
 */
export function Cover({
  src,
  seed,
  motif,
  alt = "",
  className,
}: {
  src?: string | null;
  seed: string | number;
  motif?: Motif;
  alt?: string;
  className?: string;
}) {
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={alt}
        loading="lazy"
        className={cn("h-full w-full rounded-lg object-cover", className)}
      />
    );
  }
  return <CoverArt seed={seed} motif={motif} className={className} />;
}
