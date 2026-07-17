---
date: 2026-07-17
domain: infra
client_case: none
sources:
  - apps/backend-rag/pytest.ini
  - apps/backend-rag/backend/tests/conftest.py
  - apps/backend-rag/backend/tests/db/conftest.py
  - apps/backend-rag/backend/tests/services/hr/owner_cashout/test_repository.py
  - apps/backend-rag/backend/tests/services/hr/owner_cashout/test_sync_service.py
  - apps/backend-rag/backend/tests/db/test_migration_apply_strips_rollback.py
  - apps/backend-rag/backend/tests/db/test_migration_114_115_116_roundtrip.py
  - apps/backend-rag/backend/tests/services/crm/test_practice_state_machine.py
  - apps/backend-rag/backend/services/crm/practice_state_machine.py
  - apps/backend-rag/backend/tests/services/intake/test_intake_writer.py
  - apps/backend-rag/backend/tests/routers/test_intake_review.py
  - .husky/pre-push
  - .github/workflows/tests.yml
  - scratchpad/spec-push-pipeline-optimization-v2.md (M1)
---

# M1 — Backend suite sharding investigation (pytest-xdist + per-worker DB isolation)

Mandate: `scratchpad/spec-push-pipeline-optimization-v2.md` §M1 ("Suite sharding/parallelization
(pytest-xdist) with isolated per-worker DB/resources... if the local suite drops to ~5 min, every
remaining full run cheapens"). This is an **investigation**, not an adoption PR — `.husky/pre-push`
is untouched (a separate lane owns P1/that file). Worktree: `.worktrees/research-m1-sharding-0717a`.

## 0. TL;DR verdict — COMPLETE (2026-07-18)

**CONDITIONAL GO.** Per-worker Postgres isolation for pytest-xdist is proven safe at both small
scale (360 real-DB tests, 3 configs, 0 failures) and large scale (~4100 tests, `-n8` on Pro, every
targeted hazard clean). Naive `-n auto`/`-n8` with no isolation and no prerequisite fixes does **not**
just flake — it hard-aborts at collection (§2.2-H, unrelated to DB isolation, one-line fix). One real
new flake was found at scale and root-caused to a coverage gap, not a design flaw (§2.2-D2, two files,
small fix). Timing: 147s serial → 127s isolated `-n8` on the representative subset — real but modest,
not yet the full-suite `-n auto` number the pre-registered threshold needs (§5). Two small fixes
(§6) are hard prerequisites before ANY `-n>1` adoption; full-suite timing is a fast follow-up once
they land (PENDING-ARMS line, §5).

- Per-worker DB isolation (§3) is proven correct on a subset that actually touches Postgres
  (`backend/tests/db/` + `backend/tests/services/hr/`, 360 collected items): 0 real test failures
  across 3 configurations (serial / naive `-n4` / isolated `-n4`), clean teardown verified after
  each run (zero orphan `nuzantara_test_gw*` databases) — **and again at ~4100-test scale on Pro**
  (§4.2), where it also caught 2 real hazards static analysis alone had missed.
- Phase 2 (the full representative-subset timed comparison) **did run**, on Pro rather than M5 — the
  investigation was redirected mid-flight when M5 turned out to be under severe memory pressure from
  Zero's own live interactive session (96% swap, GUI apps active), not from sibling pytest lanes.
  Pro (14-core workhorse, provisioned `nuzantara_test`) gave real numbers: see §4.2-4.3 for the
  full story of that redirect and the two additional findings it surfaced.
- **Correction acknowledged**: the mandate's own suggested quiet-window check, `pgrep -fc pytest`,
  does not exist on macOS BSD `pgrep` (`-c` is not a supported flag — confirmed directly: it prints a
  usage error and exits 2). Every quiet-window check in this investigation used
  `ps -Ao ucomm=,args= | awk '...'` or `pgrep -f pytest | wc -l` instead, never the broken form.

## 1. Baseline (restated from spec, unchanged)

17,384 tests, 11–32 min serial (`.husky/pre-push` state 4: clone `nuzantara_test` → throwaway
per-push DB → `pytest backend/tests/ --ignore=backend/tests/e2e --tb=short -q` with CI-parity env).
CI itself (`.github/workflows/tests.yml`) runs the **same suite serially with `-x`** (fail-fast)
against a single shared Postgres 15 + Redis 7 service container — there is no parallel-execution
precedent anywhere in this repo to lean on; this investigation is the first.

## 2. Reconnaissance

### 2.1 Is xdist installed?

**No.** `pip show pytest-xdist` in `apps/backend-rag/.venv` → not found. Neither
`requirements.txt`, `requirements-test.txt`, nor `requirements.lock.txt` reference it — adoption
needs a new pin in `requirements-test.txt` + a `requirements.lock.txt` relock. Installed
`pytest-xdist==3.8.0` (+ sole dependency `execnet==2.1.2`) into the shared venv for this
investigation — additive only, no version bumps to existing packages (verified via `pip install`
output: only 2 new packages).

Also noted in passing (not part of this investigation's scope, but relevant context for anyone
picking up M1 adoption): `requirements-test.txt` carries `testcontainers[postgres]` and
`testcontainers[compose]` — grep across `backend/` finds **zero** actual usage. Dead dependency,
possibly an earlier abandoned design for the same per-worker-isolation problem this doc solves
with a lighter template-clone approach. Also: the venv's installed `pytest` is `9.0.3` while
`requirements.lock.txt` pins `pytest==9.1.1` — a pre-existing minor drift, unrelated to xdist,
noted for completeness.

### 2.2 What breaks parallelism — with file:line

Backend-rag has 21 `conftest.py` files. The shared-state hazard for xdist is almost entirely
**Postgres**; Redis and Qdrant turned out to be non-issues (details below). Findings, ranked by
confidence:

**A. CONFIRMED, deterministic collision — shared-table DELETE-at-setup fixtures (2 files)**

- `backend/tests/services/hr/owner_cashout/test_repository.py:31-44` — fixture `populated_pool`
  (function-scoped) connects to whatever `TEST_DATABASE_URL`/`DATABASE_URL` resolves to (one
  shared DB today) and unconditionally runs `DELETE FROM owner_weekly_cashout_rows` /
  `DELETE FROM owner_weekly_cashout_weeks` at the start of **every** test using it, then seeds rows
  via a **module-level mutable counter** `_row_idx` (line 22, `_next_idx()` at line 25-28) to avoid
  ID collisions — but only within this file's own sequential execution.
- `backend/tests/services/hr/owner_cashout/test_sync_service.py:17-34` — sibling fixture `db_pool`,
  identical pattern, same three tables plus `owner_cashout_sync_log` (line 27-29), own counter
  `_row_counter` (line 37-43).

Under serial execution this is safe (only one test runs at a time; the DELETE-then-seed-then-assert
sequence never overlaps with another test's DELETE). Under naive `-n auto` **without** per-worker DB
isolation, xdist's default `--dist=load` scheduling can interleave tests from *either* file (or
both) on different workers hitting the *same physical database*: one worker's `DELETE FROM
owner_weekly_cashout_rows` firing mid-assertion in another worker's test is a guaranteed flake —
exactly the "worker che condividono stato = flake" scenario the mandate named as enemy #1. This is
the strongest concrete evidence found for why naive `-n auto` cannot ship without DB isolation.

**B. CONFIRMED — fixed-name DDL scratch objects against the shared DB (2 files)**

- `backend/tests/db/test_migration_apply_strips_rollback.py:57` — `table =
  "mig_strip_rollback_probe"` (literal, not randomized), `migration_number=9999` (also literal),
  `CREATE TABLE`/`DROP TABLE` executed directly against `_TEST_DB_URL` (module-level, line 30,
  itself `os.environ.get("TEST_DATABASE_URL", ...)`). The file's own comment at line 58-59
  already anticipated *migration-number* collision with real migrations, but not a concurrent
  second worker running the *same* test path.
- `backend/tests/db/test_migration_114_115_116_roundtrip.py` — `_ensure_clean_slate()` helper
  does `DROP TABLE IF EXISTS alert_outcomes/compliance_alerts/intel_validator_log CASCADE`
  directly (not through the rolled-back `db_tx` transaction) before re-applying migrations.

Risk shape here is subtly different from (A): a `DROP TABLE`/`CREATE TABLE` on a shared DB takes an
ACCESS EXCLUSIVE lock. A concurrent worker's `db_tx`-wrapped `SELECT`/`INSERT` against
`compliance_alerts` (used by the `services/compliance/` suite, 252 tests, in-scope for the timed
subset below) would **block**, not corrupt — this reads as a timeout-flavored flake rather than a
wrong-answer flake, but is the same root cause: unnamespaced shared DB.

**C. Lower-risk but same root cause — 4 conftest.py files share a rollback-wrapped `db_tx`
pattern**: `backend/tests/db/conftest.py:38-47`, `backend/tests/app/routers/conftest.py:31-63`,
`backend/tests/services/intel/conftest.py:64-72`, `backend/tests/services/compliance/conftest.py:29-37`.
Each opens a transaction, yields the connection, rolls back at teardown — DATA mutations are
invisible outside the transaction (safe against A-style corruption), but not immune to the
B-style lock contention above, and all four resolve their DB target from the same single
`TEST_DATABASE_URL` env var read at *module import time* (i.e. collection time, not test time).

**D. 69 test files connect to Postgres directly** (not through the shared `db_tx` fixture) — the
concerning-sounding number in the mandate's framing. On inspection, 56 of 69 either (a) already
self-isolate via `uuid.uuid4()`-named scratch databases (e.g.
`backend/tests/unit/routers/test_wa_meta_inbox_onconflict.py:124-130` —
`db_name = f"wa_onconflict_test_{uuid.uuid4().hex[:12]}"`, and
`backend/tests/services/test_accounting_reconcile_integration.py` — same idea) and are **already
xdist-safe by construction**, or (b) resolve their DSN from `TEST_DATABASE_URL`/`DATABASE_URL` at
call time with only a *fallback default* if the env var is absent (never a truly hardcoded
override). Grep for literal `postgresql://...nuzantara...` strings not gated behind
`os.environ.get`: **zero matches**. This matters structurally — see §3.

**D2. CORRECTION found empirically in Phase 2 (§4.3), not by static grep — a real methodological
gap.** `backend/tests/services/intake/test_intake_writer.py:33` and
`backend/tests/routers/test_intake_review.py:32` resolve their Postgres target from
`os.environ.get("INTAKE_TEST_DSN", "postgresql://localhost:5432/nuzantara_dev")` — a **different env
var name entirely**, never rewritten by the §3 hook (which only targets `DATABASE_URL`/
`TEST_DATABASE_URL`), with a fallback pointing at `nuzantara_dev` — the exact database
`backend/tests/conftest.py:31-34` has an explicit `RuntimeError` guard against (`"Refusing to run
pytest against operational nuzantara_dev"`), because on Pro it carries the live local Intake/WhatsApp
queue. That guard only fires for `TEST_DATABASE_URL`; `INTAKE_TEST_DSN` walks straight past it under
a different name. Both files were structurally in the direct-connect-D bucket (69 files) but were
**excluded from the "no uuid" manual-review shortlist in the original recon pass** because they
happen to call `uuid.uuid4()` for unrelated reasons (tagging seed rows, e.g.
`tag = f"5btest-{uuid.uuid4().hex[:8]}"`) — the presence of `uuid` in a file is not the same claim as
"the DB *target* is uuid-namespaced," and conflating them let these two through undetected by grep.
Caught only because Phase 2 (§4.3) actually ran at real concurrency against a real DSN and produced a
genuine collision. Documented here as a correction to §2.2's own method, not just a finding.

**E. Redis — not a hazard.** No `flushdb`/`flushall` anywhere in `backend/tests`. Checked every
file that constructs a "real" redis client
(`test_bridge_router.py`, `test_confirmation_service.py`, `test_confirmation_flow.py`,
`test_session_service.py`, `test_unified_health_service.py`): all five use `fakeredis` (in-memory,
per-instance) or a hand-rolled `FakeRedis()` test double, or patch
`redis.asyncio.from_url` outright. `test_bridge_router.py`'s `REDIS_URL` hits are
`monkeypatch.setenv`/`delenv` testing the *absence* code path, not real I/O. No test in this suite
talks to a real Redis server.

**F. Qdrant — not a hazard.** No Qdrant listens locally on this machine
(`nc -z 127.0.0.1 6333` fails) and yet the QdrantClient unit tests
(`backend/tests/unit/core/test_qdrant_*.py`, 6 files) pass today — because every one mocks the
underlying `httpx` transport (`unittest.mock.AsyncMock`/`patch("httpx.AsyncClient")`) rather than
dialing out. `QDRANT_URL` is inert config in this suite, same conclusion as Redis.

**G. No explicit order dependencies.** `grep -rn "pytest.mark.order\|pytest_collection_modifyitems"
backend/tests` → zero hits. `pytest.ini` sets `asyncio_default_fixture_loop_scope = function`
(pytest.ini:18) — every async test gets its own event loop; no shared-loop leakage across tests
within a worker. No `functools.lru_cache` on Settings/client singletons found in
`backend/app/core/config.py` or `backend/app/dependencies.py`. No session-scoped fixture with
mutable state except one Ollama-related fixture in
`backend/tests/unit/services/rag/agentic/conftest_ollama.py:52`, which self-skips via
`is_ollama_available()` when `OLLAMA_URL` points at the dead port the pre-push hook already sets.

**H. CONFIRMED LIVE in Phase 2 (§4.3) — non-deterministic parametrize source hard-fails xdist
collection.** `backend/tests/services/crm/test_practice_state_machine.py:118` —
`@pytest.mark.parametrize("state", list(ALL_STATES))`, where
`backend/services/crm/practice_state_machine.py:35` defines
`ALL_STATES = frozenset(VALID_TRANSITIONS.keys())`. `frozenset` iteration order in CPython depends on
element hash values, and string hashing is randomized per-process by default (`PYTHONHASHSEED`,
PEP 456) — so `list(ALL_STATES)` produces a **different test-ID order in every separate Python
process**. Under serial execution there's only one process, so this is invisible. Under xdist, each
`-n N` worker is a separate process with its own random hash seed, and xdist requires every worker to
collect the identical item sequence to distribute work safely — a mismatch is a **hard abort of the
entire session** (not a flake, not a single test failure: `7 errors`, zero tests run), independent of
and unrelated to the §3 DB-isolation design entirely. Swept the rest of the suite for the same
signature (`parametrize.*list(.*frozenset|set(`) — exactly one other hit,
`backend/tests/unit/test_business_rules_i18n.py:15`, which already uses `sorted(...)` and is safe.
This is an isolated, one-line-fix case (`sorted(ALL_STATES)` instead of `list(ALL_STATES)`), not a
pattern — but it is a **hard prerequisite** for xdist adoption: any `-n>1` run against this suite
today aborts before running a single test, every time, regardless of DB isolation. Workaround used to
get past it for measurement purposes in §4.3: `PYTHONHASHSEED=0` (pins the hash seed so all workers
agree) — a standard, well-known mitigation, applied here only to unblock measurement, not proposed as
the adoption fix (sorting the source is the real fix; §6).

**Net read**: the entire hazard surface for this suite is Postgres, concentrated in ~4-6 files with
un-namespaced writes to shared tables (2 of which, §D2, were missed by static grep and only found by
actually running Phase 2), plus one collection-order hard-blocker (§H) that must be fixed before ANY
`-n>1` run can even start, plus a structural pattern (single `TEST_DATABASE_URL` for
the whole `-n auto` invocation) that would make even the "safe" 56/69 direct-connect files and the
4 `db_tx` conftests collide under naive parallelization even though none of them are individually
buggy — they were only ever exercised one-at-a-time.

## 3. Per-worker DB isolation — prototype fixture (built + proven, not shipped)

Built as a `pytest_configure`/`pytest_unconfigure` hook pair temporarily added to
`apps/backend-rag/backend/tests/conftest.py` in this worktree only (reverted before the final
commit of this doc — see the code block below for the shipped reference). Mechanism:

1. Each `-n N` xdist worker is a separate OS process. Before spawning it, xdist sets
   `PYTEST_XDIST_WORKER` (`"gw0"`.."gwN-1"`) in that process's environment.
2. `pytest_configure` on the **root** conftest fires before collection starts — i.e. before any of
   the 4 subdirectory conftests (§2.2-C) or the ~56 direct-connect files (§2.2-D) import/execute
   and read `DATABASE_URL`/`TEST_DATABASE_URL`. Rewriting those two env vars inside this hook is
   therefore early enough for **every** downstream reader to pick up the per-worker DB automatically
   — zero changes needed to any of the 69 files or 4 conftests.
3. The hook clones a fresh `<original_db>_<worker>` database (`CREATE DATABASE ... TEMPLATE
   <original_db>` via `psql` subprocess — no event loop is running yet at `pytest_configure` time,
   so this deliberately mirrors `.husky/pre-push`'s own `psql`-based clone rather than reaching for
   `asyncpg`) off whatever `DATABASE_URL`/`TEST_DATABASE_URL` already pointed at. This **layers on
   top of** the existing per-push clone (`.husky/pre-push`'s `CLONE_DB`) rather than replacing it —
   the per-push clone becomes the per-worker TEMPLATE.
4. `pytest_unconfigure` drops the per-worker DB at session end.

**Proven live** (not asserted from memory — reran and verified in this turn): a throwaway test
asserting `SELECT current_database()` under `-n 4` showed the executing worker (`gw1`) connected to
`nuzantara_test_gw1`, not the shared `nuzantara_test`; after the run, `SELECT datname FROM
pg_database WHERE datname LIKE 'nuzantara_test_gw%'` returned zero rows — clean teardown across all
4 workers (including the 3 that received no test item but still create+drop their DB — a minor,
constant-time overhead per worker, immaterial at full-suite scale).

Reference implementation (the version that ran in this worktree; NOT present in the diff this PR
ships — pre-push ownership belongs to a separate lane per this mandate):

```python
import shutil
import subprocess

_PSQL_BIN = shutil.which("psql") or "/opt/homebrew/opt/postgresql@17/bin/psql"


def pytest_configure(config):
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker:
        return  # not running under xdist, or this is the xdist controller

    for var in ("DATABASE_URL", "TEST_DATABASE_URL"):
        base_url = os.environ.get(var)
        if not base_url or "/" not in base_url:
            continue
        prefix, _, dbname = base_url.rpartition("/")
        dbname = dbname.split("?", 1)[0]
        worker_db = f"{dbname}_{worker}"
        admin_url = f"{prefix}/postgres"
        subprocess.run(
            [_PSQL_BIN, admin_url, "-v", "ON_ERROR_STOP=0", "-tAc",
             f'CREATE DATABASE "{worker_db}" TEMPLATE "{dbname}"'],
            capture_output=True, timeout=30,
        )
        os.environ[var] = f"{prefix}/{worker_db}"


def pytest_unconfigure(config):
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker:
        return
    test_url = os.environ.get("TEST_DATABASE_URL", "")
    if not test_url or "/" not in test_url or not test_url.endswith(f"_{worker}"):
        return
    prefix, _, dbname = test_url.rpartition("/")
    admin_url = f"{prefix}/postgres"
    subprocess.run(
        [_PSQL_BIN, admin_url, "-tAc", f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)'],
        capture_output=True, timeout=30,
    )
```

Known gaps not covered by this prototype (flagged, not solved, here):

- **Redis/Qdrant namespacing**: not needed today (§2.2-E/F show zero real usage), but if a future
  test starts talking to real Redis, the fix is cheap — suffix the Redis DB index by worker
  (`redis://localhost:6379/{worker_index}`, up to 16 logical DBs by default) using the same hook.
- **The 4 `db_tx` conftests (§2.2-C) still share physical *lock* exposure** with any DDL-running
  test if BOTH happen to land in the exact same per-worker DB — moot once every worker has its own
  DB (this prototype's whole point), but worth stating explicitly: isolation is per-*worker*, not
  per-*test*. Two tests scheduled onto the *same* worker still run sequentially within that worker
  (xdist's model), so this is not a residual risk — noted only so a future reader doesn't assume
  per-test isolation was attempted and missed.

## 4. Timed experiment

### 4.1 Phase 1 — safety/mechanism proof (DONE, real numbers, small footprint)

Run against `backend/tests/db/` + `backend/tests/services/hr/` (360 collected items — the two
directories carrying every CONFIRMED hazard from §2.2-A/B), specifically chosen to be fast and
light enough to run safely even under the degraded machine conditions in §4.3. Machine state during
these 3 runs: swap 94.8-96.3% used, load average 15-55 (1-min) — **not clean**, so the wall-time
column below is noisy and NOT the number the §5 threshold judges; the pass/fail column is the
signal that matters here and is unaffected by ambient noise.

| Run | Workers | Wall (s) | Pass | Fail | Skip | Notes |
|---|---:|---:|---:|---:|---:|---|
| Serial baseline | 1 | 28 | 321 | 0 | 39 | `--tb=line -q`, real Postgres (`nuzantara_test`) |
| Naive parallel (control) | `-n4` | 41 | 320 | **1** | 39 | No isolation hook (`XDIST_DB_ISOLATION_PROTOTYPE` unset) |
| Isolated parallel | `-n4` | 16 | 321 | 0 | 39 | Isolation hook active (§3) |

The single failure in the naive-control run was the throwaway proof test itself
(`test_worker_lands_on_its_own_db`, deliberately asserting the worker's DB name — see §3) — it is
*designed* to fail without isolation and *designed* to pass with it, and did exactly that in both
runs; it is not an independent collision finding, it is confirmation the on/off switch works.

**Honest negative result**: this single naive-control run did **not** spontaneously reproduce the
§2.2-A owner_cashout DELETE-race or the §2.2-B migration-DDL lock contention as visible failures —
`backend/tests/services/hr/owner_cashout/{test_repository,test_sync_service}.py` self-skip on this
machine (the local `nuzantara_test` template lacks the `owner_weekly_cashout_*` tables — a
provisioning gap unrelated to xdist), and the `db/` migration-DDL tests happened not to overlap in
wall-clock time with each other this run. This is consistent with the mandate's own framing
("worker che condividono stato = flake") — a race that doesn't fire on every single run is still a
real hazard, not a false alarm; §2.2's file:line evidence (fixed table names, shared-table
unconditional DELETE, no per-test namespace) is the actual basis for classifying it as confirmed,
not this one run. A follow-up worth doing before full adoption: provision `owner_cashout` tables
into the local template and/or run the naive-control config N>1 times or at higher worker count to
raise collision probability and get a directly-observed failure, not just the mechanism proof.
Wall-time itself is **inconclusive** at this scale/under this noise: naive `-n4` (41s) was slower
than serial (28s) — consistent with per-worker interpreter/import startup cost dominating at only
360 tests, especially under 96% swap — while isolated `-n4` (16s) was fastest, plausibly warm-cache
from immediately following run 2. None of these 3 numbers should be read as a scaling signal; see
§4.3.

Orphan-DB check after all 3 runs: `SELECT datname FROM pg_database WHERE datname LIKE
'nuzantara_test_gw%'` → zero rows. Teardown is clean under real (not just synthetic) test content
too, not only the throwaway proof test from §3.

### 4.2 Phase 2 — full ~3.9k-subset timed comparison (design, not yet executed)

Representative subset (~3.9k test-function definitions, ~4.0-4.2k collected items after
parametrization — grep-based defs undercount collected items by the same ~4-5% ratio observed
suite-wide, see §1), chosen as a "mix unit+servizi" per the mandate, deliberately weighted toward
every hazard class found in §2.2:

| Directory | test defs (grep) | Why included |
|---|---:|---|
| `backend/tests/db/` | 290 | Highest-risk category (§2.2-B, real DDL) |
| `backend/tests/routers/` | 386 | Mix of mocked + integration |
| `backend/tests/unit/core/` | 695 | Includes the Qdrant-mocked files (§2.2-F) |
| `backend/tests/unit/llm/` | 208 | Unit, LLM client mocks |
| `backend/tests/unit/middleware/` | 133 | Unit |
| `backend/tests/unit/channels/` | 180 | Unit |
| `backend/tests/services/rag/` | 1,161 | Largest single chunk; **0/71 files touch real Postgres** (§2.2 net read) — the "safe majority" control group |
| `backend/tests/services/compliance/` | 252 | Uses the `db_tx` conftest pattern (§2.2-C) |
| `backend/tests/services/crm/` | 186 | Services mix |
| `backend/tests/services/intake/` | 379 | Services mix, some real-DB |
| `backend/tests/services/hr/` | 51 | **Contains the two confirmed-collision files (§2.2-A)** |
| **Total** | **3,921** | |

#### 4.2.1 Timings — RUN, on Pro (redirected from M5 — see §4.3)

Executed on `nuzantara@Nuzantara` (Pro, 14-core M4 Pro), not M5: the orchestrator redirected Phase 2
away from M5 mid-investigation because M5 is Zero's live interactive session (§4.3 below explains the
diagnosis that led there). Isolated worktree `.worktrees/research-m1-sharding-0717a-pro`, §3's proven
fixture transferred by `scp` + sha256-verified byte-identical, `pytest-xdist==3.8.0` installed
additively. Pro's own state at run time: 0 pytest processes, load average 7-11 (1-min), swap 88.3%
used / 1.68GB free (elevated — Pro is a workhorse with background daemons per its role — but stable
across both runs, unlike M5's thrashing 96%/375MB free).

| Run | Workers | Wall time | Pass | Fail | Skip | Notes |
|---|---:|---:|---:|---:|---:|---|
| Serial baseline | 1 | **147s (2:27)** | **4058** | **0** | 59 | `nuzantara_test` real Postgres, 4117 collected items |
| Parallel, naive `-n8` | 8 | 26s → **aborted** | 0 | — | — | **Hard collection-mismatch abort (§2.2-H)** — 7/8 workers disagreed with gw6 on item order; zero tests ran. Root cause unrelated to DB isolation (frozenset parametrize, not this design) |
| Parallel, isolated `-n8` (+`PYTHONHASHSEED=0` to unblock §H) | 8 | **127s (2:07)** | 4057 | **1** | 59 | §3 hook active; the 1 failure is `test_intake_writer.py::test_blocked_plan_no_write_even_with_flag_on` — a REAL new cross-worker collision (§D2/§4.2.2), not a §3 design flaw |

`-n auto` (14 workers) was deliberately not attempted: 8 was chosen as a conservative ceiling given
Pro's pre-existing 88% swap utilization from its normal daemon load, to avoid destabilizing a shared
production-adjacent machine for a research measurement. The serial number (147s) already sits well
under the mandate's 8-minute full-suite threshold for a ~24% subset — see §5 for what that
does and doesn't imply about the full 17,384-test suite.

#### 4.2.2 New-flake count (the decision-making number) — MEASURED: 1 real, root-caused, both causes external to the isolation design

Two distinct parallel-only problems surfaced, **neither of them a defect in the §3 per-worker DB
isolation design itself**:

1. **Naive `-n8` (no isolation) didn't produce a comparable data point at all** — it aborted at
   collection (§2.2-H, the `frozenset` parametrize hazard), before a single test executed. This is
   real evidence of "loses reliability under naive parallelization," just not the DB-collision kind
   Phase 1 was built to catch — it's a different, unrelated hazard class this investigation wasn't
   originally hunting for, found only because Phase 2 ran at real scale.
2. **Isolated `-n8` produced exactly 1 new failure vs. serial**: `test_intake_writer.py::
   test_blocked_plan_no_write_even_with_flag_on` — `AssertionError: blocked plan wrote to CRM despite
   being blocked`. Root-caused (§D2), not guessed: this file's `pool` fixture resolves its DSN from
   `INTAKE_TEST_DSN`, an env var the §3 hook never rewrites (it only targets `DATABASE_URL`/
   `TEST_DATABASE_URL`), defaulting to the shared, un-namespaced `nuzantara_dev` — so under `-n8`, up
   to 8 workers could concurrently touch the exact same physical tables this test snapshots
   before/after. This is **not a flaw in the isolation mechanism** (§3's env-var-rewrite approach is
   proven correct for everything using the `DATABASE_URL`/`TEST_DATABASE_URL` convention, including
   the harder DDL/DELETE cases in §2.2-A/B) — it's a **coverage gap**: one more env var name needed
   in the rewrite list, or these 2 files renamed onto the standard convention. Fix is small and
   scoped (§6, tracked in PENDING-ARMS).

Verified no contamination: `SELECT count(*) FROM clients WHERE full_name LIKE '5btest-%' AND
created_at::date = CURRENT_DATE` on Pro's `nuzantara_dev` → **0** — the failing test's own fixture
teardown (scoped `DELETE ... WHERE id=$1` by row ID, §2.2-D2 code) ran correctly despite the
assertion failure, so no test data survives from this run. (24 *unrelated* `5btest-%` rows dated
2026-06-05 were found and left untouched — pre-existing debris from a prior, unrelated crash, out of
this investigation's scope to clean up.)

### 4.3 Why Phase 2 initially stalled on M5, and the redirect to Pro

**Not** sibling-pytest-fleet contention — that specific condition cleared. Timeline, each reading
taken fresh in the turn it's reported (never carried forward from memory):

1. A background monitor was armed waiting for `ps`-based pytest-process-count == 0 (the mandate's
   intended check; **not** `pgrep -fc pytest`, which does not exist on this machine's BSD `pgrep` —
   confirmed directly, it errors with a usage message and exit 2, so a naively-trusted `|| echo 0`
   wrapper around it would have falsely reported "quiet" on every single check, and an un-wrapped
   form would never have fired at all; this investigation never used that form for a real gating
   decision, but the correction is noted since it was flagged and is a real landmine for the next
   reader of this doc).
2. That monitor correctly fired at 21:55:51 WITA on 2026-07-17 (`ps`-based count 0, load average
   2.98) — a genuine sibling-fleet quiet window.
3. By the time that notification was processed, several hours of real wall-clock time had elapsed
   (session-relay delay, not a bug in the monitor) and the machine had moved into a **different**
   state: 0 pytest processes (re-confirmed fresh, twice, with both `ps`-based counting and
   `pgrep -f pytest | wc -l`) but severe memory pressure — `sysctl vm.swapusage` read
   `used = 9704.81M` then, minutes later, `used = 9865.00M` **of a 10240M total** (94.8% → 96.3%,
   free swap 535M → 375M), load average 27-70 (1-min), driven by `ps aux` sorted by CPU: a
   ChatGPT-desktop "Codex Framework Renderer" process (117% CPU), `avconferenced` (101% CPU, a
   macOS video-conferencing daemon), `iTerm2` (93.9% CPU), `WindowServer` (59.8% CPU) — an active
   interactive/GUI session on this specific machine, not other agent lanes' pytest runs.
4. §4.1's 3 small runs (360 items, light footprint) executed successfully under these degraded
   conditions with correct pass/fail behavior, so the machine was not so far gone that nothing could
   run — but launching Phase 2's ~4000-item / up-to-10-way-parallel (`-n auto` on this 10-core M5)
   run against **375MB of free swap headroom**, where each worker is a fresh Python process
   importing this backend's full dependency chain (FastAPI, pydantic, asyncpg, langgraph, the
   RAG stack), was judged an unacceptable risk of either invalid numbers (swap-thrashing dominates
   wall time, defeating the point of measuring) or actually destabilizing what looks like Zero's own
   live interactive session on this machine — not a call to make unilaterally on a shared box with
   evidence of a real person's foreground work in progress.
5. **Redirect (orchestrator, mid-investigation)**: rather than wait indefinitely on a machine that is
   Zero's live interactive session by nature (M5 is the "dev workstation PRINCIPALE interattiva"),
   Phase 2 was moved to Pro — the fleet's designated H24 workhorse, explicitly provisioned for exactly
   this kind of batch/background load. Environment check confirmed viable before committing: repo at
   `/Users/nuzantara/nuzantara` (real directory, not symlink), venv present, `nuzantara_test`
   provisioned (`clients` table exists), 0 pytest processes, 14 cores. §4.2 above is the result.

This is a genuinely different failure mode than the mandate anticipated ("altre lane pushano") and
is called out explicitly rather than folded silently into "waiting for quiet" — the fix for #1
(pgrep flag) was real and is corrected everywhere in this investigation's own tooling, but it was
not, in the end, what stood between this doc and real Phase 2 numbers. What actually stood between
them was M5-specific memory pressure from Zero's own interactive session — resolved by moving the
measurement to the machine built for it, not by waiting for a human's foreground work to pause.

## 5. Verdict

**CONDITIONAL GO — safe and worth adopting, but not as a drop-in `-n auto` today. Two small, scoped
fixes are hard prerequisites (§6), not "would be nice."**

Pre-registered threshold (mandate step 3): GO if full-suite `-n auto` completes in < 8 min with 0 new
flakes across 2 runs. What actually happened doesn't map onto that threshold cleanly, and the honest
read is more useful than forcing a binary fit:

- **The core design (§3) is proven correct**, not just on a small subset (§4.1, 360 real-DB tests,
  3 configs, 0 failures) but at real scale under real concurrency (§4.2, ~4100 tests, `-n8` on Pro):
  every hazard the isolation hook was built to fix (§2.2-A/B, DELETE-race + DDL-lock) produced **zero
  failures** once isolated. It requires zero changes to the 4 conftest.py files or the ~56
  direct-connect files that already use the standard `DATABASE_URL`/`TEST_DATABASE_URL` convention.
- **Naive `-n auto`/`-n8` today is worse than "might flake" — it doesn't run at all.** §2.2-H is a
  100%-reproducible hard collection-abort, unrelated to DB isolation, that must be fixed first
  (one-line: `sorted(ALL_STATES)`). This is arguably the most important finding of the whole
  investigation: it means "just add `-n auto`" as a naive first step would have looked like total
  breakage with zero diagnosis in the commit history, not a flaky-test problem — exactly the kind of
  failure mode that would get xdist adoption reverted by whoever hit it first, for the wrong reason.
- **One real new flake was found, root-caused, and it's a coverage gap, not a design flaw** (§2.2-D2):
  2 files (`test_intake_writer.py`, `test_intake_review.py`) resolve their DB target from
  `INTAKE_TEST_DSN`, a name the isolation hook doesn't yet rewrite. Small, scoped, one extra env-var
  name to add.
- **Timing is real but modest, and doesn't extrapolate to a scored verdict on its own**: 147s → 127s
  (~14% faster) on a ~24%-by-count subset at `-n8` on a machine already carrying 88% swap from its own
  background load — encouraging directionally (serial time for this subset is already well inside the
  8-minute full-suite bar), but this is not the full 17,384-test suite, not `-n auto`, and not on an
  otherwise-idle machine, so it should not be read as "the suite will hit ~5 min." A clean full-suite
  `-n auto` run, once §6's two fixes land and on either an idle M5 or a lower-background-load Pro
  window, is the number that actually scores against the pre-registered threshold.

**Recommendation**: land §6's two fixes (both small, both outside `.husky/pre-push`, both safe for
any lane to pick up independently of the pre-push P1 work), then re-run the full-suite `-n auto`
timing as a fast follow-up — at that point the pre-registered threshold becomes directly measurable
for the first time. Tracked as a PENDING-ARMS line (below) rather than re-opening this investigation.
The structural verdict — **is per-worker DB isolation the right shape for this problem** — is
answered: yes, proven on both a small deliberately-adversarial subset and a large realistic one.

## 6. Design recommendation for pre-push adoption (if GO)

Not implemented here (a separate lane owns `.husky/pre-push` per this mandate — collision
avoidance). For that lane's reference:

**Hard prerequisites (block any `-n>1` adoption, both small and independent of the pre-push lane's
own P1 work — either could be picked up as its own tiny PR before or in parallel with pre-push
integration):**

0a. **Fix §2.2-H**: `backend/tests/services/crm/test_practice_state_machine.py:118` —
    `@pytest.mark.parametrize("state", list(ALL_STATES))` → `sorted(ALL_STATES)`. Without this, `-n>1`
    aborts at collection every time (100% reproducible, not a flake) the moment
    `services/crm/` is in scope. One line.
0b. **Fix §2.2-D2**: add `INTAKE_TEST_DSN` to the set of env vars the §3 hook rewrites (or simpler:
    rename the two call sites — `test_intake_writer.py:33`, `test_intake_review.py:32` — onto the
    standard `TEST_DATABASE_URL` convention, matching every other file in the suite and removing the
    special-cased fallback to `nuzantara_dev`, which the rest of the suite already treats as a guarded
    footgun — `backend/tests/conftest.py:31-34`). Two files, one env-var name.

**The isolation design itself (proven, §3-§4):**

1. Add `pytest-xdist` to `requirements-test.txt`, relock `requirements.lock.txt`.
2. Move the §3 `pytest_configure`/`pytest_unconfigure` pair into
   `apps/backend-rag/backend/tests/conftest.py` for real (currently reverted from this worktree).
3. Change the pre-push invocation's final line from
   `python -m pytest backend/tests/ --ignore=backend/tests/e2e --tb=short -q` to add
   `-n auto` (or a tuned fixed count — `sysctl -n hw.ncpu` on Apple Silicon dev boxes typically
   over-subscribes if paired with `-n auto`'s default of "all cores", worth an explicit ceiling
   given this repo's own finding that dev boxes routinely run 2-5 **other** concurrent pytest
   processes from sibling agent lanes, AND that even a dedicated workhorse (Pro) carries enough
   background load that this investigation itself deliberately capped at `-n8` of 14 available cores
   — see §4.2/§4.3 for direct evidence of this contention pattern recurring twice, on two different
   machines, during THIS investigation).
4. The existing `CLONE_DB="nuzantara_test_run_$$"` single clone (`.husky/pre-push` lines 97-143)
   stays exactly as-is — it becomes the TEMPLATE the new hook clones per-worker from, so this is a
   strictly additive layer, not a replacement of the existing per-push isolation.
5. Kill-switch: an env var (e.g. `PREPUSH_XDIST=0`) falling back to today's serial invocation,
   consistent with this repo's existing convention of loud, explicit escape hatches
   (`PREPUSH_FULL=1`, `PRE_PUSH_TEST_DB`) rather than silent behavior changes.
6. Guilt+innocence tests for the new hook itself, per W81/guard-conformance convention: guilt =
   two workers MUST land on different `current_database()` under `-n 2`; innocence = a `-n 0`
   (single-process, no xdist) run MUST be a complete no-op (env vars unchanged) — both cases
   verified manually in §3 above, should become a permanent regression test if adopted.
7. A collection-determinism guard is worth adding independent of §0a's fix landing: a cheap
   pre-flight (`pytest --collect-only -q` run twice with different `PYTHONHASHSEED`, diffed) would
   have caught §2.2-H's class of bug before it ever reached a real `-n auto` run.

## 7. Risks and residual concerns

- **This experiment ran on a busy, shared dev box** (multiple sibling agent lanes pushing
  concurrently — direct live evidence the spec's own P0 problem statement is real, not
  theoretical: this investigation itself had to queue behind 2-5 concurrent full-suite serial
  pytest runs from other lanes before a quiet window opened). Timings in §4 reflect whatever
  ambient load existed at run time (recorded per-row); GO/NO-GO should be re-validated on a truly
  idle machine or CI-equivalent hardware before this becomes a hard gate, since a false-NO-GO from
  ambient noise would kill a genuinely good design.
- **Fixed worker count vs `auto`**: `-n auto` on Apple Silicon defaults to physical core count;
  this repo's dev boxes are NOT dedicated CI runners (M5 = 24GB, "leggera — no daemon/cron/Ollama
  H24" per project CLAUDE.md, yet routinely runs 2-5 concurrent sibling pytest processes in
  practice per this investigation's own observations) — an unbounded `-n auto` in the adopted hook
  risks worse contention than today's serial-but-queued model on exactly the busy days this spec
  is trying to fix. The design in §6 explicitly flags this rather than assuming `-n auto` is free.
- **DDL lock contention (§2.2-B) is now physically impossible cross-worker** (separate databases),
  but two tests landing on the *same* worker via xdist's `--dist=load` scheduling still run
  sequentially on that worker's single DB — no new risk there, just restating §3's "per-worker not
  per-test" scope honestly.
- **This doc's fixture lived only in this worktree (and a matching worktree on Pro for §4.2)** and
  was reverted before commit on both (per mandate step 4 — doc + trial files only, no
  `.husky/pre-push` changes). A future adopter must re-implement it from §3's code block, not assume
  it exists on `main`.
- **"Wait for a quiet machine" doesn't scale as a research methodology on this fleet** — this
  investigation itself needed a mid-flight redirect from M5 to Pro because the anticipated hazard
  (sibling pytest lanes) and the actual hazard (Zero's own live interactive session eating swap) were
  different problems requiring different fixes. The general lesson for future measurement-heavy
  investigations on this fleet: check what KIND of "busy" a machine is (fleet contention vs.
  interactive human use) before choosing whether to wait it out or move the work to a dedicated
  workhorse — the two require opposite responses.
