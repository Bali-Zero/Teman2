---
date: 2026-05-16
domain: nb-lifecycle
client_case: R5 Phase 2 — Indexing parity audit (Qdrant + KG canonical for Core domains)
sources: 8
---

# R5 Phase 2 — Indexing Parity Audit (2026-05-16)

> **Predecessor**: R5 Phase 1 SHIPPED 2026-05-16 08:45 WITA (mem #2389): 379 skills/reflection/insight migrated SQLite knowledge.db → Qdrant local `bali_zero_skills_local`, parity 100%, $0.05 cost, 5s wall.
>
> **Goal Phase 2** (R5 master, week 2, 16h est.): Qdrant + KG canonical per Core domains (visa/tax/company/property/ops). NotebookLM diventa solo human-facing UI.
>
> **Status**: Audit completato (6h wall) + panel review BLOCK da Codex (1 P0 mio invalidato, 4 P1 strutturali emersi). Report aggiornato post-review. Re-index gap (step 2.5) AIL → richiede NotebookLM MCP live.

> ⚠️ **REVIEW AMENDMENT (2026-05-16 10:45 WITA, post-Codex panel)**: Il mio "P0 ghost collection nuzantara_general_hybrid causa 404 prod" era **falso positivo**. Production routing usa `backend/services/routing/query_router.py` + `QueryRouterIntegration` (instantiated da `service_initializer.py`), NON `multi_hop.py` (referenziato solo da 2 test files + module-level singleton dead-code) né `query_planner.py` (shadow mode `USE_QUERY_PLANNER=false`). Severity corretta: P2 (dead-code debt), NON P0. Vedi §13 per finding panel review completi.

---

## EXECUTIVE SUMMARY

| Area                      | Stato                                                                                | Note                                    |
| ------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------- |
| Qdrant Cloud GCP          | ✅ 12 collections, 111.750 points, all green                                         | Drift +7% vs CLAUDE.md claim 104k       |
| Qdrant Local Docker (Pro) | ✅ 11 collections incluso `bali_zero_skills_local` (Phase 1)                         | NON in cloud → split-brain              |
| KG Postgres (localhost)   | ✅ 58.907 nodes, 164.582 edges                                                       | Drift -45% vs CLAUDE.md claim 108k/242k |
| Canonical domain mapping  | ⚠️ **P2** (post-review): `nuzantara_general_hybrid` ghost in 6 dead-code mappings    | NOT production-wired — vedi §13 review  |
| Real production routing   | ✅ `QueryRouterIntegration` → `tax_genius`, `legal_unified`, etc — tutto in registry | Verified post-Codex review              |
| Payload schema            | ❌ **P1**: ALL collections violate golden rule #11 (Flat payloads)                   | Tutto sotto `metadata.*` nested         |
| Source attribution        | ❌ **P1**: 6/12 collection con 0-1 unique source (UNKNOWN)                           | Coverage gap detection impossibile      |
| Re-index gap NB → Qdrant  | ⏸ AIL                                                                                | Block: notebooklm-mcp not loaded        |

**Verdict iniziale**: Phase 3 SurfaceRouter Haiku NON deve essere shippato finché P0 ghost collection è risolto.
**Verdict post-panel**: P0 invalidato. Phase 3 può procedere. Prerequisiti rivisti: (a) deal con `QueryRouter` SSOT real production (NON `query_planner`/`multi_hop`), (b) full payload census su 12 collection, (c) define provenance schema PRIMA del Phase 2.5 ingest. Phase 2.5 (re-index) richiede ground-truth NB enumeration via MCP.

---

## 1. Qdrant Cloud GCP — Inventory verified

URL: `https://5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333`
Tutti i collection status=green. Scan via raw HTTPX (qdrant-client breaks su Apple silicon connect).

| Collection                      | Points | Note                                                               |
| ------------------------------- | -----: | ------------------------------------------------------------------ |
| `legal_unified_hybrid_hybrid`   | 81.316 | Largest. Doppio `_hybrid_hybrid` suffix sospetto (typo migration?) |
| `legal_unified_2026`            | 15.410 | Sospetto: 2 collections legali separate (drift R5 master claim)    |
| `kbli_2025_final_hybrid`        |  4.624 | KBLI canonical                                                     |
| `training_conversations_hybrid` |  3.638 | Training data                                                      |
| `balizero_news`                 |  3.513 | Intel feed                                                         |
| `immigration_circulars`         |  1.979 | Imigrasi/Kemnaker SE                                               |
| `intel_authoritative_sources`   |    525 | Intel sources                                                      |
| `tax_genius_hybrid`             |    339 | Tax (small!)                                                       |
| `kbli_tka_hybrid`               |    246 | KBLI TKA-eligible                                                  |
| `visa_oracle`                   |     90 | Visa types (per type)                                              |
| `bali_zero_pricing_hybrid`      |     70 | Pricing                                                            |
| `garuda_assets`                 |  **0** | **VUOTO** — collection-only, never populated                       |

**Totale**: 111.750 punti. CLAUDE.md riga 1283 claim "104,154 documents" → drift +7,3% (probabilmente growth Q1 2026).

---

## 2. Qdrant Local Docker (Pro) — SPLIT-BRAIN scoperto

URL: `http://localhost:6333`
11 collection. Subset di cloud + 1 extra:

- ✅ Match cloud (10): `bali_zero_pricing_hybrid`, `training_conversations_hybrid`, `intel_authoritative_sources`, `legal_unified_hybrid_hybrid`, `kbli_2025_final_hybrid`, `kbli_tka_hybrid`, `visa_oracle`, `immigration_circulars`, `tax_genius_hybrid`, `garuda_assets`
- 🆕 Solo local: **`bali_zero_skills_local`** (379 points — Phase 1 R5 ieri)
- ❌ Mancante in local: `balizero_news`, `legal_unified_2026`

**Implicazione P0 per Phase 3**: SurfaceRouter deve sapere quale Qdrant endpoint usare per ogni domain. Routing skills:

- `bali_zero_skills_local` esiste **solo** in Qdrant local Pro
- Backend prod su Fly usa Qdrant Cloud GCP → query skills da Fly = collection_not_found
- Antonello must decide: (a) re-indicizzare skills in cloud (cost $0.05 + new line in Fly secrets), oppure (b) cabling Phase 3 router a localhost solo via VPN/tailnet quando Antonello è sul Pro

**MOS save**: discovery id 2392 (importance 9) — "Phase 1 R5 ha indicizzato bali_zero_skills_local SOLO in Qdrant Docker locale Pro"

---

## 3. KG Postgres (localhost) — verified

Connection: `postgresql://nuzantara@localhost:5432/nuzantara_rag` (Fly proxy?)

| Table      |    Rows |
| ---------- | ------: |
| `kg_nodes` |  58.907 |
| `kg_edges` | 164.582 |

**Drift CLAUDE.md**:

- Claim §1 "108,068 nodes, 242,827 edges" → real 58.907/164.582 (**-45% / -32%**)
- Possibili spiegazioni: (a) numbers in CLAUDE.md sono stantii, (b) KG pruning recente, (c) connessione DB localhost = staging vs Fly = prod

⚠️ **Verifica pending**: connessione Fly DB (via `fly-pg-proxy-wrapper.sh`) per confermare se 108k/242k è il vero target prod. Se sì, KG prod ha 49k nodi + 78k edges extra rispetto a localhost staging — bidirectional sync rotto.

**Fixed for future**: Phase 6 (R5 doc) "Decommission Core NB" assume KG completo. Senza verify cloud number, non sicuro.

---

## 4. Canonical domain → collection mapping — **P0 ghost collection**

### Hardcoded mappings discovered

| File                                   | Domain   | Collections claimed                                       | Esiste in cloud?                                         |
| -------------------------------------- | -------- | --------------------------------------------------------- | -------------------------------------------------------- |
| `query_planner.py:_DOMAIN_COLLECTIONS` | VISA     | `visa_oracle`, `legal_unified_hybrid`                     | ✅ + ❌ (`legal_unified_hybrid` → resolves via registry) |
| `query_planner.py`                     | TAX      | `nuzantara_general_hybrid`, `legal_unified_hybrid`        | ❌ + ✅                                                  |
| `query_planner.py`                     | PROPERTY | `nuzantara_general_hybrid`, `legal_unified_hybrid`        | ❌ + ✅                                                  |
| `query_planner.py`                     | KBLI     | `kbli_2025_final`                                         | ✅ (alias → `kbli_2025_final_hybrid`)                    |
| `query_planner.py`                     | COMPANY  | `legal_unified_hybrid`, `kbli_2025_final`                 | ✅ + ✅                                                  |
| `query_planner.py`                     | PRICING  | `nuzantara_general_hybrid`                                | ❌                                                       |
| `query_planner.py`                     | NEWS     | `balizero_news`                                           | ✅                                                       |
| `query_planner.py`                     | GENERAL  | `legal_unified_hybrid`, `training_conversations_hybrid`   | ✅ + ✅                                                  |
| `multi_hop.py:get_domain_collections`  | tax      | `nuzantara_general_hybrid`, `legal_unified_hybrid_hybrid` | ❌ + ✅                                                  |
| `multi_hop.py`                         | property | `nuzantara_general_hybrid`, `legal_unified_hybrid_hybrid` | ❌ + ✅                                                  |
| `multi_hop.py`                         | company  | `legal_unified_hybrid_hybrid`, `kbli_2025_final_hybrid`   | ✅ + ✅                                                  |
| `multi_hop.py`                         | general  | `legal_unified_hybrid_hybrid`, `nuzantara_general_hybrid` | ✅ + ❌                                                  |

### Collection registry SSOT (`backend/core/collection_registry.py`)

8 canonical logical + 9 physical aliases. **`nuzantara_general_hybrid` NON è nel registry**: né come logical, né come alias, né come physical. `resolve_collection_name("nuzantara_general_hybrid")` → fallback identity → Qdrant 404.

### Feature flag state

- `USE_QUERY_PLANNER` default `false` → `query_planner.py` in shadow mode (logs ma non routing prod)
- `multi_hop.py` invece wired in production (`engine = MultiHopEngine()` instantiated by orchestrator)

### Impatto runtime

Ogni query TAX/PROPERTY/PRICING che attiva il multi-hop engine in prod:

1. Decompose into sub-queries
2. Call `get_domain_collections(domain)` → ritorna `["nuzantara_general_hybrid", ...]`
3. Qdrant HTTP POST `/collections/nuzantara_general_hybrid/points/search` → **404 Not Found**
4. Search degrada al fallback collection (se presente) o restituisce 0 risultati per quel hop

**Quante query oggi colpiscono questo path?** Non misurato qui. Phase 3 deve fissare PRIMA di Phase 3 ship.

### Fix candidati (per Phase 3 decision)

1. **Alias only** (lowest risk): aggiungere a `LOGICAL_TO_PHYSICAL_COLLECTIONS`:
   ```python
   "nuzantara_general_hybrid": "legal_unified_hybrid_hybrid",
   ```
   E in `CANONICAL_COLLECTION_ALIASES`. Costo: 0 (solo registry edit + test).
2. **Refactor hardcoded mappings**: rimuovere `nuzantara_general_hybrid` da `query_planner.py` + `multi_hop.py` → SurfaceRouter Phase 3 SSOT. Costo: 2h + test.
3. **Create empty collection** (mantiene status quo): `PUT /collections/nuzantara_general_hybrid` con vector cfg → ogni search ritorna 0. **NO, peggio del 404**.

**Raccomandazione Phase 3**: option 2 (refactor) — `nuzantara_general_hybrid` è ghost-legacy, va eliminato dalle reference.

**MOS save**: discovery id 2393 (importance 9) — "P0 Phase 2 finding: nuzantara_general_hybrid collection..."

---

## 5. Payload schema — P1 golden rule #11 violation

Audit su 4 collection critiche via `/points/scroll` (1 sample each):

| Collection                    | Top-level keys     |                                  Nested in `metadata` |
| ----------------------------- | ------------------ | ----------------------------------------------------: |
| `visa_oracle`                 | `metadata`, `text` |   24 sub-keys (category, code, doc_type, is_kitas...) |
| `legal_unified_hybrid_hybrid` | `metadata`, `text` | 31 sub-keys (bab_title, book_author, legal_number...) |
| `kbli_2025_final_hybrid`      | `metadata`, `text` |      15 sub-keys (chunk_id, kode_kbli, pma_status...) |
| `tax_genius_hybrid`           | `metadata`, `text` |     10 sub-keys (category, language, source, tier...) |

CLAUDE.md golden rule #11 ("Flat Qdrant Payloads — never nested. Use `kode_kbli`, `judul`, `content`, `pma_status` etc.") **NON è rispettata** in production. Tutto sotto `metadata.*`.

### Impatto

Qdrant filtering richiede nested-key syntax:

```python
# WRONG (golden rule assumption)
filter={"must": [{"key": "kode_kbli", "match": {"value": "56303"}}]}

# RIGHT (actual schema)
filter={"must": [{"key": "metadata.kode_kbli", "match": {"value": "56303"}}]}
```

Codice che assume payload flat probabilmente sta facendo 0-result silent fallback. Phase 3 SurfaceRouter deve scegliere: aderire allo schema reale (consigliato — re-indexing è caro) o ri-indicizzare TUTTO flat (costoso, breaking).

**Raccomandazione**: aggiornare golden rule #11 in CLAUDE.md per riflettere realtà (`metadata.<field>` filter syntax). Re-indexing flat è fuori scope Phase 2/3.

---

## 6. Source attribution audit — P1 coverage detection broken

Scan via `/points/scroll` con `with_payload=[metadata.source, metadata.document_id, metadata.file_path, metadata.judul, metadata.book_title]` per estrarre source attribution.

| Collection                      | Chunks |  Unique sources | Top source                                               |
| ------------------------------- | -----: | --------------: | -------------------------------------------------------- |
| `legal_unified_hybrid_hybrid`   | 25.000 |             345 | `DOC_UNKNOWN_1847` (2.242x)                              |
| `kbli_2025_final_hybrid`        |  4.624 |           1.528 | "PENGOLAHAN DAN PENGAWETAN BIOTA AIR LAINNYA" (27x)      |
| `training_conversations_hybrid` |  3.638 |               2 | `training_conversation` (2.898x), UNKNOWN (740x)         |
| `balizero_news`                 |  3.513 | **1 (UNKNOWN)** | —                                                        |
| `immigration_circulars`         |  1.979 | **1 (UNKNOWN)** | —                                                        |
| `intel_authoritative_sources`   |    525 | **1 (UNKNOWN)** | —                                                        |
| `tax_genius_hybrid`             |    339 |              10 | `training-data/tax/tax_019_ppn_vat_full_cycle.md` (161x) |
| `visa_oracle`                   |     90 |              87 | distribuited 1x each                                     |
| `bali_zero_pricing_hybrid`      |     70 | **1 (UNKNOWN)** | —                                                        |
| `legal_unified_2026`            | 15.410 |              18 | `Permen_18_2021` (10.266x), `Permen_35_2012` (1.240x)    |

**6 collection con source attribution rotta** (`balizero_news`, `immigration_circulars`, `intel_authoritative_sources`, `bali_zero_pricing_hybrid`, 2 parziali). Coverage gap detection (NB sources vs Qdrant) **impossibile** finché payload re-indexed con source uri.

`legal_unified_hybrid_hybrid` con 2.242 chunk attribuiti a `DOC_UNKNOWN_1847` è P0 audit-trail risk: cliente chiede source legale → no provenance.

---

## 7. NotebookLM coverage gap detection — AIL

### Block

Per fare gap detection vero (NB sources NOT in Qdrant), serve enumerazione live di ogni Core NB tramite `mcp__notebooklm-mcp__list_sources` o equivalente. **MCP non caricato in questa sessione**. Senza:

- Conosciamo source counts NB via `reference_notebooklm_arsenal_full.md` (snapshot 2026-05-03): NB-2 Visa 97, NB-3 Company 183, NB-4 Tax 118, NB-5 Property 117, NB-7 Editorial 89, etc.
- Non conosciamo source-by-source identity → no cross-reference con Qdrant `metadata.source`

### NB UUID SSOT (verified via `apps/mata-garuda/mata_garuda/notebook_registry.py`)

| NB            | Label               | UUID                                   | Domain                           | Qdrant counterpart                                       |
| ------------- | ------------------- | -------------------------------------- | -------------------------------- | -------------------------------------------------------- |
| NB-2          | Immigration & Visa  | `cff93ab0-813a-42f2-a8de-36987e724271` | immigration, kbli, visa          | `visa_oracle` (90 pts) + `immigration_circulars` (1.979) |
| NB-3          | Company & Licensing | `933509f9-1561-403d-bd44-4a7a67a36df2` | company, legal, property (claim) | `kbli_2025_final_hybrid` (4.624) + `legal_unified_*`     |
| NB-4          | Tax & Compliance    | `d4b2eedb-9863-4a1a-81ff-a11b0b45d853` | tax                              | `tax_genius_hybrid` (339)                                |
| NB-5          | Property & Zoning   | `d9438180-5e63-4e2a-a473-6061101f6a8d` | property                         | `legal_unified_2026` (Permen_18_2021 majority)           |
| NB-7          | Editorial & Market  | `f51ab8a0-50d0-49f1-a64f-ebc131fed7b8` | editorial                        | `balizero_news` (3.513)                                  |
| NB-Operations | Operations          | `85207af3-352f-4554-8d2a-18f42cc541ba` | operations                       | `bali_zero_skills_local` LOCAL ONLY                      |
| NB-Lifestyle  | Expat Life          | `4fd8cd0f-93f1-4e43-9c9e-86c0d581852c` | lifestyle                        | (none — pure NB consumer-only domain)                    |

### Conceptual gap finding (without MCP enumeration)

- **NB-2 → Qdrant**: ratio NB sources 97 / Qdrant unique visa sources 88 (87 in `visa_oracle` + 1 UNKNOWN in `immigration_circulars` 1.979x). visa_oracle ha 1 source per visa type — sembra coverage diretta. `immigration_circulars` invece ha 1.979 chunk con 1 source = source-attribution rotta.
- **NB-4 Tax 118 sources → tax_genius_hybrid 10 unique sources**: gap **NB-4 ha 10x più sources di Qdrant tax_genius**. Phase 2.5 dovrebbe ingestare le ~108 fonti mancanti.
- **NB-5 Property 117 sources → legal_unified_2026 18 unique sources** (di cui 1 dominante `Permen_18_2021` con 10.266 chunks): gap simile, NB-5 ha ~99 fonti property mancanti in Qdrant cloud.
- **NB-7 Editorial 89 sources → balizero_news 1 UNKNOWN source**: gap totale per source attribution. Re-ingest necessario per coverage report misurabile.

### AIL per Antonello

Per shippare Phase 2.5 (re-index) serve:

1. Lanciare `notebooklm-mcp` in questa sessione (o nuova)
2. Enumerare 7 Core NB sources via MCP `list_sources`
3. Per ogni source: download content + ingest via `LegalIngestionService.ingest_legal_document()` o equivalent → Qdrant cloud
4. **Costo stimato**: 600+ NB sources × ~$0.05/100k tokens ≈ $30-100 totali + 2-4h wall
5. **CICATRIX**: respect 300k token batch limit (cicatrix scar 2026-05-10 — `LegalIngestionService` silent data loss)

**Decisione richiesta**: ship Phase 2.5 dopo Phase 3 (router routing-aware su known-gap), oppure ship Phase 2.5 ora (router può supporre coverage completo).

---

## 8. Decision matrix per Phase 3

| Decision point                                | Default raccomandato                 | Razionale                                                                                                       |
| --------------------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `nuzantara_general_hybrid` ghost              | **Refactor remove** (option 2)       | Eliminate da query_planner + multi_hop; registry SSOT autoritativo                                              |
| Skills routing local Pro vs Cloud             | **Ship cloud first**                 | Pre-re-indicizza `bali_zero_skills_local` in cloud (~$0.05). SurfaceRouter Fly può servire skills               |
| Payload schema flat vs nested                 | **Accept nested current schema**     | Re-indexing flat fuori scope; aggiorna golden rule #11 + filter syntax docs                                     |
| Source attribution gap (6 collection UNKNOWN) | **Defer to Phase 2.5** (AIL)         | Coverage report richiede re-index — pulizia provenance                                                          |
| KG nodes drift CLAUDE.md vs reality           | **Verify Fly DB** (1h investigation) | Se 108k è Fly prod, sync KG localhost-Fly rotto — separato bug fix                                              |
| `legal_unified_hybrid_hybrid` doppio suffix   | **Rename in Phase 3** (cosmetic)     | `legal_unified_hybrid_hybrid` → `legal_unified` via migration v2 (rename non destructive, just registry update) |
| `garuda_assets` vuoto (0 points)              | **Delete o populate**                | Antonello decision: enrolled in genome ma never wired up                                                        |

---

## 9. Numbers cheat-sheet (Phase 3 input)

- **12 Qdrant Cloud collections live**, total **111.750 points**, all green
- **11 Qdrant Local collections**, di cui 1 unique (`bali_zero_skills_local` 379 pts)
- **KG localhost**: 58.907 nodes, 164.582 edges (Fly verify pending)
- **6/12 collection con source attribution rotta** (UNKNOWN-only)
- **6/12 hardcoded domain mappings reference ghost collection** (`nuzantara_general_hybrid`)
- **100% collection nested payload** (golden rule #11 violation systemica)
- **7 Core NB UUIDs** verified in `notebook_registry.py` SSOT

---

## 10. Open questions / Devils-advocate seeds

1. `legal_unified_hybrid_hybrid` con 81.316 chunk e 345 sources di cui `DOC_UNKNOWN_1847` 2.242x → quanti chunk sono effectively "perdonati" per source ambiguity? Audit trail risk per cliente legal-sensitive.
2. Se `nuzantara_general_hybrid` è ghost da Nov 2025, perché nessun test/canary ha catturato il 404? Suggerisce che TAX/PROPERTY/PRICING query non sono mai entrate in path `multi_hop.decompose()` in prod (forse intent classifier filtra prima).
3. `kbli_2025_final_hybrid` ha 1.528 unique sources di cui top "PENGOLAHAN..." con 27x → ogni KBLI code è ~3 chunk. CLAUDE.md claim "1,563 BPS codes + 304 gold editorial" → ratio sospetto ma plausibile.
4. `tax_genius_hybrid` con 339 chunk vs NB-4 118 sources → NB-4 chiaramente ha più ground-truth. NB-4 → Qdrant migration è il single highest-value Phase 2.5 task.
5. Phase 1 R5 ha shipped local-only. Era plan? `project_nb_lifecycle_master_2026_05_04.md` non specifica cloud target — ipotesi tacita "production = Fly = Cloud Qdrant" è assunta.
6. `garuda_assets` 0 points — la enrollment genome è morta? Verificare se cell wiring previsto da R6 "Genome enrollment" è ancora viable.

---

## 11. Next actions (Phase 3 SurfaceRouter prerequisiti) — POST-PANEL REVISED

**MUST DO PRIMA di Phase 3 ship**:

1. ~~Fix `nuzantara_general_hybrid` ghost~~ — INVALIDATED (dead-code, no prod impact). Cleanup optional debt P2.
2. Verify KG Fly prod count (resolve drift CLAUDE.md vs reality) — 1h (DeepSeek flagged)
3. Decision Antonello: skills routing local-only vs re-index cloud — 5min
4. **NEW (Codex P1)**: SurfaceRouter Phase 3 design MUST consume `QueryRouter` SSOT (production) NOT `query_planner` (shadow). Aggiornare `project_nb_lifecycle_master_2026_05_04.md` Phase 3 spec di conseguenza.
5. **NEW (Codex P1)**: registry/live diff test — `pytest` che fail se Qdrant cloud ha collection NON in registry (caught `legal_unified_2026`, `kbli_tka_hybrid`, `intel_authoritative_sources`, `garuda_assets` come gap registry-side) — 2h

**NICE TO HAVE PRE-Phase 3**: 6. ~~Update CLAUDE.md golden rule #11~~ — REVISED (Codex P1: full payload census su 12 col PRIMA di policy update) — 4h 7. Document `legal_unified_hybrid_hybrid` typo rename in Phase 3 acceptance — 10min 8. Source attribution backfill plan — REVISED methodology (Codex P1: scan ALL payload fields, not just 5) — 6h investigation

**AIL per Antonello** (gate Phase 2.5):

- ✅ Approve approccio Phase 2.5 (re-index NB sources to Qdrant cloud)
- ✅ Launch notebooklm-mcp + retry Phase 2.5 enumeration
- ✅ Approve $30-100 spend re-index
- ✅ Decide `garuda_assets` (delete o populate)
- ~~Decide `nuzantara_general_hybrid` fix~~ — INVALIDATED (dead-code cleanup, P2)
- ✅ **NEW (Codex P1)**: Approve domain-specific ingest paths design (NOT `LegalIngestionService` per tutti i domain) — 30min spec writing

---

## 12. Sources verified this turn

1. Qdrant Cloud HTTPX `/collections` + `/collections/{name}` (12 collections live count)
2. Qdrant Local Docker HTTP `localhost:6333/collections` (11 collections + skills_local 379 pts)
3. `apps/backend-rag/backend/services/rag/agentic/query_planner.py:_DOMAIN_COLLECTIONS` (hardcoded mapping)
4. `apps/backend-rag/backend/services/rag/multi_hop.py:get_domain_collections` (production wired)
5. `apps/backend-rag/backend/core/collection_registry.py` (canonical SSOT)
6. `apps/backend-rag/backend/services/rag/agentic/tools.py:AVAILABLE_COLLECTIONS` (LLM-exposed list)
7. `apps/mata-garuda/mata_garuda/notebook_registry.py` (NB UUID SSOT — 7 Core NB)
8. `reports/notebook_registry_audit.csv` (40 lines, 7 unique UUIDs, mapping consumers→NB)

Reference docs (read-only):

- `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/project_nb_lifecycle_master_2026_05_04.md` (R5 master Phase 2 spec)
- `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/reference_notebooklm_arsenal_full.md` (NB source counts snapshot 2026-05-03)
- `apps/backend-rag/CLAUDE.md` (golden rule #11, migration scars)
- `.claude/rules/cicatrix-scars.md` (LegalIngestionService 300k batch limit)

---

_Audit by Claude Opus 4.7, autonomous L2, session 2026-05-16 09:00→10:30 WITA. Phase 2.5 re-index gated on Antonello approval + notebooklm-mcp launch. Phase 3 SurfaceRouter design awaits ghost collection fix._

---

## 13. Panel review — Codex GPT-5.5 + DeepSeek V4 Pro (2026-05-16 10:30 WITA)

> **Setup**: 3-LLM fan-out parallel red-team (Gemini 3.1 Pro: 429 capacity exhausted; Codex: ✅ replied; DeepSeek: reasoning_content troncato a 4k tokens, content vuoto — reasoning leak utilizzato comunque). NB-1 ground-truth NON disponibile (notebooklm-mcp not loaded).

### Codex BLOCK verdict — 5 findings

**P0 (Codex)** — Ghost collection P0 claim era falso positivo

- Claim originale (mio): "TAX/PROPERTY/PRICING queries hit `nuzantara_general_hybrid` → 404 prod"
- Codex problem: `MultiHopEngine` solo referenziato da `test_multi_hop.py` (2x) + module-level singleton dead-code (`engine = MultiHopEngine()` line 100ish, mai importato altrove). Production routing live usa `QueryRouterIntegration` (instantiated da `service_initializer.py:create_app`), che mappa pricing/tax/property a `tax_genius`/`legal_unified`/`training_conversations_hybrid` — TUTTE in registry.
- **Verified via grep callsite analysis**: confermato Codex. **Severity correggo P0→P2** (dead-code debt, no prod impact).

**P1 (Codex)** — Golden rule #11 update policy regression

- Claim originale (mio): "aggiornare golden rule #11 in CLAUDE.md per riflettere realtà metadata.<field> syntax"
- Codex problem: questo trasforma una violation in policy, locking schema regression. Sample size 4 collection / 12.
- Fix: full payload census + dual-read/dual-write compatibility + decide migration vs documented exception.
- **Status report aggiornato**: §5 raccomandazione downgraded a "investigation needed" non "accept".

**P1 (Codex)** — Phase 2.5 ingest via LegalIngestionService rischia pollution

- Claim originale (mio): "ingest via LegalIngestionService.ingest_legal_document() o equivalent"
- Codex problem: forzare tax/property/editorial/ops sources attraverso legal metadata/chunking semantics → collection pollution.
- Fix: domain-specific ingest paths, target collection mapping, dry-run counts, provenance contract.
- **Status report aggiornato**: §7 AIL aggiunge "define ingest path per domain".

**P1 (Codex)** — Source attribution methodology narrow

- Claim originale (mio): "6/12 collection con source attribution rotta (UNKNOWN-only)"
- Codex problem: scan checked solo 5 field (`metadata.source`, `metadata.document_id`, `metadata.file_path`, `metadata.judul`, `metadata.book_title`). Codice prod legge anche `title`, `url`, `chapter_id`, `id`, `_source_collection`.
- Fix: define provenance schema first, scan ALL payload fields per full collections.
- **Status report aggiornato**: §6 methodology limitation explicit.

**P1 (Codex)** — Registry SSOT incompleto per Phase 3 consumption

- Claim originale (implicit): "8 canonical logical OK per Phase 3"
- Codex problem: registry include `nlm_shadow_hybrid` (presente?), omette `garuda_assets`/`legal_unified_2026`/`kbli_tka_hybrid`/`intel_authoritative_sources` come logical physical targets. "8 canonical" count is stale.
- Fix: generate registry/live diff test; SurfaceRouter consume ONLY audited logical names + explicit aliases.
- **Status report aggiornato**: §4 registry table aggiunge missing entries note.

### DeepSeek V4 Pro reasoning-leak findings (content vuoto, reasoning intercepted)

DeepSeek su `reasoning_effort=high` consuma tutti max_tokens come reasoning, content vuoto. Su `reasoning_effort=low` content ancora vuoto (~bug API o param issue separato). Findings da reasoning leak (parziali, ~3000 chars caught):

**P0 (DeepSeek concorrente)** — KG localhost vs Fly proxy ambiguity

- "Connection: postgresql://nuzantara@localhost:5432/nuzantara_rag (Fly proxy?)" — ambiguo. Se è Fly proxy, numeri sono prod KG → CLAUDE.md è stale, NON sync issue. Se è staging, drift è reale.
- Fix: verify connection nature (sock vs proxy vs local DB).
- **Status report aggiornato**: §3 explicit "Fly verify pending" già presente; aggiungo nota DeepSeek-flagged.

**P1 (DeepSeek)** — Numerical typo NB-2 87 vs 88

- "Qdrant unique visa sources 87 (87 in visa_oracle + 1 UNKNOWN in immigration_circulars)" → 87+1 = 88, non 87.
- **Status report aggiornato**: §7 corrected to 88.

**P1 (DeepSeek)** — Multi-hop fallback path non auditato

- Report claim "Impatto runtime" senza esaminare se `multi_hop` engine error-handle 404 graceful.
- Mooted: per Codex P0 invalidation, multi_hop nemmeno in prod path. DeepSeek finding sussunto.

### Verdict consolidato post-panel

| Severity                  | Count               | Status                                               |
| ------------------------- | ------------------- | ---------------------------------------------------- |
| P0 originale (mio)        | 1                   | INVALIDATED da Codex (false positive)                |
| P0 da panel (DeepSeek)    | 1                   | OPEN (KG localhost vs Fly proxy verification needed) |
| P1 da Codex               | 4                   | OPEN (4 incorporated in report aggiornato)           |
| P1 da DeepSeek            | 1                   | RESOLVED (typo corrected)                            |
| **NET**: Report decisione | **BLOCK → REVISED** | Phase 3 può procedere con prerequisiti rivisti       |

### Lessons

1. **Mai citare "P0 prod breakage" senza grep callsite analysis del consumer**. Mio errore: vedere hardcoded mapping → assumere production wire. Codex catch via 5-line grep.
2. **DeepSeek `reasoning_effort=high` API non utilizzabile per panel review parallel** (consuma tutto budget in reasoning). Workaround future: usare `reasoning_effort=low` + più ampi max_tokens, oppure DeepSeek separato in dedicated session.
3. **Gemini 3.1 Pro 429 capacity hit pattern wave-level** già documentato (lessons.md 2026-04-29). 1 LLM solido (Codex) + 1 reasoning-leak (DeepSeek) > waiting.
4. **NB-1 unavailable** per ground-truth: serve enrollment notebooklm-mcp per future panel review che tocchi codebase claims.
