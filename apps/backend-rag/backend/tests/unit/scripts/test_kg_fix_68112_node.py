"""Unit tests for kg_fix_68112_node.py's pure planning/verification functions.

No DB, no network — these exercise plan_main_node_fix / plan_shadow_node_fix /
verify_node_clean directly. The "before" fixtures below are the ACTUAL stale
shapes read live from Postgres (dev instance, 2026-07-17, via
mcp__postgres-nuzantara-local__query) during this cure's investigation, not
synthetic guesses — see research/operations/2026-07-17-kbli-68112-node-cure.md.

Several tests below (marked "Codex red-team regression") were added AFTER an
adversarial review (Codex GPT-5.6-sol, read-only, 2026-07-17) found concrete
bugs in the first draft that the ORIGINAL test suite did not catch because it
tested each piece in isolation rather than the actual end-to-end combined
shape. Kept as permanent regressions, not deleted once fixed.
"""

from __future__ import annotations

from backend.scripts.kg_fix_68112_node import (
    CANONICAL_ENTITY_ID,
    SHADOW_DATA_NOTE,
    SHADOW_DEPRECATION_NOTICE,
    SHADOW_ENTITY_ID,
    plan_main_node_fix,
    plan_shadow_node_fix,
    verify_main_node_matches_canonical,
    verify_node_clean,
    verify_shadow_node_deprecated,
)

# Trimmed canonical record shape (post-#2508/#2527 fix) — mirrors the real
# fields plan_main_node_fix reads, values shortened but the STALE-text
# markers kept verbatim so the "gets cleaned" assertions are meaningful.
CANONICAL_RECORD_FIXED = {
    "kode_kbli_2025": "68112",
    "uraian": "Kelompok ini mencakup penyewaan dan pengoperasian real estat hunian milik sendiri atau sewa.",
    "per_skala": [],
    "_data_note": (
        "KBLI 2025 code 68112 = residential leasing (BPS Peraturan 7/2025). "
        "... code-number collision ... corrected 2026-07-16, image-verified."
    ),
    "intel_2026": {
        "whatItMeans": "Renting out residential property you own or lease.",
        "whatYouNeed": (
            "**Registration:** ... The risk level and standard certificate shown here "
            "previously were a code-number collision — they belonged to a different "
            "activity, MICE-venue rental, which does not apply to residential leasing."
        ),
        "baliContext": "Long-term residential rental in Bali is a growing market.",
        "whatChanged": "Unchanged from KBLI 2020 — direct match (MATCH_LANGSUNG).",
        "zantaraOpener": "Renting out residential property in Bali? 68112 is your code.",
    },
}

# The ACTUAL stale kg_nodes row observed live (dev, 2026-07-17) — properties.uraian
# bleeds into the unrelated 6812 subgroup, properties.whatYouNeed is the
# pre-#2508 MICE self-assessment text.
KG_ROW_STALE = {
    "description": "AKTIVITAS PENYEWAAN BANGUNAN DAN LAHAN HUNIAN MILIK SENDIRI ATAU SEWA",
    "properties": {
        "kode": "68112",
        "uraian": (
            "Kelompok ini mencakup penyewaan dan pengoperasian real estat hunian milik "
            "sendiri atau sewa. 6812 AKTIVITAS REAL ESTAT (BANGUNAN DAN LAHAN) NONHUNIAN "
            "MILIK SENDIRI ATAU SEWA Subgolongan ini mencakup ..."
        ),
        "pma_status": "TERBUKA",
        "whatItMeans": "Renting out residential property you own or lease.",
        "whatYouNeed": (
            "**All scales (Micro through Large)**: Medium-Low risk. NIB + Standard "
            "Certificate issued automatically. PMA businesses need an LSPr-certified "
            "standard. Self-Assessment document covering MICE venue standards "
            "(facilities, organization, HR) is referenced in the obligations.\n\n"
            "**PMA:** Fully open — 100% foreign ownership."
        ),
        "baliContext": "Long-term residential rental in Bali is a growing market.",
        "kategori_risiko": "Menengah Rendah",
        "licensing_status": "REGULATED",
    },
}


def test_main_node_stale_uraian_and_whatyouneed_gets_fixed_and_edges_deleted():
    plan = plan_main_node_fix(CANONICAL_RECORD_FIXED, KG_ROW_STALE)

    assert plan.entity_id == CANONICAL_ENTITY_ID
    assert plan.exists is True
    assert plan.update_node is True
    assert plan.delete_requires_perizinan_edges is True
    assert plan.skip_reason is None
    assert plan.new_properties["uraian"] == CANONICAL_RECORD_FIXED["uraian"]
    assert "MICE" not in plan.new_properties["whatYouNeed"] or "code-number collision" in plan.new_properties["whatYouNeed"].lower()
    assert plan.new_properties["whatYouNeed"] == CANONICAL_RECORD_FIXED["intel_2026"]["whatYouNeed"]
    # untouched fields survive the merge
    assert plan.new_properties["pma_status"] == "TERBUKA"
    assert plan.new_properties["kategori_risiko"] == "Menengah Rendah"
    assert plan.new_properties["licensing_status"] == "REGULATED"
    assert plan.new_properties["_data_note"] == CANONICAL_RECORD_FIXED["_data_note"]


