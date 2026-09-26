"""T3 promise gate — PRO-LOCAL (owner ruling 2026-09-25, Symbiosis Law 2:
data never leaves Pro). PR-1 of the #7316 re-spec shipped schema + connection
guard only; this file now also carries PR-2, the scanner: `--scan` reads
`whatsapp_message_context` (outbound, last 30 days) and inserts/revises
`team_promise_candidates` rows. The judge (PR-3) reads those separately and
is not this file's job — it never dedups and never discards a past-tense
clause; that's the judge's call, not the regex's.

REWORK (post gate REWORK-DESIGN on the original PR-2 head, spec addendum
A1-A8): no persisted watermark. `hi = max(id)` of the eligible window is
read ONCE at tick start; the tick then walks an IN-TICK cursor over the
FULL 30-day window from 0 to that `hi`, every time. A monotonic watermark
permanently missed a row that commits out of id order, or whose body is
filled in later than its own commit (`apps/wa-mirror/bridge/
message_capture.ts` upserts on `baileys_message_id`, same id) — rescanning
the whole window every tick means a late/out-of-order row is inside SOME
future tick's range, by construction, and `hi` fixed at tick start is what
makes each tick still terminate against a live-growing table. A message
whose body CHANGED between ticks revises its candidate row in place
(`ON CONFLICT ... DO UPDATE`, guarded to unjudged rows only, never a judged
or quarantined one) rather than being silently skipped by `DO NOTHING`.

CLI:
  apps/backend-rag/.venv/bin/python scripts/wa_team_promises.py --init-schema
  apps/backend-rag/.venv/bin/python scripts/wa_team_promises.py --scan [--dry-run]

Applies scripts/sql/pro_local/team_promises.sql in ONE transaction, verifies
both unique indexes against pg_catalog INSIDE it, ROLLBACK on any mismatch.
Connection is Pro-local ONLY via explicit kwargs (no DSN/URL parsing);
`_guard_pro_local_env` refuses (exit 2) before any connect attempt if any
`FLY_*` env var is present at all, even empty; PG* libpq vars are cleared so
they can never override the kwargs. Every other error path prints ONLY
`wa_team_promises: FAIL <Type> sqlstate=<code|-> stage=<name> counts=<...>`
— never the exception message, DETAIL or a traceback.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg

logger = logging.getLogger("wa_team_promises")

_SQL_PATH = Path(__file__).resolve().parent / "sql" / "pro_local" / "team_promises.sql"

# Reuse the shipped, tested v1 regex catalog — same sys.path pattern as
# scripts/wa_mirror_intake_sweeper.py (self-inserted so this resolves
# regardless of the caller's PYTHONPATH, not just the documented CLI form).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))
from backend.services.wa_copilot.team_promises import (  # noqa: E402
    _PROMISE_PATTERNS_RE,
    _TEMPORAL_CUES,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.tg_gateway_verdict import extract_gateway_verdict  # noqa: E402

# B — Pro-local connection guard (explicit kwargs, no DSN/URL parsing)

PRO_LOCAL_CONNECT_KWARGS = {
    "host": "127.0.0.1", "port": 5432, "database": "nuzantara_dev", "user": "nuzantara",
}

# Cleared so libpq env vars can never override the kwargs above — round-2
# review on #7316 caught a DSN-string guard walkable via `?host=` or PGHOST.
_PG_ENV_VARS_TO_CLEAR = ("PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGSERVICE")


class EnvGuardError(RuntimeError):
    """Raised by _guard_pro_local_env — never carries an env value in str()."""


def _guard_pro_local_env() -> None:
    """Refuses if ANY `FLY_*` var is present, even empty — presence alone
    means this process runs (or is probed) under a Fly-graded environment,
    the one place Symbiosis Law 2 forbids this data from reaching."""
    if any(k.startswith("FLY_") for k in os.environ):
        raise EnvGuardError("fly_env_detected")


def _clear_pg_env() -> None:
    for var in _PG_ENV_VARS_TO_CLEAR:
        os.environ.pop(var, None)


# A — init-schema + catalog verification (columns, then both unique indexes)

# Single source of truth for EVERY column of both tables — name, Postgres
# type, NOT NULL — as declared in team_promises.sql (round-2 review: the
# round-1 contract covered only the ALTER-added columns, so a core column
# with the WRONG type, or missing outright, passed silently). A unit test
# asserts every column the SQL file declares appears here.
_REQUIRED_COLUMNS: dict[str, list[tuple[str, str, bool]]] = {
    "team_promises": [
        ("promise_id", "bigint", True), ("message_id", "bigint", True),
        ("conversation_id", "bigint", False), ("client_id", "bigint", False),
        ("promise_text", "text", True), ("promise_type", "text", False),
        ("due_at", "timestamp with time zone", False), ("resolved", "boolean", True),
        ("resolved_at", "timestamp with time zone", False),
        ("resolved_by_message_id", "bigint", False),
        ("created_at", "timestamp with time zone", True),
        ("thread_key", "text", False), ("team_member_email", "text", False),
        ("extractor_version", "text", False), ("resolution_kind", "text", False),
    ],
    "team_promise_candidates": [
        ("id", "bigint", True), ("message_id", "bigint", True),
        ("clause_idx", "integer", True), ("clause_hash", "text", True),
        ("promise_type", "text", True), ("cue", "text", False),
        ("due_at_hint", "text", False), ("status", "text", True),
        ("attempts", "integer", True), ("last_attempt_at", "timestamp with time zone", False),
        ("created_at", "timestamp with time zone", True),
        ("revised_at", "timestamp with time zone", False),
    ],
}

# Every identifier a SchemaMismatchError can carry — closed set, so the
# sanitized fail line can safely print `.identifier` without ever risking a
# caller-influenced string. Derived from _REQUIRED_COLUMNS so the two never drift.
_ALLOWED_SCHEMA_IDENTIFIERS = frozenset(
    {"uix_team_promises_msg_type", "uix_team_promise_candidates_msg_clause"}
    | {f"{table}.{col}" for table, cols in _REQUIRED_COLUMNS.items() for col, _, _ in cols}
)


class SchemaMismatchError(RuntimeError):
    """Carries ONLY a STATIC allowlisted identifier; str(exc) (the raw
    diagnostic) is never what _fail_line prints — only .identifier is."""

    def __init__(self, identifier: str, detail: str = ""):
        self.identifier = identifier if identifier in _ALLOWED_SCHEMA_IDENTIFIERS else "unknown"
        super().__init__(detail or identifier)


# pg_attribute, not information_schema: information_schema.data_type reads a
# DOMAIN over text as "text" (its base type), so a column retyped to an
# incompatible domain would pass silently. atttypid = <type>::regtype fails
# for a domain (its atttypid is the domain's OWN oid, never the base type's).
_COLUMN_CHECK_SQL = """
SELECT u.column_name,
       (a.attname IS NOT NULL
        AND a.atttypid = u.expected_type::regtype
        AND a.attnotnull = u.expected_notnull) AS ok
