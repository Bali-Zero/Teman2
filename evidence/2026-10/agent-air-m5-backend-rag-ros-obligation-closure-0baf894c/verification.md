# Obligation completion verification

## Executed checks

- Focused backend contracts, query compatibility and Sentry redaction: 117 passed.
- Repeated after review with `-n auto --dist loadfile`, two workers and real PostgreSQL: 117 passed in 66.73s. Isolated schemas in `nuzantara_test` worker databases; synthetic records only.
- Obligations UI and desk colour guard: 43 passed after review fixes.
- Mouth TypeScript: `tsc --noEmit` passed.
- Dependency import smoke passed; mandatory LangGraph, subgraphs and confidence tests: 91 passed.
- Ruff on the six changed Python files and `git diff --check`: passed.

## Independent design and code review

BLUE Dux: Claude Opus 5.5, xhigh, OAuth session
`c7c02d41-2f72-4f4e-95a6-4dcd3670ab88`.
The initial design review approved this bounded scope. The code review blocked
the candidate because its test-database suffix guard rejected xdist workers.
That guard now accepts test databases and their numbered workers, and the
parallel test run above passed. Required completion audit logging (IDs and
staff actor only) and section headers were added. Evidence references remain
excluded from application logs and are scrubbed from Sentry.

Additional dispositions: completion checkbox/help identify the row; a 409
notice survives row refresh (tested); the five counters have mobile borders;
the unrelated Sentry formatting change was removed; the subtitle retains
Generate; obligation status and outcome constraints are present in the test
schema. Alert-schema coverage remains intentionally minimal for this slice.

The final gate must be a fresh Opus 5.5 xhigh session on the committed candidate.
This document is test evidence, not a final gate or deployment claim.

## Production acceptance

Verify both deployed revisions, endpoint schema/authentication, a synthetic
nonexistent obligation request and the existing register UI. Do not complete
a real client obligation for release testing. Capture only identifiers and
aggregate results; no client rows or evidence references in release artifacts.
