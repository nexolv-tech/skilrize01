"use client";

import * as React from "react";
import Link from "next/link";

import {
  ActionWithInput,
  AdminHeading,
  AdminList,
  PersonLink,
  StateSwitch,
  StatusText,
} from "@/components/admin";
import { Badge } from "@/components/ui";
import { admin, type AdminReport } from "@/lib/api";
import { formatRelative, useLoader } from "@/lib/session";

type State = "open" | "upheld" | "dismissed";

const KIND: Record<AdminReport["kind"], string> = {
  thread: "Discussion",
  reply: "Reply",
  chat: "Chat message",
  resource: "Resource",
  community: "Community",
};

function ReportRow({ row, onChanged }: { row: AdminReport; onChanged: () => void }) {
  return (
    <div className="space-y-3 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{KIND[row.kind]}</Badge>
        {row.community && <span className="text-[13px] text-muted">in {row.community}</span>}
        <span className="text-[12.5px] text-subtle">reported {formatRelative(row.created_at)}</span>
      </div>
      <p className="text-[13.5px] text-fg">
        <span className="text-muted">Reason:</span> {row.reason}
      </p>
      <p className="text-[13px]">
        <PersonLink person={row.reporter} label="Reported by" />
      </p>
      <div className="rounded-lg border border-line bg-sunken/60 p-4">
        {row.content_exists ? (
          <>
            <p className="whitespace-pre-line text-[13px] leading-relaxed text-fg">{row.content.text}</p>
            <p className="mt-2 flex flex-wrap gap-x-4 text-[12.5px]">
              {row.content.author && <PersonLink person={row.content.author} label="Posted by" />}
              {row.content.url && (
                <Link href={row.content.url} className="text-accent underline-offset-4 hover:underline">
                  Open where it was posted
                </Link>
              )}
            </p>
          </>
        ) : (
          <p className="text-[13px] text-subtle">The reported content no longer exists.</p>
        )}
      </div>
      {row.status === "open" ? (
        <div className="flex flex-wrap items-start gap-2">
          {row.kind !== "community" && row.content_exists && (
            <ActionWithInput
              label="Remove content"
              confirmLabel="Remove"
              tone="danger"
              required={false}
              prompt="The content is taken down, its author is told, and every open report on it is closed. Add a note (optional)."
              onConfirm={async (note) => {
                await admin.resolveReport(row.id, "remove", note);
                onChanged();
              }}
            />
          )}
          <ActionWithInput
            label="Dismiss"
            confirmLabel="Dismiss report"
            required={false}
            prompt="The content stays up. Add a note for the record (optional)."
            onConfirm={async (note) => {
              await admin.resolveReport(row.id, "dismiss", note);
              onChanged();
            }}
          />
        </div>
      ) : (
        <StatusText tone={row.status === "upheld" ? "critical" : "muted"}>
          {row.status === "upheld" ? "Content removed" : "Dismissed"}
          {row.resolved_at && ` ${formatRelative(row.resolved_at)}`}
          {row.resolution_note && `: ${row.resolution_note}`}
        </StatusText>
      )}
    </div>
  );
}

export default function AdminReportsPage() {
  const [state, setState] = React.useState<State>("open");
  const [page, setPage] = React.useState(1);
  const list = useLoader(() => admin.reports(state, page), [state, page]);

  return (
    <>
      <AdminHeading
        title="Reports"
        description="Community content members have flagged, oldest first. Community moderators see their own; this is every community."
        action={
          <StateSwitch
            value={state}
            onChange={(next) => {
              setState(next);
              setPage(1);
            }}
            options={[
              { value: "open", label: "Open" },
              { value: "upheld", label: "Removed" },
              { value: "dismissed", label: "Dismissed" },
            ]}
          />
        }
      />
      <AdminList
        data={list.data}
        loading={list.loading}
        page={page}
        onPage={setPage}
        empty={{
          title: state === "open" ? "No open reports" : "Nothing here yet",
          description: state === "open" ? "Members' reports land here as they come in." : undefined,
        }}
      >
        {(row: AdminReport) => <ReportRow key={row.id} row={row} onChanged={() => void list.reload()} />}
      </AdminList>
    </>
  );
}
