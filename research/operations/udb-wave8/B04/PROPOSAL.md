---
adversarial_review: codex
---

> Historical research retained for traceability. Superseded statements and commands are BLOCKED FOR IMPLEMENTATION. Current evidence is the synthesis addendum, pinned receipt and binding Dux rulings. No production/native action is authorized here.

# UDB Wave 8 — Block B04: Physical Stores and Connections (PROPOSAL)

## 1. Governance, Scope, and Sibling Contract Alignment

- **Campaign / Block:** `universal-db-wave8-20261015` / `B04` (*Physical stores and connections*)
- **Colour / Gear / Role:** `BLUE` / `GEAR 3` / `EXTERNAL PREPARER, NO_DUX` (`PREPARE_ONLY`)
- **Host / Worktree:** `Mini` (`Mini-Pro2`) / `/Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Model / Effort Honesty (`BATTLE.md` §2):**
  - `requested_model`: `Gemini 4 Argon` | `requested_effort`: `high`
  - `effective_runtime_model`: `UNOBSERVED` | `effective_runtime_effort`: `UNOBSERVED`
  - `session_handle`: `0db3627f-7483-4259-98e1-4bf16babad18`

### 1.1 Frozen Sibling Contract (`BATTLE.md` §3)

To guarantee zero schema drift across `B02`, `B03`, `B04`, and `B05`, every B04 store-binding record and adapter output preserves the exact frozen sibling columns unchanged:

1. **Base Contract Fields (Frozen Across All Sibling Blocks):**
   ```text
   consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns
   ```
2. **Operation Instance Fields (Owned by `B05`, Consumed via Join on `(consumer_id, operation_id, store_id)`):**
   ```text
   principal,role,tenant,authorization,transaction,effects,retries,idempotency,failure,retention,recovery
   ```
3. **Canonical `store_id` Namespace (Owned by `B04`, Joined by `B02`/`B03`/`B05`):**
   Every physical or logical store instance is assigned a deterministic `store_id` of the form `<family>:<environment>:<instance_slug>[:<subcontainer>]`:
   - `pg:fly:nuzantara_postgres:public` (Fly.io production PostgreSQL 17, `DATABASE_URL` / `MIGRATION_DATABASE_URL`)
   - `pg:pro:local_postgres:public` (Pro local/observer PostgreSQL, `557` relations in `STATE.json:31`)
   - `pg:fly:nuzantara_postgres:kg_graph` (`GraphService` tables `kg_nodes` and `kg_edges` in `apps/backend-rag/backend/services/misc/graph_service.py:6-8`)
   - `qdrant:cloud:nuzantara_qdrant:<physical_collection>` (Production Qdrant Cloud physical collections resolved via `collection_registry.py:34-56`)
   - `qdrant:pro:local_6333:<physical_collection>` (Pro local Qdrant loopback `http://localhost:6333`, `2` collections in `STATE.json:45`)
   - `redis:pro:local_6379:db0` and `redis:mini:local_6379:db0` (Pro and Mini Redis instances, currently `AUTHORIZATION_REQUIRED` in `STATE.json:43-44`)
   - `sqlite:<host>:<app_slug>:<db_filename>` (e.g., `sqlite:pro:remediator:remediator.sqlite` in `apps/remediator/main.py:23`)
   - `object:gdrive:balizero_root:<folder_role>` (`google_drive_root_folder_id`, `legal_drive_root_folder_id`, `gdrive_individuals_folder_id`, `gdrive_companies_folder_id` in `config.py:1164-1176`)
   - `file:<host>:<scope_slug>:<path_template>` (e.g., `file:fly:intel_staging:/data/staging`, `file:local:intel_staging:/tmp/staging` in `config.py:1363-1379`)
   - `sheet:gsheets:<workbook_role>` (Spreadsheet surfaces in `consumer-matrix.csv`)
   - `browser:client:<origin_slug>:<storage_mechanism>` (`localStorage`, `sessionStorage`, `indexedDB`, auth cookies in `apps/mouth/` and `apps/admin-dashboard-local/`)

---

## 2. Scoped Candidate Development Proposal (S1 Implementation Scope)

All proposed code changes are strictly scoped to B04-owned store registry/connection modules and unit tests (`<= 250` net lines, zero touches to `fly.toml`, `.env*`, `zantara_core.py`, or migrations).

### 2.1 Proposal P1 — Symmetrize `collection_registry.py` Alias Resolution and `qdrant_db.py` Flat-Payload Filtering

