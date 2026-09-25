"""T3 promise extractor — PRO-LOCAL (owner ruling 2026-09-25, Symbiosis Law 2:
data never leaves Pro). Reads whatsapp_message_context, writes team_promises,
both local to Pro's nuzantara_dev.

Round 1 (after codex BLOCK on PR #7316): the schema left migrations_v2 (see
scripts/sql/pro_local/team_promises.sql's own header for why); classification
is now regex-candidate + local-judge, not regex alone — the v1 catalog
(backend.services.wa_copilot.team_promises) only proposes clause-scoped
candidates, and Pro Ollama qwen3.5:9b decides `future_commitment_by_sender`,
same client pattern as the existing `wa-mirror-attention-classifier.py`
(ollama_classify, :158-192) — urllib.request to localhost:11434/api/generate,
think:false. Pro's whatsapp_message_context has no sender_role/
conversation_id (mig-200 columns, Fly-only) — the team side of a thread is
`direction = 'outbound'`.

CLI:
    apps/backend-rag/.venv/bin/python scripts/wa_team_promises.py --init-schema
    apps/backend-rag/.venv/bin/python scripts/wa_team_promises.py [--dry-run]
      [--limit N] [--batch-size 200] [--metrics-json PATH] [--log-level INFO]

Run with PYTHONPATH=apps/backend-rag so the v1 catalog import resolves.
DSN is WA_TEAM_PROMISES_DSN ONLY (no DATABASE_URL fallback) and is refused
before any connection attempt if it is not the local Pro DB (see
_guard_local_dsn). Every error path prints ONLY
`wa_team_promises: FAIL <Type> sqlstate=<code|-> stage=<name> counts=...` —
never the exception message, DETAIL or a traceback (cron-runner.sh forwards
stderr's tail to Telegram on a nonzero exit). Logs and the digest line carry
COUNTS ONLY: no body, name or phone.
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
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))
from backend.services.wa_copilot.team_promises import (  # noqa: E402
    _PROMISE_PATTERNS_RE,
    _TEMPORAL_CUES,
)

logger = logging.getLogger("wa_team_promises")

PRO_EXTRACTOR_VERSION = "pro-local-v2-2026-09-25"
BATCH_SIZE_DEFAULT = 200
PROMISE_TEXT_WINDOW = 200  # max chars stored per candidate clause
BACKFILL_DAYS = 30

# D6 (coordinator decision, PR body flags it as owner-changeable): a
# judged-true candidate with no temporal cue defaults to message time + 48h.
DEFAULT_DUE_AT_HOURS = 48

# Past-tense markers, checked against the WHOLE CLAUSE (round-0 bug: checking
# only the narrow regex match missed "sudah"/"telah" sitting just before the
# matched verb phrase in the same clause — "sudah saya cek" matches the
# tense-neutral ID "check" pattern on "saya cek" alone).
PAST_TENSE_RE = re.compile(
    r"\b(sudah|telah|already|gi[aà]|have\s+(?:sent|submitted|processed|checked))\b",
    re.IGNORECASE | re.UNICODE,
)

# Clause splitter: sentence enders, the ellipsis character, and conjunctions
# (id/en/it) — "already sent … I will send tomorrow" must split into two
# clauses so the past one is dropped WITHOUT marking "send" as already seen
# and losing the genuine future one right after it (round-0 bug #2).
CLAUSE_SPLIT_RE = re.compile(r"[.!?\n]+|…|\b(?:but|and|dan|tapi|e|ma)\b", re.IGNORECASE)

STATE_DIR = Path.home() / ".cell-bridge-state"
LOCK_FILE = STATE_DIR / "wa_team_promises.lock"
WATERMARK_FILE = STATE_DIR / "wa_team_promises_last_id.txt"
METRICS_FILE_DEFAULT = STATE_DIR / "wa_team_promises_last_metrics.json"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SQL_PATH = Path(__file__).resolve().parent / "sql" / "pro_local" / "team_promises.sql"

_PY3_CANDIDATES: tuple[str, ...] = (
    "/usr/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
)

# Same client as scripts/wa-mirror-attention-classifier.py's ollama_classify.
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_TIMEOUT_S = 30


# ---------------------------------------------------------------------------
# B — Pro-local DSN, enforced before any connection attempt
# ---------------------------------------------------------------------------

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", None}  # None = unix-socket netloc


class DsnGuardError(RuntimeError):
    """Raised by _guard_local_dsn — never carries the DSN itself in str()."""


def _guard_local_dsn(dsn: str) -> None:
    if os.environ.get("FLY_APP_NAME") or os.environ.get("FLY_MACHINE_ID"):
        raise DsnGuardError("fly_env_detected")
    parts = urlsplit(dsn)
    qs = parse_qs(parts.query)
    unix_socket = bool(qs.get("host")) and str(qs.get("host", [""])[0]).startswith("/")
    if not unix_socket and parts.hostname not in _ALLOWED_HOSTS:
        raise DsnGuardError("non_local_host")
    dbname = (parts.path or "").lstrip("/")
    if dbname != "nuzantara_dev":
        raise DsnGuardError("wrong_dbname")


def _build_dsn() -> str:
    dsn = os.environ.get("WA_TEAM_PROMISES_DSN") or DEFAULT_DSN
    _guard_local_dsn(dsn)
    return dsn


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class ExtractMetrics:
    total_scanned: int = 0
    candidate_messages: int = 0
    fulfilments_skipped: int = 0  # past-tense clauses — never a candidate
    judged_true: int = 0
    judged_false: int = 0
    unjudged: int = 0  # Ollama unreachable/malformed — never stored
    promises_created: int = 0
    promises_skipped_conflict: int = 0
    with_due_at_cue: int = 0
    with_due_at_default: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    open_total: int | None = None
    overdue_total: int | None = None
    wall_ms: int = 0


# ---------------------------------------------------------------------------
# D — clause-scoped candidate generation (pure, no DB/Ollama)
# ---------------------------------------------------------------------------

def _thread_key(team_member_phone: str | None, chat_jid: str | None,
                 counterpart_phone: str | None, counterpart_lid: str | None) -> str | None:
    """md5(team_member_phone|chat_jid-or-counterpart) — spec §2.3. No ALTER
    on whatsapp_message_context, so this key lives only in team_promises."""
    counterpart = chat_jid or counterpart_phone or counterpart_lid
    if not team_member_phone or not counterpart:
        return None
    raw = f"{team_member_phone}|{counterpart}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _infer_due_at(text: str, base_dt: _dt.datetime) -> tuple[_dt.datetime, bool]:
    """Returns (due_at, from_cue). from_cue=False means the D6 default fired."""
    for pattern, hours in _TEMPORAL_CUES:
        if pattern.search(text):
            return base_dt + _dt.timedelta(hours=hours), True
    return base_dt + _dt.timedelta(hours=DEFAULT_DUE_AT_HOURS), False


def _extract_window(clause: str, match: re.Match[str], window: int = PROMISE_TEXT_WINDOW) -> str:
    start = max(0, match.start() - window // 2)
    end = min(len(clause), match.end() + window // 2)
    snippet = clause[start:end].strip()
    return snippet[:window].rstrip() if len(snippet) > window else snippet


def split_clauses(body: str) -> list[str]:
    return [p.strip() for p in CLAUSE_SPLIT_RE.split(body) if p and p.strip()]


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
    """Returns (candidates, fulfilments_skipped). Dedup by promise_type is
    applied AFTER a clause is confirmed non-past (round-0 bug #2: adding the
    type to seen_types on ANY match — even a past-tense one — lost a
    genuine future commitment later in the same message)."""
    seen_types: set[str] = set()
    out: list[_Candidate] = []
    fulfilments = 0
    tkey = _thread_key(team_member_phone, chat_jid, counterpart_phone, counterpart_lid)
    for clause in split_clauses(body):
        clause_is_past = bool(PAST_TENSE_RE.search(clause))
        for ptype, pat in _PROMISE_PATTERNS_RE:
            if ptype in seen_types:
                continue
            m = pat.search(clause)
            if not m:
                continue
            if clause_is_past:
                fulfilments += 1
                continue
            due_at, from_cue = _infer_due_at(clause, base_dt)
            out.append(_Candidate(
                message_id=message_id, conversation_id=None, client_id=client_id,
                thread_key=tkey, team_member_email=team_member_email,
                promise_text=_extract_window(clause, m), promise_type=ptype,
                due_at=due_at, from_cue=from_cue,
            ))
            seen_types.add(ptype)
    return out, fulfilments


# ---------------------------------------------------------------------------
# D — local judge (Pro Ollama qwen3.5:9b, same client as
# wa-mirror-attention-classifier.py's ollama_classify)
# ---------------------------------------------------------------------------

def _ollama_judge_sync(clause_text: str) -> dict | None:
    """Returns {'future_commitment_by_sender': bool, 'due_hint': str|None},
    or None if Ollama is unreachable or the response is malformed. Blocking
    by design — matches the existing precedent's client shape exactly."""
    prompt = (
        "A Bali-business-services team member sent this WhatsApp clause. "
        "Decide if it is a genuine FIRST-PERSON commitment BY THE SENDER to "
        "do something in the future (not a past report, not an instruction "
        "directed at someone else, not negated).\n\n"
        f"Clause:\n```\n{clause_text[:400]}\n```\n\n"
        'Respond ONLY with JSON: {"future_commitment_by_sender": true|false, '
        '"due_hint": "<temporal phrase or null>"}'
    )
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps({
            "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
            "think": False, "format": "json",
            "options": {"temperature": 0.0, "num_predict": 64},
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_S) as r:
            raw = json.loads(r.read()).get("response") or ""
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or "future_commitment_by_sender" not in parsed:
            return None
        return {
            "future_commitment_by_sender": bool(parsed["future_commitment_by_sender"]),
            "due_hint": parsed.get("due_hint") or None,
        }
    except Exception:
        return None


async def _ollama_judge(clause_text: str) -> dict | None:
    return await asyncio.to_thread(_ollama_judge_sync, clause_text)


async def judge_candidates(
    candidates: list[_Candidate], base_dt: _dt.datetime,
) -> tuple[list[_Candidate], int, int, int]:
    """Returns (accepted, judged_true, judged_false, unjudged). Fail-fast:
    the first unreachable/malformed verdict marks Ollama dead for the REST
    of this call — a dead local daemon is an all-or-nothing condition, so
    hammering it once per remaining candidate wastes the tick."""
    accepted: list[_Candidate] = []
    judged_true = judged_false = unjudged = 0
    ollama_dead = False
    for c in candidates:
        if ollama_dead:
            unjudged += 1
            continue
        verdict = await _ollama_judge(c.promise_text)
        if verdict is None:
            unjudged += 1
            ollama_dead = True
            continue
        if not verdict["future_commitment_by_sender"]:
            judged_false += 1
            continue
        judged_true += 1
        if not c.from_cue and verdict.get("due_hint"):
            due_at, from_cue = _infer_due_at(str(verdict["due_hint"]), base_dt)
            if from_cue:
                c.due_at, c.from_cue = due_at, True
        accepted.append(c)
    return accepted, judged_true, judged_false, unjudged


# ---------------------------------------------------------------------------
# A — init-schema + catalog index verification
# ---------------------------------------------------------------------------

_INDEX_CHECK_SQL = """
SELECT ix.indisunique, ix.indisvalid, ix.indpred IS NOT NULL AS has_predicate,
       (SELECT array_agg(a.attname ORDER BY o.ord)
        FROM unnest(ix.indkey) WITH ORDINALITY AS o(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = o.attnum
       ) AS columns
FROM pg_index ix
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
WHERE t.relname = $1 AND i.relname = $2
"""


async def verify_unique_index(conn, table: str, index: str, columns: list[str]) -> None:
    row = await conn.fetchrow(_INDEX_CHECK_SQL, table, index)
    if row is None:
        raise RuntimeError(f"index {index} missing after init-schema")
    ok = (row["indisunique"] and row["indisvalid"] and not row["has_predicate"]
          and list(row["columns"] or []) == columns)
    if not ok:
        raise RuntimeError(
            f"{index} exists with an incompatible definition — abort, change nothing "
            f"(unique={row['indisunique']} valid={row['indisvalid']} "
            f"predicate={row['has_predicate']} columns={row['columns']})"
        )


async def run_init_schema(pool: asyncpg.Pool) -> None:
    ddl = _SQL_PATH.read_text()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(ddl)
        await verify_unique_index(conn, "team_promises", "uix_team_promises_msg_type",
                                   ["message_id", "promise_type"])


# ---------------------------------------------------------------------------
# Watermark, lock, digest
# ---------------------------------------------------------------------------

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
        os.close(fd)
        sys.exit(0)  # another instance running — silent, expected


def _resolve_py3() -> str:
    for candidate in _PY3_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return sys.executable


def _digest_line(metrics: ExtractMetrics) -> str:
    """Counts only — no promise_text, thread_key or team_member_email ever
    touches this string."""
    return (
        f"promises: new {metrics.promises_created} "
        f"open {metrics.open_total} overdue {metrics.overdue_total} "
        f"unjudged {metrics.unjudged}"
    )


def _tg_notify_digest(text: str) -> bool:
    try:
        gateway = _REPO_ROOT / "scripts" / "tg_notify.py"
        if not gateway.is_file():
            return False
        res = subprocess.run(
            [_resolve_py3(), str(gateway), "--tier", "digest",
             "--source", "wa-team-promises", "--", text],
            capture_output=True, text=True, timeout=30,
        )
        return res.returncode == 0
    except Exception:  # never raises — a gateway hiccup must not fail the tick
        return False


# ---------------------------------------------------------------------------
# E — bounded batch query (id watermark AND a rolling 30-day created_at
# floor, on EVERY tick — not just the first run). round-0 bug: an id-only
# seed fell back to 0 whenever no row matched the 30-day window at seed
# time, which then scanned the FULL archive with no date bound at all.
# ---------------------------------------------------------------------------

_BATCH_SQL = """
SELECT id, client_id, team_member_phone, team_member_email,
       chat_jid, counterpart_phone, counterpart_lid,
       COALESCE(message_date, created_at) AS base_dt,
       COALESCE(body, message_text) AS body
FROM whatsapp_message_context
WHERE direction = 'outbound'
  AND id > $1
  AND created_at >= now() - interval '30 days'
  AND COALESCE(body, message_text) IS NOT NULL
  AND length(COALESCE(body, message_text)) > 3
ORDER BY id
LIMIT $2
"""


async def run_tick(pool: asyncpg.Pool, *, apply: bool, limit: int | None,
                    batch_size: int) -> ExtractMetrics:
    t0 = time.monotonic()
    metrics = ExtractMetrics()
    watermark = _load_watermark() or 0
    safe_watermark = watermark
    offset_id = watermark
    remaining = limit
    stop = False

    while not stop:
        fetch = batch_size if remaining is None else min(batch_size, remaining)
        if fetch <= 0:
            break
        async with pool.acquire() as conn:
            rows = await conn.fetch(_BATCH_SQL, offset_id, fetch)
        if not rows:
            break
        metrics.total_scanned += len(rows)

        to_insert: list[_Candidate] = []
        for r in rows:
            candidates, fulfilments = find_candidates_in_message(
                message_id=r["id"], client_id=r["client_id"],
                team_member_phone=r["team_member_phone"],
                team_member_email=r["team_member_email"],
                chat_jid=r["chat_jid"], counterpart_phone=r["counterpart_phone"],
                counterpart_lid=r["counterpart_lid"], body=r["body"], base_dt=r["base_dt"],
            )
            metrics.fulfilments_skipped += fulfilments
            if candidates:
                metrics.candidate_messages += 1

            accepted, jt, jf, unj = await judge_candidates(candidates, r["base_dt"])
            metrics.judged_true += jt
            metrics.judged_false += jf
            metrics.unjudged += unj
            for c in accepted:
                to_insert.append(c)
                metrics.by_type[c.promise_type] = metrics.by_type.get(c.promise_type, 0) + 1
                if c.from_cue:
                    metrics.with_due_at_cue += 1
                else:
                    metrics.with_due_at_default += 1

            if unj > 0:
                stop = True  # watermark must NOT advance past an unjudged candidate
                break
            safe_watermark = r["id"]

        if apply and to_insert:
            async with pool.acquire() as conn, conn.transaction():
                for c in to_insert:
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
        elif to_insert:
            metrics.promises_created += len(to_insert)

        # Advance the cursor to this batch's highest fetched id REGARDLESS of
        # `stop` — rows are ORDER BY id, so the last row is always the max —
        # otherwise the next `id > $1` refetches the exact same batch forever
        # (a bug caught by the round-1 Pro dry-run: 200 rows reprocessed
        # ~1000x over 81 minutes until a flaky Ollama call finally broke the
        # loop). `safe_watermark` still stops short of an unjudged id — this
        # only moves the SELECT window, not what gets persisted.
        offset_id = rows[-1]["id"]

        if remaining is not None:
            remaining -= len(rows)
        if stop:
            break

    if apply and safe_watermark > watermark:
        _save_watermark(safe_watermark)

    if apply:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT count(*) FILTER (WHERE resolved = false) AS open_total, "
                "count(*) FILTER (WHERE resolved = false AND due_at < now()) AS overdue_total "
                "FROM team_promises"
            )
        metrics.open_total = int(row["open_total"])
        metrics.overdue_total = int(row["overdue_total"])

    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# ---------------------------------------------------------------------------
