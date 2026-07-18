---
date: 2026-07-17
domain: infra
client_case: none
adversarial_review: codex
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
  - apps/backend-rag/backend/tests/services/crm/partners/conftest.py
  - .husky/pre-push
  - .github/workflows/tests.yml
  - orchestrator mandate M1 (session-relayed, not a repo-tracked file — the
    scratchpad it originally lived in is gitignored/ephemeral by design; see
    §M1 restated verbatim in the opening paragraph below)
  - "adversarial review: gpt-5.6-sol via codex CLI, high effort, read-only
    sandbox, 2026-07-18 — full raw verdict in §8"
---

# M1 — Backend suite sharding investigation (pytest-xdist + per-worker DB isolation)

Mandate: `scratchpad/spec-push-pipeline-optimization-v2.md` §M1 ("Suite sharding/parallelization
(pytest-xdist) with isolated per-worker DB/resources... if the local suite drops to ~5 min, every
remaining full run cheapens"). This is an **investigation**, not an adoption PR — `.husky/pre-push`
is untouched (a separate lane owns P1/that file). Worktree: `.worktrees/research-m1-sharding-0717a`.

## 0. TL;DR verdict — COMPLETE (2026-07-18, revised post-adversarial-review — see §8)

**GO TO HARDENED PILOT — not "safe and ready," a promising design with two proof gaps and a
prototype that is not yet crash-safe.** An earlier draft of this doc called this "CONDITIONAL GO...
proven safe." A real adversarial review (§8, gpt-5.6-sol/Codex, read-only, REJECT verdict) correctly
caught that the evidence supports a narrower claim, on two fronts: (1) the single highest-risk hazard
this investigation set out to prove safe — §2.2-A's owner_cashout DELETE-race — was **never actually
exercised as a live pass/fail at either scale**, because `owner_weekly_cashout_rows`/`_weeks` are
absent from the test-DB template on *both* M5 and Pro (verified freshly against Pro's `nuzantara_test`
during the revision: `to_regclass('public.owner_weekly_cashout_rows')` → NULL); what's actually proven
is the isolation *mechanism* (§3's synthetic proof + the D2/H hazards it did catch live), not that
specific hazard under real concurrency. (2) The §3 hook is a working prototype, not hardened code —
it has real, enumerated gaps (§3 "Known gaps," expanded post-review) including no protection against
two concurrent pytest invocations colliding on the same `<db>_gwN` name, fail-open behavior if
`CREATE DATABASE` actually fails, incomplete cleanup coverage, and no crash/SIGKILL handling.

Per-worker Postgres isolation for pytest-xdist **is proven to work as a mechanism** at both small
scale (360 real-DB tests, 3 configs, 0 failures) and large scale (~4100 tests, `-n8` on Pro) — every
hazard it *did* get to exercise (§2.2-B/D2/H) came back clean or was root-caused to a scoped, fixable
gap, not a flaw in the core approach. Naive `-n auto`/`-n8` with no isolation and no prerequisite
fixes does **not** just flake — it hard-aborts at collection (§2.2-H, unrelated to DB isolation,
one-line fix). One real new flake was found at scale and root-caused to a coverage gap, not a design
flaw (§2.2-D2, two files, small fix — though see §8 on how rigorously "root-caused" should be read
here). Timing: 147s serial → 127s isolated `-n8` on the representative subset (~1.16×, ~13.6%
reduction) — real, but this does **not** extrapolate to the pre-registered full-suite threshold: naively
applying the same ~13.6% reduction to today's 11–32 min baseline gives ~9.5–27.6 min, which does **not**
clear the <8 min bar (§5 corrects an earlier version of this doc that read the subset's absolute wall
time, 147s, against the 8-minute threshold as if that were informative — it isn't, the subset is ~24%
of the suite by test count, of course it finishes under 8 minutes). Several small fixes (§6, expanded
in §8) are hard prerequisites before ANY `-n>1` adoption; a hardened re-run — full suite, `-n auto`,
2 consecutive green runs, on an idle machine, with raw logs kept — is the fast follow-up that actually
scores against the pre-registered threshold (PENDING-ARMS line, §5).

- Per-worker DB isolation (§3) is proven correct **as a mechanism** on a subset that actually touches
  Postgres (`backend/tests/db/` + `backend/tests/services/hr/`, 360 collected items): 0 real test
  failures across 3 configurations (serial / naive `-n4` / isolated `-n4`), clean teardown verified
  after each run (zero orphan `nuzantara_test_gw*` databases) — **and again at ~4100-test scale on
  Pro** (§4.2), where it also caught 2 real hazards static analysis alone had missed. It was **not**
  proven against the specific DELETE-race hazard (§2.2-A) it was originally built to fix, because
  that hazard's tests self-skip on both machines used (missing template tables) — see above and §4.1.
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
pattern — and it is a **hard prerequisite** for xdist adoption. Workaround used to get past it for
measurement purposes in §4.3: `PYTHONHASHSEED=0` (pins the hash seed so all workers agree) — a
standard, well-known mitigation, applied here only to unblock measurement, not proposed as the
adoption fix (sorting the source is the real fix; §6).

**Precision correction (§8 revision)**: earlier drafts of this section said "every run"/"100%" —
overstated for what was actually verified. What's confirmed: (a) the mechanism (CPython's
per-process hash-randomization of `frozenset` iteration order, PEP 456, is standard documented
behavior, not a hypothesis) and (b) one live, directly-observed collection abort at Phase 2 scale.
What's *not* confirmed: repeated runs across multiple distinct `PYTHONHASHSEED` values to show the
failure rate really is ~100% rather than merely likely (two different seeds can coincidentally
produce the same iteration order for a small `frozenset`, so "100% of runs" is an inference from the
mechanism, not an N-trial measurement). The fix (`sorted(...)`) is correct regardless of the exact
failure rate. Separately, `PYTHONHASHSEED=0` unblocks *this* case but does not prove no *other*
non-deterministic parametrize source exists elsewhere in the 17,384-test suite — §2.2's own sweep
for the same signature covered only the `parametrize.*list(.*frozenset|set(` pattern textually, which
is a grep, not an exhaustive semantic check.

**I. FOUND POST-REVIEW — a fixed-name, function-scoped DDL hazard missed by the original recon
(§8 caught this; the original §2.2 grep pass didn't cover this file's pattern).**
`backend/tests/services/crm/partners/conftest.py:359-386` — the `db_conn` fixture is
**function-scoped** (`@pytest_asyncio.fixture(scope="function")`) and on **every single test** that
uses it runs `_TEARDOWN_SQL` (`DROP TABLE IF EXISTS partner_email_outbox/partner_audit_log/
partner_commissions/partner_referrals/partners` — lines 333-338) then `_SCHEMA_SQL`
(`CREATE TABLE IF NOT EXISTS` the same 5 tables — lines 176-312) at setup, and `_TEARDOWN_SQL` again
at teardown (line 375) — resolving its DB target from `TEST_DATABASE_URL` with a fallback to
`nuzantara_dev` (line 122-125, same convention as §2.2-C). This is a **higher-frequency** version of
the §2.2-B hazard shape (ACCESS EXCLUSIVE lock on `DROP`/`CREATE TABLE`): B's migration tests DDL
once per test *file*; this one DDLs on every test *function* that touches `backend/tests/services/crm/
partners/`. Under the §3 isolation hook this is fixed for free (each worker gets its own DB, so the
DROP/CREATE churn no longer touches a database any other worker can see) — it does not change the
verdict, but it is a real gap in §2.2's original inventory, found by the adversarial reviewer reading
files this investigation's grep patterns didn't surface, not by re-running anything. Not exercised as
a live collision in either Phase (single-worker in Phase 1's scope, and Phase 2's isolated `-n8` run
means it never got the chance to collide against another worker) — flagged here as an inventory
correction, not a new observed failure.

**Net read**: the entire hazard surface for this suite is Postgres, concentrated in ~5-7 files with
un-namespaced writes to shared tables (2 of which, §D2, were missed by static grep and only found by
actually running Phase 2; one more, §I, was missed by grep and only found by the adversarial review
reading source directly), plus one collection-order hard-blocker (§H) that must be fixed before ANY
`-n>1` run can even start, plus a structural pattern (single `TEST_DATABASE_URL` for
the whole `-n auto` invocation) that would make even the "safe" 56/69 direct-connect files and the
4 `db_tx` conftests collide under naive parallelization even though none of them are individually
buggy — they were only ever exercised one-at-a-time. Given §I turned up from a single reviewer's
read-through rather than an exhaustive repo-wide `CREATE TABLE`/`DROP TABLE` grep, treat this
inventory as **probably still incomplete**, not closed — §6/§8 add a pre-adoption exhaustive DDL
sweep as a new hard step for exactly this reason.

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

**Additional gaps surfaced by adversarial review (§8) — real, concrete, verified against the code
block above, not yet fixed. These are why §0/§5 read "hardened pilot," not "ready":**

- **No protection against two concurrent pytest invocations.** Worker DB names are only
  `<dbname>_<worker>` (e.g. `nuzantara_test_gw0`) — no run-scoped identifier. Two separate `pytest
  -n N` invocations running at the same time (two developers, two CI jobs, two agent lanes) will both
  try to own `nuzantara_test_gw0` and can destroy each other's data mid-run. `.husky/pre-push`'s own
  existing single-clone mechanism already solved exactly this problem for the *serial* case
  (`CLONE_DB="nuzantara_test_run_$$"`, PID-scoped); this prototype's per-worker layer needs the same
  run-scoping, not just worker-scoping, before it can sit on top of concurrent invocations safely.
- **Double-`CREATE DATABASE` is silently swallowed, and that hides real failures.** When
  `DATABASE_URL` and `TEST_DATABASE_URL` point at the same database (the common case), the loop
  processes both env vars, so the second `CREATE DATABASE` always errors (already exists) — masked by
  `ON_ERROR_STOP=0` and no `check=True`. That's cosmetically harmless *when the first CREATE
  succeeded*, but it means a *real* clone failure on the first pass is swallowed identically, and the
  env var still gets rewritten to point at a database that was never actually created — fail-open,
  not fail-closed.
- **`pytest_unconfigure` only ever drops the `TEST_DATABASE_URL`-derived database.** If
  `DATABASE_URL` and `TEST_DATABASE_URL` resolve to two different worker DBs (or `TEST_DATABASE_URL`
  is unset), the `DATABASE_URL` worker DB is never dropped — an orphan-DB leak the §4.1/§4.2
  "zero rows after teardown" check didn't catch only because both env vars happened to be identical
  in every run actually performed here.
- **DSN query parameters are dropped**, not round-tripped: `dbname.split("?", 1)[0]` strips
  `?sslmode=...`-style params and the rewritten URL never restores them. Harmless for this
  investigation's local trust-auth Postgres; a real gap if adopted against any DSN carrying connection
  params.
- **No crash/interruption handling.** `pytest_unconfigure` only runs on a normal session end.
  `SIGKILL`, a controller crash, or a killed machine leaves the worker DB orphaned — needs either a
  periodic sweep (`DROP DATABASE ... WHERE datname LIKE '%_gw%' AND age > N`) or a run-id registry,
  neither of which exists yet.
- **Postgres identifier length (63 chars, `NAMEDATALEN`) and connection/disk ceilings are unchecked.**
  Low-probability at this repo's current naming lengths, but a real hardening gap for a `<base>_run_
  <pid>_<worker>`-style name once run-scoping (above) is added.
- **Owner/role is not explicitly preserved** on the cloned database, unlike `.husky/pre-push`'s
  existing clone step, which does handle this deliberately.

None of this invalidates the core mechanism (§4 still shows it working correctly for the concurrency
shape actually tested: one invocation, N workers, one machine) — it means the reference block above is
accurately described as a **prototype that proved the concept**, not adoption-ready code, and §6's
"move it into `conftest.py` for real" step needs these gaps closed first, not just the two hazard
fixes originally listed.

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
**Checked, not assumed, during the §8 revision**: this gap is not M5-specific. Freshly queried against
Pro's `nuzantara_test` (the DB Phase 2, §4.2, actually ran against): `SELECT to_regclass('public.
owner_weekly_cashout_rows')` and the `_weeks` sibling both return NULL — the tables are absent there
too. This means §2.2-A, the hazard with the strongest file:line case for "will actually flake," was
**never exercised as a live pass/fail at either scale of this investigation** — only the synthetic
proof in §3 (a throwaway test explicitly designed to prove the isolation *mechanism*, not this
specific hazard) stands in for it. This is the single largest gap between what §0/§5 originally
claimed ("proven safe... every targeted hazard clean") and what was actually shown, and is the main
reason the verdict reads "hardened pilot" rather than "safe to adopt" after review (§8).
Wall-time itself is **inconclusive** at this scale/under this noise: naive `-n4` (41s) was slower
than serial (28s) — consistent with per-worker interpreter/import startup cost dominating at only
360 tests, especially under 96% swap — while isolated `-n4` (16s) was fastest, plausibly warm-cache
from immediately following run 2. None of these 3 numbers should be read as a scaling signal; see
§4.3.

Orphan-DB check after all 3 runs: `SELECT datname FROM pg_database WHERE datname LIKE
'nuzantara_test_gw%'` → zero rows. Teardown is clean under real (not just synthetic) test content
too, not only the throwaway proof test from §3.

### 4.2 Phase 2 — full ~3.9k-subset timed comparison (DONE, executed on Pro — see §4.2.1)

> Corrected in §8 revision: this heading previously still read "design, not yet executed," left
> over from the draft written before Phase 2 ran and never updated once §4.2.1's real numbers landed
> below — a genuine editing bug, caught by the adversarial reviewer, not a re-run.

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
production-adjacent machine for a research measurement.

**Correction (§8 revision): the serial number (147s) being "under 8 minutes" is not informative and
an earlier draft of this section implied otherwise.** 147s is the wall time for ~24% of the suite by
test count, not the full 17,384 — of course a quarter of the suite finishes inside the full-suite
budget; that comparison proves nothing about whether the *full* suite will. The number that actually
matters is the *reduction ratio* (147s→127s, ~13.6%) extrapolated onto the real 11–32 min serial
baseline: **~9.5–27.6 min, which does not clear the pre-registered <8 min bar.** This is a naive
linear extrapolation (parallel efficiency measured here was only ~14.5% at `-n8` — see §8 — so even
this extrapolation is likely optimistic, not pessimistic), presented not as a prediction but as the
honest reason §5's verdict does not claim the threshold is met. See §5 for the full accounting.

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
   being blocked`. Explained at the source-code level, not guessed from symptoms: this file's `pool`
   fixture resolves its DSN from `INTAKE_TEST_DSN`, an env var the §3 hook never rewrites (it only
   targets `DATABASE_URL`/`TEST_DATABASE_URL`), defaulting to the shared, un-namespaced
   `nuzantara_dev` — so under `-n8`, up to 8 workers could concurrently touch the exact same physical
   tables this test snapshots before/after. **Precision correction (§8 revision)**: "root-caused" is
   accurate for the *code-level* explanation (the env-var mismatch is real and directly readable in
   both files, not inferred) but the *evidence tying it to this specific failure* is a full-table
   `COUNT` comparison plus a contamination check (below), not a controlled A/B replication (same test,
   run twice, once with `INTAKE_TEST_DSN` isolated and once not, to directly observe the failure
   appear/disappear). Other explanations — a different concurrent worker on the same shared DB, an
   external process, incomplete cleanup from a prior run — were not individually excluded by
   experiment, only made implausible by the code-level match (the exact env-var name the test reads is
   provably un-rewritten, which is a strong but not airtight case). This is **not a flaw in the
   isolation mechanism** (§3's env-var-rewrite approach is proven correct for everything using the
   `DATABASE_URL`/`TEST_DATABASE_URL` convention, including the harder DDL/DELETE cases in §2.2-B) —
   it's a **coverage gap**: one more env var name needed in the rewrite list, or these 2 files renamed
   onto the standard convention (§6/§8 recommend the rename over adding a third alias, since a third
   alias just moves the same footgun). Fix is small and scoped (§6, tracked in PENDING-ARMS); the A/B
   replication is worth doing when that fix lands, both to close this gap and to double as the
   regression test for it.

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

**GO TO HARDENED PILOT — not a plain GO, and not a REJECT of the approach either.** (Revised in the
§8 post-adversarial-review pass — an earlier draft of this section called this "CONDITIONAL GO...
safe and worth adopting." A real red-team review, §8, REJECTed that framing as exceeding the evidence,
and on re-reading its 5 points against the doc's own data, most of them are correct. This section now
says what the evidence actually supports.)

Pre-registered threshold (mandate step 3): GO if full-suite `-n auto` completes in < 8 min with 0 new
flakes across 2 runs. **That threshold was not met, and was not close to being tested** — the honest
accounting:

- **The core design (§3) is proven correct as a mechanism**, not just on a small subset (§4.1, 360
  real-DB tests, 3 configs, 0 failures) but at real scale under real concurrency (§4.2, ~4100 tests,
  `-n8` on Pro): every hazard it actually got to exercise (§2.2-B DDL-lock, §2.2-D2, §2.2-H) came back
  either clean or root-caused to a small, scoped, external-to-the-design gap. It requires zero changes
  to the 4 conftest.py files or the ~56 direct-connect files that already use the standard
  `DATABASE_URL`/`TEST_DATABASE_URL` convention. **It was not proven against §2.2-A specifically** —
  the DELETE-race hazard with the strongest file:line case in the whole doc — because
  `owner_weekly_cashout_rows`/`_weeks` are absent from the test-DB template on both M5 and Pro
  (verified fresh against Pro during this revision), so those tests self-skip everywhere this
  investigation ran. The synthetic proof in §3 shows the isolation *mechanism* works; it does not
  substitute for actually watching this specific hazard fail-then-not-fail.
- **The §3 prototype itself has real, unfixed hardening gaps** (expanded list in §3): no protection
  against two concurrent pytest invocations colliding on the same worker-DB name, fail-open behavior
  if `CREATE DATABASE` actually fails, incomplete `pytest_unconfigure` coverage (only drops the
  `TEST_DATABASE_URL`-derived DB), dropped DSN query parameters, no crash/SIGKILL cleanup. None of
  these were exercised by anything this investigation actually ran (single invocation, no crashes,
  identical `DATABASE_URL`/`TEST_DATABASE_URL` in every test) — they are real gaps between "proven to
  work in the shape tested" and "safe to adopt."
- **Naive `-n auto`/`-n8` today is worse than "might flake" — it doesn't run at all.** §2.2-H is a
  reproducible hard collection-abort, unrelated to DB isolation, that must be fixed first (one-line:
  `sorted(ALL_STATES)`) — confirmed mechanism + one live reproduction, not confirmed as literally
  100% of runs across multiple hash seeds (§2.2-H precision correction). This is arguably the most
  important finding of the whole investigation regardless of the exact failure rate: "just add
  `-n auto`" as a naive first step would have looked like total breakage with zero diagnosis in the
  commit history, not a flaky-test problem — exactly the kind of failure mode that gets xdist adoption
  reverted by whoever hits it first, for the wrong reason.
- **One real new flake was found and explained at the code level** (§2.2-D2): 2 files
  (`test_intake_writer.py`, `test_intake_review.py`) resolve their DB target from `INTAKE_TEST_DSN`, a
  name the isolation hook doesn't yet rewrite — the explanation is a direct code-read, not a
  controlled A/B replication (§4.2.2 precision correction). Small, scoped fix either way.
- **A newly found DDL hazard (§2.2-I) was never exercised as a collision** — `partners/conftest.py`'s
  function-scoped `DROP`/`CREATE TABLE` churn, found by the adversarial reviewer reading source, not
  by re-running anything. It's covered "for free" by the isolation design if adopted, but its
  existence means §2.2's inventory is probably still incomplete — see §6's new sweep step.
- **Timing does not clear the threshold, even optimistically.** 147s → 127s (~1.16×, ~13.6%
  reduction) on a ~24%-by-count subset at `-n8` on a machine already carrying 88% swap from its own
  background load. Naively extrapolating that same reduction onto the real 11–32 min serial baseline
  gives **~9.5–27.6 min — not under 8 min.** Measured parallel efficiency at `-n8` was only ~14.5%
  (recalculated independently by the adversarial reviewer, matching this doc's own arithmetic), meaning
  most of the theoretical 8× from 8 workers was eaten by isolation overhead and Pro's own background
  load — a real, unfavorable signal for how much headroom this design has on a busy shared machine, not
  just a footnote. Single sample per configuration, non-randomized run order (second run could carry
  warm-cache advantage), no `n4`/`-n auto` comparison, no repeated trials for variance — all real
  limitations on how much this timing number should be trusted (§8).

**Recommendation**: this is not "ship it" and not "abandon it" — it's "the concept is validated, the
implementation and the proof are both one tier short of adoption-ready." Before any `-n>1` change to
`.husky/pre-push` (a separate lane's decision to make): (1) land §6/§8's prerequisite fixes — the
2 original ones (§2.2-H sort, §2.2-D2 env var) plus the concurrency/crash-safety hardening §3 now
lists explicitly; (2) provision `owner_cashout` tables into the test-DB template (or otherwise force
§2.2-A to actually run) so the hazard with the strongest case gets a real pass/fail, not a skip; (3) do
an exhaustive DDL/DML shared-state sweep, not another single-reviewer read, given §2.2-I was found by
one person reading source and probably isn't the last one; (4) re-run full-suite `-n auto`, 2
consecutive green runs, on an idle machine, with raw logs/JUnit output committed or archived so the
result is auditable — that is the number that actually scores against the pre-registered threshold,
and it does not exist yet. Tracked as a PENDING-ARMS line (below) rather than re-opening this
investigation now. The structural question — **is per-worker DB isolation the right shape for this
problem** — reads as yes, the mechanism works cleanly everywhere it was actually exercised; the
adoption question — **is this specific prototype, on this evidence, safe to ship** — is not yet.

## 6. Design recommendation for pre-push adoption (if GO)

Not implemented here (a separate lane owns `.husky/pre-push` per this mandate — collision
avoidance). For that lane's reference:

**Hard prerequisites (block any `-n>1` adoption, both small and independent of the pre-push lane's
own P1 work — either could be picked up as its own tiny PR before or in parallel with pre-push
integration):**

0a. **Fix §2.2-H**: `backend/tests/services/crm/test_practice_state_machine.py:118` —
    `@pytest.mark.parametrize("state", list(ALL_STATES))` → `sorted(ALL_STATES)`. Without this, `-n>1`
    reproducibly aborts at collection the moment `services/crm/` is in scope. One line.
0b. **Fix §2.2-D2**: add `INTAKE_TEST_DSN` to the set of env vars the §3 hook rewrites (or simpler:
    rename the two call sites — `test_intake_writer.py:33`, `test_intake_review.py:32` — onto the
    standard `TEST_DATABASE_URL` convention, matching every other file in the suite and removing the
    special-cased fallback to `nuzantara_dev`, which the rest of the suite already treats as a guarded
    footgun — `backend/tests/conftest.py:31-34`). Two files, one env-var name. Prefer the rename over
    adding a third alias — a third alias just relocates the same footgun (§8).
0c. **NEW (§8): harden §3's prototype before it moves into real `conftest.py`** — run-scoped (not just
    worker-scoped) database names to survive concurrent invocations, `check=True`/explicit
    post-creation verification instead of `ON_ERROR_STOP=0`-and-ignore, `pytest_unconfigure` coverage
    for both `DATABASE_URL`- and `TEST_DATABASE_URL`-derived DBs independently, DSN query-parameter
    preservation, and either a crash-sweep cron or a run-id registry for orphan cleanup after
    SIGKILL/crash. Full list in §3's "Additional gaps" block.
0d. **NEW (§8): provision `owner_weekly_cashout_rows`/`_weeks` into the test-DB template** (or
    otherwise force §2.2-A's tests to actually run instead of self-skip) before claiming this design
    is proven against the DELETE-race hazard it was originally built to fix — it has not yet been
    exercised as a live pass/fail anywhere.
0e. **NEW (§8): run one more exhaustive DDL/shared-state sweep** (grep for `CREATE TABLE`/`DROP TABLE`
    /`TRUNCATE` repo-wide against `backend/tests/`, not file-by-file inspection) before treating §2.2's
    inventory as closed — §2.2-I (`partners/conftest.py`) was found by one adversarial reviewer reading
    source, not by this investigation's own recon, which is a signal the inventory undercounts.

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
   verified manually in §3 above, should become a permanent regression test if adopted. **NEW (§8):
   add a third, negative case** — inject a `CREATE DATABASE` failure (e.g. point `admin_url` at a
   role without `CREATEDB`) and assert the *session aborts*, not "silently falls through to the
   original shared DB and runs anyway." This is the direct regression test for the fail-open gap in
   §3's "Additional gaps."
7. A collection-determinism guard is worth adding independent of §0a's fix landing: a cheap
   pre-flight (`pytest --collect-only -q` run twice with different `PYTHONHASHSEED`, diffed) would
   have caught §2.2-H's class of bug before it ever reached a real `-n auto` run.
8. **NEW (§8): keep raw evidence.** This investigation's Phase 1/2 numbers are reported as summary
   pass/fail/wall-time only — no JUnit XML, no raw pytest output, no per-worker test distribution was
   archived. A hardened pilot run should commit or archive these (e.g. `--junitxml`) so the eventual
   full-suite `-n auto` result is independently auditable from the repo, not just asserted in prose.

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

## Adversarial review (§8)

**Reviewer**: `gpt-5.6-sol` via the `codex` CLI, `model_reasoning_effort=high`, `--sandbox read-only`,
2026-07-18. Dispatched as a genuine red-team pass on the finished draft (the version that still said
"CONDITIONAL GO... proven safe") — the reviewer read the doc directly off disk (not fed a summary) and
was asked for a structured critique across 5 attack surfaces plus a one-line verdict: CONCUR /
CONCUR-WITH-CAVEATS / REJECT.

**Verdict returned: REJECT** — of the *verdict framing*, not of the underlying design. The reviewer's
own summary line: *"Il verdetto `CONDITIONAL GO` non supera il red-team gate. L'indagine giustifica un
'GO a un pilot più rigoroso', non l'adozione della soluzione come sicura."*

### What it found, and what changed in response

1. **`CONDITIONAL GO` exceeds the evidence.** The owner_cashout tests (§2.2-A, the strongest
   file:line case in the doc) were skipped, not run, at the only scale where they mattered; the
   pre-registered full-suite/`-n auto`/2-runs/0-flakes criterion was never attempted; the §3 synthetic
   proof shows nominal DSN separation, not safety under concurrent invocations, creation failures, or
   interruption. **Accepted in full.** Verdict retitled "GO TO HARDENED PILOT" (§0/§5); the
   owner_cashout skip-on-both-machines gap is now stated explicitly and verified fresh against Pro
   during this revision (`to_regclass('public.owner_weekly_cashout_rows')` → NULL).
2. **The DB design has concrete holes**: no run-scoping (only worker-scoping) so concurrent
   invocations can collide; double-`CREATE DATABASE` fail-open when `DATABASE_URL`==`TEST_DATABASE_URL`;
   `pytest_unconfigure` only ever drops the `TEST_DATABASE_URL`-derived DB; dropped DSN query params;
   no owner preservation; no crash/SIGKILL cleanup; unchecked 63-char identifier ceiling. **Accepted in
   full** — every point checked directly against the §3 code block and confirmed real, not just
   plausible. Written up as "Additional gaps surfaced by adversarial review" in §3, promoted to hard
   prerequisites 0c-0e in §6.
3. **The two root causes have different evidence strength.** Frozenset/hash-seed (§2.2-H): mechanism
   correct, but "every run"/"100%" wasn't shown across multiple seeds, only inferred from one
   reproduction + the documented PEP 456 mechanism. `INTAKE_TEST_DSN` (§2.2-D2): a plausible,
   code-level explanation, not a controlled A/B replication — full-table counts don't rule out other
   writers. **Accepted, precision-corrected** in §2.2-H and §4.2.2 without discarding either finding
   (the fixes recommended for both are unaffected by this correction).
4. **`147s → 127s` was doing too much rhetorical work.** Single sample per configuration, non-random
   order, degraded machine (load 7-11, 88% swap), only ~14.5% parallel efficiency at `-n8`, a non-green
   parallel run, only 24% of the suite, no `n4`/`-n auto` comparison — and reading "subset serial time
   is already under 8 minutes" as reassuring is actually irrelevant (of course a 24%-by-count subset
   is fast); a naive extrapolation of the observed ~13.6% reduction onto the real 11-32 min baseline
   lands at ~9.5-27.6 min, **not** under the 8-minute bar. **Accepted in full** — this is the most
   consequential single correction in this revision; §4.2.1/§5 now state the extrapolation explicitly
   and the verdict no longer implies the threshold is close to being met.
5. **Other gaps**: `partners/conftest.py`'s function-scoped DDL churn wasn't inventoried in §2.2 —
   confirmed real by direct inspection during this revision, added as §2.2-I. No raw logs/JUnit/exact
   commands were archived — acknowledged as a real reproducibility gap (§6 point 8, new), not backfilled
   after the fact (fabricating logs post-hoc would be worse than admitting they weren't kept).
   §4.2's own heading still read "not yet executed" after Phase 2 had already run — a real leftover
   editing bug, fixed. `pytest-xdist` pinning: already flagged as an investigation-only, non-pinned
   install in §2.1 before this review, not a new gap. A negative test (DB-creation-failure must abort
   the session, not silently continue) was missing from §6's guilt+innocence list — added as a third
   case.

### Where this doc did not simply defer to the reviewer

The reviewer's own numerical spot-check (independently recomputed from the same 147s/127s pair: `speedup=1.1575x reduction=13.61% parallel_efficiency_at_8=14.47%`) matches this doc's arithmetic, which is why point 4 was accepted outright rather than argued. Point 3's push on evidentiary rigor was accepted as a *precision correction* to the wording, not a retraction of either finding — the frozenset mechanism and the INTAKE_TEST_DSN env-var mismatch are both still correct as stated in the source code; what changed is not overstating how many independent trials confirm them. No point in the reviewer's critique was rejected outright — on review, all 5 were substantively fair reads of the doc as it stood before this pass. That is itself worth stating plainly: the R1 gate's purpose is a real check, not a formality, and it worked as designed here.
