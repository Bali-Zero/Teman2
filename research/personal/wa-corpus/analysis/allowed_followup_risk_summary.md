# WhatsApp Follow-Up Risk Queue Summary

- Generated UTC: `2026-05-26T14:12:12+00:00`
- Messages DB: `allowed_messages.local.sqlite`
- Signal DB: `allowed_signal_hits.local.sqlite`
- Temporal DB: `allowed_temporal.local.sqlite`
- Local queue DB: `allowed_followup_risk.local.sqlite`

## Privacy Boundary

- This tracked summary contains no raw message text or snippets.
- This tracked summary contains no raw contact names, phone numbers, or emails.
- This tracked summary contains no raw source paths or raw extracted values.
- The ignored local SQLite queue stores only hashed/local message references, timestamps, aggregate-safe metadata, and reason codes.

## Overview

| Metric                         | Value |
| ------------------------------ | ----- |
| Messages scanned               | 20169 |
| Signal hits read               | 12249 |
| Temporal total messages        | 20169 |
| Queue messages                 | 8948  |
| High severity queue messages   | 1560  |
| Medium severity queue messages | 2783  |
| Low severity queue messages    | 4605  |
| Threshold hours                | 48.0  |
| Repeat window hours            | 72.0  |

## Queue Buckets

| Bucket                | Queue messages |
| --------------------- | -------------- |
| repeated_request      | 5118           |
| deadline_followup     | 2741           |
| risk_or_problem       | 519            |
| waiting_or_unanswered | 438            |
| followup_or_reminder  | 132            |

## Reason Codes

| Reason code                       | Queue messages | Files | High severity |
| --------------------------------- | -------------- | ----- | ------------- |
| repeated_request_thread           | 8354           | 31    | 1444          |
| deadline_mention                  | 3120           | 31    | 955           |
| source_signal_scheduling_followup | 915            | 31    | 711           |
| explicit_followup                 | 891            | 31    | 317           |
| urgency_risk_problem              | 557            | 31    | 526           |
| unanswered_later_than_threshold   | 438            | 31    | 395           |
| source_signal_urgency_risk        | 406            | 31    | 382           |
| reminder_waiting                  | 255            | 31    | 78            |

## Severity

| Severity | Queue messages |
| -------- | -------------- |
| low      | 4605           |
| medium   | 2783           |
| high     | 1560           |

## Queue By Month

| Month   | Queue messages |
| ------- | -------------- |
| 2026-01 | 771            |
| 2025-04 | 692            |
| 2026-03 | 679            |
| 2025-09 | 624            |
| 2026-02 | 597            |
| 2025-10 | 572            |
| 2026-04 | 524            |
| 2025-12 | 466            |
| 2025-07 | 462            |
| 2025-08 | 424            |
| 2025-06 | 416            |
| 2025-05 | 410            |
| 2026-05 | 395            |
| 2025-11 | 354            |
| 2024-11 | 343            |
| 2025-03 | 294            |
| 2025-02 | 218            |
| 2024-10 | 169            |
| 2025-01 | 140            |
| 2024-07 | 99             |
| 2024-09 | 64             |
| 2024-06 | 63             |
| 2024-12 | 59             |
| 2023-12 | 45             |
| 2024-08 | 31             |

_Showing 25 of 29 rows._

## Queue By Source Tag

| Source tag     | Queue messages | Files | High severity |
| -------------- | -------------- | ----- | ------------- |
| tag-f6302850cc | 3280           | 10    | 533           |
| tag-f4c6a73c2c | 3091           | 10    | 563           |
| tag-02a8764847 | 2577           | 11    | 464           |

## Top File IDs

