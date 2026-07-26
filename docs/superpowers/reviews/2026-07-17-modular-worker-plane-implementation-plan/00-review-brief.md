---
date: 2026-07-17
subject: modular-worker-plane-implementation-plan
review_mode: asymmetric-independent-panel
design_spec: docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md
master_plan: docs/superpowers/plans/2026-07-17-modular-kernel-worker-plane-implementation.md
client_data: none
---

# Independent implementation-plan review brief

Review the design specification, all eight implementation documents, and the
current-system refresh memo from one immutable content-addressed packet supplied
through each reviewer's attested read-only input route. Phase 1 sends the
byte-exact packet independently to Gemini, Codex, and Kimi. Only after those
three findings-only reviews exist and the orchestrator has dispositioned every
finding does Phase 2 send Fable the same packet plus all three reviews and the
disposition for the sequential final on-disk gate.

Each Phase-1 review input begins with the deterministic
`NUZANTARA-REVIEW-INPUT-V1` attestation header: schema
`nuzantara.worker-plane-review-input/v1`, the freezer-attested
`input_manifest_sha256`, and the exact decimal `packet_bytes`, followed by one
blank line and then the byte-exact packet. The packet contains one canonical
non-circular input manifest, this brief as its only `role=instructions` entry,
and the ten documents below as `role=covered` entries. Verify the declared
packet length against the supplied content, then start the verdict by repeating
the header's `input_manifest_sha256`; you are not expected to calculate
SHA-256. Do **not** repeat or guess `packet_sha256`: that transport hash exists
only in the launcher's external receipt. If the header, embedded length, role,
path, Git blob OID, size, or content hash is missing or inconsistent, return
`NO-GO` without substituting other bytes.

Phase-1 seats must use only the supplied packet bytes as evidence. The launcher
does not provide a checkout path, starts each client from an isolated temporary
working directory, and records the exact client and sandbox controls; those
controls must not be described as universal tool denial. Optional repository
corroboration is admissible only when the launcher has added the exact selected
bytes from a read-only archive of the recorded source commit to a newly hashed
covered projection; never request or infer mutable worktree content. Fable is
the only on-disk gate: in Phase 2 it receives read-only access to the immutable
packet, all three bound review artifacts, and the orchestrator disposition,
never to mutable candidate bytes. Every phase is non-mutating: do not edit
files, invoke any additional external service, inspect client records, or
expose secrets. Do not infer another reviewer's opinion and do not optimize for
consensus.

Raw responses, normalized reviews, invocation receipts, dispositions, packet
objects, and attestation manifests are excluded outputs. Adding or correcting
only those outputs does not invalidate a review when a post-commit check proves
the canonical covered projection is unchanged. Any change to a covered or
instructions role/path/byte requires one new manifest and packet, all three new
independent external reviews, a new disposition, and a new sequential Fable
final gate. The historical packet and panel predating the 2026-07-23 refresh are
non-authoritative for the current candidate bytes.

Documents under review:

1. `docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md`
2. `docs/superpowers/plans/2026-07-17-modular-kernel-worker-plane-implementation.md`
3. `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-0.md`
4. `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-1.md`
5. `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-2.md`
6. `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-3.md`
7. `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-4.md`
8. `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-5.md`
9. `docs/superpowers/plans/2026-07-17-modular-worker-plane-production-rollout.md`
10. `docs/superpowers/reviews/2026-07-17-modular-worker-plane-implementation-plan/2026-07-23-current-system-refresh.md`

## 2026-07-23 live-refresh questions

Treat the covered refresh memo as current evidence to reconcile against the
older design and plans, not as permission to implement, merge, migrate, deploy,
or mutate any environment.

- Since `origin/main@8e826f0940c483f1050b81e74502fbe57aef2479` now reaches
  migration 255, does the plan reject its colliding `247`–`251` allocation and
  fail closed until a formally leased collision-free block is recorded?
- Is candidate range `256`–`260` treated only as an unleased proposal, with
  every covered migration reference, test, receipt, and rollback statement
  amended together before implementation?
