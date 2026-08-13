"use client";

import * as React from "react";
import { useParams } from "next/navigation";

import { PageHeading } from "@/components/shell";
import { Alert, Badge, Button, Card, Field, Icon, Input, Skeleton, Textarea } from "@/components/ui";
import { challenges, type Challenge, type ChallengeParticipation } from "@/lib/api";
import { useAsyncAction, useLoader } from "@/lib/session";

/** Ticks every 30s so a countdown/deadline check on screen does not go stale
 * while someone sits on the page. */
function useNow(intervalMs = 30_000): number {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function countdownLabel(deadline: string, now: number): string {
  const ms = new Date(deadline).getTime() - now;
  if (ms <= 0) return "Time's up";
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h left to submit`;
  return `${hours}h ${minutes}m left to submit`;
}

function JoinPanel({
  challenge,
  onJoined,
}: {
  challenge: Challenge;
  onJoined: (participation: ChallengeParticipation) => void;
}) {
  const join = useAsyncAction(challenges.join);

  if (!challenge.is_open) {
    return (
      <Card className="p-5">
        <Alert tone="neutral">This challenge is not open for new participants.</Alert>
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <p className="text-[13.5px] leading-relaxed text-muted">
        Joining starts your own {challenge.duration_hours}-hour clock from right now — it does not
        depend on when anyone else joined.
      </p>
      <Button
        block
        className="mt-4"
        loading={join.pending}
        onClick={async () => {
          const result = await join.run(challenge.slug);
          if (result) onJoined(result);
        }}
      >
        Join challenge
      </Button>
      {join.error && (
        <Alert tone="critical" className="mt-3">
          {join.error}
        </Alert>
      )}
    </Card>
  );
}

function SubmissionForm({
  challenge,
  participation,
  onSubmitted,
}: {
  challenge: Challenge;
  participation: ChallengeParticipation;
  onSubmitted: (participation: ChallengeParticipation) => void;
}) {
  const submit = useAsyncAction(challenges.submit);
  const now = useNow();
  const overdue = new Date(participation.deadline).getTime() <= now;
  const [form, setForm] = React.useState({ submission_url: "", repo_url: "", notes: "" });

  if (overdue) {
    return (
      <Card className="p-5">
        <Alert tone="critical">Your window to submit this attempt has closed.</Alert>
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2 text-[13px] font-medium text-accent">
        <Icon name="clock" className="size-4" />
        {countdownLabel(participation.deadline, now)}
      </div>
      <form
        className="space-y-4"
        onSubmit={async (event) => {
          event.preventDefault();
          const result = await submit.run(challenge.slug, form);
          if (result) onSubmitted(result);
        }}
      >
        <Field
          label="Live URL"
          htmlFor="submission-url"
          required
          hint="Where the finished thing is actually deployed and reachable."
          error={submit.fieldErrors.submission_url}
        >
          <Input
            id="submission-url"
            type="url"
            required
            placeholder="https://your-build.vercel.app"
            value={form.submission_url}
            onChange={(event) => setForm({ ...form, submission_url: event.target.value })}
          />
        </Field>
        <Field
          label="Repository"
          htmlFor="repo-url"
          hint="Optional."
          error={submit.fieldErrors.repo_url}
        >
          <Input
            id="repo-url"
            type="url"
            placeholder="https://github.com/you/project"
            value={form.repo_url}
            onChange={(event) => setForm({ ...form, repo_url: event.target.value })}
          />
        </Field>
        <Field label="Notes for the reviewer" htmlFor="notes" hint="Optional.">
          <Textarea
            id="notes"
            value={form.notes}
            onChange={(event) => setForm({ ...form, notes: event.target.value })}
          />
        </Field>
        <Button type="submit" block loading={submit.pending}>
          Submit attempt
        </Button>
        {submit.error && <Alert tone="critical">{submit.error}</Alert>}
      </form>
    </Card>
  );
}

function ResultCard({ participation }: { participation: ChallengeParticipation }) {
  const graded = participation.status === "graded";
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-semibold text-fg">Your result</h3>
        {participation.final_score !== null && (
          <span className="text-2xl font-semibold text-fg">
            {participation.final_score}
            <span className="text-[13px] font-normal text-muted">/100</span>
          </span>
        )}
      </div>

      {!graded ? (
        <p className="mt-2 text-[13px] text-muted">
          {participation.status === "submitted"
            ? "Submitted — waiting on grading."
            : "This attempt expired without a submission."}
        </p>
      ) : (
        <div className="mt-3 space-y-3">
          {participation.automated_status === "complete" &&
            Object.keys(participation.automated_report).length > 0 && (
              <div>
                <p className="text-[12px] font-medium text-subtle">Automated (Lighthouse)</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {Object.entries(participation.automated_report).map(([key, value]) => (
                    <Badge key={key} tone="neutral">
                      {key.replace("-", " ")}: {value}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          {participation.human_score !== null && (
            <div>
              <p className="text-[12px] font-medium text-subtle">Reviewer notes</p>
              <p className="mt-1 text-[13px] leading-relaxed text-fg">
                {participation.human_notes || "No notes left."}
              </p>
            </div>
          )}
          <p className="text-[11.5px] text-subtle">
            Your rank badge appears on your profile once this challenge closes and every attempt
            is graded.
          </p>
        </div>
      )}

      <a
        href={participation.submission_url}
        target="_blank"
        rel="noreferrer"
        className="mt-4 inline-flex items-center gap-1 text-[12.5px] text-accent hover:underline"
      >
        View your submission <Icon name="arrowRight" className="size-3" />
      </a>
    </Card>
  );
}

export default function ChallengeDetailPage() {
  const params = useParams<{ slug: string }>();
  const detail = useLoader(() => challenges.detail(params.slug), [params.slug]);
  const mine = useLoader(() => challenges.mine(), []);
  const [justJoinedOrSubmitted, setJustJoinedOrSubmitted] =
    React.useState<ChallengeParticipation | null>(null);

  const participation =
    justJoinedOrSubmitted ?? mine.data?.find((p) => p.challenge_slug === params.slug) ?? null;

  if (detail.loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (detail.error || !detail.data) {
    return <Alert tone="critical">{detail.error ?? "Challenge not found."}</Alert>;
  }

  const challenge = detail.data;

  return (
    <>
      <PageHeading
        title={challenge.title}
        description={`${challenge.duration_hours}-hour challenge${challenge.skill_name ? ` · ${challenge.skill_name}` : ""} · ${challenge.participant_count} joined`}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card className="p-5">
          <h2 className="text-[13px] font-semibold text-subtle">Brief</h2>
          <p className="mt-2 whitespace-pre-wrap text-[13.5px] leading-relaxed text-fg">
            {challenge.brief}
          </p>
          {challenge.reference_file_url && (
            <a
              href={challenge.reference_file_url}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 text-[13px] text-accent hover:underline"
            >
              <Icon name="file" className="size-3.5" />
              Reference material
            </a>
          )}
        </Card>

        <div>
          {!participation ? (
            <JoinPanel
              challenge={challenge}
              onJoined={(p) => {
                setJustJoinedOrSubmitted(p);
                void detail.reload();
              }}
            />
          ) : participation.status === "in_progress" ? (
            <SubmissionForm
              challenge={challenge}
              participation={participation}
              onSubmitted={setJustJoinedOrSubmitted}
            />
          ) : (
            <ResultCard participation={participation} />
          )}
        </div>
      </div>
    </>
  );
}
