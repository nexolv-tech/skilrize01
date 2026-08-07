"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
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
  Progress,
  Skeleton,
  cn,
} from "@/components/ui";
import { auth, notifications as notificationsApi, uploadFile, type Notification } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

/* -------------------------------------------------------------------------- */
/* The profile-completion gate                                                */
/* -------------------------------------------------------------------------- */


function StepShell({
  index,
  icon,
  title,
  description,
  done,
  pending,
  children,
}: {
  index: number;
  icon: "mail" | "phone" | "id";
  title: string;
  description: string;
  done: boolean;
  pending?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <li className="relative flex gap-4 p-5">
      {/* Connector between steps, stopping short of the last one. */}
      <span
        aria-hidden
        className="absolute left-[38px] top-[60px] h-[calc(100%-52px)] w-px bg-line last:hidden"
      />
      <span
        className={cn(
          "relative z-10 grid size-9 shrink-0 place-items-center rounded-full ring-4 ring-raised transition-colors duration-200",
          done
            ? "bg-positive text-white"
            : pending
              ? "bg-caution-soft text-caution"
              : "bg-sunken text-subtle",
        )}
      >
        {done ? (
          <Icon name="check" className="size-4" strokeWidth={2.6} />
        ) : (
          <Icon name={icon} className="size-4" />
        )}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-medium text-fg">
            <span className="mr-1.5 text-subtle">{index}.</span>
            {title}
          </h3>
          {done ? (
            <Badge tone="positive">Verified</Badge>
          ) : pending ? (
            <Badge tone="caution">In review</Badge>
          ) : (
            <Badge>Required</Badge>
          )}
        </div>
        <p className="mt-1 text-[13px] leading-relaxed text-muted">{description}</p>
        {!done && children && <div className="mt-4">{children}</div>}
      </div>
    </li>
  );
}

function EmailStep() {
  const { user } = useSession();
  const [sent, setSent] = React.useState(false);

  const resend = useAsyncAction(async () => {
    await auth.requestEmailVerification();
    setSent(true);
  });

  return (
    <StepShell
      index={1}
      icon="mail"
      title="Confirm your email"
      description={`We sent a link to ${user?.email}. Opening it confirms the address.`}
      done={user?.email_verified ?? false}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" variant="secondary" loading={resend.pending} onClick={() => void resend.run()}>
          {sent ? "Send again" : "Resend link"}
        </Button>
        {sent && !resend.error && (
          <span className="text-[13px] text-positive">Sent — check your inbox.</span>
        )}
        {resend.error && <span className="text-[13px] text-critical">{resend.error}</span>}
      </div>
    </StepShell>
  );
}

function PhoneStep() {
  const { user, refresh } = useSession();
  const [phone, setPhone] = React.useState(user?.phone_number ?? "");
  const [code, setCode] = React.useState("");
  const [awaitingCode, setAwaitingCode] = React.useState(false);

  const sendCode = useAsyncAction(async () => {
    await auth.setPhone(phone);
    setAwaitingCode(true);
  });

  const confirmCode = useAsyncAction(async () => {
    await auth.verifyPhone(code);
    await refresh();
  });

  return (
    <StepShell
      index={2}
      icon="phone"
      title="Verify your phone"
      description="A six-digit code by SMS. Used for account recovery and security alerts."
      done={user?.phone_verified ?? false}
    >
      {awaitingCode ? (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void confirmCode.run();
          }}
        >
          <Field
            label="Code"
            htmlFor="otp"
            className="w-40"
            error={confirmCode.error ?? confirmCode.fieldErrors.code}
          >
            <Input
              id="otp"
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              placeholder="123456"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              invalid={Boolean(confirmCode.error)}
              className="tracking-[0.2em]"
            />
          </Field>
          <Button type="submit" size="sm" loading={confirmCode.pending} className="mb-0.5">
            Verify
          </Button>
          <button
            type="button"
            onClick={() => setAwaitingCode(false)}
            className="mb-2.5 text-[13px] text-muted transition-colors hover:text-fg"
          >
            Change number
          </button>
        </form>
      ) : (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void sendCode.run();
          }}
        >
          <Field
            label="Phone number"
            htmlFor="phone"
            className="w-56"
            error={sendCode.error ?? sendCode.fieldErrors.phone_number}
          >
            <Input
              id="phone"
              type="tel"
              autoComplete="tel"
              placeholder="+92 300 1234567"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              invalid={Boolean(sendCode.error)}
            />
          </Field>
          <Button type="submit" size="sm" loading={sendCode.pending} className="mb-0.5">
            Send code
          </Button>
        </form>
      )}
    </StepShell>
  );
}

function IdentityStep() {
  const { user, refresh } = useSession();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const status = user?.identity_status ?? "unverified";

  const submit = useAsyncAction(async (file: File) => {
    await uploadFile("/auth/identity/", file);
    await refresh();
  });

  return (
    <StepShell
      index={3}
      icon="id"
      title="Verify your identity"
      description="Upload your national identity card. Required of everyone, because the platform holds money on your behalf. The image is encrypted, access is logged, and it is deleted once reviewed."
      done={status === "verified"}
      pending={status === "pending"}
    >
      {status === "rejected" && (
        <Alert tone="critical" className="mb-3">
          That submission was rejected. Please upload a clearer photo of the full card.
        </Alert>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void submit.run(file);
          event.target.value = "";
        }}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          variant="secondary"
          loading={submit.pending}
          onClick={() => inputRef.current?.click()}
        >
          <Icon name="id" className="size-4" />
          Upload document
        </Button>
        <span className="text-[12.5px] text-subtle">JPG, PNG, WebP or PDF · up to 10 MB</span>
      </div>

      {submit.error && <p className="mt-2 text-[13px] text-critical">{submit.error}</p>}
    </StepShell>
  );
}

