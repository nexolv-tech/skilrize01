"use client";

/**
 * Privacy & data — the self-service half of the GDPR rights the Privacy
 * Policy promises: a copy of everything held (Arts. 15, 20) and erasure
 * (Art. 17). Both need step-up, because a stolen session alone must be able
 * to do neither. Deletion shows what would block it and what is kept anyway
 * *before* asking for a password, so nobody confirms blind.
 */

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import { Alert, Button, Card, CardHeader, Field, Icon, Input, Skeleton } from "@/components/ui";
import { auth, type StepUp } from "@/lib/api";
import { BUSINESS } from "@/lib/business";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

/** The one proof field every step-up form here asks for: the authenticator
 *  code when two-factor is on (a password alone is not step-up then), the
 *  password otherwise. */
function StepUpField({
  id,
  value,
  onChange,
  invalid,
}: {
  id: string;
  value: string;
  onChange: (next: string) => void;
  invalid?: boolean;
}) {
  const { user } = useSession();
  const usesCode = Boolean(user?.has_two_factor);
  return (
    <Field
      label={usesCode ? "Authentication code" : "Your password"}
      htmlFor={id}
      hint={usesCode ? "From your authenticator app." : "To confirm it is really you."}
      required
    >
      <Input
        id={id}
        type={usesCode ? "text" : "password"}
        inputMode={usesCode ? "numeric" : undefined}
        autoComplete={usesCode ? "one-time-code" : "current-password"}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        invalid={invalid}
      />
    </Field>
  );
}

function useStepUpBody() {
  const { user } = useSession();
  return React.useCallback(
    (proof: string): StepUp => (user?.has_two_factor ? { code: proof } : { password: proof }),
    [user?.has_two_factor],
  );
}

/* -------------------------------------------------------------------------- */
/* Export                                                                     */
/* -------------------------------------------------------------------------- */

const EXPORT_CONTENTS = [
  "Your account, profile and verification status",
  "Services, briefs, proposals, orders and contracts",
  "Payments, payouts and refunds",
  "Messages, reviews and community posts",
  "Notification settings, devices and sign-in history",
];

