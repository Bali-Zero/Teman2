---
date: 2026-08-28
domain: operations
part: F2 conversion-funnels
scope: Public visa/assessment/booking funnels in apps/mouth, GARUDA VOA anonymous funnel, Xendit checkout, magic-link exchange, WhatsApp handoff, funnel analytics — benchmarked against CRO / guided-eligibility / checkout / passwordless SOTA.
sources:
  - https://design-system.service.gov.uk/patterns/question-pages/
  - https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/
  - https://designsystem.gov.scot/patterns/check-answers
  - https://producthabits.com/how-turbotax-used-design-and-emotion-to-solve-a-boring-problem-and-dominate-an-11b-industry/
  - https://stripe.com/newsroom/news/optimized-checkout-suite
  - https://stripe.com/newsroom/news/payments-revenue-uplift
  - https://www.boundless.com/guides/topics/costs-and-fees
  - https://www.zuko.io/blog/which-form-fields-cause-the-biggest-ux-problems
  - https://www.baytechconsulting.com/blog/magic-links-ux-security-and-growth-impacts-for-saas-platforms-2025
  - https://blog.logrocket.com/ux-design/how-to-use-magic-links/
  - https://snowplow.io/blog/server-side-tracking-vs-client-side-tracking
  - https://www.klaviyo.com/uk/blog/abandoned-cart-email
  - https://www.xendit.co/en/payment-channel/qris/
  - https://www.zipchat.ai/blog/cart-abandonment-benchmarks-and-causes
status: DONE 2026-08-29 (anatomy verified on worktree pinned at origin/main 11a3c89a2e)
adversarial_review: kimi-k3
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# F2 — Conversion Funnels

## Anatomy (as measured)

### Route inventory — what the funnel groups actually contain

The mandate's five named route groups are not five funnels. Measured on disk:

- **`(visa-oracle)/visa-oracle`** — the Visa Oracle v2 guided interview, the deepest funnel in the repo (163 files across the funnel groups; `_lib/` alone holds ~40 modules with paired tests).
- **`visa/`** — the funnel hub: `/visa` (entry, `useFunnelApp("visa_clock")` at `apps/mouth/src/app/visa/page.tsx:13`), `/visa/clock` + `/visa/clock/[hash]`, `/visa/match` + `/visa/match/[hash]` (4-step quiz), `/visa/second-home` + `/visa/second-home/studio` (E33 planning studio), and **`/visa/voa/*` — the GARUDA VOA money funnel** (eligibility → result → upload → checkout → orders).
- **`(book)/book`** — company book chapters with `ServicePricingCard`/`TeamGrid` (`apps/mouth/src/components/book/`); funnel-adjacent marketing, no transactional step.
- **`(assessment)/assessment`** — **not a client funnel at all**: it is an internal hiring assessment with a hardcoded candidate name (`apps/mouth/src/app/(assessment)/assessment/page.tsx:16`, `CANDIDATE_NAME = "<employee name>"`, Bahasa Indonesia question blocks). Anyone routing "assessment" traffic here expecting a lead-gen eligibility assessment is landing on an employee test.
- **`verification/`** — also **not a funnel**: a ChatHeader accessibility verification harness (`apps/mouth/src/app/verification/page.tsx:17`, "ChatHeader Accessibility Verification").

So the real conversion surface is: Visa Oracle v2 (guided eligibility → WhatsApp handoff), visa clock/match (micro-apps → WhatsApp handoff), second-home studio (plan builder → WhatsApp handoff), and GARUDA VOA (eligibility → paid order) — plus the KBLI/tax/zoning CTA funnels that share the same lead-capture spine.

### The VOA journey — step topology and where it breaks

The intended journey is contract-first (field names frozen against `products/garuda-voa/contracts/openapi.yaml`, per the header at `apps/mouth/src/app/visa/voa/page.tsx:14-23`):

