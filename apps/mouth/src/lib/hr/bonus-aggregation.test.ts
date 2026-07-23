import { describe, expect, it } from "vitest";
import type { Bonus, BonusHistoricalRecord } from "@/types/hr";
import {
  aggregateByMember,
  bonusesToCsv,
  buildMonthlyReconciliation,
  groupBonusesByMonth,
  monthKeyLabel,
  parseHistoricalAmount,
  reconcileMonth,
  witaMonthKey,
} from "./bonus-aggregation";

/** Minimal Bonus factory — only the fields the aggregation reads. */
function bonus(over: Partial<Bonus> & { id: number }): Bonus {
  return {
    practice_id: 0,
    employee_id: 1,
    payroll_period_id: null,
    bonus_rate_id: null,
    practice_type_code: "visa_b211",
    amount_idr: 100_000,
    status: "approved",
    awarded_at: "2026-07-10T02:00:00.000Z",
    awarded_by: null,
    approved_by: null,
    approved_at: null,
    employee_name: "Surya",
    employee_email: "surya@balizero.com",
    practice_status: "completed",
    client_name: null,
    notes: null,
    ...over,
  } as Bonus;
}

describe("witaMonthKey", () => {
  it("buckets by Asia/Makassar (WITA), not by UTC", () => {
    // 2026-02-28T16:00Z === 2026-03-01T00:00 WITA → March, not February.
    expect(witaMonthKey("2026-02-28T16:00:00.000Z")).toBe("2026-03");
  });

  it("keeps a mid-day UTC timestamp in its own month", () => {
    expect(witaMonthKey("2026-07-10T02:00:00.000Z")).toBe("2026-07");
  });

  it("handles the last instant of a WITA month", () => {
    // 2026-06-30T15:59Z === 2026-06-30T23:59 WITA → still June.
    expect(witaMonthKey("2026-06-30T15:59:00.000Z")).toBe("2026-06");
  });

  it("returns empty string for missing or unparseable input", () => {
    expect(witaMonthKey("")).toBe("");
    expect(witaMonthKey("not-a-date")).toBe("");
    expect(witaMonthKey(null as unknown as string)).toBe("");
  });
});

