---
name: secondhome
description: "E33 Second Home Visa corner — the live shared context for ALL work on the E33 vertical (base E33 deposit/property route, E33E/E33F senior). Load BEFORE touching any E33 code, content, pricing, engine rule, or the letters pipeline — or when Zero says /secondhome, 'second home', 'E33', 'visa rumah kedua'. Holds: where the truth lives (fact registry + letter tracker), verified facts, owner decisions, what is LIVE vs merely BUILT, the open phases F4-F8, and the blood-bought gotchas."
---

# /secondhome — E33 Second Home Visa corner

> The live shared context for ALL work on the E33 Second Home Visa vertical
> (Bali Zero). Load BEFORE touching any E33/second-home code, content, pricing,
> engine rule, or the letters pipeline — or when Zero says `/secondhome`,
> "second home", "E33", "visa rumah kedua".
> Born 2026-07-24 (Kimi session, Air-M5) after the vertical went live end-to-end.
> Armed 2026-07-25 (architect pass): frontmatter + tracked path + §4bis LIVE STATE.

---

## 0. What this vertical is

Bali Zero's Second Home Visa (Indonesian visa index **E33**) product line:
base E33 (deposit/property route, up to 5y), E33E (senior 55+, 5y),
E33F (senior 55+, 1y income-only). E33A/B/C (experts/world figures) deferred —
no sales intent. E33D is an official stub ("Data Belum Tersedia") — hidden.
E33G = remote worker, NOT second home (different product, don't conflate).

**Status: LIVE IN PRODUCTION (2026-07-24).** Engine, guard, prices, landing,
lifecycle all deployed. **Read §4bis before believing any "it's armed" claim** —
two organs are built-but-not-armed, and the engine answers nothing yet.

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
   (`visa-second-home-variants.jsonl`) +
   `research/visa/2026-07-21-e31j-e33f-kitap-verification.md` (Pasal 113 caps,
   age 55 via 11/2024, USD 3,000/month current).
6. Non-repo workspace (PDFs, 6 letters, role-play, competitor scan):
   **`~/Desktop/marketing/E33-SecondHome/`** — NOT `~/Desktop/E33-SecondHome/`,
   the dead path still cited by the stale corner copies (see §6).
7. MOS memory: `mem query "E33 Second Home"`.

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

- **Pricing**: base E33 = **IDR 39,000,000 ALL-INCLUSIVE**. NEVER decompose
  into PNBP + service fee in any client-facing material.
- **Fit Memo**: **FREE** (no paid fit assessment).
- **Dependent pricing**: flat add-on per person, draft **IDR 12M/person**.
  No volume discount; first cohort = price discovery. NOT live yet.
- **StayGuard** (annual monitoring retainer): YES, but launches only after
  the Day-90 tracker is active in prod → **blocked by §4bis**.
- **Split deposits**: NEVER offered, never planned. LPS exposure may be
  explained, nothing more.
- **BSI (sharia)**: decide only when letter 005 answers. Forbidden claim
  until then.
- **ITAP marketing**: only after written confirmation (letter 006 Q7), and
  only with its exact formulation. Never "automatic conversion".
- **Property-route module**: separate paid module, blocked on
  `property_validation_standard` (addendum 007 Q5).
- **Engine scope**: bank-route only (E33/E33E/E33F + dependents vocab).

## 4. What's built (merged 2026-07-23/25)

- **Engine** (Visa Oracle v2): 5 `secondhome.*` FactPaths (deposit USD,
  at-state-bank, own-name, property value, passive income; SENSITIVE per
  UU PDP), products E33/E33E/E33F, the 55–59 human-review band rule with
  purpose guard, 23 gold personas. `RelationType.SIBLING` added for E31J.
  First signed PRODUCTION RulePack (#3090): 38 products, 110 rules,
  28 sources, seq 1, version `2026.7.25`, payload sha `47a97c32…`.
- **Pricing**: `VisaType.E33` + dedicated rows: base 39M; E33E/E33F
  14M offshore / 16M onshore; E33F extend 10M. Bridge resolves all three.
- **Guard**: `e33_claim_guard.py` hooked in `orchestrator_core.py` step 12b
  (log + safe fallback note, non-blocking). 10 forbidden patterns:
  USD 1,500, any-bank, E33S/E33R, local work, ITAP-automatic, 5-10y,
  IDR 2M, approval-guaranteed, LPS-full-coverage, BSI, split-deposit.
- **Landing** `/visa/second-home`: Fit-Memo funnel, EN/ID/IT, CTA =
  WhatsAppLeadButton `cta_handoff` with product context.
- **Lifecycle CRM**: 13-stage state machine (`e33_lifecycle.py`), Day-90
  scanner (`e33_guarantee_scanner.py` + cron endpoint
  `POST /api/cron/notifiers/e33-guarantee-scan`), alerts Day 30/60/75 via
  the existing AlertsEngine, `stayguard_eligible` flag, no-custody SOP
  enforced, migration **259** (`e33_cases`).
- **Content**: canonical guide patched, 16 contradictory articles noIndexed,
  CTA sweep, wrong-code sweep, re-slugs `e33f-spouse`→`e31b`,
  `e33e-child`→`e31e` (+301s).

## 4bis. LIVE STATE — built ≠ armed (probed on prod 2026-07-25)

Method for every row: a live prod probe or a `postgres-nuzantara` query in the
same turn — never a report. Re-verify before trusting; update when you change it.

| Organ              | Verified state                                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pricing            | ✅ **LIVE** — `search_service_pricing` prod returns E33 = 39.000.000 IDR all-inclusive, + E33E 14/16M, E33F 14/16M, E33F extend 10M               |
| Landing            | ✅ **LIVE** — `balizero.com/visa/second-home`: correct figures, free-Fit-Memo CTA → `wa.me/6282230102328`, zero red-line claims                   |
| Migration 259      | ✅ **APPLIED in prod** — `e33_cases` exists. (The pre-2026-07-25 corner claimed "NOT applied" — that was **wrong**.)                              |
| RulePack prod-001  | ✅ **INSERTED + ACTIVATED** — `visa_ruleset_activations` since 2026-07-25 04:17, `operator.zero-2026-07`                                          |
| Day-90 kill switch | ❌ **DEAD** — `system_settings.e33_guarantee_scan_enabled` **row does not exist** → fails closed, every call skips                                |
| Day-90 cron        | ❌ **DEAD** — no `.github/workflows/cron-notifiers-e33-guarantee-scan.yml`; its 5 sibling notifiers all have one. Nothing ever calls the endpoint |
| Engine output      | ⚠️ **ANSWERS NOTHING** — see below                                                                                                                |

### The review-saturation finding (2026-07-25)

Seven payloads through the live `POST /api/visa-oracle/evaluate` (all-UNKNOWN,
fully-populated, qualified / underfunded / senior / 30-day tourist control) all
return `state=HUMAN_REVIEW_REQUIRED` with **`candidates: []`**. The qualified
client and the unqualified one are indistinguishable in the response.

Cause, grounded in the code and the pack source:

- `evaluator.py:44` — `HUMAN_REVIEW_REQUIRED` outranks `SUPPORTED_CANDIDATES`
  **unconditionally**; one TRUE HUMAN_REVIEW rule returns immediately, candidates empty.
- The prod pack is **65 HUMAN_REVIEW / 28 ELIGIBILITY / 17 HARD_FILTER** of 110 —
  document requirements (CV, itinerary, passport validity, support letter, proof
  of funds) are modelled as route-to-human triggers, so even a clean 30-day
  tourist trips five of them across three products.
- **E33's own trigger is inverted**: `review.e33.guarantee-maintenance` fires
  `when purposes ∋ SECOND_HOME AND (deposit ≥ 130000 OR property ≥ 1000000)` —
  exactly the qualification condition. `GUARANTEE_VALUE_MUST_BE_MAINTAINED` is a
  client _disclosure_ wired as a _refusal to decide_.

**Not client-facing yet**: `evaluate_path.resolve_response_mode()` hard-returns
`"CURATED"`; the ENGINE flip is a separate unimplemented gate. This is a loaded
gun, not an open wound — but **the ENFORCE gate must not be opened until the
pack's review stage is re-authored**, or every applicant gets "a human must look
at this" and zero product names.

**Why it was invisible**: the #3090 gate verified compile + signature +
per-product coherence — the pack's _form_. `scripts/visa_gold_replay.py` replays
the 20 canonical personas against `build_gold_compiled_pack()`
(`gold_replay.py:170`), the synthetic TEST fixture. **No organ replays personas
against the pack that is active in production.**

Correcting the rule touches a **signed legal artifact** → re-sign + re-activation
ceremony + adversarial review. Propose it; never hand-edit a signed pack.

## 5. Open phases (the roadmap to "done")

- **F4 — Activation**: seed `e33_guarantee_scan_enabled` + add the cron workflow
  (both session-ownable); harvest QA corrections rounds 3–5 to prod Qdrant
  (review-gated — wrong E33F/KITAP rows are LIVE until then); send addenda **007**
  (Imigrasi) and **008** (banks), both in `~/Downloads/` — operator[physical]:
  sign + stamp + dispatch.
- **F5 — Letter-reply intake**: promote pending facts per the tracker;
  stricter path wins on conflict; resolve BSI/split/dependents/ITAP.
- **F6 — Commercial**: dependent go-live (12M confirm → PricingTool),
  StayGuard offer, property module, senior price review (E33E 5y = E33F 1y
  same price today — questionable), oracle interview tree "Retirement &
  second home" + E33F senior card, FR/RU landing translations.
- **F7 — Hygiene**: npm waiver removal, noIndex articles editorial
  rewrite-or-delete, `.husky/_` → .gitignore, llms files regeneration check.
- **F8 — Marketing (Legge 5, Zero only)**: canonical article update, WR2
  dispatch, newsletter. ITAP only with written confirmation.

## 6. Gotchas / scars (read before touching)

- **`purposes=frozenset()` on `VisaType.E33`** (`catalogue.py:304-312`) is
  DELIBERATE: `match_tree.Purpose` has no `SECOND_HOME` member, so the match
  wizard can never surface E33. Note that the engine's own `enums.VisaPurpose`
  **does** have `SECOND_HOME` — two vocabularies. Don't "fix" one side alone.
- **Senior renewal rule**: `renewal_rules.py:276-300` — `e33_second_home_renewal`
  matches pattern `"e33"`, so E33E/E33F (income-only, NO deposit) inherit
  `guarantee_proof_bank_confirmation_or_property_title`, and it sits at priority
  5 in `RULE_PRIORITY_ORDER`, ahead of `kitas_retirement_extend` (which matches
  `"retirement"` only). A senior is asked for a bank letter that does not exist.
  Fix before E33E/F renewals are sold.
- **`E33_ITAP_EVAL_ENABLED=False`** gates the ITAP stage. Flip only after letter 006 Q7.
- **Corner drift** — this file is the ONLY corner. Two stale copies disagree with
  prod and must not be trusted: `~/.claude/commands/secondhome.md` (14 Jul, points
  at the dead `~/Desktop/E33-SecondHome/` path) and the
  `memory/secondhome-profile.md` charter + activity log (stops 22 Jul, blind to
  the whole vertical build). Treat both as archaeology.
- **Docsync churn**: every new service file changes README/AI_ONBOARDING counters —
  run `python3 scripts/docs_sync.py` and fold the regen into the SAME commit (W86).
- **`.husky/_` symlink**: exists untracked in worktrees; never `git add -A` it.
- **Pre-push hook runs the FULL backend suite** on backend lanes (11–32 min). On
  Air-M5 the asyncpg errors are environmental (no local PG) — verify on CI.
- **No-custody boundary**: metadata KEYS are validated (substring); `document_ref`/
  `note`/values are deliberately free-text. Pinned by test — don't re-flag as a gap.

## 7. Loop protocol for future sessions

1. Read §1 SSOT files first. Never write E33 facts from memory.
2. Any new fact → registry entry with status/source/date, not prose.
3. Client-facing claims must map to a `confirmed` fact; pending/disputed →
   BERSYARAT wording or silence.
4. **Probe the work, not the proxy**: "pack active", "endpoint 200", "cron green"
   are proxies. Prove by the downstream state-delta — a real evaluation's
   candidates, a real alert row, a real served answer.
5. Multi-seat review for non-trivial work. Generator≠grader, always.
6. Worktree discipline (`scripts/agent_start.py`), never the main checkout.
7. Legge 5: nothing outward (no sends, no publishing) — Zero publishes.
