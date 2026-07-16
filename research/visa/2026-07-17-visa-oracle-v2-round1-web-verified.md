---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 1 (lane: sonnet-web-grounded)
status: round-1 raw lane output, faithfully preserved
adversarial_review: codex
---

# Round 1 — Web-grounded lane (Sonnet, live-verified URLs) — 2026-07-17

## 1. Government wizards
GOV.UK check-uk-visa (LIVE-FETCHED): landing "Start now" → /check-uk-visa/y; Q1 verbatim "What's your nationality as shown on your passport or travel document?" — dropdown + Continue, NO progress bar on Q1 (content-first philosophy). Engine: "Smart Answers" — 4 artifact types: Flow / Landing / Question pages / Outcome pages. Ships a `/visualise` suffix rendering the whole tree as a diagram (debug/trust feature to steal for internal ops + Ditjen demo). Sources: gds.blog.gov.uk/2012/02/16/smart-answers-are-smart/, design-guide.publishing.service.gov.uk/frontend-templates/smart-answer/, insidegovuk.blog.gov.uk/2016/10/27/making-it-easier-to-understand-smart-answer-logic/.
GOV.UK Design System (FETCHED VERBATIM):
- Question pages (design-system.service.gov.uk/patterns/question-pages/): one question per page; hint text = single short sentence, no full stops, never links; MANDATORY Back link ("Some users do not trust browser back buttons when they're entering data"); page = Back + heading + Continue, nothing else.
- Check a service is suitable (design-system.service.gov.uk/patterns/check-a-service-is-suitable/): THE exact Visa Oracle pattern — intro (general rules) → simple questions → auto eligibility → results. Never re-ask data; eligible results state costs/benefits/timeline; ineligible results "explain why and tell them what to do instead" — never dead-end.
Canada IRCC Come to Canada (403 on fetch — search-corroborated, UNVERIFIED live): 10-15 min, single flow for ALL pathways; disclaimer "no immigration decision will be made based on your answers"; openly states limits (no PNP/humanitarian). 1.6M visits in first 12 months.
Australia Visa Finder (403, corroborated): category-first — 4 entries (Visit/Work/Study/Join family) vs Canada single-flow; "entry level assistance" disclaimer, primary-applicant-only.
NZ find-a-visa (marketing page only, tool internals UNVERIFIED). Singapore ICA, US travel.state.gov "Visa Wizard": UNVERIFIED (403) — flag: browser automation could unblock.
Estonia e-Residency (LIVE-FETCHED): NOT a wizard — linear 4-step post-decision checklist (€150/30min apply → 30d approval + card → pickup → activate). Negative example: wizards are for MULTI-product funnels.

## 2. Private visa-tech
- Atlys: $36M Series C March 2026 (Susquehanna Asia, $76M total, ~700k visas/yr). AI roadmap: doc verification, eligibility assessment, real-time support (rolling out). Shipped: approval-likelihood pre-check (risk-scored) — adaptable to "which visa are you most likely to get". atlys.com; business-standard.com; yourstory.com.
- iVisa: 2-field checker (nationality+destination), embeddable partner widget (15-20% abandonment recovery claim — UNVERIFIED third-party). ivisa.com.
- VisaHQ: color-coded world map as PRIMARY navigation (green visa-free / amber eTA-VOA / orange consular). visahq.com/visa-requirements/.
- Boundless: wizard for triage + human legal team for complex cases — the Bali Zero model. >100k users, 99.7% success (self-reported UNVERIFIED). boundless.com.
- SafetyWing: no real wizard — weak comp, discarded.
- Sherpa° (B2B): passport-scan auto-fill (photo → pre-fills nationality; kills the 195-country dropdown = highest-friction field of every wizard reviewed); interactive requirements map incl. layovers. joinsherpa.com/products/travel-requirements.

