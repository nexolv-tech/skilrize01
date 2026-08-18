import type { NextConfig } from "next";

/**
 * Security headers are set here as well as at the API, because the web app is
 * a separate origin and gets none of Django's (report Section 7.1).
 *
 * Content-Security-Policy is deliberately *not* here — it needs a per-request
 * nonce, so it is issued from `middleware.ts` instead. Everything below is
 * request-independent and belongs on the static header set.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Redundant with the CSP's `frame-ancestors`, kept for browsers that honour
  // only the older header.
  { key: "X-Frame-Options", value: "DENY" },
  {
    key: "Permissions-Policy",
    value:
      "camera=(), microphone=(), geolocation=(), payment=(), usb=(), " +
      "magnetometer=(), gyroscope=(), interest-cohort=()",
  },
  // Two years, with preload — the value browsers require to accept a domain
  // onto the HSTS preload list.
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  // Cuts this origin out of any cross-origin attacker's browsing context group,
  // which is what closes the XS-Leaks and Spectre-adjacent side channels.
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
  // Uploaded files are reached through signed API URLs and never rendered from
  // this origin, so nothing here needs to be embeddable elsewhere.
  { key: "X-Permitted-Cross-Domain-Policies", value: "none" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Production Docker image runs the standalone server output (a pruned
  // node_modules + server.js), not `next start` against the full build —
  // but only there. Vercel supplies its own serverless bundling and this
  // setting changes the build output shape in a way that actively breaks
  // Vercel's own trace step (an ENOENT on a missing .nft.json), so it's
  // skipped whenever `VERCEL` is set — Vercel sets that env var on every
  // build automatically, so nothing has to be configured by hand per target.
  output: process.env.VERCEL ? undefined : "standalone",
  // Next 16.3 writes AGENTS.md and CLAUDE.md into the app directory on every
  // dev start. This repository documents itself in README.md and DECISIONS.md;
  // generated files that reappear after every `npm run dev` are noise in a
  // diff, so they are turned off.
  agentRules: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
