"use client";

/**
 * Student verification, as a single card that knows where it is.
 *
 * The step shown is driven by `application.next_step`, which the server
 * computes. The client deliberately does not re-derive it from `status`: some
 * universities skip the ID card entirely (`University.require_id_card`), and a
 * UI branching on its own copy of that rule is how a student ends up being
 * asked for a document nobody wants.
 */

import * as React from "react";

import { Alert, Badge, Button, Card, CardHeader, Field, Icon, Input, cn } from "@/components/ui";
import { auth, type StudentApplication } from "@/lib/api";
import { useAsyncAction, useSession } from "@/lib/session";

const STEPS = ["University email", "Confirm code", "Student ID", "Review"] as const;

function stepIndexFor(application: StudentApplication | null): number {
  if (!application) return 0;
  switch (application.next_step) {
    case "confirm_email":
      return 1;
    case "upload_id_card":
      return 2;
    case "wait_for_review":
      return 3;
    default:
      return STEPS.length;
  }
}

function Stepper({ current, skipIdCard }: { current: number; skipIdCard: boolean }) {
  const steps = skipIdCard ? STEPS.filter((label) => label !== "Student ID") : STEPS;
  return (
    <ol className="mb-6 flex flex-wrap items-center gap-x-2 gap-y-2">
      {steps.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                "grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold",
                done && "bg-positive text-white",
                active && "bg-accent text-on-accent",
                !done && !active && "bg-sunken text-subtle",
              )}
            >
              {done ? <Icon name="check" className="size-3" strokeWidth={3} /> : index + 1}
            </span>
            <span
              className={cn(
                "text-[12.5px]",
                active ? "font-medium text-fg" : done ? "text-muted" : "text-subtle",
              )}
            >
              {label}
            </span>
            {index < steps.length - 1 && (
              <span className="h-px w-4 bg-line-strong sm:w-6" aria-hidden />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function StudentVerificationCard() {
  const { user, refresh } = useSession();
  const [application, setApplication] = React.useState<StudentApplication | null>(null);
  const [loaded, setLoaded] = React.useState(false);

  const [email, setEmail] = React.useState("");
  const [code, setCode] = React.useState("");
  const [file, setFile] = React.useState<File | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    void auth
      .studentApplication()
      .then((result) => {
        if (!cancelled) setApplication(result.application);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const start = useAsyncAction(async () => {
    const result = await auth.startStudentVerification(email);
    setApplication(result.application);
    setEmail("");
  });

  const confirm = useAsyncAction(async () => {
    const result = await auth.confirmStudentEmail(code);
    setApplication(result.application);
    setCode("");
    // Universities that skip the ID card are approved by a reviewer straight
    // away, so the account may already have changed underneath us.
    await refresh();
  });

  const upload = useAsyncAction(async () => {
    const result = await auth.uploadStudentIdCard(file!);
    setApplication(result.application);
    setFile(null);
  });

  if (!user) return null;

  const step = stepIndexFor(application);
  const verified = user.is_verified_student;

  return (
    <Card>
      <CardHeader
        title="Student verification"
        description="Verify with your university email to unlock your campus marketplace — a private portal only your university can see."
        action={
          verified ? (
            <Badge tone="positive">Verified</Badge>
          ) : application ? (
            <Badge tone="caution">In progress</Badge>
          ) : (
            <Badge>Not started</Badge>
          )
        }
      />

      <div className="p-5">
        {!loaded ? (
          <p className="text-[13.5px] text-muted">Loading…</p>
        ) : verified ? (
          <div className="flex flex-wrap items-center gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-positive-soft text-positive">
              <Icon name="building" className="size-5" />
            </span>
            <p className="text-[13.5px] text-muted">
              You are verified at{" "}
              <span className="font-medium text-fg">{user.university?.name}</span>. Switch to your
              campus portal from the header.
            </p>
          </div>
        ) : (
          <>
            <Stepper current={step} skipIdCard={application?.id_card_required === false} />

            {application?.status === "rejected" && (
              <Alert tone="critical" title="Not approved" className="mb-5">
                {application.rejection_reason || "Your last application was not approved."} You can
                start again below.
              </Alert>
            )}

            {/* Step 1 — claim the address */}
            {(!application || application.next_step === "start_again") && (
              <form
                className="max-w-md space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void start.run();
                }}
              >
                {start.error && <Alert tone="critical">{start.error}</Alert>}
                <Field
                  label="University email"
                  htmlFor="university_email"
                  hint="We send a code here. This can be different from your account email."
                  error={start.fieldErrors.university_email}
                  required
                >
                  <Input
                    id="university_email"
                    type="email"
                    required
                    placeholder="fa21-bcs-001@cuiatd.edu.pk"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    invalid={Boolean(start.error)}
                  />
                </Field>
                <Button type="submit" loading={start.pending}>
                  Send code
                </Button>
              </form>
            )}

            {/* Step 2 — prove it */}
            {application?.next_step === "confirm_email" && (
              <form
                className="max-w-md space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void confirm.run();
                }}
              >
                <p className="text-[13.5px] text-muted">
                  We sent a six-digit code to{" "}
                  <span className="font-medium text-fg">{application.university_email}</span>.
                </p>
                {confirm.error && <Alert tone="critical">{confirm.error}</Alert>}
                <Field label="Code" htmlFor="student_code" error={confirm.fieldErrors.code} required>
                  <Input
                    id="student_code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    required
                    placeholder="123456"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    invalid={Boolean(confirm.error)}
                    className="max-w-40 text-center text-[17px] tracking-[0.35em]"
                  />
                </Field>
                <div className="flex gap-3">
                  <Button type="submit" loading={confirm.pending}>
                    Confirm
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setApplication(null)}
                  >
                    Use a different address
                  </Button>
                </div>
              </form>
            )}

            {/* Step 3 — the card, where the university asks for one */}
            {application?.next_step === "upload_id_card" && (
              <form
                className="max-w-md space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void upload.run();
                }}
              >
                <Alert tone="positive">
                  {application.university_email} confirmed. {application.university.name} also asks
                  for your student ID card.
                </Alert>
                {upload.error && <Alert tone="critical">{upload.error}</Alert>}
                <Field
                  label="Student ID card"
                  htmlFor="id_card"
                  hint="A clear photo or scan. Stored privately, and every view of it is logged."
                  required
                >
                  <Input
                    id="id_card"
                    type="file"
                    accept="image/*,application/pdf"
                    required
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                    className="file:mr-3 file:rounded-md file:border-0 file:bg-sunken file:px-3 file:py-1.5 file:text-[13px] file:text-fg"
                  />
                </Field>
                <Button type="submit" loading={upload.pending} disabled={!file}>
                  Submit for review
                </Button>
              </form>
            )}

            {/* Step 4 — waiting on a human */}
            {application?.next_step === "wait_for_review" && (
              <Alert tone="caution" title="With our team">
                We are reviewing your {application.university.short_code} verification. You will be
                notified as soon as it is decided — usually within a day.
              </Alert>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