- **Target Files:**
  - `apps/backend-rag/backend/core/collection_registry.py` (lines 34–103)
  - `apps/backend-rag/backend/core/qdrant_db.py` (lines 461–479)
- **Defects Resolved:** `CE-B04-02` and `CE-B04-04` in `ANALYSIS.md` §3.
- **Exact Design:**
  1. In `collection_registry.py`:
     - Update `resolve_collection_name(collection_name: str) -> str` (`collection_registry.py:85-87`) to first normalize aliases via `canonical = CANONICAL_COLLECTION_ALIASES.get(collection_name, collection_name)` when `collection_name` is not directly in `LOGICAL_TO_PHYSICAL_COLLECTIONS`, then return `LOGICAL_TO_PHYSICAL_COLLECTIONS.get(canonical, collection_name)`.
     - Update `is_known_collection(collection_name: str) -> bool` (`collection_registry.py:90-92`) to return `bool(collection_name in LOGICAL_TO_PHYSICAL_COLLECTIONS or collection_name in CANONICAL_COLLECTION_ALIASES)`.
     - This ensures `"intel_authoritative_sources"` resolves to `"balizero_news"` and physical names `"kbli_2025_final_hybrid"` and `"legal_unified_hybrid_hybrid"` are recognized by `is_known_collection(...) == True`.
  2. In `qdrant_db.py`:
     - Add `"kbli_2025_final"` (and `"bali_zero_pricing_hybrid"`, `"visa_oracle"`, `"balizero_news"`, `"bali_zero_skills_hybrid"`) to `QdrantClient._FLAT_PAYLOAD_COLLECTIONS` (`qdrant_db.py:464-474`) so that `QdrantClient.search()` filter conversion (`_convert_filter_to_qdrant_format`, `qdrant_db.py:411-426`) matches flat top-level payload keys (`{"key": "code", ...}`) in addition to legacy `"metadata.code"`.

### 2.2 Proposal P2 — Namespace `_global_embedding_cache` by `(provider, model, dimensions)`

- **Target File:** `apps/backend-rag/backend/core/embeddings.py` (lines 160–198, 358–375)
- **Defect Resolved:** `CE-B04-01` in `ANALYSIS.md` §3 (cross-provider/cross-dimension MD5 cache collision between 1536-dim OpenAI and 384-dim Sentence-Transformers).
- **Exact Design:**
  - Extend `EmbeddingCache._make_key(self, texts: list[str], *, provider: str = "openai", model: str = "text-embedding-3-small", dimensions: int = 1536) -> str` to serialize `{"provider": provider, "model": model, "dimensions": dimensions, "texts": texts}` with `json.dumps(..., sort_keys=True)` before hashing.
  - Thread `provider=self.provider, model=self.model, dimensions=self.dimensions` through `_global_embedding_cache.get(...)` (`embeddings.py:358`) and `_global_embedding_cache.set(...)` (`embeddings.py:374`), while keeping default keyword arguments backward-compatible for any existing direct unit test calls to `EmbeddingCache.get(texts)` / `set(texts, embeddings)`.

### 2.3 Proposal P3 — Read-Only Physical Store & Qdrant Compatibility Adapter (`store_catalog_adapter.py`)

- **Target File (New, Scoped to B04):** `apps/backend-rag/backend/core/store_catalog_adapter.py` (and generated report artifact `research/operations/udb-wave8/B04/store-catalog.json` / `store-bindings.csv`).
- **Defects Resolved:** `CE-B04-03`, `CE-B04-05`, `CE-B04-06` in `ANALYSIS.md` §3.
- **Exact Design:**
  - Define frozen dataclasses:
    - `StoreBindingRecord`: exact 8 frozen sibling fields (`consumer_id`, `operation_id`, `store_id`, `source_version`, `evidence_timestamp`, `evidence_sha256`, `status`, `unknowns`).
    - `PhysicalStoreDescriptor`: (`store_id`, `store_family`, `environment`, `deployment_target`, `connection_factory`, `dsn_env_vars`, `expected_vector_model`, `expected_vector_dimensions`, `payload_layout`, `verification_status`, `unknowns`).
  - Provide pure, deterministic validation functions:
    - `verify_qdrant_collection_contract(collection_name: str, observed_size: int | None, observed_distance: str | None, provider: str, model: str, dimensions: int) -> dict[str, Any]`: checks that logical/physical collection names resolve cleanly, enforces `model == "text-embedding-3-small"` and `dimensions == 1536` for production OpenAI embeddings, and flags any 384-dim or unnamed-vector mismatch as `CONFLICT`.
    - `classify_consumer_store_binding(row: Mapping[str, str]) -> StoreBindingRecord`: maps `consumer-matrix.csv` rows into the frozen 8-column sibling contract while explicitly filtering out `NOTEBOOK_CONTAINER_REFERENCE` rows and flagging lexical-only non-code rows (e.g., `.github/dependabot.yml`) as `NOT_APPLICABLE_LEXICAL_FALSE_POSITIVE`.

