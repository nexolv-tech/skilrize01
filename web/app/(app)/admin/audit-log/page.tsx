"use client";

import * as React from "react";

import { PageHeading } from "@/components/shell";
import { Alert, Badge, Card, EmptyState, Field, Icon, Input, Select, Skeleton } from "@/components/ui";
import { admin } from "@/lib/api";
import { useLoader } from "@/lib/session";

const ACTIONS = [
  "",
  "create",
  "update",
  "delete",
  "read_sensitive",
  "login",
  "login_failed",
  "logout",
  "password_reset",
  "two_factor_enabled",
  "two_factor_disabled",
  "impersonate",
  "scope_denied",
];

const ACTION_TONE: Record<string, "neutral" | "accent" | "positive" | "critical" | "caution"> = {
  delete: "critical",
  login_failed: "critical",
  scope_denied: "critical",
  read_sensitive: "caution",
  impersonate: "caution",
  create: "positive",
};

export default function AdminAuditLogPage() {
  const [action, setAction] = React.useState("");
  const [actor, setActor] = React.useState("");
  const [targetType, setTargetType] = React.useState("");

  const log = useLoader(
    () =>
      admin.auditLog({
        action: action || undefined,
        actor: actor || undefined,
        target_type: targetType || undefined,
      }),
    [action, actor, targetType],
  );
  const rows = log.data?.results ?? [];

  return (
    <>
      <PageHeading
        title="Audit log"
        description="Every administrative action, append-only — nothing here can be edited or deleted, including by a Super Admin."
      />

      <Card className="mb-6 grid gap-4 p-5 sm:grid-cols-3">
        <Field label="Action" htmlFor="audit-action">
          <Select
            id="audit-action"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          >
            {ACTIONS.map((value) => (
              <option key={value} value={value}>
                {value ? value.replaceAll("_", " ") : "All actions"}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Actor email contains" htmlFor="audit-actor">
          <Input
            id="audit-actor"
            value={actor}
            onChange={(event) => setActor(event.target.value)}
            placeholder="name@example.com"
          />
        </Field>
        <Field label="Target type" htmlFor="audit-target">
          <Input
            id="audit-target"
            value={targetType}
            onChange={(event) => setTargetType(event.target.value)}
            placeholder="Contract, User, Milestone…"
          />
        </Field>
      </Card>

      {log.loading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((row) => (
            <Skeleton key={row} className="h-14" />
          ))}
        </div>
      ) : log.error ? (
        <Alert tone="critical">{log.error}</Alert>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="shield" className="size-5" />}
            title="No matching entries"
            description="Nothing recorded for this filter yet."
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {rows.map((entry) => (
              <li key={entry.id} className="flex flex-wrap items-start gap-3 p-4">
                <Badge tone={ACTION_TONE[entry.action] ?? "neutral"}>
                  {entry.action.replaceAll("_", " ")}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] text-fg">
                    <span className="font-medium">{entry.actor_name ?? "System"}</span>
                    {entry.actor_email && (
                      <span className="text-muted"> · {entry.actor_email}</span>
                    )}
                    {entry.target_type && (
                      <span className="text-muted">
                        {" "}
                        → {entry.target_type} #{entry.target_id}
                      </span>
                    )}
                  </p>
                  {entry.justification && (
                    <p className="mt-0.5 text-[12.5px] text-muted">{entry.justification}</p>
                  )}
                </div>
                <div className="shrink-0 text-right text-[11.5px] text-subtle">
                  <p>{new Date(entry.created_at).toLocaleString()}</p>
                  {entry.ip_address && <p>{entry.ip_address}</p>}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
