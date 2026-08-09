---
date: 2026-08-09
domain: visa
adversarial_review: codex
adversarial_review_note: "gpt-5.6-sol, R1 round 2026-08-09 — 20 objections, verdict BLOCKER; the retractions and corrections in this document are its result"
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

## Adversarial review

Seat: **codex** (`gpt-5.6-sol`, medium effort), 2026-08-09, prompted to REFUTE this
document. 20 objections, verdict **BLOCKER**. Author did not grade the author's own work;
and per W65 ("even the refuter hallucinates") every objection acted on below was
independently re-measured before being accepted.

**Survived and acted on** (each is now a retraction/correction in the text above):

1. *"multiple activations open by design, newest `created_at` wins" contradicts the schema.*
   **CONFIRMED, and the mechanism was mine**: the probe filtered `legal_period` alone,
   omitting the runtime's `system_period` clause. Re-measured — exactly ONE active row
   (seq-5); seq 1/3/4 carry a CLOSED `system_period`. Retracted in full.
2. *The minor "safety defect" audits the evaluator, not the served runtime.* **CONFIRMED**:
   `_apply_minor_privacy_hold` (`evaluate_path.py:902`, invoked `:1459`) already abstains for
   known minors. Retracted.
3. *The rule keys on `family.sponsor_confirmed`, which is not a guardian fact.* **CONFIRMED**
   from the adapter's own docstring ("no guardian-identity/consent fact"). Naming defect
   recorded; a real fix needs a contract expansion.
4. *"no `visa_ledger_owner`" is stale.* **CONFIRMED** — all six capability roles measured
   present 2026-08-09. The enforce-gate runbook is itself stale on this point.
5. *"seq-5 is served" is not a prove-live test.* **ACCEPTED** — scope narrowed to a DB fact
   plus the selection query's source; a runtime receipt naming sequence 5 is still owed.
6. *`shadow.py:77` miscited for the no-cache claim.* **ACCEPTED** — that line is about
   `MATCH_MODE`; the citation was dropped and the claim restated from the resolver itself.
7. *`build_seq5_full.py` is not in the repo.* **ACCEPTED** — it is a session scratchpad;
   the reproducible artifacts are the checked-in source pack + `compile_pack.py`.
8. *The kid's causal history is unsupported.* **ACCEPTED** — the syntax facts and the live
   value are proven; the "copied from the docstring" story is not, and was withdrawn.

**Raised, not resolved here — recorded as open limitations** (they narrow this document's
claims rather than change a shipped artifact):

- The FAMILY / SECOND_HOME "legitimate" verdicts rest on 1–3 personas each, not on
  exhaustive coverage; "redundant but harmless" is therefore unproven for unexplored fact
  patterns. The per-branch table should be read as evidence-so-far, not a truth table.
- "BUSINESS is not a defect" is an **owner-accepted** position (Zero, after pushback) plus
  observed reason codes — not a cited design artifact or regulation.
- The "38 schede testate in prod" line describes work the team is *starting*, not a completed
  validation; no result table, timestamps or case manifest exists yet. The number equals the
  pack's product count and should not be read as a test-pass count.

## Minor handling (RETRACTED as a "safety defect" — corrected 2026-08-09)

> **RETRACTION.** An earlier revision of this section called this a false-SUPPORTED
> **safety defect**: "a 15-year-old travelling alone for TOURISM → auto-SUPPORTED B1,C1",
> with the seq-5 rule as its "proven fix". That was measured on the **raw `evaluate()`**
> in the offline harness — the evaluator layer — and does **not** describe the served
> runtime. The public evaluation path calls `_apply_minor_privacy_hold`
> (`evaluate_path.py:902`, invoked at `:1459`), which abstains for every KNOWN minor
> before a response is built. **No real applicant was ever auto-SUPPORTED as a minor by
> the live surface.** Auditing a layer and reporting it as the product's behaviour is the
> error; the claim is withdrawn.

What the pack-level rule in seq-5 (`review.minor-without-guardian`) actually is:
**defence in depth at the RulePack layer** for a case the runtime adapter already covers.
It is not harmful and it keeps the pack self-sufficient if the adapter is ever bypassed,
but it closed no live hole.

**Naming is also wrong and should be corrected in a later pack.** The rule keys on
`family.sponsor_confirmed`, which is a *sponsor* fact (family/work sponsorship), **not**
guardian identity or consent. `_apply_minor_privacy_hold`'s own docstring states the
contract "has no guardian-identity/consent fact" — so a rule called
`minor-without-guardian` emitting `MINOR_WITHOUT_CONFIRMED_GUARDIAN` asserts a fact the
vocabulary cannot express. Fixing it properly needs an interview/contract expansion (a
real guardian fact), not a rename.

