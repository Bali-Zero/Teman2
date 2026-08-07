---
date: 2026-08-08
domain: visa
client_case: none — Visa Oracle v2 decision-tree full-index design (Track B/A convergence)
sources:
  - .agents/skills/visaoracle/SKILL.md + CURRENT_STATE.md (corner, LIVE STATE 2026-08-08)
  - HANDOFF-2026-08-08-voa-conclusive-rate.md (PR #3779, root-cause 0% conclusive)
  - research/visa/2026-07-17-visa-catalog-bonifica-110-remap.md (110/114 KEEP per-code verified)
  - research/visa/2026-07-17-bridging-visa-branch-d7ab-diaspora-closeout.md (D7A/D7B/D8A/D8B EXIST)
  - research/visa/2026-07-17-visa-oracle-v2-round2-glm-interview-design.md (interview design, implemented in Track C)
  - research/visa/2026-07-24-w2-factbase-*.md (8 family fact-bases)
  - research/visa/2026-07-23-d1-decision-pack.md (real traffic ~0.8 sess/day)
  - Round-1 2026-08-08 lanes: Codex gpt-5.6-sol xhigh architecture+red-team (repo-grounded), Gemini 3.1 Pro High regulatory width (via Pro), house Sonnet web-grounded VOA-list lane
adversarial_review: pending — 4-LLM panel round scheduled on this document (degraded roster declared: GLM Keychain-dead, Kimi quota-dead, NLM auth-dead on Mini; seats = Gemini + Codex + house web-grounded)
status: DRAFT for panel
---

# Decision Tree V2 — full-index design (Round-1 synthesis)

## 0. Mandate

Zero, 2026-08-08: the decision tree must cover the FULL current official visa Index (~110 indexes, Kepmen Imipas M.IP-08.GR.01.01/2025) — per visa: what it is for, who it is for, every nationality/age/financial limitation — leading a traveller through questions to the final visa(s). Target from the standing handoff: conclusive-rate 0% → >60% on real traffic. Product contract unchanged: zero unsupported recommendations, fail-closed abstention, only the signed RulePack selects paths, SHADOW only (ENFORCE stays Zero-gated on DPIA + analytics TTL).

## 1. Ground (all verified this session)

- **Catalog**: seed = 114 rows; 110/114 confirmed KEEP per-code (bonifica 2026-07-17, negative-control method); 4 OUT-OF-SCOPE service/product rows (E23-FREELANCE, EPO, ERP, SKTT); +4 missing official codes proven to EXIST: D7A, D7B, D8A, D8B (closeout, double-verified) → official D-series is 13 codes, seed has 9.
- **Active pack**: 38 products / 110 rules (17 HARD_FILTER, 65 HUMAN_REVIEW, 28 ELIGIBILITY, 0 RANKING). Sequence trap: on-disk source file says sequence 2; active DB row is seq 3 (re-signed identical content, retroactive legal_period) — artifact identity ≠ activation identity.
- **Interview** (Track C, live): 48 questions, 10 categories, 35 FACT + 12 HUMAN_CONTEXT + 1 REVIEW_ONLY; covers 34/40 FactPaths; 5 always NOT_ASKED by the mapper.
- **Root cause of 0% conclusive** (handoff + Codex confirmation):
  (a) 30/63 PRODUCTS-scoped HUMAN_REVIEW rules keyed on `intent.purposes` alone;
  (b) D1/D2/D12 match plain tourists (no `entry_pattern` condition, foreign purposes);
  (c) P0-B precedence (any REVIEW masks all SUPPORTED, `evaluator.py:1381-1405`);
  (d) `el.b1.tourism` has no nationality gate.
- **SECOND BLOCKER** (Codex §3.5, decisive): 12 HUMAN_CONTEXT interview answers map to disclosed review flags, and ANY flag forces HUMAN_REVIEW_REQUIRED and clears candidates (`evaluate_path.py:1173-1220, 1449-1462`). Pack repair alone cannot reach >60% for non-tourism categories.
- **KB raw material**: `apps/kb/data/immigration` = 87 official per-code scrape files from imigrasi.go.id (provenance headers) — the fact-base feedstock for the long tail. 8 W2 fact-bases already exist (bridging, bvk, dseries, e23, e28, e31, e33, student).
- **Real traffic**: ~0.8 sessions/day whole funnel (D1 pack) — proof of conclusive-rate must be replay + labeled synthetic corpus, not organic volume.

## 2. Round-1 regulatory findings (new, 2026-08-08)

### 2.1 VOA (B1) nationality list — the missing gate

Working list: 97 countries, triangulated on two mutually-consistent government-domain reproductions (depok.imigrasi.go.id + detik 2026-01-24). Base instrument Kepmenkumham M.HH-02.GR.01.06/2024 (9 Jan 2024, 97 countries) — KNOWN STALE on ≥1 point: Macau removed ~25 Nov 2024 (confirmed multi-source; Macau moved to BVK via Permenimipas 10/2026). Amending instrument number(s) post-Jan-2024 NOT identified. Central imigrasi.go.id FAQ is stale (Jan 2024): wrong on Macau + San Marino today.

Fail-closed encoding for pack seq-4:

| Bucket | Countries | Encoding |
|---|---|---|
| KNOWN | 95 (both Jan-2024 FAQ ∩ current reproductions) | allowlist, ELIGIBILITY |
| Needs ratification | Azerbaijan, Mauritius (only in current lists, no instrument found) | include ONLY with Zero source-ratification (same class as the CM/GN announcement-level ruling); else HUMAN_REVIEW |
| Removal not corroborated | San Marino | HUMAN_REVIEW, never auto-include |
| Excluded | Macau | NOT in VOA — routes to A1/BVK path |

Freshness policy on the list source: 7d portal class.

Operational facts (verified): IDR 500,000; 30 days; one +30-day extension; not convertible. Ports-of-entry list NOT current (2022 data) — do not surface port claims.

### 2.2 BVK control list

19 members per Permenimipas 10/2026 (13 pre + TR, BR, PE, KZ, MO, BY added 2026-07-09). OPEN: corner records "19 states/SARs + 1 entity" — reconcile the +1 entity during implementation (grep the A1 pack rules + the 10/2026 text).

### 2.3 Per-index limits confirmed by the Gemini lane

Secondary confirmations of already-held facts; instrument-grade sources required at authoring time:

- E33G income ≥ USD 60k/yr
- E33 deposit ≥ USD 130k
- E28A ≥ IDR 10 mld share ownership
- Golden tiers E28B-E: USD 350k–50M
- Retirement age threshold to re-verify (55 vs 60 conflict between sources — resolve from primary at authoring)
- Passport-validity floors scale with permit duration
- Sponsor-free: E33*, E28*
- Guarantor: E23, most C-class

### 2.4 Traps for the tree

Gemini lane, consistent with our archive:

- A1 ≠ B1 (extension!)
- C vs D = single vs multi entry (ask re-entry intent)
- E33G vs E33 = salary vs capital
- "Golden Visa" is never a terminal node (parse individual/corporate × vehicle × zone)

## 3. Architecture decision (proposed, panel-gated where marked)

### Phase A — pack seq-4 repair (NO contract change, this session)

Implements handoff §4 items 1-5 + VOA gate with the fail-closed encoding above:

1. D1: `entry_pattern=MULTIPLE` on `el.d1*` + the 5 `hr.d1-*` rules.
2. D2: `purposes ∩ {BUSINESS_MEETINGS}` only + same alignment.
3. D12: `purposes ∩ {INVESTMENT}` only + same alignment.
4. B1 nationality gate (HARD_FILTER not-in-list + ELIGIBILITY in-list, on `person.nationalities` as interim — travel-document fact is Phase C; document the dual-national approximation explicitly).
5. Sweep the remaining 30 purpose-only PRODUCTS reviews: each either gains its product's real applicability discriminators or is demoted to checklist (non-blocking) — target: 0 purpose-only product reviews, with a pack-diff report.
6. New sequence (4), new `rule_pack_id` per uuid5 convention, M5 signing ceremony (keys never leave M5), pre-activation semantic diff, SHADOW activation.

Verification: handoff §2 payload replay → SUPPORTED_CANDIDATES/B1_VOA_ELIGIBLE; Calling-Visa positive controls unchanged (Nigeria still flagged, Cameroon/Italy normal); existing gold suite green with an accepted-delta manifest (target: zero UNEXPLAINED change, not zero change).

### Phase B — full-index waves (Codex plan, adopted)

Wave 0 crosswalk (official index ↔ product ↔ seed ↔ pricing; add D7A/B/D8A/B to catalog; classify OFFICIAL_INDEX/SERVICE/LEGACY/WITHDRAWN/UNAVAILABLE) →

- W1: A/B/F + C1/C2
- W2: full C-family
- W3: full D-family (13)
- W4: E31 + E30
- W5: E28 + E33
- W6: E2x work (highest risk, last of the big families)
- W7: specialist (E32, E34, E35, crew/government)

Authoring feedstock: 87 KB scrape files + 8 W2 fact-bases; every axis of the product profile carries REQUIRED/PROHIBITED/NOT_APPLICABLE/REVIEW/UNVERIFIED_SOURCE — UNVERIFIED_SOURCE keeps the branch fail-closed. Estimated full-index pack: ~350-430 rules (compiler caps 256 products / 4096 rules — comfortable).

### Phase C — contract expansion (4-LLM panel MANDATORY before any of it)

(a) New FactPaths: `person.travel_document_country_code` + type + passport_expiry_date; `intent.activity_subtype`; `finance.available_funds`; `work.rptka_status`/job_family/kbli_match; `investment.vehicle`/target; `family.sponsor_type`; `person.former_indonesian_citizen` + descent; `study.program_type`; remote income period; specialist confirmations. Typed assertions only — no raw documents in the facts envelope.

(b) Promote legally-discriminative HUMAN_CONTEXT questions to signed facts; keep flags only for genuine ambiguity.

(c) P0-B evolution: Option A (pack-only, Phase A) is the measured baseline; then evaluate B (APPLICABILITY stage) / C (DECISION_BLOCKING vs CANDIDATE_LOCAL review) / D (route frontier) — Codex leans "A first, then B+C combined as a NEW CONTRACT, never a patch". The panel decides; not this doc.

## 4. Verification harness (adopted from Codex §5)

- Coverage matrix invariant chain: official index → product → eligibility rule → sources → reachable facts → gold cases.
- 4-6 gold cases per product (~500-700 total) incl. nearest-sibling collisions: B1/D1, C2/D2, C12/D12/E28, remote/employment, E23/investor-director, E31 variants, E33 triplet.
- Extended metamorphic properties: UNKNOWN never adds candidates; nationality-set growth never defeats a document-country restriction; SINGLE→MULTIPLE flips; threshold n-1/n/n+1; re-sign identity invariance.
- Conclusive-rate = (SUPPORTED + NO_SUPPORTED_PATH) / valid real completed interviews, NO_SUPPORTED_PATH counted only at full coverage, Wilson 95% lower bound > 60%, synthetic excluded and labeled.

## 5. Red team (top risks, from Codex §6, kept verbatim in spirit)

1. Stale sources.
2. Catalog-mistaken-for-law.
3. Purpose-only explosion.
4. Citizenship ≠ passport-used.
5. UI flags defeat pack repairs.
6. Vocabulary underfit.
7. PII creep.
8. Multi-purpose combinatorics.
9. Conclusive-rate gaming.
10. Pack supply-chain drift.

## 6. Decisions for Zero (open)

1. Ratify depok.imigrasi.go.id + detik as sufficient evidence for AZ/MU on the VOA list (CM/GN-class decision), or keep both HUMAN_REVIEW until the amending Kepmen is retrieved.
2. D1 G-a-vol threshold (standing: proposal ≥100 real/14d in the D1 pack).
3. Retirement age 55/60 conflict — authorize primary-source pull at W5 authoring.
4. DPIA + analytics TTL remain the ENFORCE blockers (unchanged, not part of this program).

## 7. Session ledger

Round-1 lanes: Codex sol xhigh (repo-grounded architecture+red-team) · Gemini 3.1 Pro High via Pro (regulatory width; 2 claims discarded with evidence: E28F/G "missing" — present in seed; CM/GN re-litigation — Zero-ratified, no new evidence) · house Sonnet web-grounded (VOA list) · internal inventory (Sonnet Explore). Dead seats declared: GLM (Keychain), Kimi (quota), NLM (auth) — cures are operator[credential]/[business].

## Adversarial review

Pending — panel round on this document follows; dispositions will be appended here before ship.
