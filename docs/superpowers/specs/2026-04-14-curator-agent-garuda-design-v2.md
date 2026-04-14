# Curator Agent — GARUDA Asset Indexer & Multi-Channel Publisher (v2)

**Status:** Design v2 — Sprint 5 Mata Garuda
**Date:** 2026-04-14 (revised after red team Gemini + Codex review)
**Author:** Zero + Claude Opus 4.6
**Context:** Mata Garuda Layer 4.5 (new)
**Cost target:** $0.20 one-shot OpenAI embeddings, $0/month operational

---

## 0. CHANGES vs v1

This v2 supersedes `2026-04-14-curator-agent-garuda-design.md`. 14 fixes integrated from red team review:

| #   | Fix                                                                                                     | Source             |
| --- | ------------------------------------------------------------------------------------------------------- | ------------------ |
| 1   | Use `text-embedding-3-small` (1536-dim, OpenAI) — $0.20 one-shot — for cross-query with `balizero_news` | Red team Gemini #1 |
| 2   | DLP post-extraction (regex + LLM classifier) for PII detection                                          | Red team Gemini #2 |
| 3   | Cron at **04:30 WITA** + semaphore `pgrep core_guardian`                                                | Red team Gemini #3 |
| 4   | Dedup by `content_hash` SELECT before upsert (handles file copies)                                      | Red team Gemini #4 |
| 5   | Qdrant upsert FIRST, then Postgres commit (no split brain)                                              | Red team Gemini #5 |
| 6   | Migration in `backend/db/migrations_v2/109_garuda_curator.sql` (not legacy `backend/migrations/`)       | Codex #1           |
| 7   | Drive incremental via `changes.list` + `getStartPageToken` (not `modifiedTime`)                         | Codex #2           |
| 8   | `garuda_indexer_state` keyed by `worker_name TEXT PK` + advisory lock                                   | Codex #3           |
| 9   | `apps/zantara-media/` as installable package with `pyproject.toml`                                      | Codex #4           |
| 10  | Async bounded concurrency: Drive 4, extract 2, vision 1, embed 2                                        | Codex #5           |
| 11  | Qdrant `default_segment_number=0`, `full_scan_threshold=30000`                                          | Codex #6           |
| 12  | Tombstone garbage collector weekly (Sunday 05:00)                                                       | Red team #6        |
| 13  | Frame extraction at 15%/50%/85% (not 0/50/100%) or scene detection                                      | Red team #7        |
| 14  | Drop ElevenLabs free tier — use **Google TTS via OAuth** (proven $0 in current ffmpeg pipeline)         | Red team #8        |

---

## 1. PROBLEM (unchanged from v1)

Bali Zero has accumulated significant creative-editorial material. Mata Garuda current design is broadcaster (1→N), but missing is a **curator / assignment desk** that pulls from a magazine and composes per-channel.

---

## 2. SOLUTION

Dedicated GDrive folder `GARUDA/` as single source of truth. Daily incremental indexer (50 files/night, 04:30 WITA). Channel-specific sub-curators query the indexed pool, compose products, publish via existing Channel Agents.

### 2.1 Folder structure (created 2026-04-14)

```
Bali Zero Root (1hkOeV03YM5-sHbQhswYz809jsrnwC0At)
└── GARUDA/                (1xjkBpgic3tZl3_K1u7vy-qJpw7XzpIYN)
    ├── photos/            (1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq)
    ├── videos/            (1QZ6hnEqUAxIwhz6yhWeXh6m3QsgFnJ6G)
    ├── audio/             (1CX2K-MtRQVMqDwlbcT9gLTGf4mGmGVh3)
    ├── intelligence/      (1n3VjN-YZGGH-6-yByxIi0rLGxi4iTDu1)
    ├── drafts/            (1b7ERuRssLPAxKYHtAhv2Kx-G81ot0Ulb)
    ├── research/          (18E-rHjO94JFqao1xMCoA2mmy4oK9Waw7)
    └── published/         (1dX87C514aOZO82NTxl8meHiiO3dhIJNl)
```

**Hard rule:** indexer only reads files inside GARUDA/ tree. Never CRM, PERATURAN, CLIENTI, CONTRATTI.

