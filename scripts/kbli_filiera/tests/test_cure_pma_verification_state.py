from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if FILIERA_DIR not in sys.path:
    sys.path.insert(0, FILIERA_DIR)

import cure_pma_verification_state as C  # noqa: E402


def rec(code: str, **overrides):
    return {
        "kode_kbli_2025": code,
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        **overrides,
    }


def test_partition_requires_a_per_code_basis_and_vintage():
    records = [
        rec("01111"),
        rec(
            "50122",
            pma_official_basis="Perpres 49/2021 Lampiran III entry #22",
            pma_source_vintage="2021-05-25",
        ),
    ]
    plans = C.plan(records)
    assert plans["01111"]["patch"] == {
        "pma_verification_status": "declared_gap"
    }
    assert plans["50122"]["patch"] == {
        "pma_verification_status": "located"
    }


def test_known_instrument_vintages_are_filled_without_inventing_a_basis():
    records = [
        rec("73100", pma_official_basis="Perpres 10/2021 Pasal 3(1)(d)"),
        rec(
            "65121",
            pma_official_basis="PP 14/2018 Pasal 5(1) jo. PP 3/2020 Pasal I angka 1",
        ),
    ]
    plans = C.plan(records)
    assert plans["73100"]["patch"]["pma_source_vintage"] == "2021-05-25"
    assert plans["65121"]["patch"]["pma_source_vintage"] == "2020-01-20"


def test_unknown_instrument_is_a_refusal_not_a_guessed_vintage():
    with pytest.raises(C.CureError, match="unrecognised official basis"):
        C.plan([rec("99999", pma_official_basis="Some future circular")])


def test_vintage_without_basis_is_a_refusal_not_silently_deleted():
    with pytest.raises(C.CureError, match="vintage exists without"):
        C.plan([rec("99999", pma_source_vintage="2021-05-25")])


def test_applied_state_is_idempotent():
    records = [
        rec("01111", pma_verification_status="declared_gap"),
        rec(
            "50122",
            pma_official_basis="Perpres 49/2021 Lampiran III",
            pma_source_vintage="2021-05-25",
            pma_verification_status="located",
        ),
    ]
    assert {item["action"] for item in C.plan(records).values()} == {"noop"}


def test_custom_fixture_apply_changes_only_declared_fields(tmp_path):
    records = [
        rec("01111", untouched={"x": 1}),
        rec(
            "65121",
            pma_official_basis="PP 14/2018 jo. PP 3/2020",
            untouched={"x": 2},
        ),
    ]
    before = copy.deepcopy(records)
    path = tmp_path / "canonical.json"
    path.write_text(json.dumps({"data": records}) + "\n")

    assert C.main(["--apply", "--canonical", str(path)]) == 0
    after = json.loads(path.read_text())["data"]
    assert after[0]["untouched"] == before[0]["untouched"]
    assert after[1]["untouched"] == before[1]["untouched"]
    assert after[0]["pma_verification_status"] == "declared_gap"
    assert after[1]["pma_verification_status"] == "located"
    assert after[1]["pma_source_vintage"] == "2020-01-20"
    assert C.main(["--apply", "--canonical", str(path)]) == 0