1. **Eligibility wizard** (`/visa/voa`): 4 steps in an `AppWizard` with `persistKey="bz.garuda_voa.wizard"` (page.tsx:491-494), English-only by declared constraint 5a. Submit POSTs `/api/visa/voa/eligibility-checks` with a `crypto.randomUUID()` Idempotency-Key (page.tsx:434-443); on 201 it follows the `Location` header to `/visa/voa/{resultId}` (page.tsx:444-450). Failure shows an honest error with a WhatsApp escape hatch (page.tsx:453-470).
2. **Result page** (`/visa/voa/[hash]`): ACCEPT renders a single all-inclusive `price_idr` (page.tsx:270-271) plus a WhatsApp CTA carrying the price as context (page.tsx:277-283); DECLINE renders decline education (`components/garuda/declineEducation.ts`) with a WhatsApp fallback — no dead ends. The page also hosts `MagicLinkRequestForm` (page.tsx:302-327) which POSTs `/api/visa/voa/auth/magic-links` and always shows the same "check your email" copy (non-enumerating 202, mirrored server-side).
3. **Upload** (`/visa/voa/upload/[resultId]`): passport biodata upload, authenticated by the contract's `MagicSession` — "a Secure, HttpOnly `garuda_session` cookie set by L4's magic-link exchange" (`apps/mouth/src/app/visa/voa/upload/api-client.ts:5-8`).
4. **Checkout** (`/visa/voa/checkout/[resultId]`): `full_name`/`passport_number` arrive via a sessionStorage same-visit handoff (`checkoutHandoff.ts:10-12` — deliberately sessionStorage not localStorage, PII must not outlive the tab), email/phone are collected fresh (`CheckoutFlow.tsx:16-19`). A created order never renders success on this page: `awaiting_payment` redirects to the provider's `checkout_url`, everything else forwards to the tracker (`CheckoutFlow.tsx:40-52`).
5. **Return + tracker** (`/orders/[orderId]/return` → `/orders/[orderId]`): the return page never claims payment success ("recorded, not paid" — `return/page.tsx:16-22`); the tracker (`OrderTracker.tsx`) is the single place order state renders, polling every 5s only while the order is "still moving" and stopping on terminal states so Delivered can never regress to a flicker (`useOrderTracking.ts:12-31`).

**Where it breaks, measured:**

- **The magic-link exchange has zero frontend callers.** The backend exposes `POST /sessions` (`exchangeMagicLink`, `garuda_portal_auth.py:376-381`) which sets the `garuda_session` cookie (`_ACCOUNT_SESSION_COOKIE = "garuda_session"`, `garuda_portal_auth.py:91`, `response.set_cookie` at :289). Grep across `apps/mouth/src` finds **no fetch of `/auth/sessions` anywhere**. The emailed link is built as `{GARUDA_MAGIC_LINK_BASE_URL:-https://balizero.com/visa/voa}?result_id=X&magic_token=Y` (`magic_link_store.py:134-136`, whose own docstring admits the default "is a placeholder pending frontend confirmation") — and `/visa/voa/page.tsx` reads **neither query param** (no `useSearchParams`/`magic_token` anywhere in the file). The customer clicks the email, lands on the blank wizard, and the token expires. Steps 3-5 are therefore unreachable by construction: the request half of passwordless auth is built and wired, the exchange half is built and orphaned.
- **The order routes fail closed with 503** until the orchestrator injects the payment adapters onto `app.state` (`garuda_orders_router.py:22-23` "fails closed with 503 until that happens"; 503 raises at :110-111, :258-259). The live context (2026-08-28 prod probe, done by the parent program, not re-run here) matches: eligibility answers end-to-end with 201 `verdict:ACCEPT` and a single `price_idr`, while the three order routes 503 for lack of `GARUDA_XENDIT_SECRET_KEY` (unverified live; the fail-closed design is verified on disk). Checkout is dead twice over: unreachable via auth, and 503 if reached.
- **The funnel flag lives on two platforms.** `isGarudaVoaPublicEnabled()` reads `GARUDA_PUBLIC_ENABLED` at call time, fails closed on anything but literal "true" (`apps/mouth/src/app/visa/voa/flag.ts:27-31`); the backend re-checks the same-named env per-request as a router-level dependency (`garuda_orders_router.py:16-19`). Vercel and Fly hold independent copies of that name — turning it on on one platform leaves the other dark.

### State management

Two distinct, deliberate models:

- **Visa Oracle v2** is a pure reducer state machine (`flow.ts:1-8` — "a pure reducer plus a thin `useOracleFlow` hook"; 1,217 lines, with the 1,391-line question graph in `tree.ts`, ~40 question ids). History is a real stack, GOV.UK-style ("spec item 35 / GOV.UK mandatory Back link, real history" — flow.ts:5-7), so Back and confirmation-card Edit are the same mechanism: truncate the stack. It carries an `attempt` counter bumped only by full reset (flow.ts:36-52, used to key the evaluation request-lease cache), and a `blockedAnswer` contradiction detector that refuses to record an answer conflicting with a known fact and asks the user to resolve it rather than guessing (flow.ts:53-63). Resume is versioned-schema sessionStorage with a 2-hour TTL and fail-closed restore of untrusted snapshots (`resume-store.ts:1-16`, `flow.ts:88-91`).
- **VOA/second-home** use storage-keyed wizard persistence: `AppWizard` persistKey, sessionStorage PII handoff (`checkoutHandoff.ts`), and in second-home a defensive plan codec — localStorage + base64url URL fragment for "copy plan link", every decode failure resolving to a fresh plan, never a throw (`plan-codec.ts:1-22`).

