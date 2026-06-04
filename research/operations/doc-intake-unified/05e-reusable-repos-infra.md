---
date: 2026-06-04
domain: operations
client_case: doc-intake-unified (document-intake system infrastructure)
sources:
  - https://github.com/janbjorge/pgqueuer
  - https://github.com/vduseev/raquel
  - https://github.com/mattbillenstein/pg-queue
  - https://github.com/singer-io/singer-tap-template
  - https://github.com/moj-analytical-services/splink
  - https://github.com/567-labs/instructor
  - https://github.com/lennartpollvogt/ollama-instructor
  - https://github.com/a-rahimi/python-checkpointing2
  - https://github.com/cdancette/pyrunner
---

# 05e — Reusable GitHub repos for doc-intake infrastructure

Scope: REPO-APPLICATIONS with **readable, copyable code** for the 5 infrastructural pillars of
the unified document-intake system. Stack target: Python + asyncpg + Ollama locale, Mac Apple Silicon.
NOT pip-as-blackbox — code of others to read and adapt. Privilege small/readable over framework-giant.

## Master table

| Esigenza                                  | Repo                                       | URL                                          | Stelle | Lic          | Pezzo copiabile                                                                                                               | Grade              |
| ----------------------------------------- | ------------------------------------------ | -------------------------------------------- | ------ | ------------ | ----------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| (a) PG queue worker-loop                  | **pgqueuer**                               | github.com/janbjorge/pgqueuer                | ~1.5k  | MIT          | `pgqueuer/queries.py` (SKIP LOCKED dequeue SQL) + `qb.py` query-builder + executor retry                                      | Production         |
| (a) PG queue lease/DLQ readable           | **raquel**                                 | github.com/vduseev/raquel                    | ~50    | Apache-2.0   | claimed-status + `claimed_at+1min` reclaim + exponential backoff + `exhausted`/`expired` terminal states                      | Small/readable     |
| (a) PG queue minimal reference            | **pg-queue**                               | github.com/mattbillenstein/pg-queue          | ~19    | MIT          | `pg-queue.sql` schema + `workers/python/worker.py` (single-file loop, LISTEN/NOTIFY + tries + timeout)                        | Demo/reference     |
| (b) Multi-source adapter abstraction      | **singer-tap-template**                    | github.com/singer-io/singer-tap-template     | ~73    | **AGPL-3.0** | discover/sync two-mode connector skeleton (catalog + stream schemas)                                                          | Template           |
| (b) Real connector examples               | **singer-io/getting-started + tap-github** | github.com/singer-io                         | —      | varies       | `sync()`/`discover()` stream pattern, bookmark/state mgmt                                                                     | Reference          |
| (c) Entity resolution + review threshold  | **splink**                                 | github.com/moj-analytical-services/splink    | ~2.2k  | MIT          | DuckDB local backend, comparison-vs-threshold + Comparison Viewer dashboard for clerical review                               | Production         |
| (d) Deterministic stage pipeline + resume | **python-checkpointing2**                  | github.com/a-rahimi/python-checkpointing2    | small  | MIT          | generator-yield checkpoint→disk, resume from last good stage                                                                  | Reference/idea     |
| (d) Idempotent stage guard                | **pyrunner**                               | github.com/cdancette/pyrunner                | small  | MIT          | wrap script step → idempotent + no parallel double-run (done-marker pattern)                                                  | Micro-lib readable |
| (e) LLM structured extract + retry        | **instructor (567-labs)**                  | github.com/567-labs/instructor               | ~9k+   | MIT          | `dsl/maybe.py` (Maybe escape-hatch = never-invent), `dsl/partial.py`, Optional-field semantics, auto-reask on validation fail | Production         |
| (e) Ollama-specific validation loop       | **ollama-instructor**                      | github.com/lennartpollvogt/ollama-instructor | ~77    | MIT          | `src/ollama_instructor/` wraps Ollama Client + Pydantic validate + configurable retry attempts                                | Small/readable     |

## (a) Postgres job queue — worker loop, lease, DLQ

**Recommended read order**: `pg-queue` (understand the bare pattern in ~1 file) → `raquel` (steal the lease/DLQ
state-machine semantics) → `pgqueuer` (production-grade SQL + asyncpg pool + LISTEN/NOTIFY if you want the polished version).

- **pgqueuer** — the only one production-grade AND asyncpg-native (asyncpg single-conn + pool, also psycopg3).
  Python 3.11+, PG 12+. Workers coordinate via `FOR UPDATE SKIP LOCKED`; LISTEN/NOTIFY wakes idle workers with
  polling backup. Custom executors give retry strategies + job cancellation. Copy: the dequeue SQL in `queries.py`
  and the executor retry wrapper. Has graceful shutdown, completion guarantees, Prometheus.
- **raquel** — best _semantics_ reference for lease + DLQ, deliberately tiny ("rewrite in a day"). When a worker
  dies the row unlocks but stays `claimed`; reclaim if `claimed_at + 1 minute` elapsed and not locked = clean
  visibility-timeout. Retry = `backoff_base * 2^attempt` between `min_retry_delay`(1s) and `max_retry_delay`(12h).
  Terminal/DLQ states: `exhausted` (max_retry_count) and `expired` (max_age). SQLAlchemy core (not asyncpg) but
  the SQL/state-machine translates 1:1 to asyncpg.
- **pg-queue** — single-file `workers/python/worker.py` + `pg-queue.sql`. SKIP LOCKED + LISTEN/NOTIFY + `tries`
  column + `timeout` + `worker_id`. Explicitly built as a learn/reuse reference, not a framework.

