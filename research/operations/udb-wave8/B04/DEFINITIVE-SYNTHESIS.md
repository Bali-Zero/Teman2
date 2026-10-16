---
adversarial_review: codex
---

# B04 current synthesis and historical dispositions

## Current boundary correction (2026-10-16)

Current source SHA256: `e12c366a1e82731b54c4b679dd3abdf320213d9544b94eebcad5c14e9793a9c5`. Current verified suite: 18 passed in both original and clean copies, independently reproduced. Output-boundary defects were corrected and reviewed; valid artifacts remain byte-identical. All older pass counts below describe historical stages. Status remains PARTIAL with block_closed:false and all native unknowns retained.


## Current execution addendum (2026-10-16)

The candidate remains PARTIAL, with block_closed: false. The already prepared hermetic patch was applied once after exact preimage and patch hash verification. The current source suite with admitted receipts passed 14 tests with zero failures and skips; a clean copied root without .agent-receipts also passed 14 tests with zero failures and skips. Both CLI executions exited 0 and reproduced the pinned catalog and binding CSV byte for byte. All 8 original tests and 106 assertion ASTs remain unchanged.

Current preparer observations are source-bound in integration-20261016/CURRENT-SOURCE-TESTS.json, CURRENT-CLEAN-CHECKOUT.json and CURRENT-REGENERATION.json. PATCH-INTAKE.json records original preimages and applied patch provenance. The earlier 2-pass/6-fail run, historical isolated 8-pass receipt and prepared worker checks retain their own timestamps and scope; they are not the current candidate result. Prepared mutation/roundtrip results are retained in PREPARED-VERIFICATION-SUMMARY.json without a new correction round.

The frozen CSV has 6029 rows plus one separate nested delta giving 6030 union leads. This is a lead inventory; the active denominator stays UNKNOWN. Qdrant embedding model/version/dimensions, producer/consumer compatibility, deployed endpoint/principal/store bindings, authenticated Redis metadata and other physical facts remain UNKNOWN or blocked. These executions perform no native store observation and authorize no credential, grant or configuration change.

The coordinator must accept the frozen candidate, issue its official verification receipt, bind the committed head externally and obtain fresh independent review. The authenticated owner availability exception of 2026-10-16 removes the Claude seat dependency while preserving substantive acceptance and reviewer independence. head_sha remains PENDING_DUX_COMMIT until the parent binds it.

The historical body below is superseded wherever it conflicts with this addendum, actual pinned code/output receipts or binding campaign conventions. Historical commands, hypotheses, numbers, seat availability requirements and proposed changes are not implementation approval. Production changes await the ordered later stages; none of the four successors has started.

## Historical synthesis, superseded by the addendum

# DEFINITIVE-SYNTHESIS.md — Block B04: Physical Stores and Connections

- **Campaign:** `universal-db-wave8-20261015`
- **Block:** `B04` — Physical stores and connections
- **Host / Worktree:** `[Mini]` · `/Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed012f9ed072df3ef3d6` (worktree HEAD `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`)
- **Colour / Gear / Role:** `BLUE` · `GEAR 3` · `EXTERNAL PREPARER, NO_DUX`
- **Runtime Identity:** `requested_model=Gemini 4 Argon`, `requested_effort=high`, `effective_runtime_model=UNOBSERVED`, `effective_runtime_effort=UNOBSERVED`, `session_handle=0db3627f-7483-4259-98e1-4bf16babad18`

---

## 1. Correction Pass Accounting (`DUX-NOTE-CORRECTION.md`)

In the prior synthesis turn, the parent test harness executed `pytest research/operations/udb-wave8/B04/tests/test_store_catalog.py` and recorded **`2 passed, 6 failed`**. Those 6 failures were caused by three ungrounded schema/count assumptions in the prior version of [`store_catalog.py`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/store_catalog.py) and [`test_store_catalog.py`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/tests/test_store_catalog.py):

