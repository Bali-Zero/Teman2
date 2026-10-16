---
adversarial_review: codex
---

> Historical research retained for traceability. Superseded statements and commands are BLOCKED FOR IMPLEMENTATION. Current evidence is the synthesis addendum, pinned receipt and binding Dux rulings. No production/native action is authorized here.

# UDB Wave 8 — Block B04: Production Defects Handed Forward to S2/S3

- **Campaign / Block:** `universal-db-wave8-20261015` / `B04` (*Physical stores and connections*)
- **Colour / Gear / Role:** `BLUE` / `GEAR 3` / `EXTERNAL PREPARER, NO_DUX`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Scope Rule (`DUX-SCOPE-CORRECTION.md` §1–§2):** `.github/workflows/fly-deploy.yml:3-7` deploys `nuzantara-rag` on any push to `main` touching `apps/backend-rag/**` (excluding only docs and `**/tests/**`). B04's manifest `owned_code` is `"own store reports/adapters only"` and `BATTLE.md:7` bars production redesign before S2. Accordingly, B04 makes **zero edits** under `apps/**` and hands the following verified source defects forward to the S2/S3 implementation lanes with exact `file:line` and SHA-256 pins.

---

## D1 (`CE-B04-01`) — `_global_embedding_cache` Key Omits `(provider, model, dimensions)`

- **Target File:** `apps/backend-rag/backend/core/embeddings.py`
- **Pinned SHA-256 (`DUX-B04-06.out`):** `fd6b78142b20ae1b6eba8567c18af2852c293b57280e95533e9ec13f5f73f358`
- **Status:** `PARTIAL` (Confirmed in source; unverified at deployed production runtime)
- **Verified Facts:**
  - `EmbeddingCache._get_key(self, texts: list[str]) -> str` (`apps/backend-rag/backend/core/embeddings.py:160-163`) computes `hashlib.md5(serialized.encode()).hexdigest()` over `json.dumps(texts, sort_keys=True)` alone, omitting `provider`, `model`, and `dimensions`.
  - A single module-level `_global_embedding_cache = EmbeddingCache(max_size=1000, ttl_seconds=3600)` (`embeddings.py:203-205`) is shared by all `EmbeddingsGenerator` instances in the process via `await _global_embedding_cache.get(texts)` (`embeddings.py:358`) and `await _global_embedding_cache.set(texts, result)` (`embeddings.py:374`).
  - `EmbeddingsGenerator._init_openai` (`embeddings.py:253-263`) hard-codes `self.dimensions = 1536` regardless of `self.model`.
- **Production Reachability Qualification (`DUX-SCOPE-CORRECTION.md` §2 D1):**
  - On Fly.io production, `apps/backend-rag/fly.toml:37` sets `EMBEDDING_PROVIDER = 'openai'`, `requirements-prod.txt:110-111` removes `sentence-transformers`, and `ImportError` in `_init_sentence_transformers` (`embeddings.py:305-315`) falls back to OpenAI.
  - However, `requirements.lock.txt:4132` pins `sentence-transformers==5.7.0` for local/Pro environments, and two OpenAI `EmbeddingsGenerator` instances configured with different `model` names in one process share `_global_embedding_cache`.
- **Recommended S3 Cure:** Include `(self.provider, self.model, self.dimensions)` in `EmbeddingCache._get_key` and validate `self.dimensions` against the configured OpenAI model name.

---

## D2 (`CE-B04-02` & `WIZ-5` / `WIZ-6`) — Cross-Registry Alias Asymmetry and Producer/Consumer Conflict on `balizero_news` vs `intel_authoritative_sources`

- **Target Files:**
  - `apps/backend-rag/backend/core/collection_registry.py` (`sha256: e3fa7082b36e52f2099be36eab013c6c7b02a4175c1a125a38be5b494add4abf`)
  - `apps/graph-engine/src/nuzantara_graph/services/collection_registry.py`
  - `apps/bali-intel-scraper/scripts/load_intel_sources.py`
  - `apps/bali-intel-scraper/scripts/load_intel_sources_streaming.py`
  - `scripts/ci/ingest_target_lint.py`
