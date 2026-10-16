#!/usr/bin/env python3
"""
NUZANTARA PRIME - Migration CLI Tool
Centralized tool for managing database migrations

CONTRACT (the consumers this file is written for)
-------------------------------------------------
* The Fly `release_command` (`apps/backend-rag/fly.toml`) and two jobs in
  `.github/workflows/fly-deploy.yml` run `python -m backend.db.migrate
  apply-all` and judge it by EXIT CODE: 0 only when every pending migration
  was applied or nothing was pending; 1 when anything failed OR the run was
  refused (another runner held the advisory lock, a requested number was
  unknown or out of order); 130 on interrupt.
* The post-deploy job additionally counts applied migrations with
  `grep -cF "   - Migration "` over the combined stdout+stderr. That fixed
  string is `APPLIED_LINE_PREFIX` below and is emitted EXACTLY once per
  migration that was really applied -- never in a dry run (guarded here,
  independent of the runner's return shape), never for a skip, a refusal or
  a failure, whose lines use a different marker character.
* The same job's comment documents a `✅ Applied: N migrations` line; it is
  `APPLIED_SUMMARY` below and is always printed by `apply-all` / `apply`.
* The two APPLY commands (`apply-all`, `apply N`) end with one machine-stable
  line: `Summary: applied=<n> skipped=<n> failed=<n> refused=<n>`; exit 1
  iff `failed` or `refused` is non-zero. `status` / `list` / `info` end with
  their own last line and exit 0; configuration errors and interrupts print
  one `❌` / `⚠` line and exit 1 / 130 without a Summary.

DRY RUN (bounded behaviour, Kimi round 3 F5/F6)
-----------------------------------------------
`apply-all --dry-run` prints its preview from the same two reads the runner
uses (`discover_migrations`, `get_applied_migrations`) and then drives the
runner's own dry-run path, which takes and releases the real advisory lock.
Consequences, deliberate: a dry run started while a release holds the lock
is REFUSED (exit 1, `refused=1`) rather than reporting an empty success; a
release started while a dry run holds the lock is refused for the few
milliseconds of the preview. The preview and the runner read the ledger at
two instants, so a migration applied by another session in between shows in
the preview and not in the runner's log; the preview never claims to have
applied anything.

REPORTING BOUNDARY (stdout AND stderr are outputs) -- fail-closed
----------------------------------------------------------------
Nothing this process emits may carry a DSN, a password, a query body, a bound
value, a server DETAIL line, a token or any other interpolated text -- the
deploy jobs tee both streams into Telegram alerts, and a PostgreSQL error
routinely quotes the failing row. Two mechanisms, both bounded to this CLI:

1. The CLI's own diagnostics are built from migration NUMBERS, exception
   CLASS names, code-authored REASON CODES and a validated five-character
   SQLSTATE (`describe_exception`). A `MigrationError` is classified by a
   static fragment of its code-authored message; the message itself is never
   written. `info` never prints ledger text verbatim: the description is
   reported as present/absent with a fingerprint, the ledger name only when
   it is the on-disk file stem.
2. `install_cli_reporting_boundary()` attaches a `logging.Filter` to every
   root handler for the lifetime of the process. Every record is REBUILT
   from its code-authored template, its numeric arguments and exception
   class names; every string argument is replaced by `<withheld>` whatever
   its shape (a token is identifier-shaped); a record logged as one
   pre-formatted string (f-string) is withheld entirely, because nothing can
   tell a static message from interpolated free text once it is one string;
   `exc_info`/tracebacks are stripped and replaced by the exception class
   name. `--verbose` lowers the log level to DEBUG and changes nothing about
   redaction. There is no scrubbing by pattern: that was attempt 1 and it
   could not be made safe.

Serialisation, the `-- === ROLLBACK ===` split, the full-file checksum and
the two-ledger bookkeeping all live in `backend/db/migration_manager.py` /
`migration_base.py`; this module only drives them and reports truthfully.
"""

import argparse
import asyncio
import hashlib
import logging
import re
import sys
from collections.abc import Mapping
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db.migration_base import MigrationError, resolve_migration_dsn
from backend.db.migration_manager import MigrationManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

#: Counted by `.github/workflows/fly-deploy.yml` (`grep -cF "   - Migration "`).
#: One line per REALLY applied migration; no other line may contain it.
APPLIED_LINE_PREFIX = "   - Migration "
#: Documented in the same workflow's comment block.
APPLIED_SUMMARY = "✅ Applied: {count} migrations"
#: Last line of both apply commands; stable, grep-friendly key=value.
SUMMARY_LINE = "Summary: applied={applied} skipped={skipped} failed={failed} refused={refused}"

