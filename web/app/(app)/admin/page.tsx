"use client";

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import { Card, Icon, Skeleton, type IconName } from "@/components/ui";
import { admin, type AdminRole } from "@/lib/api";
import { useLoader, useSession } from "@/lib/session";

function SummaryCard({
  href,
  icon,
  title,
  loading,
  value,
  description,
}: {
  href: string;
  icon: IconName;
  title: string;
  loading: boolean;
  value: number | null;
  description: string;
}) {
  return (
    <Link href={href}>
      <Card className="lift p-5">
        <div className="flex items-start justify-between gap-3">
          <span className="grid size-9 place-items-center rounded-md bg-accent-soft text-accent">
            <Icon name={icon} className="size-[18px]" />
          </span>
          {loading ? (
            <Skeleton className="h-7 w-10" />
          ) : (
            value !== null && <span className="text-2xl font-semibold text-fg">{value}</span>
          )}
        </div>
        <p className="mt-3 text-[14px] font-medium text-fg">{title}</p>
        <p className="mt-0.5 text-[12.5px] text-muted">{description}</p>
      </Card>
    </Link>
  );
}

export default function AdminOverviewPage() {
  const { user } = useSession();
  const role = (user?.admin_role ?? "") as AdminRole;
  const isSuperAdmin = role === "super_admin";
  const can = (r: AdminRole) => isSuperAdmin || role === r;

  const verifications = useLoader(
    () => (can("verification_officer") ? admin.verifications() : Promise.resolve(null)),
    [role],
  );
  const contracts = useLoader(
    () => (can("finance_admin") ? admin.contracts("active") : Promise.resolve(null)),
    [role],
  );

  return (
    <>
      <PageHeading
        title="Admin console"
        description="Operator tooling for identity review, contract operations, accounts, and the audit trail."
      />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {can("verification_officer") && (
          <SummaryCard
            href="/admin/verifications"
            icon="id"
            title="Verification queue"
            loading={verifications.loading}
            value={verifications.data?.count ?? 0}
            description="Student ID applications awaiting a decision."
          />
        )}
        {can("finance_admin") && (
          <SummaryCard
            href="/admin/contracts"
            icon="briefcase"
            title="Active contracts"
            loading={contracts.loading}
            value={contracts.data?.count ?? 0}
            description="Every contract on the platform, not just your own."
          />
        )}
        {can("support_agent") && (
          <SummaryCard
            href="/admin/users"
            icon="users"
            title="Users"
            loading={false}
            value={null}
            description="Search accounts, suspend, or reactivate."
          />
        )}
        {isSuperAdmin && (
          <SummaryCard
            href="/admin/audit-log"
            icon="shield"
            title="Audit log"
            loading={false}
            value={null}
            description="Every administrative action, append-only."
          />
        )}
      </div>
    </>
  );
}
