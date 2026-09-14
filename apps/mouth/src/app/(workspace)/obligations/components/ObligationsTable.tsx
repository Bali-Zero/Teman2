"use client";

import { Fragment, useState } from "react";

import { cn } from "@/lib/utils";
import {
  CellStack,
  FOCUS,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  TABULAR,
} from "@/components/workspace/r19";

import { INPUT_STYLE, type CatalogRuleOut, type ObligationOut } from "./types";

/**
 * Register status → outlined SQUARE pill, word first. Kept page-local
 * (rather than the shared `StatePill`, which is `rounded-full`) so the
 * concept's `.state{border-radius:2px}` square survives on a dense table row.
 *
 * - `proposed` is copper because the row renders the viewer's own Approve and
 *   Reject controls, so the viewer is demonstrably the next actor;
 * - `alerted` is copper by the standing ruling in `concept/DISPOSITION.md`
 *   C11 ("obligations `alerted` -> copper, `rejected` -> waiting"), recorded
 *   as a RULING and not as a derivation this row can prove.
 *
 * `approved`/`done` are forest. `rejected` is a TERMINAL failure, so law #3
 * binds it — muted, never danger, plus its own word. A due DATE is never a
 * tone here: urgency lives on the date cell in warning, and it neither grants
 * nor removes ownership.
 */
const STATUS_TONE: Record<string, string> = {
  proposed: "text-[var(--bz-copper-text)] border-[var(--bz-copper-text)]",
  approved: "text-[var(--state-success)] border-[var(--state-success)]",
  done: "text-[var(--state-success)] border-[var(--state-success)]",
  rejected: "text-[var(--tx-secondary)] border-[var(--line-control)]",
  alerted: "text-[var(--bz-copper-text)] border-[var(--bz-copper-text)]",
};

function StatusPill({ status }: { status: string }) {
  const tone =
    STATUS_TONE[status] ??
    "text-[var(--tx-secondary)] border-[var(--line-control)]";
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-[2px] border bg-transparent px-2.5",
        "text-[10px] font-[650] uppercase tracking-[0.12em]",
        tone,
      )}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 shrink-0 rounded-full bg-current"
      />
      {status}
    </span>
  );
}

/**
 * The grid's column order, desktop width. Below 768px the grid collapses to
 * `Client` (the primary column) + `Actions` (see the `HairlineGrid`
 * `className` override below); every other value MOVES onto `Client`'s
 * secondary line rather than leaving the accessibility tree.
 */
// The ten tracks' MINIMA are what decide whether this fits, not their fr
// weights: a grid cannot shrink below the sum of its minimums. At
// 56/150/170/90/92/104/110/108/120/216 that sum is 1216px, and the desk's
// content column at a 1440 viewport is ~1176 — so the register overflowed
// its own page by 44px on the widest width anyone uses it at (measured:
// scrollWidth 1484, clientWidth 1440). Every minimum below is set from the
// widest string the column can actually hold, not from a guess.
const COLS =
  "48px minmax(110px,1.1fr) minmax(150px,1.6fr) minmax(80px,0.7fr) " +
  "86px 100px minmax(100px,0.9fr) 104px minmax(110px,1fr) 180px";

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
] as const;

/**
 * "2026-10-10" -> "October 2026". Parsed from the ISO string, never through
 * `new Date(...)`: the backend sends a plain date and a Date parse would shift
 * it by the viewer's UTC offset, moving a due date into the previous month for
 * anyone west of Greenwich.
 */
export function dueMonthLabel(dueDate: string): string {
  const match = /^(\d{4})-(\d{2})/.exec(dueDate ?? "");
  if (!match) return "Unscheduled";
  const month = MONTH_NAMES[Number(match[2]) - 1];
  return month ? `${month} ${match[1]}` : "Unscheduled";
}

/**
 * True when `dueDate` (YYYY-MM-DD) is already past or due within 7 days,
 * measured against "today" in the business timezone Asia/Makassar — never
 * the runtime's, so a reviewer in another timezone sees the same urgency
 * window the Bali desk does. Urgency ONLY: this never touches a pill's tone
 * and never makes a row copper.
 */
