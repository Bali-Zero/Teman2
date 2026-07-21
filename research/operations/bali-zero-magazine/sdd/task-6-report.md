---
adversarial_review: codex
adversarial_review_date: 2026-07-21
---

# Task 6 Report — Pro Editorial Publisher and Automatic Cadence

## Outcome

Implemented and hardened the deterministic Pro-side publisher that turns named,
sanitized collector projections into closed Magazine packets. Publication now
anchors the audit stream, uploads asset bytes, binds only canonical Worker
digests, and then promotes an edition or Breaking packet through the authenticated
machine transport. No production deployment, collector mutation, or paid API call
was performed.

## Review Remediation

All three critical, nine important, and three minor findings from the independent
Task 6 review were addressed.

- **Canonical two-phase promotion:** production publication no longer accepts an
  arbitrary local audit-event file. It first stages the exact packet, then walks
  the authenticated cursor-bound `GET /api/machine/audit-events/v1` feed from the
  last durable Pro checkpoint, verifies every event/hash/cursor/head and the exact
  operation + packet target, submits the signed receipt to
  `POST /api/machine/audit-anchor`, and finally retries the byte-identical packet.
  `--offline-audit-events` is fixture-only and cannot unlock `--publish`.
- **Target receipt is not page head:** concurrent candidates can make the target
  event precede the verified page head. The verifier now returns the page cursor
  and head independently from an exact target binding; the publisher verifies all
  returned events but signs only the contiguous prefix ending at that target.
  A receipt for a later candidate can therefore never unlock an earlier packet.
- **Sequential concurrent promotion:** the real Sites routes and SQLite-backed D1
  harness now stage edition A at audit sequence 1 and edition B at sequence 2,
  prove B remains blocked without its exact receipt, promote A, resume the feed
  from A's checkpoint, and then promote B. Both finalizations return `201` in
  audit order. The earlier persistent B `409` was a stale fixture: B must bind the
  future edition and Breaking pointer revisions (`1`), not A's genesis values.
- **Closed release proof:** each durable unlock row binds the stream, sequence,
  event hash, operation ID, packet ID, and accepted receipt hash. Restart checks
  re-verify the complete JSONL history and cross-check the signed receipt against
  the anchor ledger; forged, truncated, stale, or target-mismatched rows remain
  blocked. Every anchor attempt persists + fsyncs a blocked row before work and
  re-blocks on every exception or non-exact Sites response.
- **Restart-safe mutation reconciliation:** the durable outcome record binds the
  operation ID, route, body SHA-256, state, and response. Preflight runs before a
  send; completed responses replay locally; pending/unknown outcomes require a
  reconciliation result; retry occurs only after a proven `absent` result.
  Strict, fsynced JSONL and an operation-scoped `flock` held across the complete
  request lifecycle reject torn/conflicting rows and concurrent duplicate sends.
  Audit-anchor receipts are the deliberate exception: because Sites provides
  exact replay semantics, an unknown durable outcome is safely resent with the
  identical body and then committed locally from the replay response.
- **Two-phase durable audit acceptance:** a signed receipt is first fsynced to a
  separate pending journal and does not advance canonical Pro history. Only an
  exact Sites `created` or `replay` response promotes it to the accepted ledger;
  explicit rejection closes the pending receipt without advancing history, while
  an unknown transport outcome preserves it for byte-identical restart replay.
  Accepted/rejected receipt identities are terminal and cannot be reopened.
- **Persistent audit release interlock:** accepted receipt history is
  signature/hash verified and chained under exclusive locks. A stream-scoped
  filesystem lock serializes prepare, submit, and promotion across processes;
  local promotion independently enforces the exact next sequence. The persistent
  gate starts blocked, unlocks only after durable acceptance, and is checked on
  every edition and Breaking promotion across restarts.
- **Upload-first assets:** a closed `asset-intents.v1` manifest is required for
  publication. Upstream asset digests are rejected, each source is uploaded first,
  request/response identity is bound to packet ID + asset ID + source digest, the
  20-asset limit is enforced, and only returned canonical PNG digests enter the
  publication packet. Every intent must reference a story carried by the packet,
  and that invariant is checked before the first HTTP mutation.
- **Boundary DLP:** adapters recursively reject contaminated keys and values,
  including UUID/source identifiers, credentials, raw-OSINT markers, and Indonesian
  PII. Errors expose value-free codes and never silently sanitize a contaminated row.
- **Legal-effect gate:** `legal_effect` is a required closed claim enum in both
  Python and TypeScript. A claim that changes legal effect requires a verified
  official primary source; omission cannot downgrade the gate.
- **Readiness semantics:** composition selects the latest eligible healthy/fresh
  run per named system at or before the cutoff, rejects late candidates, preserves
  partial coverage, and emits the exact quiet-edition notice when there is no
  verified material change.