_MAX_LISTED_NUMBERS = 20
_SQLSTATE_RE = re.compile(r"\A[0-9A-Z]{5}\Z")

#: `MigrationError` messages are code-authored, but several embed `str(e)` of
#: a PostgreSQL error. They are classified by a static fragment into a reason
#: code and the text is NEVER written. Most specific fragments first.
_MIGRATION_ERROR_REASONS: tuple[tuple[str, str], ...] = (
    ("Duplicate migration numbers", "duplicate_migration_numbers"),
    ("DATABASE_URL not configured", "dsn_not_configured"),
    ("Migration runner cannot connect", "connect_failed"),
    ("Cannot connect to database", "connect_failed"),
    ("Cannot assume the runtime role", "runtime_role_failed"),
    ("MIGRATION_DATABASE_URL refused", "migrator_role_refused"),
    ("SQL file not found", "sql_file_missing"),
    ("Failed to read SQL file", "sql_file_unreadable"),
    ("SQL contains", "sql_validation_failed"),
    ("SQL execution failed", "sql_failed"),
    ("Verification failed", "verification_failed"),
    ("verify_apply failed", "verification_failed"),
    ("depends on migration", "dependency_missing"),
    ("still lock-blocked", "lock_blocked"),
    ("Migration failed", "migration_failed"),
)

#: Refusal codes the runner can return; anything else prints as `unknown`.
_KNOWN_REFUSALS = frozenset({"unknown_number", "earlier_pending", "lock_busy"})


# ---------------------------------------------------------------------------
# Reporting boundary
# ---------------------------------------------------------------------------


def reason_code(exc: BaseException) -> str:
    """A stable, code-authored reason code for an exception. Never its text."""
    if isinstance(exc, MigrationError):
        text = str(exc)
        for fragment, code in _MIGRATION_ERROR_REASONS:
            if fragment in text:
                return code
        return "migration_error"
    return "unexpected_exception"


def describe_exception(exc: BaseException) -> str:
    """`<Class> reason=<code>[ cause=<Class>][ sqlstate=<5 chars>]`.

    Built ONLY from class names, the reason code and a validated five-character
    SQLSTATE. The exception message, its `detail`/`hint` fields and the query
    are never consulted for output.
    """
    parts = [type(exc).__name__, f"reason={reason_code(exc)}"]
    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        parts.append(f"cause={type(cause).__name__}")
    for candidate in (exc, cause):
        sqlstate = getattr(candidate, "sqlstate", None)
        if isinstance(sqlstate, str) and _SQLSTATE_RE.fullmatch(sqlstate):
            parts.append(f"sqlstate={sqlstate}")
            break
    return " ".join(parts)


def fingerprint(text: str) -> str:
    """Twelve hex characters of SHA-256: identifies ledger text without quoting it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class CliReportingBoundary(logging.Filter):
    """Fail-closed rebuild of every record that reaches a root handler.

    Installed on HANDLERS (not on loggers): a filter on a logger only sees
    records logged directly on it, while a handler filter sees every record
    propagated to the root, including those of `backend.db.migration_base`
    (read-only for this lane, and it logs `str(e)` with `exc_info=True`).

    What passes: the code-authored template of an args-style call, `int` /
    `float` / `bool` / `None` arguments, exception CLASS names. What never
    passes: any string argument (replaced by `<withheld>`, whatever its
    shape), any pre-formatted single-string message (withheld entirely, with
    logger and level kept), any traceback.
    """

    WITHHELD = "<withheld>"
    _REBUILT = object()

    @classmethod
    def _safe_arg(cls, value: object) -> object:
        if isinstance(value, BaseException):
            return type(value).__name__
        if value is None or isinstance(value, bool | int | float):
            return value
        return cls.WITHHELD

    def filter(self, record: logging.LogRecord) -> bool:
        # A LogRecord is shared by all root handlers. Rebuilding twice would
        # redact the already-safe exception class and erase the reason code.
        if getattr(record, "_nuz_cli_rebuilt", None) is self._REBUILT:
            return True
        suffix = ""
        if record.exc_info or record.exc_text:
            exc_name = "exception"
            if isinstance(record.exc_info, tuple) and record.exc_info[0] is not None:
                exc_name = record.exc_info[0].__name__
            record.exc_info = None
            record.exc_text = None
            suffix = f" [traceback withheld at the CLI boundary: {exc_name}]"
        record.stack_info = None

        if isinstance(record.msg, BaseException):
            message = f"{type(record.msg).__name__} [exception body withheld at the CLI boundary]"
            record.args = ()
        elif record.args:
            # Args-style call: the template is code-authored; the arguments
            # are rebuilt so that no string survives.
            if isinstance(record.args, Mapping):
                record.args = {k: self._safe_arg(v) for k, v in record.args.items()}
            else:
                record.args = tuple(self._safe_arg(v) for v in record.args)
            message = str(record.msg)
        else:
            # One pre-formatted string: static text and interpolated free text
            # are indistinguishable here, so the body is withheld.
            message = f"{record.name} {record.levelname}: diagnostic withheld at the CLI boundary"
        record.msg = message + suffix
        record._nuz_cli_rebuilt = self._REBUILT
        return True


def install_cli_reporting_boundary() -> CliReportingBoundary:
    """Attach the boundary to every root handler (idempotent per handler)."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    boundary = CliReportingBoundary()
    for handler in root.handlers:
        if not any(isinstance(f, CliReportingBoundary) for f in handler.filters):
            handler.addFilter(boundary)
    return boundary


