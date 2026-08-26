# NAGA baseline inventory (read-only, measured 2026-08-26)

Measured on `origin/main` from the read-only main checkout, via `find`/`grep`/`Read` — no writes,
no DB queries. Every path below was verified to exist at the stated content; nothing here is a
paraphrase of the packet spec.

## 1. Persistence — migrations `079` and `081`

`apps/backend-rag/backend/migrations/migration_079_naga_tables.py` (231 lines) creates 5 tables,
applied via the **custom** migration runner (`backend/migrations/`, not `db/migrations_v2/` —
these are two different migration systems in this repo; see §4 below for why that matters):

| Table | Key columns | Notes |
|---|---|---|
| `naga_sessions` | `id`, `parent_session_id→self`, `query`, `tier`, `domain`, `mode`, `channel`, `trusted_mode`, `status`, `duration_ms`, `iterations`, `search_calls`, `sources_found`, `claims_extracted`, `avg_confidence`, `report_markdown`, `report_drive_path`, `action_items JSONB`, `evidence_map_uri TEXT` (pointer, not blob — comment says this is deliberate to avoid TOAST bloat on 2GB Fly PG), `sub_questions JSONB`, `url_history TEXT[]`, `langgraph_thread_id`, `created_at`, `completed_at` | One row per research run. No revision concept — a session is mutated in place until `completed_at`. |
| `naga_sources` | `id`, `session_id→naga_sessions CASCADE`, `url`, `title`, `domain`, `source_type`, `credibility_score`, `freshness_date`, `content_hash`, `content_archived`, `drive_archive_path`, `fetched_at`. `UNIQUE(url, session_id)` | credibility_score is set once at insert and never distinguishes original vs syndicated vs translated vs derived — see gap G4 in `02-p04-adapter-mapping.md`. |
| `naga_claims` | `id`, `session_id→naga_sessions CASCADE`, `claim_text`, `claim_key`, `domain`, `topic_tags TEXT[]`, `jurisdiction`, `verification_level`, `confidence`, `cross_ref_count`, `review_status` (default `'auto_extracted'`), `valid_as_of DATE`, `expires_at DATE`, `resolution_hint`, `created_at` | **Single-point-in-time validity** (`valid_as_of` is a `DATE`, not an interval) — no `valid_from`/`valid_to`, no distinct system-time `recorded_at`. See gap G1. |
| `naga_claim_evidence` | `id SERIAL`, `claim_id→naga_claims CASCADE`, `source_id→naga_sources CASCADE`, `relation`, `extraction_method`, `source_span_hint TEXT` (freeform, not structured), `created_at`. `UNIQUE(claim_id, source_id, relation)` | `source_span_hint` is a hint string, not a locator+offsets+quote-hash structure. See gap G2. |
| `naga_claim_transitions` | `id SERIAL`, `from_claim_id→naga_claims`, `to_claim_id→naga_claims`, `transition_type`, `reason`, `detected_by`, `created_at`. `UNIQUE(from_claim_id, to_claim_id, transition_type)` | A real transition table exists already — many-to-many, append-only by construction (no UPDATE/DELETE in the migration, no rollback path that mutates rows). This is the closest existing analogue to P04's `ObjectSuccessorEdge`; see `03-migration-design-notes.md`. |

`apps/backend-rag/backend/migrations/migration_081_naga_claim_quality.py` (97 lines) adds 5
columns to `naga_claims` via `ALTER TABLE`:

- `quality_score FLOAT`
- `claim_status VARCHAR(20) DEFAULT 'active'` — lifecycle enum, values (from the migration's own
  docstring): `active / expired / duplicate / conflicting / superseded`
- `expired_at TIMESTAMPTZ`
- `duplicate_of_id UUID → naga_claims(id)`
- `similarity_hash VARCHAR(64)` (trigram-based fuzzy dedup)

Both migrations have `rollback()` functions that reverse the forward DDL (`DROP TABLE
CASCADE` / `DROP COLUMN`). `backend/tests/migrations/test_migration_079_naga.py` exists (not
read in full this session — flagged in the README as unread); **no equivalent test file for
migration 081 was found** (`find … -iname "*naga*"` under `backend/tests/migrations/` returns
only the 079 test). This is a gap worth noting to whoever owns migration hygiene, not something
this lane fixes.

## 2. Write path — `services/naga/persist.py` (241 lines, read in full)

`save_session(pool, state) -> str | None` is the **only** writer found for these 5 tables
(confirmed by the consumer grep in §3 — no other file matches `INSERT INTO naga_`). One
transaction per session:

1. `INSERT naga_sessions` — note the inline comment (lines 76-83) documenting a **past bug**:
   `action_items` used to be hardcoded to `"[]"` and silently discarded the orchestrator's real
   value; fixed by reading `state.get("action_items", [])` and using `::text::jsonb` casting to
   route around a codec double-encoding issue. This is exactly the class of "claim/evidence
   mutation bug that leaves silent data loss" the packet's mission cares about — worth carrying
   forward as an example of why the new ledger needs replay/idempotency tests (packet
   deliverable/test: "invalidation idempotency and replay tests").
