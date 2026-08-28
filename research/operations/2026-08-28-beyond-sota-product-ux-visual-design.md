---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 11/13 — Product, UX & visual design craft
model: claude-fable-5 (pinned lane)
sources: 18
repo_files_verified: 35
status: complete
sections_done: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
---

# Beyond-SOTA — Part 11/13: Product, UX & visual design craft

## §0 TL;DR

Position in one sentence: **ahead of world SOTA at deciding what the design should be
(adversarially-refuted Design Study Loop, constitutional WR2 critic, computed-contrast token
contract), behind it at knowing what the visitor actually gets** (0 of 6 measured 2026-08-28
production defects caught by the 53-spec e2e suite; 3+ live palettes vs one refuted identity).
Biggest gap: **verification vantage point** — every judge sits on a surface we control
(localhost builds, rendered PNGs, HTTP codes) instead of where the anonymous visitor stands;
ASSEMBLY-LINE already mandates the inversion, unarmed (family #2).
Top-3 moves: **(1)** scar-derived Production Journey Sentinels — every cured UX defect becomes
a permanent cron-run production probe with guilt+innocence self-test (R1);
**(2)** R4 Merah Putih → DTCG 2025.10 token SSOT with a CI tripwire that *recomputes* every
claimed contrast ratio (R2); **(3)** critic conformance — benchmark WR2's own critic against
its own incident corpus so W99-class false-PASSes go 100%→0% (R3).

## §1 How Nuzantara does it today

### 1.1 The Design Study Loop — design research as an adversarial, PR-shipped pipeline

The organism's flagship design practice is the **Design Study Loop** (Zero's mandate 2026-08-27:
marketing/psychology/aesthetics study, *no product code, flags OFF*). Verified in
`research/design/` (15 dossiers on disk this session): R0 census → R1 user psychology/personas →
R2 SOTA competitor census → R3 heuristic autopsy → R4 identity token spec → R5 mockups →
R5b tree-as-journey interactive prototype → R6 walkthrough + blind perception panel →
R7 doctrine/closure, plus follow-on build-lane dossiers (checkout, consent placement, delegate
flow, sponsor i18n, case-code). **Exactly 15 armed PRs**: #5058, #5060, #5064, #5074, #5077,
#5078, #5079, #5087, #5090, #5091 (loop) + #5099, #5104, #5130, #5131, #5172 (follow-on lanes) —
cross-checked against `git log` (e.g. `faff8e479 docs(design): case-code…(#5172)`).

Mechanisms that make it unusual (memory
`project_design_study_loop_garuda_visa_oracle_2026_08_27.md`, 47.5 KB, verified):

