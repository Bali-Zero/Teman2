#!/usr/bin/env python3
"""Intel Lake Tier 1 Router — Pro-local standalone cron (A2 design, 2026-05-13).

Bypass for Fly EventBus blocked by DISABLE_BACKGROUND_WORKERS=1 (kill-switch
from disk-full incident 2026-04-12, never removed). The Fly router code
exists at apps/backend-rag/backend/services/intel/intel_lake_router.py but
its EventBus subscriber never fires. This script applies the same rules
from Pro every 5 min instead.

Tri-LLM review (Codex + Gemini + DeepSeek) caught 7 bugs in the v1 design;
all addressed below:

1. **SELECT FOR UPDATE SKIP LOCKED** — prevents two cron instances from
   double-routing the same row when DB is slow.
2. **UPDATE ... RETURNING id** — audit log only inserts for rows that
   actually transitioned (no duplicate audit rows on no-op UPDATEs).
3. **conn.transaction() wraps UPDATE+INSERT** — atomicity guaranteed.
4. **Time-windowed failure counter** — 3 fails within 30 min, reset on
   success. State file holds (timestamp, count); old fails decay.
5. **Rules imported from `intel_lake_rules.py`** — single source of truth
   shared with the backend (2026-09-23: JSON copy retired, was drifting —
   see PENDING-ARMS row intel-lake-pro-fallback-router-rules-drift).
6. **None-safe source_domain** — handled inside `classify()`.
7. **Explicit JSONB cast** — `$N::jsonb` in SQL, never raw dict.

Schedule: LaunchAgent com.balizero.intel-lake-router.5min (300s interval).
Logs: ~/logs/intel-lake-router-cron.{log,state}
Requires: ~/.nuzantara-secrets.env with DATABASE_URL (will rewrite flycast
host to localhost:15432 via WR2 PG-proxy LaunchAgent).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("intel-lake-router-cron")

STATE_PATH = Path.home() / "logs" / "intel-lake-router-cron.state.json"
BATCH_SIZE = 100
FAILURE_WINDOW_SECONDS = 30 * 60  # 30 min sliding window for failure decay


# ─── Rules loader ───────────────────────────────────────────────────────────

# Deployed Pro path first (sibling file, no repo checkout needed there), then
# the repo checkout path (dev/test runs from a worktree). See
# scripts/intel-lake-router-a2/README.md for the deploy step that copies
# intel_lake_rules.py next to this script as ~/scripts/intel_lake_rules.py.
_RULES_MODULE_CANDIDATES = (
    Path(__file__).resolve().parent / "intel_lake_rules.py",
    Path(__file__).resolve().parents[2]
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "intel"
    / "intel_lake_rules.py",
)


def _load_rules_module() -> Any:
    """Import `intel_lake_rules.py` by path — zero backend package imports."""
    for path in _RULES_MODULE_CANDIDATES:
        if path.exists():
            spec = importlib.util.spec_from_file_location("intel_lake_rules", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise SystemExit(
        "intel_lake_rules.py not found in any of: "
        + ", ".join(str(p) for p in _RULES_MODULE_CANDIDATES)
    )


# ─── Failure tracking (time-windowed) ───────────────────────────────────────


def _load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {"failures": []}
    return {"failures": []}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state))


def _record_failure() -> int:
    """Append a failure timestamp, prune old ones, return count in window."""
    state = _load_state()
    now = time.time()
    state["failures"] = [
        ts for ts in state.get("failures", []) if (now - ts) < FAILURE_WINDOW_SECONDS
    ]
    state["failures"].append(now)
    _save_state(state)
    return len(state["failures"])


def _record_success() -> None:
    """Reset failure counter on success (transition-based)."""
    state = _load_state()
    if state.get("failures"):
        state["failures"] = []
        state["last_success_at"] = time.time()
        _save_state(state)


# ─── DATABASE_URL rewrite ───────────────────────────────────────────────────


def _resolve_database_url() -> str:
    """Read DATABASE_URL from env, rewrite Fly flycast host to local proxy."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit(
            "DATABASE_URL env not set. Source ~/.nuzantara-secrets.env first."
        )
    # Rewrite @host:port → @localhost:15432 (WR2 PG-proxy LaunchAgent forwards
    # this to nuzantara-postgres.flycast:5432).
    url = re.sub(r"@[^:/]+(:[0-9]+)?/", "@localhost:15432/", url)
    return url


# ─── Routing batch ──────────────────────────────────────────────────────────


