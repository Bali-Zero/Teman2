# WhatsApp Corpus Classification

This directory contains the Step 2 pre-flight taxonomy for the local WhatsApp
corpus workflow.

## Privacy Contract

- Do not call cloud LLMs.
- Do not output raw message text.
- Do not output message snippets.
- Do not output phone numbers.
- Do not output raw source paths.
- Do not output raw contact names.
- Use `file_id`, `path_hash`, and hashed `source_tag` for per-file references.

## Generate Classification

Run from repo root with the repo virtualenv active:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.classify_chats \
  --registry-db research/personal/wa-corpus/registry/registry.sqlite \
  --output-dir research/personal/wa-corpus/classification
```

Outputs:

- `research/personal/wa-corpus/classification/chat_classification.sqlite`
- `research/personal/wa-corpus/classification/classification_summary.md`

The SQLite file is ignored by git. The Markdown summary is safe to keep in the
repo because it contains only aggregate counts and hashed per-file references.

## Local Review

Use the resolver only for explicit references that need review:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.resolve_refs \
  --root "$HOME/Desktop/wa-chats-MASTER-2026-05-26" \
  --file-id wa-file-0421
```

The resolver prints raw local paths to the terminal. Do not redirect that output
into tracked files.

## Meaning

This is not content analysis. It is a conservative gate before content analysis:

- Personal-sensitive archives stay blocked until an explicit local allowlist
  exists.
- Team-sensitive archives stay local-only and require owner approval before any
  message-body mining.
- Mixed or unknown archives are limited to metadata until manual review.
