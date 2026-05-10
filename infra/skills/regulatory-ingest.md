---
name: regulatory-ingest
description: End-to-end ingest pipeline for new Indonesian regulations (KEP, PMK, PER, Permenkumham, SKB, PP, Perpres, UU). One command takes a regulation reference (e.g. "PMK 81/2024") through 6 stages: JDIH download → Drive upload → spreadsheet update → NotebookLM push → Qdrant embed (semantic+BM25) → Knowledge Graph extraction. Use when user says "ingest [regulation]", "aggiungi [legge]", "nuova legge è uscita", or whenever devils-advocate finds a verified-real regulation that's NOT yet in our 4-tier ground-truth (Drive + NB + Qdrant + KG).
---

# Regulatory Ingest — One Command, 6 Stages

You orchestrate the complete lifecycle of a new Indonesian regulation across all
4 Bali Zero ground-truth surfaces. This is the **canonical** way to add legal
documents — never short-circuit any stage, the gaps create exactly the kind of
inconsistencies that produced the KEP-37/PJ/2026 hallucination saga.

## Identity

- **Owner**: Antonello (Bali Zero). Italian conversation, English logs.
- **Voice**: terse, surgical, no marketing. Treat regulation references as
  immutable strings — never paraphrase a citation.
- **Audience**: future devils-advocate runs (NB ground truth), kita.balizero.com
  chatbot (Qdrant), team manual lookup (Drive PDF), KG-aware queries.

## When to invoke

Trigger this skill when ANY of the following is true:

- User explicitly asks to ingest a regulation
- A devils-advocate report flags `NOT_FOUND_IN_QUERIED` for a regulation
  that subsequent web check confirms IS real (e.g. KEP-55/PJ/2026 case)
- A research file (`~/Desktop/nuzantara/research/`) cites a new regulation
  not yet covered
- Intel scraper drops a new daily regulation into `bz:regulatory.delta.detected`
  event stream
- User mentions a regulation that the system doesn't recognize

**Do NOT invoke** for:

- Hallucinated/non-existent regulations (verify EXISTS first via web search)
- Regional regulations (Pergub Bali, Perda) — these need separate JDIH
  (jdih.baliprov.go.id) handling, not part of national pipeline
- Internal SE (Surat Edaran) circulars not on JDIH — manual review needed

## The 4 ground-truth surfaces

| Surface                                  | Purpose                            | Latency to update      | Failure mode                |
| ---------------------------------------- | ---------------------------------- | ---------------------- | --------------------------- |
| **Drive** `/peraturan/`                  | PDF archive, team manual reference | Minutes                | Out-of-sync sheet           |
| **Spreadsheet** GAP_ANALYSIS             | Inventory + status tracking        | Seconds                | Inventory gaps              |
| **NotebookLM** NB-2/3/4/5/INTEL          | Devils-advocate ground truth       | Minutes (indexing)     | Red-team false negatives    |
| **Qdrant** legal_unified_2026 + semantic | RAG chatbot kita.balizero.com      | Minutes (embed+upsert) | Chatbot says "I don't know" |
| **KG** kg_nodes/kg_edges                 | Graph queries, structured citation | Hours (extraction)     | No relationship navigation  |

Skipping any surface creates an asymmetry. **All 5 stages MUST complete or
the regulation MUST be marked as partial-ingest in the spreadsheet** so future
audits can resume from the correct stage.

---

## Workflow

### Step 0 — Receive input + verify

Input formats accepted:

- `"ingest PMK 81/2024"` (free text)
- `{"reg_code": "PMK 81/2024"}` (from devils-advocate event payload)
- `{"reg_code": "...", "domain": "tax|visa|property|company|regulatory", "url_hint": "..."}`

**FIRST action**: verify regulation EXISTS. Run a web search for the canonical
form on JDIH. If you can't find an authoritative source on:

- `peraturan.go.id`
- `peraturan.bpk.go.id`
- `jdih.kemenkumham.go.id` (now also `kemenimipas.go.id` post-mid-2024 split)
- `jdih.kemenkeu.go.id`
- `jdih.atrbpn.go.id`
- `pajak.go.id` (DJP-specific regs may have 6-12 month JDIH backfill lag)

**STOP** and report `STATUS: regulation_not_verifiable` to user. Do NOT proceed
to ingest a hallucination — that's exactly the failure mode this skill prevents.

If found, capture:

- `reg_code` canonical form (e.g. `PMK-81/2024`, `KEP-55/PJ/2026`)
- `domain` ∈ {tax, visa, property, company, regulatory, labor, environment, fintech, other}
- `official_title` (Bahasa Indonesia, exact)
- `jdih_url` direct link to PDF or HTML detail page
- `priority` ∈ {CRITICAL, HIGH, MEDIUM, LOW} based on Bali Zero service relevance

### Step 1 — Download PDF

Goal: get the official PDF in `~/Desktop/nuzantara/data/source_documents/peraturan/`.

```bash
mkdir -p ~/Desktop/nuzantara/data/source_documents/peraturan/<domain>/
PDF_PATH=~/Desktop/nuzantara/data/source_documents/peraturan/<domain>/<reg_code_safe>.pdf

# Try direct PDF first
curl -sfL -o "$PDF_PATH" "<jdih_pdf_url>" -w "HTTP %{http_code}, size %{size_download}\n"

# If JDIH page is HTML (not direct PDF), use page scrape + find PDF link
# Many JDIH pages have a "Download PDF" button with href pattern like /Download/N/lampiran.pdf
```

Validation:

- File size > 50 KB (smaller = HTML error page disguised as PDF)
- `file "$PDF_PATH"` returns `PDF document` not HTML
- If validation fails, fall back to text extraction from HTML page (`curl ... | python3 strip-html` → save as `.txt`)

If even text fallback fails, mark `STATUS: pdf_unavailable` in spreadsheet
and skip Step 5 (Qdrant ingest needs file, not page reference). Proceed with
NB push using URL-only.

### Step 2 — Upload to Drive

Target: Google Drive folder `peraturan/` under shared Bali Zero folder.

Use service account (Python, not gws CLI which doesn't exist):

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

creds = service_account.Credentials.from_service_account_file(
    "/Users/nuzantara/.nuzantara-drive-sa.json",
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive = build('drive', 'v3', credentials=creds, cache_discovery=False)

# Find or create peraturan/<domain>/ subfolder
# (parent folder ID for Bali Zero shared: lookup via search 'name=peraturan')

media = MediaFileUpload(PDF_PATH, mimetype='application/pdf', resumable=True)
file_meta = {
    'name': f'{reg_code_safe}.pdf',
    'parents': [PERATURAN_FOLDER_ID],  # resolve once, cache in skill state
    'description': f'{reg_code} | {official_title} | JDIH: {jdih_url} | uploaded by regulatory-ingest skill {date}',
}
result = drive.files().create(body=file_meta, media_body=media, fields='id,webViewLink').execute()
DRIVE_FILE_ID = result['id']
DRIVE_URL = result['webViewLink']
```

If the SA doesn't have access to the parent folder, FIRST ensure it via
`drive.permissions().create(...)` with `role=writer, type=user, emailAddress=<SA_EMAIL>`.
SA email is in `~/.nuzantara-drive-sa.json` field `client_email`.

Output: `DRIVE_FILE_ID`, `DRIVE_URL` — needed for Step 3.

### Step 3 — Update spreadsheet GAP_ANALYSIS tab

Spreadsheet ID: `1Je7eAK3ya_P5yY9L_JtnwRzkTDrucnzgZ4PvvWlb2us`
Tab: `GAP_ANALYSIS` (NOT `Sheet1`)

Schema (10 columns, exact order):
`Priority | Category | Regulation Number | Title | Why We Need It | Source URL | Status | On Drive? | In Qdrant? | Notes`

```python
from googleapiclient.discovery import build

sheets = build('sheets', 'v4', credentials=creds, cache_discovery=False)

# Check if reg already exists (idempotency)
result = sheets.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range="GAP_ANALYSIS!C2:C200"
).execute()
existing = [r[0] if r else "" for r in result.get('values', [])]

if reg_code in existing:
    # UPDATE existing row (not append duplicate)
    row_idx = existing.index(reg_code) + 2  # 1-based + header
    update_range = f"GAP_ANALYSIS!G{row_idx}:J{row_idx}"
    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=update_range, valueInputOption="RAW",
        body={"values": [["DOWNLOADED+NB+QDRANT+KG", "YES", "YES", notes]]}
    ).execute()
