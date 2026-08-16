"""Disclosure contract for the standalone KBLI gold-content generators."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_generator() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    path = repo_root / "apps" / "kbli-navigator" / "scripts" / "generate_gold_content.py"
    spec = importlib.util.spec_from_file_location("kbli_gold_generator_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()


def _located(**overrides: object) -> dict:
    record = {
        "kode_kbli_2025": "73100",
        "judul": "Periklanan",
        "uraian": "Kegiatan periklanan.",
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_verification_status": "located",
        "pma_official_basis": "Perpres 49/2021 official per-code locator",
        "pma_source_vintage": "2021-05-25",
        "pma_cap_verified": True,
        "per_skala": [
            {
                "skala_usaha": ["Besar"],
                "kategori_risiko": "Rendah",
                "perizinan": "NIB",
            }
        ],
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pma_verification_status", "declared_gap"),
        ("pma_status", " terbuka "),
        ("pma_status", "OPEN"),
        ("pma_official_basis", " "),
        ("pma_source_vintage", None),
    ],
)
def test_partial_or_noncanonical_pma_tuple_fails_closed(field: str, value: object) -> None:
    record = _located(**{field: value})

    assert GENERATOR.pma_claims_verified(record) is False
    assert GENERATOR.public_pma_prompt(record) == GENERATOR.PMA_NOT_VERIFIED_PROMPT


def test_complete_tuple_crosses_the_prompt_boundary_and_preserves_zero_cap() -> None:
    prompt = GENERATOR.public_pma_prompt(_located())

    assert prompt == (
        "pma_status: TERBATAS (0%); "
        "pma_official_basis: Perpres 49/2021 official per-code locator; "
        "pma_source_vintage: 2021-05-25"
    )


def test_batch_prompt_never_defaults_a_declared_gap_to_open_or_100_percent() -> None:
    record = _located(
        pma_verification_status="declared_gap",
        pma_status="TERBUKA",
        pma_max_asing=100,
        pma_official_basis=None,
        pma_source_vintage=None,
    )

    prompt = GENERATOR.build_llm_batch_input([record])

    assert GENERATOR.PMA_NOT_VERIFIED_PROMPT in prompt
    assert "pma_status: TERBUKA" not in prompt
    assert "100%" not in prompt
    assert "pma_official_basis: None" not in prompt


def test_what_you_need_withholds_raw_pma_and_does_not_prescribe_pt_pma_for_a_gap() -> None:
    record = _located(
        pma_verification_status="declared_gap",
        pma_status="TERBUKA",
        pma_max_asing=100,
        pma_official_basis=None,
        pma_source_vintage=None,
        pma_kondisi="UNSAFE_CONDITION",
        pma_nota="UNSAFE_NOTE",
    )

    content = GENERATOR.build_what_you_need(record)

    assert "**PMA:** NOT_VERIFIED" in content
    assert "Verify the ownership route" in content
    assert "PT PMA incorporation" not in content
    assert "100% foreign ownership" not in content
    assert "UNSAFE_CONDITION" not in content
    assert "UNSAFE_NOTE" not in content


def test_what_you_need_discloses_a_complete_located_tuple() -> None:
    content = GENERATOR.build_what_you_need(_located())

    assert "**PMA:** Restricted — max 0% foreign ownership." in content
    assert "Domestic entity route" in content
    assert "PT PMA incorporation" not in content


def test_what_you_need_prescribes_pt_pma_only_for_a_positive_located_cap() -> None:
    content = GENERATOR.build_what_you_need(_located(pma_max_asing=49))

    assert "**PMA:** Restricted — max 49% foreign ownership." in content
    assert "PT PMA incorporation" in content


def test_closed_zero_cap_is_not_worded_as_permission() -> None:
    content = GENERATOR.build_what_you_need(_located(pma_status="TERTUTUP", pma_max_asing=0))

    assert "**PMA:** Closed — 0% foreign ownership." in content
    assert "foreign ownership allowed" not in content
    assert "Domestic entity route" in content


def test_special_located_regime_is_disclosed_without_inventing_a_percentage() -> None:
    record = _located(
        kode_kbli_2025="47221",
        pma_max_asing="special",
        pma_cap_special=True,
    )

    assert "special non-percentage conditions" in GENERATOR.public_pma_prompt(record)
    content = GENERATOR.build_what_you_need(record)
    assert "Open with special non-percentage conditions" in content
    assert "PT PMA incorporation" in content
    assert "% foreign ownership" not in content


def test_unmarked_special_cap_does_not_authorize_a_pt_pma_route() -> None:
    record = _located(pma_max_asing="special", pma_cap_special=False)

    assert "special non-percentage conditions" not in GENERATOR.public_pma_prompt(record)
    content = GENERATOR.build_what_you_need(record)
    assert "Verify the ownership route" in content
    assert "PT PMA incorporation" not in content


@pytest.mark.parametrize(
    "cap",
    [0, 49, "49", True, float("inf")],
)
def test_unverified_or_malformed_cap_never_crosses_prompt_or_selects_entity_route(
    cap: object,
) -> None:
    record = _located(pma_max_asing=cap, pma_cap_verified=False)

    prompt = GENERATOR.public_pma_prompt(record)
    content = GENERATOR.build_what_you_need(record)

    assert f"({cap}%)" not in prompt
    assert "Verify the ownership route" in content
    assert "PT PMA incorporation" not in content
    assert "Domestic entity route" not in content


def test_few_shot_prompt_no_longer_teaches_an_unverified_open_cap() -> None:
    assert "pma_status: TERBUKA (100%)" not in GENERATOR.SYSTEM_PROMPT
    assert GENERATOR.SYSTEM_PROMPT.count("pma_status: NOT_VERIFIED") == 4
