---
panel: beyond-sota-xfamily
lane: 11-product-ux-visual-design
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T19:08:48Z
finished: 2026-08-28T19:20:59Z
duration_s: 731
exit: 0
words: 5842
prompt_sha256_16: dfa0ec53cd02ebd0
prompt_chars: 18316
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 11/13 — Product, UX & visual design craft
model: OpenAI GPT-5.6 sol at reasoning effort ULTRA (pinned lane)
sources: 12
repo_files_verified: 40
status: complete
---

## 0. TL;DR

Nuzantara is **ahead of SOTA in design investigation and cross-family critique**, but **behind SOTA in turning design promises into continuously executable user-journey contracts**.
Its strongest asset is the GARUDA/Visa Oracle Design Study Loop: measured census, heuristic autopsy, identity specification, prototypes, runtime probes, independent refuters, and explicit promotion boundaries.
Its biggest gap is receptor coverage: 158 page routes face only 53 E2E specification files, while advisory suites, localStorage-only authentication predicates, stale token references, and failure-only screenshots allow serious public defects to escape.
Top move 1: build a scar-derived Journey Contract Graph covering anonymous, cookie-only, expired, multilingual, zoomed, reduced-motion, and degraded-network states.
Top move 2: compile editorial and product tokens from a typed federated contract, preserving surface differences while eliminating dead references and undeclared literals.
Top move 3: replace critic-first visual QA with deterministic-first perception gates—fonts, assets, overflow, accessibility, locale expansion, console/network integrity, and screenshot diffs—then use an LLM only for residual judgment.
All three exploit assets unusual even among SOTA organizations: a measured scar corpus, full-lifecycle ownership, cross-family flat-subscription seats, local always-on machines, and hooks capable of turning each escaped defect into an executable antibody.

## 1. How Nuzantara does it today

### 1.1 A serious design-study discipline exists

The GARUDA/Visa Oracle study is not a mood-board exercise. Its R0 stage measures the live DOM, Playwright output, and repository token sources before making aesthetic judgments; it also records blind spots such as unmeasured email output and the absence of recent WR2 examples beyond the historical corpus (`research/design/2026-08-27-r0-censimento-superfici-design-system-di-fatto.md`).

The subsequent stages form a coherent study loop:

- R3 applies Nielsen, Stanford/Fogg, and government-service heuristics and records a severity-ranked defect inventory rather than merely proposing a restyle (`research/design/2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md`).
- R4 defines identity, contrast, typography, motion, form behavior, pricing honesty, human handoff, responsive targets, keyboard behavior, live regions, and reduced-motion expectations (`research/design/2026-08-27-r4-identity-merah-putih-token-spec.md`).
- R6 runs eight Chromium probes at 360×640: seven passed and one failed because fixed `16px` root typography prevented effective 200% text zoom. It also explicitly leaves VoiceOver timing, mobile soft keyboards, and physical fold behavior outside the headless proof boundary (`research/design/2026-08-27-r6-walkthrough-perception-runtime.md`).
- R7 closes the loop with generator≠grader, four reviewer families, real-user promotion boundaries, and a residual backlog. It reports 337 derived findings across R3–R7 and refuses to let LLM preference tests promote high-stakes identity choices without real-user evidence (`research/design/2026-08-27-r7-doctrine-loop-closure.md`).

That is unusually rigorous. The core loop records ten PRs at its R7 checkpoint, with later repository history showing additional follow-ons. The prompt’s exact “15 PR” count depends on an external memory document that this lane was forbidden to read, so it cannot be independently certified here.

