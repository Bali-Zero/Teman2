/**
 * Bonus aggregation for the HR /hr/bonuses accounting view.
 *
 * Accounting needs one number per member per month. The API returns a flat
 * ledger, so the roll-up happens here — as pure functions, so the arithmetic
 * that payroll depends on is unit-testable without a browser.
 *
 * Timezone: buckets are cut on **Asia/Makassar (WITA)**, the business
 * timezone, NEVER on the browser's local zone. `awarded_at` is a UTC
 * timestamptz and rows written at midnight WITA are stored as 16:00Z the
 * previous day — bucketing on UTC (or on a laptop set to Europe/Rome) silently
 * moves those rows into the previous month and makes two machines disagree
 * about the same payroll. Live prod data already contains such rows.
 */

import type { Bonus, BonusHistoricalRecord, BonusStatus } from "@/types/hr";

/** Business timezone for month cut-off. Bali Zero operates on WITA. */
const BUSINESS_TZ = "Asia/Makassar";

/** Bucket key used for rows whose `awarded_at` is missing or unparseable. */
export const UNDATED_KEY = "";

const monthKeyFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: BUSINESS_TZ,
  year: "numeric",
  month: "2-digit",
});

const monthLabelFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: BUSINESS_TZ,
  year: "numeric",
  month: "long",
});

export interface MemberMonthAggregate {
  /** Stable identity: employee_id when present, else the email/name fallback. */
  memberKey: string;
  employeeId: number | null;
  employeeName: string;
  employeeEmail: string;
  count: number;
  total: number;
  /** Amount per status. Absent statuses are 0. */
  byStatus: Record<BonusStatus, number>;
  /** This member's own rows for this month, newest first. */
  bonuses: Bonus[];
}

export interface MonthAggregate {
  /** `YYYY-MM` in WITA, or `UNDATED_KEY` for undated rows. */
  key: string;
  label: string;
  count: number;
  memberCount: number;
  total: number;
  pendingTotal: number;
  approvedTotal: number;
  members: MemberMonthAggregate[];
}

export interface MemberTotal {
  memberKey: string;
  employeeId: number | null;
  employeeName: string;
  employeeEmail: string;
  count: number;
  total: number;
  /** Number of distinct months this member earned a bonus in. */
  monthCount: number;
  byStatus: Record<BonusStatus, number>;
  /** Month key → total for this member. */
  byMonth: Record<string, number>;
}

function emptyStatusMap(): Record<BonusStatus, number> {
  return { pending: 0, approved: 0, rejected: 0, paid: 0, reversed: 0 };
}

/** Coerce an amount that may arrive as a JSON string (BIGINT) to a number. */
function amountOf(bonus: Bonus): number {
  const n = Number(bonus.amount_idr);
  return Number.isFinite(n) ? n : 0;
}

function memberKeyOf(bonus: Bonus): string {
  if (bonus.employee_id != null) return `id:${bonus.employee_id}`;
  return `email:${bonus.employee_email || bonus.employee_name || "unknown"}`;
}

function addStatus(
  map: Record<BonusStatus, number>,
  status: BonusStatus,
  amount: number,
): void {
  map[status] = (map[status] ?? 0) + amount;
}

/**
 * `YYYY-MM` of an ISO timestamp in WITA, or `UNDATED_KEY` when unparseable.
 */
export function witaMonthKey(awardedAt: string): string {
  if (!awardedAt) return UNDATED_KEY;
  const d = new Date(awardedAt);
  if (Number.isNaN(d.getTime())) return UNDATED_KEY;
  // en-CA renders as `YYYY-MM`, already zero-padded.
  return monthKeyFormatter.format(d);
}

/** Human month label, e.g. `July 2026`. */
export function witaMonthLabel(awardedAt: string): string {
  if (!awardedAt) return "Undated";
  const d = new Date(awardedAt);
  if (Number.isNaN(d.getTime())) return "Undated";
  return monthLabelFormatter.format(d);
}

