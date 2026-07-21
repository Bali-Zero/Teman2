---
name: wr2
description: "WR2 corner — the live shared context for the War Room 2 editorial organism (intel → carousel → Instagram). Load BEFORE touching any WR2 script, the Control app, the queue, metrics, or brand surfaces — or when Zero says /wr2, 'war room', 'carosello', 'WR2'. Holds: the north star (a self-improving, facts-honest editorial machine), the anatomy map (every hot file/daemon/log), LIVE STATE, blood-bought rules, and the standing GROWTH LOOP mandate for no-stop improvement sessions."
---

# /wr2 — War Room 2 corner (project brain)

> Created 2026-07-17 on Zero's order after the facts-first ship ("crea la skill di contesto /wr2
> dove inserisci i file più importanti per avere un contesto caldo e pronto e dove possiamo
> continuare a fare crescere la wr2"). This file is the HOT CONTEXT shared by every Fable/Claude
> session and every Codex dispatch working on WR2. **Update §1 LIVE STATE whenever it changes —
> this corner is only useful if it stays true.**

## 0. What WR2 is + the north star

WR2 is Bali Zero's autonomous editorial organism: Indonesian regulatory/visa/tax intel →
grounded brief → 7-10 slide branded carousel → human review → Instagram. It spans a Python
pipeline (Pro launchd), a macOS review app (M5), a queue protocol (Pro SSOT + M5 mirror), a
metrics loop (IG Graph scrape → weekly analyst), and the brand cortex.

**Constitutional principle** ([[principle_wr2_codebase_app_indissoluble_2026_06_25]]): the WR2
codebase and the Control app are ONE organism — never evolve one side without the other.

**THE NORTH STAR: a self-improving editorial machine that is facts-honest by construction.**
Every carousel must tell a TRUE, CONCRETE story (facts-first — the 2026-07-16 "storia inventata"
incident is the founding scar), pass brand + accessibility bars, and feed measured engagement
back into the next editorial decision. Growth = the standing loop in §4.

**Legge 5 (absolute)**: publishing to Instagram is Zero's act. The pipeline stops at `drafted`
in the review queue. No session ever publishes autonomously.

## 1. LIVE STATE (last update 2026-07-19 — keep current)

