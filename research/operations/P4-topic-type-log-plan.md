---
date: 2026-06-05
domain: operations
subject: wr2-P4-topic-type-log
status: PLAN — for 4-LLM review then autonomous implementation to merge
author: orchestrator (Opus 4.8) + Explore recon + direct re-verification
sources:
  - research/operations/2026-06-04-wr2-autopsy-report.md (P-4 prescription)
  - research/operations/W66-wr2-autopsy-deferred-spec.md (deferred-items spec)
  - direct Pro recon 2026-06-05 (publish point, schema, migration runner)
---

# P-4 — Persist `topic_type_log` to make anti-sameness (Art 10.6) enforceable

## REV 2 (2026-06-05) — 4-LLM panel applied (DeepSeek NO-GO→conditional, Codex GO-WITH-CHANGES; Gemini unavailable: OAuth logout on Pro, panel ran 2-deep)

The panel found the feature was **DOA as first drafted**. Changes folded into the
sections below; summary of what the panel forced:

1. **CRITICAL — `image_mode` does not exist in the producer.** `wr2_draft_generator.py`
   SYSTEM_INSTRUCTIONS per-slide schema has NO `image_mode`/`image_style_mode`, and
   `_normalise_slides` (whitelist ~line 710) would STRIP it even if present. So
   `dominant_mode` would be "unknown" 100% of the time and Art 10.6's mode axis is
   inoperative. **NEW GATING PREREQUISITE (§3.0): add `image_mode` to the prompt schema
   + whitelist + tests FIRST**, else this whole table is garbage-in. Verified by both
   DeepSeek and Codex against source.
2. **HIGH — collision rule "differ in BOTH" + mode-always-unknown → dead letter.**
   Changed §3.5 to **"differ in EITHER register OR image-mode"** (looser, matches Art
   10.6 intent for meaningful variety, avoids livelock on the narrow 7-register space
   where "analitico" dominates visa/tax).
3. **HIGH — writing at `rendered` logs Damar-rejected carousels too.** Added
   `published_at` + `deleted_at` nullable columns to the DDL NOW (§3.1) so switching to
   published-semantics later is a 1-line query change, not a new migration. v1 lookup
   reads `rendered_at` with a documented TODO.
4. **MEDIUM — "unknown" domain bucket cross-constrains unrelated topics.** §3.5 now
   **exempts domain="unknown" from the hard-reject** (soft-steer only).
5. **Codex — transaction premise was wrong.** `_persist_result` is a bare `conn.execute`
   (no transaction) called from TWO sites (headless ~420 + desktop ~547). §3.3 rewritten:
   best-effort write AFTER the status update, in a savepoint (`conn.transaction()`), applied
   to BOTH call sites — or folded into `_persist_result` itself (preferred, single site).
6. **Codex — rollback needs the literal marker.** §3.1 uses `-- === ROLLBACK ===` with
   executable `DROP INDEX`/`DROP TABLE` (the runner `migration_base.py:35,461` splits on
   that exact marker), not a comment.

## 0. CRITICAL CORRECTIONS to the autopsy (verified on Pro 2026-06-05)

The autopsy made TWO claims that direct re-verification proved FALSE. The plan
is built on the verified reality, not the autopsy text:

1. **The autopsy hallucinated `_state-schema.sql:63` and `_voyager-curriculum.py:49`
   with precise line numbers.** `find` → 0 results for both. `topic_type_log` is
   mentioned NOWHERE in the codebase except the autopsy report itself. There is
   no SQLite table, no LEFT JOIN, no Voyager curriculum reader. We are building
   from zero, not "making an existing aspirational table real."

2. **There is NO software "publish to Instagram" event.** Pipeline A's
   `wr2_carousel_orchestrator.py:900` (`transition_state → published`) that the
   Explore agent flagged is DEAD CODE — its dispatcher (`carousel-dispatcher`)
   AND its Telegram gate (`telegram-gate`) are BOTH crash-looping (launchctl
   exit 75, verified). Pipeline B (the one that ships) has NO instagram/graph
   call (grep → 0) — correct per Legge 5 (never auto-publish). The terminal
   software status in Pipeline B is **`rendered`** (`wr2_canva_desktop_apply.py:188`
   sets `status='rendered'`; supervisor map line 98 `("*","rendered"): None #
   Telegram only`). Damar publishes MANUALLY from the Canva design.

**Consequence:** `topic_type_log` must be written at the **`rendered`** transition
(the real terminal event), NOT at a non-existent publish event. This is correct
on the merits: anti-monotony must prevent repetition in what we *produce*, and
"rendered" = produced + sent to human review. (If a real publish signal is built
later — e.g. Damar confirms in Telegram — we add a `published_at` update then.)

