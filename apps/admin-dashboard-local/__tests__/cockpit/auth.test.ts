import { describe, it, expect, beforeEach } from "vitest";
import bcrypt from "bcryptjs";
import {
  verifyPin,
  recordFailure,
  isLockedOut,
  resetRateLimit,
} from "@/lib/cockpit-auth";

describe("cockpit-auth", () => {
  beforeEach(() => {
    resetRateLimit("test");
  });
  it("verifyPin correct PIN", async () => {
    const hash = bcrypt.hashSync("123456", 10);
    expect(await verifyPin("123456", hash)).toBe(true);
  });
  it("verifyPin wrong PIN", async () => {
    const hash = bcrypt.hashSync("123456", 10);
    expect(await verifyPin("999999", hash)).toBe(false);
  });
  it("isLockedOut false initially", () => {
    expect(isLockedOut("test")).toBe(false);
  });
  it("5 failures → locked", () => {
    for (let i = 0; i < 5; i++) recordFailure("test");
    expect(isLockedOut("test")).toBe(true);
  });
  it("4 failures → not locked", () => {
    for (let i = 0; i < 4; i++) recordFailure("test");
    expect(isLockedOut("test")).toBe(false);
  });
  it("lockout duration 5 minutes", () => {
    for (let i = 0; i < 5; i++) recordFailure("test");
    const orig = Date.now;
    Date.now = () => orig() + 5 * 60 * 1000 + 1000;
    expect(isLockedOut("test")).toBe(false);
    Date.now = orig;
  });
});
