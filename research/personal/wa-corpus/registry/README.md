# WhatsApp Corpus Registry Output

This directory is for local-only generated registry artifacts for:

`~/Desktop/wa-chats-MASTER-2026-05-26/`

Expected generated files:

- `registry.sqlite`
- `registry_summary.md`

Privacy posture:

- Metadata-only output.
- No raw message text.
- No message snippets.
- No raw source paths in the Markdown summary.
- Per-file references use `file_id` plus `path_hash`.

Regenerate with:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_registry
```