### 2.2 Architecture layer

```
Layer 4 Analysis    → garuda:digest stream
        │
        ▼
Layer 4.5 CURATION (new)
   ├── garuda_indexer        (04:30 daily, async bounded, 50 files/night)
   ├── garuda_dlp            (post-extraction PII guard)
   ├── garuda_gc             (Sunday 05:00 tombstone collector)
   ├── asset_pool_builder    (08:00 daily)
   ├── channel_planner       (08:15)
   ├── curator_per_channel   (08:30, loop per channel)
   └── curation_tracker      (publish history, fitness, GENOME)
        │
        ▼
Layer 5 Distribution → existing Channel Agents
```

---

## 3. COMPONENTS (revised)

### 3.1 `garuda_indexer` — Daily incremental indexer

**Location:** `apps/zantara-media/` (installable package, pyproject.toml)
**Runtime:** Python 3.11 + asyncio + bounded executors
**Scheduling:** OpenClaw cron `04:30 WITA daily`
**Throughput cap:** 50 files/night (configurable via env)
**Drive cursor:** `changes.list` API (not `modifiedTime`)
**Concurrency:** Drive I/O 4, extract 2, vision 1, embed 2

**Pre-flight check (before running):**

```bash
# Refuse to start if Core Guardian is active
if pgrep -f "core_guardian" > /dev/null; then
    log "Core Guardian active, deferring indexer run"
    exit 0
fi

# Refuse if disk free < 5GB
df -BG /tmp | awk 'NR==2 {if ($4+0 < 5) exit 1}' || exit 1
```

**Async flow (revised):**

```python
# apps/zantara-media/zantara_media/indexer/orchestrator.py
import asyncio
from contextlib import asynccontextmanager

CONCURRENCY = {
    "drive_io": 4,
    "extract": 2,
    "vision": 1,    # qwen2.5vl is heavy — single concurrent
    "embed": 2,
}

async def run_indexer(worker_name: str = "default"):
    # 1. Acquire advisory lock (PostgreSQL)
    async with pg_advisory_lock(f"garuda_indexer:{worker_name}"):
        state = await load_state(worker_name)

        # 2. Get start page token if first run
        if state.last_change_page_token is None:
            token = await drive.changes.getStartPageToken()
            state.last_change_page_token = token
            await save_state(state)
            return  # First run just bookmarks, no work

        # 3. Stream changes since last token
        garuda_files_processed = 0
        next_token = state.last_change_page_token

        async for change in drive_changes_stream(next_token):
            if garuda_files_processed >= 50:
                break

            file = change.file
            # Filter: only files under GARUDA/ tree
            if not is_under_garuda(file):
                continue

            # Handle tombstones (Drive deletion)
            if change.removed or file.trashed:
                await mark_archived(file.id)
                continue

            # Skip if already up-to-date (by Drive version)
            existing = await pg.fetch_one(
                "SELECT drive_version FROM garuda_index WHERE file_id = $1",
                file.id,
            )
            if existing and existing.drive_version == file.version:
                continue

            # Process file
            await index_file_safe(file)
            garuda_files_processed += 1
            next_token = change.next_page_token or next_token

        # 4. Update cursor + save state
        state.last_change_page_token = next_token
        state.files_indexed_last_run = garuda_files_processed
        state.consecutive_failures = 0
        state.last_run_completed_at = now()
        await save_state(state)
```

**Per-file pipeline (with DLP guard + transactional order):**