# C — errors never carry data
# ---------------------------------------------------------------------------

def _fail_line(exc: BaseException, stage: str, metrics: ExtractMetrics | None) -> str:
    sqlstate = getattr(exc, "sqlstate", None) or "-"
    if metrics is None:
        counts = "n/a"
    else:
        d = asdict(metrics)
        d.pop("by_type", None)  # keys are fixed promise_type literals, but keep the line short
        counts = ",".join(f"{k}={v}" for k, v in d.items())
    return f"wa_team_promises: FAIL {type(exc).__name__} sqlstate={sqlstate} stage={stage} counts={counts}"


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wa_team_promises")
    parser.add_argument("--init-schema", action="store_true",
                         help="Apply scripts/sql/pro_local/team_promises.sql "
                              "(idempotent) and verify the unique index, then exit.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Scan, judge and count only — never inserts. "
                              "Works even before --init-schema has run.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--metrics-json", default=str(METRICS_FILE_DEFAULT))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    stage = "dsn_guard"
    metrics: ExtractMetrics | None = None
    lock_fd: int | None = None
    try:
        dsn = _build_dsn()

        stage = "lock"
        apply = not args.dry_run and not args.init_schema
        lock_fd = _acquire_lock_or_exit() if (apply or args.init_schema) else None

        stage = "connect"
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=3,
                                          statement_cache_size=0, command_timeout=60)
        try:
            if args.init_schema:
                stage = "init_schema"
                await run_init_schema(pool)
                sys.stdout.write("wa_team_promises: init-schema OK\n")
                return 0

            stage = "tick"
            metrics = await run_tick(pool, apply=apply, limit=args.limit,
                                      batch_size=args.batch_size)
        finally:
            await pool.close()

        stage = "metrics_write"
        payload = asdict(metrics)
        payload.update(version=PRO_EXTRACTOR_VERSION, apply=apply,
                        ts=_dt.datetime.now(_dt.timezone.utc).isoformat())
        logger.info("tick done (counts only): %s", payload)
        STATE_DIR.mkdir(exist_ok=True)
        tmp = Path(args.metrics_json).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str))
        tmp.replace(args.metrics_json)

        stage = "digest"
        if apply:
            _tg_notify_digest(_digest_line(metrics))
        return 0
    except Exception as exc:
        sys.stderr.write(_fail_line(exc, stage, metrics) + "\n")
        return 1
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