/** Date of a single bonus row, rendered in WITA. */
export function formatBonusDate(awardedAt: string): string {
  if (!awardedAt) return "—";
  const d = new Date(awardedAt);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", {
    timeZone: BUSINESS_TZ,
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/**
 * Group the flat ledger into months (newest first), and within each month into
 * one row per member (largest total first).
 *
 * Every input row lands in exactly one bucket — undated rows get their own,
 * sorted last, so the sum of the month totals always equals the sum of the
 * payload. Accounting must never see money quietly disappear.
 */
export function groupBonusesByMonth(bonuses: Bonus[]): MonthAggregate[] {
  const months = new Map<string, Map<string, MemberMonthAggregate>>();
  const labels = new Map<string, string>();

  for (const bonus of bonuses) {
    const key = witaMonthKey(bonus.awarded_at);
    if (!labels.has(key)) labels.set(key, witaMonthLabel(bonus.awarded_at));

    let members = months.get(key);
    if (!members) {
      members = new Map();
      months.set(key, members);
    }

    const mKey = memberKeyOf(bonus);
    let member = members.get(mKey);
    if (!member) {
      member = {
        memberKey: mKey,
        employeeId: bonus.employee_id ?? null,
        employeeName: bonus.employee_name || bonus.employee_email || "Unknown",
        employeeEmail: bonus.employee_email || "",
        count: 0,
        total: 0,
        byStatus: emptyStatusMap(),
        bonuses: [],
      };
      members.set(mKey, member);
    }

    const amount = amountOf(bonus);
    member.count += 1;
    member.total += amount;
    addStatus(member.byStatus, bonus.status, amount);
    member.bonuses.push(bonus);
  }

  const result: MonthAggregate[] = [];
  for (const [key, members] of months) {
    const memberList = [...members.values()].sort(
      (a, b) =>
        b.total - a.total || a.employeeName.localeCompare(b.employeeName),
    );
    for (const m of memberList) {
      m.bonuses.sort(
        (a, b) =>
          new Date(b.awarded_at).getTime() - new Date(a.awarded_at).getTime() ||
          b.id - a.id,
      );
    }
    result.push({
      key,
      label: labels.get(key) ?? "Undated",
      count: memberList.reduce((s, m) => s + m.count, 0),
      memberCount: memberList.length,
      total: memberList.reduce((s, m) => s + m.total, 0),
      pendingTotal: memberList.reduce((s, m) => s + m.byStatus.pending, 0),
      approvedTotal: memberList.reduce((s, m) => s + m.byStatus.approved, 0),
      members: memberList,
    });
  }

  // Newest month first; the undated bucket always sorts last.
  return result.sort((a, b) => {
    if (a.key === UNDATED_KEY) return 1;
    if (b.key === UNDATED_KEY) return -1;
    return b.key.localeCompare(a.key);
  });
}

/**
 * All-time total per member (largest first) — the "totale membri, membro per
 * membro" summary, with each member's per-month breakdown attached.
 */
export function aggregateByMember(bonuses: Bonus[]): MemberTotal[] {
  const rows = new Map<string, MemberTotal>();

  for (const bonus of bonuses) {
    const mKey = memberKeyOf(bonus);
    let row = rows.get(mKey);
    if (!row) {
      row = {
        memberKey: mKey,
        employeeId: bonus.employee_id ?? null,
        employeeName: bonus.employee_name || bonus.employee_email || "Unknown",
        employeeEmail: bonus.employee_email || "",
        count: 0,
        total: 0,
        monthCount: 0,
        byStatus: emptyStatusMap(),
        byMonth: {},
      };
      rows.set(mKey, row);
    }

    const amount = amountOf(bonus);
    const monthKey = witaMonthKey(bonus.awarded_at);
    row.count += 1;
    row.total += amount;
    addStatus(row.byStatus, bonus.status, amount);
    row.byMonth[monthKey] = (row.byMonth[monthKey] ?? 0) + amount;
  }

  const result = [...rows.values()];
  for (const row of result) row.monthCount = Object.keys(row.byMonth).length;
  return result.sort(
    (a, b) => b.total - a.total || a.employeeName.localeCompare(b.employeeName),
  );
}

function csvCell(value: string | number): string {
  let s = String(value);
  // Formula injection: a cell starting with = + - @ (or a lone tab/CR) is
  // executed as a formula by Excel and Sheets. Only text cells reach this
  // guard — the amount columns are written as raw numbers below — so the
  // leading apostrophe can never turn a figure into text.
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * One CSV row per member per month — the shape accounting pastes into a sheet.
 * Amounts are bare integers (no `Rp`, no thousands separator) so spreadsheets
 * parse them as numbers rather than text.
 */
export function bonusesToCsv(months: MonthAggregate[]): string {
  const header = [
    "month",
    "employee_id",
    "employee_name",
    "employee_email",
    "bonus_count",
    "pending_idr",
    "approved_idr",
    "paid_idr",
    "total_idr",
  ].join(",");

  const lines = months.flatMap((month) =>
    month.members.map((m) =>
      [
        csvCell(month.key || "undated"),
        csvCell(m.employeeId ?? ""),
        csvCell(m.employeeName),
        csvCell(m.employeeEmail),
        m.count,
        m.byStatus.pending,
        m.byStatus.approved,
        m.byStatus.paid,
        m.total,
      ].join(","),
    ),
  );

  return [header, ...lines].join("\n") + "\n";
}

/**
 * Reconciliation verdict for a month that ALSO has a pre-system PDF recap
 * (`hr_bonus_historical`). The ledger and the PDF overlap on the transition
 * months (2026-02, 2026-03) with different totals and are NOT a clean
 * subset of one another, so the two are never summed. Instead we decide, per
 * month, which source is authoritative — the ruling Zero delegated on
 * 2026-07-23:
 *
 *   The bonus ledger is the source of truth, EXCEPT for a month where the
 *   ledger is demonstrably incomplete — i.e. the PDF paid a member (>0) who
 *   has zero ledger rows that month. That is the real signal of "the ledger
 *   wasn't in use yet", and it triggers only for the adoption month
 *   (2026-02: ADIT/ARI/SAHIRA paid on paper, absent from the ledger). It is
 *   NOT hard-coded to a date: it reads the data, and it turns itself off the
 *   moment someone backfills the ledger for that month.
 *
 * March does NOT trigger it — the PDF's only ledger-absent member (ADIT) was
 * recorded at 0 IDR, so nothing was paid on paper that the ledger is missing;
 * the ledger's richer 84 rows win.
 *
 * Never mutates the ledger. The page uses this only to word the strip and to
 * pick which figure to headline; the ledger stays the stored truth.
 */
export interface HistoricalReconciliation {
  /** `YYYY-MM` this verdict is for. */
  monthKey: string;
  /** Human label, e.g. `February 2026` — derived from the key, timezone-free. */
  monthLabel: string;
  pdfTotal: number;
  pdfTasks: number;
  sources: string[];
  /** Full-month ledger total (unfiltered) — the figure the strip compares against. */
  ledgerTotal: number;
  /** true → ledger wins, PDF is a historical snapshot; false → ledger is incomplete, PDF is authoritative. */
  ledgerAuthoritative: boolean;
  /**
   * DISTINCT members the PDF paid (>0) that have zero ledger rows this month.
   * Counted by member id, not by record — two PDF rows for the same absent
   * member are one missing member, not two.
   */
  missingPaidMembers: number;
  /**
   * PDF paid lines that cannot be reconciled to a ledger member: a positive
   * amount with no `employee_id`, or an amount that does not parse to a
   * non-negative safe integer. Any of these blocks a clean ledger-authoritative
   * verdict — we cannot assert the ledger covers a payment we cannot attribute.
   */
  unresolvedPaidRecords: number;
  /**
   * false when at least one PDF amount was unparseable, so `pdfTotal` is an
   * UNDERSTATEMENT. The UI must then NOT print "use the PDF total (Rp X)" — it
   * would instruct a wrong (too-small) payment — and demand manual verification.
   */
  pdfTotalReliable: boolean;
}

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** `2026-02` → `February 2026`. No timestamp needed (PDF months carry no time). */
export function monthKeyLabel(key: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(key);
  if (!m) return "Undated";
  const name = MONTH_NAMES[Number(m[2]) - 1];
  return name ? `${name} ${m[1]}` : key;
}

/**
 * A historical PDF amount is a `bigint` that may arrive as a JSON string. Accept
 * ONLY a non-negative safe integer; a comma-formatted string, `NaN`, `Infinity`
 * or a value beyond 2^53 returns `null` ("unparseable"). It must NOT silently
 * become 0 (as `Number(x) || 0` would): a swallowed amount reads as "member not
 * paid" and could wrongly clear the ledger-incomplete flag.
 */
export function parseHistoricalAmount(value: number | string): number | null {
  if (typeof value === "number") {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    const n = Number(value.trim());
    return Number.isSafeInteger(n) ? n : null;
  }
  return null;
}

/**
 * Reconciliation verdict for ONE month, computed from the FULL-month ledger
 * member set + ledger total (both unfiltered) and the month's PDF records.
 * Kept pure and filter-agnostic on purpose — see `buildMonthlyReconciliation`.
 */
export function reconcileMonth(
  monthKey: string,
  ledgerMemberIds: ReadonlySet<number>,
  ledgerTotal: number,
  historicalForMonth: BonusHistoricalRecord[],
): HistoricalReconciliation | null {
  if (historicalForMonth.length === 0) return null;

  let pdfTotal = 0;
  let pdfTasks = 0;
  let unresolvedPaidRecords = 0;
  let pdfTotalReliable = true;
  const missingMemberIds = new Set<number>();
  const sources = new Set<string>();

  for (const r of historicalForMonth) {
    const amt = parseHistoricalAmount(r.total_amount_idr as number | string);
    pdfTotal += amt ?? 0;
    const tasks = Number(r.task_count);
    pdfTasks += Number.isSafeInteger(tasks) && tasks >= 0 ? tasks : 0;
    if (r.source_pdf) sources.add(r.source_pdf);

    if (amt === null) {
      // A paid line we cannot read — pdfTotal now understates the true amount,
      // and we can never call this reconciled.
      unresolvedPaidRecords += 1;
      pdfTotalReliable = false;
      continue;
    }
    if (amt > 0) {
      if (r.employee_id == null) {
        // Paid on paper but not attributable to a ledger member.
        unresolvedPaidRecords += 1;
      } else if (!ledgerMemberIds.has(r.employee_id)) {
        // The ledger was not yet capturing this member's payment this month.
        // A 0-IDR PDF line is NOT evidence of a missing payment. Counted by
        // distinct id — repeat PDF rows for one member are still one member.
        missingMemberIds.add(r.employee_id);
      }
    }
  }

  return {
    monthKey,
    monthLabel: monthKeyLabel(monthKey),
    pdfTotal,
    pdfTasks,
    sources: [...sources],
    ledgerTotal,
    ledgerAuthoritative:
      missingMemberIds.size === 0 && unresolvedPaidRecords === 0,
    missingPaidMembers: missingMemberIds.size,
    unresolvedPaidRecords,
    pdfTotalReliable,
  };
}

/**
 * Build the per-month reconciliation verdict for EVERY month that has a
 * pre-system PDF recap, from the FULL unfiltered ledger + PDF.
 *
 * The verdict is a property of the whole MONTH and must NOT depend on the page's
 * year/status/member display filters. Computing it on a filtered slice was a
 * real defect: filtering to a single member drops the very members whose absence
 * defines the incompleteness, silently flipping a PDF-authoritative month to
 * "ledger authoritative" and telling accounting to pay the wrong (smaller)
 * number. The page looks this map up by month key and NEVER recomputes it from a
 * filtered slice; filters only change which months/rows/amounts are displayed.
 */
export function buildMonthlyReconciliation(
  bonuses: Bonus[],
  historical: BonusHistoricalRecord[],
): Map<string, HistoricalReconciliation> {
  const ledgerIds = new Map<string, Set<number>>();
  const ledgerTotals = new Map<string, number>();
  for (const b of bonuses) {
    const key = witaMonthKey(b.awarded_at);
    if (b.employee_id != null) {
      let set = ledgerIds.get(key);
      if (!set) {
        set = new Set();
        ledgerIds.set(key, set);
      }
      set.add(b.employee_id);
    }
    ledgerTotals.set(key, (ledgerTotals.get(key) ?? 0) + amountOf(b));
  }

  const pdfByMonth = new Map<string, BonusHistoricalRecord[]>();
  for (const r of historical) {
    const key = `${r.bonus_year}-${String(r.bonus_month).padStart(2, "0")}`;
    const arr = pdfByMonth.get(key) ?? [];
    arr.push(r);
    pdfByMonth.set(key, arr);
  }

  const out = new Map<string, HistoricalReconciliation>();
  for (const [key, recs] of pdfByMonth) {
    const recon = reconcileMonth(
      key,
      ledgerIds.get(key) ?? new Set<number>(),
      ledgerTotals.get(key) ?? 0,
      recs,
    );
    if (recon) out.set(key, recon);
  }
  return out;
}
