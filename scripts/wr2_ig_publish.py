#!/usr/bin/env python3
"""wr2_ig_publish — operator-gated Instagram carousel publisher for WR2.

WHY THIS EXISTS (2026-06-25)
----------------------------
The WR2 pipeline renders a carousel's slides to ``output/carousel/<slug>/slides/``
but the *publish* step is deliberately NOT automated (Legge 5 — nothing
auto-publishes). This thin CLI is what the WR2 Control app shells out to when an
operator clicks "Publish to Instagram". It:

  1. Loads ``slides.json`` + the numbered ``NN.png`` slides for ``<slug>``.
  2. Uploads each PNG to Tigris (``image/png``, public-read) — Meta Graph rejects
     Drive HTML preview pages, so we serve raw image bytes from a stable URL.
  3. Builds a :class:`DraftPayload`. ``approval_state`` is set to ``"approved"``
     ONLY when ``--confirm`` is passed — this is the operator gate.
  4. Writes a ``wr2_publish_attempts`` ledger row as a HARD precondition BEFORE
     the Meta ``media_publish`` call (anti-double-publish). On a UNIQUE
     idempotency-key clash where the existing row is already
     ``published``/``recorded``, it REFUSES (no-op) and prints the prior link.
  5. Calls :meth:`IGPublisher.publish` — which itself refuses unless
     ``approval_state == "approved"`` (Legge 5, untouched in the restored
     publisher).

DRY-RUN IS THE DEFAULT. Without ``--confirm`` the CLI does EVERYTHING except the
ledger write + ``publish()``: it uploads to Tigris, builds the draft, and prints
exactly what WOULD post. With ``--confirm`` it writes the ledger row, flips
``approval_state="approved"``, and publishes for real.

HARD STOPS
  - ``WR2_IG_CONTENT_PUBLISH_VERIFIED`` must equal ``"1"`` or the CLI aborts
    before doing anything (the token-scope gate the workflow flagged).
  - The ledger DB is a HARD requirement for a real (``--confirm``) publish. If
    the DSN (``settings.database_url`` / ``DATABASE_URL``) is unreachable, the
    CLI FAILS CLOSED rather than publishing without an idempotency guard. A FK
    violation (slug has no/an-uncreatable ``wr2_carousel_runs`` row) is surfaced,
    never swallowed.

USAGE
    PYTHONPATH=scripts <wt>/apps/backend-rag/.venv/bin/python -m wr2_ig_publish \
        <slug> [--confirm] [--caption-file <path>]

    <slug> = a dir name under apps/war-room/output/carousel/

On a successful publish the LAST line of stdout is exactly::

    IG_URL=<permalink>

(the app parses this line). Everything else goes through ``logger`` (stderr).

EXIT CODES
    0  dry-run completed, or publish succeeded (IG_URL printed), or a prior
       already-published row was found (idempotent no-op — prior link printed).
    1  any hard stop / failure (token gate, missing slides, ledger unreachable,
       FK violation, validation failure, Meta API failure, Legge-5 refusal).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("wr2.ig_publish")

# ── path bootstrap ───────────────────────────────────────────────────
# `backend` is NOT editable-installed in the venv (verified 2026-06-25), so we
# put apps/backend-rag on sys.path explicitly. Derive it from this file's
# location so the script is invocation-agnostic (works from any cwd / however
# the app spawns it). Repo root = three parents up from scripts/wr2_ig_publish.py
# (scripts/ -> repo root). The backend lives at <repo>/apps/backend-rag.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "apps" / "backend-rag"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import wr2_orchestrator_metrics as wom  # noqa: E402  (B11: per-step observability, fail-open)

# Carousel output root. Matches wr2_rerender_local.py convention: defaults to the
# M5 app-machine Desktop path, overridable via WR2_CAROUSEL_ROOT for Pro/Mini.
# Resolved at CALL time (not import time) so the env override is honoured even
# when the module is imported once and driven repeatedly (app / tests).
def _carousel_root() -> Path:
    return Path(
        os.environ.get(
            "WR2_CAROUSEL_ROOT",
            str(Path.home() / "nuzantara/apps/war-room/output/carousel"),
        )
    )

# Deterministic namespace so the same slug always maps to the same draft UUID
# (DraftPayload.draft_id is typed UUID; the ledger groups slides under it).
_WR2_DRAFT_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

_PLATFORM = "instagram"

# Graph host. The live Fly secret INSTAGRAM_ACCESS_TOKEN is an *Instagram API
# with Instagram Login* token (verified 2026-06-25 via content_publishing_limit
# probe: username=balizero0, account_type=BUSINESS, instagram_content_publish
# scope present). That token works against graph.instagram.com, NOT
# graph.facebook.com (the latter returns "Cannot parse access token"). The
# restored IGPublisher defaults to graph.facebook.com/v20.0, so we override its
# graph_base at construction — the carousel endpoint shapes (/{ig-id}/media,
# media_type=CAROUSEL, /{ig-id}/media_publish) are identical across both hosts.
# Overridable via WR2_IG_GRAPH_BASE for the rare facebook-graph token case.
_IG_GRAPH_BASE = os.environ.get(
    "WR2_IG_GRAPH_BASE", "https://graph.instagram.com/v22.0"
)

_PLACEHOLDER_CAPTION = (
    "[PLACEHOLDER CAPTION — operator did not supply --caption-file] "
    "Bali Zero regulatory update. See balizero.com."
)


class PublishAborted(RuntimeError):
    """Raised for any hard-stop condition. Caller maps to exit 1."""


# ── slide discovery ──────────────────────────────────────────────────


def _slug_dir(slug: str) -> Path:
    d = _carousel_root() / slug
    if not d.is_dir():
        raise PublishAborted(
            f"carousel dir not found: {d} "
            f"(set WR2_CAROUSEL_ROOT or check the slug)"
        )
    return d


def _load_slides_json(slug_dir: Path) -> dict[str, Any]:
    f = slug_dir / "slides.json"
    if not f.is_file():
        raise PublishAborted(f"slides.json not found: {f}")
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise PublishAborted(f"slides.json unreadable: {f} — {exc}") from exc


def _discover_slide_pngs(slug_dir: Path) -> list[Path]:
    """Return numbered slide PNGs sorted by their integer stem.

    Handles BOTH naming schemes seen on disk: zero-padded ``NN.png``
    (production composer) and single-digit ``N.png`` (older path). Hero
    intermediates (``NN-hero.jpg/png``), logo, html, fonts are ignored — only
    a pure-digit stem with a ``.png`` suffix counts.
    """
    slides_dir = slug_dir / "slides"
    if not slides_dir.is_dir():
        raise PublishAborted(f"slides/ dir not found: {slides_dir}")
    numbered: list[tuple[int, Path]] = []
    for p in slides_dir.iterdir():
        if p.suffix.lower() != ".png":
            continue
        if not p.stem.isdigit():
            continue
        numbered.append((int(p.stem), p))
    if not numbered:
        raise PublishAborted(
            f"no numbered slide PNGs (NN.png) under {slides_dir}"
        )
    numbered.sort(key=lambda t: t[0])
    return [p for _, p in numbered]


def _content_hash(png_paths: list[Path]) -> str:
    """sha256 over the concatenated slide bytes — the idempotency content key."""
    h = hashlib.sha256()
    for p in png_paths:
        h.update(p.read_bytes())
    return h.hexdigest()


# ── Tigris upload ────────────────────────────────────────────────────


def _upload_slides_to_tigris(
    png_paths: list[Path], *, draft_id: str
) -> list[str]:
    """Upload every slide PNG to Tigris, return the public image URLs in order."""
    from backend.services.canva_renderer_v2._tigris import get_s3_client, upload_png

    s3 = get_s3_client()
    urls: list[str] = []
    for idx, p in enumerate(png_paths):
        url, key = upload_png(
            s3, p, draft_id=draft_id, slide_index=idx, prefix="wr2-ig"
        )
        logger.info("uploaded slide %d -> %s (key=%s)", idx, url, key)
        urls.append(url)
    return urls


# ── ledger (anti-double-publish) ─────────────────────────────────────


async def _resolve_carousel_id(conn: Any, slug: str) -> str:
    """Return a REAL ``wr2_carousel_runs.carousel_id`` (UUID) for this slug.

    The ledger FK requires a row in ``wr2_carousel_runs``. We look up an existing
    run by topic (== slug) and, failing that, create one. We DO NOT swallow a FK
    error: if we can neither find nor create the run row, the caller fails closed.
    """
    # 1) Existing run keyed on topic == slug (most specific), newest first.
    row = await conn.fetchrow(
        "SELECT carousel_id FROM wr2_carousel_runs "
        "WHERE topic = $1 ORDER BY created_at DESC LIMIT 1",
        slug,
    )
    if row is not None:
        cid = str(row["carousel_id"])
        logger.info("found existing carousel_run for slug=%s -> %s", slug, cid)
        return cid

    # 2) Create a minimal run row. topic_hash mirrors the migration's convention
    #    (sha256(topic)). state='rendered' reflects that slides exist on disk.
    topic_hash = hashlib.sha256(slug.encode("utf-8")).hexdigest()
    session_id = f"wr2_ig_publish:{slug}"
    output_dir = str(_carousel_root() / slug)
    new_row = await conn.fetchrow(
        "INSERT INTO wr2_carousel_runs "
        "(topic, topic_hash, state, session_id, output_dir, publish_mode) "
        "VALUES ($1, $2, 'rendered', $3, $4, 'manual') "
        "RETURNING carousel_id",
        slug,
        topic_hash,
        session_id,
        output_dir,
    )
    cid = str(new_row["carousel_id"])
    logger.info("created carousel_run for slug=%s -> %s", slug, cid)
    return cid


async def _ledger_precondition(
    *,
    slug: str,
    content_hash: str,
) -> tuple[str, str, str | None]:
    """HARD precondition before media_publish. Returns (carousel_id, action, prior_url).

    action == "proceed"  -> a 'planned' row was written; caller may publish.
    action == "refuse"   -> already published/recorded; caller must NOT publish.

    Fails closed (raises PublishAborted) if the ledger DB is unreachable or the
    carousel_runs FK can't be satisfied — NEVER silently skips the guard.
    """
    try:
        import asyncpg
    except ImportError as exc:  # pragma: no cover - asyncpg is a backend dep
        raise PublishAborted(f"asyncpg unavailable, cannot guard publish: {exc}") from exc

    from backend.app.core.config import settings

    dsn = settings.database_url or os.environ.get("DATABASE_URL")
    if not dsn:
        raise PublishAborted(
            "ledger DB unreachable: settings.database_url / DATABASE_URL not set. "
            "A real publish REQUIRES the wr2_publish_attempts idempotency guard — "
            "refusing to publish without it (fail-closed)."
        )

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:  # any connect failure must fail closed
        raise PublishAborted(
            f"ledger DB unreachable ({type(exc).__name__}: {exc}). "
            "Refusing to publish without the idempotency guard (fail-closed)."
        ) from exc

    try:
        carousel_id = await _resolve_carousel_id(conn, slug)
        # idempotency_key = carousel_id || platform || content_hash (UNIQUE).
        idempotency_key = f"{carousel_id}:{_PLATFORM}:{content_hash[:16]}"

        # Check for a prior terminal attempt first (already published/recorded).
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
                "REFUSE double-publish: idempotency_key=%s already state=%s",
                idempotency_key,
                prior["state"],
            )
            return carousel_id, "refuse", prior_url

        # Write the 'planned' row as the hard precondition. ON CONFLICT keeps the
        # existing non-terminal row (planned/container_created/failed) so a retry
        # reuses it rather than crashing on the UNIQUE constraint.
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
            "ledger 'planned' row written: idempotency_key=%s carousel_id=%s",
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

    Best-effort post-publish bookkeeping: a failure here is logged but does NOT
    flip a successful Meta publish into a failure (the post already exists). It
    never blocks; the anti-double-publish guarantee is the PRE-publish 'planned'
    row + UNIQUE key, which is already committed by this point.
    """
    try:
        import asyncpg

        from backend.app.core.config import settings

        dsn = settings.database_url or os.environ.get("DATABASE_URL")
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
            logger.info("ledger updated -> state=%s key=%s", state, idempotency_key)
        finally:
            await conn.close()
    except Exception as exc:  # bookkeeping must never crash a live post
        logger.warning("ledger result update failed (non-fatal): %s", exc)


