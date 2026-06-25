"""WR2 Instagram publish router — server-side, operator-gated (Legge 5).

WHY THIS EXISTS (2026-06-25)
---------------------------
The WR2 Control app runs on M5 (the operator's workstation). The Instagram
publisher needs three things that live ONLY on the Fly backend, never on M5:

  * Tigris creds (already used by ``/api/assets/upload`` to host the slide PNGs)
  * the ``wr2_publish_attempts`` ledger DB (anti-double-publish guard)
  * the Instagram access token + account id (``INSTAGRAM_ACCESS_TOKEN`` /
    ``INSTAGRAM_ACCOUNT_ID`` Fly secrets)

So the publish step is driven server-side. The flow the app follows:

  1. App renders the 8 slides locally, then POSTs each PNG to
     ``/api/assets/upload`` (existing endpoint) → 8 public, Graph-fetchable
     ``https://...tigris.dev/...`` URLs.
  2. App POSTs those URLs here. This endpoint NEVER touches raw bytes — it
     receives ``image_urls`` that are already public.

LEGGE 5 — operator gate
-----------------------
The endpoint publishes ONLY when ``confirm == True``. With ``confirm == False``
(the default) it builds the :class:`DraftPayload`, runs ``IGPublisher.validate``,
and returns exactly what WOULD be posted — it NEVER calls ``publish()`` and it
NEVER writes a terminal ledger row. ``approval_state`` is set to ``"approved"``
ONLY when ``confirm == True``; that is the single flag that the restored
publisher checks at ``ig_publisher.py:239`` before dispatching to Meta.

ANTI-DOUBLE-PUBLISH
-------------------
Before ``publish()`` (confirm path only) we apply the SAME ledger precondition
as the CLI ``scripts/wr2_ig_publish.py`` (``_ledger_precondition``): resolve a
REAL ``wr2_carousel_runs.carousel_id``, REFUSE (HTTP 409 + prior permalink) if a
prior attempt for this carousel+content is already in a terminal state
(``published``/``recorded``), else write a ``planned`` row as a hard precondition
keyed on the SAME ``idempotency_key`` format
(``<carousel_id>:<platform>:<content_hash[:16]>``). The two code paths therefore
share one ledger and one idempotency guarantee. Fails CLOSED if the DB is
unreachable — a real publish without the guard is refused, never silently
skipped.

The ``scripts/wr2_ig_publish.py`` helpers are NOT importable on Fly (the
Dockerfile ships ``apps/backend-rag/scripts``, not the repo-root ``scripts/``
where that module lives), so the precondition is replicated here — same SQL,
same key format, ledger-compatible with the CLI.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user
from backend.app.utils.crm_utils import is_crm_admin
from backend.app.utils.logging_utils import get_logger
from backend.services.publisher.base import DraftPayload, SlidePayload

logger = get_logger(__name__)

# Graph host. The live Fly secret INSTAGRAM_ACCESS_TOKEN is an "Instagram API
# with Instagram Login" token (verified 2026-06-25): it works against
# graph.instagram.com, NOT graph.facebook.com (the restored IGPublisher's
# default). scripts/wr2_ig_publish.py wires the publisher the same way — we
# reuse that exact pattern: IGPublisher(graph_base=_IG_GRAPH_BASE).
_IG_GRAPH_BASE = "https://graph.instagram.com/v22.0"

_PLATFORM = "instagram"

# Deterministic namespace so the same slug always maps to the same draft UUID
# (mirrors scripts/wr2_ig_publish.py:_WR2_DRAFT_NAMESPACE).
_WR2_DRAFT_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


# ── Auth gate (same pattern as war_room_dashboard._require_admin) ──────────────


async def _require_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not is_crm_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


router = APIRouter(
    prefix="/api/war-room",
    tags=["war-room", "wr2", "publish"],
    dependencies=[Depends(_require_admin)],
)


# ── Request / response models ──────────────────────────────────────────────────


class PublishIGRequest(BaseModel):
    slug: str = Field(..., min_length=1, description="Carousel slug (== wr2_carousel_runs.topic).")
    image_urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Public Tigris URLs of the slides, slide 1 = cover. Max 10 (IG carousel limit).",
    )
    caption: str = Field(..., description="IG caption (max 2200 chars, enforced by publisher).")
    alt_texts: list[str] | None = Field(
        default=None,
        description="Optional per-slide alt-text, aligned to image_urls by index.",
    )
    confirm: bool = Field(
        default=False,
        description="LEGGE 5 operator gate. False = dry validation (no publish). True = publish.",
    )


# ── Content key + draft assembly ───────────────────────────────────────────────


def _content_hash(image_urls: list[str], caption: str) -> str:
    """sha256 over the ordered slide URLs + caption — the idempotency content key.

    The CLI hashes raw slide bytes; here the bytes live behind content-addressed
    Tigris URLs (the URL embeds the sha256 of the bytes), so hashing the ordered
    URLs + caption yields an equally stable, content-bound key for this path.
    """
    h = hashlib.sha256()
    for u in image_urls:
        h.update(u.encode("utf-8"))
        h.update(b"\x00")
    h.update(caption.encode("utf-8"))
    return h.hexdigest()


def _build_draft(
    *,
    slug: str,
    draft_id: uuid.UUID,
    image_urls: list[str],
    caption: str,
    alt_texts: list[str] | None,
    approved: bool,
) -> DraftPayload:
    """Assemble a DraftPayload. cover = image_urls[0]; rest = body slides."""

    def _alt(idx: int) -> str | None:
        if alt_texts and idx < len(alt_texts):
            return alt_texts[idx]
        return None

    cover_url = image_urls[0]
    body = [
        SlidePayload(slide_number=i + 1, image_url=url, caption=None, alt_text=_alt(i))
        for i, url in enumerate(image_urls[1:], start=1)
    ]
    return DraftPayload(
        draft_id=draft_id,
        topic=slug,
        tone_register=None,
        cover_image_url=cover_url,
        main_caption=caption,
        slides=body,
        cover_alt_text=_alt(0),
        approval_state="approved" if approved else "pending",
    )


# ── Ledger (anti-double-publish) — replicated from scripts/wr2_ig_publish.py ────


async def _resolve_carousel_id(conn: asyncpg.Connection, slug: str) -> str:
    """Return a REAL ``wr2_carousel_runs.carousel_id`` (UUID) for this slug.

    Mirrors scripts/wr2_ig_publish.py:_resolve_carousel_id — look up an existing
    run by topic == slug (newest first), else create a minimal 'rendered' row.
    Never swallows a FK error: if neither find nor create works the caller fails
    closed (the exception propagates and the publish is refused).
    """
    row = await conn.fetchrow(
        "SELECT carousel_id FROM wr2_carousel_runs "
        "WHERE topic = $1 ORDER BY created_at DESC LIMIT 1",
        slug,
    )
    if row is not None:
        cid = str(row["carousel_id"])
        logger.info("wr2_publish: found carousel_run slug=%s -> %s", slug, cid)
        return cid

    topic_hash = hashlib.sha256(slug.encode("utf-8")).hexdigest()
    session_id = f"wr2_publish_endpoint:{slug}"
    new_row = await conn.fetchrow(
        "INSERT INTO wr2_carousel_runs "
        "(topic, topic_hash, state, session_id, publish_mode) "
        "VALUES ($1, $2, 'rendered', $3, 'manual') "
        "RETURNING carousel_id",
        slug,
        topic_hash,
        session_id,
    )
    cid = str(new_row["carousel_id"])
    logger.info("wr2_publish: created carousel_run slug=%s -> %s", slug, cid)
    return cid


async def _ledger_precondition(
    *,
    slug: str,
    content_hash: str,
) -> tuple[str, str, str | None]:
    """HARD precondition before media_publish. Returns (carousel_id, action, prior_url).

    action == "proceed" -> a 'planned' row was written; caller may publish.
    action == "refuse"  -> already published/recorded; caller MUST NOT publish.

    Fails closed (raises HTTPException 503) if the ledger DB is unreachable or
    the carousel_runs FK can't be satisfied — NEVER silently skips the guard.
    Identical SQL + idempotency_key format to scripts/wr2_ig_publish.py so the
    two paths share one ledger.
    """
    dsn = settings.database_url
    if not dsn:
        raise HTTPException(
            status_code=503,
            detail=(
                "ledger DB unreachable (DATABASE_URL not set). A real publish "
                "REQUIRES the wr2_publish_attempts idempotency guard — refusing "
                "to publish without it (fail-closed)."
            ),
        )

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:  # any connect failure must fail closed
        logger.error("wr2_publish: ledger DB unreachable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"ledger DB unreachable ({type(exc).__name__}). Refusing to "
                "publish without the idempotency guard (fail-closed)."
            ),
        ) from exc

    try:
        carousel_id = await _resolve_carousel_id(conn, slug)
        idempotency_key = f"{carousel_id}:{_PLATFORM}:{content_hash[:16]}"

        prior = await conn.fetchrow(
            "SELECT state, provider_response FROM wr2_publish_attempts "
            "WHERE idempotency_key = $1",
            idempotency_key,
        )
        if prior is not None and prior["state"] in ("published", "recorded"):
            prior_url = None
            pr = prior["provider_response"]
            if pr:
                try:
                    pr_d = pr if isinstance(pr, dict) else json.loads(pr)
                    prior_url = pr_d.get("permalink") or pr_d.get("post_url")
                except (ValueError, TypeError):
                    prior_url = None
            logger.warning(
                "wr2_publish: REFUSE double-publish key=%s already state=%s",
                idempotency_key,
                prior["state"],
            )
            return carousel_id, "refuse", prior_url

        await conn.execute(
            "INSERT INTO wr2_publish_attempts "
            "(carousel_id, platform, content_hash, state, idempotency_key) "
            "VALUES ($1, $2, $3, 'planned', $4) "
            "ON CONFLICT (idempotency_key) DO UPDATE "
            "SET state = 'planned', updated_at = now()",
            uuid.UUID(carousel_id),
            _PLATFORM,
            content_hash,
            idempotency_key,
        )
        logger.info(
            "wr2_publish: ledger 'planned' written key=%s carousel_id=%s",
            idempotency_key,
            carousel_id,
        )
        return carousel_id, "proceed", None
    finally:
        await conn.close()


async def _ledger_record_result(
    *,
    carousel_id: str,
    content_hash: str,
    state: str,
    provider_response: dict[str, Any] | None,
) -> None:
    """Update the ledger row to a terminal state after the publish attempt.

    Best-effort: a failure here is logged but NEVER flips a successful Meta
    publish into a failure (the post already exists). The anti-double-publish
    guarantee is the PRE-publish 'planned' row + UNIQUE key, already committed.
    """
    try:
        dsn = settings.database_url
        if not dsn:
            return
        conn = await asyncpg.connect(dsn)
        try:
            idempotency_key = f"{carousel_id}:{_PLATFORM}:{content_hash[:16]}"
            await conn.execute(
                "UPDATE wr2_publish_attempts "
                "SET state = $1, provider_response = $2::jsonb, updated_at = now() "
                "WHERE idempotency_key = $3",
                state,
                json.dumps(provider_response or {}),
                idempotency_key,
            )
            logger.info("wr2_publish: ledger updated state=%s key=%s", state, idempotency_key)
        finally:
            await conn.close()
    except Exception as exc:  # bookkeeping must never crash a live post
        logger.warning("wr2_publish: ledger result update failed (non-fatal): %s", exc)


# ── Endpoint ───────────────────────────────────────────────────────────────────


@router.post("/publish-ig")
async def publish_ig(body: PublishIGRequest) -> dict[str, Any]:
    """Publish (or dry-validate) a WR2 carousel to Instagram, server-side.

    LEGGE 5: ``confirm == False`` => dry validation only, ``publish()`` is never
    called and ``approval_state`` stays ``"pending"``. ``confirm == True`` =>
    ledger precondition + real publish with ``approval_state == "approved"``.
    """
    from backend.services.publisher.ig_publisher import (
        IGPublisher,
        close_ig_publisher_client,
    )
    from backend.services.publisher.base import PublisherError

    slug = body.slug
    image_urls = body.image_urls
    caption = body.caption
    draft_id = uuid.uuid5(_WR2_DRAFT_NAMESPACE, slug)
    content_hash = _content_hash(image_urls, caption)

    # ── DRY path (LEGGE 5): build draft (pending) + validate, NEVER publish. ──
    if not body.confirm:
        draft = _build_draft(
            slug=slug,
            draft_id=draft_id,
            image_urls=image_urls,
            caption=caption,
            alt_texts=body.alt_texts,
            approved=False,  # stays 'pending' — publisher gate would refuse.
        )
        try:
            publisher = IGPublisher(graph_base=_IG_GRAPH_BASE)
        except PublisherError as exc:
            # Missing creds — surface as 503 (service not configured), no publish.
            raise HTTPException(status_code=503, detail=f"IG publisher not configured: {exc}") from exc
        validation = await publisher.validate(draft)
        logger.info(
            "wr2_publish: DRY validation slug=%s items=%d valid=%s",
            slug,
            len(image_urls),
            validation.ok,
        )
        return {
            "ok": True,
            "dry_run": True,
            "would_publish": {
                "slug": slug,
                "cover_image_url": image_urls[0],
                "slide_count": len(image_urls),
                "image_urls": image_urls,
                "caption_chars": len(caption),
                "approval_state": draft.approval_state,  # 'pending'
            },
            "validation": {"ok": validation.ok, "issues": validation.issues},
            "note": "confirm=false → publish() NOT called (Legge 5). Re-send with confirm=true to publish.",
        }

    # ── CONFIRM path: ledger precondition (anti-double-publish), then publish. ──
    carousel_id, action, prior_url = await _ledger_precondition(
        slug=slug, content_hash=content_hash
    )
    if action == "refuse":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "already_published",
                "message": "A prior attempt for this carousel+content is already published.",
                "permalink": prior_url,
            },
        )

    draft = _build_draft(
        slug=slug,
        draft_id=draft_id,
        image_urls=image_urls,
        caption=caption,
        alt_texts=body.alt_texts,
        approved=True,  # flips publisher's internal gate (ig_publisher.py:239).
    )

    try:
        publisher = IGPublisher(graph_base=_IG_GRAPH_BASE)
    except PublisherError as exc:
        await _ledger_record_result(
            carousel_id=carousel_id,
            content_hash=content_hash,
            state="failed",
            provider_response={"error": f"publisher init: {exc}"},
        )
        raise HTTPException(status_code=503, detail=f"IG publisher not configured: {exc}") from exc

    try:
        result = await publisher.publish(draft)
    finally:
        await close_ig_publisher_client()

    if not result.ok:
        await _ledger_record_result(
            carousel_id=carousel_id,
            content_hash=content_hash,
            state="failed",
            provider_response={"error": result.error},
        )
        # The publisher's approval-gate refusal and validation failures both
        # surface here as result.ok == False — return a clear 4xx, not a 500.
        logger.warning("wr2_publish: publish failed slug=%s err=%s", slug, result.error)
        raise HTTPException(status_code=422, detail={"error": "publish_failed", "message": result.error})

    await _ledger_record_result(
        carousel_id=carousel_id,
        content_hash=content_hash,
        state="published",
        provider_response={
            "permalink": result.post_url,
            "post_external_id": result.post_external_id,
            "meta": result.meta,
        },
    )

    logger.info(
        "wr2_publish: PUBLISHED slug=%s media_id=%s permalink=%s",
        slug,
        result.post_external_id,
        result.post_url,
    )
    return {
        "ok": True,
        "dry_run": False,
        "permalink": result.post_url,
        "post_id": result.post_external_id,
    }
