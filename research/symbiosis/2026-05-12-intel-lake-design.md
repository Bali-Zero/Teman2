---
date: 2026-05-12
domain: architecture
status: design-approved
authors: Antonello Siano + Claude Opus 4.7 + Codex GPT-5.5 + Gemini 3.1 Pro + DeepSeek Reasoner
client_case: Nuzantara intel pipeline unification
sources: tri-LLM panel + empirical codebase audit
---

# Intel Lake — Unified Intel Pipeline Design

## Problem statement

Nuzantara has **12+ intel/scraping producers** writing to **30+ heterogeneous destinations** (Redis streams, PG tables, JSON files, NotebookLM, Qdrant, MDX files, Telegram, Drive, Google Sheets). Same URL discovered by 4 producers → 4 separate writes, no provenance merge, no global dedup, no central routing logic. WR2 topic-selector reads only Fly staging; NB-INTEL feeder reads only Mata Garuda Redis stream; blog reads only Bali Intel Scraper MDX commits. The 3 worlds don't see each other.

**Goal**: single source of truth (`intel_lake`) where all 12 producers write canonical items, then a rules+LLM router decides per item where to dispatch (blog / WR2 / NB-INTEL / archive / skip).

## Producer inventory (12 verified)

| #   | Producer                    | Path                                                              | Cadence          | Native output                                                                                        |
| --- | --------------------------- | ----------------------------------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------- |
| 1   | Bali Intel Scraper          | `apps/bali-intel-scraper/`                                        | 03:00 WITA daily | Qdrant `intel_articles`, Fly `/api/intel/staging`, MDX commit, homepage-layout.json gh-api, Telegram |
| 2   | Mata Garuda (24 harvester)  | `apps/mata-garuda/mata_garuda/agents/`                            | launchd various  | Redis streams `garuda:{raw,enriched,alerts,digest,osint,feedback}`, `bridge:outbound`, Telegram      |
| 3   | NLM Deep Research           | `nlm research start` CLI                                          | not active yet   | Direct NB push                                                                                       |
| 4   | imigrasi_monitor            | `~/scripts/cron-agent-python/imigrasi_monitor.py`                 | daily 06:00      | `~/.intel_scraper/incoming/*.json`, Redis dedup set, Telegram                                        |
| 5   | pajak_monitor               | `~/scripts/cron-agent-python/pajak_monitor.py`                    | daily 08:00      | idem                                                                                                 |
| 6   | oss_monitor                 | `~/scripts/cron-agent-python/oss_monitor.py`                      | every 2h 08-22   | Redis hash + Telegram                                                                                |
| 7   | intel_radar                 | `~/scripts/cron-agent-python/intel_radar.py`                      | hourly           | PG `intel_radar_findings` + Redis 7d TTL                                                             |
| 8   | t4_monitor                  | `apps/evaluator/nlm_deep_research/t4_monitor.py`                  | Mar/Gio 18:00    | NB-2 direct via `nlm` CLI                                                                            |
| 9   | yt_monitor                  | `apps/evaluator/nlm_deep_research/yt_monitor.py`                  | scheduled        | NB-2/3/4/5 via `nlm` CLI                                                                             |
| 10  | peraturan_ingestion_trigger | `apps/evaluator/nlm_deep_research/peraturan_ingestion_trigger.py` | scheduled        | Fly `/api/legal/upload`, Drive, NB-6, Sheet                                                          |
| 11  | regulatory-watcher          | `~/scripts/regulatory-watcher-run.sh`                             | daily 07:00      | `research/regulatory/*.json`, Telegram                                                               |
| 12  | fact_checker                | `~/scripts/cron-agent-python/fact_checker.py`                     | on-demand        | `~/.intel_scraper/validation-reports/`                                                               |

## Schema

### `intel_items` (canonical item)

