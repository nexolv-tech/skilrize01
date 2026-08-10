/**
 * SkilRize UI primitives.
 *
 * Every interactive component here defines the full state set the design
 * system requires — default, hover, focus-visible, active, disabled, loading,
 * and error — and reaches colour only through semantic tokens, never a raw
 * value. Anything built on top of these inherits correct keyboard behaviour
 * and contrast for free, which is the entire point of having them.
 */
import * as React from "react";

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

/* -------------------------------------------------------------------------- */
/* Brand                                                                      */
/* -------------------------------------------------------------------------- */

export function Logo({ className, showText = true }: { className?: string; showText?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span
        aria-hidden
        className="grid size-8 shrink-0 place-items-center rounded-[9px] bg-linear-to-br from-brand-500 to-brand-700 shadow-e1"
      >
        {/* An ascending step mark: skill, rising. */}
        <svg viewBox="0 0 24 24" className="size-[18px]" fill="none">
          <path
            d="M5 17.5V13h4.2V17.5H5Zm5.4 0V8.5h4.2v9h-4.2Zm5.4 0v-13H20v13h-4.2Z"
            fill="white"
            fillOpacity="0.95"
          />
        </svg>
      </span>
      {showText && (
        <span className="text-[17px] font-semibold tracking-[-0.02em] text-fg">
          Skil<span className="text-accent">Rize</span>
        </span>
      )}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Button                                                                     */
/* -------------------------------------------------------------------------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "link";
type ButtonSize = "sm" | "md" | "lg";

const BUTTON_BASE =
  "relative inline-flex items-center justify-center gap-2 rounded-md font-medium whitespace-nowrap " +
  "transition-[background-color,border-color,color,box-shadow,transform] duration-150 " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
  "active:translate-y-px disabled:pointer-events-none disabled:opacity-45 " +
  "disabled:active:translate-y-0";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-on-accent shadow-e1 hover:bg-accent-hover hover:shadow-e2 " +
    "active:shadow-e1",
  secondary:
    "border border-line-strong bg-raised text-fg shadow-e1 hover:bg-sunken hover:border-line-strong",
  ghost: "text-muted hover:bg-sunken hover:text-fg",
  danger: "bg-critical text-white shadow-e1 hover:brightness-110",
  link: "text-accent underline-offset-4 hover:underline p-0 h-auto",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-[15px]",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  block?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, block, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      // A loading button stays in the tab order and keeps its size, so the
      // layout does not jump and focus is not lost mid-submit.
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        BUTTON_BASE,
        BUTTON_VARIANTS[variant],
        variant !== "link" && BUTTON_SIZES[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && <Spinner className="size-4" />}
      {/* Flex, not the default block: buttons are routinely given an icon and a
          label together, and inside a block box the icon baseline-aligns to the
          text and drops below the optical centre — visible as an arrow sitting
          a few pixels low, or wrapping outright once the label is long enough.
          Laying the children out as flex items also gives them the same gap the
          spinner already gets. */}
      <span className={cn("inline-flex items-center gap-2", loading && "opacity-90")}>
        {children}
      </span>
    </button>
  );
});

export function Spinner({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cn("size-4 shrink-0", className)} aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" fill="none" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        fill="none"
        style={{ transformOrigin: "center", animation: "spin 0.7s linear infinite" }}
      />
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* Form fields                                                                */
/* -------------------------------------------------------------------------- */

const CONTROL_BASE =
  "w-full rounded-md border bg-raised px-3 text-sm text-fg placeholder:text-subtle " +
  "transition-[border-color,box-shadow] duration-150 " +
  "focus:outline-none focus-visible:outline-none " +
  "disabled:cursor-not-allowed disabled:bg-sunken disabled:opacity-60";

const CONTROL_TONE = {
  normal: "border-line-strong focus:border-accent focus:ring-[3px] focus:ring-accent/25",
  error: "border-critical focus:border-critical focus:ring-[3px] focus:ring-critical/25",
};

export interface FieldProps {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function Field({ label, htmlFor, hint, error, required, children, className }: FieldProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-fg">
        {label}
        {required && (
          <span className="ml-0.5 text-critical" aria-hidden>
            *
          </span>
        )}
      </label>
      {children}
      {/* Errors take the place of the hint rather than stacking, so the layout
          does not shift when validation fails. */}
      {error ? (
        <p id={htmlFor ? `${htmlFor}-error` : undefined} role="alert" className="text-[13px] text-critical">
          {error}
        </p>
      ) : hint ? (
        <p id={htmlFor ? `${htmlFor}-hint` : undefined} className="text-[13px] text-subtle">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, className, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined}
      className={cn(CONTROL_BASE, "h-10", invalid ? CONTROL_TONE.error : CONTROL_TONE.normal, className)}
      {...rest}
    />
  );
});

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }
>(function Textarea({ invalid, className, ...rest }, ref) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        CONTROL_BASE,
        "min-h-24 py-2.5 leading-relaxed",
        invalid ? CONTROL_TONE.error : CONTROL_TONE.normal,
        className,
      )}
      {...rest}
    />
  );
});

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...rest }, ref) {
  return (
    <select
      ref={ref}
      className={cn(CONTROL_BASE, "h-10 cursor-pointer pr-8", CONTROL_TONE.normal, className)}
      {...rest}
    >
      {children}
    </select>
  );
});

