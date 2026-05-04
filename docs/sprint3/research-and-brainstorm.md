# Sprint 3 W1 — Research & Brainstorm: Self-Improving Agents, CRM-Cell, Mata-Garuda-Cell

**Date:** 2026-05-04
**Author:** Claude Opus 4.7 (Air session, antonellosiano@Nuzantara-9)
**Scope:** Validate Sprint 3 design choices for `crm-cell` + `mata-garuda-cell` against academic literature and production OSS implementations.
**Method:** WebSearch + Brave + WebFetch (Exa+Perplexity quotas exhausted). 5 parallel research streams.

---

## TL;DR — What changed after research

| Design choice (pre-research) | Validated? | Action |
|---|---|---|
| SQLite + FTS5 for genome | ✅ matches Voyager (Chroma per skill, JSON+files for code) | Keep |
| Confidence threshold 0.7 + scope=Project for HGT publish | ⚠️ no literature anchor; ExpeL uses importance-count (start 2, prune 0) | **Add `uses ≥ MIN_USES` AND `confidence ≥ 0.7` AND `std < threshold` over 7d window** (mirror HGTCoordinator) |
| 0.9x decay on inheritance | ✅ Voyager has no decay; ours is more conservative | Keep |
| 7-day cooldown on rejected proposals | ⚠️ no direct literature anchor | Keep (operational pragma — escalation noise control) |
| 5-phase lifecycle (embrione/neonato/giovane/adulto/anziano) | ⚠️ unique to our design; SOAR/ACT-R have no equivalent | **Document as design-original, justify by HITL frequency findings (§2.3)** |
| Polymorphic FK for asset_provenance (asset_kind+asset_id, no FK) | ⚠️ GitLab/Rails warn against for >5 entity types AND when consistency matters — but only 4/12 asset_kinds have PG tables (rest in Qdrant + external systems), so per-asset-kind FK link tables are infeasible | **Keep polymorphic** with documented "unverifiable FK" limitation; weekly orphan-GC cron mitigates. Multi-LLM review 2026-05-04 rejected the 3-layer pivot — see mata-garuda-cell-design.md § "M1 — CONSIDERED AND REJECTED". |
| 6-band confidence (UNCONFIRMED→CONFIRMED) | ✅ matches MISP admiralty A-F + 1-6 | Keep, **map to Admiralty explicitly** |
| Outbox + pg_notify | ✅ event-driven.io best practice; Twenty CRM uses BullMQ on top | Keep, our migration 146 is correct |
| ~50 practice events/day, ~100 Drive events/day | ✅ well below LISTEN/NOTIFY breaking point (`max_connections` exhaustion) | Keep direct LISTEN, no PgDog yet |

**Three concrete proposals each for crm-cell and mata-garuda-cell follow in §6.**

---

## Stream 1 — Self-Improving Agents

### Voyager (NeurIPS 2023, Wang et al.) — `MineDojo/Voyager`

**Skill schema (verified from `voyager/agents/skill.py`):**

```
{ckpt_dir}/skill/
├── code/{name}.js          # JavaScript function (action body)
├── description/{name}.txt  # generated NL summary
├── skills.json             # metadata dict
└── vectordb/               # Chroma collection (OpenAI embeddings of description)
```

Per-skill fields: `name` (unique key), `code` (JS body), `description` (NL summary, indexed in vector DB).

**Add policy** (`add_new_skill(info)`):
- Filter out trivial tasks (e.g., "Deposit useless items...")
- On duplicate name: rename old to `{name}V{i}` (versioning, no overwrite)
- Assert `vectordb.count() == len(skills.json)` post-insert

**Retrieval** (`retrieve_skills(query)`):
- `top_k = min(vectordb.count(), retrieval_top_k=5)`
- Cosine similarity (Chroma default)
- **No confidence/score gating** — all top-K returned

**Pruning/decay:** **NONE.** Skills persist indefinitely. The paper does not address skill bloat — it's a known limitation.

