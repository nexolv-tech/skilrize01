"use client";

/**
 * The admin console — Phase 9. `AppLayout` already requires a session for
 * everything under `(app)`; this adds the second gate, on `admin_role`.
 *
 * Every role sees only the sections its role covers, Super Admin sees all
 * four — matching exactly what the backend enforces per endpoint
 * (`accounts.auth.require_admin_role`). The nav hiding a section is a
 * convenience, same as every other client-side guard in this app; the real
 * boundary is server-side.
 */

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Icon, Spinner, cn, type IconName } from "@/components/ui";
import { type AdminRole } from "@/lib/api";
import { useSession } from "@/lib/session";

interface Section {
  href: string;
  label: string;
  icon: IconName;
  /** null means every admin role can see it. */
  roles: AdminRole[] | null;
}

const SECTIONS: Section[] = [
  { href: "/admin", label: "Overview", icon: "home", roles: null },
  {
    href: "/admin/verifications",
    label: "Verifications",
    icon: "id",
    roles: ["verification_officer"],
  },
  { href: "/admin/users", label: "Users", icon: "users", roles: ["support_agent"] },
  { href: "/admin/contracts", label: "Contracts", icon: "briefcase", roles: ["finance_admin"] },
  { href: "/admin/audit-log", label: "Audit log", icon: "shield", roles: ["super_admin"] },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  const role = (user?.admin_role ?? "") as AdminRole;
  const isAdmin = Boolean(role);
  const isSuperAdmin = role === "super_admin";

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

  const visibleSections = SECTIONS.filter(
    (section) => !section.roles || isSuperAdmin || section.roles.includes(role),
  );

  return (
    <div>
      <div className="mb-6 -mt-2 border-b border-line">
        <nav className="flex gap-1 overflow-x-auto">
          {visibleSections.map((section) => {
            const active = pathname === section.href;
            return (
              <Link
                key={section.href}
                href={section.href}
                className={cn(
                  "flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-medium transition-colors",
                  active
                    ? "border-accent text-fg"
                    : "border-transparent text-muted hover:text-fg",
                )}
              >
                <Icon name={section.icon} className="size-3.5" />
                {section.label}
              </Link>
            );
          })}
        </nav>
      </div>
      {children}
    </div>
  );
}
