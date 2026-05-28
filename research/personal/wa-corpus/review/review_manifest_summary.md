# WhatsApp Review Manifest Summary

Generated UTC: `2026-05-26T12:22:28+00:00`
Input classification DB: `research/personal/wa-corpus/classification/chat_classification.sqlite`
Private local manifest: `research/personal/wa-corpus/review/review_manifest.local.tsv`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers.
- This tracked summary contains no raw source paths.
- This tracked summary contains no raw contact names.
- The private `.local.tsv` manifest contains raw local paths and is ignored by git.

## Scope

- The manifest is for owner review only.
- The goal is to create a local allowlist/denylist before content mining.
- Rows are ordered by baseline message-start volume.

## Counts

| Metric                                            |  Value |
| ------------------------------------------------- | -----: |
| Total review-required chats in classification DB  |    698 |
| Rows selected for this private manifest           |     80 |
| Rows resolved to local paths                      |     80 |
| Baseline message-start records in selected rows   |  74361 |
| Normalized message-start records in selected rows | 124933 |

## Resolution Status

| Status   | Rows |
| -------- | ---: |
| resolved |   80 |

## Selected Gates

| Gate                                          | Rows |
| --------------------------------------------- | ---: |
| manual_review_before_content_mining           |   45 |
| local_only_team_analysis_after_owner_approval |   31 |
| deny_content_mining_until_owner_allowlist     |    4 |

## Selected Labels

| Label                             | Rows |
| --------------------------------- | ---: |
| bulk_drive_export_candidate       |   38 |
| team_operator_archive_candidate   |   31 |
| mirror_contact_archive_unreviewed |    7 |
| private_drive_icloud_candidate    |    4 |

## Owner Decision Values

Use these values in the private manifest `owner_decision` column:

| Decision               | Meaning                                                                        |
| ---------------------- | ------------------------------------------------------------------------------ |
| `allow_team_local`     | Team archive can be analyzed locally after explicit scope selection.           |
| `allow_business_local` | Business/client archive can be analyzed locally for Bali Zero use cases.       |
| `deny_personal`        | Personal/family/private archive stays excluded from content mining.            |
| `deny_sensitive`       | Sensitive archive stays excluded except for legal/forensic owner-directed use. |
| `unknown_hold`         | Do not use until more review is done.                                          |

## Next Command

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_review_manifest \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --classification-db research/personal/wa-corpus/classification/chat_classification.sqlite \
  --output-dir research/personal/wa-corpus/review \
  --limit 80
```
