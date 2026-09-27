"use client";

import * as React from "react";

import {
  ActionWithInput,
  AdminHeading,
  AdminList,
  FilterBar,
  PersonLink,
  StatusText,
  canSee,
} from "@/components/admin";
import { Badge, Money } from "@/components/ui";
import { admin, type AdminOrder, type AdminRole, type OrderStatus } from "@/lib/api";
import { formatRelative, useLoader, useSession } from "@/lib/session";

type Filter = "" | OrderStatus;

const CHIPS: Array<{ value: Filter; label: string }> = [
  { value: "", label: "All" },
  { value: "awaiting_payment", label: "Awaiting payment" },
  { value: "pending_requirements", label: "Waiting for requirements" },
  { value: "active", label: "In progress" },
  { value: "delivered", label: "Delivered" },
  { value: "revision", label: "In revision" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const STATUS_LABEL: Record<OrderStatus, string> = {
  awaiting_payment: "Awaiting payment",
  pending_requirements: "Waiting for requirements",
  active: "In progress",
  delivered: "Delivered",
  revision: "In revision",
  completed: "Completed",
  cancelled: "Cancelled",
};

const PAYMENT: Record<AdminOrder["payment"], { label: string; tone: "positive" | "caution" | "muted" }> = {
  confirmed: { label: "Payment confirmed", tone: "positive" },
  reported: { label: "Payment reported, not yet confirmed", tone: "caution" },
  none: { label: "No payment recorded", tone: "muted" },
};

function OrderRow({
  row,
  canVoid,
  onChanged,
}: {
  row: AdminOrder;
  canVoid: boolean;
  onChanged: () => void;
}) {
  const payment = PAYMENT[row.payment];
  const voidable =
    canVoid &&
    row.payment !== "confirmed" &&
    (row.status === "pending_requirements" || row.status === "active");
  return (
    <div className="space-y-1.5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[14px] font-medium text-fg">
          <span className="figure text-subtle">#{row.id}</span> {row.title}
        </p>
        <Money amount={row.price} className="figure text-[15px] font-semibold text-fg" />
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
        <PersonLink person={row.buyer} label="Buyer" />
        <PersonLink person={row.seller} label="Seller" />
      </p>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-muted">
        <Badge tone={row.status === "cancelled" ? "neutral" : row.status === "completed" ? "positive" : "accent"}>
          {STATUS_LABEL[row.status]}
        </Badge>
        <StatusText tone={payment.tone}>{payment.label}</StatusText>
        <span>ordered {formatRelative(row.created_at)}</span>
        {row.due_at && <span>due {formatRelative(row.due_at)}</span>}
      </p>
      {voidable && (
        <div className="pt-1">
          <ActionWithInput
            label="Cancel: payment not received"
            confirmLabel="Cancel the order"
            tone="danger"
            required={false}
            prompt="Use this only when the buyer's transfer never arrived. Both sides are told; no refund is recorded. Add a note (optional)."
            onConfirm={async (note) => {
              await admin.voidOrder(row.id, note);
              onChanged();
            }}
          />
        </div>
      )}
    </div>
  );
}

export default function AdminOrdersPage() {
  const { user } = useSession();
  const role = (user?.admin_role ?? "") as AdminRole;
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState<Filter>("");
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.orders({ q: query || undefined, status: filter || undefined, page }),
    [query, filter, page],
  );

  return (
    <>
      <AdminHeading
        title="Orders"
        description="Every service order, with where its payment stands. Search by order number, service, buyer or seller."
      />
      <FilterBar
        query={query}
        onQuery={(next) => {
          setQuery(next);
          setPage(1);
        }}
        placeholder="Order number, service or person"
        chips={CHIPS}
        value={filter}
        onChip={(next) => {
          setFilter(next);
          setPage(1);
        }}
      />
      <AdminList
        data={list.data}
        loading={list.loading}
        page={page}
        onPage={setPage}
        empty={{ icon: "search", title: "No orders match" }}
      >
        {(row: AdminOrder) => (
          <OrderRow
            key={row.id}
            row={row}
            canVoid={canSee(role, ["finance_admin"])}
            onChanged={() => void list.reload()}
          />
        )}
      </AdminList>
    </>
  );
}
