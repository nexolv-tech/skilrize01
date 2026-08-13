"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Skeleton,
  Textarea,
} from "@/components/ui";
import { admin, type AdminUserRow } from "@/lib/api";
import { useAsyncAction, useLoader } from "@/lib/session";

function UserRow({ row, onChanged }: { row: AdminUserRow; onChanged: () => void }) {
  const [suspending, setSuspending] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const suspend = useAsyncAction(admin.suspendUser);
  const reactivate = useAsyncAction(admin.reactivateUser);
  const isAdminAccount = Boolean(row.admin_role) || row.is_staff;

  return (
    <li className="p-5">
      <div className="flex flex-wrap items-start gap-3">
        <Avatar name={row.display_name} src={row.avatar_url} size={36} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[14px] font-medium text-fg">{row.display_name}</p>
            <Badge tone={row.is_active ? "positive" : "critical"}>
              {row.is_active ? "Active" : "Suspended"}
            </Badge>
            {isAdminAccount && <Badge tone="accent">{row.admin_role || "staff"}</Badge>}
          </div>
          <p className="text-[12.5px] text-muted">
            {row.handle} · {row.email}
          </p>
          {row.university_name && (
            <p className="mt-1 text-[12px] text-subtle">{row.university_name}</p>
          )}
        </div>
      </div>

      <div className="mt-4 border-t border-line pt-4">
        {isAdminAccount ? (
          <p className="text-[12px] text-subtle">
            Admin accounts cannot be suspended from here — that needs a Super Admin acting
            deliberately.
          </p>
        ) : row.is_active ? (
          suspending ? (
            <div className="space-y-3">
              <Textarea
                placeholder="Why is this account being suspended?"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  loading={suspend.pending}
                  disabled={!reason.trim()}
                  onClick={async () => {
                    if (await suspend.run(row.id, reason)) {
                      setSuspending(false);
                      onChanged();
                    }
                  }}
                >
                  Confirm suspension
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setSuspending(false)}>
                  Cancel
                </Button>
              </div>
              {suspend.error && <p className="text-[12.5px] text-critical">{suspend.error}</p>}
            </div>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setSuspending(true)}>
              Suspend account
            </Button>
          )
        ) : (
          <>
            <Button
              size="sm"
              loading={reactivate.pending}
              onClick={async () => {
                if (await reactivate.run(row.id)) onChanged();
              }}
            >
              Reactivate account
            </Button>
            {reactivate.error && (
              <p className="mt-2 text-[12.5px] text-critical">{reactivate.error}</p>
            )}
          </>
        )}
      </div>
    </li>
  );
}

export default function AdminUsersPage() {
  const [query, setQuery] = React.useState("");
  const [committedQuery, setCommittedQuery] = React.useState("");
  const results = useLoader(() => admin.users(committedQuery || undefined), [committedQuery]);
  const rows = results.data?.results ?? [];

  return (
    <>
      <PageHeading
        title="Users"
        description="Search accounts by email, handle, or name. Suspending is reversible; nothing here deletes anything."
      />

      <form
        className="mb-6 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setCommittedQuery(query.trim());
        }}
      >
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by email, handle, or name…"
          className="max-w-sm"
        />
        <Button type="submit" variant="secondary">
          <Icon name="search" className="size-3.5" />
          Search
        </Button>
      </form>

      {results.loading ? (
        <div className="space-y-4">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-28" />
          ))}
        </div>
      ) : results.error ? (
        <Alert tone="critical">{results.error}</Alert>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="users" className="size-5" />}
            title={committedQuery ? "No matches" : "Search for an account"}
            description={
              committedQuery
                ? "Nothing matched that search."
                : "Recent accounts appear here, or search by email, handle, or name."
            }
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {rows.map((row) => (
              <UserRow key={row.id} row={row} onChanged={() => void results.reload()} />
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
