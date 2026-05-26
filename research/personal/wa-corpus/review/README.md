# WhatsApp Corpus Review

This directory contains Step 3 of the local WhatsApp corpus workflow: owner
review manifests.

## Privacy Contract

- Tracked Markdown files must not contain raw message text.
- Tracked Markdown files must not contain message snippets.
- Tracked Markdown files must not contain phone numbers.
- Tracked Markdown files must not contain raw source paths.
- Tracked Markdown files must not contain raw contact names.
- Files ending in `.local.tsv`, `.local.csv`, `.local.jsonl`, or `.private.*`
  are ignored because they may contain raw local paths.

## Generate Review Manifest

Run from repo root with the repo virtualenv active:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_review_manifest \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --classification-db research/personal/wa-corpus/classification/chat_classification.sqlite \
  --output-dir research/personal/wa-corpus/review \
  --limit 80
```

Outputs:

- `research/personal/wa-corpus/review/review_manifest.local.tsv`
- `research/personal/wa-corpus/review/review_manifest_summary.md`

The `.local.tsv` file is for private owner review on the Pro. It contains local
paths and blank decision columns. Do not copy it into prompts, reports, commits,
tickets, cloud docs, or chats.

## Decision Values

Use these values in the private manifest `owner_decision` column:

- `allow_team_local`
- `allow_business_local`
- `deny_personal`
- `deny_sensitive`
- `unknown_hold`

## Compile Decisions

After review, compile decisions into allow/deny/hold lists:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_review_decisions \
  --review-manifest research/personal/wa-corpus/review/review_manifest.local.tsv \
  --output-dir research/personal/wa-corpus/decisions \
  --apply-safe-defaults
```

With safe defaults, only team-gated rows are allowed. Private-drive rows are
denied, and all remaining blank manual-review rows stay on hold.