### Network client discipline

`evaluation-client.ts` is the strongest funnel HTTP client in the repo: idempotency-key-required retries (a caller cannot opt into retry without a durable key — :244-247), bounded retry set on {408, 425, 429, 5xx} (:21), 32KB request / capped-byte streamed response with strict JSON parsing (:17, :64-108), a 12s timeout, and an explicitly untrusted "peek" at `decision.state` used only to choose honest fallback copy (:110-116). The VOA order/upload clients follow the same contract-frozen error-code pattern (`orders/api-client.ts`, `upload/api-client.ts`).

### Event instrumentation

- **Taxonomy**: `packages/core/analytics/funnel-app.ts` defines 13 `app_*` events (APP_EVENTS, :22-36) covering view → branch → form start/submit/fail → wizard step/abandon → result → CTA → WhatsApp handoff → share/pdf/email. It has a compile-time proof that the const list exactly covers the event union in both directions (:98-107), and the backend allowlist mirrors it — `ALLOWED_EVENTS = FUNNEL_PAGE_EVENTS | FUNNEL_APP_EVENTS` (`apps/backend-rag/backend/app/routers/analytics.py:114-132`), enforced bidirectionally by `test_analytics_funnel_parity.py`. Privacy is designed into the payloads: `app_form_submit_failed` carries only endpoint + HTTP status, "never form values" (funnel-app.ts:50-57), with a CI guard placed where CI actually runs because packages/core has no CI job (`apps/mouth/src/lib/funnel-app-events.test.ts:4-11` — an honest, documented workaround).
- **Transport**: dual-write — GA4 `gtag` fire-and-forget plus a first-party `POST /api/analytics/funnel-event` with `keepalive: true` and a required 30-day first-party `bz_session` cookie scoped to `.balizero.com` (`funnel-app.ts:126-149`; `session-bridge.ts:1-2, 28-54`). `SessionInit` touches a server session per funnel on the visa/kbli/tax-calendar/property/marketing layouts (`SessionInit.tsx:10-16`; mounts measured via grep).
- **Coverage, measured**: `/visa/match` is fully instrumented (formStarted per field at match/page.tsx:99-237, formSubmitted :253, formSubmitFailed :279, wizardStep/wizardAbandoned :315-316). `/visa/clock` and the match/clock `[hash]` result pages likewise. **The VOA funnel emits zero `app_*` events** — grep across `apps/mouth/src/app/visa/voa` finds no tracker import, no gtag, no analytics call in any of its 17 tsx/ts files. The Visa Oracle uses its own parallel 7-event PII-free taxonomy (`visa_oracle_v2_*`, `telemetry.ts:3-11`) with SHA-256-only correlation and pinned-pack parity events — excellent for engine QA, but not funnel-step analytics, and not unified with `app_*`.

### UTM and attribution

- **Outbound is enforced**: every WhatsApp CTA must route through `buildWhatsAppLink` (`whatsapp-utm.ts:4-6` — shared `WA_NUMBER` because before sharing "they had drifted onto two different people", :13-17), stamping `utm_source=balizero_web&utm_medium=whatsapp_cta&utm_campaign={funnel}`. Social links must use `buildSocialCTA`, which **throws** on missing fields (`social-utm.ts:27-29`) — motivated by a measured baseline: "social_90d = 5 / 324 leads (1.5%)" (:10-13).
- **Inbound is absent**: grep for `utm_source|utm_campaign` outside the two builders finds **no code that reads or persists incoming UTM parameters** — no first-touch capture into `bz_session`, no UTM on the lead-capture payload's session side. Paid/social arrivals evaporate into GA4's default attribution.
- **Lead capture spine**: `WhatsAppLeadButton` POSTs `/api/lead/capture` (anonymous `lead_intents` row), navigates to the returned prefilled wa.me deeplink, and falls back to a bare wa.me link on any failure — "the user is never blocked by our own funnel" (`WhatsAppLeadButton.tsx:32-36, 56-77`). Used by 10+ surfaces (blog articles, second-home, v2 hero, zoning, tax-gap, KBLI decoder/builder).

### Trust and price surfaces

