import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import bcrypt from "bcryptjs";
import {
  verifyPassphrase,
  recordFailure,
  isLockedOut,
  resetRateLimit,
} from "@/lib/cockpit-auth";

describe("cockpit-auth", () => {
  const PASSPHRASE = "synthetic-cockpit-passphrase-2026";

  beforeEach(() => {
    resetRateLimit();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });
  it("accepts a valid high-entropy passphrase", async () => {
    const hash = bcrypt.hashSync(PASSPHRASE, 10);
    expect(await verifyPassphrase(PASSPHRASE, hash)).toBe(true);
  });
  it("rejects a wrong passphrase", async () => {
    const hash = bcrypt.hashSync(PASSPHRASE, 10);
    expect(await verifyPassphrase("different-long-passphrase-2026", hash)).toBe(
      false,
    );
  });
  it("rejects short PIN-style credentials", async () => {
    const hash = bcrypt.hashSync("1234", 10);
    expect(await verifyPassphrase("1234", hash)).toBe(false);
  });
  it("rejects Unicode credentials above bcrypt's 72-byte boundary", async () => {
    const tooWide = "😀".repeat(19);
    const hash = bcrypt.hashSync(tooWide, 10);
    expect(tooWide.length).toBeLessThanOrEqual(64);
    expect(new TextEncoder().encode(tooWide).byteLength).toBeGreaterThan(72);
    expect(await verifyPassphrase(tooWide, hash)).toBe(false);
  });
  it("isLockedOut false initially", () => {
    expect(isLockedOut()).toBe(false);
  });
  it("5 failures → locked", () => {
    for (let i = 0; i < 5; i++) recordFailure();
    expect(isLockedOut()).toBe(true);
  });
  it("4 failures → not locked", () => {
    for (let i = 0; i < 4; i++) recordFailure();
    expect(isLockedOut()).toBe(false);
  });
  it("lockout duration 5 minutes", () => {
    const start = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(start);
    for (let i = 0; i < 5; i++) recordFailure();
    vi.mocked(Date.now).mockReturnValue(start + 5 * 60 * 1000 + 1);
    expect(isLockedOut()).toBe(false);
  });
  it("cleans up an expired non-locked failure window", () => {
    const start = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(start);
    for (let i = 0; i < 4; i++) recordFailure();
    vi.mocked(Date.now).mockReturnValue(start + 5 * 60 * 1000 + 1);
    expect(isLockedOut()).toBe(false);

    recordFailure();
    expect(isLockedOut()).toBe(false);
  });
});
