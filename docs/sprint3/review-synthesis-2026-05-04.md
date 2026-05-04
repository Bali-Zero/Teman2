# Sprint 3 W1 design — Multi-LLM review synthesis

**Reviewers:**
- **Me** (Claude Opus 4.7 1M, Pro session 2026-05-04, with repo grep verifica)
- **DeepSeek-Reasoner** (4925 token, 65s — schema/migration safety angle)
- **Gemini 3 Pro Preview** (yolo mode, ~1min — architecture coherence + research grounding angle)
- **Codex GPT-5.5** ❌ out-of-quota fino al 2026-05-06
- **NotebookLM** ❌ auth expired

Three independent perspectives is enough. Not letting myself be pulled by majority. For each finding: source, claim, **my judgment**, reasoning.

---

## CONVERGED BLOCKERS (3/3 reviewers, independent reasoning)

### 🚫 B1 — M1 (3-layer schema with 12 FK link tables) is structurally broken

| Source | Finding |
|---|---|
| Me | 8/12 asset_kind target tables don't exist in `migrations_v2/`. Verified via grep (mata-garuda-cell-design.md:82-95 vs `apps/backend-rag/backend/db/migrations_v2/*.sql`). |
| DeepSeek | Same reasoning, same evidence. Quotes exact DDL line `article_id BIGINT NOT NULL REFERENCES news_articles(id)` and notes `news_articles` doesn't exist. |
| Gemini | Same + adds dimension I missed: even where data exists, it's in **Qdrant** (`intel_finding`=Qdrant point_id), **external systems** (`crm_enrichment_lookup`=Google Places ID composite string), or **abstract keys** (`kg_entity`=kbli_code). FK to non-PG datastores is impossible by definition. |

**My verdict: BLOCKER ACCEPTED. Revert M1 entirely.** This is the strongest finding of the round — three independent paths to the same conclusion, and the third (Gemini) catches an even deeper failure than the first two.

**Action for W2:**
- Drop the 3-layer pivot.
- Keep the original single-table polymorphic design (asset_kind+asset_id, no FK), per W1.3 lines 75-170.
- The "polymorphic FK is unverifiable" risk in W1.3:431-434 is acknowledged from day 1 — it stays as a **known limitation** and is mitigated via a weekly garbage-collection cron (W2 backlog as originally planned).
- The ADDENDUM M1 in mata-garuda-cell-design.md (lines 506-556) gets **deleted** or rewritten as "M1 — 3-layer schema CONSIDERED AND REJECTED, see post-mortem".

**Why I'm not hedging**: the only argument FOR M1 was "FK integrity wins". That argument **does not survive** the empirical fact that most asset_kinds aren't in PG at all. Keeping M1 means shipping 12 broken-by-design link tables. Reversal is correct.

---

### 🚫 B2 — Migration numbering `154a..154m` is invented and incompatible with tooling

| Source | Finding |
|---|---|
| Me | No file in `migrations_v2/` uses letter suffixes. Verified by find. Runner (`migration_manager.py`) reads integer-indexed `schema_migrations`. |
| DeepSeek | "Migration runner expects integer ordering. `154a..154m` violates that. Squawk lint will fail. No project file uses letters." Recommends single atomic migration or sequential ints. |
| Gemini | Did not address directly (focused on architecture). |

**My verdict: BLOCKER ACCEPTED.** With M1 reverted (B1) the 12-link issue evaporates. Sprint 3 W2 ships migration `153_crm_welcome_completed` (CRM cell) + `154_asset_provenance` (single-table polymorphic, mata-garuda) — two clean integer migrations.

**Action for W2:**
- Drop `154a..m` notation from all docs.
- Single integer per migration. If schema needs many tables, group in 1 file (idempotent CREATE TABLE IF NOT EXISTS).

---

## CONVERGED IMPORTANT (2/3 reviewers, reasoning aligns)

### ⚠️ I1 — `asset_provenance` UNIQUE (asset_kind, asset_id) constraint dropped silently in addendum

| Source | Finding |
|---|---|
| Me | M1 § Medium addendum: 3-layer addendum DDL doesn't preserve the original `UNIQUE (asset_kind, asset_id)` constraint. |
| DeepSeek | Same, more explicit: "Without it, multiple provenance rows for the same asset (from different activities) are allowed, which may be intentional, but original intent was one row per asset." Recommends adding `UNIQUE (asset_kind, asset_id)`. |
| Gemini | Did not address. |

