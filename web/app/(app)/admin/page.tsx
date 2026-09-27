"use client";

import * as React from "react";
import Link from "next/link";

import { AdminHeading, Figure } from "@/components/admin";
import { Card, Icon, Money, Skeleton, cn, type IconName } from "@/components/ui";
import { admin, type AdminOverview } from "@/lib/api";
import { useLoader } from "@/lib/session";

interface Queue {
  key: keyof AdminOverview["queues"];
  label: string;
  href: string;
  icon: IconName;
  total?: keyof AdminOverview["queues"];
  hint: string;
}

/** Oldest-first work queues, in the order money and people are waiting. */
const QUEUES: Queue[] = [
  {
    key: "transfers",
    label: "Payments to confirm",
    href: "/admin/payments",
    icon: "wallet",
    hint: "Recorded by hand: match each against the statement.",
  },
  {
    key: "payouts",
    label: "Payouts to send",
    href: "/admin/payments?tab=payouts",
    icon: "send",
    total: "payouts_total",
    hint: "Freelancers whose work was approved.",
  },
  {
    key: "refunds",
    label: "Refunds to send",
    href: "/admin/payments?tab=refunds",
    icon: "arrowRight",
    total: "refunds_total",
    hint: "Buyers owed money back.",
  },
  {
    key: "identity",
    label: "Identity checks",
    href: "/admin/verifications",
    icon: "id",
    hint: "CNIC photos waiting for a decision.",
  },
  {
    key: "students",
    label: "Student checks",
    href: "/admin/verifications?tab=students",
    icon: "building",
    hint: "Student ID cards waiting for a decision.",
  },
  {
    key: "reports",
    label: "Reports",
    href: "/admin/reports",
    icon: "megaphone",
    hint: "Community content flagged by members.",
  },
];

function QueueCard({ queue, overview }: { queue: Queue; overview: AdminOverview }) {
  const count = Number(overview.queues[queue.key] ?? 0);
  const total = queue.total ? overview.queues[queue.total] : undefined;
  return (
    <Link
      href={queue.href}
      className={cn(
        "group flex items-start gap-3 rounded-lg border p-4 transition-colors duration-150",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        count > 0
          ? "border-action/50 bg-action/[0.06] hover:border-action"
          : "border-line bg-raised hover:border-fg/40",
      )}
    >
      <span
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-md",
          count > 0 ? "bg-action text-on-action" : "bg-sunken text-muted",
        )}
      >
        <Icon name={queue.icon} className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="text-[13.5px] font-medium text-fg">{queue.label}</span>
          <span className="figure text-[20px] font-semibold text-fg">{count}</span>
        </span>
        <span className="mt-0.5 block text-[12.5px] text-muted">
          {count > 0 && total ? (
            <>
              <Money amount={total} className="figure" /> in all
            </>
          ) : count > 0 ? (
            queue.hint
          ) : (
            "Nothing waiting."
          )}
        </span>
      </span>
    </Link>
  );
}

export default function AdminOverviewPage() {
  const { data, loading } = useLoader(() => admin.overview(), []);
  const queues = QUEUES.filter((queue) => data && queue.key in data.queues);
  const waiting = queues.reduce((sum, queue) => sum + Number(data?.queues[queue.key] ?? 0), 0);

  return (
    <>
      <AdminHeading
        title="Overview"
        description={
          loading
            ? "Loading…"
            : waiting > 0
              ? `${waiting} ${waiting === 1 ? "item needs" : "items need"} someone today, oldest first in each queue.`
              : "Nothing is waiting in your queues."
        }
      />

      {!data ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((slot) => (
            <Skeleton key={slot} className="h-[84px] w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {queues.length > 0 && (
            <section>
              <h2 className="eyebrow mb-3">Needs attention</h2>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {queues.map((queue) => (
                  <QueueCard key={queue.key} queue={queue} overview={data} />
                ))}
              </div>
            </section>
          )}

          {data.figures.escrow_held !== undefined && (
            <section>
              <h2 className="eyebrow mb-3">Money</h2>
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                <Figure
                  label="Held in escrow"
                  value={<Money amount={data.figures.escrow_held} />}
                  hint="Funded work not yet released."
                />
                <Figure
                  label="Paid in this month"
                  value={<Money amount={data.figures.paid_in_this_month} />}
                  hint="Reported by buyers."
                />
                <Figure
                  label="Commission this month"
                  value={<Money amount={data.figures.commission_this_month} />}
                />
                <Figure
                  label="Commission all time"
                  value={<Money amount={data.figures.commission_all_time} />}
                />
              </div>
            </section>
          )}

          <section>
            <h2 className="eyebrow mb-3">The marketplace</h2>
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
              <Figure
                label="Members"
                value={data.figures.users.toLocaleString()}
                hint={`${data.figures.users_this_week} joined this week`}
              />
              <Figure label="Live services" value={data.figures.services_live} />
              <Figure label="Open briefs" value={data.figures.briefs_open} />
              <Figure label="Orders in progress" value={data.figures.orders_in_progress} />
              <Figure label="Active contracts" value={data.figures.contracts_active} />
            </div>
          </section>

          <Card className="p-5 text-[13px] leading-relaxed text-muted">
            Every action in this console is recorded in the audit log with who took it and why,
            and the person it affects is told. Payouts and refunds are sent from the bank; the
            console records that they were.
          </Card>
        </div>
      )}
    </>
  );
}
