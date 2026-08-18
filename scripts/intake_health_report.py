#!/usr/bin/env python3
"""intake_health_report.py — read-only daily health snapshot of the document-intake organism.

W0 read-only guardian (never writes DB, never mutates a proposal/queue row).
Reads the local Postgres `nuzantara_dev` (Law 2 — PII stays local, only
integers/rates/booleans ever leave this machine) and reports one JSON object
covering the intake corner's LIVE STATE anatomy: review load, the empty-OCR
noise class (C-02), blob presence for the review feed (C-01), the CRM's
`companies` table sanity (C-29), done-but-orphaned queue rows (C-07),
zombie claimed-but-lease-less proposals (C-05), committed-but-undelivered
documents (C-08), the worker's own log inode, and 24h freshness counters.

Model: scripts/intake_gate_count_pusher.py (DSN/env/logging conventions) +
scripts/wr2_daily_reconciler.py (module-level `_tg_notify`/`_heartbeat` so a
test can monkeypatch the SIDE EFFECT without touching the DB or the network —
`run()`/`gather()` take a live/fake connection, everything else is pure).

DB: SELECT-only. Connection opened with `default_transaction_read_only=on`
(server_settings) as defense-in-depth beyond "we only issue SELECTs" — a
write attempted over this connection is refused by Postgres itself, not by
code discipline alone.

Env:
  INTAKE_DATABASE_URL / LOCAL_DATABASE_URL   DSN (default local nuzantara_dev)
  INTAKE_HEALTH_REPORT_ENABLED               kill switch (default true) — G5
  INTAKE_HEALTH_COMPANIES_MIN_ROWS           default 1  (breach if companies_rows < N)
  INTAKE_HEALTH_BLOB_PRESENT_MIN             default 0.5 (breach if newest blob-present rate < N)
  INTAKE_HEALTH_ALL_EMPTY_MAX                default 0.5 (breach if quarantine all-pages-empty rate > N)
  INTAKE_HEALTH_ZOMBIE_MAX                   default 0  (breach if zombie count > N)
  INTAKE_HEALTH_SUPERSEDED_TIMEOUT_MS        default 60000 (statement_timeout for the C-07b query)
  INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS
                                               default 5 (asyncpg connection-close bound)

Flags: --dry-run (skip Telegram + state-file write; heartbeat still fires) ·
       --json-only (no success side effects: skip Telegram + state-file write +
       success heartbeat; failures still emit heartbeat=error)

Exit: 0 after a completed/disabled/lock-held run; 1 after a connect, gather,
      report-build, persistence, or connection-close failure (heartbeat=error).
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import math
import os
import plistlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered  # noqa: E402

logging.basicConfig(
    level=os.getenv("INTAKE_HEALTH_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("intake_health_report")

ORGAN_ID = "pro.intake_health_report"
STATE_PATH = Path.home() / ".agent" / "decisions" / "state" / "intake_health_report.json"
LOCK_FILE = Path.home() / ".cell-bridge-state" / "intake_health_report.lock"
DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_SUPERSEDED_TIMEOUT_MS = 60_000
# Matches the five-second asyncpg close bound used by the PG bridge and both
# WR2 supervisors. Set INTAKE_HEALTH_LOG_LEVEL=DEBUG to record actual close
# latency, then tune the env override if a future driver/proxy needs a
# different measured bound; no code edit or frozen re-estimate is required.
DEFAULT_CONNECTION_CLOSE_TIMEOUT_SECONDS = 5.0
REPO_WORKER_PLIST_PATH = _REPO / "infra" / "launchagents" / "com.nuzantara.intake-worker.plist"
# The INSTALLED launchd plist — the one actually driving the running worker —
# takes precedence over the repo copy (verbale #8, superscar #1 HOME-fork):
# this script's own _REPO is derived from whichever checkout happened to
# invoke it (main / a worktree / a stale deploy copy), which is not
# necessarily the checkout the worker was installed from. Reading the repo
# copy when the two diverge is a false-clean or a false-breach on
# worker_log_inode_exists, decided by an accident of which checkout ran this
# report today rather than by what launchd is actually running.
INSTALLED_WORKER_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.nuzantara.intake-worker.plist"
_FALLBACK_WORKER_LOG = Path.home() / "logs" / "intake-worker.launchd.err.log"

# The absolute python3 candidates tg_notify.py is spawned with (W108 — the
# alarm must not share the failure mode of a possibly-broken venv PATH
# resolution). tg_notify.py is stdlib-only by design for exactly this reason.
_PY3_CANDIDATES: tuple[str, ...] = (
    "/usr/bin/python3",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
)

# The live (non-terminal-loss) proposal statuses (migration 235, verified
# live against document_routing_proposal.chk_rp_status 2026-08-15). A `done`
# queue row whose ONLY proposals sit OUTSIDE this set has effectively lost
# its trail (dead/superseded, never landed anywhere a human or the writer
# can still act on it).
_LIVE_PROPOSAL_STATUSES: tuple[str, ...] = (
    "review_pending", "review_claimed", "routed", "rejected",
    "auto_routed", "quarantine", "duplicate",
)
_LIVE_STATUS_SQL_ARRAY = "ARRAY[" + ",".join(f"'{s}'" for s in _LIVE_PROPOSAL_STATUSES) + "]"

# ---------------------------------------------------------------- SQL (module constants — shape-tested)

STATUS_COUNTS_SQL = """
    SELECT
        count(*) FILTER (WHERE p.status = 'review_pending')                            AS review_pending_total,
        count(*) FILTER (WHERE p.status = 'review_pending' AND q.source = 'whatsapp')   AS review_pending_wa,
        count(*) FILTER (WHERE p.status = 'quarantine')                                 AS quarantine_total,
        count(*) FILTER (WHERE p.status = 'duplicate')                                  AS duplicate_total,
        count(*) FILTER (
            WHERE p.status = 'review_pending'
              AND p.entity_resolution ->> 'decision' = 'NO_MATCH'
        ) AS zero_candidate_count
    FROM document_routing_proposal p
    JOIN intake_queue q ON q.id = p.queue_id
