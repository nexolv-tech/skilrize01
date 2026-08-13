"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Money,
  Select,
  Skeleton,
  Textarea,
} from "@/components/ui";
import { admin, type AdminContractDetail, type AdminContractRow } from "@/lib/api";
import { useAsyncAction, useLoader } from "@/lib/session";

const STATUS_TONE: Record<string, "neutral" | "accent" | "positive" | "critical" | "caution"> = {
  pending: "neutral",
  active: "accent",
  paused: "caution",
  delivered: "caution",
  completed: "positive",
  cancelled: "neutral",
  disputed: "critical",
};

function MilestonePanel({ contractId, detail }: { contractId: number; detail: AdminContractDetail }) {
  const [fundingId, setFundingId] = React.useState<number | null>(null);
  const [reason, setReason] = React.useState("");
  const fund = useAsyncAction(admin.fundMilestone);

  return (
    <div className="border-t border-line bg-sunken/40 p-5">
      <p className="mb-3 text-[12px] font-medium text-subtle">Milestones</p>
      <ul className="space-y-3">
        {detail.milestones.map((milestone) => (
          <li key={milestone.id} className="rounded-md border border-line bg-surface p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[13px] font-medium text-fg">{milestone.title}</p>
                <p className="text-[12px] text-muted">{milestone.description}</p>
              </div>
              <div className="flex items-center gap-2">
                <Money amount={milestone.amount} className="text-[13px] text-fg" />
                <Badge tone={STATUS_TONE[milestone.status] ?? "neutral"}>{milestone.status}</Badge>
              </div>
            </div>

            {milestone.status === "pending" && detail.status === "active" && (
              <div className="mt-3">
                {fundingId === milestone.id ? (
                  <div className="space-y-2">
                    <Textarea
                      placeholder="Why is this being funded manually? e.g. bank transfer confirmed."
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        loading={fund.pending}
                        onClick={async () => {
                          if (await fund.run(contractId, milestone.id, reason)) {
                            setFundingId(null);
                            setReason("");
                          }
                        }}
                      >
                        Confirm funding
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setFundingId(null)}>
                        Cancel
                      </Button>
                    </div>
                    {fund.error && <p className="text-[12px] text-critical">{fund.error}</p>}
                  </div>
                ) : (
                  <Button size="sm" variant="secondary" onClick={() => setFundingId(milestone.id)}>
                    Force fund
                  </Button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ContractRow({ row }: { row: AdminContractRow }) {
  const [expanded, setExpanded] = React.useState(false);
  const detail = useLoader(
    () => (expanded ? admin.contract(row.id) : Promise.resolve(null)),
    [expanded, row.id],
  );

  return (
    <li>
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full flex-wrap items-center gap-3 p-5 text-left hover:bg-sunken"
      >
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-medium text-fg">{row.title}</p>
          <p className="text-[12.5px] text-muted">
            {row.client_name} → {row.freelancer_name}
          </p>
        </div>
        <div className="text-right">
          <Money amount={row.total_amount ?? row.hourly_rate} className="text-[14px] text-fg" />
          <p className="text-[11.5px] text-subtle">
            <Money amount={row.funded_amount} /> funded
          </p>
        </div>
        <Badge tone={STATUS_TONE[row.status] ?? "neutral"}>{row.status}</Badge>
        <Icon name="chevronDown" className={`size-4 text-subtle ${expanded ? "rotate-180" : ""}`} />
      </button>
      {expanded && (
        <>
          {detail.loading ? (
            <div className="border-t border-line p-5">
              <Skeleton className="h-20" />
            </div>
          ) : detail.data ? (
            <MilestonePanel contractId={row.id} detail={detail.data} />
          ) : null}
        </>
      )}
    </li>
  );
}

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "active", label: "Active" },
  { value: "delivered", label: "Delivered" },
  { value: "completed", label: "Completed" },
  { value: "disputed", label: "Disputed" },
  { value: "cancelled", label: "Cancelled" },
];

export default function AdminContractsPage() {
  const [status, setStatus] = React.useState("");
  const list = useLoader(() => admin.contracts(status || undefined), [status]);
  const rows = list.data?.results ?? [];

  return (
    <>
      <PageHeading
        title="Contracts"
        description="Every contract on the platform. Force-funding a milestone stands in for a payment gateway until Phase 3 — it does not resolve disputes or release money without the client's own approval."
      />

      <div className="mb-6 max-w-56">
        <Select value={status} onChange={(event) => setStatus(event.target.value)}>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      {list.loading ? (
        <div className="space-y-4">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-20" />
          ))}
        </div>
      ) : list.error ? (
        <Alert tone="critical">{list.error}</Alert>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="briefcase" className="size-5" />}
            title="No contracts"
            description="Nothing matches this filter."
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {rows.map((row) => (
              <ContractRow key={row.id} row={row} />
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
