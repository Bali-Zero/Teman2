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
WR2_NOTIFY_RECIPIENTS (comma phones; default the two below), WR2_HTML_HEARTBEAT_SECS (60),
WR2_RUNTIME_SHA_GATE (C2 deploy-fork content-gate: off|warn|strict, default warn —
warn logs provenance problems and proceeds; strict refuses impure boots and aborts
pre-Drive when HEAD moves mid-run, releasing the lease without burning an attempt).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import socket
import sys
import threading
import time
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, NamedTuple

# --- sys.path so backend.* and the renderer package import regardless of launchd cwd
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))
sys.path.insert(0, str(_REPO / "scripts"))

import asyncpg  # noqa: E402

import wr2_orchestrator_metrics as wom  # noqa: E402  (B11: per-step observability, fail-open)
from backend.services.canva_renderer_v2 import _pg  # noqa: E402
from wr2_html_renderer.claude_vision import VisionTransient  # noqa: E402

# ── C2 runtime provenance (deploy-fork content-gate) — fail-open on any error ──
# scripts/lib is not a package: importlib load, same pattern as wr2_reflexion_synthesis.
try:
    import importlib.util as _ilu  # noqa: E402

    _rs_spec = _ilu.spec_from_file_location(
        "wr2_runtime_stamp", str(_REPO / "scripts" / "lib" / "wr2_runtime_stamp.py")
    )
    runtime_stamp = _ilu.module_from_spec(_rs_spec)
    _rs_spec.loader.exec_module(runtime_stamp)
except Exception:  # noqa: BLE001 — provenance must never break the worker
    runtime_stamp = None

# Load-bearing modules whose LIVE content is compared blob-per-file vs HEAD (W88).
_WATCHED_MODULES = (
    Path(__file__),
    _REPO / "apps" / "backend-rag" / "backend" / "services" / "canva_renderer_v2" / "_pg.py",
    _REPO / "scripts" / "wr2_html_renderer" / "designer_loop.py",
)
# Populated once per run() by the boot stamp; read by the pre-Drive gate.
_BOOT_STAMP: dict = {}


class RuntimeStale(Exception):
    """Strict runtime-sha gate tripped: NOT a draft defect — released without
    burning an attempt (same no-burn contract as VisionTransient)."""

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# Silence httpx/httpcore INFO logs that would otherwise leak the Telegram bot token in the request URL
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("wr2_html_apply")

MAX_DRAFTS_PER_RUN = 1
DEFAULT_RECIPIENTS = ["6282230102328", "628213454726"]  # Antonello +62 822-3010-2328, Damar +62 821-3454-726
TELEGRAM_OWNER_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


# ── ops alert (NOT the carousel link — operational signal only, C6/L3) ──────────
def _tg_notify(tier: str, dedup_key: str, text: str) -> bool:
    """Route a notification through the tg_notify gateway (tier router + digest +
    anti-noise, PR #2067). Spool-based and fast; returns True when the gateway
    accepted the message. NEVER raises — visibility must not break the render."""
    try:
        import subprocess

        script = _REPO / "scripts" / "tg_notify.py"
        if not script.is_file():
            return False
        cmd = [
            sys.executable, str(script),
            "--tier", tier, "--source", "wr2-html-apply",
            "--dedup-key", dedup_key, text,
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=30)
        return res.returncode == 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("tg_notify failed (%s): %s", dedup_key, exc)
        return False


async def _ops_alert(text: str, *, tier: str = "p0", dedup_key: str = "wr2-html-ops") -> None:
    """Operational alert. Primary path = tg_notify gateway (R8 cure: raw sendMessage
    to the owner chat is one of 206 unread senders — the gateway tiers/dedups/digests).
    Legacy direct Telegram kept ONLY as fallback when the gateway is absent."""
    if _tg_notify(tier, dedup_key, text):
        return
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


# ── visibility chain (R1-R3 cure, 2026-07-07) ───────────────────────────────────
# "rendered" must mean "on Zero's screen": durable local PNGs + review-queue entry
# + tg_notify P0. Every rendered draft used to live ONLY in a tempdir + Drive, with
# a WhatsApp notify that failed 24h_window_closed since 06-17 — production was
# invisible to the human (spec docs/specs/wr2-definitiva-v1.md §0).

def _slugify(topic: str, max_len: int = 60) -> str:
    """Filesystem/queue-safe slug from a topic string."""
    import re as _re

    slug = _re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "carousel"


def _default_output_root() -> Path:
    """The output tree the queue-server, warroom-sync and WR2 Control app read.
    Lives in the MAIN checkout on Pro (runtime-state convention), NOT the deploy
    clone this worker runs from — override with WR2_OUTPUT_ROOT."""
    return Path(
        os.environ.get(
            "WR2_OUTPUT_ROOT",
            str(Path.home() / "Desktop" / "nuzantara" / "apps" / "war-room" / "output"),
        )
    )


