---
date: 2026-06-10
domain: operations
client_case: none (internal — balizero.com frontend, Mythos Round 1, §11 study seeding Round 1B)
sources:
  - NB-4 Tax (d4b2eedb, 162 src) notebook_query 2026-06-10 — digest preserved verbatim below
  - NB-5 Property (d9438180, 143 src) notebook_query 2026-06-10 — digest preserved verbatim below
  - GSC 90d demand baseline (same branch, 2026-06-10)
  - Competitor tax/property sweep (11 pages fetched: cekindo.com, emerhub.com, letsmoveindonesia.com, lmiconsultancy.com, sevenstonesindonesia.com via proxy, balilegals.com, villabalisale.com, pkwalaw.com)
  - Exemplar study (same branch) for pattern cross-references
---

# MYTHOS · Tax + Property Channel Study (charter §11 — seeds Round 1B)

**Lane:** `research-only`. **Law-2 note:** built exclusively from curated NB ground truth + public behavioral data + competitor pages. No CRM, no client cases, no internal workflow data — per charter §11, with the known limitation on the record: the win/loss and sales-objection reality is invisible to this study (§5 below).

Both channels share one hard datum from Phase 0: **near-zero captured demand today** (Tax: `/services/tax` at GSC position 22.6, tool page 3 sessions/28d · Property: no property-intent query or page in GSC top-60, tool page 6 sessions/28d). **Round 1B design must start from demand creation, not funnel polish.** Charter §2's per-channel metric (booked consultation) depends on the `/book` rail proposed in the Stage-A pack (IA-3).

---

## 1. TAX channel

### 1a. The service shape (NB-4 ground truth)

The domain is a **calendar + risk** domain. The client's lived reality:

- **The calendar** (PMK 81/2024 CoreTax framework): monthly withholding + PPh 25 installments **paid by the 15th**, SPT Masa **filed by the 20th**, PPN (if PKP) paid+filed **end of following month**; SPT Tahunan Badan **April 30**; personal SPT **March 31** (SPDN) — with the 2025-tax-year transitional relaxation to April 30, 2026 (KEP-55/PJ/2026). SPLN individuals: no annual filing, final 20% PPh 26.
- **The thresholds:** PKP at IDR 4.8B turnover; 183-day/KITAS residency rule; 22% PPh badan; 5–35% personal brackets; PPN 11% effective / 12% headline (PMK 131/2024); UMKM 0.5% final — capped at 3 years for PT PMA.
- **The 7 pain points** (each one is a content/service hook): SPDN-vs-SPLN misclassification (audit trigger) · worldwide-income surprise (+ the 4-year skilled-foreigner exemption vs DTA trade-off) · the CoreTax "pre-populated liability trap" (CRM algorithm cross-references e-Faktur in real time — zero-reporting is instantly visible) · treaty abuse post-PMK 112/2025 (CoD alone no longer sufficient) · nominee/UBO visibility (CoreTax ↔ Ministry of Law UBO registry) · late-filing penalties (IDR 1M corporate / 100k individual + interest) · the exit-tax audit (NPWP deregistration triggers a full DJP audit).

### 1b. Demand reality (GSC)

Nothing captured: no tax-intent query in the top-60; `/services/tax` on page 3. The opportunity space (to be built as intent pages): expat tax residency 183 days · PT PMA tax obligations · Coretax for foreigners · NPWP for foreigners (1 GSC impression exists — "npwp orang asing") · Indonesia tax calendar 2026 · UMKM 0.5% PMA. The dengue-article precedent proves the dispatch can rank fast on fresh topics; the 7 pain points above are evergreen equivalents.

### 1c. What competitors do (fetched 2026-06-10)

| | Framing | CTA | Pricing | Tools/deadlines | Humans |
|---|---|---|---|---|---|
| Cekindo/InCorp | Problem-first → 4 services | Free-consultation form | None | **PIT+CIT calculators** (only tool in market) | **Dessy Amelia, USKP C, IKPI** (only named credential) |
| Emerhub | Problem-first → 5 services | Schedule consultation | None | Deadlines in prose only | 1 photo, no name/credential |
| LMI | Pure service-list | **None found** | None | None | None |

**The empty slot, verified:** *no competitor shows a deadline calendar or reminder utility* — and Bali Zero already has the `/tax-calendar` tool with iCal export. Hypothesis H1 held with one refinement: Cekindo is not "static" (it has calculators); the uncontested gap is specifically **calendar/reminder utility + named credentialed human**.

### 1d. DRAFT design proposal (paper-only, gated — Round 1B)

**Thesis: "the deadline guardian."** The tax frontend's job: *you will never miss a deadline, and you will never be misclassified.*

