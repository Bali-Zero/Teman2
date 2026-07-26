import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatDate, formatRelative, formatTime } from "./date";

describe("date utilities", () => {
  const now = new Date(2026, 6, 18, 12, 0, 0);

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("formats valid dates and times with the shared en-GB format", () => {
    const value = new Date(2026, 6, 8, 9, 5, 0);

    expect(formatDate(value)).toBe("08 Jul 2026");
    expect(formatTime(value)).toBe("09:05");
  });

  it.each([null, undefined, "not-a-date"])(
    "returns an em dash for a missing or invalid value (%s)",
    (value) => {
      expect(formatDate(value)).toBe("—");
      expect(formatTime(value)).toBe("—");
      expect(formatRelative(value)).toBe("—");
    },
  );

  it.each([
    [30_000, "just now"],
    [45 * 60_000, "45m ago"],
    [4 * 60 * 60_000, "4h ago"],
    [3 * 24 * 60 * 60_000, "3d ago"],
    [10 * 24 * 60 * 60_000, "08 Jul 2026"],
  ])("formats an age of %i milliseconds as %s", (ageMs, expected) => {
    expect(formatRelative(new Date(now.getTime() - ageMs))).toBe(expected);
  });
});
