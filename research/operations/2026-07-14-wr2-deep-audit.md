---
date: 2026-07-14
domain: operations
adversarial_review: codex
---

# WR2 Deep Audit — coherence + SOTA positioning (2026-07-14)

> **Mandate** (Zero, 2026-07-14): *"analisi profonda della codebase wr2 (deve coincidere anche con
> l'app, dove però deve vincere una UI semplice ed efficace e sotto al cofano il resto) e capire se
> è tutto coerente e se questa automazione è al livello SOTA con quello che c'è sul mercato oggi."*
>
> **Method**: modus GEAR 3 TAC — 6 parallel anatomical readers (pipeline state, render engine +
> brand system, agent layer, Control app, Pro/Mini cron liveness, market SOTA research). Every
> load-bearing claim was re-executed on disk by the orchestrator before entering this report
> (superscar #6 discipline); "corrected" below always means *the claim text was corrected after
> re-verification* — no disk state was modified, all runtime probes were strictly READ-ONLY.
> The draft was then red-teamed by two external seats (Codex GPT-5.5 + Gemini 3.1 Pro); their
> surviving objections are folded in, and two of Codex's objections were verified on disk and
> **promoted to top findings** (§5a). Both red-team raw outputs are preserved in the session
> transcript.

---

## 1 · Verdict in three lines

1. **Design: frontier.** Four capabilities absent from every publicly documented offering in the
   July-2026 market — independent vision-critic gate, engagement-metrics→brand-rule loop,
   self-amending constitution, verbatim citation against a curated corpus — all exist in this
   codebase, and each has demonstrably fired at least once (the 06-23/06-29 IG-insights
   amendments were applied to the constitution; the critic gate passed the bike carousel on
   2026-07-14).
2. **Coherence: split-brain.** WR2 is not one system: it is **two pipelines coupled only through
   shared directories and queue files, with no transactional interface** (autonomous Python vs
   interactive subagents), documented by **a third that no longer exists** (the retired Canva
   lane), over **five state surfaces** of which the live publish path updates exactly one.
3. **Exercise: starved.** The autonomous pipeline's image stage is functionally dead on both
   providers (every observed attempt today failed 0/5 on both), so nothing completes — and three
   further independent blockers (hung metrics analyst, publication-state blindness, zero-signal
   trend ingestion) would each dampen the learning loop even with images restored. SOTA-by-design,
   under-armed in production — superscar #2 at system scale.

---

## 2 · The two pipelines (and the ghost third)

| | Autonomous (production) | Interactive (quality) | Documented (ghost) |
|---|---|---|---|
| Driver | `wr2_supervisor.py` LISTEN/NOTIFY + launchd kickstart (reconciler 3×/day is the polling fallback for dropped notifications) | `wr2-design-architect` + 4 subagents | `wr2_carousel_orchestrator.py` — **does not exist on disk** |
| Compose | `wr2_html_renderer/composer.py` (deterministic, "Engine A") | `wr2-layout-composer` writes HTML in-LLM ("Engine B") | Canva duplica-poi-edita (retired PR #2396) |
| Ground truth | briefer stub must be *fed* an NB brief | Contract B: NB query required (self-reported, no external gate) | same as interactive |
| Critic | designer-loop legibility critic only (see §5a for the wiring defect) | `wr2-critic` 4-rubric constitution gate | `wr2_telegram_publish_gate.py` — **does not exist on disk** |
| Invokes subagents? | **Never** — zero `subagent_type="wr2-…"` hits in repo | Always | — |

Consequences, all disk-verified this session:

- **Quality contracts A/B/C are written for a path production never takes — and even there they
  are self-attested.** Enforcement is the agent's own report of its Agent-call count / NB arrays;
  `_audit-checklist.sh` (real, all 5 modes) only reports. A self-attested instruction is not an
  enforced contract.
- **The W99 font fix lives in Engine A only.** `composer.py:199-216` anchors `_fonts.css`
  injection on `<head>`; Engine B's hand-written HTML never passes through `_normalize_skeleton`,
  so the interactive path can plausibly still produce the system-font failure the fix just cured.
  *(Contract-inferred, not artifact-proven: before any Engine-B rework, add one representative
  Engine-B render test that proves or disproves this — red-team point accepted.)* The
  `renderer.py:225` hard gate is the backstop, and only if that HTML is rendered through
  `render_html_files`. Engine B also renders LLM-authored HTML with no declared sanitization /
  execution boundary (scripts, remote requests, local-file reads) — unaudited surface.
- **A fresh agent reading `wr2-carousel-pipeline` SKILL.md runs a file that isn't there** (both
  ghost scripts verified absent; the skill was loaded in this very session and cites both as
  entry points).

## 3 · Five state surfaces, one writer short

The five surfaces have **different semantics** (a lease manifest and an idempotency ledger are
not "the same fact" as a publication state — red-team point accepted); the defect is narrower
and worse: **the three surfaces that DO represent publication truth (PG status, review-queue
file, publish-attempts ledger) are updated by four different publish paths, none of which writes
all three.**

1. PG `war_room_drafts.status` — the live manual publish path (Damar by hand → WhatsApp →
   consumer → `wr2_queue_writer.mark_published`) never touches it: only `wr2_ig_publish.py:618`
   writes `'published'`, and that is not the daily path. `wr2_daily_reconciler.py:56` codifies
   the blindness (`TERMINAL_OK = {"rendered", …}`). DB-side published counts are therefore
   *incomplete and non-authoritative* (not "all wrong" — draft-#1 phrasing corrected).
2. `human-review-queue.json` — the *most* authoritative publication surface, but not fully: the
   direct backend publisher can return an IG permalink without updating queue or DB. Also
   M5↔Pro split-brained (blind 300s `wr2-queue-pull.sh` replace, band-aided by
   `wr2_queue_pull_merge.py`), two coexisting item schemas, one ghost Canva state still in
   `PUBLISHABLE_STATES` (`wr2_queue_writer.py:69`).
3. PG `wr2_publish_attempts` idempotency ledger — written by 2 of 4 publish paths. Note: even
   where written, publication idempotency is not airtight — IG can accept the post and the local
   write can then fail; safe retry requires persisting the platform post-ID and reading platform
   state back (red-team point accepted, folded into the cure).
4. Per-carousel `.run.json` — app telemetry, read by nothing (fine as telemetry; just invisible
   to the watchdogs that reason about liveness).
5. Drive `manifest.json` — lease-written, watchdog-probed (healthy).

**Correction vs the pipeline lane's claim**: the DB review vocabulary is *not* fully vestigial —
`review_handler.py:226` writes `DraftStatus.APPROVED`, `sla_worker.py` and
`wr2_draft_generator.py:1164` write `rejected`. The accurate statement: **the live carousel path
bypasses the DB review lattice entirely** (review happens in the file queue:
drafted→reviewed→published, transitions written by the app/damar-server), while backend review
services still write the DB lattice — two live review state machines on two surfaces, neither
reading the other. The `DraftStatus` enum (`models.py:18-31`) has additionally drifted from the
live CHECK constraint (migration 222) badly enough that pipeline workers use raw string literals.

## 4 · Runtime liveness (Pro, read-only probe 2026-07-14)

- **Image generation: functionally dead on both providers.** Evidence basis: today's two observed
  runs (05:18, 09:08) generated 0/5 slide images on both attempts; Codex `$imagegen` fails
  "latest PNG older than 600s window" on every slide and the Playwright/Nano-Banana fallback
  times out at 240s; failures of this shape appear in logs since at least 2026-05-07. Root cause
  is **not yet established** — a `refresh_token_reused` Codex OAuth error was observed 2026-05-21
  and `codex` is unresolvable in a non-interactive SSH shell, but production uses an absolute
  path, so the July state needs a fresh authenticated probe before treating auth as the cause
  (red-team point accepted; §9 item 1 is now "diagnose, then fix", with the operator login as a
  *contingent* step).
- **FlowKit `/health` says `ok, extension_connected:true` while every real call fails** — a
  green-that-lies (family #2). Cure: a *scheduled* synthetic render canary whose result the
  health endpoint reports — not a render per health request (cost/thundering-herd, red-team
  point accepted).
- **`wr2.ig-metrics-analyst.weekly` is a hung zombie** — PID running 28+ h, both logs empty.
  Independent of the image outage; blocks the metrics→amendments link on its own.
- **`wr2.newsletter` has skipped every send since ≥2026-05-11** (`no_recipients`) — 9+ weeks of
  green cron that never delivered anything.
- **`wr2.reflexion.weekly` is the best-behaved organ in the fleet**: it raised its own
  "TAUTOLOGY ALARM — 3 runs, zero state-delta" rather than fabricating a lesson. The scar-#2
  antidote working as designed. (But note: its documented output target `layouts/_proposed/`
  does not exist AND the writer has no layout-routing logic — creating the dir alone would fix
  nothing; red-team point accepted.)
- HOME-fork status (claim corrected after re-verification): `wr2-script-wrapper.sh` **is**
  repo-tracked (`infra/openclaw/wr2/`) and byte-identical to Pro's live copy (`e8e22fe1` both)
  but the pair is **undeclared** → the lint is blind to it; identical today by luck, not
  enforcement. `wr2-cron-wrapper.sh` HOME copy on Pro (`f17092b3`) **has diverged** from the
  repo copy on the same machine (`3cd52391`) and oracle/connector/newsletter run the stale fork.
  Neither pair is in `infra/home-fork/declared-pairs.json`.
- Secondary: oracle degraded (Gemini leg down), connector flaky (`runner: no JSON`), trend-hunter
  persists 0 signals every 2h cycle (config smell), worktree-gc log empty (unverifiable),
  matagaruda-bridge disk-full lines are stale log residue from a past incident (verified: 80GB
  free now).

## 5 · Constitution enforcement map (render engine)

Structural articles are real code gates; content articles are vision-LLM-only or nothing:

- **[CODE, hard — with honest qualifiers]**: 1080×1350 (`renderer.py:347`); brand-font-loaded
  (`renderer.py:225`, the W99 gate, guilt+innocence+library-sweep tested); hero decoded +
  visible-on-canvas (`renderer.py:240-412`); family pool (`composer.py:50,77`); cover/closing
  forcing (`composer.py:145-163`) — **but an explicit `layout_family` bypasses Art 9.3/9.5 by
  documented design** (`composer.py:140-143`); contrast ≥7.0 + OCR round-trip
  (`designer_loop.py`) — **but the loop accepts one non-converged best-effort slide as
  "composition debt", and OCR degrades to pass when unavailable**; fail-closed vision only under
  `WR2_VISION_REQUIRED=1`. "Hard" gates with by-design escape hatches should be listed as such —
  red-team point accepted.
- **[LLM-only]**: banned colors in text zones, citations verbatim, no-emoji, bullet-promise,
  type-as-design bans — every copy rule rides on a *vision* model reading *painted* text
  (OCR-grade fragility on top of judge-grade fragility), and only on the interactive path.
- **[NONE — "hard fail" on paper, nothing executable]**: Art 7 forbidden-phrase list (**no
  scanner anywhere in the engine** — grep verified), Art 2.3 "≥95% palette pixels" (**the
  measurement does not exist in code**), Art 6.1 body word-count, Art 1.3 hero-count range,
  Art 4.3 logo-on-every-slide (warning only, `renderer.py:130`).
- **Library drift both directions**: constitution promises 4 families that have no skeleton
  (composer correctly refuses them), while the actual workhorse default `editorial-text`
  (`composer.py:171`) is absent from the constitution. `tokens_to_css.py:38-53` `_SUPPLEMENT`
  holds 9 tokens outside tokens.json ("delete when migrated", pending since 2026-05-12).

## 5a · Red-team promotions — two defects the lanes missed (disk-verified)

1. **The production "critic-proposes / verifier-vetoes" guardrail is self-approval.**
   `wr2_html_render_apply.py:751` passes `brand_verifier=claude_design_critic` — the *same
   function* serves as critic and verifier in the cron path. The two-role architecture exists in
   `designer_loop.py`; the production wiring collapses it. (Codex objection #14, verified.)
2. **The Python path fabricates a critic verdict exactly like the Swift app does.**
   `wr2_html_render_apply.py:229`: `verdict = "pass" if weak_count == 0 else "soft_fail"` — a
   legibility-only outcome is written into the queue as `critic_overall_verdict`, a field named
   for the 4-rubric constitution critic that never ran on this path. Downstream consumers (the
   app, the analyst) cannot distinguish this "pass" from a real constitution-critic pass.
   (Codex objection #15, verified. The app's `QueueWriter.swift:117` fabricated `"pass"` is the
   same disease — see §6.)

## 6 · Control app (UI semplice, cofano potente — la dottrina regge?)

The surface honors the doctrine: 7 sections, plain IT/ID step names, honest empty states,
Legge-5 two-step publish, `ANTHROPIC_API_KEY` stripped on every spawn (by design — the OAuth CLI
is the sanctioned auth path), scar-#1/#2 cures genuinely engineered (path re-rooting, disk-marker
+ `ps` dual-signal run detection, PNG backup/restore on failed re-render). No app lever points at
a dead script — the drift is the reverse: pipeline power with no button (reject/discard,
hero-only regen, critic re-run, slide-copy edit — the "caption editor" edits only the IG
caption).

Under the hood, four real defects (all disk-verified):

1. **Dual queue-writer**: the app reimplements `wr2_queue_writer.py` in Swift with divergent
   side-fields (doesn't clear `engagement_metrics`, matches by slug not ref-code) and **no
   flock** → lost-update race against the Python/cron writer. Note: a shared flock alone cannot
   serialize M5↔Pro (independent replaced copies) — the real cure is one canonical writer plus
   the merge protocol, or a CAS/lease scheme (red-team point accepted).
2. **Fabricated critic verdict**: `QueueWriter.swift:117` stamps `critic_overall_verdict:"pass"`
   on every app-enqueued draft, including raw PNG uploads the critic never saw. Replacing it with
   `null` is necessary but not sufficient — PNG imports also bypass every render gate
   (dimensions, font, logo), so they need their own validation lane before release eligibility.
3. **Sibling race**: Migliora/Ri-renderizza stay enabled while an external run rebuilds the same
   slug. UI disabling is TOCTOU-prone — the durable cure is a per-slug lease at the write path.
4. **Agent runs on the MAIN checkout with `--permission-mode bypassPermissions`**
   (`ClaudeRunner.swift:70,115,117`) — the app bypasses the agent-worktree discipline the rest of
   the organism enforces with hooks.

Cross-cutting (red-team point accepted): critic verdicts, human approvals and engagement metrics
are nowhere bound to an **artifact hash** — a re-render can change bytes after approval
(mitigated for published entries by the REPOINT immutable-history guard,
`wr2_html_render_apply.py:263-342`, but approvals-in-flight and metrics attribution are unbound).

## 7 · SOTA positioning (July 2026 market)

From the market lane (Canva Magic Studio, Adobe GenStudio, Predis, FeedHive, Jasper, Figma's
May-2026 Design Review Agent, Superside Brand Brain, LangGraph/CrewAI stacks; LLM-as-judge
reliability sources: MLAI Digital 2026 guide, NextFuture June-2026 study roundup, DeepEval):

- **Commoditized (table stakes — no advantage)**: brand token systems, layout template libraries,
  deterministic HTML→PNG rendering, human publish gates, multi-agent role separation.
- **Where SaaS beats WR2**: speed-to-first-draft, template variety, native cross-platform
  scheduling, analytics dashboards, Adobe's "commercially safe" licensed-training legal posture.
- **Genuinely frontier** — with the honest scope *"absent from everything publicly documented"*
  (a time-boxed sweep cannot prove absence from proprietary stacks — red-team point accepted):
  1. Independent vision-critic gate with binary verdict (Figma productized the first native
     analog in May 2026 — months old as a market capability);
  2. Engagement-metrics → amendable, versioned brand-rule document;
  3. Self-amending constitution with human-gated merge;
  4. Verbatim-citation enforcement against a curated regulatory corpus (nearest general analog:
     Cohere grounding-spans; nothing carousel-specific).
- **Consistent with the judge literature**: reported ≈85% LLM-judge/human agreement with
  measurable position/verbosity/self-enhancement biases supports hybrid architectures of exactly
  WR2's shape — deterministic gates + LLM judge + human final gate, generator≠grader. Which makes
  §5a sting: the one place production violates generator≠grader is the exact property the
  architecture was designed around.
- Editorial-media cluster (NYT/Bloomberg carousel ops): no public evidence found — not usable as
  a benchmark either way.

**Positioning verdict**: WR2's *architecture* is ahead of anything publicly documented,
commercial or bespoke. Its *production exercise* is currently below a $32/month Predis
subscription, because Predis ships images and WR2's image stage is dead. SOTA is a property of
the running system, not the repo.

## 8 · §Meta-pattern — la malattia delle malattie

Every top finding across all six lanes AND both red-team promotions is the same defect wearing
different clothes:

> **Surfaces assert states they never verified, because the asserting organ and the knowing
> organ are different organs that don't share a nerve.**

- FlowKit `/health` asserts ok; the image call knows otherwise.
- The app asserts `critic_overall_verdict:"pass"`; no critic ever ran (`QueueWriter.swift:117`).
- The cron path asserts the same field from a legibility-only loop
  (`wr2_html_render_apply.py:229`) — and its "independent verifier" is the critic itself
  (`:751`).
- PG asserts `rendered` as terminal-OK; the file queue knows it's published.
- The docs assert `wr2_carousel_orchestrator.py` is the entry point; the disk knows better.
- The constitution asserts "hard fail" for Art 7/2.3/4.3; no code implements the fail.
- `launchctl` asserted green for the newsletter for 9 weeks; the recipient list knew better.
- The contracts assert fan-out/NB-grounding; enforcement is the agent's own self-report.

This is superscar #2 (Esiste≠Armato) generalized from cron to **every layer of the stack**:
state, docs, contracts, health probes, verdicts. The organism already owns the antidote — it is
written in the reconciler ("verify by CONTENT, alarm on unmet guarantee, P0 not silence") and in
reflexion's tautology alarm. The cure is not new inventions; it is **extending the reconciler
posture to the surfaces that don't have it** — and the red-team sharpened the how: a choke-point
that performs several writes is not atomic (a crash mid-sequence recreates split-brain), so the
publication truth needs a **canonical event (outbox) with idempotent projections and
reconciliation**, not just "one function that writes everywhere". Verdict fields need
**provenance** (which critic, on which artifact hash). Health needs **functional canaries**.
Docs need **CI that rejects references to absent executables**. And one **end-to-end exit test**
(brief→image→gates→approval→publish→read-back of every projection) would have caught most of
this report by itself.

## 9 · §Solo-operatore — cosa resta a Zero

Only genuinely operator-only items (everything else is session-executable):

1. **Codex OAuth re-login on Pro** (`codex login`, interactive terminal) — *contingent*: only if
   the fresh authenticated probe (§10 item 1) confirms token revocation as the image-gen Tier-1
   cause. `operator[gui]`.
2. **Gemini leg of oracle / agy auth on Pro** if the probe shows the same interactive-login wall.
   `operator[gui]`.
3. **Newsletter: business decision** — wanted? If yes, someone owns the recipient list (Brevo
   list id); if no, retire the cron instead of nine more green skips. `operator[business]`.
4. **Revenue-carousel republish** (4/9 slides live on IG in the wrong font) — already surfaced
   2026-07-14, Zero's call. `operator[business]`.
5. **Bike-carousel publish click** — release-ready in the app, Legge 5. `operator[business]`.

## 10 · Cure plan (re-prioritized after red-team: truth before throughput)

**Wave 0 — diagnose + contain lying surfaces (all session-executable, no operator dependency)**
1. **Image-gen root-cause probe** on Pro: authenticated Codex health-ping via absolute path,
   FlowKit functional render probe, log-window analysis. Output: cause + whether §9 item 1 fires.
2. **Stop the fabricated verdicts** (cheap, high-integrity): render-apply writes
   `critic_overall_verdict: "legibility_only_pass"` (or a separate field) instead of `"pass"`
   (`wr2_html_render_apply.py:229`); the app writes `null`/`not_run` (`QueueWriter.swift:117`).
   Consumers updated to distinguish. This is one honest enum, not a refactor.
3. **Un-collapse the verifier**: pass a real second-role verifier (distinct prompt at minimum)
   instead of `brand_verifier=claude_design_critic` (`wr2_html_render_apply.py:751`).
4. Declare the two wr2 wrapper pairs in `declared-pairs.json`; realign the diverged
   `wr2-cron-wrapper.sh` fork on Pro.

**Wave 1 — resuscitate production (after Wave 0 so recovery doesn't scale unsafe output)**
5. Fix image-gen per the Wave-0 diagnosis (operator login only if confirmed); add bounded retry
   + backoff + overlap-prevention, and a **backlog requeue** for the accumulated `image_failed`
   drafts (provider recovery alone does not revive them).
6. FlowKit: scheduled synthetic render canary; `/health` reports the canary's last result.
7. Kill + investigate the hung ig-metrics-analyst PID; wall-clock timeout in its wrapper.
   (Separate lane from image-gen — does not block carousel production, but blocks learning.)

**Wave 2 — one truth per publication fact**
8. **Publication outbox**: a canonical publish event (with platform post-ID persisted
   *before* local projections, read-back on retry) projected idempotently to queue + PG +
   ledger; the four existing paths converge on it. Handles `draft_id:null` external posts via an
   explicit external-post identity (no synthetic provenance). Drop/reconcile the DB's bypassed
   review vocabulary in a follow-up migration — after mapping the backend review services that
   still write it (`review_handler.py:226`, `sla_worker.py`).
9. App: single canonical queue-writer (shell-out or port with ref-code match + metrics-clear
   semantics) + per-slug lease at the write path (not just UI disabling); launch agents in a
   worktree, not the main checkout, and drop `bypassPermissions`.
10. Bind approvals/verdicts/metrics to artifact hashes (extend the REPOINT guard's logic
    upstream to approval time).
11. Docs: rewrite `wr2-carousel-pipeline` SKILL.md + procedure.md + design-architect to the
    supervisor+HTML reality; delete Canva-lane references and the two ghost scripts; add a CI
    lint that fails on doc references to non-existent executables (generalizes W65/W81).

**Wave 3 — close the gate gaps**
12. Engine unification — **high effort, structural** (red-team correction): first the
    representative Engine-B render test (proves/disproves the font-path claim and pins current
    behavior), plus an HTML sanitization boundary for LLM-authored markup; then migrate Engine B
    to emit slide-spec JSON consumed by `composer.py`.
13. Give the [NONE] articles teeth or honesty: forbidden-phrase scanner + body word-count in
    `composer.py` (trivial); palette-ratio (2.3) gets a pixel measurement in `critic_signals.py`
    or the article is rewritten; logo becomes a gate; PNG-import validation lane in the app
    (dimensions/font/logo at minimum).
14. Constitution↔library reconcile: document `editorial-text` + orphan photo families, drop or
    build the four skeleton-less promised families; migrate the 9 `_SUPPLEMENT` tokens.
15. One **end-to-end exit test**: brief→image→gates→approval→publish→read-back of every
    projection surface. The single highest-leverage regression net this audit identifies.

**Wave 4 — learning loop to full pressure**
16. Reflexion layout-routing: implement the write logic (the missing dir is a symptom, not the
    cause); build Voyager's substrate dirs or delete the aspirational prose; refresh
    external-bench (July run).
17. Trend-hunter adapter config audit (0 signals every cycle for weeks is a config smell).

## Adversarial review

Two external seats red-teamed the draft before landing — **Codex (GPT-5.5)**, 29 objections,
and **Gemini 3.1 Pro (agy)**, 10 objections. Three Codex objections were verified on disk and
promoted to findings (§5a: verifier self-approval at `wr2_html_render_apply.py:751`, fabricated
Python-side verdict at `:229`, explicit-family bypass of Art 9.3/9.5 at `composer.py:140-143`);
the cure plan was re-ordered truth-before-throughput on their joint objection. Objections
rejected after re-verification are listed below with reasons — the refuter is not trusted
blindly either (W65).

## 11 · Verification notes

- Lane claims corrected by orchestrator re-execution: `wr2-script-wrapper.sh` "not in git"
  (cron lane) → tracked, real gap is the undeclared pair; "DB review vocabulary vestigial"
  (pipeline lane) → written by backend review services + draft-generator, accurate claim is
  "bypassed by the live carousel path"; matagaruda disk-full → stale log residue.
- Red-team objections verified and promoted: verifier self-approval wiring
  (`wr2_html_render_apply.py:751`), Python-side fabricated verdict (`:229`), explicit-family
  bypass of Art 9.3/9.5 (`composer.py:140-143`). Red-team objections rejected after
  verification: "LISTEN/NOTIFY has no fallback" (the 3×/day reconciler is the fallback);
  "`ANTHROPIC_API_KEY` strip is an auth failure mode" (it is the sanctioned OAuth design);
  Codex's claim that the loop-critic prompt checks palette/emoji/citations (the prompt at
  `claude_vision.py` is legibility-scoped — the *wiring*, not the prompt, is the defect).
- Engine-B font-path claim remains contract-inferred, not artifact-proven (flagged in §2, test
  mandated in §10.12).
- "Dead image-gen" is evidenced by today's 0/5×2 runs + log history, not by an exhaustive
  window; root cause deliberately left open pending the Wave-0 probe.

## 12 · Resurrection outcome (2026-07-14, GEAR-3 execution session)

The audit's Wave-0..Wave-4 cure plan was executed the same day via a 9-lane implementer fan-out (Sonnet workers, Fable/Opus orchestrator, one adversarial finisher per lane). Outcome by finding:

**Crown jewel — image-gen was BLIND, not dead (proven live).** Root cause confirmed exactly as §4 suspected but sharper: Codex `$imagegen` succeeds ~100% of attempts; the consumer globbed `ig_*.png` while Codex had silently renamed output `ig_* -> call_* -> exec-*.png`, so the detector went permanently red on a live organ (scar #2 inverted — a red gate hiding a working producer, not a green gate hiding a dead one). Fixes: #2443 (name-agnostic `rglob("*.png")` + pre_existing snapshot + mtime window), #2441 (FlowKit fallback + `image_failed` requeue), #2454 closed as a test-hardening superset (bounded Codex retry + guilt/innocence tests for a 4th unannounced rename; content already on main via #2443). PROVEN LIVE on the Pro deploy worktree (`~/Desktop/nuzantara-deploy`) via `launchctl kickstart` of the real production agent: a Codex render produced `exec-d22cbab9-*.png`, logged as "1 fresh candidate", the draft advanced `drafts -> rendering`, the Tigris image returned HTTP 200; 8 backlogged `image_failed` drafts were requeued and are draining unattended.

**Truth surfaces (the §8 meta-pattern — surfaces asserting states they never verified):** #2444 landed the honest `legibility_only_pass` verdict vocabulary + wired the real independent `claude_brand_verifier` (it existed fully-formed in `claude_vision.py`, never called — the §5a self-approval was one wiring line); #2442 vendored the orphaned Swift Control app SOURCE into the repo (`apps/wr2-control-app/`, ending the undeclared HOME-fork) and replaced the app's fabricated `critic_overall_verdict:"pass"` with `not_run` (app rebuilt, reinstall deferred — app in active use; operator replaces at app-quit).

**Dead/dormant organs armed:** #2450 wired the never-written `wr2_orchestrator_metrics` table (per-step observability, fail-open-loud); #2440 gave reflexion its missing layout-proposal write path; #2453 resurrected trend-hunter (dead RSS feeds replaced, adapters made loud, starvation receptor added); #2452 added a wall-clock timeout to the ig-metrics-analyst wrapper (complementary to #2441's agy-health-check watchdog — different failure mode); #2448 gave teeth to the [NONE] constitution articles (forbidden-phrase scanner + word-count + logo gate + palette signal); #2446 promoted the never-installed worktree-gc plist (report-only by design — the gc itself fails the 3-AND reap safety check and targets a retired naming convention: install without `--apply`); #2447 rewrote the pipeline docs to disk reality + a CI lint that fails on doc references to non-existent executables (kills the ghost-script class W65/W81); #2449 declared the wr2 wrapper home-fork pairs.

**A1 sweep corrections (anti-hallucination):** the audit's claimed "ghost Canva state in `PUBLISHABLE_STATES`" (`wr2_queue_writer.py:69`) was NOT reproducible — the constant reads `("applied_ready_for_damar","approved","reviewed")`, no "canva" string. Two additional never-wired surfaces found: the WR2->WR3 handoff producer (migration 186's `publish_wr2_episode_published_event()` has a LISTEN consumer but no emitter — deliberately NOT armed, see §Solo-operatore) and a twin `agent-worktree-cleanup.daily.plist.example` cron (current naming, WIP-safe, never installed — the more valuable of the two GC crons).

**Still operator/pending (not armed under this WR2 mandate):**
- WR2->WR3 auto-handoff: wiring the producer is a Legge-5 business decision — `companion-mode.yaml` sub-mode `story_15s` has `activation: automatic_on_publish` with a soft (non-hard) cost ceiling and a human gate only POST-Veo-spend; the chain has three broken links (no emit, no LISTEN converter, wr3_supervisor not cron-armed) so it is inert today, but arming the first stone points toward "every published carousel auto-spawns a Veo mini-video". Zero decides.
- App reinstall (#2442): at app-quit — the installed bundle was in active use.
- `WR2_RUNTIME_SHA_GATE` warn->strict flip: still pending its 7-day clean-warn-log verification (PENDING-ARMS, not rushed).
- Post-drain fleet re-align: the Pro deploy worktree was ff-pulled for the image-gen fix mid-train; it needs a second `git pull --ff-only` once the remaining armed PRs finish the strict-CI merge-train.
- competitor-monitor.monthly / yield-optimizer.weekly (runs=0 since 2026-05-09): found by the Pro probe but OUT of WR2 scope (CRM/marketing agents; yield drafts client-facing WhatsApp) — flagged for a separate operator-scoped task, not auto-bootstrapped.
