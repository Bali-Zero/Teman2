import json

import httpx
import pytest

from backend.services.crm.birthplace_enrichment_service import BirthplaceEnrichmentService


class FakeAcquire:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def __aenter__(self) -> object:
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


class FakeConn:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *args: object) -> list[dict]:
        self.last_fetch = (query, args)
        return self.rows

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append((query, args))
        return "UPDATE 1"


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self) -> dict[str, object]:
        return self.payload


class FakeOllamaClient:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.posts: list[dict[str, object]] = []

    async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
        self.posts.append({"url": url, "json": json})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_service(conn: object | None = None) -> BirthplaceEnrichmentService:
    return BirthplaceEnrichmentService(FakePool(conn or FakeConn()))


@pytest.mark.asyncio
async def test_get_clients_needing_enrichment_fetches_limited_rows() -> None:
    conn = FakeConn(rows=[{"id": 1, "birthplace": "Rome"}])
    service = make_service(conn)

    rows = await service.get_clients_needing_enrichment(limit=3)

    assert rows == [{"id": 1, "birthplace": "Rome"}]
    assert conn.last_fetch[1] == (3,)


def test_build_enrichment_prompt_includes_place_nationality_and_json_contract() -> None:
    service = make_service()

    prompt = service.build_enrichment_prompt("Kyiv", "Ukrainian")

    assert "Place: Kyiv" in prompt
    assert "Nationality context: Ukrainian" in prompt
    assert "conversation_starters" in prompt
    assert "Return ONLY the JSON object" in prompt


def test_parse_enrichment_response_extracts_first_json_object() -> None:
    service = make_service()

    parsed = service.parse_enrichment_response(
        'prefix {"famous_people": ["Name"], "conversation_starters": ["Ask about home"]} suffix'
    )

    assert parsed == {
        "famous_people": ["Name"],
        "conversation_starters": ["Ask about home"],
    }
    assert service.parse_enrichment_response("not json") is None


@pytest.mark.asyncio
async def test_call_ollama_returns_response_text_for_successful_generation() -> None:
    fake_client = FakeOllamaClient(FakeResponse(200, {"response": "done"}))
    service = make_service()
    service._get_client = lambda timeout: fake_client

    result = await service.call_ollama("prompt")

    assert result == "done"
    request = fake_client.posts[0]["json"]
    assert request["stream"] is False
    assert request["prompt"] == "prompt"


@pytest.mark.asyncio
async def test_call_ollama_returns_none_for_http_errors_and_non_200() -> None:
    service = make_service()
    service._get_client = lambda timeout: FakeOllamaClient(FakeResponse(500, {}))

    assert await service.call_ollama("prompt") is None

    service._get_client = lambda timeout: FakeOllamaClient(httpx.ConnectError("offline"))

    assert await service.call_ollama("prompt") is None


@pytest.mark.asyncio
async def test_enrich_client_persists_enrichment_data() -> None:
    conn = FakeConn()
    service = make_service(conn)
    service.call_ollama = lambda prompt: _async_value(
        '{"conversation_starters": ["Tell me about Rome"], "famous_people": ["Fellini"]}'
    )

    success = await service.enrich_client(
        {
            "id": 42,
            "full_name": "Client",
            "birthplace": "Rome",
            "nationality": "Italian",
            "custom_fields": '{"existing": true}',
        }
    )

    assert success is True
    saved_payload = json.loads(conn.executed[0][1][0])
    assert saved_payload["existing"] is True
    assert saved_payload["birthplace_enrichment"]["data"]["conversation_starters"] == [
        "Tell me about Rome"
    ]


@pytest.mark.asyncio
async def test_run_batch_enrichment_short_circuits_when_ollama_probe_fails() -> None:
    class ProbeClient:
        async def get(self, url: str) -> FakeResponse:
            return FakeResponse(503, {})

    service = make_service()
    service._get_client = lambda timeout: ProbeClient()

    stats = await service.run_batch_enrichment()

    assert stats["clients_processed"] == 0
    assert stats["error"] == "Ollama not available"


async def _async_value(value: object) -> object:
    return value