- One all-inclusive price is a doctrine, enforced by construction: the checkout page "never fetches or renders a price breakdown itself — the price only appears once, on the order tracker" (`CheckoutFlow.tsx:11-14`), and the ACCEPT page footer repeats the no-hidden-government-fees pledge (`[hash]/page.tsx:257`).
- `TrustBar` renders rating/review proof in desktop-inline and mobile-sticky variants (`TrustBar.tsx:5-11`). The repo's most remarkable trust artifact is `response-time-claim.test.ts:5-25`: the homepage's "Avg reply: 2 min" claim was measured against 189 real inbound/outbound pairs (average 548.8 min, median 4.9, 24.3% within 2 min), found false under every favourable framing, **removed**, and a test now prevents any unmeasured response-time claim from returning.
- Consent for the Oracle's WhatsApp handoff is a first-class object: versioned schema, policy version string, receipt id, TTL-bound scope carrying only the outcome state and an opaque engine reference — "No facts, candidates or applicant data" (`consent-store.ts:3-38`); the handoff emits `visa_oracle_v2_handoff_opened` (`ConsentHandoff.tsx:272`).

## Honest state vs. SOTA

**What is genuinely good — at or above industry practice:**

1. **The interview engine is GOV.UK-grade.** One-thing-per-page, a real history stack, contradiction refusal instead of silent overwrite, "what instead" category jumps so a rejection is never a dead end (flow.ts:114-118), resume with TTL and fail-closed restore. Most commercial eligibility checkers (including most visa-services competitors) are a `<form>` with steps faked in component state.
2. **Contract-first checkout with a single state renderer.** The "tracker is the only place order state is rendered" rule, the never-claim-success return page, and idempotency keys on every mutating call are Stripe-practice-level payment UX discipline, written before the payment provider is even live.
3. **Analytics schema governance.** A typed, compile-time-proven event union mirrored into a backend allowlist with a bidirectional parity test is beyond what most CRO teams have; most SOTA shops enforce taxonomy by convention and lose it within a quarter.
4. **Honest trust signals, tested.** Measuring your own "Avg reply: 2 min" claim, finding it false, deleting it, and pinning the deletion with a test is a pattern Baymard would cite approvingly; almost nobody does it.
5. **Privacy-by-construction in the funnel** (PII-free event payloads, SHA-256 correlation, sessionStorage PII handoff, consent receipts) — well past typical CRO practice, which leaks form values into analytics constantly.

**What is broken or theater:**

1. **The money funnel cannot take money.** Orders 503 (deliberate fail-closed, but the effect is zero revenue capability), and even with Xendit armed the journey dies earlier: the emailed magic link lands on a page that ignores its own token. The funnel converts anonymous visitors into *emails sent to themselves*, not into uploads or orders. This is the single highest-leverage defect in F2.
2. **The funnel that sells is the one funnel that is analytics-dark.** visa/match — which ends in a free WhatsApp handoff — measures every field start, step, abandon, and failure; `/visa/voa` — the paid product — emits nothing. Today nobody can answer "what fraction of ACCEPT verdicts request a magic link?" from instrumentation.
3. **Two parallel event taxonomies** (`app_*` funnel events vs `visa_oracle_v2_*` engine telemetry) with no join; a third spine (`lead_intents` rows) carries conversion truth for WhatsApp handoffs. There is no single funnel view from landing → verdict → handoff/checkout.
4. **Attribution is outbound-only.** The CRM can see that a WhatsApp lead came from the site (wa.me UTM), but the site never records where the visitor came from — the 1.5% social attribution the social-utm builder was created to fix cannot improve materially while inbound UTMs are dropped on the floor.
5. **Route-group naming lies.** `(assessment)` is a hiring test and `verification/` is an a11y harness, both squatting names that in a funnel-anatomy read as conversion surfaces.
6. **No experimentation substrate**: no A/B assignment, no feature-flag variants beyond the binary funnel flag, no holdout mechanics anywhere in the funnel groups.

## Deep research: the world's best

**GOV.UK Design System — question pages and check-your-answers.** The canonical guided-flow doctrine: split every question onto its own page ("one thing per page") — easier for low-confidence users, mobile-friendly, and clean at handling "errors, branches, loops and saving progress"; merge only when research proves it. Every question must trace to a *question protocol* documenting why each datum is needed. The companion **check-your-answers** pattern: all answers shown (skipped optionals as "Not answered"), change-links back to source pages, answers *reworded* for review context, a submit button stating the full action; Social Security Scotland's research found users specifically valued correcting errors pre-submit. Nuzantara's Oracle already implements the mechanism (history-stack Edit); the VOA wizard has no review screen — the contract is submitted straight off step 4.