## 1. Goal

Create a Postgres `topic_type_log` table, write one row when a carousel reaches
`status='rendered'` (domain + dominant register + dominant image-mode +
layout_family + draft_id + timestamp), expose a "last-2-in-this-domain" lookup,
and feed it into the draft generator so Art 10.6 (same-domain 14-day window must
differ in register AND image-mode) becomes enforceable instead of aspirational.

## 2. Verified ground truth (Pro 2026-06-05)

- **Migrations:** `apps/backend-rag/backend/db/migrations_v2/NNN_slug.sql`, runner
  `migration_manager.py`, tracking table **`_schema_versions`** (NOT
  schema_migrations — verified migration_manager.py:144-180), uniqueness asserted
  at discovery. **Highest existing number = 205 → P-4 = `206_wr2_topic_type_log.sql`.**
- **Auto-apply:** post-deploy job `run-sql-v2-migrations-post-deploy` in
  `.github/workflows/fly-deploy.yml`, idempotent, Telegram-alerted.
- **Squawk lint:** `.github/workflows/migration-lint.yml` runs on
  `migrations_v2/*.sql` PRs; bypass a rule with `-- squawk-ignore: <rule>`.
- **war_room_drafts columns:** id, topic, tone_register, register, status,
  slides_json, council_debate_json, rejection_reason, canva_url, lease_owner,
  lease_acquired_at, created_at, updated_at. **ABSENT:** domain, dominant_mode,
  layout_family, archetype (archetype/per-slide modes live inside slides_json).
- **register** IS persisted (war_room_drafts.register; valid set in
  wr2_draft_generator VALID_TONES: analitico/tecnico/militante/pedagogico/
  ironico/rituale/poetico).
- **image-mode taxonomy** (constitution Art 5.8, 9 modes): desk-document,
  event-photo, architecture-or-texture, provocation-photo, human-silhouette,
  object-comparison, calendar-photo, data-visualization, cultural-photo.
  NOT persisted as a "dominant" — must be derived from slides_json.
- **domain** (constitution Art 5.7, 5+1): visa, tax, property, regulatory,
  health, (brand). NOT persisted — must be derived from `topic` text.
- **Write site:** `wr2_canva_desktop_apply.py` around line 183-190 (the
  `UPDATE war_room_drafts SET status='rendered'` block).

## 3. Design

### 3.0 GATING PREREQUISITE — make the generator emit `image_mode` (panel-critical)
Without this, `dominant_mode` is "unknown" forever. Do this FIRST, in the same PR:
- `wr2_draft_generator.py` SYSTEM_INSTRUCTIONS: add to the per-slide schema a required
  `"image_mode"` field for hero slides, constrained to the 9 Art 5.8 modes
  (desk-document / event-photo / architecture-or-texture / provocation-photo /
  human-silhouette / object-comparison / calendar-photo / data-visualization /
  cultural-photo), with a one-line instruction to pick the mode matching the scene
  (and to vary it — ties into Art 10.6). Non-hero slides may omit it.
- `_normalise_slides` (~line 710): add `image_mode` to the whitelisted fields —
  `"image_mode": (raw.get("image_mode") or "").strip().lower() or None`. Without this
  the field is stripped at persistence.
- Tests: a normalise test asserting a slide with `"image_mode":"Desk-Document"` survives
  as `"desk-document"`, and absence → None.
- This is the ONLY change that touches the generation contract; everything else is
  additive logging + a soft/hard steer.

### 3.1 Migration `206_wr2_topic_type_log.sql`
```sql
CREATE TABLE IF NOT EXISTS topic_type_log (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    draft_id        UUID NOT NULL,
    domain          TEXT NOT NULL,         -- visa|tax|property|regulatory|health|brand|unknown
    register        TEXT,                  -- the 7-tone register
    dominant_mode   TEXT,                  -- one of the 9 image-style modes (or 'mixed'/'unknown')
    layout_family   TEXT,                  -- derived from archetype/slides (nullable)
    archetype       TEXT,                  -- nullable (from slides_json if present)
    topic           TEXT,                  -- denormalized for human inspection
    rendered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,           -- NULL until a real publish signal exists (panel B)
    deleted_at      TIMESTAMPTZ            -- soft-delete to prune Damar-rejected rows (panel B)
);
-- idempotency: one row per draft (re-render must not duplicate)
CREATE UNIQUE INDEX IF NOT EXISTS ux_topic_type_log_draft_id ON topic_type_log (draft_id);
-- the hot query: last-N by domain, newest first
CREATE INDEX IF NOT EXISTS ix_topic_type_log_domain_time ON topic_type_log (domain, rendered_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_topic_type_log_domain_time;
DROP INDEX IF EXISTS ux_topic_type_log_draft_id;
DROP TABLE IF EXISTS topic_type_log;
```
- Squawk-safe: `CREATE TABLE/INDEX IF NOT EXISTS` on a brand-new empty table — no
  ALTER, no NOT NULL backfill, no lock on war_room_drafts. If Squawk still flags the
  non-concurrent index, add `-- squawk-ignore: prefer-robust-stmts` + reason.
