# Finite dates in personal obligations

Mission: `kita-duties-finite-1017`. BLUE; Gear 1. The existing Opus Dux reviews and releases; an independent fresh Opus session signs the final gate.

The production personal view returns 200, while team overview returns 500. A read-only console query reproduced `DatetimeFieldOverflowError`, SQLSTATE `22008`. Aggregate inspection found one active client with a negative-infinity passport expiry. No client identity or record content was emitted.

Filter non-finite passport expiry and process creation timestamps before calculating elapsed days. These sentinels are not calendar dates and cannot establish the 90-day or 14-day eligibility windows. Preserve ownership, role checks, response fields, pagination, and source records. No schema, frontend, status, or permission changes.

Reuse PostgreSQL's native [`isfinite` date/time predicate](https://www.postgresql.org/docs/current/functions-datetime.html). An isolated read-only console evaluation of the proposed predicates produced valid DTOs for the first 50 team items and consistent totals and owner counts. This did not change the running application or database.

Acceptance:

- Reproduce HTTP 500 on unmodified code with synthetic negative-infinity dates in an isolated PostgreSQL test schema; retain positive infinity as control cases.
- Pass those regressions and the existing CRM authorization and obligations suites after the query change.
- Release through the normal reviewed PR and canonical mirror workflow, then verify authenticated personal and team HTTP 200, fixed response fields, ownership isolation, and anonymous rejection. Emit only aggregates; make zero client writes.
