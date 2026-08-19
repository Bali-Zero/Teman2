/**
 * Cockpit auth: bcrypt passphrase + one bounded in-memory failure bucket.
 * The service binds directly to loopback and has no trusted proxy, so request
 * headers never choose rate-limit keys. Five failures in 5min → 5min lockout.
 * Panel finding 4-LLM v2: rate-limit active from S1 (NOT deferred to S5).
 */
import bcrypt from "bcryptjs";

export const MIN_PASSPHRASE_LENGTH = 16;
export const MAX_PASSPHRASE_LENGTH = 64;

const MAX_FAILURES = 5;
const WINDOW_MS = 5 * 60 * 1000;
const LOCKOUT_MS = 5 * 60 * 1000;

interface FailureRecord {
  count: number;
  inFlight: number;
  firstFailureAt: number;
  lockedUntil: number;
}

export interface PassphraseAttemptReservation {
  readonly record: FailureRecord;
  completed: boolean;
}

let failureBucket: FailureRecord | null = null;

function activeFailureBucket(now: number): FailureRecord | null {
  const record = failureBucket;
  if (!record) return null;

  if (record.lockedUntil > 0) {
    if (now < record.lockedUntil) return record;
    failureBucket = null;
    return null;
  }
  if (record.inFlight === 0 && now - record.firstFailureAt >= WINDOW_MS) {
    failureBucket = null;
    return null;
  }
  return record;
}

export async function verifyPassphrase(
  passphrase: string,
  hash: string,
): Promise<boolean> {
  if (
    !hash ||
    typeof passphrase !== "string" ||
    passphrase.length < MIN_PASSPHRASE_LENGTH ||
    passphrase.length > MAX_PASSPHRASE_LENGTH ||
    new TextEncoder().encode(passphrase).byteLength > 72
  ) {
    return false;
  }
  try {
    return await bcrypt.compare(passphrase, hash);
  } catch {
    return false;
  }
}

export function recordFailure(): void {
  const now = Date.now();
  const record = activeFailureBucket(now);
  if (!record) {
    failureBucket = {
      count: 1,
      inFlight: 0,
      firstFailureAt: now,
      lockedUntil: 0,
    };
    return;
  }
  record.count += 1;
  if (record.count >= MAX_FAILURES) record.lockedUntil = now + LOCKOUT_MS;
}

export function reservePassphraseAttempt(): PassphraseAttemptReservation | null {
  const now = Date.now();
  let record = activeFailureBucket(now);
  if (!record) {
    record = {
      count: 0,
      inFlight: 0,
      firstFailureAt: now,
      lockedUntil: 0,
    };
    failureBucket = record;
  }
  if (
    record.lockedUntil > now ||
    record.count + record.inFlight >= MAX_FAILURES
  ) {
    return null;
  }
  record.inFlight += 1;
  return { record, completed: false };
}

export function completePassphraseAttempt(
  reservation: PassphraseAttemptReservation,
  succeeded: boolean,
): void {
  if (reservation.completed) return;
  reservation.completed = true;

  if (failureBucket !== reservation.record) {
    if (!succeeded) recordFailure();
    return;
  }

  const record = reservation.record;
  record.inFlight = Math.max(0, record.inFlight - 1);
  if (!succeeded) {
    record.count += 1;
    if (record.count >= MAX_FAILURES) {
      record.lockedUntil = Date.now() + LOCKOUT_MS;
    }
  } else if (record.count === 0 && record.inFlight === 0) {
    failureBucket = null;
  }
}

export function isLockedOut(): boolean {
  const now = Date.now();
  const record = activeFailureBucket(now);
  return record !== null && record.lockedUntil > now;
}

export function resetRateLimit(): void {
  failureBucket = null;
}

export function readPassphraseHash(): string | null {
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
