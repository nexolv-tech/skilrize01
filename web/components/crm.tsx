"use client";

/**
 * The CRM panels.
 *
 * Stage changes are a `<select>` on each card rather than drag-and-drop. Drag
 * is the expected gesture on a pipeline board, but it is unusable by keyboard
 * without a parallel implementation and awkward on the phone screens most of
 * this audience works from — and a select is the parallel implementation, so
 * building it first means the board works for everyone on day one.
 */

import * as React from "react";

import { ActionError } from "@/components/professional";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Icon,
  Input,
  Money,
  Select,
  Skeleton,
  Textarea,
  cn,
} from "@/components/ui";
import {
  professional,
  type CrmContact,
  type CrmDeal,
  type CrmTask,
  type DealStage,
  type PipelineSummary,
} from "@/lib/api";
import { formatRelative, useAsyncAction, useLoader } from "@/lib/session";

const OPEN_STAGES: Array<{ value: DealStage; label: string }> = [
  { value: "lead", label: "Lead" },
  { value: "qualified", label: "Qualified" },
  { value: "proposed", label: "Proposal sent" },
  { value: "negotiating", label: "Negotiating" },
];

const ALL_STAGES: Array<{ value: DealStage; label: string }> = [
  ...OPEN_STAGES,
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

const SOURCES = [
  { value: "platform", label: "SkilRize" },
  { value: "referral", label: "Referral" },
  { value: "direct", label: "Direct outreach" },
  { value: "repeat", label: "Repeat client" },
  { value: "other", label: "Other" },
];

const INTERACTION_KINDS = [
  { value: "note", label: "Note" },
  { value: "call", label: "Call" },
  { value: "email", label: "Email" },
  { value: "meeting", label: "Meeting" },
  { value: "proposal", label: "Proposal sent" },
];

/* -------------------------------------------------------------------------- */
/* Pipeline                                                                   */
/* -------------------------------------------------------------------------- */

function DealCard({ deal, onMove }: { deal: CrmDeal; onMove: () => void }) {
  const move = useAsyncAction(professional.moveDeal);
  const [askingReason, setAskingReason] = React.useState(false);
  const [reason, setReason] = React.useState("");

  async function change(stage: DealStage) {
    // "Lost" is the one transition worth interrupting for. The reason is the
    // only field in the pipeline that turns a dead deal into something you can
    // learn from, and nobody ever goes back to fill it in later.
    if (stage === "lost") {
      setAskingReason(true);
      return;
    }
    if (await move.run(deal.id, stage)) onMove();
  }

  return (
    <div className="rounded-md border border-line bg-raised p-3 shadow-e1">
      <p className="text-[13px] font-medium leading-snug text-fg">{deal.title}</p>
      <p className="mt-0.5 truncate text-[12px] text-muted">{deal.contact_name}</p>

      <div className="mt-2.5 flex items-center justify-between gap-2">
        <Money amount={deal.value} className="text-[13px] font-semibold text-fg" />
        {deal.expected_close && (
          <span className="text-[11.5px] text-subtle">
            {new Date(deal.expected_close).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })}
          </span>
        )}
      </div>

      {askingReason ? (
        <div className="mt-2.5 space-y-2">
          <Input
            autoFocus
            value={reason}
            placeholder="Why was it lost?"
            onChange={(event) => setReason(event.target.value)}
            className="h-8 text-[12.5px]"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="danger"
              loading={move.pending}
              onClick={async () => {
                if (await move.run(deal.id, "lost", reason)) {
                  setAskingReason(false);
                  onMove();
                }
              }}
            >
              Mark lost
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setAskingReason(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Select
          aria-label={`Stage for ${deal.title}`}
          value={deal.stage}
          disabled={move.pending}
          onChange={(event) => void change(event.target.value as DealStage)}
          className="mt-2.5 h-8 text-[12.5px]"
        >
          {ALL_STAGES.map((stage) => (
            <option key={stage.value} value={stage.value}>
              {stage.label}
            </option>
          ))}
        </Select>
      )}

      {move.error && <p className="mt-1.5 text-[12px] text-critical">{move.error}</p>}
    </div>
  );
}

