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
