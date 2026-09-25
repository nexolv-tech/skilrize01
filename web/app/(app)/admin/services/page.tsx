"use client";

import * as React from "react";
import Link from "next/link";

import {
  ActionWithInput,
  AdminHeading,
  AdminList,
  FilterBar,
  PersonLink,
  QuickAction,
} from "@/components/admin";
import { Badge } from "@/components/ui";
import { admin, type AdminGig } from "@/lib/api";
import { formatRelative, useLoader } from "@/lib/session";

type Filter = "" | "active" | "draft" | "paused" | "denied";

const CHIPS: Array<{ value: Filter; label: string }> = [
  { value: "", label: "All" },
  { value: "active", label: "Live" },
  { value: "draft", label: "Drafts" },
  { value: "paused", label: "Paused" },
  { value: "denied", label: "Removed" },
];

const STATUS: Record<AdminGig["status"], { label: string; tone: "positive" | "neutral" | "caution" | "critical" }> = {
  active: { label: "Live", tone: "positive" },
  draft: { label: "Draft", tone: "neutral" },
  paused: { label: "Paused", tone: "caution" },
  denied: { label: "Removed", tone: "critical" },
};

function ServiceRow({ row, onChanged }: { row: AdminGig; onChanged: () => void }) {
  const status = STATUS[row.status];
  return (
    <div className="flex flex-wrap gap-4 p-5">
      <div className="h-[60px] w-24 shrink-0 overflow-hidden rounded-md border border-line bg-sunken">
        {row.cover_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={row.cover_url} alt="" className="size-full object-cover" />
        )}
      </div>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/gigs/${row.id}`}
            className="text-[14px] font-medium text-fg underline-offset-4 hover:underline"
          >
            {row.title}
          </Link>
          <Badge tone={status.tone}>{status.label}</Badge>
          {row.visibility !== "global" && <Badge tone="accent">Campus</Badge>}
        </div>
        <p className="text-[13px]">
          <PersonLink person={row.seller} label="By" />
        </p>
        <p className="text-[12.5px] text-muted">
          {row.category ?? "No category"} · {row.orders} {row.orders === 1 ? "order" : "orders"} ·
          created {formatRelative(row.created_at)}
        </p>
        <div className="flex flex-wrap items-start gap-2 pt-1">
          {row.status === "denied" ? (
            <QuickAction
              label="Restore"
              onRun={async () => {
                await admin.restoreGig(row.id);
                onChanged();
              }}
            />
          ) : (
            <ActionWithInput
              label="Remove"
              confirmLabel="Remove service"
              tone="danger"
              prompt="Why? The seller is told, and existing orders carry on."
              placeholder="e.g. The pictures are stock photos, not the seller's own work."
              onConfirm={async (reason) => {
                await admin.removeGig(row.id, reason);
                onChanged();
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default function AdminServicesPage() {
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState<Filter>("");
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.gigs({ q: query || undefined, status: filter || undefined, page }),
    [query, filter, page],
  );

  return (
    <>
      <AdminHeading
        title="Services"
        description="Every service on SkilRize, drafts and campus ones included. Remove one that breaks the rules; the seller is told why."
      />
      <FilterBar
        query={query}
        onQuery={(next) => {
          setQuery(next);
          setPage(1);
        }}
        placeholder="Search by title or seller"
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
        empty={{ icon: "search", title: "No services match" }}
      >
        {(row: AdminGig) => <ServiceRow key={row.id} row={row} onChanged={() => void list.reload()} />}
      </AdminList>
    </>
  );
}
