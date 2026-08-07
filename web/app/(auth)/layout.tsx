import Link from "next/link";

import { ThemeToggle } from "@/components/shell";
import { Icon, Logo } from "@/components/ui";

const PROOF = [
  ["Escrow on every contract", "Funds are captured before work starts and released on acceptance."],
  ["Verified identity", "Email, phone and national ID — checked before anyone can transact."],
  ["Your campus, privately", "Verify as a student and unlock a portal only your university can see."],
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,42rem)]">
      {/* Form side. Placed first in the DOM so keyboard and screen-reader users
          reach the actual task before the marketing panel. */}
      <div className="flex flex-col">
        <header className="flex items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <Logo />
          </Link>
          <ThemeToggle />
        </header>

        <main id="main" className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-sm">{children}</div>
        </main>
      </div>

      {/* Brand side. Decorative — hidden below large screens rather than
          stacked, so the form is never pushed below the fold on a phone. */}
      <aside className="bg-aurora-live texture-grain relative hidden overflow-hidden border-l border-line lg:block">
        <div className="bg-grid absolute inset-0 opacity-40" aria-hidden />
        <div className="relative flex h-full flex-col justify-center px-14 py-16">
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-line bg-raised/70 px-3 py-1.5 text-[12px] font-medium text-muted backdrop-blur">
            <span className="size-1.5 rounded-full bg-positive" aria-hidden />
            Two marketplaces, one account
          </span>

          <h2 className="display-2 mt-6 max-w-md text-fg">
            Hire, get hired, and rise — on one account.
          </h2>
          <p className="mt-5 max-w-md text-[15.5px] leading-relaxed text-muted">
            Post a project and compare proposals, or publish a fixed-price service and sell it
            outright. Same wallet, same reputation, same protection either way.
          </p>

          <ul className="mt-12 space-y-5">
            {PROOF.map(([title, body]) => (
              <li
                key={title}
                className="glass edge-light flex gap-3.5 rounded-xl border border-line p-4"
              >
                <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                  <Icon name="check" className="size-3.5" strokeWidth={2.6} />
                </span>
                <div className="max-w-sm">
                  <p className="text-[14px] font-medium text-fg">{title}</p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