def _persist_local_artifacts(
    *,
    draft_id: str,
    topic: str,
    png_paths: list[Path],
    drive_url: str,
    weak_count: int,
    fact_check_status: str | None,
    out_root: Path | None = None,
    rendered_at: str | None = None,
) -> Path:
    """Copy the rendered PNGs to a durable carousel dir + write meta.json.
    Returns the carousel dir. Raises on IO failure (caller decides severity)."""
    import json as _json
    import shutil
    from datetime import datetime, timezone

    root = out_root if out_root is not None else _default_output_root()
    ts = rendered_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    day = ts[:10]
    slug = _slugify(topic)
    car_dir = root / "carousel" / f"{day}-{slug}-{str(draft_id)[:8]}"
    slides_dir = car_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    # re-render of the same draft/day: clear stale PNGs so a shorter carousel
    # does not keep ghost slides in the app preview (red-team LOW)
    for stale in slides_dir.glob("*.png"):
        stale.unlink()
    for p in png_paths:
        shutil.copy2(p, slides_dir / p.name)
    # A1: re-derive slide_count from the DURABLE artifact just written, never
    # from the in-memory png_paths list — this is the ONE helper every writer
    # of a persisted slide_count routes through (2026-07-16). A copy that
    # silently dropped a file (or a stray leftover the stale-clear missed)
    # must be visible here, not carried forward as a lie in meta.json/queue.
    durable_count = derive_slide_count(slides_dir)
    if durable_count != len(png_paths):
        raise RuntimeError(
            f"persist_local_artifacts completeness mismatch for draft {draft_id}: "
            f"copied {len(png_paths)} PNGs but slides_dir now verifies {durable_count} "
            f"— refusing to write a lying meta.json/queue entry"
        )
    meta = {
        "draft_id": str(draft_id),
        "topic": topic,
        "slug": slug,
        "drive_url": drive_url,
        "slide_count": durable_count,
        "weak_slides": weak_count,
        "fact_check_status": fact_check_status,
        "rendered_at": ts,
        "producer": "wr2-html-apply",
    }
    (car_dir / "meta.json").write_text(_json.dumps(meta, indent=2), encoding="utf-8")
    return car_dir


def _make_queue_entry(
    *,
    draft_id: str,
    topic: str,
    carousel_dir: Path,
    drive_url: str,
    slide_count: int,
    weak_count: int,
    fact_check_status: str | None,
    drafted_at: str,
) -> dict:
    """Review-queue entry per skills/bali-zero-brand/_review-queue-schema.md."""
    slug = _slugify(topic)
    # WR2 deep audit 2026-07-14 (§5a finding #2, Codex objection #15): this path
    # runs ONLY the per-slide designer-loop legibility critic (readable/hierarchy/
    # balanced) — the 4-rubric constitution critic (wr2-critic subagent) never
    # touches this draft. A bare "pass" here was indistinguishable from a real
    # constitution-critic pass to every downstream consumer (the app, the
    # analyst, reflexion). Name the verdict for what actually ran.
    verdict = "legibility_only_pass" if weak_count == 0 else "legibility_soft_fail"
    return {
        "id": f"carousel_{drafted_at}_{slug}",
        "draft_id": str(draft_id),
        "topic_slug": slug,
        "topic": topic,
        "drafted_at": drafted_at,
        "carousel_path": str(carousel_dir),
        # the queue-server preview endpoint reads slides_dir verbatim
        # (_damar-queue-server.py:476) — omit it and the app shows no slides
        "slides_dir": str(carousel_dir / "slides"),
        "drive_url": drive_url,
        "media_type": "carousel",
        "slide_count": slide_count,
        "critic_overall_verdict": verdict,
        "critic_summary": (
            f"{weak_count} weak slide(s) placed as composition debt (N-1)"
            if weak_count else "all slides converged"
        ),
        "fact_check_status": fact_check_status,
        "state": "drafted",
        "state_history": [
            {"state": "drafted", "at": drafted_at, "by": "wr2-html-apply"}
        ],
        "instagram_post_url": None,
        "instagram_published_at": None,
        "engagement_metrics": None,
    }


# Content fields a re-render refreshes in place on the existing queue entry.
# Identity fields (id, draft_id, topic_slug, topic, drafted_at) and publish
# fields (instagram_*, engagement_metrics) are deliberately NOT here:
# the entry id feeds ref_code downstream, so it must survive a repoint.
_REPOINT_FIELDS = (
    "carousel_path",
    "slides_dir",
    "drive_url",
    "slide_count",
    "critic_overall_verdict",
    "critic_summary",
    "fact_check_status",
)

# Pre-publish states the damar review flow can hold an entry in (see
# _damar-queue-server.py transitions). A re-render of any of these is a NEW
# review candidate: repoint the content and reset state to "drafted" so it
# re-enters review — a `reviewed` approval or `rejected` verdict given on the
# OLD images must never silently apply to the new ones (Codex review
# 2026-07-13). Anything else (published, archived, legacy no-state) is
# immutable history.
_REPOINTABLE_STATES = ("drafted", "reviewed", "rejected", "drafted_needs_human_edit")


