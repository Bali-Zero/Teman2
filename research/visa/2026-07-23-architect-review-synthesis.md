---
date: 2026-07-23
domain: visa
client_case: none
author: Kimi (Air-M5) — architect session, synthesis of the 4-seat adversarial panel
status: DEFINITIVE PLAN — pending owner decisions D1/D2/D3
panel:
  - gemini (agy, Gemini 3.1 Pro High) — regulatory width — verdict FIX-FIRST
  - codex (codex CLI, gpt-5.5 high, read-only sandbox) — architecture red-team — verdict FIX-FIRST
  - glm → SEAT DEGRADED (Keychain token absent via SSH on Pro) → house Sonnet design seat — verdict FIX-FIRST
  - web-grounded (house Sonnet + WebSearch/live curl) — verification — verdict FIX-FIRST
sources:
  - research/visa/2026-07-23-architect-state-analysis.md
  - research/visa/2026-07-23-architect-review-gemini.md
  - research/visa/2026-07-23-architect-review-codex.md
  - research/visa/2026-07-23-architect-review-web-grounded.md
  - research/visa/2026-07-23-architect-review-design-house.md
  - research/visa/2026-07-23-architect-review-glm-FAILED-seat-degraded.md
---

# Visa Oracle v2 — definitive correction + completion plan (panel synthesis)

**Unanimous verdict: FIX-FIRST (4/4).** The engine is well-built and the blocker inventory is
accurate, but the original analysis carried one wrong mechanism (M1), one wrong regulatory
date, one refuted sub-claim, and one structural evidence flaw (SHADOW-on-v1 thin facts) that
together change the critical path. Every correction below was verified on disk or live by the
orchestrator — the panel's load-bearing claims are not self-attested.

## PART 1 — Corrections to the analysis (adjudicated)

