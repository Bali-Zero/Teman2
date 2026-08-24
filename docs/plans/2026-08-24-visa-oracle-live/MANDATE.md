# MANDATE — VISA ORACLE: from shadow to voice, absorbing GARUDA

> For the **Opus 5 orchestrator session on Pro** (the product's home machine — NB-2/NotebookLM
> MCP and postgres MCP live there; the 84-file engine suite needs Pro's RAM).
> Procedure: `docs/factory/ASSEMBLY-LINE.md`. Sibling product already dispatched:
> GARUDA VOA (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`, home M5).
> Owner blueprint (approved picture): artifact `claude.ai/code/artifact/9454adba-fd56-4442-aaad-8274d7804bf7` (rev2).
> No duration estimates anywhere in this mandate — owner ruling: worked well, this can close
> fast; pace is set by gates going green, not by calendar prose.

## 1. The product (owner-framed)

Visa Oracle is the single front door of every Bali Zero visa sale. An anonymous visitor tells
their situation to a beautifully designed interactive decision tree — one question at a time,
the path visibly narrowing from 38 products to theirs ("magia decisionale", owner's words; the
current `balizero.com/visa-oracle` page is "un motore in panne" and its experience is rebuilt,
not patched). The Oracle answers with THE right visa (or two candidates with the differences
explained), one all-inclusive price, and the declared service tier — then hands off to the
GARUDA commerce rails (account, documents+OCR, checkout, parcel-style tracker, portal
delivery). **The Oracle absorbs GARUDA**: VOA becomes the first product sold inside this
funnel.

**Three service tiers (owner ruling — load-bearing):**

- **T1 self-purchase puro**: basic services (VOA). No consultant needed.
- **T2 self-purchase + consultant included**: the significant visas (D12 investor, E31 family,
  E33 second home, …). The client buys online AND the assigned consultant always makes
  contact after purchase — part of the service, inside the price, never a fallback.
- **T3 assisted-only (for now)**: products whose rules are incomplete are never sold solo —
  the Oracle recognizes them and routes straight to the consultant. Never an invented answer.

**The consultant thread (invariant, every tier):** a visible "Talk to a consultant" control on
EVERY screen — wizard, verdict, checkout, portal — invokable at ANY moment, including before
buying. Self-service is an option, never an obligation.

## 2. Ground truth to build on (verified, do not rebuild)

- Engine LIVE in SHADOW: `apps/backend-rag/backend/services/visa_engine/` — deterministic
  evaluator, tri-state rules (HARD_FILTER → HUMAN_REVIEW → ELIGIBILITY → RANKING), 5-outcome
  contract (NEEDS_INPUT / SUPPORTED_CANDIDATES / HUMAN_REVIEW_REQUIRED / NO_SUPPORTED_PATH /
  TEMPORARILY_UNAVAILABLE), 44 fact paths, 84 test files.
- Signed rule packs: `visa_rule_packs` bitemporal, Ed25519-signed bundles, two-login
  activation ceremony (credential path: memory
  `reference_visa_pack_activation_ceremony_credential_path_2026_08_24` — PK is `id`, writer
  role minted ephemeral from `postgres`/$OPERATOR_PASSWORD). Current pack: seq-13.
- Public router `/visa-oracle` (recommend/chat/handoff) + mouth wizard (EN/ID) wired
  fire-and-forget to shadow.
- Retention primitive migrations 264/266/268 (fail-closed, Zero-recorded policy) — GARUDA's
  L1 lane is extending it; reuse, never duplicate.
- Doctrine corpus: `research/visa/doctrine-factory/` (cards for 38 products, query-bank,
  reachability, freshness). The three local M5 blueprint packages dated 15/8
  (`visa-oracle-blueprint/`, `visa-oracle-adjudication/`, master prompt) are probably
  superseded by what already landed on main — reconcile (mine for unused good ideas), do not
  resurrect as authorities.
- **ENFORCE is NO-GO by owner ruling** until the signatures in §5 — SHADOW until then.

## 3. Lanes (integration branch `feature/visa-oracle` on Pro — local-first)

Same workflow as GARUDA: branch from fresh origin/main, nightly push (backup, no PR), one
lane = one session = one worktree, ONLY the orchestrator merges into the integration branch,
morning rebase, evening cross-family refuter pass on the day's diff, final landing as a short
train of reviewable PRs, everything behind flags.

| Lane                                  | Scope                                                                                                                                                                                                                                               | Builder                            | Refuter                                                                                   |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------- |
| V1 la via semplice (products)         | Cure the 9 BLOCKED products (E23U/V, E28B/C/D/F, E33A/B/C) and the 5 never-asked interview facts, then sweep remaining gaps — **per-product method below**                                                                                          | Sonnet 5 (one session per product) | Kimi K3                                                                                   |
| V2 magia decisionale (wizard)         | Rebuild the public wizard experience: real guided decision tree, one question at a time, visible path-narrowing 38→1, crafted transitions, human language, EN/ID, consultant control ever-present. Elegant, never gaudy.                            | Codex Terra + Haiku grunt          | Opus 5 critic gate (screenshots, mobile-first, WCAG AA) — blocks until the magic is there |
| V3 commerce graft + consultant thread | Verdict → "proceed" on GARUDA rails (consume GARUDA's FROZEN contracts from main — never share files cross-machine); consultant: ever-present control, auto-assignment in CRM, T2 post-purchase entrance, WhatsApp continuity with practice context | Sonnet 5                           | Sol                                                                                       |
| V4 ignition (shadow → voice)          | Gold-persona suite (engine↔consultant zero-divergence report), DPIA draft, wizard-data TTL proof on the retention primitive, ENFORCE flag plumbing, business-invariant probes (synthetic wizard journey + dead-man)                                 | Sonnet 5                           | Sol + Gemini                                                                              |

**V1 per-product method (owner ruling — THE anti-loop rule, verbatim intent):** for each visa,
exactly three moves — **(1)** the visa index in question; **(2)** what it is and what it does;
**(3)** interrogate **NB-2** to understand how to draw it on the decision tree and build all
the questions that help. One product, one session, one verified result (rules, tree placement,
questions, tests, NB-2-cited card), then the next. Three reds on the same cause → the lane
STOPS and hands off (assembly-line rule 8) — the infinite negative loops previous sessions
fell into are a banned failure mode, and a session that catches itself philosophizing instead
of shipping a product card must stop. Until a product passes, it stays T3.

Contracts to FREEZE before dispatch: wizard↔engine wire schema (the 5-outcome contract is the
base — freeze the public projection) · verdict→checkout handoff event (consumes GARUDA's
order contract from main) · consultant-assignment event to CRM · product-card schema for V1
output (index, definition, tree placement, questions, NB-2 citations, tier).

## 4. Gates & verification

- Per assembly-line: one cross-family refuter per PR; full adversarial always on engine rules,
  pricing, and the checkout handoff.
- V1 acceptance per product: rules reachable (no orphan fact paths), a cross-family seat
  (Kimi K3 — the DeepSeek seat was RETIRED 2026-07-19) re-derives the eligibility outcomes on
  the product's gold personas and matches, NB-2 citations verbatim. "Reachable" here means the
  narrow thing it says: `reachable = bool(support)` is STATIC, so it is not evidence the product
  evaluates correctly — the gold re-derivation is what carries that weight.
- V2 acceptance: critic gate PASS on the full journey on a phone + the 5-state contract fully
  expressed in the UX (including honest hand-offs) + consultant control on every screen.
- Gauntlet: full Playwright wizard journeys (happy + every 5-outcome path + tier routing) on
  an ephemeral env; synthetic wizard journey probe armed in prod (SHADOW mode counts — probe
  asserts the shadow verdict pipeline, then flips meaning at ignition).
- Ship dark; at partial rollout put real users in front of the wizard and watch them.

## 5. Owner switchboard (NOTHING blocks — build in shadow, collect signatures at the end)

| #   | Decision                | Prepared for Zero                                            | Gesture           |
| --- | ----------------------- | ------------------------------------------------------------ | ----------------- |
| 1   | DPIA                    | drafted on the real flow                                     | read, sign        |
| 2   | Wizard-data retention   | TTL proposal, auto-purge proven on the primitive             | approve or change |
| 3   | Gold-persona rehearsal  | zero-divergence report engine↔consultants                    | acknowledge, sign |
| 4   | Product→tier map        | all 38 mapped to T1/T2/T3 with recommendation                | correct, approve  |
| 5   | Prices & terms per tier | all-inclusive list + T2 consultant-included terms            | approve           |
| —   | IGNITION                | ENFORCE flag flip + the wizard becomes the site's front door | flip              |

## 6. Constraints the orchestrator must carry

- Home = Pro (`nuzantara@Nuzantara`, checkout `~/Desktop/nuzantara`); NB-2 via NotebookLM MCP
  profile `default`; postgres MCP read-only for measures; rule-pack ceremonies follow the
  credential-path memory exactly.
- GARUDA contact surface: ONLY through contracts landed on main. A change needed in GARUDA's
  rails is a request to the GARUDA orchestrator (fleet mailbox), never a cross-edit.
- Seat quota check before lane assignment (`~/.claude/seat-quota.json`); Team seat last
  resort; TP1 probe `GET /models`, reasoning seats `max_tokens ≥ 16000`; `agy` argv-only;
  headless seats `< /dev/null`.
- Merge queue: arm `gh pr merge --auto` bare; draft does not dequeue (W126).
- Law 2 output boundary (vendor-neutral, all five families at parity per Zero ruling): no
  client PII cleartext in persisted outputs/logs/memories/artifacts.
- ENFORCE stays OFF until every §5 signature exists — no exception, no partial ignition.

## 7. Definition of done

DONE = on production, in shadow-complete state: the rebuilt wizard runs the full magic journey
on a phone (EN/ID) with the consultant control everywhere; all 38 products answer through the
5-outcome contract with the tier map applied (no product silently unreachable); the
verdict→GARUDA-checkout handoff works end-to-end for a T1 and a T2 test case; gold-persona
report shows zero divergences; the synthetic wizard probe is green with dead-man armed; and
the §5 switchboard is filled with prepared proposals. Then Zero signs five times and flips
ignition — and every visa sale at Bali Zero enters through one door.
