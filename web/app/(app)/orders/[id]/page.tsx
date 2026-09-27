"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  Alert,
  Button,
  ButtonLink,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Icon,
  Money,
  Skeleton,
  Textarea,
  cn,
} from "@/components/ui";
import { SwichPay } from "@/components/payments";
import { orders, type GigOrder, type OrderStatus } from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader } from "@/lib/session";

const STEPS: Array<{ status: OrderStatus; label: string }> = [
  { status: "awaiting_payment", label: "Payment" },
  { status: "pending_requirements", label: "Requirements" },
  { status: "active", label: "In progress" },
  { status: "delivered", label: "Delivered" },
  { status: "completed", label: "Complete" },
];

/** An order placed but not paid for: the seller cannot see it yet. */
function AwaitingPayment({ order }: { order: GigOrder }) {
  const pay = useAsyncAction(() => orders.pay(order.id));
  return (
    <Card>
      <CardHeader
        title="Complete your payment"
        description="Your order is saved, but the seller only sees it once the payment goes through. If you left Swich's page or the payment was declined, try again below. Unpaid orders close after 48 hours; nothing is charged."
      />
      <div className="space-y-4 p-5">
        <SwichPay
          amount={order.price}
          label="Pay now"
          error={pay.error}
          onStart={() => pay.run()}
        />
      </div>
    </Card>
  );
}

