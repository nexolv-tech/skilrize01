"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

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
  Skeleton,
  Stars,
  Textarea,
  cn,
  type IconName,
} from "@/components/ui";
import { ActivityFeedPanel, MeetingsPanel } from "@/components/integrations";
import { BankTransferPanel, ReleaseEstimate } from "@/components/payments";
import { TwoFactorRequiredPrompt } from "@/components/two-factor";
import {
  contracts,
  type ContractDetail,
  type ContractEvent,
  type Milestone,
  type MilestoneStatus,
  type TimeEntry,
} from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader, useSession } from "@/lib/session";

const MILESTONE_TONE: Record<MilestoneStatus, "neutral" | "accent" | "positive" | "caution"> = {
  pending: "neutral",
  funded: "accent",
  in_progress: "accent",
  delivered: "caution",
  approved: "caution",
  released: "positive",
  cancelled: "neutral",
};

const EVENT_ICON: Record<ContractEvent["kind"], IconName> = {
  message: "send",
  status: "layers",
  funded: "lock",
  delivered: "file",
  released: "wallet",
  time: "clock",
  review: "star",
};

function ReleasePanel({
  amount,
  pending,
  onRelease,
}: {
  amount: string;
  pending: boolean;
  onRelease: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="sm" loading={pending} onClick={onRelease}>
        <Icon name="check" className="size-3.5" strokeWidth={2.4} />
        Accept and release from escrow
      </Button>
      <ReleaseEstimate amount={amount} />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Milestones                                                                 */
/* -------------------------------------------------------------------------- */

function MilestoneRow({
  contract,
  milestone,
  onChanged,
}: {
  contract: ContractDetail;
  milestone: Milestone;
  onChanged: (next: ContractDetail) => void;
}) {
  const isClient = contract.my_role === "client";
  const [note, setNote] = React.useState("");
  const [files, setFiles] = React.useState<File[]>([]);
  const [delivering, setDelivering] = React.useState(false);
  const [funding, setFunding] = React.useState(false);

  const fund = useAsyncAction(async (referenceNote: string) => {
    onChanged(await contracts.fund(contract.id, milestone.id, referenceNote));
    setFunding(false);
  });
  const release = useAsyncAction(async () => {
    onChanged(await contracts.release(contract.id, milestone.id));
  });
  const deliver = useAsyncAction(async () => {
    onChanged(await contracts.deliver(contract.id, milestone.id, note, files));
    setDelivering(false);
    setNote("");
    setFiles([]);
  });

  const error = fund.error ?? release.error ?? deliver.error;
  // Only the two money actions can be refused for a missing second factor;
  // delivering is not gated on it.
  const blockedCode = fund.code ?? release.code;

  return (
    <li className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-[14px] font-medium text-fg">{milestone.title}</h4>
            <Badge tone={MILESTONE_TONE[milestone.status]}>
              {milestone.status.replace("_", " ")}
            </Badge>
          </div>
          {milestone.description && (
            <p className="mt-1 text-[13px] text-muted">{milestone.description}</p>
          )}
          {milestone.due_date && (
            <p className="mt-1 text-[12px] text-subtle">Due {milestone.due_date}</p>
          )}
        </div>
        <p className="shrink-0 text-[15px] font-semibold text-fg">
          <Money amount={milestone.amount} />
        </p>
      </div>

      {milestone.delivery_note && (
        <p className="mt-3 rounded-md border border-line bg-sunken p-3 text-[13px] text-muted">
          {milestone.delivery_note}
        </p>
      )}

      {milestone.deliverable_urls.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {milestone.deliverable_urls.map((file) => (
            <li key={file.url}>
              <a
                href={file.url}
                className="inline-flex items-center gap-1.5 text-[13px] text-accent underline-offset-2 hover:underline"
              >
                <Icon name="file" className="size-3.5" />
                {file.name}
              </a>
            </li>
          ))}
        </ul>
      )}

      {/* Actions available to whichever side is next to act. */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {isClient &&
          milestone.status === "pending" &&
          contract.status === "active" &&
          (funding ? (
            <BankTransferPanel
              amount={milestone.amount}
              pending={fund.pending}
              onConfirm={(referenceNote) => void fund.run(referenceNote)}
              onCancel={() => setFunding(false)}
            />
          ) : (
            <Button size="sm" onClick={() => setFunding(true)}>
              <Icon name="lock" className="size-3.5" />
              Fund <Money amount={milestone.amount} /> into escrow
            </Button>
          ))}

        {!isClient && milestone.status === "pending" && (
          <p className="text-[12.5px] text-caution">
            Not funded yet — do not start work on this milestone.
          </p>
        )}

        {!isClient && (milestone.status === "funded" || milestone.status === "in_progress") && (
          delivering ? (
            <form
              className="w-full space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void deliver.run();
              }}
            >
              <Field label="Delivery note" htmlFor={`note-${milestone.id}`}>
                <Textarea
                  id={`note-${milestone.id}`}
                  rows={3}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="What you are handing over, and anything the client needs to know."
                />
              </Field>
              <div>
                <label
                  htmlFor={`files-${milestone.id}`}
                  className="mb-1.5 block text-[13px] font-medium text-fg"
                >
                  Attach deliverables
                </label>
                <input
                  id={`files-${milestone.id}`}
                  type="file"
                  multiple
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                  className="block w-full text-[13px] text-muted file:mr-3 file:rounded-md file:border-0 file:bg-sunken file:px-3 file:py-1.5 file:text-[13px] file:text-fg"
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" loading={deliver.pending}>
                  Submit delivery
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setDelivering(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <Button size="sm" onClick={() => setDelivering(true)}>
              <Icon name="send" className="size-3.5" />
              Deliver work
            </Button>
          )
        )}

        {isClient && milestone.status === "delivered" && (
          <ReleasePanel
            amount={milestone.amount}
            pending={release.pending}
            onRelease={() => void release.run()}
          />
        )}

        {milestone.status === "released" && (
          <p className="inline-flex items-center gap-1.5 text-[12.5px] text-positive">
            <Icon name="check" className="size-3.5" strokeWidth={2.4} />
            Released {milestone.released_at ? formatRelative(milestone.released_at) : ""}
          </p>
        )}

        {blockedCode !== "two_factor_required" && error && (
          <span className="text-[12.5px] text-critical">{error}</span>
        )}
      </div>

      {/* Enrolment is offered in place rather than as a link to settings: a
          user stopped mid-payment who is sent elsewhere to fix it mostly does
          not come back to finish the payment. */}
      {blockedCode === "two_factor_required" && (
        <div className="mt-4">
          <TwoFactorRequiredPrompt
            onComplete={() => void (fund.code ? fund.run("") : release.run())}
          />
        </div>
      )}
    </li>
  );
}

/* -------------------------------------------------------------------------- */
/* Work diary                                                                 */
/* -------------------------------------------------------------------------- */

function TimeLog({ contract }: { contract: ContractDetail }) {
  const [hours, setHours] = React.useState("");
  const [memo, setMemo] = React.useState("");
  const [day, setDay] = React.useState(() => new Date().toISOString().slice(0, 10));

  const { data, loading, reload } = useLoader(() => contracts.time(contract.id), [contract.id]);
  const entries: TimeEntry[] | null = loading ? null : (data ?? []);
  const load = reload;

  const log = useAsyncAction(async () => {
    await contracts.logTime(contract.id, {
      worked_on: day,
      minutes: Math.round(Number(hours) * 60),
      memo,
    });
    setHours("");
    setMemo("");
    await load();
  });

  const total = (entries ?? []).reduce((sum, entry) => sum + entry.hours, 0);

  return (
    <Card>
      <CardHeader
        title="Work diary"
        description="Time logged against this contract. Manually added time is marked as such and is not protected in a dispute."
        action={
          <span className="tabular text-[13px] font-medium text-fg">
            {total.toFixed(1)} h · <Money amount={contract.logged_amount} />
          </span>
        }
      />

      {contract.my_role === "freelancer" && contract.status === "active" && (
        <form
          className="flex flex-wrap items-end gap-3 border-b border-line p-5"
          onSubmit={(event) => {
            event.preventDefault();
            void log.run();
          }}
        >
          <Field label="Date" htmlFor="worked_on" className="w-40">
            <Input
              id="worked_on"
              type="date"
              required
              value={day}
              onChange={(event) => setDay(event.target.value)}
            />
          </Field>
          <Field label="Hours" htmlFor="hours" className="w-28">
            <Input
              id="hours"
              type="number"
              step="0.25"
              min="0.25"
              required
              value={hours}
              onChange={(event) => setHours(event.target.value)}
              placeholder="2.5"
            />
          </Field>
          <Field label="What you worked on" htmlFor="memo" className="min-w-48 flex-1">
            <Input
              id="memo"
              required
              maxLength={280}
              value={memo}
              onChange={(event) => setMemo(event.target.value)}
              placeholder="Auth refactor and tests"
            />
          </Field>
          <Button type="submit" loading={log.pending} className="mb-0.5">
            Log time
          </Button>
          {log.error && (
            <p className="w-full text-[12.5px] text-critical">{log.error}</p>
          )}
        </form>
      )}

      {entries === null ? (
        <div className="space-y-2 p-5">
          <Skeleton className="h-10 w-full" />
        </div>
      ) : entries.length === 0 ? (
        <EmptyState
          icon={<Icon name="clock" className="size-5" />}
          title="No time logged yet"
          description={
            contract.weekly_hour_limit
              ? `Capped at ${contract.weekly_hour_limit} hours a week by agreement.`
              : undefined
          }
        />
      ) : (
        <ul className="divide-y divide-line">
          {entries.map((entry) => (
            <li key={entry.id} className="flex items-center gap-3 px-5 py-3">
              <span className="tabular w-14 shrink-0 text-[13px] font-medium text-fg">
                {entry.hours}h
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] text-fg">{entry.memo}</p>
                <p className="text-[11.5px] text-subtle">{entry.worked_on}</p>
              </div>
              {entry.is_disputed && <Badge tone="critical">Disputed</Badge>}
              <Badge tone={entry.is_protected ? "positive" : "neutral"}>
                {entry.is_protected ? "Tracked" : "Manual"}
              </Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Review                                                                     */
/* -------------------------------------------------------------------------- */

function StarPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-[13px] text-fg">{label}</span>
      <span className="flex gap-1">
        {[1, 2, 3, 4, 5].map((step) => (
          <button
            key={step}
            type="button"
            aria-label={`${label}: ${step} of 5`}
            aria-pressed={value === step}
            onClick={() => onChange(step)}
            className={cn(
              "rounded-sm p-0.5 transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent",
              step <= value ? "text-brand-500" : "text-line-strong hover:text-brand-400",
            )}
          >
            <svg viewBox="0 0 24 24" width={20} height={20} fill="currentColor" aria-hidden>
              <path d="m12 3 2.9 5.9 6.1.9-4.5 4.3 1.1 6.4-5.6-3-5.6 3 1.1-6.4L3 9.8l6.1-.9L12 3Z" />
            </svg>
          </button>
        ))}
      </span>
    </div>
  );
}

function ReviewPanel({
  contract,
  onSubmitted,
}: {
  contract: ContractDetail;
  onSubmitted: () => void;
}) {
  const isClient = contract.my_role === "client";
  const [scores, setScores] = React.useState<Record<string, number>>({
    overall: 5,
    communication: 5,
    quality: 5,
    deadline: 5,
    value: 5,
    clarity: 5,
    payment_promptness: 5,
  });
  const [comment, setComment] = React.useState("");
  const [result, setResult] = React.useState<string | null>(null);

  const submit = useAsyncAction(async () => {
    const body = isClient
      ? {
          overall: scores.overall,
          communication: scores.communication,
          quality: scores.quality,
          deadline: scores.deadline,
          value: scores.value,
          comment,
        }
      : {
          overall: scores.overall,
          communication: scores.communication,
          clarity: scores.clarity,
          payment_promptness: scores.payment_promptness,
          comment,
        };
    const saved = await contracts.submitReview(contract.id, body);
    setResult(saved.detail);
    onSubmitted();
  });

  if (contract.my_review_id || result) {
    return (
      <Card>
        <CardHeader title="Your review" />
        <div className="p-5">
          <Alert tone={contract.counterparty_review ? "positive" : "neutral"}>
            {result ??
              (contract.counterparty_review
                ? "Both reviews are public."
                : "Saved. It stays hidden until the other side reviews too.")}
          </Alert>
          {contract.counterparty_review && (
            <div className="mt-4 rounded-md border border-line bg-sunken p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[13px] font-medium text-fg">
                  {contract.counterparty_review.author_name}
                </p>
                <Stars value={contract.counterparty_review.overall} />
              </div>
              {contract.counterparty_review.comment && (
                <p className="mt-2 text-[13px] leading-relaxed text-muted">
                  {contract.counterparty_review.comment}
                </p>
              )}
            </div>
          )}
        </div>
      </Card>
    );
  }

  const fields = isClient
    ? [
        ["overall", "Overall"],
        ["communication", "Communication"],
        ["quality", "Quality of work"],
        ["deadline", "Met the deadline"],
        ["value", "Value for money"],
      ]
    : [
        ["overall", "Overall"],
        ["communication", "Communication"],
        ["clarity", "Clarity of the brief"],
        ["payment_promptness", "Paid promptly"],
      ];

  return (
    <Card>
      <CardHeader
        title="Leave a review"
        description="Neither review is published until both sides have written one — so nobody can react to what the other said."
      />
      <form
        className="space-y-4 p-5"
        onSubmit={(event) => {
          event.preventDefault();
          void submit.run();
        }}
      >
        {submit.error && <Alert tone="critical">{submit.error}</Alert>}

        <div className="divide-y divide-line rounded-md border border-line px-4">
          {fields.map(([key, label]) => (
            <StarPicker
              key={key}
              label={label!}
              value={scores[key!] ?? 5}
              onChange={(next) => setScores((current) => ({ ...current, [key!]: next }))}
            />
          ))}
        </div>

        <Field label="Comment" htmlFor="comment" hint="Public once both reviews are in.">
          <Textarea
            id="comment"
            rows={4}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="What was it like to work together?"
          />
        </Field>

        <Button type="submit" loading={submit.pending}>
          Submit review
        </Button>
      </form>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */

export default function ContractDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useSession();

  const [message, setMessage] = React.useState("");

  const { data, loading, reload, setData } = useLoader(async () => {
    const detail = await contracts.detail(params.id);
    const timeline = await contracts.events(params.id).catch(() => [] as ContractEvent[]);
    return { detail, timeline };
  }, [params.id]);

  const contract: ContractDetail | null = data?.detail ?? null;
  const events: ContractEvent[] | null = loading ? null : (data?.timeline ?? []);
  const load = reload;

  /** Fold a fresh contract into the loaded pair without a second round trip. */
  const applyContract = React.useCallback(
    (next: ContractDetail) => setData((current) => (current ? { ...current, detail: next } : current)),
    [setData],
  );

  const accept = useAsyncAction(async () => {
    applyContract(await contracts.accept(contract!.id));
    await load();
  });

  const send = useAsyncAction(async () => {
    await contracts.postMessage(contract!.id, message);
    setMessage("");
    await load();
  });

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!contract) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name="briefcase" className="size-5" />}
          title="Contract not available"
          description="You are not a party to this contract, or it no longer exists."
          action={
            <Link href="/contracts">
              <Button variant="secondary">Back to contracts</Button>
            </Link>
          }
        />
      </Card>
    );
  }

  const other = contract.my_role === "client" ? contract.freelancer : contract.client;
  const hourly = contract.contract_type === "hourly";

  return (
    <>
      <Link
        href="/contracts"
        className="mb-5 inline-flex items-center gap-1.5 text-[13px] text-muted transition-colors hover:text-fg"
      >
        <Icon name="chevronLeft" className="size-3.5" />
        All contracts
      </Link>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          {/* Header */}
          <Card className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={contract.status === "completed" ? "positive" : "accent"}>
                    {contract.status}
                  </Badge>
                  <Badge>
                    {hourly
                      ? "Hourly"
                      : contract.contract_type === "milestone"
                        ? "Milestones"
                        : "Fixed price"}
                  </Badge>
                </div>
                <h1 className="mt-3 text-[24px] font-semibold leading-tight tracking-[-0.025em] text-fg">
                  {contract.title}
                </h1>
                {contract.project && (
                  <Link
                    href={`/projects/${contract.project}`}
                    className="mt-1 inline-block text-[12.5px] text-accent underline-offset-2 hover:underline"
                  >
                    View the original brief
                  </Link>
                )}
              </div>

              <div className="shrink-0 text-right">
                <p className="text-[20px] font-semibold text-fg">
                  <Money amount={contract.total_amount ?? contract.hourly_rate} />
                  {hourly && <span className="text-[13px] font-normal text-muted">/hr</span>}
                </p>
                <p className="text-[12px] text-subtle">
                  <Money amount={contract.released_amount} /> released
                </p>
              </div>
            </div>

            {contract.status === "pending" && contract.my_role === "freelancer" && (
              <Alert tone="caution" title="This offer is waiting for you" className="mt-5">
                Accepting freezes the terms below. Neither side can change them afterwards without
                a formal amendment.
                <div className="mt-3">
                  <Button size="sm" loading={accept.pending} onClick={() => void accept.run()}>
                    Accept contract
                  </Button>
                </div>
                {accept.error && (
                  <p className="mt-2 text-[12.5px] text-critical">{accept.error}</p>
                )}
              </Alert>
            )}

            {contract.status === "pending" && contract.my_role === "client" && (
              <Alert tone="neutral" className="mt-5">
                Waiting for {other.display_name} to accept.
              </Alert>
            )}
          </Card>

          {/* Milestones */}
          {!hourly && (
            <Card>
              <CardHeader
                title="Milestones"
                description="Fund a stage, then the freelancer delivers it, then you release the payment."
                action={
                  <span className="text-[13px] text-muted">
                    <Money amount={contract.funded_amount} /> held
                  </span>
                }
              />
              <ul className="divide-y divide-line">
                {contract.milestones.map((milestone) => (
                  <MilestoneRow
                    key={milestone.id}
                    contract={contract}
                    milestone={milestone}
                    onChanged={(next) => {
                      applyContract(next);
                      void load();
                    }}
                  />
                ))}
              </ul>
            </Card>
          )}

          {hourly && <TimeLog contract={contract} />}

          {/* Review */}
          {contract.status === "completed" && (
            <ReviewPanel contract={contract} onSubmitted={load} />
          )}

          {/* Integrations */}
          <MeetingsPanel contractId={contract.id} />
          <ActivityFeedPanel contractId={contract.id} />

          {/* Activity */}
          <Card>
            <CardHeader
              title="Activity"
              description="Messages, deliveries, and payments in one thread — the whole history of this contract."
            />

            <div className="max-h-[32rem] overflow-y-auto p-5">
              {events === null ? (
                <Skeleton className="h-20 w-full" />
              ) : events.length === 0 ? (
                <p className="text-[13px] text-subtle">Nothing yet.</p>
              ) : (
                <ol className="space-y-4">
                  {events.map((event) => {
                    const mine = event.actor_name && event.actor_id === user?.id;
                    return (
                      <li key={event.id} className="flex gap-3">
                        <span
                          className={cn(
                            "mt-0.5 grid size-7 shrink-0 place-items-center rounded-full",
                            event.kind === "message"
                              ? "bg-sunken text-muted"
                              : "bg-accent-soft text-accent",
                          )}
                        >
                          <Icon name={EVENT_ICON[event.kind]} className="size-3.5" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[12px] text-subtle">
                            {event.actor_name ?? "System"}
                            {mine && " (you)"} · {formatRelative(event.created_at)}
                          </p>
                          {event.body && (
                            <p className="mt-0.5 whitespace-pre-wrap text-[13.5px] leading-relaxed text-fg">
                              {event.body}
                            </p>
                          )}
                          {event.attachment_urls.length > 0 && (
                            <ul className="mt-1.5 space-y-1">
                              {event.attachment_urls.map((file) => (
                                <li key={file.url}>
                                  <a
                                    href={file.url}
                                    className="inline-flex items-center gap-1.5 text-[12.5px] text-accent underline-offset-2 hover:underline"
                                  >
                                    <Icon name="file" className="size-3" />
                                    {file.name}
                                  </a>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>

            <form
              className="flex gap-2 border-t border-line p-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (message.trim()) void send.run();
              }}
            >
              <label htmlFor="composer" className="sr-only">
                Message
              </label>
              <Input
                id="composer"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder={`Message ${other.display_name}…`}
              />
              <Button type="submit" loading={send.pending} disabled={!message.trim()}>
                <Icon name="send" className="size-4" />
                Send
              </Button>
            </form>
            {send.error && (
              <p className="px-4 pb-3 text-[12.5px] text-critical">{send.error}</p>
            )}
          </Card>
        </div>

        {/* Sidebar */}
        <aside className="space-y-6">
          <Card>
            <CardHeader title={contract.my_role === "client" ? "Freelancer" : "Client"} />
            <div className="p-5">
              <div className="flex items-center gap-3">
                <Avatar name={other.display_name} src={other.avatar_url} size={44} />
                <div className="min-w-0">
                  <p className="truncate text-[14px] font-medium text-fg">{other.display_name}</p>
                  {other.headline && (
                    <p className="truncate text-[12.5px] text-subtle">{other.headline}</p>
                  )}
                </div>
              </div>
              {other.is_verified_student && (
                <Badge tone="accent" className="mt-3">
                  {other.university_name ?? "Verified student"}
                </Badge>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Money" />
            <dl className="space-y-3 p-5 text-[13px]">
              {[
                ["Contract value", contract.total_amount ?? contract.hourly_rate],
                ["Held in escrow", contract.funded_amount],
                ["Released", contract.released_amount],
                ...(hourly ? [["Logged so far", contract.logged_amount] as const] : []),
              ].map(([label, amount]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-muted">{label}</dt>
                  <dd className="font-medium text-fg">
                    <Money amount={amount} />
                  </dd>
                </div>
              ))}
            </dl>
          </Card>

          {contract.status === "pending" || contract.status === "active" ? (
            <Card className="p-5">
              <div className="flex gap-3">
                <Icon name="shield" className="mt-0.5 size-4 shrink-0 text-positive" />
                <p className="text-[12.5px] leading-relaxed text-muted">
                  Funds are held by the platform until the client accepts a delivery. If a delivery
                  goes unanswered, the review window expires into automatic release.
                </p>
              </div>
            </Card>
          ) : null}
        </aside>
      </div>
    </>
  );
}
