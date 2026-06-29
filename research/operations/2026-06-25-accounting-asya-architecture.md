---
date: 2026-06-25
domain: operations
client_case: false
status: v2 — POST 3-LLM PANEL (unanimous GO-WITH-CHANGES) — awaiting Zero final GO
author: Claude Opus 4.8 (1M) — M5 session
panel: Gemini 3.1 Pro + DeepSeek V4 Pro + Codex GPT-5.5 (all 3 GO-WITH-CHANGES, convergent)
sources:
  - internal codebase recon (4 Explore agents, path:line verified on disk)
  - reuse-first external research (4 agents, licenses verified GitHub/PyPI 2026-06-25)
  - 3-LLM adversarial panel review
---

# Accounting for Asya — Architecture v2 (post-panel)

> **The panel's one-line correction (Codex, echoed by all 3):** this is not a mini accounting system —
> it is a **cash-control workflow for ONE accountant.** Build that, nothing more.
>
> **One-line design:** A thin cash-control layer inside the repo that reuses the invoice/pricing/payroll
> machinery already built, adds reconciliation + a single flat money-log + client-advance tracking, and
> gives Asya a Google Sheets export (her real tool — Bali Zero has no Excel) on demand. IDR-native.

---

## 0. What changed v1 → v2 (the panel earned its keep)

| v1 (rejected) | v2 (panel consensus) | Why |
|---|---|---|
| Double-entry ledger (`accounts`/`journal_entries`/`journal_lines` + pyluca + trigger) | **ONE flat `money_movements` table** (single-entry, cash-basis) | 3/3: "accounting cosplay" for 1 person; trigger errors Asya can't debug; schema gravity |
| Subset-sum invoice matching | **Exact amount/date + manual multi-select + rapidfuzz hint** | 3/3: PPh23 + bank fees + partial pay → subset-sum "generates plausible lies" |
| Auto push DB→Google Sheets (wipe-rewrite) | **On-demand "Export to Google Sheets" button** | 3/3: destructive, drifts, "which is truth" fights |
| Cash PNBP = expense | **`cash_advances` table (client receivable)** | 3/3 (Codex STRONGLY): treating as expense destroys margins + double-counts |
| No tax fields | **PPN/PPh first-class on movements + invoices** | 3/3: else Asya keeps a parallel tax sheet → defeats the system |
| P1 = expenses | **P1 = reconciliation** | 3/3: reconciliation is the daily pain; expenses can wait |
| (missing) | **Explicit payment state machine** | Codex: don't mutate `practices.payment_status` bluntly |
| (missing) | **Immutable audit trail per confirm** | Codex: source row + IDs + user + ts + before/after + reversal path |
| PDF + CSV in v1 | **CSV first; PDF deferred to later phase** | Codex: PDF = "brittle false precision", burns time |
| `pyluca` dependency | **dropped** | no ledger → no need |

**Net pip additions (v2, slimmer):** `rapidfuzz pandas openpyxl gspread gspread-dataframe tenacity`.
(`pdfplumber camelot pikepdf pyluca` deferred/dropped.) All MIT/Apache. No paid API. No PII to cloud.

---

## 1. What already exists — REUSE, don't rebuild (verified on disk)

| Organ | Path (verified) |
|---|---|
| Invoice automation (PDF→email→Drive→DB), Asya already emailed per invoice | `services/invoicing/invoice_service.py`, `invoice_generator.py` |
| `invoices` table (thin) + UNIQUE(practice_id) | `db/migrations_v2/125_invoices_unique_practice.sql` |
| Pricing SSOT | `services/pricing/pricing_service.py` + `data/bali_zero_official_prices_2026.json` |
| Practice payment fields (`quoted_price, actual_price, currency, payment_status, paid_amount`) | `app/modules/crm/models.py:102-174` |
| HR/Payroll (9 tables) | `migrations/migration_068_hr_payroll.py` |
| **PPh21 + BPJS calculation already implemented** (TER method, 2025 rates) | `app/utils/hr_utils.py` — REUSE for any payroll-tax math |
| Partner commission ledger (append-only) | `migrations/migration_119_partners.py` |
| Asya RBAC = CRM admin | `app/utils/crm_utils.py:17-24` |
| Accounting dashboard widget | `mouth/.../role-widgets/AccountingRoleWidget.tsx` |
| Auth (Google OAuth→JWT `.balizero.com`) — Asya logs in from Windows Chrome | `app/dependencies.py` `get_current_user` |
| Google Drive integration (token table + app) | `google_drive_tokens`, `apps/drive/` |