- **Status:** `CONFLICT` (Cross-registry producer/consumer target mismatch; fix direction requires S2 architectural decision)
- **Verified Facts:**
  1. In `apps/backend-rag/backend/core/collection_registry.py`:
     - `LOGICAL_TO_PHYSICAL_COLLECTIONS` (`:34-56`) maps 18 keys to 11 physical collections, including `"balizero_news": "balizero_news"` (`:51`).
     - `CANONICAL_COLLECTION_ALIASES` (`:58-82`, 21 entries at `:59-81`) maps `"intel_authoritative_sources": "balizero_news"` (`:76`), `"kbli_2025_final_hybrid": "kbli_2025_final"` (`:61`), and `"legal_unified_hybrid_hybrid": "legal_unified"` (`:69`).
     - `resolve_collection_name` (`:85-87`) looks up `LOGICAL_TO_PHYSICAL_COLLECTIONS.get(collection_name, collection_name)` without consulting `CANONICAL_COLLECTION_ALIASES`.
     - `is_known_collection` (`:90-92`) checks `collection_name in LOGICAL_TO_PHYSICAL_COLLECTIONS` only (and currently has zero non-test callers in `apps/backend-rag/backend`).
  2. In `apps/graph-engine/src/nuzantara_graph/services/collection_registry.py:20`:
     - `LOGICAL_TO_PHYSICAL_COLLECTIONS` maps in the **opposite direction**: `"balizero_news": "intel_authoritative_sources"`, and also includes `"v6_cache_vectors": "v6_cache_vectors"` (`:25`), which is absent from `backend-rag`'s registry.
  3. In `apps/bali-intel-scraper/scripts/load_intel_sources.py:25` and `load_intel_sources_streaming.py:20`:
     - Both producers write directly to `COLLECTION_NAME = "intel_authoritative_sources"`.
  4. In `scripts/ci/ingest_target_lint.py:89-133`:
     - Documents open findings `WIZ-4` (`kbli_notebook_expert`), `WIZ-5` (`kbli_tka` -> `kbli_tka_hybrid`), `WIZ-6` (`intel_authoritative_sources` vs `balizero_news`), `WIZ-7` (`nlm_shadow_hybrid` in registry but absent from the 2026-08-25 14-collection probe), and `WIZ-8` (`collective_memories`, `test`, `balizero_news_history`, `kb_politics_hier_v1`).
- **Why B04 Must Not Drive-By Edit `resolve_collection_name` (`DUX-SCOPE-CORRECTION.md` §2 D2):**
  - Making `resolve_collection_name("intel_authoritative_sources")` return `"balizero_news"` in `backend-rag` would silently re-route write callers (`oracle_ingest.py:116`, `legal_ingestion_service.py:315, 508`) while `bali-intel-scraper` and `graph-engine` continue targeting `"intel_authoritative_sources"`.
- **Recommended S2/S3 Cure:** Reconcile `backend-rag` and `graph-engine` into a single canonical collection registry after deciding whether `intel_authoritative_sources` and `balizero_news` remain distinct physical collections or merge.

---

## D3 (`CE-B04-03`) — Qdrant Estate Drift Between `CollectionManager.collection_definitions` and `collection_registry.py`

- **Target Files:**
  - `apps/backend-rag/backend/services/ingestion/collection_manager.py` (`sha256: 16ef3e7bd869e4f47db715f84f3552ad4c0015d6e877cd7605de2fa83030e39a`)
  - `apps/backend-rag/backend/core/qdrant_db.py` (`sha256: 5b67c71400cbb38154f32c7f85ddf6b1fa8ec24e5d54c4c05de84fa4ceac400e`)
  - `apps/backend-rag/backend/app/core/config.py` (`sha256: 1e103424bc2cba0bfb1a432c6ca43ee581d41ab182507a6c1740c3bd30092f3e`)
  - `docs/runbooks/qdrant-estate-reconciliation.md`
