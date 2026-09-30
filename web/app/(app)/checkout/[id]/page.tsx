"use client";

/**
 * Checkout for a service.
 *
 * Public on purpose: a buyer — or a payment provider's reviewer — can see the
 * whole order, its price, the policies that govern it and how payment works
 * before being asked to sign in. The selection (package and extras) lives in
 * the URL rather than component state, so the sign-in round trip returns to
 * exactly the order that was being built, and a checkout link can be shared.
 *
 * The server prices the order from what it finds, never from this page; the
 * totals here are a preview of the same arithmetic.
 */

import * as React from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";

import { PaymentMethods, SwichPay } from "@/components/payments";
import { TwoFactorRequiredPrompt } from "@/components/two-factor";
import {
  Alert,
  Avatar,
  ButtonLink,
  Card,
  CardHeader,
  EmptyState,
  Icon,
  Money,
  Segmented,
  Skeleton,
  Stars,
  cn,
} from "@/components/ui";
import { gigs, payments, type GigDetail, type Tier } from "@/lib/api";
import { BUSINESS } from "@/lib/business";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

const TIERS: Tier[] = ["basic", "standard", "premium"];

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Package and extras, read from and written to the query string. */
function useSelection(gig: GigDetail | null) {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const active = gig?.packages.filter((p) => p.is_active) ?? [];
  const extras = gig?.extras.filter((e) => e.is_active) ?? [];

  const requested = search.get("package");
  const tier = TIERS.find((t) => t === requested);
  const selected = active.find((p) => p.tier === tier) ?? active[0];

  const extraIds = (search.get("extras") ?? "")
    .split(",")
    .map(Number)
    .filter((id) => extras.some((e) => e.id === id));
  const chosenExtras = extras.filter((e) => extraIds.includes(e.id));

  const write = React.useCallback(
    (next: { tier?: Tier; extras?: number[] }) => {
      const params = new URLSearchParams(search.toString());
      if (next.tier) params.set("package", next.tier);
      if (next.extras) {
        if (next.extras.length) params.set("extras", next.extras.join(","));
        else params.delete("extras");
      }
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, search],
  );

  const total =
    Number(selected?.price ?? 0) + chosenExtras.reduce((sum, e) => sum + Number(e.price), 0);
  const days = Math.max(
    1,
    (selected?.delivery_days ?? 0) + chosenExtras.reduce((sum, e) => sum + e.extra_days, 0),
  );

  return {
    active,
    extras,
    selected,
    chosenExtras,
    extraIds: chosenExtras.map((e) => e.id),
    total,
    days,
    here: `${pathname}${search.size ? `?${search.toString()}` : ""}`,
    setTier: (t: Tier) => write({ tier: t }),
    toggleExtra: (id: number, on: boolean) =>
      write({
        extras: on
          ? [...chosenExtras.map((e) => e.id), id]
          : chosenExtras.map((e) => e.id).filter((x) => x !== id),
      }),
  };
}

type Selection = ReturnType<typeof useSelection>;

/* -------------------------------------------------------------------------- */
/* Steps                                                                      */
/* -------------------------------------------------------------------------- */

const STEPS = ["Review your order", "Pay into escrow", "Send requirements"];

function Steps({ current }: { current: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-[13px]" aria-label="Checkout steps">
      {STEPS.map((label, index) => (
        <li key={label} className="flex items-center gap-2">
          <span
            aria-current={index === current ? "step" : undefined}
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3 py-1",
              index === current
                ? "bg-fg text-surface"
                : index < current
                  ? "text-fg"
                  : "text-subtle",
            )}
          >
            <span className="figure text-[11px]">{index + 1}</span>
            {label}
          </span>
          {index < STEPS.length - 1 && (
            <Icon name="chevronLeft" className="size-3 rotate-180 text-subtle" />
          )}
        </li>
      ))}
    </ol>
  );
}

/* -------------------------------------------------------------------------- */
/* The order                                                                  */
/* -------------------------------------------------------------------------- */

