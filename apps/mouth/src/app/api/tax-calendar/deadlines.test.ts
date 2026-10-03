import { describe, it, expect } from "vitest";
import { getNextTaxDeadlines, getUpcomingTaxDeadlines } from "./deadlines";

describe("getNextTaxDeadlines — guilt: no elapsed dates", () => {
  it("every returned date is >= the clock (2026-09-28), RED on the pre-fix hardcoded array", () => {
    const now = new Date("2026-09-28T00:00:00Z");
    const deadlines = getNextTaxDeadlines(now);
    expect(deadlines).toHaveLength(7);
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

describe("annual rule rollover (SPT Tahunan)", () => {
  it("Badan: after 30 Apr passes, the next occurrence is 30 April next year", () => {
    const now = new Date("2026-05-01T00:00:00Z");
    const [spt] = getNextTaxDeadlines(now).filter((d) => d.id === "spt-badan");
    expect(spt.date.slice(0, 10)).toBe("2027-04-30");
    expect(spt.title).toBe("SPT Tahunan — Badan 2026");
  });

  it("Individual: due 31 March (3 months after the tax year), not the corporate 30 April", () => {
    const now = new Date("2026-09-28T00:00:00Z");
    const [spt] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "spt-individual-2026",
    );
    expect(spt.date.slice(0, 10)).toBe("2027-03-31");
    expect(spt.title).toBe("SPT Tahunan — Individual 2026");
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

// gate-7583 fix-forward (fresh Opus 5.5 REWORK-BUILD, 2026-09-28): F1 month-end
// roll missed, F2 duplicate iCal UIDs, F3 due-day dropped + WITA off-by-one.
const MS_DAY = 86_400_000;
const WITA_OFFSET_MS = 8 * 60 * 60 * 1000;

/** The Asia/Makassar calendar date of `instant`, as a UTC-midnight Date. */
function witaDate(instant: Date): Date {
  const shifted = new Date(instant.getTime() + WITA_OFFSET_MS);
  return new Date(
    Date.UTC(
      shifted.getUTCFullYear(),
      shifted.getUTCMonth(),
      shifted.getUTCDate(),
    ),
  );
}

describe("F1 — month-end roll across a month boundary is not missed", () => {
  it("31 Oct 2026 is a Saturday: PPN rolls to Mon 2 Nov, still found from 1 Nov onward", () => {
    const now = new Date("2026-11-01T01:00:00Z");
    const [ppn] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "ppn-monthly",
    );
    expect(ppn.date.slice(0, 10)).toBe("2026-11-02");
  });

  it("31 Jan 2027 is a Sunday: PPN rolls to Mon 1 Feb", () => {
    const now = new Date("2027-02-01T00:00:00Z");
    const [ppn] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "ppn-monthly",
    );
    expect(ppn.date.slice(0, 10)).toBe("2027-02-01");
  });

  it("30 Apr 2028 is a Sunday: SPT Badan rolls to Mon 1 May", () => {
    const now = new Date("2028-05-01T00:00:00Z");
    const [spt] = getNextTaxDeadlines(now).filter((d) => d.id === "spt-badan");
    expect(spt.date.slice(0, 10)).toBe("2028-05-01");
  });

  it("31 Mar 2029 is a Saturday: SPT Individual rolls to Mon 2 Apr", () => {
    const now = new Date("2029-04-01T00:00:00Z");
    const [spt] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "spt-individual-2026",
    );
    expect(spt.date.slice(0, 10)).toBe("2029-04-02");
  });
});

describe("F2 — iCal UIDs stay unique across a rolled month-end", () => {
  it.each(["2026-09-28T00:00:00Z", "2027-07-15T00:00:00Z"])(
    "every UID in getUpcomingTaxDeadlines(%s, 12) is unique",
    (clock) => {
      const occurrences = getUpcomingTaxDeadlines(new Date(clock), 12);
      const ids = occurrences.map((d) => d.id);
      expect(new Set(ids).size).toBe(ids.length);
    },
  );
});

describe("F3 — due day is not dropped before 08:00 WITA, and inclusive at/after", () => {
  it("15 Oct 2026 09:00 WITA: PPh 25 due that day is still listed as today, not skipped to November", () => {
    const now = new Date("2026-10-15T01:00:00Z");
    const [pph25] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "pph25-monthly",
    );
    expect(pph25.date.slice(0, 10)).toBe("2026-10-15");
  });

  it("07:10 WITA 28 Sep 2026: PPN due 30 Sep is still returned (the 'in Nd' count itself is a DeadlineBadge concern, see packages/core/components/DeadlineBadge.test.tsx)", () => {
    const now = new Date("2026-09-27T23:10:00Z");
    const [ppn] = getNextTaxDeadlines(now).filter(
      (d) => d.id === "ppn-monthly",
    );
    expect(ppn.date.slice(0, 10)).toBe("2026-09-30");
  });
});

describe("property sweep — independent oracle, every day 2026-09-28..2030-12-31 at 00:00Z/12:00Z", () => {
  // Rule table duplicated deliberately (not imported): an independent
  // reference must not share the production scan's month-offset bound, or a
  // bug in that bound (this PR's F1) would be invisible to the oracle.
  interface RuleLike {
    months: number[] | "all";
    day: number | "last";
    rollWeekend: boolean;
  }
  const RULES: Record<string, RuleLike> = {
    "pph25-monthly": { months: "all", day: 15, rollWeekend: true },
    "ppn-monthly": { months: "all", day: "last", rollWeekend: true },
    "lkpm-q1": { months: [0, 3, 6, 9], day: 15, rollWeekend: false },
    "pb1-badung": { months: "all", day: 10, rollWeekend: false },
    "pb1-gianyar": { months: "all", day: 15, rollWeekend: false },
    "spt-individual-2026": { months: [2], day: 31, rollWeekend: true },
    "spt-badan": { months: [3], day: 30, rollWeekend: true },
  };

  /** Brute-force reference: scans a WIDER month window than production (-2 vs
   * production's -1) so an under-sized production scan window shows up as a
   * mismatch, not as an oracle blind spot. */
  function referenceNextDate(now: Date, rule: RuleLike): Date {
    const today = witaDate(now);
    const baseYear = now.getUTCFullYear();
    const baseMonth = now.getUTCMonth();
    let best: Date | null = null;
    for (let offset = -2; offset <= 30; offset++) {
      const monthIndexAbs = baseMonth + offset;
      const year = baseYear + Math.floor(monthIndexAbs / 12);
      const monthIndex = ((monthIndexAbs % 12) + 12) % 12;
      if (rule.months !== "all" && !rule.months.includes(monthIndex)) continue;
      const day =
        rule.day === "last"
          ? new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate()
          : rule.day;
      let due = new Date(Date.UTC(year, monthIndex, day));
      if (rule.rollWeekend) {
        const weekday = due.getUTCDay();
        if (weekday === 6) due = new Date(due.getTime() + 2 * MS_DAY);
        if (weekday === 0) due = new Date(due.getTime() + 1 * MS_DAY);
      }
      if (
        due.getTime() >= today.getTime() &&
        (!best || due.getTime() < best.getTime())
      ) {
        best = due;
      }
    }
    if (!best) throw new Error("reference: no occurrence found in scan window");
    return best;
  }

  it("getNextTaxDeadlines never disagrees with the independent reference, and never lands before the WITA clock date", () => {
    const start = Date.UTC(2026, 8, 28);
    const end = Date.UTC(2030, 11, 31);
    for (let t = start; t <= end; t += MS_DAY) {
      for (const hour of [0, 12]) {
        const now = new Date(t + hour * 3_600_000);
        const today = witaDate(now);
        const deadlines = getNextTaxDeadlines(now);
        for (const d of deadlines) {
          const rule = RULES[d.id];
          if (!rule) continue;
          const dueDate = new Date(d.date);
          expect(dueDate.getTime()).toBeGreaterThanOrEqual(today.getTime());
          const expected = referenceNextDate(now, rule);
          expect(d.date.slice(0, 10)).toBe(expected.toISOString().slice(0, 10));
        }
      }
    }
  });
});
