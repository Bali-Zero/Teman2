import json

import pytest

from backend.services.crm import birthday_notifier_service as birthday_module
from backend.services.crm.birthday_notifier_service import BirthdayNotifierService


def make_service() -> BirthdayNotifierService:
    service = BirthdayNotifierService.__new__(BirthdayNotifierService)
    service.db_pool = None
    service.email_service = None
    return service


def test_get_language_for_nationality_maps_known_values_and_defaults_to_english() -> None:
    service = make_service()

    assert service.get_language_for_nationality("Italian") == "it"
    assert service.get_language_for_nationality("Ukraine") == "uk"
    assert service.get_language_for_nationality("Indonesia") == "id"
    assert service.get_language_for_nationality("Unknown") == "en"
    assert service.get_language_for_nationality(None) == "en"


def test_get_personalized_note_handles_dict_json_and_invalid_payloads() -> None:
    service = make_service()
    enrichment = {
        "birthplace_enrichment": {
            "data": {
                "conversation_starters": ["Hope Bali feels like home."],
                "famous_people": ["Famous Person"],
                "local_specialties": ["local cake"],
            }
        }
    }

    note_from_dict = service.get_personalized_note(
        {"birthplace": "Milan", "custom_fields": enrichment}
    )
    note_from_json = service.get_personalized_note(
        {"birthplace": "Milan", "custom_fields": json.dumps(enrichment)}
    )

    assert "Hope Bali feels like home." in note_from_dict
    assert "home of Famous Person" in note_from_dict
    assert "local cake" in note_from_dict
    assert note_from_json == note_from_dict
    assert service.get_personalized_note({"custom_fields": "{bad json"}) == ""
    assert service.get_personalized_note({}) == ""


def test_build_email_content_uses_subject_prefix_and_fallback_note() -> None:
    service = make_service()

    subject, html = service.build_email_content({"full_name": "Ada Lovelace"}, "en")

    assert subject == "[CLIENT] Happy Birthday from Bali Zero!"
    assert "Dear Ada," in html
    assert "We value you as a client" in html


@pytest.mark.asyncio
async def test_send_birthday_email_falls_back_to_zoho_when_brevo_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "BrokenAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, *args, **kwargs) -> object:
            raise RuntimeError("brevo down")

    class FakeEmailService:
        def __init__(self) -> None:
            self.sent: list[dict[str, object]] = []

        async def send_email(self, **kwargs: object) -> None:
            self.sent.append(kwargs)

    service = make_service()
    service.email_service = FakeEmailService()
    monkeypatch.setattr(birthday_module.httpx, "AsyncClient", BrokenAsyncClient)

    result = await service.send_birthday_email(
        {"full_name": "Client Name", "email": "client@example.com", "nationality": "Italian"}
    )

    assert result is True
    assert service.email_service.sent[0]["to"] == ["client@example.com"]
    assert service.email_service.sent[0]["is_html"] is True


@pytest.mark.asyncio
async def test_run_birthday_notifications_counts_successes_and_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service()
    service.get_todays_birthdays = lambda: _async_value(
        [{"email": "a@example.com"}, {"email": "b@example.com"}]
    )
    results = iter([True, False])
    service.send_birthday_email = lambda client: _async_value(next(results))

    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(birthday_module.asyncio, "sleep", no_sleep)

    stats = await service.run_birthday_notifications()

    assert stats["birthdays_found"] == 2
    assert stats["sent"] == 1
    assert stats["failed"] == 1


@pytest.mark.asyncio
async def test_run_birthday_notifier_task_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeService:
        def __init__(self, db_pool: object) -> None:
            self.db_pool = db_pool

        async def run_birthday_notifications(self) -> dict[str, int]:
            return {"sent": 3}

    monkeypatch.setattr(birthday_module, "BirthdayNotifierService", FakeService)

    assert await birthday_module.run_birthday_notifier_task(db_pool=object()) == {"sent": 3}


async def _async_value(value: object) -> object:
    return value
