---
date: 2026-08-09
domain: visa
client_case: none (Visa Oracle V2 decision-tree audit)
sources:
  - rulepack-prod-004.source.json (seq-4, active SHADOW since 2026-08-08)
  - real evaluator backend/services/visa_engine/evaluator.py (frozen REVIEW>SUPPORTED precedence)
  - gold personas fixtures/personas/*.json (23) + synthetic qualified applicants
  - offline harness (real evaluate() + real prod pack, synthetic facts, in-memory edits only)
---

# Visa Oracle V2 — full decision-tree audit ("albero perfetto")

Zero mandate 2026-08-09: audit EVERY always-review branch, classify each
SPURIOUS-MASK vs LEGITIMATE-REVIEW, + add the minor-without-guardian safety gate.
Method: faithful OFFLINE harness (real `evaluate()` + real prod-004 pack,
synthetic facts, in-memory pack edits only, zero prod/ledger pollution).

## Method — how a branch is judged

A PRODUCTS-scoped HUMAN_REVIEW rule is **purpose-only** when the only fact its
`when` references is `intent.purposes` — it fires for ANY applicant with that
purpose, masking regardless of qualifying facts (D12 class). It is
**discriminating** when it also references a real fact (D1 keys on
`intent.entry_pattern`; E31 on `family.relation_to_sponsor`; E33 on deposits).
Under the frozen REVIEW>SUPPORTED precedence any firing review masks all
SUPPORTED candidates, so a purpose-only rule that fires for a QUALIFIED applicant
(facts satisfy a dedicated product's eligibility) can spuriously mask that
product. Empirical test: remove the purpose-only rules for a purpose, re-evaluate
a qualified applicant; if a dedicated product surfaces SUPPORTED, the mask was
real. Static count: 25 purpose-only rules, 38 discriminating.

## Per-branch verdict

| Branch | purpose-only rules | Qualified-applicant counterfactual | Verdict |
|---|---|---|---|
| **INVESTMENT (D12)** | 5 | 09_investor (PT PMA committed, 3B capital): HUMAN_REVIEW → **SUPPORTED E28A** | 🔴 CLEAR CROSS-PRODUCT DEFECT — a real investor is routed to a business-visit review, hiding the investor KITAS (E28A). FIX. |
| **BUSINESS (D2)** | 5 | RE-VERIFIED 2026-08-09 (Zero pushback): business single OR multi-entry always → HUMAN_REVIEW with document reasons | ✅ NOT A DEFECT (retracted). Document review (CV/itinerary/funds/support-letter) is intended verification like EMPLOYMENT/RPTKA. The earlier "SUPPORTED D2" was a FLAWED single-entry test vs a multiple-entry product. No seq-5 change. |
| **STUDY (E30)** | 5 | E30/E30A/E30B/E30E/E30F all covered_purposes=[STUDY]; only study.admission_confirmed/level/sponsor_confirmed facts exist | 🟡 MISSING FACTS — E30E=KEK-institution, E30F=exchange-program, E30B=izin-belajar are distinct visas but NO interview fact distinguishes them, so all 3 fire as review for every student. Fix = interview/contract EXPANSION (add is_kek/is_exchange facts) → then route + conclude. A design project, not a rule edit. |
| **EMPLOYMENT (E23/U/V)** | 8 | reasons: RPTKA_VERIFICATION, JABATAN_MUST_MATCH_KBLI, PROHIBITED_HR_ROLES_KEPMENAKER_349_2019 | ✅ LEGITIMATE — government/RPTKA verification, not auto-determinable |
| **FAMILY (E31)** | 2 (E31D) | 06_family: remove → stays HUMAN_REVIEW (E31 sponsor-ITAS/ITAP discriminating rules dominate) | ✅ LEGITIMATE (E31D purpose-only rules redundant but harmless) |
| **SECOND_HOME (E33)** | 1 | 13/22/23: remove → stays HUMAN_REVIEW (deposit/property discriminating) | ✅ LEGITIMATE |
| **RETIREMENT (E33E/F)** | 0 | age-band discriminating (E33E 55-59, E33F <55) | ✅ LEGITIMATE |
| **REMOTE_WORK (E33G)** | 0 | income/local-market discriminating | ✅ LEGITIMATE |
| **TOURISM** | 0 | single-entry → SUPPORTED B1,C1; multi-entry → D1 review (D1 was cured with an entry_pattern gate) | ✅ CORRECT |
| **MEDICAL / OTHER** | — | no product covers them → NEEDS_INPUT | ⚪ COVERAGE GAP (business: does Bali Zero serve these lines?) |

## Safety defect (false-SUPPORTED — the dangerous class)

**minor-without-guardian**: prod-004 has NO GLOBAL age gate. Only `hr.e30a-minor-consent`
(PRODUCTS/E30A, gated on STUDY). A 15-year-old traveling alone for TOURISM
(sponsor_confirmed=False) → auto-SUPPORTED B1,C1. Proven fix: GLOBAL rule
`review.minor-without-guardian` (is_minor AND sponsor_confirmed==false →
REQUIRE_REVIEW/MINOR_WITHOUT_CONFIRMED_GUARDIAN). Verified: persona 15 → HUMAN_REVIEW,
adult persona 01 → still SUPPORTED (innocence). Shipped in the prod-005 draft.

## Root cause of the spurious masks (superscar W107, incomplete-cure)

D1's review rules double-gate `all(purpose, entry_pattern==MULTIPLE)` — prod-004
cured D1. D2 and D12 fire on purpose alone; the same cure was NOT applied to them
(cured one of three). E30's rules are purpose-only too, but 3 encode
product-applicability (E30E only for KEK institutions, E30F only for exchange
programs) disguised as review — deleting them wholesale would OVER-support a
generic student. Their correct fix is conversion to ELIGIBILITY conditions.

## seq-5 (prod-005) fix set

FINAL seq-5 = TWO fixes only (both DRAFTED + harness-verified in prod-005, guilt/innocence PASS):
1. **Minor gate** (safety): GLOBAL `review.minor-without-guardian` — persona 15 flips
   SUPPORTED→HUMAN_REVIEW/minor, adult unchanged.
2. **D12→E28A unmask** (cross-product defect): the 5 D12 investment purpose-only rules
   gated `all(purposes intersects [INVESTMENT], investment.pt_pma_committed neq true)`
   (Codex-vetted, single-seat: agy/kimi were quota/auth down). 09_investor →
   SUPPORTED E28A; pt_pma FALSE → D12 review; UNKNOWN → NEEDS_INPUT. No precedence change.

NOT fixed (resolved as non-defects / separate projects):
3. **D2** — NOT a defect (retracted after Zero pushback + re-verification). Business
   always-review is intended document verification.
4. **E30** — needs interview/contract EXPANSION (missing is_kek/is_exchange/izin facts);
   a design project, not a seq-5 rule edit.
5. **LEAVE**: EMPLOYMENT, FAMILY, SECOND_HOME, RETIREMENT, REMOTE_WORK (legitimate).
6. **Coverage gap (Legge-5)**: MEDICAL / OTHER have no product.

Activation of any seq-5 pack is Zero-gated (two-login signing ceremony); ENFORCE
stays NO-GO. The "38 schede testate in prod" is the Bali Zero team's heavy manual
SHADOW testing (Zero mandate 2026-08-08), enabled by the offline harness above.

## seq-5 activation runbook (Zero-gated ceremony)

State verified live 2026-08-09: frontend `balizero.com/visa-oracle` HTTP 200,
backend `nuzantara-rag.fly.dev/health` HTTP 200. Active pack = prod-004 (seq-4,
`rule_pack_id 720f50fc-12e2-5633-8586-4b31b086ea64`). SHADOW testing of the
current tree is possible NOW, with the 2 known holes above still open until seq-5.

**Mechanical (session already did): DONE** — prod-005.source.json drafted +
harness-verified (`rulepack-prod-005.source.json`, seq=5, 113 rules; compiles clean;
exactly 2 personas flip 09_investor→SUPPORTED E28A / 15_minor→HUMAN_REVIEW,
guilt/innocence PASS). Reproducible via `build_seq5_full.py`.

**Two ceremony-blocking chain bugs caught + fixed (2026-08-09, pre-signature):** the
initial draft `deepcopy`-ed prod-004 and carried two fields that would have failed the
ceremony — (1) `rule_pack_id` was prod-004's `720f50fc…` → PK collision on
`insert_rule_pack`; (2) `previous_payload_sha256` was prod-003's `99b843b8…` →
`bundle.validate_activation` (bundle.py:987) hard-rejects unless it equals the ACTIVE
pack's hash. Fixed: minted a new uuid5 `rule_pack_id = 4159265d-53e8-5b25-ab5a-fa4f5b25a2d1`
(design-doc convention: uuid5 never uuid4; unique vs 001/002/004) and chained
`previous_payload_sha256 = 1f0f7b0d189d0d9adecb08afa158f1f221ef698340a65b029beb0fc21f410e49`
(prod-004, read dynamically from its signed bundle — no frozen constant). All four
activation preconditions re-verified GREEN (unique id · seq 5>4 · prev==prod-004 · PRODUCTION).

**⚠️ KID CORRECTION (2026-08-09 — the real signing key id, proven against live prod-004):**
The production signing kid is **`prod-2026-07-1`** (letter-first) — NOT `2026-07-prod-1`.
The earlier `2026-07-prod-1` was a transcription/transposition that propagated from an
ILLUSTRATIVE docstring example (`bundle.py:253`, inside `StaticTrustStore.from_env`'s
`.. code-block:: json`) and the M5 key FILENAME (`2026-07-prod-1.ed25519.pem`) — the file
name uses a date-first convention that does NOT equal the kid it holds. Proven the hard way:
signing with `--kid 2026-07-prod-1` is REJECTED (digit-first fails the `Identifier` pattern
`^[A-Za-z]…`), and `RulePack.model_validate(prod-004.signed.json)` shows the LIVE bundle's
`protected.kid == 'prod-2026-07-1'`. A GATE probe verified prod-004's Ed25519 signature with
a trust store built from that key's derived pubkey (`gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA`)
under kid `prod-2026-07-1` → PASS, so this exact key+kid is prod-004's live signer. There is
NO kid Identifier regression on main — the pattern accepts `prod-2026-07-1` fine.

**Session-executed (DONE 2026-08-09 — "io sono te", sign_pack reads --key-file, never prints):**
1. **Signed on M5** (`ssh air`, user `balizero`) — Ed25519 PRIVATE key at
   `~/.config/nuzantara/visa-signing/2026-07-prod-1.ed25519.pem` (chmod 0600, never
   Pro/Mini/Keychain/repo, cicatrix #4). `python -m backend.scripts.visa_engine.sign_pack
   rulepack-prod-005.source.json --kid prod-2026-07-1 --key-file <pem> --environment
   PRODUCTION --sequence 5 --output rulepack-prod-005.signed.json --i-know-this-is-production`.
   Result: `sequence=5 kid=prod-2026-07-1 payload_sha256=ebc19f5c0550b601350f4e8e9ab95a61cc8107ea15c2ecd03781d023aaad322e
   public_key=gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA` (IDENTICAL pubkey to prod-004's
   signer). sign_pack self-verified before writing.
2. **Faithful dry-run of activate_pack** (no `--yes`, returns before any DB): with a
   `VISA_ENGINE_TRUST_STORE_KEYS_JSON` built from the derived pubkey, the REAL path ran
   `StaticTrustStore.from_env` → `verify_rule_pack` (PASS) → `validate_activation`
   (anti-rollback pre-gate PASS: seq 5>4 · chain `1f0f7b0d…` · PRODUCTION · engine 1.0.0)
   → `would_insert_and_activate=true rule_pack_id=4159265d-… payload_sha256=ebc19f5c…`.

**Operator-checkpoint (Zero — Legge 5) → GRANTED + EXECUTED 2026-08-09:**
Zero authorized activation this session ("Sì, attiva seq-5 (SHADOW)" via checkpoint).
3. **Two-login `--yes` activate — DONE.** Ran on Pro (`fly proxy 15432:5432` →
   `nuzantara-postgres` haproxy). TWO ephemeral LOGIN roles minted via stdin→psql
   (pw never in argv, cicatrix #4): `visa_pack_writer_ceremony_260809` (in `visa_pack_writer`)
   + `visa_activation_ceremony_260809` (in `visa_activation_executor`, invariant
   `no-pack-writer-activation-combination`), passed to `activate_pack.py --yes` as the two
   DSN env vars; `_assert_production_separation` passed (distinct non-superuser principals);
   roles DROPPED same session via EXIT trap. **Result:** `rule_pack_id=4159265d-… ·
   activation_id=560839f3-a71d-42ef-bdec-246579630884 · sequence=5 · payload_sha256=ebc19f5c…`.
4. **Prove-live — CONFIRMED at DB + runtime-code level.** The runtime's active-pack
   selection (`repository.load_active_rule_pack` AND its twin `shadow._resolve_active_pack_binding`)
   is `WHERE legal_period @> now() AND system_period @> now() ORDER BY created_at DESC LIMIT 1` —
   NOT single-active: multiple PRODUCTION activations are open by design (seq 1/3/4/5 all
   in_force; the docstring acknowledges overlapping `legal_period`s), and the NEWEST
   `created_at` wins. seq-5's activation (`created_at 2026-08-09 13:27:38Z`) is the newest →
   **served.** No import-time cache, no TTL wrapper on the binding (`shadow.py:77` "re-read
   fresh on every call") → live immediately, no restart. EVALUATE_MODE stays SHADOW
   (engine result shadow-logged, users still see CURATED) — ENFORCE remains NO-GO. Frontend
   `balizero.com/visa-oracle` 200, backend `/health` healthy (v100-qdrant, postgres connected).
   The Bali Zero team now runs the 38-scheda manual SHADOW test against the corrected tree.

**NOT a blocker for this SHADOW activation** (corrected 2026-08-09 — earlier draft
over-flagged it): the enforce-gate doc's DB findings (migration 264 unapplied,
`visa_activation_executor` holds direct grants, `backend_rag_v2` can insert activation
rows, no `visa_ledger_owner`) are explicitly **"latent while mode is SHADOW"** and are
**hard ENFORCE blockers only**. prod-004 (seq-4) was activated in SHADOW with these
exact conditions present, so seq-5 activates the same way. ENFORCE stays NO-GO, so they
do not gate anything on the current path. They remain a separate operator[credential]
DB-hardening prerequisite for any future ENFORCE decision (Zero + privacy owner + DPIA).