```sql
CREATE TABLE intel_items (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_url   TEXT UNIQUE NOT NULL,
  content_hash    TEXT NOT NULL,                -- sha256(title || ' ' || summary)[:32]
  title           TEXT NOT NULL,
  summary         TEXT,
  source_domain   TEXT NOT NULL,
  language        TEXT,                          -- 'id','en','it', ...
  jurisdiction    TEXT,                          -- 'ID-national','ID-bali', ...
  topic_tags      TEXT[],                        -- ['visa','kitas','permenkumham']
  routing_status  TEXT NOT NULL DEFAULT 'unrouted',
  routing_targets JSONB,                         -- {nb_uuids:[], blog_slug, wr2_draft_id, telegram_chat:''}
  confidence_score REAL CHECK (0 <= confidence_score AND confidence_score <= 1),
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  published_at    TIMESTAMPTZ,
  expires_at      TIMESTAMPTZ,
  raw_payload     JSONB
);
CREATE INDEX idx_intel_items_routing ON intel_items(routing_status) WHERE routing_status = 'unrouted';
CREATE INDEX idx_intel_items_freshness ON intel_items(first_seen_at DESC);
CREATE INDEX idx_intel_items_tags ON intel_items USING GIN(topic_tags);
```

routing_status enum: `unrouted | blog | wr2 | nb-intel | archive | skip | needs_review`

### `intel_observations` (one row per producer-hit)

```sql
CREATE TABLE intel_observations (
  id              BIGSERIAL PRIMARY KEY,
  item_id         UUID NOT NULL REFERENCES intel_items(id) ON DELETE CASCADE,
  producer_name   TEXT NOT NULL,
  observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_payload     JSONB,
  score           REAL
);
CREATE INDEX idx_intel_obs_item ON intel_observations(item_id);
CREATE INDEX idx_intel_obs_producer ON intel_observations(producer_name, observed_at DESC);
```

Multi-producer convergence is preserved: 4 producers seeing the same URL → 1 `intel_items` row + 4 `intel_observations` rows. Trust signal = COUNT(observations) per item.

### Outbox emission

`intel_items` INSERT trigger → channel `intel_lake_event` + `_outbox_id` (reuse `events_outbox` pattern from migration 144/146).

## Producer adapter pattern

Single endpoint: `POST /api/intel/lake/observations`

```json
{
  "producer_name": "intel_radar",
  "canonical_url": "https://imigrasi.go.id/berita/12345",
  "title": "...",
  "summary": "...",
  "source_domain": "imigrasi.go.id",
  "topic_tags": ["visa","kitas"],
  "language": "id",
  "score": 0.85,
  "raw_payload": {...},
  "observed_at": "2026-05-12T17:00:00Z"
}
```

Server logic:

1. URL canonicalization: strip scheme normalize, lowercase host, strip fragment + `utm_*` + `fbclid`
2. UPSERT `intel_items` ON CONFLICT(canonical_url) DO UPDATE SET `last_seen_at`
3. INSERT `intel_observations` always
4. NOTIFY `intel_lake_event` only on `xmax = 0` (new row)

## Router

**Tier 1 — Rules** (Python service on Pro, listens `intel_lake_event`):

```python
RULES = [
  (r"imigrasi\.go\.id|kanwilkemenkumham", "nb-intel", ["1ed02e54-..."]),  # NB-INTEL-Immigration
  (r"pajak\.go\.id|ortax\.org|kemenkeu\.go\.id", "nb-intel", ["7fb12c9c-..."]),
  (r"bkpm\.go\.id|oss\.go\.id|kemendag\.go\.id", "nb-intel", ["a17f134e-..."]),
  (r"arxiv\.org|github\.com|huggingface\.co", "nb-intel", ["dc5d01cd-..."]),
  (r"detik|kompas|tempo|tribunnews|jakartapost", "blog", None),  # press for blog
  # default: needs_review
]
```

Updates `routing_status` + `routing_targets`, then NOTIFY for downstream consumers.

**Tier 2 — LLM** (daily 04:00 WITA, GPT-5.5 via OpenClaw): processes `routing_status='needs_review'` queue, decides routing with structured output, audit trail in `intel_observations.raw_payload->'llm_routing_decision'`.

## Consumer interfaces

