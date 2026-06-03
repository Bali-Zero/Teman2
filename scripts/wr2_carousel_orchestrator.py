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
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import asyncpg

# Local regex for layout-composer JSON fence extraction (mirrors parser-fix
# branch _CRITIC_JSON_FENCE_RE). Promote to shared util when both branches merge.
_CRITIC_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

logger = logging.getLogger("wr2.orchestrator")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUBAGENTS_DIR = Path.home() / ".claude" / "agents"
_OUTPUT_BASE = Path.home() / ".claude" / "carousels"
# Canonical carousel output dir consumed by wr2-layout-composer + wr2-critic.
# The critic's mandatory pre-Rubric vision sweep reads
# apps/war-room/output/carousel/<slug>/carousel.pdf — the orchestrator MUST
# render into the same slug dir so <draft_id> == slugify(topic). See
# docs/runbooks (S8 render fix) for the path-divergence root cause.
_WAR_ROOM_CAROUSEL_BASE = _REPO_ROOT / "apps" / "war-room" / "output" / "carousel"


def slugify(topic: str) -> str:
    """Topic → on-disk carousel slug (e.g. 'KITAS C312 Expat Workers 2026' →
    'kitas-c312-expat-workers-2026'). Matches the war-room slug convention the
    layout-composer/critic agents hardcode. Empty/degenerate topics fall back
    to a stable placeholder so the path is always well-formed."""
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s or "untitled-carousel"

CLAUDE_BIN = shutil.which("claude") or "/Users/nuzantara/.npm-global/bin/claude"
DEFAULT_STEP_TIMEOUT_SEC = 300
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
    # Render into the canonical war-room slug dir so the critic's mandatory
    # vision sweep finds carousel.pdf at apps/war-room/output/carousel/<slug>/.
    # <draft_id> == slugify(topic). (session_id stays in the DB for traceability.)
    output_dir = _WAR_ROOM_CAROUSEL_BASE / slugify(topic)
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
    budget_usd: float = 1.50,
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
            # Tell the subagents WHERE the carousel lives on disk so the
            # layout-composer writes HTML/_base.css/logo.png/qr.png into the
            # SAME slides dir the hero generator + renderer use, and the critic
            # reads carousel.pdf from the right path. layout-composer documents
            # output_dir as input #3 — previously never supplied (agent guessed).
            "output_dir": str(output_dir),
            "slides_dir": str(output_dir / "slides"),
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


def _resolve_slide_html_paths(layout_payload: dict[str, Any], output_dir: Path) -> list[Path]:
    """Extract HTML slide paths from layout-composer Claude SDK envelope.

    Envelope shape (per `~/.claude/carousels/manual-1779819591/layout_composer.json`):
        {"type": "result", "result": "<prose>\n\n```json\n{\"slides_written\":
         [\"/path/<NN>.html\", ...]}\n```\n<more>"}

    Falls back to scanning `output_dir/slides/*.html` if envelope parsing yields nothing.

    The layout-composer is an LLM and sometimes writes degenerate `slides_written`
    paths (e.g. abbreviated `.../slides/01.html`) that don't resolve on disk.
    Envelope paths are therefore VALIDATED — accepted only if they actually exist
    (tried both verbatim and relative to output_dir) — else we fall through to the
    authoritative filesystem scan, since output_dir is the source of truth.
    """

    def _validate(paths: list[Any]) -> list[Path]:
        resolved: list[Path] = []
        for p in paths:
            if not isinstance(p, str):
                continue
            cand = Path(p)
            if cand.exists():
                resolved.append(cand)
                continue
            # Retry relative to the authoritative output_dir / its slides dir.
            alt = output_dir / "slides" / cand.name
            if alt.exists():
                resolved.append(alt)
        return resolved

    if not isinstance(layout_payload, dict):
        return _scan_slides_dir(output_dir)
    # 1. Bare top-level (test fixtures, future direct schema)
    direct = layout_payload.get("slides_written")
    if isinstance(direct, list) and direct:
        validated = _validate(direct)
        if validated:
            return validated
    # 2. Claude SDK envelope nested in result text
    result_text = layout_payload.get("result")
    if isinstance(result_text, str):
        match = _CRITIC_JSON_FENCE_RE.search(result_text)
        if match:
            try:
                parsed = json.loads(match.group(1))
                paths = parsed.get("slides_written") if isinstance(parsed, dict) else None
                if isinstance(paths, list) and paths:
                    validated = _validate(paths)
                    if validated:
                        return validated
            except json.JSONDecodeError:
                pass
    # 3. Fallback: filesystem scan (authoritative — output_dir is source of truth)
    return _scan_slides_dir(output_dir)


