"""
Root conftest for all backend tests.

Sets up environment variables and shared fixtures BEFORE any module is imported.
This prevents pydantic validation errors and real API key requirements.

Shared fixtures: mock_db_pool, mock_qdrant_client, mock_redis
"""

import asyncio
import os
import re
from unittest.mock import AsyncMock, MagicMock

# ============================================================================
# Environment Variables — must be set FIRST, before any import
# Covers: EmbeddingsGenerator, Settings validation, JWT, WhatsApp, Instagram
# ============================================================================

os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only-nuzantara")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
# Fail closed for integration tests that historically defaulted to
# ``nuzantara_dev``.  That database carries the live local Intake/WhatsApp
# queue on Pro, so a manual pytest run must never claim or rewrite its rows.
# CI and operators can still provide an explicit isolated DSN.
#
# 2026-07-28: this is a LIST, not one variable, because the guard used to know
# only about ``TEST_DATABASE_URL`` while three intake tests resolve their DSN
# from ``INTAKE_TEST_DSN`` — a door the guard could not see. CI (tests.yml) and
# the pre-push hook both export it at a safe target, so the exposure was the
# path neither of them covers: a bare manual ``pytest``, where the module-level
# fallback in those tests is literally ``.../nuzantara_dev``. A guard that
# watches one variable while the code reads another is the same shape as a
# scan surface that skips a file type (superscar #3, UNDER-match).
#
# ``scripts/tests/test_intake_dsn_guard_covers_every_var.py`` fails the build if
# a test module ever introduces a FOURTH variable without adding it here.
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)
# INTAKE_TEST_DSN follows TEST_DATABASE_URL rather than carrying its own
# literal: one knob to point the whole suite at an isolated database, and no
# second default that can drift away from the first.
os.environ.setdefault("INTAKE_TEST_DSN", os.environ["TEST_DATABASE_URL"])

TEST_DSN_ENV_VARS: tuple[str, ...] = ("TEST_DATABASE_URL", "INTAKE_TEST_DSN")
for _dsn_var in TEST_DSN_ENV_VARS:
    if os.environ[_dsn_var].split("?", 1)[0].rstrip("/").endswith("/nuzantara_dev"):
        raise RuntimeError(
            f"Refusing to run pytest against operational nuzantara_dev "
            f"({_dsn_var}); use nuzantara_test"
        )
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
# Unit tests run with localhost Qdrant while developer shells may export a
# different cloud QDRANT_URL; keep the production ingest guard explicit.
os.environ["LEGAL_INGEST_ALLOW_QDRANT_ENV_OVERRIDE"] = "1"
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
# FORCE-assign (not setdefault): the Pro dev/cron shell exports the REAL
# TELEGRAM_BOT_TOKEN (a GitHub secret used by all cron wrappers). With
# setdefault the real token survived into pytest, so every un-mocked Telegram
# sender — sentinel alerter (scripts/sentinel_lib/alerter.py), canva_renderer
# _telegram.send_telegram, email_audit.notify_email_failure_critical — fired
# REAL alerts to the owner chat (8847435604) during the test run (verbatim
# leaks: "OCR ... Context: unit.test.context", "WR2 rendered: Test / DAG123",
# "Invoice INV-2026-001 ... john@example.com"). Forcing the fake token makes
# those calls hit a non-existent bot (401, swallowed) — never the owner.
# Tests that genuinely exercise a sender still win via per-test monkeypatch.
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:test_token"
os.environ.setdefault("EMBEDDING_PROVIDER", "openai")
os.environ.setdefault("EMBEDDING_MODEL", "text-embedding-3-small")

# Some SDK import chains load `mcp.types`, which asks pydantic to create
# RootModel generics before `pydantic.root_model` has been registered in
# sys.modules on the local dev venv. Import it here before test modules pull
# portal/multimodal services through router imports.
import pydantic.root_model  # noqa: E402,F401

# ============================================================================
# Shared fixtures
# ============================================================================
import pytest  # noqa: E402 — must come after env setup


@pytest.fixture
def mock_db_pool():
    """Standard mock asyncpg connection pool.

    Supports: async with pool.acquire() as conn
              async with conn.transaction()  (no-op async context manager)
    Usage: pool, conn = mock_db_pool
    """
    pool = MagicMock()
    conn = MagicMock()

    class _AsyncCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    class _TransactionCtx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            return None

    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=_AsyncCtx())
    # conn.transaction() must return an async context manager, not a coroutine.
    # AsyncMock would make it a coroutine; use MagicMock returning _TransactionCtx.
    conn.transaction = MagicMock(return_value=_TransactionCtx())
    return pool, conn


