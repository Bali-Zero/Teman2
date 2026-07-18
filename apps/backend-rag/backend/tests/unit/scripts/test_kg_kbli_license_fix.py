"""Unit tests for kg_kbli_license_fix.py's `plan_fix` — pure decision logic.

No DB, no network — `plan_fix` takes the canonical record + current KG node
+ current REQUIRES edge targets as plain dicts/lists and returns a
`LicenseFixPlan`. These tests pin the GARUDA-FILIERA Fase 1 8-code cure
behavior AND the specific bug this version fixes: the first draft of the
script deleted only `perizinan:%`-prefixed REQUIRES edges, missing
bare-name targets (e.g. an aviation certificate wrongly attached to a
space-transport code) and `license:*` edges. See the module docstring in
`backend/scripts/kg_kbli_license_fix.py` for the full incident writeup.
"""

from __future__ import annotations

from backend.scripts.kg_kbli_license_fix import LicenseFixPlan, plan_fix

# A trimmed canonical record shape post Fase-1 cure (per_skala -> []) — one
# of the 8 codes (51103, space-passenger transport) whose license block was
# a false-friend collision with an unrelated aviation activity.
CANONICAL_CURED = {
    "kode_kbli_2025": "51103",
    "uraian": "Angkutan udara untuk penumpang antar ruang angkasa.",
    "per_skala": [],
    "_data_note": "51103: aviation licensing on space-passenger transport — code-number "
    "collision, corrected 2026-07-17, image-verified.",
}

# The stale KG node — properties.uraian and description still carry the
# pre-cure text, and the licensing edges include a MIX of target-id shapes:
# perizinan:*, license:*, and a bare-name node — the exact shape the first
# draft's `perizinan:%`-only DELETE would have partially missed.
KG_ROW_STALE = {
    "description": "Angkutan udara luar angkasa berjadwal untuk penumpang.",
    "properties": {
        "uraian": "Angkutan udara luar angkasa berjadwal untuk penumpang.",
        "pma_status": "TERBUKA",
    },
}

MIXED_TARGETS = [
    "perizinan:nib_berbasis_risiko",
    "license:sertifikat_standar",
    "sertifikat_operator_pesawat_udara_aoc",  # bare-name, no prefix — the bug this version fixes
]


def test_guilty_per_skala_empty_deletes_all_requires_and_archives_every_target():
    plan = plan_fix("51103", CANONICAL_CURED, KG_ROW_STALE, MIXED_TARGETS)

    assert plan.per_skala_empty is True
    assert plan.delete_all_requires is True
    # THE regression this version exists for: every target prefix is
    # captured, not just perizinan:% — bare-name and license:* included.
    assert plan.disputed_requires == MIXED_TARGETS
    assert "sertifikat_operator_pesawat_udara_aoc" in plan.disputed_requires
    assert "license:sertifikat_standar" in plan.disputed_requires
    assert plan.update_node is True
    assert plan.new_properties["_disputed_requires"] == MIXED_TARGETS
    assert plan.new_properties["uraian"] == CANONICAL_CURED["uraian"]
    assert plan.new_properties["_data_note"] == CANONICAL_CURED["_data_note"]
    assert plan.new_description == CANONICAL_CURED["uraian"]
    # untouched fields survive the merge
    assert plan.new_properties["pma_status"] == "TERBUKA"
    assert plan.skip_reason is None
    # class-cure (2026-07-18): the node has no licensing_status key at all —
    # the cure writes PENDING_REGULATION so the router stops defaulting to
    # "REGULATED" on a freshly-declared honest gap.
    assert plan.new_properties["licensing_status"] == "PENDING_REGULATION"
    assert plan.licensing_status_note == "licensing_status: missing -> PENDING_REGULATION"


def test_guilty_with_no_current_edges_still_marks_delete_all_requires_but_no_archive():
    """per_skala==[] always means 'delete all REQUIRES edges if any exist' —
    even with zero current edges, the plan still reflects that decision so a
    caller doesn't need special-casing; but there is nothing to archive."""
    plan = plan_fix("51103", CANONICAL_CURED, KG_ROW_STALE, [])

    assert plan.delete_all_requires is True
    assert plan.disputed_requires == []
    # uraian/description still drifted, so update happens, but without a
    # _disputed_requires key (nothing to archive this run).
    assert plan.update_node is True
    assert "_disputed_requires" not in plan.new_properties
    # licensing_status is still written even with zero edges to archive —
    # it is gated on delete_all_requires (the per_skala verdict), not on
    # whether this particular run found edges to delete.
    assert plan.new_properties["licensing_status"] == "PENDING_REGULATION"


def test_idempotent_rerun_after_edges_already_deleted_does_not_touch_prior_archive():
    """Second run: edges are already gone (current_requires_targets=[]) and
    the node was already fully synced by a prior run, including a
    _disputed_requires archive AND a licensing_status=PENDING_REGULATION
    write from that run. Must be a total no-op — critically, must NOT
    overwrite/blank the existing archive, and the licensing_status
    re-write must be declared a no-op, not silently skipped."""
    already_synced_row = {
        "description": CANONICAL_CURED["uraian"],
        "properties": {
            "uraian": CANONICAL_CURED["uraian"],
            "pma_status": "TERBUKA",
            "_data_note": CANONICAL_CURED["_data_note"],
            "_disputed_requires": MIXED_TARGETS,  # archived by the first run
            "licensing_status": "PENDING_REGULATION",  # written by the first run
        },
    }

    plan = plan_fix("51103", CANONICAL_CURED, already_synced_row, [])

    assert plan.delete_all_requires is True  # still the right decision, just nothing to do
    assert plan.disputed_requires == []
    assert plan.update_node is False
    assert plan.new_properties is None
    assert plan.new_description is None
    assert plan.licensing_status_note == "licensing_status already PENDING_REGULATION (no-op)"


