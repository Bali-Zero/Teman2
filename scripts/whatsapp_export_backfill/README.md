# WhatsApp Export Backfill

Local, dry-run-safe tools for parsing WhatsApp chat exports into JSONL and scoring exported contacts against candidate CRM/contact dictionaries.

## Scope

- Standard library only.
- No production database writes.
- Binary attachments are not OCRed or parsed; the parser records path, MIME guess, size, and SHA-256 hash.
- Filenames are normalized to NFC for matching, while original relative paths are preserved in emitted records.

## Parse An Export

```bash
apps/backend-rag/.venv/bin/python -m scripts.whatsapp_export_backfill.parse_exports \
  "/path/to/WhatsApp Chat" \
  --batch-id yopo \
  --output /tmp/yopo-export.jsonl
```

Record types emitted:

- `batch`
- `message`
- `document`
- `contact`

Supported message headers:

- `[dd/mm/yy, hh.mm.ss] Sender: body`
- `[dd/mm/yy, hh:mm:ss] Sender: body`

Supported attachment markers:

- `<attached: file>`
- `<allegato: file>`

## Match Contacts

`match_exports.py` exposes `score_contact_match(export_contact, candidate_clients, whatsapp_contacts)`.

The matcher is pure Python and accepts dictionaries/lists, so tests and future import code do not need a database connection.

Scoring rules:

- exact one active non-team client: `1.0`
- exact phone with WhatsApp contact plus client: `0.95`
- deleted duplicate or alias mismatch: `0.80`, review
- name-only: `0.65`, review
- otherwise below `0.65`

## Staging Import Skeleton

`import_staging.py` currently summarizes JSONL in dry-run mode only. It intentionally does not require any staging schema to exist.

```bash
apps/backend-rag/.venv/bin/python -m scripts.whatsapp_export_backfill.import_staging /tmp/yopo-export.jsonl
```

## Tests

```bash
apps/backend-rag/.venv/bin/python -m pytest scripts/whatsapp_export_backfill/tests -q
```
