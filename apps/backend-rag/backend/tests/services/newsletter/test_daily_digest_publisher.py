"""Tests for NewsletterPublisher.send_daily_digest / render_daily_html."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services.newsletter.builder import DailyDigestContent, DailyDigestItem
from backend.services.newsletter.publisher import (
    DEFAULT_DAILY_LOGO_URL,
    LOCKED_SENDER_EMAIL,
    LOCKED_SENDER_NAME,
    NewsletterPublisher,
)


def _item(
    title: str = "Indonesia Cuts Visa-Free Entry by 87%",
    body: str = "Indonesia cut visa-free entry to tighten foreign screening.",
    kind: str = "intel_item",
    domain_tag: str = "VISA",
    source_label: str = "en.tempo.co",
    source_url: str | None = "https://en.tempo.co/read/123",
) -> DailyDigestItem:
    return DailyDigestItem(
        kind=kind,
        title=title,
        body=body,
        source_label=source_label,
        source_url=source_url,
        source_date=datetime(2026, 7, 14, 6, 0, tzinfo=timezone.utc),
        domain_tag=domain_tag,
    )


def _content(
    *,
    items: list[DailyDigestItem] | None = None,
    scarce: bool = False,
) -> DailyDigestContent:
    return DailyDigestContent(
        day=date(2026, 7, 14),
        generated_at=datetime.now(timezone.utc),
        items=items if items is not None else [_item()],
        scarce=scarce,
    )


def _ok_response(status: int = 202) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = "ok"
    return r


# ── Skip paths ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_digest_skipped():
    pub = NewsletterPublisher()
    result = await pub.send_daily_digest(_content(items=[]), ["zero@balizero.com"])
    assert result.skipped
    assert result.skip_reason == "empty_digest"


@pytest.mark.asyncio
async def test_no_recipients_skipped():
    pub = NewsletterPublisher()
    result = await pub.send_daily_digest(_content(), [])
    assert result.skipped
    assert result.skip_reason == "no_recipients"


# ── Happy path ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_recipient_happy_path():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client, api_key="test-key")

    result = await pub.send_daily_digest(_content(), ["zero@balizero.com"])
    assert result.recipients_attempted == 1
    assert result.recipients_sent == 1

    call = client.post.call_args
    payload = call.kwargs["json"]
    assert payload["from"] == LOCKED_SENDER_EMAIL
    assert payload["from_name"] == LOCKED_SENDER_NAME
    assert payload["to"] == "zero@balizero.com"
    assert "Bali Zero Daily" in payload["subject"]


@pytest.mark.asyncio
async def test_subject_prefix_applied_to_actual_sent_email():
    """Regression: prefix must reach the POSTed subject, not just result.subject."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)

    result = await pub.send_daily_digest(
        _content(), ["zero@balizero.com"], subject_prefix="[TEST] "
    )
    assert result.subject.startswith("[TEST] ")
    payload = client.post.call_args.kwargs["json"]
    assert payload["subject"].startswith("[TEST] ")


# ── Rendering ──────────────────────────────────────────────


def test_render_includes_logo_and_items():
    pub = NewsletterPublisher()
    html = pub.render_daily_html(
        _content(items=[_item(title="Item A"), _item(title="Item B", domain_tag="TAX")])
    )
    assert DEFAULT_DAILY_LOGO_URL in html
    assert "Item A" in html
    assert "Item B" in html
    assert "TAX" in html
    assert "<style" not in html  # inline-CSS-only per email-template.md


def test_render_escapes_html_in_item_title():
    pub = NewsletterPublisher()
    html = pub.render_daily_html(_content(items=[_item(title="<script>alert(1)</script>")]))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_includes_source_url_link():
    pub = NewsletterPublisher()
    html = pub.render_daily_html(_content())
    assert "https://en.tempo.co/read/123" in html


def test_render_scarce_note_present_when_scarce():
    pub = NewsletterPublisher()
    html = pub.render_daily_html(_content(scarce=True))
    assert "pochi segnali" in html


def test_render_scarce_note_absent_when_not_scarce():
    pub = NewsletterPublisher()
    html = pub.render_daily_html(_content(scarce=False))
    assert "pochi segnali" not in html


def test_thesis_item_has_no_source_url_link_rendered():
    pub = NewsletterPublisher()
    thesis_item = _item(kind="thesis", source_label="Bali Zero Connector", source_url=None)
    html = pub.render_daily_html(_content(items=[thesis_item]))
    assert "Bali Zero Connector" in html


# ── Subject ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subject_includes_date_and_top_item_title():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)
    result = await pub.send_daily_digest(
        _content(items=[_item(title="Big regulation change")]), ["x@y.com"]
    )
    assert "2026-07-14" in result.subject
    assert "Big regulation change" in result.subject