def test_innocent_per_skala_non_empty_refuses_edge_deletion():
    record = dict(CANONICAL_CURED, per_skala=[{"skala_usaha": ["Menengah"]}])

    plan = plan_fix("51103", record, KG_ROW_STALE, MIXED_TARGETS)

    assert plan.per_skala_empty is False
    assert plan.delete_all_requires is False
    assert plan.disputed_requires == []
    assert plan.skip_reason is not None and "non-empty" in plan.skip_reason
    # text sync is independent of the licensing decision and still proceeds
    assert plan.update_node is True
    assert plan.new_properties is not None
    assert "_disputed_requires" not in plan.new_properties
    # NOT a cure (per_skala non-empty) — licensing_status is never touched,
    # even though the text sync happens.
    assert plan.licensing_status_note is None
    assert "licensing_status" not in plan.new_properties


def test_innocent_per_skala_non_empty_leaves_existing_licensing_status_untouched():
    """A code that is NOT a detached/cured gap (per_skala non-empty) may
    already carry its OWN licensing_status (e.g. a legacy "REGULATED" value
    unrelated to this cure) — the class-cure only ever writes
    PENDING_REGULATION for per_skala==[] codes; a non-detached code's
    existing value must survive the merge byte-for-byte."""
    record = dict(CANONICAL_CURED, per_skala=[{"skala_usaha": ["Menengah"]}])
    row = {
        "description": KG_ROW_STALE["description"],
        "properties": dict(KG_ROW_STALE["properties"], licensing_status="REGULATED"),
    }

    plan = plan_fix("51103", record, row, MIXED_TARGETS)

    assert plan.delete_all_requires is False
    assert plan.licensing_status_note is None
    assert plan.new_properties["licensing_status"] == "REGULATED"


def test_innocent_per_skala_key_entirely_absent_treated_as_non_empty():
    record = {k: v for k, v in CANONICAL_CURED.items() if k != "per_skala"}

    plan = plan_fix("51103", record, KG_ROW_STALE, MIXED_TARGETS)

    assert plan.delete_all_requires is False
    assert plan.skip_reason is not None and "non-empty" in plan.skip_reason
    assert plan.licensing_status_note is None


def test_innocent_already_clean_node_is_full_noop_except_edge_flag():
    clean_row = {
        "description": CANONICAL_CURED["uraian"],
        "properties": {
            "uraian": CANONICAL_CURED["uraian"],
            "_data_note": CANONICAL_CURED["_data_note"],
            "licensing_status": "PENDING_REGULATION",
        },
    }

    plan = plan_fix("51103", CANONICAL_CURED, clean_row, [])

    assert plan.update_node is False
    assert plan.new_properties is None
    assert plan.new_description is None
    assert plan.delete_all_requires is True  # still checked/attempted, idempotent — no edges exist
    assert plan.licensing_status_note == "licensing_status already PENDING_REGULATION (no-op)"


def test_skip_code_missing_from_canonical_dataset():
    plan = plan_fix("99999", None, KG_ROW_STALE, MIXED_TARGETS)

    assert plan.skip_reason == "not in canonical dataset"
    assert plan.update_node is False
    assert plan.delete_all_requires is False
    assert plan.disputed_requires == []
    assert plan.found_in_kg is True  # kg_row was provided, even though canonical lookup failed


def test_skip_code_missing_from_kg():
    plan = plan_fix("51103", CANONICAL_CURED, None, MIXED_TARGETS)

    assert plan.skip_reason == "not in KG (kg_nodes)"
    assert plan.found_in_kg is False
    assert plan.delete_all_requires is False


def test_default_current_requires_targets_is_treated_as_no_archive():
    """Caller can omit the 4th arg entirely (e.g. a dry-run with no DB
    access) — must not crash, must behave like an empty list."""
    plan = plan_fix("51103", CANONICAL_CURED, KG_ROW_STALE)

    assert plan.delete_all_requires is True
    assert plan.disputed_requires == []


def test_never_writes_null_description_when_only_properties_drifted():
    """Regression guard mirroring the sibling kg_fix_68112_node.py cure: if
    update_node is True purely because properties changed (canonical uraian
    empty/blank) new_description must fall back to the CURRENT description,
    never None — binding NULL would wipe out a perfectly good column."""
    record = dict(CANONICAL_CURED, uraian="", _data_note="a brand new note that changes properties")
    already_uraian_synced_row = {
        "description": "existing good description",
        "properties": {"uraian": "existing good description"},
    }

    plan = plan_fix("51103", record, already_uraian_synced_row, [])

    assert plan.update_node is True  # _data_note changed
    assert plan.new_description == "existing good description"
    assert plan.new_description is not None


def test_plan_is_dataclass_instance():
    plan = plan_fix("51103", CANONICAL_CURED, KG_ROW_STALE, [])
    assert isinstance(plan, LicenseFixPlan)