describe("groupBonusesByMonth", () => {
  it("returns months newest-first", () => {
    const months = groupBonusesByMonth([
      bonus({ id: 1, awarded_at: "2026-05-02T02:00:00.000Z" }),
      bonus({ id: 2, awarded_at: "2026-07-02T02:00:00.000Z" }),
      bonus({ id: 3, awarded_at: "2026-06-02T02:00:00.000Z" }),
    ]);
    expect(months.map((m) => m.key)).toEqual(["2026-07", "2026-06", "2026-05"]);
  });

  it("totals each month and splits pending out", () => {
    const months = groupBonusesByMonth([
      bonus({ id: 1, amount_idr: 300_000, status: "approved" }),
      bonus({ id: 2, amount_idr: 200_000, status: "pending" }),
      bonus({ id: 3, amount_idr: 500_000, status: "approved" }),
    ]);
    expect(months).toHaveLength(1);
    expect(months[0].total).toBe(1_000_000);
    expect(months[0].pendingTotal).toBe(200_000);
    expect(months[0].approvedTotal).toBe(800_000);
    expect(months[0].count).toBe(3);
  });

  it("aggregates per member inside the month, highest total first", () => {
    const months = groupBonusesByMonth([
      bonus({
        id: 1,
        employee_id: 1,
        employee_name: "Adit",
        amount_idr: 100_000,
      }),
      bonus({
        id: 2,
        employee_id: 3,
        employee_name: "Surya",
        amount_idr: 900_000,
      }),
      bonus({
        id: 3,
        employee_id: 1,
        employee_name: "Adit",
        amount_idr: 250_000,
      }),
    ]);
    const members = months[0].members;
    expect(members.map((m) => m.employeeName)).toEqual(["Surya", "Adit"]);
    expect(members[0].total).toBe(900_000);
    expect(members[1].total).toBe(350_000);
    expect(members[1].count).toBe(2);
    expect(months[0].memberCount).toBe(2);
  });

  it("splits a member's month total by status", () => {
    const months = groupBonusesByMonth([
      bonus({ id: 1, amount_idr: 400_000, status: "approved" }),
      bonus({ id: 2, amount_idr: 150_000, status: "pending" }),
      bonus({ id: 3, amount_idr: 50_000, status: "paid" }),
    ]);
    const m = months[0].members[0];
    expect(m.total).toBe(600_000);
    expect(m.byStatus.approved).toBe(400_000);
    expect(m.byStatus.pending).toBe(150_000);
    expect(m.byStatus.paid).toBe(50_000);
  });

  it("keeps the member's own bonus rows attached, newest first", () => {
    const months = groupBonusesByMonth([
      bonus({ id: 1, awarded_at: "2026-07-02T02:00:00.000Z" }),
      bonus({ id: 2, awarded_at: "2026-07-20T02:00:00.000Z" }),
    ]);
    expect(months[0].members[0].bonuses.map((b) => b.id)).toEqual([2, 1]);
  });

  it("never drops money: undated rows land in their own bucket, sorted last", () => {
    const months = groupBonusesByMonth([
      bonus({ id: 1, amount_idr: 100_000 }),
      bonus({ id: 2, amount_idr: 700_000, awarded_at: "" }),
    ]);
    expect(months).toHaveLength(2);
    expect(months[1].key).toBe("");
    expect(months[1].total).toBe(700_000);
    const grand = months.reduce((s, m) => s + m.total, 0);
    expect(grand).toBe(800_000);
  });

  it("separates members with the same name but different employee_id", () => {
    const months = groupBonusesByMonth([
      bonus({
        id: 1,
        employee_id: 1,
        employee_name: "Ari",
        amount_idr: 100_000,
      }),
      bonus({
        id: 2,
        employee_id: 9,
        employee_name: "Ari",
        amount_idr: 200_000,
      }),
    ]);
    expect(months[0].members).toHaveLength(2);
  });

  it("coerces string amounts (BIGINT serialised as text) instead of concatenating", () => {
    const months = groupBonusesByMonth([
      bonus({ id: 1, amount_idr: "300000" as unknown as number }),
      bonus({ id: 2, amount_idr: "200000" as unknown as number }),
    ]);
    expect(months[0].total).toBe(500_000);
  });

  it("returns an empty array for no bonuses", () => {
    expect(groupBonusesByMonth([])).toEqual([]);
  });
});

describe("aggregateByMember", () => {
  it("totals each member across every month, highest first", () => {
    const rows = aggregateByMember([
      bonus({
        id: 1,
        employee_id: 1,
        employee_name: "Adit",
        amount_idr: 100_000,
        awarded_at: "2026-05-02T02:00:00.000Z",
      }),
      bonus({
        id: 2,
        employee_id: 1,
        employee_name: "Adit",
        amount_idr: 200_000,
        awarded_at: "2026-06-02T02:00:00.000Z",
      }),
      bonus({
        id: 3,
        employee_id: 3,
        employee_name: "Surya",
        amount_idr: 250_000,
        awarded_at: "2026-06-02T02:00:00.000Z",
      }),
    ]);
    expect(rows.map((r) => r.employeeName)).toEqual(["Adit", "Surya"]);
    expect(rows[0].total).toBe(300_000);
    expect(rows[0].monthCount).toBe(2);
    expect(rows[0].count).toBe(2);
    expect(rows[1].monthCount).toBe(1);
  });

  it("exposes each member's per-month totals keyed by month", () => {
    const rows = aggregateByMember([
      bonus({
        id: 1,
        amount_idr: 100_000,
        awarded_at: "2026-05-02T02:00:00.000Z",
      }),
      bonus({
        id: 2,
        amount_idr: 400_000,
        awarded_at: "2026-06-02T02:00:00.000Z",
      }),
    ]);
    expect(rows[0].byMonth["2026-05"]).toBe(100_000);
    expect(rows[0].byMonth["2026-06"]).toBe(400_000);
  });

  it("agrees with the month grouping on the grand total", () => {
    const data = [
      bonus({
        id: 1,
        employee_id: 1,
        amount_idr: 100_000,
        awarded_at: "2026-05-02T02:00:00.000Z",
      }),
      bonus({
        id: 2,
        employee_id: 2,
        amount_idr: 250_000,
        awarded_at: "2026-06-02T02:00:00.000Z",
      }),
      bonus({
        id: 3,
        employee_id: 2,
        amount_idr: 300_000,
        awarded_at: "2026-07-02T02:00:00.000Z",
      }),
      bonus({ id: 4, employee_id: 1, amount_idr: 700_000, awarded_at: "" }),
    ];
    const byMonth = groupBonusesByMonth(data).reduce((s, m) => s + m.total, 0);
    const byMember = aggregateByMember(data).reduce((s, r) => s + r.total, 0);
    expect(byMonth).toBe(byMember);
    expect(byMonth).toBe(1_350_000);
  });
});