- **Status:** `PARTIAL` (Static registry drift confirmed; current live production Qdrant estate unverified in Wave 8)
- **Verified Facts:**
  - `collection_manager.py:51-60` and `docs/runbooks/qdrant-estate-reconciliation.md:8-50` document (from a dated probe on `2026-07-05`, not a Wave 8 observation) that only 6 of the 20 entries in `CollectionManager.collection_definitions` matched live collections at that date, 14 were dead names (including `"collective_memories"`, now a PostgreSQL table, plus 5 other names absent from `collection_registry.py`: `"bali_zero_team"`, `"zantara_books"`, `"cultural_insights"`, `"property_listings"`, `"property_knowledge"`), and 8 live collections at that date (`legal_unified_hybrid_hybrid`, `legal_unified_2026`, `kbli_2025_final_oss`, `kbli_2025_final_hybrid`, `bali_zero_skills_hybrid`, `intel_authoritative_sources`, `kbli_tka_hybrid`, `garuda_assets`) had no entry in `collection_definitions`.
  - `QdrantClient.__init__` (`qdrant_db.py:289`) and `Settings.qdrant_collection_name` (`config.py:205`) default to `"knowledge_base"`, which is absent from both `collection_registry.py` and `collection_manager.py`.
- **Recommended S3 Cure:** After an admitted read-only production Qdrant metadata probe establishes the current live collection inventory, regenerate `collection_definitions` from `collection_registry.py` and retire dead entries.

---

## D4 (`CE-B04-04`) — Writer Flat-Payload Layout vs `QdrantClient._FLAT_PAYLOAD_COLLECTIONS` Omission for `kbli_2025_final`

- **Target Files:**
  - `apps/backend-rag/backend/core/qdrant_db.py` (`sha256: 5b67c71400cbb38154f32c7f85ddf6b1fa8ec24e5d54c4c05de84fa4ceac400e`)
  - `apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py`
  - `apps/backend-rag/backend/app/routers/kbli_notebook.py`
- **Status:** `CONFLICT` (Static writer-vs-reader contract mismatch; live search filter impact unverified)
- **Verified Facts:**
  - `reindex_kbli_2025_final.py:340-400` (`build_payload`) writes flat top-level payload keys (`"kode"`, `"kode_kbli"`, `"kode_kbli_2025"`, `"judul"`, `"doc_type"`, `"version"`, `"sektor"`, `"pma_status"`, etc.; note: it emits `"kode"` / `"kode_kbli"` / `"kode_kbli_2025"`, never `"code"`).
  - `QdrantClient._FLAT_PAYLOAD_COLLECTIONS` (`qdrant_db.py:464-474`) lists only `{"legal_unified", "tax_genius", "curated_qa"}`. Because `_include_flat_payload_filters` (`qdrant_db.py:476-478`) checks `canonicalize_collection_name(self.collection_name) in self._FLAT_PAYLOAD_COLLECTIONS`, and `"kbli_2025_final_hybrid"` canonicalizes to `"kbli_2025_final"` (`collection_registry.py:61`), `_convert_filter_to_qdrant_format` (`qdrant_db.py:385-459`) generates nested `"metadata.<key>"` conditions only (`include_flat_payload=False`) when called on `kbli_2025_final_hybrid`.
  - `kbli_notebook.py:493-524` bypasses `QdrantClient.search` and posts directly to `/points/scroll` with explicit dual flat+nested keys (`"kode_kbli"`, `"kode"`, `"metadata.kode"`, `"metadata.kode_kbli"`, `"metadata.kode_kbli_2025"`, `"doc_type"`, `"metadata.doc_type"`).
- **Recommended S3 Cure:** Add `"kbli_2025_final"` to `QdrantClient._FLAT_PAYLOAD_COLLECTIONS` after verifying all KBLI callers and live payload schemas.

---

## D5 (`CE-B04-05`) — PostgreSQL Pool Parameter & Env-Var Resolution Divergence Across Monorepo Consumers

- **Target Files:**
  - `apps/backend-rag/backend/app/setup/service_initializer.py` (`sha256: 6b02f424902a7d791713a81e52fc44e30a49201f263616bf36a0f71db25f0f09`)
  - `apps/backend-rag/backend/app/core/database.py` (`sha256: b4c8d3b606e7d8eac8795c9a9fe08595a8d2fd1b8d0be4e405d304490c8163bf`)
  - `apps/graph-engine/src/nuzantara_graph/services/kg_store.py`
  - `apps/graph-engine/src/nuzantara_graph/curiosity/proposals.py`
  - `apps/wa-mirror/bridge/pg.ts` (`sha256: baa7b55798c0e909623dce0c7629baada04a3a34ebaaff2ac8dcc3d9882e865b`)
  - `apps/admin-dashboard-local/app/lib/db.ts` (`sha256: 826a41c8e532f3d2ce267b25c34c208d203b6d669fb4b4033cdce82cb9bc0919`)
