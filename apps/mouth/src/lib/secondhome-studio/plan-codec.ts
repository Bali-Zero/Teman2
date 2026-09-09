/**
 * Second Home Studio — plan persistence codec (spec §5, SavePlanBar).
 *
 * Wizard answers stay client-side within THIS module: they live in
 * component state, `localStorage` (key `bz_shs_plan_v1`), and a
 * base64url-encoded URL fragment for "copy plan link". This module itself
 * posts nothing anywhere — the two surfaces that DO share a plan outside
 * the browser are the copied plan link (a URL the user chooses to send)
 * and the WhatsApp handoff (`WhatsAppHandoff`/`whatsapp-bullets.ts`), which
 * POSTs a lead capture to `/api/lead/capture` when the user taps the CTA
 * (P0-C3/C4, P1-B).
 *
 * Every function here is defensive-by-construction: a malformed fragment,
 * a wrong schema version, an oversized payload, a corrupted localStorage
 * value, or an SSR environment with no `window` all resolve to a safe
 * fallback (`null` or a fresh plan) — NEVER a throw. This module runs both
 * server-side (the thin page.tsx shell) and client-side (StudioApp), so
 * every `window`/`localStorage` touch is guarded — INCLUDING the
 * `window.localStorage` property access itself (P2-C12): it is a getter
 * that can throw `SecurityError` in opaque-origin/strict-privacy contexts
 * merely by being read, before any method call on it.
 */

import type { PlanState } from "./types";

export const PLAN_STORAGE_KEY = "bz_shs_plan_v1";

/** Fragment size ceiling. Base64url is pure ASCII, so char length ==
 *  byte length here — no separate UTF-8 byte-counting pass needed. */
const MAX_FRAGMENT_BYTES = 8 * 1024;

const BASE64URL_RE = /^[A-Za-z0-9_-]*$/;

export function emptyPlan(): PlanState {
  return {
    v: 1,
    age: null,
    route: null,
    capital: null,
    seniorFunding: null,
    property: null,
    family: { spouse: false, children: 0, parents: 0 },
    horizon: null,
    location: null,
    checklist: {},
    updatedAt: new Date().toISOString(),
  };
}

function hasLocalStorage(): boolean {
  if (typeof window === "undefined") return false;
  try {
    // P2-C12: `window.localStorage` is a GETTER — merely reading it (the
    // `typeof` check below) can throw `SecurityError` in opaque-origin or
    // strict-privacy-mode contexts, before any method is ever called on
    // the returned object. The try/catch has to wrap the property access
    // itself, not just the calls made against it.
    return (
      typeof window.localStorage !== "undefined" && window.localStorage !== null
    );
  } catch {
    return false;
  }
}

// P0-C1 (Codex-verified): every PlanState enum field must be validated by
// PRESENCE + whitelist membership, not just "not null". A fragment that
// simply OMITS a key (e.g. age/route absent) previously sailed through as
// `undefined`, and `evaluatePlan`'s `=== null` guards let `undefined` slip
// past as if it were a real answer — a crafted link could manufacture a
// strong_fit verdict this way. Every set below mirrors types.ts verbatim.
const AGE_BANDS = new Set<string>(["under_55", "55_59", "60_plus"]);
const ROUTE_INTENTS = new Set<string>(["deposit", "property", "unsure"]);
const CAPITAL_BANDS = new Set<string>([
  "ready_130k",
  "close_100k_130k",
  "below_100k",
]);
const SENIOR_FUNDINGS = new Set<string>([
  "deposit_50k_income",
  "income_only_3k",
  "neither",
  "not_applicable",
]);
const PROPERTY_STATUSES = new Set<string>([
  "owns_qualifying_strata",
  "buying_completed_strata",
  "villa_land_leasehold",
  "none",
]);
const TIMELINE_HORIZONS = new Set<string>([
  "asap",
  "this_quarter",
  "exploring",
]);
const LOCATIONS = new Set<string>(["in_indonesia", "abroad"]);

/** `undefined` (an ABSENT key) is neither `null` nor a set member, so it is
 *  correctly rejected here without a separate presence check. */
function isNullOrOneOf(value: unknown, allowed: Set<string>): boolean {
  return value === null || (typeof value === "string" && allowed.has(value));
}

function isValidFamily(value: unknown): value is PlanState["family"] {
  if (typeof value !== "object" || value === null) return false;
  const f = value as Record<string, unknown>;
  return (
    typeof f.spouse === "boolean" &&
    typeof f.children === "number" &&
    f.children >= 0 &&
    typeof f.parents === "number" &&
    f.parents >= 0
  );
}

function isValidChecklist(value: unknown): value is Record<string, boolean> {
  if (typeof value !== "object" || value === null) return false;
  return Object.values(value as Record<string, unknown>).every(
    (v) => typeof v === "boolean",
  );
}

