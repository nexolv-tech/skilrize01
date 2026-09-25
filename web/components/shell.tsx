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

import { Avatar, Badge, ButtonLink, Icon, Logo, cn, type IconName } from "@/components/ui";
import { useSession, useTheme } from "@/lib/session";

interface NavItem {
  href: string;
  label: string;
  icon: IconName;
}

/** Account-level pages, shown in the settings sidebar and the user menu. */
const NAV: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: "home" as const },
  { href: "/settings", label: "Profile", icon: "user" as const },
  { href: "/settings/security", label: "Security", icon: "shield" as const },
  { href: "/settings/notifications", label: "Notifications", icon: "bell" as const },
  { href: "/settings/integrations", label: "Integrations", icon: "link" as const },
  { href: "/settings/payouts", label: "Payouts", icon: "wallet" as const },
  { href: "/settings/privacy", label: "Privacy & data", icon: "lock" as const },
];

/** The marketplace itself, shown in the top bar. */
const WORK_NAV = [
  { href: "/search", label: "Search", icon: "search" as const },
  { href: "/gigs", label: "Services", icon: "layers" as const },
  { href: "/projects", label: "Projects", icon: "briefcase" as const },
  { href: "/challenges", label: "Challenges", icon: "zap" as const },
  { href: "/showcase", label: "Showcase", icon: "star" as const },
  { href: "/orders", label: "Orders", icon: "wallet" as const },
  { href: "/contracts", label: "Contracts", icon: "file" as const },
];

/** The social layer. Separated from the work nav so the two do not compete. */
const SOCIAL_NAV = [
  { href: "/communities", label: "Communities", icon: "users" as const },
  { href: "/feed", label: "Activity", icon: "sparkles" as const },
  { href: "/messages", label: "Messages", icon: "send" as const },
];

/**
 * The professional layer — tools for running the business rather than surfaces
 * for browsing it. Kept out of the top bar deliberately: those are the things
 * you click many times an hour, and these are the things you open a few times
 * a day, so they sit with the account rather than competing for the same space.
 */
const BUSINESS_NAV: NavItem[] = [
  { href: "/crm", label: "Clients", icon: "chart" },
  { href: "/retainers", label: "Retainers", icon: "clock" },
  { href: "/teams", label: "Teams", icon: "building" },
  { href: "/pricing", label: "Plans", icon: "sparkles" },
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
/**
 * Global marketplace vs university portal.
 *
 * Section 15.2 names posting to the wrong scope as the most likely user-facing
 * failure in this system, and the defence is that the active surface is
 * unmistakable at a glance — hence a permanently visible control rather than a
 * setting, and an accent-coloured campus state rather than a subtle one.
 *
 * The campus side is shown to everyone, disabled until verification passes, so
 * the model is legible before you qualify for it. Disabling it here is a
 * courtesy: `core.scope.resolve_for` refuses the surface server-side regardless
 * of what the client sends.
 */
function SurfaceSwitcher() {
  const { user, surface, switchSurface } = useSession();
  const campus = (user?.surfaces ?? []).find((option) => option.kind === "university");
  const verified = Boolean(campus);

  return (
    <div
      role="group"
      aria-label="Active marketplace"
      className="hidden items-center gap-0.5 rounded-lg border border-line bg-sunken p-0.5 sm:flex"
    >
      <button
        type="button"
        onClick={() => switchSurface("global")}
        aria-pressed={surface === "global"}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-[7px] px-2.5 py-1.5 text-[13px] font-medium",
          "transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
          surface === "global"
            ? "bg-raised text-fg shadow-e1"
            : "text-muted hover:text-fg",
        )}
      >
        <Icon name="layers" className="size-3.5" />
        Global
      </button>

      <button
        type="button"
        disabled={!verified}
        onClick={() => switchSurface("university")}
        aria-pressed={surface === "university"}
        title={
          verified
            ? `${campus?.university?.name ?? "Your university"} portal`
            : "Verify as a student to unlock your university portal"
        }
        className={cn(
          "inline-flex items-center gap-1.5 rounded-[7px] px-2.5 py-1.5 text-[13px] font-medium",
          "transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
          !verified && "cursor-not-allowed text-subtle",
          verified && surface === "university" && "bg-campus text-white shadow-e1",
          verified && surface !== "university" && "text-muted hover:text-fg",
        )}
      >
        <Icon name={verified ? "building" : "lock"} className="size-3.5" />
        {campus?.university?.short_code ?? "Campus"}
      </button>
    </div>
  );
}

/**
 * A full-width bar shown only inside a campus portal.
 *
 * The switcher alone is a small control in a busy header. This is the part that
 * makes the surface impossible to miss while composing a brief, which is the
 * moment the mistake actually costs something.
 */