def test_main_node_non_empty_per_skala_refuses_edge_deletion_but_still_syncs_properties():
    """Defensive regression guard: if the canonical dataset ever regresses
    68112's per_skala to non-empty, this script must NEVER delete edges on
    a stale/unverified assumption — but property text sync (uraian/intel)
    is independent of the licensing decision and should still proceed."""
    record = dict(CANONICAL_RECORD_FIXED, per_skala=[{"skala_usaha": ["Menengah"]}])

    plan = plan_main_node_fix(record, KG_ROW_STALE)

    assert plan.delete_requires_perizinan_edges is False
    assert plan.skip_reason is not None and "non-empty" in plan.skip_reason
    assert plan.update_node is True  # uraian/whatYouNeed still drifted
    assert plan.new_properties["uraian"] == record["uraian"]


def test_main_node_already_clean_is_noop_on_properties_but_edges_still_flagged():
    """A node already carrying the corrected text plans no property write,
    but per_skala==[] still means 'delete REQUIRES->perizinan edges if any
    exist' — that check is edge-state-driven, not property-staleness-driven."""
    clean_row = {
        "description": CANONICAL_RECORD_FIXED["uraian"],
        "properties": {
            "uraian": CANONICAL_RECORD_FIXED["uraian"],
            **CANONICAL_RECORD_FIXED["intel_2026"],
            "_data_note": CANONICAL_RECORD_FIXED["_data_note"],
        },
    }

    plan = plan_main_node_fix(CANONICAL_RECORD_FIXED, clean_row)

    assert plan.update_node is False
    assert plan.new_properties is None
    assert plan.new_description is None
    assert plan.delete_requires_perizinan_edges is True  # still checked/attempted, idempotent if none exist


def test_main_node_missing_from_canonical_dataset_is_skipped():
    plan = plan_main_node_fix(None, KG_ROW_STALE)
    assert plan.skip_reason == "canonical dataset fetch/parse returned no 68112 record"
    assert plan.update_node is False
    assert plan.delete_requires_perizinan_edges is False


def test_main_node_missing_from_kg_is_skipped():
    plan = plan_main_node_fix(CANONICAL_RECORD_FIXED, None)
    assert plan.exists is False
    assert plan.skip_reason == "kbli:68112 not present in this kg_nodes table"


def test_shadow_node_gets_neutralized():
    stale_shadow_row = {
        "description": "Penyewaan Venue Penyelenggaraan Aktifitas MICE dan Event Khusus",
        "properties": {},
    }

    plan = plan_shadow_node_fix(stale_shadow_row)

    assert plan.entity_id == SHADOW_ENTITY_ID
    assert plan.exists is True
    assert plan.update_node is True
    assert plan.new_description == SHADOW_DEPRECATION_NOTICE
    assert plan.new_properties["_deprecated"] is True
    assert plan.new_properties["_superseded_by"] == CANONICAL_ENTITY_ID
    assert "_data_note" in plan.new_properties


def test_shadow_node_already_deprecated_is_noop():
    already_done_row = {
        "description": SHADOW_DEPRECATION_NOTICE,
        "properties": {"_deprecated": True, "_superseded_by": CANONICAL_ENTITY_ID, "_data_note": "x"},
    }

    plan = plan_shadow_node_fix(already_done_row)

    assert plan.update_node is False
    assert plan.new_description is None
    assert plan.new_properties is None


def test_shadow_node_absent_is_a_noop():
    plan = plan_shadow_node_fix(None)
    assert plan.exists is False
    assert plan.update_node is False


def test_verify_node_clean_detects_bare_mice_with_no_disclaimer():
    problems = verify_node_clean(
        "some description",
        {"whatYouNeed": "Self-Assessment document covering MICE venue standards is required."},
    )
    assert len(problems) == 1
    assert "whatYouNeed" in problems[0]


def test_verify_node_clean_allows_disclaimed_mice_mention():
    problems = verify_node_clean(
        "some description",
        {
            "whatYouNeed": (
                "The MICE venue standards previously shown were a code-number "
                "collision and do not apply here."
            )
        },
    )
    assert problems == []


def test_verify_node_clean_walks_nested_properties_and_reports_path():
    problems = verify_node_clean(
        "clean",
        {"nested": {"list": ["fine", "This MICE requirement applies to you."]}},
    )
    assert len(problems) == 1
    assert "nested.list[1]" in problems[0]


def test_verify_node_clean_passes_when_actually_clean():
    problems = verify_node_clean(
        CANONICAL_RECORD_FIXED["uraian"],
        {"uraian": CANONICAL_RECORD_FIXED["uraian"], "pma_status": "TERBUKA"},
    )
    assert problems == []


def test_verify_node_clean_passes_on_shadow_deprecation_notice():
    """The deprecation notice ITSELF names 'MICE' while disclaiming it —
    must not flag itself as contaminated (regression guard for the shadow
    node's own cure)."""
    problems = verify_node_clean(SHADOW_DEPRECATION_NOTICE, {})
    assert problems == []


