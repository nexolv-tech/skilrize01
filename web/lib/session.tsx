"use client";

/**
 * Session and theme context.
 *
 * The signed-in user is fetched once and shared; every screen that needs to
 * know whether the profile gate has been passed reads it from here rather than
 * re-deriving it, so there is exactly one answer in the UI at any moment.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  auth,
  getSurface,
  restoreSurface,
  setSurface as persistSurface,
  type SurfaceKind,
  type User,
} from "./api";

interface SessionValue {
  user: User | null;
  loading: boolean;
  /** Re-read the account from the server, e.g. after a verification step. */
  refresh: () => Promise<User | null>;
  setUser: (user: User | null) => void;
  signOut: () => Promise<void>;
  /** Which marketplace is being viewed. */
  surface: SurfaceKind;
  switchSurface: (next: SurfaceKind) => void;
}

const SessionContext = React.createContext<SessionValue | null>(null);

export function SessionProvider({
  children,
  initialUser = null,
}: {
  children: React.ReactNode;
  initialUser?: User | null;
}) {
  const [user, setUser] = React.useState<User | null>(initialUser);
  const [loading, setLoading] = React.useState(true);
  const [surface, setSurfaceState] = React.useState<SurfaceKind>(getSurface);
  const router = useRouter();

  const refresh = React.useCallback(async () => {
    try {
      const next = await auth.me();
      setUser(next);

      // A stored surface can outlive the entitlement behind it — the student
      // graduated, or a reviewer revoked the approval. Every request would then
      // 403 until the user found the switcher, so the stale choice is dropped
      // here instead, the moment the server tells us what is actually allowed.
      const allowed = (next.surfaces ?? []).some((option) => option.kind === getSurface());
      if (!allowed && getSurface() !== "global") {
        persistSurface("global");
        setSurfaceState("global");
      }
      return next;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const switchSurface = React.useCallback(
    (next: SurfaceKind) => {
      if (next === getSurface()) return;
      persistSurface(next);
      setSurfaceState(next);
      // A full navigation rather than a soft refresh: every cached list on the
      // page belongs to the surface it was fetched under, and re-rendering with
      // the old data under a new label is exactly the confusion the switcher
      // exists to prevent.
      router.refresh();
    },
    [router],
  );

  React.useEffect(() => {
    // localStorage is not readable during render, so the surface is restored
    // here and the module-level value in api.ts is primed before the first
    // request goes out.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSurfaceState(restoreSurface());
    // Restoring the session from the refresh cookie is a read of external
    // state; the setState lands in the async continuation, which the lint rule
    // cannot follow across the await.
    void refresh();
  }, [refresh]);

  const signOut = React.useCallback(async () => {
    await auth.logout().catch(() => undefined);
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = React.useMemo(
    () => ({ user, loading, refresh, setUser, signOut, surface, switchSurface }),
    [user, loading, refresh, signOut, surface, switchSurface],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const context = React.useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside a SessionProvider.");
  return context;
}

/* -------------------------------------------------------------------------- */
/* Theme                                                                      */
/* -------------------------------------------------------------------------- */

export type Theme = "light" | "dark";

const STORAGE_KEY = "skilrize-theme";

/**
 * Applied before first paint by an inline script in the root layout, so the
 * page never flashes the wrong theme.
 */
export const themeBootstrap = `
(function () {
  try {
    var stored = localStorage.getItem('${STORAGE_KEY}');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (stored === 'dark' || (!stored && prefersDark)) document.documentElement.classList.add('dark');
  } catch (e) {}
})();
`;

/**
 * The document element is the source of truth for theme — the bootstrap script
 * sets it before React ever runs. Subscribing to it with `useSyncExternalStore`
 * rather than mirroring it into state means there is no window in which React
 * and the DOM disagree, and no render cascade on mount.
 */
const themeStore = {
  listeners: new Set<() => void>(),
  subscribe(listener: () => void) {
    themeStore.listeners.add(listener);
    return () => themeStore.listeners.delete(listener);
  },
  emit() {
    themeStore.listeners.forEach((listener) => listener());
  },
  get(): Theme {
    return document.documentElement.classList.contains("dark") ? "dark" : "light";
  },
};

export function useTheme() {
  const theme = React.useSyncExternalStore(
    themeStore.subscribe,
    themeStore.get,
    // The server has no document; light matches the pre-hydration markup.
    () => "light" as Theme,
  );

  const setTheme = React.useCallback((next: Theme) => {
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // A blocked storage API is not a reason to refuse to change theme.
    }
    themeStore.emit();
  }, []);

  const toggle = React.useCallback(
    () => setTheme(theme === "dark" ? "light" : "dark"),
    [theme, setTheme],
  );

  return { theme, setTheme, toggle };
}

/* -------------------------------------------------------------------------- */
/* Data loading                                                               */
/* -------------------------------------------------------------------------- */

/**
 * Fetch on mount and whenever `deps` change, with cancellation.
 *
 * Every screen in the app loads through this rather than writing its own
 * effect. That is worth a shared hook on its own — the cancel-on-unmount
 * bookkeeping is easy to get subtly wrong and produces the classic "state
 * update on an unmounted component after the user navigated away" bug — and it
 * also means the one place React's lint rule cannot see across an `await` is
 * suppressed once, here, with an explanation, instead of at a dozen call sites.
 *
 * The state updates below all happen in an async continuation after the
 * request resolves, which is the "subscribe to an external system and set
 * state in a callback" shape React documents as correct.
 */
export function useLoader<T>(load: () => Promise<T>, deps: React.DependencyList) {
  const [data, setData] = React.useState<T | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Held in a ref so a fresh inline arrow on every render does not retrigger
  // the effect; `deps` is what decides when to refetch.
  const loadRef = React.useRef(load);
  React.useEffect(() => {
    loadRef.current = load;
  });

  const run = React.useCallback(async (signal?: { cancelled: boolean }) => {
    try {
      const next = await loadRef.current();
      if (!signal?.cancelled) {
        setData(next);
        setError(null);
      }
    } catch (caught) {
      if (!signal?.cancelled) setError((caught as Error).message ?? "Could not load this.");
    } finally {
      if (!signal?.cancelled) setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    const signal = { cancelled: false };
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    void run(signal);
    return () => {
      signal.cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const reload = React.useCallback(() => run(), [run]);

  return { data, loading, error, reload, setData };
}

/* -------------------------------------------------------------------------- */
/* Small shared helpers                                                       */
/* -------------------------------------------------------------------------- */

export function useAsyncAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
) {
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [code, setCode] = React.useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({});

  const run = React.useCallback(
    async (...args: TArgs): Promise<TResult | undefined> => {
      setPending(true);
      setError(null);
      setCode(null);
      setFieldErrors({});
      try {
        return await action(...args);
      } catch (caught) {
        const apiError = caught as {
          message?: string;
          code?: string;
          fields?: Record<string, string>;
        };
        setError(apiError.message ?? "Something went wrong. Please try again.");
        // Surfaced separately from the message so a caller can branch on *why*
        // it failed — `two_factor_required` and `device_cooloff` both want a
        // specific next step, not a red banner.
        setCode(apiError.code ?? null);
        setFieldErrors(apiError.fields ?? {});
        return undefined;
      } finally {
        setPending(false);
      }
    },
    [action],
  );

  return { run, pending, error, code, fieldErrors, setError };
}

export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const seconds = Math.round((Date.now() - then) / 1000);
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["second", 60],
    ["minute", 60],
    ["hour", 24],
    ["day", 7],
    ["week", 4.35],
    ["month", 12],
    ["year", Infinity],
  ];

  let value = seconds;
  for (const [unit, step] of units) {
    if (Math.abs(value) < step) {
      return new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(-Math.round(value), unit);
    }
    value /= step;
  }
  return new Date(iso).toLocaleDateString();
}
