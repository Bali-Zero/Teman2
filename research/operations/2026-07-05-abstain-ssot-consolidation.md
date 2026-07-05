---
date: 2026-07-05
domain: operations
task: abstain SSOT consolidation (#31) + RAG evidence-threshold hardening
session: fable-abstain (M5, autonomous Fable 5 mandate)
sources:
  - apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py (PR #1414, 2026-06-14)
  - apps/backend-rag/backend/tests/services/rag/agentic/test_abstain_threshold_convergence.py
  - apps/backend-rag/backend/tests/services/rag/agentic/test_reasoning_utils.py
  - git log 5623c6bfad (feat(rag): name the evidence-threshold gates, #1414)
---

# Abstain SSOT consolidation (#31) — close-out report

## TL;DR

The mandate's photograph (2026-06-11: "two live abstain paths; reasoning.py hardcodes the
flat 0.15 at ~11 sites; consolidate into one per-domain accessor") was **stale on arrival**.
PR #1414 (2026-06-14, `5623c6bfad`) had already built the SSOT — `_abstain_policy.py` with
four NAMED gates wired into all three decision sites — and a multi-LLM panel (Gemini
synthesis + GPT-5.5 refuter, 2026-06-14) had **ruled against** the mandate's expected
design: making the generation gate per-domain would let the system GENERATE tax advice at
evidence 0.11 (> tax 0.10) where the flat 0.15 correctly suppresses it — a safety
regression in the highest-penalty domain. The mandate anticipated exactly this
("FALSIFICALO se il codice reale dice altro, non forzarlo"), so this session closed the
RESIDUAL gap instead of re-doing the migration:

1. **Fifth gate named** — `reasoning.py:187` still read
   `EvidenceScoreConstants.ABSTAIN_THRESHOLD` bare for `_min_context_quality_score`
   (the anonymous-gate disease #1414 cured elsewhere). Added `CONTEXT_QUALITY_MIN` to
   `_abstain_policy.py`; reasoning.py now reads the named alias. Zero behavior change
   (same value object, pinned by test).
2. **Env-override range guard** — `DOMAIN_ABSTAIN_THRESHOLDS=tax:-0.5` used to silently
   DISABLE the tax abstain gate (score < -0.5 never true); `kbli:7` forced permanent
   abstain; `nan`/`inf` passed through. Parser now skips out-of-[0,1] entries with a
   warning (0.0 and 1.0 stay valid — inclusive, as already pinned by existing tests).
3. **Golden/boundary hardening suite** — new
   `backend/tests/services/rag/agentic/test_abstain_policy_hardening.py` (37 tests):
   golden matrix with hardcoded literal expectations at every EXACT boundary
   (==0.10 tax, ==0.12 visa, ==0.15 flat/zone-low, ==0.20 kbli, ==0.60 zone-high; all
   prod comparisons are strict `<`, so score==threshold PASSES), label-gate end-to-end
   through the real `OrchestratorResponseBuilder.build_core_result` (abstain flag +
   all three `abstain_reason` buckets — the prior test file for that module was an
   auto-generated skeleton with 4 skips), trusted-path zone semantics, empty-query
   fallback, None evidence_score, env-guard cases, unknown-domain-key harmlessness.
4. **Doc truth** — root `CLAUDE.md` §9 "Evidence scoring thresholds" bullet still taught
   the stale 2026-06-11 two-path photograph and declared "#31 open" — it is the very
   line that generated this mandate. Rewritten to the 5-named-gates truth with the
   panel-ruling warning. `docs_sync.py` regen folded into the same commit (W86),
   which also cured the standing P3 INDEX.md drift (plist count 118→117, the regen
   the canva-retire commit #1958 never shipped).

## Golden pre/post proof (mandate's regina)

- Baseline (pre-change tree): mandated suites `test_kg_langgraph` + `test_kg_subgraphs` +
  `test_confidence` + existing abstain suites = **211 passed**.
- The golden matrix + label-gate tests were run against the UNTOUCHED tree first and
  passed 29/29 (they pin current behavior); only the 8 intended new-behavior tests were
  red (range guard ×6, named-gate ×2).
- Post-change (incl. the Codex-driven nlm_verifier cure): hardening suite **38/38**,
  combined abstain+mandated **249 passed**, full RAG subtree
  (`backend/tests/services/rag/` + `backend/tests/unit/services/rag/`)
  **2551 passed, 152 skipped**. Same inputs, same abstain/cautious/confident decisions.
- Threshold VALUES untouched: 0.15 / 0.10 / 0.12 / 0.20 / 0.60 all identical.

## "Site n.12" sweep (W89 class-audit)

Exhaustive grep of every `evidence_score` comparison and threshold read outside the SSOT
module (non-test):

| Site | Verdict |
|---|---|
| `reasoning.py` ×8 comparisons (sync+streaming) | all read `generation_threshold` derived from `build_abstain_policy` — SSOT-compliant |
| `_reasoning_policy.py:99 should_apply_low_evidence_policy` | takes threshold as PARAMETER; both callers pass the SSOT-derived value — plumbing, not a 12th site |
| `orchestrator_response.py:99` `< 0.05` | reason-BUCKET edge (`no_relevant_context`), not a decision gate — abstain already decided; left anonymous, now covered by tests |
| `reasoning.py:746/1364` `< 0.5` | prompt-nudge band ("moderate evidence → precautionary wording"), affects wording not decisions — left, documented here |
| `nlm_verifier.py:23-24` `EVIDENCE_MIN/MAX = 0.15/0.60` | **Codex finding, CONFIRMED and CURED in this PR**: the NLM-verify trigger window reuses the CAUTIOUS band with its own fresh literals — would drift silently if the zone edges moved. Now sourced from `EvidenceScoreConstants.CONFIDENCE_LOW/HIGH` (same values, zero behavior change) + value-coupling tripwire test |
| `kg_auto_expansion.py MIN_EVIDENCE_SCORE`, `orchestrator_core.py:1061 > 0.6` (same KG-expansion trigger), `low_confidence_emitter.py 0.3`, `confidence.py 0.35/0.80`, `crag_router.py 0.15/0.60/0.70` | separate concerns (KG expansion gating, telemetry, SOURCE-confidence labels, retrieval routing refinement) — trigger/routing gates, not abstain decisions; pulling them into AbstainPolicy would couple unrelated semantics. Left, listed for the follow-up below |

## §Adversarial review (generator≠grader)

- Design council: SKIPPED, declared — the architecture was already council-reviewed at
  #1414 (panel 2026-06-14) and the residual scope shrank to small edits + one test
  suite; a fresh council would have been a rubber stamp (modus anti-sperpero gate).
- Codex GPT-5.5 red-team (read-only, on the diff + independent site-12 hunt) returned
  verdict "defective as PR" with 4 findings; each re-verified on disk by Fable:
  1. "Test suite not in the PR" — process artifact: the file was untracked because the
     review ran pre-commit. Non-defect (committed in this PR).
  2. `nlm_verifier.py:23/119` anonymous 0.15/0.60 window — **CONFIRMED, cured** (see
     sweep table). This is the real "site n.12" of the mandate.
  3. "Golden matrix wrong at ==0.60 (expects cautious)" — **REFUTED**: prod implements
     the HIGH edge as `<=` (`_abstain_policy.confidence_zone`, mirroring the pre-#1414
     streaming literals), so ==0.60 untrusted IS cautious; the golden matrix pins prod.
     The refutation did expose a lie in MY test docstring ("all comparisons strict <")
     — docstring corrected to state the per-edge semantics. W65 both ways: the refuter
     was wrong about the code and right about the doc.
  4. "Static guard scans only reasoning.py" — accepted in robust form: value-coupling
     tripwire for nlm_verifier instead of a brittle repo-wide source grep.
- Final on-disk grep re-executed by Fable (this session) — the last grep was not
  delegated.

## §Meta-pattern

**The organism's documentation of its own defects ages faster than the defects get
fixed — and stale defect-docs then GENERATE stale mandates.** The chain here: CLAUDE.md
§9 recorded the two-path finding on 2026-06-11 → #1414 fixed the substance on
2026-06-14 but did NOT update the §9 bullet (nor memory #6441) → the 2026-07-05 mandate
was written FROM the stale bullet → a full session was scoped at "migrate ~11 sites"
when ~0.5 sites remained. Same family as W90 ("anche il ground-truth invecchia") but on
the INTERNAL doc layer: every cure PR that closes a documented "open question" must
update the document that declares it open, in the same PR — otherwise the doc becomes a
mandate-generator for work already done. The antidote applied here: the §9 rewrite ships
IN this PR, and the mandate's own "RI-VERIFICA OGGI su disco" clause is what contained
the damage (GROUND falsified the photograph in ~10 tool calls instead of a wasted
migration). Corollary honored: the divergence-is-intentional ruling is now pinned in
THREE places that fail loudly (convergence tripwire test, golden matrix, CLAUDE.md §9
warning), so the next "tidier" cannot re-collapse it silently.

## §Solo-operatore

- **Deploy `nuzantara-rag`** — DECLARED FIREBREAK per mandate: the merged PR is this
  session's terminus. The RAG heart does not deploy without operator GO
  (skill `nuzantara-deploy`, CLAUDE.md §11 sequence). PENDING-ARMS line written.
- Nothing else requires physical/strategic operator action: no secrets, no migrations,
  no launchd, no fleet-runtime consumers of these modules outside the Fly app.

## Files touched

- `apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py` (+8: CONTEXT_QUALITY_MIN)
- `apps/backend-rag/backend/services/rag/agentic/reasoning.py` (site :187 → named alias)
- `apps/backend-rag/backend/services/rag/agentic/reasoning_utils.py` (env range guard)
- `apps/backend-rag/backend/services/rag/nlm_verifier.py` (window sourced from named constants — Codex finding)
- `apps/backend-rag/backend/tests/services/rag/agentic/test_abstain_policy_hardening.py` (NEW, 38 tests)
- `CLAUDE.md` §9 bullet (stale photograph → current truth)
- `INDEX.md` + `docs/AI_ONBOARDING.md` (docs_sync regen, same commit — W86)