function CampusBanner() {
  const { user, surface, switchSurface } = useSession();
  const campus = (user?.surfaces ?? []).find((option) => option.kind === "university");

  if (surface !== "university" || !campus) return null;

  return (
    <div className="border-b border-campus/30 bg-campus-soft">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 sm:px-6">
        <Icon name="building" className="size-4 shrink-0 text-campus" />
        <p className="text-[13px] text-fg">
          You are inside the{" "}
          <span className="font-semibold">{campus.university?.name}</span> portal. Everything you
          post or publish here is visible only to verified students of your university.
        </p>
        <button
          type="button"
          onClick={() => switchSurface("global")}
          className="ml-auto text-[13px] font-medium text-campus underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Back to global
        </button>
      </div>
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
        <span className="block max-w-[7.5rem] truncate text-[13px] font-medium text-fg sm:max-w-[12rem]">
          {user.display_name}
        </span>
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
            {BUSINESS_NAV.map((item) => (
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
          {user.admin_role && (
            <div className="border-t border-line p-1">
              <Link
                href="/admin"
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-muted transition-colors duration-150 hover:bg-sunken hover:text-fg"
              >
                <Icon name="shield" className="size-4" />
                Admin console
              </Link>
            </div>
          )}
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
  const { user } = useSession();
  const cooloff = user?.device_cooloff_seconds ?? 0;

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/85 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
        <Link
          href="/dashboard"
          className="shrink-0 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <Logo />
        </Link>

        {/* The nav is the one part allowed to give way. Nine destinations plus
            the account controls do not fit a laptop width, and the failure
            mode of a fixed-width nav is the *page* scrolling sideways — which
            pushes the user menu off-screen entirely. This scrolls inside its
            own box instead, so the controls on the right always stay put. */}
        <nav
          aria-label="Marketplace"
          className="ml-4 hidden min-w-0 flex-1 items-center gap-1 overflow-x-auto md:flex [scrollbar-width:none] [&::-webkit-scrollbar]:hidden [mask-image:linear-gradient(to_right,#000_calc(100%-2.5rem),transparent)]"
        >
          {[...WORK_NAV, ...SOCIAL_NAV].map((item) => {
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

        <div className="ml-auto flex shrink-0 items-center gap-2">
          {/* Held back until there is room for it beside the nav: on a laptop
              it is the first thing that pushes the account controls out. */}
          <ButtonLink href="/projects/new" size="sm" variant="secondary" className="hidden lg:inline-flex">
            <Icon name="plus" className="size-3.5" />
            Post a brief
          </ButtonLink>
          <SurfaceSwitcher />
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>

      <CampusBanner />
      {/* Keyed on the value so a fresh countdown starts from scratch when the
          session reloads, rather than the effect writing over live state. */}
      <DeviceCooloffBanner key={cooloff} seconds={cooloff} />
    </header>
  );
}

/**
 * The new-device hold, explained where the user will hit it.
 *
 * A control the user cannot see is a control they experience as a bug. This
 * says what is held, for how long, and — the part that matters — what to do if
 * the sign-in was not theirs. It counts down locally rather than polling: the
 * server is still the authority on every request, so a display that drifts a
 * second is harmless and a request per second is not.
 */
function DeviceCooloffBanner({ seconds }: { seconds: number }) {
  const [remaining, setRemaining] = React.useState(seconds);

  // The deadline is captured inside the effect rather than during render:
  // `Date.now()` is impure, and anchoring to a wall-clock deadline keeps the
  // countdown honest across a backgrounded tab, where interval callbacks are
  // throttled and a naive decrement would fall behind.
  React.useEffect(() => {
    if (seconds <= 0) return;
    const deadline = Date.now() + seconds * 1000;
    const timer = setInterval(() => {
      const left = Math.max(Math.ceil((deadline - Date.now()) / 1000), 0);
      setRemaining(left);
      if (left <= 0) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [seconds]);

  if (remaining <= 0) return null;

  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const label = hours > 0 ? `${hours}h ${minutes}m` : `${Math.max(minutes, 1)}m`;

  return (
    <div className="border-b border-caution/30 bg-caution-soft">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 sm:px-6">
        <Icon name="shield" className="size-4 shrink-0 text-caution" />
        <p className="text-[13px] text-fg">
          <span className="font-medium">New device.</span> You can browse everything, but
          posting, bidding, and payments unlock in{" "}
          <span className="tabular font-medium">{label}</span>.
        </p>
        <Link
          href="/settings/security"
          className="text-[13px] font-medium text-accent underline-offset-4 hover:underline"
        >
          Not you? Secure your account
        </Link>
      </div>
    </div>
  );
}

export function SideNav() {
  const pathname = usePathname();

  function link(item: NavItem) {
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
            active ? "bg-accent-soft text-fg" : "text-muted hover:bg-sunken hover:text-fg",
          )}
        >
          <Icon name={item.icon} className="size-4" />
          {item.label}
        </Link>
      </li>
    );
  }

  return (
    <nav aria-label="Account" className="w-full shrink-0 space-y-1 lg:w-56">
      <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
        {NAV.map(link)}
      </ul>
      <p className="hidden px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-subtle lg:block">
        Business
      </p>
      <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
        {BUSINESS_NAV.map(link)}
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
    <div className="flex flex-wrap items-end justify-between gap-4 pb-7">
      <div className="space-y-2">
        <h1 className="display-md text-fg">{title}</h1>
        {description && (
          <p className="max-w-2xl text-[15px] leading-relaxed text-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/**
 * The marketing header.
 *
 * Four destinations a first-time visitor actually wants — see what is for
 * sale, post a brief, understand how the money works, see the price — and one
 * action. Everything else lives in the footer.
 */
const MARKETING_NAV: Array<[string, string]> = [
  ["/gigs", "Browse services"],
  ["/projects", "Open briefs"],
  ["/#how-it-works", "How it works"],
  ["/pricing", "Pricing"],
];

export function MarketingHeader() {
  const { user, loading } = useSession();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center px-5">
        <Link
          href="/"
          aria-label="SkilRize home"
          className="rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <Logo />
        </Link>
        <nav className="ml-10 hidden items-center gap-7 lg:flex" aria-label="Main">
          {MARKETING_NAV.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              className="text-[14px] font-medium text-muted transition-colors duration-150 hover:text-fg"
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {loading ? (
            <div className="h-9 w-32" />
          ) : user ? (
            <ButtonLink href="/dashboard" size="sm">
              Open dashboard
            </ButtonLink>
          ) : (
            <>
              <ButtonLink href="/login" variant="ghost" size="sm">
                Sign in
              </ButtonLink>
              <ButtonLink href="/signup" size="sm">
                Join free
              </ButtonLink>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
