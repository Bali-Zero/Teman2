# WhatsApp Export Backfill

Tools to parse local WhatsApp exports into JSONL and import them into *staging* tables only.

Safety boundaries:
- No CRM writes.
- No LID normalization from exports.
- No auto-create CRM clients from vCards.
- Default is dry-run; DB writes require `--apply`.

Example (YOPO pilot):

```bash
cd /Users/nuzantara/Desktop/nuzantara
cd apps/backend-rag && source .venv/bin/activate

PYTHONPATH=/Users/nuzantara/Desktop/nuzantara \
  python -m scripts.whatsapp_export_backfill.parse_exports \
  "/Users/nuzantara/Desktop/WhatsApp Chat - YOPO company/WhatsApp Chat - YOPO company" \
  -o /tmp/yopo-export.jsonl \
  --batch-id yopo-2026-05

PYTHONPATH=/Users/nuzantara/Desktop/nuzantara \
  python -m scripts.whatsapp_export_backfill.import_staging \
  /tmp/yopo-export.jsonl \
  --dry-run
```
