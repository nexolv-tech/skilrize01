"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  ActionWithInput,
  AdminHeading,
  AdminList,
  AdminTabs,
  PersonLink,
  QuickAction,
  StateSwitch,
  StatusText,
} from "@/components/admin";
import { Alert, Button, Money, Skeleton } from "@/components/ui";
import {
  admin,
  type AdminBankDetails,
  type AdminPayout,
  type AdminPlanPayment,
  type AdminRefund,
  type AdminTransfer,
} from "@/lib/api";
import { formatRelative, useLoader } from "@/lib/session";

type Tab = "transfers" | "plans" | "payouts" | "refunds";
type State = "todo" | "done";

const STATES: Array<{ value: State; label: string }> = [
  { value: "todo", label: "To do" },
  { value: "done", label: "Done" },
];

/* -------------------------------------------------------------------------- */
/* Bank details, shown only on request                                        */
/* -------------------------------------------------------------------------- */

function BankDetails({
  load,
  ready,
  missing,
}: {
  load: () => Promise<AdminBankDetails>;
  ready: boolean;
  missing: string;
}) {
  const [details, setDetails] = React.useState<AdminBankDetails | null>(null);
  const [pending, setPending] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  if (!ready) return <p className="text-[12.5px] text-caution">{missing}</p>;
  if (!details) {
    return (
      <Button
        size="sm"
        variant="ghost"
        loading={pending}
        onClick={async () => {
          setPending(true);
          try {
            setDetails(await load());
          } finally {
            setPending(false);
          }
        }}
      >
        Show bank details
      </Button>
    );
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg border border-line bg-sunken/60 p-3 text-[13px]">
      <dt className="text-muted">Bank</dt>
      <dd className="text-fg">{details.bank_name}</dd>
      <dt className="text-muted">Account title</dt>
      <dd className="text-fg">{details.account_title}</dd>
      <dt className="text-muted">Account number</dt>
      <dd className="flex flex-wrap items-center gap-2">
        <span className="figure text-fg">{details.account_number}</span>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(details.account_number ?? "");
            setCopied(true);
          }}
          className="text-[12px] font-medium text-accent underline-offset-4 hover:underline"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </dd>
      {details.cnic_last4 && (
        <>
          <dt className="text-muted">CNIC</dt>
          <dd className="figure text-fg">•••• {details.cnic_last4}</dd>
        </>
      )}
      {details.mobile_wallet && (
        <>
          <dt className="text-muted">Mobile wallet</dt>
          <dd className="figure text-fg">{details.mobile_wallet}</dd>
        </>
      )}
      <dd className="col-span-2 pt-1 text-[12px] text-subtle">
        Viewing these is recorded in the audit log.
      </dd>
    </dl>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="space-y-3 p-5">{children}</div>;
}

function Headline({ amount, title, sub }: { amount: string; title: string; sub?: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <p className="text-[14.5px] font-medium text-fg">
        {title}
        {sub && <span className="font-normal text-muted"> · {sub}</span>}
      </p>
      <Money amount={amount} className="figure text-[16px] font-semibold text-fg" />
    </div>
  );
}

