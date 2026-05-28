# WhatsApp Allowlist Candidate Extraction Summary

Generated UTC: `2026-05-26T13:50:57+00:00`
Input raw SQLite artifact: `allowed_messages.local.sqlite`
Local candidate SQLite artifact: `allowed_candidates.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers.
- This tracked summary contains no raw source paths.
- This tracked summary contains no raw contact names.
- Candidate SQLite stores hashed body/value references only, not raw extracted values.

## Scope

- Extracted only from messages parsed out of `content_allowlist.local.jsonl`.
- Denylist and holdlist files were not opened.
- Extraction is deterministic regex and hashing, not LLM interpretation.

## Counts

| Metric                           | Value |
| -------------------------------- | ----: |
| Messages scanned                 | 20169 |
| Messages with candidates         |  7407 |
| Candidate rows                   | 18925 |
| Distinct hashed extracted values |  4979 |

## Candidate Categories

| Category           | Rows |
| ------------------ | ---: |
| contact_reference  | 7610 |
| date_reference     | 3270 |
| visa_case          | 3166 |
| identity_document  | 2174 |
| tax_payment        |  778 |
| company_case       |  629 |
| money_reference    |  541 |
| urgency_case       |  406 |
| external_reference |  205 |
| property_case      |  146 |

## Evidence Codes

| Evidence           | Rows |
| ------------------ | ---: |
| category_keyword   | 7295 |
| phone_like_hash    | 4711 |
| date_like_hash     | 3270 |
| phone_like_present | 2777 |
| money_like_hash    |  541 |
| url_present        |  205 |
| email_hash         |   61 |
| email_present      |   61 |
| passport_like_hash |    4 |

## Candidate Rows By Source Tag

| Source tag     | Rows |
| -------------- | ---: |
| tag-f6302850cc | 8092 |
| tag-f4c6a73c2c | 6603 |
| tag-02a8764847 | 4230 |

## Top Candidate Months

| Month   | Rows |
| ------- | ---: |
| 2026-01 | 1980 |
| 2026-03 | 1474 |
| 2025-04 | 1289 |
| 2025-09 | 1227 |
| 2025-10 | 1076 |
| 2025-12 | 1070 |
| 2026-02 | 1063 |
| 2026-04 |  991 |
| 2025-07 |  961 |
| 2025-06 |  887 |
| 2025-05 |  877 |
| 2025-08 |  859 |
| 2025-11 |  834 |
| 2024-11 |  809 |
| 2026-05 |  747 |
| 2025-03 |  724 |
| 2025-02 |  416 |
| 2024-10 |  406 |
| 2025-01 |  377 |
| 2024-09 |  167 |

## Next Safe Step

Use the ignored candidate SQLite to build local review queues by `category_code` and `evidence_code`. Do not publish raw values; resolve hashes only inside local owner-review tools.
