---
date: 2026-07-23
domain: visa
client_case: none
author: Kimi (Air-M5) — wave-0 dispatch briefs for cross-machine tracks
adversarial_review: human-zero
status: DISPATCHED — Track B (Mini) and Track C (Pro) remain owned by their home machines
---

# Wave-0 dispatch briefs — Track B FASE 2 and Track C 4a

These briefs hand the panel's adjudicated requirements to the lanes this session cannot claim
(Track B claimed by Mini/2026-07-17; Track C claimed by Pro/2026-07-17, shipped but not
released). Everything below is already adjudicated by the 4-seat panel + Fable 5 final gate —
see `2026-07-23-architect-review-synthesis.md` (addendum).

## Adversarial review — panel and Fable 5 disposition

The briefs below incorporate the panel's adjudicated requirements and Fable 5 final gate.

## BRIEF 1 — Track B FASE 2 (Mini; continues MANDATO MINI-A2 of 2026-07-19)

The 7 behavioral interview trees, now gate-coupled: **ENFORCE = 110 signed codes AND
behavioral trees for every launched category** (Fable-delta-5). Authoring order (design-seat
UX ranking, confirmed):

1. **Tourism depth + the shared `nationality` question FIRST** — blocking: BVK is
   nationality-only per Permen Imipas 10/2026 (eff. 2026-07-09; 19 states/SARs + 1 entity);
   without nationality the highest-volume lane abstains systematically. Include the
   band→exact-days split (Codex P0#1).
2. Business · 3. Invest & golden (needs nationality in place for the calling-visa overlay) ·
4. Retirement (bundle `birth_date`, 55+) · 5. Family · 6. Diaspora · 7. Study.

Constraints from the panel (all binding):

- Registry is **38 FactPaths** (35 applicant + 3 derived), `FactPath → questionId |
  notCollected`; `commercial.*` = not-collected-by-design.
- Overstay/blacklist and clients/compensation questions must SPLIT (Codex P0#1) — transmit
  UNKNOWN until split, never representative values.
- Microcopy carrying legal weight (design-seat list): amount thresholds, the Rp1,000,000/day
  overstay figure (exact or omit), Bridging ≥3-day cutoff (Permenkumham 11/2024), W3
  calling-visa wording, chip copy "Supported path under current rules", NO PNBP/fee split
  (owner ruling R1, GLM §5–6 superseded).
- Regulatory anchors corrected by the panel: Kepmen M.IP-08.GR.01.01/2025 **effective
  2025-06-01** (dictum KELIMA); B211* death = dictum KEEMPAT; "Permenkumham 10/2026 Second
  Home" is REFUTED (notary PMPJ) — the parked round-4 recheck note must be corrected before
  re-landing. Second Home = SE IMI-0740.GR.01.01/2022 (+E28B/E33F).
- Category vocabulary ruling needed from W1 (10-tile→8-enum; business/diaspora home) —
  coordinate in LIVE STATE before freezing the trees' category keys.

## BRIEF 2 — Track C wave 4a (Pro; per design-seat wiring table + Fable errata)

Frontend skeleton, developable NOW against `contracts/contract.schema.json` fixtures (no
backend dependency): `fact-mapper.ts` (UNKNOWN, never representatives), `engine-client.ts`
(4s AbortController, single retry, runtime validation), `decision-adapter.ts` (invalid
payload → synthesized TEMPORARILY_UNAVAILABLE), async flow rework in `_lib/flow.ts`
(replacing the sync `useMemo(evaluate)`), `OracleShell`/`VerdictReveal`/`OutcomeSheet`
modifications + NEW `CitationChip`, `CitationList`, `NeedsInputPanel`, `NoticesStrip`.

Binding errata (Fable/design): NeedsInputPanel dispatches **insert-at-frontier**, NOT `EDIT`
(truncateToNode no-ops on absent nodes); the shared footer/disclaimer renders on **all five**
states (the W0b lane is shipping the guard fix now — rebase onto it); `mock-engine.ts` KEPT
verbatim (curated/rollback renderer); candidate display model is unpinned — flag in LIVE
STATE, it's a W1/P0-3 contract deliverable; `public_id` WhatsApp receipt (E-g) is
coordinated with the W1 endpoint.

Blocked staging: 4b (provenance components) waits for the W1 read-path API; 4c (e2e) waits
for the signed 30-code pack. Do not start 4b/4c early.
