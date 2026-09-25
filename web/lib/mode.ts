"use client";

/**
 * Buying or selling: which side of the one account the signed-in header and
 * the dashboard are arranged around.
 *
 * Every account can do both (signup creates a buyer and a seller profile
 * together), so this is a view, not a permission. Nothing on the server reads
 * it, and nothing is hidden from the other side: it only decides which links
 * the header leads with and which summary the dashboard opens on. Kept per
 * browser in localStorage, like the Global/Campus choice.
 */

import * as React from "react";

export type Mode = "buying" | "selling";

const STORAGE_KEY = "skilrize.mode";
/** Same-tab listeners; the `storage` event only fires in other tabs. */
const CHANGE_EVENT = "skilrize:mode";

/** Holds the choice for this page when storage is blocked. */
let unsaved: Mode = "buying";

function read(): Mode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "selling" || stored === "buying" ? stored : unsaved;
  } catch {
    return unsaved;
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

export function useMode(): [Mode, (next: Mode) => void] {
  // The server renders buying; a stored "selling" takes over after hydration.
  const mode = React.useSyncExternalStore(subscribe, read, () => "buying" as const);
  const setMode = React.useCallback((next: Mode) => {
    unsaved = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private mode or blocked storage: the switch still works for this page.
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);
  return [mode, setMode];
}
