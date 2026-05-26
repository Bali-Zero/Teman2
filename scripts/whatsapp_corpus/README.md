# WhatsApp Corpus Registry

Local-only utilities for the 2026-05-26 WhatsApp corpus archive.

## Privacy Contract

- Do not call cloud LLMs.
- Do not output raw message text.
- Do not output message snippets.
- Do not output phone numbers.
- Do not output raw source paths in shareable reports.
- Use `file_id` and `path_hash` for per-file references.

## Build Registry

Run from repo root with the repo virtualenv active:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_registry \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --output-dir research/personal/wa-corpus/registry \
  --target-total 105530
```

Outputs:

- `research/personal/wa-corpus/registry/registry.sqlite`
- `research/personal/wa-corpus/registry/registry_summary.md`

The SQLite registry stores metadata only: source bucket, hashed ZIP source tag,
parser type, file hash, path hash, line count, message-start count, timestamp
min/max, and parser warning codes. It intentionally avoids raw message bodies
and raw paths.

The registry keeps two export counts:

- `message_start_count`: baseline count that preserves the original 105k brief
  rule.
- `normalized_message_start_count`: diagnostic count that also accepts invisible
  Unicode-prefixed WhatsApp timestamp lines.

## Classify Chats

Run the privacy gate classifier after the registry exists:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.classify_chats \
  --registry-db research/personal/wa-corpus/registry/registry.sqlite \
  --output-dir research/personal/wa-corpus/classification
```

Outputs:

- `research/personal/wa-corpus/classification/chat_classification.sqlite`
- `research/personal/wa-corpus/classification/classification_summary.md`

The classifier is deterministic and metadata-only. It does not inspect message
bodies. It uses source buckets, hashed ZIP source tags, message counts, parser
warnings, and normalized count deltas to assign each file to a conservative
processing gate:

- `deny_content_mining_until_owner_allowlist`
- `local_only_team_analysis_after_owner_approval`
- `manual_review_before_content_mining`
- `manual_review_before_any_use`

All categories are pre-flight safety labels. They are not semantic claims about
the conversation contents.

## Resolve Review References Locally

Shareable reports intentionally expose only `file_id`, `path_hash`, and hashed
`source_tag`. To review a file on the Pro, resolve a specific reference in the
terminal:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.resolve_refs \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --file-id wa-file-0421
```

This command prints raw local paths, so do not redirect its output into tracked
repo files.

## Build Owner Review Manifest

Generate a private manifest for owner decisions before any content mining:

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

The `.local.tsv` file contains raw local paths and is ignored by git. Use its
blank `owner_decision` column to create the next allowlist/denylist:

- `allow_team_local`
- `allow_business_local`
- `deny_personal`
- `deny_sensitive`
- `unknown_hold`