def _append_review_queue(entry: dict, *, queue_path: Path | None = None) -> bool:
    """Append `entry` to human-review-queue.json atomically (fcntl lock, tmp+rename).

    Dedup/repoint contract (re-render verb, W82 exist-not-content):
    - exact id match (same render batch re-applied) -> skip, return False;
    - same draft_id, existing entry still pre-publish (state in
      _REPOINTABLE_STATES) -> REPOINT: refresh content fields in place (new
      slides_dir/drive_url/critic), keep the entry id (ref_code stability) and
      drafted_at, RESET state to "drafted" (a review verdict on the old images
      never applies to the new ones), append a state_history breadcrumb,
      return True. Before this existed, a re-rendered draft kept its queue
      entry pointed at the OLD slides_dir forever;
    - same draft_id but already published/archived (or legacy no-state) ->
      history is immutable, skip, return False.
    Raises on IO/corrupt-JSON so the caller can alert — a corrupt queue must be
    VISIBLE, never silently rebuilt."""
    import fcntl
    import json as _json

    qp = queue_path if queue_path is not None else (_default_output_root() / "queue" / "human-review-queue.json")
    qp.parent.mkdir(parents=True, exist_ok=True)
    lock_path = qp.with_suffix(".lock")
    with open(lock_path, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            if qp.exists():
                queue = _json.loads(qp.read_text(encoding="utf-8"))
                if not isinstance(queue, list):
                    raise ValueError(f"review queue is not a JSON array: {qp}")
            else:
                queue = []
            repointed = False
            for item in queue:
                if not isinstance(item, dict):
                    continue
                if item.get("id") == entry["id"]:
                    return False  # same render batch re-applied — pure dup
                if entry.get("draft_id") and item.get("draft_id") == entry.get("draft_id"):
                    if item.get("state") not in _REPOINTABLE_STATES:
                        return False  # published/archived/legacy — history is immutable
                    for fld in _REPOINT_FIELDS:
                        item[fld] = entry.get(fld)
                    item["state"] = "drafted"  # new images → back through review
                    item.setdefault("state_history", []).append(
                        {
                            "state": "drafted",
                            "at": entry.get("drafted_at"),
                            "by": "wr2-html-apply-rerender",
                        }
                    )
                    repointed = True
                    break
            if not repointed:
                queue.append(entry)
            tmp = qp.with_suffix(f".tmp.{os.getpid()}")
            tmp.write_text(_json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, qp)
            return True
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


async def _publish_visibility(
    *,
    draft_id: str,
    topic: str,
    png_paths: list[Path],
    drive_url: str,
    weak_count: int,
    fact_check_status: str | None,
) -> None:
    """Best-effort visibility: durable PNGs -> queue entry -> tg P0. A failure here
    NEVER fails the render (the DB row + Drive upload are already terminal) but is
    ALWAYS alerted — invisible production is the disease this cures."""
    from datetime import datetime, timezone

    if not str(topic or "").strip() or not png_paths:
        # W96 junk guard: an empty topic / zero slides violates the queue-entry
        # contract (every real draft carries its topic — the leaked test
        # fixtures did not). Enqueueing would put an undisplayable
        # micro-carousel in front of the operator; refuse and alert instead.
        logger.warning(
            "visibility REFUSED for draft %s: malformed (topic=%r, slides=%d)",
            draft_id, topic, len(png_paths),
        )
        await _ops_alert(
            f"WR2 visibility REFUSED for draft {draft_id}: empty topic or zero "
            f"slides — entry NOT queued (W96 junk guard). Drive: {drive_url or 'n/a'}",
            tier="p1", dedup_key=f"wr2-visibility-malformed-{draft_id}",
        )
        return

    drafted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        car_dir = _persist_local_artifacts(
            draft_id=draft_id, topic=topic, png_paths=png_paths,
            drive_url=drive_url, weak_count=weak_count,
            fact_check_status=fact_check_status, rendered_at=drafted_at,
        )
        # A1: the queue entry's slide_count is RE-DERIVED from the durable
        # slides_dir _persist_local_artifacts just verified (single helper,
        # never the in-memory png_paths list) — the queue must never disagree
        # with the artifact it points at.
        durable_slide_count = derive_slide_count(car_dir / "slides")
        entry = _make_queue_entry(
            draft_id=draft_id, topic=topic, carousel_dir=car_dir,
            drive_url=drive_url, slide_count=durable_slide_count,
            weak_count=weak_count, fact_check_status=fact_check_status,
            drafted_at=drafted_at,
        )
        appended = _append_review_queue(entry)
        logger.info(
            "visibility: artifacts=%s queue_appended=%s", car_dir, appended
        )
        _tg_notify(
            "p0",
            f"wr2-carousel-{draft_id}",
            f"🎠 Carousel pronto: {topic}\nDrive: {drive_url}\n"
            f"Slides: {len(png_paths)} (weak={weak_count}, fact-check={fact_check_status or 'n/a'})\n"
            f"Review: {car_dir}",
        )
    except Exception as exc:  # noqa: BLE001 — alert, never break the render
        logger.warning("visibility chain failed for draft %s: %s", draft_id, exc, exc_info=exc)
        await _ops_alert(
            f"WR2 visibility chain FAILED for draft {draft_id} ({topic}): {exc} — "
            f"carousel IS rendered on Drive ({drive_url}) but not queued/visible.",
            tier="p0", dedup_key=f"wr2-visibility-fail-{draft_id}",
        )


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


# ── Drive upload (idempotent — upsert + orphan-sweep + manifest, under the lease) ───
async def _drive_list_folder_children(svc: Any, folder_id: str) -> list[dict[str, Any]]:
    """Every non-trashed direct child of the folder as {id, name}. Pages fully so a
    folder that accreted many duplicate PNGs (the 30-file bug) is drained completely."""
    import asyncio as _a

    children: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        req = svc.service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1000,
            pageToken=page_token,
        )
        res = await _a.to_thread(req.execute)
        children.extend(res.get("files", []))
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return children


