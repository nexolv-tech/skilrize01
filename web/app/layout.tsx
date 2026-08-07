import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

import { SessionProvider, themeBootstrap } from "@/lib/session";
import "./globals.css";

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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        {/* Runs before first paint so the correct theme is already applied and
            the page never flashes white on the way to dark. */}
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
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
