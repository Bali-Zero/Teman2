---
date: 2026-06-05
domain: operations
subject: wr2-P1-pipeline-consolidation-rev2
status: SPEC rev2 — POST 3-deep panel (Codex+DeepSeek+NB-1), every claim re-verified on aligned origin/main
client_case: n/a
author: orchestrator (Opus 4.8) + 3-deep panel + per-claim live re-verification
sources:
  - research/operations/P1-pipeline-consolidation-spec.md (rev1, this supersedes)
  - research/operations/2026-06-04-wr2-autopsy-report.md (P-1 prescription)
  - research/operations/W66-wr2-autopsy-deferred-spec.md (Route 1A vs 1B)
  - 3-deep panel 2026-06-05 (Codex GPT-5.5, DeepSeek V4 Pro via devils-advocate, NB-1 via nb-curator)
---

# P-1 rev2 — Consolidate to ONE brand-cortex-aware pipeline (Route 1A)

> rev2 supersedes rev1. rev1 was reviewed by a 3-deep panel; this rev applies the
> surviving findings AND corrects rev1's own factual errors caught by re-verifying
> every load-bearing claim on an origin/main-aligned worktree.
> The panel itself was unreliable per-panelist — Codex got 3 of its 5 factual claims
> WRONG (all from a stale read: it claimed image_mode isn't persisted, fact-checker
> doesn't read brief_json, and migrations stop at 205 — all FALSE on live main). The
> orchestrator's independent re-grep is what separated real findings from stale-state
> hallucinations. Lesson re-applied (see 0.1).

## 0. Verified reality (origin/main @ 0db878623, 2026-06-05) — re-checked file:line

Pipeline A (wr2_carousel_dispatcher.py -> wr2_carousel_orchestrator.py -> 5 subagents
-> critic) is DEAD CODE (dispatcher + telegram-gate both launchctl exit 75,
crash-loop on phantom Postgres channel topic_ready, 0 producers). Its quality organs
live as subagent prompts (.md), not Python:
~/.claude/agents/wr2-{brief-interpreter,storyboarder,critic,design-architect}.md.
We do NOT resurrect it (Route 1B rejected). Route 1A ports its VALUE.

Pipeline B (the LIVE path, all Python cron): wr2_topic_selector.py ->
wr2_draft_generator.py -> wr2_image_generator.py -> wr2_fact_checker.py ->
wr2_canva_desktop_apply.py -> rendered (manual publish by Damar — Legge 5).

What the live path ALREADY has (re-verified on aligned main — corrects rev1 AND the panel):
- register IS chosen by the model in-prompt (SYSTEM_INSTRUCTIONS "pick ONE of 7"),
  validated _normalise_slides:714 (VALID_TONES), persisted to war_room_drafts.register.
- layout_family IS per-slide (model picks; renderer dispatches via
  LAYOUT_DISPATCH.get(family); the 4 P-2a families — stat-card-hero,
  thin-red-rule-divider, swiss-grid-asymmetry, monospace-evidence-block — are ALREADY
  merged, wr2_canva_pdf_render.py:1188/1251/1291/1329, registered 1396-99).
- image_mode IS emitted + persisted (P-4, PR #1133): SYSTEM_INSTRUCTIONS
  wr2_draft_generator.py:177/265/284/294 (9 Art-5.8 modes, MANDATORY per hero),
  whitelist _normalise_slides:774. wr2_topic_type.derive_dominant_mode:175 reads it.
  Codex's "not persisted" was a stale read — FALSE.
- tonal_palette IS emitted (batch-1) — distinct from image_mode (palette = photo
  colour look; image_mode = one of 9 scene/style modes). Both on main.
- The fact-checker DOES read brief_json as external truth: wr2_fact_checker.py:209
  _has_external_truth(... brief_json=...), :271 for blob in (research_json, brief_json,
  council_debate_json), SELECT :507 includes brief_json, fail-closed when all empty
  (#1112 + P-5). Codex's "reads research_json only" was reading stale docstrings
  (lines 24-37) — FALSE.
- topic_type_log (migration 216, on main) records domain+register+dominant_mode+
  layout_family at rendered; anti-sameness Art 10.6 enforceable behind
  WR2_ANTIMONOTONE_ENFORCE (default OFF until the table fills).

What the live path GENUINELY LACKS (the real P-1 gap, narrowed by verification):
1. Archetype — NO archetype is selected or persisted. war_room_drafts has no
   archetype column; grep archetype wr2_draft_generator.py = 0. THE missing organ
   (constitution Art 13, 9-row table — see 0.2).
2. A critic/quality gate on the live path — wr2-critic.md is invoked ONLY by the dead
   orchestrator. The live path has NO rubric gate before rendered. (The fact-checker
   is a FACT gate, not a brand/distinctiveness gate.)
3. The storyboarder's STRUCTURAL discipline — the live generator's SYSTEM_INSTRUCTIONS
   enforce cover/hero-count/tonal/image_mode, but NOT the storyboarder's
   cover-empirical-anchor (Art 6.9), S-pattern (rule+consequence+next-step),
   bullet-promise (Art 6.3), slide-2 framing-question, or the
   photo-headline-yellow-sub MAX-2 cap. grep for these in the generator = 0. rev1
   silently dropped this; rev2 makes it explicit scope (2 PR-1b).
4. Real NB ground-truth — brief_json is the scraped article + enrichment, NOT a
   NotebookLM query. The brief-interpreter's NB-grounding never runs on the live path.
   So the fact-checker's corpus is "background reading", not authoritative regulatory
   truth (and it can't tell the difference — see 2 PR-1 fix D1).

### 0.1 Anti-hallucination note (load-bearing)
This rev was written AFTER the orchestrator nearly built a phantom "image_mode is
missing" PR on a stale worktree read. The broker's agent_start.py based the worktree
on a commit PRECEDING P-4; grep on that checkout returned 0 image_mode hits; only
git reset --hard origin/main on the worktree revealed the 7 real hits. Rule
re-applied: a worktree checkout is NOT authoritative for "what's on main" until
aligned to the ref. Re-grep after alignment before trusting any absence. The same
trap hit Codex (3 false claims). Treat every panelist file:line as a LEAD.

### 0.2 Corrected archetype table (constitution Art 13, verified by nb-curator)
The constitution prose says "8 archetypes" but the Art-13 TABLE has 9 rows (the table
is authoritative; the "8" in prose is stale — flag to amend Art 13.1 -> "9"). Ranges
that BREAK the global Art-1.2 "7-10" floor (these are the danger archetypes):

| Archetype | Slides | Register pool | Image mode | Floor risk |
|---|---|---|---|---|
| regulatory-explainer | 8-10 | tecnico+analitico | desk-document | safe |
| news-flash | 4-6 | analitico+militante | event-photo | < floor 6 |
| quote-led | 6-8 | rituale+poetico | architecture/texture | edge (6) |
| anti-cliche | 5-7 | ironico+militante | provocation-photo | < floor 6 |
| story-driven | 8-10 | pedagogico+tecnico | human-silhouette+doc | safe |
| comparison | 7-9 | analitico+pedagogico | object-comparison | safe |
| calendar-tracker | 6-8 | analitico | calendar-photo | edge (6) |
| testimonial-data | 5-7 | rituale+tecnico | data-visualization | < floor 6 |
| cultural-insight | 7-9 | poetico+pedagogico | cultural-photo | safe |

## 1. Goal & non-goals
Goal: the path that ships runs, in order: NB ground-truth -> archetype selection
(NB-informed) -> register (already there, tie to archetype) -> storyboarder
structural compose -> critic/quality gate -> image/fact/render. Decommission dead
Pipeline A.

Non-goals: resurrecting the orchestrator (1B — rejected); renderer god-module refactor
(P-2a neighbourhood — its 4 families already merged); a real publish-to-IG signal
(Legge 5 — stays manual). Commercial spine = P-6 (W66).

## 2. Route 1A — port A's organs INTO Pipeline B, as Python, on war_room_drafts
Each organ = a Python step reading/writing war_room_drafts (the live store), NOT the
orchestrator's filesystem. ONE atomic PR each. PR order changed from rev1 per
nb-curator finding (archetype needs NB facts first).

### PR-1 (FOUNDATION, was rev1 PR-2): real NB ground-truth into brief_json
Moved first because the brief-interpreter picks the archetype AFTER seeing NB facts —
archetype-on-scraped-article-only degrades fidelity (nb-curator concern #2).
- Python helper: given the topic's domain (derive_domain), run nlm query against the
  CORRECT NB (corrected routing — rev1 was wrong):
  - visa/immigration -> NB-2 (cff93ab0)  [rev1 said NB-1 — WRONG, that's codebase]
  - tax -> NB-4 (d4b2eedb)
  - property -> NB-5 (d9438180)
  - regulatory -> NB-INTEL Regulation (a17f134e) + NB-3 (933509f9) for KBLI/PMA
    [rev1 said NB-1 — WRONG]
- Write verbatim facts/citations into brief_json.nb_ground_truth (a NAMED key, not the
  blob) BEFORE fact-extraction.
- Fix D1 (DeepSeek MEDIUM): the fact-checker currently reads the whole brief_json
  blob, so it can't distinguish NB truth from the scraped article (circular). PR-1
  MUST also: (a) add brief_json.nb_ground_truth_sourced: bool, (b) make the
  fact-checker PREFER nb_ground_truth when present, (c) emit a flag when NB was absent
  at compose time. Otherwise PR-1 is latency with no benefit.
- Risk #2 handling: NB query is best-effort + hard timeout (e.g. 20s); on
  timeout/degradation fall back to today's behavior (never block the draft). NB-INTEL
  is degraded post-UUID-switch — most queries may fall back; the value is the rare
  authoritative hit, acceptable AS LONG AS D1's flag tells downstream which case.
- Bipolar-verifier (1 LLM + 1 NB), NOT a 4-LLM council per query. Local/OAuth — no
  PII to paid cloud (Law 2).

### PR-2 (was rev1 PR-1): archetype selection + storyboarder structural rules
Now NB-informed (depends on PR-1's nb_ground_truth).
- Migration: archetype TEXT column on war_room_drafts (additive, nullable,
  Squawk-safe, next free number — verify >=217 at impl, NOT 206).
- Python select_archetype(topic, brief_json_with_nb) -> {archetype, register_hint,
  rationale} — picks ONE of the 9 (0.2 table) from topic + NB facts. Port the
  brief-interpreter's LOGIC into a helper + ONE Claude OAuth CLI call (MAX quota;
  never the dead per-agent subprocess fan-out).
- Wire into draft_generator: pass archetype into the compose prompt; branch
  slide_count / register-pool / layout-pool / hero-count on the archetype's 0.2
  ranges. Persist archetype. Add to the topic_type_log write (anti-sameness can vary
  archetype too).
- PR-1b inside PR-2 (DeepSeek A / NB concern — the storyboarder is NOT optional):
  embed the storyboarder's structural rules into SYSTEM_INSTRUCTIONS (or a
  post-compose validator on slides_json): cover-empirical-anchor (Art 6.9, hard fail
  if none of the 6 anchors), slide-2 framing-question, S-pattern (>=1 rule +
  >=1 consequence + >=1 next-step slide), bullet-promise (Art 6.3),
  photo-headline-yellow-sub MAX-2 cap. Without these, an archetype is a label on an
  unstructured compose — a regression vs the dead Pipeline A.
- Risk #1 — THE BLOCKER (Codex+DeepSeek HIGH, re-verified HARD): there is a HARD slide
  floor of 6 (wr2_draft_generator.py:707 raises <6; pending_builder.py:311
  MIN_SLIDES=5). The 3 short archetypes (news-flash 4-6, anti-cliche 5-7,
  testimonial-data 5-7) can emit 4-5 slides -> raise ValueError BEFORE Canva. AND the
  "carousels shorter than 11 -> wipe trailing pages -> IG auto-crops blanks" path
  (pending_builder.py:170-178) is an UNTESTED ASSERTION (a code comment, zero test
  proves IG actually absorbs the blanks vs a 4-page-then-7-blank mess). Mitigation in
  PR-2: scope archetype selection to slide_count >= 6 archetypes ONLY
  (regulatory-explainer, quote-led, story-driven, comparison, calendar-tracker,
  cultural-insight + clamp the 5-7 ones to 6-7). news-flash@4-5 stays DEFERRED until
  the short-carousel empirical test (4) proves the wipe path OR the skill gains true
  first-N page export. Do NOT ship an archetype that can produce <6 slides until that
  test passes.

### PR-3: a critic/quality gate on the live path  [BLOCKED until consumer exists]
- Port wr2-critic.md's rubric into Python critic_gate(draft) -> {verdict, per_rubric,
  reasons} AFTER compose, BEFORE drafts_imaged_checked. ONE Claude OAuth call (text
  rubrics v1; vision on rendered PDF later).
- Add NEW Rubric 6 "editorial distinctiveness" (batch-1 P-3 prescribed it) — the ONLY
  rubric that can REWARD a braver carousel; must PASS bland-but-legal, just not reward
  it (Risk #3 — punishment-only gate is the current failure mode).
- BLOCKER (DeepSeek C, re-verified): a critic_review_required status has NO consumer —
  wr2_canva_desktop_apply.py:669 consumes only
  ('drafts_imaged','drafts','drafts_imaged_facted','drafts_imaged_checked'). Shipping
  the gate without a consumer silently strands carousels (identical to the dead-end
  fact_check_failed the autopsy flagged). PR-3 is NO-GO until: (a) the new status value
  is named, (b) either canva_apply skips-with-Telegram-alert on it OR a dedicated
  notifier watches it, (c) the regen state machine is designed (how a critic-failed
  row resets to briefed + clears slides_json for recompose, max-2 then human-review —
  never infinite block).

### PR-4: decommission dead Pipeline A (cleanup, do LAST)
- launchctl bootout + remove plists com.balizero.wr2.carousel-dispatcher +
  com.balizero.wr2.telegram-gate; archive wr2_carousel_orchestrator.py +
  wr2_carousel_dispatcher.py -> scripts/.disabled-2026-06-05/; remove the
  phantom-channel LISTEN. Update the wr2_worktree_gc.py:6 docstring (only live
  reference — NOT an import; verified zero live imports). Keep the subagent .md files
  (their LOGIC is now ported; prompts remain the reference).
- Only after PR-1..3 prove the live path carries the organs.

## 3. Sequencing & dependencies (revised)
- PR-1 first (NB ground-truth) — archetype needs it; also fixes fact-checker D1.
- PR-2 (archetype + storyboarder) — after PR-1 (NB-informed selection).
- PR-3 (critic) — after PR-2 AND after the consumer/state-machine design lands.
  Currently BLOCKED.
- PR-4 (decommission) — LAST, after 1-3 verified live.
- File-collision guard: PR-1, PR-2, PR-3 all touch wr2_draft_generator.py and/or
  wr2_fact_checker.py. MUST be sequential on those files (each rebases on prior merged
  state). P-2a (renderer, merged) + P-4 (merged) don't collide.

## 4. Gating empirical test — short-carousel (MUST run before any <6-slide archetype)
Submit a hand-built 4-slide canva_pending.json through the canva-apply skill on a
THROWAWAY Canva design. Observe: do pages 5-11 (wiped to blank) publish as a clean
4-slide carousel, or as a 4-page-then-7-blank mess? Document in research/operations/.
If mess/error -> short archetypes stay banned (clamp to 6). If clean -> the floor can
drop + news-flash unblocks. This is the deciding test for whether archetype-driven
slide_count is even compatible with the fixed-11 import. (Per operator decision
2026-06-05, this test is NOT in this autonomous batch — queued for when archetype PRs
are authorized.)

## 5. Operator gates (Legge 5 + charter SQUAD 3) — what is NOT autonomous-eligible
Per the user's Opt-1 decision (2026-06-05): the orchestrator executes to merge ONLY
the zero-IG-risk work. The following CHANGE what reaches Instagram and require an
explicit operator "go P-1" before implementation:
- PR-2 archetype going LIVE (changes what the path composes).
- PR-3 critic gate LIVE (new blocker on the shipping path).
- PR-4 decommission (removes the dead path — low risk but production-state change).
- The 4 short-carousel empirical test (touches a Canva design).

Autonomous-eligible now: this spec rev2 (docs), and PR-1's NB-ground-truth helper IF
scoped as additive infrastructure that does NOT change compose output (writes
nb_ground_truth + the D1 flag, fact-checker prefers it — but fails open to today's
behavior). Even PR-1 is borderline (it feeds the fact gate); flag to operator before
merging it. Default: STOP after rev2 + present this plan.

## 6. Out of scope -> tracked elsewhere
- Commercial spine / service routing -> P-6 (W66).
- Renderer god-module refactor -> adjacent to P-2a (4 families already merged).
- Real publish-to-IG signal -> future (Legge 5 manual today).
