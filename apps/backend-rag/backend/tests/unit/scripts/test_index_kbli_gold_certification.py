from __future__ import annotations

import copy

from backend.scripts.index_kbli_gold_content import (
    GOLD_CONTENT_FILE,
    KBLI_DATA_FILE,
    build_point,
    disclosed_standalone_gold,
    load_kbli_base_data,
    parse_gold_content_ts,
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