function NewDealForm({ contacts, onDone }: { contacts: CrmContact[]; onDone: () => void }) {
  const create = useAsyncAction(professional.createDeal);
  const [form, setForm] = React.useState({ contact: "", title: "", value: "", expected_close: "" });

  if (contacts.length === 0) {
    return (
      <Alert tone="neutral">Add a contact first — every deal hangs off one.</Alert>
    );
  }

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={async (event) => {
        event.preventDefault();
        const created = await create.run({
          contact: Number(form.contact || contacts[0]?.id),
          title: form.title,
          value: form.value || "0",
          expected_close: form.expected_close || null,
        });
        if (created) {
          setForm({ contact: "", title: "", value: "", expected_close: "" });
          onDone();
        }
      }}
    >
      <Field label="Contact" htmlFor="deal-contact" required className="sm:col-span-1">
        <Select
          id="deal-contact"
          required
          value={form.contact}
          onChange={(event) => setForm({ ...form, contact: event.target.value })}
        >
          <option value="">Choose a contact…</option>
          {contacts.map((contact) => (
            <option key={contact.id} value={contact.id}>
              {contact.name}
              {contact.company ? ` — ${contact.company}` : ""}
            </option>
          ))}
        </Select>
      </Field>

      <Field label="What is the work?" htmlFor="deal-title" required>
        <Input
          id="deal-title"
          required
          maxLength={200}
          value={form.title}
          placeholder="Brand refresh for the spring launch"
          onChange={(event) => setForm({ ...form, title: event.target.value })}
        />
      </Field>

      <Field label="Value" htmlFor="deal-value" hint="What you expect to bill, in rupees.">
        <Input
          id="deal-value"
          type="number"
          min={0}
          step="0.01"
          value={form.value}
          onChange={(event) => setForm({ ...form, value: event.target.value })}
        />
      </Field>

      <Field label="Expected close" htmlFor="deal-close">
        <Input
          id="deal-close"
          type="date"
          value={form.expected_close}
          onChange={(event) => setForm({ ...form, expected_close: event.target.value })}
        />
      </Field>

      <div className="sm:col-span-2">
        <Button type="submit" loading={create.pending}>
          Add to pipeline
        </Button>
        <ActionError error={create.error} code={create.code} />
      </div>
    </form>
  );
}