def remove_cli_reporting_boundary() -> None:
    """Detach every boundary from the root handlers (tests clean up with this)."""
    for handler in logging.getLogger().handlers:
        for existing in list(handler.filters):
            if isinstance(existing, CliReportingBoundary):
                handler.removeFilter(existing)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _emit(line: str = "") -> None:
    sys.stdout.write(f"{line}\n")
    sys.stdout.flush()


def _fmt_numbers(numbers: list[int]) -> str:
    shown = ", ".join(f"{n:03d}" for n in numbers[:_MAX_LISTED_NUMBERS])
    extra = len(numbers) - _MAX_LISTED_NUMBERS
    return f"{shown} ... (+{extra} more)" if extra > 0 else shown


def _refusal_lines(subject: str, refused: Mapping) -> list[str]:
    """Human lines for a refusal, built from numbers and known codes only."""
    code = refused.get("code")
    if code not in _KNOWN_REFUSALS:
        return [f"   ✗ {subject} refused: reason=unknown"]
    if code == "unknown_number":
        known = int(refused.get("known_count") or 0)
        span = ""
        if known:
            span = (
                f" (on disk: {known} file(s), "
                f"{int(refused['known_min']):03d}..{int(refused['known_max']):03d})"
            )
        return [f"   ✗ {subject} refused: no file with this number{span}"]
    if code == "earlier_pending":
        earlier = [int(n) for n in (refused.get("earlier_pending") or [])]
        return [
            f"   ✗ {subject} refused: {len(earlier)} earlier pending migration(s) "
            f"must be applied first: {_fmt_numbers(earlier)}",
            "     hint: run `apply-all`, or `apply <number>` for each earlier number in order",
        ]
    return [
        f"   ✗ {subject} refused: another migration runner holds advisory lock "
        f"{MigrationManager._APPLY_ALL_LOCK_ID}; nothing was applied, retry when it has finished"
    ]


def _report_result(result: Mapping, *, dry_run: bool, subject: str) -> bool:
    """Print the applied/skipped/failed/refused lines and the two summary lines.

    Returns True only when nothing failed AND nothing was refused. Shared by
    `apply-all` and `apply N`. The counted line is guarded against the
    runner's return shape: in a dry run it is never emitted, whatever the
    runner put in `applied`.
    """
    applied = [] if dry_run else list(result.get("applied") or [])
    skipped = list(result.get("skipped") or [])
    failed = list(result.get("failed") or [])
    refused = result.get("refused") or None

    for number in applied:
        _emit(f"{APPLIED_LINE_PREFIX}{int(number):03d} applied")
    for number in skipped:
        _emit(f"   ~ Migration {int(number):03d} skipped (already applied)")
    for failure in failed:
        # `failure["error"]` is `str(e)` recorded by the manager; it can quote
        # the failing statement, a bound value or a server DETAIL line, so it
        # is never written. The number and the class are enough to act on.
        _emit(
            f"   ! Migration {int(failure['number']):03d} FAILED (reason withheld; see runner log)"
        )
    if refused:
        for line in _refusal_lines(subject, refused):
            _emit(line)

    _emit(APPLIED_SUMMARY.format(count=len(applied)) + (" (dry run)" if dry_run else ""))
    if failed:
        _emit(f"❌ Failed: {len(failed)} migrations")
    _emit(
        SUMMARY_LINE.format(
            applied=len(applied),
            skipped=len(skipped),
            failed=len(failed),
            refused=1 if refused else 0,
        )
    )
    return not failed and not refused