describe("bonusesToCsv", () => {
  it("emits one row per member per month plus a header", () => {
    const csv = bonusesToCsv(
      groupBonusesByMonth([
        bonus({
          id: 1,
          employee_id: 1,
          employee_name: "Adit",
          amount_idr: 100_000,
        }),
        bonus({
          id: 2,
          employee_id: 3,
          employee_name: "Surya",
          amount_idr: 900_000,
        }),
      ]),
    );
    const lines = csv.trim().split("\n");
    expect(lines[0]).toBe(
      "month,employee_id,employee_name,employee_email,bonus_count,pending_idr,approved_idr,paid_idr,total_idr",
    );
    expect(lines).toHaveLength(3);
    expect(lines[1]).toContain("2026-07");
    expect(lines[1]).toContain("900000");
  });

  it("quotes and escapes fields containing commas or quotes", () => {
    const csv = bonusesToCsv(
      groupBonusesByMonth([
        bonus({ id: 1, employee_name: 'Adit, "AD"', amount_idr: 100_000 }),
      ]),
    );
    expect(csv).toContain('"Adit, ""AD"""');
  });

  it("neutralises formula injection in a name without touching the amounts", () => {
    const csv = bonusesToCsv(
      groupBonusesByMonth([
        bonus({
          id: 1,
          employee_name: "=cmd|'/c calc'!A1",
          amount_idr: 250_000,
        }),
      ]),
    );
    expect(csv).toContain("'=cmd");
    expect(csv).not.toMatch(/,=cmd/);
    // The amount is still a bare number, not text.
    expect(csv).toContain(",250000");
  });

  it("writes amounts as bare integers so spreadsheets read them as numbers", () => {
    const csv = bonusesToCsv(
      groupBonusesByMonth([bonus({ id: 1, amount_idr: 1_250_000 })]),
    );
    expect(csv).toContain(",1250000");
    expect(csv).not.toContain("Rp");
  });
});

function hist(
  over: Partial<BonusHistoricalRecord> & { id: number },
): BonusHistoricalRecord {
  return {
    employee_name: "SURYA",
    employee_id: 3,
    bonus_month: 2,
    bonus_year: 2026,
    total_amount_idr: 3_000_000,
    task_count: 13,
    source_pdf: "LIST BONUS FEBRUARY 2026.pdf",
    accounting_total_data: null,
    accounting_not_paid: null,
    accounting_paid: null,
    imported_at: "2026-03-01T00:00:00.000Z",
    notes: null,
    ...over,
  } as BonusHistoricalRecord;
}

describe("parseHistoricalAmount", () => {
  it("accepts a non-negative safe integer, as number or digit-string", () => {
    expect(parseHistoricalAmount(550_000)).toBe(550_000);
    expect(parseHistoricalAmount("550000")).toBe(550_000);
    expect(parseHistoricalAmount(" 550000 ")).toBe(550_000);
    expect(parseHistoricalAmount(0)).toBe(0);
  });

  it("returns null for anything that must NOT silently become 0", () => {
    // A comma-formatted string coerced by `Number(x)||0` would become 0 and
    // read as "member not paid" — hiding a real incompleteness.
    expect(parseHistoricalAmount("500,000")).toBeNull();
    expect(parseHistoricalAmount("Infinity")).toBeNull();
    expect(parseHistoricalAmount("12.5")).toBeNull();
    expect(parseHistoricalAmount("")).toBeNull();
    expect(parseHistoricalAmount(-5 as unknown as number)).toBeNull();
    // Beyond 2^53 — a bigint that would lose precision through Number().
    expect(parseHistoricalAmount("9007199254740993")).toBeNull();
  });
});

