#!/usr/bin/env python3
"""WR2 Carousel Orchestrator — autonomous workflow driver.

Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md
Phase 2.1 of WR2 autonomous carousel pipeline (Antonello 2026-05-27).

Flow:
    1. Acquire PG advisory lock by carousel_id (idempotency)
    2. State machine driver (wr2_carousel_runs):
       drafted → brief_done → storyboard_done → layout_done → critic_pass
       → rendered → awaiting_approval → approved/rejected → published
    3. Per-step: claude --print --agent <subagent> subprocess
       (cwd=/tmp, ANTHROPIC_API_KEY stripped, --max-budget-usd cap)
    4. Critic gate PASS/FAIL/RETRYABLE_FAIL (retry max 2)
    5. Playwright render PNG 1080x1350 IG 4:5
    6. Emit awaiting_approval — wr2_telegram_publish_gate.py handles approval

Env:
    DATABASE_URL            — PG via localhost:15432 proxy on Pro
    CLAUDE_OAUTH_TOKEN      — Inherited from claude --print discovery
    WR2_PUBLISH_MODE        — manual (default Day 1) | auto (in standby)
    WR2_AUTO_PUBLISH_ENABLED — false Day 1 (flag controlled, code ready)
    TELEGRAM_BOT_TOKEN      — for failure alerts
    TELEGRAM_OWNER_CHAT_ID  — default 1125336968 (Zero)

Usage:
    python scripts/wr2_carousel_orchestrator.py --carousel-id <uuid> --topic "<text>"
    python scripts/wr2_carousel_orchestrator.py --resume <carousel_id>  # idempotent
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import asyncpg

logger = logging.getLogger("wr2.orchestrator")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUBAGENTS_DIR = Path.home() / ".claude" / "agents"
_OUTPUT_BASE = Path.home() / ".claude" / "carousels"

CLAUDE_BIN = shutil.which("claude") or "/Users/nuzantara/.npm-global/bin/claude"
DEFAULT_STEP_TIMEOUT_SEC = 120
DEFAULT_RENDER_TIMEOUT_SEC = 60
MAX_CLAUDE_INVOCATIONS_PER_DRAFT = 8
CRITIC_RETRY_MAX = 2

# Pipeline steps in order (Spec §1)
PIPELINE_STEPS: tuple[dict[str, str], ...] = (
    {"name": "brief_interpreter", "agent": "wr2-brief-interpreter", "model": "claude-opus-4-7"},
    {"name": "storyboarder", "agent": "wr2-storyboarder", "model": "claude-opus-4-7"},
    {"name": "image_prompt_author", "agent": "wr2-image-prompt-author", "model": "claude-sonnet-4-6"},
    {"name": "layout_composer", "agent": "wr2-layout-composer", "model": "claude-sonnet-4-6"},
    {"name": "critic", "agent": "wr2-critic", "model": "claude-opus-4-7"},
)


class OrchestratorError(Exception):
    """Recoverable error during pipeline."""


class FatalOrchestratorError(Exception):
    """Unrecoverable — abort run, mark failed_cascade."""


async def acquire_carousel_lock(conn: asyncpg.Connection, carousel_id: str) -> bool:
    """Try to acquire PG advisory lock for idempotency.

    Returns True if acquired, False if another process holds it.
    """
    lock_key = int(hashlib.sha256(carousel_id.encode()).hexdigest()[:15], 16)
    return await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_key)


async def release_carousel_lock(conn: asyncpg.Connection, carousel_id: str) -> None:
    lock_key = int(hashlib.sha256(carousel_id.encode()).hexdigest()[:15], 16)
    await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)


async def preflight_claude_auth() -> None:
    """Spec §2.1 — fail-loud on claude --print unauthenticated."""
    try:
        r = subprocess.run(
            [CLAUDE_BIN, "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise FatalOrchestratorError(f"claude CLI unavailable: {exc}") from exc
    if r.returncode != 0 or "not authenticated" in (r.stdout + r.stderr).lower():
        raise FatalOrchestratorError(f"claude --print not authenticated (rc={r.returncode})")
    logger.info("preflight: claude auth OK")


def topic_hash(topic: str) -> str:
    return hashlib.sha256(topic.strip().lower().encode()).hexdigest()


async def get_or_create_run(
    conn: asyncpg.Connection,
    carousel_id: str | None,
    topic: str,
    session_id: str,
) -> dict[str, Any]:
    """Spec §3 — idempotent create-or-resume."""
    if carousel_id:
        row = await conn.fetchrow(
            "SELECT * FROM wr2_carousel_runs WHERE carousel_id = $1",
            uuid.UUID(carousel_id),
        )
        if row:
            return dict(row)

    th = topic_hash(topic)
    # Reuse active run if exists
    active = await conn.fetchrow(
        """
        SELECT * FROM wr2_carousel_runs
        WHERE topic_hash = $1
          AND state NOT IN ('published','rejected','failed_cascade','stale_abandoned')
        ORDER BY created_at DESC LIMIT 1
        """,
        th,
    )
    if active:
        logger.info(f"resuming active run carousel_id={active['carousel_id']}")
        return dict(active)

    publish_mode = os.environ.get("WR2_PUBLISH_MODE", "manual")
    if publish_mode not in ("manual", "auto"):
        publish_mode = "manual"

    new_id = uuid.uuid4()
    output_dir = _OUTPUT_BASE / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    row = await conn.fetchrow(
        """
        INSERT INTO wr2_carousel_runs
            (carousel_id, topic, topic_hash, state, session_id, output_dir, publish_mode)
        VALUES ($1, $2, $3, 'drafted', $4, $5, $6)
        RETURNING *
        """,
        new_id, topic, th, session_id, str(output_dir), publish_mode,
    )
    logger.info(f"created run carousel_id={new_id} mode={publish_mode}")
    return dict(row)


async def transition_state(
    conn: asyncpg.Connection,
    carousel_id: uuid.UUID,
    new_state: str,
    *,
    error: str | None = None,
) -> None:
    """Spec §3.4 — ACID transition. File writes must precede DB update."""
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE wr2_carousel_runs
               SET state = $1,
                   state_updated_at = now(),
                   last_error = $2,
                   completed_at = CASE
                       WHEN $1 IN ('published','rejected','failed_cascade','stale_abandoned')
                       THEN now() ELSE completed_at END
             WHERE carousel_id = $3
            """,
            new_state, error, carousel_id,
        )
    logger.info(f"state {carousel_id} → {new_state}")


