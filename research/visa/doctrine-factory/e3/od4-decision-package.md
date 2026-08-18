---
date: 2026-08-18
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/cards/E23U.md (branch agent/air-m5/ops/e3-cards-work)
  - path: research/visa/doctrine-factory/cards/E23V.md (branch agent/air-m5/ops/e3-cards-work)
  - path: research/visa/doctrine-factory/cards/E28B.md (branch agent/air-m5/ops/e3-cards-work)
  - path: research/visa/doctrine-factory/cards/E28C.md (branch agent/air-m5/ops/e3-cards-work)
  - path: research/visa/doctrine-factory/cards/E28D.md (branch agent/air-m5/ops/e3-cards-work)
  - path: research/visa/doctrine-factory/cards/E28F.md (branch agent/air-m5/ops/e3-cards-work)
  - path: research/visa/doctrine-factory/cards/E30E.md (branch agent/air-m5/ops/e3-cards-stay)
  - path: research/visa/doctrine-factory/cards/E30F.md (branch agent/air-m5/ops/e3-cards-stay)
  - path: research/visa/doctrine-factory/cards/E33A.md (branch agent/air-m5/ops/e3-cards-stay)
  - path: research/visa/doctrine-factory/cards/E33B.md (branch agent/air-m5/ops/e3-cards-stay)
  - path: research/visa/doctrine-factory/cards/E33C.md (branch agent/air-m5/ops/e3-cards-stay)
  - path: research/visa/doctrine-factory/cards/E33E.md (branch agent/air-m5/ops/e3-cards-stay, engine-defect cross-verification)
  - path: research/visa/doctrine-factory/cards/E33G.md (branch agent/air-m5/ops/e3-cards-stay, engine-defect cross-verification)
  - path: research/visa/doctrine-factory/query-bank/fused-bank.jsonl
  - path: research/visa/doctrine-factory/query-bank/coverage-matrix-after-batch1.json
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
  - path: research/visa/doctrine-factory/claims/e2b-batch2-claim-ledger.md
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
adversarial_review: kimi-k3-real-run-see-section-below
---

# OD-4 Decision Package — the 11 BLOCKED products at the E3 gate

Pure synthesis. Every row below cites the doctrine card it comes from; nothing here is a new claim,
a new NB-2 query, or an upgrade of any card's own GAP/UNVERIFIED/CONFLICTING label. Where a card
proposes a disposition, it is reproduced as a **proposal** — Zero rules at the E3 gate, not this
package.

## 1. What OD-4 decides

1. **Per-product disposition of the 11 BLOCKED products**: for each, whether it gets tagged
   `OUT_OF_COMMERCIAL_SCOPE` (permanently deprioritized — no further doctrine/rule work) or kept in
   the active backlog (`AWAITING_...` states below) for a future E4/E5 pass.
