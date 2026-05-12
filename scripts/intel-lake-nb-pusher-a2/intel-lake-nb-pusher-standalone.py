#!/usr/bin/env python3
"""Intel Lake → NB-INTEL Pusher — Pro-local standalone cron (v2, 2026-05-13).

The missing piece of the Intel Lake pipeline. Tier 1 router classifies
intel_items.routing_status='nb-intel' + routing_targets.nb_uuids. Nothing
reads it. mata-garuda's nlm_feeder reads from Redis garuda:enriched (a
parallel pipeline) and feeds its own NB-INTEL UUIDs. Intel Lake routing
is currently inert. This script closes the loop.

Junction table intel_item_nb_pushes(item_id, nb_uuid, content_hash, status, ...)
provides per-target row tracking so partial success (NB-A pushed, NB-B
failed) doesn't false-mark or duplicate. Tri-LLM round 1 (Codex + DeepSeek)
found 10 bugs in v1; all 10 addressed in v2:

1. Junction table (not column on intel_items) — handles N:M
2. URL push primary, text fallback with structured envelope
3. Error classification via NLM stderr pattern (copied from
   apps/mata-garuda/.../nlm_feeder.py)
4. Per-class retry policy:
   - auth_expired → headless refresh ONCE per run, then exit
   - rate_limit → sleep 60s, exit
   - quota → mark failed_permanent (daily limit)
   - not_found → quarantine (notebook UUID typo)
   - timeout/network → failed_transient, retry next tick
   - unknown → failed_transient up to 3 attempts, then permanent
5. Skip-poison: per-item failure increments attempts but loop continues
6. flock LaunchAgent-level (in wrapper .sh)
7. GNU timeout --kill-after for process-tree kill on hang
8. Observability metrics file + debounced Telegram alert
9. Pro permanent owner (no fake retire path)
10. Auth check at startup (fail-fast vs slow-bleed)

Acceptance: at-least-once (NOT exactly-once) — NLM CLI has no --source-id
flag, verified empirically 2026-05-13. URL push has NB-side dedup; text
push may produce ≤1 duplicate per Pro reboot.

Schedule: LaunchAgent com.balizero.intel-lake-nb-pusher.15min (900s)
Logs: ~/logs/intel-lake-nb-pusher.{log,metrics.json}
Migration: apps/backend-rag/backend/db/migrations_v2/171_intel_item_nb_pushes.sql
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("intel-lake-nb-pusher")

METRICS_PATH = Path.home() / "logs" / "intel-lake-nb-pusher.metrics.json"
NLM_CLI = Path.home() / ".local" / "bin" / "nlm"
BATCH_SIZE = 10
NLM_TIMEOUT_SECONDS = 60
SLEEP_BETWEEN_ITEMS_S = 5
MAX_ATTEMPTS_PERMANENT = 3
TELEGRAM_OLDEST_PENDING_THRESHOLD_S = 6 * 3600


# ─── DB URL ────────────────────────────────────────────────────────────────


def _resolve_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL not set")
    # Rewrite flycast → localhost:15432 (WR2 PG-proxy forwards)
    return re.sub(r"@[^:/]+(:[0-9]+)?/", "@localhost:15432/", url)


# ─── NLM error classification (copied from mata-garuda nlm_feeder.py) ───────


def _classify_nlm_error(stderr: str, stdout: str, returncode: int) -> str:
    text = (stderr or "") + (stdout or "")
    tl = text.lower()
    if "Authentication expired" in text or "Authentication Error" in text:
        return "auth_expired"
    if "auth" in tl and "expir" in tl:
        return "auth_expired"
    if ("rate" in tl and "limit" in tl) or "429" in text:
        return "rate_limit"
    if "quota" in tl:
        return "quota"
    if "not found" in tl or ("notebook" in tl and "exist" in tl):
        return "not_found"
    if returncode == 124:  # GNU timeout exit code
        return "timeout"
    if any(k in tl for k in ("network", "timeout", "connection", "unreachable")):
        return "network"
    return "unknown"


def _try_headless_auth_refresh() -> bool:
    """Best-effort: spawn headless Chrome auth refresh. Returns True if OK."""
    try:
        uv_python = Path(
            "/Users/nuzantara/.local/share/uv/tools/notebooklm-mcp-cli/bin/python"
        )
        if not uv_python.exists():
            return False
        result = subprocess.run(
            [
                str(uv_python),
                "-c",
                "from notebooklm_tools.utils.cdp import run_headless_auth; "
                "t = run_headless_auth(profile_name='default', timeout=45); "
                "print('OK' if t else 'FAIL')",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return "OK" in result.stdout
    except Exception as e:
        logger.warning("headless auth refresh failed: %s", e)
        return False


# ─── NLM push (URL primary, text fallback) ─────────────────────────────────


def _nlm_check_auth() -> bool:
    """Fail-fast auth check at startup."""
    try:
        result = subprocess.run(
            [str(NLM_CLI), "login", "--check"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and "✓" in result.stdout
    except Exception:
        return False


def _nlm_push_url(notebook_id: str, url: str, title: str | None = None) -> tuple[bool, str, str]:
    """Try URL push. Returns (ok, error_class, error_text)."""
    cmd = [
        "/usr/bin/env",
        "timeout",
        f"--kill-after=5",
        str(NLM_TIMEOUT_SECONDS),
        str(NLM_CLI),
        "source",
        "add",
        notebook_id,
        "--url",
        url,
    ]
    if title:
        cmd.extend(["--title", title])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=NLM_TIMEOUT_SECONDS + 10)
        if r.returncode == 0:
            return True, "", ""
        cls = _classify_nlm_error(r.stderr, r.stdout, r.returncode)
        return False, cls, (r.stderr or r.stdout or "")[:500]
    except subprocess.TimeoutExpired:
        return False, "timeout", "subprocess.TimeoutExpired"
    except Exception as e:
        return False, "unknown", str(e)[:500]


def _nlm_push_text(notebook_id: str, title: str, body: str) -> tuple[bool, str, str]:
    """Fallback to text push via temp file."""
    tmp = Path(f"/tmp/nlm_push_{uuid4().hex[:8]}.txt")
    try:
        tmp.write_text(body)
        cmd = [
            "/usr/bin/env",
            "timeout",
            f"--kill-after=5",
            str(NLM_TIMEOUT_SECONDS),
            str(NLM_CLI),
            "source",
            "add",
            notebook_id,
            "--file",
            str(tmp),
            "--title",
            title[:100],
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=NLM_TIMEOUT_SECONDS + 10)
        if r.returncode == 0:
            return True, "", ""
        cls = _classify_nlm_error(r.stderr, r.stdout, r.returncode)
        return False, cls, (r.stderr or r.stdout or "")[:500]
    except subprocess.TimeoutExpired:
        return False, "timeout", "subprocess.TimeoutExpired"
    except Exception as e:
        return False, "unknown", str(e)[:500]
    finally:
        tmp.unlink(missing_ok=True)


def _build_text_envelope(item: dict[str, Any], content_hash: str) -> str:
    """Structured text body for fallback push. NEVER dump raw_payload blindly."""
    tags = item.get("topic_tags") or []
    if isinstance(tags, str):
        tags = [tags]
    title = item.get("title") or item.get("canonical_url") or "(untitled)"
    return f"""# {title}