**The gap (verified):** today Asya hand-PATCHes `payment_status` then hand-moves `sending_invoice→on_process`.
No reconciliation, no expense/movement log, no client-advance tracking.

---

## 2. Data model v2 (additive — migration 232, sequence verified at 231)

### 2.1 `bank_transactions` (the import landing zone — CSV first)
```
bank_statements(id, bank_code, account_label, uploaded_by, uploaded_at,
  source_filename, source_format='csv', period_start, period_end,
  opening_balance_idr, closing_balance_idr, balance_check_ok BOOLEAN)
bank_transactions(id, statement_id FK, txn_date, description, amount_idr,
  direction,                 -- 'credit'(in) | 'debit'(out); normalizes BCA flag + Mandiri 2-col
  running_balance_idr,
  reconciled_status,         -- 'unmatched' | 'matched' | 'manual' | 'ignored'   (4-state, nothing vanishes)
  bank_account_id,           -- which account it landed in (Codex: keep audit trail)
  raw_row JSONB)             -- original line verbatim, for audit
```

### 2.2 `money_movements` (THE single flat money-log — replaces double-entry)
```
money_movements(
  id, movement_date,
  direction,                 -- 'in' | 'out'
  type,                      -- invoice_payment | expense | payroll | commission | bank_fee | cash_advance | advance_recovery | tax_payment | refund | manual
  amount_idr BIGINT,
  -- multi-currency LIGHT, but FX explicit (Codex: else decorative)
  original_currency DEFAULT 'IDR', original_amount NUMERIC NULL, fx_rate NUMERIC NULL, fx_date DATE NULL,
  -- tax reality (all 3: first-class, not afterthought)
  ppn_amount_idr BIGINT DEFAULT 0,          -- VAT 11% if applicable
  pph_withheld_idr BIGINT DEFAULT 0,        -- PPh 23/21/26 withheld
  bank_fee_idr BIGINT DEFAULT 0,            -- fee deducted by bank
  -- typed links (Codex: typed links, not a GL)
  linked_practice_id FK NULL, linked_invoice_id FK NULL,
  linked_bank_txn_id FK NULL, linked_advance_id FK NULL,
  category,                  -- for expenses: government_fees|it_saas|office_ops|professional_fees|other
  description, counterparty, payment_method,  -- cash|bank_transfer|card
  receipt_drive_file_id NULL,   -- reuse existing Drive
  recorded_by, recorded_at,
  reversed_by_id FK NULL)    -- correct-by-reversal, never hard-edit money rows
```
Cash-basis P&L = `SUM(in where type=invoice_payment) − SUM(out where type in expense/payroll/commission/tax/bank_fee)`.
One table, one query. Auditable. Trivially exportable to a Sheet.

### 2.3 `cash_advances` (the domain correction — PNBP cash is a RECEIVABLE, not expense)
```
cash_advances(
  id, practice_id FK, client_id FK,
  purpose,                   -- 'pnbp_visa' | 'izin_kerja_usd' | 'other_govt_fee'
  amount_idr BIGINT, original_currency, original_amount, fx_rate, fx_date,
  paid_out_date,             -- when Asya/runner paid the govt office
  status,                    -- 'pending' (client owes it back) | 'recovered' (client paid invoice incl. it) | 'written_off'
  recovered_movement_id FK NULL,  -- the invoice_payment that settled it
  paid_out_movement_id FK NULL,   -- the cash-out movement
  notes, recorded_by, recorded_at)
```
Flow: pay PNBP cash → `cash_advances(status=pending)` + a `money_movements(type=cash_advance, out)`.
Client pays invoice (which includes PNBP reimbursement) → advance flips to `recovered`. Margin stays honest.

