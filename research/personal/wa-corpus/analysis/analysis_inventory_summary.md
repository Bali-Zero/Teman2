# WhatsApp Analysis Inventory Summary

Generated UTC: `2026-05-26T14:02:52+00:00`
Analysis directory label: `analysis`

## Privacy Mode

- This inventory does not open raw corpus files.
- This inventory does not select raw message text, sender labels, or local paths.
- SQLite inspection is limited to table names and row counts.
- Tracked output contains artifact names, table names, titles, and counts only.

## Artifact Counts

| Artifact type              | Count |
| -------------------------- | ----: |
| Local SQLite artifacts     |     5 |
| Tracked markdown summaries |     5 |

## Local SQLite Artifacts

| Artifact                           | Status | Tables | Total rows |
| ---------------------------------- | ------ | -----: | ---------: |
| allowed_candidates.local.sqlite    | ok     |      2 |      18926 |
| allowed_messages.local.sqlite      | ok     |      3 |      20201 |
| allowed_signal_hits.local.sqlite   | ok     |      2 |      12250 |
| allowed_signal_matrix.local.sqlite | ok     |      6 |        447 |
| allowed_temporal.local.sqlite      | ok     |     10 |        125 |

## Largest Local Tables

| Artifact                           | Table                      |  Rows |
| ---------------------------------- | -------------------------- | ----: |
| allowed_messages.local.sqlite      | parsed_messages            | 20169 |
| allowed_candidates.local.sqlite    | extracted_candidates       | 18925 |
| allowed_signal_hits.local.sqlite   | signal_hits                | 12249 |
| allowed_signal_matrix.local.sqlite | signal_month_matrix        |   302 |
| allowed_signal_matrix.local.sqlite | signal_cooccurrence        |    63 |
| allowed_signal_matrix.local.sqlite | signal_source_matrix       |    36 |
| allowed_messages.local.sqlite      | file_parse_summaries       |    31 |
| allowed_signal_matrix.local.sqlite | file_signal_density        |    31 |
| allowed_temporal.local.sqlite      | median_body_chars_by_month |    29 |
| allowed_temporal.local.sqlite      | messages_by_month          |    29 |
| allowed_temporal.local.sqlite      | messages_by_hour           |    24 |
| allowed_temporal.local.sqlite      | top_file_id_by_volume      |    20 |
| allowed_signal_matrix.local.sqlite | signal_totals              |    12 |
| allowed_temporal.local.sqlite      | messages_by_weekday        |     7 |
| allowed_temporal.local.sqlite      | feature_flag_counts        |     4 |
| allowed_temporal.local.sqlite      | messages_by_year           |     4 |
| allowed_temporal.local.sqlite      | metadata                   |     4 |
| allowed_signal_matrix.local.sqlite | analysis_metadata          |     3 |
| allowed_temporal.local.sqlite      | messages_by_source_tag     |     3 |
| allowed_candidates.local.sqlite    | candidate_runs             |     1 |

## Tracked Summaries

| Summary                          | Title                                           | Lines |
| -------------------------------- | ----------------------------------------------- | ----: |
| allowed_candidates_summary.md    | WhatsApp Allowlist Candidate Extraction Summary |    95 |
| allowed_messages_summary.md      | WhatsApp Allowlist Parse Summary                |   100 |
| allowed_signal_matrix_summary.md | Allowed Signal Matrix Summary                   |   152 |
| allowed_signal_summary.md        | WhatsApp Allowlist Signal Summary               |   110 |
| allowed_temporal_summary.md      | WhatsApp Allowed Temporal Summary               |   173 |

## Next Safe Step

Use this inventory as the run checklist before adding new local extractors. New analyzers should add one ignored `.local.sqlite` artifact and one aggregate tracked summary.
