"use client";

/**
 * Live password policy feedback.
 *
 * These rules are a mirror of `accounts/validators.py` and `AUTH_PASSWORD_
 * VALIDATORS`, and they are guidance only — the server is the authority and
 * re-checks every one of them, plus the breach corpus and the similarity check
 * that cannot run in the browser. The mirror exists so a user is told what is
 * wrong *while typing* rather than after a round trip; it must never be the
 * thing that decides whether the password is accepted.
 *
 * Keeping the two in step matters: a rule that appears here but not on the
 * server is a lie, and a rule on the server but not here is a rejection the
 * user cannot see coming. If you change one, change the other.
 */

import * as React from "react";

import { Icon, cn } from "@/components/ui";

export const PASSWORD_MIN_LENGTH = 12;

/** Ordered alphabets and keyboard rows — the walks people reach for. */
const SEQUENCES = [
  "abcdefghijklmnopqrstuvwxyz",
  "01234567890",
  "qwertyuiop",
  "asdfghjkl",
  "zxcvbnm",
  "!@#$%^&*()",
];

const RUN_LENGTH = 4;

function hasPredictableRun(password: string): boolean {
  const lowered = password.toLowerCase();
  if (new RegExp(`(.)\\1{${RUN_LENGTH - 1},}`).test(lowered)) return true;

  for (const sequence of SEQUENCES) {
    for (let start = 0; start <= sequence.length - RUN_LENGTH; start += 1) {
      const window = sequence.slice(start, start + RUN_LENGTH);
      const reversed = [...window].reverse().join("");
      if (lowered.includes(window) || lowered.includes(reversed)) return true;
    }
  }
  return false;
}

export interface PasswordRule {
  label: string;
  passed: boolean;
}

export function evaluatePassword(password: string): PasswordRule[] {
  return [
    { label: `At least ${PASSWORD_MIN_LENGTH} characters`, passed: password.length >= PASSWORD_MIN_LENGTH },
    { label: "A lowercase letter", passed: /[a-z]/.test(password) },
    { label: "An uppercase letter", passed: /[A-Z]/.test(password) },
    { label: "A digit", passed: /\d/.test(password) },
    { label: "A symbol", passed: /[^A-Za-z0-9\s]/.test(password) },
    { label: "No runs or sequences (aaaa, 1234, qwer)", passed: !hasPredictableRun(password) },
  ];
}

/**
 * A checklist rather than a strength bar.
 *
 * A bar answers "how good is this?", which a user cannot act on. A checklist
 * answers "what is still missing?", which they can — and since the policy here
 * is a set of hard requirements rather than a score, the checklist is also the
 * honest representation of it.
 */
export function PasswordPolicy({
  password,
  className,
}: {
  password: string;
  className?: string;
}) {
  const rules = React.useMemo(() => evaluatePassword(password), [password]);
  const met = rules.filter((rule) => rule.passed).length;
  const complete = met === rules.length;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-3">
        <div className="flex flex-1 gap-1" aria-hidden>
          {rules.map((rule, index) => (
            <span
              key={rule.label}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors duration-300",
                index < met ? (complete ? "bg-positive" : "bg-caution") : "bg-sunken",
              )}
            />
          ))}
        </div>
        <span
          className={cn(
            "w-28 shrink-0 text-right text-[12px] font-medium transition-colors",
            complete ? "text-positive" : "text-muted",
          )}
          aria-live="polite"
        >
          {complete ? "Meets policy" : `${met} of ${rules.length}`}
        </span>
      </div>

      <ul className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {rules.map((rule) => (
          <li
            key={rule.label}
            className={cn(
              "flex items-center gap-1.5 text-[12px] transition-colors duration-200",
              rule.passed ? "text-positive" : "text-subtle",
            )}
          >
            <Icon
              name={rule.passed ? "check" : "x"}
              className="size-3 shrink-0"
              strokeWidth={3}
            />
            {rule.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