# ============================================================================
# Codex red-team regressions (2026-07-17) — each test below pins a bug the
# adversarial review found in the first draft, using the EXACT combined
# real-world shape (not an isolated piece) so the class of bug can't
# silently return.
# ============================================================================


def test_shadow_data_note_itself_passes_verify_node_clean():
    """BUG (found live): SHADOW_DATA_NOTE originally read
    'code-number-collision' (extra hyphen) while DISCLAIMER_MARKER is
    'code-number collision' (space) — the two strings did not match, so
    verify_node_clean flagged the shadow node's OWN cure text as still
    contaminated, and --apply could never converge to a clean verification.
    This test walks the exact plan_shadow_node_fix() OUTPUT (description +
    properties together, the shape run_verification actually re-reads),
    not the description alone — the original test suite only checked the
    description in isolation and missed this."""
    plan = plan_shadow_node_fix({"description": "old MICE text", "properties": {}})
    problems = verify_node_clean(plan.new_description, plan.new_properties)
    assert problems == [], f"shadow node's own cure text fails its own guard: {problems}"
    # Guard the exact string too, so a future edit re-typo'ing the hyphen
    # fails loudly at the source instead of only downstream.
    assert "code-number collision" in SHADOW_DATA_NOTE.lower()


def test_main_node_empty_canonical_uraian_never_writes_null_description():
    """BUG (found live): when update_node was True for a properties-only
    change (e.g. only whatYouNeed drifted) while canonical uraian happened
    to be empty/missing, new_description computed to None — which the SQL
    layer binds as NULL, wiping out a perfectly good existing description.
    new_description must fall back to the CURRENT description instead."""
    record = dict(CANONICAL_RECORD_FIXED, uraian="")
    plan = plan_main_node_fix(record, KG_ROW_STALE)

    assert plan.update_node is True  # whatYouNeed still drifted
    assert plan.new_description == KG_ROW_STALE["description"]
    assert plan.new_description is not None


def test_main_node_per_skala_key_entirely_absent_is_treated_as_non_empty():
    """Regression: `per_skala` missing from the record entirely (not present
    as a key at all) must be treated the same as non-empty — i.e. refuse to
    delete edges — never conflated with an explicit `[]`."""
    record = {k: v for k, v in CANONICAL_RECORD_FIXED.items() if k != "per_skala"}
    plan = plan_main_node_fix(record, KG_ROW_STALE)

    assert plan.delete_requires_perizinan_edges is False
    assert plan.skip_reason is not None and "non-empty" in plan.skip_reason


def test_main_node_handles_none_properties_directly():
    """Defense in depth: even if a caller bypasses the DB-read helper's own
    `props or {}` normalization and passes properties=None directly, the
    pure planning function must not crash and must treat it as empty."""
    kg_row_none_props = {"description": "old", "properties": None}
    plan = plan_main_node_fix(CANONICAL_RECORD_FIXED, kg_row_none_props)

    assert plan.update_node is True
    assert plan.new_properties["uraian"] == CANONICAL_RECORD_FIXED["uraian"]


def test_verify_main_node_matches_canonical_catches_subgroup_bleed_even_without_mice_markers():
    """BUG-CLASS (found live): the properties.uraian subgroup-bleed
    contamination ('...6812 AKTIVITAS REAL ESTAT ... NONHUNIAN...') contains
    NEITHER 'MICE' nor 'Venue' — verify_node_clean's marker scan alone would
    never catch it. verify_main_node_matches_canonical must."""
    problems = verify_main_node_matches_canonical(CANONICAL_RECORD_FIXED, KG_ROW_STALE)
    assert any("properties.uraian" in p for p in problems)
    assert any("description" in p for p in problems) or KG_ROW_STALE["description"] == CANONICAL_RECORD_FIXED["uraian"]


def test_verify_main_node_matches_canonical_passes_once_fixed():
    fixed_row = {
        "description": CANONICAL_RECORD_FIXED["uraian"],
        "properties": {
            "uraian": CANONICAL_RECORD_FIXED["uraian"],
            **CANONICAL_RECORD_FIXED["intel_2026"],
        },
    }
    assert verify_main_node_matches_canonical(CANONICAL_RECORD_FIXED, fixed_row) == []


def test_verify_shadow_node_deprecated_fails_on_neutral_but_untagged_text():
    """BUG (found live): a shadow row with harmless (non-MICE) text but
    WITHOUT the _deprecated/_superseded_by markers would pass
    verify_node_clean's marker scan yet was never actually confirmed
    retired. verify_shadow_node_deprecated must catch this independently."""
    almost_right_but_untagged = {"description": "some neutral text", "properties": {}}
    problems = verify_shadow_node_deprecated(almost_right_but_untagged)
    assert len(problems) == 3  # description mismatch + both markers missing


def test_verify_shadow_node_deprecated_passes_on_correctly_neutralized_row():
    plan = plan_shadow_node_fix({"description": "old MICE text", "properties": {}})
    correctly_neutralized = {"description": plan.new_description, "properties": plan.new_properties}
    assert verify_shadow_node_deprecated(correctly_neutralized) == []