def _scan_slides_dir(output_dir: Path) -> list[Path]:
    """Authoritative slide-HTML discovery: glob output_dir/slides/NN.html."""
    slides_dir = output_dir / "slides"
    if slides_dir.is_dir():
        return sorted(slides_dir.glob("[0-9]*.html"))
    return []


async def _render_html_to_png(
    html_path: Path,
    png_path: Path,
    *,
    timeout_ms: int = 30000,
) -> None:
    """Render a single HTML slide to 1080x1350 PNG via Playwright Chromium.

    Pattern from `~/.claude/skills/bali-zero-brand/_render_smoke_test.py`:
      - viewport 1080x1350, device_scale_factor=1
      - wait `document.fonts.ready` for Montserrat/IBM Plex Mono
      - screenshot full_page=False, omit_background=False
    """
    from playwright.async_api import async_playwright  # lazy import

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1080, "height": 1350},
                device_scale_factor=1,
            )
            page = await context.new_page()
            page.set_default_timeout(timeout_ms)
            await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            try:
                await page.evaluate("() => document.fonts.ready")
            except Exception as exc:
                logger.warning(f"font wait failed for {html_path.name}: {exc}")
            await page.screenshot(
                path=str(png_path),
                full_page=False,
                omit_background=False,
            )
        finally:
            await browser.close()


def _compose_pdf(png_paths: list[Path], pdf_path: Path) -> None:
    """Combine PNG slides into a multipage PDF via PIL.

    PIL `save(save_all=True, append_images=[...])` writes one PDF page per image,
    preserving 1080x1350 dimensions. Order preserved from input list.
    """
    from PIL import Image  # lazy import

    if not png_paths:
        raise ValueError("cannot compose PDF from empty PNG list")
    images: list[Image.Image] = []
    for p in png_paths:
        img = Image.open(p)
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)
    first, *rest = images
    first.save(
        str(pdf_path),
        save_all=True,
        append_images=rest,
        format="PDF",
        resolution=72.0,
    )
    for img in images:
        img.close()


