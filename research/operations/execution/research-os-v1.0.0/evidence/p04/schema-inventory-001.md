---
adversarial_review: gemini-3.1-pro
---

# P04 Deliverable 0 — Schema & Field-Collision Inventory

**What this is**: the baseline inventory the Conductor red-teams before a P04 (Research OS v1.0.0, canonical
contracts) contract is cut. It is not the contract. It is what exists on disk today, across the five
named producer systems plus the shared workflow/outbox/receipt plumbing, gathered so the contract design
starts from measured fact instead of the dispatch's stated assumptions.

- **Builder**: H1 (this document only synthesizes six independent sweeps — see Method).
- **Date**: 2026-08-23.
- **Measured at**: worktree `docs-ros-v1-p04-inventory` HEAD `03998cf90` (`feat(hooks): repo canon for
  model_routing_gate + measured arsenal routing floor (#4579)`). `origin/main` has since advanced one
  commit to `148f0bfca` via a docs-only ledger commit; that commit does not touch any file cited below.
- **Method**: six independent read-only sweeps (one agent per producer: Intel Lake, NAGA, WR2, WR3,
  publishing/regulatory, and a fourth cross-cutting sweep on workflow-runs/outboxes/outcome-telemetry
  split into 4 parallel lanes internally), each opening every cited file directly this session. This
  document adds no new grep — it is synthesis, and every claim below traces to one of those six raw
  files (paths in the dispatch). Where two sources disagreed, both readings are kept and flagged, not
  resolved by picking one. Where a source flagged a claim as unverified/UNCONFIRMED/not-opened-this-pass,
  that flag is carried forward here unchanged — never laundered into certainty. **Caveat added
  post-refutation (2026-08-23)**: a channel-name/table-name grep proves where the NAME appears, not
  where the write happens. The original `lkpm_ingest_completed` "no writer" finding in §2.6 was produced
  by grepping the channel string and reading only the hits it returned — that finds the constant
  declaration but not the emit call three functions away, which references the constant by name, not by
  the literal string. A sweep built this way will systematically miss any writer reached through a
  function rather than an inline literal; see the corrected finding in §2.6 for the concrete case.
- **All example rows in this document are SYNTHETIC** (invented for shape illustration) unless captioned
  otherwise. No real client data, no real PII, no real private URL appears anywhere below.

---

## §1 — Correction to the dispatch's premises

The dispatch that spawned the six sweeps named five producer paths. The sweeps found three of the five
descriptions incomplete or wrong. Read this section before anything else — it is the most actionable
part of the document, because it changes what P04's contract has to point at.

| Dispatch said | What the sweep found |
|---|---|
| Intel Lake lives at `apps/bali-intel-scraper/…` | **Wrong.** The canonical, Postgres-backed Intel Lake that 8+ producers write to lives at `apps/backend-rag/backend/{db/migrations_v2,services/intel,app/routers}/`, table `intel_items` (`apps/backend-rag/backend/db/migrations_v2/168_intel_lake_schema.sql:21-40`). `apps/bali-intel-scraper/` is a separate, older, entirely file-based pipeline with **zero Postgres tables of its own** — its own Pydantic DB schemas (`Article`/`Source`/etc., `apps/bali-intel-scraper/backend/models/schemas.py`) are dead code, never backed by a migration. There are in fact **three architecturally unrelated "intel" persistence systems** sharing vocabulary but no schema, writer, or reader (detailed in §2.1 and §3): (1) `intel_items` Postgres, (2) an Intel Staging / "News Room" filesystem-JSON system on a Fly volume, (3) the bali-intel-scraper file-based pipeline. P04 must pick one as in-scope and say so explicitly, or namespace every field by system.
| NAGA lives at `migration_079_naga_tables.py` | **Right on the path, wrong on the tier.** The file exists and creates the tables, but `apps/backend-rag/backend/migrations/MIGRATIONS.md:5-6` states this directory is legacy/manual — *"the live automated loader uses `backend/db/migrations_v2/*.sql`"*. Whether NAGA's schema exists in any given Postgres instance depends on someone having run `migration_079_naga_tables.py`/`migration_081_naga_claim_quality.py` by hand. The one *active-tier* migration touching NAGA (`243_jsonb_string_scalar_organism_wide_backfill.sql:284-299`) defensively gates on `to_regclass('public.naga_sessions') IS NOT NULL` — i.e. the active pipeline itself treats NAGA's existence as unknown/optional.
| WR2 queue lives at `apps/war-room/…` | **Wrong location, and there are two non-identical pipelines both called "WR2."** `apps/war-room/**` holds only legacy WR3-style episode artifacts, `.venv`, and logs. The live, cron-driven WR2 carousel code is `scripts/wr2_*.py` (Pipeline B), state machine on `war_room_drafts` (Postgres, migration 112 + 8 later ALTERs). A second, DB-schema-only architecture — `wr2_carousel_runs`/`wr2_orchestrator_metrics`/`wr2_publish_attempts`/`wr2_carousel_events_outbox` (migrations 197/198/199/203), matching the `.claude/agents/wr2-*.md` agent-orchestration contract — is **not the pipeline that drafts/renders carousels**; its own code comment (`scripts/wr2_orchestrator_metrics.py:12-25`) calls `wr2_carousel_runs` *"an invisible fossil for six weeks"* (46 rows, all `session_id LIKE 'manual-%'` test-harness rows, as of a 2026-07-14 DB check cited in that comment). `war_room_drafts.id` and `wr2_carousel_runs.carousel_id` are two different UUIDs for the same carousel, bridged only by string-equality on `topic` at publish time. P04 must pick one identity — `war_room_drafts.id` is the one the render pipeline actually keys on end-to-end.
| WR3 lives at `apps/war-room/output/episode/` | **Right on the path.** Confirmed: 3 subdirs exist, 1 populated (`content-creator-3-roads-2026-05-29/`), 2 empty. But **no `episode_manifest.json` exists anywhere on disk in this repo** (repo-wide find, zero hits) — the one populated episode has no manifest file at all, and the 18-mandatory-field validator that would produce/check one (`scripts/wr3_episode_manifest.py`) is dead code, called only from tests/smoke. In production, an LLM agent (`wr3-post-assembler`, sonnet) writes the manifest as free-form JSON on a bare text prompt — the schema exists in Python but has never gated a real episode.
| Publishing lives at `research/regulatory/*-delta.json` | **Right on the path, no schema exists anywhere.** No JSON Schema, no Pydantic model, no validator for these files in the whole repo. 58 files (`2026-05-16` through `2026-08-23`) were diffed field-by-field; the stable core is only 6 top-level fields, and 4 different field names (`nb_query_notes`/`nb_notes`/`nb_results`/`nb_query_results`) have been used for the same underlying concept without ever being consolidated (see §2.5).

---

## §2 — Per-producer inventory

### §2.1 Intel Lake

**Correction carried from §1**: three disjoint systems share the name. Only System 1 is Postgres; the
other two are file-based and are named here only to establish the collision surface for §3. Detail on
Systems 2/3 lives in §3, not repeated here.

#### `intel_items` (System 1 — canonical, Postgres, Fly)

Defined `apps/backend-rag/backend/db/migrations_v2/168_intel_lake_schema.sql:21-40`, altered by
`187_probe_sandbox_isolation.sql:30-31` (adds `is_probe_sandbox`).

| field | type | null? | default | constraint |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | `gen_random_uuid()` | PK |
| `canonical_url` | TEXT | NOT NULL | — | UNIQUE |
| `content_hash` | TEXT | NOT NULL | — | caller-supplied, opaque to the service; **not verified to be sha256** |
| `title` | TEXT | NOT NULL | — | immutable post-first-write by design |
| `summary` | TEXT | nullable | — | immutable post-first-write by design |
| `source_domain` | TEXT | NOT NULL | — | always lowercased by writer (`intel_lake_service.py:187`) |
| `language` | TEXT | nullable | — | |
| `jurisdiction` | TEXT | nullable | — | |
| `topic_tags` | TEXT[] | NOT NULL | `'{}'` | |
| `routing_status` | TEXT | NOT NULL | `'unrouted'` | CHECK IN (`unrouted`,`blog`,`wr2`,`nb-intel`,`archive`,`skip`,`needs_review`) |
| `routing_targets` | JSONB | NOT NULL | `'{}'` | convention shape `{nb_uuids:[], blog_slug, wr2_draft_id, telegram_chat}`, not enforced |
| `confidence_score` | REAL | nullable | — | CHECK 0≤x≤1 |
| `first_seen_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | |
| `last_seen_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | |
| `published_at` | TIMESTAMPTZ | nullable | — | **the source's own publish date**, not ours — see §3 |
| `expires_at` | TIMESTAMPTZ | nullable | — | **dead on this column/table** — zero writers, zero readers of `intel_items.expires_at` specifically (the field name is alive elsewhere, `dossier_models.py:90`, unrelated domain) |
| `raw_payload` | JSONB | NOT NULL | `'{}'` | |
| `is_probe_sandbox` | BOOLEAN | NOT NULL | `false` | CHECK: true ⟺ `canonical_url LIKE 'https://probe-sandbox.example.test/%'` |

**Reader status column recommendation (see §5)**: of these 18 fields, `expires_at` is `dead`; every other
field has at least one confirmed live reader (router or `magazine_prepare.py`, below).

**State machine (`routing_status`)**: `unrouted` (default) → one of `blog|wr2|nb-intel|archive|skip|needs_review`,
transitioned by `intel_lake_router.py:341-353`, guarded `WHERE routing_status='unrouted'` (idempotent).

**Trigger**: `trg_notify_intel_lake_event` AFTER INSERT ONLY (`168:130-134`) → `events_outbox` row
(channel `intel_lake_event`) + `pg_notify`.

**Writer (only one)**: `IntelLakeService.record_observation()` — `intel_lake_service.py:173-193`.
`INSERT ... ON CONFLICT (canonical_url) DO UPDATE SET last_seen_at=NOW()`. Title/summary/content_hash are
immutable post-first-write **by design** (docstring, not a bug); content drift is logged but never
mutates the row.

**Readers**: `intel_lake_router.py` (Tier-1 rules router, SELECT+UPDATE); `intel_observability.py:136-156`
(dashboard aggregates, behind `get_current_user`); `scripts/intel-lake-nb-pusher-a2/*.py:284-322` (join to
`intel_item_nb_pushes`); `apps/zantara-media/zantara_media/cli/magazine_prepare.py:22-43` (cross-app, raw
SQL SELECT, own asyncpg connection — not via the service layer).

