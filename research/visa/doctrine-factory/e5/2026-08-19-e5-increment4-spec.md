---
date: 2026-08-19
domain: visa
client_case: none — engine doctrine work (Visa Oracle E5 increment 4 / RulePack seq-10)
sources:
  - rulepack-prod-009.source.json + rulepack-prod-009.signed.json (seq-9, on main via #4332/#4338)
  - research/visa/doctrine-factory/sources/freshness-recheck-2026-08-16.md (QW-5 method)
  - research/visa/doctrine-factory/e5/inc4-pack-edits/freshness-restamp-2026-08-19.md (live re-verification, this increment)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C (live fetch 2026-08-19T04:22:00Z)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C2 (live fetch 2026-08-19T04:21:51Z)
adversarial_review: codex
---

# E5 increment 4 — RulePack seq-10 spec (re-stamp fonti + cura el.c2/el.e31c)

Mandate (Zero, 2026-08-19): "procedi con seq-10: re-stamp fonti + cura el.c2/el.e31c".
Scope is exactly the two CP3-declared residuals plus the 18-source staleness finding from
the seq-9 arc. Nothing else in the pack changes; ENFORCE is untouched (SHADOW stays).

## 1. Identity

| Field | Value | How derived |
|---|---|---|
| `sequence` | 10 | next after seq-9 |
| `version` | `"2026.8.19"` | same-day precedent (seq-2/seq-3 shared `2026.8.8`); `sequence` is the identity field |
| `rule_pack_id` | `d390c8eb-926d-5c37-9bbb-83e4a8601195` | `uuid5(NAMESPACE_URL, ".../rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/10")` — anchor gate in the fold script |
| `previous_payload_sha256` | read LIVE from `rulepack-prod-009.signed.json`'s `payload_sha256` at fold time (expected `47feff8246c608c7c6085ffdac776fdc020bb56688d5f35a0a3e685eb40f271e`) | never hardcoded-only: the script reads the signed file and asserts the expectation |
| base pack | `rulepack-prod-009.source.json` | byte-inherited except the edits below |

## 2. Phase A — source re-stamp (17 bumps, 1 drop)

Method: QW-5 (live `WebFetch`, content compared against the exact fact each `source_ref`
backs — never HTTP reachability alone). Executed 2026-08-19 ~04:20–04:22 UTC by three
independent readers; full evidence with verbatim quotes in
`inc4-pack-edits/freshness-restamp-2026-08-19.md`.

**Re-stamp (`verified_at` + `verified_by` bump, everything else byte-identical):**

| record | page | verdict | new `verified_at` |
|---|---|---|---|
| bc309fa9 | Calling Visa list | CURRENT (exactly the 6 states; no CM/GN) | 2026-08-19T04:20:35Z |
| 38a6cb08 | VOA list | CURRENT (97 entries; IT in, NG out) | 2026-08-19T04:20:35Z |
| 3da72c7b | bridging-permit press | CURRENT (60d + 3d window verbatim) | 2026-08-19T04:20:35Z |
| dcf08e19 | ITK→ITAS service page | CURRENT (procedure + 30d window) | 2026-08-19T04:20:35Z |
| 950a9f63 | E31A | CURRENT (USD 2000 verbatim) | 2026-08-19T04:20:00Z |
| 570f2bc4 | E31B | CURRENT (title-embedded ITAS/ITAP, same caveat as QW-5) | 2026-08-19T04:21:00Z |
| 40523028 | E31C | CURRENT (marriage-proof clause verbatim; full Persyaratan transcribed) | 2026-08-19T04:22:00Z |
| 50457cd0 | E31D | CURRENT | 2026-08-19T04:20:00Z |
| f9306203 | E31F | CURRENT (putusan pengadilan verbatim) | 2026-08-19T04:20:00Z |
| 86880290 | E31G | CURRENT (4 facts verbatim) | 2026-08-19T04:20:00Z |
| 153beca1 | E31H | CURRENT (child ITAS/ITAP bullet verbatim) | 2026-08-19T04:21:00Z |
| ca5a2ce8 | D1 | CURRENT (6 facts verbatim) | 2026-08-19T04:21:51Z |
| d3ad622e | D2 | CURRENT (6 facts) | 2026-08-19T04:21:51Z |
| 5e64ec6b | D12 | CURRENT (USD 5000 + non-convertibility verbatim) | 2026-08-19T04:21:51Z |
| 38242587 | E30A | CURRENT **with exception** (passport+funds verbatim; the `review.minor-without-guardian` citation remains unsupported — page has zero minor/wali language; residual, see §5) | 2026-08-19T04:21:51Z |
| cb1b7182 | E30B | CURRENT (acceptance letter verbatim) | 2026-08-19T04:21:51Z |
| ecd22722 | E31E | already re-stamped in seq-9 (2026-08-18T21:41:23Z) — NOT touched | — |

`verified_by` = `agent.air-m5.backend-rag.visa-e5-seq10-reader-<1|2|3>.qw5-recheck-2026-08-19`
(reader 1 = lists/procedural, 2 = E31 family, 3 = D-series/E30/C2-probe).

**Drop: `ee8fe5b8` (izin-tinggal-keimigrasian landing page).** Two independent semantic
rechecks (2026-08-16 QW-5 #4 and 2026-08-19 reader 1) agree: the page's Persyaratan
section is 3 generic items and supports none of the D1/D2/D12 facts it is co-cited for.
Seq-9 already dropped its 18 rule-level refs; the 3 remaining PRODUCT-level refs
(D1/D2/D12) were left "out of scope" then. With the second recheck in evidence, seq-10
removes those 3 product refs and drops the record (0497cb52 precedent: zero active refs →
drop, with a fold-gate asserting zero refs remain). Each product keeps its own dedicated
page record (ca5a2ce8/d3ad622e/5e64ec6b), all re-stamped CURRENT — no citation coverage
is lost.

## 3. Phase B — the two cures

### 3a. `el.c2.corporate-sponsor-type` → RETIRED (no replacement)

Grounding attempt (mandated by CP3) came back **refuted**:
- Live C2 page (2026-08-19T04:21:51Z): *"Anda tidak membutuhkan penjamin/sponsor untuk
  mengajukan visa ini"* — no sponsor by default (exceptions: stateless, non-national
  travel document, listed nationalities). Zero corporate-sponsor language anywhere.
- Production catalog (`get_visa_details c2`): `sponsor_required: false`,
  `invitation_required: true` (invitation from company/institution ≠ penjamin).
- No claim in any ledger names `sponsor.type`/corporate for C2; `CL-C2-03`
  (VERIFIED-WITH-CAVEAT, PROSE_ONLY) asserts a mandatory penjamin per Permenkumham
  11/2024 Pasal 1(18) — now in three-way tension with the portal and the catalog. New
  conflict entry **CF-17** records this (claims ledger, §4); it is a doctrine question,
  not a seq-10 rule edit.

Structural fact (verified on seq-9 bytes this session): the rule's deduplicated subtree
is canonical-JSON-identical to `el.c2.business`'s ENTIRE `when`. Post-dedupe the rule
would be an exact condition-duplicate of the healthy sibling, differing only in the
false-promise `reason_code`. Retiring it (removal from `rules[]`, the
`el.e33e.deposit-income-basis` precedent) removes the lie with zero behavioral change:
`el.c2.business` still grants the identical SUPPORT on the identical facts. Witness test
pins C2 reachability unchanged and `C2_CORPORATE_SPONSOR_TYPE_VERIFICATION` absent.
`SUPPORT_REASON_COPY` keeps the old code's entry (map is additive; seq-9's file on disk
still carries it — the mouth glob covers every pack file).

