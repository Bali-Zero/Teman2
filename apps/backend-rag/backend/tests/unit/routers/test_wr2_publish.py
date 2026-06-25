"""Tests for the WR2 server-side IG publish endpoint (Legge 5 operator gate).

Covers the four load-bearing guarantees of POST /api/war-room/publish-ig:

  1. confirm=False  -> IGPublisher.publish() is NEVER called (dry validation).
  2. confirm=True   -> publish() IS called with approval_state == "approved"
                       (the Meta HTTP is mocked; we assert the draft passed the
                       publisher's internal approval gate).
  3. admin gate     -> a non-admin user gets 403.
  4. already-published -> 409 with the prior permalink (ledger mocked to refuse).

The publisher's Meta HTTP is never hit: we monkeypatch IGPublisher.publish /
.validate. The ledger DB is never hit: we monkeypatch the two ledger helpers in
the router module (_ledger_precondition / _ledger_record_result).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user
from backend.app.routers import wr2_publish
from backend.services.publisher.base import PublishResult, ValidationResult
from backend.services.war_room.models import Platform

ADMIN_USER = {"email": "zero@balizero.com", "role": "founder"}
NON_ADMIN_USER = {"email": "viewer@example.com", "role": "team"}

IMAGE_URLS = [
    "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-ig/cover.png",
    "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-ig/02.png",
    "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-ig/03.png",
]
CAPTION = "Bali Zero regulatory update — KBLI 2025 conversion clock. See balizero.com."


def _app(user: dict[str, Any]) -> FastAPI:
    app = FastAPI()
    app.include_router(wr2_publish.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _body(confirm: bool) -> dict[str, Any]:
    return {
        "slug": "kbli-2025-conversion",
        "image_urls": IMAGE_URLS,
        "caption": CAPTION,
        "alt_texts": ["cover alt", "slide 2 alt", "slide 3 alt"],
        "confirm": confirm,
    }


# ── 1. confirm=False => publish() NEVER called ─────────────────────────────────


def test_dry_run_never_calls_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    """confirm=False: a dry validation runs, publish() is never invoked, and the
    ledger is never touched (no 'planned' / terminal row written)."""
    publish_spy = AsyncMock(
        side_effect=AssertionError("publish() must NOT be called on a dry run")
    )
    validate_spy = AsyncMock(
        return_value=ValidationResult(ok=True, platform=Platform.INSTAGRAM, issues=[])
    )
    ledger_precondition_spy = AsyncMock(
        side_effect=AssertionError("ledger precondition must NOT run on a dry run")
    )

    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.IGPublisher.publish", publish_spy
    )
    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.IGPublisher.validate", validate_spy
    )
    # Make IGPublisher() constructible without real creds.
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "24126743553672359")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "dummy-token-not-used")
    monkeypatch.setattr(wr2_publish, "_ledger_precondition", ledger_precondition_spy)

    app = _app(ADMIN_USER)
    try:
        resp = TestClient(app).post("/api/war-room/publish-ig", json=_body(confirm=False))
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["dry_run"] is True
    assert data["would_publish"]["approval_state"] == "pending"
    assert data["would_publish"]["slide_count"] == 3
    assert data["validation"]["ok"] is True

    publish_spy.assert_not_called()  # THE guarantee: no publish on a dry run.
    validate_spy.assert_awaited_once()  # but we DID validate.
    ledger_precondition_spy.assert_not_called()  # and no ledger write.


# ── 2. confirm=True => publish() called with approval_state == "approved" ──────


def test_confirm_calls_publish_with_approved_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    """confirm=True: ledger precondition proceeds, publish() IS called, and the
    draft handed to publish() has approval_state == 'approved' (the flag the
    real publisher checks at ig_publisher.py:239)."""
    permalink = "https://www.instagram.com/p/ABC123/"
    captured: dict[str, Any] = {}

    async def fake_publish(self: Any, draft: Any) -> PublishResult:  # noqa: ANN401
        # Assert the gate the real publisher would check actually passed.
        assert draft.approval_state == "approved"
        captured["approval_state"] = draft.approval_state
        captured["cover"] = draft.cover_image_url
        captured["slides"] = len(draft.slides)
        return PublishResult(
            ok=True,
            platform=Platform.INSTAGRAM,
            draft_id=draft.draft_id,
            post_external_id="17900000000000000",
            post_url=permalink,
        )

    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.IGPublisher.publish", fake_publish
    )
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "24126743553672359")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "dummy-token-not-used")

    carousel_id = str(uuid4())
    monkeypatch.setattr(
        wr2_publish,
        "_ledger_precondition",
        AsyncMock(return_value=(carousel_id, "proceed", None)),
    )
    record_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(wr2_publish, "_ledger_record_result", record_spy)
    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.close_ig_publisher_client",
        AsyncMock(return_value=None),
    )

    app = _app(ADMIN_USER)
    try:
        resp = TestClient(app).post("/api/war-room/publish-ig", json=_body(confirm=True))
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["dry_run"] is False
    assert data["permalink"] == permalink
    assert data["post_id"] == "17900000000000000"

    assert captured["approval_state"] == "approved"  # gate passed
    assert captured["cover"] == IMAGE_URLS[0]
    assert captured["slides"] == 2  # 3 urls => cover + 2 body slides
    # ledger written to terminal 'published'
    assert record_spy.await_args.kwargs["state"] == "published"


# ── 3. admin gate => non-admin user is 403 ─────────────────────────────────────


def test_non_admin_is_forbidden() -> None:
    """A non-admin user is blocked by the router-level _require_admin dependency."""
    app = _app(NON_ADMIN_USER)
    try:
        resp = TestClient(app).post("/api/war-room/publish-ig", json=_body(confirm=False))
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert resp.json() == {"detail": "Admin access required"}


# ── 4. already-published slug => 409 with existing permalink ───────────────────


def test_already_published_returns_409_with_permalink(monkeypatch: pytest.MonkeyPatch) -> None:
    """confirm=True but the ledger says this carousel+content is already
    published => 409, the prior permalink is returned, publish() is never run."""
    prior_permalink = "https://www.instagram.com/p/PRIOR99/"
    carousel_id = str(uuid4())

    monkeypatch.setattr(
        wr2_publish,
        "_ledger_precondition",
        AsyncMock(return_value=(carousel_id, "refuse", prior_permalink)),
    )
    publish_spy = AsyncMock(
        side_effect=AssertionError("publish() must NOT run when ledger refuses")
    )
    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.IGPublisher.publish", publish_spy
    )
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "24126743553672359")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "dummy-token-not-used")

    app = _app(ADMIN_USER)
    try:
        resp = TestClient(app).post("/api/war-room/publish-ig", json=_body(confirm=True))
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "already_published"
    assert detail["permalink"] == prior_permalink
    publish_spy.assert_not_called()


# ── Bonus: publisher approval-gate refusal surfaces as a clear 4xx ─────────────


def test_publisher_gate_refusal_surfaces_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """If publish() returns ok=False (e.g. the real publisher's approval gate or
    a validation failure), the endpoint returns 422, not a 500, and records the
    ledger as 'failed'."""

    async def refusing_publish(self: Any, draft: Any) -> PublishResult:  # noqa: ANN401
        return PublishResult(
            ok=False,
            platform=Platform.INSTAGRAM,
            draft_id=draft.draft_id,
            error="approval_state='pending' (required: 'approved').",
        )

    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.IGPublisher.publish", refusing_publish
    )
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "24126743553672359")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "dummy-token-not-used")

    carousel_id = str(uuid4())
    monkeypatch.setattr(
        wr2_publish,
        "_ledger_precondition",
        AsyncMock(return_value=(carousel_id, "proceed", None)),
    )
    record_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(wr2_publish, "_ledger_record_result", record_spy)
    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.close_ig_publisher_client",
        AsyncMock(return_value=None),
    )

    app = _app(ADMIN_USER)
    try:
        resp = TestClient(app).post("/api/war-room/publish-ig", json=_body(confirm=True))
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "publish_failed"
    assert record_spy.await_args.kwargs["state"] == "failed"


# ── Content-hash determinism (idempotency key stability) ───────────────────────


def test_content_hash_is_stable_and_order_sensitive() -> None:
    h1 = wr2_publish._content_hash(IMAGE_URLS, CAPTION)
    h2 = wr2_publish._content_hash(IMAGE_URLS, CAPTION)
    h3 = wr2_publish._content_hash(list(reversed(IMAGE_URLS)), CAPTION)
    h4 = wr2_publish._content_hash(IMAGE_URLS, CAPTION + " edited")
    assert h1 == h2  # deterministic
    assert h1 != h3  # order-sensitive (slide order matters)
    assert h1 != h4  # caption-sensitive

    # MagicMock import kept for parity with other router tests' tooling surface.
    assert isinstance(MagicMock(), MagicMock)


# ── /upload-slide : PNG bytes -> public Tigris URL ─────────────────────────────

# A minimal valid 1x1 PNG (magic bytes + IHDR + IEND), enough to pass the magic
# check. The real bytes never reach Tigris in tests — upload_png is mocked.
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_upload_slide_returns_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """A PNG is uploaded to Tigris and the public URL is returned. upload_png is
    mocked so no real S3 call happens; we assert the bytes + key args flow through."""
    captured: dict[str, Any] = {}

    def fake_upload_png(s3: Any, png: Any, *, draft_id: str, slide_index: int, **kw: Any):  # noqa: ANN401
        captured["bytes_len"] = len(png)
        captured["draft_id"] = draft_id
        captured["slide_index"] = slide_index
        url = f"https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-ig/{draft_id}/{slide_index:02d}.png"
        return url, f"wr2-ig/{draft_id}/{slide_index:02d}.png"

    monkeypatch.setattr(
        "backend.services.canva_renderer_v2._tigris.get_s3_client",
        lambda: MagicMock(),
    )
    monkeypatch.setattr(
        "backend.services.canva_renderer_v2._tigris.upload_png", fake_upload_png
    )

    app = _app(ADMIN_USER)
    try:
        resp = TestClient(app).post(
            "/api/war-room/upload-slide",
            files={"file": ("01.png", _PNG_1X1, "image/png")},
            data={"draft_id": "my-carousel", "slide_index": "0"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["url"].endswith("/wr2-ig/my-carousel/00.png")
    assert data["slide_index"] == 0
    assert captured["bytes_len"] == len(_PNG_1X1)
    assert captured["draft_id"] == "my-carousel"


def test_upload_slide_non_admin_is_forbidden() -> None:
    app = _app(NON_ADMIN_USER)
    try:
        resp = TestClient(app).post(
            "/api/war-room/upload-slide",
            files={"file": ("01.png", _PNG_1X1, "image/png")},
            data={"draft_id": "my-carousel", "slide_index": "0"},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_upload_slide_rejects_non_png() -> None:
    """A body without the PNG magic bytes is rejected 400 before touching Tigris."""
    app = _app(ADMIN_USER)
    try:
        resp = TestClient(app).post(
            "/api/war-room/upload-slide",
            files={"file": ("evil.png", b"GIF89a not a png", "image/png")},
            data={"draft_id": "my-carousel", "slide_index": "0"},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400
    assert "not a PNG" in resp.json()["detail"]


def test_upload_slide_tigris_failure_is_502(monkeypatch: pytest.MonkeyPatch) -> None:
    """A TigrisError surfaces as 502 (upstream storage failure), not a 500."""
    from backend.services.canva_renderer_v2._tigris import TigrisError

    def boom(*a: Any, **k: Any) -> None:  # noqa: ANN401
        raise TigrisError("simulated S3 outage")

    monkeypatch.setattr(
        "backend.services.canva_renderer_v2._tigris.get_s3_client",
        lambda: MagicMock(),
    )
    monkeypatch.setattr(
        "backend.services.canva_renderer_v2._tigris.upload_png", boom
    )

    app = _app(ADMIN_USER)
    try:
        resp = TestClient(app).post(
            "/api/war-room/upload-slide",
            files={"file": ("01.png", _PNG_1X1, "image/png")},
            data={"draft_id": "my-carousel", "slide_index": "0"},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 502
    assert "Tigris upload failed" in resp.json()["detail"]
