"use client";

/**
 * Pieces shared by the professional surfaces.
 *
 * The one worth reading is `UpgradePrompt`. The server answers a blocked action
 * with 402 and `code: "upgrade_required"`, and the reason that code is distinct
 * from a plain denial is so the client can offer the fix *where the user hit
 * the wall*. A paywall that only says no, and leaves the user to go find the
 * pricing page themselves, is a paywall most of them simply leave.
 */

import * as React from "react";
import Link from "next/link";

import { Alert, Badge, Button, Card, Icon, cn } from "@/components/ui";
import { professional, type Entitlements, type PlanTier } from "@/lib/api";
import { useLoader } from "@/lib/session";

const TIER_TONE = {
  free: "neutral",
  pro: "accent",
  elite: "positive",
} as const;

export function PlanBadge({ tier, name }: { tier: PlanTier; name?: string }) {
  return (
    <Badge tone={TIER_TONE[tier]}>
      {tier !== "free" && <Icon name="sparkles" className="size-3" />}
      {name ?? tier}
    </Badge>
  );
}

/** Shown in place of a feature the caller's plan does not include. */
export function UpgradePrompt({
  title,
  description,
  tier = "pro",
}: {
  title: string;
  description: string;
  tier?: "pro" | "elite";
}) {
  return (
    <Card className="overflow-hidden">
      <div className="relative px-6 py-10 text-center">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-linear-to-b from-accent-soft/60 to-transparent"
        />
        <div className="relative mx-auto max-w-md space-y-3">
          <div className="mx-auto grid size-11 place-items-center rounded-full bg-accent-soft text-accent">
            <Icon name="sparkles" className="size-5" />
          </div>
          <p className="text-[15px] font-semibold text-fg">{title}</p>
          <p className="text-[13px] leading-relaxed text-muted">{description}</p>
          <Link href="/pricing" className="inline-block pt-1">
            <Button size="sm">
              See {tier === "elite" ? "Elite" : "Pro"} plans
              <Icon name="arrowRight" className="size-3.5" />
            </Button>
          </Link>
        </div>
      </div>
    </Card>
  );
}

/**
 * A 402 turned into an offer rather than a red banner.
 *
 * Any other failure still renders as an error — conflating "you cannot afford
 * this" with "the server broke" in either direction would be worse than either
 * message alone.
 */
export function ActionError({ error, code }: { error: string | null; code: string | null }) {
  if (!error) return null;
  if (code !== "upgrade_required") {
    return (
      <Alert tone="critical" className="mt-3">
        {error}
      </Alert>
    );
  }
  return (
    <Alert tone="accent" title="Your plan does not include this" className="mt-3">
      <div className="flex flex-wrap items-center gap-3">
        <span>{error}</span>
        <Link href="/pricing" className="font-medium text-accent underline-offset-4 hover:underline">
          View plans
        </Link>
      </div>
    </Alert>
  );
}

/** A limit rendered as "12 of 25", or "12" when the plan has no cap. */
export function UsageMeter({
  used,
  limit,
  label,
}: {
  used: number;
  limit: number;
  label: string;
}) {
  const unlimited = limit === -1;
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  const tight = !unlimited && pct >= 80;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-[13px]">
        <span className="text-muted">{label}</span>
        <span className={cn("tabular font-medium", tight ? "text-caution" : "text-fg")}>
          {used}
          {!unlimited && <span className="text-subtle"> / {limit}</span>}
        </span>
      </div>
      {unlimited ? (
        <p className="text-[12px] text-subtle">No limit on your plan.</p>
      ) : (
        <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-500",
              tight ? "bg-caution" : "bg-accent",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}

/**
 * The caller's live entitlements, fetched once per surface that needs them.
 *
 * Deliberately not held in the session context: entitlements change on a
 * subscribe or an expiry, and a stale copy of "unlimited" cached at sign-in is
 * the exact hole the server-side resolver was written to avoid.
 *
 * A failed load leaves `rights` null rather than surfacing an error, and every
 * caller already renders that as "no upgrade hint". The server authorises each
 * action independently, so the worst case here is a missing prompt, never a
 * bypassed limit.
 */
export function useEntitlements(): {
  rights: Entitlements | null;
  reload: () => Promise<void>;
} {
  const { data, reload } = useLoader(() => professional.subscription(), []);
  return { rights: data?.entitlements ?? null, reload };
}