```python
async def index_file_safe(file):
    try:
        # 1. Download (with size cap 500MB)
        if file.size > 500_000_000:
            await log_skip(file.id, reason="too_large")
            return

        # 2. Type-specific extraction
        async with extract_semaphore:  # max 2 concurrent
            text, metadata = await extract_content(file)

        # 3. DLP guard — quarantine if PII detected
        dlp_result = await dlp_check(text, file.name)
        if dlp_result.has_pii:
            await quarantine(file.id, dlp_result)
            await alert_telegram(
                f"⚠️ PII detected in GARUDA: {file.name}\n"
                f"Patterns: {dlp_result.patterns}\n"
                f"Quarantined."
            )
            return

        # 4. Compute content hash for dedup
        content_hash = sha256(file.id + text[:1000])

        # 5. CRITICAL: dedup BEFORE insert (handles file copies)
        existing_by_hash = await pg.fetch_one(
            "SELECT file_id FROM garuda_index WHERE content_hash = $1 AND file_id != $2",
            content_hash, file.id,
        )
        if existing_by_hash:
            await log_duplicate(file.id, master_id=existing_by_hash.file_id)
            return  # Skip — already indexed under different file_id

        # 6. Generate embedding via OpenAI text-embedding-3-small
        async with embed_semaphore:
            embedding = await openai_embed(text[:8000], model="text-embedding-3-small")

        # 7. Vision/audio handlers (if applicable)
        if file.mime.startswith("image/"):
            async with vision_semaphore:  # max 1
                description = await qwen2_5vl_describe(file)
                # Re-embed using description for image-as-text retrieval
                embedding = await openai_embed(description, model="text-embedding-3-small")

        # 8. ATOMIC: Qdrant FIRST, then Postgres
        await qdrant.upsert(
            collection_name="garuda_assets",
            points=[PointStruct(
                id=file.id,
                vector=embedding,
                payload={
                    "file_id": file.id,
                    "category": guess_category(file.parent_id),
                    "mime": file.mime,
                    "name": file.name,
                    "path": file.path,
                    "description": (description or text)[:500],
                    "tags": auto_tag(text),
                    "modified_at": file.modified_time.isoformat(),
                    "drive_version": file.version,
                    "content_hash": content_hash,
                },
            )],
        )

        # 9. Only after Qdrant success: write to Postgres
        await pg.execute("""
            INSERT INTO garuda_index (...) VALUES (...)
            ON CONFLICT (file_id) DO UPDATE SET
                drive_version = EXCLUDED.drive_version,
                modified_at = EXCLUDED.modified_at,
                indexed_at = NOW(),
                content_hash = EXCLUDED.content_hash
        """, ...)

    except Exception as e:
        await log_error(file.id, error=str(e))
        # Don't raise — single file failure shouldn't kill the batch
```

### 3.2 DLP (Data Loss Prevention) module

**Location:** `apps/zantara-media/zantara_media/security/dlp.py`

```python
import re

INDONESIAN_PII_PATTERNS = {
    "NIK": r"\b\d{16}\b",                          # Indonesian national ID
    "KITAS_NUMBER": r"\b\d{2}[A-Z]{2}\d{4,7}\b",   # KITAS format
    "PASSPORT_ID": r"\b[A-Z]\d{7}\b",              # Indonesian passport
    "NPWP": r"\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b",  # Tax ID
    "BANK_ACCOUNT_RUPIAH": r"\bIDR\s*\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "PHONE_INDONESIAN": r"\b\+?62[\d\s-]{8,15}\b",
}

# Filename triggers (extra layer)
FILENAME_TRIGGERS = ["passport", "kitas", "npwp", "client_", "invoice", "contract", "akta"]

@dataclass
class DLPResult:
    has_pii: bool
    patterns: list[str]
    confidence: float

async def dlp_check(text: str, filename: str) -> DLPResult:
    found = []

    # Layer 1: filename triggers
    name_lower = filename.lower()
    for trigger in FILENAME_TRIGGERS:
        if trigger in name_lower:
            found.append(f"FILENAME:{trigger}")

    # Layer 2: regex patterns
    for label, pattern in INDONESIAN_PII_PATTERNS.items():
        if re.search(pattern, text):
            found.append(label)

    # Layer 3: LLM classifier (Ollama gemma4 — cheap, local)
    if not found:
        # Only call LLM if regex passed (saves CPU)
        llm_verdict = await ollama_classify_pii(text[:2000])
        if llm_verdict.contains_pii:
            found.append(f"LLM:{llm_verdict.reason}")

    return DLPResult(
        has_pii=bool(found),
        patterns=found,
        confidence=1.0 if len(found) > 1 else 0.7,
    )
```

### 3.3 PostgreSQL schema (revised)

