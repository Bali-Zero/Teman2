import { describe, it, expect, vi, afterEach } from "vitest";
import {
  formatDate,
  formatDateShort,
  formatDateLong,
  formatTimeAgo,
} from "./format-date";

describe("formatDate", () => {
  it("returns em-dash for null/undefined/empty input", () => {
    expect(formatDate(null)).toBe("\u2014");
    expect(formatDate(undefined)).toBe("\u2014");
    expect(formatDate("")).toBe("\u2014");
  });

  it("formats a valid ISO date string as 'day month year'", () => {
    const result = formatDate("2026-03-25T10:00:00Z");
    // en-GB short month format: "25 Mar 2026"
    expect(result).toMatch(/25\s+Mar\s+2026/);
  });

  it("handles date-only string without time", () => {
    const result = formatDate("2026-01-15");
    expect(result).toMatch(/15\s+Jan\s+2026/);
  });

  it("returns 'Invalid Date' for unparseable date string (toLocaleDateString does not throw)", () => {
    // Note: "not-a-date" produces NaN date, but toLocaleDateString returns "Invalid Date" rather than throwing
    expect(formatDate("not-a-date")).toBe("Invalid Date");
  });
});

describe("formatDateShort", () => {
  it("returns em-dash for null/undefined", () => {
    expect(formatDateShort(null)).toBe("\u2014");
    expect(formatDateShort(undefined)).toBe("\u2014");
  });

  it("formats date without year", () => {
    const result = formatDateShort("2026-07-04T00:00:00Z");
    expect(result).toMatch(/4\s+Jul/);
    // Should NOT include year
    expect(result).not.toMatch(/2026/);
  });
});

describe("formatDateLong", () => {
  it("returns em-dash for null/undefined", () => {
    expect(formatDateLong(null)).toBe("\u2014");
    expect(formatDateLong(undefined)).toBe("\u2014");
  });

  it("formats date with full month name", () => {
    const result = formatDateLong("2026-03-25T10:00:00Z");
    expect(result).toMatch(/25\s+March\s+2026/);
  });
});

describe("formatTimeAgo", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns em-dash for null/undefined", () => {
    expect(formatTimeAgo(null)).toBe("\u2014");
    expect(formatTimeAgo(undefined)).toBe("\u2014");
  });

  it('returns "Just now" for less than a minute ago', () => {
    const now = new Date();
    const tenSecondsAgo = new Date(now.getTime() - 10_000).toISOString();
    expect(formatTimeAgo(tenSecondsAgo)).toBe("Just now");
  });

  it("returns minutes ago for recent times", () => {
    const now = new Date();
    const fiveMinAgo = new Date(now.getTime() - 5 * 60_000).toISOString();
    expect(formatTimeAgo(fiveMinAgo)).toBe("5m ago");
  });

  it("returns hours ago for times within a day", () => {
    const now = new Date();
    const threeHoursAgo = new Date(
      now.getTime() - 3 * 60 * 60_000,
    ).toISOString();
    expect(formatTimeAgo(threeHoursAgo)).toBe("3h ago");
  });

  it("returns days ago for times within a month", () => {
    const now = new Date();
    const fiveDaysAgo = new Date(
      now.getTime() - 5 * 24 * 60 * 60_000,
    ).toISOString();
    expect(formatTimeAgo(fiveDaysAgo)).toBe("5d ago");
  });

  it('returns "upcoming" for future dates', () => {
    const now = new Date();
    const tomorrow = new Date(now.getTime() + 24 * 60 * 60_000).toISOString();
    expect(formatTimeAgo(tomorrow)).toBe("upcoming");
  });

  it("falls back to formatDate for dates older than 30 days", () => {
    const now = new Date();
    const twoMonthsAgo = new Date(
      now.getTime() - 60 * 24 * 60 * 60_000,
    ).toISOString();
    const result = formatTimeAgo(twoMonthsAgo);
    // Should be a formatted date, not "Xd ago"
    expect(result).not.toMatch(/d ago/);
    expect(result).toMatch(/\d{4}/); // Contains year
  });
});