## 3. Indonesian official ecosystem (SHARPEST FINDING, live-verified)
- imigrasi.go.id/wna/permohonan-visa-republik-indonesia (LIVE-FETCHED): ZERO wizard — flat alphabetical list of 100+ text links ("A1 BEBAS VISA (WISATA)", "E28A VISA INVESTOR", ...), no filter/search. Strongest live evidence of the functional gap Visa Oracle fills.
- `?golden_visa=1` on the same URL (LIVE-FETCHED) filters to 4 Golden Visa sub-types (E28B/C/D/F) with promo copy — the official backend already supports category filtering via URL params, never exposed as UI. Partnership intel: the ask would be "expose this as UI", not "build new infra".
- evisa.imigrasi.go.id: fetch empty (JS SPA) — UNVERIFIED live. Search-corroborated: eVOA (30d, IDR 500k, 24-48h), status tracking, ≤5 people/batch; delivery channel for Bridging Visa.
- Bridging Visa (Permenkumham 11/2024): 60-day onshore transition permit for VOA/ITAS/ITAP, apply ≤3 days before expiry, overstay-penalty-exempt while pending; still promoted in 2026 regional press — under-covered by all competitors. depok.imigrasi.go.id; hukumonline.com.
- Golden Visa official numbers (May 2026, *.imigrasi.go.id + Antara): 1,274 issued, Rp52.1T investment realized, 1,000-target exceeded. Citable social-proof for E28/E33 outcome pages. antaranews.com/berita/5576216.
- Ditjen Imigrasi 2026 posture: "digital immigration ecosystem", autogates, digitalization framed as ANTI-CORRUPTION ("reduce direct contact... minimizing transactional practices") — a polished third-party tool is thematically aligned with their stated goals.
- Bahasa search: NO Indonesian-language wizard exists anywhere; results point to the flat official list or blogs (balizero.com's article already ranks).

## 4. Literature
- NN/g: progressive disclosure (1995) + wizard variant "staged disclosure" (Nielsen 2006). Forms: inline validation on field completion. NO dedicated NN/g eligibility-checker article exists (checked).
- Conversational-UI 2025-26 (smashingmagazine.com/2025/07/design-patterns-ai-interfaces/): chat fits when intent varies turn-to-turn — NOT recommended as sole interface for a well-defined decision tree; structured form outperforms. → chat = edge-case escape hatch only. Validates "Decision Tree" framing.
- Typeform: the aesthetic-forward counterpart to GOV.UK utilitarianism; Visa Oracle sits exactly between.

## 5. Design inspiration (mixed confidence)
- Randstad "Quiz" (Awwwards SOTD 7.1): premium eligibility-quiz reference. awwwards.com/sites/randstad-quiz.
- "Chekhov Is Alive" (SOTD 7.49): personality-test with 28-30 illustrated outcomes → direction for per-visa illustrated outcome pages (UNVERIFIED URL).
- Categories: awwwards.com/inspiration/interactive-and-animated-quiz, /inspiration/quiz-result, /websites/web-interactive.
- GAP: no 2025-26 design-award winner exists for the "immigration decision tree" shape — an excellent Visa Oracle would itself be awwwards-submittable.

## TOP-15 verified steal-list (ranked)
1. GOV.UK "Check a service is suitable" structure = THE skeleton (S)
2. One-question-per-page + mandatory Back link (S)
3. `/visualise` tree debug view — internal QA + Ditjen demo artifact (M)
4. Category-first entry (Australia model) (S)
5. Passport-scan auto-fill (Sherpa°) (M)
6. Color-coded map teaser (VisaHQ) (M)
7. Ineligible → never dead-end, always "what to do instead" → lead (S)
8. IRCC self-assessment disclaimer language (S)
9. Illustrated per-outcome result pages (L)
10. True skip-logic branching (M)
11. Chat as escape hatch, NEVER primary funnel (validated by literature)
12. Explicit stated tool limitations on results (S)
13. `?golden_visa=1` intel (partnership angle)
14. Official Golden Visa stats as social-proof (S)
15. Bridging Visa as distinct tree branch — competitors don't have it (M)

## Verification gaps
403-blocked: IRCC, Australia, US Visa Wizard (browser automation could unblock). evisa.imigrasi.go.id homepage unverified (JS SPA — needs screenshot check). Awwwards section weakest-verified (search summaries, not full fetches).

## Adversarial review

**Seat:** codex (GPT-5.6-terra-high adversarial grading, 2026-07-17)
**Verdict:** SURVIVES-WITH-CAVEATS

Challenged points:
- The flat list, `golden_visa=1` filter, and the 1,274/Rp52.1T statistic survive live re-checks.
- The "TOP-15 verified" label is internally false — several listed entries were actually 403/unverified,
  not verified.
- Universal negatives ("no Indonesian wizard exists anywhere") are unsupported beyond the specific
  surfaces this lane actually checked.

This section is an appended R1-gate artifact (generator≠grader); the file body above is preserved
verbatim as the faithful record of this panel lane's original output.