async def _drive_upsert_file(
    svc: Any, folder_id: str, name: str, content: bytes, mime_type: str,
    existing_id: str | None,
) -> str:
    """Update the media of an existing file (stable file-id) or create it. Returns the
    file-id. Update-in-place is what makes re-render idempotent instead of accreting a
    new copy every attempt (cicatrix #9: idempotent by ENTITY, not by count)."""
    import asyncio as _a
    from io import BytesIO

    from googleapiclient.http import MediaIoBaseUpload  # type: ignore[import-untyped]

    media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type, resumable=True)
    if existing_id:
        req = svc.service.files().update(
            fileId=existing_id, media_body=media, fields="id", supportsAllDrives=True,
        )
        res = await _a.to_thread(req.execute)
        return res["id"]
    res = await svc.upload_file_to_folder(
        folder_id=folder_id, file_content=content, file_name=name, mime_type=mime_type,
    )
    return res["id"]


async def _drive_upload_carousel(draft_id: str, png_paths: list[Path], shadow: bool) -> str:
    """Create (or reuse) folder WR2-{draft_id} [shadow: under a WR2-SHADOW root], then make
    its contents EXACTLY the current PNG set + a manifest.json, idempotently. Returns the
    folder webViewLink.

    C0 — three moves that make ``rendered`` mean one canonical set (cicatrix #9 / #2):
      1. UPSERT each current PNG by name (update media in place if the name already lives in
         the folder → stable file-id, no new copy per retry). Never a create-then-dup loop.
      2. ORPHAN-SWEEP: delete children whose name is no longer in the current set (stale PNGs
         from a longer previous render, or the 30 duplicates from the create-loop bug). Runs
         AFTER the upserts, so the folder is never momentarily empty.
      3. MANIFEST: write manifest.json (ordered {name, file_id}) — an audit/prove-of-life
         artifact the C1 watchdog can assert on ("rendered without manifest" = anomaly). It is
         NOT a reader contract: the publishers read PNGs from the local render dir, not Drive.
    Concurrent-create of the folder is prevented by the single-owner lease; search-before-create
    is the residual dedup."""
    import asyncio as _a
    import json as _json

    from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

    svc = ServiceAccountDriveService()
    folder_name = f"WR2-{'SHADOW-' if shadow else ''}{draft_id}"

    # search-before-create (idempotency under retry/stale-lease re-render)
    folder_id: str | None = None
    web = ""
    try:
        q = (
            f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' "
            f"and trashed = false"
        )
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

    # Snapshot current children ONCE — drives both upsert (name→id) and sweep.
    existing = await _drive_list_folder_children(svc, folder_id)
    by_name: dict[str, str] = {}
    for child in existing:  # last-writer-wins collapses pre-existing dup names to one id
        by_name[child["name"]] = child["id"]

    # 1. UPSERT the current PNGs (ordered), collecting the canonical file-ids.
    manifest_slides: list[dict[str, str]] = []
    canonical_names: set[str] = set()
    for png in png_paths:
        name = Path(png).name
        canonical_names.add(name)
        file_id = await _drive_upsert_file(
            svc, folder_id, name, Path(png).read_bytes(), "image/png",
            by_name.get(name),
        )
        manifest_slides.append({"name": name, "file_id": file_id})

    # 2. MANIFEST (upsert too — the render is the source of truth for its own contents).
    manifest_name = "manifest.json"
    canonical_names.add(manifest_name)
    manifest_body = _json.dumps(
        {"draft_id": draft_id, "shadow": shadow, "slides": manifest_slides},
        ensure_ascii=False, indent=2,
    ).encode("utf-8")
    await _drive_upsert_file(
        svc, folder_id, manifest_name, manifest_body, "application/json",
        by_name.get(manifest_name),
    )

    # 3. ORPHAN-SWEEP — anything in the folder not in the canonical set is a stale leftover.
    for child in existing:
        if child["name"] in canonical_names:
            continue
        try:
            req = svc.service.files().delete(fileId=child["id"], supportsAllDrives=True)
            await _a.to_thread(req.execute)
            logger.info("swept stale Drive child %s (%s)", child["name"], child["id"])
        except Exception as exc:  # a failed sweep must not fail the render
            logger.warning("orphan-sweep failed for %s: %s", child["name"], exc)

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
# PNGs that _stage_assets copies into slides_dir for file:// resolution during
# per-slide renders — assets, never slides. Excluded from the final slide glob.
_STAGED_ASSET_PNGS = frozenset({"logo.png"})

_SLIDE_STEM_RE = re.compile(r"^\d+$")