The product mandate is similarly concrete: a user should understand the offer within ten seconds, buy within five minutes, and track progress like a parcel; paid orders and conversion are primary metrics, while wrong advice and operational quality are guardrails (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`). The factory doctrine requires journey state machines, happy/failure/recovery paths, journey specifications written red-first by a non-builder, dark release, and staged real-buyer proof (`docs/factory/ASSEMBLY-LINE.md`).

### 1.2 The brand cortex is rich, but product-token governance is fragmented

The repository brand skill is a genuine cortex: it defines a closed surface taxonomy, loads a constitution, tokens and forbidden phrases, selects layouts, and exposes a corpus of 64 previous carousels (`skills/bali-zero-brand/SKILL.md`). Its editorial palette is intentionally narrow—anthracite, black, white, yellow and red—with explicit prohibitions against green, blue, purple, pastel and beige in that surface (`skills/bali-zero-brand/tokens.json`, `skills/bali-zero-brand/SKILL.md`).

The product application has a different and legitimate need. Core tokens provide red, gold, cyan, green, purple and neutral primitives; semantic funnel and state roles; light/dark operational surfaces; chart colors; motion aliases; and reduced-motion behavior (`packages/core/tokens/primitives.css`, `packages/core/tokens/semantic.css`, `packages/core/tokens/operative.css`).

The problem is not that the editorial and operational palettes differ. The problem is that their relationship is not compiled or proven. The brand skill directs `web-mouth` consumers to `packages/core/styles/bz-tokens.css`, which does not exist; the current files live under `packages/core/tokens/` (`skills/bali-zero-brand/SKILL.md`). The design census found six coexisting systems, multiple greens and multiple visa accents, and an earlier second token SSOT whose disappearance was not traceable (`research/design/2026-08-27-r0-censimento-superfici-design-system-di-fatto.md`). A current scan also found 28 hardcoded hexadecimal occurrences under `apps/mouth/src/app/(workspace)`. That count is an indicator rather than proof that every literal is wrong, but it demonstrates that token lineage is not closed.

The unified-surfaces plan already understood the issue: it distinguishes warm-paper editorial identity from an eight-hour operational UI, calls for merging or deprecating competing SSOTs, targets zero hardcoded hex values, and sets a Lighthouse accessibility floor of 95 (`docs/design/2026-07-19-garuda-os-unified-surfaces/PLAN.md`).

### 1.3 WR2/WR3 have stronger creative orchestration than the product frontend has journey orchestration

WR2 uses a clear specialist chain: the design architect loads the cortex and delegates grounding, storyboard, layout and criticism; it requires fresh imagery, explicit asset provenance, structured artifacts, and no silent reuse (`.claude/agents/wr2-design-architect.md`). The critic evaluates palette, typography, copy, images and empirical performance, reads the final PDF rather than trusting intermediate PNGs, and verifies hashes and citations (`.claude/agents/wr2-critic.md`). The inventories under `docs/wr2/` and `docs/wr3/` show similarly explicit agent contracts and runbooks.

That architecture is stronger than a single generative-design prompt. It separates narrative, composition, production and grading. Its limit is that a visual critic is still probabilistic: W99 proves that a critic can approve an artifact whose deterministic font telemetry already says the required font is absent.

### 1.4 The frontend has substantial tooling but uneven product coverage

`apps/mouth` is a modern Next.js 16.3.1 and React 19.2.8 application with Tailwind 4, Radix primitives, Playwright 1.62.1, axe-core 4.13, Lighthouse 13 and `web-vitals` 6.1 (`apps/mouth/package.json`). The generated component catalog records 32 components and includes high-value service primitives such as `AppWizard`, `AppTrustStrip`, `AppWhatsAppCTA`, `FunnelFrame` and `TrustBand` (`docs/design/components-catalog.md`).

The catalog, however, is an API inventory rather than a complete design-system workbench. It does not provide rendered states, visual baselines, accessibility guarantees, usage prevalence, locale expansion, or interactive behavior. A duplicate `actions` property in the generated `CommandPalette` entry is also a small sign that catalog generation itself needs validation (`docs/design/components-catalog.md`).

The production-like Playwright configuration covers Chromium, Firefox, WebKit and Pixel 5, uses first-retry traces, and retains failure evidence (`apps/mouth/playwright.config.ts`). The portal-specific configuration performs strict preflight/build/start checks across four browsers, but disables screenshot, video and trace capture (`apps/mouth/playwright.prodlike.config.ts`).

The measured route-to-test inventory is:

| Inventory | Count | Interpretation |
|---|---:|---|
| `apps/mouth/src/app/**/page.tsx` | 158 | User-facing route implementation count |
| `apps/mouth/e2e/**/*.spec.ts` | 53 | E2E specification-file count |
| Crude density | 0.34 specs/route | Useful warning signal, not route coverage |

A spec may cover several routes or no complete journey, so 0.34 must not be presented as 34% coverage. It does show that route count alone cannot demonstrate journey protection.

The existing tests contain valuable islands:

- `apps/mouth/e2e/visa-funnel-fusion.spec.ts` covers a happy path, an abstention-to-WhatsApp path, and a subdomain redirect, although one environmental condition can skip the redirect case.
- `apps/mouth/e2e/portal-prodlike-smoke.spec.ts` proves a full magic-link journey and single-use behavior.
- `apps/mouth/e2e/a11y/workspace-a11y.spec.ts` scans 13 workspace routes, but only against WCAG 2.1 A/AA and only blocks serious or critical axe findings. It skips heavy routes and tolerates a failed bootstrap wait before scanning.

The CI receptors are similarly partial. Lighthouse runs on ten primarily marketing/funnel URLs, desktop-only, with performance at 0.85 as a warning, accessibility at 0.90 as an error, and Core Web Vital budgets mostly warnings (`.github/workflows/lighthouse.yml`, `apps/mouth/.lighthouserc.json`). The brand API workflow is stronger: it regenerates the catalog, lints tokens and runs scoped tests (`.github/workflows/p8-brand-api.yml`). The i18n workflow protects provider integrity but does not prove key completeness, pseudo-locale expansion, or end-to-end language continuity (`.github/workflows/lint-i18n-providers.yml`).

### 1.5 Multilingual, accessibility and field evidence are not yet closed loops

Five locale catalogs exist—English, Indonesian, Italian, French and Russian—under `apps/mouth/src/i18n/locales/`. Yet the R6 prototype had a disabled Indonesian toggle and an English-only delegate flow, demonstrating that locale files do not prove a multilingual journey (`research/design/2026-08-27-r6-walkthrough-perception-runtime.md`).

The performance guide reports approximately 1.2-second LCP, 0.05 CLS and INP below 500 milliseconds, but it was last updated in January 2026 and the reviewed repository evidence did not include raw field artifacts supporting those values (`docs/FRONTEND_PERFORMANCE_GUIDE.md`). INP below 500 milliseconds is also weaker than the current “good” threshold of 200 milliseconds.

Historically, the CRO audit reported only two website leads over 90 days against 420 WhatsApp leads, zero attributable funnel conversions, untracked CTAs, generic trust signals, pricing discontinuity, and a technology-startup presentation that could disorient high-trust buyers (`docs/cro/2026-04-19-funnel-audit.md`). This is an April baseline, not a claim about August’s current conversion rate. R3 still records the underlying measurement gap: no per-question analytics and unresolved evidence around price, progress, named human handoff, uploads and mobile payment conditions (`research/design/2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md`).

### 1.6 The five public defect classes were journey-testable

The forbidden `MEM:` files were unavailable under this lane’s snapshot-only contract. Repository code and history nevertheless verify five relevant defect classes:

1. Anonymous users could be ejected from a public surface when a 401 was interpreted as an expired session (`apps/mouth/src/app/(workspace)/layout.tsx`, `apps/mouth/src/app/dream/page.tsx`, `apps/mouth/src/lib/api/client.ts`).
2. A past visa expiry could produce a false-valid clock state before a targeted regression was added (`apps/mouth/src/app/visa/clock/[hash]/page.tsx` and its colocated test).
3. Authentication remains partly dependent on a token-local `isAuthenticated()` predicate: the current snapshot has 11 references, while portal behavior also has cookie-aware fallback (`apps/mouth/src/lib/api/client.ts`, `apps/mouth/src/app/(workspace)/layout.tsx`).
4. Magic-link frontend consumption is now covered as a complete, single-use journey, indicating that the historical missing-consumer defect has been closed (`apps/mouth/e2e/portal-prodlike-smoke.spec.ts`).
5. Public-surface integrity failures have included invented metadata, dead third-party assets and guessed article covers; current resolver tests and `apps/mouth/src/lib/blog/articles.ts` represent the corrective layer.

All five are catchable by explicit contracts: anonymous persona; past-date metamorphism; cookie-only persona; token-consumption journey; and zero broken asset/console/network invariants. The issue was not theoretical testability. The issue was the absence of one systematic public-surface matrix before the live sweep.

## 2. Scars & ledger evidence in this area

| Evidence | What actually failed | Recurrence and implication |
|---|---|---|
| W99, `.claude/rules/cicatrix-scars.md` | Six of nine bike slides and four of nine already-published revenue slides used a system font while rendering and critic review were green. Telemetry already contained `montserrat=false`, but it was only a warning. | At least ten slides across two outputs: a repeated family, not one corrupt file. Deterministic typography checks outperform aesthetic confidence. |
| Superscar family #2, `.claude/rules/cicatrix-superscar.md` | “Exists” or “ran” was mistaken for “armed and consequential.” | Directly explains advisory E2E, warning-only Lighthouse budgets, locale files without locale journeys, and token declarations without consumers. |
| Visa Oracle full-stack row, `.claude/skills/modus/PENDING-ARMS.md` | Thirty jobs produced 13 failures, 17 skips and zero successes while `continue-on-error` allowed the parent result to remain green. | Strong evidence of receptor theater: the journey suite existed but could not block promotion. |
| Privacy-shaped declaration row, `.claude/skills/modus/PENDING-ARMS.md` | `sensitive:` appeared 56 times in the Visa Oracle tree without a consumer or test. | A declarative product property had no runtime effect; this is superscar #2 with potential #9 schema drift. |
| WR2 arming row, `.claude/skills/modus/PENDING-ARMS.md` | The WR2 arming chain later produced eight verified PNGs and closed its ledger item. | Demonstrates that the organism can convert a creative pipeline into evidence when the output contract is explicit. |
| AMENDMENTS drift, `.claude/skills/modus/AMENDMENTS.md` | A still-PROPOSED amendment reached live prompts and introduced four accessibility rules conflicting with the constitution. Adversarial review caught and unwired it. | Governance state was not mechanically coupled to runtime state; superscar #9. |
| Empty amendment windows, `.claude/skills/modus/AMENDMENTS.md` | Repeated windows had zero entries despite active product mandates. | Recognition existed without a receptor that converted observations into queued learning. |
| Design-system census, `research/design/2026-08-27-r0-censimento-superfici-design-system-di-fatto.md` | Six systems, multiple greens, multiple visa accents, and an untraced token-SSOT removal. | The recurring failure is not lack of design taste; it is uncompiled authority and lineage. |
| Runtime walkthrough, `research/design/2026-08-27-r6-walkthrough-perception-runtime.md` | Seven of eight probes passed; 200% text zoom failed. | Independent runtime inspection found a defect that static design review could easily miss. |
| Historic CRO audit, `docs/cro/2026-04-19-funnel-audit.md` | Two website leads in 90 days versus 420 WhatsApp leads, no attributable conversions, untracked CTA behavior. | Historic but material evidence that visual completeness and commercial usefulness were decoupled. |

The lexical count of `journey|mouth|design` in `.claude/skills/modus/PENDING-ARMS.md` is 250 mentions. It is not 250 open tasks and must not be reported as such. It does show that product experience is a recurring organism-level concern rather than a one-off redesign.

The strongest pattern across the evidence is deterministic weakness beneath sophisticated judgment. Nuzantara already possesses strong design critics, cross-family dissent and unusually good reflective documents. What repeatedly bites is a warning, declaration, proposed state, generated catalog or advisory job that is mistaken for an enforced user contract.

## 3. World SOTA survey

| System or practice | Primary source | Mechanism that makes it best-in-class | Published effect | Transfer to Nuzantara |
|---|---|---|---|---|
| GOV.UK Service Standard | [Make the service simple to use](https://www.gov.uk/service-manual/service-standard/point-4-make-the-service-simple-to-use) | Tests the entire online/offline service with actual and potential users across devices, not isolated screens. | No universal effect size claimed. | Direct analogue for visa journeys spanning web, WhatsApp, payment and human operations. |
| GOV.UK form structure | [Structuring forms](https://www.gov.uk/service-manual/design/form-structure) | One primary question per page, logical ordering, easy recovery and per-question analytics. | No single conversion statistic claimed. | Maps directly to Visa Oracle progress, abandonment and error instrumentation. |
| USWDS | [Design principles](https://designsystem.digital.gov/design-principles/) | Starts with real users; treats accessibility, comprehension, key tasks, keyboard and screen readers as system properties. | No single effect size claimed. | Suitable quality bar for a high-stakes public service, including less digitally fluent users. |
| WCAG 2.2 | [W3C Recommendation](https://www.w3.org/TR/WCAG22/) | Adds focus visibility, target-size, consistent-help, redundant-entry and accessible-authentication requirements; evaluates complete processes. | Normative standard, not an experiment. | Upgrade current WCAG 2.1/serious-only scans and test complete purchase/advice processes. |
| DTCG | [Design Tokens Format 2025.10](https://www.designtokens.org/tr/2025.10/format/) | Typed values, aliases, groups and explicit resolution/error semantics enable interoperable compilation. | Standardization effect, not a published conversion number. | Can federate editorial and operational namespaces without falsely forcing one palette. |
| Storybook | [UI testing documentation](https://storybook.js.org/docs/writing-tests) | Component states become browser-executable stories supporting interaction, accessibility and visual tests. | No universal effect size claimed. | Replaces the static 32-component catalog with executable local state coverage. |
| Figma Code Connect | [Official developer documentation](https://developers.figma.com/docs/code-connect/) | Links design components to real production implementations and exposes true code references to humans and agents. | No universal effect size claimed. | The mechanism is valuable, but paid-plan dependency requires a ruling; a local manifest can reproduce most lineage value. |
| web.dev Core Web Vitals | [Defining thresholds](https://web.dev/articles/defining-core-web-vitals-thresholds) | Uses field distributions and the 75th percentile: LCP ≤2.5s, INP ≤200ms, CLS ≤0.1. | Thresholds were selected from web-scale empirical distributions. | Replace stale document-level numbers with route/persona/locale field evidence. |
| Stripe Optimized Checkout | [Optimized Checkout Suite](https://stripe.com/newsroom/news/optimized-checkout-suite) | Dynamically selects relevant payment methods using large-scale transaction evidence and removes payment friction. | Stripe reports up to 10.5% revenue improvement for migrations and a 3% authorization lift for River Island. | Transfer adaptive simplicity and payment relevance, not Stripe’s data scale or unsupported claims. |
| Baymard checkout research | [2024 checkout research](https://baymard.com/blog/checkout-2024-launch) | More than 4,000 research hours, 200+ think-aloud sessions, 1,350+ observed issues and 110+ evidence-based guidelines. | Publishes research scale and issue prevalence rather than one universal lift. | Validates focus on field clarity, recovery and trust fundamentals over decorative novelty. |
| VisualWebArena | [ACL 2024 paper](https://aclanthology.org/2024.acl-long.50/) | Evaluates agents on 910 visually grounded tasks in realistic websites. | Best evaluated model achieved 16.4% versus 88.7% for humans. | Strong warning against allowing an LLM visual critic to be the sole product gate. |
| CUPED | [Microsoft Research variance-reduction review](https://www.microsoft.com/en-us/research/articles/deep-dive-into-variance-reduction/) | Uses pre-experiment covariates to reduce estimator variance and increase experimental power without simply buying more traffic. | Reported as effectively multiplying experimental traffic/power; effect depends on covariate correlation. | Valuable for a low-volume funnel only after consent, event correctness and a sufficient experimental population exist. |

### The practices that matter most

**Whole-service testing is the closest external analogue.** GOV.UK’s unit of design is not the screen but the service, including offline and assisted channels. Nuzantara’s case-code and WhatsApp thinking points in the same direction, but current tests remain clustered around individual surfaces. The decisive transfer is to make “web answer → payment → receipt → human handoff → status” one testable contract.

**Design-system SOTA is executable, not documentary.** DTCG, Storybook and Code Connect solve different parts of the same problem: semantic authority, rendered behavioral states and design-to-code lineage. Nuzantara has each ingredient in partial form—tokens, a generated catalog, Playwright and a brand cortex—but not the compiled connection.

**A visual model must remain a refuter, not the final truth source.** VisualWebArena’s human/model gap and Nuzantara’s own W99 converge on the same conclusion. A model is useful for hierarchy, tone and semantic awkwardness; fonts, assets, contrast, overflow, focus order and network integrity should be deterministic.

**Conversion optimization must begin with evidence quality.** Stripe’s scale cannot be copied, and CUPED cannot rescue missing or semantically wrong events. For Nuzantara, the first SOTA move is not an A/B platform—it is a consented event contract that distinguishes qualified completion, wrong advice, human escalation, payment failure and operational fulfillment.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Design discovery and synthesis | **AHEAD** | R0–R7 combine live census, heuristic study, identity specification, prototype, runtime probes, cross-family review and explicit promotion boundaries (`research/design/2026-08-27-r7-doctrine-loop-closure.md`). |
| Editorial orchestration | **AHEAD** | WR2 separates grounding, story, layout and criticism and tracks asset provenance (`.claude/agents/wr2-design-architect.md`, `.claude/agents/wr2-critic.md`). |
| Deterministic editorial QA | **BEHIND** | W99 allowed ten wrong-font slides across two outputs despite green render and critic verdict (`.claude/rules/cicatrix-scars.md`). |
| Token design | **AT** conceptually | Editorial and operational surfaces deliberately have different semantic needs and both have structured token definitions (`skills/bali-zero-brand/tokens.json`, `packages/core/tokens/`). |
| Token governance and lineage | **BEHIND** | The cortex references a nonexistent token path; six systems and untraced SSOT removal were found; 28 workspace hex literals remain (`skills/bali-zero-brand/SKILL.md`, `research/design/2026-08-27-r0-censimento-superfici-design-system-di-fatto.md`). |
| Component catalog | **BEHIND** | Thirty-two generated API entries exist, but rendered states, a11y contracts, locale expansion and visual baselines do not (`docs/design/components-catalog.md`). |
| Journey specification | **BEHIND** | Doctrine requires red-first journeys, but the live inventory is 158 page routes versus 53 E2E spec files, and a 30-job advisory smoke reported zero success (`docs/factory/ASSEMBLY-LINE.md`, `.claude/skills/modus/PENDING-ARMS.md`). |
| Accessibility | **BEHIND** live SOTA | The main scan targets WCAG 2.1 and blocks only serious/critical findings across 13 routes; R6 independently caught broken 200% text zoom (`apps/mouth/e2e/a11y/workspace-a11y.spec.ts`, `research/design/2026-08-27-r6-walkthrough-perception-runtime.md`). |
| Internationalization | **BEHIND** | Five catalogs exist, but provider lint does not prove completeness and the prototype contained a disabled Indonesian path (`apps/mouth/src/i18n/locales/`, `.github/workflows/lint-i18n-providers.yml`, `research/design/2026-08-27-r6-walkthrough-perception-runtime.md`). |
| Visual regression | **BEHIND** | General Playwright captures failure evidence but no comprehensive component-state baselines; the portal configuration disables screenshots and traces (`apps/mouth/playwright.config.ts`, `apps/mouth/playwright.prodlike.config.ts`). |
| Performance proof | **BEHIND** | Lighthouse scope is ten desktop URLs with several warning-only budgets; documented CWV numbers are stale and not backed by reviewed raw field artifacts (`.github/workflows/lighthouse.yml`, `docs/FRONTEND_PERFORMANCE_GUIDE.md`). |
| High-stakes trust design | **AT**, approaching ahead | Case codes, honesty devices, human handoff and price/risk clarity are explicitly designed, but missing-price and named-human defects remain in the backlog (`research/design/2026-08-28-case-code-design.md`, `research/design/2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md`). |
| Conversion evidence | **BEHIND** | The last verified audit found negligible attributable web conversion and no per-question analytics (`docs/cro/2026-04-19-funnel-audit.md`). |
| Learning from escaped defects | **AHEAD** in corpus, **BEHIND** in automatic receptor creation | W99 and the PENDING-ARMS rows are exceptionally honest evidence, but their antibodies are not yet generated as journey contracts (`.claude/rules/cicatrix-scars.md`, `.claude/skills/modus/PENDING-ARMS.md`). |

## 5. Beyond-SOTA recommendations

All recommendations keep PII out of persisted prompts and artifacts, use deterministic local mechanisms first, permit only sanctioned flat-subscription CLI calls for subjective review, never auto-route Fable, and reserve business choices for Zero.

### 1. Scar-derived Journey Contract Graph

**Priority score:** 9.4/10 by impact × confidence ÷ cost.

**What:** Generate a versioned graph connecting routes, personas, auth states, dates, locales, accessibility modes, expected network behavior and operational handoffs. Seed it with every escaped product scar. Initial metamorphic states should include anonymous, token-only, cookie-only, expired session, past visa date, malformed storage, reduced motion, 200% text zoom, Indonesian locale, missing image and failed optional API.

**Why it beats SOTA:** GOV.UK tests whole services and Storybook tests component states, but neither surveyed system combines those mechanisms with a private, organization-specific scar corpus that automatically becomes future journey input. Nuzantara can make every escaped defect permanently increase the state-space of its immune system.

**Before → after:** 158 routes and 53 E2E files with no defensible route-journey coverage percentage; five reconstructed defect classes were individually catchable but not uniformly guarded. Target: 100% of Tier-1 public routes represented in the graph, all five classes replayed on every relevant PR, zero advisory-red/parent-green journey jobs, and no more than one escaped P0/P1 UX defect per quarter.

**Cost and gear:** 30–45 engineering hours; deterministic execution plus approximately 0.5–1 flat-subscription critic session per contract expansion; Gear 3.

**Risk:** Overmatching or brittle selectors—superscar #3; unconsumed declarations—#2; contract/schema drift—#9.

**Measurement:** CI emits route/state coverage, unrepresented Tier-1 routes, contract execution success, advisory failures and escaped-defect count. A monthly mutation inserts each five known failure class and requires the graph to fail.

**Kill criterion:** Stop or simplify if the median suite adds more than eight minutes to PR latency for two weeks, flaky failure exceeds 2%, or more than 20% of failures are non-actionable.

**First PR:** `test(mouth): encode five escaped public-surface contracts`; proposed files `apps/mouth/e2e/contracts/public-surface-contracts.ts`, `apps/mouth/e2e/public-surface-immune.spec.ts`, and a small manifest under `apps/mouth/e2e/contracts/`; ≤400 net lines, one concern.

### 2. Federated token proof compiler

**Priority score:** 8.7/10.

**What:** Define one typed DTCG-compatible authority graph with namespaces for invariant brand identity, editorial surfaces and operational product surfaces. Compile existing CSS and cortex JSON from it, retain intentional surface-specific colors, reject dead references, and emit a usage-lineage manifest consumed by the component catalog.

**Why it beats SOTA:** DTCG standardizes tokens, while most organizations still choose between a centralized token library and surface-local systems. Nuzantara can compile both without flattening the editorial/product distinction and can attach each exception to measured accessibility and product rationale.

**Before → after:** At least three practical authorities—cortex JSON, core CSS and application literals—plus a dead `bz-tokens.css` reference and 28 workspace hex occurrences. Target: zero dead token paths; zero undeclared literals in touched Tier-1 code; 100% of the 32 catalog components reporting token lineage; 100% of aliases resolving deterministically.

**Cost and gear:** 24–36 hours; no LLM needed for compilation, one flat-sub critic pass for naming and migration review; Gear 2 for compiler, Gear 3 for authority migration.

**Risk:** Destroying legitimate surface differentiation—#3; home/copy drift—#1; schema drift—#9.

**Measurement:** Token compiler reports unresolved aliases, dead tokens, undeclared literals, contrast pairs and component usage. Baseline and after reports are committed as machine-readable summaries.

**Kill criterion:** Reject the compiler design if it requires more than two compatibility layers, increases shipped CSS by more than 10%, or cannot preserve existing editorial and operational snapshots without unexplained diffs.

**First PR:** `feat(tokens): add typed authority map and dead-reference lint`; proposed files `packages/core/tokens/design-tokens.json`, `scripts/lint_design_token_authority.py`, and focused tests; ≤350 net lines.

### 3. Deterministic-first Perception Gate

**Priority score:** 8.5/10.

**What:** Turn the 32-component catalog into a local, browser-rendered state gallery. For five components at a time, render loading, empty, error, success, disabled, long-text and five-locale states. Gate font loading, image dimensions, overflow, console errors, failed requests, focus visibility, WCAG 2.2 axe findings, reduced motion and screenshot diffs before sending the residual artifact to a cross-family visual critic.

**Why it beats SOTA:** Storybook and visual-regression services test component states; Nuzantara adds a formally subordinated LLM critic plus scar-derived deterministic assertions. The model may flag hierarchy or trust problems, but it cannot overrule a failed font, asset or accessibility invariant.

**Before → after:** Failure-only screenshots, no comprehensive state baselines, and W99’s ten wrong-font slides. Target: 32/32 catalog components with critical states; 100% deterministic font/asset checks; zero uncaught missing-font regressions; visual baseline review under five minutes per changed component group.

**Cost and gear:** 35–50 hours across incremental PRs; local Playwright storage; one Sonnet/Opus flat-sub CLI review only when deterministic gates pass; Gear 3.

**Risk:** Snapshot churn—#3; model claim treated as proof—#6; a gallery that exists but is not required—#2.

**Measurement:** State coverage, visual-diff rate, false-positive rate, review time and escaped perception defects. Quarterly seeded missing-font, broken-image and overflow mutations must all fail.

**Kill criterion:** Abandon screenshot gating for a component family if unexplained churn exceeds 5% across three consecutive runs; retain DOM/a11y invariants and redesign the visual fixture.

**First PR:** `test(design): render deterministic states for five trust components`; proposed local gallery for `AppWizard`, `AppTrustStrip`, `AppWhatsAppCTA`, `FunnelFrame` and `TrustBand`, plus Playwright assertions; ≤400 net lines.

### 4. High-stakes evidence and experimentation loop

**Priority score:** 7.7/10, conditional on ruling.

**What:** Establish a consented, PII-minimized event contract for question viewed/completed, validation error, abstention, human handoff, payment start/failure/success and operational receipt. Pre-register experiments and guardrails; apply variance reduction only after event correctness and sample adequacy are established.

**Why it beats SOTA:** Commercial experimentation systems optimize clicks or revenue. Nuzantara can optimize qualified completion while simultaneously constraining wrong advice, unwanted escalation, payment confusion and unfulfilled operational promises—an objective shaped for regulated high-stakes services.

**Before → after:** Historic baseline of two website leads over 90 days versus 420 WhatsApp leads, zero attributable funnel conversions and no per-question analytics. First establish a current four-week baseline; then target a 30% relative increase in qualified completion with no increase in wrong-advice flags, unresolved payment errors or seven-day unfulfilled receipts.

**Cost and gear:** 20–30 engineering hours before any experiment, then four to eight weeks of observation; no per-token API cost; Gear 3.

**Risk:** Invalid event semantics—#9; analytics declaration without delivery—#2; false causal claims—#6. PII must never appear in events.

**Measurement:** Schema-valid event percentage, funnel transitions, qualified completion, abstention quality, payment failure, handoff SLO and fulfillment. Experiment reports must include sample size, pre-registered primary metric and guardrails.

**Kill criterion:** Stop experimentation if event completeness is below 98%, assignment mismatch exceeds 1%, guardrail data is delayed, or the sample cannot reach the pre-registered minimum within the allowed window.

**First PR:** `docs(mouth): specify high-stakes funnel event contract`; proposed `apps/mouth/docs/funnel-event-contract.md` plus schema validation tests with synthetic identifiers only; ≤300 net lines. No production collection before ruling.

### 5. Trust-continuity service receipt

**Priority score:** 7.4/10.

**What:** Make the case code a durable journey receipt shared across web, WhatsApp and the human service boundary. It should communicate what was concluded, what remains uncertain, price source/timestamp, next step, responsible team or named person, promised response window and status—without copying PII into shared artifacts.

**Why it beats SOTA:** Service blueprints usually document backstage handoffs; they rarely make the handoff itself a user-visible, testable receipt bound to high-stakes advice. Nuzantara already controls the web-to-human operational path and can close that gap.

**Before → after:** R3 records missing price floor, weak progress visibility, dead ends and absent named-human assurance. Target: 100% of qualified or abstained Tier-1 flows produce a receipt; 95% of human handoffs meet the declared response SLO; zero re-entry of already supplied non-sensitive facts; zero unverified price displays.

**Cost and gear:** 25–40 hours, excluding backend data work owned by lane 12; Gear 2 for the component, Gear 3 for cross-channel proof.

**Risk:** Receipt/schema drift—#9; asserted fulfillment without receptor—#2; trust copy becoming an unsupported claim—#6.

**Measurement:** Receipt issuance, handoff acknowledgment, declared-versus-observed response time, repeat-entry rate and PricingTool provenance. Synthetic journeys only in CI.

**Kill criterion:** Remove or narrow the receipt if acknowledgment falls below 90% after four weeks, users interpret it as a government document in moderated testing, or operational status cannot be kept current.

**First PR:** `feat(mouth): add synthetic case-receipt component contract`; proposed component, story fixture and Playwright contract under `apps/mouth/src/components/`; ≤400 net lines. Live wording and ownership remain gated by ruling.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: make authority executable

| First PR | Proposed files | Size / gear | Acceptance test |
|---|---|---:|---|
| `test(mouth): encode five escaped public-surface contracts` | `apps/mouth/e2e/contracts/public-surface-contracts.ts`, `apps/mouth/e2e/public-surface-immune.spec.ts` | ≤400 lines, Gear 3 | Seed anonymous 401, past-date, cookie-only, unconsumed token and broken-asset defects; all five must fail for the right reason. |
| `feat(tokens): add typed authority map and dead-reference lint` | `packages/core/tokens/design-tokens.json`, `scripts/lint_design_token_authority.py`, focused tests | ≤350 lines, Gear 2 | Existing aliases resolve; nonexistent `packages/core/styles/bz-tokens.css` reference fails; editorial and operational snapshots remain distinct. |
| `test(design): render five trust components in critical states` | Local gallery fixtures plus Playwright test under `apps/mouth/` | ≤400 lines, Gear 3 | Five components render normal/error/long-text/ID/reduced-motion states with zero console, font, asset, overflow or serious axe failures. |

Wave-1 exit: all five escaped defect classes are executable, the token authority has no dead references, and five components have deterministic perception evidence.

### Wave 2 — Days 31–60: expand the experience immune system

| First PR | Proposed files | Size / gear | Acceptance test |
|---|---|---:|---|
| `test(a11y): upgrade Tier-1 journeys to WCAG 2.2 contracts` | `apps/mouth/e2e/a11y/tier1-wcag22.spec.ts`, scoped helpers | ≤400 lines, Gear 3 | Keyboard, focus-not-obscured, 24px minimum target exceptions, accessible auth, reduced motion and 200% text zoom pass at 360/390 widths. |
| `test(i18n): enforce locale completeness and pseudo-locale expansion` | `apps/mouth/src/i18n/` validation utility and tests | ≤350 lines, Gear 2 | EN/ID/IT critical keys are complete; pseudo-locale produces no clipped critical CTA or untranslated key; FR/RU gaps are explicitly classified. |
| `ci(mouth): make journey red consequential` | `.github/workflows/frontend-ux-contract.yml`, minimal script glue | ≤250 lines, Gear 3 | A failing journey produces a failing required job; no `continue-on-error`; merge rollup reflects the failure. |
| `test(design): expand state gallery to the 32-component catalog` | Incremental fixtures/tests, one component family per PR | ≤400 lines each, Gear 2 | Machine report reaches 32/32 components without exceeding 2% flaky visual diffs. |

Wave-2 exit: Tier-1 accessibility is process-level rather than page-scan-only; critical locale journeys are measurable; advisory-red/parent-green behavior is impossible.

### Wave 3 — Days 61–90: connect experience to service outcomes

| First PR | Proposed files | Size / gear | Acceptance test |
|---|---|---:|---|
| `docs(mouth): specify high-stakes funnel event contract` | `apps/mouth/docs/funnel-event-contract.md`, synthetic schema tests | ≤300 lines, Gear 3 | Every event has purpose, lawful/consented basis, redacted payload, owner, consumer, guardrail and deletion rule; no production emission yet. |
| `feat(mouth): add synthetic case-receipt component contract` | Component, local state fixtures and journey test | ≤400 lines, Gear 2 | Qualified and abstained synthetic journeys render distinct receipts with price provenance and human-handoff expectations. |
| `feat(ux-immune): generate contract candidates from closed scars` | `scripts/generate_ux_contract_candidates.py`, tests, machine-readable mapping | ≤400 lines, Gear 3 | W99 and the five public defect classes produce stable, reviewable test candidates; generator never changes required checks automatically. |
| `perf(mouth): record field-aligned CWV evidence` | First-party aggregate adapter and synthetic contract, subject to ruling | ≤400 lines, Gear 3 | Reports p75 LCP/INP/CLS by route family and locale with no identifiers or free text; stale documentation values are not treated as live proof. |

Wave-3 exit: design decisions connect to qualified completion and operational receipts; every closed UX scar proposes an executable antibody; field metrics have provenance and privacy boundaries.

## 7. Needs-ruling

1. **Behavioral analytics consent, retention and purpose.** Zero must decide whether first-party funnel measurement is acceptable, which jurisdictions and notices apply, and how long anonymous aggregate events may be retained. No production instrumentation should precede this ruling.

2. **Identity experiments involving a named human versus an institutional team.** R7 correctly prevents LLM proxies from promoting this choice. Zero must approve the variants and the real-user test because the answer changes brand accountability, staffing expectations and client trust (`research/design/2026-08-27-r7-doctrine-loop-closure.md`).

3. **Use of institutional red as a dominant trust signal.** The repository research identifies both recognition value and potential governmental misinterpretation. Final promotion requires owner judgment plus real-user evidence (`research/design/2026-08-27-r4-identity-merah-putih-token-spec.md`).

4. **Paid Figma Code Connect or hosted visual-regression services.** Their mechanisms are useful, but any new subscription, credential or cloud artifact boundary requires explicit approval. The recommended default is a local manifest and local Playwright baseline until the business case is proven.

5. **Price, timeline and trust claims.** Product code must use PricingTool-derived values and verified evidence, but Zero must approve how price floors, service guarantees, testimonials and experience claims are presented.

6. **Publishing or replacing WR2/WR3 output.** Technical gates may produce approved drafts, but outward publication remains a Legge-5 business act.

## 8. §Meta-pattern

The single defective belief is:

> **A persuasive declaration or a favorable critic verdict is equivalent to an observed user contract.**

It generates nearly every gap in this lane:

- A `sensitive:` declaration had no consumer (`.claude/skills/modus/PENDING-ARMS.md`).
- A 30-job full-stack suite produced zero successes without making the parent red (`.claude/skills/modus/PENDING-ARMS.md`).
- Font telemetry said false, yet rendering and critic judgment passed (`.claude/rules/cicatrix-scars.md`, W99).
- A brand skill pointed to a token file that no longer existed (`skills/bali-zero-brand/SKILL.md`).
- Five translation catalogs coexisted with an unusable Indonesian prototype path (`apps/mouth/src/i18n/locales/`, `research/design/2026-08-27-r6-walkthrough-perception-runtime.md`).
- Performance numbers existed in prose without reviewed current field artifacts (`docs/FRONTEND_PERFORMANCE_GUIDE.md`).
- A generated component catalog described APIs without proving rendered states (`docs/design/components-catalog.md`).

The corrective meta-rule is simple:

> **Every design promise must compile into a state, a journey, or a field metric—or remain explicitly labeled as an unpromoted hypothesis.**

Nuzantara does not need more taste. It needs to connect its already exceptional taste, study discipline and scar memory to consequential receptors. That composition—scar-derived state generation, deterministic perception proof, cross-family residual criticism, and whole-service outcome measurement—is the credible path beyond SOTA.

## 9. Sources

1. [GOV.UK Service Manual — Make the service simple to use](https://www.gov.uk/service-manual/service-standard/point-4-make-the-service-simple-to-use). Published 2019; updated 2022; accessed 2026-08-29. Authoritative UK government standard for whole-service usability and real-user testing.

2. [GOV.UK Service Manual — Structuring forms](https://www.gov.uk/service-manual/design/form-structure). Accessed 2026-08-29. Primary government guidance on one-question-per-page flows, ordering, recovery and question-level analysis.

3. [U.S. Web Design System — Design principles](https://designsystem.digital.gov/design-principles/). Accessed 2026-08-29. Official US government design-system principles for accessible, comprehensible public services.

4. [W3C — Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/). W3C Recommendation, 2024-12-12; accessed 2026-08-29. Normative accessibility standard, including complete-process requirements.

5. [Design Tokens Community Group — Format Module 2025.10](https://www.designtokens.org/tr/2025.10/format/). Published 2025-10-28; accessed 2026-08-29. Primary specification for typed, interoperable token exchange and resolution.

6. [Storybook — UI testing documentation](https://storybook.js.org/docs/writing-tests). Accessed 2026-08-29. Official documentation for browser-executable component, interaction, accessibility and visual testing.

7. [Figma — Code Connect documentation](https://developers.figma.com/docs/code-connect/). Accessed 2026-08-29. Official design-to-production-component linkage documentation.

8. [web.dev — Defining Core Web Vitals thresholds](https://web.dev/articles/defining-core-web-vitals-thresholds). Published 2020; updated 2025-05-07; accessed 2026-08-29. Primary Google explanation of field-based LCP, INP and CLS thresholds.

9. [Stripe — Optimized Checkout Suite](https://stripe.com/newsroom/news/optimized-checkout-suite). Published 2023-09-18; accessed 2026-08-29. Primary product report describing payment-method optimization and reported merchant effects.

10. [Baymard Institute — 2024 checkout research](https://baymard.com/blog/checkout-2024-launch). Published 2024-03-13; accessed 2026-08-29. Primary research-program summary covering observed checkout usability failures and guidelines.

11. [VisualWebArena — Evaluating Multimodal Agents on Realistic Visual Web Tasks](https://aclanthology.org/2024.acl-long.50/). ACL 2024; accessed 2026-08-29. Peer-reviewed benchmark quantifying the gap between visual web agents and humans.

12. [Microsoft Research — Deep Dive into Variance Reduction](https://www.microsoft.com/en-us/research/articles/deep-dive-into-variance-reduction/). Published 2022-11-15; accessed 2026-08-29. Primary industry research explanation of CUPED-style experimental power improvement.