"use client";

import * as React from "react";
import Link from "next/link";

import {
  ActionWithInput,
  AdminHeading,
  AdminList,
  FilterBar,
  PersonLink,
} from "@/components/admin";
import { Badge, Money } from "@/components/ui";
import { admin, type AdminProject } from "@/lib/api";
import { formatRelative, useLoader } from "@/lib/session";

type Filter = "" | "open" | "draft" | "paused" | "awarded" | "closed";

const CHIPS: Array<{ value: Filter; label: string }> = [
  { value: "", label: "All" },
  { value: "open", label: "Open" },
  { value: "draft", label: "Drafts" },
  { value: "paused", label: "Paused" },
  { value: "awarded", label: "Hired" },
  { value: "closed", label: "Closed" },
];

const STATUS: Record<AdminProject["status"], { label: string; tone: "positive" | "neutral" | "caution" | "accent" }> = {
  open: { label: "Open", tone: "positive" },
  draft: { label: "Draft", tone: "neutral" },
  paused: { label: "Paused", tone: "caution" },
  awarded: { label: "Hired", tone: "accent" },
  closed: { label: "Closed", tone: "neutral" },
};

function BriefRow({ row, onChanged }: { row: AdminProject; onChanged: () => void }) {
  const status = STATUS[row.status];
  const closable = row.status === "open" || row.status === "draft" || row.status === "paused";
  return (
    <div className="space-y-1.5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/projects/${row.id}`}
            className="text-[14px] font-medium text-fg underline-offset-4 hover:underline"
          >
            {row.title}
          </Link>
          <Badge tone={status.tone}>{status.label}</Badge>
          {row.visibility !== "global" && <Badge tone="accent">Campus</Badge>}
        </div>
        {row.budget_max && (
          <span className="text-[14px] font-semibold text-fg">
            <Money amount={row.budget_max} />
            {row.project_type === "hourly" && <span className="font-normal text-muted">/hr</span>}
          </span>
        )}
      </div>
      <p className="text-[13px]">
        <PersonLink person={row.client} label="By" />
      </p>
      <p className="text-[12.5px] text-muted">
        {row.category ?? "No category"} · {row.proposals}{" "}
        {row.proposals === 1 ? "proposal" : "proposals"} · posted {formatRelative(row.created_at)}
      </p>
      {closable && (
        <div className="pt-1">
          <ActionWithInput
            label="Close brief"
            confirmLabel="Close brief"
            tone="danger"
            prompt="Why? The client is told, and the brief stops taking proposals."
            placeholder="e.g. Asks for work that breaks the Terms."
            onConfirm={async (reason) => {
              await admin.closeProject(row.id, reason);
              onChanged();
            }}
          />
        </div>
      )}
    </div>
  );
}

export default function AdminBriefsPage() {
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState<Filter>("");
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.projects({ q: query || undefined, status: filter || undefined, page }),
    [query, filter, page],
  );

  return (
    <>
      <AdminHeading
        title="Briefs"
        description="Every brief clients have posted. Close one that asks for something against the rules; the client is told why."
      />
      <FilterBar
        query={query}
        onQuery={(next) => {
          setQuery(next);
          setPage(1);
        }}
        placeholder="Search by title or client"
        chips={CHIPS}
        value={filter}
        onChip={(next) => {
          setFilter(next);
          setPage(1);
        }}
      />
      <AdminList
        data={list.data}
        loading={list.loading}
        page={page}
        onPage={setPage}
        empty={{ icon: "search", title: "No briefs match" }}
      >
        {(row: AdminProject) => <BriefRow key={row.id} row={row} onChanged={() => void list.reload()} />}
      </AdminList>
    </>
  );
}
