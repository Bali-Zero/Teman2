# Sprint 3 W1.3 — mata-garuda-cell + asset provenance schema

**Date:** 2026-05-03 · **Author:** Sprint 3 Air session (Claude Opus 4.7 1M)
**Predecessors:** W1.1 (CRM inventory), W1.2 (crm-cell design)
**References:**
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md`
  § Sprint 3 + § "L4.5 mata-garuda-cell"
- `apps/mata-garuda/README.md` (existing walking skeleton)
- `apps/zantara-media/README.md` (Mata Garuda Layer 4.5 — asset indexer)

> **DRAFT FOR USER REVIEW.** Same conservative-default discipline as W1.2.
> Asset provenance schema is the heart of this doc; cell-class promotion
> is mostly bookkeeping over the existing walking skeleton.

## What we're building

Promote the existing **`apps/mata-garuda/`** walking skeleton (Sprint 1
state) to a full L4.5 cell with:

1. **Asset provenance schema** — per-asset row carrying source +
   confidence + owner + invalidation_path, queryable by other cells
   before they consume the asset.
2. **Cell descriptor** (`apps/mata-garuda/cell.yaml`) validated by
   `AdmissionTest` — declared at L4.5 (meta-awareness, separate tier
   from L1-L4).
3. **Bidirectional innervation** with WR2 — events flowing in BOTH
   directions, per 99b synthesis "Innervation incrociata bidirezionale".
4. **OSINT blindato preserved** — same constraints from existing
   `mata-garuda/README.md` (Pro-local, CLI-only, OSINT data never
   leaves the Pro perimeter).

## Why L4.5 (separate tier)

99b synthesis taxonomy:
- L1 — ground-truth ingest, signal extraction, metric capture
- L2 — orchestration / consumer / infrastructure
- L3 — synthesis across L1 outputs
- L4 — strategic recommendations
- **L4.5 — meta-awareness: cells reasoning ABOUT other cells' outputs**

Mata-Garuda is L4.5 because its job is "intelligence about intelligence":
it provenance-tags assets that other cells (L1 trend-hunter, L1
intel-scraper-cell, L3 strategos, L4 oracle) produce or consume.
It doesn't produce primary intel — it tags the primary intel with
trustworthiness metadata.

This is structurally distinct from "Mata Garuda Layer 4.5" mentioned
in `apps/zantara-media/README.md` (asset indexer). The cell `level:
L4.5` is the SAME meaning, picked up from the existing terminology.

## Asset provenance schema (the core deliverable)

### Why this matters

CRM enrichment, WR2 dossier compilation, intel-scraper findings, and
KG-bridge proposals all consume "data from somewhere". Today the
"somewhere" is implicit (logged in scraper output, but not queryable).
When a downstream cell decides "should I trust this entity?",
it has no programmatic way to ask "what's the provenance?".

The schema makes provenance a **first-class queryable artifact**.

### Schema (migration 154 target)

```sql
-- 154_mata_garuda_asset_provenance.sql
--
-- Sprint 3 W1.3 — Mata-Garuda asset provenance schema
--
-- Per-asset row carrying source + confidence + owner + invalidation_path.
-- Other cells query this BEFORE consuming an asset (cross-cell trust check).
--
-- Idempotency: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS asset_provenance (
    id BIGSERIAL PRIMARY KEY,

    -- What asset are we tagging? Asset ID is opaque — could be a UUID
    -- (war_room_drafts.id), a Qdrant point_id (intel findings),
    -- a kbli_code (KG entity), a client_id, a research_dossier slug.
    -- The asset_kind disambiguates the namespace.
    asset_kind TEXT NOT NULL CHECK (asset_kind IN (
        'war_room_draft',
        'war_room_post',
        'intel_finding',
        'research_dossier',
        'cross_dossier_thesis',
        'weekly_strategic_brief',
        'ultra_move',
        'kg_entity',
        'kg_proposal',
        'crm_enrichment_lookup',
        'compliance_alert',
        'measurer_metric'
    )),
    asset_id TEXT NOT NULL,    -- string for uniformity; UUIDs cast to text

    -- WHO produced it? Free-form but constrained namespace.
    -- Examples: 'wr2.connector', 'intel-scraper-cell.bali_tribunnews',
    -- 'crm-cell.enrichment.google_places', 'kg.imigrasi_extract',
    -- 'oracle', 'manual.zero', 'manual.team.<email>'
    source TEXT NOT NULL,

    -- HOW confident are we? 0.0-1.0 calibrated.
    -- Convention (W2 will codify):
    --   1.00 — manual entry by Zero / canonical authority
    --   0.90 — manual entry by Bali Zero team member
    --   0.80 — automated extraction from .go.id source w/ 2+ corroborations
    --   0.70 — automated extraction from .go.id source, single source
    --   0.60 — automated extraction from established 3rd party (tribunnews)
    --   0.50 — automated extraction from social / less-vetted source
    --   0.30 — LLM inference without primary source citation
    --   0.10 — speculative (e.g. cross-thesis hypothesis with low corroboration)
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- WHO owns it? Owner = the human who can be asked "is this still true?".
    -- For automated sources, owner = the team responsible for that data
    -- domain (visa-team, tax-team, etc.). For manual entries, owner =
    -- the email of the person who entered it.
    owner TEXT NOT NULL,

    -- HOW does this asset get invalidated? A predicate-string the consumer
    -- can interpret as "is this still valid?". Format:
    --   'time:7d' — expires 7 days after created_at
    --   'time:90d' — expires 90 days
    --   'event:reg_alert.<topic>' — invalidated by a reg-alert on topic
    --   'manual' — never auto-expires; manual review required
    --   'never' — canonical, doesn't change (e.g. ID number formats)
    invalidation_path TEXT NOT NULL,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Optional structured metadata (JSON for forward-compat, NOT for query
    -- — index-by structure later if a payload field becomes hot)
    metadata JSONB DEFAULT '{}',

    -- Uniqueness: one provenance row per (asset_kind, asset_id) pair.
    -- If an asset is re-tagged (e.g. confidence bumped after corroboration),
    -- UPDATE in place; don't create a second row.
    UNIQUE (asset_kind, asset_id)
);

