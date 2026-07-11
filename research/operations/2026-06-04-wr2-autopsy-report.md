---
date: 2026-06-04
domain: operations
subject: wr2-pipeline
auditor: 13-agent-workflow
sources:
  - scripts/wr2_*.py (26 files, ~12k LOC)
  - .claude/agents/wr2-*.md (8 subagents)
  - .claude/skills/bali-zero-brand/{constitution.md, voice/, layouts/, tokens.json}
  - apps/backend-rag/backend/services/canva_renderer/pending_builder.py
  - launchctl list, ~/logs/wr2-carousel-dispatcher.error.log
status: FROZEN
---

# WR2 AUTOPSY REPORT — Why the carousels are always the same

## 1. EXECUTIVE VERDICT

WR2 produces monotone, occasionally-wrong carousels because **the entire variety-and-quality apparatus the brand built lives in a pipeline that does not ship, and the pipeline that does ship has none of it.** This is not a tuning problem — it is structural, and it is all three layers at once.

There are two pipelines. **Pipeline A** (dispatcher → `wr2_carousel_orchestrator.py` → 5 subagents → critic) is where the brand cortex, the 9 image-style "anti-monotone" modes, the archetype taxonomy, the maieutic brief/storyboard reasoning, and the only real vision critic live. It is **dead code**: its dispatcher `LISTEN`s on a Postgres channel `topic_ready` that **no producer anywhere fires** (verified: zero `NOTIFY topic_ready` in the entire repo), and the daemon crash-loops (exit 75). **Pipeline B** (`wr2_topic_selector.py` → `wr2_draft_generator.py` → `wr2_image_generator.py` → `wr2_fact_*` → Canva apply) is what actually ships — and it has **no brief-interpreter, no storyboarder, no critic, no archetype, no layout-family selection, no anti-monotone check, and no NotebookLM ground-truth gate.** It is a single Claude call against a frozen prompt that bakes in one editorial skeleton (cover → "Our read:" → body → "What This Means For You" CTA), text-swapped onto **one** hardcoded Canva master template (`DAHJSqJOIO8`, "11 pages, gray background"), with hero images force-suffixed by `BRAND_SUFFIX` ("deep charcoals and warm ochre accents") on every single image. On top of that, the **constitution itself encodes monotony as a brand value** — Article 10.5 makes "re-running a brief produces semantically equivalent output… random-walk drift = hard fail," i.e. variety is literally a hard fail; Article 13.3 defaults every carousel to `regulatory-explainer` (the driest register + the desk-document image mode that *was* the S11 trap); and the critic is a punishment-only gate with zero rubric that can ever *reward* a braver carousel, so a generator optimizing to pass converges on the safest, dullest template that trips no taboo. **Code, architecture, and constitution are all guilty, but the architecture split is the master cause: the cure exists and is unplugged.** The owner's exact words — "same antracite slide + white text + yellow number" — are the literal, deterministic output of Pipeline B obeying its hardcoded master template and `BRAND_SUFFIX`.

---

## 2. TOP 10 FINDINGS (severity × leverage)

### #1 — P0 · The live pipeline (B) has no brief-interpreter, no storyboarder, no critic, no archetype, no NB ground-truth
**What:** Every quality/variety/fact organ the audit was asked about exists only in Pipeline A and is never invoked for shipped carousels.
**Evidence:** `grep` across `scripts/wr2_*.py` finds `wr2-brief-interpreter`/`wr2-storyboarder`/`wr2-critic` ONLY in `wr2_carousel_orchestrator.py`. Live entry `wr2_topic_selector.py:413-422` inserts `war_room_drafts(status='briefed', brief_json=<raw scraped article>)`; `wr2_draft_generator.py:817-839` calls `claude_compose_slides()` directly on that blob. Live routing confirmed: only `com.balizero.wr2.draft-generator` + `wr2.fact-extractor` LaunchAgents are scheduled; no orchestrator plist exists.
**Impact:** Sameness AND factual errors both trace here — the path that ships has no variety enforcement and no NB-authority fact gate.
**Fix:** Pick ONE canonical path. Either route live IG through Pipeline A, or port the contracts (archetype, register reasoning, NB ground-truth, forbidden-phrases) into `wr2_draft_generator.py`. Red-team: **CONFIRMED** (P0).

