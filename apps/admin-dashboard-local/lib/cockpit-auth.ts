/**
 * Cockpit auth: bcrypt PIN + in-memory rate-limit.
 * Rate-limit per-client-ID: 5 failures in 5min window → 5min lockout.
 * Panel finding 4-LLM v2: rate-limit active from S1 (NOT deferred to S5).
 */
import bcrypt from "bcryptjs";

const MAX_FAILURES = 5;
const WINDOW_MS = 5 * 60 * 1000;
const LOCKOUT_MS = 5 * 60 * 1000;

interface FailureRecord {
  count: number;
  firstFailureAt: number;
  lockedUntil: number;
}

const failureMap = new Map<string, FailureRecord>();

export async function verifyPin(pin: string, hash: string): Promise<boolean> {
  if (!pin || !hash || typeof pin !== "string") return false;
  try {
    return await bcrypt.compare(pin, hash);
  } catch {
    return false;
  }
}

export function recordFailure(clientId: string): void {
  const now = Date.now();
  const r = failureMap.get(clientId);
  if (!r || now - r.firstFailureAt > WINDOW_MS) {
    failureMap.set(clientId, {
      count: 1,
      firstFailureAt: now,
      lockedUntil: 0,
    });
    return;
  }
  r.count += 1;
  if (r.count >= MAX_FAILURES) r.lockedUntil = now + LOCKOUT_MS;
}

export function isLockedOut(clientId: string): boolean {
  const r = failureMap.get(clientId);
  if (!r) return false;
  const now = Date.now();
  if (r.lockedUntil > 0 && now < r.lockedUntil) return true;
  if (r.lockedUntil > 0 && now >= r.lockedUntil) {
    failureMap.delete(clientId);
    return false;
  }
  return false;
}

export function resetRateLimit(clientId: string): void {
  failureMap.delete(clientId);
}

export function readPinHash(): string | null {
  const fs = require("node:fs");
  const path = require("node:path");
  const os = require("node:os");
  const p = path.join(os.homedir(), ".config/zantara-cockpit/pin.hash");
  try {
    return fs.readFileSync(p, "utf8").trim();
  } catch {
    return null;
  }
}
