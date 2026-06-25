"use client";

/**
 * Accounting — cash-control workspace for Asya (the agency accountant).
 *
 * Modelled on Asya's own "Weekly Cashout" Google Sheet: each invoice-payment
 * row carries the price decomposition (PNBP / URGENT / RPTKA-IMTA / MARGIN /
 * FINAL PRICE). Two surfaces:
 *   1. Weekly Cashout — the money-log table (read), grouped newest-first.
 *   2. Reconciliation inbox — unmatched incoming bank transfers; pick the
 *      matching invoice (candidate ranking from the backend matcher) and
 *      confirm. Confirm is the SINGLE writer of payment_status (superscar #9);
 *      it never auto-advances the practice (Zero's decision: Asya clicks again).
 *
 * RBAC is enforced server-side (403 → error boundary). Money is IDR.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  Wallet,
  Inbox,
  TableProperties,
  CheckCircle2,
  ArrowDownToLine,
  ArrowUpFromLine,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { formatIDR, formatIDRCompact } from "@balizero/core/utils";
import {
  accountingApi,
  type CashoutRow,
  type BankTransaction,
  type CashbookSummary,
  type MatchCandidate,
} from "@/lib/api/workspace/accounting.api";

type Tab = "cashout" | "inbox";

// ── Summary cards ────────────────────────────────────────────────────────────

function SummaryCards({ summary }: { summary: CashbookSummary | null }) {
  const cards = [
    {
      label: "Income (in)",
      value: summary?.income_idr ?? 0,
      icon: ArrowDownToLine,
      tone: "text-emerald-600",
    },
    {
      label: "Outgoing (out)",
      value: summary?.outgoing_idr ?? 0,
      icon: ArrowUpFromLine,
      tone: "text-rose-600",
    },
    {
      label: "Net",
      value: summary?.net_idr ?? 0,
      icon: Wallet,
      tone: "text-foreground",
    },
    {
      label: "Bali Zero margin",
      value: summary?.margin_total_idr ?? 0,
      icon: CheckCircle2,
      tone: "text-[var(--bz-accent,#d4845a)]",
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <div key={c.label} className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {c.label}
              </span>
              <Icon className={`h-4 w-4 ${c.tone}`} />
            </div>
            <p
              className={`mt-2 text-xl font-semibold tabular-nums ${c.tone}`}
              title={formatIDR(c.value)}
            >
              {formatIDRCompact(c.value)}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ── Weekly Cashout table ─────────────────────────────────────────────────────

function CashoutTable({ rows }: { rows: CashoutRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border p-10 text-center text-muted-foreground">
        No cashout rows yet.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Date</th>
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Process</th>
            <th className="px-3 py-2 text-right font-medium">PNBP</th>
            <th className="px-3 py-2 text-right font-medium">Urgent</th>
            <th className="px-3 py-2 text-right font-medium">RPTKA-IMTA</th>
            <th className="px-3 py-2 text-right font-medium">Margin</th>
            <th className="px-3 py-2 text-right font-medium">Final price</th>
            <th className="px-3 py-2 font-medium">Note</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-muted/30">
              <td className="whitespace-nowrap px-3 py-2 tabular-nums text-muted-foreground">
                {r.movement_date ?? "—"}
              </td>
              <td className="px-3 py-2 font-medium">
                {r.client_name ?? r.counterparty ?? "—"}
              </td>
              <td className="px-3 py-2 text-muted-foreground">
                {r.category ?? r.type}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {r.pnbp_idr ? formatIDR(r.pnbp_idr) : "—"}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {r.urgent_idr ? formatIDR(r.urgent_idr) : "—"}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">
                {r.rptka_imta_idr ? formatIDR(r.rptka_imta_idr) : "—"}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-[var(--bz-accent,#d4845a)]">
                {r.margin_idr ? formatIDR(r.margin_idr) : "—"}
              </td>
              <td className="px-3 py-2 text-right font-medium tabular-nums">
                {formatIDR(r.final_price_idr || r.amount_idr)}
              </td>
              <td className="max-w-[200px] truncate px-3 py-2 text-muted-foreground">
                {r.description ?? ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Confirm modal ────────────────────────────────────────────────────────────

function ConfirmModal({
  txn,
  candidate,
  onClose,
  onConfirmed,
}: {
  txn: BankTransaction;
  candidate: MatchCandidate;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const { success, error } = useToast();
  const [busy, setBusy] = useState(false);
  const delta = txn.amount_idr - candidate.invoice_amount_idr;
  const newStatus =
    delta >= -1000 ? "paid" : ("partial" as "paid" | "partial");

  const handleConfirm = async () => {
    setBusy(true);
    try {
      await accountingApi.confirm({
        bank_txn_id: txn.id,
        practice_id: candidate.practice_id,
        invoice_id: candidate.invoice_id,
        amount_applied_idr: txn.amount_idr,
        new_status: newStatus,
        payment_method: "bank_transfer",
        payment_reference: txn.description ?? undefined,
        movement_date: txn.txn_date,
        pph_withheld_idr: candidate.likely_withheld ? -delta : 0,
      });
      success(
        "Payment confirmed",
        `${candidate.client_name} marked ${newStatus}`,
      );
      onConfirmed();
    } catch (err) {
      error("Confirm failed", "Please try again");
      logger.error(
        `accounting confirm failed txn=${txn.id} inv=${candidate.invoice_id}`,
        {},
        err as Error,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-xl">
        <div className="flex items-start justify-between">
          <h3 className="text-lg font-semibold">Confirm payment match</h3>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Transfer</dt>
            <dd className="font-medium tabular-nums">
              {formatIDR(txn.amount_idr)}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Client</dt>
            <dd className="font-medium">{candidate.client_name}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Invoice</dt>
            <dd className="tabular-nums">
              {formatIDR(candidate.invoice_amount_idr)}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Delta</dt>
            <dd
              className={`tabular-nums ${delta < 0 ? "text-amber-600" : "text-emerald-600"}`}
            >
              {delta >= 0 ? "+" : ""}
              {formatIDR(delta)}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">New status</dt>
            <dd className="font-semibold uppercase">{newStatus}</dd>
          </div>
          {candidate.likely_withheld && (
            <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-700">
              Looks net of PPh23 withholding — the delta is recorded as withheld
              tax.
            </p>
          )}
        </dl>

        <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
          {candidate.reasons.map((reason, i) => (
            <li key={i}>• {reason}</li>
          ))}
        </ul>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            Confirm {newStatus}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Reconciliation inbox ─────────────────────────────────────────────────────

function ReconciliationInbox({ onConfirmed }: { onConfirmed: () => void }) {
  const { error } = useToast();
  const [txns, setTxns] = useState<BankTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTxn, setExpandedTxn] = useState<number | null>(null);
  const [candidates, setCandidates] = useState<MatchCandidate[]>([]);
  const [candLoading, setCandLoading] = useState(false);
  const [modal, setModal] = useState<{
    txn: BankTransaction;
    candidate: MatchCandidate;
  } | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const rows = await accountingApi.getBankTransactions({
        reconciledStatus: "unmatched",
      });
      // only incoming (credit) transfers are reconcilable to invoices
      setTxns(rows.filter((t) => t.direction === "credit"));
    } catch (err) {
      error("Failed to load reconciliation inbox", "Please try again");
      logger.error("accounting inbox load failed", {}, err as Error);
    } finally {
      setLoading(false);
    }
  }, [error]);

  useEffect(() => {
    load();
  }, [load]);

  const openCandidates = async (txn: BankTransaction) => {
    if (expandedTxn === txn.id) {
      setExpandedTxn(null);
      return;
    }
    setExpandedTxn(txn.id);
    setCandidates([]);
    setCandLoading(true);
    try {
      const res = await accountingApi.getMatchCandidates(txn.id);
      setCandidates(res.candidates);
    } catch (err) {
      error("Failed to load candidates", "Please try again");
      logger.error(
        `accounting candidates failed txn=${txn.id}`,
        {},
        err as Error,
      );
    } finally {
      setCandLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-10 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading inbox…
      </div>
    );
  }

  if (txns.length === 0) {
    return (
      <div className="rounded-lg border p-10 text-center text-muted-foreground">
        <Inbox className="mx-auto mb-2 h-8 w-8 opacity-50" />
        No unmatched incoming transfers. Inbox zero.
      </div>
    );
  }

  return (
    <>
      <div className="space-y-2">
        {txns.map((txn) => (
          <div key={txn.id} className="rounded-lg border">
            <button
              onClick={() => openCandidates(txn)}
              className="flex w-full items-center justify-between gap-3 p-3 text-left hover:bg-muted/30"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {txn.description ?? "(no memo)"}
                </p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {txn.txn_date}
                </p>
              </div>
              <span className="shrink-0 font-semibold tabular-nums text-emerald-600">
                {formatIDR(txn.amount_idr)}
              </span>
            </button>

            {expandedTxn === txn.id && (
              <div className="border-t bg-muted/20 p-3">
                {candLoading ? (
                  <div className="flex items-center justify-center py-4 text-muted-foreground">
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Ranking
                    candidates…
                  </div>
                ) : candidates.length === 0 ? (
                  <p className="py-2 text-center text-sm text-muted-foreground">
                    No plausible invoice match. Leave unmatched or handle
                    manually.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {candidates.map((c) => (
                      <li
                        key={c.invoice_id}
                        className="flex items-center justify-between gap-3 rounded-md border bg-card p-2"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {c.client_name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatIDR(c.invoice_amount_idr)} ·{" "}
                            {(c.confidence * 100).toFixed(0)}% ·{" "}
                            {c.reasons[0] ?? ""}
                          </p>
                        </div>
                        <Button
                          size="sm"
                          onClick={() => setModal({ txn, candidate: c })}
                        >
                          Match
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {modal && (
        <ConfirmModal
          txn={modal.txn}
          candidate={modal.candidate}
          onClose={() => setModal(null)}
          onConfirmed={() => {
            setModal(null);
            setExpandedTxn(null);
            load();
            onConfirmed();
          }}
        />
      )}
    </>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AccountingPage() {
  const { error } = useToast();
  const [tab, setTab] = useState<Tab>("cashout");
  const [summary, setSummary] = useState<CashbookSummary | null>(null);
  const [cashout, setCashout] = useState<CashoutRow[]>([]);
  const [loading, setLoading] = useState(true);

  const loadCashout = useCallback(async () => {
    try {
      setLoading(true);
      const [s, rows] = await Promise.all([
        accountingApi.getSummary(),
        accountingApi.getCashout({ limit: 200 }),
      ]);
      setSummary(s);
      setCashout(rows);
    } catch (err) {
      error("Failed to load accounting", "Please try again");
      logger.error("accounting page load failed", {}, err as Error);
    } finally {
      setLoading(false);
    }
  }, [error]);

  useEffect(() => {
    loadCashout();
  }, [loadCashout]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet className="h-6 w-6 text-[var(--bz-accent,#d4845a)]" />
          <h1 className="text-2xl font-semibold tracking-tight">Accounting</h1>
        </div>
      </div>

      <SummaryCards summary={summary} />

      <div className="flex gap-2 border-b">
        <button
          onClick={() => setTab("cashout")}
          className={`flex items-center gap-2 px-3 py-2 text-sm font-medium ${
            tab === "cashout"
              ? "border-b-2 border-[var(--bz-accent,#d4845a)] text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <TableProperties className="h-4 w-4" /> Weekly Cashout
        </button>
        <button
          onClick={() => setTab("inbox")}
          className={`flex items-center gap-2 px-3 py-2 text-sm font-medium ${
            tab === "inbox"
              ? "border-b-2 border-[var(--bz-accent,#d4845a)] text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Inbox className="h-4 w-4" /> Reconciliation
        </button>
      </div>

      {tab === "cashout" ? (
        loading ? (
          <div className="flex items-center justify-center p-10 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading cashout…
          </div>
        ) : (
          <CashoutTable rows={cashout} />
        )
      ) : (
        <ReconciliationInbox onConfirmed={loadCashout} />
      )}
    </div>
  );
}