- Does the 67-router direct-`asyncpg` inventory remain an explicit bounded
  migration input, with its supplied count/hash revalidated rather than assumed?
- Does Phase 0 close the `main_api.py` background-init shutdown race by
  cancelling and joining `_init_task` before stopping schedulers or closing the
  pool?
- Does the legal RED/GREEN contract recognize that `document_id` already
  exists and isolate the actually missing `persist_source_to_drive` behavior?
- Does the notification ownership/effect inventory include
  `backend/app/modules/notifications/test_endpoint.py` and its `force_send`
  path?
- Does the single-mutation-route claim cover every current Fly mutator,
  including recovery, organism, cell, remediator, preflight, MCP, CLI, and
  legacy script paths, while preserving only a narrowly constrained,
  non-deploying auto-heal lane?
- Do workflow artifact contracts use the major versions actually pinned in
  the target current workflows rather than carrying forward the plan's stale
  generic v4 assumption?
- Does the panel explicitly refuse to inherit authority from the latest
  complete historical panel, whose source and packet predate this refresh?

## Shared review questions

- Can a fresh implementation agent execute every task without inventing a
  filename, symbol, schema, command, expected failure, or expected result?
- Does each production change begin with a named RED test and end with focused
  GREEN plus a proportionate regression command?
- Are task boundaries small enough for atomic commits and fresh two-part
  spec-compliance/code-quality reviews?
- Are cross-phase dependencies consistent, especially migration numbers,
  catalog symbols, SQL function signatures, ownership table names, claim
  columns, build-floor arming, effect contracts, and reverse cutover?
- Does the plan fail closed because the authoritative migration namespace on
  refreshed `origin/main` already occupies its planned `247`–`251` range, then
  require a collision-free formal lease, covered-byte amendment, and complete
  new four-seat, two-phase panel before any migration implementation?
- Is business/data ownership represented consistently by
  `BusinessContext`/`business_context`, and runtime execution by
  `RuntimeOwner`/`runtime_owner`, without an ambiguous `OwnerContext` crossing
  catalogs, migrations, claims, heartbeats, or CAS APIs?
- Does Phase 0 explicitly eliminate the current duplicate notification
  scheduler startup in API and shared API/RAG lifespan, rather than merely
  documenting the intended single owner or relying on a process-local lock?
- Is the delivery sequence coherent with the existing workflow: all six
  implementation phases and their panels on one feature branch; one protected
  compatibility merge/deploy of API/RAG plus additive schema with legacy owners
  retained and no fabricated production-companion state; exact merged-digest
  staging proof; independent release gate; environment-protected deployment of
  that same digest to the private production companion with all workloads off
  and base-only capability; then production cutovers in the fixed order
  workflow, legal, notification, WhatsApp; and only a later deletion PR after
  every rollback window closes?
- Before that protected merge, are all gates limited to source review, CI,
  deterministic simulation, and disposable PostgreSQL, with no live staging
  deploy, migration, secret, grant, guard arm/disarm, ownership transition, or
  behavioral observation, except one fixed `nuzantara_readonly` aggregate
  relation-statistics capture that selects no application rows and expires
  within seven days? After merge, does one explicit rollout task perform every live
  staging mutation against the exact merged digest and stop at an independent
  post-staging release gate before production?
- Does every design gate G1-G17 have a concrete test and evidence path before
  its dependent cutover?
- Can old and new binaries coexist safely for the entire compatibility window,
  including a stale legacy process that keeps running?
- Does the build floor compare fresh heartbeats with an authoritative expected
  instance/deployment census, including audited retirement, so a vanished
  pre-compatible replica cannot disappear from the proof?
- Does `off`/`shadow` remain incapable of claim, mutation, notification, or
  external side effects, and is that proved rather than inferred?
- Do rollout steps enforce primary-schema compatibility before companion
  promotion, one immutable digest, private `:9091/ready`, scoped grants,
  absolute resource budgets, full-cycle observation, and verified rollback?
