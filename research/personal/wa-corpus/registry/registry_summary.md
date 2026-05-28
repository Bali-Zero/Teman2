# WhatsApp Corpus Registry Summary

Generated UTC: `2026-05-26T09:48:44+00:00`
Corpus root hash: `0baa9455a5dbd35f957f6487`
SQLite registry: `research/personal/wa-corpus/registry/registry.sqlite`

## Privacy Mode

- Metadata only.
- No raw message text.
- No message snippets.
- No raw source paths in this report.
- Per-file references use `file_id` plus `path_hash`.

## Global Counts

| Metric                           |  Value |
| -------------------------------- | -----: |
| TXT chat files parsed            |    698 |
| Parser message-start records     | 105532 |
| Normalized message-start records | 162109 |
| Target message count             | 105530 |
| Delta parser-target              |     +2 |

## Source Breakdown

| Source                    | Files | Baseline starts | Normalized starts |  Lines | Size bytes | Filename claim sum | Header claim sum | Warnings |
| ------------------------- | ----: | --------------: | ----------------: | -----: | ---------: | -----------------: | ---------------: | -------: |
| 01_wa-mirror-db           |   288 |           14847 |             14847 |  18015 |    1691783 |              16836 |                0 |        1 |
| 02_zip-extracted          |   400 |           74753 |            102038 | 222289 |   12776772 |                  0 |                0 |      367 |
| 03_drive-icloud           |    10 |           15932 |             45224 | 109664 |    4556622 |                  0 |                0 |       10 |
| 04_already-extracted-team |     0 |               0 |                 0 |      0 |          0 |                  0 |                0 |        0 |
| 99_logs                   |     0 |               0 |                 0 |      0 |          0 |                  0 |                0 |        0 |

## Warning Codes

| Warning                        | Files |
| ------------------------------ | ----: |
| unicode_prefixed_export_starts |   377 |
| filename_count_mismatch        |     1 |

## Count Mismatch Candidates

These rows expose only `file_id` and `path_hash`, not contact names, phone numbers, or raw paths.

| File ID      | Source          | Source tag | Path hash                  | Baseline starts | Normalized starts | Filename claim | Header claim | Warnings                |
| ------------ | --------------- | ---------- | -------------------------- | --------------: | ----------------: | -------------: | -----------: | ----------------------- |
| wa-file-0287 | 01_wa-mirror-db |            | `f370aeca1d90eaa3c9fdbbbe` |              31 |                31 |           2020 |              | filename_count_mismatch |

## Discrepancy Interpretation

- The parser count is `105532`, target count is `105530`, delta is `+2`.
- The normalized count is `162109` after accepting invisible Unicode-prefixed WhatsApp timestamp lines.
- This registry counts timestamp-start records, not necessarily the same semantic unit as source indexes, filename prefixes, database totals, or WhatsApp UI counts.
- Baseline count intentionally preserves the original anti-hallucination counting rule used for the 105k brief; normalized count is a separate diagnostic signal.
- The mirror source has separate parser starts, filename claim sums, and header claim sums because those are independent count signals.
- Next reconciliation step: inspect warning classes locally through SQLite using `file_id` and `path_hash`; do not copy raw paths or message text into shareable reports.

## SQLite Inspection Examples

```sql
SELECT source, files, message_starts, normalized_message_starts, filename_claimed_sum, header_claimed_sum
FROM source_summaries
ORDER BY source;

SELECT file_id, source, source_tag, path_hash, message_start_count,
       normalized_message_start_count, filename_claimed_count, header_claimed_count,
       warning_codes_json
FROM corpus_files
WHERE warning_codes_json != '[]'
ORDER BY message_start_count DESC
LIMIT 50;
```