### 3b. `el.e31c-mixed-marriage-parents` → tightened in place + new HARD_FILTER

Grounding (live E31C page, full Persyaratan transcribed in the evidence doc):
- *"Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini"* — sponsor required.
- Item 1: *"Surat permohonan visa dari ayah/ibu Warga Negara Indonesia"* + item 9
  (Kartu Keluarga of the WNI parent) — the sponsoring parent is the Indonesian-citizen
  parent → grounds `family.sponsor_nationalities ∩ {ID}` (claim CL-E31C-03).
- Item 8: *"Bukti perkawinan orang tua berupa: Bukti pelaporan atau pencatatan pada
  Perwakilan Republik Indonesia atau instansi yang berwenang di bidang pencatatan sipil
  dan akta perkawinan yang telah diterjemahkan ... oleh penerjemah tersumpah; atau Buku
  nikah atau akta perkawinan yang dikeluarkan oleh kementerian atau lembaga berwenang"*
  — proof of the parents' legally registered marriage is a hard requirement → grounds
  `family.marriage_registered == true` (claim CL-E31C-02).

Both FactPaths are in the closed vocabulary (no wire change). Two edits:

1. **Rule edit (ledger-drift format)** on `el.e31c-mixed-marriage-parents`: `when`
   deduped from `all(X,X)` and tightened to
   `all(purposes ∩ {FAMILY}, relation_to_sponsor == PARENT, marriage_registered == true,
   sponsor_nationalities ∩ {ID})` — the E31A spouse-rule pattern. `reason_code`
   `REQ_MIXED_MARRIAGE_PARENTS` KEPT (now honest — it finally tests what it names).
   `required_facts` re-derived. rule_id, priority, valid_period, source_refs
   (40523028 + e3572ad2), explanation_key, product_version_ids preserved verbatim.
