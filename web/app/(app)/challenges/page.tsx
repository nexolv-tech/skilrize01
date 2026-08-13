"use client";

/**
 * Proof-of-work challenges — browse open briefs, or see your own attempts.
 *
 * Authoring a challenge and reviewing submissions are staff work with no
 * dedicated UI yet (`challenges/admin.py`'s "interim console" — the same
 * status as identity verification's admin tooling). This page is the
 * participant side only.
 */

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import {
  Badge,
  Card,
  EmptyState,
  Icon,
  Segmented,
  Skeleton,
} from "@/components/ui";
import { challenges, type Challenge, type ChallengeParticipation } from "@/lib/api";
import { useLoader } from "@/lib/session";

function timeLeftLabel(closesAt: string): string {
  const ms = new Date(closesAt).getTime() - Date.now();
  if (ms <= 0) return "Closed";
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return "Closing soon";
  if (hours < 48) return `${hours}h left to join`;
  return `${Math.floor(hours / 24)}d left to join`;
}

function ChallengeCard({ challenge }: { challenge: Challenge }) {
  return (
    <Link href={`/challenges/${challenge.slug}`}>
      <Card className="lift flex h-full flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-[15px] font-semibold leading-snug text-fg">{challenge.title}</h3>
          {challenge.skill_name && (
            <Badge tone="accent" className="shrink-0">
              {challenge.skill_name}
            </Badge>
          )}
        </div>
        <p className="mt-2 line-clamp-3 flex-1 text-[13px] leading-relaxed text-muted">
          {challenge.brief}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-subtle">
          <span className="inline-flex items-center gap-1.5">
            <Icon name="clock" className="size-3.5" />
            {challenge.duration_hours}h to submit
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Icon name="users" className="size-3.5" />
            {challenge.participant_count} joined
          </span>
        </div>
        {challenge.status === "published" && (
          <p className="mt-2 text-[11.5px] text-subtle">{timeLeftLabel(challenge.closes_at)}</p>
        )}
        {challenge.my_participation_id && (
          <Badge tone="positive" className="mt-3 self-start">
            <Icon name="check" className="size-3" />
            Joined
          </Badge>
        )}
      </Card>
    </Link>
  );
}

function BrowsePanel() {
  const list = useLoader(() => challenges.list(), []);
  const rows = list.data?.results ?? [];
  const open = rows.filter((c) => c.is_open);
  const past = rows.filter((c) => !c.is_open);

  if (list.loading) {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((key) => (
          <Skeleton key={key} className="h-56" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="zap" className="size-5" />}
          title="No challenges published yet"
          description="Timed briefs will appear here — build the thing, get graded, and a verified result lands on your profile."
        />
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      {open.length > 0 && (
        <section>
          <h2 className="mb-3 text-[13px] font-semibold text-subtle">Open now</h2>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {open.map((challenge) => (
              <ChallengeCard key={challenge.id} challenge={challenge} />
            ))}
          </div>
        </section>
      )}
      {past.length > 0 && (
        <section>
          <h2 className="mb-3 text-[13px] font-semibold text-subtle">Past challenges</h2>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {past.map((challenge) => (
              <ChallengeCard key={challenge.id} challenge={challenge} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const STATUS_TONE: Record<ChallengeParticipation["status"], "neutral" | "accent" | "positive" | "critical"> = {
  in_progress: "accent",
  submitted: "neutral",
  graded: "positive",
  expired: "critical",
};

const STATUS_LABEL: Record<ChallengeParticipation["status"], string> = {
  in_progress: "In progress",
  submitted: "Submitted",
  graded: "Graded",
  expired: "Expired",
};

function MinePanel() {
  const mine = useLoader(() => challenges.mine(), []);
  const rows = mine.data ?? [];

  if (mine.loading) return <Skeleton className="h-48" />;

  if (rows.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="zap" className="size-5" />}
          title="You haven't joined a challenge yet"
          description="Pick one from Browse — the clock starts the moment you join, not when the challenge itself opened."
        />
      </Card>
    );
  }

  return (
    <Card>
      <ul className="divide-y divide-line">
        {rows.map((p) => (
          <li key={p.id}>
            <Link
              href={`/challenges/${p.challenge_slug}`}
              className="flex flex-wrap items-center gap-3 px-5 py-4 hover:bg-sunken"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-medium text-fg">{p.challenge_title}</p>
                <p className="mt-0.5 text-[12px] text-muted">
                  {p.status === "in_progress" && !p.is_overdue
                    ? `Due ${new Date(p.deadline).toLocaleString()}`
                    : p.status === "graded"
                      ? `Final score: ${p.final_score}/100`
                      : p.status === "submitted"
                        ? `Submitted ${new Date(p.submitted_at ?? p.started_at).toLocaleDateString()}`
                        : "Deadline passed"}
                </p>
              </div>
              <Badge tone={p.is_overdue && p.status === "in_progress" ? "critical" : STATUS_TONE[p.status]}>
                {p.is_overdue && p.status === "in_progress" ? "Overdue" : STATUS_LABEL[p.status]}
              </Badge>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

type Tab = "browse" | "mine";

export default function ChallengesPage() {
  const [tab, setTab] = React.useState<Tab>("browse");

  return (
    <>
      <PageHeading
        title="Challenges"
        description="Timed briefs, graded on real submissions — a verified result on your profile instead of just a claim in your bio."
      />

      <div className="pb-6">
        <Segmented
          label="Challenges section"
          value={tab}
          onChange={setTab}
          options={[
            { value: "browse", label: "Browse", icon: "search" },
            { value: "mine", label: "Yours", icon: "zap" },
          ]}
        />
      </div>

      {tab === "browse" ? <BrowsePanel /> : <MinePanel />}
    </>
  );
}
