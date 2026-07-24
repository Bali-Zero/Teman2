---
adversarial_review: kimi
---

All evidence gathered. Writing the report.

## SEAT VERDICT — one line

**FIX-FIRST** — the analysis is an accurate state-of-the-world baseline (M1 effect, M2, M3, M6 all verified on disk), but it is not yet usable as the plan basis: its M1 mechanism is factually wrong and drives a wrong-shaped fix, critical-path step 4 hides a hard backend dependency that doesn't exist, and the gate set it proposes certifies a legally-correct engine, not a shippable user product.

---

## CLAIM-BY-CLAIM

**1. M6 "Track C engine wiring not started" — CONFIRMED.**
Grep over `apps/mouth/src/app/(visa-oracle)/visa-oracle/`: the only verdict computation is the synchronous `evaluate()` in `_lib/mock-engine.ts`, memoized at `_lib/flow.ts:298-301`. No `engine-client.ts`, `fact-mapper.ts`, `decision-adapter.ts`, or `fact-questions.ts` exists in `_lib/` (directory listing verified). The route imports only the `RecommendState` *type* from `@/lib/visa-oracle/types` (`_components/VerdictReveal.tsx:6`); `src/lib/visa-oracle/api.ts` is consumed solely by the v1 surface (`src/components/visa/VisaChat.tsx:9`) and its own test. The binding spec (`research/visa/2026-07-19-kimi-uiux-adaptation-spec.md`, 315 lines) exists and includes the Codex disposition table — verified in full.

**2. "Source swap behind a stable rendering contract" (the Kimi thesis the analysis adopts) — PARTIAL.**
The contract is stable at the **state level only**: `RecommendState` (`src/lib/visa-oracle/types.ts:28-33`) is value- and order-identical to `DecisionState` (`backend/services/visa_engine/enums.py:49-53`) — the PR0 freeze did its job, verified. But the **payload-level contract is not stable**: every component consumes `EvaluateResult`/`EvaluatedCandidate extends MockVisaCard` (`_lib/mock-engine.ts:31-46`) carrying `nameI18nKey`, `allInclusivePriceIDR`, `timelineDays`, 4-tier `eligibility`, `requirementI18nKeys` — none of which exist on the engine `Decision`, whose 18 required fields are `schema_version, decision_id, public_id, state, effective_at, observed_at, evaluated_at, rule_pack, facts_fingerprint, candidates, missing_facts, review_reasons, no_path_reasons, outage, quotes, notices, trace_sha256, decision_integrity` (`contracts/contract.schema.json#/$defs/Decision`, verified; `decision.schema.json` is a bare `$ref`). Candidates carry `rank`/`reason_codes`/`source_refs`; prices live in a separate `quotes[]`; eligibility tiers have no engine counterpart at all. "Source swap" understates it: this is an adapter layer + 4 new components + an async rework of a synchronous flow + a backend response-embedding deliverable.

**3. M6 "Does not block the SHADOW gate (measured on v1 surface)" — CONFIRMED, with a framing caveat.**
STEP-6c is a server-side fire-and-forget hook inside the v1 match handler (`backend/app/routers/visa_check.py:264-273` → `maybe_spawn_shadow_match`, `backend/services/visa_engine/shadow.py:679`); the Track C UI plays no role in G-a/G-c row generation. Caveat the analysis itself buries: the SHADOW gate is blocked anyway — by M1 (dead feed), M2 (zero pack rows), M3 (unarmed flags). "Wiring doesn't block the gate" is true and simultaneously the gate is no closer because of it. The sentence should read "wiring is *irrelevant* to the SHADOW gate" — which is precisely why the wiring sequencing error in step 4 (below) matters.