@pytest.fixture
def mock_qdrant_client():
    """Standard mock Qdrant client."""
    client = AsyncMock()
    client.search = AsyncMock(return_value=[])
    client.upsert = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=None)
    client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    return client


@pytest.fixture(autouse=True)
def _wr2_runtime_isolation(tmp_path, monkeypatch):
    """Tests must NEVER touch the real WR2 runtime state (W96, 2026-07-13).

    Any test that reaches wr2_html_render_apply's visibility chain (or any
    other WR2 writer honoring WR2_OUTPUT_ROOT) without mocking it would land
    fixture entries in the PRODUCTION human-review-queue.json and spool real
    Telegram notifications — 24 phantom "micro carousels" reached the WR2
    Control app this way. Redirect both to tmp_path unconditionally; a test
    that needs its own root still wins by monkeypatching the env itself
    (test-body setenv runs after this autouse fixture).

    Same reasoning, added 2026-08-20: claude_vision.py's chain-wide rate-limit
    cooldown + no-op fingerprint cache default to ~/.agent/state/*.json — an
    unmocked test that trips a "rate-limited" path would otherwise write a
    REAL cooldown file that then blocks the PRODUCTION vision loop for up to
    WR2_VISION_COOLDOWN_S (default 1h), discovered live when the existing
    _run_claude_json test battery (rate-limit/timeout/rotation cases) started
    failing each other in file order via the shared default path.
    """
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "wr2-output"))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path / "tg-spool"))
    monkeypatch.setenv("WR2_VISION_COOLDOWN_STATE", str(tmp_path / "wr2-vision-cooldown.json"))
    monkeypatch.setenv(
        "WR2_VISION_FINGERPRINT_CACHE", str(tmp_path / "wr2-vision-fingerprints.json")
    )


