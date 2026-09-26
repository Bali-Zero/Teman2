---
date: 2026-06-04
domain: operations
subject: wr2-autopsy-remediation
status: SPEC — deferred items awaiting operator decision
shipped_in_this_pr:
  - "P-2b: BRAND_SUFFIX split into BRAND_TECHNICAL + per-slide TONAL_PALETTES (wr2_image_generator.py)"
  - "P-5: fact-checker fail-closed on empty research_json + extended LAW_PATTERNS + no self-substring for law claims (wr2_fact_checker.py)"
  - "P-5: canva-apply locked to drafts_imaged_checked (env-overridable, default safe) (wr2_canva_desktop_apply.py)"
  - "P-6 (partial): killed 'Imagen Ultra' provenance lie + removed banned phrases from live prompt (wr2_draft_generator.py)"
  - "P-3: constitution Art 10.5 polarity flip + new Art 10.6 anti-sameness + Art 13.3 no-static-default (HOME fork, Pro+M5, NOT in git repo)"
sources:
  - research/operations/2026-06-04-wr2-autopsy-report.md
---

# WR2 Autopsy — Deferred Remediation Spec (P-1, P-2a, P-4, P-6-full)

The autopsy (`2026-06-04-wr2-autopsy-report.md`) prescribed 6 fixes. The
high-leverage / low-risk subset (P-2b, P-5, P-3 grammar, P-6 honesty) shipped in
this PR and on the HOME constitution fork. The four items below were **deliberately
NOT auto-merged** because each is either an architectural change to a pipeline that
publishes live to Instagram, a manual asset-production task, a production DDL, or a
schema change — all of which warrant an explicit operator decision (Antonello).

This is the executable plan for each, so they can be picked up without re-deriving.

---

## P-1 — Consolidate to ONE pipeline, make it brand-cortex-aware  *(architectural — operator decision)*

