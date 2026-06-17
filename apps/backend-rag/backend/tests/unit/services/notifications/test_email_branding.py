"""Tests for the shared email-branding helpers, focused on the consultant
portrait added to the team signature footer.

The team photo lives in apps/mouth/public/static/team/<slug>.jpg, the SSOT
mapping is apps/mouth/src/data/team-roster.ts, and team_members.avatar mirrors
the same site-relative paths (migration 229). The signature avatar is always
best-effort: any miss degrades to the legacy text-only footer.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.notifications.email_branding import (
    TEAM_PHOTO_BASE,
    resolve_consultant_avatar,
    team_email_html,
)


def test_team_email_html_no_consultant_is_legacy_text_only() -> None:
    """Backward compatibility: without a consultant photo the footer shows no
    portrait and the signature text is unchanged."""
    html = team_email_html(title="T", intro="I", signature="Zantara CRM")
    assert "Zantara CRM" in html
    # Only the brand logo <img> is present; no team portrait.
    assert "/static/team/" not in html
    assert "Billing: asya@balizero.com" in html


def test_team_email_html_relative_photo_is_resolved_absolute() -> None:
    """A site-relative avatar path is resolved against TEAM_PHOTO_BASE so the
    portrait renders in mail clients (which never load relative paths)."""
    html = team_email_html(
        title="T",
        intro="I",
        signature="Adit",
        consultant_photo_url="/static/team/adit.jpg",
        consultant_name="Adit",
    )
    assert f"{TEAM_PHOTO_BASE}/static/team/adit.jpg" in html
    assert 'alt="Adit"' in html
    assert "border-radius:50%" in html  # rendered as a circular portrait


def test_team_email_html_absolute_photo_passthrough() -> None:
    """An already-absolute URL is used verbatim."""
    html = team_email_html(
        title="T", intro="I", consultant_photo_url="https://cdn.test/p.jpg"
    )
    assert "https://cdn.test/p.jpg" in html


def _pool_returning(row: dict | None) -> MagicMock:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


@pytest.mark.asyncio
async def test_resolve_consultant_avatar_returns_db_values() -> None:
    pool = _pool_returning({"avatar": "/static/team/adit.jpg", "full_name": "Adit"})
    photo, name = await resolve_consultant_avatar(pool, "adit@balizero.com")
    assert photo == "/static/team/adit.jpg"
    assert name == "Adit"


@pytest.mark.asyncio
async def test_resolve_consultant_avatar_none_email_degrades() -> None:
    pool = _pool_returning({"avatar": "x", "full_name": "y"})
    assert await resolve_consultant_avatar(pool, None) == (None, None)
    pool.acquire.assert_not_called()  # no DB round-trip without an email


@pytest.mark.asyncio
async def test_resolve_consultant_avatar_no_row_degrades() -> None:
    pool = _pool_returning(None)
    assert await resolve_consultant_avatar(pool, "ghost@balizero.com") == (None, None)


@pytest.mark.asyncio
async def test_resolve_consultant_avatar_db_error_degrades() -> None:
    """A DB failure must never break the email — fall back to no portrait."""
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=RuntimeError("pool down"))
    assert await resolve_consultant_avatar(pool, "adit@balizero.com") == (None, None)