2. **Disposition is orthogonal to epistemic state.** A product can have rich, VERIFIED doctrine and
   still be BLOCKED by rule-engine design (E28B/C/D/F — plausibly an intentional always-`HUMAN_REVIEW`
   gate per every card's own hedged framing, not asserted as settled fact — never a doctrine gap); or
   it can have zero PRODUCT-SPECIFIC doctrine and zero rules of ANY kind, including no `HUMAN_REVIEW`
   (E23U/E23V — a genuine `TOTAL GAP`); or zero product-specific doctrine but ONE always-firing
   `HUMAN_REVIEW` rule, same structural shape as E28B-F (E33A/B/C — `TOTAL GAP` on doctrine content, not
   on rules). OD-4 does not conflate "how much do we know" with "should this be commercially retired" —
   every card in this bulk states this instruction explicitly and applies it (each card's own §7/§5
   "Disposition" section).
3. **Nothing here is self-executing.** Every card's proposal is a recommendation for Zero's ruling at
   the E3 gate; none of the 11 cards claims authority to close its own disposition.

## 2. Decision table

Legend — **epistemic state**: `TOTAL GAP` (zero product-specific claims — E23U/V additionally have zero
product rules of any kind; E33A/B/C have exactly one `HUMAN_REVIEW`-only rule, same shape as the
RULE-DESIGN BLOCKED row below, but their doctrine content is the gap) · `RULE-DESIGN BLOCKED`
(real claim-backed doctrine exists; blocked because the only product rule is an always-firing
`HUMAN_REVIEW`, by apparent design) · `AWAITING RULE-AUTHORING` (real, mostly VERIFIED doctrine
exists; blocked only because no rule was ever authored) · `CONTESTED` (doctrine exists but is
`CONFLICTING` on a load-bearing point, not merely incomplete).

| Product | Epistemic state | Why blocked | Lane's proposed disposition | Cheapest unblock | Open conflict |
|---|---|---|---|---|---|
| **E23U** — Working Visa, Foreign Diplomat House Assistant | `TOTAL GAP` — all 17 doctrine fields GAP; 0 PRODUCTS-scope rules (only 6 GLOBAL) [`E23U.md` §3, §6] | No claim names E23U anywhere in any merged ledger; no rule of any kind can route a candidate to it [`E23U.md` §4, §6] | **NOT** `OUT_OF_COMMERCIAL_SCOPE` — targeted E4/E5 doctrine hunt, flagged PRIORITY per Zero's 2026-08-18 identity-priority instruction [`E23U.md` §7] | Run `VO-FUSED-T1-011` — already authored in `fused-bank.jsonl`, `state: PLANNED`, never dispatched [`E23U.md` §4, §8.1] | None (no claim exists to conflict with) |
| **E23V** — Working Visa, Trade and Economic Office | `TOTAL GAP` — same shape as E23U [`E23V.md` §3, §6] | Same: no claim, no product rule [`E23V.md` §4, §6] | **NOT** `OUT_OF_COMMERCIAL_SCOPE` — case for a real hunt is arguably stronger than E23U's, since a trade-office role could plausibly intersect the client base [`E23V.md` §7] | Run `VO-FUSED-T1-012` — already authored, `state: PLANNED`, never dispatched [`E23V.md` §4, §8.1] | None |
| **E28B** — Investor Golden Visa, Company Establishment | `RULE-DESIGN BLOCKED` — 6/7 claims in the digest VERIFIED or VERIFIED-WITH-CAVEAT (`CL-CROSS-06` is the sole UNVERIFIED — the cross-cutting calling-visa claim shared by every product in this bulk); USD 2.5M/5M thresholds and Rp 10bn existing-PT-PMA route both VERIFIED [`E28B.md` §3, `claims_digest`] | Exactly one PRODUCTS-scope rule, `review.e28b.usd-threshold-manual`, `HUMAN_REVIEW`, fires unconditionally for every E28B/INVESTMENT candidate; no ELIGIBILITY/SUPPORT rule exists at all [`E28B.md` §6] | **NOT** `OUT_OF_COMMERCIAL_SCOPE` — recommend the always-REVIEW design is treated as **intentional and retained** (high-value/high-fraud-risk threshold verification is not the kind of fact an automated evaluator should self-certify) [`E28B.md` §7] | Not a doctrine gap — no query needed to unblock reachability (the REVIEW gate is retained by design). Content-hygiene items only: resolve the E28A/B Rp 10bn overlap and the 3-vs-5yr KITAP-conversion figure [`E28B.md` §8.1-2] | Two unescalated internal ambiguities (E28A/B threshold overlap; 3-vs-5yr KITAP figure) — not numbered CF, self-flagged only [`E28B.md` §5] |
| **E28C** — Investor Golden Visa, Capital Market | `RULE-DESIGN BLOCKED` — same shape as E28B (USD 350k/700k thresholds, VERIFIED) [`E28C.md` §3] | Same always-firing single `HUMAN_REVIEW` rule pattern [`E28C.md` §6] | **NOT** `OUT_OF_COMMERCIAL_SCOPE`, retain REVIEW-by-design — additional flag: verify the USD 350k/700k figures were actually corrected against a document that names E28C (the correcting errata is E28B-titled) before any client-facing content ships [`E28C.md` §7] | Not a doctrine gap. Content-hygiene: confirm the errata-document provenance names E28C, not just E28B [`E28C.md` §5, §7] | Two unescalated internal ambiguities (shared 3-vs-5yr KITAP figure; errata-document naming discrepancy) — not numbered CF [`E28C.md` §5] |
| **E28D** — Investor Golden Visa, Branch or Subsidiary | `CONTESTED` — category itself is `CONFLICTING` (`CL-E28D-02`), not merely incomplete [`E28D.md` §3, §7] | Same always-firing single `HUMAN_REVIEW` rule pattern as E28B/C — the rule engine is unaffected by which category reading governs [`E28D.md` §6] | **NOT** `OUT_OF_COMMERCIAL_SCOPE`, retain REVIEW-by-design — but flagged **HIGHER PRIORITY than E28B/C/F** for a pre-publication content-accuracy check: content must disclose BOTH readings and that CF-13 is open, never silently pick a side [`E28D.md` §7] | Not a doctrine gap for reachability. Priority unblock is the CF-13 downstream-consumer audit (§8.1: which live surface, if any, actually reads `nb2_visa_types_final.txt`'s E28D row) — not yet done, scope stated as outside this batch [`E28D.md` §8.1] | **CF-13, OPEN.** Primary law (T0/T1: branch/subsidiary director) vs. internal production DB `nb2_visa_types_final.txt` (T2/T3: reads as a bonds-investor index). Risk is conditional — real only if an unaudited live surface consumes that DB row [`E28D.md` §5] |
| **E28F** — Investor Golden Visa, New Capital (IKN) Subsidiary | `CONTESTED` — thinner doctrine than E28B/C/D: category `CONFLICTING` (`CL-E28F-02`) AND stay-duration/threshold `UNVERIFIED`/GAP [`E28F.md` §3, §7] | Same always-firing single `HUMAN_REVIEW` rule pattern [`E28F.md` §6] | **NOT** `OUT_OF_COMMERCIAL_SCOPE` — flagged as the **single highest-priority content-accuracy item in the entire 8-product WORK/INVEST bulk**, per CF-14's own "higher client-risk" language [`E28F.md` §7] | Not a doctrine gap for reachability. Priority unblock is the CF-14 downstream-consumer audit, same class as E28D's; a dedicated query would also resolve the still-open stay-duration/threshold gap [`E28F.md` §5, §8] | **CF-14, OPEN — explicitly higher client-risk than CF-13.** Primary law (T0/T1: IKN branch/subsidiary director) vs. internal DB (T2/T3: "Bali real-estate investor" — Rp 5bn+ figure, disputed reading) — if any live surface reads the internal-DB category, it actively misdescribes a Bali-relevant product using Bali Zero's own data [`E28F.md` §5] |
| **E30E** — Student KITAS, Special Economic Zone (KEK) Institution | `AWAITING RULE-AUTHORING` — the richest doctrine of any BLOCKED product in this bulk: 5/5 claims VERIFIED or self-flagged CONFLICTING, covering category, activities, entry/duration, extension, sponsor [`E30E.md` §3] | **Zero PRODUCTS-scope rules of any kind** — not even a `HUMAN_REVIEW` rule exists; stronger BLOCKED than E28B-F (cannot even route to review today) [`E30E.md` §2, §4] | **PROPOSED: keep BLOCKED**, log `AWAITING_RULE_AUTHORING_ONLY` (inverse of E33A/B/C's doctrine-and-rule gap) — identity already resolved, doctrine already sufficient [`E30E.md` §5] | No new NB-2 query needed — pure rule-authoring gap. Author ELIGIBILITY to SUPPORT the KITAS itself; route any KITAP-conversion question to HUMAN_REVIEW, never direct SUPPORT, to avoid re-encoding CF-15 [`E30E.md` §5.1-2] | **CF-15, OPEN.** Operational material advertises a direct student→KITAP "Path to KITAP" that primary law (`UU 6/2011`, `PP 31/2013`) does not support without an intervening `Alih Status`; flagged as a pattern that may recur across the E30 family [`E30E.md` §3.4] |
| **E30F** — Student KITAS, Bilateral Student Exchange | `AWAITING RULE-AUTHORING` — same shape as E30E: 5/5 claims VERIFIED or VERIFIED-WITH-CAVEAT [`E30F.md` §3] | Zero PRODUCTS-scope rules, identical structural cause to E30E [`E30F.md` §2, §4] | **PROPOSED: keep BLOCKED**, `AWAITING_RULE_AUTHORING_ONLY` — recommend a **single combined E30E/E30F rule-authoring pass** since both share the identical CF-15 issue and starting state [`E30F.md` §5] | No new query strictly required to unblock; two narrow follow-ups (entry-mechanics asymmetry, sponsor citation) worth doing first but not blockers to a first-pass rule on the uncontested facts [`E30F.md` §5.3] | CF-15's pattern extends here, surfaced less explicitly than in E30E's own answer; also carries a weak cross-family citation for the KITAP-conversion figure, unexplained relevance [`E30F.md` §3.4] |
| **E33A** — Second Home Visa, Special-Expertise Government Invitation | `TOTAL GAP` on product-specific doctrine — only a family-level claim (`CL-E33-01`) names E33A at all; no eligibility-gate content [`E33A.md` §3] | One PRODUCTS-scope rule, `review.e33a.central-government-invitation`, `HUMAN_REVIEW`-only; zero ELIGIBILITY rule — the pack cannot mark this SUPPORTED even with perfect doctrine, without an accompanying E5 rule change [`E33A.md` §2, §4] | **PROPOSED: keep BLOCKED**, `AWAITING_DOCTRINE_AND_RULE_AUTHORING` (not doctrine-only) [`E33A.md` §5] | One narrow, dedicated NB-2 query on "central government invitation" (issuing body, document type, validity, deposit/property basis if any) — not yet run [`E33A.md` §5, §6.1] | No numbered CF. A **naming-collision worth flagging, not re-litigated as a CF**: one NB-2 answer informally calls "E33A" the "Second Home via Property" route — a different product from the live pack's actual E33A (government-invitation, `EMPLOYMENT/TOURISM/FAMILY`); this card explicitly warns future authors not to import those facts here [`E33A.md` §3] |
| **E33B** — Second Home Golden Visa, Special-Expertise Collaboration | `TOTAL GAP` — the **least-documented of the three**: does not even appear in `CL-E33-01`'s own family enumeration [`E33B.md` §3] | One PRODUCTS-scope rule, `review.e33b.expertise-qualification`, `HUMAN_REVIEW`-only; zero ELIGIBILITY rule [`E33B.md` §4] | **PROPOSED: keep BLOCKED**, `AWAITING_DOCTRINE_AND_RULE_AUTHORING`, **HIGHER research priority than E33A/C** given the near-total absence of content [`E33B.md` §5] | **Highest-priority dedicated query of the three** — E33B's `covered_purposes` includes `INVESTMENT`, suggesting an undiscovered financial-threshold rule may be needed in addition to the qualification check [`E33B.md` §5] | None numbered; no naming-collision finding surfaced for E33B specifically — the card is explicit this is absence-of-evidence, not evidence of a clean label [`E33B.md` §3] |
| **E33C** — Second Home Golden Visa, World-Figure Government Invitation | `TOTAL GAP` — same absence from `CL-E33-01`'s enumeration as E33B [`E33C.md` §3] | One PRODUCTS-scope rule, `review.e33c.central-government-invitation` — same `reason_code` (`GOVT_INVITATION_REQUIRED`) as E33A's rule, `HUMAN_REVIEW`-only; zero ELIGIBILITY rule [`E33C.md` §2, §4] | **PROPOSED: keep BLOCKED**, `AWAITING_DOCTRINE_AND_RULE_AUTHORING`, same tier as E33B [`E33C.md` §5] | Recommend **batching E33B+E33C into the same query round as E33A** — structurally identical in the pack, likely share one primary-law source (`Kepmen M.IP-08.GR.01.01/2025`'s Second Home Golden Visa provisions); one well-targeted query could resolve all three [`E33C.md` §5] | None numbered. A structural observation only (not a sourced claim): E33A and E33C share the identical review mechanism/`reason_code` applied to two different applicant categories — no source confirms this is doctrinally correct, just what the pack's own JSON does [`E33C.md` §3] |

## 3. Red flags for the owner

- **E28F / CF-14 — highest client risk in this bulk.** If any live quoting/onboarding surface for E28F
  reads its category from Bali Zero's own internal production DB rather than the primary law, it is
  currently telling applicants E28F is a **"Bali real-estate investor visa" (Rp 5bn+)** — exactly the
  question a Bali-based client is likely to ask — when the primary-law reading is an **IKN
  branch/subsidiary director** index, a structurally different product for a different purpose. Neither
  reading has been confirmed as the one actually driving client-facing content; the audit of which
  surface(s) consume `nb2_visa_types_final.txt`'s E28F row has not been done. [`E28F.md` §5, §7]
- **E28D / CF-13 — same defect class, one tier lower risk.** Primary law reads E28D as a branch/
  subsidiary director index; the internal DB reads it as a bonds-investor product. The lane's own risk
  ranking treats this as real but structurally less likely to surface walk-in, given Bali Zero's actual
  client mix skews property/visa over international bonds — still unresolved, still worth a downstream-
  consumer audit before any E28D content ships without the open-conflict caveat. [`E28D.md` §5, §7]
- **The internal E33E guide still saying 60 instead of 55 is a live operational risk, not a repo
  defect.** `CF-7`'s legal component is RESOLVED at **55** years (`Permenkumham No. 11 Tahun 2024`,
  `Kepmen M.IP-08.GR.01.01/2025`'s classification annex, in force 1 June 2025 — independent articles,
  all agree). What is explicitly NOT resolved is whether **Kantor Imigrasi Ngurah Rai's actual
  real-world counter practice** still applies the older 60-year figure — a legal-text-vs-live-
  enforcement gap the pack's own `el.e33e.age-55-59-disputed-band` rule mitigates mechanically (routes
  55-59 applicants to an advisor check) but which no claim resolves. This is a **business/operator
  fix** — an in-person field-check at the Ngurah Rai counter — not something an E4/E5 doctrine or rule
  pass can close from inside the repo. [`E33E.md` §3.2-3.3, §5-6, cross-verified via
  `.worktrees/ops-e3-cards-stay/research/visa/doctrine-factory/cards/E33E.md`]

## 4. Engine defects feeding the seq-9 signing gate

Two confirmed rule-engine defects were found by the E5-adjacent lane's adversarial review of the
REACHABLE E33-family cards (not part of this bulk's 11 BLOCKED products, but load-bearing context for
whoever signs off seq-9 and should not be re-discovered independently). **Not fixed here** — this
package only reports them, per the mandate's explicit scope.

1. **`el.e33e.deposit-income-basis` is logically unsatisfiable — never fires for any input.** The
   rule's outer `all()` requires BOTH (a) an inner `any()` XOR-shaped branch demanding exactly one of
   {deposit-met, income-met}, AND (b) a second branch demanding both deposit-met AND income-met
   simultaneously — mutually exclusive by construction. The pack's rule inventory still lists it as
   "SUPPORTED" in the sense that it exists and targets E33E, but no applicant fact pattern can ever
   satisfy it. An earlier draft of `E33E.md` described this rule as a working advisor-check without
   disclosing the defect; corrected on the same card after the defect was found live this session.
   [`E33E.md` §3.8, §4, §6]
2. **`el.e33g.income-60k-manual` never tests any income fact — the USD 60,000 threshold is
   doctrine-only, not runtime-enforced.** The rule's `when` clause is a byte-for-byte duplicate of
   `el.e33g.remote-work`'s condition; it fires for any clean remote worker regardless of income, and
   the figure `60000` does not appear anywhere in either `rulepack-prod-007.source.json` or the
   sibling `rulepack-prod-008.source.json`. An earlier draft of `E33G.md` described this rule as a
   working USD-60k advisor-check without disclosing that the figure is unenforced; corrected on the
   same card. [`E33G.md` §3.2, §4, §6]

Both defects were found by the same-session adversarial-review pass on the REACHABLE E33-family cards
(`.worktrees/ops-e3-cards-stay/research/visa/doctrine-factory/cards/E33E.md` and `E33G.md`), and are
cross-verified live against the pack JSON in that pass — not asserted from memory. Recommend routing
both to an E5 rule-authoring fix before the seq-9 signing gate treats either rule as functioning:
`el.e33e.deposit-income-basis`'s XOR/conjunction conflict reads as a copy-paste template error, not an
intentional design; `el.e33g.income-60k-manual` needs an actual income-fact predicate added.

## 5. Recommended rulings (PROPOSALS — Zero rules)

The 11 cards' consolidated recommendation, reproduced here as a single cross-product summary. Every
item below is a proposal from the lane, not a ruling — Zero decides at the E3 gate.

1. **No product in this bulk gets `OUT_OF_COMMERCIAL_SCOPE`.** E23U and E23V argue against the label
   explicitly, by name, with the rationale spelled out: `OUT_OF_COMMERCIAL_SCOPE` is meant for products
   the sources themselves attest zero relevance for, and their `TOTAL GAP` traces to an **unrun query**
   (already authored, never dispatched), not a confirmed absence of legal basis or commercial fit
   [`E23U.md` §7, `E23V.md` §7]. E33A/B/C do not invoke the label or that rationale by name — each simply
   proposes **keep BLOCKED**, `AWAITING_DOCTRINE_AND_RULE_AUTHORING`, which is the same practical outcome
   (stay in the active backlog, not retired) reached by a narrower route: a dedicated NB-2 query plus an
   ELIGIBILITY rule are both still needed regardless of scope questions [`E33A.md` §5, `E33B.md` §5,
   `E33C.md` §5].
2. **E28B/C/D/F keep their always-`HUMAN_REVIEW` design, by intention, not by neglect.** All four cards
   independently recommend retaining the single always-firing REVIEW rule as a deliberate high-value/
   high-fraud-risk safety gate, not a gap to close with an automated SUPPORT path — absent an explicit
   business decision that automated Golden-Visa-threshold self-certification is acceptable risk
   [`E28B.md` §7, `E28C.md` §7, `E28D.md` §7, `E28F.md` §7].
3. **E23U/V and E33A/B/C get their dedicated queries dispatched — E33B/C highest priority.**
   E23U (`VO-FUSED-T1-011`) and E23V (`VO-FUSED-T1-012`) already have authored, `PLANNED`,
   never-dispatched queries — the cheapest possible unblock in this entire bulk (1 query each, already
   written). E33A/B/C need new dedicated queries — none exist yet. E33B is flagged the least-documented
   **of the three** BLOCKED Golden-Visa-tier products (absent even from the family-level claim
   enumeration `CL-E33-01`, unlike E33A) and E33C can likely be batched with E33A/B under one shared
   Kepmen-source query [`E23U.md` §8.1, `E23V.md` §8.1, `E33A.md` §5, `E33B.md` §5, `E33C.md` §5].
4. **E30E/F need rule-authoring only, no new doctrine query.** Both already carry 5/5 claims — E30E's
   set is VERIFIED plus one self-flagged CONFLICTING (CF-15, the student→KITAP conversion gap); E30F's
   is VERIFIED or VERIFIED-WITH-CAVEAT — the richest doctrine of any BLOCKED product in this bulk either
   way. The single blocker is that no rule-authoring pass has ever encoded that doctrine into the pack.
   Recommend a combined E30E+E30F pass, both routing any KITAP-conversion question to `HUMAN_REVIEW`
   (never a direct SUPPORT) to avoid re-encoding CF-15's law-vs-practice gap into the rule engine
   [`E30E.md` §3.4, §5, `E30F.md` §3.4, §5].
5. **E28D and E28F content needs the open-conflict caveat before shipping, regardless of query
   priority.** Neither CF-13 nor CF-14 blocks the REVIEW-gate mechanism (§6 of each card is unaffected
   either way) — the risk is entirely in client-facing/operator-facing content silently picking a side.
   Both cards recommend the content itself state both readings and name the conflict as open, not defer
   to whichever source the author happens to read first [`E28D.md` §7, `E28F.md` §7].

## Adversarial review

Real Kimi K3 refutation run against this finished document (generator≠grader) — the full decision
package minus its own not-yet-written Adversarial review section, plus condensed identity+disposition
excerpts from all 11 source cards (the cards' own claims were already independently adversarially
reviewed twice each, documented in their own `## Adversarial review` sections, and are not re-litigated
here). Invocation: `kimi -p "<refutation prompt: verify every table row and every claim in §3-5 against
the cited excerpts, flag any upgraded epistemic label, any disposition presented as more settled than
the source card's own PROPOSED framing, any missing CF/engine-defect, any table cell not traceable>"
-m kimi-code/k3`, run inside an 8-minute (480s) Bash `timeout` parameter (macOS has no `timeout`
binary). **The run completed inside the timebox** (unlike the source cards' own Kimi passes on a
heavier 8-card joint prompt, which both timed out).

Seven items were raised. Disposition below reflects what was actually checked against the full source
cards (not just the condensed excerpts Kimi saw) before curing or declining to cure:

1. **[P2, CONFIRMED, cured]** §5 item 3 originally called E33B "the single most under-documented product
   in the bulk" — an upgrade beyond what `E33B.md` §5 actually says ("the least-documented **of the
   three**" Golden-Visa government-invitation products). E23U/E23V are equally zero-claim `TOTAL GAP`s,
   so the bulk-wide superlative was unsupported. Cured: reworded to match the card's own scoped claim.
2. **[P2, CONFIRMED, cured]** The legend's `TOTAL GAP` definition ("zero claims, zero product rules")
   and §1.2's phrasing ("zero doctrine and zero rules at all — E23U/E23V, E33B/C") contradicted the
   table's own E33A/B/C rows, each of which records exactly one PRODUCTS-scope `HUMAN_REVIEW` rule
   (`E33A.md` §4, `E33B.md` §4, `E33C.md` §4) — and E33A additionally carries a family-level claim
   (`CL-E33-01`). §1.2 also omitted E33A from its TOTAL GAP list while the table labels E33A `TOTAL GAP`
   on doctrine content. Cured: legend and §1.2 rewritten to distinguish E23U/V's "zero rules of any kind"
   from E33A/B/C's "zero product-specific doctrine, but one always-firing `HUMAN_REVIEW` rule exists" —
   both real, but structurally different `TOTAL GAP` shapes.
3. **[P3, CONFIRMED — but the underlying claim states check out, only the prose was wrong]** §5 item 4
   originally stated both E30E and E30F carry "5/5 claims at VERIFIED or VERIFIED-WITH-CAVEAT." The
   table's own E30E row (line 69) already correctly said "VERIFIED or self-flagged CONFLICTING" — E30E's
   `CL-E30E-04` is explicitly CONFLICTING per CF-15 (`E30E.md` §3.4), not VERIFIED-WITH-CAVEAT. Only §5
   item 4's summary prose was wrong, contradicting the table two sections above it. Cured: §5 item 4
   reworded to state each product's actual claim-state mix.
4. **[P3, PLAUSIBLE]** §1.2's original text asserted the E28B-F always-`HUMAN_REVIEW` design as settled
   fact ("an intentional...gate"), while every E28 card hedges it as "plausibly a DELIBERATE safety
   design" (`E28B.md` §7 et al.) — never confirmed by any claim. Cured: §1.2 now carries the same hedge.
5. **[P3, PLAUSIBLE]** §5 item 1 originally attributed the "argue against `OUT_OF_COMMERCIAL_SCOPE`,
   because the gap is an unrun query not a confirmed absence" rationale to all five cards (E23U/V,
   E33A/B/C) as if stated "explicitly" in each. Re-checked directly: only E23U/E23V §7 name the label
   and that rationale; E33A/B/C's §5 sections simply propose keep-BLOCKED/`AWAITING_DOCTRINE_AND_RULE_
   AUTHORING` without invoking the label or that specific reasoning. Cured: §5 item 1 now distinguishes
   the two groups' actual argument shapes.
6. **[P3, unverifiable given the condensed excerpts Kimi saw — not a defect]** Kimi flagged that §3's
   E33E/CF-7 red flag and §4's two engine-defect citations rest entirely on `E33E.md`/`E33G.md`, which
   were not in its condensed excerpt set, so it could not itself check the "55 vs 60," `el.e33e.deposit-
   income-basis` XOR-unsatisfiable, or `el.e33g.income-60k-manual` figures. Both are real: independently
   re-read in full from `.worktrees/ops-e3-cards-stay/research/visa/doctrine-factory/cards/E33E.md` and
   `E33G.md` this session (§3.2-3.3/§4/§6 and §3.2/§4/§6 respectively) before those sections of this
   package were first drafted — this is a scope limitation of what was fed to the refuter, not an error
   in the document.
7. **[Not contested]** The CF-13/CF-14/CF-15 risk framing, the E28D/E28F "both readings, conflict open"
   caveat language, the withdrawn E33A "operationally-tested" referral, and every dedicated-query /
   rule-authoring recommendation in the table and §5 were checked against their cited card sections and
   found accurate.

Net: 5 real findings (2 CONFIRMED upgrades, 1 CONFIRMED internal contradiction, 2 PLAUSIBLE
over-statements), all 5 cured; 1 scope-limitation note requiring no change; 0 fabricated CF numbers or
figures found.