Harness evidence, stated for what it is: on the evaluator layer, persona 15 flips
SUPPORTED → HUMAN_REVIEW and adult persona 01 is unchanged (innocence). That is a true
statement about `evaluate()`, and only about `evaluate()`.

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
guilt/innocence PASS — on the EVALUATOR layer; see the minor-handling retraction above for
what that does and does not say about the served runtime). Built by a session scratchpad
script (`build_seq5_full.py`), which is **not committed to this repo** — the reproducible
artifact is the checked-in `rulepack-prod-005.source.json` plus `compile_pack.py`.

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
Two date-first strings exist nearby and are easy to mistake for the kid: the ILLUSTRATIVE
docstring example at `bundle.py:253` (inside `StaticTrustStore.from_env`'s
`.. code-block:: json`, which still shows the invalid `2026-07-prod-1`) and the M5 key
FILENAME `2026-07-prod-1.ed25519.pem` — a filename convention that does NOT equal the kid
the file holds. *How* the wrong value entered this runbook is not established here (the
visaoracle skill records earlier ceremony ids that began with a digit, failed the pattern,
and were relabelled — a different history than "copied from the docstring"); what IS
established is the syntax and the live value. Proven the hard way:
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
4. **Post-activation verification — seq-5 is the single active pack.** The runtime's
   active-pack selection (`repository.load_active_rule_pack` and its documented twin
   `shadow._resolve_active_pack_binding`) filters on **BOTH** bitemporal clocks:
   `WHERE legal_period @> $effective_at AND system_period @> $observed_at ORDER BY created_at
   DESC LIMIT 1`. Measured against prod with that exact predicate: **exactly one row —
   seq-5** (`4159265d-…`). Per-row: seq 1/3/4 have `legal_period @> now()` **but their
   `system_period` is CLOSED**; only seq-5 has both open.

   > **CORRECTION (same day, caught by the R1 adversarial review).** An earlier revision of
   > this section claimed "multiple PRODUCTION activations are open by design … the newest
   > `created_at` wins". That was **wrong**, and it was wrong because the probe behind it
   > queried `legal_period` ALONE — omitting the `system_period` filter the runtime actually
   > applies — and then an explanation was invented to fit the flawed measurement. The schema
   > forbids what that sentence asserted: `250_visa_engine_core.sql` carries a GiST exclusion
   > constraint over both periods, and the activation writer
   > (`253_visa_activation_writer_hardening.sql`) closes covered open activations before
   > inserting. `ORDER BY created_at DESC LIMIT 1` is **defensive**, not a selection policy —
   > treating it as "newest wins" would invite tolerating a ledger-integrity violation.
   > The prior `CURRENT_STATE.md` wording ("seq-4 was the single open activation") was
   > therefore CORRECT and is reinstated; this document's earlier "imprecise" label on it is
   > withdrawn.

   **Scope of what this proves:** a DB fact (which activation is bitemporally current) plus
   the source of the selection query. It is **not** a runtime receipt: no evaluation response
   or audit row has yet been observed naming `sequence 5` / activation `560839f3-…`. That
   end-to-end proof is the remaining prove-live step. The binding is read per request (the
   resolver queries the DB on every call and holds no module-level cache), so no restart is
   expected to be needed. EVALUATE_MODE stays SHADOW (engine result shadow-logged, users still
   see CURATED) — ENFORCE remains NO-GO. Frontend `balizero.com/visa-oracle` 200, backend
   `/health` healthy (v100-qdrant, postgres connected).

**DB hardening status — re-measured, an earlier claim here was stale.** A prior revision
repeated `docs/runbooks/visa-oracle-privacy-enforce-gate.md`'s 2026-08-06 snapshot
("no `visa_ledger_owner`", migration 264 unapplied). **Measured live on 2026-08-09 (read-only,
`pg_roles`): all six capability roles EXIST** as NOLOGIN — `visa_pack_writer`,
`visa_activation_executor`, `visa_ledger_owner`, `visa_policy_writer`,
`visa_retention_executor`, `visa_privacy_operator`. The DB was hardened AFTER that snapshot,
so the enforce-gate doc is itself stale on this point; repeating it here without re-measuring
was the mistake.

What is NOT claimed: that the remaining privilege-separation items are irrelevant. They did
not prevent this activation — the ceremony ran under two distinct, non-superuser ephemeral
principals and `_assert_production_separation` passed — but "did not block this ceremony" is
not "not a prerequisite". Activation-ledger integrity and privilege separation remain live
prerequisites for any ENFORCE decision (Zero + privacy owner + DPIA), which stays NO-GO.
