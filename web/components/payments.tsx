"use client";

/**
 * Escrow funding UI — the platform's own bank account, shown before a
 * client confirms they've paid (Phase 3, D42). Shared between the
 * contract-milestone flow, the gig checkout and plan upgrades, which all
 * fund the same way: a real bank transfer this app cannot verify, followed
 * by the client's own confirmation.
 */

import * as React from "react";
import Link from "next/link";

import { Alert, Button, Field, Input, Money, Skeleton } from "@/components/ui";
import { payments } from "@/lib/api";
import { BUSINESS } from "@/lib/business";
import { useLoader } from "@/lib/session";

function CopyValue({ value }: { value: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="figure rounded-sm px-1 text-right font-medium text-fg underline decoration-line-strong decoration-dotted underline-offset-4 hover:decoration-fg"
      aria-label={`Copy ${value}`}
    >
      {copied ? "Copied" : value}
    </button>
  );
}

export function BankTransferPanel({
  amount,
  onConfirm,
  pending,
  onCancel,
  confirmLabel = "I've sent the payment",
  confirmDisabled = false,
}: {
  amount: string;
  onConfirm: (referenceNote: string) => void;
  pending: boolean;
  onCancel?: () => void;
  confirmLabel?: string;
  /** For a caller with its own precondition — the checkout's terms box. */
  confirmDisabled?: boolean;
}) {
  const { data } = useLoader(() => payments.bankTransferInstructions(), []);
  const [reference, setReference] = React.useState("");

  if (data && !data.available) {
    return (
      <Alert tone="caution" title="Payments are not open yet">
        Bank transfer will be available shortly. Nothing has been charged. To place this order now,
        email <a href={`mailto:${BUSINESS.email}`} className="font-medium underline">{BUSINESS.email}</a>{" "}
        or call {BUSINESS.phone}.
      </Alert>
    );
  }

  return (
    <div className="w-full space-y-4 rounded-md border border-line bg-sunken p-4">
      <p className="text-[13.5px] font-medium text-fg">
        Transfer <Money amount={amount} /> to this account, then confirm below.
      </p>
      {data ? (
        <dl className="space-y-1.5 text-[13px] text-muted">
          <div className="flex justify-between gap-3">
            <dt>Bank</dt>
            <dd className="font-medium text-fg">{data.bank_name}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>Account title</dt>
            <dd className="font-medium text-fg">{data.account_title}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>Account number / IBAN</dt>
            <dd>
              <CopyValue value={data.account_number} />
            </dd>
          </div>
        </dl>
      ) : (
        <Skeleton className="h-16 w-full" />
      )}
      <Field
        label="Transfer reference"
        htmlFor="reference_note"
        hint="The transaction ID from your bank or app. It helps us match your payment quickly."
      >
        <Input
          id="reference_note"
          value={reference}
          maxLength={200}
          onChange={(event) => setReference(event.target.value)}
          placeholder="e.g. FT2609251234"
        />
      </Field>
      <p className="text-[12px] leading-relaxed text-subtle">
        Only confirm once the transfer has gone through. Orders whose payment does not arrive
        within three business days are cancelled — see the{" "}
        <Link href="/terms#escrow" className="underline underline-offset-2">
          Terms
        </Link>
        .
      </p>
      <div className="flex flex-wrap gap-2">
        <Button loading={pending} disabled={!data || confirmDisabled} onClick={() => onConfirm(reference)}>
          {confirmLabel}
        </Button>
        {onCancel && (
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}

/** The other half of the split — what a client sees before releasing a
 * milestone, so "release" doesn't look like the freelancer gets the full
 * amount when the platform's commission comes out first. */
export function ReleaseEstimate({ amount }: { amount: string }) {
  const { data } = useLoader(() => payments.bankTransferInstructions(), []);
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