### #2 — P0 · Pipeline A is dead code — dispatcher listens on a phantom channel
**What:** The only automated trigger for the variety-aware orchestrator never fires.
**Evidence:** `wr2_carousel_dispatcher.py:55 PG_NOTIFY_CHANNEL = "topic_ready"`; repo-wide grep for `topic_ready` returns ONLY the dispatcher's own LISTEN (verified this run — zero producers in scripts/apps/shared/infra). The spec doc `research/wr2/2026-05-27-...spec.md:672` has it as an UNCHECKED checklist item. `launchctl list` → `com.balizero.wr2.carousel-dispatcher` exit 75 (crash-loop); error log: `LISTEN topic_ready active` waiting forever.
**Impact:** A crash-looping daemon gives the illusion the agentic pipeline is live. It is not.
**Fix:** Either wire `wr2_topic_selector.py` to `NOTIFY topic_ready` and converge B onto the orchestrator, or formally decommission Pipeline A. Do not leave a phantom-channel daemon. Red-team: **CONFIRMED** (P0).

### #3 — P0 · `BRAND_SUFFIX` hard-codes the exact S11 monotone aesthetic onto every image
**What:** The single biggest photographic-monotony lever, applied unconditionally.
**Evidence:** `wr2_image_generator.py:145-152` BRAND_SUFFIX = "…chiaroscuro lighting, low-key exposure, desaturated muted palette of deep charcoals and warm ochre accents. Minimalist composition with vast negative space…" — appended to every prompt via `_compose_final_prompt`, used by Codex/FlowKit/Playwright backends alike. This is verbatim the "chiaroscuro… deep charcoal, warm-amber" pattern `wr2-image-prompt-author.md:16-19` documents as the S11 failure (60 identical hero images).
**Impact:** Even if upstream prompts varied, the generator clamps every output back to dark-charcoal-ochre. The `tonal_palette` field (cool-teal/monochrome/high-contrast) is meaningless.
**Fix:** Parameterize BRAND_SUFFIX by the slide's tonal_palette/mode; keep only non-aesthetic constraints (4:5, no faces, photoreal) universal. Strip the "deep charcoals and warm ochre" clamp. Red-team: **CONFIRMED** (this is the *real* monotony lever — see #4 downgrade).

### #4 — P1 (downgraded from P0) · Fail-open error swallowing silently degrades QA — but is NOT the monotony root cause
**What:** Hard failures convert to silently-accepted output across ~83 `except Exception` handlers.
**Evidence:** VLM scorer `wr2_image_generator.py:273-277` returns `(1.0, "vlm-error: …")` on ANY exception ("fail-open: accepting image", verified this run); cover VLM gate `wr2_draft_generator.py:643-644` swallows and falls through to upload; fact_checker LLM cross-check `wr2_fact_checker.py:514-519` swallows; 83 `except Exception` across 26 files (verified).
**Impact:** Real robustness defect — swallowed Tigris/scoring errors, silent quality degradation (consistent with the W64 asyncpg silent-death scar family and the `discovery_wr2` "upload error inghiottito in rejection_reason" finding).
**RED-TEAM DOWNGRADE — EXAGGERATED:** The VLM gate is a **subject-match** guard (1.0=right subject, 0.0=wrong subject), NOT a variety/brand guard — its own instruction says "editorial reinterpretations of the same subject still score ≥0.6," so a *healthy* VLM accepts monotone on-subject images too. Fail-open is not the causal lever for "same thing." Ship as a P1 robustness finding; point the monotony causation at #3 (BRAND_SUFFIX), not here.
**Fix:** Make the VLM scorer fail-CLOSED in production (retry/reject on scorer error) and tag drafts `vlm_unscored=true`. Distinguish "scorer unavailable" from "scored 1.0."

### #5 — P0 · Live output is ONE hardcoded Canva master template — zero layout/background variety by construction
**What:** Every live carousel is a text-swap of a single gray design.
**Evidence:** `pending_builder.py:86-92` "Master ID: DAHJSqJOIO8 · 11 pages · gray Bali-Zero brand background" / `TEMPLATE_DESIGN_ID = "DAHJSqJOIO8"` (verified verbatim this run). `slides_to_operations` emits only `replace_text` + upload-asset ops into fixed slots — no background/layout/color op exists.
**Impact:** This IS the sameness complaint. No carousel can look structurally different — only words and 4 hero photos change. "Variety in tone and dynamics" is physically impossible on this path.
**Fix:** Build 3-5 distinct master templates; `build_canva_pending` selects one per carousel by archetype/register. Even 2-template alternation breaks the monotony immediately. Red-team: **CONFIRMED** (P0).