def derive_slide_count(slides_dir: Path) -> int:
    """Count REAL slide PNGs in `slides_dir` — the one true way to answer "how
    many slides does this carousel actually have on disk" (A1 completeness
    gate, 2026-07-16). Every writer of a persisted slide_count (queue entry,
    meta.json, reconciler backfill) must route through this function instead
    of trusting an in-memory count or a bare `*.png` glob — a stale/renamed/
    partial file on disk is the whole disease this closes.

    Filter mirrors the WR2 Control app's slidePNGs() (WarRoom.swift) so Python
    and Swift agree on what "a slide" is: numeric-stem *.png only, excluding
    staged chrome (logo.png) and any placeholder* name. Missing dir -> 0
    (dirless is a mismatch to report, never a crash).
    """
    if not slides_dir.is_dir():
        return 0
    count = 0
    for p in slides_dir.iterdir():
        if p.suffix.lower() != ".png":
            continue
        name = p.name.lower()
        if name in _STAGED_ASSET_PNGS or name.startswith("placeholder"):
            continue
        if _SLIDE_STEM_RE.match(p.stem):
            count += 1
    return count


class WeakSlide(NamedTuple):
    """A slide that did NOT converge its designer loop but DID produce a usable
    best-effort PNG. Its PNG is still placed in the carousel (N-1 semantics,
    operator decision 2026-06-30) so a single editorial-weak slide does not sink
    the whole carousel; the weakness is surfaced to ops/human-review instead."""

    index: int
    reason: str
    excerpt: str