function OrderCard({ gig, selection }: { gig: GigDetail; selection: Selection }) {
  const { selected, active, extras, extraIds } = selection;
  if (!selected) return null;

  return (
    <Card>
      <div className="flex gap-4 p-5">
        {/* The seller's own image, when there is one — never a stand-in. */}
        {gig.gallery_urls[0] && (
          <div className="aspect-[4/3] w-24 shrink-0 overflow-hidden rounded-md bg-sunken sm:w-36">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={gig.gallery_urls[0]} alt="" className="size-full object-cover" />
          </div>
        )}
        <div className="min-w-0">
          {gig.category && <p className="eyebrow">{gig.category.name}</p>}
          <Link
            href={`/gigs/${gig.id}`}
            className="mt-1 block text-[17px] font-semibold leading-snug text-fg underline-offset-4 hover:underline"
          >
            {gig.title}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
            <span className="inline-flex items-center gap-2">
              <Avatar name={gig.seller.display_name} src={gig.seller.avatar_url} size={22} />
              <Link href={`/u/${gig.seller.handle}`} className="font-medium text-fg hover:underline">
                {gig.seller.display_name}
              </Link>
            </span>
            {gig.rating_count > 0 ? (
              <span className="inline-flex items-center gap-1.5 text-muted">
                <Stars value={Number(gig.rating_average ?? 0)} size={12} />
                {gig.rating_average} ({gig.rating_count})
              </span>
            ) : (
              <span className="text-subtle">New service</span>
            )}
          </div>
        </div>
      </div>

      {active.length > 1 && (
        <div className="border-t border-line px-5 py-3">
          <Segmented
            label="Package"
            size="sm"
            value={selected.tier}
            onChange={selection.setTier}
            options={active.map((p) => ({ value: p.tier, label: titleCase(p.tier) }))}
          />
        </div>
      )}

      <div className="border-t border-line p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-[15px] font-semibold text-fg">{selected.name}</h2>
          <Money amount={selected.price} className="figure text-[15px] font-semibold text-fg" />
        </div>
        {selected.description && (
          <p className="mt-1 text-[13.5px] leading-relaxed text-muted">{selected.description}</p>
        )}
        {selected.features.length > 0 && (
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {selected.features.map((feature) => (
              <li key={feature} className="flex gap-2 text-[13px] text-fg">
                <Icon name="check" className="mt-0.5 size-3.5 shrink-0 text-positive" strokeWidth={2.6} />
                {feature}
              </li>
            ))}
          </ul>
        )}
      </div>

      {extras.length > 0 && (
        <fieldset className="border-t border-line p-5">
          <legend className="float-left mb-3 w-full text-[13px] font-semibold text-fg">
            Add extras
          </legend>
          <div className="clear-both space-y-2">
            {extras.map((extra) => {
              const on = extraIds.includes(extra.id);
              return (
                <label
                  key={extra.id}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors duration-150",
                    on ? "border-accent bg-accent-soft" : "border-line hover:bg-sunken",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={(event) => selection.toggleExtra(extra.id, event.target.checked)}
                    className="size-4 accent-[var(--accent)]"
                  />
                  <span className="min-w-0 flex-1 text-[13.5px] text-fg">
                    {extra.title}
                    {extra.extra_days !== 0 && (
                      <span className="ml-1 text-subtle">
                        ({extra.extra_days > 0 ? "+" : ""}
                        {extra.extra_days} day{Math.abs(extra.extra_days) === 1 ? "" : "s"})
                      </span>
                    )}
                  </span>
                  <Money amount={extra.price} className="figure shrink-0 text-[13px] font-medium text-fg" />
                </label>
              );
            })}
          </div>
        </fieldset>
      )}
    </Card>
  );
}

