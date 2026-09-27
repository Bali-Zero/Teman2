export type TaxDeadlineKind = "PPh" | "PPN" | "LKPM" | "PB1";

export interface TaxDeadline {
  id: string;
  kind: TaxDeadlineKind;
  title: string;
  date: string; // ISO 8601, always >= the clock the deadline was computed against
  regency?: string;
  description: string;
}

const MS_DAY = 86_400_000;

/**
 * A due date recurs on `day` (or the LAST calendar day, for "last") of every
 * month whose 0-based index is in `months` ("all" = every month = a monthly
 * obligation). `rollWeekend` shifts a Sat/Sun date to the next Monday — the
 * only shift this module implements. `obligations_catalog.yaml` (found at
 * apps/backend-rag/backend/data/obligations_catalog.yaml) also rolls a few of
 * these past Indonesian public holidays (hari libur nasional / cuti bersama),
 * but that calendar only exists in the Python backend (data/id_holidays.py);
 * porting it here is out of scope for this fix, so a due date can still land
 * on a national holiday — see the visible note in TaxCalendarBody.
 */
interface RecurrenceRule {
  months: number[] | "all";
  day: number | "last";
  rollWeekend: boolean;
}

function dueDateInMonth(
  year: number,
  monthIndex: number,
  day: number | "last",
): Date {
  return day === "last"
    ? new Date(Date.UTC(year, monthIndex + 1, 0))
    : new Date(Date.UTC(year, monthIndex, day));
}

function shiftWeekendForward(date: Date): Date {
  const weekday = date.getUTCDay(); // 0 = Sun, 6 = Sat
  if (weekday === 6) return new Date(date.getTime() + 2 * MS_DAY);
  if (weekday === 0) return new Date(date.getTime() + 1 * MS_DAY);
  return date;
}

/** Every occurrence of `rule` with `now <= date < limit`, ascending. */
function occurrencesInWindow(
  now: Date,
  limit: Date,
  rule: RecurrenceRule,
): Date[] {
  const results: Date[] = [];
  const baseYear = now.getUTCFullYear();
  const baseMonth = now.getUTCMonth();
  // 26 months of scan room covers any monthly/quarterly/annual rule twice over.
  for (let offset = 0; offset < 26; offset++) {
    const monthIndexAbs = baseMonth + offset;
    const year = baseYear + Math.floor(monthIndexAbs / 12);
    const monthIndex = ((monthIndexAbs % 12) + 12) % 12;
    if (rule.months !== "all" && !rule.months.includes(monthIndex)) continue;
    let due = dueDateInMonth(year, monthIndex, rule.day);
    if (rule.rollWeekend) due = shiftWeekendForward(due);
    if (due >= limit) break;
    if (due >= now) results.push(due);
  }
  return results;
}

function nextOccurrence(now: Date, rule: RecurrenceRule): Date {
  const farLimit = new Date(
    Date.UTC(now.getUTCFullYear() + 2, now.getUTCMonth(), now.getUTCDate()),
  );
  const [first] = occurrencesInWindow(now, farLimit, rule);
  if (!first) {
    throw new Error(
      "tax-calendar: no occurrence found within the 2-year scan window",
    );
  }
  return first;
}

interface Obligation {
  id: string;
  kind: TaxDeadlineKind;
  regency?: string;
  rule: RecurrenceRule;
  /** obligations_catalog.yaml rule id this is grounded in, or null if the catalog has no matching rule. */
  catalogId: string | null;
  title: (due: Date) => string;
  description: string;
}

