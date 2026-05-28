# WhatsApp Case Window Review Queue Summary

Generated UTC: `2026-05-26T16:54:00+00:00`
Input case-window SQLite artifact: `allowed_case_windows.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or raw extracted values.
- The ignored local TSV contains anonymous window IDs and local aggregate metadata only.

## Counts

| Metric                        | Value |
| ----------------------------- | ----: |
| Total windows                 |   656 |
| Queue windows                 |   100 |
| Queue messages                |  6850 |
| Queue events                  | 30022 |
| High severity events in queue |  2732 |

## Review Reason Counts

| Reason             | Windows |
| ------------------ | ------: |
| high_severity      |     100 |
| multi_domain       |     100 |
| high_event_volume  |     100 |
| large_window       |      87 |
| lifecycle_dominant |      76 |
| followup_dominant  |      23 |
| cross_month        |      20 |
| document_dominant  |       1 |

## Queue Dominant Domains

| Domain                | Windows |
| --------------------- | ------: |
| immigration_lifecycle |      76 |
| followup_risk         |      23 |
| document_requirement  |       1 |

## Queue Window Size Buckets

| Message count bucket | Windows |
| -------------------- | ------: |
| 101+                 |      19 |
| 51-100               |      33 |
| 26-50                |      35 |
| 11-25                |      11 |
| 6-10                 |       2 |

## Operational Reading

- Use the ignored TSV as a manual triage queue for dense local windows.
- Review reasons are heuristic signals, not a legal or client-side conclusion.
