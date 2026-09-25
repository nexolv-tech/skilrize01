/**
 * The public footer.
 *
 * Carries what a buyer — and a payment network's reviewer — looks for before
 * paying anyone: who operates the site, where they are, how to reach them,
 * and every policy that governs a purchase. Rendered on the landing page, the
 * legal pages, and every public marketplace page.
 */

import Link from "next/link";

import { Logo } from "@/components/ui";
import { BUSINESS } from "@/lib/business";

const COLUMNS: Array<{ heading: string; links: Array<[string, string]> }> = [
  {
    heading: "Marketplace",
    links: [
      ["Browse services", "/gigs"],
      ["Open briefs", "/projects"],
      ["Post a brief", "/projects/new"],
      ["Sell a service", "/gigs/new"],
      ["Plans and fees", "/pricing"],
    ],
  },
  {
    heading: "Company",
    links: [
      ["About SkilRize", "/about"],
      ["Contact us", "/contact"],
      ["How payments work", "/#how-it-works"],
      ["Campus portals", "/#campus"],
    ],
  },
  {
    heading: "Legal",
    links: [
      ["Terms of Service", "/terms"],
      ["Privacy Policy", "/privacy"],
      ["Refund & Cancellation", "/refunds"],
      ["Service Delivery", "/delivery"],
      ["Cookie Policy", "/cookies"],
    ],
  },
];

export function SiteFooter() {
  const a = BUSINESS.address;
  return (
    <footer className="border-t border-line bg-raised">
      <div className="mx-auto max-w-7xl px-5 py-14">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-[13.5px] leading-relaxed text-muted">
              A freelance marketplace where every payment is held in escrow until the work is
              approved.
            </p>
            <address className="mt-5 space-y-1 text-[13px] not-italic leading-relaxed text-muted">
              <span className="block font-semibold text-fg">{BUSINESS.operator}</span>
              <span className="block">
                {a.line1}, {a.line2}
              </span>
              <span className="block">
                {a.city}, {a.region}, {a.country}
              </span>
              <a
                href={`mailto:${BUSINESS.email}`}
                className="block text-accent underline-offset-4 hover:underline"
              >
                {BUSINESS.email}
              </a>
              <a href={BUSINESS.phoneHref} className="block text-accent underline-offset-4 hover:underline">
                {BUSINESS.phone}
              </a>
            </address>
          </div>

          {COLUMNS.map((column) => (
            <nav key={column.heading} aria-label={column.heading}>
              <p className="eyebrow">{column.heading}</p>
              <ul className="mt-4 space-y-2.5">
                {column.links.map(([label, href]) => (
                  <li key={href}>
                    <Link
                      href={href}
                      className="text-[13.5px] text-muted transition-colors duration-150 hover:text-fg"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-6 text-[12.5px] text-subtle">
          <p>
            © {new Date().getFullYear()} {BUSINESS.product} · Operated by {BUSINESS.operator},{" "}
            {a.city}, {a.country}
          </p>
          <p>All prices in {BUSINESS.currency}</p>
        </div>
      </div>
    </footer>
  );
}
