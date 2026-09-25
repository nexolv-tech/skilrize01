"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { PASSWORD_MIN_LENGTH, PasswordPolicy } from "@/components/password";
import { Alert, Button, Field, Icon, Input, Spinner, ButtonLink } from "@/components/ui";
import { auth } from "@/lib/api";
import { useAsyncAction } from "@/lib/session";

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const email = params.get("email") ?? "";

  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [mismatch, setMismatch] = React.useState(false);
  const [done, setDone] = React.useState(false);

  const submit = useAsyncAction(async () => {
    await auth.confirmPasswordReset({ email, token, password });
    setDone(true);
  });

  if (!token || !email) {
    return (
      <div className="animate-rise">
        <h1 className="display-md text-fg">Link not valid</h1>
        <p className="mt-2 text-sm text-muted">
          This reset link is incomplete. Request a fresh one and try again.
        </p>
        <ButtonLink href="/forgot-password" block className="mt-7">Request a new link</ButtonLink>
      </div>
    );
  }

  if (done) {
    return (
      <div className="animate-rise">
        <span className="grid size-11 place-items-center rounded-lg bg-positive-soft text-positive">
          <Icon name="check" className="size-5" strokeWidth={2.4} />
        </span>
        <h1 className="mt-5 display-md text-fg">Password updated</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Every other device has been signed out. Sign in again with your new password.
        </p>
        <Button block size="lg" className="mt-7" onClick={() => router.push("/login")}>
          Go to sign in
        </Button>
      </div>
    );
  }

  return (
    <div className="animate-rise">
      <h1 className="display-md text-fg">Set a new password</h1>
      <p className="mt-2 text-sm text-muted">
        For <span className="font-medium text-fg">{email}</span>
      </p>

      <form
        className="mt-7 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (password !== confirm) {
            setMismatch(true);
            return;
          }
          setMismatch(false);
          void submit.run();
        }}
      >
        {submit.error && <Alert tone="critical">{submit.error}</Alert>}

        <Field
          label="New password"
          htmlFor="password"
          error={submit.fieldErrors.password}
          required
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            autoFocus
            required
            minLength={PASSWORD_MIN_LENGTH}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            invalid={Boolean(submit.fieldErrors.password)}
          />
        </Field>

        {password.length > 0 && <PasswordPolicy password={password} />}

        <Field
          label="Confirm password"
          htmlFor="confirm"
          error={mismatch ? "Both passwords must match." : undefined}
          required
        >
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            invalid={mismatch}
          />
        </Field>

        <Button type="submit" block size="lg" loading={submit.pending}>
          Update password
        </Button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex justify-center py-10">
          <Spinner className="size-6 text-muted" />
        </div>
      }
    >
      <ResetForm />
    </React.Suspense>
  );
}