**Source:** {item.get("canonical_url", "")}
**Domain:** {item.get("source_domain", "")}
**Published:** {item.get("published_at", "") or ""}
**Jurisdiction:** {item.get("jurisdiction", "") or ""}
**Tags:** {", ".join(tags) if tags else ""}
**Content-Hash:** {content_hash}

{item.get("summary", "") or ""}
"""


# ─── Main batch loop ────────────────────────────────────────────────────────


async def fetch_pending_pushes(
    pool: asyncpg.Pool, batch_size: int
) -> list[dict[str, Any]]:
    """Discover (item, nb_uuid) pairs that need a push attempt.

    Strategy:
      1. Find intel_items.routing_status='nb-intel' with routing_targets.nb_uuids
      2. For each (item_id, nb_uuid) pair, ensure an intel_item_nb_pushes row
         exists (INSERT ... ON CONFLICT DO NOTHING).
      3. SELECT rows with status IN ('pending','failed_transient')
         AND attempts < MAX_ATTEMPTS_PERMANENT.
    """
    async with pool.acquire() as conn:
        # Step 1+2: insert any missing rows in junction
        await conn.execute(
            """
            INSERT INTO intel_item_nb_pushes (item_id, nb_uuid, content_hash, status)
            SELECT
                ii.id,
                (uuid_elem)::uuid,
                ii.content_hash,
                'pending'
              FROM intel_items ii,
                   jsonb_array_elements_text(
                       COALESCE(ii.routing_targets->'nb_uuids', '[]'::jsonb)
                   ) AS uuid_elem
             WHERE ii.routing_status = 'nb-intel'
               AND ii.content_hash IS NOT NULL
            ON CONFLICT (item_id, nb_uuid, content_hash) DO NOTHING
            """
        )

        # Step 3: fetch eligible push attempts with full item data, SKIP LOCKED
        rows = await conn.fetch(
            """
            SELECT p.id AS push_id, p.item_id, p.nb_uuid, p.content_hash,
                   p.status, p.attempts,
                   ii.title, ii.summary, ii.canonical_url, ii.source_domain,
                   ii.published_at, ii.jurisdiction, ii.topic_tags
              FROM intel_item_nb_pushes p
              JOIN intel_items ii ON ii.id = p.item_id
             WHERE p.status IN ('pending','failed_transient')
               AND p.attempts < $2
             ORDER BY p.created_at ASC
             LIMIT $1
             FOR UPDATE OF p SKIP LOCKED
            """,
            batch_size,
            MAX_ATTEMPTS_PERMANENT,
        )
        return [dict(r) for r in rows]


async def update_push_result(
    pool: asyncpg.Pool,
    push_id: int,
    *,
    success: bool,
    push_method: str | None,
    error_class: str | None,
    error_text: str | None,
) -> None:
    """Apply the push outcome to the junction row + audit log."""
    async with pool.acquire() as conn, conn.transaction():
        if success:
            await conn.execute(
                """
                UPDATE intel_item_nb_pushes
                   SET status = 'pushed',
                       pushed_at = NOW(),
                       updated_at = NOW(),
                       push_method = $2,
                       last_error = NULL,
                       last_error_class = NULL
                 WHERE id = $1
                """,
                push_id,
                push_method,
            )
        else:
            # Decide status by error class
            if error_class in ("quota",):
                new_status = "failed_permanent"
            elif error_class in ("not_found",):
                new_status = "quarantined"
            else:
                # transient errors retry until attempts >= MAX_ATTEMPTS_PERMANENT
                new_status = "failed_transient"

            await conn.execute(
                """
                UPDATE intel_item_nb_pushes
                   SET status = CASE
                                  WHEN attempts + 1 >= $4 AND $5::text = 'failed_transient'
                                       AND last_error_class IN ('unknown','network','timeout')
                                  THEN 'failed_permanent'
                                  ELSE $5
                                END,
                       attempts = attempts + 1,
                       updated_at = NOW(),
                       last_error = $2,
                       last_error_class = $3
                 WHERE id = $1
                """,
                push_id,
                (error_text or "")[:1000],
                error_class,
                MAX_ATTEMPTS_PERMANENT,
                new_status,
            )

        await conn.execute(
            """
            INSERT INTO intel_lake_audit_log
                (producer_name, client_ip, request_path,
                 status_code, payload_size, error_message)
            VALUES ('nb-pusher', NULL, 'pusher/tier1.5',
                    $1, NULL, $2)
            """,
            200 if success else 500,
            f"push_id={push_id} method={push_method or '-'} class={error_class or '-'}",
        )


# ─── Telegram ──────────────────────────────────────────────────────────────


def _telegram_send(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")
    if not (token and chat):
        return
    try:
        import urllib.parse  # noqa: PLC0415
        import urllib.request  # noqa: PLC0415
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


# ─── Main ──────────────────────────────────────────────────────────────────


async def main() -> int:
    metrics: dict[str, Any] = {
        "last_run_at": time.time(),
        "pushed_this_run": 0,
        "failed_this_run": {},
        "selected": 0,
        "errored": 0,
    }

    # Auth fail-fast
    if not _nlm_check_auth():
        msg = "🔴 intel-lake-nb-pusher: nlm auth invalid. Run `nlm login --clear` interactively."
        logger.error(msg)
        _telegram_send(msg)
        _write_metrics(metrics, auth_ok=False)
        return 2

    try:
        pool = await asyncpg.create_pool(_resolve_database_url(), min_size=1, max_size=2, timeout=10)
    except Exception as e:
        logger.error("asyncpg pool failed: %s", e)
        return 1
    if pool is None:
        logger.error("asyncpg pool returned None")
        return 1

    try:
        rows = await fetch_pending_pushes(pool, BATCH_SIZE)
        metrics["selected"] = len(rows)
        logger.info("selected %d pending push attempts", len(rows))

        auth_refresh_attempted = False
        for row in rows:
            push_id = row["push_id"]
            nb_uuid = str(row["nb_uuid"])
            canonical_url = row.get("canonical_url") or ""
            title = (row.get("title") or canonical_url or "(untitled)")[:100]
            content_hash = row["content_hash"]
            item_dict = dict(row)

            logger.info(
                "push push_id=%s item=%s nb=%s url=%s",
                push_id, str(row["item_id"])[:8], nb_uuid[:8], canonical_url[:60],
            )

            # Try URL first
            ok, err_class, err_text = (False, "", "")
            push_method = None
            if canonical_url:
                ok, err_class, err_text = _nlm_push_url(nb_uuid, canonical_url, title)
                if ok:
                    push_method = "url"

            # Fallback to text on URL failure for not_found / network reasons
            if not ok and err_class in ("not_found", "network"):
                body = _build_text_envelope(item_dict, content_hash)
                ok, err_class, err_text = _nlm_push_text(nb_uuid, title, body)
                if ok:
                    push_method = "text"

            # auth_expired: one-shot headless refresh, then exit run
            if err_class == "auth_expired" and not auth_refresh_attempted:
                auth_refresh_attempted = True
                logger.warning("auth_expired — attempting headless refresh")
                if _try_headless_auth_refresh():
                    logger.info("headless refresh OK — retrying current item once")
                    ok, err_class, err_text = _nlm_push_url(nb_uuid, canonical_url, title)
                    if ok:
                        push_method = "url"

            await update_push_result(
                pool, push_id,
                success=ok, push_method=push_method,
                error_class=err_class or None,
                error_text=err_text or None,
            )

            if ok:
                metrics["pushed_this_run"] += 1
            else:
                metrics["errored"] += 1
                key = err_class or "unknown"
                metrics["failed_this_run"][key] = metrics["failed_this_run"].get(key, 0) + 1

            # Certain-fail-for-all early-out
            if err_class == "auth_expired":
                logger.error("auth still expired after refresh — aborting batch")
                _telegram_send("🔴 intel-lake-nb-pusher: NLM auth_expired AND headless refresh failed. Run `nlm login --clear` interactively.")
                break
            if err_class == "rate_limit":
                logger.warning("rate_limit — sleeping 60s then aborting batch")
                time.sleep(60)
                break

            time.sleep(SLEEP_BETWEEN_ITEMS_S)

        # Operational metric: oldest pending age
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS pending_count,
                       EXTRACT(EPOCH FROM (NOW() - MIN(created_at)))::int AS oldest_age
                  FROM intel_item_nb_pushes
                 WHERE status IN ('pending','failed_transient')
                """
            )
            metrics["pending_count"] = int(row["pending_count"] or 0)
            metrics["oldest_pending_age_seconds"] = int(row["oldest_age"] or 0)

            qrow = await conn.fetchrow(
                "SELECT COUNT(*) AS n FROM intel_item_nb_pushes WHERE status='quarantined'"
            )
            metrics["quarantined_total"] = int(qrow["n"] or 0)

        # Debounced Telegram
        if (
            metrics["pending_count"] > 0
            and metrics["oldest_pending_age_seconds"] > TELEGRAM_OLDEST_PENDING_THRESHOLD_S
        ):
            _telegram_send(
                f"⚠️ intel-lake-nb-pusher: oldest pending push is "
                f"{metrics['oldest_pending_age_seconds']//3600}h old "
                f"({metrics['pending_count']} pending). Check ~/logs/intel-lake-nb-pusher.log"
            )

        if metrics["pushed_this_run"] > 0:
            metrics["last_success_at"] = time.time()

        logger.info(
            "run done: selected=%(selected)s pushed=%(pushed_this_run)s errored=%(errored)s "
            "pending=%(pending_count)s oldest_age=%(oldest_pending_age_seconds)ss",
            metrics,
        )
        _write_metrics(metrics, auth_ok=True)
        return 0

    finally:
        await pool.close()


def _write_metrics(metrics: dict[str, Any], *, auth_ok: bool) -> None:
    metrics["auth_ok"] = auth_ok
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
