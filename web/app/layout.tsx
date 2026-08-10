import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Instrument_Serif } from "next/font/google";

import { SessionProvider, themeBootstrap } from "@/lib/session";
import "./globals.css";

/**
 * Display face for marketing headlines only.
 *
 * Every marketplace at this size sets its headlines in a grotesque sans, which
 * is why they are hard to tell apart with the logo covered. A high-contrast
 * serif is the cheapest real differentiation available — it reads as considered
 * rather than transactional, and it never competes with the interface, because
 * it is not allowed anywhere near it.
 *
 * Self-hosted at build time by `next/font`, so it costs no third-party request
 * and needs no exception in the content-security policy.
 */
const displaySerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "SkilRize — Find the right talent. Or become it.",
    template: "%s · SkilRize",
  },
  description:
    "Hire for a one-off task or a long build. Sell a service or win a contract. One account, " +
    "one wallet, one reputation — with escrow on every contract and private campus " +
    "marketplaces for verified students.",
  applicationName: "SkilRize",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fcfcfd" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0b10" },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Minted per request by middleware.ts. Every inline script on the page must
  // carry it or the Content-Security-Policy drops the script on the floor.
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${displaySerif.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* Runs before first paint so the correct theme is already applied and
            the page never flashes white on the way to dark.

            `suppressHydrationWarning` is required, not cosmetic: the HTML spec
            has browsers blank the `nonce` *attribute* once parsed (it survives
            only as a property) so that a CSS attribute selector cannot
            exfiltrate it. React compares attributes, sees "" against the value
            it rendered, and reports a mismatch that is really the browser
            behaving correctly. */}
        <script
          nonce={nonce}
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: themeBootstrap }}
        />
      </head>
      <body className="min-h-dvh antialiased">
        <a
          href="#main"
          className="sr-only rounded-md bg-accent px-4 py-2 text-on-accent focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
        >
          Skip to content
        </a>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
