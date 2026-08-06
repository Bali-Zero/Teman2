# Visa Oracle V2 — production-readiness gate

Initial audit date: 2026-08-04 WITA

Completion pass: 2026-08-06 WITA

Machine: Mini-Pro2 (`arm64`)

Current integration branch:
`agent/mini-pro2/backend-rag/visa-oracle-v2-final-integration`

Historical post-rebase independently graded code revision:
`07625dfea22f9040cd370f2a448128ac744424e7`

Initial audited baseline: `550f95f7a`

The initial code candidate was rebased onto
`origin/main` `c260dd1b8e31e0970a6f395ca4850160f991deb2`; all code gates and
the independent review in this dossier were repeated against the resulting
revision above. This addendum changes evidence only. The former frozen
candidate `3dff0b95f1535ca2a11f6fbfbacf8f77af3bed13` remains historical
evidence, not the reviewed merge target.

The 2026-08-06 completion pass supersedes the historical final-gate claims
below where explicitly noted. It adds an anonymous query-free proxy boundary,
PII-free middleware handling, full keyboard-only EN/ID journeys, a real
same-pass deterministic evaluation trace with migration `265`, and a bounded
unmocked browser -> Next -> FastAPI -> signed TEST RulePack -> disposable
PostgreSQL smoke. The smoke proves persistence, retention binding, trace/HMAC
integrity and exact idempotent replay; it deliberately produces
`HUMAN_REVIEW_REQUIRED` because the checked-in signed pack has no approved
source-specific freshness policy.

This report preserves the initial AS-IS findings separately from the final
gate. A green legacy test is not treated as evidence of engine authority: the
baseline browser suite intentionally renders the mock result while discarding
the backend response.

## G0 — verified AS-IS

Runtime path at the initial baseline:

```text
/visa-oracle
  -> OracleShell
  -> useOracleFlow
  -> mock-engine.evaluate()        visible candidate authority
  -> VerdictReveal / OutcomeSheet

verdict reached
  -> manual fact mapper
  -> POST /api/visa-oracle/evaluate
  -> signed deterministic engine
  -> SHADOW audit persistence
  -> response ignored by the browser
```

| Capability                                         | Initial state  | Verified evidence                                                                    |
| -------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------ |
| Signed RulePack, compiler and tri-state evaluator  | DONE           | Valid Ed25519 signature; 38 products, 110 rules, 28 sources                          |
| State precedence and monotone UNKNOWN              | DONE           | Evaluator tests and target backend suite                                             |
| Bitemporal repository, HMAC and anti-rollback      | DONE / PARTIAL | Runtime exists; activation executor role is not provisioned locally                  |
| Decision persistence                               | PARTIAL        | SHADOW envelope exists; persistence failure did not block a future ENFORCE response  |
| Deterministic trace and decision integrity         | MISSING        | Both response fields were `null`                                                     |
| PricingTool and Bali Zero service axis             | MISSING        | Engine quotes empty; UI prices hardcoded in the mock catalog                         |
| Source freshness and clock                         | MISSING        | Dates/status exist but no fail-closed freshness policy                               |
| Typed OpenAPI and derived TypeScript               | MISSING        | Evaluate request body/response were generic objects                                  |
| Public decision authority                          | MOCK           | `flow.ts` called `mock-engine.evaluate()`; backend was fire-and-forget               |
| Ten interview categories                           | PARTIAL        | Ten entry tiles; seven jumped directly to review and only three had branch questions |
| Edit/back, stale-fact pruning, EN/ID and QR/print  | DONE / PARTIAL | Core behavior tested; no resume or consent receipt                                   |
| Legal / operational / Bali Zero service separation | MISSING        | Collapsed in both wire contract and outcome                                          |
| Network timeout, abort, safe retry and idempotency | MISSING        | No production client control or server idempotency key                               |
| Ingress security                                   | PARTIAL        | 32 KiB cap; duplicate JSON keys and `application/jsonp` were accepted                |
| Production golden/adversarial evidence             | PARTIAL        | Broad suite green; main golden vectors used a synthetic pack                         |
| Responsive and accessibility browser gate          | PARTIAL        | Static support existed without current 320 px/keyboard/axe proof                     |
| Prototype/noindex and legacy helpers               | OBSOLETE       | Kept the v2 hidden and described real output as sample data                          |