function Where({ contractId, orderId }: { contractId: number; orderId: number | null }) {
  return (
    <span className="text-subtle">
      {orderId ? `Order #${orderId}` : `Contract #${contractId}`}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Tabs                                                                       */
/* -------------------------------------------------------------------------- */

function TransfersTab({ state }: { state: State }) {
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.transfers(state === "todo" ? "unconfirmed" : "confirmed", page),
    [state, page],
  );
  return (
    <AdminList
      data={list.data}
      loading={list.loading}
      page={page}
      onPage={setPage}
      empty={{
        title: state === "todo" ? "Every payment is confirmed" : "No confirmed payments yet",
        description:
          state === "todo"
            ? "New ones appear here when a buyer says they have sent a bank transfer."
            : undefined,
      }}
    >
      {(row: AdminTransfer) => (
        <Row key={row.id}>
          <Headline amount={row.amount} title={row.title} sub={row.milestone} />
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
            <PersonLink person={row.payer} label="From" />
            <PersonLink person={row.payee} label="For" />
          </p>
          <p className="text-[13px] text-muted">
            Reference:{" "}
            <span className="font-medium text-fg">{row.reference_note || "none given"}</span> ·
            reported {formatRelative(row.reported_at)} · <Where contractId={row.contract_id} orderId={row.order_id} />
          </p>
          {row.confirmed_at ? (
            <StatusText tone="positive">
              {row.confirmed_by
                ? `Confirmed ${formatRelative(row.confirmed_at)} by ${row.confirmed_by.name}`
                : `Received through Swich ${formatRelative(row.confirmed_at)}`}
            </StatusText>
          ) : (
            <div className="flex flex-wrap items-start gap-2">
              <QuickAction
                label="It arrived"
                variant="primary"
                icon="check"
                onRun={async () => {
                  await admin.confirmTransfer(row.id);
                  await list.reload();
                }}
              />
              <ActionWithInput
                label="Not received"
                confirmLabel={row.order_id ? "Cancel the order" : "Mark as unpaid"}
                tone="danger"
                required={false}
                prompt={
                  row.order_id
                    ? "The order is cancelled and both sides are told. Add a note for the record (optional)."
                    : "The milestone goes back to awaiting payment and both sides are told. Add a note (optional)."
                }
                placeholder="e.g. Nothing on the statement after 3 working days"
                onConfirm={async (note) => {
                  await admin.transferNotReceived(row.id, note);
                  await list.reload();
                }}
              />
            </div>
          )}
        </Row>
      )}
    </AdminList>
  );
}

function PlansTab({ state }: { state: State }) {
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.planPayments(state === "todo" ? "unconfirmed" : "confirmed", page),
    [state, page],
  );
  return (
    <AdminList
      data={list.data}
      loading={list.loading}
      page={page}
      onPage={setPage}
      empty={{ title: state === "todo" ? "No plan payments to confirm" : "None confirmed yet" }}
    >
      {(row: AdminPlanPayment) => (
        <Row key={row.id}>
          <Headline amount={row.amount} title={row.plan} sub={row.interval} />
          <p className="text-[13px]">
            <PersonLink person={row.payer} label="From" />
          </p>
          <p className="text-[13px] text-muted">
            Reference:{" "}
            <span className="font-medium text-fg">{row.reference_note || "none given"}</span> ·
            reported {formatRelative(row.reported_at)}
          </p>
          {row.confirmed_at ? (
            <StatusText tone="positive">
              {row.confirmed_by
                ? `Confirmed ${formatRelative(row.confirmed_at)} by ${row.confirmed_by.name}`
                : `Received through Swich ${formatRelative(row.confirmed_at)}`}
            </StatusText>
          ) : (
            <div className="flex flex-wrap items-start gap-2">
              <QuickAction
                label="It arrived"
                variant="primary"
                icon="check"
                onRun={async () => {
                  await admin.confirmPlanPayment(row.id);
                  await list.reload();
                }}
              />
              <ActionWithInput
                label="Not received"
                confirmLabel="Cancel the plan"
                tone="danger"
                required={false}
                prompt="The plan is cancelled at once and the member is told. Add a note (optional)."
                onConfirm={async (note) => {
                  await admin.planPaymentNotReceived(row.id, note);
                  await list.reload();
                }}
              />
            </div>
          )}
        </Row>
      )}
    </AdminList>
  );
}

/** What Swich said the last time, when it did not go through. */
function SwichProblem({ message }: { message: string }) {
  if (!message) return null;
  return (
    <Alert tone="caution" title="Not sent through Swich">
      {message}
    </Alert>
  );
}

function PayoutsTab({ state, viaSwich }: { state: State; viaSwich: boolean }) {
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.payouts(state === "todo" ? "pending" : "paid", page),
    [state, page],
  );
  return (
    <AdminList
      data={list.data}
      loading={list.loading}
      page={page}
      onPage={setPage}
      empty={{
        title: state === "todo" ? "No payouts waiting" : "No payouts sent yet",
        description:
          state === "todo" ? "A payout appears when a buyer approves the work." : undefined,
      }}
    >
      {(row: AdminPayout) => (
        <Row key={row.id}>
          <Headline amount={row.net_amount} title={row.title} sub={row.milestone} />
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
            <PersonLink person={row.freelancer} label="To" />
          </p>
          <p className="text-[13px] text-muted">
            <Money amount={row.gross_amount} /> released, less {row.commission_percent}%
            commission (<Money amount={row.commission_amount} />) ·{" "}
            <Where contractId={row.contract_id} orderId={row.order_id} /> · approved{" "}
            {formatRelative(row.created_at)}
          </p>
          {row.status === "paid" ? (
            <StatusText tone="positive">
              Sent {row.paid_at ? formatRelative(row.paid_at) : ""}{" "}
              {row.paid_by ? `by ${row.paid_by.name}` : "through Swich"} · reference {row.note}
            </StatusText>
          ) : (
            <div className="space-y-3">
              {row.destination && (
                <p className="text-[13px] text-muted">
                  To <span className="font-medium text-fg">{row.destination}</span>
                  {row.swich_ready ? ", which Swich pays." : ", which is not on Swich's list: send it by hand."}
                </p>
              )}
              <SwichProblem message={row.last_error} />
              <BankDetails
                ready={row.bank_details_ready}
                load={() => admin.payoutBankDetails(row.id)}
                missing="No bank details yet. The freelancer adds them under Settings → Payouts; they have been told they are owed."
              />
              <div className="flex flex-wrap items-start gap-2">
                {viaSwich && row.swich_ready && (
                  <QuickAction
                    label={row.last_error ? "Try Swich again" : "Send through Swich"}
                    variant="primary"
                    icon="send"
                    onRun={async () => {
                      await admin.sendPayoutViaSwich(row.id);
                      await list.reload();
                    }}
                  />
                )}
                <ActionWithInput
                  label="Mark as paid"
                  confirmLabel="Record payment"
                  tone="primary"
                  singleLine
                  prompt="Transfer reference from your bank's receipt. The freelancer is told it was sent."
                  placeholder="e.g. IBFT 8821 3310"
                  onConfirm={async (reference) => {
                    await admin.markPayoutPaid(row.id, reference);
                    await list.reload();
                  }}
                />
              </div>
            </div>
          )}
        </Row>
      )}
    </AdminList>
  );
}