- Is the protected primary chain exact and fail-closed across pre-deploy,
  old-image migrations, fresh-image release migration/audit, post-deploy SQL,
  Python migrations, explicit schema audit, health, centralized rollback, and
  digest export only on complete success? Are both private staging targets
  (`nuzantara-rag-staging`, `nuzantara-worker-staging`) coordinated from that
  exported digest with the primary as sole migration runner?
- Is `.github/workflows/fly-deploy.yml` the sole protected primary
  build/migrate/promote/rollback/digest-export route; is
  `.github/workflows/worker-plane-production.yml` the sole worker-plane
  topology/image/capability/fault route; and is
  `.github/workflows/worker-plane-live-control.yml` the sole guard/ownership
  route, with direct staging/Fly/SQL paths retired? Does every arm/drain/
  activate/reverse CAS consume and immediately re-audit an immutable effective
  grant plus allowed-secret-symbol state hash so capability cannot change
  between admission and activation?
- Does effect execution separate stable effect identity from an
  append-only-at-runtime attempt ledger with protected bounded retention,
  atomically lock and validate grant/domain claim/effect state at attempt
  start, and block cutover on every live lease, pending run, prepared,
  retryable, attempting, or unresolved blocking effect?
- Does every historical G16 migration block express policy as of that migration,
  while the latest touching block equals the current catalog; and do guilt tests
  reject retroactive annotation rewrites and a stale latest block?
- When API/RAG is intentionally configured with a workload now owned by the
  companion, does startup skip it as `not_current_owner` and stay ready with
  zero pilot tasks rather than failing the whole process?
- Are pre-quarantined Release-A rows terminal `quarantined`, excluded from
  activation outstanding counts, and never replayed; and do compatibility
  integer wrappers still surface quarantine/failure counts through structured
  observation?
- For non-reconcilable provider effects, are
  `unknown_blocks_cutover=true`, `unknown_page_seconds=900`, and
  `unknown_resolution_seconds=14400` explicit and enforced through retention,
  alert, cutover, and manual-decision tests?
- Do automatic and manual WhatsApp paths share the exact total lock order
  grant -> advisory -> source -> projection -> begun attempt -> next boundary,
  with manual resolution available while off/drained, a concurrency proof
  against automatic finish/reconcile, and same-held-row/effect resend denied?
- Does the protected digest artifact use explicitly pinned, repository-current
  action majors for each target workflow (the current protected
  `.github/workflows/fly-deploy.yml` uses `actions/setup-python@v7` and
  `actions/upload-artifact@v7`, while `.github/workflows/tests.yml` also uses
  `actions/download-artifact@v8`), bind one `shared`/1-CPU/1-GB VM tuple and an
  in-image-generated route catalog hash to the immutable digest, and reject
  every caller/checkout/provenance or resource mismatch before mutation?
- Are forward and reverse transitions strictly drain -> lease/effect barrier ->
  atomic generation advance/activation, with no interval containing two active
  owners or late effects from two generations?
- Is all execution bound to Pro/CI with no remaining Air-M5 worktree, artifact, provider, or service dependency?
- Does G8 execute real breaking-contract tests against generated backend
  OpenAPI plus Mouth types/routes and MCP consumers, rather than only naming
  those adapters? Does G9 retain Phase 0 only as a pre-merge code-regression
  gate, capture inert production-local and staging-local baselines after the
  complete newly leased authoritative compatibility migration chain, and
  compare all four API/RAG
  metrics after every workload forward, reverse, and final re-cutover only
  against the matching environment-local baseline captured after the newly
  leased compatibility migration chain, while keeping worker absolute budgets
  separate? Does G10 reject prohibited raw PII before both job and event
  publication and prove logs, receipts, quarantine, and DLQ captures are
  redacted or opaque?
- Does the later deletion release prove the four old/new primary-worker binary
  combinations, deploy primary first, update the existing worker to the exact
  exported deletion digest without changing ownership/capabilities, converge
  both targets, and restore prior worker plus primary on partial failure without
  reversing ownership?