FROM unnest($2::text[], $3::text[], $4::boolean[]) AS u(column_name, expected_type, expected_notnull)
LEFT JOIN pg_attribute a
  ON a.attrelid = to_regclass('public.' || $1)::oid
 AND a.attnum > 0 AND NOT a.attisdropped AND a.attname = u.column_name
"""


async def verify_required_columns(conn, table: str) -> None:
    """Verifies name+exact-type(no domains)+NOT NULL for EVERY column of
    `table`, via pg_attribute inside the caller's transaction. Raises
    SchemaMismatchError('<table>.<column>') on the first mismatch found."""
    required = _REQUIRED_COLUMNS[table]
    names = [c[0] for c in required]
    types = [c[1] for c in required]
    notnulls = [c[2] for c in required]
    rows = await conn.fetch(_COLUMN_CHECK_SQL, table, names, types, notnulls)
    for row in rows:
        if not row["ok"]:
            identifier = f"{table}.{row['column_name']}"
            raise SchemaMismatchError(identifier, f"{identifier} missing or mistyped")


_INDEX_CHECK_SQL = """
SELECT ix.indisunique, ix.indisvalid, ix.indnkeyatts,
       ix.indpred IS NOT NULL AS has_predicate,
       ix.indexprs IS NOT NULL AS has_expr,
       (SELECT array_agg(a.attname ORDER BY o.ord)
        FROM unnest(ix.indkey) WITH ORDINALITY AS o(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = o.attnum
        WHERE o.ord <= ix.indnkeyatts) AS key_columns
FROM pg_index ix
JOIN pg_class i ON i.oid = ix.indexrelid
WHERE ix.indrelid = to_regclass('public.' || $1)::oid AND i.relname = $2
"""


async def verify_unique_index(conn, table: str, index: str, columns: list[str]) -> None:
    """Verifies `index` on `table` by OID+catalog, never by name alone —
    `CREATE UNIQUE INDEX IF NOT EXISTS` silently no-ops on a same-named
    index with a DIFFERENT definition. Raises SchemaMismatchError(index) on
    ANY mismatch, inside the DDL's own transaction, so it rolls back."""
    row = await conn.fetchrow(_INDEX_CHECK_SQL, table, index)
    if row is None:
        raise SchemaMismatchError(index, f"index {index} missing on {table} after init-schema")
    ok = (
        row["indisunique"] and row["indisvalid"]
        and not row["has_predicate"] and not row["has_expr"]
        and row["indnkeyatts"] == len(columns)
        and list(row["key_columns"] or []) == columns
    )
    if not ok:
        raise SchemaMismatchError(index, f"{index} exists with an incompatible definition")


_TABLES_TO_VERIFY = ("team_promises", "team_promise_candidates")
_UNIQUE_INDEXES_TO_VERIFY = (
    ("team_promises", "uix_team_promises_msg_type", ["message_id", "promise_type"]),
    ("team_promise_candidates", "uix_team_promise_candidates_msg_clause",
     ["message_id", "clause_idx"]),
)


async def run_init_schema(pool: asyncpg.Pool) -> None:
    ddl = _SQL_PATH.read_text()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(ddl)
            for table in _TABLES_TO_VERIFY:
                await verify_required_columns(conn, table)
            for table, index, columns in _UNIQUE_INDEXES_TO_VERIFY:
                await verify_unique_index(conn, table, index, columns)


# D — PR-2: scanner. Reads whatsapp_message_context (Node-runtime-maintained
# mirror, never ALTERed here, never written to), proposes candidates.
#
# No persisted watermark (REWORK — see module docstring). Every tick reads
# `hi = max(id)` of the eligible window ONCE, then walks an IN-TICK cursor
# from 0 to that `hi` — the FULL 30-day window, every time. `hi` fixed at
# tick start (never re-read mid-tick) is what makes the tick terminate
# against a live-growing table.

STATE_DIR = Path.home() / ".cell-bridge-state"
_SCAN_LOCK_FILE = STATE_DIR / "wa_team_promises_scan.lock"
_SCAN_METRICS_FILE = STATE_DIR / "wa_team_promises_scan_metrics.json"
_SCAN_BATCH_SIZE_DEFAULT = 200
_SCAN_LOOKBACK_DAYS = 30

_WITA = ZoneInfo("Asia/Makassar")

# Shared by both queries below so the 30-day floor and eligibility rule can
# never drift between the ceiling read and the batch read.
_SCAN_ELIGIBLE_WHERE = f"""
    direction = 'outbound'
    AND created_at >= now() - interval '{_SCAN_LOOKBACK_DAYS} days'
    AND COALESCE(NULLIF(body, ''), NULLIF(message_text, '')) IS NOT NULL
"""

_SCAN_HI_SQL = f"SELECT max(id) FROM whatsapp_message_context WHERE {_SCAN_ELIGIBLE_WHERE}"

_SCAN_SELECT_SQL = f"""
SELECT id, COALESCE(NULLIF(body, ''), NULLIF(message_text, '')) AS body
  FROM whatsapp_message_context
 WHERE {_SCAN_ELIGIBLE_WHERE}
   AND id > $1
   AND id <= $2
 ORDER BY id ASC
 LIMIT $3
"""

# Revises an existing UNJUDGED row in place when its clause text actually
# changed (`clause_hash IS DISTINCT FROM`); a judged_true/judged_false/
# quarantined row is NEVER rewritten — the WHERE guards that. `attempts`/
# `last_attempt_at` reset because the judge has not yet seen this new text.
# `RETURNING (xmax = 0) AS inserted` (no row at all when the WHERE excludes
# the conflict) lets the caller count inserted vs revised separately.
_CANDIDATE_UPSERT_SQL = """
INSERT INTO team_promise_candidates
  (message_id, clause_idx, clause_hash, promise_type, cue, due_at_hint)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (message_id, clause_idx) DO UPDATE SET
  clause_hash = EXCLUDED.clause_hash,
  promise_type = EXCLUDED.promise_type,
  cue = EXCLUDED.cue,
  due_at_hint = EXCLUDED.due_at_hint,
  attempts = 0,
  last_attempt_at = NULL,
  revised_at = now()
 WHERE team_promise_candidates.status = 'unjudged'
   AND team_promise_candidates.clause_hash IS DISTINCT FROM EXCLUDED.clause_hash
RETURNING (xmax = 0) AS inserted
"""

# Digest counts, read fresh from Postgres at send time (see _send_scan_digest).
# REWORK B2: the window is YESTERDAY's full local day, not "since midnight" —
# a completed day has a fixed total, which is what makes "send it once" work.
_DIGEST_COUNTS_SQL = """
SELECT
  count(*) FILTER (WHERE created_at >= $1 AND created_at < $2) AS created_yesterday,
  count(*) FILTER (WHERE revised_at >= $1 AND revised_at < $2) AS revised_yesterday,
  count(*) FILTER (WHERE status = 'unjudged') AS unjudged
FROM team_promise_candidates
"""

# Clause boundaries: sentence punctuation, `;` and newline (discarded — the
# predecessor's round-2 review flagged both as missing), plus a conjunction
# boundary per language (EN/ID/IT: but/however/tapi/tetapi/namun/ma/pero/però,
# and — REWORK A3 — and/dan/serta/e). The conjunction stays attached to the
# clause it introduces — catalog patterns aren't string-anchored, so a
# leading "but"/"tapi"/"and"/"e" never blocks a match. Over-splitting is safe
# here: this is a PROPOSER only (no dedup, no past-tense discard — the judge
# in PR-3 decides both), so an extra clause just gives it one more thing to
# rule on, never a lost one.
#
# REWORK B3: the right boundary is `(?=\s)` (an actual whitespace char after
# the word), not `\b` — a bare word boundary also fires between a word char
# and adjacent punctuation, so "e-mail" and "e' pronto" used to split and
# lose the due hint that followed. The left side needs no separate boundary:
# `\s+` itself already requires the PRECEDING char to be literal whitespace,
# which already excludes "candidate"/"Android"/"che"/"sede" (the conjunction
# there is never preceded by whitespace) without a `\b`.
#
# The period alternative is narrowed the same way, for the same reason: a
# bare `.` split treated "e.g." as two sentence terminators (splitting "e"
# from "g" from what follows), which is how it lost a due hint on the OTHER
# side of it too. `(?![a-z])` skips a period immediately followed by a
# lowercase letter (still mid-abbreviation, e.g. the dot between "e" and
# "g"); `(?<!e\.g)` skips the period immediately AFTER "e.g" itself (its
# trailing dot). This is a narrow, named allowlist for the one abbreviation
# the addendum's guilt case names — not general abbreviation detection.
_CLAUSE_SPLIT_RE = re.compile(
    r"[!?;\n]+|(?<!e\.g)\.(?![a-z])|\s+(?=(?:but|however|tapi|tetapi|namun|ma|per[oò]"
    r"|and|dan|serta|e)\s)",
    re.IGNORECASE,
)


def _split_clauses(body: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT_RE.split(body) if c and c.strip()]


def _match_clause(clause: str) -> tuple[str, str, str | None] | None:
    """First catalog pattern that matches `clause` -> (promise_type, cue,
    due_at_hint). `cue` is the matched substring itself: every pattern in
    `_PROMISE_PATTERNS_RE` is a closed keyword vocabulary with no open
    capture group, so it can never carry a name, phone or client id.
    `due_at_hint` is the temporal keyword matched in the SAME clause (else
    None) — stored as the label only, never resolved to a timestamp here;
    that stays the judge's call in PR-3."""
    for promise_type, pattern in _PROMISE_PATTERNS_RE:
        m = pattern.search(clause)
        if not m:
            continue
        due_at_hint = None
        for cue_pattern, _hours in _TEMPORAL_CUES:
            cue_m = cue_pattern.search(clause)
            if cue_m:
                due_at_hint = cue_m.group(0).lower()
                break
        return promise_type, m.group(0).lower(), due_at_hint
    return None


def _hash_clause(clause: str) -> str:
    normalized = " ".join(clause.split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ScanMetrics:
    """Every field is a bare int — the digest line is built ONLY from these,
    so a clause, name, phone or client id has no path into it. A structural
    test asserts every field stays int-typed."""

    scanned: int = 0
    clauses: int = 0
    candidates_new: int = 0
    candidates_revised: int = 0
    wall_ms: int = 0


def _save_scan_metrics(metrics: ScanMetrics) -> None:
    """Local observability file, same convention as other Pro organs
    (e.g. wa_mirror_intake_sweeper.py's metrics-json). Never read back by
    this file — Zero/a future dashboard reads it directly."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _SCAN_METRICS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({**asdict(metrics), "ts": time.time()}))
    tmp.replace(_SCAN_METRICS_FILE)


def _acquire_scan_lock_or_none() -> int | None:
    """mkdir/flock-free sibling of _acquire_lock_or_exit in
    wa_mirror_intake_sweeper.py — returns None instead of exiting the
    process, so the caller can still log+return 0 (this file's contract:
    every path prints a `wa_team_promises: ...` line, cron never sees a
    bare silent exit)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(_SCAN_LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        os.close(fd)
        return None


def _release_scan_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        pass


async def run_scan_batch(
    pool: asyncpg.Pool, *, cursor: int, hi: int, batch_size: int, dry_run: bool, metrics: ScanMetrics,
) -> int:
    """One batch of the full `(0, hi]` rescan, `hi` fixed by the caller at
    tick start (id-cursor SELECT, never OFFSET — the predecessor paged by
    OFFSET against a table new rows keep arriving into, which is how it
    refetched the same 200 rows for 81 minutes). Returns the new cursor:
    either the max id actually fetched (strictly > `cursor`, since every row
    satisfies `id > cursor`), or `hi` itself when nothing eligible remains in
    `(cursor, hi]` — both are strictly forward, so the caller's
    `while cursor < hi` loop always terminates."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SCAN_SELECT_SQL, cursor, hi, batch_size)
    if not rows:
        return hi
    metrics.scanned += len(rows)

    candidates: list[tuple[int, int, str, str, str, str | None]] = []
    for row in rows:
        body = row["body"]
        for idx, clause in enumerate(_split_clauses(body)):
            match = _match_clause(clause)
            if match is None:
                continue
            promise_type, cue, due_at_hint = match
            metrics.clauses += 1
            candidates.append(
                (int(row["id"]), idx, _hash_clause(clause), promise_type, cue, due_at_hint)
            )

    new_cursor = max(int(r["id"]) for r in rows)
    if candidates and not dry_run:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for c in candidates:
                    result = await conn.fetchrow(_CANDIDATE_UPSERT_SQL, *c)
                    if result is None:
                        continue  # unchanged text on an unjudged row, or a judged/quarantined row
                    if result["inserted"]:
                        metrics.candidates_new += 1
                    else:
                        metrics.candidates_revised += 1
    elif candidates:
        # dry-run: nothing is written, so insert-vs-revise can't be told
        # apart without touching the DB — report every match found as a bare
        # would-be-candidate count; verification only needs scanned/clauses.
        metrics.candidates_new += len(candidates)
    return new_cursor


async def run_scan(pool: asyncpg.Pool, *, batch_size: int, dry_run: bool) -> ScanMetrics:
    """Every tick rescans the FULL 30-day window, `cursor` from 0 up to a
    `hi` read ONCE here (never inside the loop, or a live-growing table would
    never let the tick end). `--dry-run` walks the identical read-only path
    and differs only in run_scan_batch's own write guard — there is no
    separate watermark state to keep in sync with it anymore."""
    t0 = time.monotonic()
    metrics = ScanMetrics()
    async with pool.acquire() as conn:
        hi = await conn.fetchval(_SCAN_HI_SQL)
    if hi is not None:
        cursor = 0
        while cursor < hi:
            cursor = await run_scan_batch(
                pool, cursor=cursor, hi=hi, batch_size=batch_size, dry_run=dry_run, metrics=metrics,
            )
    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


def _wita_yesterday_window() -> tuple[datetime, datetime, str]:
    """Yesterday's full local (Asia/Makassar/WITA) day as `[start, end)`
    UTC-aware timestamps, plus yesterday's `YYYY-MM-DD` label.

    REWORK B2: A4's premise was false — `tg_notify` dedups BEFORE spooling,
    so a per-day key on a "since midnight, growing all day" count only ever
    let the first tick or two of the day through, each showing a stale
    near-zero total (simulated: 6 records over 3 days, all "today 0", against
    a true ~120/day). A COMPLETED day has a FIXED total, so reporting
    yesterday's window makes the CONTENT correct — but the key alone does
    not make the CADENCE exactly-once: calling this every tick all day would
    still let tg_notify's own ladder open a SECOND opportunity ~6h after the
    first hit (its window starts at `TG_DEDUP_HOURS`, same key, same day).
    See `_is_first_digest_opportunity_of_the_day`, which is what actually
    restricts the attempt to the midnight hour and removes that second
    opportunity — this function only computes WHAT to report, not WHEN."""
    now_wita = datetime.now(_WITA)
    today_midnight_wita = now_wita.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_midnight_wita = today_midnight_wita - timedelta(days=1)
    return (
        yesterday_midnight_wita.astimezone(timezone.utc),
        today_midnight_wita.astimezone(timezone.utc),
        yesterday_midnight_wita.strftime("%Y-%m-%d"),
    )


def _is_first_digest_opportunity_of_the_day(now_wita: datetime) -> bool:
    """True only during the midnight WITA hour (00:00-00:59).

    This — not a persisted "already sent today" flag — is what makes the
    digest send exactly once per day: `tg_notify`'s own dedup on the
    per-yesterday-date key only needs to collapse however many ticks land
    inside THIS hour into one spooled record (its window starts well past
    one cron interval, so the first hit in the hour suppresses the rest of
    it); calling `notify()` again later the same day — at 06:00, say — would
    hand the ladder a SECOND chance to open (its window keeps growing, but
    it always starts a new day's clock from the first hit, wherever that
    lands), which is exactly the double-send the gate's simulation caught.
    Restricting the ATTEMPT to this one hour removes that chance instead of
    hoping the ladder absorbs it. No state file: a missed 00:00 tick is
    covered by 00:15/00:30/00:45 landing in the same hour."""
    return now_wita.hour == 0


async def _fetch_digest_counts(
    pool: asyncpg.Pool, start_utc: datetime, end_utc: datetime,
) -> tuple[int, int, int]:
    """Candidates created/revised during yesterday's full local day, plus the
    CURRENT unjudged total — read fresh from Postgres at SEND time, never
    carried over from this tick's own counters. See _send_scan_digest's
    REWORK note."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_DIGEST_COUNTS_SQL, start_utc, end_utc)
    return int(row["created_yesterday"]), int(row["revised_yesterday"]), int(row["unjudged"])


def _digest_line(candidates_yesterday: int, revised_yesterday: int, unjudged_total: int) -> str:
    """Counts only, enforced — not just by convention. A caller that ever
    tried to pass a clause, name, phone or client id here (even embedded in
    a string) gets a TypeError before it can reach the gateway."""
    if not all(isinstance(x, int) for x in (candidates_yesterday, revised_yesterday, unjudged_total)):
        raise TypeError("wa_team_promises: _digest_line accepts int counts only")
    return (
        f"promises: yesterday {candidates_yesterday} "
        f"(revised {revised_yesterday}), unjudged {unjudged_total}"
    )


# Absolute python3 candidates the gateway is spawned with (W108 — the alarm
# must not share the failure mode of a possibly-broken venv PATH resolution),
# same list as scripts/wa_mirror_intake_sweeper.py::_PY3_CANDIDATES.
_PY3_CANDIDATES: tuple[str, ...] = (
    "/usr/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
)


def _resolve_py3() -> str:
    for candidate in _PY3_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return sys.executable


def _send_scan_digest(
    candidates_yesterday: int, revised_yesterday: int, unjudged_total: int, *, yesterday_label: str,
) -> None:
    """Best-effort, never raises — same contract as
    wa_mirror_intake_sweeper.py::_tg_notify. The message is built ONLY from
    the three int counts passed in; nothing else reaches this call. The
    caller only invokes this during the midnight WITA hour (see
    `_is_first_digest_opportunity_of_the_day`) — `tg_notify`'s own dedup
    ladder on `wa-team-promises:<yesterday>` then collapses however many
    ticks land in that hour into exactly one spooled record. No local state
    file: a missed 00:00 tick is covered by 00:15/00:30/00:45."""
    try:
        gateway = Path(__file__).resolve().parent / "tg_notify.py"
        if not gateway.is_file():
            logger.warning("wa_team_promises: tg_notify.py missing at %s", gateway)
            return
        text = _digest_line(candidates_yesterday, revised_yesterday, unjudged_total)
        res = subprocess.run(
            [_resolve_py3(), str(gateway), "--tier", "digest",
             "--source", "wa-team-promises-scan",
             "--dedup-key", f"wa-team-promises:{yesterday_label}",
             "--", text],
            capture_output=True, text=True, timeout=30,
        )
        verdict = extract_gateway_verdict(res.stderr)
        logger.info("wa_team_promises: tg_notify verdict=%s rc=%s", verdict, res.returncode)
    except Exception as exc:  # never raises
        # REWORK A6: str(exc) could carry gateway stderr/argv text — route it
        # through the same sanitizer every other error path in this file uses.
        logger.warning(_fail_line(exc, "digest"))


# C — errors never carry data, and neither does argument/log-level parsing

def _fail_line(exc: BaseException, stage: str, counts: dict[str, int] | None = None) -> str:
    sqlstate = getattr(exc, "sqlstate", None) or "-"
    counts_str = "n/a" if counts is None else ",".join(f"{k}={v}" for k, v in counts.items())
    line = f"wa_team_promises: FAIL {type(exc).__name__} sqlstate={sqlstate} stage={stage} counts={counts_str}"
    identifier = getattr(exc, "identifier", None)
    return line if identifier is None else f"{line} identifier={identifier}"


_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class _ArgSyntaxError(RuntimeError):
    """Raised in place of argparse's own error() — never carries the raw
    argv token argparse's default message would (round-1 review #3)."""


class _SanitizingArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # message may embed raw argv — never used
        raise _ArgSyntaxError("argparse_error")


async def cli_main(argv: list[str] | None = None) -> int:
    parser = _SanitizingArgumentParser(prog="wa_team_promises")
    parser.add_argument("--init-schema", action="store_true",
                         help="Apply scripts/sql/pro_local/team_promises.sql "
                              "(idempotent) and verify columns + both unique indexes, then exit.")
    parser.add_argument("--scan", action="store_true",
                         help="Scan whatsapp_message_context (outbound, last 30 days) for "
                              "promise-catalog clauses and insert unjudged "
                              "team_promise_candidates rows. Judge lands in PR-3.")
    parser.add_argument("--dry-run", action="store_true",
                         help="With --scan: compute counts only — no candidate insert/revise, "
                              "no digest.")
    parser.add_argument("--batch-size", type=int, default=_SCAN_BATCH_SIZE_DEFAULT)
    parser.add_argument("--log-level", default="INFO")
    try:
        args = parser.parse_args(argv)
    except _ArgSyntaxError as exc:
        sys.stderr.write(_fail_line(exc, "argparse") + "\n")
        return 2
    log_level = args.log_level if args.log_level in _LOG_LEVELS else "INFO"
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    if args.init_schema and args.scan:
        sys.stderr.write(_fail_line(_ArgSyntaxError("multiple_modes"), "argparse") + "\n")
        return 2
    if not args.init_schema and not args.scan:
        sys.stderr.write(_fail_line(_ArgSyntaxError("missing_mode"), "argparse") + "\n")
        return 2

    stage = "env_guard"
    try:
        _guard_pro_local_env()
    except EnvGuardError as exc:
        sys.stderr.write(_fail_line(exc, stage) + "\n")
        return 2
    _clear_pg_env()

    try:
        stage = "connect"
        pool = await asyncpg.create_pool(
            **PRO_LOCAL_CONNECT_KWARGS, min_size=1, max_size=1,
            statement_cache_size=0, command_timeout=60,
        )
        try:
            if args.init_schema:
                stage = "init_schema"
                await run_init_schema(pool)
                sys.stdout.write("wa_team_promises: init-schema OK\n")
            else:
                stage = "scan"
                lock_fd = None if args.dry_run else _acquire_scan_lock_or_none()
                if not args.dry_run and lock_fd is None:
                    sys.stdout.write("wa_team_promises: scan SKIPPED another instance holds the lock\n")
                    return 0
                # REWORK A5: count, metrics write and digest enqueue all
                # happen BEFORE the unlock (moved inside this try/finally) —
                # they used to run after the lock was already released, so
                # two overlapping ticks could race each other's metrics.tmp
                # rename and interleave their digest counts.
                try:
                    metrics = await run_scan(pool, batch_size=args.batch_size, dry_run=args.dry_run)
                    if not args.dry_run:
                        stage = "digest"
                        _save_scan_metrics(metrics)
                        # REWORK B2: the digest is only ATTEMPTED during the
                        # midnight WITA hour — see
                        # _is_first_digest_opportunity_of_the_day for why
                        # that (not the dedup key alone) is what makes the
                        # cadence exactly-once-per-day.
                        if _is_first_digest_opportunity_of_the_day(datetime.now(_WITA)):
                            start_utc, end_utc, yesterday_label = _wita_yesterday_window()
                            candidates_yesterday, revised_yesterday, unjudged_total = (
                                await _fetch_digest_counts(pool, start_utc, end_utc)
                            )
                            _send_scan_digest(
                                candidates_yesterday, revised_yesterday, unjudged_total,
                                yesterday_label=yesterday_label,
                            )
                finally:
                    if lock_fd is not None:
                        _release_scan_lock(lock_fd)
                sys.stdout.write(
                    f"wa_team_promises: scan OK scanned={metrics.scanned} "
                    f"clauses={metrics.clauses} candidates_new={metrics.candidates_new} "
                    f"candidates_revised={metrics.candidates_revised}\n"
                )
        finally:
            await pool.close()
        return 0
    except Exception as exc:
        sys.stderr.write(_fail_line(exc, stage) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
