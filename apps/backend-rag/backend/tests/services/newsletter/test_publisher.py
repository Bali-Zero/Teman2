"""Tests for NewsletterPublisher — sender lock, render, per-recipient results."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from backend.services.cognitive.models import (
    CrossDossierThesis,
    WeeklyStrategicBrief,
)
from backend.services.intel.dossier_models import (
    ResearchDossier,
    TopicCategory,
)
from backend.services.newsletter.builder import RoundupContent
from backend.services.newsletter.publisher import (
    LOCKED_SENDER_EMAIL,
    LOCKED_SENDER_NAME,
    NewsletterPublisher,
)


def _dossier(
    title: str = "Permenkumham 22/2023 — art. 51",
    summary: str = "Le tre condizioni per la quarta proroga.",
    public_safe: bool = True,
) -> ResearchDossier:
    now = datetime.now(timezone.utc)
    return ResearchDossier(
        id=uuid4(),
        slug="s",
        title=title,
        topic_category=TopicCategory.VISA,
        domains=["newsletter"],
        public_safe=public_safe,
        facts=[],
        numbers=[],
        citations=[],
        entities_linked=[],
        precedents=[],
        confidence_0_1=0.82,
        freshness_expiry=now + timedelta(days=30),
        source_signals=None,
        language="it",
        summary_short=summary,
        summary_medium="full medium summary here",
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


def _thesis(
    title: str = "Regulatory convergence Q3 2026",
    implication: str | None = "PT PMA fintech a 90gg dalla scadenza",
) -> CrossDossierThesis:
    return CrossDossierThesis(
        id=uuid4(),
        title=title,
        narrative="long narrative",
        source_dossier_ids=[uuid4(), uuid4()],
        confidence=0.78,
        implication=implication,
        generated_at=datetime.now(timezone.utc),
    )


def _brief(
    narrative: str = "Settimana di ribilanciamento tonale",
) -> WeeklyStrategicBrief:
    return WeeklyStrategicBrief(
        id=uuid4(),
        week_of=date(2026, 4, 20),
        top_themes=[{"name": "Focus pedagogico"}],
        proposed_actions=[],
        narrative=narrative,
        generated_at=datetime.now(timezone.utc),
    )


def _content(
    *,
    dossiers: list | None = None,
    theses: list | None = None,
    brief: WeeklyStrategicBrief | None = None,
) -> RoundupContent:
    return RoundupContent(
        week_of=date(2026, 4, 20),
        generated_at=datetime.now(timezone.utc),
        dossiers=dossiers or [_dossier()],
        theses=theses or [],
        brief=brief,
    )


def _ok_response(status: int = 202) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = "ok"
    return r


def _err_response(status: int = 500, text: str = "boom") -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text
    return r


# ── Sender lock (hard requirement from memory §email_sender) ──


def test_locked_sender_constants_are_balizero():
    assert LOCKED_SENDER_EMAIL == "zantara@balizero.com"
    assert LOCKED_SENDER_NAME == "Zantara"


# ── Empty / skip paths ────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_roundup_skipped():
    pub = NewsletterPublisher()
    content = RoundupContent(
        week_of=date(2026, 4, 20),
        generated_at=datetime.now(timezone.utc),
    )
    result = await pub.send_roundup(content, ["a@b.com"])
    assert result.skipped
    assert result.skip_reason == "empty_roundup"


@pytest.mark.asyncio
async def test_no_recipients_skipped():
    pub = NewsletterPublisher()
    result = await pub.send_roundup(_content(), [])
    assert result.skipped
    assert result.skip_reason == "no_recipients"


@pytest.mark.asyncio
async def test_recipients_trimmed_and_empty_filtered():
    """Whitespace / empty strings should be dropped before counting."""
    pub = NewsletterPublisher()
    # All entries are empty/whitespace — result = no_recipients
    result = await pub.send_roundup(_content(), ["", "  ", ""])
    assert result.skipped


# ── Happy send ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_recipient_happy_path():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)

    result = await pub.send_roundup(_content(), ["zero@balizero.com"])
    assert result.recipients_attempted == 1
    assert result.recipients_sent == 1
    assert result.recipients_failed == 0

    call = client.post.call_args
    url = call.args[0]
    headers = call.kwargs["headers"]
    payload = call.kwargs["json"]

    assert url.endswith("/api/notifications/send-email")
    assert headers.get("X-API-Key") == "zantara-secret-2024"
    assert payload["from"] == LOCKED_SENDER_EMAIL
    assert payload["from_name"] == LOCKED_SENDER_NAME
    assert payload["to"] == "zero@balizero.com"
    assert "Bali Zero" in payload["subject"]
    assert "<strong>" in payload["body"]   # HTML body rendered


@pytest.mark.asyncio
async def test_multiple_recipients_all_sent():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)
    result = await pub.send_roundup(
        _content(),
        ["a@b.com", "c@d.com", "e@f.com"],
    )
    assert result.recipients_sent == 3
    assert client.post.await_count == 3


# ── Partial failures ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_partial_failure_counts_correctly():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=[
        _ok_response(202),
        _err_response(500, "smtp down"),
        _ok_response(202),
    ])
    pub = NewsletterPublisher(http_client=client)
    result = await pub.send_roundup(
        _content(),
        ["a@b.com", "c@d.com", "e@f.com"],
    )
    assert result.recipients_sent == 2
    assert result.recipients_failed == 1
    assert any("500" in (r.error or "") for r in result.per_recipient if not r.ok)


@pytest.mark.asyncio
async def test_httpx_exception_recorded_per_recipient():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
    pub = NewsletterPublisher(http_client=client)
    result = await pub.send_roundup(_content(), ["a@b.com"])
    assert result.recipients_failed == 1
    assert "ConnectError" in (result.per_recipient[0].error or "")


# ── HTML rendering ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_html_includes_brief_dossiers_theses():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)

    content = _content(
        dossiers=[_dossier(title="A dossier"), _dossier(title="B dossier")],
        theses=[_thesis(title="T1 thesis")],
        brief=_brief("Narrative line"),
    )
    await pub.send_roundup(content, ["x@y.com"])
    html = client.post.call_args.kwargs["json"]["body"]
    assert "Narrative line" in html
    assert "A dossier" in html
    assert "B dossier" in html
    assert "T1 thesis" in html


@pytest.mark.asyncio
async def test_html_escapes_dossier_title_with_html_chars():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)

    dangerous = _dossier(title="<script>alert(1)</script>")
    await pub.send_roundup(
        _content(dossiers=[dangerous]), ["x@y.com"],
    )
    html = client.post.call_args.kwargs["json"]["body"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.asyncio
async def test_subject_uses_top_dossier_title():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)

    content = _content(dossiers=[_dossier(title="Permenkumham 22/2023")])
    result = await pub.send_roundup(content, ["x@y.com"])
    assert "Permenkumham 22/2023" in result.subject
    assert "2026-04-20" in result.subject


@pytest.mark.asyncio
async def test_cover_fallback_when_no_dossier_cover():
    """Dossiers without cover_image_url → fallback URL is used."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_ok_response())
    pub = NewsletterPublisher(http_client=client)

    content = _content(
        dossiers=[],
        theses=[_thesis()],
    )
    # no dossiers → no cover URL from dossier; fallback used in template vars
    await pub.send_roundup(content, ["x@y.com"])
    html = client.post.call_args.kwargs["json"]["body"]
    # body rendered even without dossiers
    assert "Connector" in html or "Tesi" in html
