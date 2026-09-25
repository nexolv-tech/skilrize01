/**
 * Stand-in thumbnails.
 *
 * Listing cards and service pages show a picture only when the seller has
 * uploaded one — an invented cover is worse than none. What remains is the
 * small square a few screens need beside an order (checkout, orders, the
 * showcase): a soft tint of the category's colour with its initial, quiet
 * enough not to pass for a real image. The colour belongs to the category, so
 * it stays the same on every page.
 */
import * as React from "react";

import { cn } from "./ui";

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

interface Palette {
  /** The initial. */
  deep: string;
  /** The tile. */
  light: string;
}

/**
 * One colour per field, from the dyes and glazes of Pakistani craft: lapis,
 * ajrak's madder red, slate, multani clay, marigold, mehndi green, kohl, and
 * the firozi of Multan tilework — which is also the campus portals' colour,
 * so Academic Support shares it.
 */
const PALETTES: Record<Motif, Palette> = {
  code: { deep: "#1E3A6E", light: "#DCE6F7" }, // lapis
  design: { deep: "#7E1D22", light: "#F6DCD8" }, // madder
  writing: { deep: "#2B2A26", light: "#E6E4DE" }, // slate
  video: { deep: "#5E3D22", light: "#F2E6D8" }, // multani clay
  marketing: { deep: "#9A5800", light: "#FEEFCF" }, // marigold
  data: { deep: "#465619", light: "#E7EDCF" }, // mehndi
  business: { deep: "#23394A", light: "#DEE6EC" }, // kohl
  academic: { deep: "#0B5552", light: "#CAEBE6" }, // firozi
};

const INITIAL: Record<Motif, string> = {
  code: "D",
  design: "D",
  writing: "W",
  video: "V",
  marketing: "M",
  data: "D",
  business: "B",
  academic: "A",
};

/* -------------------------------------------------------------------------- */

export function CoverArt({
  motif = "design",
  className,
  rounded = true,
}: {
  /** Kept for callers; the tile depends only on the category. */
  seed?: string | number;
  motif?: Motif;
  className?: string;
  rounded?: boolean;
}) {
  const { deep, light } = PALETTES[motif];
  return (
    <svg
      viewBox="0 0 320 220"
      className={cn("h-full w-full", rounded && "rounded-lg", className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
    >
      <rect width="320" height="220" fill={light} />
      <text
        x="160"
        y="112"
        textAnchor="middle"
        dominantBaseline="central"
        fill={deep}
        fillOpacity="0.55"
        fontSize="92"
        style={{ fontFamily: "var(--font-sans)", fontWeight: 600 }}
      >
        {INITIAL[motif]}
      </text>
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
