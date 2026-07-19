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

Four review waves corrected independently confirmed authorization, lease,
heartbeat-lifecycle, DLP, production-wiring, and filter-semantics findings.

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

### Wave 3 — Production Research Sources and Runner

- **Closed Pro source registry:** a strict server-side configuration maps only
  stable `topic:` and `entity:` identifiers to sanitized labels/search terms,
  exactly four bounded `*.public.json` projections, and masked NotebookLM
  references. Relative, symlinked, oversized, missing, duplicate, or unknown
  projection paths fail startup; no live notebook reference is committed.
- **Concrete local adapters:** search, compare, and timeline load the existing
  Intel Lake, MATA GARUDA, Regulatory Watcher, and NotebookLM public projection
  contracts. They filter only configured sources, stable subjects, domains,
  languages, evidence types, normalized confidence, normalized lifecycle state,
  and projection cutoff timestamps; claims without a public HTTPS citation and
  publication timestamp are excluded. Compare and timeline cardinality and
  ordering are deterministic.
- **Closed Notebook Insight:** the production client invokes the authenticated
  Pro-local `nlm` mechanism with `asyncio.create_subprocess_exec`, fixed argv,
  no shell, discarded stderr, bounded output, and a hard timeout. The prompt is
  assembled only from a configured public label and one fixed template. Strict
  JSON, evidence, URL, timestamp, numeric metadata, and sanitization checks run
  before a finding can reach the worker DLP gate; malformed, private, uncited,
  unavailable, or oversized responses become content-free failures.
- **Production composition root:** one factory builds all four adapters and the
  persistent signed `MagazineTransport` with a `DurableOutcomeJournal`. The new
  `magazine-research-worker` executable polls only through the existing outbound
  machine bridge, uses bounded backoff, handles termination cleanly, and logs no
  request, notebook, response, secret, or exception content.

### Wave 4 — Closed Filter Semantics

- **Sanitized metadata normalization:** local candidates expose only closed
  confidence and lifecycle values. Confidence labels and numeric scores map to
  the repository thresholds (`> 0.60` normal, `0.15–0.60` cautious, `< 0.15`
  abstain); conflicting, unknown, non-finite, or out-of-range values fail
  closed. Lifecycle aliases normalize only to published, amended, or
  superseded; missing metadata cannot satisfy a selected filter.
- **Every accepted local filter is enforced:** domain, language, evidence type,
  source, confidence, lifecycle, and cutoff filtering all run against sanitized
  candidate metadata. Combined filters are conjunctive and candidates missing
  any selected facet are excluded.
- **Provable Notebook facets only:** the TypeScript creation boundary, Python
  worker, and Notebook adapter reject unsupported nonempty domain, confidence,
  lifecycle, or language filters before any NotebookLM invocation. NotebookLM
  is the mandatory exact source; selected evidence types are included in the
  fixed prompt and enforced again against returned citations. A response with
  no surviving evidence becomes a content-free source-unavailable outcome, and
  its summary is derived only from the surviving structured claims.
- **Honest workbench controls:** Notebook Insight hides unsupported domain and
  language controls, fixes the source to NotebookLM, clears unsupported facets
  from the request, and explains why those combinations are unavailable.

## Delivered Components

- Internal Research list, workbench, and structured finding detail views.
- Closed research catalog and bounded request/result schemas without free-form
  prompts, notebook identifiers, raw source text, credentials, or client PII.
- D1 migration and repository for idempotent creation, leasing, fencing,
  heartbeat, cancellation, completion, failure, replay, and metadata-only audit.
- Human APIs with current-role authorization and machine APIs with signed HMAC
  envelopes.
- Pro-side production registry, four adapters, persistent signed transport,
  deterministic runner, and safe structured receipts.

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

### Wave 3

- RED was captured before implementation: the new production integration suite
  failed collection because `zantara_media.magazine.research_runtime` did not
  exist.
- GREEN production-factory coverage is `7 passed`: all four modes execute
  through the real factory against temporary sanitized projections and an
  injected Notebook client; the non-injected path constructs the persistent
  signed transport and durable journal; unknown subject IDs, raw query/path
  keys, missing or unsafe configuration, future-dated rows, uncited/private
  Notebook output, UUID leakage, unbound/numerically incomplete claims, shell
  invocation, unbounded output, backoff, and graceful stop are rejected or
  covered.

### Wave 4

- RED was captured before implementation. TypeScript research coverage produced
  `15 passed, 2 failed` for the missing creation-boundary and workbench
  restrictions. Python runtime and worker coverage produced `12 passed, 8
  failed` across confidence/lifecycle enforcement, fail-closed missing metadata,
  all four unsupported Notebook facets, and Notebook evidence filtering.
- GREEN focused coverage is `17 passed` in the TypeScript research suite and
  `32 passed` across Python runtime and worker suites. It exercises every local
  facet independently, combined filters, confidence thresholds, absent
  metadata, unsupported Notebook facets with zero NotebookLM calls, mandatory
  source selection, evidence filtering, and the no-surviving-evidence failure.

## Final Gates

From `apps/bali-zero-magazine`:

```text
npm run typecheck
exit 0

npm test
Build complete; 141 passed, 0 failed

npm run lint
exit 0

npx prettier --check components/research-workbench.tsx \
  lib/server/research-repository.ts tests/research.test.mjs
All matched files use Prettier code style!
```

From `apps/zantara-media`:

```text
.venv/bin/python -m pytest tests/magazine/test_research_runtime.py \
  tests/magazine/test_research_worker.py -q
32 passed in 0.71s

.venv/bin/python -m pytest tests/magazine tests/test_dlp.py -q
124 passed in 3.10s

.venv/bin/ruff check zantara_media/magazine/adapters.py \
  zantara_media/magazine/research_adapters.py \
  zantara_media/magazine/research_worker.py \
  tests/magazine/test_research_runtime.py \
  tests/magazine/test_research_worker.py
All checks passed!

.venv/bin/ruff format --check zantara_media/magazine/adapters.py \
  zantara_media/magazine/research_adapters.py \
  zantara_media/magazine/research_worker.py \
  tests/magazine/test_research_runtime.py \
  tests/magazine/test_research_worker.py
5 files already formatted

.venv/bin/python -m compileall -q zantara_media
.venv/bin/python -m zantara_media.cli.magazine_research_worker --help
exit 0
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