**Adapt for us**: take raquel's claimed/exhausted/expired state-machine + claimed_at visibility-timeout, implement
the dequeue with pgqueuer's `FOR UPDATE SKIP LOCKED ... LIMIT 1` SQL over our asyncpg pool. DLQ = move row to
`*_dead` table (or status `exhausted`) on attempt>max. This mirrors our existing `events_outbox` outbox pattern.

## (b) Multi-source ingestion / connector framework

- **singer-tap-template** — the cleanest minimal "base adapter" abstraction: every source implements two modes,
  `--discover` (emit catalog of streams + JSON schemas) and `--sync` (emit records as JSON over stdout). Clean
  separation config / schema-discovery / sync. **CAVEAT: AGPL-3.0** — copyleft, do NOT vendor verbatim into our
  proprietary backend; use as _pattern reference only_ (re-implement the discover/sync interface ourselves).
- **singer-io/getting-started + tap-github** — real taps showing `sync()` per-stream + bookmark/state for
  incremental pulls. Good for seeing IMAP/Drive/webhook-style sources collapse into one record schema.

**Adapt for us**: a `BaseAdapter` with `discover()` + `poll() -> Iterable[RawDoc]`; concrete `EmailIMAPAdapter`,
`DriveAdapter`, `WebhookAdapter` each normalize to one envelope, then enqueue into the PG queue from (a).
Singer's stdout-JSON contract is overkill — keep the _abstraction_, drop the subprocess/pipe transport.

## (c) Entity resolution — doc → canonical persona

- **splink** — 2.2k stars, MIT, Python 3.9+, **DuckDB local backend** = perfect for Apple-Silicon offline (no
  cloud, aligns with OSINT Law 2). Probabilistic record linkage: comparison functions (JaroWinkler-at-thresholds,
  DateOfBirth, ExactMatch) + blocking rules + a match-weight score. The **auto-match vs manual-review** decision
  is exactly threshold-driven: pick a match-weight threshold, use the **Comparison Viewer dashboard** to inspect
  records on either side of the threshold for clerical review. Caveat: needs multiple low-correlation columns;
  not for single bag-of-words. For doc→persona use name + DOB + passport/NIK + address as comparison columns.

**Adapt for us**: above upper-threshold = auto-link to canonical client; between lower/upper = route to
human-review queue (reuse PG queue from (a) with status `needs_review`); below lower = new candidate entity.
Splink gives the score; the two thresholds + review-routing is our 20-line wrapper.

## (d) Deterministic staged pipeline — idempotency + crash-resume (NON LangGraph)

Deliberately avoiding Prefect/Dagster heaviness and agent-swarm orchestration. Minimal copyable patterns:

- **python-checkpointing2** (MIT) — write the pipeline as a generator; each `yield` snapshots state to disk;
  restart resumes from last good checkpoint, and surviving a code-fix on the crashed stage. This is the cleanest
  "crash-resume between stages" idea to copy, though its setjmp/longjmp magic is more inspiration than vendor.
- **pyrunner** (MIT) — wraps each step to be idempotent + prevents parallel double-run via done-markers. Copy the
  done-marker-per-stage idea: `stage1.done`/`stage2.done` (or a `pipeline_state(doc_id, stage, status)` PG row).

**Adapt for us (recommended, simplest)**: a `pipeline_runs` table keyed `(doc_id, stage)` with status. The
orchestrator is a plain `for stage in [extract, resolve, validate, persist]:` loop that SELECTs the row, skips if
`done`, runs + commits the stage transactionally, marks `done`. Crash-resume = re-run picks up first non-done
stage. Idempotency-per-stage = each stage upserts keyed by doc_id. Zero framework, fully auditable, deterministic.

## (e) LLM structured extraction — validation + confidence + retry + never-invent

- **instructor (567-labs)** — MIT, the reference. Two copyable gems: (1) **`dsl/maybe.py` Maybe pattern** =
  `MaybeUser{result: Optional[X], error: bool, message: Optional[str]}` — gives the LLM an explicit escape-hatch
  so it returns "not found" instead of hallucinating a value (directly satisfies "mai inventare"). (2) Optional
  fields semantics + **auto-reask on Pydantic validation failure** (the retry loop). `dsl/partial.py` for
  streaming partial objects. Works with Ollama via `from_provider("ollama/...")`.
- **ollama-instructor** — MIT, small, Ollama-specific: `src/ollama_instructor/` wraps the official Ollama Client,
  validates against a Pydantic model, retries failed validations with configurable attempts. Easiest to read end
  to end for our exact `ollama + asyncpg + Apple-Silicon` stack. Use `think:false` per our CLAUDE.md Qwen rule.

**Adapt for us**: per-field `Optional[...] = None` + a top-level `Maybe`-style wrapper so missing data is explicit
null, never fabricated. Add a `confidence: float` field per Ollama's structured-outputs docs and gate on it
(reuse our evidence thresholds: <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL). Retry loop = ollama-instructor's
validate-then-reask; cap attempts. Validation = Pydantic; null-safe = Maybe escape-hatch.

## License caveats (load-bearing)

- **singer-tap-template = AGPL-3.0** → pattern-reference ONLY, never vendor into proprietary code.
- All others MIT / Apache-2.0 → safe to read, adapt, vendor with attribution.

## Bottom-line recommended stack to copy

- Queue: raquel state-machine semantics + pgqueuer SKIP-LOCKED SQL over our asyncpg pool.
- Adapters: singer discover/sync abstraction re-implemented (skip AGPL code), normalize to one envelope.
- Entity resolution: splink + DuckDB local, two-threshold auto/review routing.
- Orchestration: plain `pipeline_runs(doc_id, stage, status)` loop — no framework (pyrunner done-marker idea).
- Extraction: ollama-instructor validate+reask loop + instructor Maybe escape-hatch + confidence gating.
