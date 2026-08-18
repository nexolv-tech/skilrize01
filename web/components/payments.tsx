"use client";

/**
 * Escrow funding UI — the platform's own bank account, shown before a
 * client confirms they've paid (Phase 3, D42). Shared between the
 * contract-milestone flow and the gig-order flow, which both fund the
 * same way: a real bank transfer this app cannot verify, followed by the
 * client's own confirmation.
 */

import * as React from "react";

import { Button, Field, Input, Money, Skeleton } from "@/components/ui";
import { payments } from "@/lib/api";
import { useLoader } from "@/lib/session";

export function BankTransferPanel({
  amount,
  onConfirm,
  pending,
  onCancel,
}: {
  amount: string;
  onConfirm: (referenceNote: string) => void;
  pending: boolean;
  onCancel: () => void;
}) {
  const { data } = useLoader(() => payments.bankTransferInstructions(), []);
  const [reference, setReference] = React.useState("");

  return (
    <div className="w-full space-y-3 rounded-md border border-line bg-sunken p-4">
      <p className="text-[13px] font-medium text-fg">
        Transfer <Money amount={amount} /> to this account, then confirm below.
      </p>
      {data ? (
        <dl className="space-y-1 text-[13px] text-muted">
          <div className="flex justify-between gap-3">
            <dt>Bank</dt>
            <dd className="font-medium text-fg">{data.bank_name}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>Account title</dt>
            <dd className="font-medium text-fg">{data.account_title}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt>Account number</dt>
            <dd className="font-medium text-fg">{data.account_number}</dd>
          </div>
        </dl>
      ) : (
        <Skeleton className="h-16 w-full" />
      )}
      <Field label="Transfer reference (optional)" htmlFor="reference_note">
        <Input
          id="reference_note"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
          placeholder="Bank transaction ID, for reconciliation"
        />
      </Field>
      <div className="flex gap-2">
        <Button size="sm" loading={pending} onClick={() => onConfirm(reference)}>
          I&apos;ve sent the payment
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
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
