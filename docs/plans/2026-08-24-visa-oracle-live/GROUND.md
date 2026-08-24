# GROUND — Visa Oracle live, measured 2026-08-24 (Pro, orchestrator session)

Every number here was produced by a command run on this machine on this date. Nothing is
inherited from the mandate's prose, a memory, or a fleet message. Where a circulating claim
turned out to be false, it is recorded as false, with what the measurement actually said.

Base: `origin/main` @ `04a29fe13`. Integration branch `feature/visa-oracle` cut from it.

## 1. The engine, against the pack that is actually signed

Command: `reachability_report.py --pack <payload of rulepack-prod-013.signed.json>`

| Measure                            | Value                                                                   |
| ---------------------------------- | ----------------------------------------------------------------------- |
| Products in pack                   | **38**                                                                  |
| Rules in pack                      | **111**                                                                 |
| Pack version / environment         | `2026.8.23` / `PRODUCTION`, uuid `79b62b85-829e-59f8-a058-c38c065b8cb5` |
| Reachable (has >=1 SUPPORT rule)   | **29**                                                                  |
| Blocked (zero SUPPORT rules)       | **9** — E23U, E23V, E28B, E28C, E28D, E28F, E33A, E33B, E33C            |
| FactPaths referenced by >=1 rule   | **37 / 49**                                                             |
| FactPaths referenced by zero rules | **12**                                                                  |
| Orphan rules                       | **none**                                                                |

**TOOL TRAP, recorded so the next session does not pay for it.** `reachability_report.py --pack`
expects the _source_ shape. Pointed at `rulepack-prod-013.signed.json` it emits a long cascade of
Pydantic `Field required` / `Extra inputs are not permitted` errors that reads exactly like a
corrupt pack. The pack is sound; the signing envelope wraps it. Unwrap `json["payload"]` first.

## 2. The five facts the interview never asks

Hard-coded `unknownFact(NOT_ASKED)` in `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts`,
regardless of what the applicant answers:

- `commercial.service_fee_budget_idr`
- `commercial.wants_quote`
- `immigration.last_entry_date`
- `intent.desired_entry_date`
- `intent.requested_product_code`

Four of the five are also referenced by zero rules — consistent, an unasked fact cannot be
usefully gated on. The fifth, `intent.requested_product_code`, **is** referenced, and that is the
disease: it is the sole condition of the one `REQUIRE_REVIEW` rule on each of E28B/C/D/F. With
`on_unknown=NEEDS_INPUT` the product's proof becomes `BLOCKED_UNKNOWN`, which loses to any
SUPPORTED product, so the four highest-value products in the catalogue are **invisible** — not
merely un-firing. A separate class of defect from "has no SUPPORT rule".

Eight facts run the other way — the interview collects them and this pack gates on none of them:
`derived.has_active_stay_permit`, `family.sponsor_permit_basis`,
`family.stepchild_birth_certificate_confirmed`, `family.stepchild_marriage_certificate_confirmed`,
`immigration.renewal_paid`, `person.birth_date`, `process.application_channel`,
`work.employer_country_code`.

## 3. The gold corpus is thinner than any headline suggests

- The 20-persona corpus positively supports **5 distinct codes**: C1, E23, E28A, E31, E33G.
- **`E31` does not exist in this pack** — it uses E31A..E31J. A dead assertion that never fails,
  because `test_evaluator_gold.py` deliberately drives a synthetic FIXTURE pack, not this one.
- **34 of 38 products are never any persona's `expected_candidates`.**

**Do not answer "how many visas are ready" with 29.** `reachable=bool(support)` is a static
existence check on a rule. The dynamic measurement — the gold replay against the real signed pack —
touched 6 of 38 products and matched 4 of 20 personas, with 16 divergences untriaged. Two different
numbers, routinely read as one.

## 4. GARUDA's commerce rails do not exist on main — V3's premise is false as written

The mandate's V3 lane says "consume GARUDA's FROZEN contracts from main". Measured:

- `apps/backend-rag/backend/services/garuda_flow/` contains: `constants`, `eligibility`, `intake`,
  `internal_preview_cli`, `nationality_eligibility`, `operating_calendar`, `pricing`, `repository`,
  `safe_clock`. **No order, no checkout, no commerce contract.**
- `apps/backend-rag/backend/app/routers/garuda_voa.py` exposes exactly one public route:
  `GET /voa/{hash}` — a read-only archive lookup.
- A repo-wide grep for an order/checkout/commerce contract returns three files, all unrelated
  (`llm_cost_recorder.py`, research-os `metric_result.py`, `story_cluster.py`).
- `https://balizero.com/visa/voa` -> **404**. The public VOA surface was withdrawn in PR #4344
  (2026-08-21); GARUDA today is an owner-only internal preview tool.

**Consequence, carried openly rather than papered over:** V3 cannot be built against rails that are
not there. Its consultant half (CRM assignment, ever-present control, WhatsApp continuity) is
independent of GARUDA and proceeds now; its checkout half becomes a _contract request_ to the
GARUDA orchestrator (fleet mailbox, per mandate §6) and a stub behind a flag on our side. This is a
sequencing fact, not a reason to stop: three of four lanes are unblocked.

## 5. The public surface is correctly in shadow

- `https://balizero.com/visa-oracle` -> **200**, and the served HTML carries
  `<meta name="robots" content="noindex, nofollow"/>`.
- Guarded by `layout.test.tsx` ("guilt: robots directive is present and blocks both index and follow").

**Method note.** The first probe read response _headers_ only, found no `x-robots-tag`, and would
have raised a false alarm about an unindexed-shadow violation. The directive is a meta tag. A
probe that looks in one of two possible places and reports absence has measured its own aim.

## 6. A circulating claim that is false

Fleet message S14/Mini (2026-08-23) reported: "the `tree.ts` of Visa Oracle v2 self-declares
`MOCK_CATALOG` and carries VOA=500.000 / C1=2.500.000 against PricingTool's 790.000 — must be
re-attached before production."

Measured on disk today: **already cured.** `_lib/tree.test.ts:13` asserts
`expect("MOCK_CATALOG" in treeRegistry).toBe(false)`. Not an open defect. Recorded because this is
the exact shape that bit three lanes on 2026-08-23 — a fact arriving beside a correct correction
borrows its credibility.

## 7. A claim that survives, and is ours

The **D-7 VOA extension deadline is not national.** Ngurah Rai publishes two incompatible
formulations on the same page (body: earliest D-14, no closing term; callout: D-16..D-7);
Yogyakarta publishes a third (latest = D-1 working day). A `D-7` constant written as a fleet-wide
fact is supported by none of the three pages. It is a per-kanim LEAD until verified per office.

## 8. In-flight work owned by another live session

PR **#4797** (`agent/air-m5/backend-rag/blocked5-eligibility-rules-0824`) carries the E23U/E23V
cure — the first two of the nine blocked products. Its lane is alive (last commit 12:00:14Z today).
State measured here: `autoMergeRequest.enabledAt = 2026-08-24T12:00:27Z`, `isInMergeQueue = false`,
`mergeQueueEntry = null` — i.e. **armed but not queued**, which per W111 means it enters only when
green, and it is not: 4 failing checks (R1 adversarial-review gate, Frontend Tests mouth,
Visa Oracle fullstack smoke, Test Summary) against 64 green.

Not touched. Handoff offered to that lane by fleet message; V1 plans around it rather than through it.

## 9. Tooling gap found while working, not closed here

`scripts/fleet_mail.sh` accepts only `local|pro|mini` and rejects `air` with "unknown host". The
fleet has been three nodes since 2026-05-31, so **no Pro or Mini session can reach M5 with the
fleet tool**. This session's handoff message was delivered by hand over ssh using the script's own
protocol, and verified landed. The fix is one line and belongs in its own PR, not in a product branch.