-- Index for the most common query: "what assets does X own?"
CREATE INDEX IF NOT EXISTS ix_asset_provenance_owner
    ON asset_provenance (owner);

-- Index for invalidation sweeps: "which time-based assets are expiring?"
-- Partial index — only on time:* invalidation paths.
CREATE INDEX IF NOT EXISTS ix_asset_provenance_invalidation_time
    ON asset_provenance (created_at)
    WHERE invalidation_path LIKE 'time:%';

-- Index for confidence-band queries: "show me low-trust assets"
CREATE INDEX IF NOT EXISTS ix_asset_provenance_confidence
    ON asset_provenance (confidence)
    WHERE confidence < 0.5;

-- Index for source-of-truth queries: "what came from KG?"
CREATE INDEX IF NOT EXISTS ix_asset_provenance_source
    ON asset_provenance (source);

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_asset_provenance_source;
DROP INDEX IF EXISTS ix_asset_provenance_confidence;
DROP INDEX IF EXISTS ix_asset_provenance_invalidation_time;
DROP INDEX IF EXISTS ix_asset_provenance_owner;
DROP TABLE IF EXISTS asset_provenance;
```

### Why those four columns

- **`source`** — without this, "where did this come from" is a grep
  through scraper logs. With it, every consumer can filter
  trustworthy sources without re-implementing source-vetting logic.
- **`confidence`** — calibrated 0.0-1.0 lets consumers pick threshold
  bands (intel-radar might require ≥0.8; CRM enrichment might
  accept ≥0.5).
- **`owner`** — separates "machine produced it" from "human can
  vouch for it". For high-stakes decisions (compliance, immigration
  filing), consumer can require `owner LIKE '%@balizero.com'`.
- **`invalidation_path`** — the killer feature. "Is this still
  valid?" is the question every consumer wants to ask but today
  can't. The predicate-string is parseable by a small library
  (W2 deliverable) so consumers don't have to re-invent expiration
  checking.

### NOT in the schema

- **No `asset_payload`** — the asset itself lives in its own table
  (`war_room_drafts`, `intel_radar_findings`, `kg_entities`, etc.).
  Provenance is metadata-only.
- **No `superseded_by`** — when an asset is re-tagged, UPDATE in
  place (the UNIQUE constraint enforces this). If you need history,
  add it later via a separate audit table; YAGNI for Sprint 3.
- **No FK to a hypothetical `assets` table** — there is no such
  table; assets live across many tables in many namespaces.
  `asset_kind + asset_id` is the polymorphic ref pattern, accepted
  trade-off for cross-namespace provenance.

### Trigger emission

```sql
CREATE OR REPLACE FUNCTION notify_asset_provenance()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    event_type   TEXT;
    outbox_id    BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        event_type := 'provenance_recorded';
    ELSIF TG_OP = 'UPDATE' THEN
        event_type := 'provenance_updated';
    ELSE
        RETURN COALESCE(NEW, OLD);
    END IF;

    payload := jsonb_build_object(
        'provenance_id',     NEW.id,
        'asset_kind',        NEW.asset_kind,
        'asset_id',          NEW.asset_id,
        'source',            NEW.source,
        'confidence',        NEW.confidence,
        'owner',             NEW.owner,
        'invalidation_path', NEW.invalidation_path,
        'event_type',        event_type,
        'occurred_at',       NEW.updated_at
    );

    -- Mig 146 outbox pattern (durability before pg_notify)
    INSERT INTO events_outbox (channel, payload)
    VALUES ('asset_provenance', payload)
    RETURNING id INTO outbox_id;

    PERFORM pg_notify(
        'asset_provenance',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER asset_provenance_notify
    AFTER INSERT OR UPDATE ON asset_provenance
    FOR EACH ROW
    EXECUTE FUNCTION notify_asset_provenance();
```

`PG_CHANNEL_MAP` adds: `"asset_provenance": "mata_garuda.asset_provenance"`.

## Bidirectional innervation with WR2

Per 99b synthesis: "Innervation incrociata bidirezionale Mata-Garuda ↔
WR2". Two flows:

### WR2 → Mata-Garuda (event: WR2 tags an asset for Mata-Garuda to learn)

When WR2 newsletter publishes a `war_room_post`, the cell calls
`mata_garuda.tag_provenance(asset_kind='war_room_post', asset_id=...,
source='wr2.newsletter', confidence=0.9, owner='damar@balizero.com',
invalidation_path='time:90d')`. Tag goes into `asset_provenance`,
trigger fires `asset_provenance` event.

### Mata-Garuda → WR2 (event: invalidation_path triggered)

Mata-Garuda runs a daily cron (`apps/mata-garuda/cell.yaml`
`runtime: pro-cron`) that scans for `time:Nd` rows past expiration
+ `event:*` rows where the matching event has fired. For each
expired row, emits `asset_invalidated` event. WR2 supervisor LISTENs
on `asset_invalidated` and reacts (e.g. dossier-compiler re-scrapes
the source, oracle's ultra_move citing this asset gets demoted).

Channel name: `asset_invalidated`. Same outbox pattern.

`PG_CHANNEL_MAP`: `"asset_invalidated": "mata_garuda.asset_invalidated"`.

## Cell descriptor (`cell.yaml`)

```yaml
# mata-garuda-cell — Sprint 3 W2 (promotion from walking skeleton)
# Reference: docs/sprint3/mata-garuda-cell-design.md
# Validated against 7 Leggi via packages/cell-core/cell_core/admission_test.py.

name: mata-garuda-cell
version: 0.1.0
level: L4.5            # meta-awareness — reasoning ABOUT other cells' outputs
runtime: pro-cli + pro-cron
owner: zero            # exclusive owner per existing OSINT blindato constraint

cell_class: cell

# 7 Leggi declarations
exposes_gui: false
llm_invocation: cli_subprocess   # Claude/Gemini/Codex CLI subprocess only
                                  # (per existing mata-garuda principle #1)
external_sources: []             # OSINT blindato — Pro-local, no inbound cloud
client_data_access: false        # Mata-Garuda does NOT touch CRM client data
                                 # by design (separate from crm-cell domain)
publishes_via: pg_notify         # asset_provenance + asset_invalidated channels

fallback_modes:
  - postgres_down       # Pro-local SQLite mirror in mata-garuda for read-only
  - cli_subprocess_fail # log scar to genome, retry on next run
  - cloud_disconnected  # natural state per principle #3 — feature, not failure

kill_switch: true       # disable: launchctl unload com.matagaruda.<all>.plist
auto_publishes: false   # provenance tags require explicit cell call
                        # (no autonomous "tag everything in sight" behavior)

depends_on_other_cell_decisions: false   # Mata-Garuda observes assets,
                                         # does not gate other cells'
                                         # decisions (consumers OPTIONALLY
                                         # query provenance)

genome_integration:
  registered: true
  reason: |
    Mata-Garuda is structurally distinct from nuz-sync (cicatrix exclusion).
    Pro-local cell with launchd-only writes via canonical install paths
    (no rogue plist mutation). Supervisor pulse adds value for centralized
    health view across the 9 com.matagaruda.* LaunchAgents.
  pulse_endpoint: pro_local       # not HTTP — the supervisor reads pulse
                                  # via launchctl print state for each LA

events:
  inbound:
    - war_room_event              # consumes WR2 publishes, may auto-tag provenance
    - intel_event                 # consumes scraper findings, may auto-tag
    - cognitive_event             # consumes oracle/strategos for trust monitoring
  outbound:
    - asset_provenance            # NEW (mig 154) — emitted on INSERT/UPDATE
    - asset_invalidated           # NEW (mig 154 follow-up) — daily cron sweep

sub_organelles:
  - name: provenance_tagger
    location: pro
    runtime: in_process_within_cell
    role: ingest WR2/intel/cognitive events, derive provenance tags
  - name: invalidation_sweeper
    location: pro
    schedule: "13 4 * * *"   # daily 04:13 WITA — off-minute, off-hour
    script: scripts/mata_garuda_invalidation_sweep.py
    role: scan asset_provenance for time:Nd or event:* expirations,
          emit asset_invalidated events

metrics:
  - assets_tagged_today
  - invalidations_emitted_today
  - tags_by_confidence_band      # histogram 0.0-0.3 / 0.3-0.6 / 0.6-1.0
  - tags_by_source               # cardinality per source identifier
  - sweeper_duration_ms

# Layer 4.5 specific — what makes this a META-awareness cell
meta_awareness:
  observes_cells: [wr2-organism, intel-scraper-cell, kg-cell, crm-cell]
  does_not_observe: [self]       # MUST NOT tag own outputs (avoid feedback loop)
  trust_function: |
    confidence(asset_X) = f(source_reputation, corroboration_count,
                            owner_reliability, time_since_creation)
  feedback_to_observed_cells: |
    Via asset_invalidated event. Cells optionally subscribe;
    Mata-Garuda does NOT push fixes — it raises questions
    (per existing principle "Lamarckian — ogni regola
    richiede review", review = the consumer cell decides).
```

## What this enables (concrete examples)

### Example 1: CRM enrichment trust check

```python
# In crm-cell enrichment, before merging external data:
prov = await mata_garuda.get_provenance(
    asset_kind='crm_enrichment_lookup',
    asset_id=f'{client_id}:google_places:{place_id}',
)
if prov is None or prov.confidence < 0.5:
    # Don't auto-merge; flag for team review
    return ReviewRequired(reason='no_provenance_or_low_confidence')
```

### Example 2: WR2 oracle ultra_move citation guard

```python
# In oracle synthesis, before citing a thesis:
prov = await mata_garuda.get_provenance(
    asset_kind='cross_dossier_thesis',
    asset_id=str(thesis_id),
)
if prov.invalidation_path == 'time:90d':
    age_days = (now - prov.created_at).days
    if age_days > 90:
        # Skip the thesis; ask connector to re-corroborate
        await event_bus.emit_pg('cognitive_event',
            {'event_type': 'thesis_stale', 'thesis_id': thesis_id})
        return None
```

### Example 3: KG entity demotion

```python
# Daily KG quality cron:
expired = await mata_garuda.list_expired_assets(asset_kind='kg_entity')
for asset_id in expired:
    await kg.demote_entity(asset_id, reason='provenance_expired')
```

## Migration impact summary (for W2 planning)

- **Migration 154** — `asset_provenance` table + INSERT/UPDATE
  trigger emitting `asset_provenance` channel.
- **Migration 155** (later in W2) — daily cron-emitted
  `asset_invalidated` channel via `notify_asset_invalidated()`.
- **`PG_CHANNEL_MAP`** — add 2 entries for the new channels.
- **Test mirroring:** `backend/tests/db/test_migration_154.py`
  + `test_migration_155.py` following `test_migration_152.py` template.
- **Cell descriptor:** `apps/mata-garuda/cell.yaml`.
- **Adapter module:** `apps/mata-garuda/mata_garuda/cell_adapter.py`
  exposing `tag_provenance`, `get_provenance`,
  `list_expired_assets`. ~150 LOC.
- **Admission test:** `packages/cell-core/tests/test_admission.py`
  `test_mata_garuda_cell_admission()`.
- **Sweeper script:** `scripts/mata_garuda_invalidation_sweep.py`
  + `infra/launchagents/com.matagaruda.invalidation-sweep.plist`
  (KeepAlive=false, StartCalendarInterval Hour=4, Minute=13).

## Risks called out

1. **Polymorphic FK is unverifiable.** `asset_kind + asset_id`
   doesn't enforce that `asset_id` actually exists in the target
   table. A weekly garbage-collection cron is W2 backlog.
2. **Confidence calibration is subjective.** The 0.0-1.0 band
   convention in the schema is a starting point; W2 codifies it
   via `mata_garuda.confidence_calibration` constants. Should
   be reviewed quarterly.
3. **Self-tagging trap.** `meta_awareness.does_not_observe: [self]`
   is enforced by convention only (cell won't tag
   `asset_provenance` rows); add an assertion in the cell adapter
   in W2 (`assert asset_kind != 'asset_provenance'`).
4. **Volume.** Every WR2 post + every intel finding + every CRM
   enrichment lookup → one provenance row. Estimate: ~500 rows/day.
   Table grows ~180k rows/year. The partial indexes keep query
   cost bounded; full-table scans only on the `metadata` JSONB
   for cross-source queries (not hot path).
5. **Pro-only constraint asymmetry.** Like crm-cell drive_poll,
   the invalidation sweeper runs Pro-only. If Pro is down for
   >24h, expirations stop. Tradeoff accepted (Mata-Garuda is
   Pro-exclusive by design — principle #3).

## Bidirectional innervation status (per 99b synthesis check)

99b synthesis required: "Innervation incrociata bidirezionale
Mata-Garuda ↔ WR2".

✅ **WR2 → Mata-Garuda:** WR2 events (war_room_event, intel_event,
   cognitive_event) consumed by `provenance_tagger` sub-organelle.
   Auto-tagging logic in cell adapter.

✅ **Mata-Garuda → WR2:** `asset_invalidated` channel consumed by
   wr2_supervisor (extension to existing supervisor's LISTEN
   handlers, not in this design's scope — Sprint 4 backlog).

The bidirectionality is in the channel topology; whether wr2_supervisor
actually subscribes to `asset_invalidated` is a future-Sprint
decision. The cell EMITS regardless.

## What this doc does NOT decide

- The `confidence_calibration` constants table (W2 codification).
- The `invalidation_path` parser implementation (W2 — the predicate
  language is small but needs unit tests).
- Garbage collection of provenance rows for deleted assets (W2 backlog).
- WR2 supervisor's subscription to `asset_invalidated` (Sprint 4 work).
- Mata-Garuda's existing `cell/` and `cells/` dirs reorg (out of scope
  for cell-class promotion — those modules stay as-is, the cell
  adapter wraps them).

## Sprint 3 design phase complete

W1.1 (inventory) + W1.2 (crm-cell design) + W1.3 (mata-garuda-cell
+ provenance schema) — all three docs ready for review. W2 (code
phase) opens once user signs off on the architectural picks.

W2 estimate: ~5-7 days of focused work (migration 153 + 154 + 155,
cell adapters for both cells, admission tests, integration tests,
PR per phase).
