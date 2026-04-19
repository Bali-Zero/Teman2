"""WR2 activation smoke test — dry-run end-to-end sanity check.

What it does:
    1. Connects to nuzantara-postgres via the fly proxy on localhost:15432.
    2. Creates a single war_room_draft with a clearly labelled test topic.
    3. Skips the 3-LLM ToneCouncil (too costly + needs Claude/Gemini CLI
       subprocess setup). Deterministically picks register=analitico.
    4. Calls ImagenClient.generate() ONCE for the cover slide — the only
       real cost on this run (~$0.06 ULTRA). Records the cost row.
    5. For 3 other slide positions, stores placeholder dicts with the
       prompt text only (no Imagen call, no cost row).
    6. Sends ONE Telegram message to Zero via TelegramReviewAdapter with
       a [DRY-RUN] prefix so the review gate keyboard is recognisably
       non-actionable.
    7. Prints final draft state + war_room_costs total.

What it does NOT do:
    - Publish to Instagram / X / LinkedIn / Brevo.
    - Invoke the Claude/Gemini/DeepSeek CLI runners.
    - Trigger the Playwright layout renderer.
    - Run the review SLA worker or measurer.

Preconditions:
    - `fly proxy 15432:5432 -a nuzantara-postgres &` in another shell.
    - Env: DATABASE_URL (localhost form), GOOGLE_API_KEY, TELEGRAM_BOT_TOKEN,
      TELEGRAM_OWNER_CHAT_ID.

Run:
    cd apps/backend-rag
    PYTHONPATH=. python -m scripts.wr2_smoke_test  # from repo root instead
    # or: PYTHONPATH=. python ../../scripts/wr2_smoke_test.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from decimal import Decimal
from uuid import uuid4

import asyncpg

logger = logging.getLogger("wr2.smoke")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


async def run() -> int:
    _configure_logging()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set (need localhost form via fly proxy)")
        return 1
    if "flycast" in dsn:
        logger.error("DATABASE_URL uses flycast; start `fly proxy 15432:5432 -a nuzantara-postgres` and export the localhost DSN")
        return 1

    owner_chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    if not owner_chat_id:
        logger.error("TELEGRAM_OWNER_CHAT_ID not set")
        return 1

    # Late imports so failed preconditions above don't trigger heavy deps
    from backend.services.visual.imagen_client import (
        ImagenClient,
        ImagenQuality,
    )
    from backend.services.war_room.models import (
        CostType,
        DraftStatus,
        RegisterTone,
        WarRoomDraftCreate,
    )
    from backend.services.war_room.repository import WarRoomRepository

    async def _init_conn(conn: asyncpg.Connection) -> None:
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=2,
        command_timeout=60,
        init=_init_conn,
    )
    try:
        repo = WarRoomRepository(db_pool=pool)

        # ── 1. Create draft ──────────────────────────────────────────
        # Intentionally omit brief_json here to sidestep a pre-existing
        # double-encoding bug in WarRoomRepository.create_draft (stores
        # json.dumps(dict) under the jsonb codec → JSON-encoded string).
        # We UPDATE the row with a proper dict below instead.
        topic = "WR2 activation smoke test 2026-04-20"
        draft = await repo.create_draft(
            WarRoomDraftCreate(
                topic=topic,
                tone_register=RegisterTone.ANALITICO,
                status=DraftStatus.BRIEFED,
            ),
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE war_room_drafts
                   SET brief_json = $1
                 WHERE id = $2;
                """,
                {
                    "origin": "wr2_smoke_test",
                    "dry_run": True,
                    "council_skipped": True,
                },
                draft.id,
            )
        logger.info("draft created id=%s", draft.id)

        # ── 2. Imagen cover (real call) ──────────────────────────────
        cover_prompt = (
            "Editorial hero illustration for a business intelligence brief, "
            "balanced composition, muted palette, Italian editorial tone. "
            "Subject: Bali business ecosystem, abstract."
        )
        # NOTE: 4:5 is the IG carousel spec but Imagen 4.0 rejects it with
        # "supported: 1:1, 9:16, 16:9, 4:3, 3:4". Using 3:4 (closest) for
        # the smoke test; ImagenClient.DEFAULT aspect_ratio needs a bug-fix
        # PR separately — see ACTIVATION_PLAN §B.7.
        imagen = ImagenClient(aspect_ratio="3:4")
        logger.info("calling Imagen ULTRA for cover...")
        imagen_result = await imagen.generate(
            cover_prompt, quality=ImagenQuality.ULTRA,
        )
        if not imagen_result.ok:
            logger.error("Imagen failed: %s", imagen_result.error)
            return 2
        logger.info(
            "Imagen OK — model=%s bytes=%d duration_ms=%.1f",
            imagen_result.model_id,
            len(imagen_result.image_bytes or b""),
            imagen_result.duration_ms,
        )

        # Record cost row (ULTRA = $0.06)
        await repo.record_cost(
            draft_id=draft.id,
            cost_type=CostType.IMAGEN_ULTRA,
            cost_usd=Decimal("0.06"),
            meta={
                "model": imagen_result.model_id,
                "slide_kind": "cover",
                "prompt_preview": cover_prompt[:120],
                "dry_run": True,
            },
        )

        # ── 3. Placeholder slides ($0) ───────────────────────────────
        placeholders = [
            {
                "slide_number": i,
                "kind": "placeholder",
                "prompt": f"[{topic}] slide {i} body — render deferred "
                          f"(cost-saving smoke test mode)",
            }
            for i in range(2, 5)
        ]
        # Attach placeholders to draft via update of slides_json. Pass the
        # list directly — asyncpg jsonb codec handles serialization. (The
        # repository's own methods wrap with json.dumps which double-encodes
        # under the codec, see WR2 repository bug note in ACTIVATION_PLAN
        # §B.7.)
        # Also: slides_json column is jsonb with no object/array enforcement,
        # but WarRoomDraft pydantic model expects a dict. We store as a
        # dict keyed by slide_number to match model expectations.
        slides_dict = {str(p["slide_number"]): p for p in placeholders}
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE war_room_drafts
                   SET slides_json = $1
                 WHERE id = $2;
                """,
                slides_dict,
                draft.id,
            )
        logger.info(
            "stored %d placeholder slides (no Imagen call, no cost row)",
            len(placeholders),
        )

        # ── 4. Advance status to pending_review ─────────────────────
        await repo.update_status(draft.id, DraftStatus.PENDING_REVIEW)
        logger.info("draft status → pending_review")

        # ── 5. Telegram [DRY-RUN] notice ────────────────────────────
        from backend.services.review.telegram_adapter import (
            TelegramReviewAdapter,
        )

        adapter = TelegramReviewAdapter()
        msg = (
            f"[DRY-RUN] WR2 activation smoke test\n\n"
            f"Draft ID: {draft.id}\n"
            f"Topic: {topic}\n"
            f"Register: analitico (council skipped)\n"
            f"Cover: Imagen ULTRA bytes={len(imagen_result.image_bytes or b'')}\n"
            f"Placeholder slides: {len(placeholders)}\n"
            f"Cost recorded: $0.06\n\n"
            f"NESSUNA PUBBLICAZIONE effettuata — Legge 5 rispettata. "
            f"Questo è solo un sanity check di pipeline, non richiede azione."
        )
        # Send plain message (no image upload — would need Tigris bucket)
        # Directly hit Telegram sendMessage via httpx using the adapter's token.
        import httpx  # local import to keep deps minimal
        async with httpx.AsyncClient(timeout=20.0) as client:
            tg_resp = await client.post(
                f"{adapter.api_url}/sendMessage",
                data={"chat_id": owner_chat_id, "text": msg},
            )
            if tg_resp.status_code != 200:
                logger.error(
                    "telegram sendMessage failed: HTTP %d %s",
                    tg_resp.status_code,
                    tg_resp.text[:300],
                )
            else:
                logger.info("telegram notice delivered")

        # ── 6. Final state summary ──────────────────────────────────
        final_draft = await repo.get_draft(draft.id)
        total_cost = await repo.total_cost_for_draft(draft.id)
        summary = {
            "draft_id": str(draft.id),
            "final_status": final_draft.status.value if final_draft else "unknown",
            "total_cost_usd": float(total_cost),
            "placeholder_slides": len(placeholders),
            "imagen_ok": imagen_result.ok,
        }
        sys.stdout.write(json.dumps(summary, default=str) + "\n")
        return 0
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
