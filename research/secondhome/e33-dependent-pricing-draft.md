---
date: 2026-07-23
domain: marketing
adversarial_review: gemini
status: DRAFT — decision-ready proposal, NOT client-facing, NOT live pricing
author: Kimi (docs-e33-dependent-pricing lane)
governing_decisions:
  - "Base E33 = IDR 39,000,000 all-inclusive (owner, 2026-07-23) — never decompose client-facing"
  - "Dependent pricing working model = flat add-on per person (owner, 2026-07-23)"
  - "StayGuard launches only after the Day-90 compliance tracker exists (owner, 2026-07-23)"
pending_gates:
  - "Dependent codes E31B/E31E/E31H/E31J — pending written Immigration confirmation (Letter 006 Q6)"
  - "Government PNBP figures — internal reference only, pending authority confirmation"
  - "No price goes live without PricingTool + explicit owner sign-off"
---

# E33 Second Home — Dependent (Family) Pricing Draft

Proposal for Zero. Nothing here is client-facing or authorized. All numbers
require PricingTool + owner sign-off before any client use.

## 1. Recommendation: flat add-on IDR 12,000,000 per dependent

One flat add-on per accompanying family member (spouse, child, parent,
sibling — codes E31B/E31E/E31H/E31J, pending confirmation), sold only
alongside a main E33 file. One price for every dependent type — the
"dependent = dependent" simplicity matches the all-inclusive E33 doctrine.

Anchoring logic:
- Existing Bali Zero catalog: standalone Dependent KITAS 2y = IDR 18M onshore /
  IDR 15M offshore. The E33 add-on sits **below** standalone (IDR 12M) because
  it rides the main file — shared dossier, shared bank proof, one coordinated
  submission — while staying premium vs. local filing agents.
- International comparable: Portugal GV charges ~€1–3k per dependent vs ~€8k
  base advisory (12–37%). IDR 12M is ~31% of the IDR 39M main fee — in band.
- Competitor check: Flado prices family E31 at IDR 30M vs E33 35M (nearly
  equal) — a filing-SKU pattern. Bali Zero does not follow it; the premium
  position is the managed main file, with dependents as a true add-on.

### Priced scenarios (all-inclusive totals, client-facing shape)

| Scenario | Composition | Total (IDR) |
|---|---|---|
| Main + spouse | 39M + 1 × 12M | **51,000,000** |
| Main + spouse + 2 children | 39M + 3 × 12M | **75,000,000** |
| Full family (main + spouse + 2 children + 2 parents) | 39M + 5 × 12M | **99,000,000** |

No volume discount recommended at launch — first cohort is price discovery;
revisit after observed conversions.

### Margin math — ⚠️ INTERNAL ONLY, never client-facing

Internal reference (pending authority confirmation): PNBP per dependent
(E31B/E31E/E31H/E31J, 2y) ≈ IDR 5,500,000 (visa Rp 500,000 + ITAS 2y
Rp 5,000,000 per PP 45/2024 cross-ref).

| Item | IDR |
|---|---|
| Add-on price per dependent | 12,000,000 |
| PNBP per dependent (internal ref) | −5,500,000 |
| **Gross margin per dependent** | **6,500,000 (~54%)** |

Sensitivity: if Immigration confirms dependents get a 5-year ITAS aligned to
the main E33 grant (not the 2y taxonomy line), PNBP rises to ~IDR 7,500,000
(ITAS 5y Rp 7,000,000 + visa Rp 500,000) → margin ~IDR 4,500,000 (~37%).
The IDR 12M add-on still holds; below 12M it does not. Do not go lower.

## 2. Rules of the add-on

- Dependents are **always processed alongside the main E33 file** — one
  coordinated family submission. No standalone E33-dependent sales; no
  dependent files opened without an active main E33 engagement.
- The add-on **includes**: dependent document preparation, filing,
  submission coordination with the main file, appointment/biometrics
  scheduling, and status tracking to ITAS issuance.
- The add-on **excludes**: the qualifying deposit/financial proof (carried
  by the main applicant — dependent adds no deposit), document
  legalization/apostille/translation costs (at cost, passed through),
  travel and personal expenses, and any government verification surcharge
  not yet confirmed in writing (surfaced to the client if it materializes).
- Late joiners (family member added after the main file is submitted) are
  quoted at the standalone Dependent rate from the official catalog, not the
  add-on rate — the add-on price exists because of the shared file.

## 3. StayGuard bundling option (structure only — no price yet)

Consistent with the owner's decisions: StayGuard is offered to E33 clients
**only after the Day-90 compliance tracker exists**, so it is deliverable
from day one. Proposed family structure (pricing deferred to the StayGuard
launch decision):

- StayGuard base retainer covers the main applicant.
- **Family coverage option**: one retainer covering the whole family file
  (main + all dependents), priced as base + modest per-dependent uplift
  (suggested +20–25% per dependent, capped at +50% total) — one compliance
  calendar, one evidence log per family.
- Dependents are never sold StayGuard separately from the main holder.

## 4. Pending gates (explicit)

1. **Dependent codes confirmation** — E31B/E31E/E31H/E31J (which family
   relation maps to which code, and 2y vs 5y ITAS duration) are pending
   written Immigration confirmation via Letter 006 Q6. No dependent offer is
   published before that reply.
2. **PNBP figures** — the dependent PNBP (IDR 5.5M) and the main E33 5y PNBP
   (IDR 13M) are internal references pending authority confirmation; never
   shown to clients in any form.
3. **Pricing go-live** — all figures in this document are proposals. They go
   live only after routing through PricingTool and explicit owner sign-off,
   and only then are added to the official price catalog.

## 5. Client-facing copy block (ready after gates 1–3 clear)

> Bring your family under one application. Each accompanying family member —
> spouse, children, or parents — is added to your Second Home file for a
> single all-inclusive fee of IDR 12,000,000 per person, processed together
> with your own application. One coordinated submission, one timeline, one
> point of contact for the whole family.

## Adversarial review

Reviewed 2026-07-24 by seats != author (author: kimi) on the full branch diff:
**gemini** (verdict MERGE — margin math and pending gates acknowledged) and
**glm-5.2** (no FIX-FIRST). Open items remain owner-side by design: confirm
the IDR 12M figure and the no-volume-discount stance, then route through
PricingTool before go-live. Review artifacts: PR #3045 comments +
`/tmp/secondhome_review/pr_review_gemini.md`, `pr_review_glm.md`.
