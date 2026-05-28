# WhatsApp Full Corpus Gold Signals Summary

Generated UTC: `2026-05-26T18:32:19+00:00`
Local signal DB: `full_gold_signals.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or contact names.
- Signal hits reference local file/message IDs and body hashes only.

## Scope

- Reads the full cleartext local SQLite after spicy-conversation quarantine.
- Excludes quarantined files from mining.
- Uses deterministic multilingual patterns; no cloud LLM is called.

## Counts

| Metric                         |  Value |
| ------------------------------ | -----: |
| Usable files                   |    696 |
| Usable messages scanned        | 160530 |
| Signal hits                    |  62309 |
| Messages with at least one hit |  42735 |
| Files with at least one hit    |    605 |

## Signal Groups

| Group                 |  Hits |
| --------------------- | ----: |
| immigration_lifecycle | 24774 |
| tax_payment           | 13420 |
| followup_risk         |  7539 |
| document_ops          |  6509 |
| crm_lead_intake       |  3958 |
| knowledge_mining      |  3581 |
| relationship_memory   |  1443 |
| operational_risk      |  1085 |

## Signal Codes

| Code                     |  Hits |
| ------------------------ | ----: |
| visa_stage               | 23959 |
| payment_or_transfer      | 12396 |
| deadline_or_urgency      |  5620 |
| identity_document        |  4290 |
| pricing_or_quote         |  3789 |
| regulatory_or_kbli       |  3581 |
| followup_waiting         |  1919 |
| life_event_or_memory     |  1443 |
| company_document         |  1362 |
| problem_or_complaint     |  1085 |
| tax_compliance           |  1024 |
| property_document        |   857 |
| appointment_or_biometric |   815 |
| new_lead_or_intake       |   169 |

## Sources

| Source             |  Hits |
| ------------------ | ----: |
| 02_zip-extracted   | 42414 |
| 03_drive-icloud    | 14291 |
| 01_wa-mirror-db    |  5581 |
| CHAT-HISTORY-PILOT |    23 |

## Top Months

| Month   | Hits |
| ------- | ---: |
| 2025-12 | 4346 |
| 2025-06 | 3768 |
| 2026-01 | 3705 |
| 2025-03 | 3552 |
| 2025-04 | 3407 |
| 2025-07 | 3398 |
| 2025-05 | 3339 |
| 2026-05 | 2964 |
| 2025-02 | 2809 |
| 2026-03 | 2736 |
| 2026-04 | 2639 |
| 2024-11 | 2575 |
| 2026-02 | 2508 |
| 2025-01 | 2349 |
| 2025-10 | 2321 |
| 2025-09 | 2086 |
| 2025-08 | 2084 |
| 2024-10 | 2036 |
| 2024-09 | 1854 |
| 2024-12 | 1769 |
| 2024-08 | 1545 |
| 2025-11 | 1363 |
| 2024-07 |  752 |
| 2024-06 |  338 |

## Operational Reading

- The strongest immediate value is CRM/ops retrieval over lead intake, document, payment, visa-stage, and follow-up signals.
- The local DB can drive dashboards, review queues, and local RAG without exposing corpus text.
