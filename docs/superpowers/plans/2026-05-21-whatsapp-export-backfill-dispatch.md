# WhatsApp Export Backfill Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn local WhatsApp exports under `/Users/nuzantara/Desktop/WhatsApp Chat - YOPO company` into controlled CRM/WhatsApp intelligence staging, without leaking raw private documents or creating bad CRM records.

**Architecture:** Import export-derived contacts, chats, and document metadata into staging tables first. Match against CRM/WhatsApp data with confidence and review status. Expose only allowlisted staging fields in Kita. Promote to `clients`, `practices`, or portal-visible summaries only in a separate explicit approval step.

**Tech Stack:** PostgreSQL, FastAPI, Python 3.11 in `apps/backend-rag/.venv`, Next.js/TypeScript in `apps/mouth`, local CLI parsers, local `pdftotext` for limited internal-only evidence checks.

---

## Wave 1 Evidence

- Export root: `/Users/nuzantara/Desktop/WhatsApp Chat - YOPO company`
- Total files: `15,299`, about `2.4G`.
- Canonical YOPO export: `/Users/nuzantara/Desktop/WhatsApp Chat - YOPO company/WhatsApp Chat - YOPO company`
- Root YOPO `_chat.txt` is a duplicate but incomplete: it is missing 2 referenced attachments. Do not ingest the root copy.
- Nested `WhatsApp Chat - INVOICE BALI ZERO`: `14,736` files, `9,777` messages, `3,832` vCards, `4,863` PDFs.
- Nested `WhatsApp Chat - E ITK ONLINE`: `552` files, `119` messages, `525` PDFs.
- vCards: `2,020` unique canonical phones, high duplicate pressure, and no trustworthy `@lid` evidence.
- CRM duplicate pressure is real: known risky examples include Gemma/Fabrizio/Simonetta and Makar duplicate leads.

## Decisions

- YOPO is batch 1. `INVOICE BALI ZERO` and `E ITK ONLINE` are separate future batches.
- Do not auto-create CRM clients from vCards.
- Do not auto-normalize LID from exports. Exports can support review suggestions only.
- Filename-first document classification. No OCR/PDF text extraction in first ingest except local YOPO-only internal recap if needed.
- Parser must support English `<attached: ...>` and Italian `<allegato: ...>` markers.
- Normalize filenames to NFC for matching while preserving original relative paths for audit.
- Kita review API must be allowlist-only.
- `my.balizero.com` must receive no raw export body, local path, raw PDF/OCR text, passport/MRZ, bank/account data, LID/JID/Baileys IDs, media token, or raw chat transcript.

## Wave 2 Dispatch

Run workers with disjoint write scopes:

1. DB Staging Worker: migration only.
2. Parser Worker: `scripts/whatsapp_export_backfill/` only.
3. Backend Review API Worker: new router/tests and router registration only.
4. Frontend Review UI Worker: review page/API client only.
5. Verification Worker: tests/runbook only after implementation exists.

## Files

Create:

- `apps/backend-rag/backend/db/migrations_v2/191_whatsapp_export_staging.sql`
- `scripts/whatsapp_export_backfill/README.md`
- `scripts/whatsapp_export_backfill/__init__.py`
- `scripts/whatsapp_export_backfill/parse_exports.py`
- `scripts/whatsapp_export_backfill/match_exports.py`
- `scripts/whatsapp_export_backfill/import_staging.py`
- `scripts/whatsapp_export_backfill/tests/test_parse_exports.py`
- `scripts/whatsapp_export_backfill/tests/test_match_exports.py`
- `apps/backend-rag/backend/app/routers/whatsapp_export_review.py`
- `apps/backend-rag/backend/tests/unit/routers/test_whatsapp_export_review.py`
- `apps/mouth/src/app/(workspace)/whatsapp/export-review/page.tsx`
- `apps/mouth/src/lib/api/whatsapp-export-review.ts`
- `docs/runbooks/whatsapp-export-backfill.md`

Modify:

- `apps/backend-rag/backend/app/setup/router_registration.py`
- Optionally add a Kita nav link from existing WhatsApp workspace.

## Staging Schema Requirements

Tables:

- `whatsapp_export_batches`
- `whatsapp_export_contacts_staging`
- `whatsapp_export_messages_staging`
- `whatsapp_export_documents_staging`
- `whatsapp_export_review_actions`

