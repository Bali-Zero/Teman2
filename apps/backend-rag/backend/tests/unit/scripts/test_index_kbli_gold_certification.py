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
    """Build a registry INLINE rather than pin a real code (standaloneGold is
    empty after W-H PR-3c v3 de-certified its last entry, 65121 — its
    baliContext/zantaraOpener steered a foreign investor to 66221, a
    declared_gap code, as a "more practical"/"more accessible" route). The
    two primitives here are exactly what matches_editorial_certification()
    compares a registry entry against — the same mechanism a real
    standaloneGold entry would satisfy, computed fresh from the code's own
    current (untouched) data rather than a stale historical pin."""
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
    # 47111 was de-certified from standaloneGold by W-H PR-3c: its gold prose
    # named 47191/47192 as "fully open to 100% PMA" while those codes' own
    # records are declared_gap, and no compiler exists for non-whatYouNeed
    # gold fields, so the cure is withdrawal — the page withholds it instead.
    # standaloneGold is now EMPTY: 65121 was its last remaining entry, and
    # W-H PR-3c v3 de-certified it for the same reason as 47111 above — its
    # prose steered a foreign investor to a declared_gap code (66221) as a
    # "more practical"/"more accessible" alternative.
    assert certified == set()


def test_certified_point_uses_neutral_opener_and_exact_public_pma() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    # standaloneGold is empty (65121 was its last entry, de-certified by W-H
    # PR-3c v3) — exercise the positive-certification path against a registry
    # built inline from 65121's own real, current gold/base data.
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
    # standaloneGold is empty, so load_editorial_registry() would never
    # certify 65121 and both assertions below would pass for the wrong
    # reason (build_point already None before any mutation). Build the
    # registry inline from the UNMUTATED gold/base so it genuinely certifies
    # 65121 first, then prove each mutation breaks that certification.
    registry = _synthetic_registry_certifying("65121", gold["65121"], base["65121"])

    changed_content = copy.deepcopy(gold["65121"])
    changed_content["_certification_content"]["whatItMeans"] += "!"
    assert build_point("65121", changed_content, base["65121"], "test", registry) is None

    changed_pma = copy.deepcopy(base["65121"])
    changed_pma["pma_cap_verified"] = False
    assert build_point("65121", gold["65121"], changed_pma, "test", registry) is None


def test_certified_point_discloses_a_zero_percent_cap_verbatim() -> None:
    """41020 (base pma_max_asing == 0, TERBATAS, located) is certified here
    through a registry built in-test, because standaloneGold is empty on main.
    Its standalone gold prose still reads "PMA: TERBUKA 100% — fully open to
    foreign ownership." — which is exactly why it stays UNCERTIFIED (and
    unserved) in the real registry; this test does not certify it for real.
    What it asserts is structural: a 0% cap survives the indexer's payload
    untouched (never coerced to None/falsy by a `cap or default` bug), with
    `editorial_disclosed=True` and the neutral opener, like any other
    certified gold point (gate-6598 condition, SAETTA W-H PR-3d)."""
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    assert base["41020"]["pma_max_asing"] == 0
    assert base["41020"]["pma_status"] == "TERBATAS"
    assert base["41020"]["pma_cap_verified"] is True
    registry = _synthetic_registry_certifying("41020", gold["41020"], base["41020"])

    partial = build_point("41020", gold["41020"], base["41020"], "test", registry)

    assert partial is not None
    payload = partial["payload"]
    assert payload["pma_max_asing"] == 0
    assert payload["pma_status"] == "TERBATAS"
    assert payload["pma_verification_status"] == "located"
    assert payload["pma_cap_verified"] is True
    assert payload["pma_cap_special"] is False
    assert payload["editorial_disclosed"] is True
    assert (
        "Ask me about KBLI 41020: its official scope, licensing, risk, "
        "or foreign-ownership verification."
    ) in partial["_text_to_embed"]


def test_mutating_a_zero_percent_base_cap_prevents_point_construction() -> None:
    """Guilt half of the 0%-cap assertion above: a registry certified against
    the REAL 0%-cap tuple must refuse to build a point once the base
    record's cap changes underneath it — the exact failure mode gate-6593
    exists to prevent (stale prose surviving a PMA tuple it no longer
    matches)."""
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = _synthetic_registry_certifying("41020", gold["41020"], base["41020"])

    mutated_base = copy.deepcopy(base["41020"])
    mutated_base["pma_max_asing"] = 49

    assert build_point("41020", gold["41020"], mutated_base, "test", registry) is None


def test_located_but_uncertified_gold_is_not_a_point() -> None:
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    assert base["47222"]["pma_verification_status"] == "located"
    assert build_point("47222", gold["47222"], base["47222"], "test", registry) is None


def test_decertified_gold_is_not_a_point() -> None:
    """47111's gold entry is still parsed (raw source untouched) but no
    longer in the registry's standaloneGold section (W-H PR-3c withdrawal:
    its prose named 47191/47192 as open/100% while both are declared_gap) —
    `build_point` must therefore refuse it exactly like an unreviewed code."""
    gold = parse_gold_content_ts(GOLD_CONTENT_FILE)
    base = load_kbli_base_data(KBLI_DATA_FILE)
    registry = load_editorial_registry()

    assert "47111" not in registry["standaloneGold"]
    assert build_point("47111", gold["47111"], base["47111"], "test", registry) is None


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
    # 65121 (not 47111 — de-certified from standaloneGold by W-H PR-3c): this
    # test needs a code that still reaches point-construction so retraction
    # happens BEFORE the missing-credentials exit; an uncertified code takes
    # the delete-only early return instead (see the test right below this
    # one) and never reaches the OPENAI_API_KEY check at all. standaloneGold
    # is now empty (65121 was de-certified too, by W-H PR-3c v3), so the
    # real load_editorial_registry() would also take the delete-only path —
    # monkeypatch gold_indexer.load_editorial_registry to return a synthetic
    # registry certifying 65121 inline, built from its own real, current data.
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