async def _render_carousel(
    draft_id: str, slides: list[dict[str, Any]], work: Path, vision_required: bool
) -> tuple[Path, list[WeakSlide]]:
    """Render the carousel via the HTML engine. Returns (slides_dir, weak_slides).

    weak_slides lists slides that did not converge but produced a best-effort PNG
    that was STILL placed in the carousel (N-1 semantics — see WeakSlide). A slide
    that produces NO usable PNG (a real hole: hero download / browser crash) is a
    HARD failure and still raises RuntimeError — that is not editorial debt.

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
        # A1 completeness gate (2026-07-16, explicit — belt on top of `.ok`):
        # RenderResult.ok only requires `not failures and slides_rendered > 0`,
        # NOT slides_rendered == total (see renderer.py RenderResult.ok) — a
        # future refactor of that property (or a bug in the failures-tracking
        # it depends on) could silently let a partial carousel through with
        # zero recorded failures. Re-verify against the DURABLE artifact
        # (actual PNGs on disk), never trust the in-memory tally alone.
        total = len(slides)
        disk_count = derive_slide_count(slides_dir)
        if disk_count != total:
            raise RuntimeError(
                f"carousel completeness gate failed: rendered {disk_count}/{total} "
                f"slides on disk (result.slides_rendered={result.slides_rendered}, "
                f"failures={result.failures}) — refusing partial promotion"
            )
        return slides_dir, []

    # --- per-slide designer loop with vision (GO#3 c5) ---
    from wr2_html_renderer.composer import (
        _stage_assets,
        make_slide_render_fn,
        _download_hero,
    )
    from wr2_html_renderer.claude_vision import claude_brand_verifier, claude_design_critic
    from wr2_html_renderer.designer_loop import run_designer_loop
    import httpx

    _stage_assets(out_dir)
    slides_dir.mkdir(parents=True, exist_ok=True)
    _stage_assets(slides_dir)

    total = len(slides)
    final_pngs: list[Path] = []
    weak_slides: list[WeakSlide] = []
    # N-1 semantics (operator 2026-06-30): a slide that does NOT converge but
    # still produced a usable best-effort PNG is editorial DEBT, not a carousel
    # killer — it is placed anyway and flagged. WR2_MAX_WEAK_SLIDES caps how many
    # weak slides a carousel may carry before the whole render is rejected
    # (default 1: a carousel with ≥2 weak slides is genuinely poor → render_failed).
    max_weak = int(os.environ.get("WR2_MAX_WEAK_SLIDES", "1"))
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
                        # a missing hero is a real hole, not editorial debt → HARD fail
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
                # WR2 deep audit 2026-07-14 (§5a finding #1, Codex objection #14):
                # this used to bind brand_verifier to claude_design_critic — the SAME callable
                # as the critic, so the "autonomy guardrail" (critic proposes,
                # verifier vetoes) was self-approval in production. The two-role
                # split already exists in claude_vision.py (claude_brand_verifier,
                # a distinct prompt + fail-closed-if-unavailable) and was already
                # wired correctly in _designer_e2e.py — only this call site had
                # collapsed it.
                vision_critic=claude_design_critic,
                brand_verifier=claude_brand_verifier,
                use_vision=True,
                max_iters=3,
            )
            # A usable PNG (converged OR best-effort) is the dividing line. The
            # designer loop populates final_png even when converged=False
            # (final_png=best_png), so a non-converged slide that rendered at all
            # still has a placeable PNG. ONLY a slide with no PNG on disk is a
            # real hole.
            has_png = bool(res.final_png) and Path(res.final_png).is_file()
            if not has_png:
                excerpt = _dump_designer_history(draft_id, i, res.history)
                raise RuntimeError(
                    f"slide {i} produced no PNG (reason={res.reason!r} "
                    f"critiques=[{excerpt}] final_png={res.final_png}) — hard render hole"
                )
            if not res.converged:
                # weak but usable: place it AND flag it (N-1). Do not raise.
                excerpt = _dump_designer_history(draft_id, i, res.history)
                weak_slides.append(WeakSlide(index=i, reason=res.reason, excerpt=excerpt))
                logger.warning(
                    "draft %s slide %d did NOT converge but produced a usable PNG — "
                    "placing as composition debt (N-1): reason=%s",
                    draft_id, i, res.reason,
                )
            # place the (converged or best-effort) PNG at the canonical slot
            dest = slides_dir / f"{i:02d}.png"
            if Path(res.final_png).resolve() != dest.resolve():
                dest.parent.mkdir(parents=True, exist_ok=True)
                Path(res.final_png).replace(dest)
            final_pngs.append(dest)

    if len(final_pngs) != total:
        raise RuntimeError(f"per-slide render produced {len(final_pngs)}/{total} slides")
    # A1 completeness gate, disk-verified (belt on top of the in-memory tally
    # above — see the matching comment in the non-vision branch of
    # _render_carousel): re-derive from the DURABLE artifact, never trust only
    # the list this loop built in memory.
    disk_count = derive_slide_count(slides_dir)
    if disk_count != total:
        raise RuntimeError(
            f"carousel completeness gate failed (vision path): {disk_count}/{total} "
            f"slides verified on disk after per-slide render — refusing partial promotion"
        )
    if len(weak_slides) > max_weak:
        idxs = ", ".join(str(w.index) for w in weak_slides)
        raise RuntimeError(
            f"carousel has {len(weak_slides)} weak slides (>{max_weak} allowed): "
            f"slides {idxs} did not converge — render_failed (genuinely poor draft)"
        )
    return slides_dir, weak_slides


# ── heartbeat loop ──────────────────────────────────────────────────────────────
async def _heartbeat_loop(conn: asyncpg.Connection, draft_id: str, owner: str, stop: asyncio.Event, interval: int):
    """Renew the lease every `interval`s until stop. If the lease is no longer ours,
    set stop so the caller aborts before any irreversible Drive write (C4)."""
    misses = 0
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            return
        try:
            ok = await _pg.heartbeat_html_lease(conn, draft_id=draft_id, lease_owner=owner)
        except Exception as exc:  # noqa: BLE001 — a crashed heartbeat MUST abort (C4), never die silently
            misses += 1
            logger.warning("heartbeat error for draft %s (%d/2): %s", draft_id, misses, exc)
            if misses >= 2:
                logger.error("heartbeat errored twice for draft %s — signalling abort", draft_id)
                stop.set()
                return
            continue
        misses = 0
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


async def _ensure_live(conn: "asyncpg.Connection", dsn: str) -> "asyncpg.Connection":
    """Return a live connection: if `conn` was closed while idle, reconnect.

    The render of a full carousel takes ~13-16 min, during which main_conn sits
    idle between the lease-acquire and the terminal write. The pg-proxy closes
    idle connections, so the post-render write (success OR failure path) hit
    `asyncpg.InterfaceError: connection is closed` and crashed before recording
    a terminal status — leaving the draft stuck in 'rendering' forever (2026-06-12
    SCAR). The heartbeat survives only because its own conn pings every 60s.
    Reconnect right before each post-render write.
    """
    if conn.is_closed():
        logger.warning("main_conn closed during long render — reconnecting for terminal write")
        return await asyncpg.connect(dsn, timeout=10)
    return conn


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
            # B11: per-step observability (wr2_orchestrator_metrics, migration
            # 203 — had zero writer before this). Times the whole per-carousel
            # render (designer-loop critic + Playwright PNG production happen
            # INSIDE _render_carousel, not as separate awaits) — recorded once
            # as 'playwright_render' (the concrete artifact-producing step) to
            # avoid fabricating a second, duplicate-latency 'critic' row for
            # work that isn't separately timed; see wr2_orchestrator_metrics.py
            # module docstring. Fail-open, and re-raises the real error.
            _wom_t0 = time.perf_counter()
            _wom_error: Exception | None = None
            try:
                with _HeroServer(hero_dir) as server:
                    norm_slides = _normalize_heroes(slides, hero_dir, server)
                    slides_dir, weak_slides = await _render_carousel(
                        str(draft_id), norm_slides, work, vision_required
                    )
            except Exception as _render_exc:  # noqa: BLE001 — record then re-raise, never swallow
                _wom_error = _render_exc
                raise
            finally:
                # NOTE: deliberately NOT reusing main_conn here — a render can
                # take up to ~15 min and the pg-proxy idle-closes it mid-render
                # (see the _ensure_live reconnect a few lines below, same
                # cause). conn=None makes both calls open their own short-lived
                # connection instead of racing that staleness.
                _wom_cid = await wom.resolve_carousel_id(
                    None, topic=str(dict(row).get("topic") or ""),
                    session_id=f"html_apply:{draft_id}",
                )
                await wom.record_step(
                    carousel_id=_wom_cid,
                    step_name="playwright_render",
                    step_index=6,
                    tier=1,
                    latency_ms=int((time.perf_counter() - _wom_t0) * 1000),
                    retry_count=0,
                    success=_wom_error is None,
                    error_class=type(_wom_error).__name__ if _wom_error else None,
                    error_message=str(_wom_error)[:500] if _wom_error else None,
                )
            # _stage_assets copies logo.png INTO slides_dir in vision mode (per-slide
            # HTML resolves file:// assets there) — a bare *.png glob shipped the
            # brand logo as a bogus extra slide. Exclude staged assets by name.
            png_paths = sorted(
                p for p in slides_dir.glob("*.png") if p.name not in _STAGED_ASSET_PNGS
            )
            if not png_paths:
                raise RuntimeError("no PNGs after render")

            # abort if heartbeat already lost (do NOT touch Drive)
            if stop.is_set():
                raise RuntimeError("lease_lost_before_drive")

            # C2 gate — BEFORE Drive, not just before persist (a blocked persist
            # after an upload still leaves orphan Drive artifacts). Default mode
            # is 'warn': log-only, zero pipeline effects; 'strict' is armed
            # separately (PENDING-ARMS ledger).
            gate_mode = os.environ.get("WR2_RUNTIME_SHA_GATE", "warn").strip().lower()
            if runtime_stamp is not None and _BOOT_STAMP and gate_mode != "off":
                disk_head = runtime_stamp.current_head(_REPO)
                verdict, reason = runtime_stamp.gate_verdict(gate_mode, _BOOT_STAMP, disk_head)
                if verdict == "warn":
                    logger.warning("runtime-sha gate: %s (mode=warn, proceeding)", reason)
                elif verdict == "block":
                    raise RuntimeStale(reason)

            # the render just took ~15 min — main_conn may have been closed idle
            # by the pg-proxy; reconnect before the terminal write so a converged
            # carousel actually reaches status='rendered' (2026-06-12 SCAR).
            main_conn = await _ensure_live(main_conn, pool_conn_dsn)

            web = await _drive_upload_carousel(str(draft_id), png_paths, shadow)

            if shadow:
                # terminal shadow: drive_url_shadow + rendered_shadow, NO WA (C5)
                res = await main_conn.execute(
                    """
                    UPDATE war_room_drafts
                       SET status = 'rendered_shadow', drive_url_shadow = $2,
                           lease_owner = NULL, lease_acquired_at = NULL,
                           lease_heartbeat_at = NULL, updated_at = NOW()
                     WHERE id = $1 AND lease_owner = $3 AND status = 'rendering'
                    """,
                    draft_id, web, owner,
                )
                if res != "UPDATE 1":
                    # lease stolen between render and terminal write — do not
                    # claim shadow_done for a row this worker no longer owns.
                    await _ops_alert(
                        f"WR2 HTML SHADOW draft={draft_id}: terminal UPDATE matched "
                        f"0 rows (lease stolen mid-render?) drive={web}"
                    )
                    return "shadow_race"
                await _ops_alert(f"WR2 HTML SHADOW done draft={draft_id} drive={web} (no WA sent)")
                return "shadow_done"

            msg = f"Carousel pronto: {web}"
            report = await _pg.persist_html_result_and_enqueue_notifications(
                main_conn, draft_id=draft_id, lease_owner=owner, drive_url=web,
                recipients=recipients, message_body=msg, customer_window_hours=24,
            )
            await _log_ledger_best_effort(main_conn, draft_id)
            # R1-R3 visibility chain: durable PNGs + review-queue entry + tg P0.
            # WA above stays best-effort (24h-window may be closed for months);
            # THIS is the delivery leg the human actually sees.
            fc_status = await main_conn.fetchval(
                "SELECT fact_check_status FROM war_room_drafts WHERE id=$1", draft_id
            )
            await _publish_visibility(
                draft_id=str(draft_id), topic=str(dict(row).get("topic") or ""),
                png_paths=png_paths, drive_url=web,
                weak_count=len(weak_slides), fact_check_status=fc_status,
            )
            if weak_slides:
                # N-1: the carousel rendered + was delivered, but ≤max_weak slides
                # carry editorial debt. Flag them for human review (the draft is in
                # 'rendered' which the WR2 Control app already surfaces for approval).
                detail = "; ".join(
                    f"slide {w.index}: {w.reason} — {w.excerpt[:160]}" for w in weak_slides
                )
                await _ops_alert(
                    f"WR2 HTML draft={draft_id} rendered drive={web} with "
                    f"{len(weak_slides)} WEAK slide(s) (N-1 — placed as composition debt, "
                    f"review before publish): {detail}"
                )
            closed = [r for r, info in report.items() if not info.get("window_open")]
            if closed:
                await _ops_alert(
                    f"WR2 HTML draft={draft_id} rendered drive={web} BUT 24h window CLOSED for "
                    f"{closed} -> message queued but will fail until they message the Meta number. "
                    f"Re-open by having them text +62 821-3465-159, then re-enqueue."
                )
            return f"rendered report={report}"
        except RuntimeStale as exc:
            # Deploy landed mid-run / impure provenance in strict mode: the
            # draft is healthy — release WITHOUT burning an attempt and let the
            # next (fresh-code) invocation render it.
            main_conn = await _ensure_live(main_conn, pool_conn_dsn)
            await main_conn.execute(
                """
                UPDATE war_room_drafts
                   SET status='drafts_imaged_checked', lease_owner=NULL,
                       lease_acquired_at=NULL, lease_heartbeat_at=NULL, updated_at=NOW()
                 WHERE id=$1 AND lease_owner=$2 AND status='rendering'
                """,
                draft_id, owner,
            )
            await _ops_alert(
                f"WR2 HTML draft={draft_id} aborted by runtime-sha gate (strict): {exc} "
                f"— draft requeued, no attempt burned. Restart/kickstart the worker "
                f"so the next run imports the deployed code."
            )
            logger.warning("draft %s runtime-stale abort (no attempt burned): %s", draft_id, exc)
            return f"runtime_stale:{exc}"
        except VisionTransient as exc:
            # transient vision-infra failure (HTTP 429 quota window OR endpoint
            # timeout) — NOT a draft defect. Release the lease WITHOUT touching
            # html_render_attempts so the circuit breaker is not burned; the draft
            # returns to the queue and renders next tick once the endpoint
            # recovers. (Pre-fix a 429/timeout masqueraded as "vision unavailable"
            # and killed healthy drafts in 3 attempts.)
            # The render may have run long enough to kill main_conn — reconnect so
            # this release path records its status instead of crashing on a closed
            # connection and leaving the draft stuck in 'rendering'.
            main_conn = await _ensure_live(main_conn, pool_conn_dsn)
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
        except Exception as exc:
            # transient render/Drive failure OR an unexpected bug — either way the
            # attempt is burned and the lease released, so a poisoned draft can
            # never loop forever holding 'rendering'. (Pre-fix only RuntimeError
            # was caught here: any other exception escaped without burning an
            # attempt, leaving the draft stuck until the stale-lease sweep.)
            # The render may have run long enough to kill main_conn — reconnect so
            # this failure path records its terminal status instead of crashing on
            # a closed connection and leaving the draft stuck in 'rendering'.
            main_conn = await _ensure_live(main_conn, pool_conn_dsn)
            # Counter lives in a dedicated INTEGER column (migration 228). The old
            # path read/wrote slides_json->>'_html_attempts', but slides_json is a
            # JSONB ARRAY: the read silently returned 0 (so the counter never
            # accumulated) and the write raised InvalidTextRepresentationError
            # (`path element at position 1 is not an integer`), crashing the
            # retry-release before the draft could be parked → reconciliation
            # re-kicked it forever (2026-06-13 SCAR).
            attempts = await main_conn.fetchval(
                "SELECT COALESCE(html_render_attempts, 0) FROM war_room_drafts WHERE id=$1",
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
                # digest tier: the daily reconciler owns the P0 "no carousel today"
                # escalation — per-attempt failures are informative, not actionable-now.
                await _ops_alert(
                    f"WR2 HTML draft={draft_id} -> render_failed after {attempts} attempts: {exc}",
                    tier="digest", dedup_key=f"wr2-render-failed-{draft_id}",
                )
                return f"render_failed:{exc}"
            # record attempt + release for retry (ownership-gated so a stolen lease doesn't count)
            await main_conn.execute(
                """
                UPDATE war_room_drafts
                   SET html_render_attempts = $3::int,
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

    # C2 boot stamp: provenance of the code THIS run imports. One-shot worker →
    # import-time == run-time; the stamp is per-run truth. Fail-open.
    gate_mode = os.environ.get("WR2_RUNTIME_SHA_GATE", "warn").strip().lower()
    if runtime_stamp is not None:
        _BOOT_STAMP.clear()
        _BOOT_STAMP.update(runtime_stamp.compute_runtime_stamp(_REPO, _WATCHED_MODULES))
        runtime_stamp.write_runtime_stamp("wr2.html_apply", _BOOT_STAMP)
        impure = bool(
            _BOOT_STAMP.get("dirty")
            or _BOOT_STAMP.get("stale_modules")
            or _BOOT_STAMP.get("head_sha") is None
        )
        if impure and gate_mode == "strict":
            detail = (
                f"dirty={_BOOT_STAMP.get('dirty')} stale={_BOOT_STAMP.get('stale_modules')} "
                f"head={_BOOT_STAMP.get('head_sha')}"
            )
            logger.error("runtime provenance impure, strict gate → refusing to render: %s", detail)
            await _ops_alert(f"WR2 HTML worker refused to render (strict runtime-sha gate): {detail}")
            return 3
        if impure:
            logger.warning(
                "runtime provenance impure (gate=%s): dirty=%s stale=%s",
                gate_mode, _BOOT_STAMP.get("dirty"), _BOOT_STAMP.get("stale_modules"),
            )

    # The runtime SHA rides in the lease owner (visible in DB per rendering row).
    # Built ONCE and passed everywhere — the CAS requires exact-string equality.
    head12 = (_BOOT_STAMP.get("head_sha") or "nohead")[:12]
    owner = f"html-apply-{os.getpid()}-{uuid.uuid4().hex[:8]}@{head12}"
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
