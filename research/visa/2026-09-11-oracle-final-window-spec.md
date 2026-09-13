---
adversarial_review: gemini-3.1-pro
date: 2026-09-11
domain: visa
client_case: none
sources:
  - /Users/nuzantara/nuzantara/.worktrees/mouth-visa-review-reason-audit-20260911/research/visa/2026-09-11-oracle-final-window-spec.md
---

# Visa Oracle — final converged window spec (Fable 5.1 + Astra), 2026-09-11

Status: CONVERGED — v6.2 (v6.1 launch-env fix + decisions file on the Mini desk). Three adversarial rounds with Astra (`gpt-6-astra` xhigh): REWORK on
Fable draft v2, REWORK on v3, ACCEPT-WITH-EDITS on v4 (applied in v5). v5 was then read by an
external panel — Gemini 3.1 Pro (High) via `agy` and Kimi K3 via `kimi`: both LAUNCH WITH
EDITS; the edits that hold are folded here (§8 lists what was rejected). Qwen 3.8 Max was
requested but NOT received: the TP1 `qwen` seat on Mini answers HTTP 403 "access to model
denied" for every Qwen model (3.8-max-preview, 3.7-max, 3.7-plus, 3.6-plus, 3.6-flash) — a
seat-eligibility problem for the operator, not a model choice; re-run the panel read when the
seat is restored.
Every objection verified on disk by Fable before folding.
Prepare-only document: no code, no release, no ENFORCE/pack change. Sibling packages, ALL
UNCOMMITTED on Mini at the time of writing (pin by absolute path + sha256, not by commit):
Astra `docs/plans/mouth-final-20260911/{README,LAUNCH,W0-oracle-reasons}.md` in worktree
`/Users/nuzantara/nuzantara/.worktrees/docs-mouth-final-windows-20260911` (branch
`agent/mini-pro2/docs/mouth-final-windows-20260911`, NO PR yet) — sha256 pinned here so a
drifted copy is detectable: README `073e57ded13ddbd6e113a338ac95dd8a67f227ef152baa4934ef80db66693c30`,
W0 `ae3f0ae9c664da75336f5e9e31d93960010896de8f21c4b96afae853c0b5b928`,
LAUNCH `77baf4451c741b98f97e8d59b5a8ca8efae8509be0f21aa2441114339b51d903`; Astra's audit
README `d8102e736d5602be33c9c8b668a91d6f245adb30454bf754cda8add1e0dd029b`, census.json
`11fe7c1886cf2559493811f8cbdbb883b274f797eaaae3f2e6bb90261f12e704` (this spec's own hash is
recorded in the session memory and chat, it cannot contain itself); the topic-5 R19 map is the
only thing on PR #6124 (head `d23454ce`, branch `docs/mouth-r19-design-map-20260911`). This file supersedes
Fable draft v1/v2 (scratchpad only) and EXTENDS Astra's `W0-oracle-reasons.md`; it does not
replace it.

## 1. Verified ground (2026-09-11, Mini; all numbers re-measured, none inherited)

