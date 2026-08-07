"use client";

import * as React from "react";

import { PASSWORD_MIN_LENGTH, PasswordPolicy } from "@/components/password";
import { PageHeading } from "@/components/shell";
import { TwoFactorEnrol } from "@/components/two-factor";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Icon,
  Input,
  Skeleton,
  cn,
} from "@/components/ui";
import { auth, type Session } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

/* -------------------------------------------------------------------------- */
/* Password                                                                   */
/* -------------------------------------------------------------------------- */

function PasswordCard() {
  const { setUser } = useSession();
  const [current, setCurrent] = React.useState("");
  const [next, setNext] = React.useState("");
  const [done, setDone] = React.useState(false);

  const change = useAsyncAction(async () => {
    const result = await auth.changePassword({ current_password: current, new_password: next });
    setUser(result.user);
    setCurrent("");
    setNext("");
    setDone(true);
    setTimeout(() => setDone(false), 4000);
  });

  return (
    <Card>
      <CardHeader
        title="Password"
        description="Changing it signs out every other device. This one stays signed in."
      />
      <form
        className="space-y-4 p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void change.run();
        }}
      >
        {change.error && <Alert tone="critical">{change.error}</Alert>}
        {done && <Alert tone="positive">Password updated and other sessions terminated.</Alert>}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Current password"
            htmlFor="current_password"
            error={change.fieldErrors.current_password}
            required
          >
            <Input
              id="current_password"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </Field>

          <Field
            label="New password"
            htmlFor="new_password"
            error={change.fieldErrors.new_password}
            required
          >
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              required
              minLength={PASSWORD_MIN_LENGTH}
              value={next}
              onChange={(event) => setNext(event.target.value)}
            />
          </Field>
        </div>

        {next.length > 0 && <PasswordPolicy password={next} />}

        <Button type="submit" loading={change.pending}>
          Update password
        </Button>
      </form>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Two-factor                                                                 */
/* -------------------------------------------------------------------------- */

function TwoFactorCard() {
  const { user, refresh } = useSession();
  const [enrolling, setEnrolling] = React.useState(false);
  const [disabling, setDisabling] = React.useState(false);
  const [proof, setProof] = React.useState("");

  const disable = useAsyncAction(async () => {
    await auth.twoFactorDisable(user?.has_two_factor ? { code: proof } : { password: proof });
    setDisabling(false);
    setProof("");
    await refresh();
  });

  if (!user) return null;

  return (
    <Card>
      <CardHeader
        title="Two-factor authentication"
        description="A code from your authenticator app, on top of your password. Required before money can move on your account."
        action={
          user.has_two_factor ? <Badge tone="positive">Enabled</Badge> : <Badge tone="caution">Not set up</Badge>
        }
      />

      <div className="p-5">
        {user.has_two_factor ? (
          disabling ? (
            <form
              className="max-w-sm space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void disable.run();
              }}
            >
              <Alert tone="caution">
                Turning this off makes your account materially easier to take over, and blocks
                payments until you enrol again.
              </Alert>
              {disable.error && <Alert tone="critical">{disable.error}</Alert>}

              <Field
                label="Authentication code"
                htmlFor="disable_code"
                hint="Step-up verification is required for this change."
                required
              >
                <Input
                  id="disable_code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  required
                  value={proof}
                  onChange={(event) => setProof(event.target.value)}
                  invalid={Boolean(disable.error)}
                />
              </Field>

              <div className="flex gap-3">
                <Button type="submit" variant="danger" loading={disable.pending}>
                  Turn off
                </Button>
                <Button type="button" variant="ghost" onClick={() => setDisabling(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <div className="flex flex-wrap items-center gap-4">
              <span className="inline-flex items-center gap-2 text-[13.5px] text-muted">
                <Icon name="shield" className="size-4 text-positive" />
                Your account asks for a code at every sign-in.
              </span>
              <Button variant="ghost" size="sm" onClick={() => setDisabling(true)}>
                Turn off
              </Button>
            </div>
          )
        ) : enrolling ? (
          <TwoFactorEnrol
            onComplete={() => setEnrolling(false)}
            onCancel={() => setEnrolling(false)}
          />
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            <p className="text-[13.5px] text-muted">
              Strongly recommended, and required before you can pay for or release any work.
            </p>
            <Button size="sm" onClick={() => setEnrolling(true)}>
              <Icon name="key" className="size-4" />
              Set up
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Sessions                                                                   */
/* -------------------------------------------------------------------------- */

function SessionsCard() {
  const { signOut } = useSession();
  const { data, loading, reload } = useLoader(() => auth.sessions(), []);
  const sessions: Session[] = data ?? [];

  const revoke = useAsyncAction(async (family: string) => {
    await auth.revokeSession(family);
    await reload();
  });

  const revokeAll = useAsyncAction(async () => {
    await auth.revokeAllSessions();
    await signOut();
  });

  return (
    <Card>
      <CardHeader
        title="Active sessions"
        description="Every device currently signed in. Revoking one takes effect immediately."
        action={
          <Button size="sm" variant="secondary" loading={revokeAll.pending} onClick={() => void revokeAll.run()}>
            Sign out everywhere
          </Button>
        }
      />

      {loading ? (
        <div className="space-y-3 p-5">
          {[0, 1].map((row) => (
            <Skeleton key={row} className="h-12 w-full" />
          ))}
        </div>
      ) : (
        <ul className="divide-y divide-line">
          {sessions.map((session) => (
            <li key={session.id} className="flex items-center gap-3 px-5 py-4">
              <span
                className={cn(
                  "grid size-9 shrink-0 place-items-center rounded-md",
                  session.is_current ? "bg-positive-soft text-positive" : "bg-sunken text-muted",
                )}
              >
                <Icon name="device" className="size-4" />
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-medium text-fg">
                  {session.device_label || "Unknown device"}
                </p>
                <p className="text-[12px] text-muted">
                  {session.ip_address ?? "IP unavailable"} · seen{" "}
                  {formatRelative(session.last_seen_at)}
                </p>
              </div>

              {session.is_current ? (
                <Badge tone="positive">This device</Badge>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  loading={revoke.pending}
                  onClick={() => void revoke.run(session.family)}
                >
                  Revoke
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* -------------------------------------------------------------------------- */

export default function SecuritySettingsPage() {
  return (
    <>
      <PageHeading
        title="Security"
        description="This platform holds money and identity documents on your behalf, so these controls are part of the product rather than an afterthought."
      />
      <div className="space-y-6">
        <TwoFactorCard />
        <PasswordCard />
        <SessionsCard />
      </div>
    </>
  );
}
