---
date: 2026-08-26
domain: operations
adversarial_review: kimi-k3
---

# Contract map — Intel Lake + MATA GARUDA topology, mapped onto the P04 frozen contract

All file paths are relative to repo root. All line numbers were read in this session on the
`agent/nuzantara/intel/ros-v1-p05-intel-prep-b01` worktree, HEAD `b27b46a13` (`git log --oneline
-1` at session start). Re-measure before relying on a line number after any commit lands.

## 1. Intel Lake — the live canonicalization pipeline

### 1.1 Code

| File | Role | Lines |
|---|---|---|
| `apps/backend-rag/backend/services/intel/intel_lake_service.py` | UPSERT logic: `record_observation()` writes one `intel_items` row (canonical, upsert-on-conflict) + one `intel_observations` row (append-only) per call. `canonicalize_url()` strips fragments/UTM params. | 260 |
| `apps/backend-rag/backend/services/intel/intel_lake_router.py` | Tier-1 regex/keyword routing (`route_event`), `backfill_unrouted`, `backfill_needs_review`. **No Tier-2 function exists** — see §1.4. | 549 |
| `apps/backend-rag/backend/app/routers/intel_lake.py` | FastAPI routes: `POST /api/intel/lake/observations` (single) and `POST /api/intel/lake/observations-batch`. Auth: static `X-Producer-Token` header matched against `INTEL_LAKE_PRODUCER_TOKEN` env, fail-closed if unset. | 221 |
| `apps/backend-rag/backend/services/intel/dossier_compiler.py` + `dossier_models.py` + `dossier_repository.py` + `dossier_slug.py` | A **separate** pipeline: `TrendSignal` → `ResearchDossier` compilation via Claude CLI, with its own naive clustering (`DEFAULT_CLUSTER_SIMILARITY = 3` shared keywords — dossier_compiler.py). Not Intel Lake; not MATA GARUDA. A third, independent "story-adjacent" concept already in the repo (see §5). |
| `apps/backend-rag/backend/services/intel/trend_hunter/` | Yet another adapter set (`GoogleTrendsAdapter`, `RedditAdapter`, `RSSAdapter`, `XAIAdapter`) feeding the dossier pipeline via `trend_signals` table + `pg_notify`, not Intel Lake's `intel_items`. |
| `apps/backend-rag/backend/services/mata_garuda/cell_adapter.py` | The **one** sanctioned entry point from backend-rag into MATA GARUDA's Postgres schema (`asset_provenance`, migrations 154/155). 12 canonical `asset_kind` values (`ASSET_KIND_AUTHORITATIVE`), NATO-Admiralty `reliability`/`credibility` axes, `tlp` (white/green/amber/red/black). Lives here (not in `apps/mata-garuda/`) because `apps/mata-garuda`'s own `CLAUDE.md` forbids `asyncpg` as a runtime dependency (minimal-stack rule: only `pydantic>=2`). |

### 1.2 Schema (migration `168_intel_lake_schema.sql`, additive, has rollback)

```
intel_items            -- canonical, UNIQUE(canonical_url), UPSERT touches only last_seen_at
  id UUID PK · canonical_url TEXT UNIQUE · content_hash TEXT · title/summary TEXT
  source_domain · language · jurisdiction · topic_tags TEXT[]
  routing_status TEXT CHECK IN ('unrouted','blog','wr2','nb-intel','archive','skip','needs_review')
  routing_targets JSONB · confidence_score REAL
  first_seen_at / last_seen_at / published_at / expires_at TIMESTAMPTZ
  raw_payload JSONB

intel_observations      -- append-only, no UNIQUE, one row per producer-hit on the same URL
  id BIGINT PK · item_id UUID FK->intel_items ON DELETE CASCADE
  producer_name TEXT · observed_at TIMESTAMPTZ · raw_payload JSONB · score REAL

intel_lake_audit_log     -- auth/audit trail per POST
  producer_name · client_ip · request_path · status_code · payload_size · error_message

Trigger: AFTER INSERT ON intel_items -> notify_intel_lake_event() -> events_outbox
  (channel 'intel_lake_event', migration-146 outbox pattern). INSERT-only; UPDATE
  (last_seen_at refresh) does not fire.
```