**TurboTax — the interview as emotional product.** TurboTax converted a form into a conversation: plain-English questions, onboarding personalized by segment ("does TurboTax handle *my* situation?" is the confidence gate), progress feedback on anything slow, celebration screens at milestones. The interview *is* the product; the tax engine is invisible. The Oracle has the mechanism (LivingTree, VerdictReveal); the VOA money funnel is four utilitarian card-selects with none of the confidence scaffolding TurboTax proves pays.

**Stripe — checkout as measured optimization surface.** Published numbers: the optimized Payment Element yields **+10.5% revenue on average**; Link (one-click returning-customer checkout) converts **+14%** in A/B tests, case studies showing 40% faster checkout and +34% conversion. Meta-lesson for a solo operator: Stripe ships "100+ checkout optimizations" so merchants don't hand-build them — SOTA is *renting* the optimized checkout, not building fields. Xendit's hosted invoice page is the local-market equivalent.

**Baymard Institute — checkout abandonment mechanics.** The 2025 meta-analysis: **70.22%** average cart abandonment (85.65% mobile); top killable reasons: unexpected extra costs (48%), forced account creation (26%), preferred payment method missing (22%), process too long (17%); fixing checkout UX alone is worth ~35% more conversions. The single all-inclusive-price doctrine neutralizes reason #1 and guest-first checkout matches #2 — the *design* is Baymard-aligned; missing is the measurement to prove where its own 70% actually falls.

**Zuko / Formstack — field-level form analytics.** Across 100M+ sessions: roughly two-thirds of users who *start* a form never finish; worst-friction fields are password (10.5% abandonment), email (6.4%), phone (6.3%); multi-step forms convert ~3x better than single-page equivalents (13.9% vs 4.5%, Formstack). The operational pattern is *field-level* instrumentation — exactly what `app_form_started(field)` anticipates but only `/visa/match` emits.

**Boundless — visa-services trust architecture.** The most instructive direct comparable: flat transparent service fees with government fees explained, published payment schedules, a written approval guarantee, quantified trust signals (100K+ served, 99.7% success rate) at decision points. Bali Zero's one-price doctrine is *stronger* than Boundless's fee-split, but its trust surface is thinner: the VOA result page shows a price with no guarantee language, no success-rate figure, no "what happens after payment" timeline.

**Magic-link auth practice (Descope / LogRocket / Baytech).** Consensus engineering: 10-15 minute TTL, an explicit **resend** affordance, clear expiry messaging, a fallback channel for deliverability failures, and — critically — the link must land on a route whose *only job* is to complete the exchange and continue the journey. The known failure modes (slow email, cross-device click, spam filtering) all demand an in-product "didn't get it?" recovery path. Nuzantara implemented the hard parts (non-enumeration, replay-safe idempotent exchange, one-time tokens) and skipped the easy one that makes it work: the landing page.

**Snowplow / server-side tracking doctrine.** Modern funnel instrumentation is hybrid: client-side for behavioral granularity, server-side for truth — purchase/order events emitted by the backend where ad-blockers and flaky `keepalive` fetches can't drop them, joined on a first-party session id. Nuzantara owns both halves (`bz_session` cookie + backend ingestion endpoint) but emits everything from the client; order-state transitions are the canonical server-side events and today produce no analytics at all.

**Klaviyo — abandonment recovery benchmarks.** Cart-recovery flows average 50.5% open / 3.33% placed-order rate; a 2-3 email sequence over 72h recovers 5-14% of abandoned carts, high-AOV purchases favoring a 4-8h first touch. For a visa funnel: capture email *early* (the magic-link form already does), then a sequenced "your result is waiting / your VOA window closes on {date}" — the engine's D-7 deadline is a natural, honest urgency primitive competitors fake.

**Xendit — Indonesian payment-method coverage.** First-attempt completion in Indonesia hinges on QRIS + e-wallets (OVO, DANA, ShopeePay, GoPay) and bank VAs, not cards; Xendit's hosted invoice bundles them. The `checkout_url` redirect design is already the right shape — the conversion work is configuring the invoice with the full local method set, not building payment UI.

## Gap table