---

## 3. Verification and Negative-Case Plan

- **Target Test File:** `apps/backend-rag/backend/tests/unit/core/test_b04_store_contracts.py`
- **Test Cases (Positive + Required Negative Cases):**
  1. `test_embedding_cache_isolates_1536_openai_from_384_sentence_transformers` (**Negative Case for `CE-B04-01`**):
     - Populate `EmbeddingCache` with `texts=["KITAS investor"]`, `provider="sentence-transformers"`, `model="sentence-transformers/all-MiniLM-L6-v2"`, `dimensions=384` (384-float vector).
     - Query `EmbeddingCache.get` with the identical `texts=["KITAS investor"]` under `provider="openai"`, `model="text-embedding-3-small"`, `dimensions=1536`.
     - Assert cache **MISS** (`None`), proving 384-dim vectors can never poison 1536-dim callers.
  2. `test_collection_registry_resolves_all_aliases_and_physical_names` (**Positive + Negative Case for `CE-B04-02`**):
     - Assert `is_known_collection("intel_authoritative_sources") is True` and `resolve_collection_name("intel_authoritative_sources") == "balizero_news"`.
     - Assert `is_known_collection("kbli_2025_final_hybrid") is True` and `resolve_collection_name("kbli_2025_final_hybrid") == "kbli_2025_final_hybrid"`.
     - Assert `is_known_collection("nonexistent_rogue_collection") is False` (**Negative case**).
  3. `test_qdrant_kbli_filter_includes_flat_top_level_payload_keys` (**Negative Case for `CE-B04-04`**):
     - Instantiate `QdrantClient(collection_name="kbli_2025_final_hybrid")` and convert filter `{"code": "47911"}`.
     - Assert `_include_flat_payload_filters() is True` and the generated Qdrant filter includes `{"key": "code", "match": {"value": "47911"}}` at top level, not solely nested `"metadata.code"`.
  4. `test_store_contract_rejects_dimension_mismatch_and_non_db_containers` (**Negative Cases for `P3`**):
     - Assert `verify_qdrant_collection_contract` returns `status="CONFLICT"` when `observed_size=384` against `expected_dimensions=1536` or when `collection_name="unknown_unregistered"`.
     - Assert `classify_consumer_store_binding` rejects `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` as `NOT_DATABASE_CONSUMER` and preserves all 8 frozen sibling fields (`consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns`).

---

## DUX-REQUESTS

Per `DUX-NOTE-ANALYSIS.md`, the following read-only commands and probes are requested from the BLUE Dux to supply full-file aggregations, repo-wide connection factory counts, and live read-only store metadata without running shell commands inside this `--mode accept-edits` session:

### `DUX-B04-01`: Full Aggregation of `consumer-matrix.csv` by Store Family, Disposition, and Factory Candidate Count
- **ID:** `DUX-B04-01`
- **Exact Read-Only Command:**
  ```bash
  python3 -c '
  import csv, json, hashlib
  from collections import Counter
  path = ".agent-receipts/udb-wave8-inputs/consumer-matrix.csv"
  with open(path, "rb") as fb:
      sha = hashlib.sha256(fb.read()).hexdigest()
  by_store, by_disp, by_class_store, with_factory = Counter(), Counter(), Counter(), Counter()
  with open(path, newline="", encoding="utf-8") as f:
      for row in csv.DictReader(f):
          s = row.get("store", "") or "EMPTY"
          d = row.get("disposition", "") or "EMPTY"
          c = row.get("class", "") or "EMPTY"
          fc = int(row.get("phase_factory_candidate_count") or 0)
          by_store[s] += 1
          by_disp[d] += 1
          by_class_store[f"{c}::{s}"] += 1
          if fc > 0:
              with_factory[s] += 1
  print(json.dumps({
      "sha256": sha,
      "total_rows": sum(by_store.values()),
      "by_store": dict(by_store.most_common()),
      "by_disposition": dict(by_disp.most_common()),
      "with_factory_candidates_by_store": dict(with_factory.most_common()),
      "by_class_and_store_top30": dict(by_class_store.most_common(30))
  }, indent=2))
  '
  ```
