/**
 * Workspace Accounting API — cash-control endpoints for Asya (the accountant).
 *
 * Mirrors the backend accounting router (apps/backend-rag/backend/app/routers/
 * accounting.py). RBAC is enforced server-side (is_crm_admin → 403 otherwise);
 * Asya@balizero.com is in CRM_EXTRA_ADMIN_EMAILS. Money is IDR (integer rupiah).
 *
 * Endpoints return FLAT shapes (list[dict] / dict), NOT wrapped — the types here
 * are derived from cashout_service.py + reconcile_service.py response columns.
 */

import { api } from "@/lib/api";

// ── Weekly cashout row (mirrors Asya's "Weekly Cashout" sheet) ───────────────
export interface CashoutRow {
  id: number;
  movement_date: string | null;
  week_label: string | null;
  direction: "in" | "out";
  type: string;
  amount_idr: number;
  pnbp_idr: number;
  urgent_idr: number;
  rptka_imta_idr: number;
  margin_idr: number;
  final_price_idr: number;
  original_currency: string | null;
  original_amount: number | null;
  fx_rate: number | null;
  fx_date: string | null;
  pph_withheld_idr: number;
  bank_fee_idr: number;
  linked_practice_id: number | null;
  linked_invoice_id: number | null;
  category: string | null;
  description: string | null;
  counterparty: string | null;
  payment_method: string | null;
  recorded_by: string | null;
  recorded_at: string | null;
  reversed_by_id: number | null;
  client_name: string | null;
}

export type ReconciledStatus = "unmatched" | "matched" | "manual" | "ignored";

export interface BankTransaction {
  id: number;
  statement_id: number | null;
  txn_date: string;
  description: string | null;
  amount_idr: number;
  direction: "credit" | "debit";
  running_balance_idr: number | null;
  bank_account_id: number | null;
  reconciled_status: ReconciledStatus;
  matched_practice_id: number | null;
  matched_invoice_id: number | null;
  created_at: string | null;
}

export interface CashbookSummary {
  income_idr: number;
  outgoing_idr: number;
  net_idr: number;
  margin_total_idr: number;
  pnbp_total_idr: number;
  row_count: number;
  by_type: Array<{
    type: string;
    direction: "in" | "out";
    total_idr: number;
    n: number;
  }>;
}

export interface MatchCandidate {
  invoice_id: number;
  practice_id: number;
  client_name: string;
  invoice_amount_idr: number;
  confidence: number; // 0.0 – 1.0
  reasons: string[];
  amount_delta_idr: number;
  likely_withheld: boolean;
}

export interface MatchCandidatesResponse {
  txn_id: number;
  transfer_amount_idr: number;
  candidates: MatchCandidate[];
}

export interface ConfirmRequest {
  bank_txn_id?: number | null;
  practice_id: number;
  invoice_id?: number | null;
  amount_applied_idr: number;
  new_status?: "unpaid" | "partial" | "paid";
  payment_method?: string;
  payment_reference?: string | null;
  pph_withheld_idr?: number;
  bank_fee_idr?: number;
  pnbp_idr?: number;
  urgent_idr?: number;
  rptka_imta_idr?: number;
  margin_idr?: number;
  movement_date?: string | null;
}

export interface ConfirmResponse {
  practice_id: number;
  invoice_id: number | null;
  cashout_id: number;
  reconciliation_log_id: number;
  status_before: string | null;
  status_after: string;
}

export interface ExportSheetResponse {
  spreadsheet_id: string;
  rows_exported: number;
  updated_cells: number;
  range: string;
}

export interface ImportCashoutResponse {
  source_filename: string;
  imported: number;
  weeks: string[];
  replaced: number;
}

const qs = (params: Record<string, string | number | undefined>): string => {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
};

export const accountingApi = {
  /** Weekly cashout rows (Asya's sheet), newest first. */
  async getCashout(opts?: {
    weekLabel?: string;
    type?: string;
    limit?: number;
  }): Promise<CashoutRow[]> {
    return api.get<CashoutRow[]>(
      `/api/crm/accounting/cashout${qs({
        week_label: opts?.weekLabel,
        type: opts?.type,
        limit: opts?.limit,
      })}`,
    );
  },

  /** Parsed bank-statement transactions, newest first; the reconciliation inbox. */
  async getBankTransactions(opts?: {
    reconciledStatus?: ReconciledStatus;
    limit?: number;
  }): Promise<BankTransaction[]> {
    return api.get<BankTransaction[]>(
      `/api/crm/accounting/bank-transactions${qs({
        reconciled_status: opts?.reconciledStatus,
        limit: opts?.limit,
      })}`,
    );
  },

  /** Cash-basis P&L summary over the cashout log. */
  async getSummary(opts?: {
    periodStart?: string;
    periodEnd?: string;
  }): Promise<CashbookSummary> {
    return api.get<CashbookSummary>(
      `/api/crm/accounting/summary${qs({
        period_start: opts?.periodStart,
        period_end: opts?.periodEnd,
      })}`,
    );
  },

  /** Candidate invoices for one incoming (credit) transfer. Never auto-confirms. */
  async getMatchCandidates(txnId: number): Promise<MatchCandidatesResponse> {
    return api.get<MatchCandidatesResponse>(
      `/api/crm/accounting/match-candidates/${txnId}`,
    );
  },

  /** Confirm a payment match. Single writer of payment_status (superscar #9). */
  async confirm(payload: ConfirmRequest): Promise<ConfirmResponse> {
    return api.post<ConfirmResponse>("/api/crm/accounting/confirm", payload);
  },

  /**
   * On-demand push of the weekly cashout to Zero's Google Sheet (NOT auto-sync).
   * The sheet is pre-created + shared with the service account by Zero; the
   * backend writes into it. 503 if ACCOUNTING_EXPORT_SHEET_ID is not configured.
   */
  async exportSheet(weekLabel?: string): Promise<ExportSheetResponse> {
    return api.post<ExportSheetResponse>(
      `/api/crm/accounting/export-sheet${qs({ week_label: weekLabel })}`,
    );
  },

  /**
   * Import Asya's weekly cashout worksheet PDF (GABUNGAN) into the cashout log.
   * Multipart upload — fetch sets the multipart boundary; we only attach CSRF +
   * Authorization and send httpOnly cookies. Idempotent on the backend
   * (re-uploading a file replaces that week's prior import rows). Imported rows
   * land as type='cashout_worksheet' (a draft, excluded from the cash totals).
   * 422 if the PDF carries no "NEW CASHOUT" title / no client rows.
   */
  async importCashout(file: File): Promise<ImportCashoutResponse> {
    const form = new FormData();
    form.append("file", file);

    const headers: Record<string, string> = {};
    const csrf = api.getCsrfToken();
    if (csrf) headers["X-CSRF-Token"] = csrf;
    const token = api.getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const resp = await fetch(
      `${api.getBaseUrl()}/api/crm/accounting/import-cashout`,
      { method: "POST", headers, body: form, credentials: "include" },
    );

    if (!resp.ok) {
      let detail = resp.statusText;
      try {
        const body = await resp.json();
        if (body?.detail) detail = String(body.detail);
      } catch {
        /* non-JSON error body */
      }
      throw new Error(detail);
    }
    return resp.json() as Promise<ImportCashoutResponse>;
  },
};