| Dimension | SOTA benchmark | Nuzantara measured state | Gap |
|---|---|---|---|
| Guided eligibility flow | GOV.UK one-thing-per-page + question protocol; TurboTax confidence scaffolding | Oracle v2: reducer state machine, history stack, contradiction refusal, resume TTL (flow.ts) | **At/above SOTA** (mechanism); VOA wizard far below Oracle's own bar |
| Review-before-submit | GOV.UK check-your-answers, tested with users | Oracle: ConfirmationCard exists; VOA: none — step 4 submits directly | Partial |
| Checkout completion path | Stripe/Xendit hosted checkout; guest-first; wallet-first | Correct architecture (redirect to `checkout_url`, tracker as truth) but 503-dead + auth-orphaned upstream | **Broken end-to-end** |
| Passwordless continuation | 10-15min TTL, resend, dedicated landing route, fallback | Backend complete (non-enumerating, replay-safe); email link lands on a page that ignores the token; no resend; no fallback | **Half-built — the halves don't meet** |
| Funnel event instrumentation | Field-level (Zuko), full-journey, client+server hybrid (Snowplow) | 13-event typed taxonomy w/ FE/BE parity tests; `/visa/match` fully wired; **VOA: zero events**; no server-side order events | Taxonomy SOTA, coverage ~40% |
| Attribution | First-touch UTM persisted to session/lead; server-side conversion join | Outbound UTM enforced (throws on miss); **inbound UTM never read**; lead_intents rows carry no landing attribution | One-directional |
| Price transparency | Boundless flat-fee w/ explanation; Baymard: hidden costs = #1 killer | Single `price_idr` doctrine, enforced by construction, repeated no-hidden-fees pledge | **At/above SOTA** |
| Trust signals | Quantified, placed at decision points, honest | TrustBar + measured-honest discipline (response-time claim removed by test); thin at VOA decision point | Partial, but honesty discipline is beyond SOTA |
| Abandonment recovery | Klaviyo 3-email/72h, 5-14% recovery | None — email captured only via (dead) magic link; no recovery sequence | Absent |
| Experimentation | A/B assignment, holdouts, measured checkout iteration (Stripe) | None — binary funnel flag only | Absent |
| Payment-method locality | QRIS + e-wallets + VA for Indonesia | Xendit chosen (right vendor), unarmed (`GARUDA_XENDIT_SECRET_KEY` absent) | Config, not code |
| Order status UX | Parcel-tracker mental model, no false success states | OrderTracker: 5s poll while moving, terminal-state stop, return page never claims "paid" | **At SOTA** |

## Recommendations — reach SOTA

**R1 — Land the magic link (P0).** Add a `/visa/voa/continue` (or read `magic_token` on `/visa/voa`) client route that calls `POST /api/visa/voa/auth/sessions` with the token + idempotency key, then forwards to `/visa/voa/upload/{result_id}`. Include a resend affordance on failure (the request endpoint is already idempotent and non-enumerating). This single page unblocks steps 3-5 of a journey whose every other component is built and tested. *Acceptance (falsifiable): a Playwright journey test that requests a magic link against a test store, exchanges it, and reaches the upload page with a `garuda_session` cookie — red today, green after; plus `GARUDA_MAGIC_LINK_BASE_URL` set to the real route on Fly.*

**R2 — Instrument the VOA funnel with the existing taxonomy (P0).** Wire `useFunnelApp` (new app name `visa_voa` added to `FunnelAppName` + backend mirror) into wizard steps, result view (`resultViewed` with the existing result hash), magic-link request (`emailSubscribed` or a new `app_magic_link_requested`), upload, checkout submit, and `formSubmitFailed` on every fetch. The parity test suite makes this a mechanical, safe change. *Acceptance: every step of a full VOA dry-run appears as `app_*` rows in the funnel-event store; a funnel query can compute step-to-step drop-off for a real week of traffic.*

**R3 — Emit order-state events server-side (P0, pairs with R2).** On order create / awaiting_payment / webhook-paid / failed, write a funnel event row from the backend (the ingestion table already exists) keyed by the order's session/result linkage. Client analytics can be blocked or dropped; the money events must come from the component that knows the truth. *Acceptance: a synthetic order (existing `synthetic_probe.py` path) produces `created→paid` events with zero client involvement.*

**R4 — Persist inbound attribution (P1).** On first landing, read `utm_*` + referrer in `SessionInit` (or middleware) and POST them once onto the server session (`/api/funnel/session/touch` already accepts `step_state`); stamp `lead_intents` and VOA eligibility-checks with the session's first-touch source. *Acceptance: a visit landing with `?utm_source=instagram` produces a lead_intents row whose attribution field says instagram; the social-utm builder's 1.5% baseline becomes re-measurable end-to-end.*

**R5 — Add check-your-answers to the VOA wizard (P1).** One review screen before POST, GOV.UK-shaped (reworded answers, change links that reuse `AppWizard` step navigation). Dates and nationality are exactly the fields Baymard/Zuko flag as error-prone; today a typo'd passport expiry silently produces a wrong verdict. *Acceptance: journey test edits an answer from the review screen and the corrected value reaches the request body.*