**My verdict: ACCEPTED, but it goes away if we accept B1.** With original single-table polymorphic preserved, `UNIQUE (asset_kind, asset_id)` is already in W1.3 line 142-143. No action needed if M1 reverted.

---

### ⚠️ I2 — TLP `red` default is NOT "DDL enforcement", just a default

| Source | Finding |
|---|---|
| Me | M2 line 575 claims "Symbiosis Law 2 OSINT blindato in DDL not just runtime" — but defaults are overridable by any explicit INSERT. |
| DeepSeek | Same: "default ≠ enforcement". Lists 3 actual DDL-level options (GENERATED ALWAYS AS, CHECK with current_setting, BEFORE INSERT trigger). |
| Gemini | Did not address (focused elsewhere). |

**My verdict: ACCEPTED — fix the doc claim, not the code.** TLP column itself is fine (taxonomy is useful). Just stop overselling. Update mata-garuda-cell-design.md:574 to: "TLP column defaults to 'red' as a safe-default; effective enforcement remains at the cell adapter / network boundary level".

**Action for W2:** doc-only change in addendum. No code impact.

---

### ⚠️ I3 — `(reliability, credibility)` query index missing post-M2

| Source | Finding |
|---|---|
| Me | M3 (Medium): partial indexes in original schema were fit for old design; M2 admiralty 2-axis needs new indexes. Recommended deferring to query-pattern profiling. |
| DeepSeek | Same: "no indexes on reliability/credibility. Queries will scan. Add composite index (reliability, credibility)." |
| Gemini | Did not address. |

**My verdict: ACCEPTED with caveat.** Add `CREATE INDEX IF NOT EXISTS ix_asset_provenance_admiralty ON asset_provenance(reliability, credibility) WHERE invalidated_at IS NULL` to mig 154 if M2 ships.

But: this index lives or dies with M2 (admiralty 2-axis). See I5 below — if we downsize M2 from 36-cell to 4-tier enum, the index is even cheaper.

---

## DIVERGENT FINDINGS — must judge each

### 🆕 X1 — Gemini ALONE: claimed ExpeL importance count is HALLUCINATED. **VERIFIED FALSE.**

| Source | Finding |
|---|---|
| Gemini | "The Opus 4.7 agent entirely hallucinated the mechanics of the ExpeL paper... no upvote/downvote/prune-at-0 mechanic in ExpeL." |
| Me | Did not fact-check independently. |
| DeepSeek | Did not address. |
| **Fact-check (arXiv:2308.10144 v3)** | **The mechanism IS in the paper.** Verbatim: "operations LLM agents can perform on insights: ADD, EDIT, DOWNVOTE, UPVOTE. A newly added insight will have an initial importance count of two ... count will increment if UPVOTE or EDIT applied ... decrement when DOWNVOTE applied. If insight's importance count reaches zero, it will be removed." |

**My judgment: GEMINI WAS WRONG. The research-and-brainstorm.md citation is accurate.** Ironic — Gemini accused Opus of hallucinating literature that Gemini itself hallucinated as absent. This is exactly why we run multi-LLM with fact-checks, not consensus voting.

**Action**: ignore Gemini X1. The ExpeL importance-count proposal stays as written in `mata-garuda-cell-design.md:633-654`. Original doc's recommendation (defer to Sprint 4+ as cell-core-wide change) holds.

**Lesson recall**: "verify-not-trust orchestrator pattern" (lessons.md 2026-04-29). Same principle applies to LLM reviewers as to subagents. Gemini's hostile-reviewer mode produced confident but false claims about academic literature; only WebFetch on arxiv resolved it. Save this as a generalizable lesson: **for any LLM-asserted academic claim, fact-check before propagating.**

---

### 🆕 X2 — Gemini ALONE: 36-cell admiralty matrix is OSINT-industrial overkill

| Source | Finding |
|---|---|
| Gemini | "5-person team building a CRM... not NATO. 36 cells is cognitive bloat. Defensible refinement: 4-tier enum (VERIFIED, HIGH, LOW, UNVERIFIED) tied to concrete sourcing rules". |
| Me | Did not address — I accepted the research's "OSINT industry standard" framing. |
| DeepSeek | Did not address. |

