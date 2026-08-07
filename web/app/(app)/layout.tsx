"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";

import { AppHeader, MarketingHeader, SideNav } from "@/components/shell";
import { Logo, Spinner } from "@/components/ui";
import { useSession } from "@/lib/session";

/**
 * Open work is browsable without an account — it is the shop window, and
 * requiring a sign-up to look at it would cost exactly the traffic the
 * category pages exist to attract. Everything else here needs a session.
 */
function isPublicBrowse(pathname: string): boolean {
  return (
    pathname === "/projects" ||
    pathname === "/gigs" ||
    /^\/(projects|gigs)\/\d+$/.test(pathname)
  );
}

/** Pages that get the account sidebar. Browsing is full-width. */
function hasSideNav(pathname: string): boolean {
  return pathname === "/dashboard" || pathname.startsWith("/settings");
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const publicPage = isPublicBrowse(pathname);

  React.useEffect(() => {
    if (!loading && !user && !publicPage) router.replace("/login");
  }, [loading, user, publicPage, router]);

  // The client guard is a convenience, not the control: every endpoint behind
  // it authorises independently, so a user who defeats this sees nothing.
  if (loading || (!user && !publicPage)) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <div className="flex flex-col items-center gap-4">
          <Logo showText={false} />
          <Spinner className="size-5 text-muted" />
          <span className="sr-only">Loading…</span>
        </div>
      </div>
    );
  }

  const withSidebar = Boolean(user) && hasSideNav(pathname);

  return (
    <div className="min-h-dvh bg-surface">
      {user ? <AppHeader /> : <MarketingHeader />}
      <div
        className={
          withSidebar
            ? "mx-auto flex max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:flex-row lg:gap-10"
            : "mx-auto max-w-7xl px-4 py-8 sm:px-6"
        }
      >
        {withSidebar && <SideNav />}
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}