**Location:** `apps/backend-rag/backend/db/migrations_v2/109_garuda_curator.sql` (NOT legacy `backend/migrations/`!)

```sql
-- 109_garuda_curator.sql
-- Curator Agent Sprint 5.1 — GARUDA indexer foundation

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Master index of all GARUDA files
CREATE TABLE IF NOT EXISTS garuda_index (
    file_id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(512) NOT NULL,
    path TEXT NOT NULL,
    parent_folder VARCHAR(128) NOT NULL,
    category VARCHAR(32) NOT NULL CHECK (category IN (
        'photos','videos','audio','intelligence','drafts','research','published'
    )),
    mime_type VARCHAR(128) NOT NULL,
    size_bytes BIGINT NOT NULL,
    modified_at TIMESTAMPTZ NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drive_version BIGINT,                          -- Drive's revision number
    extracted_text TEXT,
    description TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    content_hash VARCHAR(64),                      -- SHA-256
    archived BOOLEAN DEFAULT FALSE,
    trashed BOOLEAN DEFAULT FALSE,
    quarantined BOOLEAN DEFAULT FALSE,             -- Set by DLP
    quarantine_reason JSONB,                       -- DLP details
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_garuda_index_active_by_cat
    ON garuda_index(category, modified_at DESC)
    WHERE archived = FALSE AND trashed = FALSE AND quarantined = FALSE;

CREATE INDEX IF NOT EXISTS idx_garuda_index_content_hash
    ON garuda_index(content_hash)
    WHERE content_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_garuda_index_quarantined
    ON garuda_index(quarantined)
    WHERE quarantined = TRUE;

-- Publication history across all channels
CREATE TABLE IF NOT EXISTS publication_history (
    publication_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(32) NOT NULL CHECK (channel IN (
        'tg_zero','tg_channel','ig_carousel','ig_video','ig_story',
        'newsletter','blog','x_thread','linkedin','whatsapp_broadcast'
    )),
    topic VARCHAR(512) NOT NULL,
    title TEXT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    external_id VARCHAR(256),
    external_url TEXT,
    language VARCHAR(8) DEFAULT 'en',
    engagement_metrics JSONB DEFAULT '{}'::jsonb,
    curator_agent VARCHAR(64) NOT NULL,
    autonomy_level VARCHAR(4) NOT NULL CHECK (autonomy_level IN ('L1','L2','L3','L4')),
    approved_by VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_pubhist_channel_time
    ON publication_history(channel, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_pubhist_topic
    ON publication_history(topic);

-- Bridge table: which assets used in which publication (better than JSONB)
CREATE TABLE IF NOT EXISTS publication_assets (
    publication_id UUID NOT NULL REFERENCES publication_history(publication_id) ON DELETE CASCADE,
    file_id VARCHAR(128) NOT NULL REFERENCES garuda_index(file_id) ON DELETE CASCADE,
    role VARCHAR(32),                              -- cover, body, accent, etc.
    position INT,                                  -- order in carousel/video
    PRIMARY KEY (publication_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_pubassets_file
    ON publication_assets(file_id);

-- Indexer state — keyed by worker_name (supports multiple workers)
CREATE TABLE IF NOT EXISTS garuda_indexer_state (
    worker_name TEXT PRIMARY KEY,
    last_change_page_token TEXT,
    last_run_started_at TIMESTAMPTZ,
    last_run_completed_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,                  -- Soft lock; advisory_lock is hard lock
    files_indexed_total BIGINT DEFAULT 0,
    files_indexed_last_run INT DEFAULT 0,
    consecutive_failures INT DEFAULT 0,
    mode VARCHAR(16) DEFAULT 'daily',              -- daily | catch_up
    last_error JSONB,
    config JSONB DEFAULT '{}'::jsonb               -- Per-worker overrides
);

INSERT INTO garuda_indexer_state (worker_name, mode)
VALUES ('default', 'daily')
ON CONFLICT (worker_name) DO NOTHING;
```

### 3.4 Qdrant collection (revised config)

