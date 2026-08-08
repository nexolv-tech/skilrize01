"use client";

/**
 * Reputation display.
 *
 * One component per concept, shared everywhere, so a Level 2 seller looks
 * identical in search, on a profile, and beside a proposal. A badge that means
 * something in one place and something slightly different in another is worse
 * than no badge.
 */

import * as React from "react";

import { Icon, cn } from "@/components/ui";
import { SELLER_LEVEL_LABEL, type SellerLevel } from "@/lib/api";

const LEVEL_STYLE: Record<SellerLevel, string> = {
  new: "bg-sunken text-subtle ring-line-strong",
  level_one: "bg-accent-soft text-accent ring-accent/25",
  level_two: "bg-accent-soft text-accent ring-accent/40",
  // Only the top rung gets a solid fill. If every level shouts, none of them
  // carries information.
  top_rated: "bg-accent text-on-accent ring-accent",
};

export function LevelBadge({
  level,
  className,
}: {
  level: SellerLevel;
  className?: string;
}) {
  // A new seller wears no badge at all rather than a badge reading "new".
  // Labelling inexperience is a penalty the ladder does not intend — the
  // absence of a badge already says it.
  if (level === "new") return null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
        LEVEL_STYLE[level],
        className,
      )}
    >
      {level === "top_rated" && <Icon name="star" className="size-3" strokeWidth={0} />}
      {SELLER_LEVEL_LABEL[level]}
    </span>
  );
}

/**
 * The Job Success Score.
 *
 * Shown only once it exists. A seller below the history threshold has no
 * number, and inventing one — "0%", or a hopeful "100%" — would be a lie in
 * either direction.
 */
export function SuccessScore({
  score,
  className,
}: {
  score: number | null;
  className?: string;
}) {
  if (score === null) return null;

  const tone =
    score >= 90 ? "text-positive" : score >= 75 ? "text-fg" : "text-caution";

  return (
    <span
      className={cn("inline-flex items-center gap-1 text-[12px] font-medium", tone, className)}
      title="Job Success Score — completion rate, ratings, punctuality, and repeat clients"
    >
      <Icon name="chart" className="size-3.5" />
      {score}%
    </span>
  );
}

/** The "Promoted" disclosure. Never optional where a promotion is showing. */
export function PromotedTag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10.5px] font-medium",
        "bg-sunken text-subtle ring-1 ring-inset ring-line-strong",
        className,
      )}
      title="This seller paid for placement. It still had to rank on merit."
    >
      Promoted
    </span>
  );
}
