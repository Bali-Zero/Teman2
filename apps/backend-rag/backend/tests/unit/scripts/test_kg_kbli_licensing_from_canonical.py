"""Lot 0 of the KG licensing-class cure — pure decision logic, no DB, no network.

Pins spec r4 §5.4 (`--placeholders-only`: only the three placeholder ids, never
`permit:kitas`, never a real permit) and §5.9 (`--create-missing-node`: only
canonical-proven keys, refusals on an existing node / an absent code / a
`[]` code), plus the CLI fences (`--only`, mode exclusivity, unpinned apply).
"""

from __future__ import annotations

import pytest

from backend.scripts.kg_kbli_licensing_from_canonical import (
    ARCHIVE_KEY,
    DATASET_URL,
    PLACEHOLDER_TARGETS,
    Refusal,
    build_missing_node,
    derive_skala_usaha,
    parse_args,
    plan_placeholder_removal,
)

# 55300-shaped edge list: real licences + KITAS + one placeholder.
MIXED_TARGETS = [
    "perizinan:nib_dan_sertifikat_standar",
    "license:sertifikat_standar",
    "permit:kitas",
    "company:pt_pma",
    "status_perizinan_pending",
]

# 01122-shaped canonical record (8 v10 rows over 3 tiers, no sektor_id, no pp28_sources).
RECORD_01122 = {
    "kode_kbli_2025": "01122",
    "judul": "Pertanian Padi Inbrida",
    "uraian": "Kelompok ini mencakup kegiatan pertanian padi inbrida (selain padi hibrida).",
    "sektor_id": None,
    "per_skala": [
        {"skala_usaha": ["Mikro"], "kategori_risiko": "Menengah Rendah"},
        {"skala_usaha": ["Kecil"], "kategori_risiko": "Menengah Rendah"},
        {"skala_usaha": ["Menengah"], "kategori_risiko": "Menengah Tinggi"},
        {"skala_usaha": ["Besar"], "kategori_risiko": "Menengah Tinggi"},
        {"skala_usaha": ["Mikro"], "kategori_risiko": "Rendah"},
    ],
}
META = {"run_id": "kbli_lot0:test", "at": "2026-09-21T00:00:00+00:00", "dataset_sha256": "ab" * 32}


def test_placeholder_ids_are_exactly_the_three_of_spec_2_1():
    assert PLACEHOLDER_TARGETS == {
        "status_perizinan_pending",
        "izin_usaha_pending",
        "izin_usaha_status_pending_regulation",
    }
    assert "permit:kitas" not in PLACEHOLDER_TARGETS
    assert ARCHIVE_KEY == "_replaced_requires_pp28v10"


def test_placeholder_plan_removes_only_the_placeholder_and_keeps_kitas_and_real_permits():
    plan = plan_placeholder_removal("55300", True, MIXED_TARGETS)
    assert plan.remove == ["status_perizinan_pending"]
    assert "permit:kitas" not in plan.remove
    assert "perizinan:nib_dan_sertifikat_standar" not in plan.remove


def test_placeholder_plan_is_empty_on_a_code_without_placeholder_edges():
    plan = plan_placeholder_removal("01111", True, ["perizinan:nib", "permit:kitas"])
    assert plan.remove == []


def test_placeholder_plan_refuses_a_code_without_a_node():
    with pytest.raises(Refusal, match="no kbli:01122 node"):
        plan_placeholder_removal("01122", False, [])


def test_placeholder_plan_dedups_and_orders_all_three_ids():
    targets = ["izin_usaha_pending", "status_perizinan_pending", "izin_usaha_pending", "izin_usaha_status_pending_regulation"]
    assert plan_placeholder_removal("65121", True, targets).remove == sorted(PLACEHOLDER_TARGETS)


def test_missing_node_carries_only_canonical_proven_keys():
    node = build_missing_node("01122", RECORD_01122, False, **META)
    assert node.name == "Pertanian Padi Inbrida"
    assert node.description.startswith("Kelompok ini mencakup")
    assert node.properties["kode"] == "01122"
    assert node.properties["licensing_status"] == "REGULATED"
    assert node.properties["skala_usaha"] == ["Mikro", "Kecil", "Menengah", "Besar"]
    assert node.properties["_created_by"] == {
        "run": "kbli_lot0:test",
        "at": "2026-09-21T00:00:00+00:00",
        "reason": "canonical code without a KG node (spec §5.9); no edge, no licence written",
        "dataset_sha256": "ab" * 32,
    }
    # Not invented: three tiers cannot become one value; None / absent stay absent.
    assert "kategori_risiko" not in node.properties
    assert "sektor_id" not in node.properties
    assert "pp28_sources" not in node.properties
    assert "pma_status" not in node.properties


def test_missing_node_keeps_sektor_and_pp28_when_the_canonical_carries_them():
    rec = {**RECORD_01122, "sektor_id": "I.B", "pp28_sources": ["01121", "01122"]}
    node = build_missing_node("01122", rec, False, **META)
    assert node.properties["sektor_id"] == "I.B"
    assert node.properties["pp28_sources"] == ["01121", "01122"]


def test_missing_node_refuses_an_existing_node_an_absent_code_and_an_empty_code():
    with pytest.raises(Refusal, match="already exists"):
        build_missing_node("01122", RECORD_01122, True, **META)
    with pytest.raises(Refusal, match="not in the canonical"):
        build_missing_node("99999", None, False, **META)
    with pytest.raises(Refusal, match="per_skala is \\[\\]"):
        build_missing_node("85586", {**RECORD_01122, "per_skala": []}, False, **META)


def test_derive_skala_usaha_follows_the_canonical_scale_order_and_dedups():
    rows = [{"skala_usaha": ["Besar", "Mikro"]}, {"skala_usaha": ["Mikro"]}, {"skala_usaha": None}]
    assert derive_skala_usaha(rows) == ["Mikro", "Besar"]


def test_cli_requires_only_and_exactly_one_mode():
    with pytest.raises(SystemExit):
        parse_args(["--placeholders-only"])
    with pytest.raises(SystemExit):
        parse_args(["--only", "01122"])
    with pytest.raises(SystemExit):
        parse_args(["--only", "01122", "--placeholders-only", "--create-missing-node"])
    args = parse_args(["--only", "65121, 96220", "--placeholders-only"])
    assert args.codes == ["65121", "96220"] and not args.apply


def test_cli_refuses_create_missing_node_apply_against_the_unpinned_dataset():
    with pytest.raises(SystemExit):
        parse_args(["--only", "01122", "--create-missing-node", "--apply"])
    ok = parse_args(["--only", "01122", "--create-missing-node", "--apply", "--dataset", DATASET_URL.replace("/main/", "/abc123/")])
    assert ok.apply and ok.create_missing_node
