# Monorepo test coverage audit — 2026-07-18

## Scope and method

This audit combines:

- a static inventory of Python and JavaScript/TypeScript source and test files;
- the coverage gates actually enforced by `.github/workflows/tests.yml`;
- fresh local coverage runs for the backend, Mouth, Nuzantara MCP, the
  evaluator's critical circuit-breaker/CEP slice, WA Dashboard, and
  `packages/core`;
- collection and runner checks for suites that are not wired to the main CI
  workflow.

Generated assets, virtual environments, dependency directories, migrations,
and conventionally named test files are excluded from the source count. File
counts are an inventory signal, not a substitute for executable line and branch
coverage.

The starting inventory found 3,627 source files and at least 1,167 outside the
four pre-existing gated surfaces. This change adds gates for WA Dashboard and
`packages/core`, moving about 68 source files under an explicit policy. At least
1,100 source files still sit outside the six coverage gates, so a single
repository-wide coverage percentage would be misleading.

## Executive snapshot

| Surface                |             Source / test files | Fresh local result                                                                                                          | Enforced gate                                                |
| ---------------------- | ------------------------------: | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `apps/backend-rag`     |                   1,572 / 1,474 | 17,759 collected: 17,639 passed, 114 skipped, 6 failed; 74.01% statements, 63.68% branches, 71.94% combined                 | 55% combined statement/branch                                |
| `apps/nuzantara-mcp`   |                         44 / 35 | 341 passed; 78.04% statements, 55.69% branches, 73.61% combined                                                             | 70% combined statement/branch                                |
| `apps/evaluator`       |                         99 / 43 | Critical gate: 61 passed; 90.35% statements, 82.69% branches, 88.68% combined                                               | 85% on two critical modules only                             |
| `apps/mouth`           | 1,057 / 230 unit + 47 E2E specs | 2,074 unit tests passed; 26.84% statements, 22.32% branches, 21.92% functions, 27.35% lines; 2 offline browser tests passed | 20% statements                                               |
| `apps/wa-dashboard`    |                          20 / 2 | 18 passed; target slice 100% statements/branches/functions/lines                                                            | target modules: 90% statements/functions/lines, 85% branches |
| `packages/core`        |                         48 / 34 | 127 passed; 83.01% statements, 73.45% branches, 81.61% functions, 85.62% lines                                              | 80% statements/functions/lines, 70% branches                 |
| `apps/admin-dashboard` |                          59 / 3 | Tests run in CI without coverage                                                                                            | None                                                         |

The backend result needs one qualification. The six failures all came from
`test_intake_writer.py` and exposed legacy columns missing from the existing
local database (`documents.document_category` and `clients.passport_expiry`),
not assertion regressions. The CI schema bootstrap was extended with the full
writer/router contract. On a new disposable PostgreSQL database, bootstrap plus
all 129 v2 migrations completed and the affected file passed 35/35 tests. That
database was removed afterwards. The entire 20-minute backend suite was not
rerun after this targeted clean-database proof, so the table preserves the
actual full-run result rather than retroactively reporting it green.

The backend startup directory separately has 131 passing tests and measures
64.16% combined coverage across `app_factory.py` and
`service_initializer.py` (64.98% statements, 57.64% branches).

## What the aggregate does and does not prove

- The six gated surfaces have reproducible component-level policies and retained
  coverage artifacts.
- The WA Dashboard number deliberately covers `store.ts` and
  `wa-actions-api.ts`; it is not whole-application coverage.
- The evaluator gate deliberately covers the CEP runner and circuit breaker. Its
  wider suite is not yet healthy enough to gate as one unit.
- Mouth's percentage is whole-unit-suite coverage, while its browser job is a
  deterministic subset of the E2E inventory.
- Python's `coverage report --fail-under` uses the combined statement/branch
  total when branch mode is enabled. It does not enforce an independent branch
  floor.

These different denominators, plus unexecuted islands, are why the component
figures must not be averaged into a monorepo headline.

## Backend suites outside the active runner

The main backend job selects `backend/tests/` plus three verified legacy files.
The separate `apps/backend-rag/tests/` tree contains 276 modules and exposes
3,187 test items, with 11 collection-error modules. Across all explicit test
paths outside the main runner, 3,212 items are discoverable and 14 modules fail
collection.

The largest subtrees have different blockers and should not be added blindly:

- `tests/unit/`: 95 files and 1,653 collected items; collection succeeds, but a
  runtime sample reaches 202 passes before stale Qdrant mock contracts trigger
  DNS/shape failures.
