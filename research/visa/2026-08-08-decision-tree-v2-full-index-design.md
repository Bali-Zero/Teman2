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
adversarial_review: round-1 dispositions applied 2026-08-08 (roster: Gemini 3.1 Pro High ✅ full verdict, Codex gpt-5.6-sol xhigh ✅ died pre-consolidation — findings recovered from intermediate messages + empirical evaluator run, house refuter Sonnet 2nd pass pending on this updated doc; GLM/Kimi/NLM unavailable, declared). Operator (Zero) supplied the 2026-08-08 official portal lists (VOA/BVK/CallingVisa/TPI) as primary evidence.
status: DRAFT — panel round-1 dispositions applied, house refuter 2nd pass pending before ship
---

# Decision Tree V2 — full-index design (Round-1 synthesis)

## 0. Mandate

Zero, 2026-08-08: the decision tree must cover the FULL current official visa Index (~110 indexes, Kepmen Imipas M.IP-08.GR.01.01/2025) — per visa: what it is for, who it is for, every nationality/age/financial limitation — leading a traveller through questions to the final visa(s). Target from the standing handoff: conclusive-rate 0% → >60% on real traffic. Product contract unchanged: zero unsupported recommendations, fail-closed abstention, only the signed RulePack selects paths, SHADOW only (ENFORCE stays Zero-gated on DPIA + analytics TTL).

## 1. Ground

Provenance note (Codex, ACCEPTED): `HANDOFF-2026-08-08-voa-conclusive-rate.md` and the 3 Round-1 lane reports are second-hand artifacts, not files present in this worktree — origin: handoff in PR #3779, lane reports in the session scratchpad. The label "verified this session" below is reserved for the jq/evaluator runs actually reproduced (see the Acceptance proof subsection in §3).

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