**C1. M1 mechanism — the panel REFUTED "no Next route; POST never reaches the backend."**
The catch-all proxy `apps/mouth/src/app/api/[...path]/route.ts` (in repo since `7c1d23a686`,
2025-12-19) forwards every `/api/*` to the Fly backend; the live 401 carries
`fly-request-id`/`via: fly.io` and a FastAPI body byte-identical to the direct `kita` call.
Single failure layer: **backend auth floor** — `/api/visa/*` was never registered in
`apps/backend-rag/backend/app/auth/public_endpoints.py` (the registry has `/api/v1/visa-oracle/*`
at :458-478 and `/api/knowledge/visa` at :292). Root cause dated: the auth floor landed
**2026-04-25** (`57d50a7056`, PR #108 "middleware + self-healing hardening"); the last
`visa_checks` row is **2026-04-21**. The public funnel died silently 4 days after launch.
Sibling endpoints probed live 2026-07-23: `/api/visa/clock` and `/api/visa/match/{hash}` are
equally 401 — the fix scope is the whole `/api/visa/*` family.

**C2. Kepmen M.IP-08/2025 effective date: 2025-06-01** (web seat, primary source: official
decree PDF on kemenimipas.go.id — full number **M.IP-08.GR.01.01/2025**, signed 2025-05-02,
dictum KELIMA "berlaku setelah 30 hari" → 2025-06-01; EY concurs). The ledger's `2026-06-02`
is the wrong year; the round-4 recheck's `2025-06-02` is off by one day. Bonus: dictum
KEEMPAT revokes Kepmenkumham M.HH-02.GR.01.04/2023 → the legal death of the B211* codes has
a precise basis.

**C3. "Number-collision with Permenkumham 10/2026 (Second Home)" — REFUTED.** The real
Permenkum 10/2026 (2026-01-28) regulates notary beneficial-owner (PMPJ) obligations. Second
Home rests on SE Ditjen Imigrasi IMI-0740.GR.01.01/2022 (+ indexes E28B/E33F). The round-4
recheck note parked on the closed B branch **must be corrected before any re-landing**.

**C4. BVK precision (Permen Imipas 10/2026):** signed 2026-07-07, effective 2026-07-09;
eligibility by nationality/SAR/entity only; adds Kazakhstan, Macau SAR, Belarus (absorbing
10/2025's Türkiye/Brazil/Peru). Official imigrasi.go.id list = **19 states/SARs + 1 entity
class** (Singapore PRs via designated checkpoints). This regulation is 14 days old — Track B
content and any BVK rules must be authored against 10/2026, not 10/2025.

**C5. SHADOW-on-v1 collects structurally weak gate evidence.** Verified in
`shadow.py:249-301`: STEP-6c maps v1's 4 wizard fields to only **3 of 35** applicant FactPaths
(`person.nationalities`, `intent.purposes`, `intent.stay_days`); the other 32 are defaulted to
`UnknownFact(NOT_PROVIDED)`; `budget` is collected but not even passed (`visa_check.py:267`).
With "UNKNOWN can't increase eligibility" structural, most products degrade to
NEEDS_INPUT/HUMAN_REVIEW. A v1 window measures volume + grounding plumbing, **not** the
engine's real decision surface. (Independently found by orchestrator + Codex + design seat.)

**C6. Category vocabularies: the gate's "7 categories" matches no vocabulary in the system.**
Migration 255 CHECK = **8** values (7 substantive + `other`); the v2 interview has **10**
categories; `business` and `diaspora` have no `request_category` value at all. The criterion
must be restated (see D1).

**C7. The "source swap" wiring is understated.** State-level contract is stable (PR0 freeze
verified), but the payload-level contract is not: components consume `MockVisaCard`-derived
shapes; the engine `Decision` has 18 required fields of a different shape. Wiring = adapter
layer + 4 new components + async rework + a **backend read-path deliverable that does not
exist** (see P0-3).

## PART 2 — The correction plan (fix now, pre-gate)

Ordered. Each item names its scope owner per the TRACKS table.

**P0-1 — Repair the v1 feed (ops hotfix, Track A/backend; NOT gate evidence).**
Register the `/api/visa/*` family (match POST, match/{hash} GET, clock, check/start) in
`public_endpoints.py` with per-endpoint rate-limit; verify CSRF posture for anonymous public
POSTs. One-line-class fix, hours not days. Smoke test = first new row in `visa_checks`.
Do **not** build a service-token Next route — the proxy layer already exists and is
battle-tested (CSRF promotion, cookie hygiene, login handling).

**P0-2 — Telemetry so this never goes blind for 3 months again (with P0-1).**
Submit-failure client event (today `tracker.formSubmitted` fires on attempt, the swallow
emits nothing) + an ingestion-rate alert on `visa_checks` (zero rows in 24h on a live funnel
= page someone). 

**P0-3 — Build the evaluate read-path API (NEW Track A deliverable; gate-blocking).**
Public, exact, rate-limited backend endpoint: canonical `ApplicantFacts` in → persisted
`Decision` + resolved `sources[]` + `mode` envelope (ENGINE|CURATED) + pack-backed candidate
display data out. Abuse controls per Codex: schema validation, body-size cap, IP/session-hash
rate limit, no raw PII logs, no broad service impersonation. Every legal `Reason` carries ≥1
`source_ref`. SHADOW moves to this endpoint — full-fact evidence. This also unblocks Track C
wiring for real (it is the thing the UI wires to).

**P0-4 — Author the real RulePack against the full-fact schema (Track A signing + Track B
content; gate-blocking).** First slice ≥30 codes with the mandated high-risk set: **E28
family** (Golden Visa, Rp52.1T at stake), **E33 family** (remote work, high volume), **BVK**
(nationality-only edges per 10/2026), **Bridging** (overstay exact-date math), plus the
B211*-death remap grounded on dictum KEEMPAT. Source records must satisfy G-c hygiene from
day one: `VERIFIED` status, canonical URL, legal/recorded validity periods (the collector
checks all of it). Sign on M5, provision `visa_activation_executor`, activate in PRODUCTION.

**P1-1 — Pull G-b's independent replay forward (beside P0-4, not in the window).**
Cross-family grader replays the canonical PR5 suite + produce the replay-report artifact;
port M5's metamorphic properties (fact-order / rule-order invariance, monotonicity) onto the
real `evaluator.evaluate()`. Cheap, independent of everything, unblocks Track D.

**P1-2 — Amend the Kimi UI/UX spec (errata, binding on the implementer).**
(a) NeedsInputPanel dispatches an **insert-at-frontier** action, not `EDIT` (truncateToNode
is a silent no-op when the node isn't in history); (b) the shared footer/disclaimer block
renders on **all five** terminal states — today the `OutcomeSheet.tsx:455` guard strips it
from NEEDS_INPUT; (c) the FactPath→questionId registry covers **38** paths (35 applicant + 3
derived) with `commercial.*` marked not-collected-by-design; (d) pin the candidate display
model (name/tagline/timeline/requirements/checklist fields the pack must supply); (e)
per-question "verified-only" metadata to distinguish `NOT_PROVIDED` from `UNVERIFIED`.

**P1-3 — WhatsApp de-PII (Law-2-adjacent).** `buildWhatsAppSummary` embeds the full Q:A dump
in the wa.me URL today (`OutcomeSheet.tsx:53-79`). Ship the server-side `public_id` receipt
(handoff URL carries only the id) or record an explicit deferral decision.

**P1-4 — Restate the G-a category clause (with D1).** Use the 8-value `request_category`
enum as the vocabulary; decide whether `business`/`diaspora` lanes get instrumentation or are
explicitly excluded from the window.

## PART 3 — The completion plan (DAG to gate-green, then flip)

```
0.  P0-1 v1 feed repair + P0-2 telemetry            [ops hotfix, non-gating, hours]
1.  PARALLEL:  P0-4 RulePack first slice            [Track A+B]
             ∥ P0-3 evaluate read-path API          [Track A]
             ∥ P1-1 G-b independent replay          [cross-family grader]
             ∥ Track C 4a (skeleton: fact-mapper, engine-client,
               decision-adapter, async flow) against contract fixtures
2.  Arm SHADOW on the NEW endpoint: VISA_ENGINE_MATCH_MODE=shadow +
    VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON (operator action, runbook exists)
    Smoke: 1 v2 interview → 1 visa_decisions row with full-fact provenance
3.  Collection window (semantics per D1)            [≥7 consecutive days]
  ∥ Track C 4b (citation/provenance components — unblocked by P0-3)
  ∥ Traffic plan execution (see D1 note — the flagship needs it regardless)
4.  E-gates (below) + Track C 4c e2e + G-d rollback drill (recorded)
5.  FLIP (session pre-authorized when ALL green) + before/after evidence capture
```

**E-gates (experience acceptance, new ENFORCE prerequisites — proposed by the design seat,
adopted here subject to D3):** E-a coverage honesty per lane (10-lane matrix, `notices` for
partial packs) · E-b latency (p95 evaluate ≤4s throttled 3G, skeleton ≤200ms, no layout
shift) · E-c error choreography (full flip-matrix e2e, labeling invariant in CI) · E-d EN/ID
parity (tests + native sign-off artifact + `lang` sync) · E-e disclaimer on all 5 states incl.
print · E-f accessibility (axe zero-critical, async-verdict focus/live-region, keyboard
NeedsInputPanel, Lighthouse ≥95) · E-g handoff PII (`public_id` only) · E-h degraded catalog
(honest zero-product states) · E-i funnel health (NEEDS_INPUT rate <10% of completed
interviews during the window, per-state distribution reviewed).

**Track C wiring sequence (per design seat):** 4a frontend skeleton now (against
`contract.schema.json` fixtures) → 4b provenance components after P0-3 → 4c e2e after the
real pack. `mock-engine.ts` is KEPT verbatim — it is the curated/rollback renderer.
Interview prerequisites before the mapper ships real facts: the three Codex-adjudicated
question splits (duration band→exact days, overstay/blacklist split, clients/compensation
split) and the **nationality shared question** (blocking: BVK is nationality-only per
10/2026 — the highest-volume lane otherwise abstains systematically at ENFORCE).

**Track B FASE 2 priority order (UX-ranked by the design seat):** 1) Tourism depth +
nationality question (top volume × highest legal exposure) 2) Business 3) Invest & golden
4) Retirement (+birth_date) 5) Family 6) Diaspora 7) Study. Microcopy carrying legal weight
recorded in the design lane's report (amount thresholds, overstay fine figure, Bridging
≥3-day cutoff, calling-visa wording, chip copy).

