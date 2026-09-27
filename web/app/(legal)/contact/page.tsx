import type { Metadata } from "next";
import Link from "next/link";

import { Icon, type IconName } from "@/components/ui";
import { BUSINESS, formatAddress } from "@/lib/business";

export const metadata: Metadata = {
  title: "Contact us",
  description: `How to reach ${BUSINESS.operator}, the operator of SkilRize: email, phone and business address.`,
};

const CHANNELS: Array<{ icon: IconName; label: string; value: string; href?: string; note: string }> = [
  {
    icon: "mail",
    label: "Email",
    value: BUSINESS.email,
    href: `mailto:${BUSINESS.email}`,
    note: "Answered within one business day.",
  },
  {
    icon: "phone",
    label: "Phone",
    value: BUSINESS.phone,
    href: BUSINESS.phoneHref,
    note: BUSINESS.hours,
  },
  {
    icon: "building",
    label: "Business address",
    value: formatAddress(),
    note: `${BUSINESS.operatorType}.`,
  },
];

const TOPICS: Array<{ title: string; include: string; link?: [string, string] }> = [
  {
    title: "An order, delivery or refund",
    include: "Your order number, and what went wrong. Write before the review window closes if you have not accepted a delivery.",
    link: ["Refund & Cancellation Policy", "/refunds"],
  },
  {
    title: "A payment you made",
    include: "Your order number, the amount, the date, and the Swich transaction reference from your receipt.",
    link: ["How payments work", "/#how-it-works"],
  },
  {
    title: "A payout you are waiting for",
    include: "The contract or order it was released from. Check that your payout details are complete in Settings first.",
  },
  {
    title: "Your personal data",
    include: "Put “Privacy” in the subject. You can also download or delete your data yourself.",
    link: ["Privacy & data settings", "/settings/privacy"],
  },
  {
    title: "Reporting a user or listing",
    include: "A link to the profile or listing, and what you saw.",
  },
];

export default function ContactPage() {
  return (
    <div className="grid gap-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-20">
      <div>
        <p className="eyebrow">Contact</p>
        <h1 className="display-lg mt-4">Talk to the people who run SkilRize.</h1>
        <p className="mt-5 max-w-md text-[16px] leading-relaxed text-muted">
          SkilRize is operated by {BUSINESS.operator} in {BUSINESS.address.city}. Every message is
          read by a person, not a bot.
        </p>

        <ul className="mt-10 divide-y divide-line border-y border-line">
          {CHANNELS.map((channel) => (
            <li key={channel.label} className="flex gap-4 py-5">
              <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-md bg-accent-soft text-accent">
                <Icon name={channel.icon} className="size-[18px]" />
              </span>
              <div className="min-w-0">
                <p className="eyebrow">{channel.label}</p>
                {channel.href ? (
                  <a
                    href={channel.href}
                    className="mt-1 block break-words text-[17px] font-semibold text-fg underline-offset-4 hover:underline"
                  >
                    {channel.value}
                  </a>
                ) : (
                  <p className="mt-1 text-[17px] font-semibold text-fg">{channel.value}</p>
                )}
                <p className="mt-1 text-[13.5px] text-muted">{channel.note}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <section aria-labelledby="topics">
        <h2 id="topics" className="heading-sans text-[19px]">
          So we can help on the first reply
        </h2>
        <p className="mt-2 text-[14px] text-muted">Include these details with your message.</p>
        <ul className="mt-6 space-y-3">
          {TOPICS.map((topic) => (
            <li key={topic.title} className="rounded-lg border border-line bg-raised p-5">
              <p className="font-semibold text-fg">{topic.title}</p>
              <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{topic.include}</p>
              {topic.link && (
                <Link
                  href={topic.link[1]}
                  className="mt-3 inline-block text-[13.5px] font-medium text-accent underline-offset-4 hover:underline"
                >
                  {topic.link[0]}
                </Link>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