"""

ALL_PAGES_EMPTY_SQL = """
    SELECT p.status,
           count(*) FILTER (
               WHERE NOT EXISTS (
                   SELECT 1
                     FROM jsonb_array_elements(q.stage_output -> 'classify' -> 'ocr_text_per_page') AS pg
                    WHERE pg ->> 'via' IS DISTINCT FROM 'empty'
               )
           ) AS all_empty,
           count(*) AS denominator
      FROM intake_queue q
      JOIN document_routing_proposal p ON p.queue_id = q.id
     WHERE q.source = 'whatsapp'
       AND p.status IN ('quarantine', 'review_pending')
       AND jsonb_typeof(q.stage_output -> 'classify' -> 'ocr_text_per_page') = 'array'
       AND jsonb_array_length(q.stage_output -> 'classify' -> 'ocr_text_per_page') >= 1
     GROUP BY p.status
"""

BLOB_SAMPLE_SQL = """
    SELECT q.blob_path
      FROM document_routing_proposal p
      JOIN intake_queue q ON q.id = p.queue_id
     WHERE q.source = 'whatsapp' AND p.status = 'review_pending'
     ORDER BY p.created_at {direction}
     LIMIT $1
"""

COMPANIES_ROWS_SQL = "SELECT count(*) AS n FROM companies"

ORPHAN_DONE_SQL = """
    SELECT q.source, count(*) AS n
      FROM intake_queue q
      LEFT JOIN document_routing_proposal p ON p.queue_id = q.id
     WHERE q.status = 'done' AND p.id IS NULL
     GROUP BY q.source
"""

SUPERSEDED_ORPHAN_SQL = f"""
    SELECT count(*) AS n
      FROM intake_queue q
     WHERE q.status = 'done'
       AND EXISTS (SELECT 1 FROM document_routing_proposal p WHERE p.queue_id = q.id)
       AND NOT EXISTS (
             SELECT 1
               FROM document_routing_proposal p
              WHERE p.queue_id = q.id
                AND p.status = ANY({_LIVE_STATUS_SQL_ARRAY}::text[])
           )
"""

ZOMBIE_SQL = """
    SELECT count(*) AS n
      FROM document_routing_proposal
     WHERE status = 'review_claimed' AND lease_expires_at IS NULL
"""

UNDELIVERED_COMMITTED_SQL = """
    SELECT
        count(*) FILTER (WHERE file_id IS NULL) AS undelivered,
        count(*)                                AS total
      FROM documents
     WHERE intake_proposal_id IS NOT NULL
