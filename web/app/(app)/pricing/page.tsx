"use client";

/**
 * The pricing table.
 *
 * Public, because it is a marketing surface — requiring a session to read the
 * prices would cost exactly the visitors the page exists to convert. What
 * changes when signed in is only the call to action: the tier you are already
 * on says so instead of offering to sell it to you again.
 *
 * Prices come from `/plans/`, never from a constant here. The enforcement and
 * the table the user reads must not be able to disagree, and the way to
 * guarantee that is for there to be one source.
 */

import * as React from "react";
import Link from "next/link";

import { PageHeading } from "@/components/shell";
import { SwichPay } from "@/components/payments";
import {
  Alert,
  Badge,
  Button,
  Card,
  Icon,
  Money,
  Segmented,
  Skeleton,
  cn,
} from "@/components/ui";
import {
  UNLIMITED,
  professional,
  type CheckoutStart,
  type PlanTier,
  type SubscriptionPlan,
} from "@/lib/api";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

type Interval = "monthly" | "yearly";

/** Two months free on the annual price, stated rather than left to arithmetic. */
function savingLabel(plan: SubscriptionPlan): string | null {
  const monthly = Number(plan.monthly_price) * 12;
  const yearly = Number(plan.yearly_price);
  if (!monthly || yearly >= monthly) return null;
  return `Save ${Math.round(((monthly - yearly) / monthly) * 100)}%`;
}

function limitText(value: number): string {
  return value === UNLIMITED ? "Unlimited" : String(value);
}