**Cross-app bug found (not P04's to fix, flagged for awareness)**: `apps/zantara-media/.../source_projections.py:215,275,516`
reads `row.get("severity")` on every projection builder including the Intel Lake one, but `intel_items` has
no `severity` column and the SELECT in `magazine_prepare.py` doesn't project one — `_severity()` silently
defaults to `"low"` for every Intel Lake candidate, permanently.

**Producers (verified, method-scoped — treat "8" as a lower bound, not exhaustive)**: `intel_radar`,
`imigrasi_monitor`, `oss_monitor`, `pajak_monitor`, `peraturan_ingestion_trigger`, `t4_monitor`,
`yt_monitor`, `bali_intel_scraper` — via literal `grep "\"producer_name\""` scoped to three directories;
a narrower/different-scoped grep would surface a different subset (confirmed: one such grep missed
`t4_monitor`). Migration-168's own comment and the router-A2 README both say "12+ producers" — stale
relative to this grep. All funnel through a local SQLite outbox (`scripts/intel-lake-outbox-drain/intel_lake_outbox.py`)
drained every 60s to `/api/intel/lake/observations-batch`.

**Companion tables**:

| Table | Key fields | Writer | Reader | Notes |
|---|---|---|---|---|
| `intel_observations` (`168:60-67`) | `id BIGINT IDENTITY PK`, `item_id UUID FK→intel_items ON DELETE CASCADE`, `producer_name`, `observed_at DEFAULT NOW()`, `raw_payload`, `score REAL` | same `record_observation()` call | **none found** beyond ad-hoc SQL | append-only by design ("trust signal = COUNT per item"); `write_only` |
| `intel_lake_audit_log` (`168:78-87`) | `id`, `producer_name`, `client_ip`, `request_path NOT NULL`, `status_code NOT NULL`, `payload_size`, `error_message`, `created_at` | `IntelLakeService.log_audit()`, router, nb-pusher | **none found** | pure audit sink, `write_only` |
| `intel_item_nb_pushes` (`171_intel_item_nb_pushes.sql:9-24`) | `item_id FK`, `nb_uuid UUID`, `content_hash TEXT`, `status DEFAULT 'pending'` CHECK(`pending,pushed,failed_transient,failed_permanent,quarantined`), `attempts`, UNIQUE(item_id,nb_uuid,content_hash) | nb-pusher cron | nb-pusher cron (same process) | `live_reader`; state machine: `pending→pushed` \| `pending/failed_transient→failed_transient` (retry) \| `→failed_permanent` (attempts≥3 AND class∈{unknown,network,timeout}, or class=`quota`) \| `*→quarantined` (class=`not_found`) |

**Example row (synthetic)**:
```json
{
  "id": "3f9a1c2e-0000-4000-8000-000000000010",
  "canonical_url": "https://example-gov.test/id/artikel/contoh",
  "content_hash": "a1b2c3d4e5f6...",
  "title": "Example Regulation Update 2026",
  "source_domain": "example-gov.test",
  "topic_tags": ["tier1", "example_monitor"],
  "routing_status": "nb-intel",
  "routing_targets": {"nb_uuids": ["00000000-0000-0000-0000-000000000000"]},
  "confidence_score": 0.62,
  "first_seen_at": "2026-08-20T03:12:04Z",
  "last_seen_at": "2026-08-22T09:00:11Z",
  "published_at": "2026-08-19T00:00:00+07:00",
  "expires_at": null,
  "raw_payload": {"query": "example query", "tier": "T1"},
  "is_probe_sandbox": false
}
```

---

### §2.2 NAGA (claim ledger)

Path confirmed unmoved: `apps/backend-rag/backend/migrations/migration_079_naga_tables.py` (CREATE);
`migration_081_naga_claim_quality.py` (ALTER, quality/lifecycle columns). Same legacy-migration-tier
caveat as §1 applies to both.

| Table | Definition | Fields (selected, see full list in source sweep for the rest) | Writer | Reader | `reader_status` |
|---|---|---|---|---|---|
| `naga_sessions` | `079:31-62` | `id` UUID PK, `parent_session_id` FK self (session-family only, not claim-family), `query`, `tier`, `domain`, `mode DEFAULT 'oneshot'`, `channel`, `status DEFAULT 'running'`, `action_items JSONB DEFAULT '[]'` (**always `[]`** — `orchestrator.py:419` hardcodes source state), `report_drive_path`/`langgraph_thread_id` (**always written `""`**, `persist.py:75,88`, despite migration docstring calling the latter a key feature) | `persist.py::save_session()` | none (both HTTP read endpoints are hardcoded stubs, below) | `write_only` |
| `naga_sources` | `079:68-83` | `id`, `session_id` FK, `url`, `domain` (URL netloc — unrelated to session `domain`), `credibility_score`, `freshness_date` (**never written**), `content_hash VARCHAR(64)` (**misleading name**: `sha256(url)[:16]`, not a document-content hash), `content_archived` (**never flipped true**), UNIQUE(url,session_id) | `persist.py` | none | `write_only` |
| `naga_claims` | `079:89-109` + `081:24-31` | `id`, `session_id` FK, `claim_text` (truncated 2000 chars), `claim_key` (sha256 hash, **written, never read** — dedup uses live trigram instead), `topic_tags`/`jurisdiction`/`resolution_hint` (**never populated**), `verification_level` (VERIFIED/PROVISIONAL/LOW), `review_status DEFAULT 'auto_extracted'` (**always this literal**, migration docstring calls it "the CRITICAL human review gate", never transitions), `valid_as_of DATE = date.today()` at insert (conflated with system time, see below), `expires_at` (`valid_as_of + 30d` visa/immigration or `+90d`), `quality_score` (081), `claim_status DEFAULT 'active'` (081), `expired_at`/`duplicate_of_id`/`similarity_hash` (081, **all dead** — writers are dead functions) | `persist.py::save_session()` | dead functions only (`batch_rescore`, `find_duplicate`, `batch_dedup`, `cross_reference_claims` — zero call sites outside tests) | `write_only` |
| `naga_claim_evidence` | `079:116-126` | `claim_id` FK, `source_id` FK, `relation` (**only literal ever written: `"supports"`**; no `"refutes"`/`"contradicts"` exists despite column generality), `extraction_method` (only `"naga_v1"`), `source_span_hint` (**never populated** — the one column that could carry a locator/offset/quote), UNIQUE(claim_id,source_id,relation) | `persist.py` | none | `write_only` |
| `naga_claim_transitions` | `079:132-142` | `from_claim_id`/`to_claim_id` FK, `transition_type` (literals in code: `"duplicate"`, `"corroborates"`; **`"supersedes"` never implemented** despite migration docstring naming this table "claim supersession"), `reason`, `detected_by` | **zero production writers** — only writer functions (`dedup.mark_as_duplicate`, `expiry.cross_reference_claims`) live inside dead code paths | none | `write_only`, and in fact **never written at all** |

**Dead read endpoints**: `GET /api/naga/session/{id}` always returns 404 (comment: "V1: no session store
yet", `naga.py:117-125`); `GET /api/naga/claims/search` always returns `[]` (comment: "wired to Postgres
in v1.1", `naga.py:127-145`). Neither issues a SELECT. **Conclusion, verbatim from the source sweep:
nothing in the running system ever reads back a row NAGA wrote.**

**State machine — exact literals only**:
- `naga_sessions.status`: only `'completed'` is ever persisted (`persist.py:67` reads a hardcoded
  `state["status"]="completed"` set at `orchestrator.py:420`, reached only on success; on exception the
  router builds a response object without ever calling `save_session`). `'running'`/`'failed'` never
  reach the DB, despite being documented in a TypedDict comment.
- `naga_claims.review_status`: single literal `'auto_extracted'`, write-once.
- `naga_claims.claim_status`: `'active'` (default) / `'expired'`/`'duplicate'` (both dead-path only).
  Migration 081's docstring additionally claims `conflicting`/`superseded` — **neither literal is ever
  written**, aspirational only.
- `naga_claim_evidence.relation`: `'supports'` only.
- `naga_claim_transitions.transition_type`: `'duplicate'`, `'corroborates'` (both in dead code);
  `'supersedes'` never implemented.

**Bitemporal answer**: conflated, not separated. `valid_as_of = date.today()` at insertion time is the
extraction date, functionally identical to `created_at` — not the real-world effective date of the
underlying fact. `expires_at` is a forward validity-window end, not an observed timestamp.
`ClaimRecord.extracted` (an ISO datetime the extractor produces) is dropped entirely at persist.

**Supersession answer**: where implemented at all (dead code), it is append+edge, not mutate-in-place —
the "duplicate" row is flagged (`claim_status`, `duplicate_of_id`) but the canonical row is never touched,
and the relationship is a separate `naga_claim_transitions` row. No code implements true "supersedes"
semantics (a claim replacing an earlier one because the fact itself changed).

**Evidence answer**: just URL, effectively. `source_span_hint` exists specifically for a locator/quote
but is never populated. `naga_sources.content_hash` looks like a document-revision hash but is
`sha256(url)` — a hash of the address, not the content; cannot detect a page changing between fetches.

**Example row (synthetic)**:
```json
// naga_claims
{
  "id": "9c8d7e6f-0000-4000-8000-000000000002",
  "session_id": "3f1a2b4c-0000-4000-8000-000000000001",
  "claim_text": "Example minimum paid-up capital figure for a PT PMA in a general sector...",
  "claim_key": "a1b2c3d4e5f6...(sha256[:32])",
  "domain": "indonesia", "topic_tags": null, "jurisdiction": null,
  "verification_level": "PROVISIONAL", "confidence": 0.63, "cross_ref_count": 2,
  "review_status": "auto_extracted",
  "valid_as_of": "2026-08-20", "expires_at": "2026-11-18", "resolution_hint": null,
  "quality_score": 0.4116, "claim_status": "active",
  "expired_at": null, "duplicate_of_id": null, "similarity_hash": null
}
```

**Second `ClaimRecord`, unrelated schema, same name**: `backend.services.visa_engine.claim_ledger.ClaimRecord`
(`services/visa_engine/claim_ledger.py:165-202`) is a *different* frozen dataclass — `state`/`backs`/
`product_states`, parsed live from hand-authored Markdown ledgers, **never touches Postgres**. Its
6-state vocabulary (`VERIFIED`, `VERIFIED-WITH-CAVEAT`, `CONFLICTING`, `UNVERIFIED`, `STALE`,
`SUPERSEDED`) is closer to what P04 wants than anything NAGA actually implements, but it is file-based,
not a DB contract, and `SUPERSEDED`/`STALE` are self-documented as "not observed live yet."

---

### §2.3 WR2 (Instagram carousel)

**Two non-identical pipelines** (see §1). Only Pipeline B is live. The agent-orchestration schema
(migrations 197/198/199/203) is characterized here only where it intersects Pipeline B.

#### `war_room_drafts` — THE draft record (live, Pipeline B)

Origin `apps/backend-rag/backend/migrations/migration_112_war_room_tables.py:36-57`, altered by 8 later
`migrations_v2` files (Canva cols now vestigial, NOTIFY trigger, heartbeat sibling, fact-check cols, CAS
lease, retry counter, status CHECK expansion, vision circuit breaker).

| field | type | null | default | reader_status |
|---|---|---|---|---|
| `id` | UUID PK | no | `gen_random_uuid()` | `live_reader` — draft_id, the one true identity |
| `topic` | TEXT | no | — | `live_reader` |
| `status` | TEXT | no | `'briefed'` | `live_reader` (drives the state machine, below) |
| `brief_json` | JSONB | yes | — | `live_reader` (~90 top-level keys observed) |
| `research_json` | JSONB | yes | — | **`dead` on live path** — only the separate admin dashboard surface (`repository.py:174-193`) touches it |
| `council_debate_json` | JSONB | yes | — | `live_reader` — repurposed (not new column) for the narrative arc, NOT literal council transcripts |
| `slides_json` | JSONB | yes | — | `live_reader` |
| `drafts_json` | JSONB | yes | — | **`dead` on live path** — dashboard admin surface only |
| `approved_by`/`approved_at` | TEXT/TIMESTAMPTZ | yes | — | **`dead`** — zero non-migration write sites |
| `canva_design_id`/`canva_edit_url`/`canva_view_url`/`canva_applied_at` | — | yes | — | **`dead`**, superseded render path (§2.3 note below) |
| `fact_check_json`/`fact_check_status`/`fact_check_at` | — | yes | — | `live_reader` |
| `lease_owner`/`lease_acquired_at` | — | yes | — | `live_reader`, CAS lock |
| `html_render_attempts` | INTEGER | no | 0 | `live_reader`, dedicated counter added after a real production incident (an earlier version abused `slides_json`, a JSONB array, for this counter — `jsonb_set` on an array raised `InvalidTextRepresentationError` and silently broke retry-exhaustion for ~8h on 2026-06-13) |
| `html_vision_transient_streak`/`html_vision_parked_until` | INT/TZ | no/yes | 0/NULL | `live_reader`, per-draft circuit breaker |

**State machine — CHECK constraint** (migration 245, full set): `briefed, briefed_facted, researched,
concept, drafts, drafts_checked, drafts_imaged, drafts_imaged_facted, drafts_imaged_checked,
fact_check_failed, image_failed, rendering, rendered, render_failed, rendered_shadow, pending_review,
approved, rejected, published, missed, parked`.

**Actual live transitions** (`scripts/wr2_supervisor.py:93-103`, its own comment notes several CHECK
values are dead — e.g. `briefed_facted` has no producer):

```
(*, "briefed")                                     → kickstart draft-generator
("briefed", "drafts")                              → kickstart image-generator
("drafts", "drafts_imaged")                        → kickstart fact-extractor
("drafts_imaged", "drafts_imaged_facted")           → kickstart fact-checker
("drafts_imaged_facted", "drafts_imaged_checked")   → kickstart html-apply
(*, "rendered")           → None — TERMINAL of the automated chain (Telegram notify only)
(*, "fact_check_failed")  → None — manual review terminal
(*, "rejected")           → None — log only
(*, "parked")             → None — B2 "refuse-to-guess" backstop (empty source content)
```

`'approved'` and `'pending_review'` are **effectively dead on `war_room_drafts.status`**: zero
non-migration write sites; they exist only in the CHECK constraint and in a defensive
`WHERE status IN (...)` clause in `wr2_ig_publish.py`, never actually produced.

`'published'` is set **only** by `scripts/wr2_ig_publish.py:889` after a human-confirmed manual publish
(`UPDATE war_room_drafts SET status='published' WHERE status IN ('rendered','pending_review','approved')`).
`'rendered'` is the real terminal status of the automated chain — a code comment
(`216_wr2_topic_type_log.sql:7-8`) states explicitly *"there is NO software publish-to-IG event"* at that
point.

**Sibling tables from migration 112**: `war_room_posts` (per-platform published artifact, live writer
`wr2_ig_publish.py:876-884`), `war_room_metrics` (engagement time-series, writer not opened this pass —
UNCONFIRMED), `war_room_leads`/`war_room_rejections`/`war_room_missed_runs`/`war_room_costs` (schema
exists, live-write status **UNCONFIRMED**, not asserted dead or live). Two independent NOTIFY channels
exist on overlapping events (`war_room_event` vs `wr2_status_change`) — only the latter is confirmed
consumed.

**`topic_type_log`** (migration 216, live) — one row per **rendered** draft, `draft_id` (not a FK),
`domain`/`register`/`dominant_mode`/`layout_family`/`archetype`, `published_at` (NULL until a real
publish signal — "not yet wired"), `deleted_at` (soft-delete, "not yet wired either"). UNIQUE on
`draft_id`.

**The `wr2_carousel_runs` cluster (migrations 197/198/199/203) — publish-time-only identity**:

| Table | Purpose | reader_status | Notes |
|---|---|---|---|
| `wr2_carousel_runs` (197) | find-or-create by `topic` string | **`write_only`** past INSERT | 12-state CHECK (`drafted…published,failed_cascade,stale_abandoned`) never driven past initial INSERT by any live code |
| `wr2_publish_attempts` (198) | the REAL Meta-publish idempotency ledger | `live_reader` | states `planned→container_created→published→recorded`, terminal `failed`/`blocked_manual_gate`; `idempotency_key = <carousel_id>:<platform>:<content_hash[:16]>` UNIQUE |
| `wr2_carousel_events_outbox` (199) | consumer table for "strategos/learner" | **`dead`** | producer not confirmed by this sweep — UNCONFIRMED whether anything writes rows here |
| `wr2_orchestrator_metrics` (203) | per-step LLM cost/latency | `live_reader`, partial | step-name vocabulary (`brief_interpreter, storyboarder, ...`) is the AGENT-orchestration contract's steps, NOT Pipeline B's real stage names — records a thin, partial slice under someone else's vocabulary |

**Canva renderer — dead/superseded** (migration 127 columns, still schema-present): confirmed superseded
by the HTML render lane (PR #1236 cutover); `apps/backend-rag/backend/services/canva_renderer_v2/` still
exists on disk but is not in the live TRANSITIONS chain.

**On-disk artifacts**:
- `brief.json`/`slides.json` mirrors under `apps/war-room/output/carousel/<slug>/` — measured 23 real
  briefs: `primary_claim_ids` present in **0 of 23**; `key_facts` is `list[str]` in 18, `list[dict]` in 3
  (LLM variance, not a schema version).
- **"manifest" — 3 different, incompatible shapes** inside WR2 alone (direct P04 collision hit, see §3):
  Playwright composer's `{topic, total_slides, families, ...}`; the live Drive-staging "C0 manifest"
  `{draft_id, shadow, slides:[{name,file_id}]}` (an audit/prove-of-life artifact); the external-import
  `build_manifest()` (own distinct shape, not verified identical to either).
- `human-review-queue.json` (`apps/war-room/output/queue/human-review-queue.json`) — the human-review
  queue, a **separate contract from `war_room_drafts.status`**. Documented schema
  (`skills/bali-zero-brand/_review-queue-schema.md`) is explicitly stale per its own header — Canva-era.
  State machine actually driven (`_REPOINTABLE_STATES`): `drafted, reviewed, rejected,
  drafted_needs_human_edit, render_incomplete`; writer sets only `"drafted"` or `"render_incomplete"`.
  Terminal `"published"`/`"published_with_edits"` are set by a *different module*
  (`wr2_queue_writer.py`'s `mark-published` CLI, fed by a human reporting the IG URL back by hand).
  Repoint semantics (a re-render REPOINTS content in place, resets `state` to `"drafted"`) = **mutate-in-place
  with a soft-versioning guard, not true supersession**.

**"approved" answer** — three unrelated things, none of them machine/critic-approved:
`war_room_drafts.status='approved'` (dead); `wr2_carousel_runs.state='approved'` (dead, never
transitioned); `DraftPayload.approval_state` (in-memory dataclass, `"pending"|"approved"|"rejected"`,
set to `"approved"` **only** when a human passes `--confirm`/`confirm=True`, admin-gated) — this last one
is the **only `approved` that actually gates anything**, checked before any Meta API call.

**"published"/auto_publish answer** — publication is hard-gated on a human confirm action at three
independent layers (approval_state check, `wr2_publish_attempts` hard precondition fail-closed if DB
unreachable, `WR2_IG_CONTENT_PUBLISH_VERIFIED` env gate). `WR2_AUTO_PUBLISH_ENABLED` is **pure
vaporware** — the name appears only in a SQL `COMMENT ON COLUMN`, zero code occurrences repo-wide.
`wr2_carousel_runs.publish_mode` (`manual`/`auto`, default `manual`) is written on INSERT and **never
read/branched-on anywhere**.

**Per-slide hero-image identity (sha256)**: recorded only in a best-effort, non-blocking on-disk audit
sidecar (`~/.cache/wr2-imagegen-audit/<draft_id>/slide-NN-<ts>.meta.json`), a write failure is swallowed.
The **enforced** no-silent-reuse gate (Article 5.10) exists only in the interactive agent-orchestration
contract (`.claude/agents/wr2-layout-composer.md`) — **not wired into Pipeline B's live rendering code.**

---

### §2.4 WR3 (video episode)

`apps/war-room/output/episode/` confirmed to exist, 3 subdirs, 1 populated, 2 empty. **No
`episode_manifest.json` file exists anywhere on disk in this repo** — repo-wide find, zero hits, including
in the one populated episode dir.

#### The 18-field manifest shape (`scripts/wr3_episode_manifest.py:20-39,94-117`)

| # | Field | Type | Default | reader_status |
|---|---|---|---|---|
| 1 | `episode_id` | str | — | live-in-theory |
| 2 | `topic` | str | — | live-in-theory |
| 3 | `audience_segment` | str | `"general"` | live-in-theory |
| 4 | `duration_master_ms` | int\|null | `None` | live-in-theory |
| 5 | `created_at` | ISO8601 str | now() | live-in-theory |
| 6 | `completed_at` | ISO8601 str\|null | `None` until finalize | live-in-theory |
| 7 | `claim_ids` | list[str] | `[]`, non-empty enforced | live-in-theory |
| 8 | `asset_hashes` | dict[str,str] | `{}` | live-in-theory |
| 9 | `variants_delivered` | list[str] | `[]` | live-in-theory |
| 10 | `variants_missing` | list[str] | `[]` | live-in-theory |
| 11 | `contract_versions` | dict[str,str] | `{}` | populated only if the LLM agent bothers |
| 12 | `agents_invoked` | list[str] | `[]` | live-in-theory |
| 13 | `total_cost_usd` | float | `0.0` | live-in-theory |
| 14 | `flow_credits_spent` | int | `0` | live-in-theory |
| 15 | `critic_verdict` | str, enum | `"PENDING"` | live-in-theory |
| 16 | `identity_overall_cosine_avg` | float\|null | `None` | live-in-theory |
| 17 | `lufs_measured` | float\|null | `None` | live-in-theory |
| 18 | `wr3_room_version` | str, must equal runtime const | `"0.1.0"` | live-in-theory |

**"live-in-theory" because**: the strict-schema Python validator (`ManifestBuilder`,
`finalize_episode_manifest`, `normalize_assembler_manifest`) is called **only from tests and one smoke
script** — never from `wr3_supervisor.py`/`wr3_dispatch_agent.py`/`wr3_dispatch_v2.py`. In production, the
manifest is written as **free-form JSON by an LLM agent** (`wr3-post-assembler`, sonnet) responding to the
bare text prompt *"Assemble master.mp4 + 4 variants + episode_manifest.json"* — the strict-schema
validator has **never gated a real episode**; the one populated episode has no manifest file at all.
`episode_manifest.schema.json`, cited as the schema_ref in `docs/wr3/contracts/post-assembler.yaml:56`,
**does not exist anywhere in the repo.**

**No `wr3_*` Postgres table exists anywhere.** Two migrations touch WR3 and neither creates a table —
both add a plpgsql function that writes into the *shared* `events_outbox` (`183_wr3_eventbus_channels.sql`,
`186_wr2_published_channel.sql`). All episode state lives in JSON files on disk plus transient PG
NOTIFY/outbox rows.

**Episode state machine** = 6 PG channel names (`wr3_supervisor.py:144-151`), routed via
`docs/wr3/contracts/_router.yaml` (router_version `1.1.0`):

```
wr3_episode_brief_requested   → wr3-design-architect (hot)
wr3_episode_pre_render_ready  → wr3-design-architect, fans out (hot)
wr3_episode_gate_passed       → wr3-clip-renderer (hot)
wr3_episode_assembly_ready    → wr3-post-assembler (hot)
wr3_episode_critic_verdict    → wr3-design-architect, retry|staged (hot)
wr3_episode_staged            → wr3-design-architect, Drive+Telegram (cold, end)
wr2_episode_published          → wr3-design-architect, companion_from_carousel (cold)
```
Outbox-row sub-state is idempotency, not episode-level: `consumed_at IS NULL` → reserve
(`FOR UPDATE SKIP LOCKED`) → dispatch → ack (`consumed_at=NOW()`). **`wr3_episode_*` channels (6) are
orphaned on the consumer side** — see §4.

**Gate/critic verdicts**: `wr3_gatekeeper_check.py` verdicts `{PASS, FAIL, REROLL}` written to
`gate-verdict.json`. Critic verdict states `{PENDING, PASS, PASS-WITH-NOTES, FAIL, DEGRADED}` —
`PASS-WITH-NOTES` was added retroactively (2026-06-14) because the one real manifest that ever existed
used it and the original 4-value enum rejected it — **the enum was widened to match observed reality
after the fact, not derived from spec.**

**`claim_id` bindings**: confirmed present in `script.json`'s VO segments, referencing `claim_id` values
minted in `brief.json`. **Validation is not deterministic code** — the "legal_claim_gate" that verifies
every `claim_id` before `script_freeze` lives only in the `wr3-brief-interpreter` agent's *prompt*, not in
any `scripts/wr3_*.py` file — it is LLM judgment, not enforcement code with a file:line.

**Asset hash wire format**: confirmed bare lowercase hex (`hashlib.sha256().hexdigest()`, no `sha256:`
prefix) on the Python-builder path — but that path is dead code (above). The other write path
(`_master_asset_hashes()`) just reuses whatever the post-assembler LLM agent already wrote, which is
**not schema-constrained at write time**. Net: "current format is bare hex" is true-by-convention, not
by-gate.

**Versioning/supersession**: none. `episode_id` is the sole identity key. `contract_versions` versions
the agents that ran, not the episode. `post-assembler.yaml:79` calls the manifest "the immutable artifact
Antonello reviews pre-publish" — that is doc prose, not an enforced write-once guard.

---

### §2.5 Publishing / regulatory deltas

**No schema file exists** for `research/regulatory/*-delta.json` anywhere in the repo — verified by
reading and diffing 58 files on disk (`2026-05-16` through `2026-08-23`).

**Top-level fields, stable core (58/58)**: `run_at`, `today`, `new_today_count`, `partial`, `deltas`,
`seen_citations`. Everything else drifts:

| Field | Present in | Note |
|---|---|---|
| `yesterday_seen_count` | 50/58 | missing on cold-start runs |
| `unreachable_sources` | 54/58 | **shape drift**: bare strings through `2026-05-31`, structured `{url,reason,note}` objects from `2026-07-28` on — a consumer coded against either shape breaks on the other |
| `nb_query_errors` | 44/58 | |
| `sources_checked_no_delta` | 20/58, only from `2026-07-28` on | post-hoc fix, `.claude/agents/regulatory-watcher.md:87-114` |
| `dedup_baseline_file`/`dedup_baseline_note` | 1/58 | ad-hoc fallback-baseline substitution |
| `dropped_candidates` | 3/58, all ≤`2026-05-26` | abandoned |
| `nb_query_notes` / `nb_notes` / `nb_results` / `nb_query_results` | 9 / 5 / 3 / 2 files | **four different field names for the same concept, never consolidated** |

**`deltas[]` item fields** (25 of 58 files have ≥1 delta): stable core `citation, title_id, title_en,
service_line, source, summary, verbatim_excerpt` (25/25). `severity`/`impact_note` 21/25 (absent before
2026-05-31); `confidence` 22/25; `first_seen_at` 23/25. **`enacted_date`** (the *only* valid-time field
ever recorded) appears in **1 of 25** and never again in the entire corpus. **`effective_date`** (a second,
differently-named valid-time attempt) appears in 2/25 and was also abandoned after 2 uses. 24 of 25
delta-bearing files carry **zero** regulation-effective-date fields at all.

**No content hash, no source-document revision identity, anywhere in the corpus.** `citation` is a
free-text string formatted inconsistently by the producing LLM — the same regulation appears two
different ways *within the same run*. The only hash anywhere in this pipeline is computed downstream at
Intel Lake enqueue time (below), over the citation+title strings, not source bytes.

**Producer** (`.claude/agents/regulatory-watcher.md` spec + `infra/launchagents/wrappers/regulatory-watcher-run.sh`
as the actual writer): multi-LLM cascade (Claude seat → agy/Gemini → Codex → Ollama). Success gate
(`ensure_delta`) succeeds only if a file with the *right keys present* exists AND `partial != true` — this
key-presence-only check is the root mechanism that permits the field drift above; nothing validates
value shape.

**Consumers** (grep-verified, "NO READER FOUND" proven where applicable):
- `apps/zantara-media/.../source_projections.py:634-661` — the **only** consumer that reads and uses
  delta content, transforming it into the magazine's own claims/evidence schema.
- Eventbus `regulatory.delta.detected` (`regulatory-watcher-run.sh:574-583`): two fields
  (`regulation_type`, `urgency`) are synthesized at emit time and **not present in any source delta
  record** — since no delta in the 58-file corpus ever carries an `urgency` key, the emitted value is
  always the literal default `"medium"`. Sole action-taking subscriber
  (`infra/eventbus/meta_dispatcher.py:64-67`) gates Telegram alerts on `min_urgency:"high"` — **this
  alert path can never fire**, wired and deployed but permanently inert.
- Intel Lake outbox enqueue (`regulatory-watcher-run.sh:587-622`) — `content_hash =
  sha256(citation+' '+title)[:32]`, the single hash in the whole pipeline, hashing the LLM's own citation
  string, not source bytes.
- modus green-class queue — record-only mandate, explicitly "do NOT apply or advise."
- **No reader found** for the Intel Lake outbox entries beyond the generic drain path — no
  regulatory-specific consumer distinct from the generic drain.
- `.claude/agents/regulatory-watcher.md:223-225`'s claim *"does NOT trigger downstream agents"* is
  **factually stale** — the eventbus/Intel-Lake/modus wiring above already fires on every delta-bearing
  run.

**Three independent publication systems, non-unified**:

| System | State machine / gate | "published" means |
|---|---|---|
| WR2 Instagram carousel | `wr2_carousel_runs.state` (197) + `wr2_publish_attempts.state` (198) | Meta Graph API call succeeded — never re-verified as still-live afterward |
| bali-intel-scraper quality gate (`quality_gate.py`) | `GateDecision` enum `AUTO_PUBLISH`/`REVIEW`/`ARCHIVE` | **Nothing** — `AUTO_PUBLISH` only sets `art['featured']=True` and continues in-pipeline; it never calls a network-publish API despite the name |
| Bali Zero Magazine (`zantara_media/`) | `stage_publication()` → `/api/machine/publications/editions`, Ed25519-signed audit-anchor chain before the real publish call | `ok:true/status:"created"` = accepted into D1 staging with an atomic head-move — closest to "pushed," still not a post-publish liveness check. **No server handler for this endpoint exists anywhere in this repo** (grep-verified) — presumably external Sites deployment, unverifiable from code alone |

**No surface anywhere separately confirms "and it is now live/reachable" after the write succeeds** — on
every one of the three systems.

**Synthetic example row**:
```json
{
  "citation": "PMK Nomor 99 Tahun 2026",
  "title_id": "Perubahan atas ... [contoh]",
  "title_en": "Example Amendment to PMK ...",
  "service_line": ["tax"],
  "severity": "medium", "confidence": "medium",
  "impact_note": "One sentence, concrete consequence.",
  "summary": "One paragraph.",
  "source": "example-institute.test | https://example-institute.test/example",
  "verbatim_excerpt": "Verbatim Indonesian text, never paraphrased.",
  "first_seen_at": "2026-08-23T07:10:00+08:00"
}
```

---

### §2.6 Shared workflow / outbox / receipt plumbing

This is the mechanism family P04's own `WorkflowRun`/`ActionItem`/`ActionIntent`/`ApprovalReceipt`/
`ExecutionAttempt`/`OperationalReceipt`/`OutcomeEvent` would sit alongside or replace. Four independent
sweep lanes each opened the cited files directly.

#### `events_outbox` — the general-purpose broker

DDL `apps/backend-rag/backend/db/migrations_v2/144_events_outbox.sql:30-37`:
```sql
CREATE TABLE IF NOT EXISTS events_outbox (
    id BIGSERIAL PRIMARY KEY, channel TEXT NOT NULL, payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), consumed_at TIMESTAMPTZ, consumer_id TEXT
);
```

**26 distinct channel values (exact count, corrected 2026-08-23), 5+ independent producer subsystems,
≥4 independent consumer processes.** Of the 26, exactly **16 are registered in `PG_CHANNEL_MAP`**
(`apps/backend-rag/backend/services/events/event_bus.py:47-166` — `practice_changed`, `client_changed`,
`compliance_alert`, `lkpm_ingest_completed`, `war_room_event`, `intel_event`, `cognitive_event`,
`partner_commission_changed`, `federation_alert`, `cell_pulse_observed`, `cell_pulse_sustained_red`,
`measurer_event`, `crm_welcome_completed`, `whatsapp_message_received`, `asset_provenance`,
`intel_lake_event`), verified by parsing the dict with `ast` rather than grep. The remaining 10 write to
`events_outbox` but are **not** in the map — consumed instead by their own bespoke listener, or (in the
`wr3_episode_*` case) by nobody: `wr2_status_change` (`164_wr2_status_change_outbox.sql:50,54,81`),
`wr2_episode_published` (`186_wr2_published_channel.sql:64`), 6 `wr3_episode_*` channels via
`publish_wr3_event` (`183_wr3_eventbus_channels.sql:68-73`), and `whatsapp_media_pending` /
`inbound_webhook_queued` — the two channel constants passed to the shared `outbox.publish()` helper
(`apps/backend-rag/backend/app/routers/whatsapp_chat.py:1020,1063` and
`apps/backend-rag/backend/services/channels/inbound_webhook_repo.py:26,128`). **Correction note**: an
external refuter pass reported "26 distinct channels in `PG_CHANNEL_MAP`" — that count (26) is right for
`events_outbox` as a whole, but the attribution is wrong: `PG_CHANNEL_MAP` itself holds only 16, verified
directly above; the original document's own "≥25" hedge was already directionally correct and is
replaced here with the exact, evidence-cited number. Readers
include the in-app EventBus (LISTEN/NOTIFY + replay-on-reconnect), and at least 3 fully independent
external daemons each running their own LISTEN+replay (`wr2_supervisor.py`, `federation_alerts/daemon.py`,
plus a pure-poll path in `app/routers/bridge.py`).

**One confirmed-broken wiring gap** — cautionary tale for P04:
- `wr3_episode_*` (6 channels) — writer exists, **no subscriber**. The writing migration's own comment
  claims the channels are declared in `PG_CHANNEL_MAP`; grepped directly against the map's full range —
  **zero matches.**

**Corrected 2026-08-23 (refuted by Gemini 3.1 Pro, verified on disk)**: `lkpm_ingest_completed` is
**live and wired, not an orphan** — the original sweep's "no writer exists anywhere" claim was wrong.
The writer is `emit_ingest_event()`, defined `apps/backend-rag/scripts/import_lkpm_q1_2026_receipts.py:764`,
whose docstring (`:770`) states it emits `pg_notify` on
`PG_CHANNEL_INGEST = "lkpm_ingest_completed"` (`:761`) after the import transaction commits; the call
site is `:970` (`emitted = await emit_ingest_event(conn, result, source="tax_drive_manual_q1_2026")`),
suppressible via `--skip-event` (`:1007`). It has two confirmed readers:
`scripts/pg-to-organism-bridge.py:63` (channel allowlist) and
`apps/backend-rag/backend/services/events/handlers/crm_hgt_handlers.py:204`
(`async def on_lkpm_ingest_completed`). See the Method caveat above for why the original grep-based
sweep missed it — the call site at `:970` never contains the literal channel string, only the function
name.

**Related but NOT the same mechanism** (don't conflate): `bridge_outbox` (no `consumed_at`/`consumer_id`
at all, closed 6-value whitelist, cursor-based HTTP pull), `wr2_carousel_events_outbox` (array-membership
ack, **dormant** — zero call sites outside its own module+tests), `wa_outbox` (claim-lease work queue, no
`channel` column — not an event log), `observed_shell_events` (deliberately not outbox-pattern — "no
replay semantics" per its own migration comment), `partner_email_outbox` (fully self-contained legacy
domain outbox).

**Answer to "is `events_outbox` already a general event broker, would P04 duplicate it": yes,
unambiguously.** Recommended P04 posture: **emit new `channel` values on `events_outbox`, do not create a
parallel table** — becoming the 27th tenant (26 confirmed today, above), not a new mechanism — while
treating the 1 orphan-wiring gap above (`wr3_episode_*`) as a cautionary tale about how easily this
pattern silently rots. `lkpm_ingest_completed` is no longer counted here — see the correction above.

#### Job/attempt/queue/DLQ family — no generic pattern, 8 independent hand-rolled tables

| Table | Attempt-count column name | Status vocabulary | Lease pattern |
|---|---|---|---|
| `broker_jobs` (270) | none named "attempts" | `offered→leased→completed_pending_consume→consumed` \| `expired`/`failed` | `FOR UPDATE SKIP LOCKED` + `lease_expires_at` + `fence_token` |
| `failed_messages` (086) | `attempt_count` | `pending→retrying→delivered`/`exhausted` | **none** — plain UPDATE, single-poller assumed |
| `legal_ingest_jobs` (070b) | **none at all** — only `visibility_at` | `pending`(no CHECK)→`qdrant_done`→`drive_done`→`nlm_done`→`complete`/`failed` | `FOR UPDATE SKIP LOCKED` + visibility-timeout, SQS-style |
| `post_publish_queue` (077b/078) | `attempts` | `pending,processing,done,failed,dead` (**`dead` written but never in any CHECK — none exists on this column**) | plain UPDATE, **no lock at all**; failure UPDATE has **no WHERE guard on current status — can overwrite a `done` row** |
| `wr2_carousel_runs`+`wr2_publish_attempts` (197/198) | `retry_count` | see §2.3 | partial unique index on non-terminal state |
| `war_room_drafts` attempt columns | `html_render_attempts` (228) + separate `html_vision_transient_streak` (275) | — | bolted on **twice**, no shared table, two months apart |
| `intake_queue` (212 + 224/225/227/240) | `attempts` | `pending→ocr_done→extracted→validated→done`/`dead`, remapped from a v1 vocabulary that overloaded status as both stage-cursor and claim-marker (a documented past bug) | CTE `FOR UPDATE SKIP LOCKED` + separate `lease_owner`/`lease_expires_at` UPDATE — the only pair with a named `lease_owner` column |
| `visa_evaluate_idempotency` (262) | none (replay cache, not a job) | reservation→completion, `BEFORE UPDATE OR DELETE` trigger makes unexpired rows immutable except that one transition | CAS, first-writer-wins |
| `crm_welcome_runs` (153) | **none at all** | single UPSERT row, no attempt history — retry silently clobbers the prior row | none |

**Explicit finding, verbatim conclusion of the source sweep: no generic attempt-table pattern reused
across domains — every attempt/job table is domain-specific and hand-rolled**, with disjoint status
vocabularies and disjoint (or absent) attempt-counting field names. Even within one migration family
(`war_room_drafts`), a second circuit-breaker was written as three brand-new ad-hoc columns rather than
reusing the pattern from two months earlier. **This is the single strongest finding for P04**:
`WorkflowRun`/`ActionItem`/`ExecutionAttempt` fill a real gap, not a duplicate.

The fullest example of the pattern done *well* is the intake pipeline (7 tables under `212_intake_unified.sql`
and successors: `document_instances`, `intake_queue`, `document_routing_proposal`, `intake_commit_audit`,
plus 3 narrower support tables) — worth reading directly as the closest existing analog to a
multi-table atomic classification bundle (see DEFERRABLE section below).

#### Approval / outcome / alert family — no generic owner, 5 reinventions of "how did we react to X"

| Candidate | Migration | Why ranked here |
|---|---|---|
| `federation_alert_proposals` | 147 | **strongest approval-receipt candidate** — 12-state machine, `approval_token`/`approved_by`/`approved_at`/`rejected_by`/`rejected_at`, CHECK-enforced (`status<>'awaiting_approval' OR approval_token IS NOT NULL`), plus `idempotency_key`/`lease_owner`/`attempt_count` in the same table — already encodes most of what WorkflowRun+ApprovalReceipt+ExecutionAttempt would separately model |
| `crm_guardian_entity_match_candidates` | 202 | second-strongest — `approved_by`/`approved_at`/`confidence` |
| `kg_proposals` | 230 | `status CHECK(pending,approved,rejected,applied,auto_expired)` |
| `incident_ledger` | 195 (organism supervisor) | **strongest generic outcome-event candidate** — actor/actuator-agnostic, `outcome CHECK(dispatched,deferred_cb,deferred_mutex,deferred_blackout,deferred_defer_actuator,rejected_unknown,awaiting_human,shadow_logged,done,failed)`, `correlation_id` |
| `olympus_actions` | 100c | third generic-outcome candidate — `outcome CHECK(success,failure,skipped,proposed)` |
| `crm_guardian_events` | 129 | fourth — before/after JSONB diff + status enum; append-only discipline was DB-enforced via rules, then **dropped** (140) because it broke an `ON DELETE SET NULL` cascade — now application-level only |
| `alert_outcomes` / `renewal_alert_outcomes` | 115+258 / 150 | **explicitly siloed** — same concept ("how did we react to an alert"), disjoint enums, separate tables, one per alert source |

**The org has now built "how did we react to X" 5 separate times** (`incident_ledger`, `olympus_actions`,
`crm_guardian_events`, `alert_outcomes`, `renewal_alert_outcomes`) — the concrete argument for P04's
`OutcomeEvent`.

**`guardian_decisions` — live bug, do not copy this shape.** **Corrected 2026-08-23** (a refuter pass
flagged the original "none of those 4 names are real columns" claim as wrong; verified directly against
both sides rather than trusting either the refuter or the original text). The table is defined by the
legacy-tier migration `apps/backend-rag/backend/migrations/migration_098b_guardian_decisions.py`
(not `migrations_v2` — same manual-apply caveat as NAGA in §1, which is exactly what the writer's own
comment `# table may not exist in local dev` (`alert_feedback.py:204`) is hedging against) and has **12
real columns**: `id`, `run_id`, `timestamp`, `component`, `check_type`, `finding`, `severity`,
`action_taken`, `rationale`, `rollback_plan`, `risk_score`, `metadata`. The writer
(`services/compliance/alert_feedback.py:215,234`, both the pool-mode and connection-mode branches)
inserts `(decision_type, context, decision, metadata)` — of these 4 names, **1 is a real column**
(`metadata`) and **3 are not** (`decision_type`, `context`, `decision`). The original claim was
directionally right (the INSERT does fail) but numerically wrong: it is not a 0-for-4 mismatch, it is
3-for-4. The failure mode is unchanged — Postgres rejects the INSERT's column list at parse time on the
first unresolved identifier, before any NOT NULL constraint (5 of the 12 real columns —
`run_id`/`component`/`check_type`/`finding`/`action_taken` — are `NOT NULL` with no default and are
never supplied either) is ever evaluated — so **every INSERT still raises `UndefinedColumnError`,
silently swallowed**, and writer and reader have still never agreed on this table's schema. Only the
column-mismatch count changes, not the conclusion.

#### Hash-column wire format — three incompatible conventions, zero `sha256:`-prefixed anything

| Convention | Where | Note |
|---|---|---|
| TEXT/CHAR(64) bare lowercase hex | `intake_queue.intake_key`, `document_instances.blob_hash`, `crm_guardian_file_content_cache.content_hash`, `magic_link_tokens.token_hash`, `wr2_publish_attempts.content_hash`, `broker_jobs.package_hash` | matches P04's proposed `^[0-9a-f]{64}$` regex exactly — the majority pattern |
| `BYTEA(32)` raw binary digest | entire `visa_engine` surface: `visa_decision_trace_integrity`, `visa_evaluate_response_hmac`, `visa_evaluate_idempotency` (262) | **the newest, most-hardened tables in the schema chose this, not TEXT.** The app-layer Pydantic validator (`Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]`) is byte-identical to P04's mandate, but at the DB boundary it's converted `bytes.fromhex(...)` into BYTEA. P04 must decide explicitly: TEXT bare-hex, or BYTEA-with-hex-at-the-boundary — visa_engine already chose the latter for its highest-stakes tables |
| `VARCHAR(32)` **MD5** hex | `documents.content_hash` (migration_074) | wrong algorithm entirely, **still actively written** by 2 live 2026-era call sites — a migration hazard independent of P04, would need a backfill if ever unified |
| Ad-hoc string-prefix (not colon-`sha256:`, but prefixed) | `broker_jobs.completion_digest` (`"ok:"+hex` or `"err:{class}"`), `document_routing_proposal.routing_key` (`"rk:"+hex[:48]`, prefixed AND truncated), `documents.intake_idempotency_key` (`"ik:"+hex`) | a naive grep for `sha256:` would miss all three |
| False friend, not a content hash | `visa_checks.hash`/`garuda_voa_checks.hash`, `VARCHAR(20)` | CSPRNG-generated opaque public share-slug, not a digest — don't fold into the hash-column contract |

**No `sha256:`-colon-prefixed format exists anywhere in the repo** (3 independent lanes agree). **Bottom
line for P04**: pick TEXT bare-hex explicitly (majority pattern, matches the visa_engine app-layer
validator) and document that visa_engine's BYTEA columns and `documents.content_hash`'s MD5 are NOT
migrated/unified by this contract, just coexisting legacy.

#### `DEFERRABLE INITIALLY DEFERRED` — zero live uses, one reverted attempt

**Net: zero live uses anywhere in the schema at current HEAD**, confirmed by 3 independent full-repo
greps. Exactly 2 hits, same lineage, and they cancel out:

- `apps/backend-rag/backend/db/migrations_v2/173_wa_mirror_team_sessions.sql:60-62` created
  `CONSTRAINT uq_whatsapp_team_sessions_active UNIQUE (team_member_email, status) DEFERRABLE INITIALLY DEFERRED`.
- `175_wa_mirror_session_active_index.sql:54-55,76-79` **dropped it two migrations later**, replacing it
  with a non-deferrable **partial unique index** (`uq_whatsapp_team_sessions_active_member`) because the
  full-tuple DEFERRABLE UNIQUE over-constrained the actual invariant — it also blocked legitimate multiple
  terminal-state rows, not just the intended "one active row" case. The `DEFERRABLE` clause survives only
  inside 175's own rollback-comment section.

**This is a live, same-schema data point against reflexively reaching for DEFERRABLE.** The
partial-unique-index idiom recurs independently in `compliance_alerts.dedup_key` — it is the schema's
proven answer to "unique among non-terminal/active rows only," which is very likely what P04 actually
needs, distinct from a true cross-row deferred-check-at-commit requirement.

**Design risk flagged for the Conductor**: the frozen contract requires deferred cross-object constraints
for atomic classification bundles. **If P04 genuinely needs true deferred FK/uniqueness across a
multi-row bundle checked at COMMIT time (not just "one active row per key"), there is no existing
precedent in this schema to model against — P04 would be the first live user, and the only prior attempt
here was reverted.**

**Multi-table atomic transaction bundle precedent (plain transaction, not deferred)**:
1. `services/naga/persist.py:35-36` `save_session()` — one `conn.transaction()` wrapping 4 sequential
   INSERTs (`naga_sessions→naga_sources→naga_claims→naga_claim_evidence`).
2. `services/intake/writer.py::execute_commit` — document UPSERT + practice append + a **nested
   savepoint** for client-card enrichment (deliberately isolated so its failure can't abort the outer
   commit) + `intake_commit_audit` row. Its own comment states the invariant: "no orphan document without
   a routed proposal, no routed proposal without its document." **This is the closest existing analog to
   what P04 wants for atomic classification bundles** — worth reading directly if P04's writer needs the
   same shape.

#### PostgreSQL version — conflicting sources, do not pick one silently

- **Project `CLAUDE.md` §11** (doctrine, unverifiable from any file in this repo): postgres-flex 17.7,
  rolling-upgraded from 17.2 on 2026-08-09. No committed `fly.toml` exists for the `nuzantara-postgres`
  app.
- **`research/operations/2026-06-12-m5-postgres-architecture.md`**: empirical `fly image show` returned
  17.2 as of 2026-06-12, and flags CLAUDE.md as having drifted from the live image before.
- **Local/CI test path, directly verified on disk, agreeing: Postgres 15** — `docker-compose.yml:34`,
  `apps/backend-rag/docker-compose.test.yml:3`, `apps/bali-intel-scraper/docker-compose.yml:59` all
  `image: postgres:15-alpine`; four workflows pin
  `public.ecr.aws/docker/library/postgres:15` as their service container —
  `.github/workflows/tests.yml:501,1385`, `fly-deploy.yml:36`, `intel-router-tests.yml:30`,
  `scripts-tests-sweep.yml:97`.

**Corrected 2026-08-23**: the *test* path is verifiably Postgres 15 (above), but Postgres 17 is **not**
absent from CI outright — `.github/workflows/restore-drill.yml:32` pins `image: postgis/postgis:17-3.5`
for its monthly restore-drill job, and the file's own comment at `:27` names it explicitly ("PostGIS
image (not bare postgres:17)"). That is a PostGIS superset of `postgres:17`, chosen (per the same
comment, `:27-31`) because the production dump declares a `public.geometry(Point,4326)` column on
`clients` plus `CREATE EXTENSION postgis` — without it `CREATE TABLE clients` fails and the restore
drill can't prove anything. The restore drill restores an actual production dump rather than
running migrations/tests, so it exercises a real PG17 server, just not the one the four PR-gating
workflows above use to run migrations. **Restated precisely: the test/CI-migration path is PG15,
production (and the one CI job that restores a production dump) is 17.x — a PG16+-only feature can
pass a local Postgres 17.8 apply and the restore-drill's PG17 container, then still die in the *test*
CI path, which pins 15.** That consequence is unchanged from the original finding; only the "nowhere in
CI" framing was wrong.

#### Redis-backed queues — one genuinely at-risk structure

`services/rag/deep_research_dispatcher.py` — `rpush` onto a durable-seeming queue key with **no TTL and
no Postgres backing row**; only the eventual result key gets a 24h TTL. If Redis restarts/evicts/flushes
before a worker pops the queue, a pending job vanishes with zero trace. Recommendation: any new
durable-workflow-queue contract from P04 should either explicitly supersede/backstop this queue, or
explicitly declare it out of scope as an accepted best-effort surface. Everything else matching the
durable-primitive grep (`semantic_cache`, rate-limit `zadd`) turned out ephemeral-and-safe by design.
`wa_broker`/`intake_queue` are explicitly confirmed NOT Redis-backed (fully Postgres).

---

## §3 — The collision matrix

One row per colliding word. Columns are the producers where the word appears; cells give what it MEANS
there, with file:line. Read this table before naming ANY field in the P04 contract — a bare name from
this list will collide with an already-shipped, semantically different field in at least one live
system.

| Word | Intel Lake (System 1, `intel_items`) | Intel Staging "News Room" (System 2, filesystem JSON) | bali-intel-scraper legacy (System 3, file-based) | WR2 | WR3 | Publishing/regulatory | Shared plumbing |
|---|---|---|---|---|---|---|---|
| **`status`** | N/A — column is `routing_status`, 7-value CHECK | free-text, default `"pending"`, convention-only across readers (`intel_staging_service.py:382-386`) | `PendingArticle.status` dataclass, literals `pending/approved/rejected/changes_requested` (`telegram_approval.py:1010`) | `war_room_drafts.status` = 20-value CHECK pipeline-stage enum; `wr2_publish_attempts.state`/`wr2_carousel_runs.state` = **different column name (`state`), same concept, unsynced** with `war_room_drafts.status` | never an episode-lifecycle field — only ad-hoc HTTP response dicts, `{"status":"HALT",...}` | never a field name in the delta record itself | `broker_jobs.state`, `intake_queue.status`, `post_publish_queue.status`, `failed_messages.status` — each with a disjoint vocabulary, `state` vs `status` used inconsistently for the identical concept across sibling tables |
| **`published`/`published_at`** | `published_at` = **source's own** publish date (author's dateline), nullable, parsed from producer string | `published_at` = **our** News Room's own publish action; presence of sibling `published_url` is the real is-live signal | `PendingArticle.published_at` = same "our action" meaning as System 2, but a *third* independent store; `published_articles.json` is a separate 3-field dedup ledger, not the article record | `war_room_drafts.status='published'` = Meta API call succeeded, human-confirmed, never re-verified live; `wr2_carousel_runs.state='published'` = schema-only, never reached; JSON-queue `state='published'` = real but only via manual report-back — **3 unsynced booleans for the same fact** | only the channel name `wr2_episode_published` (WR2→WR3 handoff signal, not a publish confirmation) | 3 unrelated meanings across WR2/scraper/Magazine (see §2.5 table); no surface anywhere means "search-indexed" | — |
| **`auto_publish`** | not present | not present | `GateDecision.AUTO_PUBLISH` (`quality_gate.py:110-113`), composite-score routing decision, **never calls a publish API** despite the name | `WR2_AUTO_PUBLISH_ENABLED` — **pure vaporware**, zero code occurrences beyond a SQL comment; `wr2_carousel_runs.publish_mode` written, never read | not found anywhere in WR3 — notable absence given the repo's blanket never-auto-publish rule | `quality_gate.GateDecision.AUTO_PUBLISH` reused, same no-op meaning as bali-intel-scraper (same code) | — |
| **`approved`** | not present | archive_type literal `"approved"` — a directory move, not a column | `PendingArticle.status=="approved"` | 3 unrelated meanings: `war_room_drafts.status='approved'` (dead), `wr2_carousel_runs.state='approved'` (dead), `DraftPayload.approval_state` (in-memory, the ONLY one that gates anything) | not a data field — only prose ("anti-self-approval contract") | ~9+ independent migrations each define their own `approved`/`approved_by`/`approved_at` (109,132,147,157,163,169,197,198,202,222,230,245,264,266,268), no shared schema/enum | `federation_alert_proposals.approved_by/at`, `crm_guardian_entity_match_candidates.approved_by/at`, `kg_proposals.approved_by/at` — 3+ more, still disjoint |
| **`claim`** | not a field; `routing_targets` JSONB may carry NB push targets but nothing called "claim" | not present | not present | `wr2_claims.Claim` dataclass (2026-07-26 retrofit), present in only 3 of 23 measured briefs; migration 186's `primary_claim_ids` = **0 of 23** | `claim_id` in `brief.json`/`script.json`, same string space as WR2's `primary_claim_ids` (correctly inherited, not a collision) | Magazine `claims[]` array (`claim_id`,`claim_kind`,`legal_effect`,`evidence_ids`,`breaking_gate`) — a 4th, unrelated vocabulary invented for fact-checking | NAGA's `naga_claims` (DB-backed extraction) vs visa_engine's Markdown-ledger `ClaimRecord` (file-based) — **two classes named `ClaimRecord` with disjoint schemas and disjoint storage** |
| **`source`** | `source_domain` (hostname, always lowercased) | `source_url` (full URL); `list_pending_items` remaps it to a response key literally called `"source"` that is actually the URL | `source` (freeform outlet name, dataclass field) distinct from adjacent `source_url` | `war_room_metrics.source` CHECK `{meta_graph, playwright_scrape, utm_crm, partial}` — unrelated to `wr2_claims`'s `source` field on a claim | `source_nb` (which NotebookLM) vs `IOBlock.source`/`source_or_sink` (I/O plumbing) — same word, provenance sense vs plumbing sense | delta `source` = unstructured string mixing provenance+URL, vs Magazine's fully structured `evidence_refs[].source_type`/`canonical_url`/`publisher` one layer downstream | — |
| **`manifest`** | `routing_targets` JSONB documented shape only in a comment, never called "manifest" | not present | not present | **3 incompatible shapes inside WR2 alone**: Playwright composer's render-QA dict, the live Drive-staging "C0 manifest" (audit sidecar), the external-import `build_manifest()` | `episode_manifest.json` — 18-field episode-completion record, **the only one with mandatory-field validation code, and that code is unwired** | Magazine's `AssetIntentManifestV1` (asset provenance/rights) is a 4th, unrelated shape | `apps/zantara-media` "manifest" files (`morning-{date}.json`, revision counters) — a 5th |
| **`id`** | `intel_items.id` = DB-generated UUID | staging item id = string `"{type}_{timestamp}_{sha256[:8]}"`, regex-validated filename stem, not a DB key | `PendingArticle.article_id = md5(title+source_url)[:12]` — a 4th id scheme | `war_room_drafts.id` (draft_id, the real identity) vs `wr2_carousel_runs.carousel_id` — **two different UUIDs for the same carousel**, bridged only by topic-string equality at publish time | `episode_id` — operator-chosen slug, no code parses/validates/increments it | — | every job/queue table mints its own PK convention (UUID, BIGSERIAL, composite) — no shared identity scheme |
| **`hash`**/`content_hash` | caller-supplied, opaque, not verified sha256 | not used for identity | `sha256(title+" "+url)[:32]`, computed independently inline by each of 4+ producers, no shared implementation | `wr2_publish_attempts.content_hash` **diverges between its two call sites** for the "same" key — router hashes ordered image_urls+caption, standalone CLI hashes raw PNG bytes | bare hex on the dead Python-builder path; unconstrained on the live LLM-agent path | the only hash in the whole regulatory pipeline hashes citation+title strings, not source bytes | 3 incompatible wire formats repo-wide: TEXT bare-hex (majority), BYTEA raw digest (visa_engine, newest/hardened), VARCHAR(32) MD5 (`documents.content_hash`, still written) — see §2.6 |
| **`created_at` vs `published_at` vs `observed_at`/`first_seen_at`** | no `created_at` (uses `first_seen_at`/`last_seen_at`); `intel_observations.observed_at` = per-hit append-log time | `detected_at` — a 4th timestamp name for the same "when we found it" concept | `PendingArticle.created_at` = pipeline processing time, separate from its own `published_at` | — | manifest `created_at`/`completed_at` vs per-segment `t_start`/`t_end` in `script.json` (different granularity) | `first_seen_at`(observed, 23/25) vs `run_at`(58/58) vs abandoned `enacted_date`/`effective_date` (valid-time, 3/25 combined) — valid-time vs observed-time is **not separated as an enforced rule anywhere in this corpus** | — |

**The three worst, called out explicitly** (as the dispatch requires):

(a) **`manifest` names three different incompatible shapes inside WR2 alone** — the Playwright
render-QA dict, the live Drive-staging audit sidecar, and the external-import builder — and a 4th/5th
shape in WR3 and the Magazine on top of that. None of the five is "the manifest."

(b) **`published_at` means the SOURCE's publish date in Intel Lake but OUR publish action in the News
Room and the scraper** — the exact opposite meaning on the same field name, one system apart.

(c) **`auto_publish` is dead in both places it exists** (bali-intel-scraper's `GateDecision.AUTO_PUBLISH`
never calls a publish API; `WR2_AUTO_PUBLISH_ENABLED` is a zero-occurrence env var), **while the human
gate that IS enforced lives under a completely different name**:
`wr2_publish_attempts.state='blocked_manual_gate'`, an HMAC-signed, expiring, Telegram-inline-button-
verified token.

**Practical consequence for P04**: the canonical contract cannot reuse `status`, `source`, `published`,
`claim`, `manifest`, `id`, `hash`, or `approved` as bare field names without namespacing — every one of
them already means something different, actively, in at least one shipped system. P04's own contract
document must say this explicitly (either namespace every field by owning system, e.g.
`intel_lake.routing_status`, or scope the contract to net-new tables and declare every one of these words
reserved/out-of-bounds for reuse).

---

## §4 — Constraints P04 must honour

1. **`events_outbox` is already a general event broker** — 26 channel values (exact, §2.6), 5+ producing
   subsystems, 4+ consumers. P04's stated non-goal is "do not create a new general event broker" — so
   **P04 emits new `channel` values, it does not build a parallel table.** One orphan channel
   (`wr3_episode_*` = writer with no subscriber) is the cautionary tale for how easily this pattern
   silently rots once a channel is declared — P04 must ensure every new channel it adds has both a
   confirmed writer and a confirmed subscriber before being called "wired," not merely declared in a
   map/comment. (`lkpm_ingest_completed` was corrected out of this list 2026-08-23 — it is live and
   wired, see §2.6.)

2. **PostgreSQL 15 compatibility is mandatory for the migration/test path.** CI's four PR-gating
   workflows run `postgres:15` (service containers), local docker-compose across all three apps runs
   `postgres:15-alpine`; production is doctrinally 17.7 (unverified from any file in this repo, last
   empirically-confirmed image was 17.2). Postgres 17 does appear elsewhere in CI — the monthly
   restore-drill job (`.github/workflows/restore-drill.yml:32`) runs `postgis/postgis:17-3.5` — but that
   job restores a production dump, it does not run migrations/tests. A PG16+-only feature passes a local
   17.8 apply and the restore-drill's PG17 container, then still dies in the migration/test CI path,
   which pins 15.

3. **`DEFERRABLE INITIALLY DEFERRED` has zero live uses.** Exactly two grep hits repo-wide: migration 173
   added one, migration 175 dropped it two migrations later and replaced it with a partial unique index
   because the full-tuple DEFERRABLE UNIQUE over-constrained the actual invariant (it also blocked
   legitimate multiple terminal-state rows). The frozen P04 contract requires deferred cross-object
   constraints for atomic classification bundles — **P04 would be the first live user of this Postgres
   feature in this schema, and the only prior attempt here was reverted.** Flag as a design risk needing
   the Conductor's explicit attention; the proven local alternative where the invariant is "one active
   row" is the partial-unique-index idiom (`compliance_alerts.dedup_key`, the wa-mirror replacement
   index).

4. **Three incompatible hash wire formats coexist** (§2.6 detail): bare lowercase hex TEXT/CHAR(64)
   (majority pattern, matches P04's `^[0-9a-f]{64}$` mandate); `BYTEA(32)` raw digest (the entire,
   newest, most-hardened visa_engine surface, which validates bare hex at the Python boundary via
   `Sha256Hex` then converts `bytes.fromhex(...)` at the DB boundary); `VARCHAR(32)` **MD5** on
   `documents.content_hash`, still actively written by 2 live 2026-era call sites. P04 must state
   explicitly whether its own columns are TEXT-hex or BYTEA-with-hex-at-the-boundary — do not assume
   TEXT is the only precedent, since the highest-stakes existing tables chose BYTEA.

5. **Existing idempotency-key idioms**: the dominant *new*-key pattern is the `intake` family
   (`intake_key`, `intake_idempotency_key`) — TEXT, bare sha256 hex, plain UNIQUE (or per-client-scoped
   UNIQUE where two clients may legitimately share a physical blob — an explicit panel-ruled design, not
   an oversight). Real variants that also exist and that P04 should be aware of before inventing a
   fourth: composite string keys (`<carousel_id>:<platform>:<content_hash[:16]>`, WR2), partial-unique-index-scoped
   keys (non-terminal rows only), prefixed-and-truncated hex (`"rk:"+hex[:48]`), and a
   privacy-motivated `BYTEA PRIMARY KEY` digest that never stores the raw key at all (visa_engine).

---

## §5 — Meta-pattern: the organism persists far more than it reads

This is the single most important finding in this inventory, confirmed independently by every one of the
six lanes without cross-talk between them.

**Evidence, one line per lane**:
- **NAGA** is entirely write-only in production. Sole writer `persist.py::save_session()`; every quality
  reader (`batch_rescore`, `find_duplicate`, `batch_dedup`, `cross_reference_claims`) is dead code with
  zero call sites; both HTTP read endpoints are hardcoded stubs (404 / `[]`); `naga_claim_transitions` has
  no production writer at all; `review_status`, called "the CRITICAL human review gate" by its own
  migration docstring, never transitions past its default; `source_span_hint` and `similarity_hash` are
  permanently NULL.
- **Intel Lake**: `intel_items.expires_at` dead (zero writers/readers on that column specifically);
  `intel_observations`/`intel_lake_audit_log` are write-only append sinks with no in-repo reader beyond
  raw ad-hoc SQL.
- **WR2**: `approved_by`/`approved_at` on `war_room_drafts` never written by any live script;
  `wr2_carousel_runs.state` never advanced past its INSERT value by any live code;
  `WR2_AUTO_PUBLISH_ENABLED` referenced only in a SQL comment, zero code occurrences.
- **WR3**: the entire hash-format-enforcing module (`wr3_episode_manifest.py`) is dead code — called
  only from tests. The one populated episode has no manifest artifact at all.
- **Publishing/regulatory**: valid-time fields (`enacted_date`/`effective_date`) used a combined 3 times
  across 58 runs, then abandoned each time.
- **`guardian_decisions`**: writer and reader have *never* agreed on a schema — every INSERT raises
  `UndefinedColumnError` and is silently swallowed. A write path that has plausibly never successfully
  written a row since it was authored.

**Diagnosis**: this is the repo's own documented superscar family **#2 (Esiste ≠ Armato)**
(`.claude/rules/cicatrix-superscar.md`), expressed at the DATA layer rather than the daemon layer —
*written ≠ read*, where family #2 is normally stated as *exists ≠ armed* for cron/daemons. A Postgres
`INSERT` always succeeds (barring a constraint violation), so nothing about a write-only field ever goes
red. A column can look fully alive in the schema — present, typed, indexed, even documented as "the
critical gate" in its own migration comment — for months, while nothing in the running system ever reads
it back.

**Consequence for P04 (concrete and load-bearing)**: "mapped losslessly" is a meaningless guarantee for a
field nothing has ever read — a canonical contract can faithfully round-trip a value through a schema
migration and still be delivering zero actual value, because P04's own fixtures would be the first code
in the system to read many of these fields. **The compatibility matrix P04 produces next must record,
per field, whether a LIVE READER exists** — not just whether the field is present, typed, and populated.

**Recommendation**: add a `reader_status` column — one of `live_reader` / `write_only` / `dead` — to every
row of the field-level compatibility matrix that P04 produces next. This document has already applied
that classification wherever a source sweep established it clearly enough to state (see the per-table
field tables in §2); P04's contract-design pass should treat any field left unclassified here as
`unknown`, not `live_reader` by default.

---

## §6 — Declared gaps

What this inventory does **not** cover, named rather than silently missing:

- **NEXUS** — owned by P01, not this sweep. Its sanitized baseline is P01's own deliverable; P04 uses
  synthetic red fixtures and never touches the real graph. Not investigated here at all.
- **`war_room_metrics`, `war_room_leads`, `war_room_rejections`, `war_room_missed_runs`, `war_room_costs`**
  — schema exists (migration 112), live-writer status **UNCONFIRMED** by the WR2 sweep (time-boxed, not
  opened this pass). Not asserted dead or live.
- **`wr2_carousel_events_outbox`'s producer** — the consumer module (`wr2_outbox_consumer.py`) was opened
  and confirmed dormant (zero call sites outside its own module+tests); no producer was located either.
- **`manual_publish_token` path in `wr2_publish_attempts`** — column exists, caller not located.
- **`apps/wr2-control-app`** (Swift macOS app, the actual Damar-facing UI) — not opened this pass; should
  be cross-checked against `_review-queue-schema.md` before treating either as ground truth for the
  human-review-queue contract.
- **The "NLM claim registry schema" `core/claims/models.py:60` claims to mirror** — not located/verified
  by the NAGA sweep; flagged as an open thread for whoever owns the NLM/KG lane.
- **`services/kg_monitoring/*`** — matched an initial NAGA grep on unrelated identifiers (e.g.
  `ketenagakerjaan`), spot-checked but not opened individually.
- **`crm_guardian_events`'s "additional hits surfaced by grep but not opened this turn"** (the shared-plumbing
  sweep's own caution): `109_garuda_curator.sql:67`, `169_crm_workspace_ai_snapshots.sql:19-35`,
  `264_visa_decision_retention_policy.sql:34-37`, `132_legacy_lkpm_reports.sql:66-67` — cite with caution,
  DDL-only evidence, no writer/reader traced.
- **`federation_alert_proposals` and `olympus_actions`** (both ranked as strong approval-receipt /
  outcome-event candidates in §2.6) — **no writer/reader file was opened this turn for either**; the
  ranking above is DDL-only evidence.
- **`documents.content_hash`'s live call sites** (`crm_enhanced_documents.py:606`,
  `drive_poll_service.py:569`) were confirmed as 2026-era live writers of the wrong-algorithm MD5 hash,
  but the sweep did not exhaustively confirm there are no *other* writers repo-wide.