- **Cross-language parity:** one shared JSON corpus is executed through the real
  Python and TypeScript parsers for stories, editions, collector runs, asset
  metadata/responses, closed fields, coercion, and malformed URLs (including an
  invalid port).
- **Named read-only loaders:** Intel Lake, MATA GARUDA, NotebookLM, and Regulatory
  Watcher each use an explicitly named `.public.json` loader with a closed envelope,
  source-specific schema/version, system ID, cutoff, watermark, collector-run
  validation, real-instant cutoff comparison, and no raw-store access.
- **Versioned ranking:** immutable `rules.v1` data separates novelty from recency,
  applies deterministic tie-breaks, computes edition diversity, prioritizes core
  domains, and enforces a per-domain cap.
- **Real safety-path tests:** dry-run proves no network access; publish E2E uses an
  `httpx.MockTransport` and verifies audit -> asset -> edition order plus canonical
  substitution; Breaking dry-run, persistent release blocking, and a spawned
  process restart/reconciliation regression are covered.
- **Closed/durable wire details:** audit event versions are `Literal`-closed,
  sequence values are bounded to the safe unsigned wire domain, production
  transport requires an explicit durable journal, and publisher input schema
  discriminators are closed literals. Canonical timestamps always use millisecond
  UTC precision; WebP inspection parses VP8, VP8L, and VP8X dimensions and rejects
  animation. File reads in the async CLI/loader path run off the event loop.

## Delivered Components

- Frozen, extra-forbidden Pydantic mirrors for collector, story, edition, claim,
  evidence, placement, asset provenance, upload metadata, and canonical response.
- Deny-by-default public adapters and explicit source loader registry.
- Deterministic lineage collapse, evidence qualification, ranking, diversity,
  readiness cutoff, quiet/partial editions, and per-claim Breaking gates.
- One persistent `httpx.AsyncClient` with byte-exact body hashing, dual
  authentication headers, bounded retry, and durable outcome reconciliation.
- Append-only audit/outcome/release journals with process locks and fsync.
- RFC 8785 event verification and byte-exact Ed25519 anchor receipts with chained
  local history and public receipt submission.
- `magazine-publish morning` and `magazine-publish breaking`; network mutation is
  explicit through `--publish`, while `--dry-run` is deterministic.

## TDD Evidence

- Original RED: five collection errors before the Magazine package existed.
- Independent adversarial RED reproductions covered restart replay, UUID leakage,
  invalid-port parser drift, late-run readiness, missing quiet notice, and omitted
  legal-effect annotation.
- Remediation RED/GREEN cycles added durable restart reconciliation, persistent
  audit blocking, upload-first CLI orchestration, shared parser parity, source
  loaders, and real no-network E2E coverage. A final concurrency RED reproduced
  candidates A+B in one feed page and proved that a head-B receipt cannot unlock
  target A; GREEN binds and signs A exactly while still verifying head B.
- Cross-runtime RED reproduced the pre-POST accepted-ledger write: an explicit
  B-first Sites rejection left B as the local canonical head and prevented A.
  GREEN now keeps B only in the pending journal, accepts A normally, resumes an
  unknown pending receipt byte-for-byte after restart, commits exact replay once,
  and rejects terminal receipt reopening, binding drift, and anomalous sequence
  gaps even if a fixture claims `created`.

## Final Gates

From the repository root with `apps/zantara-media/.venv` activated:

```text
PYTHONPATH=apps/zantara-media pytest -q \
  apps/zantara-media/tests/magazine apps/zantara-media/tests/test_dlp.py
85 passed in 1.76s

ruff check apps/zantara-media/zantara_media/magazine \
  apps/zantara-media/zantara_media/cli/magazine_publish.py \
  apps/zantara-media/tests/magazine
All checks passed!

python -m compileall -q apps/zantara-media/zantara_media/magazine \
  apps/zantara-media/zantara_media/cli/magazine_publish.py
exit 0
```

From `apps/bali-zero-magazine`:

```text
npm run test:unit
124 passed, 0 failed

npm run typecheck
exit 0

npm run build
Build complete (including /api/machine/audit-events/v1 and /api/machine/audit-anchor)
```

Repository hygiene:

```text
git diff --check
exit 0
```

## Operational Boundary

The publisher submits public receipts to the Task 5 Sites ingress target and fails
closed unless Sites returns `created` or `replay`. This task does not deploy or
mutate the Sites runtime; enabling the cadence still requires the normal protected
PR/CI/deployment flow and configured environment secrets.

## Adversarial review

Codex challenged the title's Automatic Cadence wording against the operational
state. The publisher and schedules are prepared, but no autonomous cadence is
active until the protected merge, runtime secrets, Sites deployment, and
LaunchAgent loading occur. That activation boundary survives the review and is
explicitly retained; no claim of live publication is made.
