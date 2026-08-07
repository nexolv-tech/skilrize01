"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Alert, Button, Field, Icon, Input } from "@/components/ui";
import { auth } from "@/lib/api";
import { useAsyncAction, useSession } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const { setUser } = useSession();

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [code, setCode] = React.useState("");
  /** Set when the password was right but a second factor is still required. */
  const [challenge, setChallenge] = React.useState<string | null>(null);

  const signIn = useAsyncAction(async () => {
    const result = await auth.login({ email, password });
    if (result.two_factor_required && result.challenge) {
      setChallenge(result.challenge);
      return;
    }
    if (result.user) {
      setUser(result.user);
      router.push("/dashboard");
    }
  });

  const submitCode = useAsyncAction(async () => {
    const result = await auth.loginTwoFactor({ challenge: challenge!, code });
    setUser(result.user);
    router.push("/dashboard");
  });

  if (challenge) {
    return (
      <div className="animate-rise">
        <span className="grid size-11 place-items-center rounded-lg bg-accent-soft text-accent">
          <Icon name="shield" className="size-5" />
        </span>
        <h1 className="mt-5 text-2xl font-semibold tracking-[-0.025em] text-fg">
          Enter your code
        </h1>
        <p className="mt-2 text-sm text-muted">
          Open your authenticator app and enter the six-digit code. A recovery code works too.
        </p>

        <form
          className="mt-7 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submitCode.run();
          }}
        >
          {submitCode.error && <Alert tone="critical">{submitCode.error}</Alert>}

          <Field label="Authentication code" htmlFor="code" error={submitCode.fieldErrors.code}>
            <Input
              id="code"
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              placeholder="123456"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              invalid={Boolean(submitCode.error)}
              className="text-center text-lg tracking-[0.35em]"
            />
          </Field>

          <Button type="submit" block size="lg" loading={submitCode.pending}>
            Verify and sign in
          </Button>

          <button
            type="button"
            onClick={() => {
              setChallenge(null);
              setCode("");
            }}
            className="w-full rounded-md py-1 text-[13px] text-muted transition-colors hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Back to sign in
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="animate-rise">
      <h1 className="text-2xl font-semibold tracking-[-0.025em] text-fg">Welcome back</h1>
      <p className="mt-2 text-sm text-muted">
        New here?{" "}
        <Link href="/signup" className="font-medium text-accent underline-offset-4 hover:underline">
          Create an account
        </Link>
      </p>

      <form
        className="mt-7 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void signIn.run();
        }}
      >
        {signIn.error && <Alert tone="critical">{signIn.error}</Alert>}

        <Field label="Email" htmlFor="email" error={signIn.fieldErrors.email} required>
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
            invalid={Boolean(signIn.fieldErrors.email)}
          />
        </Field>

        <Field label="Password" htmlFor="password" error={signIn.fieldErrors.password} required>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            placeholder="••••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            invalid={Boolean(signIn.fieldErrors.password)}
          />
        </Field>

        <div className="flex justify-end">
          <Link
            href="/forgot-password"
            className="text-[13px] text-muted underline-offset-4 transition-colors hover:text-fg hover:underline"
          >
            Forgot your password?
          </Link>
        </div>

        <Button type="submit" block size="lg" loading={signIn.pending}>
          Sign in
        </Button>
      </form>
    </div>
  );
}
