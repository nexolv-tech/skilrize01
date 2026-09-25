import Link from "next/link";

import { EscrowTicket } from "@/components/marketing";
import { ThemeToggle } from "@/components/shell";
import { Logo } from "@/components/ui";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,40rem)]">
      {/* Form side. First in the DOM so keyboard and screen-reader users reach
          the actual task before the brand panel. */}
      <div className="flex flex-col">
        <header className="flex items-center justify-between px-6 py-5">
          <Link
            href="/"
            aria-label="SkilRize home"
            className="rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <Logo />
          </Link>
          <ThemeToggle />
        </header>

        <main id="main" className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-sm">{children}</div>
        </main>

        <footer className="flex flex-wrap justify-center gap-x-5 gap-y-1 px-6 pb-6 text-[12.5px] text-subtle">
          <Link href="/terms" className="hover:text-fg">
            Terms
          </Link>
          <Link href="/privacy" className="hover:text-fg">
            Privacy
          </Link>
          <Link href="/refunds" className="hover:text-fg">
            Refunds
          </Link>
          <Link href="/contact" className="hover:text-fg">
            Contact
          </Link>
        </footer>
      </div>

      {/* Brand side. Hidden below large screens rather than stacked, so the
          form is never pushed below the fold on a phone. */}
      <aside className="relative hidden border-l border-line bg-sunken lg:block">
        <div className="flex h-full flex-col justify-center px-14 py-16">
          <p className="eyebrow">Why people trust SkilRize</p>
          <h2 className="display-lg mt-4 max-w-md">Nobody gets paid until the work is approved.</h2>
          <p className="mt-5 max-w-md text-[15.5px] leading-relaxed text-muted">
            Every payment waits in escrow. Freelancers see it is funded before they start;
            clients release it only when they are happy — or get it back if the order is
            cancelled.
          </p>
          <EscrowTicket className="mt-10 max-w-md" />
        </div>
      </aside>
    </div>
  );
}
