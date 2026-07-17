import { describe, expect, it } from "vitest";
import {
  MOCK_CATALOG,
  QUESTIONS,
  daysRemaining,
  formatIsoDateForDisplay,
  getLane,
  parseIsoDateUtc,
} from "./tree";

describe("tree.ts — mock catalog", () => {
  it("has ~12 cards with unique real current codes (no legacy B211*)", () => {
    expect(MOCK_CATALOG.length).toBeGreaterThanOrEqual(10);
    expect(MOCK_CATALOG.length).toBeLessThanOrEqual(14);
    const codes = MOCK_CATALOG.map((c) => c.code);
    expect(new Set(codes).size).toBe(codes.length);
    for (const code of codes) {
      expect(code.toUpperCase()).not.toMatch(/^B211/);
    }
  });

  it("every card has one all-inclusive price and an honest [min,max] timeline", () => {
    for (const card of MOCK_CATALOG) {
      expect(typeof card.allInclusivePriceIDR).toBe("number");
      expect(card.allInclusivePriceIDR).toBeGreaterThanOrEqual(0);
      expect(card.timelineDays[0]).toBeLessThanOrEqual(card.timelineDays[1]);
    }
  });

  it("every question option has a resolvable i18n key shape", () => {
    for (const question of Object.values(QUESTIONS)) {
      for (const option of question.options) {
        expect(option.labelI18nKey.length).toBeGreaterThan(0);
      }
    }
  });
});

describe("tree.ts — daysRemaining / getLane", () => {
  const today = new Date(Date.UTC(2026, 6, 17)); // 2026-07-17

  it("computes whole-day differences across the UTC boundary", () => {
    expect(daysRemaining("2026-07-17", today)).toBe(0);
    expect(daysRemaining("2026-07-18", today)).toBe(1);
    expect(daysRemaining("2026-07-16", today)).toBe(-1);
  });

  it("returns null when offshore or unanswered", () => {
    expect(getLane({}, today)).toBeNull();
    expect(getLane({ in_indonesia: "no" }, today)).toBeNull();
    expect(getLane({ in_indonesia: "yes" }, today)).toBeNull();
  });

  it("routes the four onshore lanes per design doc §4 table", () => {
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-10" }, today),
    ).toBe("expired");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-18" }, today),
    ).toBe("urgent");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-19" }, today),
    ).toBe("urgent");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-22" }, today),
    ).toBe("bridging");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-08-10" }, today),
    ).toBe("extend");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-12-01" }, today),
    ).toBe("planning");
  });

  it("never routes a 1-2 day case into bridging (R1 adversarial fix, design doc §4)", () => {
    const lane = getLane(
      { in_indonesia: "yes", permit_expiry: "2026-07-19" },
      today,
    );
    expect(lane).not.toBe("bridging");
  });
});

describe("tree.ts — strict date parsing (finding #8, adversarial review 2026-07-17)", () => {
  const today = new Date(Date.UTC(2026, 6, 17));

  it("rejects calendar-invalid dates that would otherwise silently normalize", () => {
    // 2026-02-30 doesn't exist — a naive `new Date(...)` normalizes it to
    // 2026-03-02 instead of rejecting it. parseIsoDateUtc must reject.
    expect(parseIsoDateUtc("2026-02-30")).toBeNull();
    expect(parseIsoDateUtc("2026-13-01")).toBeNull();
    expect(parseIsoDateUtc("not-a-date")).toBeNull();
    expect(parseIsoDateUtc("2026-7-4")).toBeNull(); // not zero-padded — reject, don't guess
  });

  it("accepts a real calendar date and round-trips it", () => {
    expect(parseIsoDateUtc("2026-07-17")).toBe(Date.UTC(2026, 6, 17));
  });

  it("daysRemaining and getLane treat an invalid date as unanswered, never a lane", () => {
    expect(daysRemaining("2026-02-30", today)).toBeNull();
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-02-30" }, today),
    ).toBeNull();
  });

  it("formatIsoDateForDisplay renders in UTC so a negative-offset viewer never rolls the date back a day", () => {
    // en-GB dateStyle:"medium" — asserting only the day/year survives
    // verbatim (not asserting on the exact locale string format), which is
    // the finding: the calendar day the user TYPED must be the calendar
    // day DISPLAYED, regardless of the viewer's local timezone offset.
    const display = formatIsoDateForDisplay("2026-07-17", "en-GB");
    expect(display).toContain("17");
    expect(display).toContain("2026");
  });

  it("formatIsoDateForDisplay falls back to the raw string on an invalid date rather than throwing", () => {
    expect(formatIsoDateForDisplay("not-a-date", "en-GB")).toBe("not-a-date");
  });
});