2. **New rule `hf.e31c-marriage-not-registered`** (HARD_FILTER, the
   `hf.e31e-adult-excluded` shape): scope PRODUCTS on E31C's
   `62ab2d13-1d7e-5048-9cf7-9622c0098439`, `when` =
   `all(purposes ∩ {FAMILY}, relation_to_sponsor == PARENT, marriage_registered == false)`
   — the purpose/relation conjuncts are load-bearing (Codex refuter finding 1,
   empirically reproduced: a single-leaf `marriage == false` filter turned a STUDY
   applicant's E31C proof from seq-9's silent UNSUPPORTED into BLOCKED_UNKNOWN
   demanding the marriage fact; scoped, the filter is strong-Kleene FALSE outside the
   FAMILY+PARENT shape). Effect `EXCLUDE` with NEW code
   `REQ_PARENTS_MARRIAGE_REGISTERED`, `on_unknown: NEEDS_INPUT`, `safety_critical:
   true`, sources 40523028 + e3572ad2. Framing (per the Kimi review): the rule-1 edit
   is the honest-CITATION cure (the reason_code finally tests what it names, but the
   broad sibling keeps the verdict unchanged); this HARD_FILTER is the entire
   BEHAVIORAL cure — `false` → EXCLUDED, `UNKNOWN` → NEEDS_INPUT (tri-state asks).
   E33G precedent: the cure of the vacuous rule shipped WITH its paired enforcement
   rule. The EXCLUDE code IS user-visible via the adapter's `reasonMessage` fallback —
   curated EN/ID copy ships in the same change (`engine-adapter.ts`), and a companion
   mouth-flow change makes the interview actually ASK `family_marriage_registered` for
   PARENT relation (it was SPOUSE-gated — Kimi finding 1: without this, every real
   E31C interview shipped the fact UNKNOWN by construction and dead-ended in
   NEEDS_INPUT).

NOT touched, deliberately: `el.e31c-child-mixed-marriage-support` (not a lint residual,
not in the mandate — its breadth is now bounded by the HF); `el.c2.business`'s
`family.sponsor_confirmed` gate (conservative direction — the engine asks for more, never
grants on less; CF-17 records the tension for a future doctrine round); product
`sponsor_types` metadata (not consumed by the evaluator — enums.py:498-509).

## 4. Claims (new ledger `claims/inc4-c2-e31c-claim-ledger.md`)

- **CL-E31C-02** — E31C requires official proof of the parents' legally registered
  marriage (two routes: foreign registration + sworn translation, or Indonesian
  buku nikah/akta). Source: OFFICIAL_PORTAL 40523028 live fetch 2026-08-19T04:22:00Z
  (verbatim item 8) + e3572ad2 (Kepmen framing). State **VERIFIED**. Products: E31C.
  Backs: `el.e31c-mixed-marriage-parents` (tightened) + `hf.e31c-marriage-not-registered`.
- **CL-E31C-03** — E31C's penjamin is the Indonesian-citizen parent (portal items 1+9).
  State **VERIFIED**. Products: E31C. Backs the `sponsor_nationalities ∩ {ID}` conjunct.