function Progress({ order }: { order: GigOrder }) {
  const index = STEPS.findIndex((step) => step.status === order.status);
  // A revision loops back to "in progress" rather than inventing a fifth step.
  const inProgress = STEPS.findIndex((step) => step.status === "active");
  const current = order.status === "revision" ? inProgress : index === -1 ? 0 : index;

  return (
    <ol className="flex items-center gap-2">
      {STEPS.map((step, position) => {
        const done = position < current;
        const active = position === current;
        return (
          <li key={step.status} className="flex flex-1 items-center gap-2">
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <span
                className={cn(
                  "h-1 rounded-full transition-colors duration-300",
                  done ? "bg-positive" : active ? "bg-accent" : "bg-sunken",
                )}
              />
              <span
                className={cn(
                  "truncate text-[11.5px]",
                  active ? "font-medium text-fg" : "text-subtle",
                )}
              >
                {step.label}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* -------------------------------------------------------------------------- */

export default function OrderWorkspacePage() {
  const params = useParams<{ id: string }>();
  const { data: order, loading, setData } = useLoader(
    () => orders.detail(params.id),
    [params.id],
  );

  const [answers, setAnswers] = React.useState<Record<string, string>>({});
  const [note, setNote] = React.useState("");
  const [files, setFiles] = React.useState<File[]>([]);
  const [revisionNote, setRevisionNote] = React.useState("");
  const [revising, setRevising] = React.useState(false);

  const submitRequirements = useAsyncAction(async () => {
    setData(await orders.submitRequirements(order!.id, answers));
  });
  const deliver = useAsyncAction(async () => {
    setData(await orders.deliver(order!.id, note, files));
    setNote("");
    setFiles([]);
  });
  const requestRevision = useAsyncAction(async () => {
    setData(await orders.requestRevision(order!.id, revisionNote));
    setRevisionNote("");
    setRevising(false);
  });
  const accept = useAsyncAction(async () => {
    setData(await orders.accept(order!.id));
  });
  const [confirmingCancel, setConfirmingCancel] = React.useState(false);
  const cancel = useAsyncAction(async () => {
    setData(await orders.cancel(order!.id));
    setConfirmingCancel(false);
  });

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!order) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="wallet" className="size-5" />}
          title="Order not available"
          description="You are not a party to this order, or it no longer exists."
          action={
            <ButtonLink href="/orders" variant="secondary">
              Back to orders
            </ButtonLink>
          }
        />
      </Card>
    );
  }

  const isBuyer = order.my_role === "buyer";
  const snapshot = order.package_snapshot as {
    name?: string;
    tier?: string;
    features?: string[];
    extras?: Array<{ title: string; price: string }>;
  };

  return (
    <>
      <Link
        href="/orders"
        className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-muted transition-colors hover:text-fg"
      >
        <Icon name="chevronLeft" className="size-3.5" />
        All orders
      </Link>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex flex-wrap items-start gap-4">
              <div className="min-w-0 flex-1">
                <h1 className="text-[20px] font-semibold leading-tight tracking-[-0.02em] text-fg">
                  <Link href={`/gigs/${order.gig}`} className="underline-offset-2 hover:underline">
                    {order.gig_title}
                  </Link>
                </h1>
                <p className="mt-1 text-[12.5px] text-subtle">
                  Order #{order.id} ·{" "}
                  {isBuyer ? `from ${order.seller_name}` : `for ${order.buyer_name}`}
                  {order.due_at && ` · due ${formatRelative(order.due_at)}`}
                </p>
              </div>
              <p className="shrink-0 text-[20px] font-semibold text-fg">
                <Money amount={order.price} />
              </p>
            </div>

            <div className="mt-6">
              <Progress order={order} />
            </div>

            {order.is_late && order.status !== "completed" && (
              <Alert tone="critical" className="mt-5">
                This order is past its delivery date.
              </Alert>
            )}
          </Card>

          {/* --- Unpaid: the order waits for Swich --- */}
          {order.status === "awaiting_payment" && isBuyer && (
            <AwaitingPayment order={order} />
          )}

          {/* --- The requirements gate --- */}
          {order.status === "pending_requirements" &&
            (isBuyer ? (
              <Card>
                <CardHeader
                  title="Tell the seller what you need"
                  description="The delivery clock does not start until you submit this — so take a moment and be specific."
                />
                <form
                  className="space-y-5 p-5"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void submitRequirements.run();
                  }}
                >
                  {submitRequirements.error && (
                    <Alert tone="critical">{submitRequirements.error}</Alert>
                  )}

                  {order.requirements_form.length === 0 && (
                    <p className="text-[13px] text-muted">
                      This seller asked no specific questions. Add anything useful below.
                    </p>
                  )}

                  {order.requirements_form.map((field) => (
                    <Field
                      key={field.key}
                      label={field.label}
                      htmlFor={field.key}
                      required={field.required !== false}
                    >
                      <Textarea
                        id={field.key}
                        rows={3}
                        required={field.required !== false}
                        value={answers[field.key] ?? ""}
                        onChange={(event) =>
                          setAnswers((current) => ({ ...current, [field.key]: event.target.value }))
                        }
                      />
                    </Field>
                  ))}

                  <Button type="submit" size="lg" loading={submitRequirements.pending}>
                    Submit and start the clock
                  </Button>
                </form>
              </Card>
            ) : (
              <Alert tone="caution" title="Waiting on the buyer">
                Your delivery clock has not started. It begins when {order.buyer_name} submits the
                requirements — you are not late in the meantime.
              </Alert>
            ))}

          {/* --- Submitted requirements --- */}
          {Object.keys(order.requirements_answers).length > 0 && (
            <Card>
              <CardHeader title="Requirements" />
              <dl className="divide-y divide-line">
                {order.requirements_form.map((field) => (
                  <div key={field.key} className="px-5 py-3.5">
                    <dt className="text-[12.5px] font-medium text-subtle">{field.label}</dt>
                    <dd className="mt-1 whitespace-pre-wrap text-[13.5px] text-fg">
                      {order.requirements_answers[field.key] || "—"}
                    </dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}

          {/* --- Delivery --- */}
          {!isBuyer && (order.status === "active" || order.status === "revision") && (
            <Card>
              <CardHeader
                title={order.status === "revision" ? "Send a revised delivery" : "Deliver the work"}
                description="Attach the files and say what you changed. The buyer has three days to accept."
              />
              <form
                className="space-y-4 p-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  void deliver.run();
                }}
              >
                {deliver.error && <Alert tone="critical">{deliver.error}</Alert>}

                <Field label="Delivery note" htmlFor="note">
                  <Textarea
                    id="note"
                    rows={3}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="Three concepts attached. The second is my recommendation because…"
                  />
                </Field>

                <div>
                  <label htmlFor="files" className="mb-1.5 block text-[13px] font-medium text-fg">
                    Files
                  </label>
                  <input
                    id="files"
                    type="file"
                    multiple
                    onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                    className="block w-full text-[13px] text-muted file:mr-3 file:rounded-md file:border-0 file:bg-sunken file:px-3 file:py-1.5 file:text-[13px] file:text-fg"
                  />
                </div>

                <Button type="submit" size="lg" loading={deliver.pending}>
                  <Icon name="send" className="size-4" />
                  Deliver
                </Button>
              </form>
            </Card>
          )}

          {/* --- Acceptance --- */}
          {isBuyer && order.status === "delivered" && (
            <Card>
              <CardHeader
                title="Your delivery is ready"
                description={
                  order.accept_by
                    ? `Accept it, or request a revision. It completes automatically ${formatRelative(order.accept_by)} if you do nothing.`
                    : "Accept it, or request a revision."
                }
              />
              <div className="space-y-4 p-5">
                {(accept.error || requestRevision.error) && (
                  <Alert tone="critical">{accept.error ?? requestRevision.error}</Alert>
                )}

                {revising ? (
                  <form
                    className="space-y-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void requestRevision.run();
                    }}
                  >
                    <Field
                      label="What needs changing?"
                      htmlFor="revision"
                      required
                      hint={`${order.revisions_left} of ${order.revisions_allowed} revisions left.`}
                    >
                      <Textarea
                        id="revision"
                        rows={3}
                        required
                        autoFocus
                        value={revisionNote}
                        onChange={(event) => setRevisionNote(event.target.value)}
                        placeholder="The spacing in the second concept is too tight at small sizes."
                      />
                    </Field>
                    <div className="flex gap-2">
                      <Button type="submit" loading={requestRevision.pending}>
                        Request revision
                      </Button>
                      <Button type="button" variant="ghost" onClick={() => setRevising(false)}>
                        Cancel
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="flex flex-wrap gap-3">
                    <Button size="lg" loading={accept.pending} onClick={() => void accept.run()}>
                      <Icon name="check" className="size-4" strokeWidth={2.4} />
                      Accept and release <Money amount={order.price} />
                    </Button>
                    <Button
                      size="lg"
                      variant="secondary"
                      disabled={order.revisions_left <= 0}
                      onClick={() => setRevising(true)}
                    >
                      Request a revision
                    </Button>
                  </div>
                )}

                {order.revisions_left <= 0 && !revising && (
                  <p className="text-[12.5px] text-subtle">
                    You have used every revision in this package. The seller can send a paid
                    custom offer if more work is needed.
                  </p>
                )}
              </div>
            </Card>
          )}

          {order.status === "cancelled" && (
            <Alert tone="neutral" title="Order cancelled">
              {order.refund ? (
                order.refund.status === "refunded" ? (
                  <>
                    <Money amount={order.refund.amount} /> was refunded to {isBuyer ? "you" : "the buyer"}
                    {order.refund.refunded_at && ` ${formatRelative(order.refund.refunded_at)}`}.
                  </>
                ) : (
                  <>
                    A full refund of <Money amount={order.refund.amount} /> is on its way to{" "}
                    {isBuyer ? "the account you paid from" : "the buyer"}. Refunds are sent within
                    seven business days.
                  </>
                )
              ) : (
                "No payment was taken for this order."
              )}
            </Alert>
          )}

          {order.status === "completed" && (
            <Alert tone="positive" title="Order complete">
              Payment has been released.{" "}
              {order.contract && (
                <Link
                  href={`/contracts/${order.contract}`}
                  className="font-medium underline underline-offset-2"
                >
                  Leave a review
                </Link>
              )}
            </Alert>
          )}

          {order.contract && (
            <Card className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex gap-3">
                  <Icon name="layers" className="mt-0.5 size-4 shrink-0 text-accent" />
                  <div>
                    <p className="text-[13px] font-medium text-fg">Messages and full history</p>
                    <p className="mt-0.5 text-[12.5px] text-muted">
                      Every order runs on a contract — that is where escrow, messaging, and reviews
                      live.
                    </p>
                  </div>
                </div>
                <ButtonLink href={`/contracts/${order.contract}`} size="sm" variant="secondary">
                  Open contract
                </ButtonLink>
              </div>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <aside className="space-y-6">
          <Card>
            <CardHeader title={snapshot.name ?? "Package"} />
            <div className="space-y-3 p-5 text-[13px]">
              <div className="flex justify-between gap-3">
                <span className="text-muted">Tier</span>
                <span className="font-medium capitalize text-fg">{snapshot.tier ?? "—"}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Delivery</span>
                <span className="font-medium text-fg">{order.delivery_days} days</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Revisions</span>
                <span className="font-medium text-fg">
                  {order.revisions_used} of {order.revisions_allowed} used
                </span>
              </div>

              {snapshot.features && snapshot.features.length > 0 && (
                <ul className="space-y-2 border-t border-line pt-3">
                  {snapshot.features.map((feature) => (
                    <li key={feature} className="flex gap-2 text-[12.5px] text-muted">
                      <Icon
                        name="check"
                        className="mt-0.5 size-3.5 shrink-0 text-positive"
                        strokeWidth={2.6}
                      />
                      {feature}
                    </li>
                  ))}
                </ul>
              )}

              {order.extras.length > 0 && (
                <div className="border-t border-line pt-3">
                  <p className="mb-2 text-[12px] font-medium text-subtle">Extras</p>
                  {order.extras.map((extra) => (
                    <div key={extra.id} className="flex justify-between gap-3 text-[12.5px]">
                      <span className="text-muted">{extra.title}</span>
                      <span className="text-fg">
                        <Money amount={extra.price} />
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex justify-between gap-3 border-t border-line pt-3 text-[14px]">
                <span className="font-medium text-fg">Total</span>
                <span className="font-semibold text-fg">
                  <Money amount={order.price} />
                </span>
              </div>
            </div>
          </Card>

          {order.status !== "completed" &&
            order.status !== "cancelled" &&
            order.status !== "awaiting_payment" && (
            <Card className="p-5">
              <div className="flex gap-3">
                <Icon name="shield" className="mt-0.5 size-4 shrink-0 text-positive" />
                <p className="text-[12.5px] leading-relaxed text-muted">
                  {isBuyer
                    ? "Your payment is held until you accept the delivery. If you do nothing, it releases automatically after the review window."
                    : "The buyer's payment is already secured. Deliver with confidence — it releases to you on acceptance."}
                </p>
              </div>
            </Card>
          )}

          {/* Cancellation — only while the order is open. The server's
              `can_cancel` is the single source of truth for who may. */}
          {order.status !== "completed" && order.status !== "cancelled" && (
            <Card className="p-5">
              <p className="text-[13px] font-medium text-fg">Cancel this order</p>
              {order.can_cancel ? (
                confirmingCancel ? (
                  <div className="mt-3 space-y-3">
                    <p className="text-[12.5px] leading-relaxed text-muted">
                      {order.status === "awaiting_payment" ? (
                        "The order closes. Nothing has been paid, so nothing is charged."
                      ) : (
                        <>
                          The order closes and {isBuyer ? "you are" : "the buyer is"} refunded{" "}
                          <Money amount={order.price} /> in full. This cannot be undone.
                        </>
                      )}
                    </p>
                    {cancel.error && <Alert tone="critical">{cancel.error}</Alert>}
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="danger" loading={cancel.pending} onClick={() => void cancel.run()}>
                        {order.status === "awaiting_payment" ? "Cancel the order" : "Cancel and refund"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setConfirmingCancel(false)}>
                        Keep the order
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                      {order.status === "awaiting_payment"
                        ? "Nothing has been paid yet, so nothing is charged."
                        : `${isBuyer ? "You" : "The buyer"} will be refunded in full.`}
                    </p>
                    <Button size="sm" variant="secondary" className="mt-3" onClick={() => setConfirmingCancel(true)}>
                      Cancel order…
                    </Button>
                  </>
                )
              ) : (
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                  {order.cancel_blocked_reason}{" "}
                  <Link href="/refunds" className="text-accent underline-offset-2 hover:underline">
                    Refund policy
                  </Link>
                </p>
              )}
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}
