# Verification

PR 8656 was stopped before merge after its production-build security guard
rejected the new static register route. This successor adds an explicit dynamic
server layout. The existing proxy, prerender baseline and all CRM source logic
are unchanged. The full production build passed, including both public-bundle
security assertions. Its output marks the register dynamic and the route is
absent from the prerender manifest. Both independent delta reviews returned PASS.
The earlier targeted checks below retain their original scope.

Chromium also passed against the actual production build with synthetic API
responses: personal source links, team scope, owner filtering, server-controlled
process links, mobile layout, resolution refresh and navigation into the dynamic
register. No real client records were read or changed for that browser check.

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

The release owner staged the additional supervisor setting before PR 8656.
A read-only preflight found exactly one active intended supervisor account with
the verified role and department. The successor retains that staged setting and
must not overwrite or stage it again. Its value is never included in evidence.
`flyctl secrets import --stage` explicitly skips deployment.

After rebasing onto `1b743cb60a`, the generated API types preserve the intervening
main change. The new PostgreSQL fixtures and OpenAPI parity checks passed again
(71 tests); all 58 frontend checks passed again. Default committed-diff token
lint is clean. The enforced Gear-3 evidence floor adds the independent Codex and
Kimi review receipts in `journal.jsonl`; both reviews passed. Their bounded
findings and dispositions are recorded in `review.md` and `pack.yml`.

The M5 became heavily overloaded by unrelated simulator processes during final
checks. They were left untouched. The remaining checks ran in an isolated Pro
worktree based on the same commit and candidate files.
