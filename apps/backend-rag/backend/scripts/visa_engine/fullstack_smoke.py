"""Run the opt-in Visa Oracle browser-to-Postgres smoke on a disposable DB.

This is a local TEST-only harness.  It creates a uniquely named database on a
loopback PostgreSQL server, applies only the Visa Engine forward migrations,
activates the checked-in signed TEST RulePack, starts the light FastAPI process
and Next.js, runs the unmocked Playwright smoke, and drops the database in a
``finally`` block.

The runner intentionally cannot target an existing database.  Its generated
database name always starts with ``visa_oracle_smoke_`` and every destructive
operation re-validates that invariant.

Usage (from ``apps/backend-rag``)::

    VISA_ORACLE_FULLSTACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
      .venv/bin/python -m backend.scripts.visa_engine.fullstack_smoke

Override the local admin connection only when needed (for example Docker on
port 5433)::

    VISA_ORACLE_SMOKE_ADMIN_DSN=postgresql://test:test@127.0.0.1:5433/postgres
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import secrets
import signal
import socket
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from urllib.parse import ParseResult, urlparse, urlunparse

import asyncpg
import httpx

from backend.db.migration_base import split_migration_sql
from backend.scripts.visa_engine import activate_pack

logger = logging.getLogger("visa_engine.fullstack_smoke")

OPT_IN_ENV = "VISA_ORACLE_FULLSTACK"
ADMIN_DSN_ENV = "VISA_ORACLE_SMOKE_ADMIN_DSN"
DEFAULT_ADMIN_DSN = "postgresql://nuzantara@127.0.0.1:5432/postgres"
DATABASE_PREFIX = "visa_oracle_smoke_"
DATABASE_NAME_RE = re.compile(r"^visa_oracle_smoke_[a-z0-9_]{8,80}$")
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
MIGRATION_NUMBERS = (
    250,
    251,
    252,
    253,
    254,
    255,
    256,
    257,
    262,
    263,
    264,
    265,
    266,
    267,
    268,
)
TEST_RULE_PACK_ID = "8a57d996-c7f2-5abc-9c31-4128a29ed848"

# Public verification material for the checked-in TEST fixture.  This is an
# Ed25519 public key, not signing/HMAC secret material.  The private key remains
# outside the repo and is never needed by this smoke.
TEST_TRUST_STORE = (
    {
        "kid": "key-2026-07-test-1",
        "public_key": "hPwtyP1ekdj_n-BK4M97dyWnRxW1RJ-uGcnVsX5buHM",
        "environment": "TEST",
        "valid_from": "2026-07-19T00:00:00Z",
        "valid_to": None,
        "revoked_at": None,
    },
)
TEST_TRUST_STORE_JSON = json.dumps(TEST_TRUST_STORE, separators=(",", ":"))

POLICY_SQL = """
INSERT INTO public.visa_decision_retention_policies (
    environment, policy_version, retention_interval,
    idempotency_retention_interval, legal_hold_review_interval,
    retention_anchor,
    effective_period, approved_by, approval_reference
) VALUES (
    'TEST', 'zero-test-v1', INTERVAL '1 day', INTERVAL '1 hour', INTERVAL '30 days',
    'EVALUATED_AT', tstzrange(clock_timestamp() - INTERVAL '1 day', NULL, '[)'),
    'zero-test-approver', 'ZERO-RETENTION-TEST-APPROVAL'
)
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_safe_admin_dsn(raw_dsn: str) -> ParseResult:
    """Accept only a loopback PostgreSQL admin URL for database ``postgres``."""

    parsed = urlparse(raw_dsn)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("admin DSN must use the postgres/postgresql scheme")
    if parsed.hostname not in LOCAL_HOSTS:
        raise ValueError("admin DSN must target a loopback host")
    if parsed.path != "/postgres":
        raise ValueError("admin DSN must target the postgres maintenance database")
    if parsed.params or parsed.fragment:
        raise ValueError("admin DSN cannot contain params or a fragment")
    if parsed.query not in {"", "sslmode=disable"}:
        raise ValueError("admin DSN query may only be sslmode=disable")
    if not parsed.username:
        raise ValueError("admin DSN must include an explicit local database user")
    return parsed


def _asyncpg_dsn(parsed: ParseResult) -> str:
    """Strip the sole allowed sslmode query; local smoke never needs TLS."""

    return urlunparse(parsed._replace(query=""))


def _database_dsn(admin: ParseResult, database_name: str) -> str:
    _assert_disposable_database_name(database_name)
    return urlunparse(admin._replace(path=f"/{database_name}", query=""))


def _assert_disposable_database_name(database_name: str) -> None:
    if DATABASE_NAME_RE.fullmatch(database_name) is None:
        raise ValueError("refusing a database name outside the disposable smoke namespace")


def _new_database_name() -> str:
    name = f"{DATABASE_PREFIX}{os.getpid()}_{secrets.token_hex(6)}"
    _assert_disposable_database_name(name)
    return name


def _quote_generated_identifier(identifier: str) -> str:
    """Quote only an already-validated generated database identifier."""

    _assert_disposable_database_name(identifier)
    return f'"{identifier}"'


