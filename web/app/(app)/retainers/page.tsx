"use client";

/**
 * Retainers — services sold monthly rather than per delivery.
 *
 * The catalogue is scope-aware like every other listing, so a campus retainer
 * never surfaces in the global surface. That is enforced server-side by the
 * scoped manager; nothing here needs to filter, and nothing here should try.
 */

import * as React from "react";
import Link from "next/link";

import { ActionError, PlanBadge, UpgradePrompt, useEntitlements } from "@/components/professional";
import { PageHeading } from "@/components/shell";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Icon,
  Input,
  Money,
  Segmented,
  Skeleton,
  Tag,
  Textarea,
} from "@/components/ui";
import {
  professional,
  type Entitlements,
  type Retainer,
  type RetainerEngagement,
} from "@/lib/api";
import { useAsyncAction, useLoader, useSession } from "@/lib/session";

/* -------------------------------------------------------------------------- */
/* Catalogue                                                                  */
/* -------------------------------------------------------------------------- */

function RetainerCard({
  retainer,
  onSubscribed,
  mine,
}: {
  retainer: Retainer;
  onSubscribed: () => void;
  mine: boolean;
}) {
  const subscribe = useAsyncAction(professional.subscribeToRetainer);

  return (
    <Card className="lift flex flex-col">
      <div className="flex-1 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold leading-snug text-fg">{retainer.title}</h3>
            {!mine && (
              <Link
                href={`/users/${retainer.seller_handle}`}
                className="mt-1 inline-flex items-center gap-1.5 text-[12.5px] text-muted hover:text-accent"
              >
                <Avatar name={retainer.seller_name} size={18} />
                {retainer.seller_name}
              </Link>
            )}
          </div>
          {retainer.visibility === "university" && <Badge tone="accent">Campus</Badge>}
        </div>

        <p className="mt-3 line-clamp-3 text-[13px] leading-relaxed text-muted">
          {retainer.description}
        </p>

        {retainer.deliverables.length > 0 && (
          <ul className="mt-4 space-y-1.5">
            {retainer.deliverables.slice(0, 4).map((item) => (
              <li key={item} className="flex gap-2 text-[12.5px] leading-relaxed text-fg">
                <Icon
                  name="check"
                  strokeWidth={2.6}
                  className="mt-0.5 size-3.5 shrink-0 text-positive"
                />
                {item}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-line p-5">
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <Money amount={retainer.monthly_price} className="text-lg font-semibold text-fg" />
            <span className="text-[12.5px] text-muted"> /month</span>
          </div>
          {retainer.minimum_months > 1 && (
            <span className="text-[11.5px] text-subtle">
              {retainer.minimum_months}-month minimum
            </span>
          )}
        </div>

        {mine ? (
          <p className="mt-3 text-[12.5px] text-muted">
            {retainer.active_subscriber_count} active subscriber
            {retainer.active_subscriber_count === 1 ? "" : "s"}
            {retainer.max_subscribers > 0 && ` of ${retainer.max_subscribers}`}
            {!retainer.is_active && " · paused"}
          </p>
        ) : (
          <>
            <Button
              block
              className="mt-3"
              disabled={retainer.is_full}
              loading={subscribe.pending}
              onClick={async () => {
                if (await subscribe.run(retainer.id)) onSubscribed();
              }}
            >
              {retainer.is_full ? "Full" : "Subscribe"}
            </Button>
            <ActionError error={subscribe.error} code={subscribe.code} />
          </>
        )}
      </div>
    </Card>
  );
}

function BrowsePanel({ onSubscribed }: { onSubscribed: () => void }) {
  const { surface } = useSession();
  const catalogue = useLoader(() => professional.retainers(), [surface]);
  const rows = catalogue.data?.results ?? [];

  if (catalogue.loading) {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((key) => (
          <Skeleton key={key} className="h-72" />
        ))}
      </div>
    );
  }

  if (catalogue.error) return <Alert tone="critical">{catalogue.error}</Alert>;

  if (rows.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="clock" className="size-5" />}
          title="No retainers on offer yet"
          description="Retainers are ongoing arrangements — a set of deliverables every month for a fixed fee. Sellers on Pro and Elite can publish them."
        />
      </Card>
    );
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map((retainer) => (
        <RetainerCard
          key={retainer.id}
          retainer={retainer}
          mine={false}
          onSubscribed={onSubscribed}
        />
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Selling                                                                    */
/* -------------------------------------------------------------------------- */

function NewRetainerForm({ onDone }: { onDone: () => void }) {
  const create = useAsyncAction(professional.createRetainer);
  const [form, setForm] = React.useState({
    title: "",
    description: "",
    monthly_price: "",
    minimum_months: "1",
    max_subscribers: "0",
  });
  const [deliverables, setDeliverables] = React.useState<string[]>([]);
  const [draft, setDraft] = React.useState("");

  function addDeliverable() {
    const value = draft.trim();
    if (!value || deliverables.includes(value)) return;
    setDeliverables([...deliverables, value]);
    setDraft("");
  }

  return (
    <form
      className="space-y-4 p-5"
      onSubmit={async (event) => {
        event.preventDefault();
        const created = await create.run({
          title: form.title,
          description: form.description,
          monthly_price: form.monthly_price,
          minimum_months: Number(form.minimum_months) || 1,
          max_subscribers: Number(form.max_subscribers) || 0,
          deliverables,
        });
        if (created) {
          setForm({
            title: "",
            description: "",
            monthly_price: "",
            minimum_months: "1",
            max_subscribers: "0",
          });
          setDeliverables([]);
          onDone();
        }
      }}
    >
      <Field label="Title" htmlFor="retainer-title" required error={create.fieldErrors.title}>
        <Input
          id="retainer-title"
          required
          maxLength={200}
          value={form.title}
          placeholder="Monthly social content — 12 posts"
          onChange={(event) => setForm({ ...form, title: event.target.value })}
        />
      </Field>

      <Field
        label="Description"
        htmlFor="retainer-description"
        required
        error={create.fieldErrors.description}
      >
        <Textarea
          id="retainer-description"
          required
          value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })}
        />
      </Field>

      {/* Required by the model, and worth the friction: a retainer with no
          stated deliverables is an argument waiting to happen. */}
      <Field
        label="What the buyer gets each month"
        htmlFor="retainer-deliverable"
        required
        hint="Add each item separately. This is what you are committing to."
        error={create.fieldErrors.deliverables}
      >
        <div className="flex gap-2">
          <Input
            id="retainer-deliverable"
            value={draft}
            placeholder="4 long-form posts"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              addDeliverable();
            }}
          />
          <Button type="button" variant="secondary" onClick={addDeliverable}>
            Add
          </Button>
        </div>
      </Field>

      {deliverables.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {deliverables.map((item) => (
            <li key={item}>
              <Tag onRemove={() => setDeliverables(deliverables.filter((d) => d !== item))}>
                {item}
              </Tag>
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Field
          label="Monthly price"
          htmlFor="retainer-price"
          required
          error={create.fieldErrors.monthly_price}
        >
          <Input
            id="retainer-price"
            type="number"
            min={1}
            step="0.01"
            required
            value={form.monthly_price}
            onChange={(event) => setForm({ ...form, monthly_price: event.target.value })}
          />
        </Field>
        <Field label="Minimum months" htmlFor="retainer-minimum">
          <Input
            id="retainer-minimum"
            type="number"
            min={1}
            max={24}
            value={form.minimum_months}
            onChange={(event) => setForm({ ...form, minimum_months: event.target.value })}
          />
        </Field>
        <Field label="Subscriber cap" htmlFor="retainer-cap" hint="0 for no limit.">
          <Input
            id="retainer-cap"
            type="number"
            min={0}
            value={form.max_subscribers}
            onChange={(event) => setForm({ ...form, max_subscribers: event.target.value })}
          />
        </Field>
      </div>

      <Button type="submit" loading={create.pending} disabled={deliverables.length === 0}>
        Publish retainer
      </Button>
      <ActionError error={create.error} code={create.code} />
    </form>
  );
}

function SellingPanel({ rights }: { rights: Entitlements | null }) {
  const [creating, setCreating] = React.useState(false);
  const mine = useLoader(() => professional.retainers({ mine: "true" }), []);
  const engagements = useLoader(() => professional.myRetainers(), []);

  const rows = mine.data?.results ?? [];
  const selling = engagements.data?.selling ?? [];

  if (rights && !rights.can_sell_retainers && rows.length === 0) {
    return (
      <UpgradePrompt
        title="Selling retainers needs Pro"
        description="Turn one-off work into recurring income: publish a set of monthly deliverables at a fixed fee and let clients subscribe."
      />
    );
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="Your retainers"
          description="Recurring work you offer. Buyers subscribe and stay subscribed until one of you ends it."
          action={
            rights?.can_sell_retainers && (
              <Button
                size="sm"
                variant={creating ? "ghost" : "secondary"}
                onClick={() => setCreating(!creating)}
              >
                {creating ? "Cancel" : <><Icon name="plus" className="size-3.5" /> New retainer</>}
              </Button>
            )
          }
        />
        {creating && (
          <NewRetainerForm
            onDone={() => {
              setCreating(false);
              void mine.reload();
            }}
          />
        )}
      </Card>

      {mine.loading ? (
        <Skeleton className="h-48" />
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Icon name="clock" className="size-5" />}
            title="Nothing published"
            description="A retainer is the same work every month at a fixed fee — the difference between chasing the next brief and knowing what next month looks like."
          />
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((retainer) => (
            <RetainerCard
              key={retainer.id}
              retainer={retainer}
              mine
              onSubscribed={() => undefined}
            />
          ))}
        </div>
      )}

      {selling.length > 0 && (
        <Card>
          <CardHeader title="Subscribers" description="Who is on your retainers right now." />
          <ul className="divide-y divide-line">
            {selling.map((engagement) => (
              <li key={engagement.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                <Avatar name={engagement.buyer_name} size={30} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-medium text-fg">
                    {engagement.buyer_name}
                  </p>
                  <p className="truncate text-[12px] text-muted">{engagement.plan_title}</p>
                </div>
                <Money amount={engagement.monthly_price} className="text-[13px] text-fg" />
                <Badge tone={engagement.status === "active" ? "positive" : "caution"}>
                  {engagement.cancel_at_period_end ? "Ending" : engagement.status}
                </Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Subscriptions the caller holds                                             */
/* -------------------------------------------------------------------------- */

function EngagementRow({
  engagement,
  onChanged,
}: {
  engagement: RetainerEngagement;
  onChanged: () => void;
}) {
  const cancel = useAsyncAction(professional.cancelRetainer);
  const live = engagement.status === "active" || engagement.status === "past_due";

  return (
    <li className="flex flex-wrap items-center gap-3 px-5 py-4">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[14px] font-medium text-fg">{engagement.plan_title}</p>
        <p className="text-[12.5px] text-muted">
          {engagement.seller_name} ·{" "}
          <Money amount={engagement.monthly_price} />/month · {engagement.months_billed} month
          {engagement.months_billed === 1 ? "" : "s"} in
        </p>
      </div>

      <div className="text-right">
        <Badge tone={engagement.cancel_at_period_end ? "caution" : live ? "positive" : "neutral"}>
          {engagement.cancel_at_period_end ? "Ending" : engagement.status}
        </Badge>
        <p className="mt-1 text-[11.5px] text-subtle">
          {engagement.cancel_at_period_end ? "Ends" : "Renews"}{" "}
          {new Date(engagement.current_period_end).toLocaleDateString()}
        </p>
      </div>

      {live && !engagement.cancel_at_period_end && (
        <Button
          size="sm"
          variant="secondary"
          loading={cancel.pending}
          onClick={async () => {
            if (await cancel.run(engagement.id)) onChanged();
          }}
        >
          Cancel
        </Button>
      )}
      {cancel.error && <p className="w-full text-[12.5px] text-critical">{cancel.error}</p>}
    </li>
  );
}

function BuyingPanel() {
  const engagements = useLoader(() => professional.myRetainers(), []);
  const reload = React.useCallback(() => void engagements.reload(), [engagements]);
  const buying = engagements.data?.buying ?? [];

  if (engagements.loading) return <Skeleton className="h-40" />;

  if (buying.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="wallet" className="size-5" />}
          title="No retainers"
          description="Subscribe to one from the catalogue and it will appear here with its renewal date."
        />
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Your retainers"
        description="Cancelling stops the next renewal — you keep what the current period already covers."
      />
      <ul className="divide-y divide-line">
        {buying.map((engagement) => (
          <EngagementRow key={engagement.id} engagement={engagement} onChanged={reload} />
        ))}
      </ul>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */

type Tab = "browse" | "buying" | "selling";

export default function RetainersPage() {
  const [tab, setTab] = React.useState<Tab>("browse");
  const { rights } = useEntitlements();

  return (
    <>
      <PageHeading
        title="Retainers"
        description="Ongoing work at a fixed monthly fee — a stated set of deliverables every month, rather than a new negotiation every time."
        action={rights && <PlanBadge tier={rights.tier} name={rights.plan_name} />}
      />

      <div className="pb-6">
        <Segmented
          label="Retainers section"
          value={tab}
          onChange={setTab}
          options={[
            { value: "browse", label: "Browse", icon: "search" },
            { value: "buying", label: "Yours", icon: "wallet" },
            { value: "selling", label: "Selling", icon: "briefcase" },
          ]}
        />
      </div>

      <Alert tone="caution" className="mb-6">
        Retainer billing arrives with the wallet in the next release. Subscribing today records the
        engagement and starts the monthly clock; nothing is charged.
      </Alert>

      {/* Switching tabs unmounts the panel, so "Yours" refetches on arrival and
          the new engagement is simply there. */}
      {tab === "browse" && <BrowsePanel onSubscribed={() => setTab("buying")} />}
      {tab === "buying" && <BuyingPanel />}
      {tab === "selling" && <SellingPanel rights={rights} />}
    </>
  );
}