function AfterPayment({ gig, days }: { gig: GigDetail; days: number }) {
  const questions = gig.requirements.slice(0, 4);
  return (
    <Card>
      <CardHeader title="After you pay" description="What happens next, and how long each part takes." />
      <ol className="space-y-4 p-5 text-[13.5px]">
        <li className="flex gap-3">
          <span className="figure mt-0.5 w-5 shrink-0 text-subtle">1</span>
          <div>
            <p className="font-medium text-fg">You send the seller your requirements</p>
            {questions.length > 0 ? (
              <p className="mt-0.5 text-muted">
                They will ask: {questions.map((q) => q.label).join(" · ")}
                {gig.requirements.length > questions.length ? " …" : ""}
              </p>
            ) : (
              <p className="mt-0.5 text-muted">Anything they need to start — a brief, files, access.</p>
            )}
          </div>
        </li>
        <li className="flex gap-3">
          <span className="figure mt-0.5 w-5 shrink-0 text-subtle">2</span>
          <div>
            <p className="font-medium text-fg">
              Delivery within {days} day{days === 1 ? "" : "s"}
            </p>
            <p className="mt-0.5 text-muted">
              Counted from your requirements. If it is late, you can cancel for a full refund.
            </p>
          </div>
        </li>
        <li className="flex gap-3">
          <span className="figure mt-0.5 w-5 shrink-0 text-subtle">3</span>
          <div>
            <p className="font-medium text-fg">You accept, or ask for a revision</p>
            <p className="mt-0.5 text-muted">
              You have {BUSINESS.orderReviewDays} days to review. Only then is the seller paid.
            </p>
          </div>
        </li>
      </ol>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Summary slip                                                               */
/* -------------------------------------------------------------------------- */

function SummarySlip({ gig, selection }: { gig: GigDetail; selection: Selection }) {
  const { selected, chosenExtras, total, days } = selection;
  if (!selected) return null;
  const revisions = selected.has_unlimited_revisions
    ? "Unlimited revisions"
    : `${selected.revisions} revision${selected.revisions === 1 ? "" : "s"}`;

  return (
    <div className="ticket-edge relative rounded-t-xl border border-b-0 border-line bg-raised px-5 pt-5 pb-8 shadow-e2">
      <p className="eyebrow">Order summary</p>
      <p className="mt-2 line-clamp-2 text-[15px] font-semibold leading-snug text-fg">{gig.title}</p>
      <p className="mt-1 text-[12.5px] text-muted">
        {titleCase(selected.tier)} · {days}-day delivery · {revisions}
      </p>

      <div className="perforation my-4" aria-hidden />

      <dl className="space-y-2 text-[13.5px]">
        <div className="flex justify-between gap-3">
          <dt className="text-muted">{selected.name}</dt>
          <dd>
            <Money amount={selected.price} className="figure text-fg" />
          </dd>
        </div>
        {chosenExtras.map((extra) => (
          <div key={extra.id} className="flex justify-between gap-3">
            <dt className="text-muted">+ {extra.title}</dt>
            <dd>
              <Money amount={extra.price} className="figure text-fg" />
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Service fee</dt>
          <dd>
            <Money amount={0} className="figure text-fg" />
          </dd>
        </div>
      </dl>

      <div className="perforation my-4" aria-hidden />

      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13.5px] font-semibold text-fg">Total</span>
        <Money amount={total} className="figure text-[22px] font-bold tracking-tight text-fg" />
      </div>
      <p className="mt-1 text-right text-[11.5px] text-subtle">{BUSINESS.currency}</p>

      <ul className="mt-5 space-y-2 text-[12.5px] leading-relaxed text-muted">
        <li className="flex gap-2">
          <Icon name="shield" className="mt-0.5 size-3.5 shrink-0 text-accent" />
          Held in escrow by {BUSINESS.operator} until you accept the delivery.
        </li>
        <li className="flex gap-2">
          <Icon name="wallet" className="mt-0.5 size-3.5 shrink-0 text-accent" />
          Full refund if the order is cancelled before delivery.
        </li>
      </ul>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Payment                                                                    */
/* -------------------------------------------------------------------------- */

function PaymentCard({ gig, selection }: { gig: GigDetail; selection: Selection }) {
  const { user, loading: sessionLoading } = useSession();
  const router = useRouter();
  const next = encodeURIComponent(selection.here);
  const [accepted, setAccepted] = React.useState(false);
  const { data: options } = useLoader(() => payments.options(), []);

  // Places the order (it waits, unseen by the seller, until Swich confirms
  // the payment) and returns where to send the buyer to pay.
  const buy = useAsyncAction(() =>
    gigs.order(gig.id, { package: selection.selected!.id, extras: selection.extraIds }),
  );

  let body: React.ReactNode;
  if (sessionLoading) {
    body = <Skeleton className="h-28 w-full" />;
  } else if (user && gig.is_owner) {
    body = <Alert tone="neutral">This is your own service, so you cannot order it.</Alert>;
  } else if (user && !gig.can_order) {
    body = (
      <div className="space-y-4">
        <Alert tone="caution">{gig.order_blocked_reason}</Alert>
        {!user?.can_transact && (
          <ButtonLink href="/dashboard" variant="secondary">
            Finish verifying your account
            <Icon name="arrowRight" className="size-3.5" />
          </ButtonLink>
        )}
      </div>
    );
  } else if (buy.code === "two_factor_required") {
    body = (
      <TwoFactorRequiredPrompt
        onComplete={() => {
          void buy.run().then((started) => {
            if (started?.checkout_url) window.location.assign(started.checkout_url);
          });
        }}
      />
    );
  } else {
    body = (
      <div className="space-y-5">
        {buy.code === "device_cooloff" ? (
          <Alert tone="caution" title="This device is new">
            {buy.error} If this sign-in was not you,{" "}
            <Link href="/settings/security" className="font-medium text-accent underline-offset-4 hover:underline">
              secure your account
            </Link>
            .
          </Alert>
        ) : null}

        {!user && (
          <p className="text-[13.5px] leading-relaxed text-muted">
            You sign in before paying. New to SkilRize?{" "}
            <Link
              href={`/signup?next=${next}`}
              className="font-medium text-accent underline-offset-4 hover:underline"
            >
              Create a free account
            </Link>{" "}
            — you verify your email and identity card once, which protects both you and the seller.
          </p>
        )}

        <label className="flex cursor-pointer gap-3 rounded-md border border-line p-3.5 text-[13.5px] leading-relaxed text-fg">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(event) => setAccepted(event.target.checked)}
            className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
          />
          <span>
            I agree to the{" "}
            <Link href="/terms" target="_blank" className="font-medium text-accent underline underline-offset-2">
              Terms of Service
            </Link>{" "}
            and the{" "}
            <Link href="/refunds" target="_blank" className="font-medium text-accent underline underline-offset-2">
              Refund &amp; Cancellation Policy
            </Link>
            , and understand my payment is held in escrow until I accept the delivery.
          </span>
        </label>

        <SwichPay
          amount={selection.total}
          label="Pay and place order"
          disabled={!accepted}
          showMethods={false}
          error={buy.code === "device_cooloff" ? null : buy.error}
          onStart={async () => {
            if (!user) {
              router.push(`/login?next=${next}`);
              return undefined;
            }
            return buy.run();
          }}
        />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Payment"
        description="Pay by card, Easypaisa, JazzCash or 1Bill through Swich. Every method pays into escrow."
      />
      <div className="space-y-5 p-5">
        <PaymentMethods options={options} />
        {body}
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */

function Checkout() {
  const params = useParams<{ id: string }>();
  const { data: gig, loading } = useLoader(() => gigs.detail(params.id), [params.id]);
  const selection = useSelection(gig ?? null);

  if (loading) {
    return (
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_23rem]">
        <div className="space-y-4">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-64 w-full" />
        </div>
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (!gig || !selection.selected) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="search" className="size-5" />}
          title="This service cannot be ordered"
          description="It may have been paused or withdrawn by the seller."
          action={
            <ButtonLink href="/gigs" variant="secondary">
              Browse services
            </ButtonLink>
          }
        />
      </Card>
    );
  }

  return (
    <>
      <nav className="mb-4 flex items-center gap-1.5 text-[13px] text-muted" aria-label="Breadcrumb">
        <Link href={`/gigs/${gig.id}`} className="inline-flex items-center gap-1 transition-colors hover:text-fg">
          <Icon name="chevronLeft" className="size-3.5" />
          Back to the service
        </Link>
      </nav>

      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className="display-md">Checkout</h1>
        <Steps current={0} />
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_23rem]">
        <div className="min-w-0 space-y-6">
          <OrderCard gig={gig} selection={selection} />
          <PaymentCard gig={gig} selection={selection} />
          <AfterPayment gig={gig} days={selection.days} />
        </div>

        <aside className="order-first lg:order-none lg:sticky lg:top-20 lg:self-start">
          <SummarySlip gig={gig} selection={selection} />
          <p className="mt-4 text-[12px] leading-relaxed text-subtle">
            Sold by {gig.seller.display_name}. Payment collected and held in escrow by{" "}
            {BUSINESS.operator}. Questions?{" "}
            <Link href="/contact" className="underline underline-offset-2">
              Contact us
            </Link>
            .
          </p>
        </aside>
      </div>
    </>
  );
}

export default function CheckoutPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <Checkout />
    </React.Suspense>
  );
}