**My judgment: PARTIALLY ACCEPTED.** The argument is real. Bali Zero's actual users (Surya, Ari, Adit, Sahira, Krisna…) won't reliably distinguish "C2: Fairly reliable + Probably true" from "D3: Not usually reliable + Possibly true". Most rows will be tagged by automated cells (intel-scraper, KG extractor) — those CAN do mechanical mapping, but human team members reviewing won't.

**However**: machine-tagged rows (which are 90%+ in the design) DO benefit from finer granularity for downstream filtering. The cost is not in tagging precision (machine), it's in human cognitive load when reading the data.

**Compromise**: keep the 36-cell DDL (cheap to store), but provide a **summary view** that collapses to 4 tiers for human dashboards. Cell adapter exposes `confidence_tier(reliability, credibility)` returning {VERIFIED|HIGH|LOW|UNVERIFIED}.

**Why I'm not fully siding with Gemini here**: I think the research IS well-grounded in MISP/STIX 2.1 standards (these are real industries doing this). The 36-cell granularity isn't "cognitive bloat" if hidden from humans. Gemini may be reading "CRM team" as "primary users of the tagging UI" — but the actual primary users are LLMs and automated cells, not Surya tagging visa requirements by hand.

**Recommendation for Zero to decide**: 36-cell with view OR 4-tier enum. If 4-tier wins, drop the M2 OSINT-industrial framing — it becomes "graduated confidence enum, ad-hoc not MISP".

---

### 🆕 X3 — Gemini ALONE: 5-phase lifecycle is "pure ceremony"

| Source | Finding |
|---|---|
| Gemini | "5-phase embrione/neonato/giovane/adulto/anziano carries zero semantic weight. Industry uses 2-3 levels. Wrap automation in Sandboxed | Autonomous." |
| Me | Did not address — design doc itself defends as "design-original, justified by HITL frequency findings". |
| DeepSeek | Did not address. |

**My judgment: NOT IN SCOPE for Sprint 3.** The 5-phase lifecycle is cell-core architecture; Sprint 3 W1 is just consuming it. Whether the 5 phases are right is a separate brainstorm.

**For Zero**: this is a fair criticism but it's about the **organism design**, not Sprint 3. Park it for a future cell-core review session.

---

### 🆕 X4 — Gemini ALONE: C2 deferral right answer, wrong reason (inner-platform anti-pattern)

| Source | Finding |
|---|---|
| Gemini | "Twenty CRM uses DB registry because it's a SaaS where end-users config workflows. Nuzantara is internal tool. Hardcoded business logic in DB config is Inner-Platform anti-pattern." |
| Me | Accepted the doc's "premature abstraction" framing without challenging it. |
| DeepSeek | Did not address. |

**My judgment: FULLY ACCEPTED.** Gemini is right about the reasoning. The conclusion (defer C2) is the same, but the justification matters: "we'll add it when we hit 25 rules" (premature abstraction framing) is wrong because **we should never add it for internally-authored automations**.

**Action**: update `crm-cell-design.md:394-407` to remove "trigger to revisit at ≥25 automations" and replace with "do NOT add until/unless Bali Zero ships an end-user-facing workflow editor (multi-tenant, user-configurable)".

---

### 🆕 X5 — Gemini ALONE: Custom invalidation_path DSL is reinvention

| Source | Finding |
|---|---|
| Gemini | "Don't invent custom string-parsing DSL. Just use `valid_until TIMESTAMPTZ` and `invalidation_event_topic VARCHAR`." |
| Me | I1 (mine, IMPORTANT): same finding from different angle — "spec the parser before W2". |
| DeepSeek | Did not address. |

**My judgment: ACCEPTED, partially.** Gemini's solution is cleaner. Replace `invalidation_path TEXT` with two columns:
- `valid_until TIMESTAMPTZ NULL` (TTL)
- `invalidation_event_topic VARCHAR(64) NULL` (event-based)
- Both NULL = `'never'`
- `manual` = a separate boolean `manual_invalidation_only BOOLEAN DEFAULT false`