| Consumer           | Pre-lake                           | Post-lake                                                            |
| ------------------ | ---------------------------------- | -------------------------------------------------------------------- |
| Blog publisher     | MDX commit from Bali Intel Scraper | `GET /api/intel/lake/ready-for-blog` → MDX commit + UPDATE processed |
| WR2 topic-selector | `/api/intel/staging/pending`       | `GET /api/intel/lake/ready-for-wr2?since=24h`                        |
| nlm_feeder         | XREAD `garuda:enriched`            | XREAD `intel_lake:routed` filter `routing_targets.nb_uuids`          |
| Zantara RAG        | Qdrant + nlm-bridge                | Unchanged (downstream of lake)                                       |
| Telegram alerts    | Direct from each producer          | Subscribe `intel_lake:routed` with `urgency=high` filter             |

## Migration waves

| Wave | Producer                                             | Effort | Rationale                                                                   |
| ---- | ---------------------------------------------------- | ------ | --------------------------------------------------------------------------- |
| 1    | **intel_radar**                                      | 1 day  | Already writes PG with canonical_url + content_hash — schema 80% compatible |
| 2    | **fact_checker + t4_monitor + yt_monitor**           | 1 day  | Low-volume, validate end-to-end flow                                        |
| 3    | **imigrasi/pajak/oss_monitor**                       | 1 day  | Shadow-write 7d, then cut-over                                              |
| 4    | **regulatory-watcher + peraturan_ingestion_trigger** | 2 days | Legal critical — fallback to silos during shadow                            |
| 5    | **Bali Intel Scraper**                               | 3 days | 5 destinations — most complex, last                                         |
| 6    | **Mata Garuda**                                      | 5 days | 24 harvester — bulk adapter via base_worker patch                           |

Each wave: code + migration + shadow-write 7d + validation report + cut-over.

## Failure modes

- **Lake unreachable**: producer writes legacy sink + Redis local outbox `intel_lake:pending` → replay on reconnect (reuse pattern from `events_outbox` migration 144/146)
- **Router crashed**: items stay `routing_status='unrouted'`, accumulation visible in dashboard → consumers don't pick up but no data lost
- **Critical producer never-lose**: `peraturan_ingestion_trigger`, `regulatory-watcher`, Mata Garuda raw → dual-write for first 30 days post-migration

## Retention

- `intel_items`: 180 days full PG
- `intel_observations`: 90 days full + Sunday cold offload to Parquet GCS
- `raw_payload` JSONB: PostgreSQL TOAST natural compression
- Qdrant: only items with `routing_status IN ('blog','nb-intel')` (controlled by downstream consumer)

## Tri-LLM convergence record

3 independent LLMs (Codex GPT-5.5, Gemini 3.1 Pro, DeepSeek Reasoner) plus 1 empirical codebase agent converged on:

- ✅ Postgres primary + Redis stream buffer + Parquet cold
- ✅ URL canonical-hash dedup as primary key
- ✅ Hybrid router (rules-first, LLM for ambiguous)
- ✅ Shadow-write migration path
- ✅ Local spool fallback on lake unreachable

Divergences resolved by empirical evidence:

- **Multi-producer hit**: separate `intel_observations` table (Codex) vs JSONB merge (Gemini/DeepSeek) → Codex wins because the empirical pattern of `intel_validator_log:staging_id` already separates audit from item.
- **Migration first**: Codex says Bali Intel Scraper, DeepSeek says fact_checker — overruled by audit: intel_radar's existing PG schema (`canonical_url` UNIQUE + `content_hash` index from migration 139) is 80% lake-compatible. Wave 1 = intel_radar.
- **Retention**: Codex 180d vs DeepSeek 30d → Codex wins because NB-INTEL Press growth ~30/week implies 1-year backlog is needed for accurate trend detection.

## Open questions for production review

- [ ] OpenClaw GPT-5.5 daily orchestrator: which Pro plist (`com.balizero.intel-lake.router.daily`)?
- [ ] Qdrant downstream collection: reuse `intel_articles` or new `intel_lake_routed`?
- [ ] Telegram alert routing: per-domain rules or single firehose with severity filter?
- [ ] Mata Garuda 24-harvester refactor: patch via base_worker (single change) or per-harvester?
- [ ] Migration 147 PR: required CI checks (E2E Tests + MCP Server Tests + Squawk migration lint)?