**Collection:** `garuda_assets` on `nuzantara-qdrant` Fly.io (not local — keep consistency with existing infra)
**Dimensions:** **1536** (text-embedding-3-small) — compatible with `balizero_news`, `bali_zero_pricing_hybrid`, etc.

```python
from qdrant_client.models import (
    VectorParams, Distance, HnswConfigDiff, OptimizersConfigDiff,
    PayloadSchemaType, KeywordIndexParams,
)

await qdrant.create_collection(
    collection_name="garuda_assets",
    vectors_config=VectorParams(
        size=1536,                                 # text-embedding-3-small
        distance=Distance.COSINE,
    ),
    hnsw_config=HnswConfigDiff(
        m=16,
        ef_construct=100,
        full_scan_threshold=30000,                 # brute-force is faster under 30k
    ),
    optimizers_config=OptimizersConfigDiff(
        default_segment_number=0,                  # let Qdrant decide
        indexing_threshold=30000,
    ),
)

# Payload indexes for fast filter queries
for field, schema_type in [
    ("category", PayloadSchemaType.KEYWORD),
    ("mime", PayloadSchemaType.KEYWORD),
    ("modified_at", PayloadSchemaType.DATETIME),
    ("parent_folder", PayloadSchemaType.KEYWORD),
    ("archived", PayloadSchemaType.BOOL),
    ("quarantined", PayloadSchemaType.BOOL),
]:
    await qdrant.create_payload_index(
        collection_name="garuda_assets",
        field_name=field,
        field_schema=schema_type,
    )
```

### 3.5 Tombstone garbage collector

**Location:** `apps/zantara-media/zantara_media/maintenance/gc.py`
**Schedule:** Sunday 05:00 WITA
**Purpose:** Catch files deleted on Drive that the daily indexer's `changes.list` may have missed (rare but happens with permission issues, account changes)

```python
async def run_gc():
    """Sweep through garuda_index, verify each file still exists on Drive."""
    cursor = "BEGIN"
    batch_size = 100
    archived_count = 0

    async for batch in pg.fetch_batches(
        "SELECT file_id FROM garuda_index WHERE archived = FALSE LIMIT $1 OFFSET $2",
        batch_size,
    ):
        for file_id in batch:
            try:
                await drive.files.get(file_id, fields="id,trashed")
            except HttpError as e:
                if e.resp.status == 404:
                    await pg.execute(
                        "UPDATE garuda_index SET archived = TRUE, modified_at = NOW() WHERE file_id = $1",
                        file_id,
                    )
                    await qdrant.set_payload(
                        collection_name="garuda_assets",
                        points=[file_id],
                        payload={"archived": True},
                    )
                    archived_count += 1

    await alert_telegram(f"🧹 GARUDA GC: {archived_count} files archived (deleted on Drive)")
```

### 3.6 Frame extraction (revised)

```python
def extract_video_frames(video_path: Path) -> list[Path]:
    """Extract 3 representative frames at 15%, 50%, 85% (avoids black intro/outro)."""
    duration = ffprobe_duration(video_path)
    timestamps = [duration * 0.15, duration * 0.5, duration * 0.85]

    frames = []
    for i, ts in enumerate(timestamps):
        out = video_path.with_suffix(f".frame_{i}.jpg")
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
            "-frames:v", "1", "-q:v", "2", str(out),
        ], check=True, capture_output=True)
        frames.append(out)

    return frames
```

### 3.7 TTS strategy (revised: drop ElevenLabs, use Google TTS OAuth)

**Location:** `apps/zantara-media/zantara_media/voiceover/tts.py`

Already proven $0 in current ffmpeg pipeline (`/tmp/carousel_bali_sea/gen_voiceover.py`).

```python
async def generate_voiceover(text: str, voice: str = "en-US-Studio-O") -> Path:
    """Generate TTS via Google Cloud TTS OAuth (free tier 1M chars/month)."""
    token = await get_gcloud_oauth_token()
    response = await httpx.post(
        "https://texttospeech.googleapis.com/v1/text:synthesize",
        headers={
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": "nuzantara",
            "Content-Type": "application/json",
        },
        json={
            "input": {"text": text},
            "voice": {"languageCode": "en-US", "name": voice},
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": 0.95,
                "pitch": -1.0,
                "effectsProfileId": ["headphone-class-device"],
            },
        },
    )
    audio_b64 = response.json()["audioContent"]
    out = Path(tempfile.mktemp(suffix=".mp3"))
    out.write_bytes(base64.b64decode(audio_b64))
    return out
```

