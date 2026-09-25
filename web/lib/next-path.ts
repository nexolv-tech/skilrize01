/**
 * Where to send someone after they sign in.
 *
 * Only same-site paths are accepted. `?next=https://evil.example` — or the
 * protocol-relative `//evil.example`, or `/\evil.example`, which some browsers
 * normalise to the same thing — would turn the sign-in page into an open
 * redirect that phishing links could borrow our domain for.
 */
export function safeNext(raw: string | null | undefined, fallback = "/dashboard"): string {
  if (!raw) return fallback;
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  if (/^\/(login|signup)\b/.test(raw)) return fallback;
  return raw;
}

/** `/login?next=…` for the current location, preserving the query string. */
export function loginPathFor(pathname: string, search = ""): string {
  const here = `${pathname}${search}`;
  return `/login?next=${encodeURIComponent(here)}`;
}

/** The validated `?next=` of the current page, read at call time (client only). */
export function currentNext(fallback = "/dashboard"): string {
  if (typeof window === "undefined") return fallback;
  return safeNext(new URLSearchParams(window.location.search).get("next"), fallback);
}

/** The raw `?next=` suffix to carry between /login and /signup. */
export function nextSuffix(): string {
  if (typeof window === "undefined") return "";
  const next = new URLSearchParams(window.location.search).get("next");
  return next && safeNext(next, "") ? `?next=${encodeURIComponent(next)}` : "";
}