Later migrations touching this schema. **CORRECTED 2026-08-26 (adversarial review):** the
pattern below is a LITERAL-STRING search and therefore cannot match a migration that touches
this schema by TABLE name. At least one such file exists and is absent from the list —
`205_cockpit_intents.sql`, which references `intel_items` (comment-only, so the conclusion
happens to survive; the METHOD does not). The list below is a lower bound, not the footprint.
A second inconsistency in the same sentence: `171` is listed as found "via" this pattern, but
re-running the pattern this session returns `168, 174, 175, 187, 192` — not 171. Original
pattern, kept verbatim so the gap is reproducible: `grep -rl "intel_lake\|IntelLake"
apps/backend-rag/backend/db/migrations_v2/`:
`171_intel_item_nb_pushes.sql` (junction table for NB pushes — §3), `174` and `192`
(`*_jsonb_double_encoding_repair.sql` — two separate double-encoding incidents, one on
`intel_lake`, one on the bridge outbox; both are repair migrations for a bug class the
`intel_lake_service.py:155-160` comment documents was already hit once and fixed at the
call site), `187_probe_sandbox_isolation.sql` (test-isolation, not schema), `175` (name
contains `intel_lake`-adjacent string `wa_mirror`, false-positive grep hit — read and
confirmed unrelated to Intel Lake).

