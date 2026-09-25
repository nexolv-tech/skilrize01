"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  ActionWithInput,
  AdminHeading,
  AdminList,
  FilterBar,
  QuickAction,
} from "@/components/admin";
import { Avatar, Badge, Button, Money, Select, Skeleton } from "@/components/ui";
import { admin, type AdminRole, type AdminUserRow, type AdminUserSummary } from "@/lib/api";
import { formatRelative, useLoader, useSession } from "@/lib/session";

type Filter = "" | "active" | "suspended" | "admins" | "identity_pending";

const CHIPS: Array<{ value: Filter; label: string }> = [
  { value: "", label: "Everyone" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "identity_pending", label: "ID waiting" },
  { value: "admins", label: "Admins" },
];

const ROLES: Array<{ value: AdminRole; label: string }> = [
  { value: "", label: "Not an admin" },
  { value: "super_admin", label: "Super Admin (everything)" },
  { value: "finance_admin", label: "Finance Admin (payments, orders)" },
  { value: "verification_officer", label: "Verification Officer (ID checks)" },
  { value: "moderator", label: "Moderator (services, briefs, reports)" },
  { value: "support_agent", label: "Support Agent (users, orders)" },
  { value: "dispute_officer", label: "Dispute Officer (orders)" },
];

const IDENTITY: Record<string, { label: string; tone: "positive" | "caution" | "critical" | "neutral" }> = {
  verified: { label: "ID verified", tone: "positive" },
  pending: { label: "ID waiting", tone: "caution" },
  rejected: { label: "ID rejected", tone: "critical" },
  unverified: { label: "No ID yet", tone: "neutral" },
};