### Initial test evidence

- Backend target: 1,447 passed, 1 skipped. The skip is the unprovisioned
  `visa_activation_executor` role.
- Frontend typecheck: passed in the integration worktree after resolving the
  worktree-only dependency path.
- Target Vitest: 145/147. Two timing-dependent byte-identity assertions failed
  on Framer Motion inline styles; they did not test decision parity.
- Chromium baseline E2E: 10/10 passed. These tests exercised the visible mock,
  not backend authority.

### Initial browser evidence

- `artifacts/visa-oracle-v2/as-is/desktop-light.png`
- `artifacts/visa-oracle-v2/as-is/mobile-320-dark.png`

At 320 px the language switch was clipped and the footer/widget overlapped.
The requested dark color scheme still rendered a light first paint. Both
viewports showed prototype/sample-data copy and decorative background bubbles.

### Source validation note

The production pack already includes the July 2026 BVK additions. The current
official regulation record also shows that Permenkumham 11/2024 was partially
revoked by Permen Imipas 3/2025. A whole-record `VERIFIED` flag is therefore
insufficient by itself: decisive claims must remain joined to unaffected
locators and current legal periods.

The live national Calling Visa page was fetched again on 2026-08-04. Its HTML
listed six countries: Afghanistan, Israel, North Korea, Liberia, Nigeria and
Somalia. The signed rule `review.calling-visa` contains those six plus Guinea
and Cameroon. This is conservative over-review rather than an unsafe omission,
but it is still source/rule drift: the current national page no longer supports
the exact signed value set. A regional Immigration page concurrently exposed a
different nine-country list, so the discrepancy cannot be repaired by silently
editing the pack.

