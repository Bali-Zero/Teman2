# WhatsApp Allowlist Parse Summary

Generated UTC: `2026-05-26T13:06:02+00:00`
Input allowlist artifact: `content_allowlist.local.jsonl`
Local raw SQLite artifact: `allowed_messages.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers.
- This tracked summary contains no raw source paths.
- This tracked summary contains no raw contact names.
- Raw parsed text and raw sender labels live only in the ignored local SQLite database.

## Scope

- Parsed only files present in `content_allowlist.local.jsonl`.
- Denylist and holdlist files were not opened.
- Parser uses normalized WhatsApp timestamp starts, including invisible Unicode-prefixed export lines.

## Counts

| Metric                   |               Value |
| ------------------------ | ------------------: |
| Allowlisted files parsed |                  31 |
| Parsed messages          |               20169 |
| Distinct sender hashes   |                  33 |
| Total body characters    |             1588944 |
| Median body characters   |                  42 |
| Min timestamp            | 2023-10-18T14:22:10 |
| Max timestamp            | 2026-05-22T13:44:59 |

## Sources

| Source           | Files |
| ---------------- | ----: |
| 02_zip-extracted |    31 |

## Source Tags

| Source tag     | Files |
| -------------- | ----: |
| tag-02a8764847 |    11 |
| tag-f4c6a73c2c |    10 |
| tag-f6302850cc |    10 |

## Message Features

| Feature       | Messages |
| ------------- | -------: |
| system_events |       34 |
| url           |      205 |
| email         |       61 |
| phone_like    |     2777 |
| media_omitted |        0 |

## Messages By Year

| Year | Messages |
| ---- | -------: |
| 2023 |      108 |
| 2024 |     2005 |
| 2025 |    11373 |
| 2026 |     6683 |

## Top Months

| Month   | Messages |
| ------- | -------: |
| 2026-01 |     1559 |
| 2025-04 |     1502 |
| 2026-03 |     1480 |
| 2025-09 |     1460 |
| 2026-02 |     1410 |
| 2026-04 |     1269 |
| 2025-10 |     1256 |
| 2025-12 |     1065 |
| 2025-07 |      991 |
| 2026-05 |      965 |
| 2025-05 |      958 |
| 2025-08 |      956 |
| 2025-06 |      918 |
| 2025-11 |      842 |
| 2024-11 |      716 |
| 2025-03 |      650 |
| 2025-02 |      463 |
| 2024-10 |      402 |
| 2025-01 |      312 |
| 2024-07 |      247 |

## Parse Warnings

| Warning | Files |
| ------- | ----: |
| none    |     0 |

## Next Safe Step

Build local-only aggregate extractors against the ignored SQLite database. Any report committed to git must stay aggregate-only unless explicitly approved.
