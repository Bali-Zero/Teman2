# JEV repository context selector pilot — Phase 0 freeze

> **Status:** FROZEN Phase 0 implementation contract.
> **Mandate:** `jev-context-selector-pilot-20260925`.
> **Mission:** BLUE, Gear 2, external builder prepare-only. No merge, arm, deploy,
> publish or client-facing send is authorized here.
> **Phase boundary:** Phase 1 evaluation or workflow integration requires an explicit
> owner GO after the Phase 0 evidence pack and independent BLUE review.

## 1. Objective and primary boundary

Phase 0 builds and proves a repository-only measurement harness. It must make the
existing TypeSafe call observable, measure one Codex task from native token receipts,
and produce an explicit optional context packet for deterministic arm B or arm C
(B plus JEV ranking). It does not install a hook, change the coding workflow, or claim
that context selection saves tokens.

Only Git-tracked material below the selected repository root may enter a selector
candidate or a TypeSafe request. HOME memory, session/chat history, client data,
credentials, response bodies and external messages are ineligible. The task itself
must be a tracked repository file or a task record in the frozen repository fixture.

The frozen GROUND is:

| Artifact                                                          | SHA-256                                                            |
| ----------------------------------------------------------------- | ------------------------------------------------------------------ |
| `research/operations/2026-09-24-jev-coding-optimization-audit.md` | `34cfaf707de5012fdab524c5dfb56a1a85b86e33a105465653e23c6859eac584` |
| `research/operations/2026-09-24-jev-coding-live-probe.json`       | `04027fb75ebb96c12fde5e85253fbe57d12c6b57ad67e5116bfc438df365f544` |

Changing either input invalidates the Phase 0 ledger until its hash is refreshed by a
new mandate. Historical probe results remain historical.

## 2. TypeSafe telemetry contract

`scripts/typesafe_client.py` keeps the compatibility `ask()` surface and adds a
structured result surface. Every call records these separately:

- `attempted`: at least one HTTP open was attempted;
- `response_received`: the endpoint returned a readable response body;
- `schema_valid`: the decoded envelope contains an `answers` object;
- `abstained`: the envelope is valid but supplies no usable answer for the requested
  question identifiers;
- `failure`: a stable failure code or `null`, never inferred from an empty answer;
- requested and resolved model (`resolved_model` is `null` when not reported);
- numeric vendor usage fields, with absent values represented as `null`;
- total latency, HTTP attempt count, and whether the caller must use its fallback.

Network errors, malformed responses, authorization/key silence, exhausted budget and
deadline expiry are different failure codes. No exception or response body is stored.
The legacy `ask()` returns only `answers | None` and preserves its never-raise promise.

`scripts/lint_paid_llm_entity.py` reports the structured fields. Its incumbent OR rule
does not change. “Judged” may mean only `schema_valid and not abstained`; attempted,
answered, schema-valid, abstained and failed counts are printed independently.

## 3. Codex per-task accounting contract

`scripts/codex_task_usage.py` reads Codex JSONL rollouts locally and emits aggregates,
never raw records. The task key is an explicit `root_turn_id`; the root session is an
explicit session/thread identifier. A session is included only when its first
`session_meta.payload.parent_thread_id` chain reaches the root session. The root itself
and those explicit descendants are the only eligible threads.

Within eligible threads, only `token_usage_record` rows with the requested
`root_turn_id` count. `response_id` deduplicates receipts. Aggregation uses each row's
incremental `usage`, never cumulative `turn_token_usage` or `thread_token_usage`.

The report separates:

- uncached input = `input_tokens - cached_input_tokens` when both exist;
- cached input;
- output;
- reasoning output;
- included root/descendant thread identifiers and receipt count.

If any included receipt lacks a required numeric field, that aggregate is `null` and
the missing count is reported. If an included JSONL stream contains a malformed line,
a non-object record or a token receipt with a non-object payload, the whole usage
aggregate is `null`, `incomplete_receipt_stream=true`, and each defect count is
reported. No missing value is coerced to zero. Threads whose parent cannot be
resolved, unrelated threads with the same turn id, malformed files, and other vendors
are excluded and reported as counts, not guessed into the total.

## 4. Selector arms and protected evidence

`scripts/jev_context_selector.py` is an explicit CLI/helper. The inputs are a repository
root, a tracked task/spec, arm `B` or `C`, and a frontier packet budget between 4,000
and 8,000 estimated tokens.

Both arms share exactly one candidate pool and deterministic score:

1. explicit repository paths in the task;
2. filename/stem and lexical matches from tracked files;
3. dependency proximity from local imports where it can be derived without executing
   code;
4. stable path tie-breaking.

Candidates are compact descriptions before selection; source content is read only when
assembling the packet. Candidate provenance carries repository-relative path, the Git
index blob, the SHA-256 of the exact bytes read, `working_tree_modified`, source kind,
and the deterministic reasons/score. A fixture task record additionally carries the
full fixture file SHA-256 as carrier provenance; its source hash covers only the exact
logical record placed in the packet.