- Are there any TODO, TBD, placeholder, hand-wave, generic exactly-once claim,
  PII leak, hardcoded secret, paid Anthropic API path, frozen embedding change,
  or unbounded destructive production test?

## Shared output contract

Seats A-C run independently in Phase 1 and return findings only; none can
authorize implementation. The orchestrator must bind and disposition every
Blocking and Important finding before Seat D runs. Seat D is the Phase-2 Fable
gate and must invalidate the panel on its own `NO-GO`, any unresolved finding,
any missing/duplicated/identity-ambiguous Phase-1 route, or any mismatch between
the packet, reviews, and disposition. Fable is never counted among or launched
concurrently with the three Phase-1 seats.

Return Markdown with exactly these top-level sections:

1. `# Verdict`
2. `# Blocking findings`
3. `# Important findings`
4. `# What survives review`
5. `# Required amendments`
6. `# Falsification test`

Under `# Verdict`, the first two nonblank lines must be exactly:

```text
GO-WITH-CHANGES — confidence 84
input_manifest_sha256: <the exact 64-hex value from the review-input header>
```

Substitute the actual verdict and an integer confidence from 0 through 100.
Do not use Markdown emphasis, backticks, labels such as `Confidence: High`, or
place the manifest field on the verdict line. The validator accepts only this
machine-readable two-line shape. Every finding
must cite a packet document section/path and, when
based on repository state, the repository path. Separate verified facts from
inference. A blocking finding must identify a concrete failure mode and a
falsifiable correction. Prefix every non-`None` Blocking or Important finding
with a stable reviewer-specific ID such as `[GEMINI-PLAN-001]`,
`[CODEX-PLAN-001]`, `[KIMI-PLAN-001]`, or `[FABLE-PLAN-001]`. If there are no
findings at a severity, write `None` under that heading. Keep the response below
1,800 words.

## Seat A — Gemini 3.1 Pro High: constructive delivery reviewer

Assume the direction should ship, while withholding authorization. Make the
plan operationally complete. Focus on exact repository integration points, TDD
order, migration and compatibility release sequencing, Fly/GitHub Actions
coordination, private health, resource budgets, observability, production
evidence, and commands a fresh agent can actually run.

## Seat B — Codex GPT-5.6: red-team and empirical-contract reviewer

Default to defective. Attack false-green tests, mismatches between the plan and
current repository contracts, unsafe mutation surfaces, migration/reversal
errors, race conditions, and assumptions that only executable evidence can
settle. Identify the smallest falsifiable correction for each finding. Do not
implement changes from the review seat.

## Seat C — Kimi K3: independent adversarial refuter

Assume the plan will produce a green but unsafe release. Find the strongest
specific path to lost work, duplicate irreversible effects, stale-owner
execution, incorrect rollback, subscriber acknowledgment loss, sovereignty
failure, migration collision, public worker exposure, or unbounded production
blast radius. State the minimum amendment and test that defeats each attack.
Kimi is the permanent cross-family refuter; it is not replaced by Codex and is
never the final gate. GLM and DeepSeek are retired and are not admissible
review routes or fallbacks.

## Seat D — Fable 5: sequential Phase-2 final on-disk gate

Run only after Seats A-C have completed and the orchestrator has produced one
hash-bound disposition. Read the immutable packet, all three review artifacts,
and that disposition on disk. Re-verify what the external reviewers attacked
and what they blessed; check that every Blocking and Important finding has a
specific accepted correction or an evidence-backed rejection. Judge whether
the resulting design and plan form a coherent architecture with the smallest
reversible sequence. Attack hidden irreversibility, dual ownership,
false-green gates, oversized tasks, inconsistent contracts, and deletion
before rollback evidence.

Return `NO-GO` if any mandatory review is missing, duplicated through another
model route, identity-ambiguous, bound to different bytes, or incompletely
dispositioned. A Fable `NO-GO` or any new unresolved finding invalidates the
panel; Fable unavailability suspends the gate and must never be substituted.