describe("monthKeyLabel", () => {
  it("labels a YYYY-MM key with no timestamp", () => {
    expect(monthKeyLabel("2026-02")).toBe("February 2026");
    expect(monthKeyLabel("2026-12")).toBe("December 2026");
  });
  it("falls back for keys it cannot parse", () => {
    expect(monthKeyLabel("")).toBe("Undated");
    expect(monthKeyLabel("garbage")).toBe("Undated");
  });
});

describe("reconcileMonth", () => {
  it("returns null when the month has no PDF recap", () => {
    expect(reconcileMonth("2026-07", new Set([1]), 100_000, [])).toBeNull();
  });

  it("FEBRUARY case: a paid member absent from the ledger → PDF authoritative", () => {
    // Ledger Feb member set: only SURYA (id 3). PDF paid ADIT + ARI too.
    const rec = reconcileMonth("2026-02", new Set([3]), 2_760_000, [
      hist({ id: 1, employee_id: 3, total_amount_idr: 3_000_000 }),
      hist({
        id: 2,
        employee_id: 1,
        employee_name: "ADIT",
        total_amount_idr: 7_650_000,
      }),
      hist({
        id: 3,
        employee_id: 2,
        employee_name: "ARI",
        total_amount_idr: 4_300_000,
      }),
    ])!;
    expect(rec.ledgerAuthoritative).toBe(false);
    expect(rec.missingPaidMembers).toBe(2); // ADIT + ARI
    expect(rec.unresolvedPaidRecords).toBe(0);
    expect(rec.pdfTotal).toBe(14_950_000);
    expect(rec.ledgerTotal).toBe(2_760_000);
    expect(rec.monthLabel).toBe("February 2026");
  });

  it("MARCH case: every paid PDF member is in the ledger → ledger authoritative", () => {
    const rec = reconcileMonth("2026-03", new Set([2]), 6_100_000, [
      hist({
        id: 1,
        employee_id: 2,
        bonus_month: 3,
        total_amount_idr: 2_000_000,
      }),
      // ADIT recorded at 0 IDR on paper — NOT a missing payment.
      hist({
        id: 2,
        employee_id: 1,
        employee_name: "ADIT",
        bonus_month: 3,
        total_amount_idr: 0,
      }),
    ])!;
    expect(rec.ledgerAuthoritative).toBe(true);
    expect(rec.missingPaidMembers).toBe(0);
  });

  it("a 0-IDR PDF line for an absent member is not counted as missing", () => {
    const rec = reconcileMonth("2026-07", new Set([3]), 500_000, [
      hist({
        id: 1,
        employee_id: 9,
        employee_name: "GHOST",
        total_amount_idr: 0,
      }),
    ])!;
    expect(rec.missingPaidMembers).toBe(0);
    expect(rec.ledgerAuthoritative).toBe(true);
  });

  it("a positive PDF payment with a null employee_id is UNRESOLVED, never ledger-authoritative", () => {
    const rec = reconcileMonth("2026-02", new Set([3]), 2_760_000, [
      hist({
        id: 1,
        employee_id: null,
        employee_name: "UNMATCHED",
        total_amount_idr: 500_000,
      }),
    ])!;
    expect(rec.unresolvedPaidRecords).toBe(1);
    expect(rec.missingPaidMembers).toBe(0);
    expect(rec.ledgerAuthoritative).toBe(false);
  });

  it("an unparseable amount is UNRESOLVED, understates the total, and marks it unreliable", () => {
    const rec = reconcileMonth("2026-02", new Set([3]), 2_760_000, [
      hist({ id: 1, employee_id: 3, total_amount_idr: 1_000_000 }),
      hist({
        id: 2,
        employee_id: 3,
        total_amount_idr: "500,000" as unknown as number,
      }),
    ])!;
    expect(rec.unresolvedPaidRecords).toBe(1);
    expect(rec.pdfTotal).toBe(1_000_000); // the unreadable line is NOT added
    expect(rec.pdfTotalReliable).toBe(false); // so the total is understated
    expect(rec.ledgerAuthoritative).toBe(false);
  });

  it("counts DISTINCT missing members, not PDF records", () => {
    // Two PDF rows for the same absent member (id 99) = ONE missing member.
    const rec = reconcileMonth("2026-02", new Set([3]), 2_760_000, [
      hist({ id: 1, employee_id: 99, total_amount_idr: 1_000_000 }),
      hist({ id: 2, employee_id: 99, total_amount_idr: 500_000 }),
    ])!;
    expect(rec.missingPaidMembers).toBe(1);
    expect(rec.pdfTotal).toBe(1_500_000);
    expect(rec.pdfTotalReliable).toBe(true);
  });

  it("dedupes source filenames and sums tasks", () => {
    const rec = reconcileMonth("2026-02", new Set([3]), 100_000, [
      hist({ id: 1, employee_id: 3, task_count: 13, source_pdf: "recap.pdf" }),
      hist({ id: 2, employee_id: 3, task_count: 5, source_pdf: "recap.pdf" }),
    ])!;
    expect(rec.sources).toEqual(["recap.pdf"]);
    expect(rec.pdfTasks).toBe(18);
  });

  it("coerces string amounts (BIGINT-as-text) before comparing", () => {
    const rec = reconcileMonth("2026-02", new Set([3]), 100_000, [
      hist({
        id: 1,
        employee_id: 7,
        total_amount_idr: "550000" as unknown as number,
      }),
    ])!;
    expect(rec.pdfTotal).toBe(550_000);
    expect(rec.missingPaidMembers).toBe(1); // id 7 paid, absent from ledger
    expect(rec.ledgerAuthoritative).toBe(false);
  });
});