| File ID      | Source tag     | Queue messages | High severity | Distinct reasons | First month | Last month |
| ------------ | -------------- | -------------- | ------------- | ---------------- | ----------- | ---------- |
| wa-file-0579 | tag-f4c6a73c2c | 1503           | 218           | 8                | 2024-11     | 2026-05    |
| wa-file-0628 | tag-02a8764847 | 450            | 104           | 8                | 2025-02     | 2026-05    |
| wa-file-0313 | tag-f6302850cc | 766            | 91            | 8                | 2024-06     | 2026-05    |
| wa-file-0305 | tag-f6302850cc | 615            | 89            | 8                | 2023-12     | 2026-05    |
| wa-file-0627 | tag-02a8764847 | 290            | 61            | 8                | 2025-01     | 2026-05    |
| wa-file-0297 | tag-f6302850cc | 343            | 60            | 8                | 2024-09     | 2026-04    |
| wa-file-0293 | tag-f6302850cc | 289            | 54            | 8                | 2025-10     | 2026-05    |
| wa-file-0294 | tag-f6302850cc | 289            | 54            | 8                | 2025-10     | 2026-05    |
| wa-file-0633 | tag-02a8764847 | 270            | 53            | 8                | 2025-01     | 2026-05    |
| wa-file-0295 | tag-f6302850cc | 223            | 53            | 8                | 2025-04     | 2025-10    |
| wa-file-0574 | tag-f4c6a73c2c | 184            | 52            | 8                | 2024-11     | 2026-04    |
| wa-file-0606 | tag-02a8764847 | 420            | 49            | 8                | 2025-04     | 2026-04    |
| wa-file-0547 | tag-f4c6a73c2c | 175            | 43            | 8                | 2024-09     | 2026-05    |
| wa-file-0296 | tag-f6302850cc | 269            | 42            | 8                | 2024-09     | 2026-04    |
| wa-file-0553 | tag-f4c6a73c2c | 261            | 42            | 8                | 2025-04     | 2026-04    |
| wa-file-0538 | tag-f4c6a73c2c | 156            | 42            | 8                | 2025-07     | 2026-05    |
| wa-file-0291 | tag-f6302850cc | 197            | 41            | 8                | 2024-10     | 2026-05    |
| wa-file-0607 | tag-02a8764847 | 156            | 39            | 8                | 2025-04     | 2026-04    |
| wa-file-0558 | tag-f4c6a73c2c | 134            | 39            | 8                | 2025-09     | 2026-05    |
| wa-file-0576 | tag-f4c6a73c2c | 180            | 37            | 8                | 2025-01     | 2026-05    |
| wa-file-0598 | tag-02a8764847 | 155            | 35            | 8                | 2024-08     | 2026-05    |
| wa-file-0541 | tag-f4c6a73c2c | 180            | 34            | 8                | 2026-02     | 2026-05    |
| wa-file-0630 | tag-02a8764847 | 177            | 32            | 8                | 2024-11     | 2026-04    |
| wa-file-0634 | tag-02a8764847 | 209            | 29            | 8                | 2026-01     | 2026-04    |
| wa-file-0317 | tag-f6302850cc | 134            | 29            | 8                | 2023-10     | 2026-05    |

_Showing 25 of 31 rows._

## Reason Co-Occurrence

| Reason A                          | Reason B                          | Queue messages | Files |
| --------------------------------- | --------------------------------- | -------------- | ----- |
| deadline_mention                  | repeated_request_thread           | 2754           | 31    |
| repeated_request_thread           | source_signal_scheduling_followup | 773            | 31    |
| explicit_followup                 | repeated_request_thread           | 711            | 31    |
| deadline_mention                  | source_signal_scheduling_followup | 651            | 31    |
| repeated_request_thread           | urgency_risk_problem              | 478            | 31    |
| source_signal_urgency_risk        | urgency_risk_problem              | 406            | 31    |
| repeated_request_thread           | source_signal_urgency_risk        | 354            | 31    |
| repeated_request_thread           | unanswered_later_than_threshold   | 342            | 31    |
| deadline_mention                  | unanswered_later_than_threshold   | 238            | 28    |
| explicit_followup                 | source_signal_scheduling_followup | 226            | 31    |
| reminder_waiting                  | repeated_request_thread           | 224            | 31    |
| deadline_mention                  | urgency_risk_problem              | 163            | 30    |
| deadline_mention                  | explicit_followup                 | 135            | 30    |
| deadline_mention                  | source_signal_urgency_risk        | 120            | 29    |
| explicit_followup                 | urgency_risk_problem              | 100            | 30    |
| deadline_mention                  | reminder_waiting                  | 58             | 25    |
| source_signal_scheduling_followup | urgency_risk_problem              | 54             | 21    |
| explicit_followup                 | unanswered_later_than_threshold   | 44             | 24    |
| unanswered_later_than_threshold   | urgency_risk_problem              | 38             | 22    |
| explicit_followup                 | source_signal_urgency_risk        | 35             | 17    |
| source_signal_scheduling_followup | unanswered_later_than_threshold   | 32             | 16    |
| explicit_followup                 | reminder_waiting                  | 29             | 14    |
| reminder_waiting                  | source_signal_scheduling_followup | 29             | 17    |
| reminder_waiting                  | urgency_risk_problem              | 26             | 17    |
| source_signal_urgency_risk        | unanswered_later_than_threshold   | 23             | 16    |

_Showing 25 of 28 rows._

## Caveats

- Queue membership is deterministic pattern matching plus timestamp/sender-hash heuristics, not a client instruction or legal conclusion.
- `unanswered_later_than_threshold` uses the next different sender in the same file as the reply proxy; archived or side-channel replies can create false positives.
- Deadline detection records only a boolean reason code; extracted date values are intentionally not written to the tracked summary.
