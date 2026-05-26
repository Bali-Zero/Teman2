# WhatsApp Analysis Inventory Summary

Generated UTC: `2026-05-26T14:12:17+00:00`
Analysis directory label: `analysis`

## Privacy Mode

- This inventory does not open raw corpus files.
- This inventory does not select raw message text, sender labels, or local paths.
- SQLite inspection is limited to table names and row counts.
- Tracked output contains artifact names, table names, titles, and counts only.

## Artifact Counts

| Artifact type              | Count |
| -------------------------- | ----: |
| Local SQLite artifacts     |     9 |
| Tracked markdown summaries |    10 |

## Local SQLite Artifacts

| Artifact                                   | Status | Tables | Total rows |
| ------------------------------------------ | ------ | -----: | ---------: |
| allowed_candidates.local.sqlite            | ok     |      2 |      18926 |
| allowed_document_requirements.local.sqlite | ok     |      6 |      14720 |
| allowed_followup_risk.local.sqlite         | ok     |      9 |       9065 |
| allowed_immigration_lifecycle.local.sqlite | ok     |      9 |      29604 |
| allowed_messages.local.sqlite              | ok     |      3 |      20201 |
| allowed_signal_hits.local.sqlite           | ok     |      2 |      12250 |
| allowed_signal_matrix.local.sqlite         | ok     |      6 |        447 |
| allowed_tax_payment.local.sqlite           | ok     |      7 |       2610 |
| allowed_temporal.local.sqlite              | ok     |     10 |        125 |

## Largest Local Tables

| Artifact                                   | Table                      |  Rows |
| ------------------------------------------ | -------------------------- | ----: |
| allowed_immigration_lifecycle.local.sqlite | stage_hits                 | 21909 |
| allowed_messages.local.sqlite              | parsed_messages            | 20169 |
| allowed_candidates.local.sqlite            | extracted_candidates       | 18925 |
| allowed_document_requirements.local.sqlite | requirement_hits           | 14489 |
| allowed_signal_hits.local.sqlite           | signal_hits                | 12249 |
| allowed_followup_risk.local.sqlite         | queue_items                |  8948 |
| allowed_immigration_lifecycle.local.sqlite | message_stage_summary      |  7335 |
| allowed_tax_payment.local.sqlite           | tax_payment_hits           |  2416 |
| allowed_signal_matrix.local.sqlite         | signal_month_matrix        |   302 |
| allowed_immigration_lifecycle.local.sqlite | stage_month_matrix         |   211 |
| allowed_document_requirements.local.sqlite | requirement_month_counts   |   201 |
| allowed_tax_payment.local.sqlite           | category_month_totals      |   136 |
| allowed_immigration_lifecycle.local.sqlite | primary_stage_transitions  |    64 |
| allowed_signal_matrix.local.sqlite         | signal_cooccurrence        |    63 |
| allowed_signal_matrix.local.sqlite         | signal_source_matrix       |    36 |
| allowed_followup_risk.local.sqlite         | file_counts                |    31 |
| allowed_messages.local.sqlite              | file_parse_summaries       |    31 |
| allowed_signal_matrix.local.sqlite         | file_signal_density        |    31 |
| allowed_followup_risk.local.sqlite         | month_counts               |    29 |
| allowed_temporal.local.sqlite              | median_body_chars_by_month |    29 |

## Tracked Summaries

| Summary                                  | Title                                           | Lines |
| ---------------------------------------- | ----------------------------------------------- | ----: |
| allowed_candidates_summary.md            | WhatsApp Allowlist Candidate Extraction Summary |    95 |
| allowed_document_requirements_summary.md | WhatsApp Allowlist Document Requirement Summary |   135 |
| allowed_followup_risk_summary.md         | WhatsApp Follow-Up Risk Queue Summary           |   169 |
| allowed_immigration_lifecycle_summary.md | Allowed Immigration Lifecycle Summary           |   183 |
| allowed_messages_summary.md              | WhatsApp Allowlist Parse Summary                |   100 |
| allowed_signal_matrix_summary.md         | Allowed Signal Matrix Summary                   |   152 |
| allowed_signal_summary.md                | WhatsApp Allowlist Signal Summary               |   110 |
| allowed_tax_payment_summary.md           | Allowed Tax/Payment Aggregate Summary           |   128 |
| allowed_temporal_summary.md              | WhatsApp Allowed Temporal Summary               |   173 |
| analysis_inventory_summary.md            | WhatsApp Analysis Inventory Summary             |    67 |

## Next Safe Step

Use this inventory as the run checklist before adding new local extractors. New analyzers should add one ignored `.local.sqlite` artifact and one aggregate tracked summary.
