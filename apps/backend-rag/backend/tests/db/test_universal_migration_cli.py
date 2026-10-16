"""Unit behaviour of the migration CLI contract (`backend/db/migrate.py`).

No database here: a fake manager stands in for `MigrationManager` so these
tests pin the OUTPUT CONTRACT the deploy workflow and an operator rely on --
the counted `   - Migration ` line, the `✅ Applied: N migrations` line, the
`Summary:` line with `refused=`, exit codes, refusal diagnostics -- and the
fail-closed REPORTING BOUNDARY: no exception text, no server DETAIL, no DSN,
no token-shaped string, no traceback on stdout, on stderr or in the log
stream, with or without `--verbose`. The real-engine behaviour (ledgers,
atomicity, concurrency, rollback, lock-busy) lives in
`test_universal_migration_cli_pg.py`.

Why a fake and not `mock_db_pool`: the CLI never touches a pool; its only
collaborator is the manager's method surface, which is what the fake mirrors.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import Mock

import pytest

from backend.db import migrate
from backend.db.migration_base import MigrationError
from backend.db.migration_manager import MigrationManager

pytestmark = pytest.mark.unit

COUNTED = migrate.APPLIED_LINE_PREFIX  # "   - Migration "

#: Synthetic sensitive sentinels. One is free text, one is server-detail
#: shaped, one is IDENTIFIER-SHAPED (a token looks like an identifier, so a
#: shape-based allowlist would let it through -- root review, attempt 2).
SENTINEL_FIRST_LINE = "SENTINEL-FIRST-LINE-9f3a email=someone@example.test"
SENTINEL_DETAIL = "SENTINEL-DETAIL-7c21 Key (email)=(someone@example.test)"
SENTINEL_TOKEN = "synthetic_sensitive_token_9f3a2b"
SENTINEL_QUERY = "SELECT passport_number FROM clients"
SENTINELS = (
    SENTINEL_FIRST_LINE,
    SENTINEL_DETAIL,
    SENTINEL_TOKEN,
    SENTINEL_QUERY,
    "someone@example.test",
)

_MANAGER_LOGGER = logging.getLogger("backend.db.migration_manager")
_BASE_LOGGER = logging.getLogger("backend.db.migration_base")


def _count_applied_lines(text: str) -> int:
    """Exactly what `.github/workflows/fly-deploy.yml` does: `grep -cF`."""
    return sum(1 for line in text.splitlines() if COUNTED in line)


def _assert_no_sentinel(*surfaces: str) -> None:
    for surface in surfaces:
        for sentinel in SENTINELS:
            assert sentinel not in surface, f"leaked {sentinel!r}"
        assert "Traceback" not in surface


class FakePostgresError(Exception):
    """Shaped like `asyncpg.exceptions.PostgresError`: `detail`/`hint`/`sqlstate`
    attributes and a `__str__` that appends DETAIL and HINT lines, which is
    how a bound value or a failing row reaches `str(e)`."""

    sqlstate = "23505"

    def __init__(self, message: str, detail: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.hint = hint
        self.query = SENTINEL_QUERY

    def __str__(self) -> str:
        text = self.message + "\nDETAIL:  " + self.detail
        if self.hint:
            text += "\nHINT:  " + self.hint
        return text


def _server_error() -> FakePostgresError:
    return FakePostgresError(
        f"duplicate key value violates unique constraint {SENTINEL_FIRST_LINE} {SENTINEL_TOKEN}",
        SENTINEL_DETAIL + " already exists.",
        hint=SENTINEL_QUERY,
    )


def _wrapped_migration_error() -> MigrationError:
    """`BaseMigration.apply` shape: `MigrationError(f"SQL execution failed: {e}") from e`."""
    cause = _server_error()
    err = MigrationError(f"SQL execution failed: {cause}")
    err.__cause__ = cause
    return err


@pytest.fixture(autouse=True)
def _boundary_cleanup():
    """`main()` installs the boundary on the root handlers for the process;
    detach it after every test so no other test file inherits it."""
    yield
    migrate.remove_cli_reporting_boundary()


class FakeManager:
    """Method-compatible stand-in for `MigrationManager`.

    `files` is the on-disk view (number -> file name), `ledger` the set of
    numbers recorded in `_schema_versions` (optionally with descriptions via
    `descriptions`). `apply_all_result` / `single_result` are returned
    verbatim; `discover_error` is raised from `discover_migrations`,
    `get_status` and the apply methods; `log_like_manager` makes the fake log
    a failure exactly as the real manager does
    (`logger.error("Failed to apply migration %s: %s", number, e)`);
    `interrupt` raises `KeyboardInterrupt` from `apply_all_pending`.
    """

    _APPLY_ALL_LOCK_ID = MigrationManager._APPLY_ALL_LOCK_ID

    def __init__(
        self,
        files: dict[int, str] | None = None,
        ledger: set[int] | None = None,
        descriptions: dict[int, str] | None = None,
        ledger_names: dict[int, str] | None = None,
        apply_all_result: dict | None = None,
        single_result: dict | None = None,
        discover_error: Exception | None = None,
        log_like_manager: Exception | None = None,
        interrupt: bool = False,
    ) -> None:
        self.files = files or {}
        self.ledger = set(ledger or set())
        self.descriptions = descriptions or {}
        self.ledger_names = ledger_names or {}
        self.apply_all_result = apply_all_result or {"applied": [], "skipped": [], "failed": []}
        self.single_result = single_result
        self.discover_error = discover_error
        self.log_like_manager = log_like_manager
        self.interrupt = interrupt
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.pool = None

    async def __aenter__(self) -> FakeManager:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def discover_migrations(self) -> list[dict]:
        self.calls.append(("discover_migrations", (), {}))
        if self.discover_error is not None:
            raise self.discover_error
        return [
            {"number": n, "file": f, "path": None, "rollback_sql": "SELECT 1;"}
            for n, f in sorted(self.files.items())
        ]

    async def get_applied_migrations(self) -> list[dict]:
        return [
            {
                "migration_name": self.ledger_names.get(n, f"{n:03d}_fake"),
                "migration_number": n,
                "executed_at": "2026-01-01T00:00:00+00:00",
                "description": self.descriptions.get(n, f"Migration {n}"),
            }
            for n in sorted(self.ledger)
        ]

    async def get_status(self) -> dict:
        if self.discover_error is not None:
            raise self.discover_error
        discovered = set(self.files)
        pending = sorted(discovered - self.ledger)
        return {
            "total": len(discovered),
            "applied": len(self.ledger),
            "pending": len(discovered) - len(self.ledger),  # the manager's own naive arithmetic
            "applied_list": sorted(self.ledger),
            "pending_list": pending,
        }

    async def apply_all_pending(self, dry_run: bool = False) -> dict:
        self.calls.append(("apply_all_pending", (), {"dry_run": dry_run}))
        if self.interrupt:
            raise KeyboardInterrupt
        if self.discover_error is not None:
            raise self.discover_error
        if dry_run:
            return {"applied": [], "skipped": [], "failed": []}
        if self.log_like_manager is not None:
            _MANAGER_LOGGER.error("Failed to apply migration %s: %s", 11, self.log_like_manager)
        return self.apply_all_result

    async def apply_single(self, migration_number: int, dry_run: bool = False) -> dict:
        self.calls.append(("apply_single", (migration_number,), {"dry_run": dry_run}))
        if self.discover_error is not None:
            raise self.discover_error
        assert self.single_result is not None, "test forgot to configure single_result"
        return self.single_result


def _single(**overrides: Any) -> dict:
    base = {
        "applied": [],
        "skipped": [],
        "failed": [],
        "refused": None,
        "would_apply": [],
        "file": None,
    }
    base.update(overrides)
    return base


def _install_fake(monkeypatch: pytest.MonkeyPatch, manager: FakeManager) -> None:
    monkeypatch.setattr(migrate, "resolve_migration_dsn", lambda: "postgresql://fake")
    factory = Mock(return_value=manager)
    factory._APPLY_ALL_LOCK_ID = MigrationManager._APPLY_ALL_LOCK_ID
    monkeypatch.setattr(migrate, "MigrationManager", factory)


LOCK_BUSY_ALL = {"applied": [], "skipped": [], "failed": [], "refused": {"code": "lock_busy"}}


# ---------------------------------------------------------------------------
# describe_exception / reason_code: classes and codes, never text
# ---------------------------------------------------------------------------


def test_describe_exception_uses_classes_codes_and_sqlstate_only() -> None:
    described = migrate.describe_exception(_wrapped_migration_error())
    assert described == "MigrationError reason=sql_failed cause=FakePostgresError sqlstate=23505"
    _assert_no_sentinel(described)


def test_describe_exception_on_a_bare_exception() -> None:
    err = RuntimeError(SENTINEL_FIRST_LINE + "\n" + SENTINEL_DETAIL)
    assert migrate.describe_exception(err) == "RuntimeError reason=unexpected_exception"


def test_describe_exception_ignores_a_malformed_sqlstate() -> None:
    err = FakePostgresError("x", "y")
    err.sqlstate = "not-a-sqlstate " + SENTINEL_DETAIL  # type: ignore[misc]
    described = migrate.describe_exception(err)
    assert "sqlstate" not in described
    _assert_no_sentinel(described)


@pytest.mark.parametrize(
    ("message", "code"),
    [
        (
            "Duplicate migration numbers in migrations_v2/: 129: [a, b]",
            "duplicate_migration_numbers",
        ),
        ("DATABASE_URL not configured", "dsn_not_configured"),
        ("Migration runner cannot connect via DATABASE_URL (<x>): boom", "connect_failed"),
        ("Cannot connect to database: boom", "connect_failed"),
        (
            "MIGRATION_DATABASE_URL refused (session_user='x'): it is a SUPERUSER",
            "migrator_role_refused",
        ),
        ("SQL file not found: /x/y.sql", "sql_file_missing"),
        ("SQL contains dangerous pattern: DROP SCHEMA", "sql_validation_failed"),
        ("SQL execution failed: relation x does not exist", "sql_failed"),
        ("Verification failed for 901_x", "verification_failed"),
        (
            "Migration 5 depends on migration 4, but 4 has not been applied yet",
            "dependency_missing",
        ),
        ("901_x: still lock-blocked after 8 attempt(s)", "lock_blocked"),
        ("Migration failed: boom", "migration_failed"),
        ("something new", "migration_error"),
    ],
)
def test_reason_codes_for_migration_errors(message: str, code: str) -> None:
    assert migrate.reason_code(MigrationError(message)) == code


# ---------------------------------------------------------------------------
# The logging boundary: numbers and classes pass, strings never do
# ---------------------------------------------------------------------------


def test_boundary_keeps_numbers_and_classes_and_withholds_every_string(caplog) -> None:
    caplog.set_level(logging.INFO)
    migrate.install_cli_reporting_boundary()
    _MANAGER_LOGGER.error("Failed to apply migration %s: %s", 904, _server_error())
    _MANAGER_LOGGER.info("Migration %s already applied; nothing to do", 901)
    _MANAGER_LOGGER.warning("free text arg: %s", SENTINEL_FIRST_LINE)
    _MANAGER_LOGGER.warning(
        "token-shaped arg: %s", SENTINEL_TOKEN
    )  # identifier-shaped, still withheld
    _MANAGER_LOGGER.error("role %s assumed %s after %d ms", SENTINEL_TOKEN, "901_udb_forward", 12)
    _MANAGER_LOGGER.info("mapping style %(number)d %(name)s", {"number": 7, "name": SENTINEL_TOKEN})
    assert "Failed to apply migration 904: FakePostgresError" in caplog.text
    assert "Migration 901 already applied; nothing to do" in caplog.text
    assert "free text arg: <withheld>" in caplog.text
    assert "token-shaped arg: <withheld>" in caplog.text
    assert "role <withheld> assumed <withheld> after 12 ms" in caplog.text
    assert "mapping style 7 <withheld>" in caplog.text
    _assert_no_sentinel(caplog.text)


@pytest.mark.parametrize("level", [logging.WARNING, logging.ERROR], ids=["warning", "error"])
def test_boundary_withholds_preformatted_messages_at_any_level(caplog, level: int) -> None:
    """f-string sites (migration_base.py:1030,1114) interpolate `str(e)`; a
    static message and free text are one string there, so the body goes."""
    caplog.set_level(logging.INFO)
    migrate.install_cli_reporting_boundary()
    try:
        raise _server_error()
    except FakePostgresError as exc:
        _BASE_LOGGER.log(level, f"Migration 901_x failed: {exc}", exc_info=True)
    _BASE_LOGGER.log(level, f"{SENTINEL_TOKEN}: first-line identifier-shaped sentinel")
    _BASE_LOGGER.log(level, _server_error())  # an exception object as the message
    _BASE_LOGGER.info("Applying migration 901_x to postgresql://user:***@db.internal:5432/app")
    text = caplog.text
    assert (
        "backend.db.migration_base " + logging.getLevelName(level) + ": diagnostic withheld" in text
    )
    assert "[traceback withheld at the CLI boundary: FakePostgresError]" in text
    assert "FakePostgresError [exception body withheld at the CLI boundary]" in text
    assert "backend.db.migration_base INFO: diagnostic withheld" in text
    assert "db.internal" not in text
    _assert_no_sentinel(text)
    assert all(r.exc_info is None and r.exc_text is None for r in caplog.records)


def test_boundary_install_is_idempotent_and_removable() -> None:
    migrate.install_cli_reporting_boundary()
    migrate.install_cli_reporting_boundary()
    root = logging.getLogger()
    assert root.handlers, "the boundary must guarantee a root handler exists"
    for handler in root.handlers:
        count = sum(isinstance(f, migrate.CliReportingBoundary) for f in handler.filters)
        assert count == 1
    migrate.remove_cli_reporting_boundary()
    for handler in root.handlers:
        assert not any(isinstance(f, migrate.CliReportingBoundary) for f in handler.filters)


# ---------------------------------------------------------------------------
# status / list / info: truthful output, no ledger text verbatim
# ---------------------------------------------------------------------------


async def test_status_reports_files_applied_pending_and_ledger_only(capsys) -> None:
    # 3 files, 2 applied, plus 2 ledger rows whose files are gone (production shape).
    manager = FakeManager(
        files={1: "001_a.sql", 2: "002_b.sql", 3: "003_c.sql"}, ledger={1, 2, 40, 41}
    )
    assert await migrate.cmd_status(manager) is True
    out = capsys.readouterr().out
    assert "Migration status: files=3 applied=2 pending=1 ledger_only=2" in out
    assert "Pending: 1 migration(s): 003" in out
    assert "highest number 041" in out
    # The manager's naive `pending` (3 - 4 = -1) must never surface.
    assert "-1" not in out


async def test_status_on_fresh_database(capsys) -> None:
    manager = FakeManager(files={5: "005_x.sql"}, ledger=set())
    await migrate.cmd_status(manager)
    out = capsys.readouterr().out
    assert "files=1 applied=0 pending=1 ledger_only=0" in out
    assert "Applied: no ledger rows (fresh database)" in out


async def test_list_tags_each_file_and_names_ledger_only_rows(capsys) -> None:
    manager = FakeManager(files={1: "001_a.sql", 2: "002_b.sql"}, ledger={1, 9})
    assert await migrate.cmd_list(manager) is True
    out = capsys.readouterr().out
    assert "[applied] 001 001_a.sql" in out
    assert "[pending] 002 002_b.sql" in out
    assert "[ledger ] 009 (recorded in _schema_versions, no file on disk)" in out
    assert "Listed 2 file(s): 1 applied, 1 pending; 1 ledger-only" in out


async def test_info_never_prints_ledger_text_verbatim(capsys) -> None:
    manager = FakeManager(
        files={2: "002_b.sql", 3: "003_c.sql"},
        ledger={2, 3, 9},
        ledger_names={2: "002_b", 3: SENTINEL_TOKEN, 9: "hand written " + SENTINEL_FIRST_LINE},
        descriptions={2: "Migration 2 " + SENTINEL_TOKEN, 3: "", 9: SENTINEL_DETAIL},
    )
    await migrate.cmd_info(manager, 2)
    await migrate.cmd_info(manager, 3)
    await migrate.cmd_info(manager, 9)
    await migrate.cmd_info(manager, 7)
    out = capsys.readouterr().out
    assert "Migration 002: applied" in out
    assert "  ledger name: 002_b" in out  # equals the file stem: derived from a tracked filename
    assert (
        f"  description: present (sha256:{migrate.fingerprint('Migration 2 ' + SENTINEL_TOKEN)})"
        in out
    )
    assert "  file on disk: 002_b.sql" in out
    assert "Migration 003: applied" in out
    assert f"  ledger name: not the file stem (sha256:{migrate.fingerprint(SENTINEL_TOKEN)})" in out
    assert "  description: absent" in out
    assert "Migration 009: applied" in out
    assert "  file on disk: none" in out
    assert "Migration 007: not applied" in out
    _assert_no_sentinel(out)


# ---------------------------------------------------------------------------
# apply-all: the deploy-consumer contract
# ---------------------------------------------------------------------------


async def test_apply_all_emits_one_counted_line_per_applied_migration(capsys) -> None:
    manager = FakeManager(apply_all_result={"applied": [324, 325], "skipped": [], "failed": []})
    assert await migrate.cmd_apply(manager) is True
    out = capsys.readouterr().out
    assert _count_applied_lines(out) == 2
    assert f"{COUNTED}324 applied" in out
    assert f"{COUNTED}325 applied" in out
    assert "✅ Applied: 2 migrations" in out
    assert "Summary: applied=2 skipped=0 failed=0 refused=0" in out
    assert manager.calls[-1] == ("apply_all_pending", (), {"dry_run": False})


async def test_apply_all_with_nothing_pending_is_zero_not_silence(capsys) -> None:
    manager = FakeManager()
    assert await migrate.cmd_apply(manager) is True
    out = capsys.readouterr().out
    assert _count_applied_lines(out) == 0
    assert "✅ Applied: 0 migrations" in out
    assert "Summary: applied=0 skipped=0 failed=0 refused=0" in out


async def test_apply_all_lock_busy_is_a_refusal_not_a_success(capsys) -> None:
    """Kimi F1: a run that could not take the advisory lock has applied nothing
    and must not exit 0 -- the Fly release_command would otherwise deploy over
    pending migrations."""
    manager = FakeManager(apply_all_result=LOCK_BUSY_ALL)
    assert await migrate.cmd_apply(manager) is False
    out = capsys.readouterr().out
    assert "   ✗ apply-all refused: another migration runner holds advisory lock 73491" in out
    assert _count_applied_lines(out) == 0
    assert "Summary: applied=0 skipped=0 failed=0 refused=1" in out


async def test_apply_all_failure_is_not_counted_and_bodies_never_print(capsys) -> None:
    body = f"SQL execution failed: {_server_error()}; dsn=postgresql://u:p@h/db"
    manager = FakeManager(
        apply_all_result={"applied": [10], "skipped": [], "failed": [{"number": 11, "error": body}]}
    )
    assert await migrate.cmd_apply(manager) is False
    captured = capsys.readouterr()
    assert _count_applied_lines(captured.out) == 1  # only 010
    assert "   ! Migration 011 FAILED" in captured.out
    assert "❌ Failed: 1 migrations" in captured.out
    assert "Summary: applied=1 skipped=0 failed=1 refused=0" in captured.out
    assert "postgresql://" not in captured.out
    assert "SQL execution failed" not in captured.out
    _assert_no_sentinel(captured.out, captured.err)


async def test_apply_all_dry_run_previews_without_counted_lines(capsys) -> None:
    manager = FakeManager(files={1: "001_a.sql", 2: "002_b.sql", 3: "003_c.sql"}, ledger={1})
    assert await migrate.cmd_apply(manager, dry_run=True) is True
    out = capsys.readouterr().out
    assert "DRY RUN: 2 pending migration(s) would be applied" in out
    assert "   ~ Would apply migration 002 (002_b.sql)" in out
    assert "   ~ Would apply migration 003 (003_c.sql)" in out
    assert _count_applied_lines(out) == 0
    assert "✅ Applied: 0 migrations (dry run)" in out
    assert "Summary: applied=0 skipped=0 failed=0 refused=0" in out
    assert ("apply_all_pending", (), {"dry_run": True}) in manager.calls


async def test_dry_run_never_emits_counted_lines_even_if_the_runner_reports_applied(capsys) -> None:
    """Kimi F2: the guard lives in the CLI, independent of the runner's
    dry-run return shape."""

    class Leaky(FakeManager):
        async def apply_all_pending(self, dry_run: bool = False) -> dict:
            return {"applied": [2, 3], "skipped": [], "failed": []}

    manager = Leaky(files={2: "002_b.sql", 3: "003_c.sql"}, ledger=set())
    assert await migrate.cmd_apply(manager, dry_run=True) is True
    out = capsys.readouterr().out
    assert _count_applied_lines(out) == 0
    assert "✅ Applied: 0 migrations (dry run)" in out


async def test_dry_run_while_a_release_holds_the_lock_is_refused(capsys) -> None:
    """Kimi F6: documented behaviour -- a dry run cannot report an empty
    success when it could not observe the ledger under the lock."""
    manager = FakeManager(files={2: "002_b.sql"}, ledger=set())

    async def busy(dry_run: bool = False) -> dict:
        return LOCK_BUSY_ALL

    manager.apply_all_pending = busy  # type: ignore[method-assign]
    assert await migrate.cmd_apply(manager, dry_run=True) is False
    out = capsys.readouterr().out
    assert "   ✗ apply-all (dry run) refused: another migration runner holds advisory lock" in out
    assert "refused=1" in out
    assert _count_applied_lines(out) == 0


# ---------------------------------------------------------------------------
# apply N: single-migration path
# ---------------------------------------------------------------------------


async def test_apply_single_applied(capsys) -> None:
    manager = FakeManager(single_result=_single(applied=[42], file="042_x.sql"))
    assert await migrate.cmd_apply(manager, migration_number=42) is True
    out = capsys.readouterr().out
    assert _count_applied_lines(out) == 1
    assert "✅ Applied: 1 migrations" in out
    assert "Summary: applied=1 skipped=0 failed=0 refused=0" in out
    assert manager.calls[-1] == ("apply_single", (42,), {"dry_run": False})


async def test_apply_single_already_applied_is_a_skip_not_a_failure(capsys) -> None:
    manager = FakeManager(single_result=_single(skipped=[42], file="042_x.sql"))
    assert await migrate.cmd_apply(manager, migration_number=42) is True
    out = capsys.readouterr().out
    assert "   ~ Migration 042 skipped (already applied)" in out
    assert _count_applied_lines(out) == 0
    assert "Summary: applied=0 skipped=1 failed=0 refused=0" in out


async def test_apply_single_unknown_number_is_refused(capsys) -> None:
    refused = {
        "code": "unknown_number",
        "number": 999,
        "known_count": 3,
        "known_min": 1,
        "known_max": 3,
    }
    manager = FakeManager(single_result=_single(refused=refused))
    assert await migrate.cmd_apply(manager, migration_number=999) is False
    out = capsys.readouterr().out
    assert (
        "   ✗ Migration 999 refused: no file with this number (on disk: 3 file(s), 001..003)" in out
    )
    assert _count_applied_lines(out) == 0
    assert "Summary: applied=0 skipped=0 failed=0 refused=1" in out


async def test_apply_single_earlier_pending_is_refused_with_the_numbers(capsys) -> None:
    refused = {"code": "earlier_pending", "number": 5, "earlier_pending": [3, 4]}
    manager = FakeManager(single_result=_single(refused=refused, file="005_e.sql"))
    assert await migrate.cmd_apply(manager, migration_number=5) is False
    out = capsys.readouterr().out
    assert "refused: 2 earlier pending migration(s) must be applied first: 003, 004" in out
    assert "hint: run `apply-all`" in out
    assert _count_applied_lines(out) == 0
    assert "Summary: applied=0 skipped=0 failed=0 refused=1" in out


async def test_apply_single_lock_busy_is_refused(capsys) -> None:
    manager = FakeManager(single_result=_single(refused={"code": "lock_busy", "number": 5}))
    assert await migrate.cmd_apply(manager, migration_number=5) is False
    out = capsys.readouterr().out
    assert "   ✗ Migration 005 refused: another migration runner holds advisory lock 73491" in out
    assert "refused=1" in out


async def test_apply_single_unknown_refusal_code_is_never_echoed(capsys) -> None:
    refused = {"code": SENTINEL_TOKEN, "number": 5}
    manager = FakeManager(single_result=_single(refused=refused))
    assert await migrate.cmd_apply(manager, migration_number=5) is False
    out = capsys.readouterr().out
    assert "   ✗ Migration 005 refused: reason=unknown" in out
    _assert_no_sentinel(out)


async def test_apply_single_dry_run_previews_only(capsys) -> None:
    manager = FakeManager(single_result=_single(would_apply=[7], file="007_g.sql"))
    assert await migrate.cmd_apply(manager, migration_number=7, dry_run=True) is True
    out = capsys.readouterr().out
    assert "   ~ Would apply migration 007 (007_g.sql)" in out
    assert _count_applied_lines(out) == 0
    assert "✅ Applied: 0 migrations (dry run)" in out
    assert manager.calls[-1] == ("apply_single", (7,), {"dry_run": True})


async def test_apply_single_failure_body_never_prints(capsys) -> None:
    failed = [{"number": 7, "error": f"SQL execution failed: {_server_error()}"}]
    manager = FakeManager(single_result=_single(failed=failed, file="007_g.sql"))
    assert await migrate.cmd_apply(manager, migration_number=7) is False
    captured = capsys.readouterr()
    assert "   ! Migration 007 FAILED" in captured.out
    assert "Summary: applied=0 skipped=0 failed=1 refused=0" in captured.out
    _assert_no_sentinel(captured.out, captured.err)


# ---------------------------------------------------------------------------
# main(): parser, exit codes, and the sentinel regressions (default + verbose)
# ---------------------------------------------------------------------------


def test_main_without_command_prints_help_and_exits_1(capsys) -> None:
    assert migrate.main([]) == 1
    assert "apply-all" in capsys.readouterr().out


def test_main_without_dsn_exits_1_with_a_static_line(monkeypatch, capsys) -> None:
    monkeypatch.setattr(migrate, "resolve_migration_dsn", lambda: None)
    assert migrate.main(["status"]) == 1
    assert "❌ not configured: set DATABASE_URL" in capsys.readouterr().out


def test_main_apply_all_exit_codes(monkeypatch, capsys) -> None:
    ok = FakeManager(apply_all_result={"applied": [1], "skipped": [], "failed": []})
    _install_fake(monkeypatch, ok)
    assert migrate.main(["apply-all"]) == 0
    assert _count_applied_lines(capsys.readouterr().out) == 1

    bad = FakeManager(
        apply_all_result={"applied": [], "skipped": [], "failed": [{"number": 2, "error": "x"}]}
    )
    _install_fake(monkeypatch, bad)
    assert migrate.main(["apply-all"]) == 1

    busy = FakeManager(apply_all_result=LOCK_BUSY_ALL)
    _install_fake(monkeypatch, busy)
    assert migrate.main(["apply-all"]) == 1
    out = capsys.readouterr().out
    assert "refused=1" in out
    assert _count_applied_lines(out) == 0


def test_main_treats_a_none_returning_command_as_failure(monkeypatch) -> None:
    """Kimi F4: `is True`, never `is not False`."""
    _install_fake(monkeypatch, FakeManager())

    async def returns_none(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(migrate, "_dispatch", returns_none)
    assert migrate.main(["status"]) == 1


def test_main_interrupt_exits_130_with_zero_applied_lines(monkeypatch, capsys) -> None:
    _install_fake(monkeypatch, FakeManager(interrupt=True))
    assert migrate.main(["apply-all"]) == 130
    out = capsys.readouterr().out
    assert "⚠ apply-all interrupted by user" in out
    assert _count_applied_lines(out) == 0


def test_main_apply_requires_an_integer_number(monkeypatch) -> None:
    _install_fake(monkeypatch, FakeManager())
    with pytest.raises(SystemExit) as exc:
        migrate.main(["apply", "not-a-number"])
    assert exc.value.code == 2  # argparse usage error


def test_main_apply_dispatches_number_and_dry_run(monkeypatch) -> None:
    manager = FakeManager(single_result=_single(would_apply=[9], file="009_i.sql"))
    _install_fake(monkeypatch, manager)
    assert migrate.main(["apply", "9", "--dry-run"]) == 0
    assert manager.calls[-1] == ("apply_single", (9,), {"dry_run": True})


def test_main_duplicate_numbers_surface_as_a_reason_code(monkeypatch, capsys) -> None:
    err = MigrationError(
        "Duplicate migration numbers in migrations_v2/: 129: [129_a.sql, 129_b.sql]. "
        "Two files cannot share a prefix"
    )
    _install_fake(monkeypatch, FakeManager(discover_error=err))
    assert migrate.main(["apply-all"]) == 1
    captured = capsys.readouterr()
    assert "❌ apply-all failed: MigrationError reason=duplicate_migration_numbers" in captured.out
    assert "129_a.sql" not in captured.out
    assert "Traceback" not in captured.out
    assert _count_applied_lines(captured.out) == 0


def test_main_connect_failure_never_names_the_host(monkeypatch, capsys) -> None:
    err = MigrationError(
        "Migration runner cannot connect via DATABASE_URL "
        "(postgresql://app:***@db.internal:5432/app): ConnectionResetError"
    )
    _install_fake(monkeypatch, FakeManager(discover_error=err))
    assert migrate.main(["status"]) == 1
    captured = capsys.readouterr()
    assert "❌ status failed: MigrationError reason=connect_failed" in captured.out
    assert "db.internal" not in captured.out
    assert "db.internal" not in captured.err


@pytest.mark.parametrize("verbose", [False, True], ids=["default", "verbose"])
def test_sentinel_in_first_exception_line_never_reaches_any_surface(
    monkeypatch, capsys, caplog, verbose: bool
) -> None:
    class Exploding(FakeManager):
        async def get_status(self) -> dict:
            raise RuntimeError(
                f"{SENTINEL_TOKEN} {SENTINEL_FIRST_LINE}\nDETAIL:  {SENTINEL_DETAIL}"
            )

    _install_fake(monkeypatch, Exploding())
    caplog.set_level(logging.DEBUG)
    argv = ["-v", "status"] if verbose else ["status"]
    assert migrate.main(argv) == 1
    captured = capsys.readouterr()
    assert "❌ status failed: RuntimeError reason=unexpected_exception" in captured.out
    _assert_no_sentinel(captured.out, captured.err, caplog.text)


@pytest.mark.parametrize("verbose", [False, True], ids=["default", "verbose"])
def test_server_detail_fields_never_reach_any_surface(
    monkeypatch, capsys, caplog, verbose: bool
) -> None:
    """A PostgreSQL-shaped error (message + DETAIL + HINT + sqlstate + query)
    raised through the manager: stdout shows classes, codes and the sqlstate;
    nothing shows the message, the DETAIL, the HINT, the token or the query."""

    class Raising(FakeManager):
        async def apply_all_pending(self, dry_run: bool = False) -> dict:
            raise _wrapped_migration_error()

    _install_fake(monkeypatch, Raising())
    caplog.set_level(logging.DEBUG)
    argv = ["-v", "apply-all"] if verbose else ["apply-all"]
    assert migrate.main(argv) == 1
    captured = capsys.readouterr()
    assert (
        "❌ apply-all failed: MigrationError reason=sql_failed "
        "cause=FakePostgresError sqlstate=23505"
    ) in captured.out
    _assert_no_sentinel(captured.out, captured.err, caplog.text)


@pytest.mark.parametrize("verbose", [False, True], ids=["default", "verbose"])
def test_underlying_manager_error_log_is_rebuilt_at_the_boundary(
    monkeypatch, capsys, caplog, verbose: bool
) -> None:
    """The real manager logs `Failed to apply migration %s: %s` with the
    exception as an argument and records `str(e)` in `failed[]`; through
    `main()` neither surface may carry the server fields or the token."""
    err = _wrapped_migration_error()
    manager = FakeManager(
        apply_all_result={
            "applied": [],
            "skipped": [],
            "failed": [{"number": 11, "error": str(err)}],
        },
        log_like_manager=err,
    )
    _install_fake(monkeypatch, manager)
    caplog.set_level(logging.DEBUG)
    argv = ["-v", "apply-all"] if verbose else ["apply-all"]
    assert migrate.main(argv) == 1
    captured = capsys.readouterr()
    assert "   ! Migration 011 FAILED" in captured.out
    assert "Failed to apply migration 11: MigrationError" in caplog.text
    _assert_no_sentinel(captured.out, captured.err, caplog.text)


@pytest.mark.parametrize("verbose", [False, True], ids=["default", "verbose"])
def test_underlying_warning_and_error_with_token_args_through_main(
    monkeypatch, capsys, caplog, verbose: bool
) -> None:
    """Identifier-shaped sentinel passed as a `%s` argument at WARNING and at
    ERROR by an underlying logger during the run, default and verbose."""

    class Chatty(FakeManager):
        async def apply_all_pending(self, dry_run: bool = False) -> dict:
            _MANAGER_LOGGER.warning("Orphan ledger rows for %s", SENTINEL_TOKEN)
            _MANAGER_LOGGER.error(
                "Cannot read migration %s: %s", SENTINEL_TOKEN, OSError(SENTINEL_FIRST_LINE)
            )
            _BASE_LOGGER.warning(f"{SENTINEL_TOKEN} preformatted warning")
            return {"applied": [1], "skipped": [], "failed": []}

    _install_fake(monkeypatch, Chatty())
    caplog.set_level(logging.DEBUG)
    argv = ["-v", "apply-all"] if verbose else ["apply-all"]
    assert migrate.main(argv) == 0
    captured = capsys.readouterr()
    assert "Orphan ledger rows for <withheld>" in caplog.text
    assert "Cannot read migration <withheld>: OSError" in caplog.text
    assert "backend.db.migration_base WARNING: diagnostic withheld" in caplog.text
    _assert_no_sentinel(captured.out, captured.err, caplog.text)