- **Rollback uses the literal `-- === ROLLBACK ===` marker** the runner
  (`migration_base.py:35,461`) splits on, with EXECUTABLE drops (not a comment).
- `published_at`/`deleted_at` are added now (zero cost) so the v2 semantic switch
  (panel B: only count published, prune rejected) needs no new migration.

### 3.2 Derivation helpers (new module `scripts/wr2_topic_type.py`, pure + unit-tested)
- `derive_domain(topic: str) -> str`: keyword map (visa/visto/kitas → visa;
  pajak/tax/ppn/pph → tax; properti/property/tanah/rumah/hak pakai/nominee →
  property; permenaker/labor/bpjs/regulasi → regulatory; kesehatan/health → health;
  else "unknown"). Case-insensitive, ID+EN keywords. Deterministic, no LLM.
- `derive_dominant_mode(slides_json) -> str`: count per-slide image-mode
  occurrences (read whatever field the slides carry — `image_mode` /
  `image_style_mode`; tolerate both/absent), return the most frequent; tie or
  empty → "unknown". (We do NOT invent modes — only count what's present.)
- `derive_layout_family(slides_json) -> str | None`: most-frequent per-slide
  layout field if present, else archetype, else None.
- `extract_archetype(slides_json) -> str | None`: top-level archetype if present.
- All defensive: accept dict or JSON string, never raise on malformed input
  (return "unknown"/None) — a logging table must never break the render path.

### 3.3 Write at `rendered` (in `wr2_canva_desktop_apply.py`) — panel-corrected
**Reality (Codex):** the write site is `_persist_result` — a BARE `conn.execute`
`UPDATE ... SET status='rendered'` (~line 174), called from TWO paths (headless
~420, desktop ~547). There is NO surrounding transaction to be "inside of".
**Therefore:** fold the log write INTO `_persist_result` itself (single site, both
paths covered) as a best-effort step AFTER the status update, isolated in a
savepoint so a log error cannot abort the status update's implicit tx:
```python
# after the UPDATE ... SET status='rendered' execute() returns:
try:
    async with conn.transaction():   # savepoint — isolates the insert
        await _log_topic_type(conn, draft_id, topic, slides_json, register)
except Exception as exc:              # observability, never fail the render
    logger.warning("topic_type_log write failed for %s: %s", draft_id, exc)
```
`_log_topic_type` derives the fields (via `wr2_topic_type.py`) and does:
```sql
INSERT INTO topic_type_log (draft_id, domain, register, dominant_mode, layout_family, archetype, topic)
VALUES ($1,$2,$3,$4,$5,$6,$7)
ON CONFLICT (draft_id) DO NOTHING;   -- idempotent on re-render
```
- Best-effort: render success is independent of the log. NOT fail-closed — this is
  observability + an anti-monotony data source, not a correctness gate.

### 3.4 Lookup + injection (in `wr2_draft_generator.py`)
- New helper `fetch_recent_same_domain(conn, domain, limit=2) -> list[dict]`:
  `SELECT register, dominant_mode FROM topic_type_log WHERE domain=$1 ORDER BY
  rendered_at DESC LIMIT $2`.
- At draft-generation time, derive the *prospective* domain from the topic, fetch
  the last 2, and **inject into the prompt**: "Avoid repeating these recent
  same-domain combos: [(register, mode), …]. Per Art 10.6 you MUST differ in BOTH
  register and image-mode from each."
- This is a SOFT steer at generation (the model picks fresh register/mode). The
  HARD enforcement is §3.5.

### 3.5 Hard-reject assertion (post-generation) — panel-corrected
- After the draft is generated, derive its (domain, register, dominant_mode).
- **If domain == "unknown" → SKIP the hard-reject entirely** (soft-steer only).
  Prevents the junk-bucket cross-constraint (panel C: a visa and a tax carousel
  both classified "unknown" must not constrain each other).
- Else compare to the last-2 same-domain entries from topic_type_log. **Reject +
  regenerate if the draft matches in BOTH register AND image-mode** of EITHER of
  the last 2 — i.e. the carousel is allowed if it **differs in EITHER register OR
  image-mode** (panel A: "differ in EITHER", looser than the first draft's "differ
  in BOTH", which livelocked because mode was always unknown and "analitico"
  dominates visa/tax). Max 2 regenerate retries, then WARN-and-proceed (cold-start
  empty table → no constraint; the rule only fires with ≥1 prior same-domain row).
- Skip the mode half of the comparison when dominant_mode is "unknown" on either
  side (until §3.0 ships, this is the register-only anti-repeat; after §3.0, mode
  participates).
- Code-level intra-carousel check (autopsy): assert ≥3 distinct image-modes within
  a single carousel — WARN, not block, v1 (becomes meaningful once §3.0 ships).

### 3.6 Constitution reconciliation (Art 5.8 vs 13.4 vs 10.6)
- Art 10.6 (the 2026-06-04 rule) SUPERSEDES the 5.8/13.4 contradiction. Edit the
  constitution (HOME fork Pro+M5, not git): make 5.8 and 13.4 explicitly defer to
  10.6 ("see 10.6 for the binding same-domain window rule"), so there's one law.
  This is a doc edit, shipped to both forks, NOT in the code PR.

## 4. Risks + mitigations (the things the 4-LLM panel must stress-test)

1. **Starvation:** could the hard-reject (§3.5) block ALL carousels? Mitigation:
   max-2 retries then WARN-and-proceed; the rule needs ≥1 prior same-domain row
   to fire at all, so cold-start is safe (empty table → no constraint). The check
   is per-domain, so visa-spam is constrained but a different domain is free.
2. **Duplicate writes on re-render:** the canva renderer can re-run on the same
   draft. Mitigation: `UNIQUE(draft_id)` + `ON CONFLICT DO NOTHING`.
3. **Write failure breaks the render path:** Mitigation: try/except + WARN; the
   log is best-effort, render success is independent.
4. **Wrong write site (the autopsy's dead-orchestrator trap):** Mitigation —
   verified the live terminal status is `rendered` in Pipeline B; write there.
5. **domain misclassification:** keyword map is coarse → "unknown" bucket. A bad
   domain only weakens the anti-monotony steer, never corrupts data. Acceptable
   v1; a classifier is a follow-up.
6. **dominant_mode derivation when slides carry no mode field:** returns
   "unknown" → those rows don't constrain (and don't get constrained). Safe
   degradation; logged so we can see how often it happens.
7. **Migration auto-applies on deploy to PROD:** it's additive (new empty table),
   idempotent, Squawk-linted, with a rollback line. Low risk, but the panel
   should confirm no lock contention (CREATE TABLE on a new name takes a brief
   lock only on the catalog, not on war_room_drafts).

## 5. Test plan
- `scripts/test_wr2_topic_type.py`: derive_domain (each domain + unknown),
  derive_dominant_mode (frequency, tie→unknown, malformed→unknown),
  derive_layout_family, extract_archetype, and the collision check
  (matches-both→reject, differs-in-one→ok, empty-history→ok).
- Migration apply/rollback smoke against a throwaway schema (psql or the
  migration_manager test harness): upgrade creates table+indexes, the
  ON CONFLICT INSERT is idempotent, the domain/time index exists.
- Targeted pytest for any touched backend module; full `scripts/tests/` sanity
  (expect the known pre-existing failures only, no new ones).

## 6. Execution (autonomous, to merge)
1. Dedicated worktree via `scripts/agent_start.py --lane wr2 --task-id topic-type-log`.
2. Implement migration + `wr2_topic_type.py` + write-site + lookup/inject +
   reject + tests.
3. Squawk lint locally if available; run migration smoke; run pytest.
4. Commit atomic, push, PR with full body, auto-merge (high-traffic pattern:
   `--squash --auto` + `update-branch`), watch CI (rerun only the known flaky
   `test_duplicate_alert_id_skipped`), verify MERGED on origin/main + table DDL
   present.
5. Constitution 5.8/13.4 defer-to-10.6 edit on both HOME forks.
6. Capture: memory + a cicatrix entry for the autopsy hallucination (the two
   phantom files) so no future agent trusts those file:line refs.

## 7. Out of scope (explicit)
- Resurrecting Pipeline A's orchestrator publish path (that's P-1).
- A real "published to IG" signal (needs a Damar-confirms-in-Telegram hook).
- A domain classifier beyond keyword matching (v2).
- Making the intra-carousel ≥3-modes check a HARD block (v1 = WARN).