**Problem (verified):** Two pipelines exist. **Pipeline A** (`wr2_carousel_dispatcher.py` →
`wr2_carousel_orchestrator.py` → 5 subagents → critic) holds ALL the variety/quality
organs but is **dead code**: its dispatcher `LISTEN`s on Postgres channel `topic_ready`
which **no producer fires** (repo-wide grep: zero `NOTIFY topic_ready` outside the
dispatcher's own LISTEN). The daemon crash-loops (`launchctl` exit 75). **Pipeline B**
(`wr2_topic_selector.py` → `wr2_draft_generator.py` → `wr2_image_generator.py` →
`wr2_fact_*` → `wr2_canva_desktop_apply.py`) is what actually ships and has none of
those organs.

**Two routes — pick ONE:**

### Route 1A — Port A's organs INTO B (lower blast radius, recommended)
The path that ships keeps running; we add the missing organs to it incrementally.
1. `wr2_topic_selector.py` / `wr2_draft_generator.py`: before `claude_compose_slides()`,
   add an **archetype + register selection** step (port the logic from
   `wr2-brief-interpreter.md` into a Python helper `select_archetype(topic, scraped) ->
   {archetype, register, rationale}`). Persist `archetype` + `register` + `rationale`
   into `war_room_drafts`.
2. Add an **NB ground-truth query** step that writes real facts into `research_json`
   BEFORE fact-extraction (this is also P-5's precondition — see below). Use the
   bipolar-verifier pattern (1 LLM + 1 domain NB), NOT a 4-LLM council, per project rule.
3. Add a **critic gate** after draft compose: port the `wr2-critic.md` rubric (plus the
   new Rubric 6, see P-3) as a Python call that can return FAIL → regenerate (max 2),
   on the live path. Gate `drafts_imaged → drafts_imaged_checked` on critic PASS too,
   not just fact-check.
4. Formally **decommission Pipeline A**: `launchctl bootout` the
   `com.balizero.wr2.carousel-dispatcher` plist, archive `wr2_carousel_dispatcher.py` +
   `wr2_carousel_orchestrator.py` to `scripts/.disabled-<date>/`, and remove the
   phantom-channel LISTEN. Do NOT leave a crash-looping daemon.

### Route 1B — Wire B to trigger A (higher blast radius)
1. `wr2_topic_selector.py`: after inserting a `briefed` draft, `NOTIFY topic_ready,
   '<draft_id>'`.
2. Make `wr2_carousel_orchestrator.py` write to the SAME `war_room_drafts` Postgres
   table the live renderer reads (today it writes to `~/.claude/carousels/...` — a
   different store; the critic even reads `apps/war-room/output/...`, a third path).
3. Fix the orchestrator's critic-before-render ordering bug (`orchestrator.py:769-803`
   runs critic, THEN `render_playwright` at :806 — it judges files that don't exist yet)
   and the no-op retry (re-runs critic on byte-identical artifacts).
4. Reconcile the divergent voice spec (live path reads none of the cortex; the subagents
   self-load it).

**Recommendation:** Route 1A. It never turns off the shipping pipeline, lets each organ
land + be verified independently, and avoids resurrecting 3 storage-path mismatches and 2
ordering bugs in the orphaned orchestrator. Estimate: 1A ≈ 4-6 atomic PRs; 1B ≈ 3 PRs but
each is high-risk (touches the live trigger + storage model).

**Gate before any of this:** 4-LLM panel review of the chosen route (Gemini agy + Codex
GPT-5.5 + DeepSeek V4 Pro + NB-1), per CLAUDE.md §6.

---

## P-2a — Build 3-5 distinct Canva master templates  *(manual asset production — operator)*

**Problem (verified):** `pending_builder.py:88` `TEMPLATE_DESIGN_ID = "DAHJSqJOIO8"` — every
live carousel is a text-swap of ONE gray 11-page design. `slides_to_operations` emits only
`replace_text` + upload-asset ops; there is no background/layout/color op. Structural
sameness is therefore guaranteed by construction.

**Plan:**
1. In Canva, duplicate `DAHJSqJOIO8` into 3-5 masters with genuinely different
   backgrounds / grid systems — e.g. `swiss-grid-asymmetry`, `stat-card-hero`,
   `thin-red-rule-divider`, `monospace-evidence-block` (these layout families are already
   named in `tokens.json` but have no Canva backing). Keep the brand palette
   (antracite/white/yellow is a legitimate brand asset, Art 2 + 14.4) but vary structure.
2. Record their design IDs in a `TEMPLATE_DESIGN_IDS: dict[archetype, str]` map in
   `pending_builder.py`.
3. `build_canva_pending` selects a master per carousel **by archetype** (falls back to the
   current default only if the archetype has no dedicated master). Even 2-template
   alternation breaks the monotony immediately.
4. Verify each master resolves via `get-design` (the live master already had a
   stale-ID incident on 2026-05-09 and 2026-05-29 — add a startup reconcile check).

**Why deferred:** requires producing the actual Canva designs by hand (a design task, not
code) + an operator who can sign off on the new layouts matching brand.

---

## P-4 — Persist cross-carousel memory (`topic_type_log`)  *(production DDL — operator)*

**Problem (verified):** Art 5.8/13.4 anti-monotone ("no two consecutive carousels same
dominant mode; critic checks `topic_type_log` last 2 published") has **no backing data**.
Grep: ZERO `INSERT/UPDATE topic_type_log` sites. The table is defined only in
`_state-schema.sql:63` (a standalone SQLite file, NOT in `migrations_v2/`) and read via a
`LEFT JOIN` in `_voyager-curriculum.py:49` — which joins across a *different DB engine*
than the runtime Postgres `wr2_carousel_runs` table. So "last 2 modes" is always NULL.

**Plan:**
1. New Postgres migration in `apps/backend-rag/backend/db/migrations_v2/` (NOT SQLite):
   `topic_type_log(id, carousel_id, domain, dominant_register, dominant_image_mode,
   layout_family, published_at)`. Squawk-lint clean.
2. Write a row at **publish** time (the Telegram-approve handler, the only true
   publish point) — on the PRODUCTION path, keyed to the live table.
3. Inject "last 2 published {register, image_mode} for this domain" into the
   generator/image-prompt-author prompt; **hard-reject** a repeat (this is what makes
   new Art 10.6 enforceable).
4. Add a code-level assertion (≥3 distinct image modes per carousel) instead of trusting
   the LLM's self-attestation.
5. Reconcile Art 5.8 (0 consecutive repeats) vs Art 13.4 (up to 2 allowed) into ONE rule.

**Why deferred:** DDL on production Postgres + a write at the live publish point. Needs
operator awareness (and ties to P-1 Route choice — where "publish" actually happens).

---

## P-6 (full) — Commercial spine + popular-voice validators  *(brief schema change — operator)*

**Shipped here (partial):** removed the `"Imagen Ultra"` provenance lie; replaced the
banned `"What This Means For You"` headline and `"Link in bio"` body from the live prompt
example.

**Still deferred:**
1. Add a `commercial_target {service_line, offer, cta_destination}` block to the brief +
   slide schema. Topic selection today scores news-freshness only — add a
   "which keyword maps to a profitable service" signal.
2. Branch the closing slide + the IG caption per `audience_segment` × `service_line`
   (today: one hardcoded generic CTA regardless of topic). The caption is the ONLY place a
   service CTA + link-in-bio is permitted (Art 6.6/6.7) and it is currently never built;
   its publish function is uncalled.
3. Add validators (regenerate, not silent-truncate): 25-50-word bodies, **3-5-word covers**
   (per Antonello's hard rule + `feedback_balizero_voice_editorial_but_popular`), and a
   readability ceiling for the "popular in voice" register.
4. Instrument saves/shares/lead attribution in daily metrics (the constitution declares
   Saves+Shares the KPI; today only pipeline throughput is tracked).

**Why deferred:** schema change to the brief/slide contract (touches every downstream
consumer) + a product decision on the service-routing taxonomy.

---

## Sequencing recommendation

1. **This PR** (shipped): P-2b + P-5 + P-6-honesty + P-3-grammar. Stops shipping wrong
   facts, breaks the photographic clamp, flips the grammar — all without architectural risk.
2. **Next** (operator-gated, one PR): P-4 `topic_type_log` — it is the enforcement backend
   that makes the new Art 10.6 real and is a prerequisite for trustworthy anti-monotony.
3. **Then** (operator-gated, biggest): P-1 Route 1A — port archetype/NB/critic into the
   live path, decommission the dead dispatcher. 4-LLM panel first.
4. **Parallel, design-led:** P-2a Canva masters (no code dependency on the above).
5. **Last:** P-6 commercial spine (schema change; do after P-1 settles where "publish" is).