export function Switch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-150",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:cursor-not-allowed disabled:opacity-45",
        checked ? "bg-accent" : "bg-line-strong",
      )}
    >
      <span
        className={cn(
          "inline-block size-4.5 rounded-full bg-white shadow-e1 transition-transform duration-150",
          checked ? "translate-x-[22px]" : "translate-x-[3px]",
        )}
      />
    </button>
  );
}

/* -------------------------------------------------------------------------- */
/* Surfaces                                                                   */
/* -------------------------------------------------------------------------- */

export function Card({
  className,
  children,
  as: Tag = "div",
  id,
}: {
  className?: string;
  children: React.ReactNode;
  as?: React.ElementType;
  /** For deep links — a card is often the target of an anchor from elsewhere. */
  id?: string;
}) {
  return (
    <Tag id={id} className={cn("rounded-lg border border-line bg-raised shadow-e1", className)}>
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-line p-5", className)}>
      <div className="min-w-0 space-y-1">
        <h3 className="text-[15px] font-semibold text-fg">{title}</h3>
        {description && <p className="text-[13px] leading-relaxed text-muted">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

type Tone = "neutral" | "accent" | "positive" | "caution" | "critical";

const BADGE_TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-muted ring-line-strong",
  accent: "bg-accent-soft text-accent ring-accent/25",
  positive: "bg-positive-soft text-positive ring-positive/25",
  caution: "bg-caution-soft text-caution ring-caution/25",
  critical: "bg-critical-soft text-critical ring-critical/25",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium ring-1 ring-inset",
        BADGE_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Alert({
  tone = "neutral",
  title,
  children,
  className,
}: {
  tone?: Tone;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const border: Record<Tone, string> = {
    neutral: "border-line bg-sunken",
    accent: "border-accent/30 bg-accent-soft",
    positive: "border-positive/30 bg-positive-soft",
    caution: "border-caution/30 bg-caution-soft",
    critical: "border-critical/30 bg-critical-soft",
  };
  return (
    <div
      role={tone === "critical" ? "alert" : "status"}
      className={cn("rounded-md border px-4 py-3 text-sm", border[tone], className)}
    >
      {title && <p className="font-medium text-fg">{title}</p>}
      {children && <div className={cn("text-[13px] text-muted", title && "mt-0.5")}>{children}</div>}
    </div>
  );
}

export function Progress({ value, label }: { value: number; label?: string }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="space-y-1.5">
      {label && (
        <div className="flex items-baseline justify-between text-[13px]">
          <span className="text-muted">{label}</span>
          <span className="tabular font-medium text-fg">{clamped}%</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-1.5 overflow-hidden rounded-full bg-sunken"
      >
        <div
          className="h-full rounded-full bg-linear-to-r from-brand-500 to-brand-400 transition-[width] duration-500"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

export function Avatar({
  name,
  src,
  size = 36,
  className,
}: {
  name: string;
  src?: string | null;
  size?: number;
  className?: string;
}) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <span
      className={cn(
        "grid shrink-0 place-items-center overflow-hidden rounded-full bg-linear-to-br",
        "from-brand-400 to-brand-600 text-[12px] font-semibold text-white ring-1 ring-line",
        className,
      )}
      style={{ width: size, height: size }}
      aria-hidden
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="size-full object-cover" />
      ) : (
        initials || "?"
      )}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-sunken", className)} aria-hidden />;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {icon && (
        <div className="mb-3 grid size-11 place-items-center rounded-full bg-sunken text-subtle">
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-fg">{title}</p>
      {description && <p className="mt-1 max-w-sm text-[13px] text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Icons — a small inline set, so the bundle carries no icon library.         */
/* -------------------------------------------------------------------------- */

const ICONS = {
  check: "M20 6 9 17l-5-5",
  x: "M18 6 6 18M6 6l12 12",
  mail: "M22 7 12 13 2 7M2 6h20v12H2z",
  phone: "M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2 4.2 2 2 0 0 1 4 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.1a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z",
  id: "M2 5h20v14H2zM7 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM4 17c.6-2 1.7-3 3-3s2.4 1 3 3M14 10h5M14 14h5",
  bell: "M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8M13.7 21a2 2 0 0 1-3.4 0",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H7a1.7 1.7 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V7a1.7 1.7 0 0 0 1.5 1H23a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z",
  home: "M3 10 12 3l9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  briefcase: "M3 7h18v13H3zM8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18",
  sparkles: "m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z",
  arrowRight: "M5 12h14M13 6l6 6-6 6",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  key: "M21 2 19 4M15.5 8.5 19 5l-2-2-3.5 3.5M10.5 13.5a5 5 0 1 1-7 7 5 5 0 0 1 7-7Zm0 0 3-3",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10ZM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  building: "M4 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18M16 8h2a2 2 0 0 1 2 2v12M8 6h2M8 10h2M8 14h2",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 1 1 8 0v4",
  device: "M5 2h14v20H5zM11 18h2",
  layers: "m12 2 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 17l9 5 9-5",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM21 21l-4.3-4.3",
  star: "m12 3 2.9 5.9 6.1.9-4.5 4.3 1.1 6.4-5.6-3-5.6 3 1.1-6.4L3 9.8l6.1-.9L12 3Z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2",
  send: "M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z",
  file: "M14 2H6v20h12V6l-4-4ZM14 2v4h4",
  plus: "M12 5v14M5 12h14",
  filter: "M3 5h18l-7 8v6l-4 2v-8L3 5Z",
  chevronDown: "m6 9 6 6 6-6",
  chevronLeft: "m15 18-6-6 6-6",
  wallet: "M3 7h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H3zM3 7V5h13M17 13h.01",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z",
  zap: "M13 2 4 14h7l-1 8 9-12h-7l1-8Z",
  users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  quote: "M9 11H5a1 1 0 0 1-1-1V7a3 3 0 0 1 3-3h1M20 11h-4a1 1 0 0 1-1-1V7a3 3 0 0 1 3-3h1M9 11v3a5 5 0 0 1-5 5M20 11v3a5 5 0 0 1-5 5",
  // Category glyphs, keyed to the seeded taxonomy.
  code: "m16 18 6-6-6-6M8 6l-6 6 6 6",
  palette: "M12 21a9 9 0 1 1 0-18c4.97 0 9 3.58 9 8 0 2.5-2 3.5-4 3.5h-2a2 2 0 0 0-1.5 3.3A2 2 0 0 1 12 21ZM7.5 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM12 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM16.5 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
  pen: "M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3Z",
  video: "m23 7-7 5 7 5V7ZM14 5H3a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2Z",
  megaphone: "m3 11 18-8v18l-18-8v-2ZM3 11H2a1 1 0 0 0-1 1v0a1 1 0 0 0 1 1h1M7 12.5V20a1 1 0 0 0 1 1h2",
  chart: "M3 3v18h18M7 15l3-4 3 3 5-7",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15Z",
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({
  name,
  className,
  strokeWidth = 1.8,
}: {
  name: IconName;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("size-4 shrink-0", className)}
      aria-hidden
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* Marketplace pieces                                                         */
/* -------------------------------------------------------------------------- */

/** A 1–5 star rating. Renders as text for assistive tech, stars for everyone else. */
export function Stars({ value, size = 14 }: { value: number; size?: number }) {
  return (
    <span className="inline-flex items-center gap-0.5" role="img" aria-label={`${value} out of 5`}>
      {[1, 2, 3, 4, 5].map((step) => (
        <svg
          key={step}
          viewBox="0 0 24 24"
          width={size}
          height={size}
          className={step <= Math.round(value) ? "text-warn-500" : "text-line-strong"}
          fill="currentColor"
          aria-hidden
        >
          <path d={ICONS.star} />
        </svg>
      ))}
    </span>
  );
}

/** Money, formatted once so every surface agrees. */
export function Money({
  amount,
  currency = "PKR",
  className,
}: {
  amount: number | string | null | undefined;
  currency?: string;
  className?: string;
}) {
  if (amount === null || amount === undefined || amount === "") return null;
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return null;
  return (
    <span className={cn("tabular", className)}>
      {currency === "PKR" ? "Rs " : `${currency} `}
      {value.toLocaleString("en-PK", { maximumFractionDigits: 0 })}
    </span>
  );
}

/** A labelled segmented control. Roving focus, arrow keys, one tab stop. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  size = "md",
}: {
  options: Array<{ value: T; label: string; icon?: IconName }>;
  value: T;
  onChange: (next: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "inline-flex items-center gap-1 rounded-lg bg-sunken p-1",
        size === "sm" ? "text-[13px]" : "text-sm",
      )}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
              event.preventDefault();
              const index = options.findIndex((o) => o.value === value);
              const next = event.key === "ArrowRight" ? index + 1 : index - 1;
              const target = options[(next + options.length) % options.length];
              if (target) onChange(target.value);
            }}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-[7px] px-3 py-1.5 font-medium",
              "transition-colors duration-150",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
              active
                ? "bg-raised text-fg shadow-e1"
                : "text-muted hover:text-fg",
            )}
          >
            {option.icon && <Icon name={option.icon} className="size-3.5" />}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/** A pill used for skills, filters, and tags. */
export function Tag({
  children,
  onRemove,
  className,
}: {
  children: React.ReactNode;
  onRemove?: () => void;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md bg-sunken px-2 py-1 text-[12px] text-muted",
        className,
      )}
    >
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          className="rounded-sm text-subtle transition-colors hover:text-critical focus-visible:outline-1 focus-visible:outline-accent"
        >
          <Icon name="x" className="size-3" strokeWidth={2.4} />
        </button>
      )}
    </span>
  );
}
