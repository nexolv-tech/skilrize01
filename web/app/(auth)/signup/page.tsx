"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PASSWORD_MIN_LENGTH, PasswordPolicy } from "@/components/password";
import { Alert, Badge, Button, Field, Icon, Input } from "@/components/ui";
import { auth, type University } from "@/lib/api";
import { useAsyncAction, useSession } from "@/lib/session";

export default function SignupPage() {
  const router = useRouter();
  const { setUser } = useSession();

  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [university, setUniversity] = React.useState<{
    domainFor: string;
    value: University | null;
  } | null>(null);

  // Whether the address is even worth looking up is knowable at render time.
  const lookupTarget = /@[^@\s]+\.[^@\s]+$/.test(email) ? email : "";
  // A hint for an address the user has since edited is stale, so it is dropped
  // during render rather than cleared from inside the effect.
  const matchedUniversity = university?.domainFor === lookupTarget ? university.value : null;

  // If the address belongs to a registered university, say so — it is a strong
  // reason to finish signing up. Verification itself happens later, from
  // settings.
  React.useEffect(() => {
    if (!lookupTarget) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await auth.lookupUniversity(lookupTarget);
        if (!cancelled) {
          setUniversity({
            domainFor: lookupTarget,
            value: result.matched ? (result.university ?? null) : null,
          });
        }
      } catch {
        // A failed hint is purely additive; it is not worth surfacing.
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [lookupTarget]);

  const register = useAsyncAction(async () => {
    const result = await auth.signup({ email, password, full_name: fullName });
    setUser(result.user);
    router.push("/dashboard");
  });

  return (
    <div className="animate-rise">
      <h1 className="text-2xl font-semibold tracking-[-0.025em] text-fg">Create your account</h1>
      <p className="mt-2 text-sm text-muted">
        Already have one?{" "}
        <Link href="/login" className="font-medium text-accent underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>

      <form
        className="mt-7 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void register.run();
        }}
      >
        {register.error && <Alert tone="critical">{register.error}</Alert>}

        <Field label="Full name" htmlFor="full_name" error={register.fieldErrors.full_name}>
          <Input
            id="full_name"
            name="full_name"
            autoComplete="name"
            autoFocus
            placeholder="Ahmed Raza"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
        </Field>

        <Field
          label="Email"
          htmlFor="email"
          error={register.fieldErrors.email}
          required
          hint="Use any address. You can add a university email later to unlock your campus portal."
        >
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            invalid={Boolean(register.fieldErrors.email)}
          />
        </Field>

        {matchedUniversity && (
          <div className="animate-fade flex items-start gap-2.5 rounded-md border border-accent/30 bg-accent-soft px-3.5 py-3">
            <Icon name="building" className="mt-0.5 size-4 shrink-0 text-accent" />
            <div className="text-[13px]">
              <p className="font-medium text-fg">
                {matchedUniversity.name} <Badge tone="accent">Portal available</Badge>
              </p>
              <p className="mt-0.5 text-muted">
                Finish signing up, then verify to unlock the campus marketplace.
              </p>
            </div>
          </div>
        )}

        <Field
          label="Password"
          htmlFor="password"
          error={register.fieldErrors.password}
          required
        >
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={PASSWORD_MIN_LENGTH}
            placeholder="••••••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            invalid={Boolean(register.fieldErrors.password)}
          />
        </Field>

        {/* Shown from the first keystroke rather than on failure: the rules are
            hard requirements, so a user who cannot see them is just guessing. */}
        {password.length > 0 && <PasswordPolicy password={password} />}

        <Button type="submit" block size="lg" loading={register.pending}>
          Create account
        </Button>

        <p className="text-center text-[12px] leading-relaxed text-subtle">
          By continuing you agree to the Terms of Service and Privacy Policy.
        </p>
      </form>
    </div>
  );
}