**R6 — Trust block at the price moment (P1).** On the ACCEPT screen, alongside `price_idr`: what happens after payment (3-step timeline feeding the parcel tracker), the D-7 validity context the engine already computes, and one quantified, *measured* trust figure (the response-time-claim test shows the discipline: publish only what a query can defend — e.g. orders delivered, median processing time once real data exists). *Acceptance: the block renders only figures backed by a store query committed next to it, per the response-time-claim pattern.*

**R7 — Arm Xendit and prove the path dark (P0, operator-gated).** Code is fail-closed and ready; `GARUDA_XENDIT_SECRET_KEY` + adapter wiring is the remaining step, then a real end-to-end synthetic purchase (ship-dark → 5% per ASSEMBLY-LINE). *Acceptance: synthetic purchase probe completes created→paid→Delivered in prod against a test-mode key.*

**R8 — Abandonment recovery sequence (P2, after R1).** The magic-link email is already an email capture. Add a second send at +24h for results with no session exchange ("your result is saved; your VOA window closes {date}") via the existing Brevo path. Honest urgency only — the deadline is real, engine-computed. *Acceptance: a result with a requested-but-unexchanged link at +24h triggers exactly one recovery email; opt-out honored.*

## Recommendations — beyond SOTA

**B1 — Verdict-as-contract: signed, replayable eligibility results.** The Oracle already computes SHADOW parity against a pinned gold pack and hashes correlation ids. Go one step further than any competitor: publish the rule-pack hash + verdict on the result page ("this decision was produced by pack `a1b2…`, verifiable"), and honor a re-check diff when the pack rotates — "your result changed because regulation X changed". No visa service on the market offers auditable eligibility verdicts; the plumbing (pack hashes, parity events, D-7 recompute) exists. *Acceptance: a result page renders pack hash + last-verified date; rotating the pack in staging produces a visible "re-checked" state on an old result.* (P2)

**B2 — WhatsApp as the recovery and continuation channel, not just handoff.** Every SOTA reference recovers via email; Bali Zero's market lives on WhatsApp, and the repo already has enforced wa.me UTM, lead_intents capture, and an S7-style digest precedent (with its narrow Law-2 derogation — any extension needs Zero's ruling first). Beyond-SOTA move: a "continue on WhatsApp" branch of the magic-link flow — the customer chooses email link *or* WhatsApp message carrying the same one-time continuation link, collapsing the deliverability risk that makes email magic links fragile. *Acceptance: A/B on the result page — email-link vs WhatsApp-link continuation — measured with R2's events; PII posture reviewed against SYMBIOSIS Law 2 before build.* (P2, Legge-5 gate)

**B3 — The funnel measures its own honesty.** Generalize the response-time-claim pattern into a small conformance suite: every public numeric claim on funnel surfaces (rating, review count, price, processing time, success rate) must be produced by a committed query against a live store, and CI fails when a claim string appears without its query. This inverts the industry norm (marketing asserts, nobody checks) and the repo has already proven the pattern once. *Acceptance: `grep`-able claim registry; a PR adding an unmeasured "24h processing" string fails CI.* (P1 — cheap, differentiating)

