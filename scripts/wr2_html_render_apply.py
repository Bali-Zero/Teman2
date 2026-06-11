#!/usr/bin/env python3
"""WR2 HTML render apply-worker — the chokepoint that replaces Canva (wiring v4).

Polls war_room_drafts for status='drafts_imaged_checked', CAS-claims one via the
HTML-lane lease (heartbeat-renewable), renders the carousel with the HTML/CSS engine
(scripts/wr2_html_renderer), uploads the PNGs to Google Drive (SA-DWD), then in ONE
transaction promotes the draft to 'rendered'+drive_url and enqueues a WhatsApp text
notification (the Drive link) to Antonello + Damar via the durable wa_outbox. NO
Telegram gate (Legge 5 honored — delivery is the 24h-window WhatsApp text, the link
lives on Drive regardless).

One-shot per invocation (launchd re-fires on a schedule), NOT a daemon — mirrors the
boot/connect/kill-switch/run skeleton of wr2_canva_desktop_apply.py. The hard DB logic
(CAS lease, heartbeat, atomic persist+enqueue, idempotency) lives in
canva_renderer_v2/_pg.py (HTML-lane functions) and is already DB-tested.

Conditions closed here (WR2 wiring v4):
  C1  idempotency  -> _pg.persist_html_result_and_enqueue_notifications
  C4  heartbeat    -> background heartbeat task; render aborts on heartbeat loss
  C5  shadow       -> WR2_HTML_SHADOW=1 => drive_url_shadow + status rendered_shadow, NO WA
  C6  window-alert -> per-recipient window_open in report -> ops alert (NOT Telegram link)
  C7  CAS          -> _pg.acquire_html_lease_and_fetch
  GO#3 c1/c2/c5    -> boot asserts vision; per-slide run_designer_loop converged gate;
                      per-slide render_fn exceptions caught
  #10 Drive MIME   -> upload PNG with explicit mime_type='image/png'
  #13 hero         -> hero normalizer: serve hero_image_path over a localhost http server,
                      rewrite image_url so the composer's downloader stages it (no fake URL,
                      no file:// which httpx rejects)

Kill switch: system_settings.wr2_html_renderer_enabled (missing/!=true => no-op).
Env: DATABASE_URL (required), WR2_HTML_SHADOW (1=dry-run), WR2_VISION_REQUIRED (1=enforce
vision fail-closed), WR2_HTML_MAX_ATTEMPTS (circuit breaker, default 3),
WR2_NOTIFY_RECIPIENTS (comma phones; default the two below), WR2_HTML_HEARTBEAT_SECS (60).
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
import threading
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

# --- sys.path so backend.* and the renderer package import regardless of launchd cwd
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))
sys.path.insert(0, str(_REPO / "scripts"))

import asyncpg  # noqa: E402

from backend.services.canva_renderer_v2 import _pg  # noqa: E402
from wr2_html_renderer.claude_vision import VisionTransient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# Silence httpx INFO logs that would otherwise leak the Telegram bot token in the request URL
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("wr2_html_apply")

MAX_DRAFTS_PER_RUN = 1
DEFAULT_RECIPIENTS = ["6282264599868", "628213454726"]  # Antonello +62 822-6459-9868, Damar +62 821-3454-726
TELEGRAM_OWNER_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


# ── ops alert (NOT the carousel link — operational signal only, C6/L3) ──────────
async def _ops_alert(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("OPS-ALERT (no telegram token): %s", text)
        return
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as c:
            await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": TELEGRAM_OWNER_CHAT_ID, "text": text},
            )
    except Exception as exc:  # never let alerting crash the worker
        logger.warning("ops alert failed: %s", text, exc_info=exc)


# ── hero normalizer (#13): serve local hero files over localhost, rewrite image_url ──
class _HeroServer:
    """Tiny localhost HTTP server rooted at a dir of hero files, so the composer's
    httpx downloader can fetch them (httpx rejects file://). Lives only during render."""

    def __init__(self, root: Path):
        self.root = root
        self.port = self._free_port()
        handler = self._make_handler(root)
        self.httpd = HTTPServer(("127.0.0.1", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @staticmethod
    def _free_port() -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    @staticmethod
    def _make_handler(root: Path):
        class H(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(root), **kw)

            def log_message(self, *a):  # silence
                pass

        return H

    def __enter__(self) -> "_HeroServer":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def url_for(self, filename: str) -> str:
        return f"http://127.0.0.1:{self.port}/{filename}"


def _normalize_heroes(slides: list[dict[str, Any]], hero_dir: Path, server: "_HeroServer") -> list[dict[str, Any]]:
    """Copy each slide's local hero_image_path into hero_dir and rewrite image_url to the
    localhost URL the composer will download. Slides without a hero are passed through.
    NO fake URL: if hero_image_path is missing/unreadable the slide keeps whatever image_url
    it had (or none) and the renderer's hero gate will correctly fail it."""
    import shutil

    out: list[dict[str, Any]] = []
    for i, slide in enumerate(slides, start=1):
        s = dict(slide)
        local = s.get("hero_image_path")
        is_hero = bool(s.get("is_hero_image")) or i == 1
        if is_hero and local:
            src = Path(local)
            if src.is_file():
                fn = f"hero-{i:02d}{src.suffix or '.jpg'}"
                shutil.copyfile(src, hero_dir / fn)
                s["image_url"] = server.url_for(fn)
            else:
                logger.warning("slide %d hero_image_path missing on disk: %s", i, local)
        out.append(s)
    return out


# ── Drive upload (idempotent-by-name under the single-owner lease) ──────────────
async def _drive_upload_carousel(draft_id: str, png_paths: list[Path], shadow: bool) -> str:
    """Create (or reuse) folder WR2-{draft_id} [shadow: under a WR2-SHADOW root], upload the
    PNGs as image/png, return the folder webViewLink. Idempotent-by-name: searches first and
    reuses an existing folder of the same name. Concurrent-create is prevented by the lease
    (single owner per draft), so search-before-create is the residual dedup (#9)."""
    from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

    svc = ServiceAccountDriveService()
    folder_name = f"WR2-{'SHADOW-' if shadow else ''}{draft_id}"

    # search-before-create (idempotency under retry/stale-lease re-render)
    folder_id: str | None = None
    try:
        q = (
            f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' "
            f"and trashed = false"
        )
        import asyncio as _a

        req = svc.service.files().list(
            q=q, fields="files(id, webViewLink)", supportsAllDrives=True,
            includeItemsFromAllDrives=True, pageSize=1,
        )
        res = await _a.to_thread(req.execute)
        files = res.get("files", [])
        if files:
            folder_id = files[0]["id"]
            web = files[0].get("webViewLink", "")
            logger.info("reusing existing Drive folder %s (%s)", folder_name, folder_id)
    except Exception as exc:
        logger.warning("Drive folder search failed (will create fresh): %s", exc)

    if folder_id is None:
        folder = await svc.create_folder(name=folder_name)
        folder_id = folder["id"]
        web = folder.get("webViewLink", "")

    for png in png_paths:
        content = Path(png).read_bytes()
        await svc.upload_file_to_folder(
            folder_id=folder_id,
            file_content=content,
            file_name=Path(png).name,
            mime_type="image/png",  # #10: explicit, the service hardcodes image/jpeg otherwise
        )
    if not web:
        meta = await svc.get_file_metadata(folder_id)
        web = meta.get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")
    return web


def _dump_designer_history(draft_id: str, slide_index: int, history: list[dict[str, Any]]) -> str:
    """Persist the designer-loop history JSON for post-mortem and return a short
    excerpt of the last vision critiques. The render tmp dir is deleted on exit,
    so without this a render_failed leaves zero trace of WHY the gate rejected
    (2026-06-11: 3 drafts failed with no recorded critiques)."""
    issues: list[str] = []
    for rec in reversed(history):
        vi = (rec.get("vision") or {}).get("issues") or []
        if vi:
            issues = [str(x) for x in vi]
            break
    try:
        import json
        from datetime import datetime, timezone

        debug_dir = Path(
            os.environ.get("WR2_HTML_DEBUG_DIR", str(Path.home() / "logs" / "wr2-html-debug"))
        )
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = debug_dir / f"{ts}-{draft_id[:8]}-slide{slide_index:02d}-history.json"
        path.write_text(
            json.dumps(
                {"draft_id": draft_id, "slide": slide_index, "history": history},
                indent=1,
                default=str,
            )
        )
    except Exception:
        logger.exception("failed to persist designer history (non-fatal)")
    return "; ".join(issues)[:400]


# ── render one carousel (per-slide designer loop, GO#3) ─────────────────────────
async def _render_carousel(draft_id: str, slides: list[dict[str, Any]], work: Path, vision_required: bool) -> Path:
    """Render the carousel via the HTML engine. Returns the dir containing the slide PNGs.
    Raises RuntimeError if any slide fails its hero/converge gate.

    Two modes:
    - default (vision NOT required): compose_carousel bulk straight-render with the
      anti-Canva hero gate (result.ok requires heroes_placed == heroes_expected). Fast.
    - WR2_VISION_REQUIRED=1: per-slide run_designer_loop with the Claude vision critic,
      requiring converged AND final_png.exists() for EVERY slide (GO#3 c5). The engine's
      fail-closed patch makes a slide NOT converge when vision was required but unavailable,
      so this path genuinely enforces vision per hero."""
    out_dir = work / "carousel"
    out_dir.mkdir(parents=True, exist_ok=True)
    slides_dir = out_dir / "slides"

    if not vision_required:
        from wr2_html_renderer.composer import compose_carousel

        result = await compose_carousel(slides, out_dir, topic="", timeout_ms=30000)
        if not result.ok:
            raise RuntimeError(
                f"carousel render gate failed: slides={result.slides_rendered} "
                f"heroes={result.heroes_placed}/{result.heroes_expected} failures={result.failures}"
            )
        return slides_dir

    # --- per-slide designer loop with vision (GO#3 c5) ---
    from wr2_html_renderer.composer import (
        _stage_assets,
        make_slide_render_fn,
        _download_hero,
    )
    from wr2_html_renderer.claude_vision import claude_design_critic
    from wr2_html_renderer.designer_loop import run_designer_loop
    import httpx

    _stage_assets(out_dir)
    slides_dir.mkdir(parents=True, exist_ok=True)
    _stage_assets(slides_dir)

    total = len(slides)
    final_pngs: list[Path] = []
    async with httpx.AsyncClient() as client:
        for i, slide in enumerate(slides, start=1):
            is_hero = bool(slide.get("is_hero_image")) or i == 1
            hero_filename: str | None = None
            if is_hero:
                url = (slide.get("image_url") or "").strip()
                if url:
                    hero_filename = f"slide-{i:02d}-hero.jpg"
                    ok = await _download_hero(client, url, slides_dir / hero_filename)
                    if not ok:
                        raise RuntimeError(f"slide {i} hero download failed (vision-required path)")

            render_fn = make_slide_render_fn(
                slides_dir=slides_dir, index=i, total=total,
                hero_filename=hero_filename, timeout_ms=30000,
            )
            res = await run_designer_loop(
                slide=slide,
                render_fn=render_fn,
                out_dir=slides_dir / f"loop-{i:02d}",
                is_hero=is_hero,
                hero_path=(slides_dir / hero_filename) if hero_filename else None,
                vision_critic=claude_design_critic,
                brand_verifier=claude_design_critic,
                use_vision=True,
                max_iters=3,
            )
            if not (res.converged and res.final_png and Path(res.final_png).is_file()):
                excerpt = _dump_designer_history(draft_id, i, res.history)
                raise RuntimeError(
                    f"slide {i} did not converge (reason={res.reason!r} "
                    f"critiques=[{excerpt}] final_png={res.final_png}) — GO#3 c5 reject"
                )
            # place the converged PNG at the canonical slot
            dest = slides_dir / f"{i:02d}.png"
            if Path(res.final_png).resolve() != dest.resolve():
                dest.parent.mkdir(parents=True, exist_ok=True)
                Path(res.final_png).replace(dest)
            final_pngs.append(dest)

    if len(final_pngs) != total:
        raise RuntimeError(f"per-slide render produced {len(final_pngs)}/{total} slides")
    return slides_dir


# ── heartbeat loop ──────────────────────────────────────────────────────────────
async def _heartbeat_loop(conn: asyncpg.Connection, draft_id: str, owner: str, stop: asyncio.Event, interval: int):
    """Renew the lease every `interval`s until stop. If the lease is no longer ours,
    set stop so the caller aborts before any irreversible Drive write (C4)."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            return
        ok = await _pg.heartbeat_html_lease(conn, draft_id=draft_id, lease_owner=owner)
        if not ok:
            logger.error("heartbeat lost for draft %s — signalling abort", draft_id)
            stop.set()
            return


# ── anti-sameness ledger (P-1 S1) ───────────────────────────────────────────────
async def _log_ledger_best_effort(conn: "asyncpg.Connection", draft_id: uuid.UUID) -> None:
    """Write the topic_type_log row for a rendered draft (savepoint-isolated).

    Best-effort: a ledger failure must NEVER fail the render — the draft is
    already promoted + WA-notified by the time this runs. Gaps are caught by
    the watchdog ledger-gap probe (S10d) and the row is idempotent on draft_id.
    """
    try:
        import wr2_topic_type_log as ttl

        async with conn.transaction():  # savepoint — isolates the insert
            await ttl.log_topic_type(conn, draft_id)
    except Exception as exc:  # noqa: BLE001 — observability, never fail the render
        logger.warning("topic_type_log write failed for %s: %s", draft_id, exc)


# ── apply one draft ──────────────────────────────────────────────────────────────
async def _apply_one(pool_conn_dsn: str, draft_id: uuid.UUID, owner: str) -> str:
    """Full lifecycle for one draft. Uses a dedicated connection for the heartbeat so it
    can run concurrently with the long render. Returns a short status string."""
    shadow = os.environ.get("WR2_HTML_SHADOW") == "1"
    vision_required = os.environ.get("WR2_VISION_REQUIRED") == "1"
    max_attempts = int(os.environ.get("WR2_HTML_MAX_ATTEMPTS", "3"))
    hb_interval = int(os.environ.get("WR2_HTML_HEARTBEAT_SECS", "60"))
    recipients = [r.strip() for r in os.environ.get("WR2_NOTIFY_RECIPIENTS", ",".join(DEFAULT_RECIPIENTS)).split(",") if r.strip()]

    main_conn = await asyncpg.connect(pool_conn_dsn, timeout=10)
    hb_conn = await asyncpg.connect(pool_conn_dsn, timeout=10)
    stop = asyncio.Event()
    hb_task: asyncio.Task | None = None
    try:
        row = await _pg.acquire_html_lease_and_fetch(main_conn, draft_id=draft_id, lease_owner=owner)
        if row is None:
            return "lost_lease"

        slides_json = row["slides_json"]
        if isinstance(slides_json, str):
            import json as _json
            slides_json = _json.loads(slides_json)
        slides = slides_json.get("slides", []) if isinstance(slides_json, dict) else slides_json
        if not slides:
            await _pg.release_lease_permanent(main_conn, draft_id=draft_id, status="render_failed", reason="no_slides")
            await _ops_alert(f"WR2 HTML: draft {draft_id} has no slides -> render_failed")
            return "no_slides"

        hb_task = asyncio.create_task(_heartbeat_loop(hb_conn, str(draft_id), owner, stop, hb_interval))

        import tempfile
        work = Path(tempfile.mkdtemp(prefix=f"wr2-html-{draft_id}-"))
        try:
            hero_dir = work / "heroes"
            hero_dir.mkdir(parents=True, exist_ok=True)
            with _HeroServer(hero_dir) as server:
                norm_slides = _normalize_heroes(slides, hero_dir, server)
                slides_dir = await _render_carousel(str(draft_id), norm_slides, work, vision_required)
            png_paths = sorted(slides_dir.glob("*.png"))
            if not png_paths:
                raise RuntimeError("no PNGs after render")

            # abort if heartbeat already lost (do NOT touch Drive)
            if stop.is_set():
                raise RuntimeError("lease_lost_before_drive")

            web = await _drive_upload_carousel(str(draft_id), png_paths, shadow)

            if shadow:
                # terminal shadow: drive_url_shadow + rendered_shadow, NO WA (C5)
                await main_conn.execute(
                    """
                    UPDATE war_room_drafts
                       SET status = 'rendered_shadow', drive_url_shadow = $2,
                           lease_owner = NULL, lease_acquired_at = NULL,
                           lease_heartbeat_at = NULL, updated_at = NOW()
                     WHERE id = $1 AND lease_owner = $3 AND status = 'rendering'
                    """,
                    draft_id, web, owner,
                )
                await _ops_alert(f"WR2 HTML SHADOW done draft={draft_id} drive={web} (no WA sent)")
                return "shadow_done"

            msg = f"Carousel pronto: {web}"
            report = await _pg.persist_html_result_and_enqueue_notifications(
                main_conn, draft_id=draft_id, lease_owner=owner, drive_url=web,
                recipients=recipients, message_body=msg, customer_window_hours=24,
            )
            await _log_ledger_best_effort(main_conn, draft_id)
            closed = [r for r, info in report.items() if not info.get("window_open")]
            if closed:
                await _ops_alert(
                    f"WR2 HTML draft={draft_id} rendered drive={web} BUT 24h window CLOSED for "
                    f"{closed} -> message queued but will fail until they message the Meta number. "
                    f"Re-open by having them text +62 821-3465-159, then re-enqueue."
                )
            return f"rendered report={report}"
        except VisionTransient as exc:
            # transient vision-infra failure (HTTP 429 quota window OR endpoint
            # timeout) — NOT a draft defect. Release the lease WITHOUT touching
            # _html_attempts so the circuit breaker is not burned; the draft
            # returns to the queue and renders next tick once the endpoint
            # recovers. (Pre-fix a 429/timeout masqueraded as "vision unavailable"
            # and killed healthy drafts in 3 attempts.)
            await main_conn.execute(
                """
                UPDATE war_room_drafts
                   SET status='drafts_imaged_checked', lease_owner=NULL,
                       lease_acquired_at=NULL, lease_heartbeat_at=NULL, updated_at=NOW()
                 WHERE id=$1 AND lease_owner=$2 AND status='rendering'
                """,
                draft_id, owner,
            )
            logger.warning("draft %s vision transient (%s) — no attempt burned: %s", draft_id, type(exc).__name__, exc)
            return f"rate_limited:{exc}"
        except RuntimeError as exc:
            # transient render/Drive failure -> back to queue unless attempts exhausted
            attempts = await main_conn.fetchval(
                "SELECT COALESCE((slides_json->>'_html_attempts')::int, 0) FROM war_room_drafts WHERE id=$1",
                draft_id,
            ) or 0
            attempts += 1
            if attempts >= max_attempts:
                await main_conn.execute(
                    """
                    UPDATE war_room_drafts SET status='render_failed', lease_owner=NULL,
                           lease_acquired_at=NULL, lease_heartbeat_at=NULL, updated_at=NOW()
                     WHERE id=$1 AND lease_owner=$2 AND status='rendering'
                    """,
                    draft_id, owner,
                )
                await _ops_alert(f"WR2 HTML draft={draft_id} -> render_failed after {attempts} attempts: {exc}")
                return f"render_failed:{exc}"
            # record attempt + release for retry (ownership-gated so a stolen lease doesn't count)
            await main_conn.execute(
                """
                UPDATE war_room_drafts
                   SET slides_json = jsonb_set(slides_json, '{_html_attempts}', to_jsonb($3::int)),
                       status='drafts_imaged_checked', lease_owner=NULL,
                       lease_acquired_at=NULL, lease_heartbeat_at=NULL, updated_at=NOW()
                 WHERE id=$1 AND lease_owner=$2 AND status='rendering'
                """,
                draft_id, owner, attempts,
            )
            logger.warning("draft %s transient failure attempt %d/%d: %s", draft_id, attempts, max_attempts, exc)
            return f"retry:{attempts}:{exc}"
        finally:
            stop.set()
            try:
                await hb_task
            except Exception:
                pass
            import shutil
            shutil.rmtree(work, ignore_errors=True)
    finally:
        stop.set()
        if hb_task is not None and not hb_task.done():
            hb_task.cancel()
            try:
                await hb_task
            except (asyncio.CancelledError, Exception):
                pass
        await hb_conn.close()
        await main_conn.close()


# ── selftest (plumbing-only: prove browser + DB, process NO draft) ──────────────
async def _selftest() -> int:
    """Prove the runtime plumbing works WITHOUT touching any draft:
    (a) launch headless chromium via the renderer's playwright import path,
    (b) connect to DATABASE_URL and read the kill switch.
    Prints SELFTEST OK / SELFTEST FAIL <reason> and returns 0/1. Never processes data."""
    # (a) browser — same lazy import path as wr2_html_renderer/renderer.py
    try:
        from playwright.async_api import async_playwright  # lazy import

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
    except Exception as exc:  # noqa: BLE001
        print(f"SELFTEST FAIL chromium: {exc}")
        return 1

    # (b) DB — connect + read kill switch (read-only, no mutation)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("SELFTEST FAIL db: DATABASE_URL not set")
        return 1
    try:
        conn = await asyncpg.connect(dsn, timeout=10)
        try:
            enabled = await _pg.is_html_kill_switch_enabled(conn)
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"SELFTEST FAIL db: {exc}")
        return 1

    print(f"SELFTEST OK (chromium launched; db reachable; kill_switch_enabled={enabled})")
    return 0


# ── run / main ────────────────────────────────────────────────────────────────
async def run(dry_run: bool = False, draft_id: str | None = None) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    owner = f"html-apply-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    # R4.2 drain-loop (P-1): keep fetching batches until the queue is empty so a
    # supervisor kickstart swallowed while we are busy still gets its draft
    # processed this run (restores wr2_supervisor.py:20-22 drain assumption).
    # Capped so a draft bouncing on transient failures cannot loop forever.
    max_loops = int(os.environ.get("WR2_HTML_DRAIN_MAX_LOOPS", "10"))

    processed = 0
    successes = 0
    rate_limited_halt = False
    for loop_n in range(max_loops):
        if draft_id:
            ids = [uuid.UUID(draft_id)] if loop_n == 0 else []
        else:
            scan = await asyncpg.connect(dsn, timeout=10)
            try:
                if not await _pg.is_html_kill_switch_enabled(scan):
                    logger.info("wr2_html_renderer_enabled is OFF — no-op")
                    return 0
                if loop_n == 0:
                    # watchdog: reclaim any dead-worker leases first
                    reclaimed = await _pg.reset_stale_html_leases(scan, stale_after_minutes=10)
                    if reclaimed:
                        logger.info("reclaimed %d stale HTML leases", len(reclaimed))
                ids = await _pg.fetch_pending_html_draft_ids(scan, limit=MAX_DRAFTS_PER_RUN)
            finally:
                await scan.close()
        if not ids:
            if processed == 0:
                logger.info("no pending drafts")
            break
        if dry_run:
            logger.info("DRY-RUN would process: %s", ids)
            return 0
        for did in ids:
            processed += 1
            try:
                result = await _apply_one(dsn, did, owner)
                logger.info("draft %s -> %s", did, result)
                if result.startswith("rendered") or result == "shadow_done":
                    successes += 1
                elif result.startswith("rate_limited"):
                    # quota is exhausted account-wide — further drafts this run
                    # would hit the same 429. Stop draining; the draft stays
                    # queued (no attempt burned) and renders on a later tick.
                    logger.warning("drain-loop halting early: vision quota rate-limited")
                    rate_limited_halt = True
                    break
            except Exception:
                logger.exception("draft %s crashed", did)
        if draft_id or rate_limited_halt:
            break
        if draft_id:
            break
    return 0 if successes == processed else 1


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--draft-id", default=None)
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="prove runtime plumbing (headless chromium + DB kill-switch read); process NO draft",
    )
    args = ap.parse_args()
    try:
        if args.selftest:
            return asyncio.run(_selftest())
        return asyncio.run(run(dry_run=args.dry_run, draft_id=args.draft_id))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
