from backend.scripts.kg_kbli_license_fix import plan_fix


def _kg_row(description: str, properties: dict) -> dict:
    return {"description": description, "properties": properties}


def test_68112_style_collision_deletes_edges_and_syncs_uraian_and_note():
    """The exact 68112 pattern: per_skala == [], properties.uraian carries
    subgroup bleed the description column already dropped, canonical record
    has a _data_note explaining the collision."""
    record = {
        "kode_kbli_2025": "68112",
        "uraian": "Kelompok ini mencakup penyewaan dan pengoperasian real estat hunian milik sendiri atau sewa.",
        "per_skala": [],
        "_data_note": "KBLI 2025 code 68112 = residential leasing. OSS 404. See KBLI 68111.",
    }
    kg_row = _kg_row(
        description="Kelompok ini mencakup penyewaan dan pengoperasian real estat hunian milik sendiri atau sewa.",
        properties={
            "uraian": "Kelompok ini mencakup penyewaan dan pengoperasian real estat hunian milik sendiri atau sewa. 6812 AKTIVITAS REAL ESTAT ... nonhunian",
            "pma_status": "TERBUKA",
        },
    )

    plan = plan_fix("68112", record, kg_row)

    assert plan.per_skala_empty is True
    assert plan.delete_perizinan_edges is True
    assert plan.update_node is True
    assert plan.new_description == record["uraian"]
    assert plan.new_properties["uraian"] == record["uraian"]
    assert plan.new_properties["_data_note"] == record["_data_note"]
    assert plan.new_properties["pma_status"] == "TERBUKA"  # untouched fields preserved
    assert plan.skip_reason is None


def test_non_empty_per_skala_never_deletes_edges_even_if_uraian_drifted():
    """A code with real per-code licensing (per_skala non-empty) must NEVER
    have its REQUIRES edges touched by this script — no generic derivation
    path exists yet for that case."""
    record = {
        "kode_kbli_2025": "56101",
        "uraian": "Aktivitas penyediaan makanan.",
        "per_skala": [{"skala_usaha": ["Menengah"], "kategori_risiko": "Menengah Rendah"}],
    }
    kg_row = _kg_row(
        description="Aktivitas penyediaan makanan.",
        properties={"uraian": "Aktivitas penyediaan makanan DAN minuman keliling."},
    )

    plan = plan_fix("56101", record, kg_row)

    assert plan.per_skala_empty is False
    assert plan.delete_perizinan_edges is False
    # uraian still gets corrected independently of the licensing decision
    assert plan.update_node is True
    assert plan.new_properties["uraian"] == "Aktivitas penyediaan makanan."
    assert "_data_note" not in plan.new_properties
    assert plan.skip_reason == "per_skala non-empty — no generic derivation path"


def test_missing_per_skala_key_treated_as_non_empty_conservative():
    """per_skala absent from the canonical record (None, not an explicit []):
    must NOT be treated as the empty-list license-wipe signal."""
    record = {"kode_kbli_2025": "12345", "uraian": "Some description."}
    kg_row = _kg_row(description="Some description.", properties={})

    plan = plan_fix("12345", record, kg_row)

    assert plan.per_skala_empty is False
    assert plan.delete_perizinan_edges is False


def test_nothing_to_do_when_already_clean():
    record = {"kode_kbli_2025": "99999", "uraian": "Clean text.", "per_skala": []}
    kg_row = _kg_row(description="Clean text.", properties={"uraian": "Clean text."})

    plan = plan_fix("99999", record, kg_row)

    assert plan.delete_perizinan_edges is True  # per_skala empty -> still wipe stale edges
    assert plan.update_node is False  # but nothing to write on the node itself
    assert plan.new_properties is None


def test_code_not_in_canonical_dataset_is_skipped():
    plan = plan_fix("00000", None, _kg_row("x", {}))
    assert plan.skip_reason == "not in canonical dataset"
    assert plan.delete_perizinan_edges is False
    assert plan.update_node is False


def test_code_not_in_kg_is_skipped():
    record = {"kode_kbli_2025": "68112", "uraian": "x", "per_skala": []}
    plan = plan_fix("68112", record, None)
    assert plan.skip_reason == "not in KG (kg_nodes)"
    assert plan.found_in_kg is False