**B4 — Session-replay-free field diagnostics.** Instead of adopting a heavy session-replay vendor (PII risk under UU PDP), extend the `app_form_started(field)` pattern with per-field error and dwell events (Zuko's model) — PII-free by the same Law-2 payload discipline already enforced in tests. Yields Zuko-class field analytics with zero third-party data egress: beyond SOTA for privacy-constrained CRO. *Acceptance: a dashboard query names the worst-friction field in the VOA wizard from one week of production events.* (P2)

## §Meta-pattern

The same disease found elsewhere in this program shows up here in its purest form: **the artifact written is treated as the thing in force.** The magic-link system is *complete* on the backend — non-enumerating, replay-safe, idempotent, contract-frozen, beautifully documented — and the emailed link lands on a page that has never read its token; `magic_link_store.py:131-133` even *says* the base URL "is a placeholder pending frontend confirmation," and nothing ever confirmed it. The analytics taxonomy is compile-time-proven and parity-tested — and the one funnel that earns money emits none of it. The checkout is contract-first and fail-closed — and has been failing closed in production, correctly, invisibly. In every case the *quality of the parts* concealed the *absence of the joint*: each lane shipped its half to its own standard, and no journey-level test ever walked an anonymous visitor from verdict to paid order. The one instrument that would have caught all three at once is the thing ASSEMBLY-LINE now mandates — journey-tests-red-first and a synthetic purchase probe — applied not per-component but across the seam between lanes, platforms (Fly/Vercel double flag), and channels (email → page).

## §Solo-operatore

Decisions only Zero can take:

1. **Arm Xendit** (`GARUDA_XENDIT_SECRET_KEY` on Fly + adapter wiring + test-mode first): credential-holding operator action; also the business call on go-live sequencing (ship-dark → 5% per the VOA mandate).
2. **`GARUDA_PUBLIC_ENABLED` on both platforms** — Vercel *and* Fly, same day, or the funnel stays half-lit; plus `GARUDA_MAGIC_LINK_BASE_URL` once R1 lands.
3. **WhatsApp continuation channel (B2)**: extends the Law-2 surface beyond the single named S7 derogation — needs an explicit ruling, not an engineering default.
4. **Recovery-email cadence and tone (R8)**: sending commercial reminder email to prospects is a brand/legal posture call (and Brevo sender reputation is a business asset).
5. **Which measured trust figures to publish (R6/B3)**: success rates and processing times are public claims about the business; only Zero decides what Bali Zero asserts about itself.
6. **Spend**: everything recommended runs on existing infrastructure (Brevo, Xendit, GA4, first-party store) — no new vendors proposed; if a form-analytics or replay vendor is ever considered instead of B4, that is a paid-API authorization decision under the 2026-06-04 rule.

## Sources

1. Baymard Institute cart-abandonment meta-analysis (via 2025-26 syntheses): https://www.zipchat.ai/blog/cart-abandonment-benchmarks-and-causes · https://redstagfulfillment.com/percentage-of-online-shoppers-abandon-their-cart/ · https://www.statista.com/statistics/1228452/reasons-for-abandonments-during-checkout-united-states/
2. GOV.UK Design System — Question pages: https://design-system.service.gov.uk/patterns/question-pages/ · One thing per page: https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/
3. GOV.UK / gov.scot — Check your answers: https://designsystem.gov.scot/patterns/check-answers · https://github.com/alphagov/government-service-design-manual/blob/master/service-manual/user-centred-design/resources/patterns/check-your-answers-pages.md
4. TurboTax interview/emotional design: https://producthabits.com/how-turbotax-used-design-and-emotion-to-solve-a-boring-problem-and-dominate-an-11b-industry/ · https://www.appcues.com/blog/how-turbotax-makes-a-dreadful-user-experience-a-delightful-one · https://contentdesign.intuit.com/voice-tone/turbotax/
5. Stripe optimized checkout & Link conversion data: https://stripe.com/newsroom/news/optimized-checkout-suite · https://stripe.com/newsroom/news/payments-revenue-uplift · https://stripe.com/resources/more/one-click-payments-101-how-they-work-and-their-benefits-for-businesses
6. Boundless Immigration pricing/trust model: https://www.boundless.com/ · https://www.boundless.com/guides/topics/costs-and-fees
7. Zuko form analytics & benchmarks: https://www.zuko.io/blog/which-form-fields-cause-the-biggest-ux-problems · https://www.zuko.io/blog/8-surprising-insights-from-zukos-benchmarking-data · multi-step vs single: https://ivyforms.com/blog/multi-step-forms-single-step-forms/ (Formstack figures)
8. Magic-link UX engineering: https://www.baytechconsulting.com/blog/magic-links-ux-security-and-growth-impacts-for-saas-platforms-2025 · https://blog.logrocket.com/ux-design/how-to-use-magic-links/ · https://www.descope.com/blog/post/magic-link-email-templates
9. Snowplow server-side vs client-side tracking: https://snowplow.io/blog/server-side-tracking-vs-client-side-tracking · https://snowplow.io/blog/server-side-vs-client-side-tracking
10. Klaviyo abandoned-cart benchmarks: https://www.klaviyo.com/uk/blog/abandoned-cart-email · https://attribuly.com/blogs/abandoned-cart-timing-cohort-benchmarks-templates/
11. Xendit Indonesian payment methods / QRIS: https://www.xendit.co/en/payment-channel/qris/ · https://www.xendit.co/en/products/all-payment-methods/

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** One confirmed and embarrassing finding: this lane calls the magic-link flow complete and replay-safe, while at the pin it carried the ownership hole that #5298 later closed — a reader could have taken a reassurance from this file about the exact mechanism that was broken. Also: the hardcoded candidate name quoted from the assessment page has been redacted here, and the live page it points at is ledgered separately.