else:
    # APPEND new row
    new_row = [priority, category, reg_code, title, why, jdih_url,
               "DOWNLOADED+NB+QDRANT+KG", "YES", "YES", notes]
    sheets.spreadsheets().values().append(
        spreadsheetId=SHEET_ID, range="GAP_ANALYSIS!A:J",
        valueInputOption="RAW", body={"values": [new_row]}
    ).execute()
```

Status field convention (semicolon-separated where multiple stages complete):

- `DOWNLOADED` — PDF in Drive, no other stage done
- `DOWNLOADED+NB` — added to NotebookLM
- `DOWNLOADED+NB+QDRANT` — embedded in Qdrant
- `DOWNLOADED+NB+QDRANT+KG` — KG entities extracted (FULL)
- `PDF_UNAVAILABLE+NB` — text-only path, NB has it but no Qdrant
- `PARTIAL_FAILED_<stage>` — partial ingest, needs resume

Notes field MUST include: timestamp, NB source IDs, Qdrant point counts, KG entity counts.

### Step 4 — Push to NotebookLM

Domain → NB UUID map (canonical, also in `~/scripts/eventbus/devils_advocate_runner.py` NB_REGISTRY):

```
tax        → NB-4 (d4b2eedb-9863-4a1a-81ff-a11b0b45d853)
visa       → NB-2 (cff93ab0-813a-42f2-a8de-36987e724271)
property   → NB-5 (d9438180-5e63-4e2a-a473-6061101f6a8d)
company    → NB-3 (933509f9-1561-403d-bd44-4a7a67a36df2)
regulatory → NB-INTEL-Regulation (a17f134e-b9ab-42d9-bfc2-5bbc45165c76)
labor      → NB-3 (also)
```

Ingest method (TWO options, prefer A):

**A) Via URL** — let NotebookLM fetch the JDIH page itself:

```bash
nlm source add <NB_UUID> --url "<jdih_url>"
```

This works for `peraturan.go.id` HTML pages and direct PDF URLs.

**B) Via text paste** (fallback when --url fails on dynamic JSP pages):

```bash
TXT="REGULATION: <official_title> ($reg_code). SOURCE: $jdih_url. CONTENT: $(extract_text_from_pdf $PDF_PATH | head -c 8000)"
nlm source add <NB_UUID> --text "$TXT"
```

Capture the returned `Source ID: <uuid>` — store in spreadsheet Notes for audit.

**Wait 90-120 seconds** before considering NB-indexed (NotebookLM has eventual
consistency; a follow-up devils-advocate query within 60s may still return
NOT_FOUND even when the source is added — see lessons memory
`lessons_devils_advocate_loop_pattern.md`).

After wait, verify:

```bash
nlm batch query --notebooks <NB_UUID> "Does <reg_code> exist? Reply YES or NO."
```

If NO, retry source add (sometimes the API silently swallows the upload).

### Step 5 — Qdrant embed + upsert

Target collection (canonical):

- All law types → `legal_unified_2026` (the unified hybrid collection)
- Domain-specific overlays still go through `LegalIngestionService`
  which reads the collection from constructor

The pipeline reuses the existing `LegalIngestionService` (NEVER reimplement
the chunker / embedder / BM25 vectorizer — they are tested and tuned).

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
DATABASE_URL="postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable" \
PYTHONPATH=. python3 << 'EOF'
import asyncio
from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

async def main():
    service = LegalIngestionService(collection_name="legal_unified_2026")
    result = await service.ingest_legal_document(
        file_path="<PDF_PATH>",
        title="<official_title> (<reg_code>)",
        category="<domain>",  # tax | visa | property | company | regulatory
    )
    print(f"Ingested: {result}")

asyncio.run(main())
EOF
```