- `tests/integration/`: 134 files and 1,071 items; requires explicit PostgreSQL,
  Qdrant, Redis, and container fixture policy.
- `tests/api/`: 17 files and 217 items; currently a quarantined API suite.
- `tests/services/`: 20 files and 97 discoverable items, with 11 collection
  errors from stale Olympus and sibling LLM imports.

Three low-risk legacy paths now run in the backend job and pass 56 tests:
Sentry lazy import, Sentry PII redaction, and hierarchical politics KB tests.

## Other ungated test islands

The following components contain tests but do not run in the main test
workflow:

- Python: Mata Garuda (174/108), Cell (68/40), Graph Engine (60/35), Bali
  Intel Scraper (80/12), Organism (43/50), Cell Observatory Collector (10/9),
  Zantara Media (22/7), Cell Core (38/32), Shared Schemas (12/4), MCP Advanced,
  MCP Browser, and Browser Core.
- TypeScript: Admin Dashboard Local (46/5), Web (24/3), WA Mirror (13/6), Team
  Agent/Bridge (9/5), and Autonomous Lab (7/1).

Known zero-test source surfaces still include OSINT Nexus UI (42 files), WA
Meta Inbox (1), and TS Schemas (1). WA Dashboard is no longer in this list.

## Structural findings

1. The full evaluator snapshot remains approximately 31.16% statements and
   25.54% branches. It reports 559 passes, five environment-dependent
   integration failures, and 21 collection errors. One suite imports the
   removed `seo_guardian_agent` module and is orphaned. The NLM subtree itself
   now passes 309 tests, but that does not repair the unrelated evaluator
   islands.
2. Only a deterministic subset of Mouth's 47 E2E spec files runs in CI. The new
   `@offline` authentication journey adds two browser tests without requiring a
   live LLM, Qdrant, or production credentials.
3. Root coverage/test-automation package scripts reference missing files under
   `scripts/coverage` and `scripts/test_automation`; there is no functioning
   monorepo coverage command.
4. There is no repository `codecov.yml`. Uploads are optional and do not impose
   repository-wide component or patch policy. SonarQube is advisory.
5. Existing Python combined gates can pass with substantially lower branch
   coverage. For example, MCP clears 70% combined while branch coverage is
   55.69%.

## Remediation order

### P0 — make the signal complete and trustworthy

- classify the 3,212 discoverable backend items outside the active runner,
  repair the 14 collection-error modules, and migrate them in bounded shards;
- restore one real monorepo coverage command that fans out to component runners
  and publishes a manifest of incomparable component totals rather than a fake
  merged percentage;
- remove or repair orphan evaluator suites, then expand the gate beyond the two
  critical modules;
- keep required-job summaries derived from actual job results and fail the
  summary when a dependency fails, cancels, or skips.

### P1 — connect the largest existing suites

- shard Mata Garuda, Cell, Graph Engine, and Organism into CI;
- expand deterministic offline E2E journeys beyond page-load and authentication
  smoke tests;
- add the first behavioral tests for OSINT Nexus UI, WA Meta Inbox, and TS
  Schemas;
- establish a baseline and coverage gate for Admin Dashboard.

### P2 — raise quality thresholds gradually

- add explicit Python branch floors after current baselines are stabilised;
- expand WA Dashboard coverage beyond its two state/API boundary modules;
- cover the remaining zero-hit `packages/core` components and session-bridge
  paths;
- define Codecov component and patch policies without exposing its token to test
  or install steps.

## Changes delivered with this audit

- branch-aware backend coverage, a real Intake integration DSN, three safe
  legacy test paths, and a fresh-database schema bootstrap contract;
- lifecycle contracts for critical startup versus best-effort plugin failures;
- Intake review RBAC identity validation, blob-root/symlink containment, and
  delivery-boundary coverage;
- MCP workflow-chain and FlowKit boundary tests plus a 70% coverage runner;
- atomic evaluator HALF_OPEN probes wired into all eight NLM pipelines, with
  exception-path recovery and an 85% critical gate;
- Mouth chat-hook and process-detail unit tests, a 20% statement floor, and two
  deterministic offline authentication E2E tests;
- the first WA Dashboard test harness and an explicitly scoped high-coverage
  state/API gate;
- 27 additional `packages/core` tests, a clean-installable workspace harness,
  and its first standalone CI gate;
- coverage artifacts for every gated component, JUnit reports for Python jobs,
  truthful job summaries, and Codecov secrets scoped to upload steps only.
