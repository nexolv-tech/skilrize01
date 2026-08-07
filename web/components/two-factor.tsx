"use client";

/**
 * Two-factor enrolment, in one place.
 *
 * The same flow is reachable from two directions — deliberately, from Settings
 * → Security, and reactively, when a payment is refused with
 * `two_factor_required`. Those must be the same code: an enrolment path that
 * only exists on the settings page would mean the user hitting the wall at
 * checkout gets sent away to find it, and most of them would not come back.
 */

import * as React from "react";

import { Alert, Button, Card, CardHeader, Field, Icon, Input } from "@/components/ui";
import { auth } from "@/lib/api";
import { useAsyncAction, useSession } from "@/lib/session";

type Enrolment = { secret: string; qr: string };

/**
 * The QR, the confirmation field, and the recovery codes that follow.
 *
 * `onComplete` fires only after the user has acknowledged their recovery codes,
 * not the moment the code verifies — the codes are shown exactly once, and
 * closing the flow out from under them loses the only copy.
 */
export function TwoFactorEnrol({
  onComplete,
  onCancel,
}: {
  onComplete?: () => void;
  onCancel?: () => void;
}) {
  const { refresh } = useSession();
  const [enrolment, setEnrolment] = React.useState<Enrolment | null>(null);
  const [showKey, setShowKey] = React.useState(false);
  const [code, setCode] = React.useState("");
  const [recoveryCodes, setRecoveryCodes] = React.useState<string[] | null>(null);

  const begin = useAsyncAction(async () => {
    const result = await auth.twoFactorSetup();
    setEnrolment({ secret: result.secret, qr: result.qr_svg });
    setShowKey(false);
  });

  const confirm = useAsyncAction(async () => {
    const result = await auth.twoFactorConfirm(code);
    setRecoveryCodes(result.recovery_codes);
    setEnrolment(null);
    setCode("");
    await refresh();
  });

  // Started on mount when the caller is a blocking prompt, so the user does not
  // have to press "set up" after already being told they must.
  React.useEffect(() => {
    void begin.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (recoveryCodes) {
    return (
      <div>
        <p className="text-[13.5px] text-muted">
          Two-factor authentication is on. Save these recovery codes — each works once if you
          lose your authenticator, and this is the only time they are shown.
        </p>
        <ul className="mt-4 grid grid-cols-2 gap-2 rounded-md border border-line bg-sunken p-4 font-mono text-[13px] sm:grid-cols-3">
          {recoveryCodes.map((recovery) => (
            <li key={recovery} className="tabular text-fg">
              {recovery}
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void navigator.clipboard?.writeText(recoveryCodes.join("\n"))}
          >
            Copy all
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setRecoveryCodes(null);
              onComplete?.();
            }}
          >
            I have saved them
          </Button>
        </div>
      </div>
    );
  }

  if (begin.pending || !enrolment) {
    return (
      <div className="space-y-3">
        {begin.error && <Alert tone="critical">{begin.error}</Alert>}
        {begin.pending && <p className="text-[13.5px] text-muted">Preparing your QR code…</p>}
      </div>
    );
  }

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        void confirm.run();
      }}
    >
      <div className="grid gap-6 sm:grid-cols-[auto_1fr]">
        {/* Rendered server-side and delivered as a data URI, so the shared
            secret never passes through a QR library in the browser. The white
            plate is fixed in both themes — scanners need dark-on-light, and a
            dark-mode inversion breaks them. */}
        <div className="mx-auto shrink-0 rounded-xl border border-line bg-white p-3 shadow-e1 sm:mx-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={enrolment.qr}
            alt="QR code for enrolling this account in your authenticator app"
            width={176}
            height={176}
            className="size-44"
          />
        </div>

        <div className="min-w-0">
          <ol className="space-y-2.5 text-[13.5px] text-muted">
            {[
              "Open Google Authenticator, Authy, or 1Password.",
              "Scan this QR code with the app.",
              "Enter the six-digit code it shows.",
            ].map((step, index) => (
              <li key={step} className="flex gap-2.5">
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent">
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>

          {/* Behind a disclosure: the manual key is the fallback for an
              authenticator that cannot scan, and printing it beside the QR by
              default invites people to copy a secret around. */}
          <div className="mt-5">
            <button
              type="button"
              onClick={() => setShowKey((value) => !value)}
              aria-expanded={showKey}
              className="text-[13px] font-medium text-accent underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {showKey ? "Hide setup key" : "Can't scan? Enter a key instead"}
            </button>

            {showKey && (
              <div className="animate-fade mt-3">
                <code className="block break-all rounded-md border border-line bg-sunken px-3.5 py-3 font-mono text-[13px] tracking-wide text-fg">
                  {enrolment.secret}
                </code>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-2"
                  onClick={() => void navigator.clipboard?.writeText(enrolment.secret)}
                >
                  Copy key
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {confirm.error && <Alert tone="critical">{confirm.error}</Alert>}

      <Field
        label="Enter the six-digit code to confirm"
        htmlFor="totp"
        error={confirm.fieldErrors.code}
        required
        className="max-w-xs"
      >
        <Input
          id="totp"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          required
          maxLength={6}
          placeholder="123456"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          invalid={Boolean(confirm.error)}
          className="text-center text-[18px] tracking-[0.4em]"
        />
      </Field>

      <div className="flex gap-3">
        <Button type="submit" loading={confirm.pending}>
          Enable
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

/**
 * Shown when the API refuses a payment with `two_factor_required`.
 *
 * Explains why the wall exists before showing the QR. "Set up 2FA" with no
 * reason attached reads as bureaucracy; "this protects the money you are about
 * to move" is the same request with the answer already given.
 */
export function TwoFactorRequiredPrompt({ onComplete }: { onComplete?: () => void }) {
  return (
    <Card className="border-caution/40">
      <CardHeader
        title="Set up two-factor authentication to continue"
        description="Required before money can move on your account — it is what stops someone with your password from spending your balance."
        action={
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-caution-soft text-caution">
            <Icon name="shield" className="size-5" />
          </span>
        }
      />
      <div className="p-5">
        <TwoFactorEnrol onComplete={onComplete} />
      </div>
    </Card>
  );
}
