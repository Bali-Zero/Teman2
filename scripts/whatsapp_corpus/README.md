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
