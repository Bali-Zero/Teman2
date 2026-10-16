---
adversarial_review: codex
---

> Historical research retained for traceability. Superseded statements and commands are BLOCKED FOR IMPLEMENTATION. Current evidence is the synthesis addendum, pinned receipt and binding Dux rulings. No production/native action is authorized here.

# UDB Wave 8 — Block B04: Physical Stores and Connections (ANALYSIS)

## 1. Governance, Identity, and Input Pins

- **Campaign ID:** `universal-db-wave8-20261015`
- **Block ID:** `B04` — *Physical stores and connections*
- **Mission Colour / Gear:** `BLUE` / `GEAR 3`
- **Seat Role:** `EXTERNAL PREPARER, NO_DUX` (`PREPARE_ONLY`)
- **Host / Worktree:** `Mini` (`Mini-Pro2`) / `/Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Model / Effort Honesty (`BATTLE.md` §2):**
  - `requested_model`: `Gemini 4 Argon`
  - `requested_effort`: `high`
  - `effective_runtime_model`: `UNOBSERVED` (not self-certified by runtime environment echo)
  - `effective_runtime_effort`: `UNOBSERVED`
  - `session_handle`: `0db3627f-7483-4259-98e1-4bf16babad18`
- **Execution Mode Constraint (`DUX-NOTE-ANALYSIS.md`):** Prepared under `--mode accept-edits` using bounded `view_file` and `write_to_file` calls only (`run_command` not invoked). Full-dataset aggregations, cross-repo regex sweeps, and read-only store metadata probes are queued in `PROPOSAL.md` under `## DUX-REQUESTS`.

### Frozen Input Baseline (`FROZEN_DATED_TECHNICAL_BASELINE_NOT_NEW_LIVE_PROOF`)

From `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:1-13` (baseline observation timestamp `2026-10-15T03:28:29.868658+00:00` in `REAL-RUN-RECEIPT.json:3`):