async def route_batch(pool: asyncpg.Pool, classify: Any) -> dict[str, int]:
    """Process up to BATCH_SIZE unrouted items. Returns counts dict."""
    counts: dict[str, int] = {
        "selected": 0, "routed": 0, "noop": 0, "errors": 0,
        "nb-intel": 0, "blog": 0, "archive": 0, "needs_review": 0, "skip": 0,
    }

    async with pool.acquire() as conn:
        # SKIP LOCKED prevents two cron instances from grabbing same rows.
        # title/canonical_url are needed for the press_general content gate
        # (see intel_lake_rules.classify) — fetched eagerly here since the
        # cron already reads the whole unrouted batch every tick.
        rows = await conn.fetch(
            """
            SELECT id, source_domain, title, canonical_url
              FROM intel_items
             WHERE routing_status = 'unrouted'
             ORDER BY first_seen_at ASC
             LIMIT $1
             FOR UPDATE SKIP LOCKED
            """,
            BATCH_SIZE,
        )
        counts["selected"] = len(rows)

        if not rows:
            return counts

        for row in rows:
            item_id = row["id"]
            decision = classify(row["source_domain"], row["title"], row["canonical_url"])
            new_status = decision["status"]
            counts[new_status] = counts.get(new_status, 0) + 1

            try:
                async with conn.transaction():
                    # UPDATE WHERE unrouted + RETURNING — audit only if affected
                    affected = await conn.fetchval(
                        """
                        UPDATE intel_items
                           SET routing_status = $2,
                               routing_targets = $3::jsonb
                         WHERE id = $1::uuid
                           AND routing_status = 'unrouted'
                        RETURNING id
                        """,
                        item_id,
                        new_status,
                        json.dumps(decision["targets"]),
                    )
                    if affected is None:
                        # Someone else routed it between SELECT FOR UPDATE and
                        # this UPDATE — should not happen with SKIP LOCKED but
                        # defense-in-depth.
                        counts["noop"] += 1
                        continue
                    await conn.execute(
                        """
                        INSERT INTO intel_lake_audit_log
                            (producer_name, client_ip, request_path,
                             status_code, payload_size, error_message)
                        VALUES ('router', NULL, 'router/tier1', 200, NULL, $1)
                        """,
                        f"rule={decision['rule']} status={new_status}",
                    )
                    counts["routed"] += 1
            except Exception as exc:
                counts["errors"] += 1
                logger.exception(
                    "route_batch: failed item_id=%s domain=%s: %s",
                    item_id, row["source_domain"], exc,
                )

    return counts


# ─── Entry point ────────────────────────────────────────────────────────────


async def main() -> int:
    try:
        rules_module = _load_rules_module()
    except SystemExit as exc:
        logger.error(str(exc))
        return 2

    db_url = _resolve_database_url()
    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2, timeout=10)
    except Exception as exc:
        fails = _record_failure()
        logger.error("asyncpg pool failed (fails-in-window=%s): %s", fails, exc)
        return _alert_if_threshold(fails)
    if pool is None:
        fails = _record_failure()
        logger.error("asyncpg pool returned None (fails-in-window=%s)", fails)
        return _alert_if_threshold(fails)

    try:
        counts = await route_batch(pool, rules_module.classify)
        logger.info(
            "route_batch ok: selected=%(selected)s routed=%(routed)s noop=%(noop)s "
            "errors=%(errors)s | nb-intel=%(nb-intel)s blog=%(blog)s "
            "archive=%(archive)s needs_review=%(needs_review)s",
            counts,
        )
        if counts["errors"] > 0 and counts["routed"] == 0:
            fails = _record_failure()
            logger.warning("all rows errored (fails-in-window=%s)", fails)
            return _alert_if_threshold(fails)
        _record_success()
        return 0
    except Exception as exc:
        fails = _record_failure()
        logger.exception("route_batch crashed (fails-in-window=%s): %s", fails, exc)
        return _alert_if_threshold(fails)
    finally:
        await pool.close()


def _alert_if_threshold(failures_in_window: int) -> int:
    """Send Telegram if 3+ failures in 30 min window. Returns exit code 1."""
    if failures_in_window >= 3:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")
        if token and chat:
            import urllib.parse  # noqa: PLC0415
            import urllib.request  # noqa: PLC0415
            try:
                data = urllib.parse.urlencode({
                    "chat_id": chat,
                    "text": (
                        f"🔴 intel-lake-router-cron: {failures_in_window} failures "
                        f"in last 30min. Log: ~/logs/intel-lake-router-cron.log"
                    ),
                }).encode()
                urllib.request.urlopen(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=data,
                    timeout=10,
                )
                logger.info("Telegram alert sent (threshold breached)")
            except Exception as e:
                logger.warning("Telegram alert failed: %s", e)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