### #6 — P0 · The fact-check stage is theater — verifies the LLM draft against itself
**What:** The fact-checker's designated "primary truth" (`research_json`) is never written by any pipeline, so verification self-references the slides that asserted the claims.
**Evidence:** `wr2_fact_checker.py:373-386` treats `research_json` as primary truth (docstring :28-30); `grep -rln research_json scripts/wr2_*.py` returns ONLY the fact_checker (verified — no writer). `_persist_ready` (`wr2_draft_generator.py:777-791`) writes slides/register/council_debate but NOT research_json. So research_json is always NULL → the only source text is the slide bodies themselves. Plus `LAW_PATTERNS` (`wr2_fact_checker.py:90-98`) covers only PP/PMK/KEP/PENG/UU/Perbup/Perda — it OMITS Permenkumham, Permenimipas, Permen, Perpres, Pasal (verified) — the exact citation classes in visa carousels, which then fall to a self-substring "verified" match.
**Impact:** This is *how* the Golden Visa 3 errors shipped: a number-right/label-wrong claim, an omitted cheaper tier, and a wrong-but-real law citation all pass because the draft is verified against the draft. Omissions (the missing 7×-cheaper E28C tier) are structurally invisible — no claim, nothing to flag.
**Fix:** (1) Persist real NB-1/4/5 ground truth into research_json BEFORE fact-extraction, OR have the fact-checker query NB itself. (2) If `research_json IS NULL`, NEVER return `pass` — emit `degraded`/`fail`. (3) Add Permenkumham/Permenimipas/Pasal/Permen/Perpres regex + kill the self-substring fallback for law claims. (4) Add an attribution check (code X ↔ correct instrument). Red-team: **CONFIRMED** (P0).

### #7 — P0 · Canva renderer accepts pre-fact-check drafts — the "locked to checked" gate doesn't exist in SQL
**What:** A draft renders (and can publish) before the fact-checker ever reaches it.
**Evidence:** `wr2_canva_desktop_apply.py:161-171` `WHERE status IN ('drafts_imaged','drafts','drafts_imaged_facted','drafts_imaged_checked')` (verified verbatim, with the "Bug fix 2026-05-20" comment widening it). Contrast `wr2_supervisor.py:80` docstring "filter is locked to drafts_imaged_checked." The renderer is a separate cron (ORDER BY created_at ASC) and races the fact-checker (MAX_DRAFTS_PER_RUN=3); it can win. Fact stages are also opt-in kill-switches (`system_settings.<key>=='true'` required, else silent exit 0) and the only semantic check (`WR2_FACT_CHECKER_LLM`) defaults FALSE.
**Impact:** The entire fact-check stage is bypassable by timing or by a missing settings row. Plausibly how the Golden Visa carousel reached IG with no `pass` verdict.
**Fix:** Set eligibility to `status = 'drafts_imaged_checked'` only; make fact stages default-ON (explicit disable, not explicit enable); default LLM cross-check ON for law/number/date claims; CI test asserting the canva-apply status set ⊆ {drafts_imaged_checked}. Red-team: implied by the corroborated fact-accuracy dissection (P0).

### #8 — P0 · Constitution Art 10.5 makes VARIETY a hard fail — the opposite of the owner's request
**What:** The constitution encodes determinism as a brand value.
**Evidence:** `constitution.md:249` (verified verbatim) — "**10.5 Idempotency**: re-running the same brief must produce semantically equivalent output (same slide count, same hero indices, similar copy length). Random-walk drift = hard fail." There is no countervailing rule requiring two carousels on similar topics to differ.
**Impact:** The owner asks for variety; the constitution makes the opposite a hard fail. Any subagent/critic taking 10.5 seriously is forbidden from producing a meaningfully different carousel for a recurring topic family. The system is graded on consistency, then blamed for monotony.
**Fix:** Scope 10.5 to FACTS + STRUCTURE only (slide count, citations, key numbers stable). Add 10.6: "Two carousels in the same domain within 14 days MUST differ in dominant register AND image-style mode — sameness = soft fail." Flip the polarity: no-drift = fail. Red-team: corroborated by the constitution dissection (P0).