/** Full structural check — every PlanState field is validated by presence
 *  and type/whitelist, never just "not null" (P0-C1, absorbs/supersedes
 *  P2-1). Any violation anywhere resolves to `false` — a fresh plan is
 *  always safer than a partially-trusted one. */
function isValidPlanShape(value: unknown): value is PlanState {
  if (typeof value !== "object" || value === null) return false;
  const obj = value as Record<string, unknown>;

  if (obj.v !== 1) return false;
  if (!isNullOrOneOf(obj.age, AGE_BANDS)) return false;
  if (!isNullOrOneOf(obj.route, ROUTE_INTENTS)) return false;
  if (!isNullOrOneOf(obj.capital, CAPITAL_BANDS)) return false;
  if (!isNullOrOneOf(obj.seniorFunding, SENIOR_FUNDINGS)) return false;
  if (!isNullOrOneOf(obj.property, PROPERTY_STATUSES)) return false;
  if (!isNullOrOneOf(obj.horizon, TIMELINE_HORIZONS)) return false;
  if (!isNullOrOneOf(obj.location, LOCATIONS)) return false;
  if (!isValidFamily(obj.family)) return false;
  if (!isValidChecklist(obj.checklist)) return false;
  if (typeof obj.updatedAt !== "string") return false;

  return true;
}

/** True only after storage accepts the write, so callers can give honest feedback. */
export function savePlan(p: PlanState): boolean {
  if (!hasLocalStorage()) return false;
  try {
    window.localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(p));
    return true;
  } catch {
    // Storage full, blocked (private mode), or unavailable — keep the plan in memory.
    return false;
  }
}

export function loadPlan(): PlanState | null {
  if (!hasLocalStorage()) return null;
  try {
    const raw = window.localStorage.getItem(PLAN_STORAGE_KEY);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isValidPlanShape(parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Removes the saved plan from localStorage (SavePlanBar's "Clear saved
 * plan" action — copy deck §7, `savePlan.clearButton`) AND strips any
 * `#p=...` plan fragment from the current URL (P2-C11) — otherwise a
 * "cleared" plan reappears on the next reload because the fragment still
 * decodes to the old answers. SSR-safe, never throws: no-op when there is
 * no `window`/`localStorage`/`history`, or when nothing was ever saved.
 */
export function clearPlan(): void {
  if (hasLocalStorage()) {
    try {
      window.localStorage.removeItem(PLAN_STORAGE_KEY);
    } catch {
      // Storage blocked/unavailable — no-op.
    }
  }

  if (typeof window !== "undefined") {
    try {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
    } catch {
      // history API unavailable/blocked — no-op.
    }
  }
}

/** UTF-8-safe string -> base64url. Works in Node (Buffer, used by tests and
 *  SSR) and in the browser (TextEncoder + btoa, used by the client bundle)
 *  without deprecated escape/unescape. */
function toBase64Url(input: string): string {
  const bytes = new TextEncoder().encode(input);

  let base64: string;
  if (typeof Buffer !== "undefined") {
    base64 = Buffer.from(bytes).toString("base64");
  } else if (typeof btoa === "function") {
    let binary = "";
    for (const b of bytes) binary += String.fromCharCode(b);
    base64 = btoa(binary);
  } else {
    return "";
  }

  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Inverse of toBase64Url. Returns null on any decode failure — never
 *  throws out of this function. */
function fromBase64Url(value: string): string | null {
  try {
    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const padLength = (4 - (base64.length % 4)) % 4;
    const padded = base64 + "=".repeat(padLength);

    if (typeof Buffer !== "undefined") {
      return new TextDecoder().decode(Buffer.from(padded, "base64"));
    }
    if (typeof atob === "function") {
      const binary = atob(padded);
      const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
      return new TextDecoder().decode(bytes);
    }
    return null;
  } catch {
    return null;
  }
}

export function encodePlanFragment(p: PlanState): string {
  return toBase64Url(JSON.stringify(p));
}

/**
 * Decodes a base64url plan fragment back into a PlanState. Never throws:
 * malformed base64, a wrong schema version, an oversized fragment (>8KB),
 * or anything that fails to parse as valid PlanState-shaped JSON all
 * resolve to `null` so the caller can fall back to a fresh plan.
 */
export function decodePlanFragment(hash: string): PlanState | null {
  if (typeof hash !== "string" || hash.length === 0) return null;
  if (hash.length > MAX_FRAGMENT_BYTES) return null;
  if (!BASE64URL_RE.test(hash)) return null;

  try {
    const json = fromBase64Url(hash);
    if (json === null) return null;

    const parsed: unknown = JSON.parse(json);
    if (!isValidPlanShape(parsed)) return null;

    return parsed;
  } catch {
    return null;
  }
}