- **Inputs:** `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256=c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`).
- **Expected Output Shape:** JSON object with `total_rows` (`6030`), exact counts per `store` tag combination, exact counts per `disposition`, and counts of rows with `phase_factory_candidate_count > 0` per store family.
- **Why It Matters:** Closes `U-B04-01` by replacing sampled slices of `consumer-matrix.csv` with exact, deterministic store-family denominators across all 6,030 leads.

### `DUX-B04-02`: Repo-Wide Connection Factory & Store Client Instantiation Census
- **ID:** `DUX-B04-02`
- **Exact Read-Only Command:**
  ```bash
  rg -n --no-heading \
    -e 'asyncpg\.create_pool|asyncpg\.connect|psycopg2\.connect|psycopg\.connect|create_engine|create_async_engine|new Pool\(|new pg\.Pool\(' \
    -e 'QdrantClient\(|AsyncQdrantClient\(' \
    -e 'redis\.from_url|aioredis\.from_url|Redis\(|createClient\(' \
    -e 'sqlite3\.connect|aiosqlite\.connect|better-sqlite3' \
    -e 'localStorage\.|sessionStorage\.|indexedDB\.' \
    apps/ scripts/ packages/ \
    -g '!**/node_modules/**' -g '!**/.venv/**' -g '!**/venv/**' -g '!**/.next/**' -g '!**/tests/**' -g '!**/*.test.*' -g '!**/*.spec.*'
  ```
- **Inputs:** Tracked production code under `apps/`, `scripts/`, and `packages/` at commit `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`.
- **Expected Output Shape:** `file:line:match` lines listing every non-test connection factory and store client instantiation across PostgreSQL, Qdrant, Redis, SQLite, and Browser State.
- **Why It Matters:** Closes `U-B04-05` by distinguishing true connection-owning modules from the 6,030 lexical leads in `consumer-matrix.csv`.

### `DUX-B04-03`: Read-Only Qdrant Collection Schema & Vector Dimension/Sparse Config Probe (Local Pro + Production Endpoint if Reachable)
- **ID:** `DUX-B04-03`
- **Exact Read-Only Command:**
  ```bash
  python3 -c '
  import json, urllib.request
  base = "http://localhost:6333"
  with urllib.request.urlopen(f"{base}/collections", timeout=5) as r:
      cols = [c["name"] for c in json.loads(r.read().decode()).get("result", {}).get("collections", [])]
  out = {}
  for name in cols:
      with urllib.request.urlopen(f"{base}/collections/{name}", timeout=5) as r:
          cfg = json.loads(r.read().decode()).get("result", {})
          out[name] = {
              "status": cfg.get("status"),
              "points_count": cfg.get("points_count"),
              "vectors": cfg.get("config", {}).get("params", {}).get("vectors"),
              "sparse_vectors": cfg.get("config", {}).get("params", {}).get("sparse_vectors"),
              "on_disk_payload": cfg.get("config", {}).get("params", {}).get("on_disk_payload"),
          }
  print(json.dumps({"endpoint": base, "collection_count": len(cols), "collections": out}, indent=2))
  '
  ```
- **Inputs:** Read-only `GET /collections` and `GET /collections/{name}` metadata endpoints on Qdrant (zero payload/point reads, zero PII).
- **Expected Output Shape:** JSON dictionary mapping each live collection name to `{status, points_count, vectors: {size, distance} | {dense: {size, distance}}, sparse_vectors}` (plus the equivalent read-only `/health/collections` or Qdrant Cloud metadata output from Pro if authorized).
- **Why It Matters:** Closes `U-B04-02` and proves `qdrant_model_binding_proved` (`1536` dims `Cosine` + `bm25` sparse vector presence) against `collection_registry.py`.