What this does internally (4-stage):

1. **Clean** raw PDF text (`LegalCleaner`)
2. **Extract metadata** (title, articles, dates) (`LegalMetadataExtractor`)
3. **Parse structure** (BAB, Pasal, Ayat, Lampiran) (`LegalStructureParser`)
4. **Chunk** semantic preserve-structure (`LegalChunker`)
5. Generate embeddings: `text-embedding-3-small` (1536 dims) — **FROZEN**
6. Generate BM25 sparse vectors (`BM25Vectorizer`)
7. Upsert to Qdrant collection with hybrid (dense + sparse) vectors
8. **Hierarchical indexer** also creates aggregate "BAB" / "Pasal" parent chunks

**DO NOT bypass `LegalIngestionService`** even if you "just want to add 1 chunk".
The hybrid sparse+dense schema is non-trivial — manual upsert without BM25
breaks the search pipeline.

Output validation:

```bash
curl -sf "$QDRANT_URL/collections/legal_unified_2026" -H "api-key: $QDRANT_API_KEY" | jq '.result.points_count'
# Should be N+ (where N was previous count + chunks_from_new_doc)
```

If the collection doesn't exist yet (rare, but possible for new domains):
service auto-creates it with hybrid config.

### Step 6 — KG entity extraction

The Knowledge Graph stores regulation → article → entity → relationship triples
in PostgreSQL `kg_nodes` + `kg_edges` tables. This enables structured queries
like "show me all KITAS-related obligations from Permenkumham 22/2023".

**Note**: KG extraction is currently **disabled by default** in `LegalIngestionService`
(`self.kg_enabled = False`) due to OOM risk on 2GB Fly machine. This skill
runs KG extraction LOCALLY on Pro (which has 48GB RAM, no OOM concern).

```bash
cd ~/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate
DATABASE_URL="postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable" \
OPENAI_API_KEY="<from .env>" \
PYTHONPATH=. python3 scripts/kg_incremental_extraction.py --collection legal_unified_2026 --limit 200
```

The script is incremental: only processes chunks NOT yet in `kg_nodes`. Safe
to re-run; idempotent.

Validation:

```bash
psql "$DATABASE_URL" -c "
SELECT COUNT(*) AS new_nodes
FROM kg_nodes
WHERE source_collection = 'legal_unified_2026'
  AND created_at > NOW() - INTERVAL '10 minutes';"
```

Expected: nodes_count = roughly 5-30 entities per regulation document.

### Step 7 — Update spreadsheet status to FULL

After all 5 stages succeed, update the spreadsheet row with status
`DOWNLOADED+NB+QDRANT+KG`, In Qdrant=YES, with full notes:

```
PDF: <DRIVE_URL> | NB-X source: <SOURCE_ID> | Qdrant: <N> chunks in legal_unified_2026 | KG: <M> entities/<P> edges | Ingested: <ISO timestamp>
```

### Step 8 — Final report to user

```
✅ REGULATORY INGEST COMPLETE: <reg_code>

Stages:
  ✓ Step 1 PDF download:   <PDF_PATH> (<filesize> bytes)
  ✓ Step 2 Drive upload:   <DRIVE_URL>
  ✓ Step 3 Spreadsheet:    GAP_ANALYSIS row <N> updated
  ✓ Step 4 NotebookLM:     NB-<X> source <ID> (verified after 120s wait)
  ✓ Step 5 Qdrant:         <chunks> chunks in legal_unified_2026 (semantic + BM25)
  ✓ Step 6 KG:             <entities> entities, <edges> edges in PostgreSQL

Total time: <elapsed>
Cost: $0 (NB free + Qdrant prepaid + KG GPT-4o-mini ~$0.02 for entity extraction)

Now reachable by:
  - Devils-advocate red-team via NB-<X>
  - kita.balizero.com chatbot via Qdrant RAG
  - Team manual lookup via Drive PDF
  - Graph queries via PostgreSQL kg_nodes
```

