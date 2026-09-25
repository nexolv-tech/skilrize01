"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";

import { Icon, Spinner, ButtonLink } from "@/components/ui";
import { auth } from "@/lib/api";
import { useSession } from "@/lib/session";

type State = "working" | "done" | "failed";

function Confirm() {
  const params = useSearchParams();
  const { refresh } = useSession();
  const [state, setState] = React.useState<State>("working");
  const [message, setMessage] = React.useState("");

  const token = params.get("token");
  const email = params.get("email");
  // A missing token needs no request and no state change — it is knowable at
  // render time, so it is decided here rather than inside an effect.
  const incomplete = !token || !email;

  React.useEffect(() => {
    if (!token || !email) return;
    let cancelled = false;
    void (async () => {
      try {
        await auth.confirmEmail({ email, token });
        if (cancelled) return;
        setState("done");
        // The profile gate depends on this flag, so pull a fresh account.
        await refresh();
      } catch (error) {
        if (cancelled) return;
        setState("failed");
        setMessage((error as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, email, refresh]);

  if (incomplete) {
    return (
      <div className="animate-rise">
        <span className="grid size-11 place-items-center rounded-lg bg-critical-soft text-critical">
          <Icon name="x" className="size-5" strokeWidth={2.4} />
        </span>
        <h1 className="mt-5 display-md text-fg">Link not valid</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          This confirmation link is incomplete. You can request a new one from your dashboard.
        </p>
        <ButtonLink href="/dashboard" block size="lg" variant="secondary" className="mt-7">
          Go to dashboard
        </ButtonLink>
      </div>
    );
  }

  if (state === "working") {
    return (
      <div className="animate-fade flex flex-col items-center py-10 text-center">
        <Spinner className="size-7 text-accent" />
        <p className="mt-4 text-sm text-muted">Confirming your email…</p>
      </div>
    );
  }

  const success = state === "done";

  return (
    <div className="animate-rise">
      <span
        className={`grid size-11 place-items-center rounded-lg ${
          success ? "bg-positive-soft text-positive" : "bg-critical-soft text-critical"
        }`}
      >
        <Icon name={success ? "check" : "x"} className="size-5" strokeWidth={2.4} />
      </span>

      <h1 className="mt-5 display-md text-fg">
        {success ? "Email confirmed" : "Link not valid"}
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        {success
          ? "That is one of the three checks done. Add your phone number and identity document to finish unlocking transactions."
          : message || "This link is invalid or has expired. You can request a new one from your dashboard."}
      </p>

      <ButtonLink href="/dashboard" block size="lg" variant={success ? "primary" : "secondary"} className="mt-7">
        Go to dashboard
      </ButtonLink>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex justify-center py-10">
          <Spinner className="size-6 text-muted" />
        </div>
      }
    >
      <Confirm />
    </React.Suspense>
  );
}