| Fact | Value | Evidence |
|---|---|---|
| Prod mode / pack | ENGINE (ENFORCE), seq-20 v2026.9.6 | `probe_evaluate.py --traffic-source synthetic_driver` |
| Walk census, no disclosure flags | 67 walks: 55 SUPPORTED / 10 NO_PATH / 2 NEEDS_INPUT | `test_interview_walk_census.py` 15 passed |
| Same corpus with real frontend flags | 31 / 7 / 0 / 29 HUMAN_REVIEW (+5 edge cases → 34) | Astra `research/visa/2026-09-11-review-reason-audit/census.json` |
| Review population | ACTIVITY_BOUNDARY 13 (5 invest, 6 retirement, 2 other); AMBIGUOUS_SPONSOR 16 (8 family, 8 diaspora); UNCERTAINTY 5; BRIDGING_* 3; VOA 2 | same census, `jq '.clocks.current.rows'` |
| REVIEW_REASON_COPY | 9 mapped / 38 codes in the STRUCTURAL inventory (20 pack + 18 backend; not all 38 proven reachable); 29 fall to the generic sentence | `engine-adapter.ts:416`, audit README |
| Exhaustiveness test blind spot | scans only `stage === HUMAN_REVIEW`; misses HARD_FILTER/ELIGIBILITY with `on_unknown=HUMAN_REVIEW` (3 BRIDGING_* emitted by the real evaluator in Astra's SYNTHETIC OFFLINE replay, VOA_NATIONALITY_ONLY structural only) | `engine-adapter.test.ts:727`, `evaluator.py:359/383/741/878` |
| `review_reasons` user-facing | yes: `buildEngineOutcome` → `OutcomeSheet.ReasonList`, EN/ID + source links | `OutcomeSheet.tsx:134,555` |
| Two NEEDS_INPUT walks | offshore/retirement/{property,undecided}/age64 on `family.sponsor_confirmed`; without flags the UI offers "Answer this" (`questionForFact` layer 2); with flags the policy adapter turns them into ACTIVITY_BOUNDARY review and empties `missing_facts` | `evaluate_path.py:1342`, tsx replay |
| Contract invariant | `HUMAN_REVIEW_REQUIRED` FORBIDS `missing_facts` on both sides | `models.py:1426`, `engine-response.ts:251` |
| Contact panel | "WhatsApp handoff is not configured" = `ConsentHandoff.tsx:64` fallback; proves no VALID `NEXT_PUBLIC_VISA_ORACLE_WHATSAPP_NUMBER` reached the component, not that the Vercel var is absent | `ConsentHandoff.tsx:100,175` |
| Corner state | LIVE STATE stale at 2026-09-06 (PR-3 #5855, PR-5 #5918/#6051 never appended); Astra's fix is uncommitted in worktree `mouth-visa-review-reason-audit-20260911` | `git status` there |

Dropped from Fable v2 after review: **PR-M3** ("keep `missing_facts` under HUMAN_REVIEW") —
it violates the contract on both sides and would need a schema change plus renderer
changes across owners; after PR-O3 below the two walks collect the fact anyway.
**D2 as "is the diaspora tile too wide"** — wrong population; replaced by D2 below.

## 2. Windows: TWO, not three (Astra cap "max two operative windows", Fable agrees)

| Slot | Window | Host | Scope (exclusive, frozen for others) |
|---|---|---|---|
| ENGINES | **W-ORACLE** = Astra W0 extended (this spec §3) | Mini | FROZEN FOR OTHERS (nobody else writes here; it does NOT mean W-ORACLE may write all of it — see the read-only list below): `apps/mouth/src/app/(visa-oracle)/**` (whole group: `_lib`, `_components`, `oracle.css`), `apps/mouth/scripts/visa-oracle/**`, `apps/mouth/e2e/visa-oracle-*.spec.ts`, `apps/backend-rag/backend/tests/services/visa_engine/**`, `apps/backend-rag/backend/scripts/visa_engine/**` (new read-only inventory script), `.agents/skills/visaoracle/**`, `research/visa/**` |
| WEBSITE | Astra package: **W2 team** → W7 identity (only if D-A) → W4 news → W5 home; W6 KBLI only after W5 + explicit go | Pro | as declared by topic 5 and `docs/plans/mouth-final-20260911/W2..W7`; NEVER `(visa-oracle)/**`, `visa/**`, root `layout.tsx`, `packages/core/tokens/**`, `team-roster.ts`; `kbli/**` frozen EXCEPT the presentation files W6 owns, and only once W6 has its explicit go; shared consumers (Footer, NewsHero, NavShell) opt-in with byte-identical defaults proven on `/v2`, KBLI, reader |

Read-only for W-ORACLE, exactly as W0 §2: `evaluate_path.py`, `evaluator.py`,
`models.py`/OpenAPI, packs, pricing, engine rules, `oracle.css`, layout/theme, QUESTIONS
(`flow.ts`/`tree.ts`) and storage/consents. PR-O3 and PR-O4 below touch questions and the
outcome presentation: they are DECLARED SCOPE DELTAS (Δ1, Δ2), each gated on Zero's explicit
yes (D6). Δ1 opens `flow.ts`/`tree.ts` + the walk corpus; Δ2 opens `OutcomeSheet.tsx`
content/markup, `i18n.ts`, `outcome-fallbacks.ts`, `ConsentHandoff.tsx` text — `oracle.css`
stays READ-ONLY even under Δ2 (a styling need is a further delta, reported, not taken). Until
D6 the W0 perimeter stands unchanged and the window ends at PR-O2 with a handoff. Anything
else beyond the perimeter is a NEW mandate, never a silent extension. The Oracle route mounts
no NavShell/Footer/NewsHero (its layout renders children + bootstrap only), so the website
window's shared-chrome work cannot reach it; the only global file it may touch is
`globals.css` and only as an additive scoped `.r19-*` block. The Studio windows W1/W3 enter the ENGINES slot only if Zero rules M = both.

Roles, both windows: Opus 5 xhigh orchestrator (no hands), one Sonnet 5 implementer via
`scripts/agent_start.py` worktree (`agent/<host>/mouth/...`), refuter of a different family
(`codex exec --sandbox read-only`, generator ≠ grader) on every PR, FRESH Opus 5 xhigh gate on
the PR HEAD before merge, ship-lifecycle end to end (review → merge → arm → deploy →
prove-live) by the window itself; external seats prepare only. One PR one concern,
≤ ~400 net lines, `Bites:` line naming consumer + observation, brief with
`scripts/ci/evidence_paths.py`, no `--no-verify`, no compound push/PR/merge command.

## 3. W-ORACLE deliverables, in order (each its own PR from fresh `origin/main`)

- **PR-O0 docs/research (docs-only: no deploy, prove = visible on main)** — ship Astra's audit branch content + this spec: `research/visa/2026-09-11-review-reason-audit/**`, `live-state-log.md` entries for PR-3, PR-5 and the 2026-09-11 audit, SKILL.md CURRENT POSITION at 67 walks / 31-7-0-29. Bites: `grep -c "67" SKILL.md` and the log entry visible on main.
- **PR-O1 census + inventory (BASELINE BEFORE any interview change)** — corpus carries the real `mapDisclosedReviewFlags` output; pin 31/7/0/29 at `signed_at` AND current clock, original 67 walks separated from the declared extensions (unsure, foreign sponsor, review gate, non-current source); new read-only inventory script under `backend/scripts/visa_engine/` deriving every review code from ALL stages with `on_unknown=HUMAN_REVIEW` ∪ REQUIRE_REVIEW rules ∪ backend emitters (AST, not a hand list); `engine-adapter.test.ts` consumes it. Bites: a fabricated new backend code or pack code turns the test red; a flag added/removed turns the census red. Note: this PR touches `apps/backend-rag/**`, and merging a backend-rag PR deploys `nuzantara-rag` by itself — script-only change, but prove-live must confirm `/health` and the probe after the merge. The `signed_at` clock is the deterministic GATE; the current-clock run is informational.
- **PR-O2 copy QW-4b (needs D1: do not OPEN this PR before D1 exists; arming auto-merge at open is then correct)** — dedicated EN/ID copy for all 29 unmapped codes; product names verbatim from the pack; UNKNOWN never worded as exclusion ("we could not confirm X", never "violation"); existing 9 entries re-checked for truthful TRUE/UNKNOWN wording (today CALLING_VISA_REVIEW asserts list membership and CITIZENSHIP_LIST_DIVERGENCE asserts conflicting answers even when the rule fired on an UNKNOWN fact); `KNOWN_UNMAPPED` empty; `CLIENT_UNABLE_TO_VERIFY_DETAIL` documented as the client-side technical exception with its own text; no price/time/claim/credential in any sentence. Bites: exhaustiveness test green with empty gap list + real adapter→OutcomeSheet render test EN/ID for every code.
- **PR-O3 interview = scope delta Δ1 (needs D6)** — `flow.ts`: `retirement/property` and `retirement/undecided` ask `family_sponsor_confirmed`; regenerate corpus (`npm run visa-oracle:walk-corpus -w apps/mouth`), re-pin `walk-corpus-determinism.test.ts` and the census with `WALK_DEAD_END_ALLOWLIST` empty; PR body states the measured delta (expected 2/10/55 → 0/10/57 without flags, MEASURED not assumed) and the flagged delta vs PR-O1. Invariant: zero NEEDS_INPUT without a reachable question, before AND after the disclosure adapters; relabelling to review is not a cure; NO_SUPPORTED_PATH is a verdict. Acceptance ALSO requires D5: the measured decisiveness meets the D5 target; without D5 this PR's acceptance is PENDING, not PASS. If the measured delta contradicts the expectation above, STOP and report — never force the pin to match the spec.
- **PR-O4 explain the cause = scope delta Δ2 (needs D6)** — under HUMAN_REVIEW the OutcomeSheet names only DEMONSTRATED causes: for answer-attributable holds ("you answered 'not sure' to <question>") a prerequisite-safe edit link; source/system holds (DECISIVE_*, SAFETY_CRITICAL_*, MINOR_GUARDIAN_PRIVACY) worded as what they are; the contact panel never shows a configuration string to the visitor (neutral fallback + internal alert). Verify EN/ID, light/dark, keyboard, reduced motion, 320/390/1440; attach before/after screenshots pinned to base/candidate SHAs. Bites: `OutcomeSheet.test` + `e2e/visa-oracle-v2` pin the new block, AND a human-readable render of every residual review class listed in D5 (tests going green is necessary, not sufficient: the visitor must read a specific cause). Without D5, PENDING.
- **Order is strict**: O0 → O1 → O2 → O3 → O4. A missing D1 halts the chain at O1 (O3/O4 are never built ahead of O2, even with D6 in hand). If D6 = no, the two retirement walks keep the existing "Answer this" follow-up forever and PR-O2's copy must remain correct for that reachable state.
- **Out of scope, new mandates**: narrowing the ACTIVITY_BOUNDARY / AMBIGUOUS_SPONSOR holds (D2 outcome → adapter or pack fold seq-21 + M5 signing ceremony); any `Decision` schema change; DPIA High rows; gold replay on seq-20; team manual sign-off.

## 4. Gates (every PR, both windows)

`vitest` apps/mouth full · `test_interview_walk_census.py` + `test_seq20_pack.py` from the
backend root in the project venv with `PYTHONPATH=.` · e2e `visa-funnel-fusion`,
`visa-oracle-v2`, and `visa-oracle-fullstack` via its disposable-DB runner
(`VISA_ORACLE_FULLSTACK=1`, otherwise it SKIPS and proves nothing) · tsc/lint/build ·
after deploy: `probe_evaluate.py` synthetic_driver proves `mode=ENGINE` and that the
`rule_pack_id`/`sequence` it answers with equal the ACTIVATION-LEDGER record in force
(`repository.py` range join on `legal_period`/`system_period`). Read that record via the
readonly role where it exists (Pro: Keychain `nuzantara-postgres-readonly`); on Mini that
Keychain item does NOT exist (verified 2026-09-11), so the accepted proof there is the live
probe's `rule_pack_id`/`activation` compared with the LIVE STATE activation entry — the same
alternative the 2026-09-06 ceremony notes allow. Never "the highest signed file on main":
signing does not activate, and never a hardcoded sequence · the SHARED control
screenshot pair 390+1440 of `/visa-oracle` and `/visa/second-home/studio`, identical
before/after for the website window, changed only by PR-O4 for the Oracle window · no
`traffic_source=real`, no lead sent, no PII in any artifact.

**Rollback (owner = the shipping window, Zero informed in the report; never a data or rule
change as a UI rollback):** a PR whose prove-live fails or whose deployment fails/times out
is reverted with `git revert` in a NEW PR (auto-merge armed) and, for `apps/mouth`, the
previous Production deployment is re-promoted with `vercel promote` immediately, before the
revert lands; for `apps/backend-rag` the revert PR IS the redeploy. The mode kill switch
(`fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag`) is NOT a UI rollback and
is not touched by these windows. Window caps: appetite 5h per window (Astra W0 §6), two
reworks per block then checkpoint, three reds for the same cause suspend the PR, never a
closure "for budget exhausted". Merge priority on an unexpected shared file: the PR already
armed wins, the other rebases; the collision is reported to Zero.

## 5. Decisions for Zero (each blocks only its dependent PR, never the launch)

- **D1** authorize drafting the EN/ID copy in-window (refuter + Opus gate judge it; Zero does not review) → gates PR-O2.
- **D2** evidence-backed disposition of the 13 ACTIVITY_BOUNDARY and 16 AMBIGUOUS_SPONSOR reviews: legitimate as-is, or to narrow (→ new mandate, possibly seq-21 ceremony on M5). Not a launch blocker.
- **D3** contact: set a valid `NEXT_PUBLIC_VISA_ORACLE_WHATSAPP_NUMBER` in Vercel `mouth` Production + redeploy/promote (number = business + consent = owner); the window verifies afterwards. Gates only the handoff completion.
- **D4** website identity: D-A (R19 Direction A: paper/slate/copper + Fraunces/Manrope on home + blog group, replaces R4 only there) or D-B (composition only, current colours/fonts). Fraunces/Manrope ARE R19 Direction A (`apps/website/src/styles/brand-fonts.css` at `6603d29`); adopting them into mouth still needs D-A. Gates W7 only.
- **D5** acceptance denominator and target: the 67-walk corpus + declared extensions as the denominator; decisiveness target and the permitted residual-review classes stated explicitly. "Almost always" is not an acceptance criterion.
- **D6** scope deltas Δ1 (PR-O3, interview asks `family_sponsor_confirmed` on two retirement branches) and Δ2 (PR-O4, outcome explanation + neutral contact fallback): yes/no each. Without D6 the window stops at PR-O2.
- **M** engines slot: Oracle only (assumed by this spec), or both (Studio W1→W3 queue after W-ORACLE).

## 6. Launch prompt — W-ORACLE (paste in a fresh `claude --model claude-opus-5 --effort xhigh` on Mini, cwd `~/nuzantara`)

```text
Mandate SHWEB-20260911 / W-ORACLE (Astra W0 + declared deltas). Read first, fully, from
these ABSOLUTE paths on Mini (all uncommitted at spec time; pin each by sha256 in your
brief, never assume they are on main): (1) this spec, binding:
/Users/nuzantara/nuzantara/.worktrees/mouth-visa-review-reason-audit-20260911/research/visa/2026-09-11-oracle-final-window-spec.md;
(2) Astra's audit README + census in the same worktree under
research/visa/2026-09-11-review-reason-audit/; (3) Astra's package
/Users/nuzantara/nuzantara/.worktrees/docs-mouth-final-windows-20260911/docs/plans/mouth-final-20260911/{README,W0-oracle-reasons}.md;
(4) .agents/skills/visaoracle (SKILL.md LIVE STATE + references/live-state-log.md newest
entries) on origin/main. PR-O0 copies (1) and (2) into your worktree and commits them. (5) Zero's decisions
D1–D6 and M live in /Users/nuzantara/Desktop/w-oracle-launch-20260911/02-DECISIONI-ZERO.md: read it at
start and before every PR; a decision not written there is MISSING. Machine check, base
SHA, Pro reachability. You orchestrate (Opus 5 xhigh, no hands); one Sonnet 5 implementer
in a NEW worktree via scripts/agent_start.py --lane mouth --task-id shweb-w-oracle-20260911,
depth 1, max 50 tool calls / 45 active minutes per child; refuter = codex exec
--sandbox read-only on every PR (generator≠grader); fresh Opus 5 xhigh gate on each PR HEAD.
Scope EXCLUSIVE as spec §2; everything else frozen; evaluate_path/evaluator/models/pack/
pricing/engine rules/oracle.css/questions/consents read-only per W0 §2; no Decision schema
change; missing_facts never under HUMAN_REVIEW. Deliver PR-O0 → PR-O1 → PR-O2 (only after
D1); then PR-O3 and PR-O4 ONLY if Zero has said yes to D6 (they are declared scope deltas on
questions and outcome presentation) — otherwise stop after PR-O2 with a handoff. Exactly as
spec §3, one PR per concern from fresh origin/main, ≤ ~400 net lines, Bites: line naming
consumer + observed proof, brief via scripts/ci/evidence_paths.py. Gates per spec §4 on
every PR; fullstack e2e only through its disposable-DB runner. Ship each PR end to end:
review → merge (auto-merge armed at open, `gh pr merge --auto` bare) → deploy → prove-live
with probe_evaluate synthetic_driver (rule_pack_id must equal the activation-ledger record
in force: readonly role on Pro, or on Mini the probe vs the LIVE STATE activation entry) + the
shared screenshot pair; never traffic_source=real,
never a lead, never PII in artifacts. No ENFORCE/SHADOW flip, no pack signing/activation.
STOP and report to Zero if: a frozen file appears in a diff, a test goes red three times for
the same cause, a change needs a schema/rule/legal-source decision, a hold narrowing looks
required (that is D2, a new mandate), or a decision D1/D3/D5 is missing for the next PR —
finish every PR that does not depend on it first. Update SKILL.md LIVE STATE + the log in
the same PR that changes state. Report: PR numbers, measured census before/after, list of
codes with copy, live proof, what remains.
```

## 7. Launch — WEBSITE slot

Use Astra's `docs/plans/mouth-final-20260911/LAUNCH.md` prompts verbatim: W2 team first
(no ruling needed), W7 only after D4 = D-A, then W4, W5. The topic-5 Wave A/B prompt is
folded into those lots; do not run both schedulers. Astra objection carried over: preserving
NavShell's default is not enough — Footer and NewsHero are consumed by KBLI and `/v2`, so every
shared consumer needs an opt-in variant with a proven byte-identical default.

## 8. Panel edits rejected, and why

- Gemini: "cut the codex refuter" — no: generator ≠ grader on every PR is Builder Contract 5, not a cost knob.
- Gemini: "merge PR-O0 into PR-O1" — no: one PR one concern; PR-O0 is docs-only and costs no deploy, so the saving is nil.
- Kimi: "merge PR-O3 into PR-O2" — no: they answer different owner decisions (D1 vs D6) and different perimeters (copy vs questions).
- Kimi: "drop the fresh Opus gate per PR" — no: the per-PR on-disk gate is a repo rule (CLAUDE.md §5 routing); it is the cheapest of the five gates.
- Kimi: "single clock pin" — partially: `signed_at` is the only GATE, the current-clock run stays informational (Astra's ask, kept).

## Adversarial review

This spec is authored by Fable 5.1 converged with Astra (`gpt-6-astra`) across three
adversarial rounds documented in the body above (§8) — Astra is a co-author of the
convergence, not an independent reviewer, so its rounds are not counted toward R1
independence. The independent reviewers are the OTHER families named in this file's own
header and §8:

- **Gemini 3.1 Pro (High), via `agy`** — reviewed v5, verdict **LAUNCH WITH EDITS**. Edits
  were folded into or explicitly rejected within §8 above (see the per-point disposition
  list); no edit from this round was silently dropped.
- **Kimi K3, via `kimi`** — reviewed v5, verdict **LAUNCH WITH EDITS**. Edits were folded
  into or explicitly rejected within §8 above (see the "Kimi:" disposition lines).
- **Qwen 3.8 Max** — requested as a third independent family; not received at the time this
  spec converged. Recorded as an open gap, not fabricated as a verdict.

This section is appended documentation of the review already performed on this spec's
pinned body; the pinned body itself (everything above this heading, before this appended
section) is unchanged from the reviewed content.