def validate_subagent_exists(agent_name: str) -> None:
    """Spec §2.3 Pitfall #1 — silent fallback to default model if missing."""
    path = _SUBAGENTS_DIR / f"{agent_name}.md"
    if not path.is_file():
        raise FatalOrchestratorError(f"subagent .md not found: {path}")


def build_env_for_claude() -> dict[str, str]:
    """Strip ANTHROPIC_API_KEY per CLAUDE.md §5 ban."""
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


async def call_subagent(
    agent_name: str,
    model: str,
    user_prompt: str,
    *,
    budget_usd: float = 0.50,
    timeout_sec: int = DEFAULT_STEP_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Spec §2.3 — claude --print --agent subprocess wrapper."""
    validate_subagent_exists(agent_name)

    cmd = [
        CLAUDE_BIN, "--print",
        "--agent", agent_name,
        "--model", model,
        "--output-format", "json",
        "--max-budget-usd", f"{budget_usd:.2f}",
        "--no-session-persistence",
        "--exclude-dynamic-system-prompt-sections",
        user_prompt,
    ]

    t0 = time.monotonic()
    try:
        r = await asyncio.create_subprocess_exec(
            *cmd,
            cwd="/tmp",  # Spec §2.3 Pitfall #2 — avoid CLAUDE.md overflow
            env=build_env_for_claude(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(r.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError as exc:
        raise OrchestratorError(f"{agent_name} timeout after {timeout_sec}s") from exc

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if r.returncode != 0:
        err_msg = (stderr.decode("utf-8", errors="replace") or "")[:500]
        raise OrchestratorError(
            f"{agent_name} exit {r.returncode} ({elapsed_ms}ms): {err_msg}"
        )

    try:
        payload = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        snippet = stdout.decode("utf-8", errors="replace")[:300]
        raise OrchestratorError(
            f"{agent_name} JSON decode failed: {exc} (snippet: {snippet!r})"
        ) from exc

    if payload.get("is_error"):
        raise OrchestratorError(
            f"{agent_name} payload is_error: {payload.get('error_message', '?')}"
        )

    payload["_elapsed_ms"] = elapsed_ms
    payload["_agent"] = agent_name
    payload["_model"] = model
    return payload


async def record_metric(
    conn: asyncpg.Connection,
    carousel_id: uuid.UUID,
    step_name: str,
    step_index: int,
    payload: dict[str, Any],
    *,
    tier: int = 1,
    success: bool = True,
    error_class: str | None = None,
    error_message: str | None = None,
    retry_count: int = 0,
) -> None:
    """Spec §5.2 — per-step metrics persistence."""
    token_usage = payload.get("token_usage", {}) if isinstance(payload, dict) else {}
    cost = payload.get("cost_usd", 0.0) if isinstance(payload, dict) else 0.0
    await conn.execute(
        """
        INSERT INTO wr2_orchestrator_metrics
            (carousel_id, step_name, step_index, model, tier,
             latency_ms, tokens_in, tokens_out, cost_usd_figurative,
             retry_count, success, error_class, error_message)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        """,
        carousel_id, step_name, step_index,
        payload.get("_model") if isinstance(payload, dict) else None,
        tier,
        payload.get("_elapsed_ms") if isinstance(payload, dict) else None,
        token_usage.get("input_tokens"), token_usage.get("output_tokens"),
        cost, retry_count, success, error_class, error_message,
    )


def write_artifact(output_dir: Path, name: str, content: Any) -> Path:
    """Spec §3.4 — fsync before DB transition."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / name
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(content, (dict, list)):
            json.dump(content, f, indent=2, ensure_ascii=False)
        else:
            f.write(str(content))
        f.flush()
        os.fsync(f.fileno())
    return path


async def run_pipeline_step(
    conn: asyncpg.Connection,
    run: dict[str, Any],
    step: dict[str, str],
    step_index: int,
    prior_artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Execute single step + persist artifact + record metric."""
    carousel_id = run["carousel_id"]
    output_dir = Path(run["output_dir"])

    user_prompt = json.dumps(
        {
            "carousel_id": str(carousel_id),
            "topic": run["topic"],
            "step": step["name"],
            "prior": prior_artifacts,
        },
        ensure_ascii=False,
    )

    try:
        payload = await call_subagent(step["agent"], step["model"], user_prompt)
    except OrchestratorError as exc:
        await record_metric(
            conn, carousel_id, step["name"], step_index, {},
            success=False, error_class=type(exc).__name__, error_message=str(exc)[:500],
        )
        raise

    artifact_path = write_artifact(output_dir, f"{step['name']}.json", payload)
    logger.info(f"step {step['name']} → {artifact_path.name} ({payload.get('_elapsed_ms')}ms)")

    await record_metric(conn, carousel_id, step["name"], step_index, payload)
    return payload


async def render_playwright(
    output_dir: Path,
    layout_payload: dict[str, Any],
    *,
    timeout_sec: int = DEFAULT_RENDER_TIMEOUT_SEC,
) -> list[Path]:
    """Spec §1 step 6 — Playwright render PNG 1080x1350 IG 4:5.

    Stub: orchestrator delegates to existing scripts/wr2_canva_pdf_render.py
    or future scripts/wr2_playwright_carousel_render.py. For Phase 2.1
    ship-able skeleton, we emit a placeholder marker and let Phase 3 wire
    the real render path.
    """
    slides = layout_payload.get("slides", []) if isinstance(layout_payload, dict) else []
    slides_dir = output_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[Path] = []
    for i, slide in enumerate(slides):
        marker = slides_dir / f"slide_{i:02d}.placeholder.json"
        with open(marker, "w", encoding="utf-8") as f:
            json.dump(slide, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        rendered.append(marker)

    logger.warning(
        f"Playwright render stub — {len(rendered)} slide markers written. "
        "Phase 3 will wire real render path."
    )
    return rendered


def critic_verdict(critic_payload: dict[str, Any]) -> str:
    """Spec §6 — parse critic output into PASS / RETRYABLE_FAIL / FAIL.

    Codex amendment: critic_verdict enum, NOT boolean. Strict parse.
    """
    if not isinstance(critic_payload, dict):
        return "FAIL"
    verdict = (critic_payload.get("verdict") or "").upper().strip()
    if verdict not in ("PASS", "FAIL", "RETRYABLE_FAIL"):
        logger.warning(f"critic returned unknown verdict={verdict!r}, defaulting to FAIL")
        return "FAIL"
    return verdict


async def run_pipeline(
    conn: asyncpg.Connection,
    run: dict[str, Any],
) -> dict[str, Any]:
    """Drive state machine through pipeline."""
    carousel_id = run["carousel_id"]
    output_dir = Path(run["output_dir"])
    artifacts: dict[str, Any] = {}

    # Steps 1-4 (brief, storyboard, image-prompt, layout)
    state_after_step = {
        "brief_interpreter": "brief_done",
        "storyboarder": "storyboard_done",
        "image_prompt_author": "storyboard_done",  # not a state transition
        "layout_composer": "layout_done",
    }

    for i, step in enumerate(PIPELINE_STEPS):
        if step["name"] == "critic":
            break  # critic handled separately with retry
        payload = await run_pipeline_step(conn, run, step, i, artifacts)
        artifacts[step["name"]] = payload
        next_state = state_after_step.get(step["name"])
        if next_state and next_state != run["state"]:
            await transition_state(conn, carousel_id, next_state)
            run["state"] = next_state

    # Step 5 — critic gate with retry max 2
    critic_step = PIPELINE_STEPS[4]
    for attempt in range(CRITIC_RETRY_MAX + 1):
        try:
            critic_payload = await run_pipeline_step(
                conn, run, critic_step, 4 + attempt, artifacts
            )
            verdict = critic_verdict(critic_payload)
            artifacts["critic"] = critic_payload
            artifacts["critic_verdict"] = verdict

            if verdict == "PASS":
                await transition_state(conn, carousel_id, "critic_pass")
                break
            if verdict == "FAIL":
                raise FatalOrchestratorError(
                    f"critic FAIL (attempt {attempt + 1}): "
                    f"{critic_payload.get('reason', 'no reason given')}"
                )
            # RETRYABLE_FAIL → loop
            logger.warning(f"critic RETRYABLE_FAIL attempt {attempt + 1}/{CRITIC_RETRY_MAX + 1}")
        except OrchestratorError:
            if attempt == CRITIC_RETRY_MAX:
                raise
    else:
        raise FatalOrchestratorError(
            f"critic RETRYABLE_FAIL exhausted after {CRITIC_RETRY_MAX + 1} attempts"
        )

    # Step 6 — Playwright render
    rendered = await render_playwright(output_dir, artifacts.get("layout_composer", {}))
    artifacts["rendered_paths"] = [str(p) for p in rendered]
    write_artifact(output_dir, "rendered.json", {"slides": artifacts["rendered_paths"]})
    await transition_state(conn, carousel_id, "rendered")

    # Step 7 — awaiting approval (Telegram gate consumer takes over)
    await transition_state(conn, carousel_id, "awaiting_approval")
    logger.info(f"carousel {carousel_id} awaiting_approval — Telegram gate next")

    return artifacts


async def publish_after_approval(
    conn: asyncpg.Connection,
    carousel_id: str,
    slides_dir: Path,
    caption: str,
) -> dict[str, Any]:
    """Spec §8 — post-approval publish call.

    Codex amendment: write `wr2_publish_attempts` BEFORE Meta call,
    update post-response. Idempotency key prevents double-publish via
    UNIQUE constraint (mig 198). Reconciliation by idempotency_key on
    retry / orchestrator restart.

    Returns dict {status, ig_media_id?, permalink?, error?}.
    """
    from backend.services.publisher.ig_publisher import IGPublisher
    from backend.services.publisher.types import DraftPayload, SlidePayload

    # idempotency: sha256(carousel_id || rendered_paths). Stable across retries.
    slide_files = sorted(slides_dir.glob("slide_*.png"))
    rendered_concat = "|".join(p.name for p in slide_files)
    idempotency_key = hashlib.sha256(
        f"{carousel_id}|{rendered_concat}".encode()
    ).hexdigest()

    # PRE-INSERT publish_attempts (status=pending). UNIQUE(idempotency_key) catches double-call.
    try:
        attempt_id = await conn.fetchval(
            """
            INSERT INTO wr2_publish_attempts (
                carousel_id, idempotency_key, status, attempted_at
            ) VALUES ($1, $2, 'pending', NOW())
            ON CONFLICT (idempotency_key) DO UPDATE SET attempted_at = NOW()
            RETURNING id
            """,
            carousel_id, idempotency_key,
        )
    except (asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
        logger.error(f"publish_attempts insert failed: {exc}")
        return {"status": "db_error", "error": str(exc)}

    # Call Meta Graph
    items = [
        SlidePayload(
            image_url=None,  # publisher must upload local files (TODO Phase 4)
            caption=caption if i == 0 else "",
            local_path=str(p),
        )
        for i, p in enumerate(slide_files)
    ]
    draft = DraftPayload(carousel_id=carousel_id, slides=items, caption=caption)

    publisher = IGPublisher()
    try:
        result = await publisher.publish(draft)
    except Exception as exc:
        logger.exception(f"IG publish exception: {exc}")
        await conn.execute(
            """UPDATE wr2_publish_attempts
               SET status='failed', error_message=$2, completed_at=NOW()
               WHERE id=$1""",
            attempt_id, str(exc),
        )
        return {"status": "exception", "error": str(exc)}

    # Update post-response
    if result.success:
        await conn.execute(
            """UPDATE wr2_publish_attempts
               SET status='ok', ig_media_id=$2, permalink=$3, completed_at=NOW()
               WHERE id=$1""",
            attempt_id, result.external_id, result.permalink,
        )
        await transition_state(conn, carousel_id, "published")
        return {
            "status": "ok",
            "ig_media_id": result.external_id,
            "permalink": result.permalink,
        }
    await conn.execute(
        """UPDATE wr2_publish_attempts
           SET status='failed', error_message=$2, completed_at=NOW()
           WHERE id=$1""",
        attempt_id, result.error or "unknown",
    )
    return {"status": "failed", "error": result.error}


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WR2 Carousel Orchestrator")
    parser.add_argument("--carousel-id", help="Resume existing carousel_id (UUID)")
    parser.add_argument("--topic", help="Topic text (required if not --resume)")
    parser.add_argument("--session-id", help="Worktree session id (default: env)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not args.carousel_id and not args.topic:
        parser.error("either --carousel-id or --topic required")

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL env required")
        return 74  # EX_CONFIG

    session_id = args.session_id or os.environ.get("AGENT_TASK_ID") or f"manual-{int(time.time())}"

    try:
        await preflight_claude_auth()
    except FatalOrchestratorError as exc:
        logger.error(f"preflight failed: {exc}")
        return 75  # EX_TEMPFAIL — launchd retry

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2, timeout=10)
    try:
        async with pool.acquire() as conn:
            run = await get_or_create_run(conn, args.carousel_id, args.topic or "", session_id)
            carousel_id = run["carousel_id"]

            lock_ok = await acquire_carousel_lock(conn, str(carousel_id))
            if not lock_ok:
                logger.warning(f"another orchestrator holds lock for {carousel_id} — exit")
                return 0

            try:
                await run_pipeline(conn, run)
                return 0
            except FatalOrchestratorError as exc:
                logger.error(f"pipeline FATAL: {exc}")
                await transition_state(
                    conn, carousel_id, "failed_cascade", error=str(exc)[:500]
                )
                return 1
            except OrchestratorError as exc:
                logger.error(f"pipeline error: {exc}")
                await transition_state(
                    conn, carousel_id, "failed_cascade", error=str(exc)[:500]
                )
                return 1
            finally:
                await release_carousel_lock(conn, str(carousel_id))
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