def _migration_paths(backend_root: Path) -> tuple[Path, ...]:
    migrations_dir = backend_root / "backend" / "db" / "migrations_v2"
    resolved: list[Path] = []
    for number in MIGRATION_NUMBERS:
        matches = sorted(migrations_dir.glob(f"{number}_*.sql"))
        if len(matches) != 1:
            raise RuntimeError(
                f"expected exactly one migration {number}, found {[path.name for path in matches]}"
            )
        resolved.append(matches[0])
    return tuple(resolved)


async def _create_database(admin_dsn: str, database_name: str) -> None:
    _assert_disposable_database_name(database_name)
    connection = await asyncpg.connect(admin_dsn)
    try:
        existing = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            database_name,
        )
        if existing is not None:
            raise RuntimeError("generated disposable database unexpectedly already exists")
        await connection.execute(f"CREATE DATABASE {_quote_generated_identifier(database_name)}")
    finally:
        await connection.close()


async def _drop_database(admin_dsn: str, database_name: str) -> None:
    """Drop only the database generated by this runner, closing its sessions."""

    _assert_disposable_database_name(database_name)
    connection = await asyncpg.connect(admin_dsn)
    try:
        await connection.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            database_name,
        )
        await connection.execute(
            f"DROP DATABASE IF EXISTS {_quote_generated_identifier(database_name)}"
        )
    finally:
        await connection.close()


async def _apply_forward_migrations(database_dsn: str, backend_root: Path) -> None:
    connection = await asyncpg.connect(database_dsn)
    try:
        for migration_path in _migration_paths(backend_root):
            sql_text = migration_path.read_text(encoding="utf-8")
            forward_sql, rollback_sql = split_migration_sql(sql_text)
            if not forward_sql.strip() or not rollback_sql:
                raise RuntimeError(
                    f"migration {migration_path.name} lacks a split forward/rollback"
                )
            async with connection.transaction():
                await connection.execute(forward_sql)
            logger.info("applied forward migration %s", migration_path.name)
    finally:
        await connection.close()


async def _insert_test_policy(database_dsn: str) -> None:
    connection = await asyncpg.connect(database_dsn)
    try:
        await connection.execute(POLICY_SQL)
    finally:
        await connection.close()


async def _activate_test_pack(database_dsn: str, backend_root: Path) -> None:
    env_name = "VISA_ORACLE_SMOKE_DATABASE_URL"
    previous_database_url = os.environ.get(env_name)
    previous_trust_store = os.environ.get("VISA_ENGINE_TRUST_STORE_KEYS_JSON")
    os.environ[env_name] = database_dsn
    os.environ["VISA_ENGINE_TRUST_STORE_KEYS_JSON"] = TEST_TRUST_STORE_JSON
    args = argparse.Namespace(
        signed_bundle=str(
            backend_root
            / "backend"
            / "services"
            / "visa_engine"
            / "contracts"
            / "packs"
            / "rulepack-test-c1-tourism.signed.json"
        ),
        actor="smoke.audit",
        reason="fullstack-test",
        current_sequence=0,
        current_payload_sha256=None,
        engine_version="1.0.0",
        pack_writer_database_url_env=env_name,
        activation_database_url_env=env_name,
        yes=True,
    )
    try:
        result = await activate_pack.run(args)
        if result != 0:
            raise RuntimeError(f"TEST RulePack activation failed with exit code {result}")
    finally:
        if previous_database_url is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = previous_database_url
        if previous_trust_store is None:
            os.environ.pop("VISA_ENGINE_TRUST_STORE_KEYS_JSON", None)
        else:
            os.environ["VISA_ENGINE_TRUST_STORE_KEYS_JSON"] = previous_trust_store


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _sanitized_child_env(overrides: Mapping[str, str]) -> dict[str, str]:
    """Build a child env without inheriting unrelated credentials."""

    allow = {
        "HOME",
        "LANG",
        "LC_ALL",
        "LOGNAME",
        "PATH",
        "SHELL",
        "TMPDIR",
        "USER",
    }
    child = {key: value for key, value in os.environ.items() if key in allow}
    child.update(overrides)
    return child


async def _start_process(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_path: Path,
) -> asyncio.subprocess.Process:
    log_handle = log_path.open("wb")
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            env=dict(env),
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_handle.close()
    return process


async def _stop_process(process: asyncio.subprocess.Process | None) -> None:
    if process is None or process.returncode is not None:
        return
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), timeout=10)
    except TimeoutError:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


async def _wait_for_http(url: str, process: asyncio.subprocess.Process, *, timeout: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    async with httpx.AsyncClient(timeout=2.0, follow_redirects=True) as client:
        while asyncio.get_running_loop().time() < deadline:
            if process.returncode is not None:
                raise RuntimeError(f"server exited before readiness: {process.returncode}")
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.25)
    raise TimeoutError(f"server did not become ready: {url}")


def _tail_log(path: Path, *, lines: int = 80) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "<log unavailable>"