For higher quality/IT/ID voices: ElevenLabs free tier is too small (10k chars/mo). If needed in future, allocate budget L4 decision.

### 3.8 Selection scoring (revised — anti filter-bubble)

```python
import random

EPSILON = 0.15  # 15% exploration rate (epsilon-greedy)

def score_asset(asset, channel, topic) -> float:
    quality      = asset.quality_score
    freshness    = exp(-age_hours(asset) / channel.tau)
    relevance    = cosine(asset.embedding, topic_embedding)
    diversity    = 1 - similarity_to_recent_publications(asset)
    engagement   = asset.engagement_score or 0.5
    audience_fit = audience_match(asset, channel.audience)

    return (
        0.25 * quality +
        0.20 * freshness +
        0.20 * relevance +
        0.15 * diversity +
        0.10 * engagement +
        0.10 * audience_fit
    )

def select_assets(candidates, channel, topic, top_n: int = 8) -> list:
    """Epsilon-greedy: 85% scored, 15% random exploration."""
    if random.random() < EPSILON:
        # Exploration: pick top-3 by score, fill remaining with random unseen
        scored = sorted(candidates, key=lambda c: score_asset(c, channel, topic), reverse=True)
        return scored[:3] + random.sample(candidates[3:], min(top_n - 3, len(candidates) - 3))
    else:
        # Exploitation: pure score
        return sorted(candidates, key=lambda c: score_asset(c, channel, topic), reverse=True)[:top_n]
```

### 3.9 Package structure (revised)

```
apps/zantara-media/
├── pyproject.toml                          # Installable package
├── README.md
├── zantara_media/                          # Package root
│   ├── __init__.py
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── orchestrator.py                 # Main async loop
│   │   ├── drive_client.py                 # changes.list wrapper
│   │   ├── handlers/
│   │   │   ├── pdf_handler.py
│   │   │   ├── image_handler.py
│   │   │   ├── video_handler.py
│   │   │   └── audio_handler.py
│   │   ├── embedder.py                     # OpenAI text-embedding-3-small
│   │   ├── qdrant_writer.py
│   │   └── postgres_writer.py
│   ├── security/
│   │   └── dlp.py                          # PII detection
│   ├── maintenance/
│   │   ├── gc.py                           # Tombstone collector
│   │   └── stats.py                        # Dashboard metrics
│   ├── curators/
│   │   ├── __init__.py
│   │   ├── base.py                         # ChannelCurator ABC
│   │   ├── ig_carousel.py
│   │   ├── ig_video.py
│   │   ├── tg_channel.py
│   │   ├── newsletter.py
│   │   ├── blog.py
│   │   ├── linkedin.py
│   │   └── x_thread.py                     # Stub until CRC fix
│   ├── selection/
│   │   ├── pool_builder.py
│   │   ├── scoring.py
│   │   └── selector.py
│   ├── voiceover/
│   │   └── tts.py                          # Google TTS OAuth
│   ├── publication/
│   │   └── tracker.py                      # publication_history writer
│   └── config/
│       └── editorial_calendar.yaml
├── scripts/
│   ├── bootstrap_collection.py             # One-shot Qdrant + payload indexes
│   └── run_initial_catchup.py              # First-time bulk indexing
├── tests/
│   ├── test_dlp.py
│   ├── test_dedup.py
│   ├── test_handlers.py
│   └── test_curator_ig_carousel.py
└── cli/                                    # Entry points exposed via pyproject
    ├── garuda_indexer.py                   # `garuda-indexer` command
    ├── garuda_pool_builder.py              # `garuda-pool-builder`
    └── garuda_gc.py                        # `garuda-gc`
```

`pyproject.toml`:

