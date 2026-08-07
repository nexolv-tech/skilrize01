"use client";

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Money,
  Progress,
  Skeleton,
  cn,
} from "@/components/ui";
import { marketplace, type Proposal } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

const TONES: Record<Proposal["status"], "neutral" | "accent" | "positive" | "critical"> = {
  submitted: "neutral",
  shortlisted: "accent",
  accepted: "positive",
  declined: "critical",
  withdrawn: "neutral",
};

export default function ProposalsPage() {
  const { user } = useSession();
  const { data, loading, reload } = useLoader(async () => {
    const [list, allowance] = await Promise.all([
      marketplace.myProposals().catch(() => null),
      marketplace.quota().catch(() => null),
    ]);
    return { list, allowance };
  }, [user?.handle]);

  // The endpoint returns both sides of the relationship; this page is the
  // freelancer's view, so keep only proposals this user wrote.
  const proposals: Proposal[] | null = loading
    ? null
    : (data?.list?.results.filter((row) => row.freelancer.handle === user?.handle) ?? []);
  const quota = data?.allowance ?? null;
  const load = reload;

  const withdraw = useAsyncAction(async (id: number) => {
    await marketplace.withdrawProposal(id);
    await load();
  });

  return (
    <>
      <PageHeading
        title="My proposals"
        description="Every brief you have applied to, and where each one stands."
      />

      {quota && (
        <Card className="mb-6 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-56 flex-1">
              <Progress
                value={(quota.outstanding / quota.limit) * 100}
                label={`${quota.outstanding} of ${quota.limit} proposal slots in use`}
              />
            </div>
            <p className="max-w-sm text-[12.5px] leading-relaxed text-muted">
              A slot frees up as soon as a proposal is withdrawn, declined, or accepted — the limit
              is on outstanding bids, not lifetime.
            </p>
          </div>
        </Card>
      )}

      {proposals === null ? (
        <div className="space-y-4">
          {[0, 1, 2].map((row) => (
            <Card key={row} className="space-y-3 p-5">
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-3 w-1/4" />
            </Card>
          ))}
        </div>
      ) : proposals.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="send" className="size-5" />}
            title="No proposals yet"
            description="Find a brief that fits and make your case. Specific beats generic every time."
            action={
              <Link href="/projects">
                <Button>Browse open work</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <ul className="space-y-4">
          {proposals.map((proposal) => (
            <li key={proposal.id}>
              <Card className="p-5 transition-shadow duration-200 hover:shadow-e2">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/projects/${proposal.project}`}
                        className="text-[15.5px] font-semibold text-fg underline-offset-2 hover:underline"
                      >
                        {proposal.project_title}
                      </Link>
                      <Badge tone={TONES[proposal.status]}>{proposal.status}</Badge>
                      {proposal.client_viewed_at && proposal.status === "submitted" && (
                        <Badge>Viewed</Badge>
                      )}
                    </div>
                    <p className="mt-1 text-[12.5px] text-subtle">
                      Submitted {formatRelative(proposal.created_at)}
                      {proposal.estimated_days && ` · ${proposal.estimated_days} day estimate`}
                    </p>
                    <p
                      className={cn(
                        "mt-3 line-clamp-2 text-[13.5px] leading-relaxed text-muted",
                      )}
                    >
                      {proposal.cover_letter}
                    </p>
                  </div>

                  <div className="shrink-0 text-right">
                    <p className="text-[16px] font-semibold text-fg">
                      <Money amount={proposal.bid_amount ?? proposal.hourly_rate} />
                      {proposal.hourly_rate && (
                        <span className="text-[12px] font-normal text-muted">/hr</span>
                      )}
                    </p>
                  </div>
                </div>

                {(proposal.status === "submitted" || proposal.status === "shortlisted") && (
                  <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-4">
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={withdraw.pending}
                      onClick={() => void withdraw.run(proposal.id)}
                    >
                      Withdraw
                    </Button>
                    <Link href={`/projects/${proposal.project}`}>
                      <Button size="sm" variant="secondary">
                        View brief
                      </Button>
                    </Link>
                    {withdraw.error && (
                      <span className="text-[12.5px] text-critical">{withdraw.error}</span>
                    )}
                  </div>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