97 countries KNOWN allowlist — Azerbaijan (#10) and Mauritius (#53) INCLUDED; San Marino and Macau EXCLUDED (San Marino removed ~Nov 2024, corroborated; Macau moved to BVK via Permenimipas 10/2026, effective 2026-07-09). 3 concordant sources: operator-supplied portal list 2026-08-08 (counted: 97) + depok.imigrasi.go.id (97, AZ #10, MU #53) + detik. Documented trap: the central imigrasi.go.id FAQ is stale as of 19-Jan-2024 (still lists San Marino #71 and Macau #48; missing AZ/MU) — do not use it as the working list. Base instrument Kepmenkumham M.HH-02.GR.01.06/2024 (9 Jan 2024, 97 countries then); the amending instrument number(s) that produced the CURRENT 97 (AZ/MU in, SM/MO out) is still NOT NAMED → authoring task at Wave 1 (downgraded from a Zero-decision, see §6). Freshness window: 7d on the portal source.

Fail-closed encoding for pack seq-4:

| Bucket | Countries | Encoding |
|---|---|---|
| KNOWN allowlist — RATIFIED (Zero, 2026-08-08, operator portal list) | 97, incl. Azerbaijan and Mauritius | allowlist, ELIGIBILITY |
| Excluded | San Marino (removal corroborated, never auto-include) | NOT in VOA allowlist |
| Excluded | Macau | NOT in VOA — routes to A1/BVK path |

Freshness policy on the list source: 7d portal class.

Operational facts (verified): IDR 500,000; 30 days; one +30-day extension; not convertible. Ports-of-entry list NOT current (2022 data) — do not surface port claims (see the TPI subsection below for the current count and design rule).

### 2.2 BVK control list — 19 members + 1 entity (open item CLOSED)

19 members + 1 entity per Permenimipas 10/2026 — 13 historical (ASEAN + Timor Leste, Suriname, Colombia, Hong Kong) + 6 added 2026-07-09 (Berita Negara 463/2026, revoking Permenimipas 10/2025): Turkey, Brazil, Peru, Kazakhstan, Macau, Belarus. The "+1 entity" the corner recorded as open: foreign holders of a SINGAPORE permanent-residence permit, designated via TPI. RESOLVED — it is the Singapore-PR class, not a 20th state/SAR. NOT automatable in Phase A/B: it needs PR-status + port-of-entry facts outside the current vocabulary → candidate FactPath for Phase C; encode as HUMAN_REVIEW / outcome-copy note until then.

### 2.3 Calling Visa list — confirmed unchanged

6 countries: Afghanistan, Israel, North Korea, Liberia, Nigeria, Somalia (AF, IL, KP, LR, NG, SO). Confirms the existing corner decision, Zero-ratified — INVARIANT, no change. 3 concordant sources: operator-supplied list 2026-08-08 (operator's own correction: Somalia included), the central imigrasi.go.id page, and the bontang mirror.

### 2.4 TPI designated ports of entry — 122, not an interview question

122 designated Tempat Pemeriksaan Imigrasi (16 airports, 11 land border crossings, 95 seaports — counted from the operator-supplied 2026-08-08 list). Design rule: the port of entry does NOT become an interview question in Phase A/B — Bali is fully covered (Ngurah Rai; Benoa, Padang Bai, Celukan Bawang, plus Lembar in NTB) — it goes into outcome copy instead ("VOA/exemption valid only at designated TPI"). `immigration.intended_port_of_entry` is a candidate FactPath for Phase C.

### 2.5 Per-index limits confirmed by the Gemini lane

Secondary confirmations of already-held facts; instrument-grade sources required at authoring time. 3 Gemini objections were ACCEPTED and are folded in here as corrections (full disposition table in the Adversarial review section):

- E33G income ≥ USD 60k/yr [UNREFUTED].
- E33 (Second Home base) deposit: **IDR 2,000,000,000 at a state bank OR property ≥ USD 1,000,000** — CORRECTED (Gemini P1 ACCEPTED): never "USD 130k" as this doc previously stated. The `secondhome.*` FactPaths are denominated in USD → currency reconciliation is a Phase C task; both numbers to be re-pulled from primary source at Wave 5 authoring.
- E28A has TWO distinct capital gates (CORRECTED, Codex ACCEPTED — never fuse into one threshold): paid-in capital (modal disetor) ≥ IDR 2.5 mld, and investment plan (rencana investasi) ≥ IDR 10 mld [this IDR 10 mld figure is the Gemini UNREFUTED confirmation; this doc previously mislabeled it as a single "share ownership" threshold].
- Golden tiers E28B/C/D/F: USD 350k–50M [UNREFUTED]. CORRECTED (Codex ACCEPTED): the previous "E28B-E" range label wrongly folded in E28E — its threshold is UNVERIFIED in the fact-base and is excluded from this verified range; E28E stays flagged UNVERIFIED pending Wave 5 authoring.
- Retirement age: NO conflict (CORRECTED, Gemini P2 ACCEPTED) — two distinct indexes: E33F (Retirement) 55+, E33E (Silver Hair) 60+. Re-verify both against primary source at Wave 5 authoring.
- Passport-validity floors scale with permit duration.
- Sponsor-free / sponsored (CORRECTED, Codex ACCEPTED): "Sponsor-free: E33\*, E28\*" was false. Sponsor-free: E33 base, E33B, E33E, E33G; E28C (self-sponsor). Sponsored: E33A (central-government/pemerintah pusat sponsor mandatory), E33C (central government mandatory), E33F (LOCAL_SPONSOR/Penjamin required); several E28 codes carry `sponsor_types` in the pack (e.g. C2 EMPLOYER, E23 EMPLOYER, E23V GOVERNMENT).
- Guarantor: E23, most C-class.

### 2.6 Traps for the tree

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
4. B1 nationality gate: HARD_FILTER `hf.b1.not-voa-nationality` (EXCLUDE, `on_unknown=HUMAN_REVIEW`, safety_critical) + ELIGIBILITY in-list, gated on the passport actually traveled with — the interview asks "which passport will you travel with?" and the nationality gate evaluates THAT document's country. CORRECTED (Codex P0-2 ACCEPTED): the contract only knows the `person.nationalities` set, not the passport used — with `intersects`, an eligible nationality could wrongly authorize B1 even when the presented document isn't eligible, and vice versa. If the traveller holds multiple nationalities with divergent VOA/BVK/calling-visa outcomes and the travel document is not established → HUMAN_REVIEW (fail-closed). `person.travel_document_country_code` (+ type + expiry) remains the Phase C contract addition that removes this interim approximation.
5. Sweep the remaining 30 purpose-only PRODUCTS reviews: each gains its product's real applicability discriminators (purpose + entry-pattern, per items 1-3 above) so it stops firing out-of-target — proven at the case level in the Acceptance proof below. CORRECTED (Codex P0-1 ACCEPTED): the RulePack contract has NO "non-blocking checklist" effect — Phase A does NOT "demote to checklist" as this doc previously said. Document-requirement copy lives in the UI's outcome copy, not in rules. A genuine CHECKLIST effect in the contract is Phase C work, panel-gated.
6. New sequence (4), new `rule_pack_id` per uuid5 convention, M5 signing ceremony (keys never leave M5), pre-activation semantic diff, SHADOW activation.

#### Acceptance proof (evaluator run, Codex seat, 2026-08-08)

Codex executed the REAL evaluator (`evaluate_with_trace`, pack `rulepack-prod-002.signed`) on the target case IT/TOURISM/10 days offshore:

- **CURRENT pack** → `HUMAN_REVIEW_REQUIRED` with 15 review reasons (`hr.d1-*` / `hr.d2-*` / `hr.d12-*`).
- **With the Phase A corrections applied in-memory** (D1: AND `entry_pattern=MULTIPLE`; D2: purpose `BUSINESS_MEETINGS` only; D12: purpose `INVESTMENT` only; B1: AND nationality gate + new `hf.b1.not-voa-nationality` EXCLUDE with `on_unknown=HUMAN_REVIEW` safety_critical) → **`SUPPORTED_CANDIDATES` [B1 (`el.b1.tourism`), C1 (`el.c1.tourism-family`)], review [], missing []**.
- `review.calling-visa` evaluates false (not unknown) for the known-IT case.

This run IS the acceptance-criterion template for the seq-4 pack: the replay must reproduce it.

Verification: handoff §2 payload replay → SUPPORTED_CANDIDATES/B1_VOA_ELIGIBLE (now anchored to the reproduced run above); Calling-Visa positive controls unchanged (Nigeria still flagged, Cameroon/Italy normal); existing gold suite green with an accepted-delta manifest (target: zero UNEXPLAINED change, not zero change).

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

1. RATIFIED (Zero, 2026-08-08): Azerbaijan and Mauritius are IN the VOA allowlist, on the operator-supplied 2026-08-08 portal list corroborated by depok.imigrasi.go.id + detik. Only remaining open item: NAME the amending Kepmen/Permenkumham instrument that produced the current 97-country list — downgraded from a Zero-decision to an authoring task at Wave 1.
2. D1 G-a-vol threshold — unchanged (standing: proposal ≥100 real/14d in the D1 pack).
3. Retirement age — NO conflict found (Gemini P2 ACCEPTED): E33F (Retirement) 55+, E33E (Silver Hair) 60+ are two distinct indexes, not a 55-vs-60 disagreement. Authorize primary-source re-verification of both thresholds at Wave 5 authoring.
4. DPIA + analytics TTL remain the ENFORCE blockers (unchanged, not part of this program).

## 7. Session ledger

Round-1 lanes: Codex sol xhigh (repo-grounded architecture+red-team) · Gemini 3.1 Pro High via Pro (regulatory width; 2 claims discarded with evidence: E28F/G "missing" — present in seed; CM/GN re-litigation — Zero-ratified, no new evidence) · house Sonnet web-grounded (VOA list) · internal inventory (Sonnet Explore). Dead seats declared: GLM (Keychain), Kimi (quota), NLM (auth) — cures are operator[credential]/[business].

## Adversarial review

**Roster (round 1, 2026-08-08)**: Gemini 3.1 Pro High ✅ full verdict · Codex gpt-5.6-sol xhigh ✅ (died pre-consolidation — findings recovered from intermediate messages + the empirical evaluator run in the §3 Acceptance proof subsection) · house refuter Sonnet — 2nd pass PENDING on this updated document · GLM (Keychain-dead) / Kimi (quota-dead) / NLM (auth-dead on Mini) unavailable, declared. Operator (Zero) supplied the 2026-08-08 official portal lists (VOA/BVK/Calling-Visa/TPI) as primary evidence.

**Dispositions table** (claim → seat → verdict → fix applied):

| # | Claim | Seat | Verdict | Fix applied |
|---|---|---|---|---|
| 1 | VOA/B1 = 97 countries incl. AZ, MU; excl. San Marino, Macau | Operator list + depok.imigrasi.go.id + detik (3-source concordance) | ACCEPTED | §2.1 rewritten: AZ/MU ratified into KNOWN allowlist, San Marino moved to Excluded |
| 2 | BVK = 19 members + 1 entity (Singapore-PR via TPI) | Operator list + Permenimipas 10/2026 | ACCEPTED, corner open-item CLOSED | §2.2 rewritten with the 6 2026-07-09 additions + the entity resolved |
| 3 | Calling Visa = 6 (AF, IL, KP, LR, NG, SO) | Operator list (self-corrected: Somalia included) + imigrasi.go.id + bontang mirror | CONFIRMED, unchanged | New §2.3 added |
| 4 | TPI designated = 122 (16 air / 11 land / 95 sea) | Operator list 2026-08-08 | CONFIRMED | New §2.4 added; port-of-entry stays out of the interview, moves to outcome copy |
| 5 | San Marino should be HUMAN_REVIEW, not excluded | Gemini (P1) | ACCEPTED | §2.1 bucket corrected to Excluded |
| 6 | E33 Second Home deposit = USD 130k | Gemini (P1) | ACCEPTED — corruption | §2.5 corrected to IDR 2,000,000,000 / state bank OR property USD 1,000,000 |
| 7 | Retirement age 55-vs-60 conflict | Gemini (P2) | ACCEPTED — no conflict, two distinct indexes | §2.5 + §6 corrected: E33F 55+, E33E 60+ |
| 8 | BVK 19 / index ~110 / E28A personal-quota IDR 10 mld / E33G USD 60k+Golden 350k-50M | Gemini | UNREFUTED | Retained verbatim |
| 9 | Empirical evaluator run: CURRENT pack → HUMAN_REVIEW_REQUIRED (15 reasons); Phase-A-targeted → SUPPORTED_CANDIDATES [B1, C1] | Codex (empirical, `evaluate_with_trace` on `rulepack-prod-002.signed`) | ACCEPTED — reproduced | New "Acceptance proof" subsection added under Phase A |
| 10 | Phase A item 5 "demote to checklist" | Codex (P0-1) | ACCEPTED — contract has no checklist effect | Item 5 rewritten: rules scoped by purpose/entry-pattern; doc requirements in outcome copy; checklist effect deferred to Phase C |
| 11 | B1 gate should key on `person.nationalities`, not travel document | Codex (P0-2) | ACCEPTED | Phase A item 4 rewritten: interview asks travel-document country; dual-national divergence → HUMAN_REVIEW |
| 12 | HANDOFF + Round-1 lane reports are "verified this session" | Codex (provenance) | ACCEPTED | §1 header/provenance note corrected: second-hand artifacts cited with PR/path of origin; "verified this session" reserved for reproduced runs |
| 13 | E28A ≥ IDR 10 mld is a single threshold | Codex | ACCEPTED — corruption | §2.5 corrected: paid-in capital IDR 2.5 mld + investment plan IDR 10 mld are two distinct gates |
| 14 | Golden tiers span E28B-E | Codex | ACCEPTED — corruption | §2.5 corrected: E28B/C/D/F verified 350k–50M; E28E threshold UNVERIFIED, excluded from range |
| 15 | "Sponsor-free: E33\*, E28\*" | Codex | ACCEPTED — corruption | §2.5 corrected: named sponsor-free codes (E33 base, E33B, E33E, E33G, E28C) vs sponsored (E33A, E33C, E33F, several E28) |

House refuter Sonnet 2nd pass on this updated document is PENDING; further dispositions will be appended here before ship (push/PR owned by the orchestrator, not this writer pass).
