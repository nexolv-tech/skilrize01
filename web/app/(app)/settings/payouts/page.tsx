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
  Select,
  Skeleton,
} from "@/components/ui";
import { payments, type Payout } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader } from "@/lib/session";

const STATUS_TONE: Record<Payout["status"], "neutral" | "positive"> = {
  pending: "neutral",
  paid: "positive",
};

/**
 * Where a freelancer's released payments are sent (D56). A bank or wallet
 * chosen from Swich's list is paid automatically when a client approves the
 * work; one typed in by hand is paid by our team instead. Swich checks the
 * name on the account before paying, so a mistyped number stops a payout
 * rather than sending it to a stranger.
 */
const OTHER = "__other";

function PayoutProfileForm() {
  const { data: profile, loading, reload } = useLoader(() => payments.payoutProfile(), []);
  const { data: institutions } = useLoader(() => payments.payoutInstitutions(), []);

  const [form, setForm] = React.useState({
    bank_code: "",
    bank_name: "",
    account_title: "",
    account_number: "",
    cnic: "",
    msisdn: "",
  });
  const [saved, setSaved] = React.useState(false);
  const chosen = institutions?.find((row) => row.code === form.bank_code);
  const wallet = chosen?.kind === "wallet";

  const update = <K extends keyof typeof form>(key: K, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const save = useAsyncAction(async () => {
    const other = form.bank_code === OTHER;
    await payments.savePayoutProfile({
      ...form,
      bank_code: other ? "" : form.bank_code,
      bank_name: other ? form.bank_name : "",
      cnic: form.cnic.replace(/[^0-9]/g, ""),
      // A wallet's account number is its mobile number.
      account_number: form.account_number.replace(/\s+/g, ""),
    });
    setForm({ bank_code: "", bank_name: "", account_title: "", account_number: "", cnic: "", msisdn: "" });
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
    await reload();
  });

  if (loading) return <Skeleton className="h-64 w-full" />;

  return (
    <Card>
      <CardHeader
        title="Where to send your payments"
        description="When a client approves your work, the payment minus our fee is sent here through Swich, usually the same day."
        action={
          profile?.swich_ready ? (
            <Badge tone="positive">Paid automatically</Badge>
          ) : profile?.is_complete ? (
            <Badge tone="neutral">Paid by our team</Badge>
          ) : (
            <Badge tone="caution">Not set up</Badge>
          )
        }
      />
      <div className="space-y-5 p-5">
        {profile?.is_complete && (
          <div className="rounded-md border border-line bg-sunken p-3.5 text-[13px] text-muted">
            Currently paying <span className="font-medium text-fg">{profile.account_title}</span> at{" "}
            {profile.bank_name}
            {profile.swich_ready
              ? ", automatically through Swich."
              : ". This bank is not on Swich's list, so our team sends it by hand."}{" "}
            Saving below replaces it.
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

          <Field label="Bank or wallet" htmlFor="bank_code">
            <Select
              id="bank_code"
              value={form.bank_code}
              onChange={(event) => update("bank_code", event.target.value)}
              required
            >
              <option value="" disabled>
                Choose…
              </option>
              <optgroup label="Mobile wallets">
                {(institutions ?? [])
                  .filter((row) => row.kind === "wallet")
                  .map((row) => (
                    <option key={row.code} value={row.code}>
                      {row.name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Banks">
                {(institutions ?? [])
                  .filter((row) => row.kind === "bank")
                  .map((row) => (
                    <option key={row.code} value={row.code}>
                      {row.name}
                    </option>
                  ))}
              </optgroup>
              <option value={OTHER}>Another bank (paid by our team)</option>
            </Select>
          </Field>

          {form.bank_code === OTHER && (
            <Field label="Bank name" htmlFor="bank_name">
              <Input
                id="bank_name"
                value={form.bank_name}
                onChange={(event) => update("bank_name", event.target.value)}
                placeholder="Bank name"
                required
              />
            </Field>
          )}

          <Field
            label="Account title"
            htmlFor="account_title"
            hint="Exactly as the bank or wallet shows it. Swich checks it before paying."
          >
            <Input
              id="account_title"
              value={form.account_title}
              onChange={(event) => update("account_title", event.target.value)}
              placeholder="Ahmed Raza"
              required
            />
          </Field>

          <Field
            label={wallet ? "Wallet number" : "IBAN or account number"}
            htmlFor="account_number"
            hint={wallet ? "The mobile number of your wallet, 03xxxxxxxxx." : "Your IBAN starts with PK."}
          >
            <Input
              id="account_number"
              value={form.account_number}
              onChange={(event) => update("account_number", event.target.value)}
              placeholder={wallet ? "03001234567" : "PK36MEZN0000001234567890"}
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

          <Field label="Mobile number" htmlFor="msisdn" hint="Format 03xxxxxxxxx. Swich needs it with every payment.">
            <Input
              id="msisdn"
              value={form.msisdn}
              onChange={(event) => update("msisdn", event.target.value)}
              placeholder="03001234567"
              required
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