async def _pending_with_files(manager: MigrationManager) -> list[dict]:
    """Pending migrations from the same two reads the runner performs."""
    discovered = await manager.discover_migrations()
    applied_numbers = {m["migration_number"] for m in await manager.get_applied_migrations()}
    return sorted(
        (m for m in discovered if m["number"] not in applied_numbers),
        key=lambda m: m["number"],
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def cmd_status(manager: MigrationManager) -> bool:
    """Show migration status.

    Counts are derived from the LISTS, not from `get_status()["pending"]`:
    that field is `len(files) - len(ledger numbers)` and goes negative as soon
    as the ledger carries numbers whose files are gone (it does in production,
    where the ledger predates the SQL-v2 directory). `ledger_only` is that
    difference, named honestly.
    """
    status = await manager.get_status()
    applied_list: list[int] = list(status["applied_list"])
    pending_list: list[int] = list(status["pending_list"])
    total_files = int(status["total"])
    applied_files = total_files - len(pending_list)
    ledger_only = len(applied_list) - applied_files

    _emit(
        "Migration status: "
        f"files={total_files} applied={applied_files} pending={len(pending_list)} "
        f"ledger_only={ledger_only}"
    )
    if applied_list:
        _emit(f"Applied: {len(applied_list)} ledger row(s), highest number {max(applied_list):03d}")
    else:
        _emit("Applied: no ledger rows (fresh database)")
    if pending_list:
        _emit(f"Pending: {len(pending_list)} migration(s): {_fmt_numbers(pending_list)}")
    else:
        _emit("Pending: none")
    return True


async def cmd_list(manager: MigrationManager) -> bool:
    """List every migration file with its ledger state, then ledger-only rows."""
    discovered = await manager.discover_migrations()
    applied_numbers = {m["migration_number"] for m in await manager.get_applied_migrations()}
    discovered_numbers = {m["number"] for m in discovered}

    n_applied = n_pending = 0
    for migration_info in sorted(discovered, key=lambda x: x["number"]):
        number = migration_info["number"]
        if number in applied_numbers:
            tag = "applied"
            n_applied += 1
        else:
            tag = "pending"
            n_pending += 1
        _emit(f"[{tag}] {number:03d} {migration_info['file']}")

    ledger_only = sorted(applied_numbers - discovered_numbers)
    for number in ledger_only:
        _emit(f"[ledger ] {number:03d} (recorded in _schema_versions, no file on disk)")

    _emit(
        f"Listed {len(discovered)} file(s): {n_applied} applied, {n_pending} pending; "
        f"{len(ledger_only)} ledger-only"
    )
    return True


async def cmd_apply(
    manager: MigrationManager,
    migration_number: int | None = None,
    dry_run: bool = False,
) -> bool:
    """Apply migration(s).

    * `migration_number is None` -> `apply-all`: every pending file in number
      order via `MigrationManager.apply_all_pending`; a busy advisory lock is
      a refusal (exit 1), never an empty success.
    * otherwise -> `apply N`: exactly that number via
      `MigrationManager.apply_single`, which refuses unknown numbers, numbers
      with earlier pending files and a busy lock, and skips an already-applied
      one.

    Returns True only when nothing failed and nothing was refused.
    """
    if migration_number is not None:
        subject = f"Migration {migration_number:03d}"
        result = await manager.apply_single(migration_number, dry_run=dry_run)
        if not result.get("refused"):
            for number in result.get("would_apply") or []:
                _emit(f"   ~ Would apply migration {int(number):03d} ({result.get('file') or '?'})")
        return _report_result(result, dry_run=dry_run, subject=subject)

    if dry_run:
        pending = await _pending_with_files(manager)
        _emit(f"DRY RUN: {len(pending)} pending migration(s) would be applied")
        for migration_info in pending:
            _emit(
                f"   ~ Would apply migration {migration_info['number']:03d} "
                f"({migration_info['file']})"
            )
        # The runner's own dry-run path: it takes (and releases) the real
        # advisory lock and logs its view; a busy lock is reported as a
        # refusal here too (module docstring, DRY RUN).
        result = await manager.apply_all_pending(dry_run=True)
        return _report_result(result, dry_run=True, subject="apply-all (dry run)")

    result = await manager.apply_all_pending(dry_run=False)
    return _report_result(result, dry_run=False, subject="apply-all")


async def cmd_info(manager: MigrationManager, migration_number: int) -> bool:
    """Ledger and on-disk facts about one number, without quoting ledger text.

    The ledger name is printed only when it is the on-disk file's stem (or the
    file name), i.e. derived from a tracked filename; otherwise, and for the
    description, a presence flag plus a SHA-256 fingerprint is printed. A
    fingerprint identifies the row for an operator with database access
    without transcribing a value nobody has vetted into a deploy log.
    """
    applied_rows = await manager.get_applied_migrations()
    row = next((r for r in applied_rows if r["migration_number"] == migration_number), None)
    discovered = await manager.discover_migrations()
    file_name = next((m["file"] for m in discovered if m["number"] == migration_number), None)

    _emit(f"Migration {migration_number:03d}: {'applied' if row else 'not applied'}")
    if row:
        ledger_name = str(row["migration_name"] or "")
        derived = {file_name, Path(file_name).stem} if file_name else set()
        if ledger_name and ledger_name in derived:
            _emit(f"  ledger name: {ledger_name}")
        elif ledger_name:
            _emit(f"  ledger name: not the file stem (sha256:{fingerprint(ledger_name)})")
        else:
            _emit("  ledger name: absent")
        _emit(f"  executed at: {row['executed_at']}")
        description = row.get("description") if isinstance(row, Mapping) else row["description"]
        if description:
            _emit(f"  description: present (sha256:{fingerprint(str(description))})")
        else:
            _emit("  description: absent")
    _emit(f"  file on disk: {file_name or 'none'}")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.db.migrate",
        description="NUZANTARA PRIME - Database Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show migration status
  python -m backend.db.migrate status

  # List all migrations
  python -m backend.db.migrate list

  # Apply all pending migrations
  python -m backend.db.migrate apply-all

  # Dry run (show what would be applied; takes the advisory lock briefly)
  python -m backend.db.migrate apply-all --dry-run

  # Apply exactly one migration (refused if an earlier one is still pending)
  python -m backend.db.migrate apply 324
  python -m backend.db.migrate apply 324 --dry-run

  # Show info about migration 007
  python -m backend.db.migrate info 7

Exit codes: 0 applied or nothing pending; 1 failed, refused, or not
configured; 130 interrupted. Apply commands end with
`Summary: applied=N skipped=N failed=N refused=N`.
        """,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "DEBUG-level logging. Diagnostics stay redacted: no tracebacks, "
            "no exception or query text, with or without this flag."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    subparsers.add_parser("status", help="Show migration status")
    subparsers.add_parser("list", help="List all migrations")

    apply_all_parser = subparsers.add_parser("apply-all", help="Apply all pending migrations")
    apply_all_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without executing",
    )

    apply_parser = subparsers.add_parser("apply", help="Apply exactly one migration by number")
    apply_parser.add_argument("migration_number", type=int, help="Migration number")
    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what would be applied without executing",
    )

    info_parser = subparsers.add_parser("info", help="Show info about a specific migration")
    info_parser.add_argument("migration_number", type=int, help="Migration number")
    return parser


async def _dispatch(args: argparse.Namespace, manager: MigrationManager) -> bool:
    if args.command == "status":
        return await cmd_status(manager)
    if args.command == "list":
        return await cmd_list(manager)
    if args.command == "apply-all":
        return await cmd_apply(manager, dry_run=args.dry_run)
    if args.command == "apply":
        return await cmd_apply(
            manager, migration_number=args.migration_number, dry_run=args.dry_run
        )
    if args.command == "info":
        return await cmd_info(manager, args.migration_number)
    return False


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code (0 ok, 1 failure/refusal, 130 interrupted)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Before anything can log: the boundary governs every root handler for the
    # rest of the process, verbose or not.
    install_cli_reporting_boundary()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.command:
        parser.print_help()
        return 1

    if not resolve_migration_dsn():
        _emit("❌ not configured: set DATABASE_URL (or MIGRATION_DATABASE_URL) in the environment")
        return 1

    try:
        manager = MigrationManager()
    except MigrationError as e:
        _emit(f"❌ {args.command} failed: {describe_exception(e)}")
        return 1

    async def run_with_pool() -> bool:
        async with manager:
            return await _dispatch(args, manager)

    try:
        success = asyncio.run(run_with_pool())
        # `is True`, not `is not False`: a command that returns None is a
        # defect, not a success (Kimi round 3, F4).
        return 0 if success is True else 1
    except KeyboardInterrupt:
        _emit(f"⚠ {args.command} interrupted by user")
        return 130
    except Exception as e:  # MigrationError included: classes and codes only
        _emit(f"❌ {args.command} failed: {describe_exception(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
