"use client";

/**
 * The cookie notice.
 *
 * A notice, not a consent prompt, and deliberately so. SkilRize sets only
 * cookies that are strictly necessary for a service the visitor asked for —
 * staying signed in, and protecting forms against cross-site forgery — which
 * the ePrivacy Directive (Art. 5(3)) and the GDPR exempt from consent. There
 * is no analytics, advertising or third-party cookie to consent to, and a
 * "reject all" button that changed nothing would be a dark pattern of its own.
 * What the law does require is telling people plainly, which this does, with
 * the full list one click away at /cookies.
 */

import * as React from "react";
import Link from "next/link";

const STORAGE_KEY = "skilrize.cookie-notice";
const EVENT = "skilrize:cookie-notice";

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function isDismissed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    // Storage blocked (private mode, strict settings): show nothing rather
    // than a notice that can never be dismissed.
    return true;
  }
}

export function CookieNotice() {
  // Rendered as dismissed on the server so the first paint never flashes a
  // banner at someone who already closed it.
  const dismissed = React.useSyncExternalStore(subscribe, isDismissed, () => true);

  if (dismissed) return null;

  function dismiss() {
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore — see isDismissed */
    }
    window.dispatchEvent(new Event(EVENT));
  }

  return (
    <section
      aria-label="Cookie notice"
      className="animate-rise fixed inset-x-3 bottom-3 z-50 mx-auto max-w-xl rounded-lg border border-line bg-raised p-4 shadow-e3 sm:inset-x-auto sm:right-5 sm:bottom-5"
    >
      <p className="text-[13.5px] leading-relaxed text-fg">
        SkilRize uses only essential cookies — to keep you signed in and protect your forms.
        No advertising or tracking cookies.{" "}
        <Link
          href="/cookies"
          className="font-medium text-accent underline underline-offset-4 hover:text-accent-hover"
        >
          Cookie policy
        </Link>
      </p>
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={dismiss}
          className="inline-flex h-9 cursor-pointer items-center rounded-md bg-action px-4 text-[13px] font-semibold text-on-action transition-colors hover:bg-action-hover"
        >
          OK, got it
        </button>
      </div>
    </section>
  );
}