export function isDueSoon(dueDate: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(dueDate ?? "");
  if (!match) return false;
  const due = Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );

  const todayParts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Makassar",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const year = Number(todayParts.find((p) => p.type === "year")?.value);
  const month = Number(todayParts.find((p) => p.type === "month")?.value);
  const day = Number(todayParts.find((p) => p.type === "day")?.value);
  const today = Date.UTC(year, month - 1, day);

  const diffDays = Math.round((due - today) / 86400000);
  return diffDays <= 7;
}

interface Props {
  items: ObligationOut[];
  /** rule_id -> catalog rule, from `GET /obligations/catalog`. */
  catalog: Map<string, CatalogRuleOut>;
  /** client_id -> display name; an absent id renders as the id. */
  clientNames: Record<number, string>;
  /** True when a client filter is set: rows are grouped by due month. */
  groupByMonth: boolean;
  notes: Record<number, string>;
  rowError: Record<number, string>;
  busyId: number | null;
  onNoteChange: (id: number, value: string) => void;
  onApprove: (row: ObligationOut) => void;
  onReject: (row: ObligationOut) => void;
}

export function ObligationsTable({
  items,
  catalog,
  clientNames,
  groupByMonth,
  notes,
  rowError,
  busyId,
  onNoteChange,
  onApprove,
  onReject,
}: Props) {
  const [openDetail, setOpenDetail] = useState<number | null>(null);

  // Groups in the order the server returned the rows (due_date ascending), so
  // the flat and grouped views never disagree about sequence.
  const groups: Array<{ label: string; rows: ObligationOut[] }> = [];
  if (groupByMonth) {
    for (const row of items) {
      const label = dueMonthLabel(row.due_date);
      const last = groups[groups.length - 1];
      if (last && last.label === label) last.rows.push(row);
      else groups.push({ label, rows: [row] });
    }
  } else {
    groups.push({ label: "", rows: items });
  }

  const renderRow = (row: ObligationOut) => {
    const rule = catalog.get(row.rule_id);
    const isOpen = openDetail === row.id;
    const clientName = clientNames[row.client_id];
    const ruleLabel = rule?.name ?? row.rule_id;
    const verifiedLabel = rule?.verified ? "verified" : "unverified";

    return (
      <Fragment key={row.id}>
        <HairlineRow data-testid={`obligation-row-${row.id}`}>
          {/* ID — desktop only; re-appears prefixed "#" on the secondary
              line below, never as a second bare "101". */}
          <span className="max-md:hidden" style={TABULAR}>
            {row.id}
          </span>

          {/* Client — the primary column: stays in the grid at every width. */}
          <div className="min-w-0 px-2.5">
            <CellStack
              primary={clientName ?? row.client_id}
              secondary={clientName ? `#${row.client_id}` : undefined}
            />
            {/* The dropped columns, relocated for a phone — moved, not
                hidden. Each line is its own composite sentence so it never
                repeats a bare value the desktop cells already carry (the
                id, the rule name, the rule id, the authority, the status
                word): the SAME facts, grouped differently, not duplicated
                text nodes. */}
            <span className="mt-1 flex flex-col gap-0.5 text-[11px] text-[var(--tx-secondary)] md:hidden">
              <span>#{row.id}</span>
              <span>
                {ruleLabel} ({row.rule_id}) — {rule?.authority ?? "—"} ·{" "}
                {verifiedLabel}
              </span>
              <span style={TABULAR}>
                {row.period_key} · due {row.due_date}
                {row.needs_review_reason ? ` · ${row.needs_review_reason}` : ""}
              </span>
              <span>
                Status {row.status}
                {row.reviewer_email ? ` · ${row.reviewer_email}` : ""}
              </span>
            </span>
          </div>

          {/* Rule — desktop only. */}
          <div className="max-md:hidden px-2.5">
            <button
              type="button"
              onClick={() => setOpenDetail(isOpen ? null : row.id)}
              aria-expanded={isOpen}
              aria-label={`Rule detail for obligation ${row.id}`}
              className="text-left underline-offset-2 hover:underline"
              style={{ color: "var(--tx-pure)" }}
            >
              {ruleLabel}
            </button>
            {/* "verified" is the normal case and reads muted — no colour at
                all. "unverified" keeps --state-warning: an unverified rule
                is the one that needs attention. Previously both read the
                same warning-adjacent treatment, which made a rule and its
                opposite look alike; now only the state that needs a look
                carries the warning tone, and both keep their word. */}
            <span
              className="ml-2 rounded px-1.5 py-0.5 text-xs"
              style={{
                border: `1px solid ${
                  rule?.verified
                    ? "var(--line-control)"
                    : "var(--state-warning)"
                }`,
                color: rule?.verified
                  ? "var(--tx-secondary)"
                  : "var(--state-warning)",
              }}
            >
              {verifiedLabel}
            </span>
            {rule?.name && (
              <span className="block text-xs text-[var(--tx-secondary)]">
                {row.rule_id}
              </span>
            )}
          </div>

          {/* Authority — desktop only. */}
          <span className="max-md:hidden truncate text-xs text-[var(--tx-secondary)]">
            {rule?.authority ?? "—"}
          </span>

          {/* Period — desktop only. */}
          <span className="max-md:hidden text-[var(--tx-pure)]" style={TABULAR}>
            {row.period_key}
          </span>

          {/* Due date — desktop only; warning when due soon, never a status
              tone (urgency is a date property, not ownership). */}
          <span
            className="max-md:hidden"
            style={{
              color: isDueSoon(row.due_date)
                ? "var(--state-warning)"
                : "var(--tx-pure)",
              ...TABULAR,
            }}
          >
            {row.due_date}
          </span>

          {/* Needs review — desktop only. */}
          <span className="max-md:hidden truncate text-xs text-[var(--tx-secondary)]">
            {row.needs_review_reason ?? "—"}
          </span>

          {/* Status — desktop only; STATUS_TONE/`alerted` copper is a
              standing ruling (DISPOSITION C11), left untouched. */}
          <span className="max-md:hidden">
            <StatusPill status={row.status} />
          </span>

          {/* Reviewer — desktop only. */}
          <span className="max-md:hidden truncate text-xs text-[var(--tx-secondary)]">
            {row.reviewer_email ? (
              <>
                {row.reviewer_email}
                {row.reviewed_at
                  ? ` · ${new Date(row.reviewed_at).toLocaleString()}`
                  : ""}
              </>
            ) : (
              "—"
            )}
          </span>

          {/* Actions — always in the grid, at every width (never moved). */}
          <div className="px-2.5">
            {row.status === "proposed" ? (
              <div className="flex flex-col gap-1">
                <input
                  aria-label={`Note for obligation ${row.id}`}
                  className="w-full min-w-0 max-w-40 rounded border px-2 py-1 text-xs"
                  style={INPUT_STYLE}
                  placeholder="note (required to reject)"
                  value={notes[row.id] ?? ""}
                  onChange={(e) => onNoteChange(row.id, e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busyId === row.id}
                    onClick={() => onApprove(row)}
                    // Outlined, not filled. The ledger has no filled
                    // buttons, and a solid green Approve beside an outlined
                    // Reject read as if only one of the two were the real
                    // action. Both are the viewer's; the STATUS pill is what
                    // carries the copper that says so.
                    className={cn(
                      "min-h-8 border border-[var(--state-success)] bg-transparent px-3 text-xs font-[650] text-[var(--state-success)]",
                      FOCUS,
                    )}
                    style={{ opacity: busyId === row.id ? 0.6 : 1 }}
                  >
                    {busyId === row.id ? "…" : "Approve"}
                  </button>
                  {/* Neutral outline, not copper. Copper on this row already
                      says "you are the next actor" through the STATUS pill;
                      putting it on REJECT alone made the colour read as
                      "the negative choice", which is not what it means. */}
                  <button
                    type="button"
                    disabled={busyId === row.id}
                    onClick={() => onReject(row)}
                    className={cn(
                      "min-h-8 border border-[var(--line-control)] bg-transparent px-3 text-xs font-[650] text-[var(--tx-pure)]",
                      FOCUS,
                    )}
                    style={{ opacity: busyId === row.id ? 0.6 : 1 }}
                  >
                    {busyId === row.id ? "…" : "Reject"}
                  </button>
                </div>
                {rowError[row.id] && (
                  // Copper: the viewer just tried to decide this row and the
                  // decision failed — they are the next actor to retry it.
                  <p
                    role="alert"
                    className="text-xs"
                    style={{ color: "var(--bz-copper-text)" }}
                  >
                    {rowError[row.id]}
                  </p>
                )}
              </div>
            ) : (
              <span
                className="text-xs"
                style={{ color: "var(--tx-secondary)" }}
              >
                {row.alert_id ? `alert ${row.alert_id}` : "—"}
              </span>
            )}
          </div>
        </HairlineRow>
        {isOpen && (
          <div className="border-b border-[var(--bz-border)] bg-[var(--bz-card)] px-3 py-3">
            {rule ? (
              <dl
                className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2"
                style={{ color: "var(--tx-secondary)" }}
              >
                <div className="sm:col-span-2">
                  <dt
                    className="font-medium"
                    style={{ color: "var(--tx-pure)" }}
                  >
                    Legal source
                  </dt>
                  <dd>{rule.legal_source}</dd>
                </div>
                <div>
                  <dt
                    className="font-medium"
                    style={{ color: "var(--tx-pure)" }}
                  >
                    Schedule
                  </dt>
                  <dd>
                    {rule.frequency}, roll {rule.roll}
                  </dd>
                </div>
                <div>
                  <dt
                    className="font-medium"
                    style={{ color: "var(--tx-pure)" }}
                  >
                    Trigger
                  </dt>
                  <dd>{rule.trigger ?? "—"}</dd>
                </div>
                {rule.needs_review_reason && (
                  <div className="sm:col-span-2">
                    <dt
                      className="font-medium"
                      style={{ color: "var(--tx-pure)" }}
                    >
                      Catalog review note
                    </dt>
                    <dd>{rule.needs_review_reason}</dd>
                  </div>
                )}
                {rule.notes && (
                  <div className="sm:col-span-2">
                    <dt
                      className="font-medium"
                      style={{ color: "var(--tx-pure)" }}
                    >
                      Notes
                    </dt>
                    <dd>{rule.notes}</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-xs" style={{ color: "var(--tx-secondary)" }}>
                Rule {row.rule_id} is not in the catalog.
              </p>
            )}
          </div>
        )}
      </Fragment>
    );
  };

  return (
    <HairlineGrid
      cols={COLS}
      // NEITHER `--cols` override shape works on this primitive, and both
      // were tried and MEASURED here before this line was written:
      //
      //   1. `max-md:[--cols:minmax(0,1fr)]` as a class — inert, because
      //      HairlineGrid sets `--cols` as an INLINE style and an inline
      //      declaration beats any class.
      //   2. the primitive's OWN `colsCollapsed` + `collapseAt` + `id` API —
      //      also inert, and for the same reason: it emits a stylesheet rule
      //      setting `--cols` on the very element whose inline style already
      //      sets it. A media-query rule cannot win against inline without
      //      `!important`. That is a defect in the v2 primitive (#6520),
      //      reported to the seat that owns it; it is not this window's to
      //      edit.
      //
      // Both left the ten tracks in force at 390, where empty tracks still
      // claim their minimums, so the client column collapsed to ~60px and
      // every word wrapped one per line. This overrides the TEMPLATE on the
      // rows themselves instead of the variable they read, which does win,
      // and it is scoped to this grid's own descendants.
      className="max-md:[&_.grid]:!grid-cols-[minmax(0,1fr)]"
    >
      <HairlineHead>
        <span className="max-md:hidden">ID</span>
        <span>Client</span>
        <span className="max-md:hidden">Rule</span>
        <span className="max-md:hidden">Authority</span>
        <span className="max-md:hidden">Period</span>
        <span className="max-md:hidden">Due date</span>
        <span className="max-md:hidden">Needs review</span>
        <span className="max-md:hidden">Status</span>
        <span className="max-md:hidden">Reviewer</span>
        {/* Below md the decide controls sit inside the row's own stack, so
            a second column heading names a column that is no longer there. */}
        <span className="max-md:hidden">Actions</span>
      </HairlineHead>
      <HairlineBody>
        {groups.map((group) => (
          <Fragment key={group.label || "all"}>
            {group.label && (
              <div className="border-b border-[var(--bz-border)] bg-[var(--bz-card)] px-2.5 py-2 text-xs font-semibold text-[var(--tx-pure)]">
                {group.label}
                <span className="ml-2 font-normal text-[var(--tx-secondary)]">
                  {group.rows.length} due
                </span>
              </div>
            )}
            {group.rows.map((row) => renderRow(row))}
          </Fragment>
        ))}
      </HairlineBody>
    </HairlineGrid>
  );
}