### #9 — P1 · The critic is a punishment-only conformance policeman — it can never reward distinctiveness
**What:** 5 rubrics, all failure-detection; a perfectly compliant, utterly boring carousel scores 100/100 and PASSES.
**Evidence:** `wr2-critic.md` — 33 "hard fail" + 17 "soft fail" mentions; grep for `memorable|thumb|forward|scroll-stop|original|surprising|boring|dynam|repetit` returns ZERO substantive hits. `wr2-critic.md:264` "PASS only if every slide is PASS AND carousel_level_failures is empty." `wr2-critic.md:274` "Never invent rules… score 100 on that dimension" — novelty is un-penalized but never rewarded.
**Impact:** A pure-prohibition gate has one stable attractor: the output that trips zero rules — the minimal-risk, maximal-compliance template. This is the mechanical engine of "safe and boring always passes."
**Fix:** Add a 6th rubric "Editorial distinctiveness/forwardability" — the ONLY rubric where a carousel GAINS points, scored vision-subjectively, where bland-but-legal work can FAIL: (a) Art 6.10 "would a follower forward this to their accountant?"; (b) register differs from last 2 published; (c) ≥1 structural surprise. Red-team: corroborated (P1).

### #10 — P1 · Anti-monotone machinery is entirely aspirational — `topic_type_log` is never created or written
**What:** The flagship inter-carousel rule (Art 5.8 "no two consecutive carousels same dominant mode, critic checks topic_type_log last 2 published") has no backing data.
**Evidence:** `constitution.md:86` names topic_type_log. Grep: ZERO `INSERT/UPDATE topic_type_log` sites; the table is defined ONLY in `_state-schema.sql:63` (a standalone SQLite file, not in `migrations_v2/`) and read via a `LEFT JOIN` in `_voyager-curriculum.py:49` (which also joins across a different DB engine than the runtime `wr2_carousel_runs` Postgres table). The image-prompt-author's required input #3 ("modes used in last 2 published") is never supplied — `wr2_carousel_orchestrator.py:322-330` sends only `{carousel_id, topic, step, prior}`. There are even TWO contradictory unenforced rules (5.8: 0 consecutive repeats; 13.4: up to 2 allowed).
**Impact:** The rule built specifically to prevent the S11 "12 consecutive desk-document carousels" failure can never fire — it's a LEFT JOIN against an empty/absent table, so "last 2 modes" is always NULL.
**Fix:** Make topic_type_log real and populated on the PRODUCTION path (Postgres migration keyed to the live table; write dominant_mode at publish; query last-2 before authoring imagery; hard-reject repeats). Reconcile 5.8 vs 13.4 into one rule. Red-team: corroborated (P0/P1 depending on live path — see #1).

---

## 3. PER-DIMENSION BREAKDOWN

### Code quality
~12k LOC, battle-scarred — nearly every function carries a dated "Fix 2026-05-15 [Gemini/Codex find]" comment (reactive patching, no refactor). Two pipelines duplicate infrastructure with no shared module: `_send_telegram` ×7, `_upload_to_tigris` ×2, Codex env-strip ×2, `_CRITIC_JSON_FENCE_RE` defined twice in one file (`orchestrator.py:51` and `:648`). ~80 broad `except Exception`. The "Imagen Ultra" provenance lie is **CONFIRMED** (P1): `wr2_draft_generator.py:884` hardcodes `cover_status = "OK (Imagen Ultra)"` while the cover is actually Codex gpt-image-2 / Gemini Nano Banana — no Imagen call exists; `build_imagen_prompt`/`NEGATIVE_PROMPT` are dead. Stale `claude-opus-4-7` in 9 sites vs current `claude-opus-4-8` (P2). The Pipeline-A publish glob bug (`slide_*.png` vs `{NN}-rendered.png`) is real but **DOWNGRADED to P2/P3** by red-team: `publish_after_approval` has zero callers; the Telegram approve handler never invokes it, so flipping `WR2_AUTO_PUBLISH_ENABLED` triggers nothing — it's latent dead-code, not a "would-ship-empty-on-flag-flip" P0. `canva_pdf_render.py` is a 1548-LOC god-module: 14 copy-paste layout renderers, hardcoded magic-number geometry (`y_head = H-130`), `print(…,file=sys.stderr)` instead of `logger` (Golden Rule #8 violation — the load-bearing "hero image missing, rendering on bare antracite" warning at :524 goes to raw stderr).

### Architecture
The master cause. The 8 subagents + design-architect orchestrator are coordinated ONLY in the prompt layer; in production that layer never runs (#1, #2). The Python orchestrator bypasses `wr2-design-architect` entirely (PIPELINE_STEPS lists 5 agents, design-architect absent — verified this run) — **CONFIRMED, but red-team REFRAMED**: the contract-ENFORCER and self-audit layer is genuinely orphaned, BUT "brand cortex never loads" is false — each of the 5 specialist subagents declares `skills: bali-zero-brand` and self-loads constitution/voice/tokens, and the renderer loads tokens.json. So reframe as "the contract-enforcement layer is bypassed," not "no brand DNA enters." The critic runs BEFORE rendering (`orchestrator.py:769-803` critic loop, then `render_playwright` at :806 — verified) so it judges PNG/PDF files that don't exist; worse, `wr2-critic.md:111` tells it to Read `apps/war-room/output/...` but the orchestrator writes to `~/.claude/carousels/...` — **CONFIRMED, doubly nonexistent path**. Critic retry is a no-op (re-runs critic on byte-identical artifacts, never regenerates — **CONFIRMED**); a hard FAIL dead-ends with zero retries while only soft-fail loops, contradicting `wr2-critic.md:268` "Hard fail = retry max 2" (**CONFIRMED**). Contracts B (NB ground-truth) + C (no-silent-reuse) have ZERO enforcement; Contract A (fan-out) has no named self-check but is structurally non-violable (**CONFIRMED with that precision**). Stale model pins downgrade the image-prompt-author from its intended `opus` to `claude-sonnet-4-6` (**CONFIRMED**).

### Step brief/story (1-2)
The maieutic stage does not run live (#1, **CONFIRMED P0**). Even in Pipeline A, the brief-interpreter commits "costume before story": it fixes archetype + register from a shallow keyword/"topic flavor" map at brief time, before narrative reasoning (`wr2-brief-interpreter.md:68-76, 97`), and the storyboarder consumes it "verbatim" as default (**CONFIRMED P1** — and the live `wr2_draft_generator.py:142` independently hardcodes "analitico … (default for tax/visa/regulation)," funneling a tax/visa shop's entire output into the driest register). The live "fixed 11-slide template" claim is **DOWNGRADED to P1 (EXAGGERATED)**: the validator (`wr2_draft_generator.py:706-708`, verified this run) accepts a 6-11 RANGE, not a frozen 11, and the 2 mid-heroes are model-chosen with slides 3+6 forced only as a fallback when ≥11 slides. The substance survives — no archetype dimension, one editorial skeleton. Schema mismatch (`fact_extractor` reads `index`/`title`, generator writes `slide_number`/`headline`) mis-tags every claim to slide 0 (P2). No NB query at brief time (P1). Body-length spec self-contradictory (280-char hard cap vs ~50-70 words target vs 500-char code truncation) (P3).

### Step layout/image (3-4)
Live renderer defaults EVERY non-cover slide to `photo-headline-yellow-sub` on antracite (`wr2_canva_pdf_render.py:1405` fallback; Pipeline B emits only `slide_type`, never `layout_family`) — this IS the owner's complaint, mechanically (**P0**, where the orphan renderer is concerned). 6 layout families are advertised to the storyboarder + registered in tokens.json but have NO skill-library `.md` file (verified: `layouts/` has 9 specs; three-verdicts/stat-card-hero/thin-red-rule-divider/swiss-grid-asymmetry/monospace-evidence-block/framing-question are MISSING) — the composer hard-aborts on them, shrinking the real pool (P1). No "cover-as-scene/trompe-l'oeil" layout exists anywhere (P1). Yellow-number coloring is a blunt topic-blind regex (P1). Antracite bg is hardcoded at the top of all 14 render functions (P1). The constitution's own sanctioned variety device (swiss-grid-asymmetry, Art 15.2) has no spec.

### Step critic
See #9. The single anti-monotone check (Art 5.8) is soft-fail-only, image-mode-only, and Pipeline-A-only. The only fact-check is a capped (3-query), PASS-by-default NB-INTEL spot-check that cannot catch omissions or plausible-wrong attributions — explains the Golden Visa errors. Binary gate is structurally pass-biased: quality soft-fails route to a "human review queue" with no evidence of a consumer. All corroborated.

### Constitution
~80% prohibitions, empirically: 30 "hard fail" + 23 ban-keywords vs a handful of weak generative rules — and every variety-enforcing rule is SOFT while every safe-template-enforcing rule is HARD (severity asymmetry selects for monotony). Art 10.5 (#8) and Art 13.3 (`regulatory-explainer` default = the always, for a visa/tax shop — verified verbatim) are the smoking guns. Art 13 pre-cables register+layout+image from a category lookup BEFORE the idea. The constitution learned the wrong lesson from S11 — it banned symptoms (parchment, Dalí) not the disease (no positive variety grammar). Palette monotony (antracite/white/yellow) is genuinely constitutional (Art 2 + 14.4) and a legitimate brand asset — the problem is ALL other variety axes are also throttled, leaving nothing to differentiate (P2). The 9/8/7/10 vocabulary (modes/archetypes/registers/layouts) collapses to ~1 of each in practice (P2).

### Voice/editorial
The live path runs a divergent voice spec reading NONE of the cortex (P0, **CONFIRMED**). The cortex canonizes dictionary-register words ("perimeter" as a "signature term," "rescinded," "impunity") as gold-standard — the inverse of the owner's "popular in voice" (P1, **CONFIRMED**). Title discipline is "max 60 chars" never "3-4 words." The canonical closing slide literally instructs "Link in bio" — a phrase the constitution hard-fails on slides (P1, verified: `wr2_draft_generator.py:250`). The live path is even hardcoded to write "OUR READ:" and "WHAT THIS MEANS FOR YOU" — both on the storyboarder's banned-filler list (P1, verified). No "1 rule + 1 consequence + 1 action" structure (Art 6.9) on the live path. No register-rotation memory.

### Anti-monotony
Almost entirely aspirational (#10). The image-prompt-author's load-bearing input ("modes in last 2 published") is never supplied (**CONFIRMED P0**). The voyager curriculum joins tables across two different databases reading columns nothing writes. Mode selection is steered by a frozen 8-sample "empirical" ranking from 2026-05-12 whose refresh loop has emitted "insufficient-data" for 3+ weeks (including 2026-06-01). Intra-carousel ≥3-modes is self-attested by the LLM with no code assertion.

### Commercial
WR2 has no commercial spine. No `service_sold`/`offer`/`price`/`cta_destination` field anywhere in the brief or slide schema (P1). Topic selection scores news-freshness only, never "which keyword maps to a profitable service" (P1). The only CTA is one hardcoded generic line, identical regardless of topic/audience/service (P1). The constitution bans the entire conversion vocabulary (Art 6.6/6.7) without providing a compensating service-routing mechanism (P2). Daily metrics track only pipeline throughput — zero saves/shares/leads despite the constitution declaring Saves+Shares the KPI (P2). The caption (the ONLY place a service CTA + link-in-bio is permitted) is never constructed and its publish function is uncalled (P2). audience_segment is captured but never used to differentiate the offer (P3). Latent risk realized: polished posts that can go viral and sell nothing.

---

## 4. ROOT-CAUSE SYNTHESIS

1. **The two-pipeline split (architectural).** The brand built a sophisticated variety/quality/fact machine (Pipeline A) and then shipped a different, dumber machine (Pipeline B). Every other finding is a symptom of this. The cure exists; it is unplugged and crash-looping on a phantom channel. **Fixing variety in a pipeline that doesn't ship is wasted work — confirm the live path first (it is B), then act on B.**

2. **The constitution rewards sameness and only punishes deviation.** Art 10.5 makes variety a hard fail; Art 13.3 defaults everything to the d/riest archetype; the critic has no positive-variety rubric and the anti-monotone rules are all soft while the template-enforcing rules are all hard. A generator optimizing to pass converges on the safe template. This is a *grammar* problem, not a tuning one.

3. **Determinism is hardcoded at the render and prompt layers.** ONE Canva master template (`DAHJSqJOIO8`), ONE `BRAND_SUFFIX` clamping every image to "deep charcoals and warm ochre," ONE fixed editorial skeleton ("Our read:" → "What This Means For You"), and a renderer that defaults every interior slide to one antracite layout. The output is geometrically and tonally identical run-to-run by construction.

4. **No persisted cross-carousel memory.** `topic_type_log` is never written; the anti-monotone "last 2 published modes" check is a LEFT JOIN against an empty table. The system literally cannot know what it just published, so it cannot avoid repeating it.

5. **The fact-checker verifies the draft against itself.** `research_json` is never populated, NB is never queried on the live path, and the renderer accepts pre-fact-check drafts. There is no external ground truth in the loop that ships — which is precisely how the Golden Visa errors (wrong label, omitted cheaper tier, mis-cited Pasal) passed.

---

## 5. PRESCRIPTION (highest-leverage first)

**P-1 (kills 60% of the complaint): Consolidate to ONE pipeline, and make it brand-cortex-aware.** Decommission the dead Pipeline A dispatcher (it crash-loops on a phantom channel) and port its organs INTO Pipeline B — OR wire `wr2_topic_selector.py` to `NOTIFY topic_ready` and route live IG through the orchestrator. Either way, the path that ships MUST run: archetype selection, register reasoning, NB ground-truth query, and a critic. This single decision unblocks all of P-2..P-6.

**P-2 (kills the visual sameness directly): Break the three hardcoded determinisms.** (a) Build 3-5 distinct Canva master templates and select per-carousel by archetype — even 2-template alternation works immediately. (b) Parameterize `BRAND_SUFFIX` by per-slide `tonal_palette`; strip the "deep charcoals and warm ochre" clamp; keep only 4:5/no-faces/photoreal universal. (c) Make Pipeline B emit `layout_family` per slide so the renderer stops defaulting every interior slide to photo-headline-yellow-sub (and change that fallback from silent-default to a hard error).

**P-3 (fixes the grammar): Flip the constitution's failure polarity.** Rewrite Art 10.5 to scope idempotency to facts+structure only, and add a positive rule requiring register + image-mode variation across a domain window (no-drift = soft fail). Remove the Art 13.3 `regulatory-explainer` static default — make archetype a required, justified choice. Add critic Rubric 6 "Editorial distinctiveness" as the ONLY point-gaining, can-fail-bland-but-legal rubric. Promote the anti-monotone rules (5.8/13.4, reconciled) from soft to HARD fail.

**P-4 (real anti-monotone): Persist cross-carousel memory.** Create a Postgres `topic_type_log` keyed to the live table, written at publish with dominant_mode + register + layout_family. Inject "last 2 published modes/registers" into the generator/image-author prompt and hard-reject a repeat. Add a code-level assertion (≥3 distinct image modes per carousel) instead of trusting the LLM's self-attestation.

**P-5 (stops shipping wrong facts): Give the fact-checker external truth and teeth.** Populate `research_json` with NB-1/4/5 ground truth before fact-extraction (or query NB in the checker). Add Permenkumham/Permenimipas/Pasal/Permen/Perpres regex; kill the self-substring "verified" fallback for law claims; add an attribution check (code ↔ instrument). Add an omission/coverage check (diff carousel facts vs the canonical fact-set — catches the missing E28C tier). Lock canva-apply to `status = 'drafts_imaged_checked'` only and make fact stages default-ON.

**P-6 (matches the owner's voice + adds a commercial spine): Fix the live prompt and add service routing.** Forbid "OUR READ/WHAT THIS MEANS FOR YOU" and "link in bio" on slides; add a popular-voice register layer with a readability ceiling; enforce 25-50-word bodies and 3-5-word covers as validators (regenerate, not silent-truncate). Add a `commercial_target {service_line, offer, cta_destination}` block to the brief, branch the closer + IG caption per audience_segment × service, and instrument saves/shares/lead attribution in daily metrics.

> **Bottom line:** WR2's best output is impossible today not because the model is weak but because the shipping pipeline is a text-swap engine over one frozen template, governed by a constitution that grades consistency and a critic that only knows how to say "no." Make the cure (Pipeline A's organs) actually run, break the three hardcoded determinisms, and flip the constitution from punishing variety to requiring it — then WR2 can produce carousels like the owner's own best ones instead of antracite sameness.
