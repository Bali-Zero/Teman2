# Verification

- 178 backend tests passed: real PostgreSQL member-obligation fixtures, existing
  practice routers and CRM role boundaries. The fixture schema is isolated in
  `nuzantara_test`; no production client rows were written.
- 58 frontend tests passed across the new personal page, preserved compliance
  register, navigation and the desk color guard.
- On an identical source copy on Pro, 1,810 backend contract/RAG checks passed;
  12 integration-dependent tests were skipped. This includes the generated
  OpenAPI schema pin and deployed application contract parity checks.
- TypeScript completed with exit code 0 on Pro after correcting the new badge
  to the existing `wait` tone. Ruff checks and formatting checks passed.
- The initial staged token-lint pass depended on copy detection. The final gate
  reproduced a false positive on an existing obligation ID in the relocated
  register test under default git settings; an explicit ID annotation fixes it.
  The full base-relative diff and register tests were rechecked after the fix.
  The dependency import smoke check passed.
- Real Chromium, using synthetic intercepted API responses, passed at desktop
  and 390px mobile sizes: personal source links, supervisor scope, owner filter,
  server-controlled process links, refresh after source resolution, and the
  preserved register route. No mobile overflow remains after responsive layout
  settles. Screenshots were visually inspected; no real client data was used.
- Independent Opus 5.5 xhigh static review returned PASS in session
  `064f9749-8ce4-4304-8d5c-f8bc0a4337c0`. It checked the source permission
  predicates, fixed response fields, source-derived rules, register relocation
  and request races. It did not run tests. The fresh final gate is separate.

The process page's required-document read was also inspected after review:
it has no narrower owner predicate that would reject the newly permitted
practice assignee. Its existing authorization is unchanged.

## Accepted limits

Counts, rows and owner groups are separate read statements, so concurrent edits
can cause a transient mismatch until refresh. The view uses the current active
status aliases and existing ownership strings. No new `failed` state or automatic
age-based transition is introduced; source closure uses completed/cancelled.

The additional supervisor setting is absent in the current Fly secret inventory.
A read-only preflight found exactly one active intended supervisor account. The
release owner must stage the narrow setting before deployment; its value is never
included in evidence. `flyctl secrets import --stage` explicitly skips deployment.

The M5 became heavily overloaded by unrelated simulator processes during final
checks. They were left untouched. The remaining checks ran in an isolated Pro
worktree based on the same commit and candidate files.
