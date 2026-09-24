"""T3 promise extractor — PRO-LOCAL (owner ruling 2026-09-25, Symbiosis Law 2:
data never leaves Pro). Reads whatsapp_message_context, writes team_promises,
both local to Pro's nuzantara_dev. Reuses the v1 regex catalog
(backend.services.wa_copilot.team_promises) but fixes v1 defect 4a: a
past-tense match ("already sent" / "sudah kirim" / "gia inviato") is a
FULFILMENT, never stored as a promise.

Pro's whatsapp_message_context has no sender_role/conversation_id (mig-200
columns, Fly-only) — the team side of a thread is `direction = 'outbound'`
(spec finding #3), and the thread key is computed here, not read from a
conversations table Pro doesn't have.

CLI:
    apps/backend-rag/.venv/bin/python scripts/wa_team_promises.py [--dry-run]
      [--limit N] [--batch-size 200] [--metrics-json PATH] [--log-level INFO]

Run with PYTHONPATH=apps/backend-rag so the v1 catalog import resolves.
Dry-run touches ONLY whatsapp_message_context (read-only) — it never
queries or writes team_promises, so it works before the migration lands.
Logs and the digest line carry COUNTS ONLY: no body, no name, no phone.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import fcntl
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))
from backend.services.wa_copilot.team_promises import (  # noqa: E402
    _PROMISE_PATTERNS_RE,
    _TEMPORAL_CUES,
)

logger = logging.getLogger("wa_team_promises")

PRO_EXTRACTOR_VERSION = "pro-local-v1-2026-09-25"
BATCH_SIZE_DEFAULT = 200
PROMISE_TEXT_WINDOW = 200  # max chars stored around the regex match

# D6 (coordinator decision, PR body flags it as owner-changeable): a
# message with no temporal cue defaults to message time + 48h, instead of
# v1's NULL (which meant 83% of promises never went overdue).
DEFAULT_DUE_AT_HOURS = 48

# v1 defect 4a: the same regex alternation carries both a future/present
# form ("akan kirim" / "will send") and a past-tense one ("sudah kirim" /
# "already sent" / "gia inviato") for the SAME promise_type, and v1 stored
# both as promises. A past-tense MATCH is a report of work already done —
# checked against the matched span only (never the whole body), so an
# unrelated "already" elsewhere in the message can't misfire this.
PAST_TENSE_RE = re.compile(
    r"\b(sudah|telah|already|gi[aà]|have\s+(?:sent|submitted|processed|checked))\b",
    re.IGNORECASE | re.UNICODE,
)

STATE_DIR = Path.home() / ".cell-bridge-state"
LOCK_FILE = STATE_DIR / "wa_team_promises.lock"
WATERMARK_FILE = STATE_DIR / "wa_team_promises_last_id.txt"
METRICS_FILE_DEFAULT = STATE_DIR / "wa_team_promises_last_metrics.json"
_REPO_ROOT = Path(__file__).resolve().parent.parent

_PY3_CANDIDATES: tuple[str, ...] = (
    "/usr/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
)


@dataclass
class ExtractMetrics:
    total_scanned: int = 0
    candidate_messages: int = 0
    promises_created: int = 0
    promises_skipped_conflict: int = 0
    fulfilments_skipped: int = 0  # past-tense matches — never stored (4a)
    with_due_at_cue: int = 0
    with_due_at_default: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    open_total: int | None = None
    overdue_total: int | None = None
    errors: int = 0
    wall_ms: int = 0


def _thread_key(team_member_phone: str | None, chat_jid: str | None,
                 counterpart_phone: str | None, counterpart_lid: str | None) -> str | None:
    """md5(team_member_phone|chat_jid-or-counterpart) — spec §2.3. No ALTER
    on whatsapp_message_context, so this key lives only in team_promises."""
    counterpart = chat_jid or counterpart_phone or counterpart_lid
    if not team_member_phone or not counterpart:
        return None
    raw = f"{team_member_phone}|{counterpart}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _infer_due_at(body: str, base_dt: _dt.datetime) -> tuple[_dt.datetime, bool]:
    """Returns (due_at, from_cue). from_cue=False means the D6 default fired."""
    for pattern, hours in _TEMPORAL_CUES:
        if pattern.search(body):
            return base_dt + _dt.timedelta(hours=hours), True
    return base_dt + _dt.timedelta(hours=DEFAULT_DUE_AT_HOURS), False


def _extract_window(body: str, match: re.Match[str], window: int = PROMISE_TEXT_WINDOW) -> str:
    start = max(0, match.start() - window // 2)
    end = min(len(body), match.end() + window // 2)
    snippet = body[start:end].strip()
    return snippet[:window].rstrip() if len(snippet) > window else snippet


@dataclass(slots=True)
class _Candidate:
    message_id: int
    conversation_id: None
    client_id: int | None
    thread_key: str | None
    team_member_email: str | None
    promise_text: str
    promise_type: str
    due_at: _dt.datetime
    from_cue: bool


def find_candidates_in_message(
    *, message_id: int, client_id: int | None, team_member_phone: str | None,
    team_member_email: str | None, chat_jid: str | None, counterpart_phone: str | None,
    counterpart_lid: str | None, body: str, base_dt: _dt.datetime,
) -> tuple[list[_Candidate], int]:
    """Returns (promise candidates, fulfilments_skipped_count) for one message."""
    seen_types: set[str] = set()
    out: list[_Candidate] = []
    fulfilments = 0
    tkey = _thread_key(team_member_phone, chat_jid, counterpart_phone, counterpart_lid)
    for ptype, pat in _PROMISE_PATTERNS_RE:
        if ptype in seen_types:
            continue
        m = pat.search(body)
        if not m:
            continue
        seen_types.add(ptype)
        if PAST_TENSE_RE.search(m.group(0)):
            fulfilments += 1
            continue
        due_at, from_cue = _infer_due_at(body, base_dt)
        out.append(_Candidate(
            message_id=message_id,
            conversation_id=None,
            client_id=client_id,
            thread_key=tkey,
            team_member_email=team_member_email,
            promise_text=_extract_window(body, m),
            promise_type=ptype,
            due_at=due_at,
            from_cue=from_cue,
        ))
    return out, fulfilments


async def _resolve_seed(conn: asyncpg.Connection) -> int:
    """First-run watermark: 30 days back, so the gate has history on day 1
    (spec §5 backfill note, ~372 candidate messages measured 2026-09-25)."""
    row = await conn.fetchrow(
        "SELECT COALESCE(MIN(id) - 1, 0) AS seed FROM whatsapp_message_context "
        "WHERE message_date >= now() - interval '30 days'"
    )
    return int(row["seed"]) if row and row["seed"] is not None else 0


def _load_watermark() -> int | None:
    if not WATERMARK_FILE.exists():
        return None
    try:
        return int(WATERMARK_FILE.read_text().strip() or "0")
    except (ValueError, OSError):
        return None


def _save_watermark(value: int) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    tmp = WATERMARK_FILE.with_suffix(".tmp")
    tmp.write_text(str(int(value)))
    tmp.replace(WATERMARK_FILE)


def _acquire_lock_or_exit() -> int:
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("another instance running, skipping this tick")
        os.close(fd)
        sys.exit(0)


def _resolve_py3() -> str:
    for candidate in _PY3_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return sys.executable


def _digest_line(metrics: ExtractMetrics) -> str:
    """Counts only — no promise_text, thread_key or team_member_email ever
    touches this string. Kept as its own function so a test can assert that
    directly, independent of the DB-backed tick that produces `metrics`."""
    return (
        f"promises: new {metrics.promises_created} "
        f"open {metrics.open_total} overdue {metrics.overdue_total}"
    )


def _tg_notify_digest(text: str) -> bool:
    """Counts-only digest line, per-line dedup hash (no explicit --dedup-key
    = tg_notify hashes source+text itself). Never a body, window or name."""
    try:
        gateway = _REPO_ROOT / "scripts" / "tg_notify.py"
        if not gateway.is_file():
            logger.warning("tg_notify.py missing at %s", gateway)
            return False
        res = subprocess.run(
            [_resolve_py3(), str(gateway), "--tier", "digest",
             "--source", "wa-team-promises", "--", text],
            capture_output=True, text=True, timeout=30,
        )
        return res.returncode == 0
    except Exception as exc:  # never raises — a gateway hiccup must not fail the tick
        logger.warning("tg_notify failed: %s", exc)
        return False


async def run_tick(pool: asyncpg.Pool, *, apply: bool, limit: int | None,
                    batch_size: int) -> ExtractMetrics:
    t0 = time.monotonic()
    metrics = ExtractMetrics()
    async with pool.acquire() as conn:
        # Both apply and dry-run read the same watermark (or the 30-day seed
        # if unset) so `--dry-run` previews exactly what the next real tick
        # would scan. Only `apply` persists it back (below).
        watermark = _load_watermark()
        if watermark is None:
            watermark = await _resolve_seed(conn)
            logger.info("first run, watermark seeded to id=%d", watermark)

        offset_id = watermark
        remaining = limit
        max_id_seen = watermark
        while True:
            fetch = batch_size if remaining is None else min(batch_size, remaining)
            if fetch <= 0:
                break
            rows = await conn.fetch(
                """
                SELECT id, client_id, team_member_phone, team_member_email,
                       chat_jid, counterpart_phone, counterpart_lid,
                       COALESCE(message_date, created_at) AS base_dt,
                       COALESCE(body, message_text) AS body
                FROM whatsapp_message_context
                WHERE direction = 'outbound'
                  AND id > $1
                  AND COALESCE(body, message_text) IS NOT NULL
                  AND length(COALESCE(body, message_text)) > 3
                ORDER BY id
                LIMIT $2
                """,
                offset_id, fetch,
            )
            if not rows:
                break
            metrics.total_scanned += len(rows)

            insert_rows: list[tuple] = []
            for r in rows:
                max_id_seen = max(max_id_seen, r["id"])
                candidates, fulfilments = find_candidates_in_message(
                    message_id=r["id"], client_id=r["client_id"],
                    team_member_phone=r["team_member_phone"],
                    team_member_email=r["team_member_email"],
                    chat_jid=r["chat_jid"], counterpart_phone=r["counterpart_phone"],
                    counterpart_lid=r["counterpart_lid"], body=r["body"],
                    base_dt=r["base_dt"],
                )
                metrics.fulfilments_skipped += fulfilments
                if candidates:
                    metrics.candidate_messages += 1
                for c in candidates:
                    insert_rows.append(c)
                    metrics.by_type[c.promise_type] = metrics.by_type.get(c.promise_type, 0) + 1
                    if c.from_cue:
                        metrics.with_due_at_cue += 1
                    else:
                        metrics.with_due_at_default += 1

            if apply and insert_rows:
                async with conn.transaction():
                    for c in insert_rows:
                        result = await conn.execute(
                            """
                            INSERT INTO team_promises
                              (message_id, conversation_id, client_id, thread_key,
                               team_member_email, promise_text, promise_type,
                               due_at, extractor_version)
                            VALUES ($1, NULL, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (message_id, promise_type) DO NOTHING
                            """,
                            c.message_id, c.client_id, c.thread_key, c.team_member_email,
                            c.promise_text, c.promise_type, c.due_at, PRO_EXTRACTOR_VERSION,
                        )
                        if result.endswith(" 1"):
                            metrics.promises_created += 1
                        else:
                            metrics.promises_skipped_conflict += 1
            elif insert_rows:
                metrics.promises_created += len(insert_rows)

            offset_id = max_id_seen
            if remaining is not None:
                remaining -= len(rows)

        if apply and max_id_seen > watermark:
            _save_watermark(max_id_seen)

        if apply:
            row = await conn.fetchrow(
                "SELECT count(*) FILTER (WHERE resolved = false) AS open_total, "
                "count(*) FILTER (WHERE resolved = false AND due_at < now()) AS overdue_total "
                "FROM team_promises"
            )
            metrics.open_total = int(row["open_total"])
            metrics.overdue_total = int(row["overdue_total"])

    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


def _build_dsn() -> str:
    for env in ("WA_TEAM_PROMISES_DATABASE_URL", "DATABASE_URL"):
        val = os.environ.get(env)
        if val:
            return val
    return "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wa_team_promises")
    parser.add_argument("--dry-run", action="store_true",
                         help="Scan + count only. Never touches team_promises "
                              "(works even before the migration lands).")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--metrics-json", default=str(METRICS_FILE_DEFAULT))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level,
                         format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    apply = not args.dry_run
    lock_fd = _acquire_lock_or_exit() if apply else None
    try:
        pool = await asyncpg.create_pool(
            dsn=_build_dsn(), min_size=1, max_size=3,
            statement_cache_size=0, command_timeout=60,
        )
        try:
            metrics = await run_tick(
                pool, apply=apply, limit=args.limit, batch_size=args.batch_size,
            )
        finally:
            await pool.close()

        payload = asdict(metrics)
        payload["version"] = PRO_EXTRACTOR_VERSION
        payload["apply"] = apply
        payload["ts"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        logger.info("tick done (counts only): %s", payload)

        STATE_DIR.mkdir(exist_ok=True)
        tmp = Path(args.metrics_json).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str))
        tmp.replace(args.metrics_json)

        if apply:
            _tg_notify_digest(_digest_line(metrics))
        return 0
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