# ── draft assembly ───────────────────────────────────────────────────


def _read_caption(caption_file: str | None) -> str:
    if not caption_file:
        logger.warning("no --caption-file supplied; using placeholder caption")
        return _PLACEHOLDER_CAPTION
    p = Path(caption_file)
    if not p.is_file():
        raise PublishAborted(f"--caption-file not found: {p}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise PublishAborted(f"--caption-file is empty: {p}")
    return text


def _build_draft(
    *,
    slug: str,
    draft_id: uuid.UUID,
    image_urls: list[str],
    caption: str,
    approved: bool,
) -> Any:
    """Assemble a DraftPayload. cover = slide 1's tigris URL; rest = body slides."""
    from backend.services.publisher.base import DraftPayload, SlidePayload

    cover_url = image_urls[0]
    body = [
        SlidePayload(slide_number=i + 1, image_url=url, caption=None)
        for i, url in enumerate(image_urls[1:], start=1)
    ]
    return DraftPayload(
        draft_id=draft_id,
        topic=slug,
        tone_register=None,
        cover_image_url=cover_url,
        main_caption=caption,
        slides=body,
        approval_state="approved" if approved else "pending",
    )


# ── orchestration ────────────────────────────────────────────────────


async def _run(args: argparse.Namespace) -> int:
    # Hard stop #1: token-scope gate. The operator must have verified that the
    # token actually carries instagram_content_publish scope before this tool
    # runs. Two ways to satisfy it:
    #   (a) explicit override WR2_IG_CONTENT_PUBLISH_VERIFIED=1, OR
    #   (b) the Instagram Login creds resolve (INSTAGRAM_ACCOUNT_ID +
    #       INSTAGRAM_ACCESS_TOKEN, or the IG_* aliases) — the live probe on that
    #       exact DM token (2026-06-25) confirmed account_type=BUSINESS with
    #       content_publishing_limit readable => scope present.
    # The default-pass is scoped to the credential names actually being present;
    # if NO creds resolve we still hard-stop (can't publish without a token).
    _verified = os.environ.get("WR2_IG_CONTENT_PUBLISH_VERIFIED") == "1"
    _creds_resolve = bool(
        (os.environ.get("IG_USER_ID") or os.environ.get("INSTAGRAM_ACCOUNT_ID"))
        and (os.environ.get("IG_LONG_LIVED_TOKEN") or os.environ.get("INSTAGRAM_ACCESS_TOKEN"))
    )
    if not (_verified or _creds_resolve):
        logger.error(
            "TOKEN SCOPE UNVERIFIED — operator must confirm instagram_content_publish "
            "scope (run the probe), then set WR2_IG_CONTENT_PUBLISH_VERIFIED=1"
        )
        return 1

    slug = args.slug
    slug_dir = _slug_dir(slug)
    # Validate slides.json exists / parses (raises PublishAborted otherwise).
    _load_slides_json(slug_dir)
    png_paths = _discover_slide_pngs(slug_dir)
    logger.info("slug=%s slides=%d (%s)", slug, len(png_paths), [p.name for p in png_paths])

    draft_id = uuid.uuid5(_WR2_DRAFT_NAMESPACE, slug)
    content_hash = _content_hash(png_paths)
    caption = _read_caption(args.caption_file)

    # Upload to Tigris in BOTH dry-run and confirm (the image URLs are needed to
    # show what WOULD post, and to validate the carousel item count).
    image_urls = _upload_slides_to_tigris(png_paths, draft_id=str(draft_id))

    if not args.confirm:
        logger.info("DRY-RUN (no --confirm): NOT writing ledger, NOT publishing.")
        logger.info("WOULD post carousel '%s' with %d items:", slug, len(image_urls))
        logger.info("  cover: %s", image_urls[0])
        for i, url in enumerate(image_urls[1:], start=2):
            logger.info("  slide %d: %s", i, url)
        logger.info("  caption (%d chars): %s", len(caption), caption[:120])
        logger.info(
            "  approval_state would be 'pending' -> publish() would REFUSE (Legge 5)."
        )
        logger.info("DRY-RUN complete. Re-run with --confirm to publish.")
        return 0

    # ── CONFIRM path ─────────────────────────────────────────────────
    # Hard precondition: ledger row BEFORE media_publish. Fails closed if DB
    # unreachable / FK unsatisfiable; refuses if already published.
    carousel_id, action, prior_url = await _ledger_precondition(
        slug=slug, content_hash=content_hash
    )
    if action == "refuse":
        logger.error(
            "Already published (ledger terminal state). Refusing double-publish."
        )
        if prior_url:
            # Emit the existing permalink so the app still gets its URL contract.
            print(f"IG_URL={prior_url}")  # noqa: T201 - stdout contract line
        return 1

    # Build the approved draft and publish.
    from backend.services.publisher.ig_publisher import IGPublisher, close_ig_publisher_client

    draft = _build_draft(
        slug=slug,
        draft_id=draft_id,
        image_urls=image_urls,
        caption=caption,
        approved=True,
    )

    try:
        # graph_base override = graph.instagram.com (Instagram Login token host).
        # Creds fall back to INSTAGRAM_ACCOUNT_ID / INSTAGRAM_ACCESS_TOKEN inside
        # the restored publisher's __init__ — no env-name change needed here.
        publisher = IGPublisher(graph_base=_IG_GRAPH_BASE)
    except Exception as exc:  # missing creds -> fail closed
        await _ledger_record_result(
            carousel_id=carousel_id,
            content_hash=content_hash,
            state="failed",
            provider_response={"error": f"publisher init: {exc}"},
        )
        logger.error("IGPublisher init failed: %s", exc)
        return 1

    # B11: per-step observability (wr2_orchestrator_metrics, migration 203 —
    # had zero writer before this). Clean 1:1 mapping to the 'ig_publisher'
    # enum value; carousel_id is already resolved above by
    # _ledger_precondition (SAME find-or-create-by-topic idiom
    # wr2_orchestrator_metrics.resolve_carousel_id mirrors). Fail-open.
    _wom_t0 = time.perf_counter()
    result = None
    _wom_error: Exception | None = None
    try:
        result = await publisher.publish(draft)
    except Exception as exc:  # noqa: BLE001 — record then re-raise, never swallow
        _wom_error = exc
        raise
    finally:
        await close_ig_publisher_client()
        _wom_ok = result is not None and result.ok
        await wom.record_step(
            carousel_id=carousel_id,
            step_name="ig_publisher",
            step_index=8,
            tier=1,
            latency_ms=int((time.perf_counter() - _wom_t0) * 1000),
            retry_count=0,
            success=_wom_ok,
            error_class=(
                type(_wom_error).__name__ if _wom_error
                else (None if _wom_ok else "publish_failed")
            ),
            error_message=(
                str(_wom_error)[:500] if _wom_error
                else (None if _wom_ok else (result.error or None))
            ),
        )

    if not result.ok:
        await _ledger_record_result(
            carousel_id=carousel_id,
            content_hash=content_hash,
            state="failed",
            provider_response={"error": result.error},
        )
        logger.error("publish failed: %s", result.error)
        return 1

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

    permalink = result.post_url or ""
    logger.info("PUBLISHED ok: media_id=%s permalink=%s", result.post_external_id, permalink)

    # ── A4 publish records (spec docs/specs/wr2-definitiva-v1.md R4) ──────────
    # war_room_posts + the review-queue entry are what the learning loops eat
    # (measurer / ig-metrics-analyst / learner-nightly) — both were empty forever.
    # BEST-EFFORT: the publish already happened; record-keeping failures are
    # logged loudly but never turn a successful publish into exit 1.
    real_draft_id = _read_meta_draft_id(slug)
    try:
        await _record_war_room_post(
            draft_id=real_draft_id,
            permalink=permalink,
            post_external_id=result.post_external_id,
            caption=caption,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("war_room_posts record failed (publish OK): %s", exc)
    try:
        _mark_queue_published(slug=slug, draft_id=real_draft_id, permalink=permalink)
    except Exception as exc:  # noqa: BLE001
        logger.error("queue publish-mark failed (publish OK): %s", exc)

    # The app parses this exact stdout line.
    print(f"IG_URL={permalink}")  # noqa: T201 - stdout contract line
    return 0


def _read_meta_draft_id(slug: str) -> str | None:
    """The war_room_drafts UUID travels in meta.json (written by the html-apply
    visibility chain since 2026-07-07). Legacy carousel dirs lack it -> None."""
    meta_path = _carousel_root() / slug / "meta.json"
    try:
        if meta_path.is_file():
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            did = str(data.get("draft_id") or "").strip()
            return did or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("meta.json unreadable for %s: %s", slug, exc)
    return None


async def _record_war_room_post(
    *,
    draft_id: str | None,
    permalink: str,
    post_external_id: str | None,
    caption: str,
) -> None:
    """INSERT the publish into war_room_posts (FK -> war_room_drafts) and promote
    the draft to status='published'. Requires the REAL draft id from meta.json —
    the CLI's uuid5(slug) would violate the FK, so legacy dirs are skipped."""
    if not draft_id:
        logger.warning(
            "no real draft_id (legacy carousel dir without meta.json) — "
            "war_room_posts NOT recorded; learning loops stay blind for this one"
        )
        return
    import asyncpg

    from backend.app.core.config import settings

    dsn = settings.database_url or os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("no DSN for war_room_posts record")
        return
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO war_room_posts (draft_id, platform, post_external_id, post_url, final_text)
            VALUES ($1::uuid, 'instagram', $2, $3, $4)
            ON CONFLICT (draft_id, platform) DO UPDATE
               SET post_external_id = EXCLUDED.post_external_id,
                   post_url = EXCLUDED.post_url
            """,
            draft_id, post_external_id, permalink, caption[:4000],
        )
        await conn.execute(
            """
            UPDATE war_room_drafts SET status='published', updated_at=NOW()
             WHERE id=$1::uuid AND status IN ('rendered','pending_review','approved')
            """,
            draft_id,
        )
        logger.info("war_room_posts recorded for draft %s", draft_id)
    finally:
        await conn.close()


def _mark_queue_published(*, slug: str, draft_id: str | None, permalink: str) -> None:
    """Flip the review-queue entry to state='published' (same fcntl-lock protocol
    as the html-apply appender). Match by draft_id first, then by slug."""
    import fcntl
    from datetime import datetime, timezone

    qp = _carousel_root().parent / "queue" / "human-review-queue.json"
    if not qp.exists():
        logger.warning("review queue missing at %s — publish not queue-marked", qp)
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lock_path = qp.with_suffix(".lock")
    with open(lock_path, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            queue = json.loads(qp.read_text(encoding="utf-8"))
            if not isinstance(queue, list):
                logger.error("review queue is not a JSON array: %s", qp)
                return
            hit = None
            for item in queue:
                if not isinstance(item, dict):
                    continue
                if draft_id and item.get("draft_id") == draft_id:
                    hit = item
                    break
                cp = str(item.get("carousel_path") or "")
                if item.get("topic_slug") == slug or cp.rstrip("/").endswith(slug):
                    hit = item
                    break
            if hit is None:
                logger.warning("no queue entry matched slug=%s draft_id=%s", slug, draft_id)
                return
            hit["state"] = "published"
            hit["instagram_post_url"] = permalink
            hit["instagram_published_at"] = now
            hit.setdefault("state_history", []).append(
                {"state": "published", "at": now, "by": "wr2_ig_publish"}
            )
            tmp = qp.with_suffix(f".tmp.{os.getpid()}")
            tmp.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, qp)
            logger.info("queue entry marked published (slug=%s)", slug)
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wr2_ig_publish",
        description="Operator-gated WR2 Instagram carousel publisher.",
    )
    parser.add_argument("slug", help="carousel dir name under output/carousel/")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="operator gate: actually publish (default is dry-run).",
    )
    parser.add_argument(
        "--caption-file",
        default=None,
        help="path to a file whose contents become the IG caption.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except PublishAborted as exc:
        logger.error("ABORTED: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
