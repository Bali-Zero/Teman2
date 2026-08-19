/**
 * Second Home Studio — plan persistence codec (spec §5, SavePlanBar).
 *
 * Wizard answers never leave the browser: they live in component state,
 * `localStorage` (key `bz_shs_plan_v1`), and a base64url-encoded URL
 * fragment for "copy plan link". Nothing is posted anywhere.
 *
 * Every function here is defensive-by-construction: a malformed fragment,
 * a wrong schema version, an oversized payload, a corrupted localStorage
 * value, or an SSR environment with no `window` all resolve to a safe
 * fallback (`null` or a fresh plan) — NEVER a throw. This module runs both
 * server-side (the thin page.tsx shell) and client-side (StudioApp), so
 * every `window`/`localStorage` touch is guarded.
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
  return (
    typeof window !== "undefined" &&
    typeof window.localStorage !== "undefined" &&
    window.localStorage !== null
  );
}

/** Minimal structural check — enough to reject garbage/foreign JSON and a
 *  schema-version mismatch without over-fitting to every field's type. */
function isValidPlanShape(value: unknown): value is PlanState {
  if (typeof value !== "object" || value === null) return false;
  const obj = value as Record<string, unknown>;
  if (obj.v !== 1) return false;
  if (typeof obj.family !== "object" || obj.family === null) return false;
  if (typeof obj.checklist !== "object" || obj.checklist === null) return false;
  if (typeof obj.updatedAt !== "string") return false;
  return true;
}

export function savePlan(p: PlanState): void {
  if (!hasLocalStorage()) return;
  try {
    window.localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(p));
  } catch {
    // Storage full, blocked (private mode), or unavailable — no-op.
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
 * plan" action — copy deck §7, `savePlan.clearButton`). SSR-safe, never
 * throws: no-op when there is no `window`/`localStorage`, or when the key
 * was never set.
 */
export function clearPlan(): void {
  if (!hasLocalStorage()) return;
  try {
    window.localStorage.removeItem(PLAN_STORAGE_KEY);
  } catch {
    // Storage blocked/unavailable — no-op.
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