| Input Artifact | SHA-256 Digest |
| :--- | :--- |
| `REPORT.md` | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` |
| `STATE.json` | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` |
| `FINAL-BLUE-GATE.json` | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` |
| `REAL-RUN-RECEIPT.json` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` |
| `research-lines.csv` | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` |
| `consumer-matrix.csv` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` |
| `ASTRA-ADVICE.md` | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` |

---

## 2. Verified Facts (Source & Frozen Baseline)

### 2.1 Global Store Census and Research Line Status (Frozen Baseline)

1. **Consumer Lead Universe (`STATE.json:17-29`, `REPORT.md:19-28`):**
   - `source_baseline_consumers`: `6029`
   - `runtime_added_consumers`: `1` (`mini.restore_drill`, observed on Mini at `/tmp/nuzantara_restore_verify_20260412_033000.log`)
   - `union_consumers`: `6030` (`consumer-matrix.csv` lines 1–6031: 1 header + 6,030 data rows)
   - `active_consumer_denominator`: `UNKNOWN` (`STATE.json:21`)
   - `complete_operation_contracts`: `0` (`STATE.json:27`)
   - `complete_root_classes`: `0` (`STATE.json:28`)
2. **Research Line `D01` ("Physical stores and connections", `research-lines.csv:3`):**
   - Status is `PARTIAL` (`total_leads=6030`, `active_consumer_denominator=UNKNOWN`, `verified_items=0`, `partial_items=6029`, `blocked_items=1`, `Complete=no`).
   - Primary gap recorded in `research-lines.csv:3`: *"Map logical datasets to actual store/endpoint/environment/deployment/connection identity."*
3. **Adjacent Store-Dependent Research Lines (`research-lines.csv:9-19`):**
   - `D07` (*RAG, KBLI, knowledge and graphs*): `OPEN_WITH_LEADS`, `verified_items=2`, `partial_items=580`, `blocked_items=4`. Gap: *"Require curated contract and frozen model/dimension proof."* (`research-lines.csv:9`)
   - `D08` (*Document ingestion and assets*): `OPEN_WITH_LEADS`, `partial_items=910`, `blocked_items=15`. Gap: *"Separate blob storage from metadata ownership and prove access."* (`research-lines.csv:10`)
   - `D10` (*Research/intelligence and agent memory*): `OPEN_WITH_LEADS`, `partial_items=1414`, `blocked_items=16`. Gap: *"Bound agent memory/staging stores with provenance and TTL."* (`research-lines.csv:12`)
   - `D17` (*Cross-store references and time semantics*): `OPEN_WITH_LEADS`, `partial_items=1174`, `blocked_items=4`. Gap: *"Verify cross-store references and explicit timezone/freshness."* (`research-lines.csv:19`)

---

### 2.2 Store Family 1: PostgreSQL (`postgresql` / `sql_dialect_unknown`)

1. **Live Read-Only Observer Baseline (`STATE.json:30-42`, `REAL-RUN-RECEIPT.json:11-28`):**
   - Observed via Pro read-only observer (`pro_pg_catalog`): `relations: 557`, `actors: 13`, `triggers: 112`, `functions: 85`, `grant_pairs: 4628`, `foreign_keys: 240`, `activity_groups: 2`, `lead_metadata_data_type: "jsonb"`.
   - Restore drill log (`mini.restore_drill`) observed on Mini (`size_bytes: 59036`, `mtime_utc: 2026-10-11T19:30:27.498185+00:00`, `REAL-RUN-RECEIPT.json:45-52`).
2. **Primary Backend-RAG Connection Factories (`apps/backend-rag`):**
   - **Application Runtime Pool (`apps/backend-rag/backend/app/setup/service_initializer.py:458-598`):**
     - Reads `settings.database_url` (`config.py:478`, normalized from `postgres://` to `postgresql://` at `config.py:523-525`).
     - Strips `sslmode` query parameter manually (`service_initializer.py:495-503`) and sets `ssl=False` when `sslmode == "disable"` (`service_initializer.py:498-500, 535-536`).
     - Creates an `asyncpg.Pool` (`service_initializer.py:518-538`) with `min_size=2` (`db_pool_min_size`), `max_size=10` (`db_pool_max_size`), `command_timeout=30` (`db_command_timeout`), `max_inactive_connection_lifetime=30.0`, `statement_cache_size=0` (for PgBouncer transaction mode), and connection initializer `init_db_connection` (`service_initializer.py:506-515`) which runs `init_asyncpg_connection(conn)` + `SET statement_timeout = '30s'` + `SELECT 1`.
     - Stores the pool on `app.state.db_pool` (`service_initializer.py:557`).
   - **Standalone Script/Test Pool (`apps/backend-rag/backend/app/core/database.py:23-51`):**
     - `get_db_pool()` creates an `asyncpg.Pool` from `settings.database_url` with `_POOL_MIN_SIZE = 2`, `_POOL_MAX_SIZE = 5`, `_COMMAND_TIMEOUT = 60`, `_MAX_INACTIVE_CONN_LIFETIME = 300`, `init=init_asyncpg_connection`, `statement_cache_size=0`.
   - **Dedicated Migration Runner Identity (`apps/backend-rag/backend/app/core/config.py:480-502`):**
     - `migration_database_url` (`MIGRATION_DATABASE_URL`) supports a separate login role (`backend_rag_migrator`, member of `backend_rag_v2` and `visa_ledger_owner`) that connects and `SET ROLE`s to the runtime role.
3. **Secondary / Non-Backend-RAG PostgreSQL Connection Factories:**
   - **WA Mirror Daemon (`apps/wa-mirror/bridge/pg.ts:19-49`):** Uses Node `pg.Pool` reading `process.env.WA_MIRROR_DATABASE_URL ?? process.env.DATABASE_URL` (`pg.ts:21-22`), `max: 5` (`WA_MIRROR_PG_MAX_CONN`), `idleTimeoutMillis: 30_000`, `connectionTimeoutMillis: 5_000`, `application_name: "wa-mirror"`.
   - **Local Admin Dashboard (`apps/admin-dashboard-local/app/lib/db.ts:6-29`):** Uses Node `pg.Pool` (`max: 3`) resolving `DATABASE_URL_LOCAL` first (`source: "local"`), then `FLY_TUNNEL_URL` (`source: "tunnel"`, e.g. `fly proxy 15432 -a nuzantara-postgres`).
   - **Operational Runtime Scripts (`consumer-matrix.csv:4501-4557`):** Launchd/cron wrappers and scripts on Pro (`Nuzantara`) such as `scripts/pg-to-organism-bridge.py`, `scripts/wa_mirror_intake_sweeper.py`, `scripts/wa_mirror_session_janitor.py`, `scripts/outbox-prune.sh`, and `scripts/cost_ledger_export_run.sh` carry lexical `postgresql` store tags but are marked `BLOCKED_RUNTIME_CONTRACT` / `REGISTRATION_SCOPE_ONLY` because runtime DSN/role binding is not established from launchd registration alone.

