/**
 * Generated covers.
 *
 * Every listing needs a picture from the moment it is published — long before
 * a seller has uploaded one. The first version drew little abstractions of
 * each field (a code window, colour swatches, a book) over a gradient and a
 * dot grid, which read exactly like generated stock art. These are set, not
 * drawn: a flat field in the category's colour with the category's name cut
 * large across it, the way a printed label or a book spine would carry it.
 *
 * The colour belongs to the category, not the listing, so it means something:
 * every Development listing is lapis, every Academic one firozi, on every page.
 * The seed only moves the lettering, so neighbours in a grid are not clones.
 * When a seller uploads a real cover, that wins — this is the floor.
 */
import * as React from "react";

import { cn } from "./ui";

/** Stable small hash, so the same input always yields the same cover. */
function hash(seed: string): number {
  let value = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    value ^= seed.charCodeAt(index);
    value = Math.imul(value, 16777619);
  }
  return Math.abs(value);
}

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

export interface Palette {
  /** The field. */
  deep: string;
  /** The lettering, and the category's colour wherever it appears alone. */
  mid: string;
  /** A tint for light backgrounds. */
  light: string;
}

/**
 * One colour per field, from the dyes and glazes of Pakistani craft: lapis,
 * ajrak's madder red, slate, multani clay, marigold, mehndi green, kohl, and
 * the firozi of Multan tilework — which is also the campus portals' colour,
 * so Academic Support shares it.
 */
const PALETTES: Record<Motif, Palette> = {
  code: { deep: "#1E3A6E", mid: "#3F6FC4", light: "#DCE6F7" }, // lapis
  design: { deep: "#7E1D22", mid: "#C7453E", light: "#F6DCD8" }, // madder
  writing: { deep: "#2B2A26", mid: "#6E6A60", light: "#E6E4DE" }, // slate
  video: { deep: "#5E3D22", mid: "#B07D4F", light: "#F2E6D8" }, // multani clay
  marketing: { deep: "#9A5800", mid: "#F2A10F", light: "#FEEFCF" }, // marigold
  data: { deep: "#465619", mid: "#8BA03A", light: "#E7EDCF" }, // mehndi
  business: { deep: "#23394A", mid: "#5C7A91", light: "#DEE6EC" }, // kohl
  academic: { deep: "#0B5552", mid: "#139088", light: "#CAEBE6" }, // firozi
};

export function paletteFor(categoryName?: string | null): Palette {
  return PALETTES[motifFor(categoryName)];
}

/** The word each field is set in on its cover, and its label above. */
const WORD: Record<Motif, string> = {
  code: "Development",
  design: "Design",
  writing: "Writing",
  video: "Video",
  marketing: "Marketing",
  data: "Data",
  business: "Business",
  academic: "Academic",
};

const LABEL: Record<Motif, string> = {
  code: "Development & IT",
  design: "Design & Creative",
  writing: "Writing & Translation",
  video: "Video & Animation",
  marketing: "Marketing & Sales",
  data: "Data & Analytics",
  business: "Business & Admin",
  academic: "Academic Support",
};

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
  const { deep, mid, light } = PALETTES[motif];
  const word = WORD[motif];
  // Short words are set to fill the width; long ones run off the right edge,
  // cropped like a detail of a larger sign. Everything sits between y 30 and
  // 195, the band that survives any card shape once the frame is sliced.
  const size = Math.min(140, Math.max(92, 330 / (word.length * 0.46)));
  const baseline = 188 - (hash(String(seed)) % 3) * 4;

  return (
    <svg
      viewBox="0 0 320 220"
      className={cn("h-full w-full", rounded && "rounded-lg", className)}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
    >
      <rect width="320" height="220" fill={deep} />
      <text
        x="18"
        y="50"
        fill={light}
        fillOpacity="0.8"
        fontSize="10.5"
        style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em", textTransform: "uppercase" }}
      >
        {LABEL[motif]}
      </text>
      <text
        x="12"
        y={baseline}
        fill={mid}
        fontSize={size}
        style={{
          fontFamily: "var(--font-display)",
          fontVariationSettings: '"wdth" 62',
          fontWeight: 800,
          letterSpacing: "-0.03em",
        }}
      >
        {word}
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
