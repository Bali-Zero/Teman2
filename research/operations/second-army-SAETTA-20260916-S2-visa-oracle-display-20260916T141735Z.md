---
date: 2026-09-16
domain: operations
client_case: none
sources:
  - "infra/workflows/second-army.js + run-second-army.mjs, run live on M5 2026-09-16 with args ~/BATTAGLIA-20260911/SAETTA-20260916/second-army/S2-visa-oracle-display.json (the machine-written sections below)"
  - "shipping-session re-verification on disk, 2026-09-17: vitest src/app/(visa-oracle)/visa-oracle, tsc --noEmit, guilt run against main's OutcomeSheet.tsx"
adversarial_review: exempt-machine-run-report-verdicts-derived-on-disk-by-the-dux-and-a-fresh-shipping-session
---

# second-army run report

- mission: SAETTA-20260916-S2-visa-oracle-display
- colour: blue
- floor: 2
- promoted: false
- stamp: 20260916T141735Z

## Direction of verification (RULED 2026-09-15)
The inferior seats BUILD; the Dux VERIFIES on disk. A builder never grades its own output, and the Dux lane is never shown a builder's claim before deriving its own answer.

## Chain used
- dux (VERIFIES on disk): sonnet (family anthropic, lane model sonnet)
- builder roster (BUILDS, in fallthrough order): luna (openai), spark (openai), flash (google), deepseek-flash (deepseek), qwen-plus (alibaba), haiku (anthropic)
- anthropic-native grunt seat, legal last only: haiku
- floor-2 refuter candidates: spark, flash (one seat, on the frozen ref HEAD)

## Probe results
- luna: alive — Codex gpt-5.6-luna seat is alive. Command executed successfully with exit code 0. Stdout contains: OpenAI Codex v0.154.0 initialized, SessionStart hooks completed (one hook failed but system proceeded), UserPromptSubmit hooks completed, and genuine model reply "pong" in response to "reply pong" prompt. Tokens consumed: 18.032. No errors in stderr, no timeout.
- spark: not alive — Exit code 1. Codex returned HTTP 400 error (repeated twice): "The 'gpt-5.3-codex-spark' model is not supported when using Codex with a ChatGPT account." No reply pong received; model unavailable in current Codex configuration.
- flash: alive — stdout: "pong\n" — genuine reply, no error, exit code 0, completes instantly
- deepseek-flash: not alive — Exit code 1. Stderr: HTTP 429 insufficient_quota error — "Your token-plan 1-week quota has been exhausted. The quota will reset at 09-18 08:39:00 UTC." This is a quota exhaustion response, not a live model reply.
- qwen-plus: not alive — HTTP 429: insufficient_quota — TP1 token-plan 1-week quota exhausted. Reset scheduled 2026-09-18 08:39:00 UTC. No live model response received; quota-gating error instead.

## Dead tiers
- kimi (unknown): declared-quota-dead-2026-09-15
- qwen-cloud-code (unknown): declared-quota-dead-2026-09-15
- tp1-glm-5.2 (unknown): declared-quota-dead-2026-09-15
- tp1-deepseek-v4-pro (unknown): declared-quota-dead-2026-09-15
- spark (openai): probe-reported-not-alive — Exit code 1. Codex returned HTTP 400 error (repeated twice): "The 'gpt-5.3-codex-spark' model is not supported when using Codex with a ChatGPT account." No reply pong received; model unavailable in current Codex configuration.
- deepseek-flash (deepseek): probe-reported-not-alive — Exit code 1. Stderr: HTTP 429 insufficient_quota error — "Your token-plan 1-week quota has been exhausted. The quota will reset at 09-18 08:39:00 UTC." This is a quota exhaustion response, not a live model reply.
- qwen-plus (alibaba): probe-reported-not-alive — HTTP 429: insufficient_quota — TP1 token-plan 1-week quota exhausted. Reset scheduled 2026-09-18 08:39:00 UTC. No live model response received; quota-gating error instead.