**4. Critical-path step 4 ("Parallel: … Track C wiring per Kimi spec") — PARTIAL / under-specified to the point of being wrong.**
There is **no public endpoint that accepts `ApplicantFacts` and returns a persisted `Decision` + resolved sources**. Verified: the existing `POST /api/v1/visa-oracle/recommend` is the v1 quiz-scorer taking `nationality/purpose/duration/family` (`backend/app/routers/visa_oracle.py:820-900`, registered public at `backend/app/auth/public_endpoints.py:458-463`); the engine's `evaluator.evaluate()` (`backend/services/visa_engine/evaluator.py:1042`) is reachable over HTTP only via the SHADOW hook, which discards the result. The Kimi spec's B.2/B.3 contract (`mode: ENGINE|CURATED` envelope per Codex disposition #5, embedded `sources: SourceRecordDTO[]` per A.4.1, pack-backed product display data per B.2 #3) is a **Track A backend deliverable that step 4 never enumerates**. Wiring cannot be e2e-tested until that endpoint *and* a real pack (step 1) exist. Step 4 also cannot start meaningfully before the Codex P0#1 interview splits (band→days, overstay/blacklist, clients/compensation) land — otherwise the mapper ships as "a wrong-answer machine" (disposition wording, binding).

**5. M1 mechanism — "There is NO Next.js route handler for it … and NO rewrite" — REFUTED.**
`apps/mouth/src/app/api/[...path]/route.ts:26-29` proxies **every** `/api/*` path — including `/api/visa/match` — to the Fly backend, preserving method and body (`POST` exported at :416-418). `next.config.ts:311` states this verbatim: *"NOTE: API proxying is handled by src/app/api/[...path]/route.ts"* — the analysis quoted the *next* line (:312, "Do NOT add rewrites…") and missed the sentence that contradicts its diagnosis. The observed 401s are fully explained one layer down: the backend auth floor rejects `/api/visa/match` because **it was never registered in `public_endpoints.py`** (verified: the registry contains `/api/v1/visa-oracle/*` at :458-478 and no `/api/visa/*` entry; the `submit_match` handler itself has no auth dependency, `visa_check.py:225-228`). Git history corroborates the regression window the analysis found in the DB: `public_endpoints.py` first landed **2026-04-25** (#108, "middleware + self-healing hardening"); the last `visa_checks` row is **2026-04-21**. The auth floor arrived four days later and silently killed the public funnel. The *effect* half of M1 (feed dead since ~launch week, every user degraded to the WhatsApp fallback via the swallowing `catch` at `src/app/visa/match/page.tsx:255-267`) is **CONFIRMED** — but the fix the analysis proposes ("Next route handler with a service token") builds a second proxy layer to solve an already-solved layer. The minimal fix is a registry entry (plus rate-limit, plus a CSRF check for anonymous POSTs), costing hours — and the sibling endpoints (`/api/visa/check/start`, `/api/visa/clock`, `GET /api/visa/match/{hash}`) are presumably equally dead and were never probed.

**6. M5 traffic-vs-G-a arithmetic — UNVERIFIABLE from this seat (no analytics access), internally sound.**
28 rows / ~4 days ≈ 7/day → ~5 months to 1,000. The conclusion (owner decision needed) stands regardless of my seat's scope.

**7. "35-FactPath→questionId registry" as a spec deliverable — CONFIRMED as designed, not built; vocabulary is 38.**
Spec A.3.2/C.2/D-table (`_lib/fact-questions.ts` NEW) verified. On disk the vocabulary is 38 paths = 35 applicant + 3 derived (`enums.py:383-446`); Codex disposition #8 already corrected the "35" wording inline. Any implementer reading the analysis's "35" literally will write a coverage test that fails or, worse, passes on the wrong set.

---

## MISSED — what the analysis does not see

**P0-1. The M1 misdiagnosis cascades into the plan's P0 step.** Step 0 budgets "diagnose intended path (two candidate layers: missing Next route vs backend auth floor)". That diagnosis is already answerable from disk — it's the registry omission, full stop — and the "likely fix" named (new Next route + service token) adds a secret-holding proxy hop and a second divergent `/api/visa/match` path that bypasses the battle-tested catch-all (CSRF promotion, cookie hygiene, login handling). One-line-class fix instead: register the `/api/visa/*` family in `public_endpoints.py` (Category VISA_ORACLE/FUNNEL precedent exists at :458-478), add rate-limiting, verify the double-submit CSRF check exempts anonymous public POSTs.

**P0-2. The ENFORCE read-path API does not exist and is on nobody's critical path.** Track C wiring is not a frontend PR. Until a public endpoint exists that takes canonical facts → persists a `Decision` → returns `{mode, decision, sources[], product display data}`, the wiring PR has nothing to wire to. This is step 4's true blocker and it's invisible in the plan.

**P1-1. The gates certify an engine, not a product.** G-a/G-c measure legal correctness and volume; G-b measures replay fidelity; G-d measures ops rollback. Nothing measures: empty states, latency, error choreography, EN/ID parity sign-off, disclaimer presence, accessibility, handoff PII, or funnel health. An engine can pass all four gates while the /visa-oracle page renders NEEDS_INPUT as an empty white card (see P1-2). Experience-side acceptance criteria proposed under Corrections #4.

**P1-2. NEEDS_INPUT currently renders an empty sheet — no disclaimer, no escape hatch.** `OutcomeSheet.tsx` has no NEEDS_INPUT body section at all, and the `result.state !== "NEEDS_INPUT"` guard (line 455) strips next-steps, WhatsApp CTA, assumptions receipt, *and the entire 4-line disclaimer block* (lines 575-580). In the mock this state is barely reachable via UI navigation, so nobody noticed. In engine mode NEEDS_INPUT is a *first-class terminal outcome* (spec A.3.2) — and as spec'd it would show a hero headline over nothing. The `NeedsInputPanel` design must explicitly re-include the shared footer/disclaimer block; neither the spec nor the analysis catches this.

**P1-3. The NeedsInputPanel deep-link mechanism is broken as specified.** Spec A.3.2: "tapping dispatches the existing `EDIT` action." But `EDIT` truncates history to a node *already in history* (`_lib/flow.ts:203-209`), and `truncateToNode` returns history unchanged when the target is absent (`_lib/flow.ts:135-142`) — a silent no-op. That is exactly the case for a missing fact whose question exists on a *different lane's* branch, or a question added mid-flight by a regulation delta. This failure mode has already bitten once (the category-step EDIT no-op documented at `_lib/flow.ts:386-403`). The panel needs an INSERT-at-frontier action; the spec must be amended before an implementer builds on it.

**P1-4. Three different "category" vocabularies, and G-a names none of them.** G-a says "all 7 interview categories exercised." The engine/DB vocabulary is **8** values (`work_remote, investor, work_employee, family, long_tourism, retirement, student, other` — migration 255 CHECK at `255_visa_shadow_evidence.sql:28-37`, mirrored in `services/visa_check/match_tree.py:45-47` and remapped at `shadow.py:111-122`). The v2 interview has **10** categories (`tree.ts:82-93`). **business and diaspora have no `request_category` value at all** — they cannot be "exercised" in the gate window as instrumented, and the criterion's "7" matches no vocabulary in the system. Either the gate measures the wrong thing or the criterion needs restating.

**P2-1. The WhatsApp handoff leaks facts into a third-party URL today.** `buildWhatsAppSummary` embeds the full Q:A dump into the wa.me `?text=` parameter (`OutcomeSheet.tsx:53-79`, used at :174-180). Codex disposition #4 confirms the fix (`public_id` receipt) is blocked on server-side public-result storage that was deferred — and that dependency appears nowhere in the analysis's critical path. Law-2-adjacent: this is client-adjacent data in a cleartext outbound URL.

**P2-2. The engine-mode candidate display model is undefined.** Mock candidates render from i18n keys and inline fields; the engine `Candidate` has none of them. A.4.1/B.2#3 say "pack-backed product data in the recommend response" but no schema/field list exists for name/tagline/timeline/requirements/checklist — so `decision-adapter.ts`'s output shape, the single most important type in the wiring PR, is unpinned.

**P2-3. Mixed-mode honesty for a 30-code pack.** With the minimal G-a pack (≥30 of 110 codes), most lanes will produce curated or NO_SUPPORTED verdicts. The per-lane/per-verdict provenance labeling for *partial* packs is unspecified; "the ruleset has no path" will be misread as "you don't qualify" unless coverage states are designed (the `notices` channel exists — A.7 #7 — but no acceptance criterion exercises it).

---

## CORRECTIONS — numbered edits to the plan

1. **Rewrite M1's mechanism and step 0's fix.** Proxy exists (`src/app/api/[...path]/route.ts`); break = `/api/visa/*` absent from `public_endpoints.py` since the auth floor landed 2026-04-25 (#108). Fix: register the visa_check family (match, check/start, clock, GET match/{hash}) with rate-limit; verify CSRF posture for anonymous POSTs; smoke-test = first `visa_checks` row. Do **not** build a service-token Next route.
2. **Insert critical-path step 1.5: "ENFORCE read-path API."** Public evaluated endpoint (facts in → `Decision` + `sources[]` + `mode` envelope + candidate display data out), registered public, rate-limited; every legal `Reason` carries ≥1 `source_ref` (Codex #3). Explicit blocker of Track C wiring.
3. **Split step 4 into 4a/4b/4c.** 4a = frontend skeleton (fact-mapper with Codex P0#1 splits, engine-client, decision-adapter, VerdictSource, async flow rework) — developable *now* against `contracts/contract.schema.json` fixtures. 4b = citation/provenance components — blocked on 1.5. 4c = e2e — blocked on the real pack (step 1). Also fold in: WhatsApp de-PII + server `public_id` receipt (or an explicit Law-2 deferral note).
4. **Add experience-side gate set (E-gates) as ENFORCE prerequisites alongside G-a…G-d:**
   - **E-a Coverage honesty:** per-lane verdict correctness against the minimal pack; not-covered-yet copy via `notices`; zero "no path" misreads (10-lane test matrix).
   - **E-b Latency:** p95 evaluate ≤4s on throttled 3G; pending skeleton ≤200ms after the confirmation CTA; no layout shift on verdict arrival; skeleton-never-spinner (spec A.3.5).
   - **E-c Error choreography:** full B.4 flip-matrix + 500/timeout/garbage-DTO e2e on real devices; labeling invariant asserted in CI (prototype badge ⇔ curated mode, B.4).
   - **E-d EN/ID parity:** existing parity tests green over all new key groups; native-speaker ID sign-off recorded as an artifact; `documentElement.lang` sync (spec C.6 gap) verified; `BODY_FIRST` honored on all new outcome copy.
   - **E-e Disclaimer presence:** the 4-line block (`OutcomeSheet.tsx:575-580`) renders on **all five** terminal states including NEEDS_INPUT (fix the :455 guard) and in print.
   - **E-f Accessibility:** axe zero-critical across all 5 states + NeedsInputPanel; focus-to-heading fires when the *async* verdict lands, not only on node transition; live-region announcement; keyboard-complete NeedsInputPanel rows; print includes Sources & verification; Lighthouse a11y ≥95.
   - **E-g Handoff PII:** wa.me URL carries `public_id` only, no facts (or documented deferral); QR/link byte-identity test kept.
   - **E-h Degraded catalog:** pack yielding zero applicable products per lane → honest coverage state; never a crash, never a fabricated candidate (adapter unit tests).
   - **E-i Funnel health:** NEEDS_INPUT rate, per-state distribution, handoff rate measured during the SHADOW window with a product bar (e.g. NEEDS_INPUT <10% of completed interviews) before ENFORCE.
5. **Restate G-a's category clause** as the 8-value `request_category` enum, and either add business/diaspora instrumentation or explicitly exclude those lanes from the gate window (P1-4).
6. **Spec errata for implementers (amend the Kimi spec, don't route around it):** NeedsInputPanel dispatches an insert-at-frontier action, not `EDIT` (P1-3); NEEDS_INPUT includes the shared footer/disclaimer (P1-2); registry shape is `FactPath → questionId | notCollected` over all **38** paths with `commercial.*` marked not-collected-by-design; pin the candidate display model (P2-2); UnknownReason derivation needs per-question "verified-only" metadata to distinguish `NOT_PROVIDED` from `UNVERIFIED` (absent from `OracleQuestion`, `tree.ts:39-50`).

---

## Mandate detail — the smallest correct wiring PR (item 1)

**Backend prerequisite (separate PR, step 1.5 above).** Frontend PR itself:

| File | Change |
|---|---|
| `src/lib/visa-oracle/types.ts` | ADD `DecisionDTO`/`SourceRecordDTO`/`VerdictSource` — generate from `contract.schema.json#/$defs` (do not hand-write; `schema_export.py` exists for this) |
| `src/lib/visa-oracle/api.ts` | ADD `evaluateFacts()` + `parseDecisionResponse()` mirroring `parseRecommendResponse`'s defensive discipline (`api.ts:108-154`); KEEP all v1 functions — `VisaChat.tsx:9` depends on them |
| `_lib/fact-mapper.ts` | NEW — `OracleFacts → ApplicantFacts`; per Codex P0#1: transmit `UNKNOWN`, never representative values, until the three interview splits land |
| `_lib/engine-client.ts` | NEW — POST, 4s `AbortController` timeout, single retry, runtime validation |
| `_lib/decision-adapter.ts` | NEW — DTO → `VerdictSource`; invalid payload → synthesized `TEMPORARILY_UNAVAILABLE` (never render, never silent mock fallthrough) |
| `_lib/flow.ts` | MODIFY — replace the sync `useMemo(evaluate)` (:298-301) with async verdict state fired at the confirmation CTA; reducer stays pure; history/EDIT/prune untouched |
| `_components/OracleShell.tsx` | MODIFY — own `VerdictSource`, pending skeleton, mid-session flip (B.4), `lang` sync |
| `_components/VerdictReveal.tsx` | MODIFY — engine mode retires the 4-tier chip (:119-127) → single "Supported path under current rules" chip (Codex #7 copy, never "eligible/verified") |
| `_components/OutcomeSheet.tsx` | MODIFY (largest) — citations, tri-state price, NeedsInputPanel host **with** footer/disclaimer, retryable TEMP, dynamic provenance stamp replacing the static one (:568-572), WhatsApp payload switch |
| NEW components | `CitationChip`, `CitationList`, `NeedsInputPanel`, `NoticesStrip` |
| `_lib/fact-questions.ts` | NEW — 38-path registry + coverage test |
| `_lib/i18n.ts` / `oracle.css` | MODIFY additive |
| `mock-engine.ts` | **KEEP verbatim** — it is the curated/rollback renderer (spec D-table); "removal" is explicitly wrong |

**Under-specified for an implementer:** endpoint URL/payload (no route exists); candidate display model (P2-2); NeedsInputPanel dispatch (P1-3); `mode` envelope field (Codex #5 — backend doesn't emit it); NOT_PROVIDED-vs-UNVERIFIED metadata (Correction 6); pending-state skeleton spec beyond "never a spinner."

## Mandate detail — NEEDS_INPUT + registry feasibility (item 2)

The interview persists `OracleFacts = Record<string, string>` (`tree.ts:56`) across **8 questions** vs **35 applicant FactPaths**. Clean mappings exist for ~9 paths. Three drafted mappings are legally unsafe *as question shapes on disk*: `tourism_duration` 3-band → `intent.stay_days` (`tree.ts:194-205` — a band cannot yield canonical days), `review_gate` item `overstay_or_blacklist` → `{OVERSTAY}` (`tree.ts:229-237` — conflates two distinct violations), `remote_clients` 3-way → two legally distinct facts (`tree.ts:163-178`) — Codex P0#1 already adjudicated all three: transmit UNKNOWN until the questions split. What **breaks**: (a) 7 of 10 lanes force-review locally (`mock-engine.ts:211-213` + `BEHAVIORAL_CATEGORIES`, `tree.ts:99-103`), so their facts never exist and NEEDS_INPUT deep-links have nothing to link to — fallback CTA is the honest path, fine, but the spec's "rare by design" framing is wrong for 70% of lanes; (b) `person.nationalities` has no question — without it the calling-visa overlay and BVK nationality-only rule (Permen Imipas 10/2026; the mock already documents this exact limitation at `tree.ts:246-258`) make the highest-volume tourism lane systematically abstain at ENFORCE — the C.3.4 nationality question is **blocking ENFORCE**, per Codex #6; (c) the EDIT no-op (P1-3); (d) `criminal_record`/`health_flag`/`prior_refusal` have no FactPath and correctly stay UI-side force-review triggers (spec A.7 — consistent, keep). Verdict: feasible **if** the registry is `questionId | notCollected` over 38 paths with a coverage test, the nationality/birth_date questions land first, and the three unsafe mappings ship as UNKNOWN.

## Mandate detail — FASE 2 priorities from UX (item 4)

1. **Tourism depth + the `nationality` shared question** — top organic volume (GLM §2 frequency #1) and currently un-evaluable: BVK is nationality-only, and the mock downgrades A1/B1 to "conditional" *purely* because nationality is uncollected (`tree.ts:246-258`). The Codex P0#1 exact-days fix rides along. Highest traffic × highest legal exposure (dead B211* codes).
2. **Business** — adjacent B211/D12 family, no new question kinds, smallest content surface.
3. **Invest & golden** — revenue flagship (verified Rp52.1T stats), GLM I1–I6 fully drafted; heaviest legal microcopy; needs nationality in place first for the calling-visa overlay.
4. **Retirement** — bundle the `birth_date` shared question (55+); E33 already in the catalog.
5. **Family** — high volume but sponsor-status/document-authentication complexity → review-heavy.
6. **Diaspora** — bespoke ex-WNI routes, low volume, high complexity.
7. **Study** — lowest Bali Zero frequency. `other` stays force-review by design (C.3.3 is correct — keep it).

**Microcopy carrying legal weight** (wrong words = wrong legal advice): I3 amount bands (⚑ thresholds — a misstated boundary fabricates eligibility); R2 income-floor figure; the Rp1,000,000/day overstay fine (state it exactly or omit it — GLM rule 5); the Bridging ≥3-day filing cutoff (Permenkumham 11/2024 — the 1–2-day lane must never offer bridging; correctly encoded at `tree.ts:517-519`, the *copy* must not contradict it); W3 calling-visa conservative-default wording (adds time; must not read as accusation); the I1=d property/freehold honesty note; the R3 183-day tax note; the chip copy ("Supported path under current rules," Codex #7); the review-gate why-we-ask ("legally require human assessment" is a legal claim); GLM §5–6's fee-split ledger — superseded by R1, must never ship.

---

## SEQUENCING VERDICT

Steps 0→1→2→3 (feed → pack → arm → window) are correctly ordered. Two deltas:

1. **Step 4 as written is not a parallel item — it's a dependency chain.** Track C wiring (4a→4b→4c per Correction 3) depends on the unlisted ENFORCE API (new step 1.5) and the pack (step 1); its e2e (4c) can overlap the collection window but its provenance components cannot precede 1.5. The plan should show: `0 → (1 ∥ 1.5 ∥ G-b) → 2 → (3 ∥ 4a/4b) → (E-gates + 4c + G-d drill) → flip`.
2. **Pull G-b's independent replay forward.** It's cheap, depends on nothing in the window, unblocks Track D (M8), and derisks the only gate whose "grader ≠ engine" artifact is still missing. It currently sits inside the step-4 grab-bag; it belongs beside step 1.

One open question the panel should force the analysis to answer rather than defer: **if the v1 feed fix is a one-line registry entry, does SHADOW stay on the v1 quiz (7 shallow fields, `QuizAnswers` at `types.ts:1-13`) or is that feed too fact-poor to make G-b/G-c meaningful against a 35-fact engine?** The v1 quiz exercises purposes but almost none of the load-bearing facts (no expiry, no violation history, no employer facts) — a SHADOW window on it measures volume and grounding plumbing, not the engine's real decision surface. That trade-off deserves an explicit owner-visible sentence in the plan.
## Adversarial review

Fable 5 refined its C6 claim: 'matches no vocabulary' was overstated (collector's 7 = Purpose minus OTHER IS a real in-code vocabulary; recorded in the synthesis addendum). All other findings stand. None survived, 1 raised.