@pytest.fixture
def mock_redis():
    """Standard mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.keys = AsyncMock(return_value=[])
    return redis


# ============================================================================
# Per-xdist-worker Postgres isolation (2026-08-21)
#
# WHY: #4477's c92ed801 had to drop `-n auto --dist loadfile` — every worker
# shared the ONE `nuzantara_test` Postgres, and a counting test observed a
# sibling worker's parallel writes (test_intake_review.py::
# test_approve_live_claim_owned_by_other_rejected_without_write read (4, 1)
# where serial reads (2, 0)). world-practice import map §1.3
# (research/operations/2026-08-21-world-patterns-import-map.md) names the
# fix: one throwaway Postgres database per xdist worker, cloned from a
# template via Postgres's own `CREATE DATABASE ... TEMPLATE` mechanism.
#
# WHY HERE, NOT A FIXTURE: several test modules read TEST_DATABASE_URL /
# INTAKE_TEST_DSN at MODULE level (e.g. test_migration_113.py's
# `TEST_DSN = os.environ.get("TEST_DATABASE_URL")`) — that read happens at
# IMPORT time, during collection. A fixture only runs after collection
# finishes and would be too late to change what those modules already
# captured. The clone + env-var override below therefore runs at THIS
# file's own IMPORT time (module-level code, not a `pytest_configure` hook
# — see the longer comment further down for why the hook is too late for
# some invocation shapes), which precedes every other conftest.py under
# `backend/tests/`. It is also import-cached per worker process, so this is
# a one-time setup, not a per-test cost.
#
# DESIGN CHOICE — clone from the ALREADY-migrated base DB itself, not a
# separate `test_template`: CI's "Bootstrap SQLModel tables" + "Apply
# database migrations" steps migrate `nuzantara_test` ONCE before pytest
# ever starts, and `.husky/pre-push` has done exactly this clone-from-base
# pattern in production since 2026-07-16 (`CLONE_DB=nuzantara_test_run_$$_
# $RANDOM`, `CREATE DATABASE … TEMPLATE nuzantara_test`) — reusing that
# instead of inventing a second template avoids re-running bootstrap+migrate
# here and inherits two lessons pre-push already paid for:
#   1. OWNER clause: a clone created by a role that is not the template's
#      owner silently loses CREATE on `public` (PG15 `public` is owned by
#      the pseudo-role pg_database_owner) — measured there as 39 failed +
#      79 errored of 17339 tests before the fix.
#   2. Defensive `DROP DATABASE IF EXISTS ... WITH (FORCE)` before CREATE —
#      idempotent recovery from a crashed prior run's leaked database, plus
#      a bounded retry for a transiently busy template.
# Deterministic naming (`<base>_gw{N}`, not PID+random) means a bounded
# number of possible leaked DBs (one per worker slot) that self-heals the
# very next run at that slot, rather than pre-push's unbounded PID space
# (its own #60 needed a random suffix to bound that).
#
# INNOCENCE (unchanged behaviour when xdist is inactive): PYTEST_XDIST_WORKER
# is pytest-xdist's own convention, set as an OS env var in the worker
# subprocess before any Python/pytest code runs — a serial run (`pytest ...`,
# no `-n`) never sets it, so `pytest_configure` below returns immediately:
# zero network calls, zero behaviour change.
# ============================================================================

_XDIST_WORKER_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]+_gw\d+$")
_XDIST_WORKER_ID_RE = re.compile(r"^gw(\d+)$")


def _xdist_split_admin_dsn(dsn: str) -> tuple[str, str]:
    """Return (admin_dsn pointing at the `postgres` maintenance db, base_db_name).

    Same string-split convention already used by
    ``backend/tests/services/visa_engine/test_write_substrate.py``'s
    ``_ADMIN_URL`` — kept consistent rather than reaching for urllib here.
    """
    base_part, sep, db_and_query = dsn.rpartition("/")
    db_name = db_and_query.split("?", 1)[0]
    if not sep or not db_name:
        raise RuntimeError(f"cannot parse a database name out of DSN {dsn!r}")
    return f"{base_part}/postgres", db_name


def _xdist_worker_db_name(base_db: str, worker_id: str) -> str:
    match = _XDIST_WORKER_ID_RE.match(worker_id)
    if not match:
        raise RuntimeError(
            f"unrecognized xdist worker id {worker_id!r} (expected 'gw<N>'); "
            "refusing to guess a per-worker database name"
        )
    name = f"{base_db}_gw{match.group(1)}"
    if not _XDIST_WORKER_DB_NAME_RE.fullmatch(name):
        # Guard by regex, not by prefix alone (cicatrix-superscar #3): a DROP
        # DATABASE below must never run against a name that didn't pass
        # this exact check.
        raise RuntimeError(f"refusing to operate on unsafe database name {name!r}")
    return name


def _xdist_swap_db(dsn: str, new_db: str) -> str:
    base_part, sep, db_and_query = dsn.rpartition("/")
    if not sep:
        raise RuntimeError(f"cannot parse a database name out of DSN {dsn!r}")
    _, _, query = db_and_query.partition("?")
    return f"{base_part}/{new_db}" + (f"?{query}" if query else "")


async def _xdist_clone_worker_database(admin_dsn: str, base_db: str, worker_db: str) -> None:
    import asyncpg  # lazy: only imported when actually running under xdist

    if not _XDIST_WORKER_DB_NAME_RE.fullmatch(worker_db):
        raise RuntimeError(f"refusing to operate on unsafe database name {worker_db!r}")

    conn = await asyncpg.connect(admin_dsn)
    try:
        owner_row = await conn.fetchrow(
            "SELECT pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname = $1",
            base_db,
        )
        owner = owner_row["owner"] if owner_row else None
        owner_clause = f' OWNER "{owner}"' if owner else ""

        # Defensive pre-drop: heals a database leaked by a crashed prior run
        # at this exact deterministic worker slot.
        await conn.execute(f'DROP DATABASE IF EXISTS "{worker_db}" WITH (FORCE)')

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                await conn.execute(
                    f'CREATE DATABASE "{worker_db}" TEMPLATE "{base_db}"{owner_clause}'
                )
                return
            except Exception as exc:  # noqa: BLE001 — bounded retry, re-raised below if exhausted
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(2)
        raise RuntimeError(
            f"could not CREATE DATABASE {worker_db!r} TEMPLATE {base_db!r} after 3 "
            "attempts (template busy, permissions, or Postgres under load)"
        ) from last_error
    finally:
        await conn.close()


async def _xdist_drop_worker_database(admin_dsn: str, worker_db: str) -> None:
    if not _XDIST_WORKER_DB_NAME_RE.fullmatch(worker_db):
        raise RuntimeError(f"refusing to operate on unsafe database name {worker_db!r}")
    import asyncpg

    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{worker_db}" WITH (FORCE)')
    finally:
        await conn.close()


# ----------------------------------------------------------------------------
# WHY MODULE LEVEL, NOT `pytest_configure` (corrected 2026-08-21, same day):
# an earlier version of this ran the clone + env-var override inside
# `pytest_configure(config)`. That worked for CI's exact invocation shape
# (bare `backend/tests/`) but SILENTLY fell back to the shared, un-isolated
# `nuzantara_test` — no error — for any narrower/deeper invocation, e.g.
# `pytest backend/tests/services/visa_engine/`. Root cause: pytest's initial
# conftest-discovery phase imports every conftest.py lying on the ancestor
# path from rootdir down to each given CLI argument BEFORE any
# `pytest_configure` hook fires. `services/visa_engine/conftest.py` reads
# TEST_DATABASE_URL at ITS OWN module level (`_DEFAULT_DB_URL = os.environ
# .get("TEST_DATABASE_URL", ...)`) — when an argument sits at or below that
# subdirectory, this early import phase captures the stale DSN before
# `pytest_configure` could ever override it. Reproduced empirically across
# three invocation shapes (explicit .py files under visa_engine/, the
# visa_engine/ directory itself, and the bare backend/tests/ top level —
# only the last one isolated correctly).
#
# Fix: run at IMPORT TIME of THIS file instead. `backend/tests/conftest.py`
# is the root of the whole `backend/tests/` ancestor tree, so pytest imports
# it FIRST, before any subdirectory conftest.py, for every CLI argument
# depth — there is no "too late" for code that runs here at module scope.
# ----------------------------------------------------------------------------

_xdist_admin_dsn: str | None = None
_xdist_worker_db: str | None = None

_xdist_worker_id = os.environ.get("PYTEST_XDIST_WORKER")
if _xdist_worker_id:
    # Fail LOUD, never silently fall back to the shared DB (a swallowed
    # exception here would reintroduce the exact flake this exists to kill,
    # invisibly — cicatrix-superscar #2, "esiste ≠ armato"). "Loud" means
    # legibly attributed, not opaque: an earlier version of this ran the
    # clone inside a `pytest_configure` HOOK rather than at module import
    # time — an unhandled exception there crashed pytest-xdist's own worker
    # teardown with `INTERNALERROR> KeyError: <WorkerController gwN>`, a
    # real bug in xdist's dsession.py that buries the actual Postgres error
    # under framework internals (reproduced empirically 2026-08-21 with a
    # missing DB role under `-n 2`). Raising at IMPORT time instead (this
    # module-level block) gets pytest's own `ConftestImportFailure`
    # wrapping for free — verified the same way: zero INTERNALERROR, a
    # single `ConftestImportFailure: InvalidAuthorizationSpecificationError:
    # role "..." does not exist`. The try/except below adds only an
    # actionable next step on top of that already-clean wrapping.
    try:
        _xdist_admin_dsn, _xdist_base_db = _xdist_split_admin_dsn(os.environ["TEST_DATABASE_URL"])
        _xdist_worker_db = _xdist_worker_db_name(_xdist_base_db, _xdist_worker_id)

        asyncio.run(_xdist_clone_worker_database(_xdist_admin_dsn, _xdist_base_db, _xdist_worker_db))
    except Exception as exc:
        raise RuntimeError(
            f"per-xdist-worker Postgres isolation failed for worker {_xdist_worker_id!r}: "
            f"{exc}. Fix TEST_DATABASE_URL/INTAKE_TEST_DSN to point at a reachable Postgres "
            "your role can CREATE DATABASE on, or run pytest without -n/--dist for a plain "
            "serial pass."
        ) from exc

    _xdist_worker_dsn = _xdist_swap_db(os.environ["TEST_DATABASE_URL"], _xdist_worker_db)
    os.environ["TEST_DATABASE_URL"] = _xdist_worker_dsn
    os.environ["INTAKE_TEST_DSN"] = _xdist_worker_dsn
    # Some steps (CI's "Run unit tests") export DATABASE_URL identically to
    # TEST_DATABASE_URL/INTAKE_TEST_DSN; keep the three in sync so a test
    # reading any one of them lands on this worker's own database.
    os.environ["DATABASE_URL"] = _xdist_worker_dsn


def pytest_configure(config: pytest.Config) -> None:
    """Register per-xdist-worker Postgres teardown.

    The clone + env-var override itself already happened above, at this
    file's IMPORT time — not here. This hook exists only because
    `config.add_cleanup` needs a live `config` object, which module-level
    code does not have. See the block above for why the override cannot
    live in this hook.
    """
    if _xdist_worker_db is None:
        return  # serial / non-xdist run — current behaviour, unchanged.
    admin_dsn = _xdist_admin_dsn
    worker_db = _xdist_worker_db
    config.add_cleanup(lambda: asyncio.run(_xdist_drop_worker_database(admin_dsn, worker_db)))
