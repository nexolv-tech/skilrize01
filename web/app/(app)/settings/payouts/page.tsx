"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import { TwoFactorRequiredPrompt } from "@/components/two-factor";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Icon,
  Input,
  Money,
  Skeleton,
} from "@/components/ui";
import { payments, type Payout } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader } from "@/lib/session";

const STATUS_TONE: Record<Payout["status"], "neutral" | "positive"> = {
  pending: "neutral",
  paid: "positive",
};

/**
 * Where a freelancer's released milestones actually get paid — typed in
 * once, then read by whoever on the platform side sends the manual bank
 * transfer on release (Phase 3, D42). Nothing here verifies the account;
 * there is no gateway to ask.
 */
function PayoutProfileForm() {
  const { data: profile, loading, reload } = useLoader(() => payments.payoutProfile(), []);

  const [form, setForm] = React.useState({
    bank_name: "",
    account_title: "",
    account_number: "",
    cnic: "",
    msisdn: "",
  });
  const [saved, setSaved] = React.useState(false);

  const update = <K extends keyof typeof form>(key: K, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const save = useAsyncAction(async () => {
    await payments.savePayoutProfile({ ...form, cnic: form.cnic.replace(/[^0-9]/g, "") });
    setForm({ bank_name: "", account_title: "", account_number: "", cnic: "", msisdn: "" });
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
    await reload();
  });

  if (loading) return <Skeleton className="h-64 w-full" />;

  return (
    <Card>
      <CardHeader
        title="Payout account"
        description="Where money goes when a client releases a milestone — sent manually by our team, once you've told us where."
        action={
          profile?.is_complete ? (
            <Badge tone="positive">Set up</Badge>
          ) : (
            <Badge tone="caution">Not set up</Badge>
          )
        }
      />
      <div className="space-y-5 p-5">
        {profile?.is_complete && (
          <div className="rounded-md border border-line bg-sunken p-3.5 text-[13px] text-muted">
            Currently paying out to <span className="font-medium text-fg">{profile.account_title}</span>{" "}
            at {profile.bank_name}. Saving a new account below replaces this one.
          </div>
        )}

        <form
          className="max-w-md space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void save.run();
          }}
        >
          {save.error && save.code !== "two_factor_required" && (
            <Alert tone="critical">{save.error}</Alert>
          )}

          <Field label="Bank name" htmlFor="bank_name">
            <Input
              id="bank_name"
              value={form.bank_name}
              onChange={(event) => update("bank_name", event.target.value)}
              placeholder="Habib Bank"
              required
            />
          </Field>

          <Field label="Account title" htmlFor="account_title" hint="The name on the account.">
            <Input
              id="account_title"
              value={form.account_title}
              onChange={(event) => update("account_title", event.target.value)}
              placeholder="Ahmed Raza"
              required
            />
          </Field>

          <Field label="Account / IBAN number" htmlFor="account_number">
            <Input
              id="account_number"
              value={form.account_number}
              onChange={(event) => update("account_number", event.target.value)}
              placeholder="PK00HABB0000001234567"
              required
            />
          </Field>

          <Field label="CNIC" htmlFor="cnic" hint="13 digits, no dashes needed.">
            <Input
              id="cnic"
              value={form.cnic}
              onChange={(event) => update("cnic", event.target.value)}
              placeholder="4210112345671"
              required
            />
          </Field>

          <Field label="Mobile number" htmlFor="msisdn" hint="Format 03xxxxxxxxx.">
            <Input
              id="msisdn"
              value={form.msisdn}
              onChange={(event) => update("msisdn", event.target.value)}
              placeholder="03001234567"
            />
          </Field>

          <div className="flex items-center gap-3">
            <Button type="submit" loading={save.pending}>
              Save payout account
            </Button>
            {saved && (
              <span className="inline-flex items-center gap-1.5 text-[13px] text-positive">
                <Icon name="check" className="size-4" strokeWidth={2.6} />
                Saved
              </span>
            )}
          </div>
        </form>

        {save.code === "two_factor_required" && (
          <TwoFactorRequiredPrompt onComplete={() => void save.run()} />
        )}
      </div>
    </Card>
  );
}

function PayoutHistory() {
  const { data, loading } = useLoader(() => payments.myPayouts(), []);
  const payouts = data?.results ?? [];

  return (
    <Card>
      <CardHeader title="Payout history" description="What's been released, and what's been sent." />
      {loading ? (
        <div className="p-5">
          <Skeleton className="h-24 w-full" />
        </div>
      ) : payouts.length === 0 ? (
        <EmptyState
          icon="wallet"
          title="No payouts yet"
          description="They'll show up here the first time a client releases a milestone."
        />
      ) : (
        <ul className="divide-y divide-line">
          {payouts.map((payout) => (
            <li key={payout.id} className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="truncate text-[13.5px] font-medium text-fg">
                  {payout.milestone_title}
                </p>
                <p className="mt-0.5 text-[12px] text-subtle">
                  {formatRelative(payout.created_at)} · Rs {payout.gross_amount} minus{" "}
                  {payout.commission_percent}% fee
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Icon name="wallet" className="size-3.5 text-subtle" />
                <span className="text-[13.5px] font-semibold text-fg">
                  <Money amount={payout.net_amount} />
                </span>
                <Badge tone={STATUS_TONE[payout.status]}>{payout.status}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function PayoutsSettingsPage() {
  return (
    <>
      <PageHeading
        title="Payouts"
        description="Set up where released milestone money goes, and track what's been paid."
      />
      <div className="space-y-6">
        <PayoutProfileForm />
        <PayoutHistory />
      </div>
    </>
  );
}
