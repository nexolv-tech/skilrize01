"use client";

/**
 * The admin console (D54). `AppLayout` already requires a session for
 * everything under `(app)`; this adds the second gate, on `admin_role`.
 *
 * Each role sees only the sections it works in, and Super Admin sees all of
 * them, matching what the API enforces per endpoint
 * (`accounts.auth.require_admin_role`). Hiding a section here is a
 * convenience; the real boundary is server-side. The counts beside a
 * section are the items waiting in it, from `/admin/overview/`.
 */

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { CountPill, canSee } from "@/components/admin";
import { Icon, Spinner, cn, type IconName } from "@/components/ui";
import { admin, type AdminOverview, type AdminRole } from "@/lib/api";
import { useLoader, useSession } from "@/lib/session";

interface Section {
  href: string;
  label: string;
  icon: IconName;
  /** Roles besides Super Admin that work here; null means every admin. */
  roles: AdminRole[] | null;
  /** Items waiting, from the overview's queues. */
  count?: (queues: AdminOverview["queues"]) => number;
}

const GROUPS: Array<{ label: string | null; sections: Section[] }> = [
  {
    label: null,
    sections: [{ href: "/admin", label: "Overview", icon: "home", roles: null }],
  },
  {
    label: "Money",
    sections: [
      {
        href: "/admin/payments",
        label: "Payments",
        icon: "wallet",
        roles: ["finance_admin"],
        count: (q) => (q.transfers ?? 0) + (q.payouts ?? 0) + (q.refunds ?? 0),
      },
      {
        href: "/admin/orders",
        label: "Orders",
        icon: "layers",
        roles: ["finance_admin", "support_agent", "dispute_officer"],
      },
      { href: "/admin/contracts", label: "Contracts", icon: "file", roles: ["finance_admin"] },
    ],
  },
  {
    label: "People",
    sections: [
      {
        href: "/admin/verifications",
        label: "Verifications",
        icon: "id",
        roles: ["verification_officer"],
        count: (q) => (q.identity ?? 0) + (q.students ?? 0),
      },
      { href: "/admin/users", label: "Users", icon: "users", roles: ["support_agent"] },
    ],
  },
  {
    label: "Marketplace",
    sections: [
      { href: "/admin/services", label: "Services", icon: "star", roles: ["moderator"] },
      { href: "/admin/briefs", label: "Briefs", icon: "briefcase", roles: ["moderator"] },
      { href: "/admin/categories", label: "Categories", icon: "filter", roles: ["moderator"] },
      {
        href: "/admin/reports",
        label: "Reports",
        icon: "megaphone",
        roles: ["moderator"],
        count: (q) => q.reports ?? 0,
      },
    ],
  },
  {
    label: "System",
    sections: [
      { href: "/admin/settings", label: "Settings", icon: "key", roles: [] },
      { href: "/admin/audit-log", label: "Audit log", icon: "shield", roles: [] },
    ],
  },
];

const ROLE_LABEL: Record<Exclude<AdminRole, "">, string> = {
  super_admin: "Super Admin",
  finance_admin: "Finance Admin",
  moderator: "Moderator",
  support_agent: "Support Agent",
  dispute_officer: "Dispute Officer",
  verification_officer: "Verification Officer",
  university_moderator: "University Moderator",
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  const role = (user?.admin_role ?? "") as AdminRole;
  const isAdmin = Boolean(role);
  // Re-read on every section change so a count clears once its queue does.
  const { data: overview } = useLoader(
    () => (isAdmin ? admin.overview() : Promise.resolve(null)),
    [isAdmin, pathname],
  );

  React.useEffect(() => {
    if (!loading && !isAdmin) router.replace("/dashboard");
  }, [loading, isAdmin, router]);

  if (loading || !isAdmin) {
    return (
      <div className="grid min-h-[50vh] place-items-center">
        <Spinner className="size-5 text-muted" />
      </div>
    );
  }

  const groups = GROUPS.map((group) => ({
    ...group,
    sections: group.sections.filter((section) => canSee(role, section.roles)),
  })).filter((group) => group.sections.length > 0);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[13.5rem_minmax(0,1fr)]">
      {/* min-w-0: on a phone the section links scroll inside their strip
          instead of widening the page. */}
      <aside className="min-w-0 lg:sticky lg:top-20 lg:self-start">
        <p className="eyebrow mb-1 hidden lg:block">Admin console</p>
        <p className="mb-4 hidden text-[12.5px] text-muted lg:block">
          {ROLE_LABEL[role as Exclude<AdminRole, "">]}
        </p>
        <nav
          aria-label="Admin console"
          className="-mx-1 flex gap-1 overflow-x-auto pb-1 lg:mx-0 lg:block lg:space-y-5 lg:overflow-visible"
        >
          {groups.map((group) => (
            <div key={group.label ?? "top"} className="contents lg:block">
              {group.label && (
                <p className="hidden px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-subtle lg:block">
                  {group.label}
                </p>
              )}
              <ul className="contents lg:block lg:space-y-0.5">
                {group.sections.map((section) => {
                  const active =
                    section.href === "/admin"
                      ? pathname === "/admin"
                      : pathname.startsWith(section.href);
                  const waiting = overview && section.count ? section.count(overview.queues) : 0;
                  return (
                    <li key={section.href} className="shrink-0">
                      <Link
                        href={section.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex items-center gap-2.5 whitespace-nowrap rounded-md px-3 py-2 text-[13px] font-medium",
                          "transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                          active ? "bg-accent-soft text-fg" : "text-muted hover:bg-sunken hover:text-fg",
                        )}
                      >
                        <Icon name={section.icon} className="size-4" />
                        <span className="flex-1">{section.label}</span>
                        {waiting > 0 && <CountPill value={waiting} />}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