But: the existing `manual` and `never` modes are real and not just "absence of TTL". Keep them as either an enum or boolean flags.

**Compromise schema (Zero approval needed)**:
```sql
valid_until TIMESTAMPTZ NULL,                     -- non-null = TTL
invalidation_event_topic VARCHAR(64) NULL,        -- non-null = event-based
invalidation_mode VARCHAR(8) NOT NULL DEFAULT 'auto'
    CHECK (invalidation_mode IN ('auto', 'manual', 'never'))
```

Three columns, no DSL, all queryable. Drop `invalidation_path TEXT` and the parser library.

---

## My findings the LLMs missed

### B3 (mine alone) — `asset_kind` enum mismatch between doc and handover

The 4 docs say 12 specific asset_kinds (Bali Zero domain). The handover lists 12 different ones (general OSINT). Need to pick.

**Status**: not refuted by either LLM (they didn't read the handover, only the docs). My finding stands. Pick the doc's original list.

### I4 (mine alone) — `crm_welcome_runs` table not specified

W1.2 references "yet-to-be-created `crm_welcome_runs` table" but no schema spec.

**Status**: not refuted. Stands. Spec the columns before W2.

### I5 (mine alone) — `apps/cell-crm/` vs `apps/crm-cell/` path inconsistency

Cosmetic but real.

**Status**: stands. Pick one before W2.

---

## My finding REFUTED by LLM

### M2 mine (Symbiosis Law 2 weak in DDL) — same as DeepSeek's I2 — confirmed.

Not refuted, just amplified by DeepSeek.

### M5 mine (ExpeL scope creep into cell-core) — superseded by Gemini's X1 (hallucinated)

If Gemini's claim is correct, the "scope creep" framing is too generous — it's not just scope creep, it's bullshit citation. Pending fact-check.

---

## Final verdict

**Sprint 3 W1 design is NOT ready for W2 code phase.**

**Required changes before W2 starts (all are pre-W2 doc updates, no code):**

1. **B1 Block** — revert M1 (3-layer pivot). Keep original single-table polymorphic. Delete or rewrite mata-garuda-cell-design.md ADDENDUM § M1.
2. **B2 Block** — drop `154a..m` notation. Migration plan: 153 (CRM welcome) + 154 (asset_provenance, single table). Two clean integers.
3. **B3 Mine** — pick one asset_kind list (the doc's original 12 Bali-Zero-aligned list).
4. **I2 Doc fix** — TLP claim corrected from "DDL enforcement" to "safe default; runtime enforcement at cell adapter".
5. **I4 Mine** — spec `crm_welcome_runs` columns now (5-8 fields).
6. **I5 Mine** — pick `apps/crm-cell/` path.
7. ~~**X1 Pending**~~ — **resolved by fact-check.** ExpeL importance-count IS in the paper (verified arXiv:2308.10144 v3). Gemini was wrong. Original Opus 4.7 citation is accurate. No action — keep ExpeL proposal as deferred to Sprint 4+ as originally planned.
8. **X4 Gemini** — update C2 deferral reasoning ("never for internal-only automations" not "wait for 25 rules").

**Optional changes (Zero decides):**

9. **X2 Optional** — keep 36-cell admiralty + add `confidence_tier()` summary OR downgrade to 4-tier enum (X2 Gemini view).
10. **X5 Optional** — replace `invalidation_path TEXT` DSL with explicit columns (`valid_until` + `invalidation_event_topic` + `invalidation_mode`).
11. **I3 Conditional** — if M2 admiralty stays as DDL, add composite index `(reliability, credibility)`.

**Out of scope for now (Gemini criticisms parked):**
- X3 — 5-phase cell lifecycle. Real critique but cell-core scope, not Sprint 3.
- X1 (Homeostatic) — same scope.

**Estimated impact on W2 timeline:**
- Original plan: 5-7 days for migrations + cell adapters + tests.
- Post-revisions: SHORTER. The expensive part (12 link tables) is gone. Net savings: ~1 day. New W2 estimate: 4-6 days.

**Note on multi-LLM review value**: this round caught 3 BLOCKERS that the original handover/research had not flagged (B1+B2+X1 from Gemini's hallucination catch). That's high signal. Worth doing this BEFORE writing the code, not after.