"""

DEAD_LAST_24H_SQL = """
    SELECT count(*) AS n
      FROM intake_queue
     WHERE status = 'dead' AND updated_at > now() - interval '24 hours'
"""

WA_MEDIA_LAST_24H_SQL = """
    SELECT count(*) AS n
      FROM whatsapp_message_context
     WHERE media_stored_path IS NOT NULL
       AND created_at > now() - interval '24 hours'
"""


# ---------------------------------------------------------------- side effects (module-level, monkeypatchable)


def _resolve_py3() -> str:
    for candidate in _PY3_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return sys.executable  # last resort — never crash over interpreter resolution


def _tg_notify(tier: str, dedup_key: str, text: str) -> bool:
    """Route through the tg_notify gateway; never raises."""
    try:
        gateway = _REPO / "scripts" / "tg_notify.py"
        if not gateway.is_file():
            logger.warning("[intake_health_report] tg_notify.py missing at %s", gateway)
            return False
        res = subprocess.run(
            [_resolve_py3(), str(gateway), "--tier", tier,
             "--source", "intake-health-report", "--dedup-key", dedup_key, "--", text],
            capture_output=True, text=True, timeout=30,
        )
        verdict = extract_gateway_verdict(res.stderr)
        logger.info("[intake_health_report] tg_notify: %s", verdict or f"NESSUN verdetto rc={res.returncode}")
        return res.returncode == 0 and gateway_delivered(verdict)
    except Exception as exc:  # noqa: BLE001 — never raises
        logger.warning("[intake_health_report] tg_notify failed: %s", exc)
        return False


def _heartbeat(status: str, note: str = "") -> None:
    try:
        from scripts.lib.heartbeat import organism_heartbeat

        organism_heartbeat(ORGAN_ID, status, note=note)
    except Exception as exc:  # noqa: BLE001 — never raises
        logger.warning("[intake_health_report] heartbeat write failed: %s", exc)


def _write_state(report: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, STATE_PATH)
    except OSError as exc:
        # Persistence is part of completing this organ's run. Swallowing an
        # OSError here made launchd see rc=0 and the final heartbeat say `ok`
        # even though the durable report was never updated. Log only the type
        # (the exception message may contain a local/client-derived path), then
        # let run() emit the canonical error heartbeat and rc=1.
        logger.warning("[intake_health_report] state write failed: %s", type(exc).__name__)
        raise


def _acquire_lock_or_exit() -> int | None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o600)
    # O_CREAT's mode argument only applies when the file is CREATED (verbale
    # #9) — it does not retroactively chmod a lock file that already exists
    # on disk from an earlier pre-hardening run. Mirrors tg_notify.py's
    # harden() rationale (same repo, same PR family, and the exact lesson
    # tg_notify.py already documents in its own docstring).
    try:
        os.chmod(LOCK_FILE, 0o600)
    except OSError as exc:  # noqa: BLE001 — never let a chmod failure block the lock
        logger.warning("[intake_health_report] lock chmod failed: %s", exc)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[intake_health_report] another instance running, skipping")
        os.close(fd)
        return None


# ---------------------------------------------------------------- pure helpers (unit-tested, no DB/network)


def resolve_worker_plist_path() -> tuple[Path, str]:
    """Prefer the INSTALLED launchd plist over the repo copy (verbale #8) —
    returns (path, "installed"|"repo")."""
    if INSTALLED_WORKER_PLIST_PATH.is_file():
        return INSTALLED_WORKER_PLIST_PATH, "installed"
    return REPO_WORKER_PLIST_PATH, "repo"


def worker_log_path() -> tuple[Path, str]:
    """Resolve the intake-worker's StandardErrorPath from its own plist —
    never hardcode a duplicate of what the plist already declares. Returns
    (log_path, plist_source) so the caller can report which plist was read."""
    plist_path, source = resolve_worker_plist_path()
    try:
        payload = plistlib.loads(plist_path.read_bytes())
        raw = payload.get("StandardErrorPath")
        if isinstance(raw, str) and raw:
            return Path(raw).expanduser(), source
    except (OSError, ValueError) as exc:
        logger.warning(
            "[intake_health_report] could not read worker plist %s (%s) — falling back to %s",
            plist_path, exc, _FALLBACK_WORKER_LOG,
        )
    return _FALLBACK_WORKER_LOG, source


def blob_presence(paths: list[str]) -> dict[str, Any]:
    """os.path.exists over a caller-supplied sample. Pure — the caller owns
    SAMPLING (which rows, how many); this only judges presence."""
    sampled = len(paths)
    present = sum(1 for p in paths if p and os.path.exists(p))
    return {
        "sampled": sampled,
        "present": present,
        "rate": round(present / sampled, 4) if sampled else None,
    }


def build_report(
    *,
    status_counts: dict[str, int],
    all_pages_empty_rows: list[dict[str, Any]],
    blob_newest: list[str],
    blob_oldest: list[str],
    companies_rows: int,
    orphan_rows: list[dict[str, Any]],
    superseded_orphans: int | None,
    zombie_count: int,
    undelivered: dict[str, int],
    worker_log_exists: bool,
    worker_plist_source: str,
    dead_last_24h: int,
    wa_media_last_24h: int,
    generated_at: str,
) -> dict[str, Any]:
    """Assemble the final report dict from already-fetched raw values. Pure —
    no DB, no I/O beyond the blob_presence() calls already made by the
    caller — so the JSON shape is unit-testable with canned inputs."""
    review_pending_total = int(status_counts.get("review_pending_total") or 0)
    zero_candidate_count = int(status_counts.get("zero_candidate_count") or 0)
    zero_candidate_rate = (
        round(zero_candidate_count / review_pending_total, 4) if review_pending_total else None
    )

    empty_by_status: dict[str, dict[str, Any]] = {}
    for row in all_pages_empty_rows:
        status = row["status"]
        all_empty = int(row["all_empty"] or 0)
        denom = int(row["denominator"] or 0)
        empty_by_status[status] = {
            "count": all_empty,
            "denominator": denom,
            "rate": round(all_empty / denom, 4) if denom else None,
        }
    for status in ("quarantine", "review_pending"):
        empty_by_status.setdefault(status, {"count": 0, "denominator": 0, "rate": None})
    overall_count = sum(v["count"] for v in empty_by_status.values())
    overall_denom = sum(v["denominator"] for v in empty_by_status.values())

    orphans_by_source = {row["source"]: int(row["n"] or 0) for row in orphan_rows}

    return {
        "generated_at": generated_at,
        "review_pending_wa": int(status_counts.get("review_pending_wa") or 0),
        "review_pending_total": review_pending_total,
        "quarantine_total": int(status_counts.get("quarantine_total") or 0),
        "duplicate_total": int(status_counts.get("duplicate_total") or 0),
        "zero_candidate_rate": {
            "count": zero_candidate_count,
            "denominator": review_pending_total,
            "rate": zero_candidate_rate,
        },
        "all_pages_empty": {
            "by_status": empty_by_status,
            "overall_rate": round(overall_count / overall_denom, 4) if overall_denom else None,
        },
        "blob_present": {
            "newest": blob_presence(blob_newest),
            "oldest": blob_presence(blob_oldest),
        },
        "companies_rows": int(companies_rows),
        "orphans_done_without_proposal": orphans_by_source,
        "superseded_orphans_true": superseded_orphans,
        "zombie_review_claimed_null_lease": int(zombie_count),
        "undelivered_committed": {
            "undelivered": int(undelivered.get("undelivered") or 0),
            "total": int(undelivered.get("total") or 0),
        },
        "worker_log_inode_exists": bool(worker_log_exists),
        "worker_plist_source": worker_plist_source,
        "dead_last_24h": int(dead_last_24h),
        "wa_media_last_24h": int(wa_media_last_24h),
    }


def evaluate_breaches(report: dict[str, Any], thresholds: dict[str, float]) -> list[dict[str, str]]:
    """Pure threshold evaluation. Returns a list of {metric, message} — empty
    when nothing breaches. Each rule is independently guilt/innocence-tested."""
    breaches: list[dict[str, str]] = []

    companies_rows = report["companies_rows"]
    if companies_rows < thresholds["companies_min_rows"]:
        breaches.append({
            "metric": "companies_rows",
            "message": f"companies table has {companies_rows} rows (min {thresholds['companies_min_rows']})",
        })

    newest = report["blob_present"]["newest"]
    if newest["sampled"] and newest["rate"] is not None and newest["rate"] < thresholds["blob_present_min"]:
        breaches.append({
            "metric": "blob_present_newest",
            "message": (
                f"blob-present rate on newest review_pending sample is "
                f"{newest['rate']:.2%} ({newest['present']}/{newest['sampled']}), "
                f"below {thresholds['blob_present_min']:.0%}"
            ),
        })

    quarantine_empty = report["all_pages_empty"]["by_status"].get("quarantine", {})
    q_rate = quarantine_empty.get("rate")
    if q_rate is not None and q_rate > thresholds["all_empty_max"]:
        breaches.append({
            "metric": "all_pages_empty_quarantine",
            "message": (
                f"all-pages-empty rate among quarantined WhatsApp docs is {q_rate:.2%} "
                f"({quarantine_empty['count']}/{quarantine_empty['denominator']}), "
                f"above {thresholds['all_empty_max']:.0%}"
            ),
        })

    zombie = report["zombie_review_claimed_null_lease"]
    if zombie > thresholds["zombie_max"]:
        breaches.append({
            "metric": "zombie_review_claimed",
            "message": f"{zombie} review_claimed proposal(s) with NULL lease_expires_at (max {thresholds['zombie_max']})",
        })

    if not report["worker_log_inode_exists"]:
        breaches.append({
            "metric": "worker_log_missing",
            "message": "intake-worker StandardErrorPath log file does not exist on disk",
        })

    return breaches


def render_digest(report: dict[str, Any]) -> str:
    """The 6 headline numbers for the daily digest line."""
    zc = report["zero_candidate_rate"]["rate"]
    zc_pct = f"{zc:.1%}" if zc is not None else "n/a"
    bp = report["blob_present"]["newest"]["rate"]
    bp_pct = f"{bp:.1%}" if bp is not None else "n/a"
    return (
        f"📋 Intake health: review_pending={report['review_pending_total']} "
        f"(wa={report['review_pending_wa']}) quarantine={report['quarantine_total']} "
        f"duplicate={report['duplicate_total']} zero_candidate={zc_pct} "
        f"blob_present(newest)={bp_pct}"
    )


# ---------------------------------------------------------------- DB fetchers (thin, async)


async def _fetch_superseded_orphans(conn: Any, timeout_ms: int) -> int | None:
    try:
        await conn.execute(f"SET statement_timeout = '{int(timeout_ms)}'")
        row = await conn.fetchrow(SUPERSEDED_ORPHAN_SQL)
        return int(row["n"])
    except asyncpg.exceptions.QueryCanceledError:
        logger.warning(
            "[intake_health_report] superseded_orphans query exceeded %sms — reporting null",
            timeout_ms,
        )
        return None
    finally:
        try:
            await conn.execute("SET statement_timeout = DEFAULT")
        except Exception:  # noqa: BLE001 — never let cleanup crash the report
            pass


async def gather(conn: Any, *, superseded_timeout_ms: int) -> dict[str, Any]:
    """Run every metric query against `conn` (real or fake) and assemble the
    final report dict. The only I/O outside `conn` is os.path.exists() on the
    sampled blob paths and the worker plist read — both pure-function-wrapped
    above so a test can exercise them without a filesystem fixture if desired."""
    status_row = await conn.fetchrow(STATUS_COUNTS_SQL)
    all_pages_empty_rows = [dict(r) for r in await conn.fetch(ALL_PAGES_EMPTY_SQL)]
    newest_rows = await conn.fetch(BLOB_SAMPLE_SQL.format(direction="DESC"), 300)
    oldest_rows = await conn.fetch(BLOB_SAMPLE_SQL.format(direction="ASC"), 50)
    companies_row = await conn.fetchrow(COMPANIES_ROWS_SQL)
    orphan_rows = [dict(r) for r in await conn.fetch(ORPHAN_DONE_SQL)]
    superseded_orphans = await _fetch_superseded_orphans(conn, superseded_timeout_ms)
    zombie_row = await conn.fetchrow(ZOMBIE_SQL)
    undelivered_row = await conn.fetchrow(UNDELIVERED_COMMITTED_SQL)
    dead_row = await conn.fetchrow(DEAD_LAST_24H_SQL)
    wa_media_row = await conn.fetchrow(WA_MEDIA_LAST_24H_SQL)
    worker_log_p, worker_plist_source = worker_log_path()

    return build_report(
        status_counts=dict(status_row),
        all_pages_empty_rows=all_pages_empty_rows,
        blob_newest=[r["blob_path"] for r in newest_rows],
        blob_oldest=[r["blob_path"] for r in oldest_rows],
        companies_rows=companies_row["n"],
        orphan_rows=orphan_rows,
        superseded_orphans=superseded_orphans,
        zombie_count=zombie_row["n"],
        undelivered=dict(undelivered_row),
        worker_log_exists=worker_log_p.exists(),
        worker_plist_source=worker_plist_source,
        dead_last_24h=dead_row["n"],
        wa_media_last_24h=wa_media_row["n"],
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _thresholds_from_env() -> dict[str, float]:
    return {
        "companies_min_rows": float(os.getenv("INTAKE_HEALTH_COMPANIES_MIN_ROWS", "1")),
        "blob_present_min": float(os.getenv("INTAKE_HEALTH_BLOB_PRESENT_MIN", "0.5")),
        "all_empty_max": float(os.getenv("INTAKE_HEALTH_ALL_EMPTY_MAX", "0.5")),
        "zombie_max": float(os.getenv("INTAKE_HEALTH_ZOMBIE_MAX", "0")),
    }


def _timeouts_from_env() -> tuple[int, float]:
    """Parse and validate every operator-configurable timeout before connect."""
    superseded_timeout_ms = int(
        os.getenv(
            "INTAKE_HEALTH_SUPERSEDED_TIMEOUT_MS",
            str(DEFAULT_SUPERSEDED_TIMEOUT_MS),
        )
    )
    connection_close_timeout_seconds = float(
        os.getenv(
            "INTAKE_HEALTH_CONNECTION_CLOSE_TIMEOUT_SECONDS",
            str(DEFAULT_CONNECTION_CLOSE_TIMEOUT_SECONDS),
        )
    )
    if superseded_timeout_ms <= 0:
        raise ValueError("superseded timeout must be positive")
    if (
        not math.isfinite(connection_close_timeout_seconds)
        or connection_close_timeout_seconds <= 0
    ):
        raise ValueError("connection-close timeout must be finite and positive")
    return superseded_timeout_ms, connection_close_timeout_seconds


async def _close_connection(conn: Any, *, timeout_seconds: float) -> None:
    """Close an asyncpg connection within the configured liveness bound."""
    loop = asyncio.get_running_loop()
    started_at = loop.time()
    try:
        await asyncio.wait_for(conn.close(), timeout=timeout_seconds)
    except Exception:  # noqa: BLE001 — caller owns canonical phase reporting
        # Mirrors the established asyncpg cleanup convention in the PG bridge
        # and WR2 supervisors: a close failure/timeout must not leave the
        # transport alive after this run releases its single-instance flock.
        try:
            conn.terminate()
        except Exception:  # noqa: BLE001 — retain the original close failure
            pass
        raise
    finally:
        logger.debug(
            "[intake_health_report] connection close elapsed_seconds=%.3f "
            "timeout_seconds=%.3f",
            loop.time() - started_at,
            timeout_seconds,
        )


async def run(*, dry_run: bool, json_only: bool) -> int:
    if os.getenv("INTAKE_HEALTH_REPORT_ENABLED", "true").strip().lower() in ("0", "false", "no"):
        logger.info("[intake_health_report] disabled via INTAKE_HEALTH_REPORT_ENABLED — no-op")
        _heartbeat("disabled", "INTAKE_HEALTH_REPORT_ENABLED=false")
        print(json.dumps({"status": "disabled"}))
        return 0

    lock_fd = _acquire_lock_or_exit()
    if lock_fd is None:
        # Previously exited silently: a hung run (verbale #7 — every gather()
        # query but one ran unbounded) could hold this flock past the next
        # scheduled 07:30 tick, and that tick's own return-0-without-a-word
        # meant the organ went fully dark (no digest, no P0, no heartbeat)
        # until a human found the hung process by hand. Now it says so.
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # W0 recheck fast-follow (2026-08-18): "error" put this organ outside
        # healer_receptor_registry.py's HEALTHY_STATUSES set, so a normal
        # lock-contention tick (a manual debug run, a launchd overlap) got
        # classified dead and triggered the autonomous healer session against
        # a perfectly healthy organ — the exact failure class #4223 existed to
        # kill, reopened through this branch. Lock-held-and-skipped is a
        # no-op, not a failure.
        _heartbeat("ok", "lock held, skipped")
        _tg_notify(
            "digest",
            f"intake-health:lock-held:{date_key}",
            "🔒 intake-health-report: previous instance still running — this tick skipped",
        )
        return 0
    try:
        try:
            timeout_ms, connection_close_timeout_seconds = _timeouts_from_env()
        except (TypeError, ValueError, OverflowError) as exc:
            error_type = type(exc).__name__
            logger.error(
                "[intake_health_report] timeout configuration failed: %s",
                error_type,
            )
            _heartbeat("error", f"timeout configuration failed: {error_type}")
            return 1

        dsn = os.getenv("INTAKE_DATABASE_URL") or os.getenv("LOCAL_DATABASE_URL") or DEFAULT_DSN
        try:
            # statement_timeout at the SESSION level (verbale #7): every
            # gather() query except _fetch_superseded_orphans ran unbounded —
            # a hung jsonb-heavy join could hold the single-instance flock
            # indefinitely, and the NEXT scheduled tick would then hit the
            # lock-held branch above. _fetch_superseded_orphans still gets
            # its own tighter override (default 60000ms) via `SET
            # statement_timeout` and resets to this session default (not
            # Postgres's true default) afterward — same 60s guard as before.
            conn = await asyncpg.connect(
                dsn,
                server_settings={
                    "default_transaction_read_only": "on",
                    "statement_timeout": "120000",
                },
                timeout=20,
            )
        except Exception as exc:  # noqa: BLE001
            error_type = type(exc).__name__
            logger.error("[intake_health_report] DB connect failed: %s", error_type)
            _heartbeat("error", f"db connect failed: {error_type}")
            return 1

        failure: Exception | None = None
        failure_phase = "gather"
        try:
            try:
                report = await gather(conn, superseded_timeout_ms=timeout_ms)

                failure_phase = "report"
                thresholds = _thresholds_from_env()
                breaches = evaluate_breaches(report, thresholds)
                report["breaches"] = breaches

                print(json.dumps(report, indent=2, sort_keys=True))

                if not json_only and not dry_run:
                    failure_phase = "persist"
                    _write_state(report)
            except Exception as exc:  # noqa: BLE001 — canonical liveness boundary
                failure = exc
        finally:
            try:
                await _close_connection(
                    conn,
                    timeout_seconds=connection_close_timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 — close is part of run completion
                if failure is None:
                    failure = exc
                    failure_phase = "connection close"
                else:
                    logger.warning(
                        "[intake_health_report] connection close also failed after %s "
                        "failure: %s",
                        failure_phase,
                        type(exc).__name__,
                    )

        if failure is not None:
            # Never serialize the exception message into observability: gather
            # can touch Intake rows, so a message could carry PII. The stable
            # phase plus exception TYPE is sufficient for triage and safe for
            # the shared heartbeat channel.
            error_type = type(failure).__name__
            logger.error(
                "[intake_health_report] %s failed: %s",
                failure_phase,
                error_type,
            )
            _heartbeat("error", f"{failure_phase} failed: {error_type}")
            return 1

        if json_only:
            return 0

        # Heartbeat reflects the ORGAN (did the report complete?), never the
        # FINDING (are there breaches?) — same rule as wa_mirror_freshness_
        # liveness.py (verbale #2): a breach is real information, but it does
        # not mean this organ is unhealthy, and "degraded" made the healer
        # sentinel treat a completed report carrying findings as a dead organ.
        _heartbeat("ok", note=f"breaches={len(breaches)}")

        if not dry_run:
            # Date-stamped, not a bare constant (verbale #4): a fixed daily
            # dedup key can knife-edge-collide with tg_notify's own escalating
            # mute window — once a condition's streak reaches 2, its mute
            # window is exactly 24h, the same as this cron's own cadence, so
            # ordinary cron jitter of a few seconds could silently drop that
            # day's digest line into the existing dedup entry.
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            _tg_notify("digest", f"intake-health:daily:{date_key}", render_digest(report))
            for breach in breaches:
                _tg_notify("p0", f"intake-health:{breach['metric']}", f"🚨 {breach['message']}")

        return 0
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--dry-run", action="store_true", help="no Telegram, no state-file write")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help=(
            "JSON to stdout with no success side effects; failures still emit "
            "heartbeat=error"
        ),
    )
    args = parser.parse_args()
    return asyncio.run(run(dry_run=args.dry_run, json_only=args.json_only))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
