---
panel: beyond-sota-xfamily
lane: 11-product-ux-visual-design
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T19:20:04Z
finished: 2026-08-28T19:31:38Z
duration_s: 694
exit: 0
words: 4415
prompt_sha256_16: 580a6eb7301f3e46
prompt_chars: 18319
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• I'll ground in the repo first, then survey, then write the report. Starting with recon.

• Good grounding. Now reading the key design docs and defect evidence.

• Now the funnel audit, design loop doctrine, and defect evidence.

• Now the defect evidence, catalog, and remaining repo grounding.

• Repo grounding is solid. Now the web SOTA survey.

• Two final survey searches, then I'll write the report.

• All grounding and survey work is done. Here is the complete report.

  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 11/13 — Product, UX & visual design craft
  model: Moonshot Kimi K3 (pinned lane)
  sources: 14
  repo_files_verified: 25
  status: complete
  ---

  # BEYOND-SOTA Lane 11 — Product, UX & visual design craft

  **Access note.** This lane ran in a read-only snapshot. All `MEM:`/`$MEM` references in the lane brief (the seven `discovery_*` memory files) live outside the snapshot and were **unavailable**; I used the repository's own copies instead and say so wherever the brief assumed memory content. Where the brief said "write the file," the content is returned in this message; no file was written, so no `ls -la` probe applies.

  ## 0. TL;DR

  Nuzantara's *design governance* is genuinely ahead of world SOTA — no surveyed organization runs cross-family adversarial LLM panels with row-by-row dispositions and an evidence ladder on design dossiers — while its *surfaced product* is behind: the design law exists mostly as mockups and doctrine, journey-test coverage is roughly one spec file per three routes, the only end-to-end funnel smoke has never been green, and the website produced 2 leads in 90 days. The single biggest gap is the **claim≠control disease applied to UX**: advisory smokes, warn-only brand guards, privacy flags nothing reads, and "audited separately" translations. Top-3 moves: (1) a route↔journey-spec coverage ledger that makes every public money-path route provably tested in CI, with the red advisory fullstack smoke fixed or deleted; (2) self-hosted component-level visual regression over the 32-component brand-api catalog (a zero-SaaS Chromatic built on the Playwright stack already in the repo); (3) a repo-wide sweep promoting every warn-only design/brand guard to a hard failure, generalizing the W99 font antibody. Honorable mention: an "anonymous visitor" Playwright persona that would have caught 4 of the 5 measured public-surface defects of 2026-08-28.

  ## 1. How Nuzantara does it today

  **The Design Study Loop (the crown jewel).** On 2026-08-27 the organism ran an eight-round design study (R0 census → R1 psychology → R2 SOTA import → R3 heuristic autopsy → R4 identity LAW → R5/R5b mockups and interactive prototype → R6 walkthrough/runtime floor → R7 doctrine closure), all under `research/design/2026-08-27-r*.md`, each round shipped behind the adversarial-review CI gate. Verified on disk: `research/design/2026-08-27-r7-doctrine-loop-closure.md` (288 lines) records the loop's order, the **evidence ladder** (every load-bearing claim classed a–e, "an unclassed load-bearing claim is challengeable on that ground alone," §3.1), and a binding amendment register that R4 must absorb. R3 (`2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md`) ran a 27-defect autopsy against four declared frameworks (Nielsen heuristics, Stanford/Fogg web credibility, GDS form principles, Zero's nine rulings), with computed WCAG contrast tables and a four-seat adversarial pass whose findings are dispositioned row-by-row (codex 32, kimi 23, agy 14, qwen 10; verified in the file's adversarial section). R7's amendment 5 gates the "honest human" trust module structurally: it renders only when a verified staff record backs it — a trust pattern most of the industry implements as a copy promise.

  **The follow-on loop (GARUDA case code, 2026-08-28).** `research/design/2026-08-28-case-code-design.md` (read in full) is a design dossier for the customer-visible case code: it keys the code to the *journey* (`result_id_ref`, schema-enforced one-code-per-journey), refuses to put the code in URLs (PII opacity law R4:118 honored), and writes the human channel into the design contract — "identify before you disclose," "the code never asks for money." It went through a two-seat cross-family adversarial pass with 20 findings, 17 applied. This is service-design-for-high-stakes at a level I found in no surveyed system outside government service teams.

  **Brand cortex.** `skills/bali-zero-brand/` (listed) contains `constitution.md`, `tokens.json` (authored in the **W3C DTCG `$schema`** format — before the spec's first stable release), `voice/` (including forbidden-phrases and off-tone rubrics), `layouts/`, `anchors/`, `redteam-cortex/`, empirical metric logs and external benchmarks. The WR2 pipeline runs through eight specialist agents (`.claude/agents/wr2-*.md`): the design-architect orchestrates fan-out under hardcoded contracts (no inline artifact writing — "that is a bug, not a feature," enforced after a measured test-3 failure), and `wr2-critic.md` gates rendered PNGs with a 4-rubric score plus binary verdict, using ImageMagick pixel checks, palette-coverage thresholds, sha256 anchor checks against silent placeholder reuse, and the canonical-wordmark rule.

  **Product surfaces.** `apps/mouth` (Next.js): **158 `page.tsx` routes** (`find apps/mouth -name page.tsx | wc -l`), components under `src/components/` (30+ domain folders), 5 locales (`src/i18n/locales`: en, fr, id, it, ru — the brief said EN/ID/IT; the repo carries five), and locale-specific guard tests (`secondhome-forbidden-claims.test.ts` pins regulated claims per locale). `docs/design/components-catalog.md` is a **generated** catalog of 32 components from `packages/core/components/*.tsx`, regenerated by `scripts/brand_api_gen.py` with a CI idempotence check (`.github/workflows/p8-brand-api.yml`, plus `brand_token_lint`). The GARUDA OS plan (`docs/design/2026-07-19-garuda-os-unified-surfaces/PLAN.md`) unifies operational surfaces on copper/anthracite with two imported editorial disciplines: **yellow = verifiable facts** (fact-badge), **red = criticals only** — and deliberately scopes the editorial brand tokens away from 8-hour operational UI.

  **Design QA in CI.** Five verified workflows: `lighthouse.yml` (10 URLs, desktop preset, accessibility ≥0.9 at **error** level, performance only warn); `frontend-live-sentinel.yml` (asks production which commit it is *running*, ancestry-tested — born from the 2026-07-27 incident where balizero.com served 13-hour-old code while every record was green); `wr2-master-template-guard.yml`; `p8-brand-api.yml`; `lint-i18n-providers.yml`. Playwright: 53 e2e spec files, exactly **one** visual spec (`bz-product-family.visual.spec.ts`), one a11y spec (`e2e/a11y/workspace-a11y.spec.ts`). Recorded CWV (`docs/FRONTEND_PERFORMANCE_GUIDE.md:18-20`): LCP ~1.2s good, CLS ~0.05 good, INP <500ms "needs improvement."

  **CRO state.** `docs/cro/2026-04-19-funnel-audit.md` (read) is brutally honest: in 90 days the website produced **2 leads vs 420 from WhatsApp**; `funnel_sessions` showed 28 sessions, 0 conversions; funnel CTAs fired no analytics events; the "See transparent pricing" CTA was a bait-and-switch to the same URL. Its verdict: the site is a prestige brochure, WhatsApp is the real funnel, and the homepage should be designed as a qualified springboard into it.

  **The 5 measured defects of 2026-08-28.** The memory files are unavailable to me; I verified what the repo itself shows. (a) *Visa clock telling an overstayer they are valid* — **fixed in this snapshot**: `apps/mouth/src/app/visa/clock/[hash]/page.tsx:86` carries the postmortem comment ("an overstay was shown '0 days from today' under the heading 'Valid until'") and the page now renders an `overstay: true` branch with "Days overstayed." (b) *401 ejecting anonymous visitors* — **partially fixed**: `apps/mouth/src/lib/api/client.ts:346-360` now distinguishes a never-authenticated visitor from an expired session (`hadSession` read before `clearToken()`), with portal-vs-workspace login routing. (c) *`isAuthenticated()` localStorage-only gates* — pattern verified present: `client.ts:211` defines it, 19 files reference `isAuthenticated`, 101 files touch `localStorage`. (d) The anonymous-funnel-view and magic-link-no-consumer defects I could not verify in the snapshot; I treat the "5 defects" count as reported, with 2 confirmed cured, 1 confirmed present.

  ## 2. Scars & ledger evidence in this area

  - **W99 (2026-07-14, the defining design scar).** `.claude/rules/cicatrix-scars.md:717`: the WR2 renderer's font-inject *checked* `'href="_base.css"' in html` but *replaced* a different pattern — 6/9 slides of one carousel and 4/9 of an **already-published** Instagram carousel were painted in system fallback font, render green, critic PASS. Two scar families in one: #3 (check≠action) and #2 (the renderer already computed `montserrat=false` via `document.fonts.check` and **downgraded it to a warning in a 12MB run log** — "the guardian existed, saw, and whispered"). Antibodies: injection anchored with `re.subn` failing loudly at `n==0`; `montserrat=false` promoted to hard render failure; an 8-case guilt+innocence suite sweeping the whole layout library. The gotcha that generalizes: "a guardian that degrades to warning what it knows is fatal IS family #2 in miniature," and "font identity is proven with `document.fonts.check`/measureText, never by eye — the vision critic judges readability, not font identity."
  - **W96 (2026-07-13).** Unisolated unit tests wrote phantom micro-carousels into the **production WR2 review queue** (24 on Pro, 131 on M5) because a library default resolved to the real runtime state root — a design-ops surface polluted by the test corpus.
  - **WR2 supervisor dead 4 days (scar block ~line 471).** Zero asked "does WR2 make a carousel every day?" — it did not; `state=running, last exit=0` while the worker was a zombie (skeleton venv, `asyncpg` gone). Green-but-dead, superscar #2, on the editorial pipeline's entry point.
  - **PENDING-ARMS (grep counts: "design" 165, "mouth" 77, "journey" 6 rows sampled).** Three rows bite this lane directly: (1) the **Visa Oracle fullstack smoke has never been green** — turned on red as *advisory* by PR #4709, measured 13 failure / 17 skipped / 0 success across 30 runs, failing identically on unrelated PRs, "worse than absent: it occupies the slot where a working smoke would sit"; (2) the Visa Oracle's `sensitive:` flag appears **56 times** in `tree.ts` and **no line of code reads it** — "a claim, not a control," superscar #3 on a privacy surface; (3) a single fact added to the Oracle vocabulary broke hand-transcribed counts in ~12 places across 4 suites, costing four correction rounds and one false gate verdict — derived data maintained by hand.
  - **i18n blind spot (scar line ~223).** The editorial sentinel audits "English canonical .mdx only — translations audited separately," which "= audited **mai**": the KN-3 bug shipped stale figures in it/ru/fr while the sentinel was green.
  - **AMENDMENTS/superscars.** Superscar #2 (exists≠armed) and #3 (guard-over-match / name promises a check the code never performs) are the two families every UX finding below lands in; #6 (phantom citations) is what the Design Study Loop's evidence ladder is the antibody *for*.

  ## 3. World SOTA survey

  | System/practice | Source | Mechanism | Measured effect | Transferability |
  |---|---|---|---|---|
  | GOV.UK Design System + Service Standard | design-system.service.gov.uk; GDS blog 2026-07 | One thing per page; question-protocol; service assessments; standard now "living," continuous | UK government services consistently top usability league tables; pattern library reused by 10+ governments | **Direct analogue** (visa/immigration flows). R3 already imports GDS form principles; the *assessment* discipline maps to the organism's gate culture |
  | Baymard Institute checkout/forms research | baymard.com studies (2024) | Large-scale usability testing (11,000+ participants); field-level friction taxonomy | 70.19% avg cart abandonment; 18% abandon from length/complexity alone; avg checkout 11.3 fields | High for GARUDA checkout; mostly copy/config-level fixes — but needs traffic to matter |
  | W3C DTCG design tokens format | designtokens.org TR/2025.10 (first stable, 2025-10-28) | Vendor-neutral JSON token interchange; Style Dictionary-style compilation to every platform | First stable spec ends format fragmentation | Already partially adopted: brand `tokens.json` carries the DTCG `$schema` — ahead of most product teams |
  | Storybook + Chromatic visual regression | storybook/chromatic docs & guides 2025-26 | Every component story auto-becomes a visual test; pixel diff vs baseline; review workflow in CI | Industry-standard catch rate for unintended UI change; paid SaaS (snapshots metering) | High, but SaaS cost + token violates flat-sub rule → self-host equivalent on existing Playwright |
  | LLM-as-judge for web/design quality | WebDevJudge, arXiv 2510.18560 (2026-03) | Verifiable rubric trees; (M)LLM critics evaluated against human preference labels | LLM critics approach human ranking on web-dev quality with structured rubrics | Already home-grown: wr2-critic predates this literature; extending it to web pages is the frontier |
  | Statsig CUPED / variance reduction | statsig.com docs+blog; Deng et al. (Microsoft) | Adjust metrics by pre-experiment covariates | ~30-50% variance reduction → same power with ~half the sample | **Low today** — 28 tracked funnel sessions/month makes any A/B framework moot; traffic acquisition precedes statistics |
  | WCAG 2.2 | W3C Rec 2023-10 (ISO/IEC 40500:2025) | 9 new SC: 2.5.8 target size 24px, 3.3.8 accessible authentication, 3.3.7 redundant entry, focus-not-obscured | Legal baseline in EU (EAA 2025) | Direct: 3.3.7/3.3.8 bear on the visa funnel's auth and re-entry; R6's runtime a11y floor is aligned |
  | v0 / generative UI | Vercel v0 + independent reviews 2025; arXiv 2507.22827 | Prompt-to-React with AutoFix pass; UI-to-code benchmarks | Fast drafts; reviewers find buggy output and a11y issues requiring manual fixes | Marginal: the organism's constraint is not generation speed but verification; its critic-gate pattern is the missing piece v0 lacks |
  | NN/g trust in AI advice | nngroup.com 2025-09 | Studies: perceived accuracy/competence, not anthropomorphism, drives trust in AI advice | Scripted ~62%-accurate advice measurably erodes trust | Directly relevant to Visa Oracle's "AI drafts, team signs" framing — the CRO audit already flagged authority must be human and named |
  | E-E-A-T / YMYL trust signals | industry primaries 2026 | Named humans, verifiable identity, physical presence for high-stakes content | Local experience/verifiability is the top credibility factor for YMYL services | Already doctrine: R6's physical-address mark + honest-human verification gate exceeds common practice |

  The three that matter most: **GDS**, because it is the only culture that treats a visa-style flow as a *service* (journey, not page) and wraps it in an assessment regime — the organism's Design Study Loop is structurally a GDS service assessment run by an LLM fleet, and R7's evidence ladder is stricter than GDS's; **Chromatic-class visual regression**, because it is the one mainstream capability the organism lacks — W99 is precisely the defect class component-level VRT exists to catch, and it escaped through pixel rendering while every record was green; **Baymard**, not for its statistics (unreachable at current traffic) but for its *method*: friction taxonomies built from observed task failure, which is what R3's autopsy already does qualitatively and what the funnel telemetry must do quantitatively.

  ## 4. Position vs SOTA

  | Sub-dimension | Position | Evidence |
  |---|---|---|
  | Design process & governance (study loop, adversarial panels, evidence ladder) | **AHEAD** | `research/design/2026-08-27-r7` (evidence classes a–e; 53-findings cross-family panel with dispositions); no surveyed system, incl. GDS, runs machine-checked claim classes on design dossiers |
  | High-stakes service design doctrine (trust, identity, human channel) | **AHEAD** | R6 physical-address + honest-human structural gate; case-code dossier's "code never asks for money" / identify-before-disclose SOP (`research/design/2026-08-28-case-code-design.md` §3.5) |
  | Brand system & tokens | **AT** (drift risk) | DTCG-schema `tokens.json`; but three token realities coexist (editorial brand tokens, GARUDA product tokens, `globals.css` 80 CSS vars + tailwind) with no verified-agreement gate |
  | Editorial pipeline QA (WR2 critic) | **AT** (mechanism AHEAD, enforcement behind) | `wr2-critic.md` pixel/sha256/rubric checks — but W99 shipped a wrong-font carousel to IG with critic PASS |
  | Journey / e2e coverage | **BEHIND** | 53 spec files vs 158 routes; the one browser→FastAPI→Postgres smoke red since birth (PENDING-ARMS #4709 row); GDS-class services require a tested happy+sad path per journey (ASSEMBLY-LINE G5 says the same — doctrine ahead of practice) |
  | Visual regression | **BEHIND** | 1 visual spec; no component-level VRT; Chromatic is table stakes at SOTA shops |
  | CRO & experimentation | **BEHIND** | 2 website leads/90d; 0/28 tracked conversions; CTAs unfired analytics (2026-04-19 audit); no experiment infra — though at this traffic, statistics are not the binding constraint |
  | Accessibility | **AT** | Lighthouse a11y ≥0.9 at error level; R6 runtime a11y floor; computed WCAG contrast in R3; but a single a11y e2e spec and no per-route axe automation |
  | Performance | **AT** | Recorded LCP/CLS good, INP needs improvement; Lighthouse perf only warn-level, desktop-only |
  | i18n | **BEHIND→AT** | 5 locales + provider lint + per-locale claim tests; but the KN-3 "audited separately = never" scar and no translation-freshness parity gate |
  | Design QA via screenshots | **AT** | Playwright screenshots + live sentinel probing production content (genuinely rare); not yet systematic per component |

  Honest both directions: the organism's *doctrine* would embarrass most design orgs; its *shipped surface* carries a permanently-red smoke, one visual test, and a homepage that converts nobody. Doctrine is not the product.

  ## 5. Beyond-SOTA recommendations

  Ranked by (impact × confidence) / cost. All respect: no paid Anthropic API, CLI-only LLM seats, PII output boundary, Zero rules business matters.

  **R1 — The Journey Ledger: route↔spec coverage as a CI gate, and the red-smoke reckoning.** *What:* a generated ledger mapping every public `page.tsx` (158) to the journey spec(s) exercising it, checked in CI like `brand_api_gen --check`; every route on a money/trust path (visa, garuda, checkout, portal login, clock) must have a green journey spec — and the advisory fullstack smoke is either cured and promoted to required, or deleted (the PENDING-ARMS row's own verdict: red-and-advisory is worse than absent). *Why beyond SOTA:* coverage gates exist (Codecov), but nobody gates *customer journeys per route* recomputed from the route tree itself; it composes the repo's own ASSEMBLY-LINE G5 doctrine with its brand-api idempotence pattern, exploiting the asymmetry that sessions own the whole lifecycle and CI is the only reviewer. *Cost:* ~2 session-days, flat-sub tokens only. *Gear:* 2. *Risk/scar family:* #2 (a ledger nobody enforces) — mitigated by making it a required check from day one. *Metric:* % of public money-path routes with a green journey spec — before: unmeasured, ~1/3 of routes have any spec file, the flagship funnel smoke 0-for-30; after: 100% money-path, ledger enforced. *Kill criterion:* if the ledger itself ships red-and-advisory (its own disease), delete it and record the scar. *First PR:* `scripts/ci/journey_ledger.py` + guilt/innocence tests + workflow leg; ≤400 lines.

  **R2 — Self-hosted component visual regression over the brand-api catalog.** *What:* Playwright screenshot stories for the 32 catalog components × their prop states × light/dark, baselined in-repo, pixel-diffed in CI (harness exists: Playwright + the one visual spec + W99's measureText/font checks). No Chromatic SaaS (per-token SaaS violates the spend rule; the self-hosted pattern is an active community practice). *Why beyond SOTA:* Chromatic diffs pixels; this diffs pixels **plus brand-constitution predicates** (font identity via `document.fonts.check`, palette coverage, the wr2-critic rubrics) on the same renders — W99's antibody generalized from carousels to the product, which no surveyed VRT tool does. *Cost:* ~3 session-days + CI minutes. *Gear:* 2. *Risk:* #2 flaky baselines → threshold + retry discipline from day one. *Metric:* W99-class defects reaching production — before: 1 measured (published on IG); after: 0 across two quarters; component visual coverage 1 spec → 32 components. *Kill:* flake rate >5% of runs for 2 weeks → reduce to money-path components. *First PR:* 8 highest-traffic components (AppFrame, fact-badge, pricing cards), one baseline mechanism, one CI leg.

  **R3 — The "warn is a lie" sweep: every design/brand guard blocks or dies.** *What:* repo-wide audit (grep-driven, the W99 gotcha as a query) for guards that compute a fatal condition and log-warn it: brand renderers, token linters, i18n checks, the `sensitive:` flag (56 declarations, zero readers — either wire redaction or delete the field), "audited separately" translation scopes. *Why beyond SOTA:* nobody else has a scar corpus that names this disease (families #2/#3) and can therefore sweep for it mechanically; the asymmetry is the corpus itself. *Cost:* ~1 session-day. *Gear:* 1-2. *Risk:* #3 false positives on legitimately advisory probes → each promotion names its blast radius. *Metric:* count of warn-only guards on customer-facing render paths — before: ≥3 measured (W99 pattern, sensitive flag, translation scope); after: 0. *Kill:* if a promoted guard blocks a legitimate publish twice, demote with a recorded reason. *First PR:* the `sensitive:` flag disposition (wire to PII redaction in the oracle payload or remove), plus the sweep report.

  **R4 — The Anonymous Visitor persona suite.** *What:* a Playwright persona with no cookies/no localStorage that walks every public surface asserting: no redirect-to-login on public content, no "session expired" copy for never-authenticated visitors, no auth-gated public funnel step, no stale-validity claims (the clock's overstay branch is now covered — make the class covered). *Why beyond SOTA:* SOTA tests auth'd and unauth'd paths separately; nobody systematically tests the *never-authenticated* identity as a first-class persona against copy-level truths ("Valid until" on an overstay is a copy bug no unit test sees). Would have caught ≥3 of the 5 measured 2026-08-28 defects (401 eject, clock validity, localStorage-gate ejects). *Cost:* ~1 session-day. *Gear:* 2. *Risk:* #2 — must run against prodlike config (`playwright.prodlike.config.ts` already exists), not just dev. *Metric:* defects of the 2026-08-28 class catchable by CI — before: 0/5 caught pre-production; after: ≥4/5 classes covered. *Kill:* none — low cost. *First PR:* persona fixture + 5 assertions on the 5 known defect surfaces; ≤300 lines.

  **R5 — Funnel telemetry before any further redesign: measure-first CRO.** *What:* verify the 2026-04-19 audit's first fix actually shipped (CTA event tracking — I could not confirm it in the snapshot; treat as unverified), complete it, and let `funnel_sessions` accumulate; adopt sequential/Bayesian evaluation suited to ~tens of sessions/month, not CUPED (which is SOTA at 100k+ sessions and cargo cult here). *Why honest:* at 2 leads/90d the website cannot be A/B-tested into health; the beyond-SOTA move is admitting the funnel is WhatsApp and designing the site as a *measured* springboard into it, per the audit's own verdict. *Metric:* events per funnel session (before: ~0 on CTAs), website lead baseline established (before: 2/90d uninstrumented). *Gear:* 1. *Risk:* none material. *First PR:* CTA event wiring on the 4 funnel features + one dashboard query.

  **R6 — Token tri-source convergence.** *What:* one DTCG token source compiled to CSS vars + tailwind theme + brand-api, with a CI diff that the three agree (extends `brand_token_lint`). *Metric:* token drift count between sources — before: unmeasured, three independent sources verified present; after: 0 enforced. *Gear:* 2. *Risk:* #9 schema drift if two sources both "win" — one SSOT named in the PR. *First PR:* the diff-check read-only leg.

  **R7 — LLM design-critic for web pages (advisory first).** *What:* extend the wr2-critic pattern to mouth pages: screenshot + R4 identity law + rubric → advisory report on PRs touching funnel surfaces, promoted to gate only after its false-positive rate is measured (the W100 lesson: verifier agreement measures transcription, not truth — calibrate against the R3 defect inventory first). *Metric:* R3-class defects per release; critic precision/recall vs the 27-defect gold set. *Gear:* 2-3. *Risk:* #6 phantom citations — critic must cite computed measurements (contrast, font checks), never impressions. *First PR:* critic prompt + gold-set calibration harness, advisory-only.

  ## 6. 90-day roadmap + first PRs

  - **Wave 1 (days 1-30) — close the claim≠control gap:** R3 sweep + `sensitive:` disposition; R4 anonymous persona (first PR: persona + 5 defect-class assertions, `apps/mouth/e2e/anonymous-persona.spec.ts`, gear 2, acceptance: each of the 5 known defect surfaces has a failing-then-passing assertion); R1 ledger read-only leg + the red-smoke decision brought to Zero with the PENDING-ARMS data.
  - **Wave 2 (days 31-60) — make pixels provable:** R2 component VRT on 8 components; R6 token convergence read-only gate; R5 telemetry verification/completion. First PRs as listed in §5.
  - **Wave 3 (days 61-90) — enforce and extend:** R1 ledger required on money paths; R2 to 32 components with constitution predicates; R7 advisory critic calibrated on the R3 gold set; i18n parity gate (KN-3 class: regulated-claim content-hash check across locales). Acceptance for the wave: money-path journey coverage 100%, visual coverage 32/32, zero warn-only brand guards.

  ## 7. Needs-ruling

  - **The honest-human module A/B** (R7 amendment 5): the production default flip to a named-human trust module requires a real, employed, verifiable person and Zero's business decision — structural gate is built, the ruling is not mine.
  - **Republishing the wrong-font revenue carousel** on Instagram (W99 residual): explicitly recorded as `operator[business]`.
  - **Chromatic or any metered design SaaS:** rejected by design in R2 (self-host); if Zero ever prefers the SaaS, it is a spend decision.
  - **Translation-freshness gate scope:** which claims are "regulated" enough to require per-locale parity (legal/commercial judgment, touches Legge 5-adjacent copy).

  ## 8. §Meta-pattern

  One defective belief generates nearly everything in this lane: **"the artifact's existence is the experience's quality."** A guard that exists is assumed to guard (W99's whispered warning; the dead-green WR2 supervisor; the Vercel Build Guard that "verified nothing"); a flag named `sensitive` is assumed to protect (56 declarations, zero readers); a smoke named "fullstack" is assumed to smoke (0-for-30, advisory); a scope line "translations audited separately" is assumed to audit (never); a mockup rendered is assumed to be a surface shipped (R4's identity law vs the funnels' current pixels); a homepage published is assumed to be a funnel (2 leads in 90 days). This is superscar #2/#3 wearing UX clothes, and the Design Study Loop's evidence ladder is the organism already groping toward the antibody: nothing is true below its evidence class. The beyond-SOTA move that unifies every recommendation above is to make that ladder *mechanical* — a repo where every design claim (contrast, font, journey, translation, conversion) carries a probe that runs, and where every probe either blocks or is deleted. The world has design systems; the world has visual regression; nobody has a design organism whose every aesthetic and trust claim is falsifiable in CI. That is the gap, and it is the same gap as every other lane's — which is itself the meta-pattern's confirmation.

  ## 9. Sources

  1. [GOV.UK Design System — Question pages](https://design-system.service.gov.uk/patterns/question-pages/) (accessed 2026-08-28) — the canonical one-thing-per-page form doctrine, direct analogue for visa flows.
  2. [GDS blog — Evolving the Service Standard](https://gds.blog.gov.uk/category/service-design/) (2026-07-02) — the standard becoming continuous/"living," the regime the Design Study Loop parallels.
  3. [Baymard — cart abandonment rate statistics](https://baymard.com/lists/cart-abandonment-rate) (2024 tracking) — 70.19% average abandonment; the benchmark base rate for funnel honesty.
  4. [Checkout abandonment friction breakdown citing Baymard](https://xentro.ae/insights/checkout-abandonment-where-friction-lives) (2026-01) — 18% abandon from complexity alone; field-count taxonomy.
  5. [W3C DTCG — Design Tokens Format Module 2025.10](https://www.designtokens.org/TR/2025.10/format/) (2025-10-28) — first stable token interchange spec; validates the brand cortex's `$schema` choice.
  6. [WebDevJudge (arXiv 2510.18560)](https://arxiv.org/html/2510.18560v3) (2026-03) — LLM-as-critic for web development quality with verifiable rubric trees; the literature R7 operationalizes.
  7. [Chromatic component-level visual testing guide](https://qaskills.sh/blog/chromatic-storybook-visual-testing-guide) (2026-05) — the SOTA mechanism (every story a visual test) R2 re-implements self-hosted.
  8. [Self-hosted VRT replacing Chromatic (GitHub RFC)](https://github.com/soroush-tech/core/issues/261) (2026-07) — evidence the self-host path is practiced, with the SaaS-cost rationale this organism shares.
  9. [Statsig — CUPED docs](https://docs.statsig.com/experiments/statistical-methods/methodologies/cuped) (accessed 2026-08-28) — variance-reduction mechanism; cited to explain why it does *not* transfer at current traffic.
  10. [Statsig — CUPED explained](https://www.statsig.com/blog/cuped) (2024-09) — measured variance/p-value reductions across 300+ customers.
  11. [WCAG 2.2 overview and new criteria](https://www.audioeye.com/post/whats-new-with-wcag-2-2/) (accessed 2026-08-28) — the 9 new SC incl. 2.5.8 target size and 3.3.8 accessible authentication bearing on the funnel.
  12. [Vercel v0 independent review](https://skywork.ai/blog/vercel-v0-dev-review-2025-ai-ui-react-tailwind/) (2025-09) — generative-UI quality limits (bugs, a11y issues needing manual fixes); why generation is not this organism's bottleneck.
  13. [NN/g — Prioritize smarts over sentience to increase trust with AI](https://www.nngroup.com/articles/smarts-emotion-trust-ai/) (2025-09) — perceived accuracy, not anthropomorphism, drives trust in AI advice; grounds the "AI drafts, team signs" copy correction.
  14. [E-E-A-T/YMYL credibility guidance](https://anitech.au/seo/e-e-a-t-credibility-navigating-ymyl-compliance-for-high-stakes-content/) (accessed 2026-08-28) — verifiable local identity as the top trust factor for high-stakes services; supports the physical-address/honest-human doctrine.

  Report complete. Sections 0–9 finished; `status: complete`.

