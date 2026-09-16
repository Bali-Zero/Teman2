from __future__ import annotations

import copy
import json

import pytest

from backend.scripts.reindex_kbli_2025_final import SOURCE_FILE
from backend.services.kbli_editorial_certification import (
    assert_certified_source_dataset,
    load_editorial_registry,
    matches_editorial_certification,
    neutral_kbli_chat_opener_text,
    validate_editorial_registry,
)


@pytest.fixture(scope="module")
def registry() -> dict:
    return load_editorial_registry()


@pytest.fixture(scope="module")
def records() -> dict[str, dict]:
    payload = json.loads(SOURCE_FILE.read_bytes())
    return {record["kode_kbli_2025"]: record for record in payload["data"]}


def test_registry_is_bound_to_the_exact_canonical_dataset(registry: dict) -> None:
    source_bytes = SOURCE_FILE.read_bytes()
    assert_certified_source_dataset(source_bytes, registry)

    with pytest.raises(ValueError, match="do not match"):
        assert_certified_source_dataset(source_bytes + b"\n", registry)


def test_canonical_certification_partition_is_exact(
    registry: dict,
    records: dict[str, dict],
) -> None:
    certified = {
        code
        for code, record in records.items()
        if matches_editorial_certification(
            "canonicalIntel",
            code,
            record,
            record["intel_2026"],
            registry,
        )
    }

    assert certified == set(registry["canonicalIntel"])
    assert len(certified) == 37
    # SAETTA-20260915 W-H PR-3a moved 55201/55203/79903 from declared_gap to
    # located (Perpres 49/2021 Lampiran II allocation); none of the three is
    # a certified canonicalIntel entry, so they join the pre-existing
    # located-but-uncertified set. PR-3c v3 de-certified 12 further codes
    # (10214/16221/22121/47111/50111/50112/51102/55105/65111/79122/95220/
    # 96100) whose prose still claimed an openness their own tuple denies —
    # they join the same set (fail closed: withheld, not re-authored blind).
    assert {
        code
        for code, record in records.items()
        if record.get("pma_verification_status") == "located"
    } - certified == {
        "10722",
        "47222",
        "50134",
        "55201",
        "55203",
        "73100",
        "79903",
        "96220",
        "10214",
        "16221",
        "22121",
        "47111",
        "50111",
        "50112",
        "51102",
        "55105",
        "65111",
        "79122",
        "95220",
        "96100",
    }


def test_content_pma_and_code_drift_fail_closed(
    registry: dict,
    records: dict[str, dict],
) -> None:
    # 47111 was de-certified in PR-3c v3 (canonicalIntel AND mouthGold) — a
    # still-certified code exercises the drift checks; 47111's withheld state
    # is asserted separately below.
    original = records["41016"]
    content = original["intel_2026"]
    assert matches_editorial_certification(
        "canonicalIntel",
        "41016",
        original,
        content,
        registry,
    )

    changed_content = copy.deepcopy(content)
    changed_content["whatItMeans"] += "!"
    assert not matches_editorial_certification(
        "canonicalIntel",
        "41016",
        original,
        changed_content,
        registry,
    )

    changed_pma = copy.deepcopy(original)
    changed_pma["pma_max_asing"] = 1
    assert not matches_editorial_certification(
        "canonicalIntel",
        "41016",
        changed_pma,
        content,
        registry,
    )

    wrong_code = copy.deepcopy(original)
    wrong_code["kode_kbli_2025"] = "65121"
    assert not matches_editorial_certification(
        "canonicalIntel",
        "41016",
        wrong_code,
        content,
        registry,
    )


def test_decertified_code_is_withheld_not_reauthored(
    registry: dict,
    records: dict[str, dict],
) -> None:
    """GATE-6593 (predecessor #6593/#6594) BLOCKED partly on a stale test that
    still pinned a de-certified code as certified. 47111 lost both
    canonicalIntel and mouthGold certification in this PR (PR-3c v3) — assert
    the withdrawal fails closed rather than silently re-matching."""
    record = records["47111"]
    assert "47111" not in registry["canonicalIntel"]
    assert "47111" not in registry["mouthGold"]
    assert not matches_editorial_certification(
        "canonicalIntel",
        "47111",
        record,
        record["intel_2026"],
        registry,
    )


def test_explicit_bad_registry_never_falls_back_to_the_default(
    records: dict[str, dict],
) -> None:
    record = records["47111"]
    assert not matches_editorial_certification(
        "canonicalIntel",
        "47111",
        record,
        record["intel_2026"],
        {},
    )
    with pytest.raises(ValueError, match="expected None"):
        assert_certified_source_dataset(SOURCE_FILE.read_bytes(), {})


def test_registry_validation_and_neutral_opener(registry: dict) -> None:
    assert validate_editorial_registry(copy.deepcopy(registry)) == registry
    malformed = copy.deepcopy(registry)
    malformed["canonicalIntel"]["41016"]["contentSha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="contentSha256"):
        validate_editorial_registry(malformed)

    opener = neutral_kbli_chat_opener_text("47111")
    assert opener.startswith("Ask me about KBLI 47111")
    assert "%" not in opener
    assert "Bali" not in opener