| G1 source                                                                                                                                                                                                 | Authority                         | Evidence captured                                                                                                                            | Gate consequence                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| [National Calling Visa list](https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa)                                                                                | Ditjen Imigrasi national portal   | Live raw HTML SHA-256 `e11fd38538f7df00d081949fc40e123127e4be6cca9d20187fc8b83c632beaf7`; six-country rendered list                          | Re-author source record/rule and sign a new sequence; do not mutate the signed pack |
| [Regional Calling Visa list](https://kanwilsultra.imigrasi.go.id/wna/daftar-subjek-voa-bvk-calling-visa)                                                                                                  | Ditjen Imigrasi Sulawesi Tenggara | Conflicting nine-country official list                                                                                                       | Freshness/applicability policy must define authority and conflict handling          |
| [Cameroon removal press release](https://www.imigrasi.go.id/siaran_pers/2023/11/29/siaran-pers-kamerun-dicabut-dari-daftar-calling-visa-dirjen-imigrasi-ada-pertimbangan-ekonomi-dan-keamanan?lang=id-ID) | Ditjen Imigrasi national portal   | Kepmen M.HH-05.GR.01.06/2023, approved 2023-11-23; direct capture SHA-256 `6eae2f0d09278c64ce6d11d908dbb7dc47b11377d687e4ee3682081d9bff0681` | Remove `CM` in replacement national overlay; retain PDF archive requirement         |
| [Permenkumham 11/2024](https://peraturan.bpk.go.id/Details/285156/permenkumham-no-11-tahun-2024)                                                                                                          | BPK regulation record             | Partial-revocation relationship                                                                                                              | Verify every decisive locator against the amending regulation                       |
| [Permen Imipas 3/2025](https://www.peraturan.go.id/id/permenimipas-no-3-tahun-2025)                                                                                                                       | Official regulation portal        | Amending/revoking instrument                                                                                                                 | Required input to the locator ledger                                                |
| [July 2026 BVK additions](https://kemenimipas.go.id/berita-utama/kemenimipas-menambah-enam-negara-penerima-bebas-visa-kunjungan-ke-indonesia)                                                             | Ministry release                  | Turkey, Brazil, Peru, Kazakhstan, Macao and Belarus additions                                                                                | Already represented in the current pack; retain source evidence                     |

The complete hashes, source conflicts, unresolved instruments, and the exact
owner decisions needed to close this gate are recorded in the
[G1 source decision packet](2026-08-06-visa-oracle-g1-source-decision-packet.md).

The forward-only candidate `rulepack-prod-002` records the national canonical
overlay (`AF IL KP LR NG SO`), excludes `GN`, `CM` and `NE`, and carries
source-specific freshness policies for all 28 source records. It compiles
cleanly and was signed offline on M5 with the authorized production key
`prod-2026-07-1`; signature, payload hash and the sequence-1 anti-rollback
chain verify locally. It is not active and no production database was changed.

All 19 official-portal sources were re-observed successfully before the final
signature. A real supported-persona evaluation at the signed clock remains
`SUPPORTED_CANDIDATES` after decisive and global safety-source holds. The 16
ambiguous extension policies are explicit neutral `UNKNOWN` values; no numeric
extension timeline or positive extension claim is inferred.

### UU PDP boundary

[UU 27/2022](https://www.peraturan.go.id/id/uu-no-27-tahun-2022) is in force.
Its official record classifies nationality and marital status as general
personal data and health, criminal, child and personal-financial data as
specific personal data. The Act requires a lawful processing basis and
purpose-specific transparency, and requires deletion/destruction when the
purpose or approved retention period ends. The browser implementation therefore
keeps an explicitly disclosed resume only in `sessionStorage` for at most two
hours, clears it after a non-retryable terminal result, and sends no interview
answers or semantic facts to telemetry or WhatsApp. The backend decision row
stores a keyed, non-reversible request fingerprint and the public decision
projection, not `ApplicantFacts`.

This technical minimisation does not choose Bali Zero's legal basis. Before
activation, Zero must approve the controller/privacy notice, lawful basis for
the evaluation and local resume, decision-audit retention schedule, data-subject
request/deletion process, and whether any child/specific-data flow requires
additional controls. WhatsApp consent is purpose-bound to that handoff and must
not be treated as blanket consent for the evaluation.

## G2 — deterministic engine checkpoint

Integrated engine checkpoint: `b24c2901a` (source-line checkpoint
`714aeac833b2b510dd161270bddf2dd9050dd40c`).

- The public request and response are closed Pydantic/OpenAPI contracts. The
  operation exports typed 200, 400, 409, 413, 415 and 422 responses and the
  exact five-state decision enum.
- Strict ingress rejects unsupported MIME types, duplicate JSON properties,
  non-finite numbers, oversized streams and repeated identity headers without
  echoing applicant values.
- ENFORCE can return an authoritative `mode=ENGINE` result only after the
  immutable decision row is persisted. A write or public-projection failure
  returns `TEMPORARILY_UNAVAILABLE`; SHADOW remains `mode=CURATED`.
- The final decision has an RFC 8785 canonical trace plus a domain-separated
  HMAC integrity seal. Production/staging have no unsigned or placeholder-key
  fallback.
- Durable idempotency binds an opaque key hash to a request HMAC, a DB-frozen
  clock and the first canonical response for its Zero-approved policy-bound
  lifetime. Decision and idempotency intervals are separate policy fields and
  neither has an application default. Stored JSONB is re-hashed on read;
  concurrent completion, replay, body tamper and bounded exact-key reclamation
  are covered by DB tests.
- Pricing uses an exact PricingTool key/category lookup. Because the current
  catalogue has no approved validity/max-age policy, the adapter emits no
  amount and returns `PRICING_FRESHNESS_UNKNOWN` rather than guessing.
- Legal eligibility, operational availability and Bali Zero service
  availability are separate response fields. The latter two remain explicit
  `UNKNOWN` until supported evidence exists; documentation and processing
  timeline are likewise explicit `UNKNOWN`, never verified-empty placeholders.

Historical pre-freshness checkpoint contract hashes:

| Artifact          | SHA-256                                                            |
| ----------------- | ------------------------------------------------------------------ |
| Engine contract   | `c33969b7437614c0d6e0d13e13228f7475baacef6fdd2457ac50c90fe60e1996` |
| Evaluate request  | `3866db7b48a7d577b55fe1bd34a63a4aea3a74d11838931e9888affd2c40d934` |
| Evaluate response | `d513f941517e89e3d64702f564255276ac703c9de13f4b0cf24ac11b77f6b9aa` |
| Runtime OpenAPI   | `3ff36fc7840999d1e01afab0cee86a33fd62b33d82043dcf99ab8a9ad51802a9` |

Independent integration run: 1,503 passed, 1 skipped. The sole skip is the
still-unprovisioned `visa_activation_executor` operator role; it is an
operational activation gate, not a hidden test failure.

The later retention/integration freeze supersedes the runtime OpenAPI hash and
test count shown in this historical checkpoint. The subsequent signed
`SourceFreshnessPolicy` export intentionally changes the aggregate Engine
contract only. The completion pass reverified the current exported artifacts:

| Current artifact  | SHA-256                                                            |
| ----------------- | ------------------------------------------------------------------ |
| Engine contract   | `9e325710e8e021f47e1c00a51d75f9dbcbdb825aa449874c2a85a1fd02bd2e6d` |
| Evaluate request  | `3866db7b48a7d577b55fe1bd34a63a4aea3a74d11838931e9888affd2c40d934` |
| Evaluate response | `d513f941517e89e3d64702f564255276ac703c9de13f4b0cf24ac11b77f6b9aa` |

## Resulting architecture

```text
language-independent interview facts
  -> finite branch tree + stale-descendant pruning
  -> grouped confirmation / editable assumptions
  -> OpenAPI-derived request adapter
  -> bounded fetch (AbortController, exact-body retry, dedupe, idempotency)
  -> POST /api/visa-oracle/evaluate
       -> strict byte/JSON/header ingress
       -> policy-bound idempotency reservation
       -> signed active RulePack + source-authority/freshness gates
       -> compiler -> tri-state evaluator -> deterministic precedence
       -> PricingTool adapter (price axis only; fail-closed UNKNOWN)
       -> immutable decision persistence -> trace/HMAC seal
       -> authenticated replay envelope
  -> strict response parser
  -> render candidates only when mode=ENGINE and state=SUPPORTED_CANDIDATES
```

`SHADOW` and `OFF` never expose a fallback candidate. `PREVIEW` is isolated,
visibly labelled and test-only. The retained `mock-engine.ts` module supplies
fixtures/preview data only; it no longer selects or ranks a public result.
Qdrant and LLM explanation paths remain downstream of the deterministic
decision and cannot mutate the candidate set or ordering.

The three product axes remain independent in the response and UI:

1. legal eligibility from signed deterministic rules;
2. operational availability from dated operational evidence;
3. Bali Zero service availability from an approved service catalogue.

An `UNKNOWN` in either latter axis is shown as unknown and does not erase or
improve legal eligibility. Pricing failures likewise degrade only the price
projection; they cannot remove, add or reorder a legally supported path.

## Final gap matrix

| Capability                                       | Initial | Final implementation                                                                              | Activation status                                                                       |
| ------------------------------------------------ | ------- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Signed RulePack / compiler / tri-state evaluator | DONE    | DONE, with signed sequence 2, sealed trace and persisted public projection                        | Inactive; production activation remains an operator gate                                |
| State precedence and monotone `UNKNOWN`          | DONE    | DONE; golden, permutation, monotonicity and adversarial coverage                                  | Code-ready                                                                              |
| Decision trace and integrity                     | MISSING | DONE; RFC 8785 trace plus domain-separated HMAC                                                   | Requires production key custody/rotation runbook                                        |
| Strict public ingress                            | PARTIAL | DONE; byte cap, exact MIME, duplicate-key/header and non-finite rejection                         | Code-ready                                                                              |
| Durable idempotency and replay                   | MISSING | DONE in code; policy-bound expiry, exact response, HMAC and bounded reclaim                       | Requires role grants, policy row, worker and key-retirement procedure                   |
| Decision/payload retention and legal hold        | MISSING | DONE in code; unseeded policy, parent-bound deadline, bounded purge/evidence                      | Requires Zero-approved durations, owner split, grants, backfill/disposition and cadence |
| Pricing                                          | MISSING | PARTIAL; only `PricingTool`, one all-inclusive axis, no hardcoded amount, fail-closed `UNKNOWN`   | BLOCKED on catalogue validity/freshness policy                                          |
| Source freshness / clock                         | MISSING | DONE; signed source-specific max ages, current observations and fail-closed abstention gates      | Recheck scheduler/owner remains an operational gate                                     |
| Legal / operational / service separation         | MISSING | DONE in contract and UI                                                                           | Operational/service evidence may remain `UNKNOWN`                                       |
| OpenAPI-derived TypeScript                       | MISSING | DONE; generated operation and component types, runtime response guards                            | Code-ready                                                                              |
| Public visible authority                         | MOCK    | DONE; only verified `mode=ENGINE` response can expose candidates                                  | Feature flag must remain non-ENFORCE until G1/operations close                          |
| Ten interview categories                         | PARTIAL | DONE; finite paths, no category dead end                                                          | Code-ready                                                                              |
| Back/edit/stale descendant pruning               | PARTIAL | DONE through interview and confirmation                                                           | Code-ready                                                                              |
| EN/ID parity                                     | PARTIAL | DONE; instant switch, facts remain language-independent                                           | Code-ready                                                                              |
| Outcome anatomy                                  | PARTIAL | DONE for all five states; axes, sources/dates, assumptions, next steps, print/share/QR            | Amount/timeline/documents stay visibly unknown without evidence                         |
| Network/timeout/retry/resume                     | MISSING | DONE; retry classification, exact-body automatic retry, explicit attempt rotation, opt-in resume  | Code-ready                                                                              |
| Consent and PII-free telemetry                   | MISSING | DONE technically; expiring scoped handoff receipt, no raw answers/facts in analytics/WhatsApp     | BLOCKED on Zero lawful-basis/privacy-notice decisions                                   |
| Responsive/accessibility                         | PARTIAL | DONE; 320 px bounding-box regression, keyboard, live regions, reduced motion and axe gate         | Code-ready                                                                              |
| Live full-stack browser proof                    | MISSING | DONE; opt-in disposable TEST DB runner, signed TEST pack, real Next/FastAPI/PostgreSQL and replay | Code-ready; current expected state is conservative `HUMAN_REVIEW_REQUIRED` pending G1   |

## Implementation surface

The branch changes the existing v2 rather than replacing it. Principal areas:

- backend router, closed API models, compiler/evaluator safety gates, crypto,
  decision seal, deterministic evaluate path, pricing and idempotency;
- migrations `262` through `265` for replay authentication, policy-bound
  retention and persisted trace/integrity evidence;
- generated engine JSON Schemas, runtime OpenAPI and derived TypeScript types;
- interview tree/flow/fact mapper, bilingual content and confirmation;
- strict frontend client/response adapter, run cache, identity/resume/consent
  stores, telemetry and trusted source links;
- outcome renderer, responsive CSS and Playwright/Vitest/pytest coverage.

The exact name/status list for the review branch is reproducible with:

```bash
git diff --name-status c260dd1b8e31e0970a6f395ca4850160f991deb2..HEAD
```

## Browser evidence

- Initial desktop:
  `docs/audits/assets/visa-oracle-v2/as-is-desktop-light.png`
- Initial 320 px:
  `docs/audits/assets/visa-oracle-v2/as-is-mobile-320-dark.png`
- Final desktop engine state:
  `docs/audits/assets/visa-oracle-v2/final-desktop-engine-supported.png`
- Final 320 px dark/reduced-motion state:
  `docs/audits/assets/visa-oracle-v2/final-mobile-320-engine-reduced-motion.png`

The final mobile screenshot was inspected independently of the overflow metric.
That inspection exposed a grid min-content clipping bug which the old
`document.scrollWidth` assertion missed. The fix uses `minmax(0, 1fr)` and the
browser gate now rejects any visible non-scroll-container descendant whose
bounding box escapes the 320 px viewport.

## Verification evidence

Post-rebase code checkpoint: `07625dfea22f9040cd370f2a448128ac744424e7`.
Line D reproduced the contract, typecheck, Vitest, pytest and Chromium gates
in its own detached worktree, reviewed the source path from the relative
browser client through the Next catch-all and backend route registration, and
found **zero code BLOCKER and zero code MEDIUM findings**. The critical Visa
source content and contract hashes are byte-identical to the pre-rebase frozen
candidate.

| Check                                                 | Result                                                               |
| ----------------------------------------------------- | -------------------------------------------------------------------- |
| OpenAPI generation + typed-contract validation, twice | PASS; identical hashes                                               |
| Runtime OpenAPI SHA-256                               | `2b96b7bcb3fced054fd836b7b5f622196e7fc344c04c512a1e2af4452cac255b`   |
| Formatted derived TypeScript SHA-256                  | `fd511d7f95b5b59658323ba521c48dfee06e0bea291447c1845aeaf4fcbe7761`   |
| Mouth typecheck                                       | PASS                                                                 |
| Visa-focused Vitest                                   | 33 files, 352 tests passed                                           |
| Full Mouth Vitest                                     | 341 files, 3,097 tests passed                                        |
| Backend Visa Oracle scope                             | 1,606 passed, 1 skipped, 0 failed                                    |
| Retention/endpoint DB target                          | 30/30 passed                                                         |
| Chromium Visa Oracle suite                            | 11/11 passed independently in 14.3 s                                 |
| 320 px bounding-box regression                        | 1/1 passed after reproducing the clipping                            |
| Next proxy source path                                | PASS; query, raw body, idempotency key and upstream status preserved |
| Browser smoke / visual inspection                     | PASS; content, no overlay, dark 320 px and no horizontal overflow    |
| Grader worktree integrity                             | PASS; exact SHA, clean status/index and current `git diff --check`   |

The 11 browser tests validate frontend behavior against intercepted, typed HTTP
responses. They are not described as a live full-stack E2E run. A bounded
post-rebase browser smoke rendered meaningful content without an error overlay;
the 320 px dark view had no horizontal overflow. Neither result traverses a
real browser → Next proxy → FastAPI → PostgreSQL evaluation.

### 2026-08-06 completion evidence

The historical limitation in the preceding paragraph is now closed by
`backend.scripts.visa_engine.fullstack_smoke`. The runner refuses remote or
existing database names, creates a unique loopback `visa_oracle_smoke_*`
database, applies forward migrations `250`-`257` and `262`-`265`, activates the
checked-in signed TEST RulePack, runs Chromium against real Next/FastAPI, reads
PII-free persistence evidence, then terminates all child processes and drops
the database in `finally`. Playwright uses a non-interactive bounded reporter;
the cold-start outcome wait has an explicit 30-second budget.

| Current check                                       | Result                                                                 |
| --------------------------------------------------- | ---------------------------------------------------------------------- |
| Backend Visa Engine + router, non-DB                | PASS; one expected missing `visa_activation_executor` role skip        |
| Database evaluate/retention/idempotency/trace scope | PASS                                                                   |
| Middleware privacy success/4xx/5xx/slow/429 sinks   | PASS                                                                   |
| Full Mouth Vitest                                   | PASS; 343 files, 3,163 tests                                           |
| Mouth typecheck                                     | PASS                                                                   |
| Desktop + Mobile Chrome Visa Oracle suite           | PASS; 26/26 with WhatsApp configured                                   |
| Keyboard-only EN/ID desktop/mobile                  | PASS; conservative human-review outcome and focus transitions verified |
| Unmocked full-stack smoke                           | PASS repeatedly and independently; disposable DB removed               |

The full-stack smoke also verifies that response `trace_sha256` equals the
persisted trace digest and that a separate decision HMAC/key ID is present.
The UI renders the first public response; two exact idempotent replays remain
byte-equivalent.

## Residual Zero decisions and operational gates

No production `ENFORCE` activation is authorized by this branch. Zero must
provide or approve all of the following without application defaults:

- a new signed RulePack/source ledger resolving the national/regional Calling
  Visa conflict and partial-revocation locators;
- source-specific freshness/applicability policy and an observation process;
- PricingTool catalogue validity/max-age and Bali Zero service-availability
  evidence;
- decision and idempotency retention intervals, anchor, historical-row
  disposition/backfill, legal-hold operating procedure and DSR/deletion flow;
- database owner/runtime/approver/retention-worker separation, narrow grants,
  scheduler cadence, backlog/max-lag alert and HMAC key-retirement process;
- controller notice, lawful basis, child/specific-data controls and the scope of
  the optional local resume;
- provisioning and validation of the production activation executor role;
- a production-environment smoke after the policy, roles and signed pack are
  approved (the disposable TEST full-stack smoke is now automated and green).

`REVOKE ... FROM PUBLIC` is useful defence-in-depth but is not role separation:
the PostgreSQL object owner retains authority. Migration `264` therefore seeds
no policy, duration, role, grant, scheduler or historical disposition.

## Final gate

| Gate                                  | Result      | Evidence / blocker                                                                                                                                    |
| ------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| G0 inventory and gap matrix           | PASS        | Verified runtime, registered route, imports, signature, migrations, tests and browser behavior                                                        |
| G1 contracts and sources frozen       | BLOCKED     | Calling Visa authority/freshness/sequence 2 are closed; missing official instrument archives, pricing catalogue policy and final source review remain |
| G2 engine gold/adversarial harness    | PASS (code) | Same-pass TRUE/FALSE/UNKNOWN trace, determinism, monotone UNKNOWN, precedence, HMAC/replay, retention, tamper and failure tests green                 |
| G3 UI all states/categories           | PASS        | Five states, ten categories, EN/ID, edit/prune, 320 px, keyboard-only EN/ID, reduced-motion and Axe                                                   |
| G4 mock removed from public authority | PASS        | Only strict verified `mode=ENGINE` responses expose candidates; preview/mock isolated                                                                 |
| G5 requested automated suites         | PASS        | Typecheck, full Vitest, scoped pytest, desktop/mobile Playwright and unmocked disposable-DB smoke green                                               |
| G6 independent review                 | BLOCKED     | Regrade pending on the refreshed/re-signed sequence 2; no activation is authorized until it closes                                                    |

This branch is not a production activation approval. The product remains
`NO-GO` while G1 and the operational retention/privacy/role gates are open.
The independent grader has closed the implementation and TEST full-stack
findings, but cannot close G6 while those product blockers remain. Nothing in
this dossier authorizes production `ENFORCE`, merge or deployment.
