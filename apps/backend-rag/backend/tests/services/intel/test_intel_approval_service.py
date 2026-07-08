import json
from pathlib import Path
from typing import Any

import pytest

from backend.services.intel import intel_approval_service as approval_module
from backend.services.intel.intel_approval_service import IntelApprovalService


class FakeTelegramBot:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_message(self, **kwargs: Any) -> None:
        self.messages.append(kwargs)


def _service(tmp_path: Path) -> IntelApprovalService:
    service = IntelApprovalService.__new__(IntelApprovalService)
    service.pending_intel_path = tmp_path
    service.max_key_points = 2
    return service


def test_build_approval_keyboard_uses_stable_callback_contract(tmp_path: Path) -> None:
    service = _service(tmp_path)

    keyboard = service._build_approval_keyboard("visa", "visa-123")

    assert keyboard == {
        "inline_keyboard": [
            [
                {
                    "text": "\u2705 APPROVE",
                    "callback_data": "intel:approve:visa:visa-123",
                },
                {
                    "text": "\u274c REJECT",
                    "callback_data": "intel:reject:visa:visa-123",
                },
            ],
        ],
    }


def test_build_notification_caption_prefers_enriched_content(tmp_path: Path) -> None:
    service = _service(tmp_path)

    caption = service._build_notification_caption(
        intel_type="news",
        item_id="news-123",
        item_data={
            "title": "Raw title",
            "content": "Raw content",
            "source_name": "Source",
            "source_url": "https://example.com",
            "detected_at": "2026-07-05 10:00",
        },
        enriched_data={
            "enriched_title": "Enriched title",
            "enriched_summary": "Enriched summary",
            "key_points": ["point one", "point two", "point three"],
            "seo_keywords": ["bali", "visa", "tax", "company", "property", "extra"],
        },
        team_config={"required_votes": 2, "approvers": ["a", "b", "c"]},
    )

    assert "Enriched title" in caption
    assert "Enriched summary" in caption
    assert "point one" in caption
    assert "point two" in caption
    assert "point three" not in caption
    assert "bali, visa, tax, company, property" in caption
    assert "extra" not in caption
    assert "Votazione 2/3" in caption
    assert "ID: news-123" in caption


def test_save_voting_status_persists_audit_payload(tmp_path: Path) -> None:
    service = _service(tmp_path)

    service._save_voting_status(
        item_id="visa-123",
        intel_type="visa",
        item_data={"title": "Visa update"},
        enriched_data={"enriched_title": "Visa update"},
        image_path="/tmp/cover.png",
    )

    payload = json.loads((tmp_path / "visa-123.json").read_text())
    assert payload["item_id"] == "visa-123"
    assert payload["status"] == "voting"
    assert payload["votes"] == {"approve": [], "reject": []}
    assert payload["item_data"] == {"title": "Visa update"}
    assert payload["image_path"] == "/tmp/cover.png"


@pytest.mark.asyncio
async def test_send_approval_notification_sends_to_configured_chat_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    bot = FakeTelegramBot()
    monkeypatch.setattr(approval_module, "telegram_bot", bot)
    monkeypatch.setattr(
        approval_module,
        "get_team_config",
        lambda intel_type: {"required_votes": 1, "approvers": ["ops"]},
    )
    monkeypatch.setattr(approval_module, "get_chat_ids", lambda intel_type: ["chat-1", "chat-2"])

    sent = await service.send_approval_notification(
        intel_type="visa",
        item_id="visa-123",
        item_data={
            "title": "Visa update",
            "content": "Immigration update",
            "source_url": "https://example.com",
        },
    )

    assert sent is True
    assert [message["chat_id"] for message in bot.messages] == ["chat-1", "chat-2"]
    assert all(message["parse_mode"] == "HTML" for message in bot.messages)
    assert (tmp_path / "visa-123.json").exists()


@pytest.mark.asyncio
async def test_send_approval_notification_returns_false_without_approvers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(approval_module, "get_team_config", lambda intel_type: None)

    sent = await service.send_approval_notification(
        intel_type="news",
        item_id="news-123",
        item_data={"title": "News update"},
    )

    assert sent is False