## PART 4 — Owner decisions required (the plan forks here)

**D1 — G-a semantics + threshold.** The panel surfaced three problems: organic traffic is
~7/day at best (1,000 in 7 days unreachable organically — Gemini's power-law point: you'll
never organically hit 30 codes in 7 days); v1 facts are too thin for verdict-quality evidence
(C5); the category vocabulary is undefined (C6). Options:
- **(a) Restate G-a:** volume+window on the v2 full-fact endpoint with **real traffic**,
  breadth (7 categories/30 codes) guaranteed by **declared synthetic supplementation**
  (Gemini's proposal — synthetic requests are marked as such in the audit substrate).
- **(b) Real-traffic-only, longer window:** keep 1,000 real requests, drop 7d → e.g. 60d or
  "until breadth is met", accept the calendar cost (Codex-leaning purity).
- **(c) Hybrid (recommended):** SHADOW window on the v2 endpoint; G-a volume from real
  traffic over a stated window; breadth proven by the gold-persona fleet expanded to the 30
  priority codes (G-b extension, still "real engine, designed cases") + synthetic traffic
  explicitly labeled; the criterion text is rewritten to say exactly this.
Any change to the criterion re-opens owner sign-off per the firebreak ("threshold proposed +
set by the session per Zero's instruction" — the session proposes, Zero sets).

**D2 — Pack completeness for ENFORCE.** Gemini: the flip requires the **full 110-code** pack
("zero wrong answers" flagship can't launch with 72% of the catalog missing); the 30-slice is
only for the SHADOW window. Recommended: adopt — ENFORCE gates on 110 signed codes; the
window may start on the 30-slice.

**D3 — E-gates.** Add the 9 experience gates as ENFORCE prerequisites alongside G-a…G-d
(the current four certify a legally-correct engine, not a shippable product). Recommended:
adopt.

## PART 5 — Standing risks after flip

- **Regulatory decay** (Gemini P2): cadence ~3-4 months (5/2025 Mar → M.IP-08 Jun 2025 →
  10/2025 → 10/2026 Jul). A green gate certifies the engine as measured; any legal-content
  edit re-opens the gate per the firebreak. Watch items: BVK list amendments, E28 threshold
  changes, Bridging IT-integration rules.
- **Negative-constraint coverage** (Gemini P1): G-c checks citation validity, not revocation
  evasion — the grader should explicitly penalize dead codes (B211*) and revoked laws
  (Permenkumham 36/2021) in outputs. Fold into P1-1.
- **CORS**: `OPTIONS /api/visa/match` → 404 (web seat) — fine same-origin, blocks future
  cross-origin consumers (partner embeds). Note for the read-path API (P0-3).

## Evidence receipts

- Live probes 2026-07-23 (orchestrator + web seat, consistent): www/kita `/api/visa/match`
  GET+POST 401 (`fly-request-id` present), `/api/visa/clock` 401, `/api/visa/match/{hash}`
  401, `/api/health` 200, `/visa-oracle` 200+noindex, `/visa-v2` 308.
- Prod DB (read-only, orchestrator, re-runnable): migrations 250–255 applied;
  `visa_rule_packs`/`visa_ruleset_activations`/`visa_source_records`/`visa_decisions` = 0 rows;
  `visa_checks` = 28 rows, min 2026-04-18, max 2026-04-21.
- Git: `public_endpoints.py` created `57d50a7056` 2026-04-25 (PR #108); catch-all proxy
  created `7c1d23a686` 2025-12-19.
- Fly: only `VISA_ENGINE_TRUST_STORE_KEYS_JSON` present (digest `a68f076bc9993f0c`);
  release v3897 deployed 2026-07-23.
- Regulatory: official decree PDF (kemenimipas.go.id), JDIH BPK Permen Imipas 5/2025,
  imigrasi.go.id BVK list, ANTARA/VnExpress/IMI Golden Visa 2026-05-18 — URLs in the
  web-grounded lane file.