---

### 2.3 Store Family 2: Qdrant Vector Store (`qdrant`) & Model/Dimension/Producer-Consumer Compatibility

1. **Live Read-Only Observer Baseline (`STATE.json:45`, `REPORT.md:45-48`, `REAL-RUN-RECEIPT.json:30-37`):**
   - Local Pro loopback probe (`http://localhost:6333/collections`) returned `status: "ok"`, `collection_count: 2` (`collection_names_sha256` hashed in `REAL-RUN-RECEIPT.json:33-36`).
   - `qdrant_model_binding_proved: false` (`STATE.json:45`).
   - `REPORT.md:47` explicitly notes: *"does not attest embedding/model bindings, access principal, or physical storage."*
2. **Connection Factory & Endpoint Resolution (`apps/backend-rag/backend/core/qdrant_db.py:269-384`, `config.py:174-206, 1331-1334`):**
   - `QdrantClient.__init__` resolves `self.qdrant_url` from parameter `qdrant_url`, `settings.qdrant_url` (`QDRANT_URL`, default `"http://localhost:6333"` in `config.py:174-177`), or `settings.qdrant_default_url` (`"http://localhost:6333"`, `config.py:1331-1334`).
   - Default `collection_name` when omitted is `"knowledge_base"` (`qdrant_db.py:289`, `config.py:205`).
   - Authentication uses HTTP header `"api-key": self.api_key` (`qdrant_db.py:381-382`) from `settings.qdrant_api_key` (`QDRANT_API_KEY`, `config.py:204`), over `httpx.AsyncClient(http2=True, max_keepalive_connections=20, max_connections=100, timeout=30.0, connect=5.0)` (`qdrant_db.py:76-79, 323-335`).
   - Startup verification in `_init_search_service` (`service_initializer.py:233-258`) performs `GET /collections` with a 5.0s timeout; on failure it marks `"search"` as `ServiceStatus.UNAVAILABLE` in `service_registry` without raising, so `app.state.search_service` remains instantiated while Qdrant is unreachable (`service_initializer.py:229-232, 248-257`).
