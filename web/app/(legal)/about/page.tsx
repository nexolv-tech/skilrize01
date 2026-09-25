import type { Metadata } from "next";
import Link from "next/link";

import { ButtonLink, Icon, type IconName } from "@/components/ui";
import { BUSINESS, formatAddress } from "@/lib/business";

export const metadata: Metadata = {
  title: "About",
  description: `SkilRize is a Pakistani freelance marketplace, operated by ${BUSINESS.operator}, where every payment is held in escrow until the work is approved.`,
};

const PRINCIPLES: Array<{ icon: IconName; title: string; body: string }> = [
  {
    icon: "shield",
    title: "The money waits for the work",
    body: "A buyer's payment is held in escrow, not sent to the freelancer. It is released when the buyer approves the delivery, and refunded in full if the order is cancelled.",
  },
  {
    icon: "id",
    title: "Everyone who moves money is verified",
    body: "Buying, selling and bidding all require a verified email address and national identity card. Two-factor sign-in is available to everyone.",
  },
  {
    icon: "wallet",
    title: "Rupees in, rupees out",
    body: `Prices, payments and payouts are in ${BUSINESS.currency}. Buyers pay the listed price; freelancers pay a flat ${BUSINESS.commissionPercent}% fee, shown before anything is released.`,
  },
  {
    icon: "book",
    title: "A first step for students",
    body: "Verified university students get a campus portal — the same marketplace, private to their university — so a first client can be a classmate or a department.",
  },
];

export default function AboutPage() {
  return (
    <div className="space-y-20">
      <header className="max-w-3xl">
        <p className="eyebrow">About SkilRize</p>
        <h1 className="display-xl mt-4">A marketplace where the money waits for the work.</h1>
        <p className="mt-6 max-w-2xl text-[17px] leading-relaxed text-muted">
          Hiring a freelancer in Pakistan usually means one side takes the risk: the client pays a
          stranger up front, or the freelancer works first and hopes to be paid. SkilRize removes
          that choice. The payment is made before the work starts, and held until it is approved.
        </p>
      </header>

      <section aria-labelledby="principles">
        <h2 id="principles" className="display-md">
          How it is built
        </h2>
        <ul className="mt-8 grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2">
          {PRINCIPLES.map((item) => (
            <li key={item.title} className="bg-surface p-6 sm:p-8">
              <Icon name={item.icon} className="size-5 text-accent" />
              <h3 className="heading-sans mt-4 text-[18px]">{item.title}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-muted">{item.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-labelledby="operator"
        className="grid gap-10 rounded-lg border border-line bg-raised p-6 sm:p-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]"
      >
        <div>
          <h2 id="operator" className="display-md">
            Who runs it
          </h2>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
            SkilRize is built and operated by {BUSINESS.operator}, a software business in{" "}
            {BUSINESS.address.city}. {BUSINESS.operator} holds buyers&apos; payments in escrow,
            sends freelancers their payouts, and answers every support message itself.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <ButtonLink href="/contact">Contact us</ButtonLink>
            <ButtonLink href="/terms" variant="secondary">
              Read the terms
            </ButtonLink>
          </div>
        </div>
        <dl className="grid gap-4 text-[14px]">
          <div>
            <dt className="eyebrow">Operator</dt>
            <dd className="mt-1 font-semibold text-fg">{BUSINESS.operator}</dd>
            <dd className="text-muted">{BUSINESS.operatorType}</dd>
          </div>
          <div>
            <dt className="eyebrow">Proprietor</dt>
            <dd className="mt-1 text-fg">{BUSINESS.proprietor}</dd>
          </div>
          <div>
            <dt className="eyebrow">Address</dt>
            <dd className="mt-1 text-fg">{formatAddress()}</dd>
          </div>
          <div>
            <dt className="eyebrow">Reach us</dt>
            <dd className="mt-1">
              <a href={`mailto:${BUSINESS.email}`} className="text-accent underline-offset-4 hover:underline">
                {BUSINESS.email}
              </a>
              <span className="text-subtle"> · </span>
              <a href={BUSINESS.phoneHref} className="text-accent underline-offset-4 hover:underline">
                {BUSINESS.phone}
              </a>
            </dd>
          </div>
        </dl>
      </section>

      <p className="text-[14px] text-muted">
        Ready to start?{" "}
        <Link href="/gigs" className="font-medium text-accent underline-offset-4 hover:underline">
          Browse services
        </Link>{" "}
        or{" "}
        <Link href="/projects/new" className="font-medium text-accent underline-offset-4 hover:underline">
          post a brief
        </Link>
        .
      </p>
    </div>
  );
}
