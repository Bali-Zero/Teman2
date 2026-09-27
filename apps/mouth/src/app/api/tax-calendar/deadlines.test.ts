import { describe, it, expect } from "vitest";
import { getNextTaxDeadlines, getUpcomingTaxDeadlines } from "./deadlines";

describe("getNextTaxDeadlines — guilt: no elapsed dates", () => {
  it("every returned date is >= the clock (2026-09-28), RED on the pre-fix hardcoded array", () => {
    const now = new Date("2026-09-28T00:00:00Z");
    const deadlines = getNextTaxDeadlines(now);
    expect(deadlines).toHaveLength(6);
    for (const d of deadlines) {
      expect(new Date(d.date).getTime()).toBeGreaterThanOrEqual(now.getTime());
    }
  });
});

describe("monthly rule rollover (PPh 25, 15th of the month)", () => {
  it("Dec → Jan: after the 15th passes in December, the next occurrence is 15 January next year", () => {
    const now = new Date("2026-12-20T00:00:00Z");
    const [pph25] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "pph25-monthly",
    );
    expect(pph25.date.slice(0, 10)).toBe("2027-01-15");
  });

  it("shifts a Saturday due date to the following Monday (2026-08-15 is a Saturday)", () => {
    const now = new Date("2026-08-01T00:00:00Z");
    const [pph25] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "pph25-monthly",
    );
    expect(pph25.date.slice(0, 10)).toBe("2026-08-17");
  });

  it("shifts a Sunday due date to the following Monday (2026-11-15 is a Sunday)", () => {
    const now = new Date("2026-11-01T00:00:00Z");
    const [pph25] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "pph25-monthly",
    );
    expect(pph25.date.slice(0, 10)).toBe("2026-11-16");
  });
});

describe("quarterly rule rollover (LKPM)", () => {
  it("Q4 → next year: after 15 Oct passes, the next occurrence is 15 January next year, labelled Q4 of the elapsed year", () => {
    const now = new Date("2026-11-01T00:00:00Z");
    const [lkpm] = getNextTaxDeadlines(now).filter((d) => d.id === "lkpm-q1");
    expect(lkpm.date.slice(0, 10)).toBe("2027-01-15");
    expect(lkpm.title).toBe("LKPM Q4 2026");
  });

  it("labels the quarter the computed date actually belongs to, not a fixed 'Q1 2026'", () => {
    const now = new Date("2026-05-01T00:00:00Z");
    const [lkpm] = getNextTaxDeadlines(now).filter((d) => d.id === "lkpm-q1");
    expect(lkpm.date.slice(0, 10)).toBe("2026-07-15");
    expect(lkpm.title).toBe("LKPM Q2 2026");
  });
});

describe("annual rule rollover (SPT Tahunan Badan)", () => {
  it("year → next year: after 30 Apr passes, the next occurrence is 30 April next year", () => {
    const now = new Date("2026-05-01T00:00:00Z");
    const [spt] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "spt-individual-2026",
    );
    expect(spt.date.slice(0, 10)).toBe("2027-04-30");
    expect(spt.title).toBe("SPT Tahunan — Badan 2026");
  });
});

describe("getUpcomingTaxDeadlines — iCal window", () => {
  it("every occurrence in the 12-month window is within [now, now+12mo)", () => {
    const now = new Date("2026-09-28T00:00:00Z");
    const limit = new Date("2027-09-28T00:00:00Z");
    const occurrences = getUpcomingTaxDeadlines(now, 12);
    expect(occurrences.length).toBeGreaterThan(6); // monthly rules recur several times
    for (const d of occurrences) {
      const t = new Date(d.date).getTime();
      expect(t).toBeGreaterThanOrEqual(now.getTime());
      expect(t).toBeLessThan(limit.getTime());
    }
  });

  it("gives each monthly obligation ~12 occurrences over a 12-month window", () => {
    const now = new Date("2026-09-28T00:00:00Z");
    const occurrences = getUpcomingTaxDeadlines(now, 12);
    const pph25Count = occurrences.filter((d) =>
      d.id.startsWith("pph25-monthly-"),
    ).length;
    expect(pph25Count).toBeGreaterThanOrEqual(11);
    expect(pph25Count).toBeLessThanOrEqual(13);
  });
});