Protected evidence is unconditional and a semantic score cannot remove it:

- the tracked task/spec;
- every explicitly referenced tracked file;
- the applicable tracked `AGENTS.md` chain for each selected path;
- files containing an explicitly quoted failing assertion or symbol definition when
  the deterministic collector finds one.

An explicit path match accepts an optional leading `./` and ordinary sentence
punctuation after the complete path, but never a suffix match inside a longer path or
filename. When a quoted symbol definition protects a file, the definition line and its
local context are mandatory excerpt lines even when the definition appears after the
generic hit cap. If those mandatory lines cannot fit, the run fails visibly rather than
emitting a protected row whose evidence is absent from the packet.

The packet contains exact excerpts only, a manifest of omitted candidates, and an
expansion command. It never invents summaries or file references. If protected evidence
alone exceeds the packet budget, the run fails visibly instead of truncating it.

Arm B selects by the deterministic score. Arm C asks JEV only to rank/select candidate
identifiers and then code assembles the same exact excerpts. Invalid identifiers,
abstention, unavailable service, deadline/budget exhaustion, malformed output or
oversize input returns arm B with `fallback=true` and a named reason.

Arm C uses an exact cache keyed by policy version, requested model, task bytes,
candidate identifiers/descriptions and source hashes. Only a schema-valid,
non-fallback selection containing at least one known candidate identifier is cached;
abstentions and transient or malformed failures are never persisted. Cache contents
are identifiers plus structured telemetry, never source or response bodies. Cache hits
are separate from network calls.

One arm-C semantic invocation owns a strict monotonic total deadline and a shared
HTTP-attempt budget across all batches. Deterministic candidate collection is measured
separately and is not charged to the network deadline. Retry sleep and per-open timeout
may not extend the semantic deadline. Late results are discarded. Phase 0 starts with
an optional 1.5 second semantic deadline and one batch; the dry run reports
payload/input-size bands and fallback instead of treating that value as a universal
optimum.

## 5. Frozen evaluation fixture

The versioned fixture contains 36 repository tasks: bug fixes, bounded features, tests,
refactors, configuration, ambiguous tasks, cross-file dependencies and no-relevant-file
cases. Each row freezes:

- a synthetic task id and task text with no client data;
- repository revision;
- stratum;
- independent relevant-file labels and protected-file labels;
- an explicit no-relevant-candidate flag where applicable.

For selection, one fixture row is canonicalized to the exact JSON record
`{"id": TASK_ID, "task": TASK_TEXT}`. Only that record enters candidate descriptions,
cache material or the assembled packet; labels and all other fixture rows stay outside
the selector input. Tests verify that removing labels or changing another task does not
change the produced candidate order or packet. Phase 0 uses the fixture only for
deterministic contract tests and a 3–5 task repository-only dry run; it does not report
coding-outcome efficacy.

## 6. Acceptance checks and stop conditions

Phase 0 is complete only when:

1. focused tests first fail against the frozen contracts and then pass;
2. legacy TypeSafe authorization, redirect and OR-composition tests remain green;
3. a synthetic Codex rollout test proves root-turn filtering, descendant inclusion,
   response deduplication and unknown-not-zero behavior;
4. selector tests prove tracked-file provenance, protected evidence, deterministic B,
   C fallback, exact cache, deadline and shared-attempt budget;
5. the 36-task fixture validates without using labels for selection;
6. a 3–5 task dry run writes aggregate raw metrics by input-size band, including
   fallback reason and cache/network counts;
7. the Phase 0 ledger records the two GROUND hashes, exact commands and observations;
8. an independent BLUE adversarial reviewer outside the contribution chain returns a
   verdict and its findings are resolved or recorded as blocking.

Hard stop: missed protected evidence, repository-provenance escape, cleartext secret or
PII exposure, unknown telemetry rendered as zero, or repeated deadline violation.
An inconclusive B-versus-C dry run retains B and does not authorize Phase 1.

## 7. Planned files and PR consumer

Expected implementation surface:

- `scripts/typesafe_client.py`, `scripts/lint_paid_llm_entity.py` and focused tests;
- `scripts/codex_task_usage.py` and `scripts/tests/test_codex_task_usage.py`;
- `scripts/jev_context_selector.py` and `scripts/tests/test_jev_context_selector.py`;
- `research/operations/fixtures/jev-context-selector-eval-v1.json`;
- Phase 0 ledger and raw metrics JSON under `research/operations/`.

Proposed PR observation:

`Bites: scripts/tests/test_jev_context_selector.py proves repository-only protected packets and visible C-to-B fallback; the Phase 0 ledger records the bounded 3–5 task dry run and Codex receipt accounting without authorizing workflow integration.`
