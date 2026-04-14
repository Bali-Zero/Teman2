# GARUDA Indexer — Operations Runbook

**System:** Mata Garuda Layer 4.5 — Curator Agent (Sprint 5.1)
**Last updated:** 2026-04-14
**Owner:** Zero / Bali Zero AI Team

## Overview

The GARUDA indexer is a daily incremental indexer that reads files from the
`GARUDA/` Google Drive folder and indexes them into:

- Qdrant collection `garuda_assets` (1536-dim vector search)
- PostgreSQL table `garuda_index` (metadata + full-text)

## Architecture

```
GARUDA Drive folder (changes.list API)
    ↓ Drive I/O semaphore (4 concurrent)
Content Extractor (PDF/Image/Video/Audio)
    ↓ Extract semaphore (2 concurrent)
DLP Guard (regex + LLM)
    ↓
Content Hash Dedup (Postgres lookup)
    ↓
OpenAI Embedder (text-embedding-3-small)
    ↓ Embed semaphore (2 concurrent)
Qdrant Upsert (FIRST — atomic order)
    ↓
Postgres Commit (ONLY after Qdrant success)
```

## GARUDA Folder Structure

| Folder        | Drive ID                          | Category     |
| ------------- | --------------------------------- | ------------ |
| GARUDA (root) | 1xjkBpgic3tZl3_K1u7vy-qJpw7XzpIYN | —            |
| photos/       | 1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq | photos       |
| videos/       | 1QZ6hnEqUAxIwhz6yhWeXh6m3QsgFnJ6G | videos       |
| audio/        | 1CX2K-MtRQVMqDwlbcT9gLTGf4mGmGVh3 | audio        |
| intelligence/ | 1n3VjN-YZGGH-6-yByxIi0rLGxi4iTDu1 | intelligence |
| drafts/       | 1b7ERuRssLPAxKYHtAhv2Kx-G81ot0Ulb | drafts       |
| research/     | 18E-rHjO94JFqao1xMCoA2mmy4oK9Waw7 | research     |
| published/    | 1dX87C514aOZO82NTxl8meHiiO3dhIJNl | published    |

## Cron Schedule

| Job            | Schedule (UTC) | WITA      | Description             |
| -------------- | -------------- | --------- | ----------------------- |
| garuda-indexer | 30 20 \* \* \* | 04:30     | Daily incremental index |
| garuda-gc      | 0 21 \* \* 0   | 05:00 Sun | Weekly tombstone GC     |

## Environment Variables

