"""Pin the team-leader alert language to Indonesian (NB-E 2026-04-29).

Policy: messages directed *exclusively* at team members default to
Indonesian — the Bali Zero team is mostly Indonesian. Client-facing
flows continue to use ``NATIONALITY_LANGUAGE_MAP`` and default to
English when nationality is missing.

This test guards against accidental reverts to the old hardcoded
Italian template (which leaked Italian text to Indonesian recipients
and was the immediate trigger for this language audit).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.crm.notifiers import StalePracticeNotifier


@pytest.fixture
def practices() -> list[dict]:
    return [
        {
            "id": 42,
            "client_name": "PT Example",
            "practice_type_name": "KITAS",
            "status": "in_review",
            "days_stale": 9,
        },
    ]


@pytest.mark.asyncio
async def test_team_leader_alert_uses_indonesian_subject(practices):
    pool = MagicMock()
    notifier = StalePracticeNotifier(pool)
    sent = {}

    async def _capture(**kwargs):
        sent.update(kwargs)

    with patch(
        "backend.services.crm.notifiers.send_internal_email",
        new=AsyncMock(side_effect=_capture),
    ):
        await notifier._send_team_leader_alert(  # noqa: SLF001 — pinning private contract
            "team@balizero.com", practices,
        )

    # Subject pinned to Indonesian.
    assert sent["subject"] == "[TEAM] ⏰ Praktik tertunda — perlu pembaruan"


@pytest.mark.asyncio
async def test_team_leader_alert_body_has_no_italian_strings(practices):
    """Regression guard: verify the body contains the new Indonesian
    strings and none of the old Italian phrasing."""
    pool = MagicMock()
    notifier = StalePracticeNotifier(pool)
    sent = {}

    async def _capture(**kwargs):
        sent.update(kwargs)

    with patch(
        "backend.services.crm.notifiers.send_internal_email",
        new=AsyncMock(side_effect=_capture),
    ):
        await notifier._send_team_leader_alert(  # noqa: SLF001
            "team@balizero.com", practices,
        )

    body = sent["body"]
    # Indonesian strings present.
    assert "Halo!" in body
    assert "Beberapa praktik" in body
    assert "Terima kasih" in body
    assert "9 hari" in body
    # Italian strings absent (regression guard).
    assert "Ciao!" not in body
    assert "Alcune pratiche" not in body
    assert "Grazie mille" not in body
    assert "9 giorni" not in body