**Failure mode (from issue #98 on autogen):** The community tried to port Voyager's skill library to AutoGen; the issue was **closed as not planned**. The pattern doesn't generalize trivially because (a) JS/Python skill code is harder to verify than Minecraft action sequences, (b) skill retrieval by description embedding is noisy when descriptions overlap.

→ **Implication for cell-core:** Our genome already does better than Voyager (FTS5 instead of just embeddings, `uses` counter, `decay_unused_skills`, scope=Project|Personal). **Voyager schema validates the 3-file split (code + description + metadata) — we collapsed it into one SQLite row, which is cleaner at our scale (10-100 skills/cell).**

### ExpeL (AAAI 2024, Zhao et al.) — `LeapLabTHU/ExpeL`

**Insight extraction operations:**
- **ADD**: new insight, importance=2 (initial)
- **UPVOTE**: importance += 1
- **DOWNVOTE**: importance -= 1
- **EDIT**: rewrite content, importance unchanged
- **PRUNE**: when importance reaches 0, remove

**Bounds (from code):**
- `agent.max_num_rules = 10` (target insight count per task family)
- `agent.success_critique_num = 8` (experiences sampled per iteration)

**Insight format:** Free-text NL strings, no structured fields. Examples:
- "Consider the answer might be in the observations already made"
- "When searching for an item, consider its nature and typical usage"

**Cross-task abstraction:** Compares pairs (failed, successful) from same task; extracts what changed. Then aggregates patterns across multiple successes.

**Results:** ReAct→ExpeL improvement: HotpotQA 28%→39%, ALFWorld 40%→59%.

→ **Implication for cell-core:** Our `insight` entry type maps directly to ExpeL insights. **The `importance ≥ 2` initial / `prune at 0` policy is missing from our genome** — currently we use `confidence` (0-1) which is finer-grained but harder to update via votes. **Proposed addition: insight gets `votes` column (default 2 on creation), increment on `use_skill` success, decrement on failure or scar emission, prune at 0.**

### Reflexion (NeurIPS 2023, Shinn et al.) — `noahshinn/reflexion`

Reflections are **per-trial NL summaries** appended to episodic memory. Reward signal can be binary, scalar, or NL feedback. **Memory window is unbounded in the reference impl** (it relies on the LLM context window to truncate naturally).

→ **Implication for cell-core:** Our `Episode` (in `types.py`) with ACT-R activation = Reflexion + decay. **Better than Reflexion** (we have explicit decay + confidence vs unbounded memory + LLM-context-truncation).

### Anti-loop / Cooldown — Literature gap

Voyager: no cooldown.
ExpeL: implicit (insight prune at 0).
Reflexion: no cooldown.

**Our 7-day cooldown is original.** It exists because we have a Redis Streams-backed feedback loop (parent could re-receive same proposal); academic single-agent setups don't have this concern. **Keep as-is.**

### SQLite vs Postgres vs Vector DB

- **Voyager:** Chroma (per-skill embeddings) + JSON files (metadata) — works at ~50 skills.
- **ExpeL:** in-memory dict during training, dumped to JSON.
- **AutoGen:** SQLite with simple key-value schema.
- **MetaGPT:** YAML files for "expertise levels" (no DB).

→ **Our SQLite+FTS5 is well-calibrated for 10-100 skills/cell.** At >1000 skills/cell, we'd need to revisit (Postgres + pgvector). At our scale, no change.

**Verdict for Stream 1:** Cell-core genome design is **on-par or better** than published systems. Two concrete additions: (a) ExpeL-style importance count for `insight` type, (b) document the 7d cooldown as original-design.

---

## Stream 2 — Tiered Autonomy

### Devin (Cognition Labs) — Two non-negotiable checkpoints

Devin operates with **strict HITL at exactly two points**:
1. **Planning Checkpoint:** human reviews+approves Devin's written plan before any code execution.
2. **PR Checkpoint:** human reviews PR after Devin's tests pass.

Between checkpoints: full autonomy (multi-step debug, refactor, retry). **No mid-stream approval prompts.**

**Production pattern reported:** "After investing initial time to teach Devin how to approach sub-tasks, Devin can complete the migration autonomously while a human is kept in the loop to manage the project and approve changes."

→ Maps directly to our **adulto** phase (post-admission, full autonomy on declared scope). Our **embrione/neonato** phases = "teaching investment" period.

### Replit Agent / Cursor / Claude Code — Spectrum

- **Cursor / Codex Desktop / Claude Code:** "supervised pair programming" — every suggestion reviewed.
- **Replit Agent 3:** "limited async" — single-shot execution, end-state review.
- **Devin:** "async task delegation" — only end-state review.

**No production system uses 5 phases like ours.** The de-facto industry pattern is **2-3 levels** (interactive / async-bounded / async-full).

→ **Our 5 phases are over-engineered for what most agents need.** But for cell-core (an *organism* with cells of varying maturity), it makes sense — different organs (kbli-cell newborn vs mata-garuda-cell adult) need different gates **at the same calendar time**.

### HITL frequency studies

No quantitative threshold appeared in published literature. Industry signal:
- Devin's "plan + PR" model: **2 HITL touches per task** (typical task = hours).
- Replit Agent: **1 HITL** (end-state).
- Anthropic AUTONOMOUS_OPS L2 (our project): **0 HITL on commits, push, deploy if listed scope; 1 HITL on shared-state changes.**

→ **HITL frequency is task-duration dependent.** For long autonomous loops (like our `/loop` work), **plan-approval + final-review** = the proven minimum. Mid-stream HITL = noise.

### Autonomy drift failures

**COMPEL Framework case study** (URL exists but content not retrieved): documents incidents where Devin/Replit Agent caused damage in production. Without the article body, the indirect signal from the article title ("Coding-Agent Incidents from the Architect's Seat") implies post-mortems exist but weren't accessible.

**Generic patterns documented elsewhere:**
- AutoGPT: infinite loops on under-specified goals (well-known).
- Devin: occasional "shortcut taken" — tests pass but task semantics violated.
- Replit Agent: app generation works but deploy step often manual.

→ **Our `AdmissionTest` (7 Leggi) is more rigorous than any production system.** Devin/Replit have implicit guardrails (sandboxes, PR gates) but no formal admission test. Our DNA hash + budget validation + kill_switch = better than all.

### Metabolic metrics in production

**No company publishes TTR/AutonomyIndex/EscalationFreq externally.** These are SRE-internal. SREs measure:
- MTTR (mean time to resolve) — same as our TTR
- "Self-resolution rate" — same as our AutonomyIndex (ratio)
- "Page rate" — same as our EscalationFreq (inverse)

→ **Our 4 metrics are well-calibrated to industry SRE practice.** Names differ; concepts identical. **OntologyDensity is original** (graph-density metric for KG quality).

### SOAR / ACT-R / Homeostatic models

ACT-R has "activation" (decay over time, boost on retrieval) — **we already implement this** in `Episode.activation`. SOAR has "preference architecture" — distinct from our model.

**Homeostatic stress/energy/arousal:** "Physiological moderators have systemic effects on attention, decision making, memory retrieval" (academic survey). **No production LLM-agent system implements this.** Recent paper: "Human-Like Remembering and Forgetting in LLM Agents" (HAI 2025) — uses ACT-R-inspired memory but no homeostatic layer.

→ **Our `HomeostaticController(stress/energy/arousal)` is research-frontier, not production-standard.** **Opportunity:** publish a blog post about it; risk: untested in long-running production. **Recommendation:** keep as-is, document as "experimental" in cell.yaml schema.

**Verdict for Stream 2:** Tiered autonomy design is **more rigorous** than Devin/Replit/Cursor. The 5-phase lifecycle is unique; defensible because we run multiple concurrent cells with different maturity. Homeostatic layer is research-frontier — keep but document as experimental.

---

## Stream 3 — Provenance Schemas

### W3C PROV-O — Production usage

**Core triple:**
- `prov:Entity` — what was produced/consumed
- `prov:Activity` — the process that produced/consumed
- `prov:Agent` — who initiated

**Real production usage (MLflow + PROV-O via MLflow2PROV):**

| MLflow concept | PROV-O type |
|---|---|
| Run | `prov:Activity` |
| Artifact (model) | `prov:Entity` |
| Dataset (input) | `prov:Entity` |
| Metrics | `prov:Entity` |
| User/System | `prov:Agent` |

**Pattern:** Activities `prov:used` datasets and `prov:generated` models; both `wasAttributedTo` agents.

**Verbosity penalty:** Turtle/RDF serialization is **unfriendly to grep/SQL queries**. Production tools (MLflow native, OpenLineage) use **JSON facets** instead, with PROV-O as an export-time mapping.

→ **Implication for mata-garuda-cell:** Don't store raw PROV-O Turtle. Store **JSON facets** with PROV-O-equivalent fields (entity / activity / agent / used / generated / wasAttributedTo) — exportable to Turtle on demand.

### MLflow / OpenLineage

**OpenLineage core schema:** 3 types — Dataset, Job, Run. Extensible via **facets** (customizable metadata blocks attached to any of the 3).

**MLflow native lineage:** stored in `mlflow.runs` table with `inputs` JSON column. **Stale data invalidation: not addressed.** MLflow assumes immutable artifacts; reality (data drift) is a known gap.

→ **Implication for our asset_provenance:** OpenLineage's "facets" pattern is exactly what we need for polymorphic `asset_kind`. **Each asset_kind = a facet schema.**

### STIX 2.1 + MISP

**STIX 2.1 confidence:** numeric 0-100, with implicit mapping to NATO STANAG 2022 source grading + ICD 203 confidence levels (CONFIRMED, PROBABLE, POSSIBLE, DOUBTFUL, IMPROBABLE, MISINFORMATION/DECEIT).

**MISP admiralty taxonomy:**
- **Reliability A-F** (A=Completely reliable → F=Reliability cannot be judged)
- **Credibility 1-6** (1=Confirmed → 6=Truth cannot be judged)
- Combined: e.g., `admiralty-scale:source-reliability="b"` + `admiralty-scale:information-credibility="2"` = "Usually reliable + Probably true"

**Tag attachment pattern (machine tags):** `namespace:predicate="value"` — e.g., `tlp:amber`, `admiralty-scale:source-reliability="b"`, `CERT-XLM:malicious-code="ransomware"`.

→ **Implication for mata-garuda-cell:** **Use admiralty 2-axis (reliability A-F + credibility 1-6) instead of single 6-band.** This is the OSINT industry standard. Map our existing 6-band UNCONFIRMED→CONFIRMED to admiralty:
- F6 = UNCONFIRMED, F1 = SUSPECTED-FALSE, A6 = SUSPECTED, A3 = LIKELY, A2 = CONFIRMED, A1 = VERIFIED

Two independent fields (`reliability` + `credibility`) instead of one collapsed band. Costs 1 extra column. Buys 6×6=36 ordinal levels vs 6.

### Polymorphic FK — production tradeoffs

**GitLab production guidance** (`docs.gitlab.com/.../polymorphic_associations.html`):
> "Polymorphic associations should be avoided when possible. They make queries more expensive and break referential integrity."

**Hashrocket / Rails community consensus:**
- Type-discriminator + opaque ID (`asset_kind` + `asset_id`): **flexibility, NO referential integrity**, joins difficult, type column wastes ~10 bytes/row.
- **Exclusive-arc / nullable-FKs**: per-asset-type FK column, all but one are NULL per row, CHECK constraint. **Foreign key integrity preserved**, indexes work, joins normal.
- **PostgreSQL specific:** "null values are almost free; nullable fields can be added quickly regardless of table size."

→ **DESIGN PIVOT CONSIDERED, THEN REJECTED 2026-05-04** (see mata-garuda-cell-design.md § "M1 — CONSIDERED AND REJECTED" for the empirical check). The 3-layer schema below is **kept here for reference** — DO NOT implement. Reason: only 4/12 asset_kinds have PG target tables; 8/12 (research_dossier, cross_dossier_thesis, weekly_strategic_brief, ultra_move, kg_entity, kg_proposal, crm_enrichment_lookup, measurer_metric) live in Qdrant or external systems where Postgres FK is impossible. Original single-table polymorphic stays.

**Pre-research design (KEPT):** single `asset_provenance` table with `asset_kind VARCHAR + asset_id BIGINT` (polymorphic, no FK).

**Post-research recommendation (REJECTED — kept below for reference only):** 3-table layered approach (matched OpenLineage's facets pattern in spirit, but Gemini 3 Pro flagged that OpenLineage uses JSON facets, not 12 hardcoded link tables — the analogy was inaccurate):

```sql
-- Layer 1: PROV-O core (universal across all asset types)
CREATE TABLE asset_provenance (
    id BIGSERIAL PRIMARY KEY,
    activity_id UUID NOT NULL,                    -- prov:Activity ref
    agent VARCHAR(64) NOT NULL,                   -- prov:Agent (cell name)
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_url TEXT,
    source_sha256 BYTEA,
    -- MISP admiralty 2-axis (replaces single 0-1 confidence)
    reliability CHAR(1) NOT NULL CHECK (reliability IN ('A','B','C','D','E','F')),
    credibility SMALLINT NOT NULL CHECK (credibility BETWEEN 1 AND 6),
    -- Invalidation
    invalidation_path VARCHAR(64) NOT NULL,       -- 'time:Nd' | 'event:topic' | 'manual' | 'never'
    valid_until TIMESTAMPTZ,                      -- NULL if invalidation_path != 'time:Nd'
    invalidated_at TIMESTAMPTZ,
    invalidated_by VARCHAR(64),
    -- Polymorphic discriminator
    asset_kind VARCHAR(32) NOT NULL,              -- 'news_article' | 'regulation' | ...
    asset_id BIGINT,                              -- per-kind ID (no FK)
    metadata JSONB DEFAULT '{}'::jsonb            -- per-asset-kind facet
);

CREATE INDEX idx_asset_prov_kind_id ON asset_provenance(asset_kind, asset_id);
CREATE INDEX idx_asset_prov_valid ON asset_provenance(asset_kind, valid_until)
    WHERE invalidated_at IS NULL;
CREATE INDEX idx_asset_prov_activity ON asset_provenance(activity_id);

-- Layer 2 (per asset_kind): proper FK in dedicated link table
-- Example for news_article (created on-demand when first asset of that kind appears):
CREATE TABLE asset_provenance_news_article (
    provenance_id BIGINT PRIMARY KEY REFERENCES asset_provenance(id) ON DELETE CASCADE,
    article_id BIGINT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    UNIQUE (article_id, provenance_id)
);

-- Layer 3: prov:Activity (the cell pulse / scrape event that produced this)
CREATE TABLE provenance_activity (
    id UUID PRIMARY KEY,
    cell_name VARCHAR(64) NOT NULL,
    pulse_id VARCHAR(32),                         -- if produced by a cell pulse
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    activity_kind VARCHAR(32) NOT NULL,           -- 'scrape' | 'extract' | 'infer' | 'merge'
    metadata JSONB DEFAULT '{}'::jsonb
);
```

**Trade:** schema explosion (one Layer 2 table per asset_kind = 12 tables for our types) vs full FK integrity + queries that don't scan the whole `asset_provenance` table. **At our scale (~100K provenance rows estimated y1), per-asset-kind tables are cheap.**

**This is a non-trivial design change from `mata-garuda-cell-design.md`.** Documented here; needs separate review/decision before W2 code.

### Invalidation mechanisms

- **TTL (time-based):** `valid_until` column, daily sweeper.
- **Event-driven:** consume `cell:invalidate` topic per asset_kind; mark `invalidated_at`.
- **Manual:** human SQL UPDATE.
- **Hybrid:** all 3, prioritized by `invalidation_path` enum.

→ **Our pre-research design already had this.** Validated.

**Verdict for Stream 3:** **Major schema change** for `asset_provenance` (3-table layered + admiralty 2-axis). **Validates** invalidation design.

---

## Stream 4 — CRM Event-Driven OSS

### Twenty CRM (twentyhq/twenty)

- **Stack:** TypeScript, NestJS, PostgreSQL, **Redis + BullMQ for background workflows**.
- **Workflow triggers:** record events (created/updated/deleted), serverless functions for custom logic.
- **Pattern:** workflows defined declaratively in TypeScript SDK, run on BullMQ workers.

**Comparison to our design:**
- Our `EventBus` (PG_NOTIFY + outbox) ≈ Twenty's PostgreSQL trigger → BullMQ.
- Twenty has **explicit workflow versioning** (we don't). Each automation rule is a versioned record.

→ **Implication:** consider versioning automation rules in `crm-cell` (each rule = `crm_automation_rule` row with `version` + `enabled_at` + `disabled_at`). Today our automations are Python code (no versioning). **Defer to W2 — don't ship in W1.**

### EspoCRM / SuiteCRM — Workflow engines

- **EspoCRM:** signal trigger (object-broadcasted event) + condition-action rules.
- **SuiteCRM:** "Advanced Open Workflow (AOW)", trigger on field changes, condition matrix.

**Common pattern:** declarative rules stored in DB → workflow engine evaluates on triggers → dispatches actions.

→ **Implication:** our 13 CRM automations are **imperative Python** today. Migrating to a declarative rule engine is a Sprint 4+ scope; in Sprint 3 we just consolidate. **No design change.**

### Postgres LISTEN/NOTIFY at scale

**Production wisdom (event-driven.io, PgDog blog, EDB blog):**
- LISTEN/NOTIFY scales until **`max_connections` exhaustion** (each listener = 1 connection).
- No quantitative event/sec ceiling published, but anecdotal: ~10K notify/sec on a single connection works.
- **Workarounds at scale:**
  - PgDog proxy: multiplexes LISTEN across connections.
  - Hybrid: outbox for durability + LISTEN for low-latency wakeup.
  - **Logical replication (push-based outbox)** preferred over polling for >100 events/sec.

**Our scale:** ~150 events/day total (50 practice + 100 drive). **Three orders of magnitude below LISTEN/NOTIFY ceiling.** No change needed.

**Validates migration 146 outbox pattern:**
- `events_outbox` is the at-least-once durability layer.
- `pg_notify` is the low-latency wakeup.
- `_outbox_id` injection enables idempotent ack on replay.

→ **Our design matches event-driven.io's recommended pattern verbatim.** Validated.

### Saga / multi-step workflows

Temporal/Cadence used at Uber, Netflix. **Heavy infra** — overkill for our 5000-client CRM.

**Lighter pattern:** **practice_status_listener** (we have it) + **state machine in Postgres** (we have m087). Together = poor man's saga.

→ **No change needed.** Validates current design.

### Drive polling vs webhook

- **Drive push notifications (webhook):** Google Drive Activity API. **Not used in production CRM** at our scale because (a) webhook reliability requires public HTTPS endpoint with retry, (b) cold start of webhook can take 2-30s.
- **Polling (our pattern):** every 5min via cron, `page_token` in `system_settings`. **Robust, simple, scales to ~10M files.**

**Production failure mode (well-documented):** Drive webhook page_token loss on cold start = full re-scan = expensive.

→ **Our polling-only design is correct for Air's H24 server profile.** Validated.

### Circuit breakers

`pybreaker`, `resilience4j`. Pattern: 3 failures → OPEN → auto-recovery 5min. **We already have this** in drive_poll_service.

**Verdict for Stream 4:** CRM-cell design is **on-par with Twenty CRM** at our scale. Two refinements: (a) consider rule versioning Sprint 4+, (b) keep imperative Python in Sprint 3 W2.

---

## Stream 5 — OSINT Frameworks

### SpiderFoot (smicallef/spiderfoot)

- **Architecture:** event-driven, ~200 modules, each module declares `produces` and `consumes` event types.
- **Storage:** SQLite (via `SpiderFootDb` class) — schema details not in DeepWiki overview, would need source code read.
- **Correlation engine:** YAML-configured rules, runs **after scan completion** (batch, not streaming).
- **Confidence:** **NO explicit confidence scoring per module finding.** Risk levels (low/medium/high) are taxonomy tags.

→ **Implication for mata-garuda-cell:** SpiderFoot's "event types declared by modules" pattern matches our cell IPC design (each cell declares `produces`/`consumes` in `cell.yaml`). **Validated.** SpiderFoot's lack of confidence scoring is a gap we're closing.

### OpenCTI (OpenCTI-Platform/opencti)

- **Stack:** Elasticsearch (NOT Neo4j), GraphQL API, RabbitMQ for connectors, MinIO for files.
- **Data model:** STIX 2.1 native (SDO/SCO/SRO).
- **Provenance:** Reports are central — every piece of intel ties back to a Report (the source document).
- **Custom extensions:** Channels, Events, Narrative SDOs (for disinformation tracking).

→ **Implication for mata-garuda-cell:** "Tie every fact to a source Report" is **exactly** the asset_provenance pattern. STIX 2.1 SDO maps to our `asset_kind` enum. **Validates** the polymorphic-but-typed approach.

### MISP (misp-project/MISP)

- **Confidence:** admiralty 2-axis taxonomy (validated above).
- **Distribution:** TLP (white/green/amber/red/black) + sharing groups.
- **Event lifecycle:** publish → validate → expire (no automatic decay; manual review).

→ **Implication for mata-garuda-cell:** **Add `tlp` column to `asset_provenance`** for distribution control. Default `tlp:red` (Pro-only) per Symbiosis Law 2 (OSINT blindato). Override to `amber` only for skills/insights shareable via HGT.

### Lamarckian meta-agents in OSINT

**No published systems.** Mata-Garuda's meta-agent design (skills that improve OSINT tradecraft over time) is **frontier**.

The closest published analog: SpiderFoot module ordering optimization (community-driven, not automated).

→ **Implication:** publish a paper/blog about Mata-Garuda meta-agent design after y1 telemetry. **Not actionable for Sprint 3.**

**Verdict for Stream 5:** OSINT frameworks **validate** asset_provenance + admiralty 2-axis + TLP. **One concrete addition:** `tlp` column with default `red`.

---

## Cross-topic synthesis

### What the literature confirms

1. **PG NOTIFY + outbox** (migration 146) is industry best practice — keep verbatim.
2. **STIX 2.1 / admiralty taxonomy** is the OSINT standard — adopt 2-axis confidence.
3. **OpenLineage facets pattern** uses JSON-extensible blocks on a fixed core schema — **not 12 hardcoded link tables** as we initially read it. Multi-LLM review caught this. Implication for us: keep polymorphic `asset_kind + asset_id` AND add JSONB `metadata` column for per-kind facets (already in original schema line 137). No relational explosion.
4. **Devin's plan+PR checkpoint pattern** = our embrione (admission test) + adulto (autonomous) gates — well-aligned.
5. **Voyager skill library** validates SQLite+FTS5 at small scale — keep.
6. **ExpeL importance-count + prune-at-0** is missing from cell-core — add for `insight` type.

### What's frontier / original to our design

1. **5-phase lifecycle** with confidence-gated action — unique. Document as design-original.
2. **Homeostatic stress/energy/arousal** layer — research-frontier. Document as experimental.
3. **HGT via Redis Streams** — original combination of evolutionary biology + agent skill sharing.
4. **Lamarckian meta-agent** for OSINT — no published OSS analog.
5. **7d cooldown on rejected proposals** — operational pragma, no literature anchor.

### What we got wrong

1. **Single 6-band confidence (UNCONFIRMED→CONFIRMED)** — should be **2-axis admiralty** (reliability A-F + credibility 1-6) per OSINT industry standard. **M2 ships.**
2. **No `tlp` column on asset_provenance** — useful as a taxonomy label. **Ships in M2 — but documented as default-only, not DDL enforcement.** Real Symbiosis Law 2 enforcement remains at the cell adapter / network boundary.
3. **`asset_provenance` polymorphic FK** without per-asset-kind link tables — GitLab/Rails community warns this **when target tables exist as PG entities**. In our case, 8/12 asset_kinds live outside PG (Qdrant for KG, composite strings for crm_enrichment, etc.), so the warning doesn't apply. The 3-layer pivot was reviewed 2026-05-04 (multi-LLM: Opus 4.7, DeepSeek-Reasoner, Gemini 3 Pro Preview) and **rejected** as structurally infeasible. Keep polymorphic with documented "unverifiable FK" limitation + weekly orphan-GC cron.

---

## §6 — Concrete proposals

### crm-cell

#### Proposal C1: Keep current crm-cell-design.md, add migration 153 for crm_welcome_completed (already planned)

- **Pros:** matches Twenty CRM pattern at our scale, validates existing PG NOTIFY + outbox design, no architectural change.
- **Cons:** doesn't add automation rule versioning (Sprint 4+ scope).
- **Cost:** 0 additional engineering — this is Sprint 3 W2 as planned.

#### Proposal C2: Add automation rule registry table + version column

```sql
CREATE TABLE crm_automation_rule (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    rule_kind VARCHAR(32) NOT NULL,    -- 'practice_status_listener' | 'welcome_flow' | ...
    enabled BOOLEAN NOT NULL DEFAULT true,
    config JSONB NOT NULL,
    enabled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disabled_at TIMESTAMPTZ,
    UNIQUE (name, version)
);
```

Cell consults this table at startup; respawns sub-organelles on `enabled` change.

- **Pros:** matches Twenty CRM, gives Zero a Telegram-controllable pause/resume per rule.
- **Cons:** adds 1 migration + cell config sync logic (~150 LOC).
- **Cost:** +0.5 day in W2.

#### Proposal C3: Replace 13 imperative Python automations with EspoCRM-style declarative rules engine

- **Pros:** maintainable at 50+ rules, non-developer-friendly (Zero could add rules via UI).
- **Cons:** **rewrite all 13 automations**, ship a rule engine (mini interpreter), risk of regression.
- **Cost:** 5-7 days. Sprint 4+.
- **Recommendation:** **REJECT for Sprint 3.** Premature abstraction at 13 rules.

**Sprint 3 W2 picks: C1 (default) + optional C2 if time permits. C3 deferred.**

---

### mata-garuda-cell

#### Proposal M1: Pivot asset_provenance to 3-layer schema — **REJECTED 2026-05-04**

```sql
-- See §3 for full DDL (REJECTED — kept for reference only)
```

- **Pros (claimed):** FK integrity, OpenLineage-aligned, query-friendly (no full-table scan on asset_kind).
- **Cons (revealed by multi-LLM review):**
  - 8/12 asset_kinds have no PG table to FK against (KG=Qdrant, crm_enrichment=composite string Google Places, dossier/thesis/brief/ultra_move/measurer not yet PG-backed).
  - "OpenLineage-aligned" was inaccurate — OpenLineage uses JSON facets, not 12 hardcoded link tables.
  - "FK integrity" win is theoretical when half the link tables would point at nothing.
- **Verdict:** **REJECTED.** Keep original single-table polymorphic. Revisit per-kind link tables case-by-case when (and only when) target tables become PG-backed entities.

#### Proposal M2: Adopt MISP admiralty 2-axis confidence + TLP column

```sql
ALTER TABLE asset_provenance ADD COLUMN reliability CHAR(1) ...;
ALTER TABLE asset_provenance ADD COLUMN credibility SMALLINT ...;
ALTER TABLE asset_provenance ADD COLUMN tlp VARCHAR(8) NOT NULL DEFAULT 'red'
    CHECK (tlp IN ('white','green','amber','red','black'));
```

- **Pros:** OSINT industry standard, 36 ordinal levels vs 6, TLP enforces OSINT blindato in DDL.
- **Cons:** producers (cells emitting provenance rows) must learn admiralty mapping.
- **Cost:** ~0.5 day (mapping helper + tests).

#### Proposal M3: Defer Lamarckian meta-agent to y1+

- **Pros:** focuses Sprint 3 on getting the cell ALIVE first; meta-agent value emerges only with months of telemetry.
- **Cons:** bypasses original Mata-Garuda vision element.
- **Cost:** 0 (deferral).
- **Recommendation:** **ACCEPT.** Walking skeleton must walk before it learns.

**Sprint 3 W2 picks: ~~M1~~ + M2 + M3.** M1 rejected post-review (see above and mata-garuda-cell-design.md § "M1 — CONSIDERED AND REJECTED"). M2 (admiralty 2-axis + TLP) and M3 (defer Lamarckian meta-agent) ship.

---

## Open questions for Zero

1. **C2 (rule registry)** — deferred to Sprint 4+. **Reasoning corrected post-review (Gemini X4)**: not "premature abstraction at 13 rules" but "internal-only automations belong in code/git forever; Twenty CRM's DB registry exists because it's multi-tenant SaaS where end-users author workflows. Nuzantara is internal — never add a registry for hard-coded automations."
2. **~~M1~~ (3-layer asset_provenance)** — **REJECTED 2026-05-04** post multi-LLM review. 8/12 asset_kinds lack PG target tables. Keep polymorphic.
3. **M2 (admiralty 2-axis + TLP)** — **YES, ships.** Cheap, OSINT-standard. Note: TLP `red` default is a *safe default*, NOT DDL-level enforcement (any client can override).
4. **Voyager skill versioning (`{name}V{i}` on duplicate)** — adopt for cell-core genome? Currently we silence/decay; Voyager pattern preserves history. (default: no, our `decay_unused_skills` is cleaner)
5. **ExpeL importance-count for insights** — fact-checked against arXiv:2308.10144 v3: mechanism IS in the paper (ADD initial=2, UPVOTE/EDIT +1, DOWNVOTE -1, prune at 0). Citation accurate. Defer to Sprint 4+ as a separate cell-core-wide brainstorm.

---

## Sources

- **Voyager:** [arXiv:2305.16291](https://arxiv.org/abs/2305.16291), [github.com/MineDojo/Voyager](https://github.com/MineDojo/Voyager), `voyager/agents/skill.py`
- **ExpeL:** [arXiv:2308.10144](https://arxiv.org/abs/2308.10144), [github.com/LeapLabTHU/ExpeL](https://github.com/LeapLabTHU/ExpeL)
- **Reflexion:** [arXiv:2303.11366](https://arxiv.org/abs/2303.11366), [github.com/noahshinn/reflexion](https://github.com/noahshinn/reflexion)
- **AutoGen skill library issue:** [microsoft/autogen#98](https://github.com/microsoft/autogen/issues/98) (closed, not planned)
- **Devin / Cognition Labs:** [WWT case study](https://www.wwt.com/blog/empowering-the-enterprise-a-strategic-view-of-devin-ai-and-the-autonomous-workforce), [SitePoint](https://www.sitepoint.com/devin-ai-engineers-production-realities/)
- **MLflow + PROV-O:** [Ranjan Kumar blog Part 4](https://ranjankumar.in/provenance-in-ai-auto-capturing-provenance-with-mlflow-and-w3c-prov-o-in-pytorch-pipelines-part-4)
- **OpenLineage:** [openlineage.io](https://openlineage.io/), [github.com/OpenLineage/OpenLineage](https://github.com/OpenLineage/OpenLineage)
- **PG LISTEN/NOTIFY scaling:** [event-driven.io push-based outbox](https://event-driven.io/en/push_based_outbox_pattern_with_postgres_logical_replication/), [pgdog.dev](https://pgdog.dev/blog/scaling-postgres-listen-notify), [EDB blog](https://www.enterprisedb.com/blog/listening-postgres-how-listen-and-notify-syntax-promote-high-availability-application-layer)
- **Twenty CRM:** [github.com/twentyhq/twenty](https://github.com/twentyhq/twenty), [docs.twenty.com workflows](https://docs.twenty.com/user-guide/workflows/overview)
- **EspoCRM workflows:** [docs.espocrm.com](https://docs.espocrm.com/administration/workflows/)
- **SuiteCRM workflows:** [docs.suitecrm.com](https://docs.suitecrm.com/user/advanced-modules/workflow/)
- **SpiderFoot:** [github.com/smicallef/spiderfoot](https://github.com/smicallef/spiderfoot), [DeepWiki](https://deepwiki.com/smicallef/spiderfoot)
- **OpenCTI:** [github.com/OpenCTI-Platform/opencti](https://github.com/OpenCTI-Platform/opencti), [docs.opencti.io data-model](https://docs.opencti.io/latest/usage/data-model/)
- **MISP taxonomies:** [misp-project.org/taxonomies](https://www.misp-project.org/taxonomies.html)
- **Polymorphic FK tradeoffs:** [GitLab docs](https://docs.gitlab.com/ee/development/database/polymorphic_associations.html), [Hashrocket blog](https://hashrocket.com/blog/posts/modeling-polymorphic-associations-in-a-relational-database)
- **ACT-R / SOAR:** [arXiv:2205.03854](https://arxiv.org/pdf/2205.03854), [arXiv:2201.09305](https://arxiv.org/abs/2201.09305)
