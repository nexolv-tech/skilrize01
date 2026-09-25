"use client";

/**
 * Building blocks shared by the admin console's pages (D54).
 *
 * The console is a set of work queues, so most of what is here is about
 * acting on a row safely: every action that changes something for a user
 * asks for its reason first, says what will happen, and reports the
 * server's refusal in words rather than failing quietly.
 */

import * as React from "react";
import Link from "next/link";

import {
  Alert,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Skeleton,
  Textarea,
  cn,
  type IconName,
} from "@/components/ui";
import type { AdminPerson, AdminRole, Paginated } from "@/lib/api";

/** Whether `role` works in an area open to `roles` (null: every admin).
 *  Super Admin works everywhere, as the API's `require_admin_role` has it. */
export function canSee(role: AdminRole, roles: AdminRole[] | null) {
  return roles === null || role === "super_admin" || roles.includes(role);
}

/* -------------------------------------------------------------------------- */
/* Layout                                                                     */
/* -------------------------------------------------------------------------- */

export function AdminHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="display-md text-fg">{title}</h1>
        {description && <p className="mt-2 text-[14px] leading-relaxed text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/** A row of tabs, each optionally carrying a count. */
export function AdminTabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: Array<{ value: T; label: string; count?: number }>;
  value: T;
  onChange: (next: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={value === tab.value}
          onClick={() => onChange(tab.value)}
          className={cn(
            "-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-[13.5px] font-medium transition-colors duration-150",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            value === tab.value
              ? "border-action text-fg"
              : "border-transparent text-muted hover:text-fg",
          )}
        >
          {tab.label}
          {tab.count !== undefined && tab.count > 0 && <CountPill value={tab.count} />}
        </button>
      ))}
    </div>
  );
}

export function CountPill({ value, className }: { value: number; className?: string }) {
  return (
    <span
      className={cn(
        "figure inline-grid h-5 min-w-5 place-items-center rounded-full bg-action px-1.5 text-[11px] font-semibold text-on-action",
        className,
      )}
    >
      {value > 99 ? "99+" : value}
    </span>
  );
}