2. `INSERT naga_sources` per search result, `ON CONFLICT (url, session_id) DO NOTHING` — a real
   dedup gate on ingestion, but keyed on `(url, session_id)` — i.e. dedup is **per-session**, not
   global. The same URL fetched in two different sessions produces two independent
   `naga_sources` rows with two independent `credibility_score`s. There is no evidence-identity
   concept spanning sessions.
3. Quality score computed **at insertion time** (`compute_quality_score`, imported from
   `naga/quality/claim_scorer.py` — not read in full this session) and written once into
   `naga_claims.quality_score` (via a later `INSERT`, not by migration 081's own code — the
   column exists from 081, the value is populated by `persist.py`).
4. `expires_at` is derived with a **hardcoded** domain split: 30 days for
   `domain in ("visa", "immigration")`, 90 days otherwise (lines 154-156) — this exact same rule
   is duplicated as a `CASE` expression inside migration 081's backfill UPDATE (lines 62-66 of
   that file). Two independent copies of one business rule, one in Python and one in a
   backfill SQL statement that only ran once at migration time. If the Python rule changes, the
   SQL copy does not retroactively change — not a bug today (081 already ran), but a pattern
   worth avoiding in the new ledger (single source of truth for expiry policy, not embedded
   twice).
5. `INSERT naga_claims` hardcodes `review_status = "auto_extracted"` (line 176, with the comment
   "Human review gate") and `claim_status = "active"` (line 180) for every claim, unconditionally
   — there is no code path in `persist.py` that ever writes any other `review_status` or
   `claim_status` value at creation time. Whatever moves a claim out of `auto_extracted` /
   `active` happens elsewhere (not in this file) or does not happen at all yet — I did not find
   it in the consumer grep (`quality/dedup.py` and `quality/expiry.py` are candidates by name but
   were not read in full this session).
6. `INSERT naga_claim_evidence` links claim→source via a fragile positional convention: source
   refs from the extractor look like `"s0"`, `"s1"` (string index into `search_results`), parsed
   with `int(src_ref.replace("s", ""))` and a bare `except (ValueError, IndexError): pass` — a
   malformed or out-of-range ref is **silently dropped**, no log, no counter. This is a concrete,
   already-live instance of the packet's Non-goal "Do not infer that an absent record proves a
   negative fact" being violated by omission: a dropped evidence link here would look identical
   to "no evidence found" to any downstream reader, and nothing records that the drop happened.

`_collect_credibility_scores` (lines 220-241) reuses `relevance_score` (a search-ranking signal)
as a proxy for source credibility — the function's own docstring admits this ("since the actual
naga_sources.credibility_score is the same value set during insert"). Confidence quality here is
therefore **circular with search ranking**, not an independent evidentiary signal — relevant to
packet Non-goal "Do not use confidence as a substitute for evidence."

## 3. Full file tree (services + core + scripts + router + MCP + tests)

```
apps/backend-rag/backend/services/naga/
  __init__.py
  deps.py
  gateway.py
  orchestrator.py
  persist.py                      ← read in full (§2 above)
  actions/action_engine.py
  config/naga_config.py           ← 107 lines
  config/source_weights.json
  quality/claim_scorer.py         ← imported by persist.py, not read in full
  quality/convergence.py
  quality/crag_light.py
  quality/dedup.py
  quality/expiry.py
  quality/source_scorer.py
  readers/gemini_reader.py
  search_agents/base.py
  search_agents/brave_agent.py
  search_agents/domain_agent.py
  search_agents/exa_agent.py
  state/budget_tracker.py
  state/url_history.py
  synthesis/report_writer.py

apps/backend-rag/backend/core/claims/
  __init__.py
  confidence.py
  extractor.py
  models.py                       ← read in full (§4 below): ClaimRecord dataclass, shared with NLM pipeline

apps/backend-rag/backend/app/routers/naga.py   ← 145 lines, read in full (§5 below)

apps/backend-rag/scripts/
  naga_bali_enrich.py
  naga_bulk_enrich.py
  naga_live_test.py
  naga_stats.py
  claims_extractor.py
  batch_claims_extractor.py
  nlm_claims_extractor.py
  claims_db/{immigration,property,company,tax}_claims_db.json

apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py         ← MCP-exposed NAGA tool
apps/nuzantara-mcp/nuzantara_mcp/server_lite.py        ← references naga_* tables (grep hit)

Tests:
apps/backend-rag/backend/tests/migrations/test_migration_079_naga.py
apps/backend-rag/backend/tests/services/naga/            ← 16 test files (action_engine, brave_agent,
                                                             claim_quality, config, convergence, crag_light,
                                                             domain_agent, gateway, gemini_reader, integration,
                                                             naga_router, orchestrator, report_writer,
                                                             search_agents, source_scorer, state)
apps/backend-rag/backend/tests/unit/services/naga/test_orchestrator.py
```

## 4. `core/claims/models.py` — the OTHER claim schema (95% content re-quoted below, not paraphrased)