- **Every round is refuted by a cross-family panel** (Codex sol xhigh · Kimi K3 · Gemini agy ·
  Qwen 3.8 Max via TP1 — never the generator's own family). R3 took 79 findings from 4 seats;
  R7's panel "ate its own cooking" with 53 findings, 4 of 5 "Verbatim" payloads falsified by
  Codex reading the actual source. Where two refuters contradicted each other, the SOURCE
  (verbatim extract with file:line) adjudicated.
- **Design claims carry evidence class**: R3 caps hypothesis-grade defects at severity ≤2;
  R2 reframes all "borrow" patterns as *hypotheses-to-test*, and the tag travels into R5
  acceptance and R6 walkthrough ("a borrow never becomes a fact by being chosen" —
  `2026-08-27-r4-identity-merah-putih-token-spec.md:33`).
- **Contrast is computed, not eyeballed**: R3 measured that the funnels' reds `#ff3344`/`#ff2d4c`
  FAIL WCAG AA normal-text on paper (~3.3:1) while the logo family `#C8102E`/`#D01033`/`#c40020`
  passes every cell (5.1–6.2:1) — that measurement became the floor for ruling Q-R3.2. Kimi
  independently recomputed the whole contrast table ("esatta").
- **Owner rulings are a formal interface**: each round ends with ≤3 closed questions to Zero;
  9 accumulated rulings were ingested as census records; a standing order lets rounds proceed
  with pre-confirmed recommendations subject to async veto.
- **The deliverable is a single evolving artifact** (claude.ai HTML artifact, 6.43 MB at
  closure, JSON-driven renderer in `r0/build_artifact.py`) plus per-round repo reports gated by
  the R1 CI check (`scripts/check_adversarial_review.py` — frontmatter `adversarial_review:`
  must name one seat from a closed list; the loop itself got bitten by this gate on #5078/#5079
  and encoded the cure).

### 1.2 Brand cortex + WR2/WR3 — an editorial design system with a constitutional critic

The Instagram/editorial surface has its own governed design system, the **brand cortex**
(`/Users/nuzantara/.claude/skills/bali-zero-brand/`, verified: `SKILL.md` 114 lines,
`constitution.md` 440 lines, `tokens.json` 351 lines, plus `voice/`, `layouts/`, `past/` with
64 past carousels, `redteam-cortex/`, `_reflexion-synthesis.py`). Tokens are versioned with
provenance and WCAG history — e.g. the regulation badge migrated red→yellow on 2026-05-13
because red-on-antracite measured 2.27:1 (FAIL) vs yellow 8.14:1 AAA (`tokens.json:236,257`).

The **WR2 carousel pipeline** is agentic design-with-a-gate
(`.claude/agents/wr2-design-architect.md`, `wr2-critic.md`, both verified):

- The architect is an orchestrator bound by three hard contracts (mandatory fan-out to
  brief-interpreter/storyboarder/layout-composer/critic; NB ground-truth; no silent image
  reuse via sha256 anchor checks) — written into the agent after empirically observed
  violations (test-3: 0 Agent calls, 0 NB queries, placeholder reuse).
- **Cost discipline is codified**: test-5 cost $10.07/29 min with 165 tool calls; the agent now
  mandates 4 consolidated `_audit-checklist.sh` invocations (preflight / hero-sha /
  render-check / final-audit) instead of ~30 probes.
- The **critic is a hard gate, not an advisor**: 4 rubrics (brand adherence with ImageMagick
  pixel-palette checks on text zones; typography incl. UPPERCASE ≤35-word rule; copy with
  verbatim-citation enforcement; plus NB-INTEL spot-check of up to 3 highest-risk regulatory
  claims per carousel against ground truth). Binary PASS/FAIL per slide with retry feedback.
- WR3 (video) merged into WR2 as a single media surface
  (`docs/wr3/2026-07-26-wr3-into-wr2-single-media-surface.md`) with contracts and a weekly
  reflexion synthesis — after the W74 scar showed the reflexion cron was an 816-byte stub
  exiting 0 every Sunday (cured in W81).

### 1.3 The frontend estate — `apps/mouth`

Verified stack (`apps/mouth/package.json`, `components.json`): Next.js 16.3.1, React 19.2.8,
Tailwind v4 (CSS-based config, no `tailwind.config.*`), shadcn/ui new-york with CSS variables,
lucide icons, Vitest + Playwright, `@axe-core/playwright` present. **158 routes**
(`find src/app -name page.tsx | wc -l`) serving kita/my/prime/zantara/balizero surfaces with
SSO via `nz_access_token` httpOnly cookie on `.balizero.com` (`apps/mouth/CLAUDE.md`).
Component inventory spans 40+ domains (`src/components/`: visa, kbli, crm, portal, funnel,
trust, garuda, …). A separate **brand-api component catalog** exists
(`docs/design/components-catalog.md`, 395 lines: `AppFrame`, `AppHeroForm`, `AppStampReveal`,
`AppTrustStrip`, `AppWizard`, `CTAHandoff`, `FactBadge`, …) gated in CI by
`p8-brand-api.yml` (sentinel-pattern required check, W69-proofed).

### 1.4 Design tokens — one identity on paper, at least three in production

This is the load-bearing measured fact of this lane. R0 counted **six coexisting design
systems**; verified live in code this session, at least three distinct palettes are serving:

| Surface | Palette (verified) | Source of truth |
|---|---|---|
| IG carousels | antracite `#373D42` · red `#C8102E` · yellow `#F4C430` | brand `tokens.json` (351 lines, WCAG-annotated) |
| Workspace (kita/prime/zantara) | copper `--bz-accent #d4845a` on dark `#0f1419` | `apps/mouth/src/app/globals.css:263-309` (8 copper occurrences) |
| Public home/funnels | paper `#f7f6f2` + ink `#16213a` (hardcoded hex) | `src/app/(marketing)/page.tsx:76`, `v2/_components/PersonaDoors.tsx:43`, `layout.tsx:35` |
| Contract (not yet code) | **Merah Putih**: carta `#f7f6f2`, ink `#16213a`, computed `border-input #7a8093` (3.64:1), double-ring focus | `research/design/2026-08-27-r4-identity-merah-putih-token-spec.md` §3 |

The R4 spec is a real token contract — every hex either measured in the estate or computed
this session with contrast ratios stated per token, plus a nesting law (radius 12) and a
"contrast law" — but it lives in a research doc; `grep f7f6f2 apps/mouth/src` shows raw hex
literals, not named tokens. The reconciliation work was already identified a month earlier
(`docs/design/2026-07-19-garuda-os-unified-surfaces/PLAN.md` — "WS1 Token reconciliation
(foundation, do first)"; tri-LLM review round 1 INCONCLUSIVE) and has not landed as tokens.

### 1.5 Journey tests, probes, and QA

- **53 Playwright spec files** in `apps/mouth/e2e/` (vs 158 routes ≈ 1 spec per 3 routes),
  organized by domain (auth, crm, portal, smoke, zantara, a11y, …) plus a prod-like config
  (`playwright.prodlike.config.ts` with a preflight CLI). Spec quality is high: e.g.
  `funnel-ctas.spec.ts` pins the persona-doors reality with data-testids, documents its own
  history (chips strip → doors), and even documents a CI trap (describe title must contain
  "page Page" because `tests.yml` runs `--grep "page Page"`).
- **ASSEMBLY-LINE stage 2 mandates journey-tests-red-first**: "state machine + Gherkin/Playwright
  journey specs written BEFORE code" and DONE = "a customer journey working in production,
  meeting its SLO" (`docs/factory/ASSEMBLY-LINE.md:34,57`).
- **The probe that actually found the defects was not Playwright**: a real-browser sweep
  (28 balizero.com routes + 6 subdomains) that *types into pages* (triggering debounced work)
  and judges *where the visitor ends up*, not the HTTP code
  (memory `discovery_five_measured_defects_on_public_surfaces_2026_08_28.md`).
- **CI surfaces**: `lighthouse.yml` (10 URLs, 3 runs, desktop; a11y is an ERROR gate at 0.9,
  performance warn at 0.85, LCP warn 2500 ms — `.lighthouserc.json` verified),
  `frontend-live-sentinel.yml` (live-surface sentinel with a P0 budget of 12/day and an honest
  essay on cron-as-request-not-interval), `frontend-typecheck.yml` (merge-base-anchored changed
  files, W102-proofed), `wr2-master-template-guard.yml`, `lint-i18n-providers.yml`.

### 1.6 Funnel, conversion, trust

`docs/cro/2026-04-19-funnel-audit.md` is a real CRO audit: cognitive map of the 4 funnels,
Nielsen+Cialdini friction analysis, internal analytics (lead sources last 90 days, revenue per
category), competitor benchmark, and the honest finding that funnel tracking was
"broken-by-design" (bugs confirmed in code). The Visa Oracle work went further: R1 personas
(3: tourist/long-stayer/spouse), R2 distance map vs Airbnb (3/3) / GOV.UK (2/4) / iVisa (1/4),
and pricing doctrine from owner rulings — Q7 "one price, never split our fee" with the R7
amendment allowing exactly one state-set PNBP line pre-payment; price floor "from…" on landing,
exact at verdict. Trust devices ("Why we ask", "Not sure?", editable review, dated disclaimer)
were measured in the estate and promoted to identity law in R4 §5. On 2026-08-28 the VOA funnel
was measured answering an anonymous visitor end-to-end (201 ACCEPT, single `price_idr`,
D-7 deadline) with the only residual gate being Xendit secrets (`MEMORY_VISA_ORACLE.md:88`).

### 1.7 i18n and accessibility

Five locales on disk (`src/i18n/locales/`: en, fr, id, it, ru) with a CI lint for provider
wiring (`lint-i18n-providers.yml`). Accessibility: one dedicated axe spec
(`e2e/a11y/workspace-a11y.spec.ts`), Lighthouse a11y as the only ERROR-level category, WCAG
measured rigorously in the *design* loop (R3/R4/R6 — including SC 1.4.11 non-text contrast on
hairlines and an a11y floor declared in R6), and R5b's panel flagging a missing a11y suite as
an open item. Performance targets are documented with current numbers
(`docs/FRONTEND_PERFORMANCE_GUIDE.md`: LCP ~1.2 s good, CLS ~0.05 good, INP needs improvement
vs <200 ms target) with concrete virtualization/memoization/Framer-Motion patterns.

## §2 Scars & ledger evidence in this area

**Ledger pressure** (`.claude/skills/modus/PENDING-ARMS.md`, grep counts this session):
"design" 165 · "mouth" 77 · "journey" 6. The design surface is heavily represented in the
open-arms ledger; journey-test debt is comparatively under-tracked relative to route count.

**Scars (verified in `.claude/rules/cicatrix-scars.md` + archive):**

- **W99 (2026-07-14) — check≠action in the WR2 font-inject**: 6/9 slides painted in SYSTEM
  font with render green and **critic PASS** — 4/9 of an already-published IG carousel. Root:
  loose check vs strict replace on self-closing `<link/>` skeletons, and the renderer already
  *knew* (`montserrat=false` logged as warning in a 12 MB log). Cures: anchored injection with
  `n==0 → ValueError`, font-load promoted to hard render failure. Lesson for this lane: a
  vision critic is NOT a font/identity gate; identity is proven by `document.fonts.check`, not
  by eye.
- **W96 (2026-07-13) — unisolated tests wrote fixtures into the PRODUCTION WR2 review queue**:
  phantom 1-slide carousels in the Control app from every `pytest` pre-push and a daily cron
  (`Path.home()` defaults in the worker). Four-layer cure incl. queue-hygiene organ.
- **W112 (2026-07-30) — Prettier rewrote scar records**: the formatter as an unreviewed writer
  that judges by FORM — directly relevant to any design-token or doc pipeline where bytes are
  load-bearing.
- **W118 (2026-08-18) — frontend required check killed by a third party**: deepmerge-ts
  advisory published 87 s after the last merge → `npm audit` gate red → matrix fail-fast
  CANCELLED the required `(mouth, true)` leg → 11 h of repo-wide merge freeze with zero red
  checks to point at.
- **Design-loop CI lesson (R4/R5, 2026-08-27)**: the R1 research gate accepts a single seat
  token in `adversarial_review:`; a descriptive panel string turned #5078 red; the fix format
  is now baked into every later round — the loop learned its own compliance format mid-flight.
- **R7 self-catch**: frontmatter panel counts were INVENTED pre-tally twice in the round that
  wrote the doctrine forbidding exactly that — caught and corrected (49/4/0 recomputed).

**The five measured public-surface defects (2026-08-28**, memory
`discovery_five_measured_defects_on_public_surfaces_2026_08_28.md`, all verified this
session):**

1. **`/dream` ejected anonymous visitors**: public page, autosave hits an authenticated
   endpoint, ONE typed character → `login?expired=true&reason=token_expired` (cured PR #5143).
2. **`/chat` bounces from the page itself** (`useChatPage.ts:417`), not middleware (which is
   now `proxy.ts`, domain routing only) — and decides with `api.isAuthenticated()`, which
   reads ONLY localStorage while the app's auth is cookie-primary ⇒ can bounce genuinely
   logged-in users. Verified this session: **18 files** reference `isAuthenticated()` —
   ~13 page/hook gates incl. `/agents`, `/dream`, admin pages, `useCellStatus`.
3. **`/agents` diagnosis RETRACTED** — the gate exists and works; the probe author had read a
   skeleton 200 as "no gate". Method lesson recorded: for client-side gates the only valid
   probe is *where the visitor ends up*.
4. **`/exclusive`**: two-line body + streaming video — intended or unfinished, unowned.
5. **`/prime`**: **expired Google Maps key** (`ExpiredKeyMapError`) — the map IS the page's
   product. Owner: operator[GUI].

Plus, same day and same class: **the visa clock told a 65-day overstayer "Valid until …" and
"0 days from today"** — a `Math.max(0,…)` at `visa/clock/[hash]/page.tsx:77` erased the
overstay; no alarm branch existed. Cured PR #5170 with a dedicated `isOverstay` branch, proven
live by content on the served bundle; the same PR caught a second defect (CTA `source` enum
value nonexistent backend-side ⇒ 422 ⇒ degraded to bare wa.me). And **the magic link is
backend-only**: the OpenAPI contract defines the exchange, the backend mints and emails the
token, but `magic_token` appears nowhere in `apps/mouth/src` and the default base URL points
to the funnel's FIRST page (memory `discovery_the_magic_link_is_backend_only…`, positive
control on the grep included).

**How many of the six would journey tests have caught?** Scored against what a
journey-grade Playwright spec (anonymous context, real typing, console-error listener,
payload-driven states, assertion on final URL) would see: `/dream` ejection YES ·
`/chat` false bounce YES (cookie-primary logged-in journey) · visa-clock overstay YES
(payload with past date) · magic-link dead end YES (email-link journey) · `/prime` Maps key
YES (console `ExpiredKeyMapError` listener) · `/exclusive` PARTIAL (needs a content-mass
assertion, which is a product question). **5 of 6 mechanically catchable; 0 of 6 were caught
by the existing 53 specs** — because those run against a local build with mocked auth and
assert on elements, not on *where an anonymous visitor ends up* in production. The gap is not
test count; it is test *vantage point*.

**Counter-evidence (where the practice already worked)**: the 22 Visa Oracle routes probed
live the same day found ZERO defects — dead-hash pages carry distinct honest copy, the unlock
endpoint fails closed (401, no Set-Cookie) — and the funnel audit's honest accounting of its
own broken tracking predates all of this by four months. The organism's probes are strongest
exactly where the Design Study Loop has been (`MEMORY_VISA_ORACLE.md:75`).

## §3 World SOTA survey

| System / practice | Source | Mechanism | Measured effect | Transfers here? |
|---|---|---|---|---|
| GOV.UK Design System + Service Standard | design-system.service.gov.uk; gov.uk/guidance/government-design-principles (acc. 2026-08-28) | Research-backed patterns for government transactions: question pages, "one thing per page", start pages, check-answers, error recovery; every pattern carries research provenance | Cross-government reuse; the de-facto world reference for form-heavy state services | HIGH — visa/immigration flows are the same genre; the Design Loop already borrowed "Why we ask"/"Not sure?" as *hypotheses* (R2/R4) |
| W3C DTCG Design Tokens Format 2025.10 | designtokens.org/tr/drafts/format; w3.org/community/design-tokens (2025-10-28) | First STABLE token interchange spec ($value/$type/$description JSON), backed by 24+ orgs (Adobe, Google, Figma, NYT…) | 10+ tools already implement; Style Dictionary v4 ships first-class support | HIGH — the cure format for the measured 3-palette drift (§1.4); R4's spec is one `sed` away from DTCG shape |
| Style Dictionary v4 | styledictionary.com/info/dtcg | One token source → CSS vars, Tailwind, JSON, native; build-time translation | Industry default for token distribution | HIGH — fits Tailwind v4 CSS-config already in mouth |
| Chromatic + Storybook visual regression | chromatic.com/docs/visual; chromatic.com/blog/accessibility-testing-is-here | Per-story pixel snapshots on every commit; TurboSnap re-tests only affected components; component-level axe a11y dashboard (2025) | TurboSnap cuts snapshot usage 60–90% | MEDIUM — mouth has no Storybook; the *pattern* (component-level visual+a11y gate) transfers via Playwright screenshots without the SaaS |
| MLLM-as-UI-Judge / PerceptUI / UXBench / CritiqueCrew | arxiv 2510.08783 (Adobe/Berkeley/GaTech, 2025); arxiv 2606.05697; 2606.16262; 2602.01796 | Benchmarks of multimodal LLMs predicting human UI perception; synthetic-user agents; actionability scoring of LLM critiques; multi-role critique orchestration | MLLM judgments correlate with human ratings on some axes, fail on others (fonts, subtle identity) — matches W99 empirically | HIGH — the organism ALREADY runs LLM-as-critic (WR2) and blind perception panels (R6); the research names the failure modes and the fix (structural probes for what vision can't judge) |
| Checkly monitoring-as-code | checklyhq.com/blog/synthetic-monitoring-with-checkly-and-playwright-test; /product/playwright-check-suites | Playwright journeys promoted to PRODUCTION monitors: versioned, code-reviewed, run on schedule + post-deploy, with trace/video artifacts on failure | Full trace/DOM/network artifacts per failure; journeys become SLO probes | VERY HIGH — the exact cure for "0 of 6 defects caught by 53 local specs"; self-hostable pattern (cron + Playwright), no SaaS needed |
| Baymard checkout research | baymard.com/research/checkout-usability (2025–26) | 500+ tested usability issues; benchmark of 60 leading sites | Avg cart abandonment 70.19%; 39% abandon on surprise fees; avg leading site has 39 checkout improvement areas | HIGH — "surprise fees" is literally Q7 (one price, PNBP allowed as state-set line); calibrates the checkout lane (#5099) |
| Stripe checkout guidance + Payment Element | stripe.com/resources/more/checkout-screen-best-practices et al. | Address autocomplete, real-time validation, error messages that never wipe input, locale-aware payment methods | Payment Element users see +11.9% revenue on average (Stripe) | MEDIUM-HIGH — GARUDA checkout is Xendit not Stripe, but the interaction bar transfers verbatim |
| Figma MCP + Code Connect | help.figma.com Guide to Figma MCP; developers.figma.com code-connect-integration (2026-02) | Design frames exposed to coding agents as structured data; Code Connect maps components to the real codebase; generate_figma_design captures live UI back to Figma (Claude Code-exclusive, 2026-02-17) | 14 MCP tools GA; read free | LOW-MEDIUM — no Figma in the estate; the *inverse* insight matters: this organism's "design source of truth" is measured live surfaces + research dossiers, not canvases |
| CUPED variance reduction | statsig.com/perspectives/cuped-reducing-variance-results; growthbook.io/blog/variance-reduction-ab-testing; LA Times case (Medium/GrowthBook) | Use pre-experiment covariates to shrink variance → smaller samples, shorter tests | Up to 85% sample-size reduction in favorable cases | MEDIUM — Bali Zero traffic is small; CUPED (or its Bayesian cousins) is what makes A/B on a low-traffic funnel feasible at all; GrowthBook is OSS/self-hostable (no paid API) |
| Trust-as-conversion-variable research | userintuition.ai trust-ux guide; LogRocket trust-driven UX (2026) | Trust signals closest to the decision moment (pricing clarity, "what happens next", policies) outperform badges; measure trust via field-level drop-off, rage clicks | Transparent pricing beats badge-adding "more reliably" | VERY HIGH — confirms the loop's own R1/R2 findings; adds the missing half: field-level *measurement* |

**The five that matter most.**

1. **Checkly-style monitoring-as-code** is the single highest-leverage transfer. The organism's
   deepest measured UX truth (§2) is that its 53 Playwright specs and its live sentinel all
   probe the wrong vantage point: local builds, element assertions, HTTP codes. The browser
   sweep that found all six defects was a hand-driven one-off. SOTA practice makes that sweep a
   *versioned, scheduled, post-deploy production journey suite* with failure artifacts. The
   organism already owns every ingredient: Playwright, a prodlike config, always-on machines
   (Law 6), a Telegram alert gateway with a P0 budget, and ASSEMBLY-LINE's "synthetic-journey
   probes" clause (`docs/factory/ASSEMBLY-LINE.md:45`) — which is doctrine not yet armed
   (superscar family #2 risk, pre-named).

2. **DTCG 2025.10 + Style Dictionary** arrived at exactly the right moment: the R4 Merah Putih
   spec is already a token contract with computed contrast duties — it is a research document
   one format-shift away from being a machine-readable SSOT that emits the Tailwind v4 CSS
   config, the carousel tokens, and a contrast-law test. No surveyed company has tokens whose
   *provenance is an adversarially-refuted research PR*; the missing piece is only the pipe.

3. **MLLM-as-UI-Judge research** validates and sharpens what WR2 learned by scar: vision models
   correlate with human perception on layout/consistency axes but are unreliable on font
   identity and subtle brand deviation — which is W99 *exactly* (critic PASS on system-font
   slides). SOTA answer: pair the vision critic with structural probes (`document.fonts.check`,
   computed-style assertions) for the axes vision can't judge, and benchmark the critic itself
   against a small human-labeled set (UXBench's "actionability" framing).

4. **GOV.UK Service Standard** remains the reference genre for this product: high-stakes,
   form-heavy, state-adjacent. The Design Loop already treats it correctly (R2 distance map
   scored GOV.UK 2/4 — borrowed with evidence, not idolized). What has NOT been borrowed is the
   *Service Standard's operating rule*: every pattern in the design system cites the user
   research that earned it. The organism's analogue — every token/pattern cites the measured
   ratio or ruling — exists in R4 but not yet as an enforced property of shipped code.

5. **CUPED/GrowthBook** answers the loop's declared blocker: R6 flipped the production default
   to "team-controlled until an A/B with real users decides" — but no experimentation
   infrastructure exists in the estate. On funnel-scale traffic, naive A/B never reaches power;
   variance reduction plus Bayesian sequential analysis is what makes the R6-mandated
   experiment *possible* rather than aspirational. GrowthBook is self-hostable (respects the
   no-paid-API constraint).

## §4 Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Design research & decision process | **AHEAD** | The Design Study Loop (§1.1) has no surveyed equivalent: 8 rounds + 5 build-lane dossiers, every round refuted by a 4-seat cross-family panel, WCAG ratios computed not asserted, evidence-class caps on defect severity, borrow-tags that travel as hypotheses, owner rulings as a formal interface, 15 armed PRs in ~36 h. GOV.UK's research-provenance culture is the nearest analogue — and it doesn't adversarially refute its own rounds or falsify its own "verbatim" quotes (R7 did, 4/5). |
| Editorial design system (WR2/brand cortex) | **AHEAD, with one measured hole** | Constitutional critic with binary verdicts, pixel-level palette checks, NB ground-truth spot-checks of regulatory claims on rendered slides, sha256 anchor anti-reuse, WCAG-annotated token history (`tokens.json:257`) — beyond anything surveyed for social/editorial design. The hole: W99 proved the vision critic cannot judge font identity; the cure (structural font probe as hard render failure) landed for the renderer but the critic itself was never benchmarked against its own failure corpus. |
| Design tokens & cross-surface consistency | **BEHIND** | Measured: 3+ live palettes (§1.4 table), raw hex literals on the home (`page.tsx:76`), the R4 contract unshipped as code, WS1 "token reconciliation, do first" open since 2026-07-19. SOTA just standardized the fix (DTCG 2025.10, Style Dictionary v4). R0's own census said six systems. |
| Journey testing & production UX verification | **BEHIND (the biggest gap)** | 158 routes / 53 specs; **0 of 6** measured 2026-08-28 defects caught by the suite, 5 of 6 mechanically catchable by journey-grade probes (§2). The one probe that worked (types + judges where the visitor ends up) is a manual one-off. ASSEMBLY-LINE mandates synthetic-journey probes (`:45`) — doctrine exists, practice unarmed (family #2). Checkly-class monitoring-as-code is standard practice elsewhere. |
| Funnel, pricing & trust doctrine | **AT→AHEAD** | Q7 one-price ruling + PNBP amendment aligns with Baymard's #1 abandonment trigger (surprise fees, 39%) *before* reading Baymard; trust devices measured in-estate and promoted to identity law (R4 §5); honest CRO audit incl. its own broken tracking (`docs/cro/2026-04-19-funnel-audit.md`). Ahead on doctrine; AT on execution (checkout dossier #5099 designed, not built). |
| Experimentation | **BEHIND** | R6 flipped the production default pending "an A/B with real users" — and there is no experiment infra, no assignment, no CUPED, no pre-registration in the estate (verified: no growthbook/statsig/experiment code in mouth). The ruling created a dependency on a capability that doesn't exist. |
| Accessibility | **AT (split)** | Design-side: contrast computed per token, SC 1.4.11 duties on hairlines, a11y floor in R6 — ahead of typical practice. Code-side: ONE axe spec (`e2e/a11y/workspace-a11y.spec.ts`) for 158 routes; Lighthouse a11y is the sole error-gate (0.9) on 10 URLs. R5b's own panel flagged the missing suite. |
| i18n | **AT** | 5 locales + CI provider lint + a dedicated sponsor-i18n design dossier (#5131); W77's language-axis lesson (guards calibrated EN-only) is institutionalized. No measured locale-parity check (does ID/IT content match EN semantics?) — nobody surveyed does this well either. |
| Performance / CWV | **AT** | Real numbers documented (LCP ~1.2 s, CLS ~0.05, INP needs-improvement), LH CI with 10 URLs ×3 runs, budget assertions — but perf/CWV asserts are `warn`, only a11y `error`s; INP has been "needs improvement" without a closing loop. |
| Component system | **AT** | brand-api catalog (395 lines) + P8 CI gate + shadcn/Tailwind v4 baseline; no per-component visual regression (Chromatic-class), which is exactly where W99-class defects live for the web estate. |

**Honest summary**: the organism is *ahead of SOTA at deciding what the design should be* and
*behind SOTA at knowing what the user actually gets*. Both halves are measured, not felt.

## §5 Beyond-SOTA recommendations (ranked by impact × confidence / cost)

### R1 — Scar-derived Production Journey Sentinels (the vantage-point fix)

- **What**: a versioned suite of ~10 anonymous-visitor Playwright journeys run on cron from
  Pro/Mini against PRODUCTION (not localhost), each asserting (a) where the visitor ends up
  (final URL), (b) zero console errors of named classes (`ExpiredKeyMapError`,
  Sentry envelopes, 4xx on public XHR), (c) content truthfulness for state-driven pages
  (payload-driven: an overstay date must NOT render "Valid until"). Failures route through the
  existing Telegram gateway under the existing P0 budget. Crucially: **every cured UX scar
  becomes a permanent journey** — the /dream ejection, the visa-clock overstay, the magic-link
  dead end are the first three probes, i.e. guilt+innocence discipline (guard-conformance,
  which the organism already runs for hooks) applied to user experience.
- **Why beyond SOTA**: Checkly-class monitoring-as-code exists; *deriving the probe corpus from
  an adversarially-maintained scar ledger* does not. No surveyed system regression-tests its UX
  incidents in production forever. Exploits three organism asymmetries: always-on local
  machines (Law 6), the scar corpus, the P0-budgeted alert gateway.
- **Cost**: ~2 sessions (Sonnet implementer + one refuter pass); zero SaaS.
- **Gear**: 2. **Risk**: family #2 (a sentinel that greens while dead — cure: a seeded-failure
  self-test route that MUST fail, verified per run, exactly like `guard-conformance` guilt
  fixtures); family #8 (network flap → 3-attempt retry per W55); family #4 (journeys must run
  with NO ambient secrets; anonymous context only).
- **Metric**: seeded-regression detection latency. Before: 5/6 defects found only by a manual
  sweep, one (visa-clock class) live for an unknown but weeks-scale period. After: a seeded
  regression of each cured class detected < 24 h. Secondary: % of cured UX scars carrying a
  live probe (0% today).
- **Kill criterion**: >2 false P0s/week after tuning window → demote to daily digest.
- **First PR**: `feat(journeys): production journey sentinels wave 1 — dream, clock, magic-link`
  (new `apps/mouth/e2e/production/*.spec.ts` + `scripts/journey_sentinel.sh` + plist in
  `infra/launchagents/`; ≤400 lines; acceptance = suite red against a replayed pre-#5143 build,
  green against prod, self-test probe fails on demand).

### R2 — Token SSOT with refuted provenance (R4 → DTCG 2025.10 → Style Dictionary)

- **What**: transcribe the R4 Merah Putih contract into a DTCG 2025.10 `tokens.json` at repo
  root of the design domain; Style Dictionary v4 emits (a) Tailwind v4 CSS variables for mouth,
  (b) the carousel token file, (c) a generated contrast table. Each token carries `$description`
  = provenance (the R4 ruling / measured ratio / PR number). A CI tripwire **recomputes every
  contrast ratio the tokens claim** and fails on drift — the contrast law becomes executable.
  Migration is surface-by-surface (funnels first per R4 §6), replacing raw hex literals.
- **Why beyond SOTA**: DTCG + Style Dictionary is SOTA plumbing; *tokens whose provenance
  fields cite adversarially-refuted research PRs, enforced by a ratio-recomputing tripwire* is
  not practiced anywhere surveyed (design tokens everywhere carry values, not evidence).
  Exploits: the Design Loop corpus and the tripwire culture (`test_abstain_threshold_…` class).
- **Cost**: 1 session for the SSOT + tripwire; migration amortized per-surface.
- **Gear**: 2 (SSOT) then 1 per surface. **Risk**: family #9 (two writers, one derived file —
  cure: generated files carry a DO-NOT-EDIT header + a drift check like DOCSYNC/W86); family #3
  (a lint over-matching legitimate one-off hexes — scope it to migrated surfaces only).
- **Metric**: live palettes serving public surfaces 3→1 (measured by the R0 census method);
  raw brand-hex literals in migrated funnel routes (grep count) → 0; contrast-tripwire green on
  every claimed ratio. Baseline greps recorded this session: `#f7f6f2` ×2 in src, copper ×8 in
  globals.css.
- **Kill criterion**: if migration of the first surface breaks visual parity (screenshot diff),
  stop and re-scope to new-code-only.
- **First PR**: `feat(design-tokens): Merah Putih DTCG source + contrast tripwire` (tokens file
  + `scripts/check_token_contrast.py` + CI job; NO surface migration yet; ≤400 lines;
  acceptance = tripwire red when any `$value` edited to a failing hex, green on spec).

### R3 — Critic conformance: benchmark the design gates against their own history

- **What**: extend the guard-conformance idea (every guard proves guilt AND innocence) to
  DESIGN gates. Build a labeled corpus from what already exists: the 64 past carousels, the
  W99 failing slides (system-font renders), the R6 blind-panel outputs. The WR2 critic — and
  any future web visual critic — must, in CI, (a) FAIL the known-bad artifacts, (b) PASS the
  known-good, (c) route font/identity checks through structural probes (`document.fonts.check`,
  computed styles) instead of vision. Publish the critic's confusion matrix per rubric.
- **Why beyond SOTA**: MLLM-as-UI-Judge (arXiv 2510.08783) benchmarks *models*; nobody
  surveyed continuously benchmarks *their own production design critic* against their own
  incident corpus. Exploits: the scar corpus + 64-carousel archive + an LLM fleet whose
  critics are cheap to re-run.
- **Cost**: 1 session; corpus already on disk.
- **Gear**: 2. **Risk**: family #6 (the benchmark labels themselves must be verified renders,
  not remembered verdicts — re-render from archived HTML where possible); family #2 (the
  conformance job must run somewhere required, not a `continue-on-error` sweep — W108 lesson).
- **Metric**: critic false-PASS rate on W99-class seeded defects: 100% then (it passed the
  published carousel) → 0% on the seeded corpus; false-FAIL on known-good ≤5%.
- **Kill criterion**: if the corpus can't reach 20 labeled artifacts, fold into R1's probes.
- **First PR**: `feat(wr2): critic conformance corpus + font structural probe` (fixtures dir +
  runner + CI job; ≤400 lines).

### R4 — One auth predicate, journey-proven (kill the localStorage ghost)

- **What**: replace the 13 page/hook gates reading `api.isAuthenticated()` (localStorage-only,
  verified 18 referencing files) with one cookie-primary session predicate (server component or
  `/api/session` probe), shipped WITH the R1 journeys that prove both directions: an anonymous
  visitor lands on login with honest copy (never `expired=true` — the /dream lesson), and a
  cookie-only authenticated visitor is NOT bounced (the /chat lesson).
- **Why beyond SOTA it isn't** — this is catch-up to the organism's own SSO doctrine
  (`apps/mouth/CLAUDE.md`: cookie on `.balizero.com` is the auth). It ranks this high because
  every gate above it (R1) would otherwise keep re-detecting the same class. Honest label:
  SOTA-completion, prerequisite to beyond.
- **Cost**: 1 session. **Gear**: 2. **Risk**: family #3 (an over-strict predicate bouncing
  legitimate sessions — the journey pair IS the guilt+innocence test); staged rollout
  page-by-page.
- **Metric**: false-bounce journey (cookie-only session → /chat) passes; gates reading
  localStorage-only: 13 → 0 (grep-measurable).
- **Kill criterion**: any increase in real login-loop reports → revert page flag.
- **First PR**: `fix(auth-ux): cookie-primary session predicate + chat/dream journeys`
  (predicate + 2 gates migrated + 2 journeys; ≤400 lines).

### R5 — Hypothesis-carrying experimentation (GrowthBook + CUPED on the funnel)

- **What**: self-hosted GrowthBook (OSS, no paid API) on the existing Postgres; assignment via
  edge middleware on funnel routes; CUPED using pre-exposure covariates (traffic source,
  landing page, device) — the practical floor that makes low-traffic A/B decidable. The
  beyond-SOTA composition: **experiment cards are generated from the Design Loop's borrow-tags**
  — every R2 "borrow" hypothesis (progress "question X of Y", price-before-form, why-we-ask
  placement) becomes a pre-registered card whose hypothesis text cites the loop dossier, and
  whose result is written BACK into the dossier as evidence-class upgrade (hypothesis →
  measured). The R6 ruling ("production default decided by A/B") becomes executable.
- **Why beyond SOTA**: platforms run experiments; none close the loop research-dossier →
  pre-registered card → result → dossier evidence-class. Exploits: the loop's evidence-class
  discipline + rulings interface.
- **Cost**: 2-3 sessions infra + per-experiment marginal ~0. **Gear**: 3 (touches production
  traffic + analytics surface). **Risk**: family #2 (assignment silently broken → SRM check as
  a required probe); PII boundary (Law 2): assignment IDs only, no client PII in the
  experiment store — and consent surface per the consent-placement dossier (#5104).
- **Metric**: MDE achievable at current funnel traffic with vs without CUPED (compute at setup;
  literature: up to 85% sample reduction); time-to-decision on the R6 default question (∞ today
  — no infra — → a dated answer).
- **Kill criterion**: if SRM fails twice or traffic can't power even CUPED-assisted tests at
  MDE ≤10% relative, park experiments and default to sequential cohort comparisons (declared,
  not silent).
- **Needs-ruling**: running experiments on real prospective clients + the consent copy (Legge 5
  — §7).

### R6 — Journey-gate for new public routes (arm the ASSEMBLY-LINE clause)

- **What**: a PR gate (sentinel-pattern, W69-proofed like `p8-brand-api.yml`) requiring any NEW
  route under public segments to declare a journey spec naming: entry, the anonymous final-URL
  expectation, console-error budget, and the state-truth invariant if payload-driven. Existing
  routes grandfathered via a monotone registry (the tg-gateway `grandfathered.json` pattern —
  with the W109b two-PR coupling caveat documented in the file header).
- **Why beyond SOTA**: journey-tests-red-first exists as doctrine here and as practice at
  GOV.UK-class orgs; *enforcing it as a monotone-shrinking CI registry* wired to the same
  suite that runs in production (R1) is the composition no one surveyed has.
- **Cost**: 1 session. **Gear**: 2. **Risk**: family #3 (over-match on non-page routes — scope
  by `page.tsx` under public segments only); family #9 (registry coupling).
- **Metric**: journey coverage of NEW public routes = 100% enforced; overall coverage ratio
  (53 specs/158 routes today) trending up, reported per PR.
- **Kill criterion**: if the gate blocks >2 innocent PRs in a month (W102-class), demote to
  advisory for one cycle and fix the enumerator.

## §6 90-day roadmap (3 waves) + first PRs

**Wave 1 (days 1–21) — see what the visitor sees.** R1 wave-1 journeys (dream/clock/magic-link
+ self-test) · R4 auth predicate + chat/dream journey pair · `/prime` Maps key (operator[GUI],
§7). Exit metric: every 2026-08-28 defect class carries a live production probe; seeded
regressions detected <24 h.

**Wave 2 (days 22–50) — one identity, executable.** R2 token SSOT + contrast tripwire, then
funnel-surface migration (R4 §6 order) · R3 critic conformance corpus · R6 journey-gate armed
sentinel-pattern. Exit: palettes 3→1 on funnels; critic false-PASS 0% on seeded corpus; gate
green on an innocent PR and red on a route without a journey (guilt+innocence proven).

**Wave 3 (days 51–90) — measure what converts.** R5 GrowthBook+CUPED infra (post-ruling) ·
first pre-registered card = R6's production-default question · borrow-tag→card generator ·
close INP ("needs improvement" in `docs/FRONTEND_PERFORMANCE_GUIDE.md`) by promoting LH
perf asserts from warn to error on the 3 funnel URLs once green locally.

First PRs: exactly the six named per-recommendation in §5 (each ≤400 lines, one concern,
acceptance tests stated there).

## §7 Needs-ruling (Legge 5 / credentials / GUI)

1. **`/prime` Google Maps key expired** — operator[GUI], Google console. The map is the page's
   product; no code path fixes a credential.
2. **`/dream` public or gated?** — open product question recorded in the 5-defects memory; the
   401 cure removed the ejection, not the ambiguity.
3. **`/exclusive` two-line body + streaming video** — intended minimalism or unfinished? Unowned.
4. **VOA dark state**: is a bare 404 body the right dark state for the flagship product page if
   anything external links it? (Already flagged to Zero in the 5-defects memory.)
5. **R5 experiments on real prospective clients** + consent copy/placement (builds on dossier
   #5104) + any analytics identifier policy under Law 2.
6. **`/visa/match` investor >500M → E33G ("remote worker")** — domain misroute, owner Zero per
   `MEMORY_VISA_ORACLE.md:87`.

## §8 Meta-pattern (Gear 3)

One defective belief generates nearly every finding: **"verify at the surface I control, and
call it the experience."** The critic judged renders it could see and passed fonts it couldn't
(W99). The e2e suite judged a localhost build with mocked auth and missed six production
defects. `Math.max(0,…)` clamped an overstay into "Valid until" — the code verified a number,
not a situation. The magic link was verified emitted, never consumed. The tokens were agreed in
a refuted research PR and left as hex literals in code. Even the probe author fell to it twice
(reading a skeleton 200 as "no gate"; carrying an unread `textHead`). The organism's own
doctrine already states the inversion — ASSEMBLY-LINE: DONE = *a customer journey working in
production* — so this is not missing knowledge; it is superscar family #2 operating at the
craft level: **doctrine exists, vantage point unarmed.** Every recommendation in §5 is the same
move applied to a different organ: relocate the judge to where the visitor stands, then prove
the judge itself with guilt+innocence — the discipline the organism already trusts for hooks,
extended to experience.

## §9 Sources

1. GOV.UK Design System — https://design-system.service.gov.uk/ (acc. 2026-08-28) — the
   reference design system for government/high-stakes form services; research-provenanced patterns.
2. GOV.UK question pages pattern — https://design-system.service.gov.uk/patterns/question-pages/
   (2026-08-28) — "one thing per page" primary source.
3. UK Government Design Principles — https://www.gov.uk/guidance/government-design-principles
   (2026-08-28) — the operating culture behind the system.
4. DTCG Design Tokens Format Module 2025.10 — https://www.designtokens.org/tr/drafts/format/
   (2026-08-28) — the first stable token spec; interchange target for R2.
5. DTCG stability announcement — https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/
   (2025-10-28) — 24+ backing orgs; production-ready status.
6. Style Dictionary × DTCG — https://styledictionary.com/info/dtcg/ (2026-08-28) — v4
   first-class DTCG support; the emit tool for R2.
7. Chromatic visual tests docs — https://www.chromatic.com/docs/visual/ (2026-08-28) —
   per-story snapshot mechanics; TurboSnap 60–90% usage reduction.
8. Chromatic accessibility testing launch — https://www.chromatic.com/blog/accessibility-testing-is-here/
   (2025) — component-level axe as a gate; pattern for R3/R6.
9. MLLM as a UI Judge (Adobe/UC Berkeley/GaTech) — https://www.alphaxiv.org/overview/2510.08783
   (2025) — benchmark of multimodal LLMs predicting human UI perception; names the W99 failure class.
10. PerceptUI: LLM agents as synthetic users — https://arxiv.org/html/2606.05697v1 (2026) —
    human-aligned synthetic-user evaluation; grounding for critic conformance.
11. UXBench (actionability of LLM UX critiques) — https://arxiv.org/pdf/2606.16262 (2026) —
    scoring critiques, not just verdicts.
12. Checkly: why Playwright for synthetic monitoring —
    https://www.checklyhq.com/blog/synthetic-monitoring-with-checkly-and-playwright-test/
    (2026-08-28) — monitoring-as-code mechanics; failure artifacts; the R1 pattern.
13. Baymard checkout usability research — https://baymard.com/research/checkout-usability
    (2026-08-28) — 70.19% avg abandonment; surprise fees 39%; calibrates Q7 and lane #5099.
14. Stripe checkout best practices — https://stripe.com/resources/more/checkout-screen-best-practices
    (2026-08-28) — official interaction bar (validation, error recovery, +11.9% Payment
    Element revenue claim).
15. Statsig on CUPED — https://www.statsig.com/perspectives/cuped-reducing-variance-results
    (2026-08-28) — variance-reduction mechanism and planning implications.
16. GrowthBook variance reduction (+ LA Times case) —
    https://www.growthbook.io/blog/variance-reduction-ab-testing (2026-08-28) — OSS,
    self-hostable platform; CUPED sample-size reductions up to 85% in favorable cases.
17. Figma MCP server guide + Code Connect —
    https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server
    (2026-08-28) — where mainstream design-to-code is going; contrast case for §3.
18. Trust UX reference (proof, guarantees, risk) —
    https://www.userintuition.ai/reference-guides/trust-ux-proof-guarantees-and-signals-that-reduce-risk
    (2026-08-28) — decision-moment trust signals; field-level trust measurement.