function RefundsTab({ state, viaSwich }: { state: State; viaSwich: boolean }) {
  const [page, setPage] = React.useState(1);
  const list = useLoader(
    () => admin.refunds(state === "todo" ? "pending" : "refunded", page),
    [state, page],
  );
  return (
    <AdminList
      data={list.data}
      loading={list.loading}
      page={page}
      onPage={setPage}
      empty={{ title: state === "todo" ? "No refunds waiting" : "No refunds sent yet" }}
    >
      {(row: AdminRefund) => (
        <Row key={row.id}>
          <Headline amount={row.amount} title={row.title} sub={row.milestone} />
          <p className="text-[13px]">
            <PersonLink person={row.client} label="To" />
          </p>
          <p className="text-[13px] text-muted">
            {row.reason} · <Where contractId={row.contract_id} orderId={row.order_id} /> ·{" "}
            {formatRelative(row.created_at)}
          </p>
          {row.status === "refunded" ? (
            <StatusText tone="positive">
              Sent {row.refunded_at ? formatRelative(row.refunded_at) : ""}{" "}
              {row.refunded_by ? `by ${row.refunded_by.name}` : "through Swich"} · {row.note}
            </StatusText>
          ) : (
            <div className="space-y-3">
              <SwichProblem message={row.last_error} />
              {viaSwich && (
                <QuickAction
                  label={row.last_error ? "Try Swich again" : "Refund through Swich"}
                  variant="primary"
                  icon="send"
                  onRun={async () => {
                    await admin.sendRefundViaSwich(row.id);
                    await list.reload();
                  }}
                />
              )}
              <BankDetails
                ready={row.bank_details_ready}
                load={() => admin.refundBankDetails(row.id)}
                missing="This buyer has no bank details on file. Email them for the account to refund to, or reverse the original transfer from your bank."
              />
              <ActionWithInput
                label="Mark as sent"
                confirmLabel="Record refund"
                tone="primary"
                singleLine
                prompt="Transfer reference from your bank's receipt. The buyer is told it was sent."
                placeholder="e.g. IBFT 8821 3310"
                onConfirm={async (reference) => {
                  await admin.markRefundSent(row.id, reference);
                  await list.reload();
                }}
              />
            </div>
          )}
        </Row>
      )}
    </AdminList>
  );
}

/* -------------------------------------------------------------------------- */

function PaymentsContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const requested = params.get("tab");
  const tab: Tab =
    requested === "plans" || requested === "payouts" || requested === "refunds"
      ? requested
      : "transfers";
  const [state, setState] = React.useState<State>("todo");
  const { data: overview } = useLoader(() => admin.overview(), [tab]);
  const queues = overview?.queues ?? {};

  return (
    <>
      <AdminHeading
        title="Payments"
        description="Buyers pay through Swich by card, Easypaisa, JazzCash or 1Bill, and each payment is confirmed automatically. Payouts to freelancers and refunds to buyers are sent from your bank or Swich account and recorded here."
        action={<StateSwitch value={state} onChange={setState} options={STATES} />}
      />
      <AdminTabs
        label="Payments"
        value={tab}
        onChange={(next) => {
          setState("todo");
          router.replace(next === "transfers" ? pathname : `${pathname}?tab=${next}`, {
            scroll: false,
          });
        }}
        tabs={[
          { value: "transfers", label: "Payments in", count: queues.transfers || undefined },
          { value: "plans", label: "Plans" },
          { value: "payouts", label: "Payouts", count: queues.payouts },
          { value: "refunds", label: "Refunds", count: queues.refunds },
        ]}
      />
      {tab === "transfers" && (
        <Alert tone="neutral" className="mb-5">
          Payments made through Swich arrive here already confirmed, under Done. To do lists only
          payments recorded by hand, such as a milestone an admin marked funded, until you match
          each against your statement.
        </Alert>
      )}
      {tab === "transfers" && <TransfersTab key={state} state={state} />}
      {tab === "plans" && <PlansTab key={state} state={state} />}
      {tab === "payouts" && (
        <PayoutsTab key={state} state={state} viaSwich={Boolean(overview?.swich_payouts)} />
      )}
      {tab === "refunds" && (
        <RefundsTab key={state} state={state} viaSwich={Boolean(overview?.swich_payouts)} />
      )}
    </>
  );
}

export default function AdminPaymentsPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <PaymentsContent />
    </React.Suspense>
  );
}
