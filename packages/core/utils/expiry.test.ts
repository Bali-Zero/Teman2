import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getExpiryStatus, isBirthdayToday } from "./expiry";

describe("expiry utilities", () => {
  const now = new Date(2026, 6, 18, 12, 0, 0);
  const daysFromNow = (days: number) =>
    new Date(now.getTime() + days * 24 * 60 * 60 * 1000);

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the explicit no-expiry result for missing dates", () => {
    expect(getExpiryStatus(null)).toEqual({
      status: "ok",
      daysRemaining: Infinity,
      label: "No expiry",
      color: "var(--bz-text-2)",
    });
  });

  it.each([
    [0, "expired", "Expired", "#ef4444"],
    [1, "critical", "1d left", "#ef4444"],
    [30, "critical", "30d left", "#ef4444"],
    [31, "warning", "31d left", "#f59e0b"],
    [90, "warning", "90d left", "#f59e0b"],
    [91, "ok", "91d left", "#22c55e"],
  ] as const)(
    "classifies a deadline in %i days as %s",
    (days, status, label, color) => {
      expect(getExpiryStatus(daysFromNow(days))).toEqual({
        status,
        daysRemaining: days,
        label,
        color,
      });
    },
  );

  it("detects birthdays by local month and day", () => {
    expect(isBirthdayToday("1990-07-18T12:00:00")).toBe(true);
    expect(isBirthdayToday("1990-07-19T12:00:00")).toBe(false);
    expect(isBirthdayToday(null)).toBe(false);
  });
});