## Tasks
### vo-candidate-order-business
- builder seat: luna (openai)
- builder claim (NOT evidence): Codex (GPT-5.6-Luna) analyzed visa_engine architecture and determined: candidate ordering for 'affari/riunioni' (business meetings) is not presentation-only—the frontend copies candidates verbatim from engine's `decision.candidates` tuple (api_models.py:474-476 constraint). Since order is engine-owned and the signed pack contains no RANKING rules (only ELIGIBILITY/HARD_FILTER/HUMAN_REVIEW), any D2→D1→D12 reordering requires seq-22 (signed pack modification), not frontend change. Codex saved checkpoint to continue with research/operations/vo-candidate-order-needs-seq22.md memo after inspecting OutcomeSheet diffs.
- dux verdict: NOT verified: dux-verification-failed-on-disk — test -f research/operations/vo-candidate-order-needs-seq22.md (MISSING); git grep -n "D2.*D1.*D12" -- apps/mouth (no hits in test files); Read apps/backend-rag/backend/services/visa_engine/evaluator.py:895-965; Read apps/mouth/.../engine-adapter.ts:1440-1500; Read apps/mouth/.../engine-response.ts:300-400; Grep "rejects candidate reorder" engine-response.test.ts -> Neither disjunct of the proof criterion holds on disk. (1) No vitest test asserts ['D2','D1','D12'] candidate order for the business-meetings purpose anywhere in apps/mouth — git grep for the pattern across visa-oracle test files returns nothing, and the only uncommitted diff to OutcomeSheet.tsx/.test.tsx (pre-existing in this worktree, unrelated to this task) concerns hiding empty documents/availability cards, not candidate order. (2) research/operations/vo-candidate-order-needs-seq22.md does not exist (`test -f` → MISSING). Independently tracing the order's source confirms it SHOULD require the second branch (backend signed-pack change) rather than the first: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts:1466 builds the display candidate list by `.map`-ing directly over `response.display.candidates` (the signed engine response) with no client-side sort; apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-response.ts:355-356 enforces `if (rank !== index + 1) invariant();`, and engine-response.test.ts:32-36 explicitly asserts the parser REJECTS a display candidate reorder. The actual ranking computation is apps/backend-rag/backend/services/visa_engine/evaluator.py:903-964 (`_rank_supported`), which sorts SUPPORTED proofs by `(-score, product_code, product_version_id)` where score comes from RANKING-stage rules in the compiled/signed rule pack — this is the signed engine ranking, not mouth presentation. So no work was done on either branch: no test was written, and the required research file was never created.

### vo-d12-sponsor-wording
- builder seat: luna (openai)
- builder claim (NOT evidence): Codex exec (gpt-5.6-luna) avviato su sponsor familiare → sponsor aziendale/garante (D12 explorer branch). Fase GROUND: localizzato nodo family_sponsor_confirmed e superfici di copy collegate. Contesto esaurito; handoff salvato per patch e verifiche. Nessuna modifica ai file in questo turno.
- dux verdict: NOT verified: dux-verification-failed-on-disk — git grep -n 'sponsor familiare' apps/mouth/src; git grep -n 'sponsor aziendale/garante' apps/mouth/src; git grep -ni 'sponsor' apps/mouth/src; git diff --stat -> Ran `git grep -n 'sponsor familiare' apps/mouth/src` → no matches (exit 1), and `git grep -n 'sponsor aziendale/garante' apps/mouth/src` → no matches (exit 1) either. A broader case-insensitive sweep (`git grep -ni 'sponsor'`, plus targeted greps for 'familiare', 'aziendale', 'garante', 'penjamin', 'family sponsor') across all of apps/mouth turned up only the pre-existing engine/flow identifiers (`family_sponsor_confirmed`, `family_sponsor_nationalities`, etc.) and i18n copy `"tree.family_sponsor_confirmed": "Family sponsor"` (EN, i18n.ts:732) / `"Sponsor keluarga"` (ID, i18n.ts:1713) — there is no Italian entry for that key at all, and nowhere does 'aziendale/garante', 'corporate sponsor / guarantor', or 'sponsor perusahaan / penjamin' appear. The only uncommitted changes on this branch (`git diff --stat`: OutcomeSheet.tsx + OutcomeSheet.test.tsx) are unrelated — they hide empty operational/service axis badges and empty document sections, which is Zero's ruling (c), not the sponsor-copy ruling (b). The required replacement string was never written; the second grep clause of the proof criterion fails, so I did not proceed to the vitest run.

