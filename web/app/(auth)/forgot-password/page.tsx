"use client";

import * as React from "react";
import Link from "next/link";

import { Alert, Button, Field, Icon, Input } from "@/components/ui";
import { auth } from "@/lib/api";
import { useAsyncAction } from "@/lib/session";

export default function ForgotPasswordPage() {
  const [email, setEmail] = React.useState("");
  const [sent, setSent] = React.useState(false);

  const submit = useAsyncAction(async () => {
    await auth.requestPasswordReset(email);
    setSent(true);
  });

  // The response is identical whether or not the address is registered, so the
  // screen must be too — anything else turns this form into an account oracle.
  if (sent) {
    return (
      <div className="animate-rise">
        <span className="grid size-11 place-items-center rounded-lg bg-positive-soft text-positive">
          <Icon name="mail" className="size-5" />
        </span>
        <h1 className="mt-5 text-2xl font-semibold tracking-[-0.025em] text-fg">Check your inbox</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          If <span className="font-medium text-fg">{email}</span> has an account, a reset link is on
          its way. It expires in 30 minutes and can be used once.
        </p>
        <Link href="/login" className="mt-7 block">
          <Button variant="secondary" block>
            Back to sign in
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="animate-rise">
      <h1 className="text-2xl font-semibold tracking-[-0.025em] text-fg">Reset your password</h1>
      <p className="mt-2 text-sm text-muted">
        Enter your email and we will send you a link to set a new one.
      </p>

      <form
        className="mt-7 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void submit.run();
        }}
      >
        {submit.error && <Alert tone="critical">{submit.error}</Alert>}

        <Field label="Email" htmlFor="email" error={submit.fieldErrors.email} required>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            autoFocus
            required
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            invalid={Boolean(submit.fieldErrors.email)}
          />
        </Field>

        <Button type="submit" block size="lg" loading={submit.pending}>
          Send reset link
        </Button>

        <Link
          href="/login"
          className="block rounded-md py-1 text-center text-[13px] text-muted transition-colors hover:text-fg"
        >
          Back to sign in
        </Link>
      </form>
    </div>
  );
}