function PlanCard({
  plan,
  interval,
  currentTier,
  onChoose,
  pending,
  payingFor,
  onStartPayment,
  onCancelPayment,
}: {
  plan: SubscriptionPlan;
  interval: Interval;
  currentTier: PlanTier | null;
  onChoose: (tier: PlanTier) => void;
  pending: PlanTier | null;
  payingFor: boolean;
  onStartPayment: () => Promise<CheckoutStart | undefined>;
  onCancelPayment: () => void;
}) {
  const featured = plan.tier === "pro";
  const current = currentTier === plan.tier;
  const price = interval === "yearly" ? plan.yearly_price : plan.monthly_price;
  const saving = savingLabel(plan);

  return (
    <Card
      className={cn(
        "relative flex flex-col",
        featured && "border-accent/40 shadow-e2 lg:-my-3 lg:py-3",
      )}
    >
      {featured && (
        <span className="absolute -top-2.5 left-1/2 -translate-x-1/2">
          <Badge tone="accent">Most popular</Badge>
        </span>
      )}

      <div className="border-b border-line p-6">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[15px] font-semibold text-fg">{plan.name}</h2>
          {current && <Badge tone="positive">Your plan</Badge>}
        </div>
        <p className="mt-1 min-h-10 text-[13px] leading-relaxed text-muted">{plan.tagline}</p>

        <div className="mt-5 flex items-baseline gap-1.5">
          {Number(price) === 0 ? (
            <span className="text-3xl font-semibold tracking-[-0.03em] text-fg">Free</span>
          ) : (
            <>
              <Money
                amount={price}
                className="text-3xl font-semibold tracking-[-0.03em] text-fg"
              />
              <span className="text-[13px] text-muted">
                /{interval === "yearly" ? "year" : "month"}
              </span>
            </>
          )}
        </div>
        {interval === "yearly" && saving && (
          <p className="mt-1.5 text-[12.5px] font-medium text-positive">{saving}</p>
        )}

        <div className="mt-5">
          {current ? (
            <Button variant="secondary" block disabled>
              Current plan
            </Button>
          ) : payingFor ? (
            <div className="space-y-3">
              <SwichPay amount={price} label="Pay" showMethods={false} onStart={onStartPayment} />
              <Button variant="ghost" size="sm" block onClick={onCancelPayment}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              block
              variant={featured ? "primary" : "secondary"}
              loading={pending === plan.tier}
              onClick={() => onChoose(plan.tier)}
            >
              {plan.tier === "free" ? "Switch to Free" : `Choose ${plan.name}`}
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-3 p-6">
        <ul className="space-y-2.5">
          {plan.features.map((feature) => (
            <li key={feature} className="flex gap-2.5 text-[13px] leading-relaxed text-fg">
              <Icon
                name="check"
                strokeWidth={2.6}
                className="mt-0.5 size-3.5 shrink-0 text-positive"
              />
              {feature}
            </li>
          ))}
        </ul>

        <dl className="grid gap-1.5 border-t border-line pt-4 text-[12.5px]">
          {(
            [
              ["Proposals a month", limitText(plan.proposal_quota)],
              ["CRM contacts", limitText(plan.crm_contact_limit)],
              ["Team seats", plan.team_seats > 0 ? String(plan.team_seats) : "—"],
            ] satisfies Array<[string, string]>
          ).map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3">
              <dt className="text-muted">{label}</dt>
              <dd className="tabular font-medium text-fg">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </Card>
  );
}

/** The rows are the capabilities that actually gate a feature server-side. */
const COMPARISON: Array<[string, (p: SubscriptionPlan) => boolean]> = [
  ["Profile boost in search", (p) => p.search_boost],
  ["Advanced analytics", (p) => p.advanced_analytics],
  ["Sell monthly retainers", (p) => p.can_sell_retainers],
  ["Agencies and shared workspaces", (p) => p.can_create_agency],
  ["Priority support", (p) => p.priority_support],
];

export default function PricingPage() {
  const { user } = useSession();
  const [interval, setInterval] = React.useState<Interval>("monthly");

  const plans = useLoader(() => professional.plans(), []);
  const mine = useLoader(
    () => (user ? professional.subscription() : Promise.resolve(null)),
    [user?.id],
  );

  const subscribe = useAsyncAction(professional.subscribe);
  const cancel = useAsyncAction(professional.cancelSubscription);
  const [choosing, setChoosing] = React.useState<PlanTier | null>(null);
  // The paid tier showing its pay panel in place of a "Choose" button.
  const [payingForTier, setPayingForTier] = React.useState<PlanTier | null>(null);

  const currentTier = mine.data?.entitlements.tier ?? null;
  const subscription = mine.data?.subscription ?? null;

  async function confirm(tier: PlanTier) {
    setChoosing(tier);
    const result = await subscribe.run(tier, interval);
    setChoosing(null);
    setPayingForTier(null);
    if (result !== undefined) await mine.reload();
  }

  /** A paid tier: start the Swich checkout; the plan begins once paid. */
  async function startPayment(tier: PlanTier) {
    const result = await subscribe.run(tier, interval);
    return result && "checkout_url" in result ? result : undefined;
  }

  function choose(tier: PlanTier) {
    const plan = plans.data?.find((row) => row.tier === tier);
    // Free needs no payment: it switches at once.
    if (!plan?.is_paid) {
      void confirm(tier);
      return;
    }
    setPayingForTier(tier);
  }

  return (
    <>
      <PageHeading
        title="Plans"
        description="Everything on SkilRize works on the free plan. The paid tiers buy volume, visibility, and the tools you need once freelancing is your income rather than your side project."
      />

      <div className="flex justify-center pb-8">
        <Segmented
          label="Billing interval"
          value={interval}
          onChange={setInterval}
          options={[
            { value: "monthly", label: "Monthly" },
            { value: "yearly", label: "Yearly — 2 months free" },
          ]}
        />
      </div>

      {plans.error && <Alert tone="critical">{plans.error}</Alert>}
      {subscribe.error && (
        <Alert tone="critical" className="mb-5">
          {subscribe.error}
        </Alert>
      )}

      {plans.loading ? (
        <div className="grid gap-6 lg:grid-cols-3">
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-[30rem]" />
          ))}
        </div>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-3">
          {plans.data?.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              interval={interval}
              currentTier={currentTier}
              onChoose={user ? choose : () => undefined}
              pending={choosing}
              payingFor={payingForTier === plan.tier}
              onStartPayment={() => startPayment(plan.tier)}
              onCancelPayment={() => setPayingForTier(null)}
            />
          ))}
        </div>
      )}

      {!user && (
        <Alert tone="accent" className="mt-6">
          <div className="flex flex-wrap items-center gap-3">
            <span>Create an account to start on the free plan — no card needed.</span>
            <Link
              href="/signup"
              className="font-medium text-accent underline-offset-4 hover:underline"
            >
              Sign up
            </Link>
          </div>
        </Alert>
      )}

      {subscription && (
        <Card className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-4 p-5">
            <div className="space-y-1">
              <p className="text-[14px] font-medium text-fg">
                {subscription.plan.name} · {subscription.interval}
              </p>
              <p className="text-[13px] text-muted">
                {subscription.cancel_at_period_end ? "Ends" : "Renews"} on{" "}
                {new Date(subscription.current_period_end).toLocaleDateString()}.
              </p>
            </div>
            {!subscription.cancel_at_period_end && (
              <Button
                variant="secondary"
                size="sm"
                loading={cancel.pending}
                onClick={async () => {
                  if (await cancel.run()) await mine.reload();
                }}
              >
                Cancel plan
              </Button>
            )}
          </div>
          {cancel.error && (
            <div className="border-t border-line p-5 pt-4">
              <Alert tone="critical">{cancel.error}</Alert>
            </div>
          )}
        </Card>
      )}

      {plans.data && plans.data.length > 0 && (
        <section className="mt-12">
          <h2 className="pb-4 text-[15px] font-semibold text-fg">Compare</h2>
          <Card className="overflow-x-auto">
            <table className="w-full min-w-lg text-[13px]">
              <thead>
                <tr className="border-b border-line">
                  <th scope="col" className="p-4 text-left font-medium text-muted">
                    Feature
                  </th>
                  {plans.data.map((plan) => (
                    <th
                      key={plan.id}
                      scope="col"
                      className="p-4 text-center font-semibold text-fg"
                    >
                      {plan.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARISON.map(([label, has]) => (
                  <tr key={label} className="border-b border-line last:border-0">
                    <th scope="row" className="p-4 text-left font-normal text-fg">
                      {label}
                    </th>
                    {plans.data?.map((plan) => (
                      <td key={plan.id} className="p-4 text-center">
                        {has(plan) ? (
                          <Icon
                            name="check"
                            strokeWidth={2.6}
                            className="mx-auto size-4 text-positive"
                          />
                        ) : (
                          <span className="text-subtle" aria-label="Not included">
                            —
                          </span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      )}
    </>
  );
}