// PPh 25 monthly instalment — catalog id `pph25_installment`: monthly, due the
// 15th of the following month, roll: next_business_day (weekend-only here).
// SPT Masa PPN — catalog id `spt_masa_ppn`: monthly, due the LAST day of the
// following month, roll: next_business_day (weekend-only here).
// LKPM quarterly — catalog id `lkpm_quarterly`: due the 15th of the month
// after each calendar quarter (Apr/Jul/Oct/Jan), roll: none.
// PB1 (regional hotel/restaurant tax) — no matching id in the 21-rule
// national/employer/PSE/BPJS catalog (it is a kabupaten-level levy); kept as
// a fixed day-of-month, unshifted, per the spec's "no catalog rule → leave
// unshifted" instruction.
// SPT Tahunan — the catalog has no rule for an INDIVIDUAL annual return, only
// `spt_tahunan_badan` (corporate): annual, due 4 months after fiscal year end
// (30 April for a Dec year-end), roll: next_business_day. The pre-existing
// hardcoded date (2026-04-30) matches that corporate rule exactly, not a
// 3-months-after-year-end individual rule, so this obligation is re-grounded
// as `spt_tahunan_badan` and relabeled accordingly — see report.
const OBLIGATIONS: Obligation[] = [
  {
    id: "pph25-monthly",
    kind: "PPh",
    rule: { months: "all", day: 15, rollWeekend: true },
    catalogId: "pph25_installment",
    title: () => "PPh 25 — monthly",
    description:
      "Payment due by the 15th of the following month (JCSS 2025 shifted it from the 10th to the 15th).",
  },
  {
    id: "ppn-monthly",
    kind: "PPN",
    rule: { months: "all", day: "last", rollWeekend: true },
    catalogId: "spt_masa_ppn",
    title: () => "PPN SPT Masa",
    description: "VAT return (SPT Masa) due by the end of the following month.",
  },
  {
    id: "lkpm-q1",
    kind: "LKPM",
    // Due months: Apr(3)/Jul(6)/Oct(9)/Jan(0), day 15, no roll per the catalog.
    rule: { months: [0, 3, 6, 9], day: 15, rollWeekend: false },
    catalogId: "lkpm_quarterly",
    title: (due) => {
      const dueMonth = due.getUTCMonth();
      const dueYear = due.getUTCFullYear();
      // due month 3/6/9 reports on the quarter ending the previous month in
      // the SAME year; due month 0 (January) reports on Q4 of the PRIOR year.
      const quarterByDueMonth: Record<number, number> = {
        3: 1,
        6: 2,
        9: 3,
        0: 4,
      };
      const quarter = quarterByDueMonth[dueMonth];
      const quarterYear = dueMonth === 0 ? dueYear - 1 : dueYear;
      return `LKPM Q${quarter} ${quarterYear}`;
    },
    description:
      "Quarterly investment activity report (Laporan Kegiatan Penanaman Modal).",
  },
  {
    id: "pb1-badung",
    kind: "PB1",
    regency: "Badung",
    rule: { months: "all", day: 10, rollWeekend: false },
    catalogId: null,
    title: () => "PB1 Badung",
    description: "Hotel and restaurant tax, 10%.",
  },
  {
    id: "pb1-gianyar",
    kind: "PB1",
    regency: "Gianyar",
    rule: { months: "all", day: 15, rollWeekend: false },
    catalogId: null,
    title: () => "PB1 Gianyar",
    description: "PB1 for Gianyar regency.",
  },
  {
    id: "spt-individual-2026",
    kind: "PPh",
    rule: { months: [3], day: 30, rollWeekend: true },
    catalogId: "spt_tahunan_badan",
    title: (due) => `SPT Tahunan — Badan ${due.getUTCFullYear() - 1}`,
    description:
      "Annual corporate income tax return, due 4 months after fiscal year end (30 April for a December year end).",
  },
];

function toDeadline(o: Obligation, due: Date): TaxDeadline {
  return {
    id: o.id,
    kind: o.kind,
    regency: o.regency,
    title: o.title(due),
    date: due.toISOString(),
    description: o.description,
  };
}

/** One deadline per obligation: its next occurrence on/after `now`, sorted. */
export function getNextTaxDeadlines(now: Date = new Date()): TaxDeadline[] {
  return OBLIGATIONS.map((o) =>
    toDeadline(o, nextOccurrence(now, o.rule)),
  ).sort((a, b) => a.date.localeCompare(b.date));
}

/** Every occurrence per obligation in [now, now + monthsAhead), sorted, for iCal. */
export function getUpcomingTaxDeadlines(
  now: Date = new Date(),
  monthsAhead = 12,
): TaxDeadline[] {
  const limit = new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth() + monthsAhead,
      now.getUTCDate(),
    ),
  );
  const out: TaxDeadline[] = [];
  for (const o of OBLIGATIONS) {
    for (const due of occurrencesInWindow(now, limit, o.rule)) {
      out.push({
        ...toDeadline(o, due),
        id: `${o.id}-${due.toISOString().slice(0, 7)}`,
      });
    }
  }
  return out.sort((a, b) => a.date.localeCompare(b.date));
}

export const TAX_DEADLINES: TaxDeadline[] = getNextTaxDeadlines();

export function getRegencies(): string[] {
  return Array.from(
    new Set(
      OBLIGATIONS.filter((o): o is Obligation & { regency: string } =>
        Boolean(o.regency),
      ).map((o) => o.regency),
    ),
  );
}
