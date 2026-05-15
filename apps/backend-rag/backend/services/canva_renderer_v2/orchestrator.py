"""WR2 orchestrator top-level: composes all submodules.

Flow per run():
1. Connect to PG.
2. Check kill switch — exit 3 if off.
3. Reset stale leases (>15min watchdog).
4. Fetch up to MAX_DRAFTS_PER_RUN pending draft IDs.
5. For each ID: acquire CAS lease → process_draft().
6. Close PG. Return ExitCode.

Each draft has its own try/except so one failure doesn't block siblings.
"""
from __future__ import annotations

import enum
import json
import logging
import os
import socket
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.canva_renderer_v2 import _pg
from backend.services.canva_renderer_v2._canva_mcp import (
    CanvaImportError,
    CanvaMcpClient,
    is_transient_error,
)
from backend.services.canva_renderer_v2._pdf_pipeline import PdfRenderError, render_pdf
from backend.services.canva_renderer_v2._schema_adapter import (
    adapt_legacy_schema,
    is_legacy_schema,
)
from backend.services.canva_renderer_v2._telegram import send_telegram
from backend.services.canva_renderer_v2._telemetry import log_telemetry
from backend.services.canva_renderer_v2._tigris import (
    TigrisError,
    delete_pdf,
    delete_pdf_by_key,
    get_s3_client,
    upload_pdf,
)
from backend.services.canva_renderer_v2._token_storage import TokenStorageError

logger = logging.getLogger(__name__)

MAX_DRAFTS_PER_RUN = 3
STALE_LEASE_MINUTES = 15
WR2_DRAFTS_FOLDER_ID = os.environ.get("WR2_DRAFTS_FOLDER_ID", "")
WR2_DRAFTS_FOLDER_ID_E2E = os.environ.get("WR2_DRAFTS_FOLDER_ID_E2E", "")


class ExitCode(enum.IntEnum):
    OK = 0
    TRANSIENT_ERROR = 1
    CONFIG_INVALID = 2
    KILL_SWITCH_OFF = 3
    TOKEN_FILE_MISSING = 4
    OAUTH_REFRESH_REVOKED = 5
    FLOCK_CONTENTION = 6
    TOKEN_CORRUPT = 7


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "wr2_canva_pdf_apply.log"),
            logging.StreamHandler(),
        ],
    )


async def _connect(dsn: str) -> asyncpg.Connection:
    return await asyncpg.connect(dsn, timeout=10)


def _lease_owner() -> str:
    return f"{os.getpid()}@{socket.gethostname()}"


async def process_draft(
    *,
    conn: asyncpg.Connection,
    mcp_client: Any,
    s3: Any,
    draft_id: UUID | str,
    lease_owner: str,
) -> bool:
    """Acquire lease + run pipeline. Returns True on success, False on any failure."""
    row = await _pg.acquire_lease_and_fetch(conn, draft_id=draft_id, lease_owner=lease_owner)
    if row is None:
        return False  # lost race, silent

    topic = row["topic"]
    slides_raw = row["slides_json"]
    slides = json.loads(slides_raw) if isinstance(slides_raw, str) else slides_raw

    t0 = time.time()
    e2e_mode = os.environ.get("WR2_E2E_MODE") == "true"
    tigris_prefix = "wr2-pdf-tests" if e2e_mode else "wr2-pdf"
    folder_id = WR2_DRAFTS_FOLDER_ID_E2E if e2e_mode else WR2_DRAFTS_FOLDER_ID

    # Step A — schema adapt
    if is_legacy_schema(slides):
        slides = adapt_legacy_schema(slides, topic=topic)
        logger.info("Draft %s: adapted legacy schema", draft_id)

    # Step B — PDF render
    pdf_path = Path(f"/tmp/wr2_{draft_id}.pdf")
    try:
        render_pdf(slides, draft_id=str(draft_id), out_path=pdf_path)
    except PdfRenderError as e:
        await _pg.release_lease_permanent(
            conn, draft_id=draft_id, status="pdf_render_failed", reason=str(e),
        )
        send_telegram(
            f"🚨 WR2 PDF render FAILED\ndraft: `{draft_id}`\ntopic: {topic[:80]}\nerr: `{str(e)[:300]}`"
        )
        log_telemetry(
            draft_id=str(draft_id),
            outcome="pdf_render_failed",
            duration_s=time.time() - t0,
            exc_head=str(e),
        )
        return False

    # Step C — Tigris upload
    try:
        pdf_url, pdf_s3_key = upload_pdf(s3, pdf_path, draft_id=str(draft_id), prefix=tigris_prefix)
    except TigrisError as e:
        await _pg.release_lease_permanent(
            conn, draft_id=draft_id, status="pdf_render_failed", reason=str(e),
        )
        send_telegram(
            f"🚨 WR2 Tigris upload FAILED\ndraft: `{draft_id}`\nerr: `{str(e)[:300]}`"
        )
        log_telemetry(
            draft_id=str(draft_id),
            outcome="tigris_failed",
            duration_s=time.time() - t0,
            exc_head=str(e),
        )
        return False

    # Step D — Canva import
    try:
        design_id, edit_url = await mcp_client.import_design_from_url(pdf_url, title=topic[:80])
    except Exception as e:
        delete_pdf_by_key(s3, key=pdf_s3_key)
        if is_transient_error(e):
            await _pg.release_lease_transient(
                conn, draft_id=draft_id, reason=f"{type(e).__name__}: {e}"
            )
            log_telemetry(
                draft_id=str(draft_id),
                outcome="canva_transient",
                duration_s=time.time() - t0,
                exc_head=str(e),
            )
        else:
            await _pg.release_lease_permanent(
                conn, draft_id=draft_id, status="canva_import_failed", reason=str(e),
            )
            send_telegram(
                f"🚨 WR2 Canva import FAILED\ndraft: `{draft_id}`\nerr: `{str(e)[:300]}`"
            )
            log_telemetry(
                draft_id=str(draft_id),
                outcome="canva_import_failed",
                duration_s=time.time() - t0,
                exc_head=str(e),
            )
        return False

    # Step E — move-to-folder (best effort)
    if folder_id:
        await mcp_client.move_item_to_folder(design_id, folder_id)

    # Step F — persist
    try:
        await _pg.persist_canva_result(
            conn,
            draft_id=draft_id,
            canva_design_id=design_id,
            canva_edit_url=edit_url,
            canva_view_url=None,
        )
    except Exception as e:  # noqa: BLE001 — orphan: Canva design exists but DB didn't record
        send_telegram(
            f"🚨 WR2 PG persist FAILED (Canva design EXISTS but DB unaware)\n"
            f"draft: `{draft_id}` design: `{design_id}` err: `{str(e)[:300]}`"
        )
        log_telemetry(
            draft_id=str(draft_id),
            outcome="persist_failed",
            duration_s=time.time() - t0,
            exc_head=str(e),
        )
        return False

    duration = time.time() - t0
    send_telegram(f"🎨 WR2 rendered: {topic[:80]}\n{edit_url}\nduration: {duration:.1f}s")
    log_telemetry(draft_id=str(draft_id), outcome="success", duration_s=duration)
    pdf_path.unlink(missing_ok=True)
    return True


