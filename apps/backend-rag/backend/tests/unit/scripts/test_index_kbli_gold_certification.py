from __future__ import annotations

import copy
import sys

import httpx
import pytest

from backend.scripts import index_kbli_gold_content as gold_indexer
from backend.scripts.index_kbli_gold_content import (
    COLLECTION_NAME,
    GOLD_CONTENT_FILE,
    KBLI_DATA_FILE,
    build_point,
    certification_content,
    delete_existing_gold_points,
    deterministic_uuid,
    disclosed_standalone_gold,
    load_kbli_base_data,
    parse_gold_content_ts,
    upsert_to_qdrant,
)
from backend.services.kbli_editorial_certification import (
    load_editorial_registry,
    pma_editorial_fingerprint,
    stable_editorial_sha256,
)


def _synthetic_registry_certifying(code: str, gold: dict, base: dict) -> dict:
    """Build a registry INLINE for a code W-H PR-3c v3 de-certified from
    standaloneGold, rather than pin a stale historical entry. 65121's
    baliContext/zantaraOpener steered a foreign investor to 66221, a
    declared_gap code, as a "more practical"/"more accessible" route, so it
    was withdrawn — 47111 stays certified (only its canonicalIntel entry
    was withdrawn) but has a different PMA cap, so tests that need 65121's
    specific 80% cap still build a registry entry for it here. The two
    primitives are exactly what matches_editorial_certification() compares
    a registry entry against — the same mechanism a real standaloneGold
    entry would satisfy, computed fresh from the code's own current
    (untouched) data rather than a stale historical pin."""
    return {
        "standaloneGold": {
            code: {
                "pmaFingerprint": pma_editorial_fingerprint(base),
                "contentSha256": stable_editorial_sha256(certification_content(gold)),
            }
        }
    }


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
    # 65121 was de-certified from standaloneGold by W-H PR-3c v3: its prose
    # steered a foreign investor to a declared_gap code (66221) as a "more
    # practical"/"more accessible" alternative, and no compiler exists for
    # non-whatYouNeed gold fields, so the cure is withdrawal — the page
    # withholds it instead. 47111 is standaloneGold's only remaining entry
    # (its canonicalIntel entry was separately de-certified by the same PR,
    # for naming 47191/47192 "fully open to 100% PMA" while both are
    # declared_gap, but its standaloneGold prose was never flagged).
    assert certified == {"47111"}


def test_certified_point_uses_neutral_opener_and_exact_public_pma() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    # 65121 was de-certified from standaloneGold by W-H PR-3c v3 (47111 is
    # the section's only remaining real entry, but its cap is 0% not 80%) —
    # exercise the positive-certification path against a registry built
    # inline from 65121's own real, current gold/base data.
    registry = _synthetic_registry_certifying("65121", gold["65121"], base["65121"])

    partial = build_point("65121", gold["65121"], base["65121"], "test", registry)

    assert partial is not None
    assert partial["payload"]["pma_max_asing"] == 80
    assert partial["payload"]["editorial_disclosed"] is True
    assert (
        "Ask me about KBLI 65121: its official scope, licensing, risk, "
        "or foreign-ownership verification."
    ) in partial["_text_to_embed"]


def test_content_or_pma_mutation_prevents_point_construction() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    # 65121 is de-certified, so load_editorial_registry() would never
    # certify it and both assertions below would pass for the wrong reason
    # (build_point already None before any mutation). Build the registry
    # inline from the UNMUTATED gold/base so it genuinely certifies 65121
    # first, then prove each mutation breaks that certification.
    registry = _synthetic_registry_certifying("65121", gold["65121"], base["65121"])

    changed_content = copy.deepcopy(gold["65121"])
    changed_content["_certification_content"]["whatItMeans"] += "!"
    assert build_point("65121", changed_content, base["65121"], "test", registry) is None

    changed_pma = copy.deepcopy(base["65121"])
    changed_pma["pma_cap_verified"] = False
    assert build_point("65121", gold["65121"], changed_pma, "test", registry) is None


