"use client";

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import {
  Badge,
  Card,
  EmptyState,
  Icon,
  Money,
  Segmented,
  Skeleton,
  ButtonLink,
} from "@/components/ui";
import { contracts, type ContractStatus, type ContractSummary } from "@/lib/api";
import { formatRelative, useLoader } from "@/lib/session";

const TONES: Record<ContractStatus, "neutral" | "accent" | "positive" | "caution" | "critical"> = {
  pending: "caution",
  active: "accent",
  paused: "neutral",
  delivered: "caution",
  completed: "positive",
  cancelled: "neutral",
  disputed: "critical",
};

type Filter = "all" | "client" | "freelancer";

export default function ContractsPage() {
  const [role, setRole] = React.useState<Filter>("all");
  const { data, loading } = useLoader(
    () => contracts.list(role === "all" ? {} : { role }),
    [role],
  );
  const rows: ContractSummary[] | null = loading ? null : (data?.results ?? []);

  return (
    <>
      <PageHeading
        title="Contracts"
        description="Work you are doing and work you are paying for, in one place."
        action={
          <Segmented
            label="Filter contracts"
            value={role}
            onChange={setRole}
            size="sm"
            options={[
              { value: "all", label: "All" },
              { value: "client", label: "I'm hiring" },
              { value: "freelancer", label: "I'm working" },
            ]}
          />
        }
      />

      {rows === null ? (
        <div className="space-y-4">
          {[0, 1].map((row) => (
            <Card key={row} className="space-y-3 p-5">
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-3 w-1/3" />
            </Card>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="briefcase" className="size-5" />}
            title="No contracts yet"
            description="A contract opens when a client awards a proposal. Until then, keep applying."
            action={
              <ButtonLink href="/projects">Browse open work</ButtonLink>
            }
          />
        </Card>
      ) : (
        <ul className="space-y-4">
          {rows.map((contract) => {
            const total = contract.total_amount ?? contract.hourly_rate;
            return (
              <li key={contract.id}>
                <Card className="relative p-5 transition-shadow duration-200 hover:shadow-e2">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-[15.5px] font-semibold text-fg">
                          <Link
                            href={`/contracts/${contract.id}`}
                            className="rounded-sm after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                          >
                            {contract.title}
                          </Link>
                        </h3>
                        <Badge tone={TONES[contract.status]}>{contract.status}</Badge>
                        <Badge>
                          {contract.my_role === "client" ? "You are hiring" : "You are working"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[12.5px] text-subtle">
                        {contract.my_role === "client"
                          ? `Freelancer: ${contract.freelancer_name}`
                          : `Client: ${contract.client_name}`}
                        {" · "}
                        {contract.contract_type === "hourly"
                          ? "Hourly"
                          : contract.contract_type === "milestone"
                            ? "Milestones"
                            : "Fixed price"}
                        {" · "}
                        Opened {formatRelative(contract.created_at)}
                      </p>
                    </div>

                    <div className="shrink-0 text-right">
                      <p className="text-[16px] font-semibold text-fg">
                        <Money amount={total} />
                        {contract.hourly_rate && (
                          <span className="text-[12px] font-normal text-muted">/hr</span>
                        )}
                      </p>
                      <p className="text-[12px] text-subtle">
                        <Money amount={contract.released_amount} /> released
                      </p>
                    </div>
                  </div>

                  {Number(contract.funded_amount) > 0 && (
                    <p className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-positive-soft px-2.5 py-1 text-[12px] text-positive">
                      <Icon name="lock" className="size-3" />
                      <Money amount={contract.funded_amount} /> held in escrow
                    </p>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