| Variable                      | Required | Description                                             |
| ----------------------------- | -------- | ------------------------------------------------------- |
| DATABASE_URL                  | ✅       | PostgreSQL connection string                            |
| QDRANT_URL                    | ✅       | Qdrant endpoint URL                                     |
| QDRANT_API_KEY                | ✅       | Qdrant API key                                          |
| OPENAI_API_KEY                | ✅       | OpenAI embeddings API key                               |
| GOOGLE_DRIVE_CREDENTIALS_FILE | ✅       | Path to OAuth2 credentials JSON                         |
| TELEGRAM_BOT_TOKEN            | ✅       | Bot token for CRITICAL alerts                           |
| TELEGRAM_OWNER_CHAT_ID        | ✅       | Chat ID for CRITICAL alerts                             |
| CURATOR_BATCH_SIZE            | ⚙️       | Files per night (default: 50)                           |
| EMBED_CACHE_DIR               | ⚙️       | Embedding disk cache (default: /tmp/garuda_embed_cache) |
| OLLAMA_BASE_URL               | ⚙️       | Ollama endpoint (default: http://localhost:11434)       |

## Daily Operations

### Check last run status

```sql
SELECT worker_name, last_run_completed_at, files_indexed_last_run,
       files_indexed_total, consecutive_failures, last_error
FROM garuda_indexer_state;
```

### Check quarantined files (DLP)

```sql
SELECT file_id, name, quarantine_reason, indexed_at
FROM garuda_index
WHERE quarantined = TRUE
ORDER BY indexed_at DESC;
```

### Check indexed files today

```sql
SELECT category, COUNT(*) as files, MAX(indexed_at) as last_indexed
FROM garuda_index
WHERE indexed_at > NOW() - INTERVAL '24 hours'
  AND archived = FALSE
GROUP BY category
ORDER BY files DESC;
```

### Check Qdrant collection

```bash
# From any machine with Qdrant access:
curl -H "api-key: $QDRANT_API_KEY" \
  "$QDRANT_URL/collections/garuda_assets" | jq '.result.points_count'
```

## Manual Run

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/zantara-media
source .venv/bin/activate

# Normal run
garuda-indexer

# Verbose run
garuda-indexer --verbose

# Dry run (no real ops)
garuda-indexer --dry-run

# Bootstrap Qdrant collection (first time only)
garuda-bootstrap

# Manual GC run
garuda-gc --batch-size 50
```

## Bootstrap (First Time Setup)

1. Apply DB migration:

   ```bash
   cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
   source .venv/bin/activate
   python -c "
   from backend.db.migration_manager import MigrationManager
   import asyncio
   async def run():
       mgr = MigrationManager()
       await mgr.apply_migration('109_garuda_curator')
   asyncio.run(run())
   "
   ```

2. Create Qdrant collection:

   ```bash
   cd /Users/nuzantara/Desktop/nuzantara/apps/zantara-media
   source .venv/bin/activate
   garuda-bootstrap
   ```

3. First run (bookmarks page token):

   ```bash
   garuda-indexer
   # Output: "First run — bookmarking start page token"
   ```

4. Second run (starts actual indexing):
   ```bash
   garuda-indexer --verbose
   ```

## Cron Setup (OpenClaw)

```bash
# Install cron config
cp /Users/nuzantara/Desktop/nuzantara/apps/zantara-media/config/openclaw_cron.yaml \
   ~/.openclaw/crons/garuda_curator.yaml

# Verify
openclaw cron list | grep garuda
```

## Incident Playbook

### CRITICAL: OAuth token expiring

Telegram alert: `⚠️ GARUDA: Google Drive OAuth token expires in N days!`

**Fix:**

1. Visit: https://kita.balizero.com/settings/integrations
2. Click "Re-authorize Google Drive"
3. New token stored in `google_drive_tokens` table

### CRITICAL: 3+ consecutive failures

Telegram alert: `⚠️ GARUDA indexer: N errors in last run`

**Debug:**

```sql
SELECT last_error FROM garuda_indexer_state WHERE worker_name = 'default';
```

Check logs: `~/.openclaw/logs/garuda-indexer-daily.log`

### Split brain (Qdrant ≠ Postgres counts)

Run reconciliation query:

```sql
-- Files in Postgres but potentially missing from Qdrant
SELECT COUNT(*) FROM garuda_index
WHERE archived = FALSE AND quarantined = FALSE;
-- Compare to: Qdrant points count (curl command above)
-- If mismatch > 5: run garuda-gc, then re-run indexer
```

### DLP false positive

If legitimate file was quarantined by mistake:

```sql
-- Clear quarantine flag (requires manual review first)
UPDATE garuda_index
SET quarantined = FALSE, quarantine_reason = NULL
WHERE file_id = '<file_id>';
```

Then re-run indexer so it gets picked up.

## DLP Patterns Monitored

| Pattern          | Regex                                         |
| ---------------- | --------------------------------------------- |
| NIK              | `\b\d{16}\b`                                  |
| KITAS            | `\b\d{2}[A-Z]{2}\d{4,7}\b`                    |
| Passport ID      | `\b[A-Z]\d{7}\b`                              |
| NPWP             | `\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b` |
| Indonesian phone | `\b\+?62[\d\s-]{8,15}\b`                      |
| Email            | standard                                      |

Plus filename triggers: `passport`, `kitas`, `npwp`, `client_`, `invoice`, `contract`, `akta`

## Limits & Constraints

- Max file size: 500MB (larger files skipped)
- Max files/night: 50 (configurable via CURATOR_BATCH_SIZE)
- Embedding model: `text-embedding-3-small` (1536-dim) — NEVER CHANGE (breaks cross-query with balizero_news)
- Vision model: `qwen2.5vl:7b` only (qwen3.5 strips vision weights)
- DLP LLM: `gemma4:26b` local (Ollama) — never cloud for PII data

## Golden Rules (never violate)

1. **Qdrant FIRST, then Postgres** — no split brain
2. **Never read CRM/PERATURAN/CLIENTI/CONTRATTI** Drive folders
3. **Never modify existing Qdrant collections** (balizero_news, etc.)
4. **Never hardcode secrets** — env vars only
5. **DLP runs on every file** — over-quarantine is better than PII leak
6. **Per-file error isolation** — one failure never kills the batch
