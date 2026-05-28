# WhatsApp Allowlist Signal Summary

Generated UTC: `2026-05-26T13:09:01+00:00`
Input raw SQLite artifact: `allowed_messages.local.sqlite`
Local signal SQLite artifact: `allowed_signal_hits.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers.
- This tracked summary contains no raw source paths.
- This tracked summary contains no raw contact names.
- Signal SQLite contains only file IDs, message indexes, timestamps, hashed source tags, and signal codes.

## Scope

- Analyzed only messages parsed from `content_allowlist.local.jsonl`.
- Denylist and holdlist files were not opened.
- Signal detection is deterministic regex matching, not LLM interpretation.

## Counts

| Metric                            | Value |
| --------------------------------- | ----: |
| Messages analyzed                 | 20169 |
| Messages with at least one signal |  8416 |
| Signal hits                       | 12249 |
| Distinct signal codes             |    12 |

## Signal Codes

| Signal               | Hits |
| -------------------- | ---: |
| immigration          | 3174 |
| contains_phone_like  | 2777 |
| identity_document    | 2170 |
| scheduling_followup  |  915 |
| tax_accounting       |  778 |
| bahasa_operational   |  669 |
| company_corporate    |  629 |
| urgency_risk         |  406 |
| money_like           |  319 |
| contains_url         |  205 |
| property_real_estate |  146 |
| contains_email       |   61 |

## Signal Hits By Source Tag

| Source tag     | Hits |
| -------------- | ---: |
| tag-f6302850cc | 4907 |
| tag-f4c6a73c2c | 4107 |
| tag-02a8764847 | 3235 |

## Top Signal Months

| Month   | Hits |
| ------- | ---: |
| 2026-01 | 1174 |
| 2026-03 |  962 |
| 2025-09 |  872 |
| 2026-02 |  757 |
| 2025-04 |  755 |
| 2025-12 |  751 |
| 2025-10 |  749 |
| 2026-04 |  645 |
| 2025-07 |  600 |
| 2025-05 |  573 |
| 2025-06 |  571 |
| 2025-08 |  541 |
| 2026-05 |  538 |
| 2025-11 |  520 |
| 2024-11 |  502 |
| 2025-03 |  401 |
| 2025-02 |  338 |
| 2024-10 |  235 |
| 2025-01 |  201 |
| 2024-07 |  112 |

## Top Co-Occurrences

| Signal A            | Signal B            | Messages |
| ------------------- | ------------------- | -------: |
| contains_phone_like | identity_document   |     1218 |
| identity_document   | immigration         |      542 |
| contains_phone_like | immigration         |      250 |
| company_corporate   | immigration         |      247 |
| immigration         | scheduling_followup |      237 |
| immigration         | tax_accounting      |      229 |
| immigration         | money_like          |      222 |
| immigration         | urgency_risk        |      201 |
| identity_document   | money_like          |      197 |
| identity_document   | tax_accounting      |      159 |
| company_corporate   | identity_document   |      146 |
| bahasa_operational  | immigration         |      129 |
| contains_url        | immigration         |      123 |
| money_like          | tax_accounting      |      108 |
| contains_url        | identity_document   |      103 |
| identity_document   | scheduling_followup |      101 |
| company_corporate   | tax_accounting      |       96 |
| company_corporate   | money_like          |       93 |
| identity_document   | urgency_risk        |       93 |
| scheduling_followup | tax_accounting      |       91 |

## Operational Reading

- High `contains_phone_like` usually means many operational exchanges include IDs, amounts, dates, or phone-like digit runs.
- `tax_accounting`, `identity_document`, `immigration`, and `company_corporate` are the first safe candidates for local-only structured extraction.
- Treat these as routing signals only; do not make client or legal claims from regex counts alone.