async def generate_hero_images(
    output_dir: Path,
    image_prompt_payload: dict[str, Any],
    storyboard_payload: dict[str, Any],
    *,
    timeout_sec: int = 240,
) -> list[Path]:
    """Spec §1 step 3.5 — Codex $imagegen hero JPG generation per hero-flagged slide.

    Reads image-prompt-author output (slide-indexed prompts) + storyboarder
    output (hero flag per slide). For each slide with hero=true, dispatch
    `codex exec --sandbox workspace-write "$imagegen <prompt>"` and move the
    generated image to `slides/<NN>-hero.jpg` (1-based, matching `NN.html`).

    Codex $imagegen quirk (lessons learned 2026-05-06): ignores output path
    in prompt, writes to ~/.codex/generated_images/<uuid>/. Workflow:
    1. exec codex
    2. find latest file in ~/.codex/generated_images/ (mtime within last 30s)
    3. mv to slides/<NN>-hero.jpg

    Returns list of generated paths. Empty list if no hero slides.
    """
    slides_dir = output_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # Smoke-test escape hatch: skip the (paid, slow) Codex $imagegen calls when
    # validating the path/ordering wiring. Heroes are non-fatal downstream.
    if os.environ.get("WR2_SKIP_IMAGEGEN") == "1":
        logger.warning("WR2_SKIP_IMAGEGEN=1 — skipping hero image generation")
        return []

    codex_bin = shutil.which("codex") or "/opt/homebrew/bin/codex"

    if not Path(codex_bin).is_file():
        logger.warning(f"codex CLI not found at {codex_bin} — skipping hero generation")
        return []

    # Extract storyboarder slide specs (parse JSON from .result blob)
    raw_story = storyboard_payload.get("result", "") if isinstance(storyboard_payload, dict) else ""
    raw_prompts = image_prompt_payload.get("result", "") if isinstance(image_prompt_payload, dict) else ""
    if not raw_story or not raw_prompts:
        logger.warning("missing storyboarder/image_prompt payloads — skipping hero generation")
        return []

    # Best-effort JSON extraction (subagents emit JSON inside ```json fences)
    def _extract_json(blob: str, want_keys: tuple[str, ...]) -> dict[str, Any]:
        """Extract a JSON object from an LLM result blob, preferring the object
        that actually carries one of `want_keys` (a non-empty list).

        The LLM sometimes emits MULTIPLE ```json fences (e.g. a metadata header
        AND the slides payload, or an audit narrative + a header), so we scan
        ALL fences and pick the one with the wanted array — not blindly the
        first. Falls back to any parseable fence, then the whole blob.
        """
        import re as _re

        fences = _re.findall(r"```json\s*(\{.*?\})\s*```", blob, _re.DOTALL)
        candidates: list[dict[str, Any]] = []
        for frag in fences:
            try:
                obj = json.loads(frag)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                candidates.append(obj)
        # Prefer a candidate that carries a non-empty wanted array.
        for obj in candidates:
            for k in want_keys:
                v = obj.get(k)
                if isinstance(v, list) and v:
                    return obj
        if candidates:
            return candidates[0]
        # No fence parsed — try the whole blob as raw JSON.
        try:
            obj = json.loads(blob)
            return obj if isinstance(obj, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    story = _extract_json(raw_story, ("slides",))
    prompts = _extract_json(raw_prompts, ("slides", "prompts"))
    slides = story.get("slides", []) if isinstance(story, dict) else []
    # image-prompt-author emits the prompt array under "slides" (1-based index
    # per entry). Fall back to "prompts" for back-compat with any older artifact.
    prompt_list = (
        (prompts.get("slides") or prompts.get("prompts", []))
        if isinstance(prompts, dict)
        else []
    )

    if not slides or not prompt_list:
        # Loud, not silent: a slides=0 here means the storyboarder returned a
        # narrative/metadata-only result with no slides array. Log a snippet of
        # the raw blob so the failure is diagnosable instead of mysterious.
        logger.warning(
            "storyboarder result keys=%s (slides present=%s); raw head: %s",
            list(story.keys()) if isinstance(story, dict) else type(story).__name__,
            bool(slides),
            raw_story[:300].replace("\n", " "),
        )
        logger.warning(
            f"unable to extract slides/prompts (slides={len(slides)} prompts={len(prompt_list)}) — skip hero generation"
        )
        return []

    generated: list[Path] = []
    codex_image_dir = Path.home() / ".codex" / "generated_images"

    for pos, slide in enumerate(slides):
        # storyboarder marks hero slides with "is_hero_image" (boolean);
        # accept legacy "hero" too.
        if not (slide.get("is_hero_image") or slide.get("hero")):
            continue
        # Both storyboarder and image-prompt-author use 1-based "index".
        # Use the slide's own index (fall back to 1-based enumerate position).
        slide_index = slide.get("index") or (pos + 1)
        # Match the prompt entry by its 1-based index (NOT enumerate position).
        prompt_text = None
        for p in prompt_list:
            if isinstance(p, dict) and (
                p.get("index") == slide_index or p.get("slide_index") == slide_index
            ):
                prompt_text = p.get("prompt") or p.get("text")
                break
        # Last-resort: the storyboarder slide may carry a placeholder image_prompt.
        if not prompt_text:
            prompt_text = slide.get("image_prompt")

        if not prompt_text:
            logger.warning(f"slide {slide_index} hero=true but no prompt found")
            continue

        # 1-based name to match the layout HTML (01.html → 01-hero.jpg).
        target_path = slides_dir / f"{slide_index:02d}-hero.jpg"
        codex_prompt = f"$imagegen {prompt_text}"
        t0 = time.monotonic()

        try:
            r = await asyncio.create_subprocess_exec(
                codex_bin, "exec", "--sandbox", "workspace-write",
                "--skip-git-repo-check", codex_prompt,
                cwd="/tmp",
                env={**os.environ, "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(r.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            logger.warning(f"codex $imagegen slide {slide_index} timeout {timeout_sec}s")
            continue
        except (FileNotFoundError, OSError) as exc:
            logger.warning(f"codex spawn failed slide {slide_index}: {exc}")
            continue

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if r.returncode != 0:
            err = (stderr.decode("utf-8", errors="replace") or "")[:300]
            logger.warning(f"codex $imagegen slide {slide_index} exit {r.returncode}: {err}")
            continue

        # Find most recent file in ~/.codex/generated_images/ (Codex CLI quirk)
        if not codex_image_dir.is_dir():
            logger.warning(f"codex image dir {codex_image_dir} not found post-exec")
            continue
        candidates = sorted(
            codex_image_dir.rglob("*.[jp][pn]g"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        recent = [p for p in candidates if time.time() - p.stat().st_mtime < 60]
        if not recent:
            logger.warning(f"no recent codex output for slide {slide_index} (looked in {codex_image_dir})")
            continue

        try:
            shutil.copy2(recent[0], target_path)
            generated.append(target_path)
            logger.info(f"hero slide {slide_index} → {target_path.name} ({elapsed_ms}ms)")
        except OSError as exc:
            logger.warning(f"copy hero {slide_index} failed: {exc}")

    logger.info(f"generated {len(generated)} hero images")
    return generated


_BRAND_SKILL_DIR = Path.home() / ".claude" / "skills" / "bali-zero-brand"
# Canonical wordmark the brand uses ("3 ALI ZERO" with the 3 stacked). The LLM
# layout-composer occasionally emits a literal "BALI ZERO" — normalize it.
_WORDMARK_RE = re.compile(
    r'(<div[^>]*class="logo"[^>]*>)\s*BALI\s*ZERO\s*(</div>)', re.IGNORECASE
)
_WORDMARK_CANONICAL = r"\g<1>3<br/>ALI ZERO\g<2>"


def _ensure_brand_assets(slides_dir: Path) -> None:
    """Copy logo.png (+ _base.css) from the brand skill into the slides dir so
    the HTML's `url('logo.png')` and `../_base.css`/`./_base.css` resolve.
    Mirrors the known-good manual _compose.py. Non-fatal if the source is
    missing (logged), so render still proceeds (critic will flag it)."""
    for asset in ("assets/logo.png", "layouts/_base.css"):
        src = _BRAND_SKILL_DIR / asset
        dst = slides_dir / Path(asset).name
        try:
            if src.is_file() and not dst.is_file():
                shutil.copy2(src, dst)
                logger.info(f"brand asset co-located: {dst.name}")
            elif not src.is_file():
                logger.warning(f"brand asset source missing: {src}")
        except OSError as exc:
            logger.warning(f"failed to copy brand asset {asset}: {exc}")


def _normalize_wordmark(html_path: Path) -> None:
    """Rewrite a non-canonical `.logo` wordmark ('BALI ZERO') to the canonical
    '3<br/>ALI ZERO' in place. Deterministic; no-op if already canonical."""
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return
    new_text, n = _WORDMARK_RE.subn(_WORDMARK_CANONICAL, text)
    if n:
        html_path.write_text(new_text, encoding="utf-8")
        logger.info(f"normalized wordmark in {html_path.name} ({n} fix)")


async def render_playwright(
    output_dir: Path,
    layout_payload: dict[str, Any],
    *,
    timeout_sec: int = DEFAULT_RENDER_TIMEOUT_SEC,
) -> list[Path]:
    """Spec §1 step 6 — Playwright render PNG 1080x1350 IG 4:5 + carousel.pdf.

    Resolves HTML slide paths from the layout-composer envelope, renders each
    to PNG via headless Chromium (viewport 1080x1350), then composes
    `carousel.pdf` via PIL. PNG paths are returned (PDF path side-effect on
    disk — critic + Pre-Rubric vision sweep reads it from output_dir).

    Per-slide timeout 30s default; total wall ~30-60s for 7-slide carousel.
    Non-fatal per-slide failure is logged but does not abort — partial render
    surfaces in critic verdict instead of FatalOrchestratorError.
    """
    slides_dir = output_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # Co-locate the brand assets the HTML references. The layout-composer agent
    # only copies _base.css (per its prompt), NOT logo.png — but _base.css does
    # `.logo { background-image: url('logo.png') }`, so without the asset the
    # logo is invisible (critic Article 4 hard-fail). Mirror the known-good
    # manual _compose.py: copy logo.png (+ _base.css as belt-and-suspenders).
    _ensure_brand_assets(slides_dir)

    html_paths = _resolve_slide_html_paths(layout_payload, output_dir)
    if not html_paths:
        logger.warning(
            "render_playwright: no HTML slide paths resolved from layout_payload "
            "(neither slides_written nor envelope nor filesystem scan). "
            "Writing empty placeholder marker."
        )
        marker = slides_dir / "no_slides_resolved.placeholder.json"
        marker.write_text(json.dumps({"reason": "no html paths"}, indent=2))
        return [marker]

    logger.info(f"render_playwright: rendering {len(html_paths)} slides")
    per_slide_timeout_ms = max(5000, (timeout_sec * 1000) // max(len(html_paths), 1))

    png_paths: list[Path] = []
    for html_path in html_paths:
        if not html_path.exists():
            logger.warning(f"slide HTML missing at {html_path}, skipping")
            continue
        # Normalize the non-canonical wordmark the LLM sometimes writes
        # ("BALI ZERO" → canonical "3<br/>ALI ZERO"); deterministic, in place.
        _normalize_wordmark(html_path)
        # Name the PNG from the HTML stem (preserves 1-based 01..NN), NOT a
        # 0-based enumerate counter (off-by-one cosmetic bug).
        png_path = slides_dir / f"{html_path.stem}-rendered.png"
        try:
            await _render_html_to_png(html_path, png_path, timeout_ms=per_slide_timeout_ms)
            png_paths.append(png_path)
            logger.info(f"slide {html_path.stem}: rendered → {png_path.name}")
        except Exception as exc:
            logger.warning(f"slide {html_path.stem}: render failed ({exc!s}), continuing")

    if not png_paths:
        logger.warning("render_playwright: zero PNGs rendered, skipping PDF composition")
        return png_paths

    # Compose PDF (Pre-Rubric vision sweep + IG carousel deliverable)
    pdf_path = output_dir / "carousel.pdf"
    try:
        _compose_pdf(png_paths, pdf_path)
        logger.info(f"carousel.pdf composed: {pdf_path} ({len(png_paths)} pages)")
    except Exception as exc:
        logger.warning(f"PDF composition failed: {exc!s}")

    write_artifact(
        output_dir,
        "rendered.json",
        {"slides": [str(p) for p in png_paths], "pdf": str(pdf_path) if pdf_path.exists() else None},
    )
    return png_paths


_CRITIC_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_critic_verdict_dict(critic_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract structured verdict dict from Claude SDK critic envelope.

    Claude SDK result-envelope shape (empirically verified on pilot-3 critic.json
    2026-05-27 02:33 carousel 1596d8fd-c2a5-4182-b27f-2266977c99fc):

        {"type": "result", "is_error": false, "result": "<prose with embedded
         ```json {...} ``` code fence>", ...}

    The structured verdict (overall_verdict, binary_carousel_verdict, slides[],
    hard_failures[]) lives inside the fenced JSON inside the `result` text field,
    NOT at top level. Pre-fix orchestrator looked for top-level `verdict` key and
    always saw empty string → FatalOrchestratorError → state failed_cascade.

    Resolution order:
    1. If payload already has `binary_carousel_verdict` or `overall_verdict` at
       top level (bare JSON shape), return payload directly.
    2. Scan ALL ```json fences in `result`, preferring the object that carries a
       verdict key (the critic may emit multiple fences).
    3. Try the whole `result` text as JSON.
    4. PROSE FALLBACK: the critic sometimes emits NO fence at all and writes the
       verdict inline as markdown, e.g. **`binary_carousel_verdict: FAIL`**.
       Scan for the verdict keys as inline text and synthesize a dict.
    5. Otherwise return empty dict.
    """
    if not isinstance(critic_payload, dict):
        return {}
    if "binary_carousel_verdict" in critic_payload or "overall_verdict" in critic_payload:
        return critic_payload
    result_text = critic_payload.get("result")
    if not isinstance(result_text, str):
        return {}
    # 2. Scan ALL json fences, prefer the one carrying a verdict key.
    fenced: list[dict[str, Any]] = []
    for frag in _CRITIC_JSON_FENCE_RE.findall(result_text):
        try:
            obj = json.loads(frag)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            fenced.append(obj)
    for obj in fenced:
        if "binary_carousel_verdict" in obj or "overall_verdict" in obj:
            return obj
    if fenced:
        return fenced[0]
    # 3. Whole text as JSON.
    try:
        whole = json.loads(result_text)
        if isinstance(whole, dict):
            return whole
    except (json.JSONDecodeError, TypeError):
        pass
    # 4. Prose fallback — verdict written inline as markdown, no JSON fence.
    # Match only the long, specific keys (a bare `verdict:` regex would match the
    # suffix of `binary_carousel_verdict`), and constrain values to the real enum
    # tokens (so it can't grab unrelated prose like "objective ... PASS").
    prose: dict[str, Any] = {}
    for key, allowed in (
        ("binary_carousel_verdict", ("PASS", "FAIL")),
        ("overall_verdict", ("pass", "soft_fail", "hard_fail")),
    ):
        m = re.search(
            rf"{key}[\"'`*:\s]*\b(" + "|".join(allowed) + r")\b",
            result_text,
            re.IGNORECASE,
        )
        if m:
            prose[key] = m.group(1)
    return prose


def critic_verdict(critic_payload: dict[str, Any]) -> str:
    """Spec §6 — parse critic output into PASS / RETRYABLE_FAIL / FAIL.

    Codex amendment: critic_verdict enum, NOT boolean. Strict parse.

    Reads structured verdict from Claude SDK envelope via `_extract_critic_verdict_dict`.
    Maps semantic critic taxonomy → orchestrator enum:
      - overall_verdict=pass OR binary_carousel_verdict=PASS → PASS
      - overall_verdict=soft_fail                             → RETRYABLE_FAIL
      - overall_verdict=hard_fail OR binary_carousel_verdict=FAIL → FAIL
      - bare `verdict` key (legacy): trusted as-is if PASS/FAIL/RETRYABLE_FAIL
    """
    if not isinstance(critic_payload, dict):
        return "FAIL"
    verdict_dict = _extract_critic_verdict_dict(critic_payload)
    # Bare legacy verdict (backward compat)
    legacy = (verdict_dict.get("verdict") or critic_payload.get("verdict") or "").upper().strip()
    if legacy in ("PASS", "FAIL", "RETRYABLE_FAIL"):
        return legacy
    overall = (verdict_dict.get("overall_verdict") or "").lower().strip()
    binary = (verdict_dict.get("binary_carousel_verdict") or "").upper().strip()
    if overall == "pass" or binary == "PASS":
        return "PASS"
    if overall == "soft_fail":
        return "RETRYABLE_FAIL"
    if overall == "hard_fail" or binary == "FAIL":
        return "FAIL"
    logger.warning(
        f"critic returned unknown verdict overall={overall!r} binary={binary!r} "
        f"legacy={legacy!r}, defaulting to FAIL"
    )
    return "FAIL"


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

        # Spec §1 step 3.5 — hero JPG generation via Codex $imagegen.
        # Run after image_prompt_author + before layout_composer so the
        # layout step finds slides/<NN>-hero.jpg files on disk (Article 5.10
        # no-silent-placeholder-reuse enforcement).
        if step["name"] == "image_prompt_author":
            try:
                hero_paths = await generate_hero_images(
                    output_dir,
                    artifacts.get("image_prompt_author", {}),
                    artifacts.get("storyboarder", {}),
                )
                artifacts["hero_images"] = [str(p) for p in hero_paths]
            except Exception as exc:
                logger.warning(f"hero image generation failed (non-fatal): {exc}")
                artifacts["hero_images"] = []

    # Step 5 — Playwright render (MUST run BEFORE the critic: wr2-critic's
    # mandatory pre-Rubric vision sweep reads carousel.pdf, so the PDF must
    # exist before the critic is invoked). Render once — re-rendering identical
    # HTML on a critic retry is pointless.
    rendered = await render_playwright(output_dir, artifacts.get("layout_composer", {}))
    artifacts["rendered_paths"] = [str(p) for p in rendered]
    # render_playwright writes rendered.json with PDF path internally.
    pdf_path = output_dir / "carousel.pdf"
    # Hand the critic explicit artifact paths so it never mis-derives <draft_id>
    # (the critic doc says the orchestrator passes these; previously it did not).
    artifacts["render_paths"] = {
        "pdf_path": str(pdf_path),
        "slides_dir": str(output_dir / "slides"),
        "png_paths": [str(p) for p in rendered],
        "hero_paths": artifacts.get("hero_images", []),
    }
    await transition_state(conn, carousel_id, "rendered")

    # Step 6 — critic gate with retry max 2 (now operates on the rendered PDF).
    # On RETRYABLE_FAIL we re-invoke ONLY the critic (re-Read the same PDF) —
    # the HTML/PNG/PDF are unchanged, so re-rendering would be wasted work.
    # A real FAIL stays terminal as before.
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
                # Extract structured reason from nested verdict dict (Claude SDK envelope)
                verdict_dict = _extract_critic_verdict_dict(critic_payload)
                reason = (
                    verdict_dict.get("binary_carousel_reason")
                    or critic_payload.get("reason")
                    or verdict_dict.get("reason")
                    or "no reason given"
                )
                raise FatalOrchestratorError(
                    f"critic FAIL (attempt {attempt + 1}): {reason}"
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
