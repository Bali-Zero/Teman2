# WhatsApp Full Corpus Parse Summary

Generated UTC: `2026-05-26T18:29:11+00:00`
Local raw SQLite artifact: `full_messages.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or contact names.
- The full raw cleartext corpus lives only in the ignored local SQLite database.
- The SQLite database includes an FTS5 index for local cleartext search.

## Scope

- Parsed every TXT chat file found by the registry-compatible local resolver.
- This is owner-local processing on the Pro only.
- No cloud LLM or external API received corpus content.

## Counts

| Metric                     |               Value |
| -------------------------- | ------------------: |
| Files parsed               |                 699 |
| Zero-message files skipped |                 288 |
| Parsed messages            |              162162 |
| Distinct sender hashes     |                 276 |
| Total body characters      |            12052705 |
| Median body characters     |                  50 |
| Min timestamp              | 2022-06-01T14:09:35 |
| Max timestamp              | 2026-05-22T13:44:59 |

## Sources

| Source             | Files |
| ------------------ | ----: |
| 02_zip-extracted   |   400 |
| 01_wa-mirror-db    |   288 |
| 03_drive-icloud    |    10 |
| CHAT-HISTORY-PILOT |     1 |

## Parsers

| Parser          | Files |
| --------------- | ----: |
| whatsapp_export |   411 |
| wa_mirror_db    |   288 |

## Message Features

| Feature       | Messages |
| ------------- | -------: |
| system_events |      188 |
| url           |     2649 |
| email         |      895 |
| phone_like    |    28671 |
| media_omitted |        0 |

## Messages By Year

| Year | Messages |
| ---- | -------: |
| 2022 |        9 |
| 2023 |     2162 |
| 2024 |    38727 |
| 2025 |    83541 |
| 2026 |    37723 |

## Top Months

| Month   | Messages |
| ------- | -------: |
| 2026-01 |    12126 |
| 2025-12 |    11890 |
| 2025-04 |     8969 |
| 2025-06 |     8796 |
| 2025-03 |     8493 |
| 2025-05 |     7931 |
| 2025-07 |     7671 |
| 2024-11 |     7127 |
| 2026-04 |     7081 |
| 2025-02 |     6950 |
| 2024-10 |     6846 |
| 2024-09 |     6833 |
| 2026-05 |     6481 |
| 2025-01 |     6125 |
| 2026-03 |     6049 |
| 2026-02 |     5986 |
| 2024-08 |     5358 |
| 2025-08 |     4771 |
| 2025-09 |     4620 |
| 2024-12 |     4416 |
| 2025-10 |     4315 |
| 2025-11 |     3010 |
| 2024-07 |     2179 |
| 2024-06 |     1259 |

## Parse Warnings

| Warning | Files |
| ------- | ----: |
| none    |     0 |

## Next Local Step

Run the spicy/private quarantine pass, then mine only non-quarantined rows for CRM, KB, timeline, and ops use cases.
