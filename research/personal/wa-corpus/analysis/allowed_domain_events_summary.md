# WhatsApp Domain Event Index Summary

Generated UTC: `2026-05-26T14:15:23+00:00`
Local event SQLite artifact: `allowed_domain_events.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or raw extracted values.
- The ignored local SQLite stores normalized event codes plus local IDs and hashes only.
- This builder reads only derived extractor DBs, not the raw parsed-message DB.

## Counts

| Metric                         | Value |
| ------------------------------ | ----: |
| Domain events                  | 53750 |
| Messages with any domain event | 12130 |
| Files with any domain event    |    31 |
| Input domains                  |     4 |

## Input Event Counts

| Domain                | Input events |
| --------------------- | -----------: |
| document_requirement  |        14489 |
| followup_risk         |        14936 |
| immigration_lifecycle |        21909 |
| tax_payment           |         2416 |

## Domain Totals

| Domain                | Events | Messages | Files |
| --------------------- | -----: | -------: | ----: |
| immigration_lifecycle |  21909 |     7335 |    31 |
| followup_risk         |  14936 |     8948 |    31 |
| document_requirement  |  14489 |     6037 |    31 |
| tax_payment           |   2416 |     1393 |    31 |

## Top Event Codes

| Domain                | Event code                 | Events | Messages | Files |
| --------------------- | -------------------------- | -----: | -------: | ----: |
| immigration_lifecycle | application_submission     |   8791 |     3958 |    31 |
| document_requirement  | visa_immigration_document  |   6536 |     3370 |    31 |
| immigration_lifecycle | identity_passport          |   6536 |     2192 |    31 |
| followup_risk         | repeated_request           |   6031 |     5118 |    31 |
| followup_risk         | deadline_followup          |   5929 |     2741 |    31 |
| document_requirement  | passport_identity_document |   2922 |     2172 |    31 |
| immigration_lifecycle | sponsor_company            |   1926 |      668 |    30 |
| document_requirement  | photo_biometric            |   1692 |     1692 |    31 |
| followup_risk         | risk_or_problem            |   1649 |      519 |    31 |
| immigration_lifecycle | lead_intake                |   1577 |     1577 |    30 |
| document_requirement  | payment_proof              |   1356 |      585 |    31 |
| tax_payment           | invoice_payment_proof      |   1334 |      909 |    31 |
| immigration_lifecycle | problem_escalation         |   1226 |      521 |    31 |
| followup_risk         | waiting_or_unanswered      |   1168 |      438 |    31 |
| immigration_lifecycle | extension_renewal_expiry   |    969 |      969 |    31 |
| document_requirement  | tax_document               |    861 |      813 |    31 |
| document_requirement  | company_document           |    818 |      630 |    30 |
| tax_payment           | currency_amount            |    542 |      305 |    30 |
| immigration_lifecycle | approval_issuance          |    511 |      511 |    31 |
| immigration_lifecycle | appointment_biometric      |    373 |      373 |    31 |
| document_requirement  | property_document          |    235 |      229 |    26 |
| tax_payment           | tax_accounting             |    189 |      189 |    21 |
| followup_risk         | followup_or_reminder       |    159 |      132 |    28 |
| tax_payment           | deadline_penalty           |    144 |      140 |    30 |
| tax_payment           | payroll_bpjs               |    118 |      118 |    19 |

## Top Month x Domain Buckets

| Month   | Domain                | Events | Messages |
| ------- | --------------------- | -----: | -------: |
| 2026-01 | immigration_lifecycle |   2075 |      662 |
| 2026-03 | immigration_lifecycle |   1792 |      577 |
| 2025-09 | immigration_lifecycle |   1718 |      574 |
| 2026-01 | document_requirement  |   1457 |      557 |
| 2025-10 | immigration_lifecycle |   1399 |      495 |
| 2026-01 | followup_risk         |   1374 |      771 |
| 2026-02 | immigration_lifecycle |   1296 |      432 |
| 2025-12 | immigration_lifecycle |   1254 |      404 |
| 2025-04 | immigration_lifecycle |   1246 |      484 |
| 2025-07 | immigration_lifecycle |   1209 |      392 |
| 2025-09 | document_requirement  |   1177 |      483 |
| 2026-03 | followup_risk         |   1165 |      679 |
| 2026-03 | document_requirement  |   1131 |      469 |
| 2025-04 | followup_risk         |   1114 |      692 |
| 2025-08 | immigration_lifecycle |   1075 |      367 |
| 2025-06 | immigration_lifecycle |   1059 |      362 |
| 2025-05 | immigration_lifecycle |   1028 |      335 |
| 2025-09 | followup_risk         |    996 |      624 |
| 2025-10 | document_requirement  |    994 |      419 |
| 2026-02 | followup_risk         |    984 |      597 |
| 2026-04 | immigration_lifecycle |    967 |      354 |
| 2026-05 | immigration_lifecycle |    937 |      311 |
| 2025-10 | followup_risk         |    913 |      572 |
| 2025-11 | immigration_lifecycle |    880 |      308 |
| 2025-04 | document_requirement  |    870 |      386 |

## Domain Co-Occurrence

| Domain A              | Domain B              | Messages | Files |
| --------------------- | --------------------- | -------: | ----: |
| document_requirement  | immigration_lifecycle |     5398 |    31 |
| followup_risk         | immigration_lifecycle |     4578 |    31 |
| document_requirement  | followup_risk         |     3906 |    31 |
| document_requirement  | tax_payment           |     1140 |    31 |
| followup_risk         | tax_payment           |      917 |    31 |
| immigration_lifecycle | tax_payment           |      783 |    31 |

## Next Safe Step

Use `allowed_domain_events.local.sqlite` as the input for local case-window stitching and document/lifecycle gap analysis. Do not resolve local IDs outside owner-review tools.