**Shipped & proven (July 16-17 arc):** **typed Carousel IR + shadow-replay harness SHIPPED +
GATE PASSED (#2942, 2026-07-21, editorial-intelligence Phase 1)** — pydantic 11-kind discriminated
union projecting to explicit `layout_family` pins (composer.py:143-145), ADDITIVE (generator/composer
zero diff). Replay over ALL 61 historical decks: first-try valid 100%, 0 retries, 0 fails,
family-resolution 100% via the real `map_slide_to_family`, kind-mix non-degenerate (447 slides, prose
only ~8.7%) — red-team BLOCKER-1 (strict-schema regen spike) empirically refuted; evidence in
`_research/2026-07-21-ir-phase1-replay-metrics.json`. DISCOVERY (Phase-3 prerequisite):
source-citation `{{title}}` and elegant-close `trust_marker`/`reach`/`invite` placeholders are NEVER
substituted in `composer._fill_placeholders` — those 2 families render broken today; with the IR
routing cta→elegant-close and citation→source-citation (87/447 replay slides), the composer fix is a
Phase-3 PRE-REQUISITE, not incidental. Next: Phase 2 deterministic pre-gate (guilt+innocence corpus
per guard-conformance), then Phase 3 planner/writer dual-run. ·
complete-or-nothing gate (#2543 app / #2553 py) ·
take-label variety + vendored agent defs (#2544) · archive-aware M5 merge + reconciler repair
(#2563) · external-post registration + IG metrics FIRST LIVE on native carousels (#2578, hotfix
#2579, 49 entries backfilled with numeric Graph ids) · **facts-first + park backstop (#2598,
migration 245 `parked` on prod)** · capture ledger (#2581, #2609) ·
multi-path Pro ssh fallback in the M5 queue-pull wrapper (#2625 — scar #8: Tailscale/mDNS
alternate dying, 1102 timeouts logged; fallback probe + honest --once exit, proven live
2026-07-18) · **liveness rewire end-to-end (#2631, growth-loop B1) — carried the enricher's
live_news_score/liveness_tier/live_news_reasons through the 3-break contract chain
(scraper→ScraperSubmission→staging JSON→/pending projection), scar family #9; Codex red-team
round added projection normalization + score→tier derivation; PROVE-LIVE 2026-07-18: prod probe
submitted score=85 with NO tier, /pending returned 85/"breaking"(derived)/["probe reason"], then
rejected. Fly deployed, Pro ~/nuzantara blob-aligned, WR2_PREFER_LIVE_NEWS=true already armed** ·
**official `--rebrief <draft_id>` verb SHIPPED + PROVEN (#2667, growth-loop B5) — `_pg.rebrief_draft`
atomic reset (`status`→briefed + `fact_check_json`/status/at + `drive_url` + `html_render_attempts`=0 +
`canva_*` all cleared) mirroring `requeue_draft_for_rerender`; reconciler `--rebrief` one-shot guarded
by `lease_owner IS NULL` + a status whitelist (every literal mig-245-verified) + a queue-published
resurrection guard (reuses `wr2_rerender_requeue.check_queue_state` → refuses if the draft's queue
entry is published/published_with_edits — blood-bought #4). Codex red-team round added the queue
guard (BLOCKER it caught: rebrief of a DB-`rendered` draft whose queue entry was already published
would resurrect a live carousel). PROVE-LIVE 2026-07-18 BOTH sides on Pro: APPLY reset a real
`render_failed` draft (8e582ce0) to `briefed`, fact-check trio + attempts cleared (MCP-confirmed
delta); REFUSE left a queue-published `rendered` draft (4ca7b22b) byte-identical — exit-refused, zero
mutation. LIMITATION ledgered: the fact-extractor/checker lane takes no `lease_owner` CAS (unlike
render/image), so `--rebrief`'s lease guard cannot exclude a concurrent fact-lane run — low-risk
(rebrief resets upstream of the fact lane, extractor re-runs idempotently) but structurally
asymmetric** ·
**enrichment passthrough SHIPPED + PROVEN-LIVE (#2691, growth-loop) — killed `brief_json.enrichment={}`**:
the enricher's structured object (`the_facts`/`bali_zero_take`/`faq`/`thirty_second_brief`) was silently
dropped scraper→staging→drafts (scar family #9). Fix = 4-hop contract: `ScraperSubmission.enrichment`
field + `submit_from_scraper` persist + `list_pending_items` **opt-in** projection
(`include_enrichment=true`, never on archived — round-2 payload-fan-out fix) + `build_staging_payload`.
3 implementer rounds, 2 independent graders: Codex round-1 found 3 MUST-FIX (opt-in projection,
legacy-dirty-JSON `isinstance(dict)` type-guard, dedup enrichment-heal); a fresh-context Sonnet refuter
found the round-3 MUST-FIX (`_has_usable_source` unguarded `.get()` crash on a truthy non-dict) + a NICE
(dedup-heal status-gate) — used because Codex/agy/DeepSeek ALL failed the round-2 re-gate (Codex 30-min
hang, agy timeout, DeepSeek HTTP 402 balance-dead). PROVE-LIVE 2026-07-18 prod entity-match: submitted
`enrichment.the_facts` marker → `/pending?include_enrichment=true` returned it exactly, default
`/pending` omitted it, item cleaned. Fly deploy stalled ~90 min on GitHub-Actions runner starvation.
LIMITATION ledgered: dedup-heal is a lockless read-modify-write (pre-existing class, low risk).

**In queue awaiting Zero (Legge 5):** deportation carousel remake (`drafted`, 2026-07-17, tells
the real event) · **PMK 37/2025 "1 August" carousel now FULL-BAHASA, final-rendered 2026-07-18
(draft a80130df)** — native review Subhi+Ari complete (thread "[Review Bahasa]" 2026-07-17, 6/8
GO), Zero-delegated decisions: cover "PAJAKNYA SAMA. KASIRNYA GANTI." + closer accent word
"PERNYATAANMU"; reviewer amendments applied (slide-2 Ari rewrite, months spelled in full, slide-7
tail). Applied file-only via compose_carousel() on the Pro (same mechanism as the 2026-07-16 C2
apply; DB/queue untouched, queue `drafted`); EN version preserved in
`slides.bak-pre-bahasa-20260718/`. At publish, the IG caption MUST carry "Dikecualikan bukan
berarti bebas pajak — karena dipajaki di aturan lain" (not renderable on the slide, see template
findings below) + the sumber+kontak pattern.

**Open wounds / next targets:**

- **Adaptive-production program (2026-07-20).** Empirical DB diagnosis (30d corpus): kicker frozen
  30/30 on "Our read:" through 2026-07-15, then 3/3 on "THE SIGNAL" post-#2544 — same
  single-example-anchoring bug, one position over; narrative arc identical 33/33
  (`cover → take → body×N → CTA`) regardless of domain/liveness; cover subheads formulaic (3-example
  pool recycled); 4/9 layout families ever selected because the generator never emits the structured
  fields the other 5 need. **The one axis that varies is the one axis with a DB lookback armed
  (register/tone) — injected state beats stated intent, every time.** Kicker/subhead DB-lookback cure
  (generalizing the register/tone mechanism to those 2 axes) is IN FLIGHT in worktree
  `wr2-kicker-variety`, second red-team round as of this entry. Full 3-seat deep research (Kimi K3
  world-class-mechanisms + Gemini 3.1 Pro OSS-harvest + Codex sol-ultra architecture-review, +
  independent Fable visual review of the last 3 decks) archived at
  `_research/2026-07-20-adaptive-production-3seat-research.md`, with an adoption roadmap ruled by
  Fable as final gate: **Fase 1 (adopt now)** = typed Carousel IR (slide-shape contract:
  prose/statement/fact_stack/qa_dialogue/status_list/stat_card/citation) + Creative Ledger
  (per-draft decision-vector signatures, generalizing the kicker/subhead fix) + closer-contract unify;
  **Fase 2** = arc grammar + Planner/Slot-Writer split, gated on Fase 1; **metrics-gated** (n≥200) =
  feedback bandit + portfolio content matrix + art-direction cards; several items are **Zero-gated**
  (Legge 5/brand — franchise slot "The Bali Zero read", all-caps body doctrine, palette rotation).
  Codex fresh-eyes findings A-J on the live codebase: **finding A is the root cause of the CTA being
  absent on every single rendered deck** — the generator requires the last slide to carry a CTA while
  the `statement-bomb` layout contract explicitly forbids one and renders only a short statement;
  constitutional split-brain, not a copy-quality bug. **SHIPPED + PROVEN-LIVE (2026-07-20).** Kicker/
  subhead cure merged `84a1e347c0` (#2873); 3-seat research archive merged `6addafc333` (#2870).
  Deployed: both Pro checkouts (`~/Desktop/nuzantara` + `~/nuzantara-deploy`) pulled ff-only — the
  deploy checkout required removing a stale orphaned `.git/index.lock` (confirmed no live process
  held it via `lsof` before removal). `com.balizero.wr2.draft-generator` kickstarted; no briefed
  draft was queued at kickstart time (log: "No briefed drafts to process") so a full end-to-end
  generation could not be observed this session. PROVE-LIVE done via a direct function-level probe
  through the production wrapper (`wr2-script-wrapper.sh`, real secrets + `DATABASE_URL_LOCAL` via
  pg-proxy) against the real DB: `fetch_recent_editorial_signatures` returned the real historical
  signatures `KICKERS: ['THE SIGNAL', 'Our read']` (exactly the two pathological kickers the
  diagnosis found) + 8 real cover subheads; `_build_variety_steer` produced a 605-char steer block
  containing "MUST NOT"; `_render_system_instructions` showed zero token leaks
  (`__KICKER_EXAMPLES__`/`__KICKER_EXAMPLE_TAKE__` both absent from the rendered prompt). No
  synthetic draft was injected into `war_room_drafts` to avoid polluting prod editorial state (W96
  discipline) — the collision-regen-guard's full generation-loop behavior remains covered by the 93
  local tests (50 dedicated) rather than a live end-to-end run; this is the REMAINING natural-proof
  item, same pattern as the 2026-07-18 liveness wound (receptor = next natural draft generation, not
  forced). Both worktrees (`wr2-kicker-variety`, `wr2-research-archive`) reaped after confirming
  content-on-main via blob-per-file compare (W88 discipline) — GitHub had already auto-deleted both
  remote branches post-squash-merge.
- **Liveness live-pool — contract chain FIXED + PROVE-LIVE (#2631, 2026-07-18)**; the 0.0-for-all was scar #9 (fields dropped scraper→staging→/pending), not a scorer bug. Enricher already scored; now the values flow and `WR2_PREFER_LIVE_NEWS=true` is armed (filter min 40). REMAINING natural proof **DISTINGUISHED 2026-07-18 (growth-loop B): expected post-deploy TIMING, not a residual break.** No nightly has run on the #2631-patched code yet — the content scraper `com.balizero.intel.nightly` (StartCalendarInterval Hour=1, alive; REAL logs `~/.openclaw/workspace/logs/intel_nightly_YYYYMMDD.log`, NOT the Mar-3-frozen launchd stdout = scar #2 wrong-log) last ran 2026-07-18 01:00→01:55 on PRE-patch code (enricher/pipeline mtimes 02:23/12:52, both after the 01:55 finish; its log had 0 live_news emissions). Enricher classifier VERIFIED working: last night's `data/intel_output_latest.json` = 1 `developing` + 14 evergreen, scores 30/50 (OLD additive — the #2635 deterministic `_TIER_TO_SCORE`={breaking:90,developing:60,evergreen:0} landed with the 02:23 enricher update). Contract fields live in BOTH checkouts (`~/nuzantara` = nightly scraper root, `~/nuzantara-deploy` = WR2 daemon root; grep=4 each). E2E proven by composition (contract carries injected score = #2631 probe; enricher emits developing; both deployed). **RECEPTOR FIRED POSITIVE → WOUND CLOSED 2026-07-19 ~02:03 WITA.** The first post-patch natural nightly (`run_20260719_010004.json`, 25 articles / 15 classified) emitted **tiers {evergreen:12, developing:3}** with **distinct scores {0, 60}** — the DETERMINISTIC `_TIER_TO_SCORE`={breaking:90,developing:60,evergreen:0} (#2635), NOT the old additive 30/50, and NOT stuck all-evergreen. The 3 developing items score 60 ≥ 40 → they pass the `WR2_PREFER_LIVE_NEWS` filter and will fill the live pool at the next selector run (04:24/05:10; not forced — Legge-5-adjacent). #2631+#2635 chain proven end-to-end on a natural nightly (not just composition). Only remaining passive confirmation: the selector actually picking one. Memory `discovery_wr2_liveness_natural_proof_timing_not_break_2026_07_18`. Related item — enrichment silent-drop **CLOSED + PROVEN-LIVE (#2691, 2026-07-18)**: the enricher's structured object now reaches WR2 drafts via the 4-hop opt-in contract; prod entity-match confirmed (`/pending?include_enrichment=true` carries it, default omits it).
- **~~13 unknown_intent + 3 render_incomplete~~ → RESOLVED, verified 2026-07-18 (growth-loop B).**
  The live queue (Pro SSOT + M5 mirror, both fresh) has **0 render_incomplete, 0 unknown_intent** —
  cleared by the daily reconciler + the #2563 `slides_dir`-resolution fix (`unknown_intent` was a
  reconciler classification, not a persisted state; the "13" was a report count). Genuine
  resolution proven: 2 live entries carry `render_incomplete → drafted → published` in
  `state_history`; only 1 render_incomplete was archived. **The real current render-lane residue
  (a different, lower-urgency backlog — DB `war_room_drafts.status`):** `render_failed`=20
  (slow-accumulating since 2026-06-09, ~4/wk, 1 in last 3d — not acute), `missed`=17 (one-time
  2026-06-23), `rendered_shadow`=7 (2026-06-13 test batch). A render-failure sweep, if wanted, is
  a fresh item — not the (now-closed) queue-stuck one. **GROUND 2026-07-18 (growth-loop B):** the 19
  render_failed are CONTENT/QUALITY failures, NOT render-infra — #4b279125 = `Article 7 hard fail:
forbidden phrase 'unlock'` (deterministic content-gate `ValueError`, `composer.py:1269`), others =
  weak-slide non-convergence (max_iters). A blind requeue is FUTILE (identical content → identical
  fail). The 8 `attempts=0` rows are a stale 06-08→06-13 batch (leave — stale news). **Systematic
  sub-bug (ledgered):** the render lane's generic `except Exception` (`wr2_html_render_apply.py:1415`)
  mislabels the deterministic Article-7 reject as 'transient' and burns all 3 retries — should
  fail-fast. Deeper root cause: composer should never emit forbidden phrases.
- **fact_check_status "degraded" pipeline-wide** — ROOT-CAUSED 2026-07-18 (growth-loop B4,
  `research/marketing/2026-07-18-wr2-fact-check-degraded-root-cause.md`, Codex-CADE-sharpened):
  NOT a bug — correct fail-closed. The checker verifies each draft against `brief_json`, the
  same corpus the composer wrote from, so it can only measure fidelity-to-author, never
  independent truth (`research_json` never populated in prod). 52/79 degraded drafts are
  grounding-starved; the naive "inject citations into brief" is a closed citation-echo. Real
  fix (GO-gated): verify at check-time against a source the composer never saw + verdict-
  provenance labels + slides-excluded verification (:662/:676). The word-number sub-slice (105/438 unverifiable
  claims are numbers-as-words) was attempted (branch `factcheck-wordnumbers`) and **REJECTED by
  2 red-team rounds** (growth-loop B3, 2026-07-18): token-normalization of decomposed number-words
  structurally false-verifies (2M=200M, 101=100, pronominal "one", sign-loss — all empirically
  confirmed on the real functions) and self-verifies against the slide-inclusive source (B4's exact
  warning, proven). Branch cleaned, not shipped. Those 105 claims need the LLM-escalation path
  (`WR2_FACT_CHECKER_LLM=true`, off in prod — 90/90 telemetry `llm_enabled:false`) or a narrow
  cardinal-only-vs-external matcher, NOT normalization. Ledgered (PENDING-ARMS 2026-07-18).
- **Gate log noise — SHIPPED (#2676, growth-loop B, 2026-07-18)**: `WarRoom.swift` delta-emission
  dedups the ~29 exclusion stderr writes across scans (key `slug|reason`; memory committed only on
  a successful scan, never on the early `return []` failure path) → kills the ~30MB/day
  `wr2control.err` growth. Codex-red-teamed (reasons stationary → storm stopped, memory bounded);
  release-built + canonical `~/Applications` bundle installed 2026-07-18. Live err-rate→~0/cycle =
  receptor on Zero's next app launch (the app was OFF at ship — err last grew 2026-07-17). Adjacent
  PRE-EXISTING finding (a readable-empty `slides/` dir excluded without count/log) + 2 NICEs
  (`@MainActor`, multi-root key) ledgered in PENDING-ARMS, not fixed (intent decision).
- **Accessibility/legibility SOTA is in the external benches, NOT a separate amendments file.** Verified 2026-07-18 (M5 + Pro): `_proposed-amendments/2026-07-16-accessibility-discipline.md` does NOT exist on either machine and no "4 accessibility amendments" content is in the brand skill — the prior reference was phantom (scar #6). The real, still-UN-shipped accessibility work is grounded in `_external-bench-2026-06.md`: **Art 14.7 AI-disclosure label** (Meta AI-label + EU AI Act pressure; constitution silent, Art 5.4 covers faces only) + **translucent-caption-pill** legibility scrim. Grounding these into constitution articles is the real (Zero-gated brand judgment) work — there is no lost amendments file to reconcile.
- **Slide-7 closer micro-text — ✅ MECHANISM PINNED + FIXED + LIVE 2026-07-19 (#2767, growth-loop B).**
  Corner-note was WRONG (corrected 2026-07-18): the closer is NOT elegant-close — a true-last
  `cta`/empty-`layout_family` slide routes to **statement-bomb** (Art 9.5). The tiny rendering was a
  **SIZE COLLAPSE, not a contrast problem**: the injected hero photo's bottom edge → `bottom_ink_ratio≈0.497`
  → the designer-loop geometry critic reads "bottom overflow" → emits `shrink_font:body`, which rendered
  `[data-zone-type='text']{font-size:calc(1em*factor)}`; the statement-bomb `.statement` carries
  `data-zone-type="text"` (over-match) and `1em` resolves to the ~16px PARENT → the Art-9.5 closer collapsed
  72px→~10px. A black-bg closer has no photo → no false overflow → no lever → stays 72px. **Fix (LIVE):**
  exclude `.statement` from both the shrink AND grow body-lever selectors (`:not(.statement)`, `composer.py`) —
  Playwright prove-live on Pro `~/nuzantara-deploy`: closer+shrink_body **72px** (was 12.16px), editorial prose
  still shrinks (non-regression), 139/139 tests + a regression test; Codex R2 approved scoped.
  **Still open (SEPARATE axes, ledgered PENDING-ARMS 2026-07-19):** (a) **W89** — the `[data-zone-type='text']`
  arm over-matches OTHER primary-text leaves (dark-status-list `.heading` 56→12px CONFIRMED); root-cure =
  prose-only selector + fix `calc(1em*factor)`, render-QA'd across the layout library (NOT a `:not()` whack-a-mole
  = scar #3); (b) an over-long closer now has neither auto-shrink nor hard-fail (72px unbounded — strictly better
  than the old ~10px collapse); (c) the **translucent-caption-pill** contrast device
  (`_external-bench-2026-06.md:57`) for text-over-photo LEGIBILITY stays a separate Zero-gated brand BUILD (it
  addresses contrast, NOT the size collapse this fixed). Memory
  `discovery_wr2_slide7_closer_mislabeled_photo_statement_bomb_2026_07_18` (RESOLVED section).
- **Render/visual-QA is research-SATURATED + build-partial + armed-live — do NOT re-research** (growth-loop
  R, 2026-07-18). The 2026-06-07 pair (`design-critic-loop-sota` + `html-css-carousel-renderer-sota`) is the
  authoritative render-QA SOTA. Built + armed-live on the Pro (ssh-verified: `WR2_VISION_REQUIRED=1`,
  EasyOCR+torch present, designer-loop firing through 07-18 05:37): font-load hard gate, OCR round-trip
  (full-size), local contrast. **UNbuilt vs the research** (the narrow real gap): the _thumbnail-downscale_
  OCR pass + full geometry lint (overlap/off-grid/DOM-overflow). Capture
  `research/marketing/2026-07-18-wr2-render-qa-saturated-hero-headline-lever-gap.md` · memory
  `discovery_wr2_render_qa_saturated_hero_headline_lever_gap_2026_07_18`.
- **Hero-cover headline thumbnail illegibility — the grow-lever was REFUTED, the real cure is the fit
  policy (Zero-gated)** (growth-loop B, 2026-07-18, #2750). The `grow_font target=heading` lever was built
  - hardened over 3 adversarial rounds, then MEASURED against prod (n=113 cover instances) → fires on ~1.8%
    ⇒ refuted, code reverted, capture only. **Real cause:** `_wrap_headline_sentence_aware` (ALWAYS-ON
    cover-photo fit) shrinks **83.2% of covers to its 60px floor** to keep every sentence on its own line — at
    IG-grid downscale ~6-8px = the "caption-sized hook" the designer-loop logs. The lever can't help: the
    renderer defers ~95% via a silent `continue`, so opening the critic prompt alone = a silent no-op
    (cicatrix #2). **Real fix (NEXT B, Zero-gated):** re-tune the fit policy — a thumbnail-legible floor as the
    HARD bound, sentence integrity yields to wrapping; ADD a vertical/max-lines guard (content anchored bottom
    270px, `overflow:hidden` clips) + an indivisible-token guard; reconcile the composer-150px vs critic-110px
    grid factor. Blast radius 83% of covers → brand call + render QA on a real deck. Capture
    `research/marketing/2026-07-18-wr2-cover-headline-thumbnail-illegibility-root-cause.md` · memory
    `discovery_wr2_cover_headline_thumbnail_illegibility_root_cause_2026_07_18`.
- **Statement-bomb template ignores `yellow_accent`** (found 2026-07-18 on a80130df): the template
  unconditionally wraps the LAST word of `statement` in the accent span (composer.py ~line 1600),
  so the accent lands on whatever word ends the sentence — the EN deck had it on "INVOICE." instead
  of "DECLARATION". Workaround used: clause order chosen so the intended word is last. Fix = honor
  `yellow_accent` when present; behavior change ⇒ needs guilt+innocence tests across all
  statement-bomb decks (scar #3).
- **`dark-status-list` renders only heading + list_items** (found 2026-07-18): `body` and
  `subheading` are silently dropped by the skeleton — slide-7-class closing messages stored in
  `body` never appear on the PNG (true for the EN deck too). Fix options: add an optional
  closing-line slot to the skeleton, or route such copy to a rendered field at compose time; until
  then closing lines must ride the last list row and the IG caption.
- **Ledgered structural cures** (modus PENDING-ARMS): docs-guardian regen cron on main ·
  M5 queue shared-lock protocol · plist validator red on main ·
  19 env-coupled tests · fact-lane `lease_owner` CAS (symmetric with render/image — see §1 B5).

## 2. Anatomy — the hot files (verified 2026-07-17)

**Pipeline (Pro, launchd `com.balizero.wr2.*`, logs `~/logs/wr2*.log`; wrapper
`~/.openclaw/bin/wr2/wr2-script-wrapper.sh` → `REPO_ROOT=${WR2_REPO_ROOT:-~/nuzantara-deploy}`
— deploy = pull BOTH `~/Desktop/nuzantara` AND `~/nuzantara-deploy`, scar #1):**

| Stage | Script | launchd | Notes |
| ------------- | ------------------------------------------------------------------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------ |
| Topic pick | `scripts/wr2_topic_selector.py` | topic-selector | scores staging items, writes `war_room_drafts` (status `briefed`) with brief_json = article_summary[:2000] + enrichment + source_url; RAG grounding via `scripts/wr2_grounding.py` (citation injection + `_grounding_injected_only` marker + `is_citations_only_the_facts()` SSOT) |
| Compose | `scripts/wr2_draft_generator.py` | draft-generator | **facts-first prompt** (article leads, enriched brief supports); park backstop (news-shaped + no usable source → `parked`, never composed); tri-state outcome `success                                                                                                             | parked | failed`, exit 0 unless real failures |
| Hero images | `scripts/wr2_image_generator.py` | image-generator | Codex $imagegen primary, FlowKit fallback; CAS lease on `lease_owner`, stale-sweep TTL 40min |
| Facts | `scripts/wr2_fact_extractor.py` | fact-extractor | gates on `fact_check_json IS NULL` |
| Check | fact-checker lane | fact-checker | writes `fact_check_status` (currently degraded pipeline-wide) |
| Render | `scripts/wr2_html_render_apply.py` + `apps/backend-rag/backend/services/canva_renderer_v2/_pg.py` | html-apply | HTML/CSS→PNG Playwright; fetch gates on `drive_url IS NULL` + `lease_owner IS NULL`; official re-render verb: `_pg.requeue_draft_for_rerender` |
| Orchestration | `scripts/wr2_supervisor.py` + `scripts/wr2_supervisor_watchdog.py` | supervisor | TRANSITIONS maps (from,to)→launchd label; TERMINAL_STATUSES includes `parked` |
| Reconcile | `scripts/wr2_daily_reconciler.py` | daily-reconciler | slides-dir resolution 3-level, `--repair-false-incomplete`, `--backfill-completeness` |

**DB**: `war_room_drafts` on nuzantara-postgres. Status machine (CHECK constraint, migration 245):
briefed → drafts → drafts_imaged → drafts_imaged_facted → drafts_imaged_checked → rendering →
rendered (+ parked/rejected/failed terminals). Backend model `apps/backend-rag/backend/services/
war_room/models.py::DraftStatus` must stay in sync (repository raises on unknown status).

**Queue (SSOT Pro)**: `~/Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json` +
`queue-archive.json`. Writers: `scripts/wr2_queue_writer.py` ONLY (fcntl EX on
`human-review-queue.lock`, tmp+os.replace). M5 mirror: `~/bin/wr2-queue-pull.sh` (declared
HOME-fork pair — deploy = cp from repo + kickstart) pulls archive FIRST, merges via
`scripts/wr2_queue_pull_merge.py` (remote-wins, published-local protected, `archived_dropped`,
external push-back with `synced_to_pro`).

**App (M5)**: `apps/wr2-control-app/` (Swift; build via repo `build.sh`, canonical bundle in
`~/Applications`, Desktop symlink). Complete-or-nothing gate, external-post sheet, ReviewView.

**Metrics**: `scripts/wr2_ig_metrics_scraper.py` (authoritative `ig_media_id` numeric Graph id;
token from Pro `.env.master`, NEVER printed) + `scripts/wr2_ig_discovery.py` (shortcode
compare-and-set backfill) → weekly `wr2-ig-metrics-analyst` (Monday 06:00) → amendments in
`~/.claude/skills/bali-zero-brand/_proposed-amendments/`.

**Brand cortex**: `~/.claude/skills/bali-zero-brand/` (constitution, tokens, voice, surfaces,
external benches). Agent defs vendored in repo `.claude/agents/wr2-*.md` (#2544 — repo shadows
HOME).

**Deploy**: backend/migrations ride the CI pipeline `.github/workflows/fly-deploy.yml` (push to
main touching `apps/backend-rag/**`; release_command applies migrations). WR2 scripts on Pro =
pull both checkouts + kickstart affected daemons. Prove-live per consumer surface, always.

## 3. Blood-bought rules (violate = repeat a paid scar)

1. **Facts-first, refuse-to-guess** (founding scar 2026-07-16): the article summary LEADS the
   composition prompt; grounding citations SUPPORT, never replace. News-shaped topic with no
   usable source → `parked`, never composed. Never "tidy" this.
2. **Remake hygiene**: re-briefing a composed draft by status reset leaves stale derived fields —
   `fact_check_json` starves the extractor, `drive_url` starves the render lane. Use the official
   verb `python scripts/wr2_daily_reconciler.py --rebrief <draft_id>` (#2667) — one atomic reset
   (`status`→briefed + `fact_check_json`/status/at + `drive_url` + `html_render_attempts`=0 + `canva_*`),
   lease-guarded + queue-published-guarded (refuses to resurrect a published carousel). Do NOT
   hand-reset status + clear fields piecemeal; the verb is the single safe path.
3. **Never `launchctl kickstart -k` a one-shot job that may be mid-run** — it kills the worker
   and orphans its DB lease (42-min starvation, 2026-07-17). Plain kickstart; `-k` only for
   daemons you intend to restart.
4. **Queue mutations only via canonical writers under flock** — never hand-edit
   human-review-queue.json/queue-archive.json (data-plane guard blocks it; the merge protocol
   depends on writer invariants).
5. **The wrapper runs from `~/nuzantara-deploy`**, not `~/Desktop/nuzantara`. Aligning only one
   Pro checkout deploys nothing (scar #1 HOME-fork). M5's `~/bin/wr2-queue-pull.sh` same family.
6. **Migration PRs = auto-merge OFF** — the session merges manually after Squawk/migration gates,
   then probes the applied constraint on prod with its own query.
7. **Generator≠grader always**: implementer lane ≠ reviewer; Codex red-team on behavior changes;
   the final on-disk/live gate is the session's own tool calls.
8. **Probe entity-match** (3 strikes 2026-07-17): probes assert exact ids/status enums/counts —
   never generic "error" greps (matches fail-open observability noise), never `jq '.[0]'` output
   tested with `[ -n ]` (empty array prints literal "null null").
9. **Tests must not write prod state** (W96): WR2 workers default `Path.home()` output roots —
   conftest must redirect `WR2_OUTPUT_ROOT`/Telegram to tmp_path.
10. **Legge 5**: `drafted` is the pipeline's last stop. Zero publishes.

## 4. GROWTH LOOP — standing mandate for no-stop improvement sessions

> Zero's order (2026-07-17): a session that works in a loop on WR2 improvement, alternating deep
> research of best practices / cutting-edge tools with concrete experimentation on the automation
> and continuous live fixes. Paste the prompt below into a fresh session (or invoke with /loop).

```
/wr2 — GROWTH LOOP. Sessione no-stop di accrescimento della WR2. Lavora in loop autonomo
alternando due sprint, finché io non ti fermo:

SPRINT R (research, ~30% del tempo): deep research su UNA domanda concreta di frontiera per la
WR2 — agentic content pipelines SOTA, editorial automation, IG-format best practice, layout/
accessibility, metrics-driven editorial loops, tool nuovi (modelli, renderer, vision-QA).
Multi-fonte (web + external-bench esistenti in ~/.claude/skills/bali-zero-brand/ + carousel
corpus + metriche IG reali). Output: research capture in research/marketing/ con ≥3 fonti e UNA
raccomandazione azionabile ("adotta X per Y, atteso Z"). Niente ricerca senza raccomandazione.

SPRINT B (build, ~70% del tempo). ANTI-TWIN PRE-FLIGHT (obbligatorio, scar #5 — l'intero sprint B6
del 2026-07-18 fu un duplicato convergente di una sessione parallela M5, #2680/#2685 vs #2676/#2679,
~1 sprint bruciato): PRIMA di aprire qualunque lavoro su un wound, per l'item che stai per prendere
esegui i tre check e STAI GIÙ se un twin è già in volo — (1) `git worktree list` (un lane sibling
sullo stesso wound è già lì: il tell `wr2-log-delta` era nell'inventario dall'inizio); (2)
`gh pr list --repo Balizero1987/Teman2 --state all --search "<keyword del wound>"` (twin appena
aperto/mergiato); (3) grep `origin/main` per il fix già atterrato, verifica per CONTENUTO (W88). Se
il wound è già curato o in-volo → NON aprire un duplicato: aggiorna solo corner/ledger se stantio e
passa al prossimo item. POI: prendi UN item — dalla raccomandazione dell'ultimo sprint R,
dalla §1 LIVE STATE del corner /wr2 (open wounds: liveness scorer 0.0, 13 unknown_intent,
fact-check degraded, log noise, --rebrief verb…), o da un fix emerso live — e portalo fino in
fondo con modus: GROUND (ri-grep dei file citati) → BUILD (implementer Sonnet in worktree) →
VERIFY (red-team Codex per i behavior change, generator≠grader) → SHIP+ARM (PR + auto-merge;
migration = merge manuale) → PROVE-LIVE (deploy Pro dual-checkout + kickstart + probe con
entity-match sull'esito REALE) → CAPTURE (aggiorna §1 LIVE STATE del corner + ledger + scar).

Regole del loop:
- UNA cosa per sprint, chiusa fino a prove-live — mai 3 cose a metà.
- Alterna: dopo ogni sprint B chiuso, uno sprint R. Se uno sprint B si blocca su un gate
  operator-only, scrivi la riga PENDING-ARMS e passa al prossimo item invece di aspettare.
- Rispetta le blood-bought rules del corner /wr2 §3 — tutte, sempre.
- Legge 5: mai pubblicare su IG. I risultati arrivano a 'drafted' e si fermano.
- Niente API a pagamento nuove senza mia autorizzazione; arsenale esistente (Claude OAuth,
  agy, Codex, DeepSeek pre-autorizzato, Ollama) libero.
- Budget-onestà: dichiara a inizio sessione quanti sprint stimi; se un item supera 2x la stima,
  fermalo, ledger, passa oltre.
- Ogni 3 sprint: riga di sintesi a me su Telegram-style (cosa è cresciuto, cosa è in coda).
- A fine sessione (o /loop stop): CAPTURE finale — memoria + §1 LIVE STATE aggiornata + prompt
  di ripartenza per la sessione successiva.
```

**Seed backlog for the first loops** (in rough value order): (1) liveness scorer rewire — the
single highest-leverage fix, unlocks the whole breaking/developing register system [DONE #2631];
(2) fact-check degraded root-cause [DONE #2651 + R #2655]; (3) ~~unknown_intent/render_incomplete
adjudication~~ [DONE — verified resolved 2026-07-18, see §1];
(4) `--rebrief` official verb [DONE #2667, proven live 2026-07-18]; (5) metrics→editorial feedback: use the now-live IG metrics to
auto-tune topic selection weights; (6) gate log delta-emission; (7) accessibility amendment
implementation once Zero rules; (8) slide-7 closer layout fix; (9) A/B hook experiments on
cover copy measured via the metrics loop.

## 5. Access & artifacts

- Memory (M5): `ops_wr2_trifront_gate_variety_accessibility_shipped_2026_07_16.md` (the July
  16-17 arc, all codas) · `discovery_wr2_app_published_blind_and_contract_d_2026_07_14` ·
  `p1-wr2-pipeline-consolidation-spec.md` (REV 2, awaiting GO) ·
  `decision_wr2_renderer_html_css_over_canva_2026_06_06`.
- Modus ledger: `.claude/skills/modus/PENDING-ARMS.md` + `AMENDMENTS.md` (WR2 lines 2026-07-17).
- Output tree (Pro SSOT): `~/Desktop/nuzantara/apps/war-room/output/` (carousel/, queue/).
- Drive renders: per-draft `drive_url` in war_room_drafts.
- DB access RO: `mcp__postgres-nuzantara__query` / `scripts/pg.sh`; writes ONLY via backend
  code from Pro env (never MCP).
- IG token: Pro `.env.master` — grep into env vars, never print (scar #4).
- Adaptive-production 3-seat research (2026-07-20): `_research/2026-07-20-adaptive-production-3seat-research.md`
  (Kimi K3 + Gemini 3.1 Pro + Codex sol-ultra, full verbatim seat reports + Fable synthesis/adoption ruling).

> Chi cambia lo stato AGGIORNA la §1. Un corner stantio è peggio di nessun corner (W90: anche il
> ground-truth invecchia).
