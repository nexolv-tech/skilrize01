import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { Archivo, Martian_Mono } from "next/font/google";

import { CookieNotice } from "@/components/cookie-notice";
import { BUSINESS } from "@/lib/business";
import { SessionProvider, themeBootstrap } from "@/lib/session";
import "./globals.css";

/**
 * One superfamily at two widths: Archivo condensed for display, Archivo at
 * normal width for everything people read and operate. Martian Mono carries
 * the record — amounts, order numbers, form-style labels.
 *
 * Self-hosted at build time by `next/font`, so there is no request to Google
 * from a visitor's browser (no third party learns who visited), and no
 * exception is needed in the content-security policy.
 */
const archivo = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--font-archivo",
  display: "swap",
});

const martian = Martian_Mono({
  subsets: ["latin"],
  variable: "--font-martian",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(BUSINESS.siteUrl),
  title: {
    default: "SkilRize — Hire freelancers in Pakistan, pay when the work is approved",
    template: "%s · SkilRize",
  },
  description:
    "Buy fixed-price services or post a brief and compare proposals. Your payment is held in " +
    "escrow and released only when you approve the work — refunded if the order is cancelled.",
  applicationName: "SkilRize",
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    siteName: "SkilRize",
    locale: "en_PK",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfbfa" },
    { media: "(prefers-color-scheme: dark)", color: "#121110" },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Minted per request by proxy.ts. Every inline script on the page must
  // carry it or the Content-Security-Policy drops the script on the floor.
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html
      lang="en"
      className={`${archivo.variable} ${martian.variable}`}
      // Lets the router turn smooth scrolling off during a page change, so a
      // new page opens at the top instead of gliding there from the old one.
      data-scroll-behavior="smooth"
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
          className="sr-only rounded-md bg-action px-4 py-2 font-medium text-on-action focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
        >
          Skip to content
        </a>
        <SessionProvider>{children}</SessionProvider>
        <CookieNotice />
      </body>
    </html>
  );
}
