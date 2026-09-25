import { NextResponse, type NextRequest } from "next/server";

/**
 * Content Security Policy, issued per request with a fresh nonce.
 *
 * A CSP is only worth having if `script-src` is strict, and `script-src` can
 * only be strict if the inline bootstrap Next.js emits carries a nonce — which
 * is why this is middleware rather than a static header in `next.config.ts`.
 * With `'strict-dynamic'`, scripts the nonced bootstrap loads inherit trust,
 * so the policy survives chunk-name changes between builds without listing any
 * of them.
 *
 * `style-src` still needs `'unsafe-inline'`: Next injects inline `<style>`
 * during hydration and there is no nonce hook for it. Inline *style* is a far
 * weaker primitive than inline *script* — it cannot exfiltrate on its own — so
 * this is the accepted residual, not an oversight.
 */

const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEV = process.env.NODE_ENV !== "production";

export default function proxy(request: NextRequest) {
  const nonce = crypto.randomUUID().replaceAll("-", "");

  const csp = [
    "default-src 'self'",
    // `unsafe-eval` is the dev server's hot-reload transform. It is compiled
    // out of production, where the policy is nonce-only.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${DEV ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    // `data:` covers the inline SVG artwork; `blob:` covers client-side image
    // previews before an upload is committed.
    "img-src 'self' data: blob:",
    // Service videos arrive through the same /files/ route as images; blob:
    // covers the preview shown before an upload is sent.
    "media-src 'self' blob:",
    "font-src 'self' data:",
    // The API is a separate origin, so it has to be named explicitly.
    `connect-src 'self' ${API_ORIGIN}${DEV ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "frame-src 'none'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    ...(DEV ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");

  // The nonce travels to the server components on a request header; Next reads
  // it from there to stamp its own script tags.
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);

  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    // Static assets are immutable and carry no scripts, so they skip the
    // per-request work entirely.
    {
      source: "/((?!_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
