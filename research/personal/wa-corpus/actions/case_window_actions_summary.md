# WhatsApp Case Window Actions Summary

Generated UTC: `2026-05-26T17:36:24+00:00`
Private workbook: `research/personal/wa-corpus/review/case_window_review_workbook.local.tsv`
Private actions queue: `research/personal/wa-corpus/actions/case_window_actions.local.tsv`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or owner notes.
- Only rows with `owner_decision=approve` become local CRM/ops actions.

## Counts

| Metric                    | Value |
| ------------------------- | ----: |
| Workbook rows             |   100 |
| Approved action rows      |     0 |
| Action event refs         |     0 |
| Action message refs       |     0 |
| Action high-severity refs |     0 |

## Workbook Decisions

| Value | Rows |
| ----- | ---: |
| blank |  100 |

## Action Types

| Value | Rows |
| ----- | ---: |
| none  |    0 |

## Action Priorities

| Value | Rows |
| ----- | ---: |
| none  |    0 |

## Action Dominant Domains

| Value | Rows |
| ----- | ---: |
| none  |    0 |

## Local Execution Contract

- Treat `case_window_actions.local.tsv` as a local ops queue, not a client record.
- Validate each row against the local context before copying anything into CRM.
- Do not upload the workbook, context TSV, or action queue to any cloud service.
