"use client";

import * as React from "react";
import Link from "next/link";

import { CoverArt } from "@/components/artwork";
import { PageHeading } from "@/components/shell";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Money,
  Segmented,
  Skeleton,
} from "@/components/ui";
import { orders, type GigOrder, type OrderStatus } from "@/lib/api";
import { formatRelative, useLoader } from "@/lib/session";

const TONES: Record<OrderStatus, "neutral" | "accent" | "positive" | "caution" | "critical"> = {
  pending_requirements: "caution",
  active: "accent",
  delivered: "caution",
  revision: "caution",
  completed: "positive",
  cancelled: "neutral",
};

const LABELS: Record<OrderStatus, string> = {
  pending_requirements: "Needs requirements",
  active: "In progress",
  delivered: "Delivered",
  revision: "In revision",
  completed: "Completed",
  cancelled: "Cancelled",
};

type Filter = "all" | "buyer" | "seller";

export default function OrdersPage() {
  const [role, setRole] = React.useState<Filter>("all");
  const { data, loading } = useLoader(
    () => orders.list(role === "all" ? {} : { role }),
    [role],
  );
  const rows: GigOrder[] | null = loading ? null : (data?.results ?? []);

  return (
    <>
      <PageHeading
        title="Orders"
        description="Services you have bought and services you are delivering."
        action={
          <Segmented
            label="Filter orders"
            value={role}
            onChange={setRole}
            size="sm"
            options={[
              { value: "all", label: "All" },
              { value: "buyer", label: "Buying" },
              { value: "seller", label: "Selling" },
            ]}
          />
        }
      />

      {rows === null ? (
        <div className="space-y-4">
          {[0, 1].map((row) => (
            <Card key={row} className="flex gap-4 p-4">
              <Skeleton className="h-20 w-32 shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </Card>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="wallet" className="size-5" />}
            title="No orders yet"
            description="Buy a service, or publish one of your own and wait for the first order."
            action={
              <div className="flex gap-2">
                <Link href="/gigs">
                  <Button>Browse services</Button>
                </Link>
                <Link href="/gigs/new">
                  <Button variant="secondary">Publish a service</Button>
                </Link>
              </div>
            }
          />
        </Card>
      ) : (
        <ul className="space-y-4">
          {rows.map((order) => (
            <li key={order.id}>
              <Card className="relative flex flex-wrap gap-4 p-4 transition-shadow duration-200 hover:shadow-e2">
                <div className="h-20 w-32 shrink-0 overflow-hidden rounded-md">
                  <CoverArt seed={order.gig_slug || order.gig} rounded={false} />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-[14.5px] font-semibold text-fg">
                      <Link
                        href={`/orders/${order.id}`}
                        className="rounded-sm after:absolute after:inset-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                      >
                        {order.gig_title}
                      </Link>
                    </h3>
                    <Badge tone={TONES[order.status]}>{LABELS[order.status]}</Badge>
                    <Badge>{order.my_role === "buyer" ? "You bought" : "You are selling"}</Badge>
                    {order.is_late && <Badge tone="critical">Late</Badge>}
                  </div>

                  <p className="mt-1 text-[12.5px] text-subtle">
                    {order.my_role === "buyer"
                      ? `Seller: ${order.seller_name}`
                      : `Buyer: ${order.buyer_name}`}
                    {" · "}
                    Ordered {formatRelative(order.created_at)}
                    {order.due_at && ` · due ${formatRelative(order.due_at)}`}
                  </p>

                  {order.status === "pending_requirements" && order.my_role === "buyer" && (
                    <p className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-caution-soft px-2.5 py-1 text-[12px] text-caution">
                      <Icon name="file" className="size-3" />
                      Submit your requirements to start the clock
                    </p>
                  )}
                </div>

                <div className="shrink-0 text-right">
                  <p className="text-[16px] font-semibold text-fg">
                    <Money amount={order.price} />
                  </p>
                  <p className="text-[12px] text-subtle">
                    {order.revisions_left} of {order.revisions_allowed} revisions left
                  </p>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