This file's own docstring says: "This file defines the canonical claim schema shared across Naga
and NLM pipelines. Any change here propagates to all consumers." This is a **second, independent**
claim schema living beside `naga_claims` — it is the in-memory `ClaimRecord` dataclass that
`persist.py` reads to build `naga_claims` rows, and it is **also** consumed directly (not via the
DB) by `naga/orchestrator.py`, `naga/synthesis/report_writer.py`, and `naga/actions/action_engine.py`
(per the consumer grep in §6). The packet's own baseline instruction — "Determine … where `claim`,
`evidence`, `confidence`, `expiry`, and `conflict` carry inconsistent meanings" — is answered
concretely by this file existing at all: NAGA already has two claim vocabularies (DB row shape vs.
`ClaimRecord` dataclass shape) before P04's third (canonical `Claim` typed model) is even adapted
in.

`ClaimRecord` fields: `claim_id, claim_text, category (1 of 15 CLAIM_CATEGORIES enum),
confidence_class, confidence_score, source_ids: list[str], extracted, status="active",
geographic_scope="NATIONAL", affected_visa_types: list[str], affected_services: list[str],
flags: dict`.

`CLAIM_CATEGORIES` (15, exact list): `LEGAL_CHANGE, OPERATIONAL_CHANGE, ENFORCEMENT_ACTION,
ENFORCEMENT_PATTERN, POLICY_SIGNAL, PROCEDURAL_STEP, LOCAL_REGULATION, DOCUMENT_REQUIREMENT,
FEE_CHANGE, SOURCE_GAP, SOURCE_REGISTRATION, BASELINE_EXISTING, SYSTEM_STATUS, PROCESSING_TIME,
ELIGIBILITY_RULE`.

`VerificationLevel` thresholds (class constants, not an enum type): `VERIFIED >= 0.75`,
`0.55 <= PROVISIONAL < 0.75`, `LOW < 0.55`.

## 5. Router — `app/routers/naga.py` (145 lines, read in full)

Three endpoints, all Pydantic `BaseModel`-typed:

- `POST /research` → `start_research` — kicks off a session (writes via the orchestrator → `persist.py` path above).
- `GET /session/{session_id}` → `get_session` — reads a `naga_sessions` row.
- `GET /claims/search` → `search_claims` — reads `naga_claims` (filtered), returns `ClaimSearchResponse`.

This is the **entire live HTTP surface** that would need "consumer still using legacy semantics"
treatment per the packet's reviewer-handoff requirement. It is a small, closed surface (3
endpoints, one router file) — good news for a dual-write/shadow-read plan (packet's
Implementation sequence step 7): the fan-out to migrate is narrow.

## 6. Consumer index (every non-test, non-migration file that references the 5 tables or the DB `ClaimRecord`/`core.claims.models`)

Table consumers (`grep -l "naga_claims|naga_sessions|naga_sources|naga_claim_evidence|naga_claim_transitions"`):

- `backend/services/naga/persist.py` (writer, §2)
- `backend/services/naga/quality/claim_scorer.py`
- `backend/services/naga/quality/dedup.py`
- `backend/services/naga/quality/expiry.py`
- `apps/backend-rag/scripts/naga_bali_enrich.py`
- `apps/backend-rag/scripts/naga_bulk_enrich.py`
- `apps/backend-rag/scripts/naga_stats.py`
- `apps/nuzantara-mcp/nuzantara_mcp/server_lite.py`
- `apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py`

`core.claims.models` / `ClaimRecord` consumers (`grep -l "core.claims.models\|core\.claims import"`):

- `backend/core/claims/extractor.py`, `confidence.py`, `__init__.py` (definition site)
- `backend/services/naga/orchestrator.py`
- `backend/services/naga/persist.py`
- `backend/services/naga/synthesis/report_writer.py`
- `backend/services/naga/actions/action_engine.py`

None of these 14 files were modified, and none will be until a build lane picks up
`06-future-file-list.md`. This list **is** the downstream-dependency/consumer index the packet's
deliverable #6 and reviewer-handoff both ask for, at the granularity a read-only preparation lane
can produce (file-level, not call-graph-level — I did not trace which specific fields each
consumer reads).

## 7. What I explicitly did NOT verify in this section

- Whether `naga_claim_transitions.transition_type` values in practice line up with any fixed
  vocabulary — the migration declares the column `VARCHAR(30)` with no `CHECK` constraint and no
  application-level enum was found in the files read. Whoever builds P06 should grep
  `naga/quality/*.py` for the actual write sites before assuming a vocabulary.
- Whether any cron/scheduler currently invokes `naga_bulk_enrich.py` / `naga_bali_enrich.py` in
  production — this bundle only confirms the scripts exist and reference the tables, not that
  they run, or on what cadence.
- Live row counts for any `naga_*` table. `contract-pass-001.md §7` gives a verified live count
  for `research_os_objects` (0/89 databases) because that document's session queried it; this
  bundle makes no live-count claim for `naga_*` because this lane did not query a database.
