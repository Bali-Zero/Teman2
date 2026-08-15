from __future__ import annotations

import copy

import httpx
import pytest

from backend.scripts.index_kbli_gold_content import (
    COLLECTION_NAME,
    GOLD_CONTENT_FILE,
    KBLI_DATA_FILE,
    build_point,
    delete_existing_gold_points,
    deterministic_uuid,
    disclosed_standalone_gold,
    load_kbli_base_data,
    parse_gold_content_ts,
    upsert_to_qdrant,
)
from backend.services.kbli_editorial_certification import load_editorial_registry


def test_exact_parser_and_registry_publish_only_the_reviewed_partition() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    certified = {
        code
        for code, content in gold.items()
        if disclosed_standalone_gold(code, content, base.get(code, {}), registry) is not None
    }

    assert len(gold) == 322
    assert certified == {"47111", "65121"}


def test_certified_point_uses_neutral_opener_and_exact_public_pma() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    zero = build_point("47111", gold["47111"], base["47111"], "test", registry)
    partial = build_point("65121", gold["65121"], base["65121"], "test", registry)

    assert zero is not None
    assert partial is not None
    assert zero["payload"]["pma_max_asing"] == 0
    assert partial["payload"]["pma_max_asing"] == 80
    for code, point in (("47111", zero), ("65121", partial)):
        assert point["payload"]["editorial_disclosed"] is True
        assert (
            f"Ask me about KBLI {code}: its official scope, licensing, risk, "
            "or foreign-ownership verification."
        ) in point["_text_to_embed"]


def test_content_or_pma_mutation_prevents_point_construction() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    changed_content = copy.deepcopy(gold["47111"])
    changed_content["_certification_content"]["whatItMeans"] += "!"
    assert build_point("47111", changed_content, base["47111"], "test", registry) is None

    changed_pma = copy.deepcopy(base["47111"])
    changed_pma["pma_cap_verified"] = False
    assert build_point("47111", gold["47111"], changed_pma, "test", registry) is None


def test_located_but_uncertified_gold_is_not_a_point() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    assert base["47222"]["pma_verification_status"] == "located"
    assert build_point("47222", gold["47222"], base["47222"], "test", registry) is None


@pytest.mark.asyncio
async def test_full_retraction_targets_every_owned_legacy_gold_id(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeResponse:
        status_code = 200
        text = "ok"

    class FakeAsyncClient:
        def __init__(self, *, timeout: int) -> None:
            assert timeout == 120

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def post(self, url: str, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    point_ids = [deterministic_uuid(code) for code in sorted(gold)]

    await delete_existing_gold_points(point_ids, "https://qdrant.test", "secret")

    assert len(point_ids) == 322
    assert len(set(point_ids)) == 322
    assert calls == [
        (
            f"https://qdrant.test/collections/{COLLECTION_NAME}/points/delete",
            {
                "params": {"wait": "true"},
                "json": {"points": point_ids},
                "headers": {
                    "Content-Type": "application/json",
                    "api-key": "secret",
                },
            },
        )
    ]


@pytest.mark.asyncio
async def test_qdrant_upsert_failure_is_not_reported_as_success(monkeypatch) -> None:
    class FakeResponse:
        status_code = 503
        text = "unavailable"

    class FakeAsyncClient:
        def __init__(self, *, timeout: int) -> None:
            assert timeout == 120

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def put(self, url: str, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(RuntimeError, match="upsert certified KBLI gold"):
        await upsert_to_qdrant(
            [{"id": deterministic_uuid("47111"), "vector": {}, "payload": {}}],
            "https://qdrant.test",
            None,
        )
