# WhatsApp Corpus Registry Output

This directory is for local-only generated registry artifacts for:

the local WhatsApp export root used to build the registry

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