**Dedup mechanism today**: Postgres `UNIQUE(canonical_url)` constraint only. No
content-hash-based near-duplicate detection, no cross-URL clustering, no translation/syndication
awareness. `is_content_drift` (service layer) detects "same URL, different `content_hash`" and
only **logs** a warning — it does not create a new canonical version, contrary to the module
docstring's stated invariant ("Content drift → INSERT new row"); the actual `ON CONFLICT DO
UPDATE` only touches `last_seen_at`. **This is a live discrepancy between the file's own
docstring and its own SQL** — flagged, not fixed (out of this lane's mandate; see UNKNOWNS.md).

### 1.3 Producers (found via grep for the two live-cron consumers of the API — note the
heading says "consumers" because the grep TARGET was the consumers; the section lists producers)

- Pro-local cron `scripts/intel-lake-outbox-drain/` (LaunchAgent
  `com.balizero.intel-lake.outbox-drain.minute`, 60s) — drains a local SQLite outbox
  (`~/.intel-lake-outbox.db`) and POSTs batches to
  `/api/intel/lake/observations-batch`. Producer identity is whatever wrote to that SQLite
  file — **not enumerated by this bundle** (would require reading producer-side cron
  registrations across `~/scripts/`, out of this lane's read scope on a first pass; flagged in
  UNKNOWNS.md as the one piece of "producer registry" deliverable #1 could not close from the
  monorepo alone).
- The router-a2 and nb-pusher-a2 scripts (§1.4/§3) are consumers, not producers.
- Migration `168`'s own comment: "Wave 1 producer: `intel_radar` (existing PG
  `intel_radar_findings` from mig 139)" — i.e. `intel_radar.py` (Pro-local cron, referenced by
  `apps/mata-garuda/scripts/*` and migration `156`'s docstring: "Pro-local `intel_radar.py`
  cron call this function") is a MATA-GARUDA-adjacent producer that predates Intel Lake and
  feeds `asset_provenance` via `mata_garuda.tag_intel_finding()`, a **separate** write path from
  Intel Lake's own `record_observation()`. Confirms the packet's "12+ producers" framing refers
  to a superset larger than what lives in this monorepo checkout.

### 1.4 Tier-1/Tier-2 routing — confirms the packet's "no working Tier-2" claim

`intel_lake_router.py:12` docstring: `"needs_review: NO rule matched → Tier 2 LLM (weekly)"`.
Functions in the file. **CORRECTED after a cross-family adversarial review (Kimi K3,
2026-08-26):** the pattern this bundle originally ran, `grep -n "async def \|^def "`, is
anchored at column 0 for the sync case, so it is blind to INDENTED sync methods by
construction. It returned seven names — `_build_press_pattern`, `_compile_keyword_pattern`,
`_press_content_gate`, `route_event`, `backfill_unrouted`, `backfill_needs_review`,
`register_intel_lake_router_handlers` — and MISSED two: `def __init__` (line 267) and
`def _classify` (line 387), both indented inside `class IntelLakeRouter`. `_classify` is the
actual rules engine. Re-read directly this session: neither of the two missed methods calls an
LLM either, so the substantive conclusion survives — but it survives on a re-read, NOT on the
enumeration, and a sync LLM helper would have escaped the original pattern unseen.
`backfill_needs_review` (line 458) re-applies the same Tier-1 regex rules to the `needs_review`
pool — it is a retry of Tier 1, not an implementation of Tier 2. The packet's Live Baseline
claim ("no working Tier-2 enrichment path") is confirmed by reading all nine functions,
including the two the first pattern missed. Do not cite it as "confirmed by complete
enumeration": the enumeration was incomplete and was repaired by hand.

There is also a **second**, Pro-local implementation of Tier-1 routing:
`scripts/intel-lake-router-a2/intel-lake-router-cron-standalone.py`, whose own docstring states
it exists because "the Fly router code exists at `intel_lake_router.py` but its EventBus
subscriber never fires" (kill-switch `DISABLE_BACKGROUND_WORKERS=1` from an unrelated 2026-04-12
disk-full incident, "never removed" per the same docstring). **Two independent Tier-1
implementations of the same regex rules exist, one dormant (Fly, EventBus-gated) and one live
(Pro cron, 5-min interval)** — itself a duplicate-truth-path the packet's mission statement
("removing parallel truth paths") should register as in-scope.

## 2. MATA GARUDA — the OSINT organism

### 2.1 Two runtimes, one name

- `apps/mata-garuda/` — the actual Python package (`mata_garuda/`), Pro-local only, minimal-stack
  (`pydantic>=2` runtime, no `asyncpg`), Redis-stream-native, `CLAUDE.md`-governed by its own
  stricter rules (§4). Dozens of `scripts/run_*.py` runners, each LaunchAgent-invoked, each
  calling a `mata_garuda.agents.*`/`mata_garuda.workers.*` function and emitting a heartbeat via
  `mata_garuda.workers.heartbeat` (superscar family #2 antidote — every runner here already
  writes the heartbeat sidecar).
- `apps/backend-rag/backend/services/mata_garuda/cell_adapter.py` — the one place MATA GARUDA
  data is readable/writable from the monorepo's own asyncpg pool (§1.1 above).

### 2.2 The bridge: `apps/mata-garuda/mata_garuda/bridge/nerve.py` (Redis Stream `bridge:outbound`)

`push_once()` (line 519) reads a consumer-group batch, looks up `env.type` in a **fixed
two-entry dict** (line 398):

```python
PUSH_ROUTING: dict[str, str] = {
    "intel.article_ready": "/api/bridge/ingest/article",
    "enrichment.kb_entry": "/api/bridge/ingest/enrichment",
}
```

If `env.type` is not one of those two keys, line 557-566:

```python
endpoint_path = PUSH_ROUTING.get(env.type)
if endpoint_path is None:
    logger.warning("Unknown push type %s (msg_id=%s) — ACKing to avoid loop", env.type, msg_id)
    redis_xack(STREAM_BRIDGE_OUTBOUND, PUSH_CONSUMER_GROUP, msg_id)
    stats["acked"] += 1
    stats["errors"] += 1
    continue
```

The message is **ACKed** (permanently removed from the consumer group's pending list — Redis
Streams never redeliver an ACKed entry) and counted as `errors`, but there is no dead-letter
stream, no persisted record of what was dropped beyond a log line, and no alerting keyed to this
specific counter (confirmed: `stats` is the function's return value, consumed by whatever caller
prints it — no distinct alert path grepped in this file).

### 2.3 The producer that trips this: `apps/mata-garuda/mata_garuda/agents/wr2_bridge_publisher.py`

Module docstring (lines 1-14): converts enriched stream items for 3 domains
(`immigration_visa`, `tax_fiscal`, `investment_licensing`) into `WR2 research_dossiers`-compatible
envelopes and publishes to `bridge:outbound`. `WR2_ENVELOPE_TYPE = "intel.research_dossier"`
(line 36 — an earlier revision of this bundle said 34; re-measured 2026-08-26).
**`"intel.research_dossier"` is not a key in `PUSH_ROUTING`.**

**This is the packet's Live Baseline claim — "a broken WR2 research-dossier bridge whose
consumer acknowledges unsupported message types" — confirmed by direct cross-file read, not
inferred from the packet's own prose.** Every `intel.research_dossier` envelope
`wr2_bridge_publisher.py` has ever produced has been silently ACKed-and-dropped by `nerve.py`,
with no replay path, since the producer was written. This is exactly the shape of packet
deliverable #5 ("Consumer contract that dead-letters unsupported types; unknown messages are
never ACKed as success").

The sibling worker `apps/mata-garuda/mata_garuda/workers/gap_consumer.py:194-217`
(`process_gap`) has the **identical anti-pattern** on a different stream
(`STREAM_NEXUS_GAPS`): unknown `gap_type` → log warning → `xack()` → return `{"status":
"unknown"}`. Two independent consumers share one defect shape — the fix (dead-letter instead of
ACK-drop) is a single reusable pattern, not two separate ones.

## 3. The duplicated NotebookLM feed (packet's other named Live-Baseline defect)

Two independent, code-confirmed paths write to NotebookLM:

1. **MATA GARUDA's own feeder**: `apps/mata-garuda/scripts/run_nlm_feeder_stream.py`, consuming
   Redis `garuda:alerts` (primary) + `garuda:enriched` (raw, filtered via `_SOURCE_TO_DOMAIN`),
   routing to the 5 domain-matched NB-INTEL notebooks. Its own docstring: "Counterpart to
   `run_sentinel_py.py` (which feeds only NB-INTEL-AIResearch via legacy KB-scan mode)" — i.e. a
   **third** related-but-distinct feeder (`run_sentinel_py.py`) also exists, narrower-scoped.
2. **Intel Lake's own pusher**: `scripts/intel-lake-nb-pusher-a2/intel-lake-nb-pusher-standalone.py`.
   Its own docstring states the reason for its existence verbatim: *"mata-garuda's nlm_feeder
   reads from Redis `garuda:enriched` (a parallel pipeline) and feeds its own NB-INTEL UUIDs.
   Intel Lake routing is currently inert. This script closes the loop."* Uses a junction table
   `intel_item_nb_pushes(item_id, nb_uuid, content_hash, status, ...)` (migration `171`,
   confirmed present on disk) for per-target tracking, "at-least-once (NOT exactly-once)"
   delivery per its own docstring (NLM CLI has no `--source-id` flag).

Both feeders are live, unrelated code paths, writing to the same class of destination
(NB-INTEL notebooks) with no shared dedup key between them. This is deliverable #6's target:
"Exactly one canonical NotebookLM feed... the old parallel feed remains shadowed until Packet
16." Packet 05 does **not** get to retire either feed (explicit non-goal: "Do not retire old
producers/feeds yet"); Packet 05's job is to introduce the canonical third path *alongside*
these two, shadowed, per the packet's own rollback section.

## 4. MATA GARUDA's OSINT boundary (governs everything in §5's Cohort-B mapping)

`apps/mata-garuda/CLAUDE.md` §"OSINT blindato (one-way IN)" (read directly this session):
data flows `cloud → Mata Garuda (IN)` then only to `Mata Garuda → Nuzantara (business)` or
`Mata Garuda → Zero TG (OUT)`; explicit ban list includes `apps/mouth/`, any frontend, clients,
Bali Zero team, any cloud (Fly.io/Vercel/GCP/AWS), public repos/gists/pastebin. §1.4's named
exception (Zero-authorized 2026-05-06): the local KG SQLite (`~/.agent/mata-garuda/kg.db`) may
expose **metadata only** — `name, type, source_count, last_seen, neighbor_names,
observation_count, observation.source_url` (always a public URL) — to local Pro organs via
Tailscale loopback. Explicitly **forbidden** in that same payload: `observation.value` (may
contain raw title/snippet OSINT), any content field, full article text.

This is the ceiling for what Packet 05's `IntelEvent.payload_ref` may ever carry for a MATA
GARUDA-sourced event when `classification.sensitivity` is `restricted_osint`: a durable
`https://`/`s3://` reference (per §5.2's `DurablePayloadReference` pattern), never an inline
payload, and never routed to a destination this CLAUDE.md's ban list names.

## 5. Mapping onto the P04 frozen contract (`packages/research-os-core/research_os/models/`)

25 model files exist (confirmed: `find packages/research-os-core/research_os/models -iname
"*.py" | wc -l` → 26 including `__init__.py`). The two Cohort-B-relevant kinds, read in full
this session:

### 5.1 `IntelEvent` (`models/intel_event.py`, 305 lines)

| Frozen field | Intel Lake today | Gap |
|---|---|---|
| `event_id: UUID` | `intel_items.id UUID` exists, but is per-**canonical-item**, not per-**observation** — an `IntelEvent` is closer to one `intel_observations` row than to one `intel_items` row | new UUID needed per observation, not reuse of `intel_items.id` |
| `contract_version: Literal["research-os/v1.0.0"]` | absent | new column/field |
| `tenant: Literal["bali-zero"]` | absent | new column/field, though trivially constant today |
| `event_type: RegisteredName` (namespaced string) | `routing_status` is the closest concept but is a *downstream* classification (post-routing), not the event's own type | needs a producer-declared type distinct from routing outcome |
| `producer.{name,version,machine_class}` | `intel_observations.producer_name TEXT` only — no version, no machine_class | schema extension |
| `source.{uri,native_id,canonical_url,source_type,jurisdiction}` | `intel_items.canonical_url`, `jurisdiction` exist; `uri` (pre-canonicalization), `native_id`, `source_type` absent | partial |
| `times.{published_at,observed_at,ingested_at}` | `published_at` exists on `intel_items`; `intel_observations.observed_at` exists; no `ingested_at` distinct from `observed_at` | partial |
| `identity.{content_hash,normalized_hash,idempotency_key}` | `content_hash` exists (on `intel_items`, not per-observation); no `normalized_hash`; **no `idempotency_key` at all** — today's only idempotency is the DB `UNIQUE(canonical_url)` constraint, which is a coarser, URL-only key | this is the packet's deliverable #1's "stable idempotency keys" requirement — does not exist today in any form finer than "same URL" |
| `classification.{language,domain,risk_class,sensitivity,rights}` | `language`, partial `topic_tags` (not `domain`) exist; **`risk_class` and `sensitivity` do not exist anywhere in the Intel Lake schema** | this is the biggest single gap — Intel Lake has no sensitivity boundary in its own schema today; the classification described in §4 (OSINT-blindato) is enforced entirely *outside* Intel Lake, in MATA GARUDA's own code and org boundary, not in the shared table |
| `lineage.{pipeline_run_id,input_event_refs,parser_version,model_version,prompt_version}` | absent entirely | this is deliverable #1's "lineage" requirement and packet metric "100% producer/run/artifact lineage for the canary window" — currently 0% by construction, nothing tracks a run id |
| `payload_ref` (discriminated: durable reference vs. inline-public, with content-hash verification on the inline arm) | `raw_payload JSONB` inline always, uncapped by classification (50KB size cap only) | no reference-storage arm exists at all; every payload today is "inline," which the frozen contract only permits when `sensitivity=public` — Intel Lake cannot express "internal"/"confidential"/"restricted_osint"/"client_pii" today, so it cannot express the constraint it would need to obey |
| `object_hash` (RFC 8785 canonical + sha256, self-verifying) | absent | new, and Intel Lake has no existing canonicalization/hashing utility of its own — would need to import `research_os.hashing`. **⚠️ D7 DEPENDENCY, flagged 2026-08-26:** `apps/mata-garuda` cannot import it — its own `CLAUDE.md` caps runtime deps at `pydantic>=2`. So any MATA-side `object_hash`, or the hash reconciliation in IMPLEMENTATION-SCOPE.md §5 step 6, needs the SAME RFC 8785+sha256 digest computed identically in TWO independent implementations — which is deliverable **D7 (deterministic cross-implementation hashing)**, a primitive `contract-pass-001.md` §7 forbids Cohort B from relying on. Do not design that reconciliation until D7 lands. |

### 5.2 `StoryCluster` (`models/story_cluster.py`, 229 lines)

No equivalent exists in Intel Lake at all — confirmed by schema read (§1.2): the only grouping
mechanism today is the `UNIQUE(canonical_url)` constraint, which is exact-URL dedup, not
clustering. Concepts `StoryCluster` requires that have zero analogue today:
`independent_source_groups` (distinct-source corroboration, explicitly excluding syndicated
members — see the model's own "without mistaking syndication for corroboration" purpose
clause), `decision.layers_run` (ordered exact→normalized→near→semantic→human pipeline, with a
validator enforcing deterministic layers never run *after* a semantic/model layer),
`predecessor_refs` (merge/split/canonical_change history), `revision` numbering.

The **closest existing artifact** is `dossier_compiler.py`'s `DEFAULT_CLUSTER_SIMILARITY = 3`
(shared-keyword count) clustering of `TrendSignal` rows into `ResearchDossier` groups — a naive,
un-labeled, un-benchmarked heuristic operating on an entirely different table
(`trend_signals`/dossier tables, not `intel_items`). It is evidence that *some* clustering
appetite already exists in the codebase, but it is not a candidate incumbent: it has no golden
set, no precision/recall measurement, and no story-history/revision concept — it would need to
be evaluated on equal footing with any other layer the packet's `MetricProfile` proposes, not
promoted by default (see METRICS-AND-GOLDEN-SET.md §3).

### 5.3 `research_os_objects` persistence substrate

Per `contract-pass-001.md` §7 (re-read this session, not paraphrased): the migration for this
table is additive, has a real rollback, and its apply→rollback→re-apply cycle passed against a
throwaway database — but it **is applied in no environment**, confirmed absent from all 89 local
databases censused **by that prior session, and NOT re-measured here** — this bundle had no
live-DB access at all (UNKNOWNS.md §1), so "89" is a carried-over count, not a confirmation.
It is quoted for provenance only and contradicts this bundle's own "no live counts anywhere"
rule if read as current. `apps/backend-rag/backend/services/research_os/` (8 files:
`__init__.py`, `_core_path.py`, `action_intent_adapter.py`, `action_item_adapter.py`,
`legacy_magazine.py`, `loss_report.py`, `operational_receipt_adapter.py`,
`synthesis.py` — confirmed by directory listing this session) has adapters for
`ActionIntent`/`ActionItem`/`OperationalReceipt` — **none for `IntelEvent` or `StoryCluster`**.
**CORRECTED 2026-08-26:** an earlier revision asserted that no file in `apps/backend-rag`
imports `research_os.models.intel_event` or `research_os.models.story_cluster`. That is FALSE —
`apps/backend-rag/backend/tests/unit/research_os/test_models_and_fixtures.py:11,13` imports
both. The substantive point stands (the importer is a TEST; no adapter exists), but the
sentence as written was a claim the bundle had not run the search to support (it was hedged as an
open verification in UNKNOWNS.md, but no adapter file exists to import them from regardless).


## Adversarial review

**Seat:** Kimi K3 (`kimi -m kimi-code/k3`), cross-family — neither the model that wrote this
bundle nor the session that gated it. Run 2026-08-26 against a FROZEN diff (head `2807f50e9`):
the generator was dead before the refuter was dispatched, so nothing moved under it.

**Verdict: DEFECTIVE on method, sound on its two headline findings.** The bridge ACK-drop and the
`intel_lake_service.py` docstring-vs-SQL drift both check out on independent re-read. The
systematic defect is a *class*: single-search results stated with more precision than the search
supports. Every finding below was re-verified against disk by the gating session before it was
accepted — the refuter is not trusted either (superscar #6).

| # | Finding | Verified | Disposition |
|---|---|---|---|
| 1 | D7 dependency unflagged: `object_hash` + MATA-side hash reconciliation need the same digest in two implementations, but `apps/mata-garuda` caps deps at `pydantic>=2` | TRUE (`grep D7` → 0 hits in bundle) | **FIXED** — §5.1 now flags it as a §7-forbidden primitive; do not design that reconciliation until D7 lands |
| 2 | "Enumerated every function" used `^def ` — blind to indented sync methods; missed `__init__` (267) and `_classify` (387), the actual rules engine | TRUE | **FIXED** — §1.4 restated; conclusion survives on a re-read, not on the enumeration |
| 3 | "7 files" while listing 8 names in the same sentence | TRUE (`ls` → 8) | **FIXED** |
| 4 | Migration list from a literal-string grep, misses `205_cockpit_intents.sql` (`intel_items`); and `171` is listed as found by a pattern that does not return it | TRUE | **FIXED** — list relabelled a lower bound, both gaps named |
| 5 | Line counts off: 306→305, 230→229, `WR2_ENVELOPE_TYPE` line 34→36 | TRUE | **FIXED** — re-measured |
| 6 | "No file in `apps/backend-rag` imports `intel_event`/`story_cluster`" — false, a test file imports both | TRUE (hedged in-sentence and in UNKNOWNS §2) | **FIXED** — restated; substantive point (importer is a test, no adapter) stands |
| 7 | "89 local databases" is a count carried from a prior session, contradicting this bundle's own "no live counts anywhere" | TRUE | **FIXED** — marked carried-over, not a confirmation |
| 8 | §3.4 arithmetic defeats itself: needs >100, sets the two safety-critical strata to exactly 100; 1/100 = 1.00%, not < 1% | TRUE | **FIXED** — >=101 required, 810 total moves |
| 9 | README cites §3 (NotebookLM feed) for the ACK-drop finding, which lives in §2.2/§2.3 | TRUE | **FIXED** |
| 10 | UNKNOWNS §2 "two producer entrypoints" vs §1.3, which says `intel_radar` writes by a SEPARATE path | PARTIAL | **FIXED** — wording corrected, overstatement removed |
| 11 | "Every dossier envelope has been ACKed-and-dropped since the producer was written" is a live-traffic history claim provable only from code paths | TRUE (overreach) | **ACCEPTED AS LIMIT** — the drop PATH is proven by direct read; whether the producer ever ran with traffic is unknowable without the live stream this bundle could not reach (UNKNOWNS §1) |

**Not a finding** (refuter checked, found sound): migration numbering — head 287, 282 absent,
`272_wa_broker_package_text.sql` WhatsApp-broker-owned; the bundle correctly refuses to bind an
integer. Readiness claims — disclaimed consistently across README and UNKNOWNS §5.
