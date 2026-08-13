"use client";

/**
 * OAuth redirect target. Every provider's `authorize_url` (built by
 * `integrations.authorize` in `lib/api.ts`) points back here with `code` and
 * `state` on the query string — this page's only job is to hand those to the
 * backend's authenticated `connect` endpoint while the user is still signed
 * in normally, then send them back to the settings page.
 */

import * as React from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";

import { Button, Icon, Spinner } from "@/components/ui";
import { integrations, type IntegrationProvider } from "@/lib/api";

type State = "working" | "done" | "failed";

function Confirm() {
  const { provider } = useParams<{ provider: string }>();
  const params = useSearchParams();
  const [state, setState] = React.useState<State>("working");
  const [message, setMessage] = React.useState("");

  const code = params.get("code");
  const oauthState = params.get("state");
  const providerError = params.get("error");
  // Known invalid at render time, so it is decided here rather than inside
  // an effect — the effect below only ever runs the async connect call.
  const invalidReason = providerError
    ? "The connection was cancelled or denied."
    : !code || !oauthState
      ? "This link is missing information and cannot be completed."
      : null;

  React.useEffect(() => {
    if (invalidReason || !code || !oauthState) return;
    let cancelled = false;
    void (async () => {
      try {
        await integrations.connect(provider as IntegrationProvider, code, oauthState);
        if (!cancelled) setState("done");
      } catch (error) {
        if (!cancelled) {
          setState("failed");
          setMessage((error as Error).message);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [provider, code, oauthState, invalidReason]);

  if (invalidReason) {
    return (
      <div className="mx-auto max-w-sm py-16 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-lg bg-critical-soft text-critical">
          <Icon name="x" className="size-5" strokeWidth={2.4} />
        </span>
        <h1 className="mt-5 text-xl font-semibold tracking-[-0.025em] text-fg">Could not connect</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">{invalidReason}</p>
        <Link href="/settings/integrations" className="mt-7 block">
          <Button block size="lg">
            Back to Integrations
          </Button>
        </Link>
      </div>
    );
  }

  if (state === "working") {
    return (
      <div className="flex flex-col items-center py-16 text-center">
        <Spinner className="size-7 text-accent" />
        <p className="mt-4 text-sm text-muted">Connecting your account…</p>
      </div>
    );
  }

  const success = state === "done";

  return (
    <div className="mx-auto max-w-sm py-16 text-center">
      <span
        className={`mx-auto grid size-11 place-items-center rounded-lg ${
          success ? "bg-positive-soft text-positive" : "bg-critical-soft text-critical"
        }`}
      >
        <Icon name={success ? "check" : "x"} className="size-5" strokeWidth={2.4} />
      </span>
      <h1 className="mt-5 text-xl font-semibold tracking-[-0.025em] text-fg">
        {success ? "Connected" : "Could not connect"}
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        {success ? "That account is now linked to SkilRize." : message}
      </p>
      <Link href="/settings/integrations" className="mt-7 block">
        <Button block size="lg">
          Back to Integrations
        </Button>
      </Link>
    </div>
  );
}

export default function IntegrationsCallbackPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex justify-center py-16">
          <Spinner className="size-6 text-muted" />
        </div>
      }
    >
      <Confirm />
    </React.Suspense>
  );
}