### vo-hide-empty-cards
- builder seat: luna (openai)
- builder claim (NOT evidence): Codex ha implementato il render condizionale per le card 'documenti richiesti' e 'disponibilità' nel verdict display di Visa Oracle: nasconde la sezione documenti quando l'array è vuoto (guilt case), renderizza solo quando ci sono documenti (innocence case); nasconde i badge AxisBadge per operational e service quando lo status è UNKNOWN. Test aggiunto: una coppia guilt/innocence che verifica il non-rendering con array vuoto e rendering con contenuto.
- dux verdict: VERIFIED by the dux sonnet on disk: `git diff --stat; npx vitest run "src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.test.tsx"; git diff -- OutcomeSheet.test.tsx OutcomeSheet.tsx` -> git diff --stat shows only OutcomeSheet.test.tsx and OutcomeSheet.tsx under apps/mouth/.../visa-oracle/_components changed. `npx vitest run` for OutcomeSheet.test.tsx exits 0 with 41 passed. The test diff shows two relevant cases: "hides empty document and availability cards" (empty documents/operational/service → queryByRole/queryByText assert card absence) and "renders the required documents card when the product has documents" (getByRole heading + getByText present). The component diff wraps the documents section and operational/service AxisBadges in conditional JSX (`{candidate.documents.length > 0 && (...)}`, `{candidate.operational.status !== "UNKNOWN" && (...)}`) replacing the old always-rendered "unknown" placeholder.

## Floor-2 cross-family refuter
- seat: flash
- frozen ref: HEAD
- refuted: true
- reason: **UX regression**: The diff removes the fallback message "Document requirements unknown — not verified" that informed clients when documentation was unverified. The documents section now vanishes entirely when `documents.length === 0` (`{candidate.documents.length > 0 && (...)`), leaving clients without explanation of why no documents appear—they cannot distinguish between "documents not required" and "documents unverified."

**Asymmetry violation**: The component handles unavailable timeline/price status by rendering explanatory messages (lines 430–443, 479–480). Documents now silently hide instead, violating the component's stated PR-O4 honesty principle (lines 139–154): "never ... mis-attributed to the visitor" and render holds transparently. Hiding documentation state entirely without explanation crosses from "not fabricating" into "not explaining"—a failure to be honest about what is and isn't known.

**Test coverage regression**: The old test verified a user-facing fallback message existed. The new test only checks the heading is absent, with no assertion that a replacement explanation is rendered. If `documents.length === 0`, the new code renders nothing; the test does not verify any user sees why.

## What a reader must check on disk
Confirm this file exists at the path above, that every owned file listed per task exists with the claimed content, and that every VERIFIED verdict above names a command the dux (sonnet) actually ran — the builder's claim is never the evidence.

## Shipping-session disposition (2026-09-17, fresh Opus 5 session, re-verified on disk)
- vo-hide-empty-cards: SHIPPED. Proof re-run by the shipping session after merging origin/main (vitest OutcomeSheet.test.tsx green, diff limited to OutcomeSheet.tsx/.test.tsx). The floor-2 refuter's objection (no "documents unknown" explanation) is overruled by Zero's decision (c) of 2026-09-16: hide the cards until they have content.
- vo-candidate-order-business: the builder wrote `research/operations/vo-candidate-order-needs-seq22.md` after the Dux verify pass; its evaluator.py / evaluate_path.py / api_models.py line references were re-checked on disk and hold. The order is engine-owned, so this task stops here and goes to the seq-22 lane (D26). No mouth reorder shipped.
- vo-d12-sponsor-wording: DISCARDED (backup in the SAETTA logs). The late builder edit rewrote the shared `q.family_sponsor_confirmed` / `tree.family_sponsor_confirmed` copy, which the family and diaspora walks also ask, so spouses and children would have been asked about a "corporate sponsor / guarantor". The proof string `sponsor aziendale/garante` also has zero hits. A correct fix needs D12-scoped copy.
