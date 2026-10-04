# Marketing fact-gate transport recovery

## 1. Mandate

BLUE, Gear 2, prepare-only external builder on Mini. Worktree
`infra-marketing-gate-async-20261001`, base `9728f6dda28c7307c7183dc3f99187b12d3daee1`.
Return quickly from the MCP fact-check request without losing the eventual verdict.
The observed incident completed a durable BLOCK after a transport timeout; this is
evidence of response-delivery failure, not proof that the provider hung.

## 2. Owned perimeter

Only the marketing tool module, its tests, this specification and the marketing
runbook. No live runtime edits, credentials, articles, placement, GitHub writes,
publication, merge or deployment. Preserve unrelated checkout changes.

## 3. Sibling contract

PR #7070 also touches the marketing tool module. Prepare independently and require
integration review before release. Existing tool names and publication policy stay
unchanged. The fact-check tool gains an optional idempotency key for an explicitly
requested fresh attempt; repeated calls read the same attempt. Persist only public
verdict fields and closed operational statuses, never raw provider errors.

## 4. Acceptance

- A blocked provider does not keep an MCP request open; reads remain responsive.
- One provider job globally, even across article IDs; repeated requests do not
  launch another provider. Results and failures remain readable after completion.
- Copy/cover edits invalidate an in-flight result; a changed fingerprint cannot
  overwrite the current verdict. Cancellation kills and reaps the provider child.
- Preserve NotebookLM plus independent review and every existing PASS/BLOCK rule.
- Verify with mocked provider integration tests and the full Bridge test module.
- Production acceptance remains pending until authorized release and a supervised
  real check; local tests do not establish transport recovery in production.

## 5. Team

External Codex builder; independent Claude OAuth reviewer. Release owner must be
assigned by the coordinator; this task does not release. No parallel writers.

## 6. Appetite and stop-loss

One hour from 2026-10-01T03:52Z, one implementation and one correction round,
one independent reviewer, no descendants. Coordinator may renew the deadline.
Return a concrete blocker if the design needs a broader runtime/protocol change.

## 7. Evidence and release

Consumer: Damar's existing Marketing Bridge tools. Bites: a request returns a
running status promptly, later returns its persisted verdict without rerunning,
and unrelated reads remain usable. The deployed tunnel profile is unchanged.
The transport client's 502 client_internal/unknown failure is not yet a proven
implementation root cause; this change removes long-running request exposure.