1. **`INPUT-MANIFEST.json` Schema Mismatch:** [`.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json) maps each filename under `"files"` directly to a 64-character lowercase hex SHA-256 **string** (`"REPORT.md": "b86fb261..."`), whereas the prior parser assumed nested `{"sha256": "..."}` dictionaries and failed with `AttributeError: 'str' object has no attribute 'get'`.
2. **`QDRANT-METADATA.json` Schema Mismatch:** [`.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json) records `"collections"` as a **list of 2 SHA-256 hashed collection identity strings** (`["89ce6e199fd05c3301546dd4d16d742a6d8c3e19b9727b6218131850082c3822", "9b3006ccbd028dd90443b74afbbb0d774df7e0f09eb562fc98cd0fcc10f94067"]`, `collection_count: 2`, `raw_collection_names_exported: false`, `points_or_payloads_requested: false`, `model_binding_proved: false`, `access_principal: "UNOBSERVED"`), whereas the prior parser assumed a dictionary keyed by collection name.
3. **Collection Registry AST Structure & Counts:**
   - [`apps/backend-rag/backend/core/collection_registry.py`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/backend-rag/backend/core/collection_registry.py#L14-L98) defines module-level string constant `SKILLS_MIRROR_COLLECTION = "bali_zero_skills_hybrid"`, tuple `CANONICAL_LOGICAL_COLLECTIONS` (**11** canonical logical names), `LOGICAL_TO_PHYSICAL_COLLECTIONS` (**18** logical keys mapping onto **11** distinct physical targets: `tax_genius_hybrid` shared by 4 logical keys; `legal_unified_hybrid_hybrid` shared by 5 logical keys), and `CANONICAL_COLLECTION_ALIASES` (**21** alias keys mapping onto **11** distinct canonical targets).
   - [`apps/graph-engine/src/nuzantara_graph/services/collection_registry.py`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/graph-engine/src/nuzantara_graph/services/collection_registry.py#L18-L41) defines `DEFAULT_COLLECTION = "legal_unified"` and `LOGICAL_TO_PHYSICAL_COLLECTIONS` (**16** logical keys mapping onto **9** distinct physical targets; `0` canonical list, `0` aliases).
   - The prior parser and tests asserted nonexistent `CollectionName` / `COLLECTION_REGISTRY` symbols and false `20 / 20 / 4 / 10` counts.

All three defects are repaired in [`store_catalog.py`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/store_catalog.py) and [`tests/test_store_catalog.py`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/tests/test_store_catalog.py).

---

## 2. Consolidated Adversarial Findings & Dispositions

| Finding ID | Source / Scope | Disposition & Grounded Resolution |
| :--- | :--- | :--- |
| **WIZ-1** | Cross-Registry Qdrant Collection Resolution Drift ([`DUX-SCOPE-CORRECTION.md`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-dux/DUX-SCOPE-CORRECTION.md#L56-L65)) | **ACCEPTED & IMPLEMENTED (`D2`, `WIZ-5`):** [`compare_collection_registries()`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/store_catalog.py#L276-L343) compares `backend-rag` (`18` logical -> `11` distinct physical) and `graph-engine` (`16` logical -> `9` distinct physical), isolating `3` backend-rag-only keys (`bali_zero_skills_hybrid`, `curated_qa`, `nlm_shadow_hybrid`), `1` graph-engine-only key (`v6_cache_vectors`), and the physical target conflict on `balizero_news` (`balizero_news` in `backend-rag` vs `intel_authoritative_sources` in `graph-engine` and [`load_intel_sources.py:25`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/bali-intel-scraper/scripts/load_intel_sources.py#L25)), while confirming `kbli_2025_final -> kbli_2025_final_hybrid` is consistent across both registries. |
| **WIZ-2** | Embedding Cache Key Collisions Across Models/Dimensions ([`embeddings.py:160-163`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/backend-rag/backend/core/embeddings.py#L160-L163)) | **ACCEPTED & IMPLEMENTED (`D1`, `WIZ-6`):** [`inspect_embedding_and_qdrant_sources()`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/store_catalog.py#L406-L526) AST-inspects `EmbeddingCache._get_key` and records static discrepancy `STATIC_SOURCE_DISCREPANCY_NOT_LIVE_PROOF` because `hashlib.sha256(json.dumps(texts, sort_keys=True).encode()).hexdigest()` omits `(provider, model, dimensions)` alongside the `1536` vs `384` fallback paths in [`embeddings.py:288-313`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/backend-rag/backend/core/embeddings.py#L288-L313), [`qdrant_db.py:81-82`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/backend-rag/backend/core/qdrant_db.py#L81-L82), and [`config.py:132-139`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/backend-rag/backend/app/core/config.py#L132-L139). Kept strictly separate from live Qdrant proof. |
| **WIZ-3** | Unbounded / Divergent Asyncpg Pool Initialization & Missing Timeouts | **ACCEPTED & IMPLEMENTED (`D3`, `WIZ-7`):** [`parse_pool_factory_source()`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/store_catalog.py#L529-L560) parses [`POOL-FACTORY-SOURCE.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json) (`174` pool factory candidates across `206` files, `root_complete: false`) and preserves `PG_TARGET_DEPLOYMENT_HASHED_IDENTITY` (`sha8-2bb691c3`) as `PARTIAL`. |
| **WIZ-4** | Writer vs Reader Flat-Payload Contract Verification | **ACCEPTED & IMPLEMENTED (`D4`, `WIZ-4`):** [`inspect_kbli_writer_and_reader()`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/store_catalog.py#L346-L403) inspects [`reindex_kbli_2025_final.py:340-400`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py#L340-L400) (`build_payload`, flat keys `kode`, `kode_kbli`, `kode_kbli_2025`, no `code` key, `EMBEDDING_MODEL = "text-embedding-3-small"` at line 70) against [`QdrantClient._FLAT_PAYLOAD_COLLECTIONS`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/apps/backend-rag/backend/core/qdrant_db.py#L464-L474) (`{"curated_qa", "legal_unified", "tax_genius"}`), flagging `CONFLICT` because `"kbli_2025_final"` is omitted from `_FLAT_PAYLOAD_COLLECTIONS`. |
| **WIZ-8** | Notebook Container Exclusion in Consumer Matrix | **ACCEPTED & IMPLEMENTED (`D6`, `WIZ-8`):** [`summarize_consumer_matrix()`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/store_catalog.py#L649-L720) separates the `67` rows with `store="NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY"` from the `6,029` rows in [`consumer-matrix.csv`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs/consumer-matrix.csv), yielding `5,962` DB consumer candidates (`6,030` union reconciled via [`LEAD-DELTA.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LEAD-DELTA.json)). |

---

## 3. Grounded Store Family Synthesis

### 3.1 PostgreSQL (`pg:fly:sha8-2bb691c3/public` — Status: `PARTIAL`)
- **Pinned Observation ([`LIVE-DB-METADATA.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/LIVE-DB-METADATA.json), SHA-256 prefix `2bb691c3`, `observed_at: 2026-10-15T00:53:34.907490+00:00`, `host: pro`):** `native_metadata.summary` proves `relations: 557`, `actors: 13`, `triggers: 112`, `functions: 85`, `grant_pairs: 4628`, `dependencies: 0`, `foreign_keys: 240`, `activity_groups: 2`.
- **Pool Factories ([`POOL-FACTORY-SOURCE.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/advance-20261013-1640/POOL-FACTORY-SOURCE.json), SHA-256 prefix `d93668cb`, `prior:2bf9ed3c93`):** `174` pool factory candidates across `206` files (`root_complete: false`).
- **Remaining Unknowns:** `U3` (live Fly vs local PostgreSQL deployment identity behind hashed `sha8-2bb691c3`), `U4` (`PgBouncer` / connection proxy status), `U7` (`PG_TARGET_DEPLOYMENT_HASHED_IDENTITY`).

### 3.2 Qdrant (`qdrant:local:http-6333/*` & `qdrant:logical:*` — Status: `UNKNOWN` Live / `CONFLICT` Static)
- **Pinned Live Observation ([`QDRANT-METADATA.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/QDRANT-METADATA.json), SHA-256 prefix `af100a6d`):** `endpoint_kind: "local_http_6333"`, `collection_count: 2`, `collections: ["89ce6e199fd05c3301546dd4d16d742a6d8c3e19b9727b6218131850082c3822", "9b3006ccbd028dd90443b74afbbb0d774df7e0f09eb562fc98cd0fcc10f94067"]`, `raw_collection_names_exported: false`, `points_or_payloads_requested: false`, `model_binding_proved: false`, `access_principal: "UNOBSERVED"`.
- **Live Proof Boundary:** Because `QDRANT-METADATA.json` exports only 2 hashed collection identities without vector dimensions, point counts, payload schemas, or model bindings, `parse_qdrant_metadata()` sets `status: "UNKNOWN"`, `dimension_consistent: None`, `model_binding_proved: False`, and `live_dimension_mismatch_implied: False`. No live collection names, point totals, or live dimension mismatches are claimed.
- **Static Registry & Contract Findings:**
  - `backend-rag` (`11` canonical logical, `18` logical-to-physical -> `11` distinct physical, `21` aliases -> `11` canonical targets) vs `graph-engine` (`16` logical-to-physical -> `9` distinct physical, `0` aliases).
  - `balizero_news` maps to `balizero_news` in `backend-rag` (`collection_registry.py:42`) but `intel_authoritative_sources` in `graph-engine` (`collection_registry.py:30`) and `load_intel_sources.py:25` (`D2`).
  - `reindex_kbli_2025_final.py:340-400` writes flat keys (`kode`, `kode_kbli`, `kode_kbli_2025`), while `QdrantClient._FLAT_PAYLOAD_COLLECTIONS` (`qdrant_db.py:464-474`) lists only `{"curated_qa", "legal_unified", "tax_genius"}` (`D4`).
  - Static config discrepancies (`D1`, `STATIC_SOURCE_DISCREPANCY_NOT_LIVE_PROOF`): `EmbeddingCache._get_key` omits model/provider/dimensions; fallback `384`-dim `all-MiniLM-L6-v2` vs `1536`-dim `text-embedding-3-small`.

### 3.3 Redis (`redis:pro:local`, `redis:mini:local` — Status: `BLOCKED`)
- **Pinned Observations ([`REDIS-PRO-METADATA.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/REDIS-PRO-METADATA.json) prefix `5aa0c11b`, [`REDIS-MINI-METADATA.json`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/.agent-receipts/udb-wave8-inputs-dux/prior/completion-20261015-0831/REDIS-MINI-METADATA.json) prefix `7da9b9f0`):** Both report `status: "AUTHORIZATION_REQUIRED"`, `authentication_attempted: false`, `effective_principal: "UNOBSERVED"`. No Redis server version, key count, ACL, or DB index occupancy is proved (`U5`, `U8`).

### 3.4 SQLite, Filesystem Stores, and Consumer Matrix (`Status: PARTIAL / UNKNOWN`)
- **Consumer Matrix ([`DUX-B04-01.out`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/dux-requests/DUX-B04-01.out)):** `6,029` CSV rows (`167` distinct `store` strings): `3,647` `BLOCKED_DISCOVERY`, `1,731` `RETAINED_TEST_SOURCE`, `317` `PARTIAL_DISCOVERY`, `284` `BLOCKED_RUNTIME_CONTRACT`, `38` `UNMATCHED_CURRENT_SOURCE_PATH`, `8` `BLOCKED_MCP_REACHABILITY`, `2` `ADAPTED_PARTIAL_VERIFIED`, `2` `ADAPTED_ISOLATED_VERIFIED`.
- **Notebook Container Exclusion:** `67` rows carry `store="NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY"`, leaving `5,962` DB consumer candidates (`6,030` union with `LEAD-DELTA.json`).
- **SQLite / DuckDB / RocksDB / Pickles (`U6`, `U9`, `U10`):** Static consumer references exist in `consumer-matrix.csv`, while live file inventory (`wal_mode`, byte sizes, open-handle locks) remains uncollected (`UNKNOWN`).

---

## 4. Unknowns Register (`U1`–`U11`)

| ID | Status | Description |
| :--- | :--- | :--- |
| **U1** | `OPEN` | Live Qdrant unhashed collection names, vector dimensions, distance metrics, point counts, and payload schemas behind the 2 hashed local identities in `QDRANT-METADATA.json` and any remote Qdrant Cloud instance. |
| **U2** | `OPEN` | Live Qdrant access principal (`access_principal: "UNOBSERVED"`) and TLS/API-key posture. |
| **U3** | `OPEN` | Unhashed target PostgreSQL deployment identity (`local` vs `fly`) behind `LIVE-DB-METADATA.json` (`sha8-2bb691c3`). |
| **U4** | `OPEN` | Live PostgreSQL `max_connections`, `PgBouncer` pooling mode, and per-role connection limits. |
| **U5** | `OPEN` | Live Redis keyspace occupancy, TTL policies, eviction policy, and ACL principal on Pro and Mini (`AUTHORIZATION_REQUIRED`). |
| **U6** | `OPEN` | Live SQLite/DuckDB/RocksDB on-disk file sizes, `journal_mode` (`WAL` vs `DELETE`), and concurrent writer locks across hosts. |
| **U7** | `OPEN` | `PG_TARGET_DEPLOYMENT_HASHED_IDENTITY` mapping from `sha8-2bb691c3` to physical host/cluster. |
| **U8** | `OPEN` | Authenticated Redis `INFO` / `ACL WHOAMI` receipts on Pro and Mini (`REDIS-PRO-METADATA.json`, `REDIS-MINI-METADATA.json`). |
| **U9** | `OPEN` | Resolution of `3,647` `BLOCKED_DISCOVERY` and `284` `BLOCKED_RUNTIME_CONTRACT` rows in `consumer-matrix.csv`. |
| **U10** | `OPEN` | Live verification of filesystem JSON/JSONL/pickle state stores (`data/*.pkl`, KG exports, queue state files). |
| **U11** | `CLOSED (STATIC)` | Full distribution of the `6,029` rows in `consumer-matrix.csv` (`5,962` DB consumer candidates + `67` `NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY` exclusions) verified via [`DUX-B04-01.out`](file:///Users/nuzantara/nuzantara/.worktrees/db-udb-b04-stores/research/operations/udb-wave8/B04/dux-requests/DUX-B04-01.out). |

## Adversarial review

A real scoped Codex document review examined source SHA-256 11281c85f42f95bbd43826581ba06276bbc69c2948528fe427e59829c604d0d4. R1-DOCUMENT-REVIEW.json records scope, findings and limitations: REVIEWED_PARTIAL_WITH_BLOCKERS, no full-document or implementation approval. Historical wrong counts/paths/authority proposals do not become executable through attribution. The addendum reconciles actual receipts; this is not an independent code grade. Requested supporting seat: Astra 6 / xhigh; effective runtime identity UNOBSERVED. A fresh independent Opus 5.5 / xhigh exact-head BLUE gate remains required.