### 2.4 Extend `invoices` (thin → reconciliation+tax-ready)
```
ALTER TABLE invoices ADD:
  paid_date TIMESTAMPTZ, payment_method VARCHAR(30), payment_reference VARCHAR(120),
  paid_amount_idr BIGINT,
  ppn_amount_idr BIGINT DEFAULT 0,      -- if invoiced with VAT
  pph_expected_idr BIGINT DEFAULT 0     -- expected B2B withholding (so reconciliation knows transfer<gross)
```

### 2.5 Payment state machine (Codex: explicit, don't mutate bluntly)
```
practices.payment_status enriched path:
  unpaid → partial → paid
                  ↘ withheld_settled (paid net of PPh, delta booked as pph_withheld)
  paid → refunded (reversal)
  any → written_off
```
The reconciliation service is the ONLY writer of payment_status, goes through the existing PATCH/service
path (never side-channel SQL), updates `paid_amount` atomically, and emits the same cache invalidation
already in use (`zantara:crm_practices_stats:*` + `crm_clients_stats:*`). Every transition logged.

### 2.6 `reconciliation_log` (Codex: immutable audit per confirm)
```
reconciliation_log(id, bank_txn_id FK, invoice_ids JSONB, practice_id FK,
  confirmed_by, confirmed_at, status_before, status_after,
  amount_applied_idr, pph_delta_idr, bank_fee_delta_idr,
  reversal_of_id FK NULL)   -- un-reconcile creates a new reversal row, never deletes
```
Immutable. Un-reconcile = append a reversal (Gemini's safety valve: check downstream effects before revert).

---

## 3. The reconciliation flow v2 (the daily Asya ritual)

```
1. Asya exports CSV from BCA/Mandiri/CIMB → uploads in app          (CSV only in v1; PDF later)
2. Per-bank parser → bank_transactions, direction normalized, balance-check verified
   └─ ALL parsing LOCAL — client payer names never leave the box (Law 2)
3. For each CREDIT (incoming), the matcher proposes hints (NO auto-decision on ambiguity):
     a. exact amount (± rounding tolerance) within a date window  → high-confidence hint
     b. amount net of expected PPh23 (gross − 2%)                 → "likely withheld" hint
     c. rapidfuzz on payer-name vs client-name                     → name hint
     d. multi-invoice: Asya MANUALLY multi-selects invoices; sum must equal transfer (deterministic, no subset-sum)
4. Asya reviews: "Rp X on date D ↔ Practice #N (client C) [confidence]" → selects + confirms
   On a withheld/fee/partial case she explicitly tags the delta (PPh23 / bank_fee / partial)
5. On confirm (single writer, atomic, audited):
     - practices.payment_status via existing PATCH path (state machine) + paid_amount
     - invoices.paid_date/method/reference/paid_amount_idr
     - money_movements(type=invoice_payment, in, +ppn/pph/fee deltas)
     - if it settles a cash_advance → flip advance to recovered
     - reconciliation_log row (immutable evidence)
     - invalidate_cache(existing keys)
     - OPTIONAL auto-transition sending_invoice→on_process  [OPEN Q1 — Zero decides]
6. Unmatched credits → stay 'unmatched', surfaced loudly (superscar #2: never swallow)
   Debits → become money_movements(out) categorized as expenses
```

---

## 4. The app: one feature, two faces (Zero's "indissoluble" principle + "no Excel")

### Face A — In-system (lives in `apps/mouth`, existing Next.js workspace)
- Route group `(workspace)/accounting/`: **Reconciliation inbox** (the hero), Movements log, Cash advances, Monthly P&L
- Backend: router `app/routers/accounting.py` + `services/accounting/`
- Reuses existing auth, RBAC (accounting role), cache pattern, Drive
- This is the SOURCE OF TRUTH, in-repo, versioned, tested. A clean, dense, sortable/filterable data grid
  (the "spreadsheet feel" — but it's OUR grid reading OUR DB, not Excel which Bali Zero doesn't have).

### Face B — Google Sheets, on-demand (Asya's REAL tool — no Excel at Bali Zero)
- **"Export to Google Sheets" button** → creates/refreshes a real Google Sheet on demand (gspread + service account)
- This IS the google-native answer: Asya gets a live Google Sheet she owns, when she wants it (pivot, share, print),
  WITHOUT a fragile cron that overwrites her edits.
- **Service-account gotcha (verified):** SA has no Drive quota → Zero (human) creates the target Sheet once
  and shares it Editor with the SA email; backend writes into the granted Sheet. Or export into a Shared Drive.
  Key from secret store, `chmod 0600`. ~2 API calls, far under 60/min/user limit; `tenacity` backoff.
- Receipts/statements → existing Google Drive integration (no new wrapper).
- NO continuous push, NO Apps Script. (All 3 panelists.)

> Net "google-native": Asya lives in the in-app grid for the daily ritual, and one click spins a real
> Google Sheet whenever she wants to work in Google. Code stays 100% in repo. No Excel needed anywhere.

---

## 5. Build phases v2 (reconciliation-first, CSV-first, each shippable)

| Phase | Scope | Why |
|---|---|---|
| **P0** | Migration 232 (all §2 tables) + `accounting.py` router skeleton + RBAC + payment state machine | foundation |
| **P1** | **Reconciliation: CSV upload + BCA parser + matcher (exact/PPh-net/fuzzy + manual multi-select) + confirm→unlock practice + reconciliation_log** | THE daily pain; biggest ROI |
| **P2** | `money_movements` log + expense entry (categorized, Drive receipt) + `cash_advances` (PNBP) | cash-control completeness |
| **P3** | Monthly cash-basis P&L + "Export to Google Sheets" button | reporting + google-native |
| **P4** | More bank parsers (Mandiri XLSX, CIMB) + PDF parsing (pdfplumber) + payroll→movements link | breadth, once spine proven |
| **P5** | Auto-categorize (smart_importer), receipt OCR (local Ollama) | nice-to-have |

Payroll + PPh21/BPJS already exist (`hr_utils.py`) — P4 *links* them into `money_movements`, doesn't rebuild.

---

## 6. Superscar guardrails

- **#1 HOME-fork**: app lives in `apps/`, deploys from repo. Google Sheet is an export, never the source.
- **#2 esiste≠armato**: unmatched transactions surfaced loudly; balance-check fails visibly.
- **#4 secret-clear**: SA key in secret store, `chmod 0600`, never in repo.
- **#9 schema-drift**: reconciliation is the SINGLE writer of `payment_status`, via existing PATCH path + same cache keys (Codex's #1 prod risk).
- **Law 2 (PII)**: all bank parsing/matching LOCAL; cloud LLMs (incl. this panel) saw only architecture, never a real statement; receipt OCR = local Ollama.
- **FX honesty**: every non-IDR amount stores `(original_amount, fx_rate, fx_date)` — never collapse to IDR-only.
- **Auditability**: every confirm = immutable `reconciliation_log` row; corrections by reversal, never hard-delete.

---

## 7. Open questions for Zero (the only real decisions left)

1. **Auto-transition?** After payment confirmed: auto-move `sending_invoice→on_process`, or keep a 2nd explicit click for Asya? (speed vs safety)
2. **Which bank first** for the P1 CSV parser — BCA? (research says BCA CSV is most common but messiest; confirm the company's main account.)
3. **PPN: does Bali Zero invoice with 11% VAT** on services, or not? (Determines whether PPN fields are load-bearing now or dormant.)
4. **Who creates the Google Sheet** (the one-time SA-share step) — Zero, once?
5. **Chart of categories**: the expense/movement `type` + `category` enums above — good enough, or add/rename any?
