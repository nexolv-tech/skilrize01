"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { AppHeader, MarketingHeader, SideNav } from "@/components/shell";
import { SiteFooter } from "@/components/site-footer";
import { Logo, Spinner } from "@/components/ui";
import { BUSINESS } from "@/lib/business";
import { loginPathFor } from "@/lib/next-path";
import { useSession } from "@/lib/session";

/**
 * Open work is browsable without an account — it is the shop window, and
 * requiring a sign-up to look at it would cost exactly the traffic the
 * category pages exist to attract. Checkout is public too: a buyer (or a
 * payment network's reviewer) can see exactly what they will pay and on what
 * terms before being asked to create an account. Everything else needs a
 * session.
 */
function isPublicBrowse(pathname: string): boolean {
  return (
    pathname === "/projects" ||
    pathname === "/gigs" ||
    pathname === "/pricing" ||
    /^\/(projects|gigs)\/\d+$/.test(pathname) ||
    /^\/checkout\/\d+$/.test(pathname)
  );
}

/** Pages that get the account sidebar. Browsing is full-width. */
function hasSideNav(pathname: string): boolean {
  return pathname === "/dashboard" || pathname.startsWith("/settings");
}

const LEGAL_LINKS: Array<[string, string]> = [
  ["Terms", "/terms"],
  ["Privacy", "/privacy"],
  ["Refunds", "/refunds"],
  ["Cookies", "/cookies"],
  ["Contact", "/contact"],
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const publicPage = isPublicBrowse(pathname);

  React.useEffect(() => {
    // The return path rides along, so signing in lands back on the page the
    // visitor was trying to reach instead of the dashboard.
    if (!loading && !user && !publicPage) {
      router.replace(loginPathFor(pathname, window.location.search));
    }
  }, [loading, user, publicPage, pathname, router]);

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
    <div className="flex min-h-dvh flex-col bg-surface">
      {user ? <AppHeader /> : <MarketingHeader />}
      <div
        className={
          withSidebar
            ? "mx-auto flex w-full max-w-7xl flex-1 flex-col gap-8 px-4 py-8 sm:px-6 lg:flex-row lg:gap-10"
            : "mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6"
        }
      >
        {withSidebar && <SideNav />}
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
      {user ? (
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 text-[12.5px] text-subtle sm:px-6">
            <p>
              {BUSINESS.product} · Operated by {BUSINESS.operator}
            </p>
            <nav aria-label="Legal" className="flex flex-wrap gap-x-5 gap-y-1">
              {LEGAL_LINKS.map(([label, href]) => (
                <Link key={href} href={href} className="hover:text-fg">
                  {label}
                </Link>
              ))}
            </nav>
          </div>
        </footer>
      ) : (
        <SiteFooter />
      )}
    </div>
  );
}