Required design:

- Store full local source path only in DB backstage, never return it in API responses.
- Store `source_relpath` separately and return only basename/display-safe values to UI.
- Contacts include `display_name`, `phone_raw`, `phone_canonical`, match candidates, confidence, review status.
- Documents include filename-derived metadata only: category, inferred service, inferred person/company, sponsor, date, confidence, sensitivity flags.
- Messages include parsed sender/timestamp/body only for internal staging; API returns excerpt/redacted excerpt only.
- Review actions audit approve/reject/status transitions.

## Parser Requirements

CLI:

```bash
apps/backend-rag/.venv/bin/python scripts/whatsapp_export_backfill/parse_exports.py \
  --root "/Users/nuzantara/Desktop/WhatsApp Chat - YOPO company/WhatsApp Chat - YOPO company" \
  --label "YOPO company" \
  --out /tmp/yopo-export.jsonl
```

JSONL record kinds:

- `batch`
- `contact`
- `message`
- `document`

For YOPO, expected dry-run shape:

- `messages`: `12`
- `documents`: `5`
- no duplicate root records.

For large nested batches, parser must avoid opening large binary media beyond metadata.

## Matching Rules

Phone canonicalization:

- Strip non-digits.
- Indonesian `0...` -> `62...`.
- Indonesian local `8...` -> `62...`.
- Compare canonical digits, not raw `+` formatting.

Confidence:

- `1.00`: exactly one active CRM client by canonical phone, not team/internal.
- `0.95`: exact phone matches one WhatsApp contact and one active CRM client.
- `0.80`: exact phone but deleted duplicate or alias mismatch exists.
- `0.65`: name/document evidence only; review-only.
- `<0.65`: no suggested CRM write.

Known examples:

- Lisa Marek -> strong review match to client `9408`, alias `Lisl`.
- Sindy/Sidney Kirks -> strong review match to client `11799`.
- Trevor Richard Gerhardt -> strong review match to client `11654`.
- Gemma Inghlieri -> review-only, do not auto-link to Fabrizio/Simonetta.
- Makar Burba -> review-only, do not infer Dave/Mora/Miana as client `11787`.

## Review API Requirements

Endpoints:

- `GET /api/whatsapp-export/batches`
- `GET /api/whatsapp-export/contacts`
- `GET /api/whatsapp-export/documents`
- `GET /api/whatsapp-export/messages`
- `GET /api/whatsapp-export/yopo-case`
- `POST /api/whatsapp-export/contacts/{id}/approve-match`
- `POST /api/whatsapp-export/contacts/{id}/reject`
- `POST /api/whatsapp-export/documents/{id}/approve-link`
- `POST /api/whatsapp-export/documents/{id}/reject`

API response must deny:

- `/Users/`
- raw local paths
- `raw_baileys_event`
- JID/LID values
- raw PDF text
- raw OCR text
- passport/MRZ numbers
- bank/account numbers
- full chat transcript bodies
- media URLs/tokens

## Frontend Requirements

Route:

- `/whatsapp/export-review`

Tabs:

- Overview
- Contacts
- Documents
- YOPO

UI must show:

- counts;
- source label;
- safe basename only;
- masked phone;
- suggested match;
- confidence;
- review status;
- approve/reject controls against staging only.

UI must not render:

- local paths;
- raw document text;
- raw chat bodies;
- passport/bank data;
- LID/JID/Baileys IDs.

## Verification

Backend:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/routers/test_whatsapp_export_review.py -q
```

Parser:

```bash
apps/backend-rag/.venv/bin/python -m pytest scripts/whatsapp_export_backfill/tests -q
```

Frontend:

```bash
cd apps/mouth
npm run typecheck
npm run build
```

DB safety:

```sql
SELECT COUNT(*) FROM whatsapp_export_contacts_staging;
SELECT COUNT(*) FROM whatsapp_export_documents_staging;
SELECT COUNT(*) FROM clients WHERE created_at > now() - interval '1 hour';
SELECT COUNT(*) FROM practices WHERE created_at > now() - interval '1 hour';
```

Before explicit promotion, staging counts may be non-zero, but new `clients` and `practices` must be zero.
