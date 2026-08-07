"use client";

/**
 * Application chrome.
 *
 * The surface switcher is scaffolded here rather than added later on purpose:
 * Section 15.2 warns that the most likely user-facing failure in this system is
 * a student posting to the wrong scope, and the defence is that the active
 * surface is unmistakable at a glance. Building the header around that idea now
 * means the portal drops into a shell that already accounts for it.
 */

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Avatar, Badge, Button, Icon, Logo, cn } from "@/components/ui";
import { useSession, useTheme } from "@/lib/session";

/** Account-level pages, shown in the settings sidebar and the user menu. */
const NAV = [
  { href: "/dashboard", label: "Overview", icon: "home" as const },
  { href: "/settings", label: "Profile", icon: "user" as const },
  { href: "/settings/security", label: "Security", icon: "shield" as const },
  { href: "/settings/notifications", label: "Notifications", icon: "bell" as const },
];

/** The marketplace itself, shown in the top bar. */
const WORK_NAV = [
  { href: "/gigs", label: "Services", icon: "layers" as const },
  { href: "/projects", label: "Projects", icon: "search" as const },
  { href: "/orders", label: "Orders", icon: "wallet" as const },
  { href: "/contracts", label: "Contracts", icon: "briefcase" as const },
];

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      className={cn(
        "grid size-9 place-items-center rounded-md text-muted transition-colors duration-150",
        "hover:bg-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        className,
      )}
    >
      <Icon name={theme === "dark" ? "sun" : "moon"} className="size-[18px]" />
    </button>
  );
}

/**
 * Global marketplace vs university portal.
 *
 * Shown to everyone so the model is legible from day one, but the portal side
 * is disabled until student verification passes — which is exactly what the
 * server would enforce anyway.
 */
function SurfaceSwitcher() {
  const { user } = useSession();
  const verified = user?.is_verified_student ?? false;

  return (
    <div
      role="group"
      aria-label="Active surface"
      className="hidden items-center gap-0.5 rounded-lg border border-line bg-sunken p-0.5 sm:flex"
    >
      <span className="inline-flex items-center gap-1.5 rounded-[7px] bg-raised px-2.5 py-1.5 text-[13px] font-medium text-fg shadow-e1">
        <Icon name="layers" className="size-3.5 text-accent" />
        Global
      </span>
      <span
        title={
          verified
            ? `${user?.university?.name ?? "Your university"} portal`
            : "Verify as a student to unlock your university portal"
        }
        aria-disabled={!verified}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-[7px] px-2.5 py-1.5 text-[13px] font-medium",
          verified ? "text-muted" : "cursor-not-allowed text-subtle",
        )}
      >
        <Icon name={verified ? "building" : "lock"} className="size-3.5" />
        {verified ? (user?.university?.short_code ?? "Campus") : "Campus"}
      </span>
    </div>
  );
}

function UserMenu() {
  const { user, signOut } = useSession();
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!user) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-md p-1 transition-colors duration-150 hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <Avatar name={user.display_name} src={user.avatar_url} size={30} />
        <span className="hidden text-[13px] font-medium text-fg sm:block">{user.display_name}</span>
      </button>

      {open && (
        <div
          role="menu"
          className="animate-fade absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-lg border border-line bg-raised shadow-e3"
        >
          <div className="border-b border-line p-3">
            <p className="truncate text-sm font-medium text-fg">{user.display_name}</p>
            <p className="truncate text-[12px] text-muted">{user.email}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {user.can_transact ? (
                <Badge tone="positive">Verified</Badge>
              ) : (
                <Badge tone="caution">Profile incomplete</Badge>
              )}
              {user.is_verified_student && <Badge tone="accent">Student</Badge>}
            </div>
          </div>
          <div className="p-1">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-muted transition-colors duration-150 hover:bg-sunken hover:text-fg"
              >
                <Icon name={item.icon} className="size-4" />
                {item.label}
              </Link>
            ))}
          </div>
          <div className="border-t border-line p-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => void signOut()}
              className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-muted transition-colors duration-150 hover:bg-critical-soft hover:text-critical"
            >
              <Icon name="logout" className="size-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/85 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
        <Link
          href="/dashboard"
          className="rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <Logo />
        </Link>

        <nav aria-label="Marketplace" className="ml-4 hidden items-center gap-1 md:flex">
          {WORK_NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium",
                  "transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  active ? "bg-sunken text-fg" : "text-muted hover:bg-sunken hover:text-fg",
                )}
              >
                <Icon name={item.icon} className="size-3.5" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <Link href="/projects/new" className="hidden sm:block">
            <Button size="sm" variant="secondary">
              <Icon name="plus" className="size-3.5" />
              Post a project
            </Button>
          </Link>
          <SurfaceSwitcher />
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}

export function SideNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Account" className="w-full shrink-0 lg:w-56">
      <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
        {NAV.map((item) => {
          // `/settings` must not light up while on `/settings/security`.
          const active =
            item.href === "/settings" ? pathname === item.href : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 whitespace-nowrap rounded-md px-3 py-2 text-[13px] font-medium",
                  "transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  active
                    ? "bg-accent-soft text-accent"
                    : "text-muted hover:bg-sunken hover:text-fg",
                )}
              >
                <Icon name={item.icon} className="size-4" />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function PageHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 pb-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-[-0.025em] text-fg">{title}</h1>
        {description && <p className="max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function MarketingHeader() {
  const { user, loading } = useSession();

  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-surface/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center px-5">
        <Link href="/" className="rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
          <Logo />
        </Link>
        <nav className="ml-10 hidden items-center gap-7 md:flex" aria-label="Main">
          {[
            ["#tracks", "How it works"],
            ["#campus", "Campus"],
            ["#trust", "Trust"],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="text-[13.5px] text-muted transition-colors duration-150 hover:text-fg"
            >
              {label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {loading ? (
            <div className="h-9 w-32" />
          ) : user ? (
            <Button size="sm" onClick={() => (window.location.href = "/dashboard")}>
              Open dashboard
            </Button>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost" size="sm">
                  Sign in
                </Button>
              </Link>
              <Link href="/signup">
                <Button size="sm">Join free</Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
