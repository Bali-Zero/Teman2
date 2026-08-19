# /secondhome — E33 Second Home Visa corner

> The live shared context for ALL work on the E33 Second Home Visa vertical
> (Bali Zero). Load BEFORE touching any E33/second-home code, content, pricing,
> engine rule, or the letters pipeline — or when Zero says `/secondhome`,
> "second home", "E33", "visa rumah kedua".
> Born 2026-07-24 (Kimi session, Air-M5) after the vertical went live end-to-end.

---

## 0. What this vertical is

Bali Zero's Second Home Visa (Indonesian visa index **E33**) product line:
base E33 (deposit/property route, up to 5y), E33E (senior 55+, 5y),
E33F (senior 55+, 1y income-only). E33A/B/C (experts/world figures) deferred —
no sales intent. E33D is an official stub ("Data Belum Tersedia") — hidden.
E33G = remote worker, NOT second home (different product, don't conflate).

**Status: LIVE IN PRODUCTION (2026-07-24).** Engine, guard, prices, landing,
lifecycle all deployed. Tracker Day-90 armed but gated (see §5).

## 1. Where the truth lives (in order)

1. **`research/secondhome/e33-fact-registry.json`** — the SSOT: 33 facts with
   status (`confirmed|pending|disputed|unknown`) + confidence
   (`JELAS|BERSYARAT|BELUM_DIATUR_PUBLIK`) + source + date. Check it BEFORE
   writing any E33 content, code, price, or client answer. 7 confirmed /
   18 pending / 7 unknown / 1 disputed (age 55-59).
2. **`research/secondhome/e33-letter-response-tracker.md`** — the 6 official
   letters (001 Mandiri, 002 BRI, 003 BNI, 004 BTN, 005 BSI, 006 Ditjen
   Imigrasi, dated 2026-07-21) × question → fact-id → surface to patch when
   replies arrive. 16 pending facts.
3. **`research/secondhome/README.md`** — corner doc + ALL owner decisions.
4. **`research/secondhome/e33-dependent-pricing-draft.md`** — dependent
   pricing proposal (12M flat/person, DRAFT, not live).
5. Verified research base: `research/curated-qa-corrections-2026-07-21/`
   (visa-second-home-variants.jsonl 18 QA) +
   `research/visa/2026-07-21-e31j-e33f-kitap-verification.md` (Pasal 113 caps,
   age 55 via 11/2024, USD 3,000/month current).
6. MOS memory: `mem query "E33 Second Home"` (importance-9 session entry,
   2026-07-24).

## 2. Verified facts (hard truth — do not regress)

- **Base E33**: USD 130,000 deposit in OWN NAME at a state-owned (BUMN)
  Indonesian bank **OR** USD 1,000,000 qualifying property (completed
  strata-title only; villas/land/HGB/leasehold/off-plan do NOT qualify).
  No sponsor. First grant up to 5 years. Renewal per Permenkumham 22/2023
  **Pasal 113**: first grant ≥5y → 10y cumulative cap; <5y → 6y cap
  (`pasal_113_cumulative_caps`, JELAS).
- **E33E**: senior 55+ (USD 50,000 BUMN deposit + USD 3,000/month passive
  income, 5y). **Age ambiguity**: Permenkumham 11/2024 Pasal 33(2)(j)(4)
  says 55, Pasal 33(10)(d) still says 60 → operate on 55, handle 55–59 as
  BERSYARAT with signed client disclosure (owner decision).
- **E33F**: senior 55+, USD 3,000/month income only, NO deposit, 1y,
  6y cumulative cap. USD 1,500/month is the SUPERSEDED pre-2024 figure —
  eradicated everywhere; the claim guard watches for it.
- **PNBP** (internal reference only, pending letter 006 Q3): 5y tier =
  IDR 13,000,000; dependent E31 2y = Rp 5,5M, 5y ITAS = Rp 7,5M.
- **Dependents**: spouse E31B, children E31E, parents E31H, siblings E31J
  (pending written confirmation, letter 006 Q6).

## 3. Owner decisions (2026-07-23, binding)

- **Pricing**: base E33 = **IDR 35,000,000 ALL-INCLUSIVE** (repriced from 39M on
  2026-08-19, Zero ruling D2 — match Flado). NEVER decompose
  into PNBP + service fee in any client-facing material.
- **Fit Memo**: **FREE** (no paid fit assessment).
- **Dependent pricing**: flat add-on per person, draft **IDR 12M/person**
  (floor — margin 54% at PNBP 5,5M, 37% at 7,5M). No volume discount;
  first cohort = price discovery. NOT live yet.
- **StayGuard** (annual monitoring retainer): YES, but launches only after
  the Day-90 tracker is active in prod.
- **Split deposits**: NEVER offered, never planned. LPS exposure may be
  explained, nothing more.
- **BSI (sharia)**: decide only when letter 005 answers. Forbidden claim
  until then.
- **ITAP marketing**: only after written confirmation (letter 006 Q7), and
  only with its exact formulation. Never "automatic conversion".
- **Property-route module**: separate paid module, blocked on
  `property_validation_standard` (addendum 007 Q5).
- **Engine scope**: bank-route only (E33/E33E/E33F + dependents vocab).

## 4. What's live (merged 2026-07-23/24)

- **Engine** (Visa Oracle v2): 5 `secondhome.*` FactPaths (deposit USD,
  at-state-bank, own-name, property value, passive income; SENSITIVE per
  UU PDP), real products E33/E33E/E33F in the gold rule pack, 55–59
  human-review band rule WITH purpose guard (attached to E33E+E33F),
  23 gold personas. `RelationType.SIBLING` added for E31J.
- **Pricing**: `VisaType.E33` + dedicated rows: base 39M; E33E/E33F
  14M offshore / 16M onshore; E33F extend 10M. Bridge resolves all three.
- **Guard**: `e33_claim_guard.py` hooked in `orchestrator_core.py` step 12b
  (log + safe fallback note, non-blocking). 10 forbidden patterns:
  USD 1,500, any-bank, E33S/E33R, local work, ITAP-automatic, 5-10y,
  IDR 2M, approval-guaranteed, LPS-full-coverage, BSI, split-deposit.
- **Landing** `/visa/second-home`: Fit-Memo funnel, EN/ID/IT, CTA =
  WhatsAppLeadButton `cta_handoff` with product context (no new LeadSource
  enum — would 422). I18nProvider in route `layout.tsx`
  (lint_i18n_providers contract).
- **Lifecycle CRM**: 13-stage state machine (`e33_lifecycle.py`), Day-90
  scanner (`e33_guarantee_scanner.py` + cron endpoint
  `POST /api/cron/notifiers/e33-guarantee-scan`), alerts Day 30/60/75 via
  existing AlertsEngine, `stayguard_eligible` flag, no-custody SOP
  enforced (substring key validation + documented free-text boundary),
  migration **259** (`e33_cases`, has ROLLBACK, NOT applied).
- **Content**: canonical guide patched (any-bank claim fixed in 5 locales,
  1000× error IT/ID fixed), 16 contradictory articles noIndexed + filtered
  from listings, CTA sweep (56 files), wrong-code sweep (E28/C9A/E33A/
  E33H→E33), re-slugs `e33f-spouse`→`e31b`, `e33e-child`→`e31e` (+301s).
- **Waiver** (#3059): 3 unpatchable npm advisories waived in tests.yml
  (GHSA-frvp-7c67-39w9, GHSA-9mqv-5hh9-4cgg, GHSA-c96f-x56v-gq3h) —
  **REMOVE when upstream patches ship.**

## 5. Open phases (the roadmap to "done")

- **F4 — Activation (owner/operator, ~1h)**: set
  `e33_guarantee_scan_enabled=true` + Air cron wiring; apply migration 259
  on Pro; harvest QA corrections rounds 3–5 to prod Qdrant (commands in the
  registry branch report; wrong E33F/KITAP rows are LIVE until then);
  post-deploy QA of the landing; send addenda **007** (Imigrasi: age 55-59,
  two 90-day clocks, IDR equivalence, blocked deposit, property validation,
  E33F family/sponsor, basis switch, proof timing) and **008** (banks:
  remote opening/POA, joint accounts, blocked deposit, FX reference, roll-
  over/early withdrawal, tax withholding, CRS/FATCA, AML SoF) — both in
  `~/Downloads/`; fix README corrections date typo.
- **F5 — Letter-reply intake**: promote pending facts per the tracker;
  stricter path wins on conflict; resolve BSI/split/dependents/ITAP.
- **F6 — Commercial**: dependent go-live (12M confirm → PricingTool),
  StayGuard offer, property module, senior price review (E33E 5y = E33F 1y
  same price today — questionable), oracle interview tree "Retirement &
  second home" + E33F senior card, FR/RU landing translations.
- **F7 — Hygiene**: waiver removal, prettier debt on main (16 files),
  noIndex articles editorial rewrite-or-delete, `.husky/_` → .gitignore,
  llms files regeneration check.
- **F8 — Marketing (Legge 5, Zero only)**: canonical article update, WR2
  dispatch, newsletter. ITAP only with written confirmation.

## 6. Gotchas / scars from the birth session (read before touching)

- **`purposes=frozenset()` on `VisaType.E33`** is DELIBERATE: the match
  wizard must not surface E33 until the interview tree exists. Don't "fix".
- **`E33_ITAP_EVAL_ENABLED=False`** gates the ITAP stage in the lifecycle.
  Flip only after letter 006 Q7.
- **Docsync churn**: every new service file changes README/AI_ONBOARDING
  counters — run `python3 scripts/docs_sync.py` and commit BEFORE pushing,
  or check-docs-sync fails. Generated-number merge conflicts: take either
  side, re-run the generator.
- **`.husky/_` symlink**: exists untracked in worktrees; if swept into
  `git add -A` it breaks CI npm install everywhere. Never commit it.
- **Pre-push hook runs the FULL backend suite** on backend lanes (11–32 min).
  Budget for it. On Air-M5 the 51/118 asyncpg errors are environmental
  (no local Postgres) — verify on CI, not locally.
- **Trigger-miss**: `pull_request` workflows occasionally don't fire on
  push (observed twice on e33-source-guard). Cure: empty commit push;
  close/reopen didn't help. workflow_dispatch runs don't attach to PR
  required checks.
- **GitHub check lag**: after main moves, PR mergeable computation can be
  stale — re-check before assuming conflict.
- **No-custody boundary**: metadata KEYS are validated (substring);
  `document_ref`/`note`/values are deliberately free-text (CRM/UI layer's
  responsibility). Pinned by test — don't re-flag as a gap.
- **Senior renewal rule**: `e33_second_home_renewal` also matches E33E/F
  (would attach deposit docs to income-only tracks) — TODO in code; needs
  a senior-specific rule before those renewals are sold.
- **npm audit gate** now runs JSON mode with the waiver set; new
  high/critical advisories still fail as intended.

## 7. Loop protocol for future sessions

1. Read §1 SSOT files first. Never write E33 facts from memory.
2. Any new fact → registry entry with status/source/date, not prose.
3. Client-facing claims must map to a `confirmed` fact; pending/disputed →
   BERSYARAT wording or silence.
4. Multi-seat review for non-trivial work (fleet pattern: Gemini + GLM-5.2
   as graders; Fable 5 final gate when quota allows; Codex red-team for
   engine changes). Generator≠grader, always.
5. Worktree discipline (`scripts/agent_start.py`), never main checkout,
   never push to main, never deploy manually — PR + CI + merge triggers
   the pipelines.
6. Legge 5: nothing outward (no sends, no publishing) — Zero publishes.

---

_Corner created 2026-07-24 by Kimi (Air-M5) on Zero's order after the
12-PR birth of the vertical. Session archive: MOS memory importance-9
entry + `/tmp/secondhome_review/` (ephemeral)._