### `DUX-B04-04`: Redacted Store Env-Var Binding Audit for `operational_runtime` Jobs on Pro & Mini
- **ID:** `DUX-B04-04`
- **Exact Read-Only Command:**
  ```bash
  python3 -c '
  import csv, re, json, pathlib
  keys = ("DATABASE_URL", "MIGRATION_DATABASE_URL", "WA_MIRROR_DATABASE_URL", "DATABASE_URL_LOCAL", "FLY_TUNNEL_URL", "QDRANT_URL", "REDIS_URL", "REMEDIATOR_DB_PATH", "SQLITE")
  pat = re.compile(r"\b(" + "|".join(keys) + r")\b")
  results = {}
  with open(".agent-receipts/udb-wave8-inputs/consumer-matrix.csv", encoding="utf-8") as f:
      for row in csv.DictReader(f):
          if row.get("class") == "operational_runtime":
              p = pathlib.Path(row["path_or_unit"])
              if p.is_file():
                  txt = p.read_text(errors="ignore")
                  hits = sorted(set(pat.findall(txt)))
                  results[row["consumer_id"]] = {"path": str(p), "store_tag": row.get("store"), "env_vars_referenced": hits}
  print(json.dumps({"runtime_jobs_checked": len(results), "jobs": results}, indent=2))
  '
  ```
- **Inputs:** `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`operational_runtime` rows) and their corresponding tracked script files in the worktree (reports **only** variable names referenced, never secret values).
- **Expected Output Shape:** JSON map of `runtime_*` consumer IDs to the store environment variable names they reference.
- **Why It Matters:** Closes `U-B04-04` by binding `operational_runtime` scripts (`REGISTRATION_SCOPE_ONLY`) to their target store environment variables without exposing credentials.

### `DUX-B04-05`: Read-Only Authenticated Redis Server/Keyspace Metadata Probe (Pro & Mini)
- **ID:** `DUX-B04-05`
- **Exact Read-Only Command:**
  ```bash
  # Executed by Dux on Pro and Mini using configured local REDIS_URL (prints only non-sensitive server/keyspace/memory summary, never keys or values):
  python3 -c '
  import os, json, redis
  url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
  r = redis.from_url(url, decode_responses=True, socket_timeout=2.0)
  info = r.info()
  print(json.dumps({
      "redis_version": info.get("redis_version"),
      "role": info.get("role"),
      "maxmemory_policy": info.get("maxmemory_policy"),
      "aof_enabled": info.get("aof_enabled"),
      "keyspace": {k: v for k, v in info.items() if k.startswith("db")}
  }, indent=2))
  '
  ```
- **Inputs:** Authenticated read-only `INFO` command via `REDIS_URL` on Pro and Mini (zero key/payload inspection).
- **Expected Output Shape:** JSON summary `{redis_version, role, maxmemory_policy, aof_enabled, keyspace: {db0: {keys, expires, avg_ttl}}}`.
- **Why It Matters:** Closes `U-B04-03` (`pro_redis: AUTHORIZATION_REQUIRED`, `mini_redis: AUTHORIZATION_REQUIRED` in `STATE.json:43-44`).

### `DUX-B04-06`: SHA-256 Digest Receipt of Core B04 Source Files Inspected
- **ID:** `DUX-B04-06`
- **Exact Read-Only Command:**
  ```bash
  shasum -a 256 \
    apps/backend-rag/backend/core/collection_registry.py \
    apps/backend-rag/backend/core/embeddings.py \
    apps/backend-rag/backend/core/qdrant_db.py \
    apps/backend-rag/backend/core/redis_manager.py \
    apps/backend-rag/backend/app/core/config.py \
    apps/backend-rag/backend/app/core/database.py \
    apps/backend-rag/backend/app/setup/service_initializer.py \
    apps/backend-rag/backend/services/ingestion/collection_manager.py \
    apps/backend-rag/backend/services/misc/graph_service.py \
    apps/wa-mirror/bridge/pg.ts \
    apps/admin-dashboard-local/app/lib/db.ts \
    apps/remediator/main.py
  ```
- **Inputs:** The 12 store/connection source files inspected in `ANALYSIS.md`.
- **Expected Output Shape:** 12 lines of `<sha256>  <filepath>`.
- **Why It Matters:** Provides the exact `evidence_sha256` values required by the frozen sibling contract (`consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns`) when S1 materializes the B04 store binding rows.

## Adversarial review

A real scoped Codex document review examined source SHA-256 5dc00d53b9e9d84f436f7aed8e8f7577931e24e9fb6082a22396b3bf2f5a83eb. R1-DOCUMENT-REVIEW.json records scope, findings and limitations: REVIEWED_PARTIAL_WITH_BLOCKERS, no full-document or implementation approval. Historical wrong counts/paths/authority proposals do not become executable through attribution. The addendum reconciles actual receipts; this is not an independent code grade. Requested supporting seat: Astra 6 / xhigh; effective runtime identity UNOBSERVED. A fresh independent Opus 5.5 / xhigh exact-head BLUE gate remains required.
