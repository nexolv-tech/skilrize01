"use client";

/**
 * Where Swich sends the buyer back after paying (D55).
 *
 * This page decides nothing. Swich tells the server the outcome directly, in
 * a checksum-verified callback, and this page only reads what that callback
 * recorded, checking again every couple of seconds in case the buyer is back
 * before Swich's message is.
 */

import * as React from "react";
import { useSearchParams } from "next/navigation";

import { PageHeading } from "@/components/shell";
import { ButtonLink, Card, Icon, Money, Skeleton, Spinner } from "@/components/ui";
import { payments, type ChargeStatus } from "@/lib/api";

const POLL_MS = 2500;
const GIVE_UP_MS = 60_000;

function next(charge: ChargeStatus): { href: string; label: string } {
  if (charge.order_id) return { href: `/orders/${charge.order_id}`, label: "Go to your order" };
  if (charge.contract_id)
    return { href: `/contracts/${charge.contract_id}`, label: "Open the contract" };
  return { href: "/pricing", label: "See your plan" };
}

function ReturnContent() {
  const reference = useSearchParams().get("ref") ?? "";
  const [charge, setCharge] = React.useState<ChargeStatus | null>(null);
  const [missing, setMissing] = React.useState(false);
  const [slow, setSlow] = React.useState(false);

  React.useEffect(() => {
    if (!reference) return;
    let stopped = false;
    const started = Date.now();
    async function check() {
      try {
        const latest = await payments.charge(reference);
        if (stopped) return;
        setCharge(latest);
        if (latest.status !== "created") return;
      } catch {
        if (!stopped) setMissing(true);
        return;
      }
      if (Date.now() - started > GIVE_UP_MS) {
        setSlow(true);
        return;
      }
      window.setTimeout(() => void check(), POLL_MS);
    }
    void check();
    return () => {
      stopped = true;
    };
  }, [reference]);

  if (!reference || missing) {
    return (
      <Card className="p-8 text-center">
        <p className="text-[15px] font-medium text-fg">We could not find that payment.</p>
        <p className="mt-2 text-[13.5px] text-muted">
          If you paid, it will show on your order within a few minutes.
        </p>
        <ButtonLink href="/orders" variant="secondary" className="mt-5">
          Your orders
        </ButtonLink>
      </Card>
    );
  }

  if (!charge) return <Skeleton className="h-48 w-full" />;

  const onward = next(charge);

  if (charge.status === "paid") {
    return (
      <Card className="p-8 text-center">
        <span className="mx-auto grid size-12 place-items-center rounded-full bg-positive-soft text-positive">
          <Icon name="check" className="size-6" />
        </span>
        <p className="mt-4 text-[18px] font-semibold text-fg">Payment received</p>
        <p className="mt-2 text-[14px] leading-relaxed text-muted">
          <Money amount={charge.amount} /> is held in escrow. It is released only when you approve
          the work, and refunded if the order is cancelled before delivery.
        </p>
        <ButtonLink href={onward.href} className="mt-6">
          {onward.label}
          <Icon name="arrowRight" className="size-4" />
        </ButtonLink>
      </Card>
    );
  }

  if (charge.status === "failed" || charge.status === "expired") {
    return (
      <Card className="p-8 text-center">
        <span className="mx-auto grid size-12 place-items-center rounded-full bg-critical-soft text-critical">
          <Icon name="x" className="size-6" />
        </span>
        <p className="mt-4 text-[18px] font-semibold text-fg">Payment not completed</p>
        <p className="mt-2 text-[14px] leading-relaxed text-muted">
          Nothing was charged. You can try again with the same or another method.
        </p>
        <ButtonLink href={onward.href} className="mt-6">
          Try again
        </ButtonLink>
      </Card>
    );
  }

  return (
    <Card className="p-8 text-center">
      <Spinner className="mx-auto size-6 text-accent" />
      <p className="mt-4 text-[18px] font-semibold text-fg">Confirming your payment</p>
      <p className="mt-2 text-[14px] leading-relaxed text-muted">
        {slow
          ? "Swich has not confirmed it yet. You can close this page: we will notify you by email the moment it arrives, and your order updates on its own."
          : "Waiting for Swich to confirm. This usually takes a few seconds."}
      </p>
      {slow && (
        <ButtonLink href={onward.href} variant="secondary" className="mt-6">
          {onward.label}
        </ButtonLink>
      )}
    </Card>
  );
}

export default function PaymentReturnPage() {
  return (
    <div className="mx-auto max-w-lg">
      <PageHeading title="Payment" />
      <React.Suspense fallback={<Skeleton className="h-48 w-full" />}>
        <ReturnContent />
      </React.Suspense>
    </div>
  );
}