- **`visa_evaluate_idempotency`'s undocumented column drift** — code reads/writes
  `response_hmac`/`response_hmac_key_id` columns not present in the one migration file this sweep read;
  a later, unread migration presumably added them. Whoever maintains this table should be told the
  migration this sweep cites (`262`) is not necessarily the full current schema.
- **`Postgres` production version** — genuinely unresolved by this sweep, not merely unverified: three
  independent sources disagree (doctrine says 17.7, the last empirical check found 17.2, local/CI agree
  on 15), and no file in this repo can adjudicate between the first two. Treat as an open question for
  whoever has `fly image show -a nuzantara-postgres` access, not as settled by this document.
- Every table/field the six source sweeps themselves marked **UNCONFIRMED** rather than
  confirmed-dead-or-live is carried forward with that same UNCONFIRMED status in §2 above — this section
  exists so none of those flags get lost between the raw sweeps and the version of this document P04's
  designers actually read.

---

## Adversarial review

**Reviewer**: Gemini 3.1 Pro, via the `agy` CLI, dispatched as an independent cross-family refuter
against this Claude-authored document — generator != grader (R1, `docs/specs/rules-as-harness-and-
simulation-chamber-v1.md` §2). **Verdict: SOUND with minor defects.**

**Load-bearing findings independently CONFIRMED** (the refuter re-derived these from the cited files
rather than taking the document's word for them):

- **NAGA is write-only in production** — 0 non-test call sites for any of its quality readers
  (`batch_rescore`, `find_duplicate`, `batch_dedup`, `cross_reference_claims` are all dead code), and
  both HTTP read endpoints are hardcoded stubs (404 / `[]`). This is §2.2's single most important
  finding, confirmed independently by all six original sweep lanes without cross-talk — the refuter's
  pass is a seventh, cross-family confirmation.
- **The WR2/WR3 manifest fragmentation** — `manifest` names at least 5 incompatible shapes across the
  two systems plus the Magazine (§3 row `manifest`), and WR3's own `episode_manifest.json` mandatory-
  field validator (`wr3_episode_manifest.py`) is dead code, called only from tests, with zero manifest
  artifacts existing on disk for the one populated episode.
- **The `DEFERRABLE INITIALLY DEFERRED` finding** (§4.3) — exactly two grep hits repo-wide, the second
  of which (migration 175) drops what migration 173 added two migrations earlier, replacing it with a
  partial unique index. P04 would be the first live user of this Postgres feature in the repo.

**Four factual defects found and corrected in this pass** (each verified independently on disk before
correcting, not taken on the refuter's word alone):

1. **`lkpm_ingest_completed` was wrongly listed as a writerless orphan channel.** It has a confirmed
   writer (`emit_ingest_event()`,
   `apps/backend-rag/scripts/import_lkpm_q1_2026_receipts.py:764`, called at `:970`) and two confirmed
   readers (`scripts/pg-to-organism-bridge.py:63`,
   `apps/backend-rag/backend/services/events/handlers/crm_hgt_handlers.py:204`). Moved to the
   live-and-wired category in §2.6; every downstream count (the "two orphan channels" framing in §2.6
   and §4.1, the 26th/27th-tenant arithmetic) corrected to match. A methodological caveat was added to
   the top-of-document Method description explaining why a channel-name grep missed it: the writer is
   reached through a function call, not the literal channel string, at its call site.
2. **`guardian_decisions` "0 matching columns" claim was numerically wrong, not fabricated.** Verified
   directly against both the writer (`services/compliance/alert_feedback.py:215,234`) and the table
   definition (`apps/backend-rag/backend/migrations/migration_098b_guardian_decisions.py`, 12 columns).
   The INSERT names 4 columns; 1 (`metadata`) is real, 3 (`decision_type`, `context`, `decision`) are
   not — a 3-for-4 mismatch, not 0-for-4. The conclusion (every INSERT raises `UndefinedColumnError`,
   silently swallowed) is unchanged and still correct; only the column-match count was corrected in
   §2.6.
3. **"Postgres 17 appears nowhere in CI" was too absolute.** The CI *migration/test* path is verifiably
   Postgres 15 (four workflows + docker-compose, unchanged finding), but
   `.github/workflows/restore-drill.yml:32` runs `postgis/postgis:17-3.5` for its monthly
   production-restore drill. Restated in §2.6/§4.2: the test path is PG15, production is 17.x, and a
   PG16+-only feature can pass a local 17.8 apply and the restore-drill's PG17 container before dying in
   the migration/test CI path — the practical consequence for P04 is unchanged.
4. **The "25+ channels" hedge is now an exact, cited count.** 26 distinct channel values write into
   `events_outbox`; of those, exactly 16 are registered in `PG_CHANNEL_MAP`
   (`apps/backend-rag/backend/services/events/event_bus.py:47-166`, verified by `ast`-parsing the dict,
   not grepping it) and 10 are not. The refuter's own headline number (26) was right for the
   events_outbox total but mis-attributed as being "in `PG_CHANNEL_MAP`" — that map holds 16, not 26;
   both counts are now stated separately and cited in §2.6.

**Two claims the refuter declared UNVERIFIABLE from static repository files — left flagged as unverified
in this document, not presented as measured:**

- **The live production PostgreSQL version.** Doctrine (`CLAUDE.md` §11) says 17.7; the last empirical
  check (2026-06-12) found 17.2; neither is adjudicable from any file in this repo. Resolving it needs a
  live infrastructure query (`fly image show -a nuzantara-postgres`), out of scope for a static sweep —
  see §2.6 and §6.
- **The external staging endpoint `/api/machine/publications/editions`.** No server handler exists
  anywhere in this repository (grep-verified); it presumably lives in a separate, external Bali Zero
  Magazine/Sites deployment this repo cannot see — see §3 row `manifest`/Magazine and the `stage_
  publication()` finding.