export function PipelinePanel({
  summary,
  onChanged,
}: {
  summary: PipelineSummary | null;
  onChanged: () => void;
}) {
  const [adding, setAdding] = React.useState(false);
  const deals = useLoader(() => professional.deals({ open: "true" }), []);
  const contacts = useLoader(() => professional.contacts(), []);

  const reload = React.useCallback(() => {
    void deals.reload();
    onChanged();
  }, [deals, onChanged]);

  const byStage = React.useMemo(() => {
    const map = new Map<DealStage, CrmDeal[]>(OPEN_STAGES.map((s) => [s.value, []]));
    for (const deal of deals.data?.results ?? []) map.get(deal.stage)?.push(deal);
    return map;
  }, [deals.data]);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Open pipeline", value: summary?.open_value, money: true },
          { label: "Won", value: summary?.won_value, money: true },
          {
            label: "Win rate",
            value:
              summary?.win_rate === null || summary?.win_rate === undefined
                ? "—"
                : `${summary.win_rate}%`,
          },
          { label: "Contacts", value: summary?.contacts?.toString() },
        ].map((stat) => (
          <Card key={stat.label} className="p-5">
            <p className="text-[12.5px] text-muted">{stat.label}</p>
            {!summary ? (
              <Skeleton className="mt-2 h-7 w-24" />
            ) : stat.money ? (
              <Money
                amount={stat.value}
                className="mt-1 block text-xl font-semibold tracking-[-0.02em] text-fg"
              />
            ) : (
              <p className="tabular mt-1 text-xl font-semibold tracking-[-0.02em] text-fg">
                {stat.value ?? "—"}
              </p>
            )}
          </Card>
        ))}
      </div>

      {summary && summary.overdue_tasks > 0 && (
        <Alert tone="caution">
          {summary.overdue_tasks} follow-up{summary.overdue_tasks === 1 ? " is" : "s are"} overdue.
        </Alert>
      )}

      <Card>
        <CardHeader
          title="Pipeline"
          description="Open deals only. Won and lost move out of the board once you set the stage."
          action={
            <Button size="sm" variant={adding ? "ghost" : "secondary"} onClick={() => setAdding(!adding)}>
              {adding ? "Close" : <><Icon name="plus" className="size-3.5" /> New deal</>}
            </Button>
          }
        />
        {adding && (
          <div className="border-b border-line p-5">
            <NewDealForm
              contacts={contacts.data?.results ?? []}
              onDone={() => {
                setAdding(false);
                reload();
              }}
            />
          </div>
        )}

        {deals.loading ? (
          <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((key) => (
              <Skeleton key={key} className="h-40" />
            ))}
          </div>
        ) : (deals.data?.results.length ?? 0) === 0 ? (
          <EmptyState
            icon={<Icon name="chart" className="size-5" />}
            title="Nothing in the pipeline"
            description="Track the work you are chasing here — leads from the platform and everywhere else, in one place."
          />
        ) : (
          <div className="grid gap-4 overflow-x-auto p-5 sm:grid-cols-2 lg:grid-cols-4">
            {OPEN_STAGES.map((stage) => {
              const column = byStage.get(stage.value) ?? [];
              const total = column.reduce((sum, deal) => sum + Number(deal.value), 0);
              return (
                <section key={stage.value} className="min-w-56 space-y-3">
                  <header className="flex items-baseline justify-between gap-2 border-b border-line pb-2">
                    <h3 className="text-[13px] font-semibold text-fg">{stage.label}</h3>
                    <span className="tabular text-[12px] text-subtle">{column.length}</span>
                  </header>
                  {total > 0 && (
                    <Money amount={total} className="block text-[12px] text-muted" />
                  )}
                  {column.map((deal) => (
                    <DealCard key={deal.id} deal={deal} onMove={reload} />
                  ))}
                </section>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Contacts                                                                   */
/* -------------------------------------------------------------------------- */

function InteractionLog({ contact }: { contact: CrmContact }) {
  const log = useLoader(() => professional.interactions(contact.id), [contact.id]);
  const add = useAsyncAction(professional.logInteraction);
  const [draft, setDraft] = React.useState({ kind: "note", body: "" });

  return (
    <div className="space-y-4">
      <form
        className="space-y-3"
        onSubmit={async (event) => {
          event.preventDefault();
          if (await add.run(contact.id, draft)) {
            setDraft({ kind: "note", body: "" });
            void log.reload();
          }
        }}
      >
        <div className="flex gap-2">
          <Select
            aria-label="Kind"
            value={draft.kind}
            onChange={(event) => setDraft({ ...draft, kind: event.target.value })}
            className="h-9 w-36 shrink-0 text-[13px]"
          >
            {INTERACTION_KINDS.map((kind) => (
              <option key={kind.value} value={kind.value}>
                {kind.label}
              </option>
            ))}
          </Select>
          <Input
            required
            value={draft.body}
            placeholder="What happened?"
            onChange={(event) => setDraft({ ...draft, body: event.target.value })}
            className="h-9 text-[13px]"
          />
          <Button size="sm" type="submit" loading={add.pending}>
            Log
          </Button>
        </div>
        {add.error && <p className="text-[12.5px] text-critical">{add.error}</p>}
      </form>

      {log.loading ? (
        <Skeleton className="h-20" />
      ) : (log.data?.length ?? 0) === 0 ? (
        <p className="text-[13px] text-subtle">Nothing logged yet.</p>
      ) : (
        <ol className="space-y-3">
          {log.data?.map((entry) => (
            <li key={entry.id} className="flex gap-3 text-[13px]">
              <Badge tone="neutral" className="mt-px shrink-0 capitalize">
                {entry.kind}
              </Badge>
              <div className="min-w-0 flex-1">
                <p className="leading-relaxed text-fg">{entry.body}</p>
                <p className="mt-0.5 text-[11.5px] text-subtle">
                  {formatRelative(entry.occurred_at)}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function NewContactForm({ onDone }: { onDone: () => void }) {
  const create = useAsyncAction(professional.createContact);
  const [form, setForm] = React.useState({
    name: "",
    company: "",
    email: "",
    phone: "",
    source: "platform",
    notes: "",
  });

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={async (event) => {
        event.preventDefault();
        if (await create.run(form)) {
          setForm({ name: "", company: "", email: "", phone: "", source: "platform", notes: "" });
          onDone();
        }
      }}
    >
      <Field label="Name" htmlFor="contact-name" required error={create.fieldErrors.name}>
        <Input
          id="contact-name"
          required
          maxLength={120}
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
      </Field>
      <Field label="Company" htmlFor="contact-company">
        <Input
          id="contact-company"
          maxLength={120}
          value={form.company}
          onChange={(event) => setForm({ ...form, company: event.target.value })}
        />
      </Field>
      <Field label="Email" htmlFor="contact-email" error={create.fieldErrors.email}>
        <Input
          id="contact-email"
          type="email"
          value={form.email}
          onChange={(event) => setForm({ ...form, email: event.target.value })}
        />
      </Field>
      <Field label="Phone" htmlFor="contact-phone">
        <Input
          id="contact-phone"
          value={form.phone}
          onChange={(event) => setForm({ ...form, phone: event.target.value })}
        />
      </Field>
      <Field label="Where did they come from?" htmlFor="contact-source">
        <Select
          id="contact-source"
          value={form.source}
          onChange={(event) => setForm({ ...form, source: event.target.value })}
        >
          {SOURCES.map((source) => (
            <option key={source.value} value={source.value}>
              {source.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Notes" htmlFor="contact-notes" className="sm:col-span-2">
        <Textarea
          id="contact-notes"
          value={form.notes}
          onChange={(event) => setForm({ ...form, notes: event.target.value })}
        />
      </Field>
      <div className="sm:col-span-2">
        <Button type="submit" loading={create.pending}>
          Save contact
        </Button>
        <ActionError error={create.error} code={create.code} />
      </div>
    </form>
  );
}

export function ContactsPanel({ onChanged }: { onChanged: () => void }) {
  const [query, setQuery] = React.useState("");
  const [debounced, setDebounced] = React.useState("");
  const [adding, setAdding] = React.useState(false);
  const [openId, setOpenId] = React.useState<number | null>(null);

  React.useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const contacts = useLoader(
    () => professional.contacts({ q: debounced || undefined }),
    [debounced],
  );

  return (
    <Card>
      <CardHeader
        title="Contacts"
        description="Everyone you do business with, whether or not they have an account here."
        action={
          <Button size="sm" variant={adding ? "ghost" : "secondary"} onClick={() => setAdding(!adding)}>
            {adding ? "Close" : <><Icon name="plus" className="size-3.5" /> New contact</>}
          </Button>
        }
      />

      {adding && (
        <div className="border-b border-line p-5">
          <NewContactForm
            onDone={() => {
              setAdding(false);
              void contacts.reload();
              onChanged();
            }}
          />
        </div>
      )}

      <div className="border-b border-line p-4">
        <div className="relative">
          <Icon
            name="search"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle"
          />
          <Input
            value={query}
            placeholder="Search by name, company, or email"
            onChange={(event) => setQuery(event.target.value)}
            className="pl-9"
            aria-label="Search contacts"
          />
        </div>
      </div>

      {contacts.loading ? (
        <div className="space-y-3 p-5">
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-14" />
          ))}
        </div>
      ) : (contacts.data?.results.length ?? 0) === 0 ? (
        <EmptyState
          icon={<Icon name="users" className="size-5" />}
          title={debounced ? "No matches" : "No contacts yet"}
          description={
            debounced
              ? "Try a different name or company."
              : "Add the people you are talking to, and the pipeline has somewhere to hang."
          }
        />
      ) : (
        <ul className="divide-y divide-line">
          {contacts.data?.results.map((contact) => {
            const open = openId === contact.id;
            return (
              <li key={contact.id}>
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenId(open ? null : contact.id)}
                  className={cn(
                    "flex w-full items-center gap-4 px-5 py-3.5 text-left",
                    "transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent",
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-medium text-fg">{contact.name}</p>
                    <p className="truncate text-[12.5px] text-muted">
                      {[contact.company, contact.email].filter(Boolean).join(" · ") || "—"}
                    </p>
                  </div>
                  <div className="hidden shrink-0 text-right sm:block">
                    {contact.open_deals > 0 && (
                      <p className="text-[12.5px] text-muted">
                        {contact.open_deals} open ·{" "}
                        <Money amount={contact.pipeline_value} className="font-medium text-fg" />
                      </p>
                    )}
                    {contact.last_interaction_at && (
                      <p className="text-[11.5px] text-subtle">
                        {formatRelative(contact.last_interaction_at)}
                      </p>
                    )}
                  </div>
                  <Icon
                    name="chevronDown"
                    className={cn("size-4 shrink-0 text-subtle transition-transform", open && "rotate-180")}
                  />
                </button>
                {open && (
                  <div className="border-t border-line bg-sunken/40 px-5 py-4">
                    {contact.notes && (
                      <p className="mb-4 whitespace-pre-wrap text-[13px] leading-relaxed text-muted">
                        {contact.notes}
                      </p>
                    )}
                    <InteractionLog contact={contact} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Tasks                                                                      */
/* -------------------------------------------------------------------------- */

export function TasksPanel({ onChanged }: { onChanged: () => void }) {
  const [openOnly, setOpenOnly] = React.useState(true);
  const tasks = useLoader(
    () => professional.tasks(openOnly ? { open: "true" } : {}),
    [openOnly],
  );
  const create = useAsyncAction(professional.createTask);
  const toggle = useAsyncAction(professional.toggleTask);
  const [draft, setDraft] = React.useState({ title: "", due_at: "" });

  return (
    <Card>
      <CardHeader
        title="Follow-ups"
        description="The next thing you owe somebody. Overdue items surface on the pipeline too."
        action={
          <Button size="sm" variant="ghost" onClick={() => setOpenOnly(!openOnly)}>
            {openOnly ? "Show all" : "Show open only"}
          </Button>
        }
      />

      <form
        className="flex flex-wrap gap-2 border-b border-line p-5"
        onSubmit={async (event) => {
          event.preventDefault();
          const created = await create.run({
            title: draft.title,
            // datetime-local has no zone; the browser's own offset is the right
            // reading of "3pm" for the person who typed it.
            due_at: draft.due_at ? new Date(draft.due_at).toISOString() : null,
          });
          if (created) {
            setDraft({ title: "", due_at: "" });
            void tasks.reload();
            onChanged();
          }
        }}
      >
        <Input
          required
          value={draft.title}
          placeholder="Call Ayesha about the retainer"
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          className="min-w-48 flex-1"
          aria-label="What needs doing"
        />
        <Input
          type="datetime-local"
          value={draft.due_at}
          onChange={(event) => setDraft({ ...draft, due_at: event.target.value })}
          className="w-56"
          aria-label="Due"
        />
        <Button type="submit" loading={create.pending}>
          Add
        </Button>
      </form>
      {create.error && (
        <div className="border-b border-line px-5 py-3">
          <Alert tone="critical">{create.error}</Alert>
        </div>
      )}

      {tasks.loading ? (
        <div className="space-y-3 p-5">
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-10" />
          ))}
        </div>
      ) : (tasks.data?.results.length ?? 0) === 0 ? (
        <EmptyState
          icon={<Icon name="check" className="size-5" />}
          title={openOnly ? "Nothing outstanding" : "No follow-ups yet"}
          description="Anything you add here with a due date will flag as overdue once it passes."
        />
      ) : (
        <ul className="divide-y divide-line">
          {tasks.data?.results.map((task: CrmTask) => {
            const done = Boolean(task.completed_at);
            return (
              <li key={task.id} className="flex items-center gap-3 px-5 py-3">
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={done}
                  aria-label={`Mark ${task.title} ${done ? "not done" : "done"}`}
                  disabled={toggle.pending}
                  onClick={async () => {
                    if (await toggle.run(task.id)) {
                      void tasks.reload();
                      onChanged();
                    }
                  }}
                  className={cn(
                    "grid size-5 shrink-0 place-items-center rounded-[6px] border transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                    done
                      ? "border-positive bg-positive text-white"
                      : "border-line-strong hover:border-accent",
                  )}
                >
                  {done && <Icon name="check" className="size-3" strokeWidth={3} />}
                </button>

                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      "text-[13.5px] text-fg",
                      done && "text-subtle line-through",
                    )}
                  >
                    {task.title}
                  </p>
                  {task.due_at && (
                    <p
                      className={cn(
                        "text-[11.5px]",
                        task.is_overdue && !done ? "font-medium text-critical" : "text-subtle",
                      )}
                    >
                      {task.is_overdue && !done ? "Overdue — " : "Due "}
                      {new Date(task.due_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