/** "To do / done" for a queue. */
export function StateSwitch<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (next: T) => void;
  options: Array<{ value: T; label: string }>;
}) {
  return (
    <div role="group" className="inline-flex rounded-lg border border-line bg-sunken p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "rounded-[7px] px-3 py-1.5 text-[13px] font-medium transition-colors duration-150",
            value === option.value ? "bg-raised text-fg shadow-e1" : "text-muted hover:text-fg",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Lists                                                                      */
/* -------------------------------------------------------------------------- */

/** Loading, empty and paged states for a list of rows, so every queue
 *  behaves the same. */
export function AdminList<T>({
  data,
  loading,
  empty,
  page,
  onPage,
  children,
}: {
  data: Paginated<T> | T[] | null;
  loading: boolean;
  empty: { title: string; description?: string; icon?: IconName };
  page?: number;
  onPage?: (next: number) => void;
  children: (row: T) => React.ReactNode;
}) {
  if (loading && !data) {
    return (
      <Card className="divide-y divide-line">
        {[0, 1, 2].map((row) => (
          <div key={row} className="space-y-2 p-5">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        ))}
      </Card>
    );
  }
  const rows = Array.isArray(data) ? data : (data?.results ?? []);
  if (rows.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<Icon name={empty.icon ?? "check"} className="size-5" />}
          title={empty.title}
          description={empty.description}
        />
      </Card>
    );
  }
  const paged = !Array.isArray(data) && data ? data : null;
  return (
    <>
      <Card className={cn("divide-y divide-line", loading && "opacity-60")}>
        {rows.map((row) => children(row))}
      </Card>
      {paged && page !== undefined && onPage && (paged.next || paged.previous) && (
        <div className="mt-4 flex items-center justify-between gap-3 text-[13px] text-muted">
          <span>
            Page {page} · {paged.count} in all
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" disabled={!paged.previous} onClick={() => onPage(page - 1)}>
              Previous
            </Button>
            <Button size="sm" variant="secondary" disabled={!paged.next} onClick={() => onPage(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  );
}

/** Who someone is, linking to their account in the console. */
export function PersonLink({ person, label }: { person: AdminPerson | null; label?: string }) {
  if (!person) return <span className="text-subtle">—</span>;
  return (
    <span className="min-w-0">
      {label && <span className="text-subtle">{label} </span>}
      <Link
        href={`/admin/users?q=${encodeURIComponent(person.email)}`}
        className="font-medium text-fg underline-offset-4 hover:underline"
      >
        {person.name}
      </Link>{" "}
      <span className="text-subtle">{person.email}</span>
    </span>
  );
}

/** A labelled figure on the overview. */
export function Figure({
  label,
  value,
  hint,
  href,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  href?: string;
}) {
  const body = (
    <>
      <span className="block text-[12.5px] text-muted">{label}</span>
      <span className="figure mt-1 block text-[22px] font-semibold text-fg">{value}</span>
      {hint && <span className="mt-0.5 block text-[12px] text-subtle">{hint}</span>}
    </>
  );
  const frame = "block rounded-lg border border-line bg-raised p-4";
  return href ? (
    <Link
      href={href}
      className={cn(frame, "transition-colors duration-150 hover:border-fg/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent")}
    >
      {body}
    </Link>
  ) : (
    <div className={frame}>{body}</div>
  );
}

/* -------------------------------------------------------------------------- */
/* Acting on a row                                                            */
/* -------------------------------------------------------------------------- */

/**
 * A button that opens a short form before acting: the reason (or transfer
 * reference) is recorded in the audit log and, where it says so, sent to
 * the person affected.
 */
export function ActionWithInput({
  label,
  confirmLabel,
  prompt,
  placeholder,
  required = true,
  singleLine = false,
  tone = "secondary",
  onConfirm,
  disabled,
}: {
  label: string;
  confirmLabel: string;
  prompt: string;
  placeholder?: string;
  required?: boolean;
  singleLine?: boolean;
  tone?: "secondary" | "danger" | "primary";
  onConfirm: (text: string) => Promise<unknown>;
  disabled?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const [text, setText] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function confirm() {
    setPending(true);
    setError(null);
    try {
      await onConfirm(text.trim());
      setOpen(false);
      setText("");
    } catch (caught) {
      setError((caught as { message?: string }).message ?? "That did not work. Try again.");
    } finally {
      setPending(false);
    }
  }

  if (!open) {
    return (
      <Button
        size="sm"
        variant={tone === "danger" ? "secondary" : tone}
        className={tone === "danger" ? "text-critical" : undefined}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
    );
  }

  const Field = singleLine ? Input : Textarea;
  return (
    <div className="w-full space-y-2 rounded-lg border border-line bg-sunken/60 p-3">
      <label className="block text-[12.5px] font-medium text-fg">
        {prompt}
        <Field
          className="mt-1.5"
          placeholder={placeholder}
          value={text}
          autoFocus
          onChange={(event: React.ChangeEvent<HTMLInputElement & HTMLTextAreaElement>) =>
            setText(event.target.value)
          }
          {...(singleLine ? {} : { rows: 2 })}
        />
      </label>
      {error && <Alert tone="critical">{error}</Alert>}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant={tone === "danger" ? "danger" : "primary"}
          loading={pending}
          disabled={required && text.trim().length < 3}
          onClick={() => void confirm()}
        >
          {confirmLabel}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

/** A one-click action with its own pending state and error. */
export function QuickAction({
  label,
  onRun,
  variant = "secondary",
  icon,
}: {
  label: string;
  onRun: () => Promise<unknown>;
  variant?: "primary" | "secondary" | "ghost";
  icon?: IconName;
}) {
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  return (
    <span className="inline-flex flex-col gap-1">
      <Button
        size="sm"
        variant={variant}
        loading={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          try {
            await onRun();
          } catch (caught) {
            setError((caught as { message?: string }).message ?? "That did not work.");
          } finally {
            setPending(false);
          }
        }}
      >
        {icon && <Icon name={icon} className="size-3.5" />}
        {label}
      </Button>
      {error && <span className="text-[12px] text-critical">{error}</span>}
    </span>
  );
}

/** Rows of a status, in the site's own words. */
export function StatusText({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "positive" | "caution" | "critical" }) {
  return (
    <span
      className={cn(
        "text-[12.5px] font-medium",
        tone === "positive" && "text-positive",
        tone === "caution" && "text-caution",
        tone === "critical" && "text-critical",
        tone === "muted" && "text-muted",
      )}
    >
      {children}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Finding rows                                                               */
/* -------------------------------------------------------------------------- */

/** A search box that applies on Enter, with filter chips beside it. */
export function FilterBar<T extends string>({
  query,
  onQuery,
  placeholder,
  chips,
  value,
  onChip,
}: {
  query: string;
  onQuery: (next: string) => void;
  placeholder: string;
  chips: Array<{ value: T; label: string }>;
  value: T;
  onChip: (next: T) => void;
}) {
  const input = React.useRef<HTMLInputElement>(null);
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3">
      <form
        className="relative min-w-56 flex-1"
        onSubmit={(event) => {
          event.preventDefault();
          onQuery(input.current?.value.trim() ?? "");
        }}
      >
        <Icon
          name="search"
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle"
        />
        <Input
          ref={input}
          key={query}
          defaultValue={query}
          type="search"
          aria-label={placeholder}
          placeholder={placeholder}
          className="pl-9"
        />
      </form>
      <div className="flex gap-1.5 overflow-x-auto">
        {chips.map((chip) => (
          <button
            key={chip.value}
            type="button"
            aria-pressed={value === chip.value}
            onClick={() => onChip(chip.value)}
            className={cn(
              "shrink-0 rounded-full border px-3 py-1.5 text-[12.5px] font-medium transition-colors duration-150",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
              value === chip.value
                ? "border-fg bg-fg text-surface"
                : "border-line text-muted hover:border-fg/40 hover:text-fg",
            )}
          >
            {chip.label}
          </button>
        ))}
      </div>
    </div>
  );
}