function Summary({ id }: { id: number }) {
  const { data } = useLoader<AdminUserSummary>(() => admin.userSummary(id), [id]);
  if (!data) return <Skeleton className="h-20 w-full" />;
  const services = Object.entries(data.services)
    .map(([status, n]) => `${n} ${status === "active" ? "live" : status === "denied" ? "removed" : status}`)
    .join(", ");
  const facts: Array<[string, React.ReactNode]> = [
    ["Services", services || "None"],
    ["Briefs posted", data.briefs],
    ["Orders", `${data.orders_bought} bought · ${data.orders_sold} sold`],
    ["Contracts", data.contracts],
    ["Owed to them", <Money key="p" amount={data.payouts_pending} />],
    ["Refunds owed", <Money key="r" amount={data.refunds_pending} />],
    ["Plan", data.plan ?? "Free"],
    ["Two-factor", data.two_factor ? "On" : "Off"],
    ["Signed in on", `${data.active_sessions} ${data.active_sessions === 1 ? "session" : "sessions"} · ${data.devices} known ${data.devices === 1 ? "device" : "devices"}`],
    ["Last active", data.last_active_at ? formatRelative(data.last_active_at) : "Never"],
  ];
  return (
    <dl className="grid gap-x-6 gap-y-2 rounded-lg border border-line bg-sunken/60 p-4 text-[13px] sm:grid-cols-2">
      {facts.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3">
          <dt className="text-muted">{label}</dt>
          <dd className="text-right text-fg">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RoleControl({ row, onChanged }: { row: AdminUserRow; onChanged: () => void }) {
  const [role, setRole] = React.useState<AdminRole>(row.admin_role);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor={`role-${row.id}`}>
        Admin role
      </label>
      <Select
        id={`role-${row.id}`}
        value={role}
        onChange={(event) => setRole(event.target.value as AdminRole)}
        className="w-auto! text-[13px]"
      >
        {ROLES.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
      <Button
        size="sm"
        variant="secondary"
        disabled={role === row.admin_role}
        loading={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          try {
            await admin.setUserRole(row.id, role);
            onChanged();
          } catch (caught) {
            setError((caught as { message?: string }).message ?? "Could not change the role.");
          } finally {
            setPending(false);
          }
        }}
      >
        Change role
      </Button>
      {error && <span className="text-[12px] text-critical">{error}</span>}
    </div>
  );
}

function UserRow({
  row,
  isSuperAdmin,
  isSelf,
  onChanged,
}: {
  row: AdminUserRow;
  isSuperAdmin: boolean;
  isSelf: boolean;
  onChanged: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const isAdminAccount = Boolean(row.admin_role) || row.is_staff;
  const identity = IDENTITY[row.identity_status] ?? IDENTITY.unverified!;

  return (
    <div className="space-y-3 p-5">
      <div className="flex flex-wrap items-start gap-3">
        <Avatar name={row.display_name} src={row.avatar_url} size={36} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[14px] font-medium text-fg">{row.display_name}</p>
            {row.is_erased ? (
              <Badge tone="neutral">Deleted</Badge>
            ) : (
              <>
                <Badge tone={row.is_active ? "positive" : "critical"}>
                  {row.is_active ? "Active" : "Suspended"}
                </Badge>
                <Badge tone={identity.tone}>{identity.label}</Badge>
              </>
            )}
            {row.is_verified_student && <Badge tone="accent">Student</Badge>}
            {isAdminAccount && (
              <Badge tone="accent">
                {ROLES.find((r) => r.value === row.admin_role)?.label.split(" (")[0] ?? "Staff"}
              </Badge>
            )}
          </div>
          <p className="text-[12.5px] text-muted">
            @{row.handle} · {row.email} · joined {formatRelative(row.created_at)}
          </p>
          {row.university_name && (
            <p className="mt-0.5 text-[12px] text-subtle">{row.university_name}</p>
          )}
        </div>
        <Button size="sm" variant="ghost" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? "Hide details" : "Details"}
        </Button>
      </div>

      {open && (
        <div className="space-y-3">
          <Summary id={row.id} />
          {!row.is_erased && !isSelf && (
            <div className="flex flex-wrap items-start gap-3">
              <QuickAction
                label="Sign out everywhere"
                onRun={async () => {
                  await admin.signUserOut(row.id);
                  onChanged();
                }}
              />
              {isSuperAdmin && <RoleControl row={row} onChanged={onChanged} />}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-start gap-2">
        {row.is_erased ? (
          <p className="text-[12.5px] text-subtle">
            Deleted by its owner. Their personal data is erased; the records the law requires
            are kept.
          </p>
        ) : isAdminAccount && !isSuperAdmin ? (
          <p className="text-[12.5px] text-subtle">
            Admin accounts are changed by a Super Admin.
          </p>
        ) : row.is_active ? (
          !isAdminAccount && (
            <ActionWithInput
              label="Suspend"
              confirmLabel="Suspend account"
              tone="danger"
              prompt="Why? The member is told. Suspending is reversible and deletes nothing."
              onConfirm={async (reason) => {
                await admin.suspendUser(row.id, reason);
                onChanged();
              }}
            />
          )
        ) : (
          <QuickAction
            label="Reactivate"
            onRun={async () => {
              await admin.reactivateUser(row.id);
              onChanged();
            }}
          />
        )}
      </div>
    </div>
  );
}

function UsersContent() {
  const { user } = useSession();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const query = params.get("q") ?? "";
  const [filter, setFilter] = React.useState<Filter>("");
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.users(query || undefined, filter || undefined, page),
    [query, filter, page],
  );
  const isSuperAdmin = user?.admin_role === "super_admin";

  return (
    <>
      <AdminHeading
        title="Users"
        description="Find an account by email, handle or name. Suspending is reversible, and nothing here deletes anything."
      />
      <FilterBar
        query={query}
        onQuery={(next) => {
          setPage(1);
          router.replace(next ? `${pathname}?q=${encodeURIComponent(next)}` : pathname, {
            scroll: false,
          });
        }}
        placeholder="Email, handle or name"
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
        empty={{ icon: "users", title: query ? "No accounts match" : "No accounts here" }}
      >
        {(row: AdminUserRow) => (
          <UserRow
            key={row.id}
            row={row}
            isSuperAdmin={isSuperAdmin}
            isSelf={row.id === user?.id}
            onChanged={() => void list.reload()}
          />
        )}
      </AdminList>
    </>
  );
}

export default function AdminUsersPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <UsersContent />
    </React.Suspense>
  );
}