- **Status:** `PARTIAL` (Pool parameter divergence confirmed in source)
- **Verified Facts:**
  - Inside `apps/backend-rag`, both `service_initializer.py:511` and `database.py:40` register the canonical JSONB codec via `init_asyncpg_connection`, but their pool parameters diverge:
    - `service_initializer.py:495-538`: `min_size=2`, `max_size=10`, `command_timeout=30`, `max_inactive_connection_lifetime=30.0`, `statement_cache_size=0`, strips `sslmode=disable` into `ssl=False`, and executes `SET statement_timeout = '30s'`.
    - `database.py:16-43` (`get_db_pool`, documented for scripts/testing): `min_size=2`, `max_size=5`, `command_timeout=60`, `max_inactive_connection_lifetime=300`, `statement_cache_size=0`, no `SET statement_timeout`, no `sslmode` stripping.
  - In `apps/graph-engine`:
    - `kg_store.py:42-47` creates `asyncpg.create_pool(self.database_url, min_size=2, max_size=10, command_timeout=30)` **without** `statement_cache_size=0`, `max_inactive_connection_lifetime`, or `init_asyncpg_connection`.
    - `curiosity/proposals.py:46-59` creates `asyncpg.create_pool(self.database_url, min_size=2, max_size=5, command_timeout=30, max_inactive_connection_lifetime=60.0)` **without** `statement_cache_size=0` or `init_asyncpg_connection`.
  - In Node consumers:
    - `apps/wa-mirror/bridge/pg.ts:21-40` resolves `WA_MIRROR_DATABASE_URL ?? DATABASE_URL` (`max=5`, `idleTimeoutMillis=30000`, `connectionTimeoutMillis=5000`).
    - `apps/admin-dashboard-local/app/lib/db.ts:10-24` resolves `DATABASE_URL_LOCAL` then `FLY_TUNNEL_URL` (`max=3`).
- **Recommended S3 Cure:** Align `asyncpg.create_pool` helpers across `database.py` and `apps/graph-engine` to enforce `statement_cache_size=0` (PgBouncer compatibility) and explicit idle connection recycling.

---

## D6 (`CE-B04-06`) — Lexical Store Signals on Non-Consumer / Config Rows in `consumer-matrix.csv`

- **Target Input:** `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`)
- **Status:** `EVIDENCED` (In frozen input CSV)
- **Verified Facts:**
  - `consumer-matrix.csv` has `6029` data rows (lines 2–6030; line 1 is header).
  - Row `src_dd4fbda47e51f1e3` (`.github/dependabot.yml`, `consumer-matrix.csv:2`) has `store=qdrant` and `disposition=BLOCKED_DISCOVERY` based on a lexical match (`qdrant:26`).
  - 67 rows (`NOTEBOOK-CONTAINER-REFERENCE-NLM-01` .. `67`) carry `store="NOTEBOOK_CONTAINER_REFERENCE; NOT_DATABASE_CONSUMER_IDENTITY"` and `disposition="PARTIAL_DISCOVERY"` (`DUX-B04-01.out:19`).
  - Note: The three IDs cited in B04's earlier `ANALYSIS.md` (`repo_0e2c9f158a76731f`, `repo_5d54fa59301e6b3f`, `repo_e4964f782237c1df`) do **not** exist in `consumer-matrix.csv` (0 occurrences) and have been purged from the synthesis and adapter.

## Adversarial review

A real scoped Codex document review examined source SHA-256 655bf769ff3a926104b34dcc14c39fb0439effb3f18e347879c394edc4d948a1. R1-DOCUMENT-REVIEW.json records scope, findings and limitations: REVIEWED_PARTIAL_WITH_BLOCKERS, no full-document or implementation approval. Historical wrong counts/paths/authority proposals do not become executable through attribution. The addendum reconciles actual receipts; this is not an independent code grade. Requested supporting seat: Astra 6 / xhigh; effective runtime identity UNOBSERVED. A fresh independent Opus 5.5 / xhigh exact-head BLUE gate remains required.
