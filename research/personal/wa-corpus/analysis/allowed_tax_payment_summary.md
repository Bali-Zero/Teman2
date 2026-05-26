# Allowed Tax/Payment Aggregate Summary

- Generated UTC: `2026-05-26T14:12:12+00:00`
- Input messages DB: `allowed_messages.local.sqlite`
- Input candidates DB: `allowed_candidates.local.sqlite`
- Input signal DB: `allowed_signal_hits.local.sqlite`
- Local tax/payment SQLite artifact: `allowed_tax_payment.local.sqlite`
- Privacy boundary: tracked markdown is aggregate counts only; the ignored local SQLite stores body/value hashes, not raw values.

## Counts

| Metric                            | Value |
| --------------------------------- | ----- |
| Messages scanned                  | 20169 |
| Messages with tax/payment signals | 1393  |
| Tax/payment hit rows              | 2416  |
| Distinct hashed local values      | 244   |
| Optional support DBs read         | 2     |

## Categories

| Category                 | Hit rows | Messages |
| ------------------------ | -------- | -------- |
| invoice_payment_proof    | 1334     | 909      |
| currency_amount          | 542      | 305      |
| tax_accounting           | 189      | 189      |
| deadline_penalty         | 144      | 140      |
| payroll_bpjs             | 118      | 118      |
| nib_company_tax_docs     | 64       | 64       |
| monthly_annual_reporting | 25       | 25       |

## Evidence Codes

| Evidence                 | Hit rows | Messages |
| ------------------------ | -------- | -------- |
| invoice_payment_keyword  | 873      | 873      |
| money_like_hash          | 542      | 305      |
| reference_hash           | 407      | 326      |
| tax_accounting_keyword   | 189      | 189      |
| payroll_bpjs_keyword     | 118      | 118      |
| penalty_keyword          | 86       | 86       |
| company_doc_tax_context  | 64       | 64       |
| deadline_keyword         | 56       | 56       |
| payment_proof_keyword    | 54       | 54       |
| reporting_period_keyword | 25       | 25       |
| date_like_hash           | 2        | 1        |

## Month Counts

| Month   | Hit rows | Messages |
| ------- | -------- | -------- |
| 2026-01 | 282      | 132      |
| 2025-04 | 190      | 120      |
| 2025-10 | 176      | 107      |
| 2026-02 | 170      | 101      |
| 2025-09 | 163      | 98       |
| 2026-05 | 147      | 87       |
| 2026-03 | 143      | 81       |
| 2025-12 | 134      | 74       |
| 2026-04 | 119      | 84       |
| 2025-08 | 113      | 58       |
| 2025-07 | 110      | 55       |
| 2025-02 | 98       | 51       |
| 2025-03 | 90       | 55       |
| 2024-11 | 88       | 48       |
| 2025-06 | 82       | 50       |
| 2025-05 | 67       | 47       |
| 2025-11 | 65       | 43       |
| 2024-10 | 45       | 21       |
| 2025-01 | 42       | 22       |
| 2024-12 | 23       | 19       |
| 2024-09 | 17       | 13       |
| 2023-12 | 15       | 6        |
| 2024-07 | 13       | 8        |
| 2024-06 | 7        | 4        |
| 2023-10 | 5        | 1        |

## Category x Month

| Category              | Month   | Hit rows | Messages |
| --------------------- | ------- | -------- | -------- |
| invoice_payment_proof | 2026-01 | 143      | 93       |
| invoice_payment_proof | 2025-04 | 119      | 84       |
| invoice_payment_proof | 2025-10 | 118      | 83       |
| currency_amount       | 2026-01 | 97       | 46       |
| invoice_payment_proof | 2026-02 | 94       | 64       |
| invoice_payment_proof | 2026-05 | 91       | 66       |
| invoice_payment_proof | 2025-09 | 88       | 61       |
| invoice_payment_proof | 2025-12 | 71       | 40       |
| invoice_payment_proof | 2025-08 | 67       | 47       |
| invoice_payment_proof | 2026-03 | 67       | 41       |
| invoice_payment_proof | 2026-04 | 65       | 45       |
| invoice_payment_proof | 2025-06 | 51       | 37       |
| invoice_payment_proof | 2025-07 | 51       | 39       |
| currency_amount       | 2025-07 | 50       | 20       |
| currency_amount       | 2026-03 | 47       | 32       |
| invoice_payment_proof | 2024-11 | 44       | 30       |
| currency_amount       | 2025-09 | 41       | 28       |
| invoice_payment_proof | 2025-11 | 41       | 26       |
| invoice_payment_proof | 2025-03 | 40       | 31       |
| invoice_payment_proof | 2025-05 | 38       | 30       |
| tax_accounting        | 2025-02 | 36       | 36       |
| invoice_payment_proof | 2025-01 | 34       | 19       |
| currency_amount       | 2025-10 | 31       | 22       |
| currency_amount       | 2026-02 | 31       | 17       |
| invoice_payment_proof | 2025-02 | 30       | 23       |

## Input Support Counts

| Support source     | Code                | Rows | Messages |
| ------------------ | ------------------- | ---- | -------- |
| candidate_category | date_reference      | 3270 | 1710     |
| candidate_evidence | date_like_hash      | 3270 | 1710     |
| candidate_evidence | category_keyword    | 1407 | 1311     |
| signal_code        | scheduling_followup | 915  | 915      |
| candidate_category | tax_payment         | 778  | 778      |
| signal_code        | tax_accounting      | 778  | 778      |
| candidate_category | company_case        | 629  | 629      |
| signal_code        | company_corporate   | 629  | 629      |
| candidate_category | money_reference     | 541  | 319      |
| candidate_evidence | money_like_hash     | 541  | 319      |
| signal_code        | money_like          | 319  | 319      |

## Caveats

- Deterministic regex extraction only; counts are routing signals, not legal conclusions.
- `nib_company_tax_docs` requires company-document language plus explicit tax/reporting context.
- Amounts, dates, invoice numbers, payment references, message text, contacts, and paths are not present in this tracked summary.
