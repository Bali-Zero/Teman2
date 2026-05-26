# WhatsApp Review Decisions Summary

Generated UTC: `2026-05-26T12:31:57+00:00`
Input review manifest: `research/personal/wa-corpus/review/review_manifest.local.tsv`
Private decisions manifest: `research/personal/wa-corpus/decisions/review_decisions.local.tsv`
Private allowlist: `research/personal/wa-corpus/decisions/content_allowlist.local.jsonl`
Private denylist: `research/personal/wa-corpus/decisions/content_denylist.local.jsonl`
Private holdlist: `research/personal/wa-corpus/decisions/content_holdlist.local.jsonl`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers.
- This tracked summary contains no raw source paths.
- This tracked summary contains no raw contact names.
- The private `.local.*` files contain raw local paths and are ignored by git.

## Policy

- Safe defaults applied: `true`.
- `allow_team_local` and `allow_business_local` are eligible for local-only content mining.
- `deny_personal`, `deny_sensitive`, and `unknown_hold` remain excluded from content mining.
- No cloud upload is permitted for any bucket.

## Decision Counts

| Decision         | Rows |
| ---------------- | ---: |
| unknown_hold     |   45 |
| allow_team_local |   31 |
| deny_personal    |    4 |

## Bucket Counts

| Bucket | Rows | Baseline starts | Normalized starts |
| ------ | ---: | --------------: | ----------------: |
| hold   |   45 |           41417 |             61188 |
| allow  |   31 |           17528 |             20169 |
| deny   |    4 |           15416 |             43576 |

## Decision Origins

| Origin       | Rows |
| ------------ | ---: |
| safe_default |   80 |

## Gates

| Gate                                          | Rows |
| --------------------------------------------- | ---: |
| manual_review_before_content_mining           |   45 |
| local_only_team_analysis_after_owner_approval |   31 |
| deny_content_mining_until_owner_allowlist     |    4 |

## Labels

| Label                             | Rows |
| --------------------------------- | ---: |
| bulk_drive_export_candidate       |   38 |
| team_operator_archive_candidate   |   31 |
| mirror_contact_archive_unreviewed |    7 |
| private_drive_icloud_candidate    |    4 |

## Next Safe Step

Use only `content_allowlist.local.jsonl` as input to the next local-only parser/indexer. Do not read files from the denylist or holdlist.
