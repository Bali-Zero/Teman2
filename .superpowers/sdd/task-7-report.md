# Task 7 Report — Internal Research Room

## Outcome

Implemented the internal Research room for Bali Zero Magazine with a closed,
catalog-driven request surface, Analyst-only creation, sanitized Reader and
Operator views, D1-backed durable jobs, authenticated Pro worker transport, and
strict structured findings. The implementation remains an internal observatory
over Intel Lake, MATA GARUDA, Regulatory Watcher, and NotebookLM; it does not
replace or mutate those collectors. No production deployment, outward
publication, collector mutation, client-data access, or paid API call occurred.

## Review Remediation

Two review waves corrected four independently confirmed authorization, lease,
heartbeat-lifecycle, and DLP findings.

### Wave 1 — Authorization and Server Lease Fencing

- **Claim-time role revalidation:** the signed machine claim route reloads and
  validates the current role allowlist immediately before claiming work. Only
  current Analyst actor keys enter the repository claim contract; Operator
  membership never grants creation or execution authority.
- **Revoked creator quarantine:** an eligible queued or expired-lease job whose
  creator is no longer an Analyst is atomically moved to terminal `cancelled`,
  stripped of worker and lease material, and recorded through a metadata-only
  audit event. The bounded claim scan then continues to the next eligible job.
- **Atomic candidate fencing:** both cancellation and claim use the selected job
  ID, actor key, expiry, attempt budget, and queue/expired-lease state in the same
  transactional D1 batch. A lost race is skipped without returning stale work.
- **Authoritative lease expiry:** heartbeat and result acceptance compare
  `lease_deadline > now` inside their mutation CAS. The server clock, not a
  worker-provided completion timestamp, decides lease validity.
- **No stale result persistence:** completed and failed receipts share the same
  lease-valid update gate. If the lease is expired, the job remains claimed, no
  result or completion audit row is written, and the machine route returns a
  conflict.

### Wave 2 — Worker Lease Lifetime and Fail-Closed DLP

- **End-to-end heartbeat scope:** the worker now keeps its heartbeat active from
  the initial claim confirmation through adapter execution, projection, DLP,
  safe failure handling, and the terminal result acknowledgement or rejection.
- **Lease-loss cancellation:** if a heartbeat fails while terminal submission is
  still in flight, the worker cancels and awaits that operation, raises only a
  sanitized lease-loss error, and cannot continue into another submission path.
  The server-side lease CAS remains the authoritative stale-write fence.
- **Non-blocking projection:** synchronous projection runs in a worker thread so
  a slow projection cannot starve the event loop or suppress lease heartbeats.
- **Indeterminate DLP quarantine:** unavailable, timed-out, empty, or malformed
  classifier outcomes are explicitly indeterminate and treated as PII-bearing.
  Regex detection remains additive; an uncertain classifier can never downgrade
  a regex finding or authorize persistence.
- **Content-free failure boundary:** DLP rejection and failure receipts contain
  only the closed `dlp_rejected` outcome. Raw research text, classifier output,
  exception detail, and classifier-provided explanations are absent from return
  values and logs.

## Delivered Components

- Internal Research list, workbench, and structured finding detail views.
- Closed research catalog and bounded request/result schemas without free-form
  prompts, notebook identifiers, raw source text, credentials, or client PII.
- D1 migration and repository for idempotent creation, leasing, fencing,
  heartbeat, cancellation, completion, failure, replay, and metadata-only audit.
- Human APIs with current-role authorization and machine APIs with signed HMAC
  envelopes.
- Pro-side worker and transport with deterministic request handling and safe
  structured receipts.

## TDD Evidence

### Wave 1

- Review RED 1 used the real signed claim route and SQLite-backed D1 harness: a
  job created by a now-revoked Analyst was returned ahead of a valid current
  Analyst job.
- Review RED 2 used the real signed heartbeat/result routes: an expired lease
  still accepted a heartbeat; the same regression covers both completed and
  failed result receipts.
- GREEN proves the revoked job becomes terminal with metadata-only audit, the
  later valid job is returned, and all three expired-lease mutations return
  conflict without storing a result.

### Wave 2

- RED added deterministic coverage before implementation and produced exactly
  `14 failed, 19 passed`: four worker DLP uncertainty cases completed instead of
  quarantining, the heartbeat stopped after the adapter, in-flight terminal
  submission survived lease loss, and eight global DLP uncertainty cases failed
  open or exposed raw diagnostic detail.
- GREEN focused coverage is `33 passed`: an immediate adapter followed by slow
  projection, rejecting DLP, and terminal submission emits multiple heartbeats
  in every post-adapter phase and stops cleanly; lease failure cancels in-flight
  submission without persistence; unavailable, timeout, malformed, and empty
  classifier outcomes quarantine both PII-like and ordinary text without raw
  content in results or logs.

## Final Gates

From `apps/bali-zero-magazine`:

```text
npm run typecheck
exit 0

npm test
Build complete; 139 passed, 0 failed

npm run lint
exit 0

npx prettier --check app/api/machine/research/jobs/claim/route.ts \
  lib/server/research-http.ts lib/server/research-repository.ts \
  tests/research.test.mjs
All matched files use Prettier code style!
```

From `apps/zantara-media`:

```text
.venv/bin/python -m pytest tests/magazine/test_research_worker.py \
  tests/test_dlp.py -q
33 passed in 0.24s

.venv/bin/python -m pytest tests/magazine tests/test_dlp.py -q
104 passed in 25.58s

.venv/bin/ruff check zantara_media/magazine/research_worker.py \
  zantara_media/security/dlp.py tests/magazine/test_research_worker.py \
  tests/test_dlp.py
All checks passed!

.venv/bin/ruff format --check zantara_media/magazine/research_worker.py \
  zantara_media/security/dlp.py tests/magazine/test_research_worker.py \
  tests/test_dlp.py
4 files already formatted
```

Repository hygiene:

```text
git diff --check
exit 0
```

## Operational Boundary

The Research room is internal-only and deny-by-default. It accepts only closed
selectors and sanitized collector projections, never raw NotebookLM source IDs,
raw OSINT, credentials, or client PII. Activation still requires the normal
protected review, merge, configuration, and deployment process.
