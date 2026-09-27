"use client";

/**
 * Paying through Swich (D55). Shared by the service checkout, a brief's
 * milestone and plan upgrades: each asks its own endpoint to start a
 * checkout, then sends the buyer's browser to Swich's secure page, where
 * they pay by card, Easypaisa, JazzCash or 1Bill. Nothing is held until
 * Swich confirms the payment to the server; the page the buyer returns to
 * (`/payments/return`) only shows what that confirmation recorded.
 */

import * as React from "react";

import { Alert, Button, Icon, Money, Skeleton, cn } from "@/components/ui";
import { payments, type CheckoutStart, type PaymentOptions } from "@/lib/api";
import { BUSINESS } from "@/lib/business";
import { useLoader } from "@/lib/session";

/** The ways to pay, as the buyer will see them on Swich's page. */
export function PaymentMethods({
  options,
  className,
}: {
  options: PaymentOptions | null;
  className?: string;
}) {
  if (!options) return <Skeleton className={cn("h-24 w-full", className)} />;
  return (
    <ul className={cn("grid gap-2 sm:grid-cols-2", className)} aria-label="Ways to pay">
      {options.methods.map((method) => (
        <li
          key={method.id}
          className="flex items-center gap-3 rounded-md border border-line bg-raised p-3"
        >
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-sunken text-muted">
            <Icon name={method.id === "card" ? "wallet" : method.id === "1bill" ? "file" : "phone"} className="size-4" />
          </span>
          <span className="min-w-0">
            <span className="block text-[13.5px] font-medium text-fg">{method.label}</span>
            <span className="block text-[12px] text-muted">{method.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function PaymentsOpeningSoon() {
  return (
    <Alert tone="neutral" title="Card and wallet payments are opening shortly">
      Nothing has been charged and no order was placed. To buy now, email{" "}
      <a href={`mailto:${BUSINESS.email}`} className="font-medium underline">
        {BUSINESS.email}
      </a>{" "}
      or call {BUSINESS.phone}.
    </Alert>
  );
}

/**
 * The pay button: starts the checkout with `onStart` and hands the browser
 * to Swich. `onStart` is the caller's own endpoint (an order, a milestone,
 * a plan), which also places what is being paid for.
 */
export function SwichPay({
  amount,
  onStart,
  label = "Pay securely",
  disabled = false,
  error,
  showMethods = true,
}: {
  amount: string | number;
  onStart: () => Promise<CheckoutStart | undefined>;
  label?: string;
  /** For a caller with its own precondition, such as the checkout's terms box. */
  disabled?: boolean;
  error?: string | null;
  showMethods?: boolean;
}) {
  const { data: options } = useLoader(() => payments.options(), []);
  const [leaving, setLeaving] = React.useState(false);

  if (options && !options.available) return <PaymentsOpeningSoon />;

  return (
    <div className="space-y-4">
      {showMethods && <PaymentMethods options={options} />}
      {error && <Alert tone="critical">{error}</Alert>}
      <Button
        className="w-full"
        size="lg"
        loading={leaving}
        disabled={!options || disabled}
        onClick={async () => {
          setLeaving(true);
          const started = await onStart();
          if (started?.checkout_url) {
            window.location.assign(started.checkout_url);
          } else {
            setLeaving(false);
          }
        }}
      >
        <Icon name="lock" className="size-4" />
        {label} · <Money amount={amount} />
      </Button>
      <p className="flex gap-2 text-[12px] leading-relaxed text-subtle">
        <Icon name="shield" className="mt-0.5 size-3.5 shrink-0" />
        You pay on Swich&apos;s secure page, our licensed payment partner. SkilRize never sees
        your card number or wallet PIN, and the money is held in escrow until you approve the
        work.
      </p>
    </div>
  );
}

/** The other half of the split: what a client sees before releasing a
 * milestone, so "release" doesn't look like the freelancer gets the full
 * amount when the platform's commission comes out first. */
export function ReleaseEstimate({ amount }: { amount: string }) {
  const { data } = useLoader(() => payments.options(), []);
  const commission = data ? Number(data.commission_percent) : null;
  const net = commission !== null ? (Number(amount) * (1 - commission / 100)).toFixed(2) : null;

  if (net === null) return null;
  return (
    <span className="text-[12.5px] text-subtle">
      The freelancer receives Rs {net} (Rs {amount} minus our {commission}% fee) — cannot be
      undone.
    </span>
  );
}