3. **Embedding Model, Version, and Dimension Contract (`config.py:57-140`, `embeddings.py:63-90, 200-325`, `qdrant_db.py:81-82`):**
   - **Configured Production Standard:** `embedding_provider: str = "openai"` (`config.py:57`), `embedding_model: str = "text-embedding-3-small"` (`config.py:101`), `embedding_dimensions: int = 1536` (`config.py:102`, `DEFAULT_OPENAI_DIMENSIONS = 1536` at `qdrant_db.py:81`).
   - **Local / Fallback Provider:** `sentence-transformers/all-MiniLM-L6-v2` (`embeddings.py:288`) with `DEFAULT_SENTENCE_TRANSFORMERS_DIMENSIONS = 384` (`qdrant_db.py:82`, `config.py:139`).
   - **Token Truncation Policy (`embeddings.py:63-90, 428-440`):** `_OPENAI_MAX_INPUT_TOKENS = 7500` (safety margin under OpenAI's 8,191-token limit) using `cl100k_base` (`tiktoken`); oversized chunks are truncated and suffixed with `" [TRUNCATED]"` (`embeddings.py:89`). Two-level batching enforces `MAX_BATCH_SIZE = 2048` items and `_OPENAI_EMBED_TOKEN_BUDGET = 200_000` tokens per request (`embeddings.py:56, 441-452`).
4. **Logical-to-Physical Collection Mapping (`collection_registry.py:9-103`, `collection_manager.py:49-140`):**
   - `CANONICAL_LOGICAL_COLLECTIONS` (`collection_registry.py:9-32`) declares 11 canonical logical names: `bali_zero_pricing_hybrid`, `visa_oracle`, `kbli_2025_final`, `tax_genius`, `legal_unified`, `training_conversations_hybrid`, `immigration_circulars`, `balizero_news`, `bali_zero_skills_hybrid`, `nlm_shadow_hybrid`, `curated_qa`.
   - `LOGICAL_TO_PHYSICAL_COLLECTIONS` (`collection_registry.py:34-56`) maps 18 logical keys to 11 physical target collections:
     - `bali_zero_pricing`, `bali_zero_pricing_hybrid` $\rightarrow$ `bali_zero_pricing_hybrid`
     - `visa_oracle` $\rightarrow$ `visa_oracle`
     - `kbli_2025_final` $\rightarrow$ `kbli_2025_final_hybrid`
     - `tax_genius`, `tax_genius_hybrid`, `tax_updates`, `tax_knowledge` $\rightarrow$ `tax_genius_hybrid`
     - `legal_architect`, `legal_unified`, `legal_unified_hybrid`, `legal_updates`, `legal_intelligence` $\rightarrow$ `legal_unified_hybrid_hybrid`
     - `training_conversations`, `training_conversations_hybrid` $\rightarrow$ `training_conversations_hybrid`
     - `immigration_circulars` $\rightarrow$ `immigration_circulars`
     - `balizero_news` $\rightarrow$ `balizero_news`
     - `bali_zero_skills_hybrid` (`SKILLS_MIRROR_COLLECTION`) $\rightarrow$ `bali_zero_skills_hybrid`
     - `nlm_shadow_hybrid` $\rightarrow$ `nlm_shadow_hybrid`
     - `curated_qa` $\rightarrow$ `curated_qa`
   - **Producer/Consumer Vector & Payload Compatibility (`qdrant_db.py:185-204, 464-478, 718-907`):**
     - **Vector Naming:** `create_collection(..., enable_sparse=True)` creates named dense vector `"dense"` (`size=vector_size`, `distance="Cosine"`) and sparse vector `"bm25"` (`qdrant_db.py:742-746`), whereas `enable_sparse=False` creates an unnamed default vector `{"size": vector_size, "distance": distance}` (`qdrant_db.py:749`). During ingestion, `upsert_documents` (`qdrant_db.py:831-896`) first attempts an unnamed `"vector": batch_embeddings[j]` PUT, and only retries with `"vector": {"dense": batch_embeddings[j]}` after catching an HTTP error whose text matches `"Not existing vector name"` or `"vector name"`.
     - **Payload Schema Split (Flat vs Nested):** `_build_point_payload` (`qdrant_db.py:185-196`) nests metadata under `"metadata"` by default (`flatten_payload: bool = False` in `upsert_documents` at `qdrant_db.py:780`), and only writes top-level metadata keys when `flatten_payload=True`. On the consumer read path, `QdrantClient._FLAT_PAYLOAD_COLLECTIONS` (`qdrant_db.py:464-474`) hardcodes only `{"legal_unified", "tax_genius", "curated_qa"}` for dual nested+flat filter generation (`include_flat_payload=True` in `_convert_filter_to_qdrant_format`, `qdrant_db.py:411-426`).

---

### 2.4 Store Family 3: Redis (`redis` / `event_delivery`)

1. **Live Read-Only Observer Baseline (`STATE.json:43-44`, `REAL-RUN-RECEIPT.json:38-44`):**
   - `pro_redis`: `AUTHORIZATION_REQUIRED` (`NOAUTH Authentication required.` on unauthenticated `INFO`).
   - `mini_redis`: `AUTHORIZATION_REQUIRED` (`NOAUTH Authentication required.` on unauthenticated `INFO`).
2. **Backend-RAG Connection Factory (`apps/backend-rag/backend/core/redis_manager.py:45-199`, `config.py:531`):**
   - `RedisManager` (`redis_manager.py:45`) is a singleton reading `settings.redis_url` (`REDIS_URL`, `config.py:531`).
   - Initializes two pools when `redis_url` is set (`redis_manager.py:92-121`):
     - Synchronous `redis.from_url` (`max_connections=5`, `socket_timeout=2.0`, `socket_connect_timeout=2.0`, `decode_responses=True`, `health_check_interval=30`).
     - Asynchronous `aioredis.from_url` (`max_connections=10`, `socket_timeout=2.0`, `socket_connect_timeout=2.0`, `decode_responses=True`).
   - If `redis_url` is unset or `PING` fails, `self._available` is set to `False` (`redis_manager.py:86-88, 129-141`) and callers fall back to per-process in-memory structures or no-ops.
3. **Independent Redis Consumers Outside `RedisManager`:**
   - `apps/remediator/main.py:12, 48-60` imports `redis.asyncio as aioredis` directly and tracks stream consumer offsets (`last_redis_id`) in a local SQLite database (`remediator.sqlite`).
   - `consumer-matrix.csv` records additional Redis consumers in `apps/mata-garuda/` (`consumer-matrix.csv:1580-1650`) and Pro launchd scripts (`scripts/pg-to-organism-bridge.py`, `scripts/sentinel-aggregate.py`, `scripts/army/spark_lane.sh`, `infra/scripts/pg-organism-bridge-watchdog.sh`, `consumer-matrix.csv:4502, 4507, 4533, 4539`).

---

### 2.5 Store Families 4–9: SQLite, Graphs, Object Storage, File State, Spreadsheets, and Browser State

1. **SQLite (`sqlite`, `apps/remediator/main.py:23-89`, `consumer-matrix.csv:120-230, 4525, 4528`):**
   - Used as embedded local file databases across autonomous/ops daemons and CLIs without a shared connection factory:
     - `apps/remediator/main.py:23-46`: `DB_PATH = os.environ.get("REMEDIATOR_DB_PATH", "remediator.sqlite")` with tables `remediation_attempts` and `state`.
     - `consumer-matrix.csv` identifies SQLite stores across `apps/evaluator/`, `apps/bali-intel-scraper/`, `apps/zantara-media/`, `scripts/mata_garuda_unmapped_audit_wrapper.sh` (`consumer-matrix.csv:4525`), and `scripts/metabolic_rollup_pro.sh` (`consumer-matrix.csv:4528`).
2. **Graphs (`graph`, `apps/backend-rag/backend/services/misc/graph_service.py:1-90`, `service_initializer.py:577-587`):**
   - `GraphService` is **not** backed by a standalone graph database engine (e.g., Neo4j); it persists entities and relations inside PostgreSQL tables `kg_nodes` and `kg_edges` using the shared `app.state.db_pool` (`graph_service.py:5-8, 40-41, 74-82`; initialized at `service_initializer.py:579-583`).
   - Note at `graph_service.py:69-73` documents a historical JSONB double-encoding defect (`1517` polluted rows in `kg_nodes.properties` observed `2026-07-16`), mitigated in `GraphService.add_entity` via explicit `$4::text::jsonb` casting.
3. **Object Storage & External Drive (`object_storage`, `config.py:1157-1177`):**
   - Google Drive acts as the primary document/blob store for client and legal archives (`google_drive_root_folder_id`, `legal_drive_root_folder_id`, `gdrive_individuals_folder_id`, `gdrive_companies_folder_id` at `config.py:1164-1176`), while document metadata resides in PostgreSQL (`D08` in `research-lines.csv:10`).
4. **Local File State (`file_state`, `config.py:435, 466-467, 1022-1027, 1339-1380`, `consumer-matrix.csv:4502-4558`):**
   - Backend-RAG file-backed state paths include `./data/zantara_rag.log` (`config.py:435`), `./data/raw_books` and `./data/processed` (`config.py:466-467`), `/tmp/autonomous_lab_receipts` (`config.py:1023`), `/data/staging` (Fly volume) or `/tmp/staging` (`get_intel_staging_base_dir`, `config.py:1363-1372`), and `/tmp/pending_intel` (`config.py:1375-1379`).
   - Launchd/cron operational scripts on Pro and Mini heavily use local JSON/JSONL/log file state (`consumer-matrix.csv:4502-4558`).
5. **Spreadsheets (`spreadsheet`, `consumer-matrix.csv:50-60, 280-620`):**
   - Google Sheets / CSV / XLSX surfaces appear in `consumer-matrix.csv` for pricing/HR/reporting workflows and ingestion scripts.
6. **Browser State (`browser_state`, `consumer-matrix.csv:3020-3100`):**
   - Client-side persistence (`localStorage`, `sessionStorage`, `indexedDB`, cookies) in `apps/mouth/` (`https://kita.balizero.com`, `https://my.balizero.com`, `https://balizero.com`) and `apps/admin-dashboard-local/`, plus cross-subdomain auth cookies (`cookie_domain`, `cookie_secure`, `csrf_enabled` in `config.py:625-639`).
7. **Non-Database / Container Reference Rows in `consumer-matrix.csv` (`consumer-matrix.csv:6000-6031`):**
   - Rows `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` are explicitly classified as `NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY` (`disposition=NON_CANONICAL_EVIDENCE_CONTAINER`) and must not be counted as physical database consumers.

---

## 3. Counterexamples and Structural Defects

### Counterexample CE-B04-01: `_global_embedding_cache` Key Collision Across Provider, Model, and Dimension (`apps/backend-rag/backend/core/embeddings.py:160-184, 358-375`)
- **Claim Violated:** Embedding generation deterministically produces vectors matching the caller's configured `(provider, model, dimensions)` (1536-dim OpenAI `text-embedding-3-small` vs 384-dim `sentence-transformers/all-MiniLM-L6-v2`).
- **Exact Evidence:** `EmbeddingCache._make_key(self, texts: list[str])` (`embeddings.py:160-163`) computes `hashlib.md5(serialized.encode()).hexdigest()` over `json.dumps(texts, sort_keys=True)` alone, omitting `self.provider`, `self.model`, and `self.dimensions`. Both OpenAI and Sentence-Transformers code paths read from and write to the module-level singleton `_global_embedding_cache` (`embeddings.py:203, 358, 374`).
- **Failure Mechanism:** If any service or fallback path in the same Python process instantiates `EmbeddingsGenerator(provider="sentence-transformers")` (or `EmbeddingsGenerator()` when `settings` is unavailable, `embeddings.py:242`) and embeds a text $T$, `_global_embedding_cache` caches a 384-dimensional vector under `MD5(T)`. A subsequent call on a production `EmbeddingsGenerator(provider="openai")` (1536 dims) for $T$ hits `_global_embedding_cache.get(texts)` (`embeddings.py:358-364`) and receives the 384-dimensional vector, causing a downstream Qdrant dimension mismatch on search or upsert.

### Counterexample CE-B04-02: Alias Resolution Asymmetry in `collection_registry.py` (`apps/backend-rag/backend/core/collection_registry.py:34-102`)
- **Claim Violated:** `collection_registry.py` is the single source of truth (`collection_registry.py:2`) that maps every known logical/alias collection name to its physical Qdrant collection name and validates known collections.
- **Exact Evidence:**
  - `CANONICAL_COLLECTION_ALIASES` (`collection_registry.py:58-82`) defines 19 alias mappings, including `"intel_authoritative_sources": "balizero_news"` (line 76), `"kbli_2025_final_hybrid": "kbli_2025_final"` (line 61), and `"legal_unified_hybrid_hybrid": "legal_unified"` (line 69).
  - However, `is_known_collection(collection_name)` (`collection_registry.py:90-92`) checks `return collection_name in LOGICAL_TO_PHYSICAL_COLLECTIONS` — and `"intel_authoritative_sources"`, `"kbli_2025_final_hybrid"`, and `"legal_unified_hybrid_hybrid"` are **absent** from `LOGICAL_TO_PHYSICAL_COLLECTIONS` (`collection_registry.py:34-56`)!
  - Furthermore, `resolve_collection_name("intel_authoritative_sources")` (`collection_registry.py:85-87`) performs `LOGICAL_TO_PHYSICAL_COLLECTIONS.get(collection_name, collection_name)` without first canonicalizing through `CANONICAL_COLLECTION_ALIASES`, returning `"intel_authoritative_sources"` (a non-existent physical collection) instead of `"balizero_news"`.

### Counterexample CE-B04-03: Estate Drift Between `CollectionManager.collection_definitions`, `collection_registry.py`, and Live Qdrant (`apps/backend-rag/backend/services/ingestion/collection_manager.py:51-140`, `qdrant_db.py:289`)
- **Claim Violated:** Static collection registries in `backend-rag` match the physical Qdrant collection universe.
- **Exact Evidence:**
  - `collection_manager.py:51-60` explicitly documents (TAC-2 A6, `2026-07-05`) that only 6 of the 20 entries in `self.collection_definitions` exist live, 14 are dead names (including `"collective_memories"`, which migrated to PostgreSQL, and `"bali_zero_team"`, `"zantara_books"`, `"cultural_insights"`, `"property_listings"`, which are not in `LOGICAL_TO_PHYSICAL_COLLECTIONS` at all), while live collection `legal_unified_2026` (15k docs) has no entry in either `collection_definitions` or `collection_registry.py`.
  - Additionally, `QdrantClient.__init__` defaults `self.collection_name` to `"knowledge_base"` (`qdrant_db.py:289`, `config.py:205`), which is absent from both `collection_registry.py` and `collection_manager.py`.
  - On Pro's local Qdrant instance, the frozen baseline observer found only `2` collections (`STATE.json:45`), proving that local Pro Qdrant and production Qdrant Cloud have completely divergent collection topologies.

### Counterexample CE-B04-04: Qdrant Flat vs Nested Payload Mismatch Across KBLI and Core Collections (`apps/backend-rag/backend/core/qdrant_db.py:185-196, 464-478, 780`)
- **Claim Violated:** Project Golden Rule 9 (*"Payload Qdrant FLAT — mai nested"*, especially for KBLI `{"code": "47911", "title_id": "...", ...}`).
- **Exact Evidence:**
  - `QdrantClient.upsert_documents` defaults to `flatten_payload: bool = False` (`qdrant_db.py:780`), which causes `_build_point_payload` (`qdrant_db.py:185-196`) to wrap all metadata inside `{"text": text, "metadata": metadata}`.
  - On the filter construction path (`_convert_filter_to_qdrant_format`, `qdrant_db.py:385-478`), `_FLAT_PAYLOAD_COLLECTIONS` (`qdrant_db.py:464-474`) only enables top-level key matching (`include_flat_payload=True`) for `{"legal_unified", "tax_genius", "curated_qa"}`. Notably, `"kbli_2025_final"` (physical `kbli_2025_final_hybrid`) is **missing** from `_FLAT_PAYLOAD_COLLECTIONS`, so `QdrantClient.search(..., filter={"code": "47911"})` on `kbli_2025_final` generates a filter exclusively on `"metadata.code"` (`qdrant_db.py:412-414`), missing flat KBLI payloads where `"code"` sits at the top level!

### Counterexample CE-B04-05: PostgreSQL Pool Parameter & Codec Divergence Across Monorepo Apps (`database.py:16-43`, `service_initializer.py:518-538`, `apps/wa-mirror/bridge/pg.ts:19-49`, `apps/admin-dashboard-local/app/lib/db.ts:6-29`)
- **Claim Violated:** Every PostgreSQL consumer shares a single canonical pool configuration and JSONB codec discipline.
- **Exact Evidence:**
  - Even within `apps/backend-rag`, `service_initializer.py:518-532` configures `max_size=10`, `command_timeout=30`, `max_inactive_connection_lifetime=30.0`, and `SET statement_timeout = '30s'`, whereas `backend/app/core/database.py:16-43` configures `max_size=5`, `command_timeout=60`, `max_inactive_connection_lifetime=300` (5 minutes — the exact value `service_initializer.py:524-525` notes caused `"connection was closed in the middle of operation"` after Fly.io cold starts), and omits `SET statement_timeout = '30s'` and `sslmode=disable` stripping.
  - Across languages, `apps/wa-mirror/bridge/pg.ts` and `apps/admin-dashboard-local/app/lib/db.ts` instantiate independent Node `pg.Pool` instances with separate env var precedence (`WA_MIRROR_DATABASE_URL ?? DATABASE_URL` vs `DATABASE_URL_LOCAL ?? FLY_TUNNEL_URL`).

### Counterexample CE-B04-06: Lexical Store False-Positives in `consumer-matrix.csv` (`consumer-matrix.csv:2-18`)
- **Claim Violated:** Every row in `consumer-matrix.csv` with a non-empty `store` column represents an actual runtime store connection.
- **Exact Evidence:**
  - Row `repo_0e2c9f158a76731f` (`consumer-matrix.csv:2`) assigns `.github/dependabot.yml` to `store=qdrant` based solely on a lexical comment/package match (`qdrant:26`).
  - Rows `repo_5d54fa59301e6b3f` (`consumer-matrix.csv:17`, `001_initial_schema.sql`) and `repo_e4964f782237c1df` (`consumer-matrix.csv:18`, `schema.sql`) in `apps/bali-intel-scraper` are tagged `postgresql;sql_dialect_unknown` (`sql_dialect_unknown:1`).
  - Consequently, raw lexical counts from `consumer-matrix.csv` overcount active store consumers unless filtered by connection-factory and runtime-invocation proof.

---

## 4. Inferences (Derived from Verified Facts)

1. **Dual-Environment Store Split (Fly/Cloud vs Local Pro/Mini):**
   - From `config.py:174-206, 478-532` and `STATE.json:30-45`, `apps/backend-rag` binds to three core networked stores (`PostgreSQL`, `Qdrant`, `Redis`) whose physical endpoints depend entirely on runtime environment variables (`DATABASE_URL`, `QDRANT_URL`, `REDIS_URL`). Without joining launchd plist / `.env` / Fly secret bindings (`DUX-B04-04`), static code paths alone only identify the *logical* store family, not whether a consumer targets Fly (`nuzantara-postgres` / Qdrant Cloud) or local Pro (`localhost:5432`, `localhost:6333`, `localhost:6379`).
2. **Silent Degradation Masks Store Disconnections:**
   - Because `_init_search_service` (`service_initializer.py:248-257`), `initialize_database_services` (`service_initializer.py:468-477`), and `RedisManager` (`redis_manager.py:129-141`) all catch connection failures at boot and allow the process to continue running in degraded/fallback mode, HTTP 200 process liveness does not imply store connectivity unless `/health` or `service_registry` per-store status is inspected.
3. **Reactive Named-Vector Retry Adds Write Latency on Hybrid Collections:**
   - In `QdrantClient.upsert_documents` (`qdrant_db.py:846-888`), every batch upsert to a hybrid collection (such as `legal_unified_hybrid_hybrid`, `tax_genius_hybrid`, `kbli_2025_final_hybrid`) first sends an unnamed vector payload, fails with HTTP 400 (`"Not existing vector name"`), and then retries with `"vector": {"dense": ...}`. Caching the collection's vector schema (or checking `collection_registry` metadata) would eliminate the guaranteed 400 round-trip on every hybrid batch write.

---

## 5. Unknowns and Missing Evidence

1. **U-B04-01 — Full `consumer-matrix.csv` Breakdown by Store Family and Disposition:**
   - Because shell/python execution is disabled in this session, exact row counts across all 6,030 rows of `consumer-matrix.csv` partitioned by `(store, class, disposition, phase_factory_candidate_count)` have not been computed in this turn. Queued as `DUX-B04-01`.
2. **U-B04-02 — Live Qdrant Cloud vs Local Pro Collection Inventory & Schema Parity:**
   - `STATE.json:45` records `qdrant_local_collection_count: 2` (names hashed in `REAL-RUN-RECEIPT.json:33-36`) and `qdrant_model_binding_proved: false`. The exact live collection names, point counts, vector dimensions (`1536` vs `384`), distance metrics (`Cosine`), and named/sparse vector configurations (`dense` + `bm25`) on both local Pro Qdrant and production Qdrant Cloud remain unverified. Queued as `DUX-B04-03`.
3. **U-B04-03 — Authenticated Read-Only Observer Proof for Pro and Mini Redis:**
   - Both `pro_redis` and `mini_redis` returned `AUTHORIZATION_REQUIRED` (`STATE.json:43-44`). Keyspace db indexes (`db0`, etc.), eviction policies (`maxmemory-policy`), persistence mode (RDB/AOF), and active stream/consumer-group names on Pro and Mini Redis are `UNKNOWN`. Queued as `DUX-B04-05`.
4. **U-B04-04 — Runtime Environment Store Bindings for `operational_runtime` (`job_pro_*` / `runtime_*`):**
   - The launchd/cron leads in `consumer-matrix.csv` (`runtime_*` rows) have `store_instance_environment = UNKNOWN` and `status = BLOCKED_RUNTIME_CONTRACT` because their wrapper scripts source untracked env files (`~/.openclaw/...`, `.env*`). Exact `(consumer_id -> store_id)` bindings for these jobs require read-only inspection of their resolved environment variable targets (without printing secret values). Queued as `DUX-B04-04`.
5. **U-B04-05 — Active Consumer Denominator (`STATE.json:21`):**
   - Separating active runtime store consumers from dead/archived files, lexical false-positives (like `.github/dependabot.yml`), and non-database containers (`NOTEBOOK-CONTAINER-REFERENCE-NLM-*`) requires the repo-wide connection-factory index requested in `DUX-B04-02`.

## Adversarial review

A real scoped Codex document review examined source SHA-256 03af12ed1318d7395fe3a27042e55132974f51f0dc7373e3cbc69a900732b190. R1-DOCUMENT-REVIEW.json records scope, findings and limitations: REVIEWED_PARTIAL_WITH_BLOCKERS, no full-document or implementation approval. Historical wrong counts/paths/authority proposals do not become executable through attribution. The addendum reconciles actual receipts; this is not an independent code grade. Requested supporting seat: Astra 6 / xhigh; effective runtime identity UNOBSERVED. A fresh independent Opus 5.5 / xhigh exact-head BLUE gate remains required.
