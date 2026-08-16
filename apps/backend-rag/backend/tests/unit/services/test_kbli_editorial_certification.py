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
    assert len(certified) == 49
    assert {
        code
        for code, record in records.items()
        if record.get("pma_verification_status") == "located"
    } - certified == {"10722", "47222", "50134", "73100", "96220"}


def test_content_pma_and_code_drift_fail_closed(
    registry: dict,
    records: dict[str, dict],
) -> None:
    original = records["47111"]
    content = original["intel_2026"]
    assert matches_editorial_certification(
        "canonicalIntel",
        "47111",
        original,
        content,
        registry,
    )

    changed_content = copy.deepcopy(content)
    changed_content["whatItMeans"] += "!"
    assert not matches_editorial_certification(
        "canonicalIntel",
        "47111",
        original,
        changed_content,
        registry,
    )

    changed_pma = copy.deepcopy(original)
    changed_pma["pma_max_asing"] = 1
    assert not matches_editorial_certification(
        "canonicalIntel",
        "47111",
        changed_pma,
        content,
        registry,
    )

    wrong_code = copy.deepcopy(original)
    wrong_code["kode_kbli_2025"] = "65121"
    assert not matches_editorial_certification(
        "canonicalIntel",
        "47111",
        wrong_code,
        content,
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
    malformed["canonicalIntel"]["47111"]["contentSha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="contentSha256"):
        validate_editorial_registry(malformed)

    opener = neutral_kbli_chat_opener_text("47111")
    assert opener.startswith("Ask me about KBLI 47111")
    assert "%" not in opener
    assert "Bali" not in opener