1. **"My Tax Calendar"** — upgrade the existing `/tax-calendar` from static list to a 3-question profile (company or individual? PKP? SPDN/SPLN?) → personal deadline set → iCal + **WhatsApp reminder opt-in**. Only one in the market (1c); the reminder opt-in converts a utility into a recurring touchpoint. (Reminder send = backend work; flag: must stay PII-minimal, opt-in only.)
2. **Pain-point content spine** — 7 cornerstone guides, one per NB-4 pain point, each signed by a named tax lead with credentials (the Cekindo gap, rubric #2) and each anchoring official numbers (penalty amounts, rates — rubric #1).
3. **Penalty/official-fee anchoring** — publish the IDR 1M / 100k late-filing penalties and statutory rates prominently; "what it costs to get it wrong" is the honest urgency no competitor uses (vs scarcity timers).
4. **Primary CTA: booked consultation** (`/book`, IA-3) with the dial set formal — this is a retainer purchase, not a chat.
5. **Match-then-beat calculators** (later phase): Bali-specific cases (freelancer KITAS-holder; villa rental income) vs Cekindo's generic ones.

Measurement: feeder tier first (GSC impressions/clicks growth on tax intents, position of `/services/tax`), then tier-1 instrumentation on calendar-profile completions → consult clicks. No tier-3 claims (3 sessions/28d today).

---

## 2. PROPERTY channel

### 2a. The service shape (NB-5 ground truth)

The domain is a **fear + verification** domain. The buyer's lived reality:

- **4 lawful pathways:** Hak Pakai (KITAS/KITAP holders, 30+20+30 = up to 80 yrs, ~IDR 5B minimum in Bali, divest-within-1-year if visa lapses) · HGB via PT PMA (strongest for commercial; 80 yrs; BKPM Reg 5/2025 capital reduced to IDR 2.5B — see §4 verification flags) · leasehold (no visa/company needed; 25–30 yrs market standard; protection is purely contractual → notarized or nothing) · HMSRS strata (IDR 5B min; effectively rare in Bali due to the 15m height limit).
- **The unlawful route, now criminal:** nominee arrangements are void (Art. 26(2) UU 5/1960) and **a criminal offense in Bali under Perda Bali No. 4/2026 — up to 5 years + IDR 1B fine** (§4 flag). The nominee owns everything; the foreigner has no recourse.
- **The DD checklist:** KKPR/zoning via OSS/GISTARU (Pink=tourism w/ KBLI 55193, Yellow=residential, Green=criminal to build on) · BPN certificate via BHUMI (disputes/blokir/liens) · 5 years PBB tax history (arrears block the AJB) · PBG + SLF permits · **Adat clearances** (Bendesa Adat; temple land not always on BPN maps).
- **The 7-step buyer decision sequence** (this is the IA skeleton): purpose/structure → spatial DD → legal/tax DD → MOU + 10% escrow → notarial PPJB → tax settlement (2.5% PPh seller / 5% BPHTB buyer) → AJB + BPN registration.
- **The 5 deal-killers:** nominee trap · green-belt/Subak villas (actively demolished) · leasehold renewal traps (no guaranteed-extension clause = landlord seizes improvements) · Girik/uncertified land at 10–40% discounts · off-plan developer failures (under-hand PPJB, no PBG).

### 2b. Demand reality (GSC) + the hidden asset

Zero organic property demand captured. But the channel has the strongest **unused internal asset** of the four: the PRIME property-intelligence stack (zone lookup, competitor density, temporal analysis — live at prime.balizero.com and as internal tools) — exactly the "interactive zoning tool" that §2c shows **nobody in the market has**.

### 2c. What competitors do (fetched 2026-06-10)

| | Framing | CTA | Pricing | DD checklist/tools | Humans |
|---|---|---|---|---|---|
| Seven Stones | Problem → 4-step process | 9-step intake form | **Rp 22M + 11% VAT for DD** | Steps + document checklist | None |
| Emerhub | Buyer-advocacy | Free consultation | None | 5-step workflow, text only | None |
| Bali Legals | Fear-hook | Weak "contact us" | None | **Published 8-point checklist** | None |
| Kibarer | "First with in-house notary" | Enquire/WhatsApp | None | Named, zero methodology | None |
| LMI | (property pages 404 mid-restructure) | — | — | — | — |
| *Benchmark* PKWA (SG) | Journey-framed | Free consultation | **S$1,500–2,200 all-in** | Buyer+seller steps | **4 named lawyers + photos** |

**Hypothesis H2 half-refuted (important):** DD *checklists* are already commoditized (Bali Legals, Seven Stones) and Seven Stones *already publishes a DD price* — so "first transparent price" is not claimable in property. The uncontested edges, verified: **(1) no interactive zoning/DD tool anywhere; (2) nobody shows the OUTPUT (a redacted sample DD report with a pass/flag/fail verdict format); (3) nobody names the professional.** PKWA shows the full pattern working in a developed market.

### 2d. DRAFT design proposal (paper-only, gated — Round 1B)

**Thesis: "the verification authority."** The property frontend's job: *don't lose your money — verify before you sign.*

1. **The Buyer's Journey page** — the NB-5 7-step sequence as the channel's spine, each step mapped to what Bali Zero does there (journey-stage pattern, e-Residency/Henley). This page IS the channel hub.
2. **Public zone-checker teaser** — reuse PRIME zone-lookup as a public "check a property's zone" instrument (category-defining per 2c; GEO-citable). Teaser → full DD report. *(Gated: PRIME exposure scope needs Antonello — what's safe to expose publicly vs intel that stays internal per Law 2/6.)*
3. **The redacted sample DD report** — publish one, with the verdict format (pass/flag/fail per check). Converts the universal fear-framing into proof; nobody does it (2c-edge 2).
4. **Beat Seven Stones on "what the price buys"** — DD offer presented as scope tiers + turnaround days + the sample deliverable; price display gated on D2/E like everything pricing.
5. **The nominee wedge** — content + guard-rail framing: "the agency that tells you what NOT to do," anchored on Perda Bali 4/2026 (§4 flag first). Highest-fear, highest-search-potential topic; aligns with the WhatsApp-bridge nominee canonical already hardened in W73.
6. **Primary CTA: booked consultation**; secondary WhatsApp; eligibility tool stays as a feeder instrument.

Measurement: feeder tier (GSC growth on property intents from ~zero), tier-1 on zone-checker usage → DD inquiry chain.

---

## 3. Cross-channel notes for 1B

- Both channels depend on Stage-A approvals: `/book` rail (IA-3), trust layer (IA-4), pricing direction (E). Neither needs the §4 fork resolved differently — both are page-first by nature (consideration purchases).
- Both are **feeder-first**: 1B sequencing should put intent-content + instruments BEFORE any funnel-polish work, opposite of Visa/Company (which have demand and need conversion).
- The tax calendar and the zone checker are the channels' GEO instruments (dated, structured, citable) — same family as the RegWatch feed (IA-5).

## 4. Verification flags (anti-hallucination — re-verify before ANY public page quotes these)

All NB-sourced, not yet independently confirmed against primary sources: **BKPM Reg 5/2025** (PT PMA paid-up capital 10B→2.5B — material claim, verify at bkpm.go.id) · **Perda Bali No. 4/2026** (nominee criminalization, 5yr/1B — verify gazette) · **PMK 112/2025** (PPT/substance for DTA) · **KEP-55/PJ/2026** (transitional deadline) · the 11%-effective/12%-headline PPN mechanics (PMK 131/2024) — consistent with W73's persona rules, good sign. Rule: every regulatory number that lands on a public page passes a devils-advocate/primary-source check at content time. NB citations are leads with high prior, not gospel.

## 5. Defect-ledger addendum (found during this study's diagnosis pass)

| # | Finding | Severity | Route |
|---|---|---|---|
| D11 | Backend `/api/analytics/funnel-event` allowlist (`routers/analytics.py` ALLOWED_EVENTS) accepts only **11 of 32** FUNNEL_EVENTS — 21 events silently dropped server-side (`unknown_event`); the workspace funnel dashboard is blind to them. GA4 (gtag) unaffected. | **P2** | Stage-B B1 measurement phase (backend change + tests) |
| D12 | **Soft-404 at scale**: any slug under any category returns 200 with a title-cased phantom title (verified live: `/tax/anything-test`, `/taxes/totally-nonexistent-slug-xyz` → 200). Infinite crawlable surface, thin-content indexing risk. | **P2** | Needs `notFound()` in `[category]/[slug]` render + metadata when article resolves null — ship with a dedicated Playwright test (404-on-garbage + 200-on-known-slug); blast radius = all article pages, NOT a blind quick-fix |
| D5/D-canonical | Resolved/closed: dead `property_cta_click` removed + `/tax`→`/taxes` 308 shipped (sancho/mythos-safefix-1); `/lifestyle` already redirected (GSC entry was historical). | — | shipped |

## 6. Open questions for the team (the Law-2 limitation, §11 known-limitation on the record)

1. What actually kills Tax retainer deals and Property DD engagements? (If the team ever volunteers an anonymized, aggregated "why deals fail" digest to Subhi, both proposals above get sharper. Not solicited — noted per charter.)
2. Who is the named, credentialed face for Tax (USKP?) and for Property/legal? The competitor gap is unclaimable without a real human willing to be on the page (needs team consent, like the PPJK/DJP badges).
3. PRIME public exposure scope (2d-2) — Antonello's call, Law 2/6 boundary.