---

## Hard rules

1. **Verify EXISTS before ingest**. The KEP-37/PJ/2026 saga (4 hallucinated
   KEPs ingested as "real" via WebSearch summary chain) cost 7 devils-advocate
   passes to unwind. Web-verify against JDIH FIRST.
2. **All 5 stages or none**. Partial ingest creates inventory drift.
   If a stage fails, mark `PARTIAL_FAILED_<stage>` in spreadsheet so resume
   is unambiguous.
3. **Idempotent**. Re-running on the same regulation must not duplicate
   Drive files (search by title first), spreadsheet rows (search column C),
   Qdrant chunks (chunker dedupes by content_hash), KG nodes (incremental
   extraction skips processed).
4. **Embedding model FROZEN**: `text-embedding-3-small` (1536 dims). Never
   change — would invalidate 100k+ existing vectors per CLAUDE.md.
5. **No Anthropic API key**. KG extraction uses OpenAI gpt-4o-mini (~$0.02/run).
   Devils-advocate red-team uses DeepSeek v4-pro ($0.013/run). Both authorized.
6. **PDF size > 50 KB**. Smaller = likely HTML error page. Validate with
   `file` command.
7. **NotebookLM eventual consistency**: wait 90-120s after `nlm source add`
   before assuming the source is searchable. Cache invalidation in Redis
   (`da:nb_reg:<canonical>`) needed if DA cache is hot.
8. **Rate limits**: NotebookLM free tier ~30 sources/hour. Qdrant Cloud
   no specific limit. OpenAI gpt-4o-mini ~5k req/min.

## Failure modes

| Failure                                                | Recovery                                                                                        |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| JDIH page 403/404                                      | Mark `regulation_not_verifiable`, ask user for alt source                                       |
| PDF download fails                                     | Try text fallback; if also fails, NB-only path                                                  |
| Drive upload fails (quota)                             | Retry once; if still fails, write to local `~/Desktop/nuzantara/data/peraturan/` for later sync |
| Spreadsheet append fails                               | Check SA permissions on sheet; manual edit as fallback                                          |
| NB source add fails                                    | Wait 60s + retry; check `nlm doctor`                                                            |
| Qdrant upsert fails                                    | Check `LegalIngestionService` logs; chunks may be empty (PDF parse failed)                      |
| KG extraction OOM                                      | Reduce `--limit` flag; or split file into article-level extraction                              |
| All 5 succeed but devils-advocate still says NOT_FOUND | Wait 5 min for NB indexing + invalidate Redis cache `da:nb_reg:<canonical>`                     |

## Reference resources

- `~/scripts/eventbus/devils_advocate_runner.py` — NB_REGISTRY canonical UUID map
- `~/Desktop/nuzantara/apps/backend-rag/scripts/ingest_t0_regulations.py` — reference ingest script
- `~/Desktop/nuzantara/apps/backend-rag/scripts/kg_incremental_extraction.py` — KG extraction
- `~/Desktop/nuzantara/apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py` — main pipeline
- Spreadsheet GAP_ANALYSIS: `https://docs.google.com/spreadsheets/d/1Je7eAK3ya_P5yY9L_JtnwRzkTDrucnzgZ4PvvWlb2us/edit`
- Lesson `lessons_devils_advocate_loop_pattern.md` — why 90s NB wait matters
- CLAUDE.md §16 (Research Capture) — adjacent convention for non-regulatory docs
- `infra/eventbus/nb-population-batch.sh.example` — reference for batch NB push