async def run() -> ExitCode:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return ExitCode.CONFIG_INVALID

    try:
        conn = await _connect(dsn)
    except Exception as e:
        logger.error("PG connect failed: %s", e)
        return ExitCode.TRANSIENT_ERROR

    try:
        if not await _pg.is_kill_switch_enabled(conn):
            logger.info("wr2_canva_renderer_enabled != true — exiting quiet")
            return ExitCode.KILL_SWITCH_OFF

        # Stale lease watchdog (only emits Telegram, doesn't process)
        recovered = await _pg.reset_stale_leases(conn, stale_after_minutes=STALE_LEASE_MINUTES)
        if recovered:
            send_telegram(
                f"🪂 WR2 orchestrator recovered {len(recovered)} stale leases: "
                f"{[str(x)[:8] for x in recovered[:5]]}"
            )

        draft_ids = await _pg.fetch_pending_draft_ids(conn, limit=MAX_DRAFTS_PER_RUN)
        if not draft_ids:
            logger.info("no pending drafts")
            return ExitCode.OK

        lease_owner = _lease_owner()
        s3 = get_s3_client()

        try:
            async with CanvaMcpClient() as mcp_client:
                for draft_id in draft_ids:
                    try:
                        await process_draft(
                            conn=conn,
                            mcp_client=mcp_client,
                            s3=s3,
                            draft_id=draft_id,
                            lease_owner=lease_owner,
                        )
                    except Exception as exc:  # noqa: BLE001 — siblings must continue
                        logger.error("Draft %s unexpected exception: %s", draft_id, exc)
                        try:
                            await _pg.release_lease_transient(
                                conn, draft_id=draft_id, reason=f"unexpected: {exc}"
                            )
                        except Exception:  # noqa: BLE001
                            pass
        except TokenStorageError as e:
            msg = str(e).lower()
            if "not found" in msg:
                send_telegram(
                    f"🚨 WR2 token file missing — run scripts/wr2_bootstrap_canva_oauth.py\n{e}"
                )
                return ExitCode.TOKEN_FILE_MISSING
            if "hmac" in msg:
                send_telegram(f"🚨 WR2 token file CORRUPT — manual repair\n{e}")
                return ExitCode.TOKEN_CORRUPT
            send_telegram(f"🚨 WR2 token storage error\n{e}")
            return ExitCode.CONFIG_INVALID
        except CanvaImportError as e:
            if "refresh token revoked" in str(e).lower() or "interactive" in str(e).lower():
                send_telegram(f"🚨 WR2 OAuth refresh revoked — re-bootstrap needed\n{e}")
                return ExitCode.OAUTH_REFRESH_REVOKED
            send_telegram(f"🚨 WR2 Canva MCP error: {e}")
            return ExitCode.TRANSIENT_ERROR

        return ExitCode.OK
    finally:
        await conn.close()