describe("buildMonthlyReconciliation", () => {
  it("computes the verdict from the FULL ledger, not a filtered slice", () => {
    // The real Feb 2026 shape: ledger members {3,4,7}, PDF paid {1,2,3,4,5,7}.
    const bonuses: Bonus[] = [
      bonus({
        id: 1,
        employee_id: 3,
        amount_idr: 1_000_000,
        awarded_at: "2026-02-10T02:00:00.000Z",
      }),
      bonus({
        id: 2,
        employee_id: 4,
        amount_idr: 1_000_000,
        awarded_at: "2026-02-11T02:00:00.000Z",
      }),
      bonus({
        id: 3,
        employee_id: 7,
        amount_idr: 1_660_000,
        awarded_at: "2026-02-12T02:00:00.000Z",
      }),
    ];
    const historical = [1, 2, 3, 4, 5, 7].map((eid, i) =>
      hist({ id: i + 1, employee_id: eid, total_amount_idr: 1_000_000 }),
    );
    const map = buildMonthlyReconciliation(bonuses, historical);
    const feb = map.get("2026-02")!;
    // ids 1,2,5 are paid by the PDF but absent from the ledger → 3 missing.
    expect(feb.missingPaidMembers).toBe(3);
    expect(feb.ledgerAuthoritative).toBe(false);
    // ledgerTotal is the FULL month ledger, independent of the PDF.
    expect(feb.ledgerTotal).toBe(3_660_000);
  });

  it("keys the verdict by WITA month, and omits months with no PDF recap", () => {
    const bonuses: Bonus[] = [
      // A July ledger month with no PDF recap — must NOT appear.
      bonus({ id: 1, employee_id: 3, awarded_at: "2026-07-10T02:00:00.000Z" }),
    ];
    const historical = [hist({ id: 1, employee_id: 3 })]; // Feb 2026
    const map = buildMonthlyReconciliation(bonuses, historical);
    expect(map.has("2026-02")).toBe(true);
    expect(map.has("2026-07")).toBe(false);
  });

  it("a WITA-boundary ledger row lands in the right month for the verdict", () => {
    // 2026-01-31T16:00:00Z is 2026-02-01 00:00 WITA → February ledger.
    const bonuses: Bonus[] = [
      bonus({ id: 1, employee_id: 3, awarded_at: "2026-01-31T16:00:00.000Z" }),
    ];
    const historical = [
      hist({ id: 1, employee_id: 3, total_amount_idr: 1_000_000 }),
      hist({
        id: 2,
        employee_id: 1,
        employee_name: "ADIT",
        total_amount_idr: 500_000,
      }),
    ];
    const feb = buildMonthlyReconciliation(bonuses, historical).get("2026-02")!;
    // id 3 is present in Feb (via the WITA boundary), id 1 is missing.
    expect(feb.missingPaidMembers).toBe(1);
  });
});