def test_located_but_uncertified_gold_is_not_a_point() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    assert base["47222"]["pma_verification_status"] == "located"
    assert build_point("47222", gold["47222"], base["47222"], "test", registry) is None


def test_decertified_gold_is_not_a_point() -> None:
    """65121's gold entry is still parsed (raw source untouched) but no
    longer in the registry's standaloneGold section (W-H PR-3c v3
    withdrawal: its baliContext/zantaraOpener steered a foreign investor to
    66221, a declared_gap code, as a "more practical"/"more accessible"
    route) — `build_point` must therefore refuse it exactly like an
    unreviewed code."""
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    assert "65121" not in registry["standaloneGold"]
    assert build_point("65121", gold["65121"], base["65121"], "test", registry) is None


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

    await delete_existing_gold_points(
        point_ids,
        "https://qdrant.test",
        "secret",
        sweep_owned=True,
    )

    assert len(point_ids) == 322
    assert len(set(point_ids)) == 322
    assert calls == [
        (
            f"https://qdrant.test/collections/{COLLECTION_NAME}/points/delete",
            {
                "params": {"wait": "true"},
                "json": {
                    "filter": {
                        "must": [
                            {"key": "doc_type", "match": {"value": "kbli_gold"}},
                        ]
                    }
                },
                "headers": {
                    "Content-Type": "application/json",
                    "api-key": "secret",
                },
            },
        ),
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
        ),
    ]


@pytest.mark.asyncio
async def test_missing_embedding_credentials_happens_after_selected_retraction(
    monkeypatch,
) -> None:
    # 65121 (not 47111 — 65121's cap is 80%, exercised elsewhere in this
    # file, while 47111's is 0%): this test needs a code that still reaches
    # point-construction so retraction happens BEFORE the missing-
    # credentials exit; an uncertified code takes the delete-only early
    # return instead (see the test right below this one) and never reaches
    # the OPENAI_API_KEY check at all. 65121 was de-certified from
    # standaloneGold by W-H PR-3c v3, so the real load_editorial_registry()
    # would also take the delete-only path — monkeypatch gold_indexer.
    # load_editorial_registry to return a synthetic registry certifying
    # 65121 inline, built from its own real, current data.
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    events: list[tuple[str, object]] = []

    async def fake_delete(point_ids, qdrant_url, api_key, *, sweep_owned=False):
        events.append(("delete", (point_ids, qdrant_url, api_key, sweep_owned)))

    monkeypatch.setattr(gold_indexer, "delete_existing_gold_points", fake_delete)
    monkeypatch.setattr(
        gold_indexer,
        "load_editorial_registry",
        lambda: _synthetic_registry_certifying("65121", gold["65121"], base["65121"]),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["index_kbli_gold_content.py", "--only", "65121", "--qdrant-url", "https://q.test"],
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        await gold_indexer.main()

    assert exc_info.value.code == 1
    assert events == [
        (
            "delete",
            ([deterministic_uuid("65121")], "https://q.test", "", False),
        )
    ]


@pytest.mark.asyncio
async def test_uncertified_only_code_is_a_successful_delete_only_reconciliation(
    monkeypatch,
) -> None:
    events: list[tuple[str, object]] = []

    async def fake_delete(point_ids, qdrant_url, api_key, *, sweep_owned=False):
        events.append(("delete", (point_ids, qdrant_url, api_key, sweep_owned)))

    monkeypatch.setattr(gold_indexer, "delete_existing_gold_points", fake_delete)
    monkeypatch.setattr(
        sys,
        "argv",
        ["index_kbli_gold_content.py", "--only", "47222", "--qdrant-url", "https://q.test"],
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    await gold_indexer.main()

    assert events == [
        (
            "delete",
            ([deterministic_uuid("47222")], "https://q.test", "", False),
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
