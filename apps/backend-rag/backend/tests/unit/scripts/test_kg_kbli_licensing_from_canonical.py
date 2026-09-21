"""Lot 0 + Phase 1a of the KG licensing-class cure — pure decision logic, no DB.

Pins spec r4 §5.4 (`--placeholders-only`), §5.9 (`--create-missing-node`), §4
(the derivation rule), §5.2 (state/eligibility), §5.7 (idempotence) plus the
CLI fences (`--only`, mode exclusivity, unpinned apply, `--phase`/
`--replace-legacy`).
"""

from __future__ import annotations

import pytest

from backend.scripts.kg_kbli_licensing_from_canonical import (
    ARCHIVE_KEY,
    DATASET_URL,
    LEGAL_BASIS,
    PHASE_1B_ENABLED,
    PLACEHOLDER_TARGETS,
    SCALE_ORDER,
    TIER,
    BuildPlan,
    Refusal,
    ShapeDefect,
    _assert_legal_basis,
    build_missing_node,
    build_node_properties,
    check_eligibility,
    classify_idempotence,
    classify_state,
    decode_jsonb,
    derive_licence_groups,
    derive_skala_usaha,
    digest_of_set,
    is_non_oss_issued,
    licence_name,
    normalise_field,
    parse_args,
    plan_build,
    plan_placeholder_removal,
    s3_comparison,
    target_entity_id,
    validate_existing_target,
    validate_skala,
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


def test_cli_requires_only_and_exactly_one_lot0_mode_plus_build_mode_default():
    with pytest.raises(SystemExit):
        parse_args(["--placeholders-only"])  # --only still mandatory outside --census
    # Neither Lot-0 flag nor --census: build mode, the new default (spec §5 item 1).
    args = parse_args(["--only", "01122"])
    assert not args.placeholders_only and not args.create_missing_node and not args.census
    assert args.phase == "1a"
    with pytest.raises(SystemExit):
        parse_args(["--only", "01122", "--placeholders-only", "--create-missing-node"])
    args = parse_args(["--only", "65121, 96220", "--placeholders-only"])
    assert args.codes == ["65121", "96220"] and not args.apply


def test_cli_refuses_create_missing_node_apply_against_the_unpinned_dataset():
    with pytest.raises(SystemExit):
        parse_args(["--only", "01122", "--create-missing-node", "--apply"])
    ok = parse_args(["--only", "01122", "--create-missing-node", "--apply", "--dataset", DATASET_URL.replace("/main/", "/abc123/")])
    assert ok.apply and ok.create_missing_node


# =============================================================================
# CLI fences added this revision: --phase, --replace-legacy, --census
# =============================================================================


def test_cli_phase_1b_refused_while_the_module_constant_is_false():
    assert PHASE_1B_ENABLED is False
    with pytest.raises(SystemExit):
        parse_args(["--only", "65121", "--phase", "1b"])


def test_cli_replace_legacy_is_always_refused():
    with pytest.raises(SystemExit):
        parse_args(["--only", "25920", "--replace-legacy"])


def test_cli_census_is_read_only_and_takes_no_only():
    args = parse_args(["--census"])
    assert args.census and args.codes == []
    with pytest.raises(SystemExit):
        parse_args(["--census", "--only", "01122"])


def test_cli_census_is_mutually_exclusive_with_the_other_modes():
    with pytest.raises(SystemExit):
        parse_args(["--census", "--placeholders-only"])


# =============================================================================
# §4.2 — the normaliser
# =============================================================================


def test_normalise_field_none_str_list_and_shape_defect():
    assert normalise_field(None) == []
    assert normalise_field("") == []
    assert normalise_field("NPWP") == ["NPWP"]
    assert normalise_field(["a", "b"]) == ["a", "b"]
    with pytest.raises(ShapeDefect):
        normalise_field(42)
    with pytest.raises(ShapeDefect):
        normalise_field({"a": 1})
    with pytest.raises(ShapeDefect):
        normalise_field(True)


# =============================================================================
# §4.1 — TIER pinned against LEGAL_BASIS
# =============================================================================


def test_tier_matches_legal_basis_articles_exactly():
    assert set(TIER) == {"Rendah", "Menengah Rendah", "Menengah Tinggi", "Tinggi"}
    assert LEGAL_BASIS["Rendah"] == "Pasal 130" and TIER["Rendah"] == "NIB"
    assert LEGAL_BASIS["Menengah Rendah"] == "Pasal 131" and TIER["Menengah Rendah"] == "NIB dan Sertifikat Standar"
    assert LEGAL_BASIS["Menengah Tinggi"] == "Pasal 132" and TIER["Menengah Tinggi"] == "NIB dan Sertifikat Standar"
    assert LEGAL_BASIS["Tinggi"] == "Pasal 133" and TIER["Tinggi"] == "NIB dan Izin"


def test_assert_legal_basis_refuses_when_incomplete_and_passes_when_whole():
    with pytest.raises(Refusal):
        _assert_legal_basis({})
    with pytest.raises(Refusal):
        _assert_legal_basis({"instrument": "PP 28/2025"})
    _assert_legal_basis(LEGAL_BASIS)  # no raise


# =============================================================================
# §4.2 item 1 — the tier rule, all four classes + explicit-perizinan precedence
# =============================================================================


def test_licence_name_follows_the_tier_rule_on_all_four_classes():
    assert licence_name({"kategori_risiko": "Rendah"}) == "NIB"
    assert licence_name({"kategori_risiko": "Menengah Rendah"}) == "NIB dan Sertifikat Standar"
    assert licence_name({"kategori_risiko": "Menengah Tinggi"}) == "NIB dan Sertifikat Standar"
    assert licence_name({"kategori_risiko": "Tinggi"}) == "NIB dan Izin"


def test_licence_name_explicit_perizinan_wins_over_the_tier_rule():
    row = {"kategori_risiko": "Menengah Tinggi", "perizinan": ["Izin Usaha Sertifikasi Profesi"]}
    assert licence_name(row) == "Izin Usaha Sertifikasi Profesi"
    # 93111-shaped: perizinan a STRING, not a list — the mandatory fixture (spec §4.2 item 3).
    row_93111 = {"kategori_risiko": "Rendah", "perizinan": "Izin Usaha Fasilitas Stadion"}
    assert licence_name(row_93111) == "Izin Usaha Fasilitas Stadion"


def test_licence_name_refuses_an_unknown_tier():
    with pytest.raises(ShapeDefect):
        licence_name({"kategori_risiko": "Sangat Tinggi"})
    with pytest.raises(ShapeDefect):
        licence_name({"kategori_risiko": None})


def test_validate_skala_accepts_a_non_empty_subset_and_refuses_otherwise():
    assert validate_skala(["Besar", "Mikro"]) == ["Besar", "Mikro"]
    with pytest.raises(ShapeDefect):
        validate_skala([])
    with pytest.raises(ShapeDefect):
        validate_skala(None)
    with pytest.raises(ShapeDefect):
        validate_skala(["Kecil", "Raksasa"])


# =============================================================================
# §4.2 item 3/4 — grouping and aggregation
# =============================================================================

# 03231-shaped: two (name, tier) groups over four rows, two scales each.
ROWS_03231_SHAPED = [
    {
        "kategori_risiko": "Menengah Rendah",
        "skala_usaha": ["Mikro"],
        "jangka_waktu": "Otomatis",
        "scope_index": 0,
        "scope_uraian": "cakupan A",
        "kewajiban": ["k1"],
        "persyaratan": ["p1"],
        "kewenangan": ["Bupati"],
        "fiktif_positif": False,
    },
    {
        "kategori_risiko": "Menengah Rendah",
        "skala_usaha": ["Kecil"],
        "jangka_waktu": "Otomatis",
        "scope_index": 0,
        "scope_uraian": "cakupan A",
        "kewajiban": ["k1", "k2"],
        "persyaratan": ["p1"],
        "kewenangan": ["Bupati"],
        "fiktif_positif": True,
    },
    {
        "kategori_risiko": "Menengah Tinggi",
        "skala_usaha": ["Menengah"],
        "jangka_waktu": "3 Hari",
        "scope_index": 1,
        "scope_uraian": "cakupan B",
        "kewajiban": ["k3"],
        "persyaratan": [],
        "kewenangan": ["Menteri"],
        "fiktif_positif": False,
    },
    {
        "kategori_risiko": "Menengah Tinggi",
        "skala_usaha": ["Besar"],
        "jangka_waktu": "1 Tahun",
        "scope_index": 1,
        "scope_uraian": "cakupan B",
        "kewajiban": ["k3"],
        "persyaratan": [],
        "kewenangan": ["Menteri"],
        "fiktif_positif": False,
    },
]


def test_derive_licence_groups_on_03231_shaped_rows_yields_two_groups_aggregated():
    groups = derive_licence_groups("03231", ROWS_03231_SHAPED)
    assert len(groups) == 2
    mr, mt = groups
    assert mr.kategori_risiko == "Menengah Rendah" and mr.name == "NIB dan Sertifikat Standar"
    assert mr.skala_usaha == ["Mikro", "Kecil"]  # SCALE_ORDER, not first-seen
    assert mr.jangka_waktu == "Otomatis"  # distinct non-blank, first-seen, joined
    assert mr.kewajiban == ["k1", "k2"]  # ordered dedup
    assert mr.fiktif_positif is True  # any()
    assert mr.pp28_row_indexes == [0, 0]
    assert mr.sertifikat_standar_verification == "self-declared"

    assert mt.kategori_risiko == "Menengah Tinggi"
    assert mt.skala_usaha == ["Menengah", "Besar"]
    assert mt.jangka_waktu == "3 Hari/1 Tahun"  # two distinct values, first-seen order joined by "/"
    assert mt.sertifikat_standar_verification == "verified"


def test_derive_licence_groups_93111_fixture_string_perizinan_no_scope_fields_no_refusal():
    rows = [
        {"kategori_risiko": "Rendah", "perizinan": "Izin Usaha Fasilitas Stadion", "kewenangan": "Bupati", "skala_usaha": ["Mikro"]},
    ]
    groups = derive_licence_groups("93111", rows)
    assert len(groups) == 1
    assert groups[0].name == "Izin Usaha Fasilitas Stadion"
    assert groups[0].kewenangan == ["Bupati"]  # string normalised to a one-element list
    assert groups[0].pp28_row_indexes == [None]  # scope_index absent -> null, no refusal


def test_derive_licence_groups_refuses_on_empty_malformed_unknown_tier_or_bad_skala():
    with pytest.raises(Refusal, match="per_skala is \\[\\]"):
        derive_licence_groups("99999", [])
    with pytest.raises(Refusal, match="unknown kategori_risiko"):
        derive_licence_groups("99998", [{"kategori_risiko": "Ekstrim", "skala_usaha": ["Mikro"]}])
    with pytest.raises(Refusal, match="skala_usaha"):
        derive_licence_groups("99997", [{"kategori_risiko": "Rendah", "skala_usaha": []}])
    with pytest.raises(Refusal):
        derive_licence_groups("99996", [{"kategori_risiko": "Rendah", "skala_usaha": 42}])


# =============================================================================
# §5.3 — node properties, code-scoped id, decoded-value validation
# =============================================================================


def test_build_node_properties_carries_the_group_plus_source_verification_legal_basis():
    groups = derive_licence_groups("03231", ROWS_03231_SHAPED)
    props = build_node_properties(groups[0])
    assert props["source"] == "kbli_2025_v10_pp28"
    assert props["legal_basis"] == "PP 28/2025"
    assert props["sertifikat_standar_verification"] == "self-declared"
    assert "name" not in props  # name is the node's own column, not a property


def test_target_entity_id_is_code_scoped_stable_and_collision_free():
    groups = derive_licence_groups("03231", ROWS_03231_SHAPED)
    props0 = build_node_properties(groups[0])
    id_a = target_entity_id("03231", props0)
    id_b = target_entity_id("03231", props0)
    assert id_a == id_b  # same code, re-derived -> same id
    assert id_a.startswith("perizinan:pp28v10:03231:")
    id_other_code = target_entity_id("99999", props0)
    assert id_other_code != id_a  # two codes, identical group content -> distinct ids


def test_decode_jsonb_handles_str_dict_and_refuses_bytes():
    assert decode_jsonb('{"a": 1}') == {"a": 1}
    assert decode_jsonb({"a": 1}) == {"a": 1}
    with pytest.raises(ShapeDefect):
        decode_jsonb(b'{"a": 1}')


def test_validate_existing_target_innocence_on_whitespace_and_key_order_only():
    props = {"b": 1, "a": 2}
    raw = '{  "a" :  2, "b" :  1  }'  # same VALUE, different whitespace/key order
    result = validate_existing_target("perizinan:pp28v10:X:abc", "perizinan", "NIB", raw, "NIB", props)
    assert result is None  # no Refusal raised — decoded values match despite the JSONB round-trip


def test_validate_existing_target_guilt_on_a_real_value_difference():
    with pytest.raises(Refusal):
        validate_existing_target("perizinan:pp28v10:X:abc", "perizinan", "NIB", '{"a": 1}', "NIB", {"a": 2})
    with pytest.raises(Refusal):
        validate_existing_target("perizinan:pp28v10:X:abc", "izin_usaha", "NIB", "{}", "NIB", {})
    with pytest.raises(Refusal):
        validate_existing_target("perizinan:pp28v10:X:abc", "perizinan", "Izin Lain", "{}", "NIB", {})


# =============================================================================
# §3 — non-OSS-issued detection
# =============================================================================


def test_is_non_oss_issued_detects_the_persyaratan_phrase_and_only_that():
    yes = [{"persyaratan": ["Lembaga OSS hanya menerbitkan NIB. Permohonan ... ke Kementerian."]}]
    assert is_non_oss_issued(yes) is True
    no = [{"persyaratan": ["syarat biasa"]}]
    assert is_non_oss_issued(no) is False
    assert is_non_oss_issued([{"persyaratan": None}]) is False


# =============================================================================
# §5.2 — state classification and S3 comparison
# =============================================================================


def test_classify_state_covers_all_four_named_states_and_other():
    assert classify_state(0, "PENDING_REGULATION") == "S1"
    assert classify_state(0, "REGULATED") == "S2"
    assert classify_state(0, None) == "S2"  # router default
    assert classify_state(1, "PENDING_REGULATION") == "S3"
    assert classify_state(2, "REGULATED") == "legacy_served"
    assert classify_state(1, "NOT_APPLICABLE_OSS") == "other"


def test_s3_comparison_match_and_mismatch():
    match = s3_comparison(["Izin Terbang"], ["Izin Terbang"])
    assert match["match"] is True
    mismatch = s3_comparison(["Izin Terbang"], ["NIB", "NIB dan Sertifikat Standar"])
    assert mismatch["match"] is False
    assert mismatch["derived"] == ["NIB", "NIB dan Sertifikat Standar"]


# =============================================================================
# §5.7 — idempotence: UNCURED / CURED / DRIFTED
# =============================================================================


def test_classify_idempotence_uncured_when_no_pp28v10_targets_exist():
    v = classify_idempotence(["perizinan:pp28v10:X:aaa"], [], True, None, None)
    assert v.status == "UNCURED"


def test_classify_idempotence_cured_on_full_match_second_run_writes_zero():
    ids = ["perizinan:pp28v10:X:aaa", "perizinan:pp28v10:X:bbb"]
    d = digest_of_set(ids)
    v = classify_idempotence(ids, ids, True, "REGULATED", d)
    assert v.status == "CURED"


def test_classify_idempotence_drifted_on_set_mismatch_payload_mismatch_or_digest_mismatch():
    ids = ["perizinan:pp28v10:X:aaa"]
    d = digest_of_set(ids)
    assert classify_idempotence(ids, ["perizinan:pp28v10:X:bbb"], True, "REGULATED", d).status == "DRIFTED"
    assert classify_idempotence(ids, ids, False, "REGULATED", d).status == "DRIFTED"
    assert classify_idempotence(ids, ids, True, "PENDING_REGULATION", d).status == "DRIFTED"
    assert classify_idempotence(ids, ids, True, "REGULATED", "stale-digest").status == "DRIFTED"


# =============================================================================
# §5 item 1/§2 — eligibility ordering
# =============================================================================


def test_check_eligibility_orders_refusals_node_then_placeholder_then_canonical():
    with pytest.raises(Refusal, match="no kbli:"):
        check_eligibility("11111", RECORD_01122, frozenset(), "1a", False, True)
    with pytest.raises(Refusal, match="placeholder edge"):
        check_eligibility("11111", RECORD_01122, frozenset(), "1a", True, True)
    with pytest.raises(Refusal, match="not in the canonical"):
        check_eligibility("11111", None, frozenset(), "1a", True, False)
    with pytest.raises(Refusal, match="per_skala is \\[\\]"):
        check_eligibility("11111", {**RECORD_01122, "per_skala": []}, frozenset(), "1a", True, False)
    with pytest.raises(Refusal, match="allowlist"):
        check_eligibility("11111", RECORD_01122, frozenset({"11111"}), "1a", True, False)


def test_check_eligibility_refuses_non_oss_issued_under_phase_1a_only():
    non_oss_record = {**RECORD_01122, "per_skala": [{**RECORD_01122["per_skala"][0], "persyaratan": ["Lembaga OSS hanya menerbitkan NIB."]}]}
    with pytest.raises(Refusal, match="non-OSS-issued"):
        check_eligibility("11111", non_oss_record, frozenset(), "1a", True, False)
    # phase 1b would pass this check (module-constant gate is enforced at the CLI, not here)
    rows = check_eligibility("11111", non_oss_record, frozenset(), "1b", True, False)
    assert rows


def test_check_eligibility_passes_a_clean_oss_issued_code():
    rows = check_eligibility("01122", RECORD_01122, frozenset(), "1a", True, False)
    assert rows == RECORD_01122["per_skala"]


# =============================================================================
# §5.2 + §5.7 combined — plan_build, the orchestration function
# =============================================================================


def test_plan_build_s1_s2_builds_licences():
    plan = plan_build("01122", RECORD_01122, frozenset(), "1a", True, False, [], "PENDING_REGULATION", {}, None)
    assert plan.action == "build"
    assert len(plan.groups) == 3
    assert len(plan.targets) == 3


def test_plan_build_s3_writes_nothing_by_default_guilt():
    admitted = [("legacy:1", "Izin Terbang")]  # rendered name != derived
    plan = plan_build("52322", RECORD_01122, frozenset(), "1a", True, False, admitted, "PENDING_REGULATION", {}, None)
    assert plan.action == "skip_s3"
    assert plan.targets == {}


def test_plan_build_s3_relabels_only_on_exact_match_innocence():
    groups_record = RECORD_01122  # 3 groups: NIB, NIB dan Sertifikat Standar x2 -> names {NIB, NIB dan Sertifikat Standar}
    admitted = [("legacy:1", "NIB"), ("legacy:2", "NIB dan Sertifikat Standar")]
    plan = plan_build("90200", groups_record, frozenset(), "1a", True, False, admitted, "PENDING_REGULATION", {}, None)
    assert plan.action == "relabel"
    assert plan.targets == {}


def test_plan_build_refuses_legacy_served():
    admitted = [("legacy:1", "NIB")]
    with pytest.raises(Refusal, match="legacy-served"):
        plan_build("03231", RECORD_01122, frozenset(), "1a", True, False, admitted, "REGULATED", {}, None)


def test_plan_build_cured_second_run_writes_nothing():
    groups = derive_licence_groups("01122", RECORD_01122["per_skala"])
    targets = {target_entity_id("01122", build_node_properties(g)): build_node_properties(g) for g in groups}
    ids = sorted(targets)
    d = digest_of_set(ids)
    marker = {"digest": d}
    plan = plan_build("01122", RECORD_01122, frozenset(), "1a", True, False, [], "REGULATED", targets, marker)
    assert plan.action == "cured"
    assert plan.targets == {}


def test_plan_build_drifted_when_existing_targets_diverge():
    plan = plan_build(
        "01122",
        RECORD_01122,
        frozenset(),
        "1a",
        True,
        False,
        [],
        "REGULATED",
        {"perizinan:pp28v10:01122:stale000001": {"stale": True}},
        {"digest": "stale"},
    )
    assert plan.action == "drifted"


def test_plan_build_ordering_a_placeholder_edge_refuses_even_when_otherwise_eligible():
    with pytest.raises(Refusal, match="placeholder edge"):
        plan_build("01122", RECORD_01122, frozenset(), "1a", True, True, [], "PENDING_REGULATION", {}, None)


# =============================================================================
# Rework 1 (gate review) — CURED/DRIFTED decided BEFORE eligibility (spec §5.2)
# =============================================================================


def test_plan_build_drifted_reported_even_when_missing_from_canonical_guilt():
    """A DRIFTED verdict is read off the graph — it does not need a canonical record."""
    plan = plan_build(
        "01122",
        None,  # missing from canonical entirely
        frozenset(),
        "1a",
        True,
        False,
        [],
        "REGULATED",
        {"perizinan:pp28v10:01122:stale000001": {"stale": True}},
        {"digest": "stale"},
    )
    assert plan.action == "drifted"


def test_plan_build_drifted_reported_even_when_allowlisted_guilt():
    """A DRIFTED verdict is not excused by an allowlist refusal that never gets a chance to fire."""
    plan = plan_build(
        "01122",
        RECORD_01122,
        frozenset({"01122"}),  # would refuse under check_eligibility
        "1a",
        True,
        False,
        [],
        "REGULATED",
        {"perizinan:pp28v10:01122:stale000001": {"stale": True}},
        {"digest": "stale"},
    )
    assert plan.action == "drifted"


def test_plan_build_cured_bypasses_a_would_be_non_oss_refusal_guilt():
    """A CURED code is not re-refused by a phase/issuer check that has nothing to do with its state."""
    non_oss_record = {
        **RECORD_01122,
        "per_skala": [
            {**RECORD_01122["per_skala"][0], "persyaratan": ["Lembaga OSS hanya menerbitkan NIB."]},
            *RECORD_01122["per_skala"][1:],
        ],
    }
    groups = derive_licence_groups("01122", non_oss_record["per_skala"])
    targets = {target_entity_id("01122", build_node_properties(g)): build_node_properties(g) for g in groups}
    ids = sorted(targets)
    d = digest_of_set(ids)
    marker = {"digest": d}
    plan = plan_build("01122", non_oss_record, frozenset(), "1a", True, False, [], "REGULATED", targets, marker)
    assert plan.action == "cured"
    assert plan.targets == {}


def test_plan_build_uncured_allowlisted_code_still_refused_innocence():
    """Innocence: an UNCURED code gets no free pass — the allowlist refusal still fires."""
    with pytest.raises(Refusal, match="allowlist"):
        plan_build("01122", RECORD_01122, frozenset({"01122"}), "1a", True, False, [], "PENDING_REGULATION", {}, None)


# =============================================================================
# Rework 1 (gate review) — relabel writes §5.5 node fields, declared limit on
# `_licensing_cure` (a relabel's targets are LEGACY ids, not pp28v10 ones, so
# the digest-over-derived-ids idempotence check cannot classify it CURED)
# =============================================================================


def test_plan_build_relabelled_code_second_run_classifies_legacy_served_and_refuses():
    """A relabelled S3 code writes `licensing_status=REGULATED`; a rerun sees
    admitted>=1 + REGULATED (legacy-served) and refuses — 0 further writes,
    since no pp28v10 targets exist on the graph to be classified CURED."""
    admitted = [("legacy:1", "NIB"), ("legacy:2", "NIB dan Sertifikat Standar")]
    with pytest.raises(Refusal, match="legacy-served"):
        plan_build("90200", RECORD_01122, frozenset(), "1a", True, False, admitted, "REGULATED", {}, None)


assert isinstance(BuildPlan, type)  # imported for type-checking clarity in this module
assert SCALE_ORDER == ("Mikro", "Kecil", "Menengah", "Besar")