```toml
[project]
name = "zantara-media"
version = "0.1.0"
dependencies = [
    "asyncio",
    "asyncpg",
    "qdrant-client",
    "openai",
    "google-api-python-client",
    "google-auth-httplib2",
    "google-auth-oauthlib",
    "httpx",
    "ollama",
    "pypdf",
    "pytesseract",
    "openai-whisper",
    "pillow",
    "ffmpeg-python",
]

[project.scripts]
garuda-indexer = "zantara_media.cli.garuda_indexer:main"
garuda-pool-builder = "zantara_media.cli.garuda_pool_builder:main"
garuda-gc = "zantara_media.cli.garuda_gc:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

---

## 4. TOOLING (revised)

| Purpose                        | Tool                                             | Cost                                     |
| ------------------------------ | ------------------------------------------------ | ---------------------------------------- |
| Embeddings text+images-as-text | **OpenAI `text-embedding-3-small`** (1536-dim)   | **$0.20 one-shot, $0.05/mo incremental** |
| Image description              | Ollama `qwen2.5vl:7b`                            | $0 local                                 |
| Video frame description        | ffmpeg + qwen2.5vl                               | $0 local                                 |
| Audio transcription            | Whisper `medium`                                 | $0 local                                 |
| PDF text                       | pypdf + Tesseract fallback                       | $0 local                                 |
| PII LLM classifier             | Ollama `gemma4:26b`                              | $0 local                                 |
| GDrive metadata + download     | Drive API v3 OAuth                               | $0                                       |
| LLM for selection              | Claude CLI (Max sub) or Ollama gemma4            | $0                                       |
| TTS voiceover                  | **Google TTS via OAuth** (free tier 1M chars/mo) | $0                                       |
| Canva                          | Existing OAuth                                   | $0                                       |
| Newsletter                     | Resend (free <3000 email/mo)                     | $0                                       |
| PostgreSQL                     | `nuzantara-postgres` Fly.io                      | existing                                 |
| Vector DB                      | `nuzantara-qdrant` Fly.io                        | existing                                 |

**Total: $0.20 one-shot + $0.05/month operational.**

---

## 5. BUILD PLAN (revised)

### Sprint 5.1 — Indexer foundation (5-7 days)

**Day 1 — Package scaffold + DB**

- Create `apps/zantara-media/` with `pyproject.toml`
- Write `migrations_v2/109_garuda_curator.sql`
- Test migration locally + on Fly.io postgres staging branch
- Create Qdrant collection `garuda_assets` (1536-dim) with payload indexes

**Day 2 — Drive client + cursor**

- `drive_client.py` with `changes.getStartPageToken` + `changes.list` paging
- Filter `is_under_garuda(file)` (recursive parent check vs root `1xjkBpgic3tZl3_K1u7vy-qJpw7XzpIYN`)
- Tombstone handling
- Mock test: simulate first run, second run, file deletion

**Day 3 — Type handlers + DLP**

- `pdf_handler.py` (pypdf + Tesseract)
- `image_handler.py` (qwen2.5vl async via httpx)
- `video_handler.py` (ffmpeg frames at 15/50/85% + qwen2.5vl)
- `audio_handler.py` (Whisper subprocess)
- `dlp.py` with regex patterns + LLM fallback

**Day 4 — Embedder + writers (atomic order)**

- `embedder.py` (OpenAI text-embedding-3-small with cache)
- `qdrant_writer.py` (upsert FIRST)
- `postgres_writer.py` (commit ONLY after Qdrant success)
- `index_file_safe()` orchestrator with try/except per file

**Day 5 — Orchestrator + concurrency**

- `orchestrator.py` with bounded semaphores (drive 4, extract 2, vision 1, embed 2)
- PostgreSQL advisory lock per worker
- State save/load
- Pre-flight: `pgrep core_guardian` semaphore + disk space check

**Day 6 — CLI + cron + GC**

- `cli/garuda_indexer.py` entry point
- OpenClaw cron config for 04:30 WITA
- `gc.py` weekly Sunday 05:00 collector
- Telegram CRITICAL alerts for OAuth expiry, 3 consecutive failures

**Day 7 — Testing + bootstrap**

- End-to-end test on 20-file sample (manually placed in GARUDA/photos/)
- Verify dedup by content_hash
- Verify DLP quarantine flow
- Run first real batch
- Document in `docs/GARUDA_INDEXER_OPS.md`

### Sprint 5.2 — IG Carousel curator pilot (3-5 days)

_(Same as v1 — see original spec)_

### Sprint 5.3 — Multi-channel expansion (2-3 weeks)

_(Same as v1)_

### Sprint 5.4 — Feedback loop (1-2 weeks)

_(Same as v1)_

---

## 6. RISKS (updated)

| Risk                                                              | Severity    | Mitigation                                                            |
| ----------------------------------------------------------------- | ----------- | --------------------------------------------------------------------- |
| OpenAI API key missing/expired                                    | HIGH        | Use existing `OPENAI_API_KEY` env var + Telegram alert on 401         |
| Drive `changes.list` returns too many non-GARUDA files            | MEDIUM      | Filter aggressively + iterate page tokens until 50 GARUDA files found |
| qwen2.5vl description quality varies                              | MEDIUM      | Fallback to Claude CLI for first 100 critical assets                  |
| Pro M4 thermal throttling under sustained load                    | MEDIUM      | Sleep 5s between heavy ops; cap nightly batch at 50                   |
| PostgreSQL advisory lock not released on crash                    | LOW         | Use `pg_try_advisory_lock` + lease_expires_at fallback                |
| Dedup misses near-duplicates (different size/format same content) | LOW         | Phase 2: perceptual hash for images                                   |
| Catch-up overnight fills disk                                     | MEDIUM      | Stream-process, never cache full file >100MB                          |
| Sensitive content slips DLP                                       | MEDIUM-HIGH | Quarantine + manual review queue + monthly false-negative audit       |

---

## 7. PREREQUISITES STATUS

| Prereq                                       | Status                |
| -------------------------------------------- | --------------------- |
| GARUDA folder + 7 subfolders                 | ✅ created 2026-04-14 |
| Ollama qwen2.5vl:7b                          | ✅ installed          |
| Ollama gemma4:26b                            | ✅ installed          |
| Whisper + Tesseract + ffmpeg-full            | ✅ installed          |
| Drive OAuth token (antonellosiano@gmail.com) | ✅ active             |
| OpenAI API key                               | ⚠️ verify in `.env`   |
| `nuzantara-postgres` access from Pro         | ✅ via DATABASE_URL   |
| `nuzantara-qdrant` access from Pro           | ✅ via QDRANT_URL     |
| Google Cloud TTS API enabled                 | ✅ enabled today      |
| OpenClaw cron infrastructure                 | ✅ existing           |

---

## 8. DELIVERABLES — Sprint 5.1

- [ ] `apps/zantara-media/` installable package
- [ ] Migration `109_garuda_curator.sql` deployed on staging + production
- [ ] `garuda_assets` Qdrant collection live with payload indexes
- [ ] `garuda-indexer` CLI working end-to-end on 20-file test
- [ ] Cron 04:30 WITA active with `pgrep core_guardian` semaphore
- [ ] Sunday GC active
- [ ] DLP quarantine tested with mock NIK pattern
- [ ] Telegram CRITICAL alerts wired
- [ ] First real batch indexed (whatever is in GARUDA/ today)
- [ ] `docs/GARUDA_INDEXER_OPS.md` runbook

---

## 9. REFERENCES

- v1 spec: `docs/superpowers/specs/2026-04-14-curator-agent-garuda-design.md`
- Red team: `ai-dispatch-output/20260414-182719-gemini-redteam-d07b5ef4.md`
- Codex review: in this conversation, Codex CLI run 2026-04-14 18:25
- CLAUDE.md §6: text-embedding-3-small frozen
- CLAUDE.md §14: Drive polling patterns
- Migration loader: `apps/backend-rag/backend/db/migration_manager.py:220`
- Existing pattern (good async): `apps/backend-rag/scripts/ocr_pipeline.py:248`
- Drive API: https://developers.google.com/workspace/drive/api/reference/rest/v3/changes/list
- Qdrant HNSW: https://qdrant.tech/course/essentials/day-2/what-is-hnsw/

---

**End of spec v2.**