function ExportCard() {
  const [proof, setProof] = React.useState("");
  const [done, setDone] = React.useState(false);
  const stepUp = useStepUpBody();

  const download = useAsyncAction(async () => {
    const data = await auth.exportData(stepUp(proof));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `skilrize-my-data-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setProof("");
    setDone(true);
  });

  return (
    <Card>
      <CardHeader
        title="Download your data"
        description="A copy of everything SkilRize holds about you, as a JSON file you can keep or take elsewhere."
      />
      <form
        className="space-y-5 p-5"
        onSubmit={(event) => {
          event.preventDefault();
          setDone(false);
          void download.run();
        }}
      >
        <ul className="grid gap-2 text-[13.5px] text-muted sm:grid-cols-2">
          {EXPORT_CONTENTS.map((item) => (
            <li key={item} className="flex gap-2">
              <Icon name="check" className="mt-0.5 size-4 shrink-0 text-positive" />
              {item}
            </li>
          ))}
        </ul>
        <p className="text-[13px] text-muted">
          Passwords and security keys are never included. Bank account and CNIC numbers show only
          their last four digits.
        </p>

        {download.error && <Alert tone="critical">{download.error}</Alert>}
        {done && <Alert tone="positive">Your download has started.</Alert>}

        <div className="max-w-sm">
          <StepUpField id="export_proof" value={proof} onChange={setProof} invalid={Boolean(download.error)} />
        </div>
        <Button type="submit" loading={download.pending}>
          <Icon name="file" className="size-4" />
          Download my data
        </Button>
      </form>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Policies                                                                   */
/* -------------------------------------------------------------------------- */

function PoliciesCard() {
  const documents: Array<[string, string]> = [
    ["Terms of Service", "/terms"],
    ["Privacy Policy", "/privacy"],
    ["Refund & Cancellation Policy", "/refunds"],
    ["Cookie Policy", "/cookies"],
  ];
  return (
    <Card>
      <CardHeader
        title="Policies"
        description={`The versions in force, dated ${BUSINESS.legalEffective}. We record which version you accepted, and tell you before any change takes effect.`}
      />
      <ul className="divide-y divide-line">
        {documents.map(([label, href]) => (
          <li key={href}>
            <Link
              href={href}
              className="flex items-center justify-between gap-3 px-5 py-3.5 text-[14px] text-fg transition-colors hover:bg-sunken"
            >
              {label}
              <span className="figure text-[12px] text-subtle">v{BUSINESS.legalVersion}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Delete                                                                     */
/* -------------------------------------------------------------------------- */

function DeleteCard() {
  const { data, loading, reload } = useLoader(() => auth.deletionPreview(), []);
  const [open, setOpen] = React.useState(false);
  const [confirm, setConfirm] = React.useState("");
  const [proof, setProof] = React.useState("");
  const stepUp = useStepUpBody();

  const erase = useAsyncAction(async () => {
    await auth.deleteAccount({ ...stepUp(proof), confirm });
    // A full page load rather than a client-side route change: clearing the
    // session in place would trip the signed-in guard, which sends the
    // visitor to /login before this navigation lands. The server has
    // already cleared the auth cookies, so the fresh load starts signed out.
    window.location.assign("/?account=deleted");
  });

  const blockers = data?.blockers ?? [];
  const blocked = blockers.length > 0;

  return (
    <Card className="border-critical/40">
      <CardHeader
        title="Delete your account"
        description="Your profile, identity documents, payout details and sign-ins are erased, and your listings are taken down. This cannot be undone."
      />
      <div className="space-y-5 p-5">
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : (
          <>
            {blocked && (
              <Alert tone="caution">
                <p className="font-semibold">Settle these first</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {blockers.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </Alert>
            )}

            {data && data.retained.length > 0 && (
              <div>
                <p className="text-[13.5px] font-semibold text-fg">Kept after deletion</p>
                <ul className="mt-2 space-y-1.5 text-[13.5px] text-muted">
                  {data.retained.map((item) => (
                    <li key={item} className="flex gap-2">
                      <Icon name="lock" className="mt-0.5 size-3.5 shrink-0 text-subtle" />
                      {item}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-[12.5px] text-subtle">
                  These are shown as “Deleted user” and are not linked to your name or email.
                </p>
              </div>
            )}
          </>
        )}

        {!open ? (
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="danger" disabled={loading || blocked} onClick={() => setOpen(true)}>
              Delete my account…
            </Button>
            {blocked && (
              <Button variant="ghost" size="sm" onClick={() => void reload()}>
                Check again
              </Button>
            )}
          </div>
        ) : (
          <form
            className="max-w-sm space-y-4 border-t border-line pt-5"
            onSubmit={(event) => {
              event.preventDefault();
              void erase.run();
            }}
          >
            {erase.error && <Alert tone="critical">{erase.error}</Alert>}
            <Field label="Type DELETE to confirm" htmlFor="delete_confirm" required>
              <Input
                id="delete_confirm"
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                required
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
              />
            </Field>
            <StepUpField id="delete_proof" value={proof} onChange={setProof} invalid={Boolean(erase.error)} />
            <div className="flex gap-3">
              <Button
                type="submit"
                variant="danger"
                loading={erase.pending}
                disabled={confirm.trim().toUpperCase() !== "DELETE" || !proof}
              >
                Delete account permanently
              </Button>
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Keep my account
              </Button>
            </div>
          </form>
        )}
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */

export default function PrivacySettingsPage() {
  return (
    <>
      <PageHeading
        title="Privacy & data"
        description="Get a copy of your data, see the policies you agreed to, or delete your account. How we use your data is explained in the Privacy Policy."
      />
      <div className="space-y-6">
        <ExportCard />
        <PoliciesCard />
        <DeleteCard />
      </div>
    </>
  );
}