- **CF-17** — C2 sponsor three-way conflict (portal "no sponsor by default" vs CL-C2-03
  mandatory-penjamin vs product metadata `sponsor_types: [EMPLOYER]`). State
  **CONFLICTING**, OPEN. Consequence recorded: no compilable corporate-sponsor claim
  exists → grounds the §3a retirement; flags `el.c2.business`'s sponsor gate as a future
  doctrine question (kept, conservative).

## 5. Residuals declared (not cured here)

- E30A `38242587` remains the sole cited source for `review.minor-without-guardian`,
  which its page does not support (known since QW-5, re-confirmed live). Needs a
  re-sourcing edit (E31E pattern) in a future increment — PENDING-ARMS row.
- CF-16 (C2 onshore conversion) and CF-17 (C2 sponsor) stay OPEN — doctrine, not rules.
- Re-attestation CADENCE (the 7-day windows will lapse again ~2026-08-26) remains a
  Zero/Legge-5 ruling — this increment is the one-time re-stamp that was ordered.

## 6. Fold script + gates (`fold_pack_seq10.py`, sibling of fold_pack.py)

Deterministic, no CLI flags. Gates: uuid5 anchor; chain hash read live from
`rulepack-prod-009.signed.json` + asserted against the expected constant; retirement
count == 1; rule-edit ledger-drift (`current_value` must match seq-9 bytes); insertion
uniqueness; re-stamp ledger-drift on all 17 (`verified_at`/`verified_by` current values
asserted); ee8fe5b8 product-ref removal count == 3 then zero-refs assert then drop;
everything-else byte-match vs seq-9 (rule-by-rule + record-by-record); Pydantic
`RulePackPayload.model_validate`; atomic write + prettier; idempotence (run twice,
byte-identical).

## 7. Test plan (`test_seq10_pack.py` + evaluator witnesses)

Chain (recompute seq-9 canonical hash == signed `payload_sha256` == seq-10
`previous_payload_sha256`); `sequence == 10`; uuid5; lint sibling of
`TestInc2LintsOverEverySeq9Rule` over every seq-10 rule expecting **zero** findings;
byte-invariance of untouched rules/records vs seq-9; real-evaluator witnesses:
guilt (E31C full facts + `marriage_registered=false` → EXCLUDED with
`REQ_PARENTS_MARRIAGE_REGISTERED`), innocence (full facts + registered marriage + WNI
parent sponsor → SUPPORTED with `REQ_MIXED_MARRIAGE_PARENTS`), tri-state
(`marriage_registered` UNKNOWN → not conclusive), C2 regression (business facts →
SUPPORT unchanged via `el.c2.business`; retired reason absent). Then `compile_pack` RC 0
and `reachability_report` (expect 29/38 unchanged; E31C conclusive path now demands the
marriage fact).

## 8. Ship sequence

PR (fold + edits + tests + evidence docs) → arm bare `gh pr merge --auto` → merge →
sign on M5 from a detached worktree at origin/main (`--sequence 10`, kid
`prod-2026-07-1`) → bundle PR (prettier the signed JSON; bump `_OFFLINE_AT` only if
signed_at > 2026-08-19T12:00Z) → two-login activation (`--current-sequence 9`,
`--current-payload-sha256 47feff82…`; ceremony-seq9.zsh pattern + M5 credential-path
memory) → smoke: IT full-facts persona expecting a CONCLUSIVE verdict (no
DECISIVE_SOURCE_STALE), NG calling-visa positive control, E31C guilt/innocence live,
all-UNKNOWN fail-closed → LIVE STATE + close the two PENDING-ARMS rows (residuals cure;
staleness re-stamp) + open the E30A row → CLEAN → CAPTURE.

## Adversarial review

Two cross-family seats (Codex GPT-5.6-sol xhigh; Kimi K3), single shared round over
the whole inc4 edit set, executed against the first draft of the fold. Codex: REJECT
(2 BLOCKER / 1 MAJOR / 2 MINOR / 1 NOTE); Kimi: no BLOCKER, 1 activation-gating MAJOR.
Every finding re-verified by the orchestrator, cures applied, pack re-folded
(final hash `1ff7383f5b3c2e2a…`). This spec's §3b was rewritten accordingly (scoped
HARD_FILTER; honest framing; mouth companion change). Full findings + dispositions:
`inc4-pack-edits/cure-c2-e31c.md` §Adversarial review.
