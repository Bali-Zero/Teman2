---
date: 2026-07-17
subject: modular-worker-plane-implementation-plan
review_mode: asymmetric-independent-panel
design_spec: docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md
master_plan: docs/superpowers/plans/2026-07-17-modular-kernel-worker-plane-implementation.md
client_data: none
---

# Independent implementation-plan review brief

Review the design specification and all eight implementation documents from the
single immutable content-addressed packet supplied over stdin by the launcher.
The packet contains one canonical non-circular input manifest, this brief as its
only `role=instructions` entry, and the nine documents below as `role=covered`
entries. Start the verdict by repeating the SHA-256 of the canonical manifest
bytes as `input_manifest_sha256`. Do **not** repeat or guess `packet_sha256`:
that transport hash exists only in the launcher's external receipt. If any
embedded length, role, path, Git blob OID, size, or content hash is missing or
inconsistent, return `NO-GO` without substituting other bytes.

You have no filesystem, shell, MCP, Read, Glob, or Grep tools and no checkout
access. Treat only the supplied packet bytes as evidence. Optional repository
corroboration is admissible only when the launcher has added the exact selected
bytes from a read-only archive of the recorded source commit to a newly hashed
covered projection; never request or infer mutable worktree content. This is a
read-only review: do not edit files, contact external services, inspect client
records, or expose secrets. Do not infer the other reviewers' opinions and do
not optimize for consensus.

Raw responses, normalized reviews, invocation receipts, dispositions, packet
objects, and attestation manifests are excluded outputs. Adding or correcting
only those outputs does not invalidate a review when a post-commit check proves
the canonical covered projection is unchanged. Any change to a covered or
instructions role/path/byte requires one new manifest and packet plus all three
new reviews.

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
  observation? After merge, does one explicit rollout task perform every live
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
- Does effect execution separate stable effect identity from append-only
  attempts, atomically lock and validate grant/domain claim/effect state at
  attempt start, and block cutover on every live lease, pending run, prepared,
  retryable, attempting, or unresolved blocking effect?
- Are forward and reverse transitions strictly drain -> lease/effect barrier ->
  atomic generation advance/activation, with no interval containing two active
  owners or late effects from two generations?
- Is heavy execution correctly routed to CI or Pro from Air-M5?
- Does G8 execute real breaking-contract tests against generated backend
  OpenAPI plus Mouth types/routes and MCP consumers, rather than only naming
  those adapters? Does G9 compare all four API/RAG metrics against the Phase 0
  baseline after the complete authoritative 246–250 migration chain and after
  every workload forward, reverse, and final re-cutover, while keeping worker
  absolute budgets separate? Does G10 reject prohibited raw PII before both job and
  event publication and prove logs, receipts, quarantine, and DLQ captures are
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

Return Markdown with exactly these top-level sections:

1. `# Verdict`
2. `# Blocking findings`
3. `# Important findings`
4. `# What survives review`
5. `# Required amendments`
6. `# Falsification test`

The verdict must be one of `GO`, `GO-WITH-CHANGES`, or `NO-GO`, followed by a
confidence from 0 to 100 and the reviewed `input_manifest_sha256`. Every finding
must cite a packet document section/path and, when
based on repository state, the repository path. Separate verified facts from
inference. A blocking finding must identify a concrete failure mode and a
falsifiable correction. Prefix every non-`None` Blocking or Important finding
with a stable reviewer-specific ID such as `[FABLE-PLAN-001]`. If there are no
findings at a severity, write `None` under that heading. Keep the response below
1,800 words.

## Seat A — Fable 5: execution architecture judge

Judge whether the amended design and plan form a coherent architecture with the
smallest reversible sequence. Attack hidden irreversibility, dual ownership,
false-green gates, oversized tasks, inconsistent contracts, and deletion
before rollback evidence. Prefer a smaller executable plan when it proves the
same invariants.

## Seat B — Gemini 3.1 Pro High: constructive delivery reviewer

Assume the direction should ship. Make the plan operationally complete. Focus
on exact repository integration points, TDD order, migration and compatibility
release sequencing, Fly/GitHub Actions coordination, private health, resource
budgets, observability, production evidence, and commands a fresh agent can
actually run.

## Seat C — GLM 5.2: adversarial refuter

Assume the plan will produce a green but unsafe release. Find the strongest
specific path to lost work, duplicate irreversible effects, stale-owner
execution, incorrect rollback, subscriber acknowledgment loss, sovereignty
failure, migration collision, public worker exposure, or unbounded production
blast radius. State the minimum amendment and test that defeats each attack.