function VerificationJourney() {
  const { user } = useSession();
  if (!user) return null;

  const remaining = user.missing_requirements.length;

  return (
    <Card>
      <CardHeader
        title="Finish setting up your account"
        description={
          user.can_transact
            ? "All checks passed. You can post projects, publish gigs, and transact."
            : `${remaining} ${remaining === 1 ? "check" : "checks"} left before you can post, sell, or buy. You can browse freely in the meantime.`
        }
        action={
          user.can_transact ? (
            <Badge tone="positive">
              <Icon name="check" className="size-3" strokeWidth={2.6} />
              Ready to transact
            </Badge>
          ) : (
            <Badge tone="caution">Restricted</Badge>
          )
        }
      />

      <div className="px-5 pt-5">
        <Progress value={user.profile_strength} label="Profile strength" />
      </div>

      <ul className="mt-2 divide-y divide-line">
        <EmailStep />
        <PhoneStep />
        <IdentityStep />
      </ul>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Supporting panels                                                          */
/* -------------------------------------------------------------------------- */

function StudentPortalCard() {
  const { user } = useSession();
  if (!user) return null;

  if (user.is_verified_student) {
    return (
      <Card className="p-5">
        <div className="flex items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-md bg-accent-soft text-accent">
            <Icon name="building" className="size-[18px]" />
          </span>
          <div>
            <p className="text-sm font-medium text-fg">{user.university?.name}</p>
            <p className="text-[12.5px] text-muted">Campus portal unlocked</p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="relative overflow-hidden p-5">
      <div className="bg-aurora absolute inset-0 opacity-70" aria-hidden />
      <div className="relative">
        <Badge tone="accent">
          <Icon name="sparkles" className="size-3" />
          Students
        </Badge>
        <h3 className="mt-3 text-[15px] font-semibold text-fg">Unlock your campus portal</h3>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
          Verify with your university email and student ID to reach a private marketplace only your
          university can see — plus peer messaging and communities.
        </p>
        <Button size="sm" variant="secondary" className="mt-4" disabled>
          <Icon name="lock" className="size-3.5" />
          Arriving in Phase 4
        </Button>
      </div>
    </Card>
  );
}

function SecuritySummary() {
  const { user } = useSession();
  if (!user) return null;

  return (
    <Card>
      <CardHeader title="Security" />
      <ul className="divide-y divide-line">
        {[
          {
            label: "Two-factor authentication",
            value: user.has_two_factor,
            on: "Enabled",
            off: "Not set up",
          },
          { label: "Email confirmed", value: user.email_verified, on: "Yes", off: "Pending" },
          { label: "Phone confirmed", value: user.phone_verified, on: "Yes", off: "Pending" },
        ].map((row) => (
          <li key={row.label} className="flex items-center justify-between gap-3 px-5 py-3">
            <span className="text-[13px] text-muted">{row.label}</span>
            <Badge tone={row.value ? "positive" : "neutral"}>{row.value ? row.on : row.off}</Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function NotificationsPanel() {
  const { data, loading } = useLoader(async () => {
    const result = await notificationsApi.list();
    return (Array.isArray(result) ? result : result.results).slice(0, 5);
  }, []);
  const items: Notification[] | null = loading ? null : (data ?? []);

  return (
    <Card>
      <CardHeader title="Recent activity" />
      {items === null ? (
        <div className="space-y-3 p-5">
          {[0, 1, 2].map((row) => (
            <div key={row} className="space-y-2">
              <Skeleton className="h-3.5 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Icon name="bell" className="size-5" />}
          title="Nothing yet"
          description="Verification updates, security alerts, and contract activity will appear here."
        />
      ) : (
        <ul className="divide-y divide-line">
          {items.map((item) => (
            <li key={item.id} className="flex gap-3 px-5 py-3.5">
              <span
                className={cn(
                  "mt-1.5 size-1.5 shrink-0 rounded-full",
                  item.is_read ? "bg-line-strong" : "bg-accent",
                )}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-fg">{item.title}</p>
                {item.body && <p className="mt-0.5 text-[12.5px] text-muted">{item.body}</p>}
                <p className="mt-1 text-[11.5px] text-subtle">{formatRelative(item.created_at)}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* -------------------------------------------------------------------------- */

export default function DashboardPage() {
  const { user } = useSession();
  const firstName = user?.full_name?.split(" ")[0] ?? user?.handle ?? "there";

  return (
    <>
      <PageHeading
        title={`Welcome, ${firstName}`}
        description="Your account, your verification status, and everything that unlocks as SkilRize is built out."
      />

      {user && !user.can_transact && (
        <Alert tone="caution" title="Your profile is not complete yet" className="mb-6">
          You can browse the platform freely. Posting projects, publishing gigs, submitting
          proposals, and buying are unlocked once all three checks below are passed.
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          <VerificationJourney />
          <NotificationsPanel />
        </div>
        <div className="space-y-6">
          <StudentPortalCard />
          <SecuritySummary />
        </div>
      </div>
    </>
  );
}