async def _run_playwright(
    *,
    repo_root: Path,
    mouth_root: Path,
    frontend_port: int,
    database_dsn: str,
) -> int:
    env = _sanitized_child_env(
        {
            "PLAYWRIGHT_EXTERNAL_SERVER": "1",
            "PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{frontend_port}",
            OPT_IN_ENV: "1",
            "PLAYWRIGHT_HTML_OPEN": "never",
            "VISA_ORACLE_SMOKE_DATABASE_URL": database_dsn,
        }
    )
    process = await asyncio.create_subprocess_exec(
        str(repo_root / "node_modules" / ".bin" / "playwright"),
        "test",
        "-c",
        "playwright.config.ts",
        "--project=chromium",
        "--reporter=line",
        "--workers=1",
        "e2e/visa-oracle-fullstack.spec.ts",
        cwd=str(mouth_root),
        env=env,
        start_new_session=True,
    )
    try:
        return await asyncio.wait_for(process.wait(), timeout=120)
    finally:
        # A failed HTML reporter must never keep the runner alive or defer the
        # disposable-database teardown.
        await _stop_process(process)


async def run() -> int:
    if os.environ.get(OPT_IN_ENV) != "1":
        raise SystemExit(f"refusing to run unless {OPT_IN_ENV}=1")

    parsed_admin = _parse_safe_admin_dsn(os.environ.get(ADMIN_DSN_ENV, DEFAULT_ADMIN_DSN))
    admin_dsn = _asyncpg_dsn(parsed_admin)
    database_name = _new_database_name()
    database_dsn = _database_dsn(parsed_admin, database_name)
    backend_root = _backend_root()
    repo_root = _repo_root()
    mouth_root = repo_root / "apps" / "mouth"
    backend_port = _free_loopback_port()
    frontend_port = _free_loopback_port()
    backend_process: asyncio.subprocess.Process | None = None
    frontend_process: asyncio.subprocess.Process | None = None
    database_created = False

    with tempfile.TemporaryDirectory(prefix="visa-oracle-smoke-logs-") as temp_dir:
        backend_log = Path(temp_dir) / "backend.log"
        frontend_log = Path(temp_dir) / "frontend.log"
        try:
            await _create_database(admin_dsn, database_name)
            database_created = True
            await _apply_forward_migrations(database_dsn, backend_root)
            await _insert_test_policy(database_dsn)
            await _activate_test_pack(database_dsn, backend_root)

            backend_env = _sanitized_child_env(
                {
                    "DATABASE_URL": database_dsn,
                    "DISABLE_BACKGROUND_WORKERS": "1",
                    "ENVIRONMENT": "development",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": ".",
                    "RAG_PROXY_ENABLED": "false",
                    "REDIS_HOST": "127.0.0.1",
                    "REDIS_PORT": "1",
                    "SENTRY_DSN": "",
                    "VISA_ENGINE_EVALUATE_ENVIRONMENT": "TEST",
                    "VISA_ENGINE_EVALUATE_MODE": "ENFORCE",
                    "VISA_ENGINE_TRUST_STORE_KEYS_JSON": TEST_TRUST_STORE_JSON,
                    "WA_OUTBOX_SCHEDULER_ENABLED": "false",
                }
            )
            backend_process = await _start_process(
                (
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.app.main_api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(backend_port),
                ),
                cwd=backend_root,
                env=backend_env,
                log_path=backend_log,
            )
            await _wait_for_http(
                f"http://127.0.0.1:{backend_port}/health/ready",
                backend_process,
                timeout=60,
            )

            frontend_env = _sanitized_child_env(
                {
                    "NEXT_PUBLIC_HIDE_CELL_WIDGET": "1",
                    "NEXT_PUBLIC_HIDE_QUERY_DEVTOOLS": "1",
                    "NEXT_PUBLIC_VISA_ORACLE_MODE": "ENGINE",
                    "NUZANTARA_API_URL": f"http://127.0.0.1:{backend_port}",
                }
            )
            frontend_process = await _start_process(
                (
                    "npm",
                    "run",
                    "dev",
                    "--",
                    "--webpack",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    str(frontend_port),
                ),
                cwd=mouth_root,
                env=frontend_env,
                log_path=frontend_log,
            )
            await _wait_for_http(
                f"http://127.0.0.1:{frontend_port}/visa-oracle",
                frontend_process,
                timeout=180,
            )

            exit_code = await _run_playwright(
                repo_root=repo_root,
                mouth_root=mouth_root,
                frontend_port=frontend_port,
                database_dsn=database_dsn,
            )
            if exit_code != 0:
                raise RuntimeError(f"Playwright smoke failed with exit code {exit_code}")
            logger.info(
                "full-stack smoke passed with signed TEST RulePack %s",
                TEST_RULE_PACK_ID,
            )
            return 0
        except Exception:
            logger.error("backend log tail:\n%s", _tail_log(backend_log))
            logger.error("frontend log tail:\n%s", _tail_log(frontend_log))
            raise
        finally:
            await _stop_process(frontend_process)
            await _stop_process(backend_process)
            if database_created:
                await _drop_database(admin_dsn, database_name)
                logger.info("dropped disposable database %s", database_name)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
