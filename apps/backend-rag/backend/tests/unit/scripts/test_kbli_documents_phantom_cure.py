"""Unit tests for kbli_documents_phantom_cure.py — pure decision/render logic.

No DB, no network: `plan_phantom_cure`, `find_successors`, `same_group_codes`,
`build_phantom_content`, `build_phantom_metadata`, `phantom_codes` and
`archive_params` take plain dicts/lists and return plain dicts/dataclasses.

These pin the phantom-row cure (2026-07-24): `kbli_documents` is a strict
superset of the canonical KBLI 2025 catalogue, and the extra rows are KBLI 2020
codes whose 2020 licensing payload `chat_kbli` was injecting verbatim as
current guidance (see the module docstring for the two live prod proofs).

Guilt/innocence corpus (scar #3 discipline — a guard ships only with BOTH):

  - GUILT: a genuinely phantom code (in the table, absent from canonical) is
    cured — its 2020 licensing/PMA payload leaves every key a consumer reads,
    and the rendered content says the code is not in the 2025 catalogue.
  - INNOCENCE: a code that IS in the canonical catalogue is REFUSED even when
    it also sits in the table. That is `kbli_documents_cure.py`'s jurisdiction,
    and a phantom cure applied to a live code would destroy good licensing
    data. This is the exact over-match failure mode superscar #3 catalogues.
  - INNOCENCE (successors): `find_successors` reads ONLY the canonical
    crosswalk fields. A 2025 record that merely *starts with the same digits*
    is NOT a successor and must not be reported as one — otherwise the cure
    would manufacture a crosswalk the dataset never asserted (rule #9).
  - GUILT (no-successor branch): when the crosswalk yields nothing, the
    content must say so plainly, and any same-group listing must be fenced as
    non-certified — never rendered under the "menggantikan" (replaces) claim.
"""

from __future__ import annotations

import pytest

from backend.scripts.kbli_documents_phantom_cure import (
    KBLI_2025_STATUS,
    LICENSING_STATUS,
    ROUTER_PMA_FALLBACK,
    VINTAGE_SUFFIX,
    archive_params,
    build_phantom_content,
    build_phantom_metadata,
    canonical_codes,
    find_successors,
    phantom_codes,
    plan_phantom_cure,
    same_group_codes,
    validate_dataset,
)

# --- fixtures: a miniature canonical catalogue -----------------------------
# 82921/82922 declare 82920 as their KBLI 2020 ancestor (the real crosswalk
# shape). 82999 shares the "829" prefix but declares a DIFFERENT ancestor —
# it is the innocence probe for prefix-inference.
# 39002 is the REAL weak auto-match in the live dataset: carbon storage linked
# to packaging at 71%. It is the reason mapping_note must reach the reader.
CANONICAL = [
    {
        "kode_kbli_2025": "82921",
        "judul": "Aktivitas Pengepakan Bahan dan Produk Hasil Pertanian",
        "kbli_2020_source": "82920",
        "pp28_sources": ["82920"],
        "mapping_note": "Agent mapping: 82920 (Aktivitas Pengepakan...) [high]",
        "per_skala": [{"skala_usaha": ["Kecil"], "kategori_risiko": "Menengah Rendah"}],
    },
    {
        "kode_kbli_2025": "39002",
        "judul": "Aktivitas Penyimpanan Karbon",
        "kbli_2020_source": "82920",
        "pp28_sources": ["82920"],
        "mapping_note": "Auto-matched to 82920 (Aktivitas Pengepakan...) score=71%",
        "per_skala": [],
    },
    {
        "kode_kbli_2025": "82922",
        "judul": "Aktivitas Pengepakan Bahan dan Produk Makanan dan Minuman Olahan",
        "kbli_2020_source": "82920",
        "pp28_sources": ["82920"],
        "per_skala": [],
    },
    {
        "kode_kbli_2025": "82999",
        "judul": "Aktivitas Jasa Penunjang Usaha Lainnya YTDL",
        "kbli_2020_source": "82990",
        "pp28_sources": ["82990"],
        "per_skala": [],
    },
    {
        "kode_kbli_2025": "85599",
        "judul": "Pendidikan Lainnya Swasta",
        "kbli_2020_source": "85599",
        "pp28_sources": ["85599"],
        "per_skala": [],
    },
]

# The pre-cure phantom row as it actually sits in prod: full 2020 payload.
PHANTOM_ROW_82920 = {
    "judul": "AKTIVITAS PENGEMASAN",
    "content": "# KBLI 82920\n\nRisiko: Menengah Tinggi. Perizinan: NIB dan Izin.\n",
    "metadata": {
        "judul": "AKTIVITAS PENGEMASAN",
        "kode_kbli_2025": "82920",  # the seed's own false claim: a 2020 code in a 2025 field
        "sektor_id": "I.F.h",
        "pma_status": "TERBUKA",
        "per_skala": [
            {
                "skala_usaha": ["Besar"],
                "kategori_risiko": "Tinggi",
                "perizinan": "NIB dan Izin",
                "kewenangan": "Gubernur",
            }
        ],
    },
    "created_at": None,
    "updated_at": None,
}

PHANTOM_ROW_85598 = {
    "judul": "JASA PENDIDIKAN SWASTA LAINNYA YTDL",
    "content": "# KBLI 85598\n\nRisiko: Rendah.\n",
    "metadata": {"pma_status": "TERBUKA", "per_skala": [{"kategori_risiko": "Rendah"}]},
    "created_at": None,
    "updated_at": None,
}


def _canon() -> set[str]:
    return canonical_codes(CANONICAL)


# --- census ----------------------------------------------------------------


def test_phantom_codes_is_the_table_minus_the_catalogue():
    table = ["82921", "82922", "82999", "85599", "82920", "85598"]
    assert phantom_codes(CANONICAL, table) == ["82920", "85598"]


def test_phantom_codes_empty_when_table_is_a_subset():
    assert phantom_codes(CANONICAL, ["82921", "85599"]) == []


# --- successors: provenance-bound, never inferred --------------------------


def test_find_successors_reads_the_crosswalk_fields():
    succ = find_successors(CANONICAL, "82920")
    assert [s.code for s in succ] == ["39002", "82921", "82922"]
    assert all(s.via == "kbli_2020_source" for s in succ)


def test_weak_automatch_is_kept_but_carries_its_provenance():
    """A 71%-confidence auto-match linking carbon storage to packaging must
    neither be silently dropped (a display cap — W97) nor presented bare. It
    survives WITH its mapping_note so the reader can weigh it."""
    succ = {s.code: s for s in find_successors(CANONICAL, "82920")}
    assert "39002" in succ
    assert "score=71%" in succ["39002"].mapping_note


def test_find_successors_ignores_prefix_lookalikes():
    """INNOCENCE: 82999 starts with '829' but declares ancestor 82990, so it is
    NOT a successor of 82920. A prefix-based implementation would wrongly
    include it and manufacture a crosswalk the dataset never asserted."""
    assert "82999" not in [s.code for s in find_successors(CANONICAL, "82920")]


def test_find_successors_returns_empty_rather_than_guessing():
    assert find_successors(CANONICAL, "85598") == []


def test_same_group_is_labelled_non_certified():
    group = same_group_codes(CANONICAL, "85598")
    assert [s.code for s in group] == ["85599"]
    assert all(s.via == "same_group_not_certified" for s in group)


# --- INNOCENCE: a canonical code is refused --------------------------------


def test_canonical_code_is_refused_even_when_present_in_the_table():
    """A live 2025 code must never be run through the phantom cure — doing so
    would strip real licensing data. The refusal happens before any content is
    built, so nothing is computed for it either."""
    plan = plan_phantom_cure("82921", CANONICAL, _canon(), PHANTOM_ROW_82920)
    assert plan.update_row is False
    assert plan.in_canonical is True
    assert plan.new_content is None
    assert plan.new_metadata is None
    assert "IS in the canonical" in (plan.skip_reason or "")


def test_code_absent_from_table_is_a_declared_skip():
    plan = plan_phantom_cure("99999", CANONICAL, _canon(), None)
    assert plan.update_row is False
    assert plan.skip_reason == "not in kbli_documents table"


# --- GUILT: the phantom row is actually cured ------------------------------


def test_phantom_row_loses_its_2020_licensing_payload():
    plan = plan_phantom_cure("82920", CANONICAL, _canon(), PHANTOM_ROW_82920)
    assert plan.update_row is True
    meta = plan.new_metadata
    assert meta is not None
    # Every key a consumer reads is neutralised...
    assert meta["per_skala"] == []
    assert meta["pma_status"] == ROUTER_PMA_FALLBACK
    assert meta["kbli_2025_status"] == KBLI_2025_STATUS
    assert meta["licensing_status"] == LICENSING_STATUS
    # ...while the pre-cure values survive for audit, off the read path.
    assert meta["pma_status_superseded_kbli2020"] == "TERBUKA"
    assert meta["per_skala_superseded_kbli2020"][0]["kewenangan"] == "Gubernur"
    assert [s["kode_kbli_2025"] for s in meta["kbli_2025_successors"]] == [
        "39002",
        "82921",
        "82922",
    ]
    assert all("mapping_note" in s for s in meta["kbli_2025_successors"])


def test_cured_content_states_absence_and_lists_only_crosswalk_successors():
    content = build_phantom_content(
        "82920", "AKTIVITAS PENGEMASAN", find_successors(CANONICAL, "82920"), []
    )
    assert "TIDAK terdapat dalam katalog KBLI 2025" in content
    assert "**82921**" in content and "**82922**" in content
    assert "82999" not in content
    # No 2020 licensing fact is restated in the cured prose.
    for banned in ("Menengah Tinggi", "NIB dan Izin", "Gubernur", "TERBUKA"):
        assert banned not in content


def test_cured_content_never_claims_certified_equivalence():
    """The crosswalk records a LINK, not a legal succession. The rendered
    section must disclose per-link confidence and must not tell the reader the
    listed codes replace the old one outright."""
    content = build_phantom_content(
        "82920", "AKTIVITAS PENGEMASAN", find_successors(CANONICAL, "82920"), []
    )
    assert "score=71%" in content  # the weak link's provenance reaches the reader
    assert "tingkat keyakinan yang " in content and "BERBEDA-BEDA" in content
    # Ordering and presence must both be disarmed as relevance signals — the
    # flattening risk an adversarial review flagged on this section.
    assert "BUKAN menurut " in content and "relevansi" in content
    assert "BUKAN rekomendasi" in content
    assert "TIDAK relevan dengan kegiatan usaha nyata" in content
    assert "Menggantikan" not in content


def test_cured_content_never_asserts_a_regulatory_abolition():
    """Wording rule F12: we report what our catalogue contains, never that a
    regulator abolished or failed to publish the code."""
    content = build_phantom_content("82920", "AKTIVITAS PENGEMASAN", find_successors(CANONICAL, "82920"), [])
    lowered = content.lower()
    for banned in ("dihapus oleh", "dicabut", "abolished", "revoked", "belum diterbitkan", "not published"):
        assert banned not in lowered


def test_no_successor_branch_declares_the_gap_and_fences_the_group():
    content = build_phantom_content(
        "85598",
        "JASA PENDIDIKAN SWASTA LAINNYA YTDL",
        [],
        same_group_codes(CANONICAL, "85598"),
    )
    assert "TIDAK mencatat satu pun kode KBLI 2025 sebagai tertaut" in content
    assert "Kami tidak menyimpulkan penggantinya." in content
    # The group listing appears, but explicitly not as a crosswalk.
    assert "BUKAN crosswalk resmi" in content
    assert "85599" in content


def test_plan_uses_group_listing_only_when_there_is_no_successor():
    with_succ = plan_phantom_cure("82920", CANONICAL, _canon(), PHANTOM_ROW_82920)
    without = plan_phantom_cure("85598", CANONICAL, _canon(), PHANTOM_ROW_85598)
    assert "BUKAN crosswalk resmi" not in (with_succ.new_content or "")
    assert "BUKAN crosswalk resmi" in (without.new_content or "")


def test_judul_carries_the_vintage_qualifier():
    plan = plan_phantom_cure("82920", CANONICAL, _canon(), PHANTOM_ROW_82920)
    assert plan.new_judul == "AKTIVITAS PENGEMASAN [KBLI 2020 — tidak ada dalam KBLI 2025]"


# --- idempotence + archive fidelity ----------------------------------------


def test_rerun_on_an_already_cured_row_is_a_declared_noop():
    first = plan_phantom_cure("82920", CANONICAL, _canon(), PHANTOM_ROW_82920)
    cured_row = {
        "judul": first.new_judul,
        "content": first.new_content,
        "metadata": first.new_metadata,
        "created_at": None,
        "updated_at": None,
    }
    second = plan_phantom_cure("82920", CANONICAL, _canon(), cured_row)
    assert second.update_row is False
    assert second.skip_reason == "already cured (judul/content/metadata match)"


def test_rerun_does_not_overwrite_the_audit_trail_with_the_cures_own_output():
    """The invariant idempotence protects: on a second pass the row's live
    `pma_status` is already the cured sentinel and `per_skala` is already [].
    Capturing THOSE as the 'superseded' values would erase the genuine 2020
    payload — the audit trail must still name TERBUKA and Gubernur."""
    first = build_phantom_metadata("82920", PHANTOM_ROW_82920["metadata"], [])
    second = build_phantom_metadata("82920", first, [])
    assert second["pma_status_superseded_kbli2020"] == "TERBUKA"
    assert second["per_skala_superseded_kbli2020"][0]["kewenangan"] == "Gubernur"
    assert second["pma_status"] == ROUTER_PMA_FALLBACK


def test_rerun_does_not_stack_the_vintage_suffix():
    first = plan_phantom_cure("82920", CANONICAL, _canon(), PHANTOM_ROW_82920)
    cured_row = {
        "judul": first.new_judul,
        "content": first.new_content,
        "metadata": first.new_metadata,
        "created_at": None,
        "updated_at": None,
    }
    second = plan_phantom_cure("82920", CANONICAL, _canon(), cured_row)
    # No-op on a matching row, and the stored title still carries exactly one
    # qualifier.
    assert (cured_row["judul"] or "").count("[KBLI 2020") == 1
    assert second.new_judul is None


def test_archive_params_are_byte_exact_and_carry_the_phantom_reason():
    params = archive_params("82920", PHANTOM_ROW_82920)
    assert params[0] == "82920"
    assert params[1] == PHANTOM_ROW_82920["judul"]
    assert params[2] == PHANTOM_ROW_82920["content"]
    assert "Gubernur" in params[3]  # metadata serialised verbatim, nothing stripped
    assert "phantom-row snapshot" in params[6]


def test_metadata_preserves_unrelated_keys():
    meta = build_phantom_metadata("82920", PHANTOM_ROW_82920["metadata"], [])
    assert meta["sektor_id"] == "I.F.h"


def test_metadata_judul_carries_the_same_qualifier_as_the_column():
    """A consumer reading `metadata.judul` instead of the `judul` column must
    not get the bare 2020 title — that would drop the whole warning on one of
    the two paths."""
    qualified = f"AKTIVITAS PENGEMASAN{VINTAGE_SUFFIX}"
    meta = build_phantom_metadata(
        "82920", PHANTOM_ROW_82920["metadata"], [], qualified_judul=qualified
    )
    assert meta["judul"] == qualified


def test_metadata_rekeys_the_false_2025_claim():
    """The seed wrote the 2020 code into `kode_kbli_2025`, a field whose NAME
    asserts it is a 2025 code — the exact claim being cured."""
    meta = build_phantom_metadata("82920", PHANTOM_ROW_82920["metadata"], [])
    assert "kode_kbli_2025" not in meta
    assert meta["kode_kbli_2020"] == "82920"


def test_dataset_provenance_is_recorded_in_the_audit_note():
    meta = build_phantom_metadata(
        "82920", PHANTOM_ROW_82920["metadata"], [], dataset_provenance="file.json (sha256:abc123)"
    )
    assert "sha256:abc123" in meta["_data_note"]


# --- fail-closed shape guard ----------------------------------------------


def test_unrecognised_metadata_key_is_refused_not_silently_passed_through():
    """A row carrying a key this cure has never been verified against could be
    holding licensing facts the cure would leave behind. Refuse rather than
    guess which unknown keys are dangerous."""
    row = dict(PHANTOM_ROW_82920)
    row["metadata"] = {**PHANTOM_ROW_82920["metadata"], "kategori_risiko": "Tinggi"}
    plan = plan_phantom_cure("82920", CANONICAL, _canon(), row)
    assert plan.update_row is False
    assert "unrecognised metadata key" in (plan.skip_reason or "")
    assert "kategori_risiko" in (plan.skip_reason or "")


def test_the_cures_own_output_shape_is_not_refused_on_rerun():
    """INNOCENCE for the guard above: the keys this cure writes must be in the
    recognised set, or a second pass would refuse its own work."""
    first = plan_phantom_cure("82920", CANONICAL, _canon(), PHANTOM_ROW_82920)
    cured = {
        "judul": first.new_judul,
        "content": first.new_content,
        "metadata": first.new_metadata,
        "created_at": None,
        "updated_at": None,
    }
    second = plan_phantom_cure("82920", CANONICAL, _canon(), cured)
    assert "unrecognised metadata key" not in (second.skip_reason or "")


# --- dataset integrity gate ------------------------------------------------


def test_truncated_catalogue_is_refused():
    """"Phantom" means "absent from the catalogue", so a truncated catalogue
    would reclassify live codes as phantom and the innocence guard — which
    trusts the catalogue — would wave them through."""
    with pytest.raises(SystemExit) as e:
        validate_dataset(CANONICAL)  # 5 records, far below the expected band
    assert "outside the expected" in str(e.value)


def test_duplicate_code_in_catalogue_is_refused():
    big = [
        {"kode_kbli_2025": f"{10000 + i}", "judul": f"code {i}"} for i in range(1550)
    ]
    big.append({"kode_kbli_2025": "10000", "judul": "duplicate"})
    with pytest.raises(SystemExit) as e:
        validate_dataset(big)
    assert "duplicate kode_kbli_2025" in str(e.value)


def test_record_without_a_code_is_refused():
    big = [{"kode_kbli_2025": f"{10000 + i}", "judul": f"code {i}"} for i in range(1550)]
    big[7] = {"judul": "no code here"}
    with pytest.raises(SystemExit) as e:
        validate_dataset(big)
    assert "lack kode_kbli_2025/judul" in str(e.value)


def test_a_well_formed_catalogue_passes():
    """INNOCENCE for the integrity gate: a gate that rejected the real
    catalogue would block every cure, so acceptance is asserted explicitly —
    `validate_dataset` accepts by returning None rather than raising."""
    big = [{"kode_kbli_2025": f"{10000 + i}", "judul": f"code {i}"} for i in range(1559)]
    assert validate_dataset(big) is None
    # And the accepted catalogue still yields a working phantom census.
    assert phantom_codes(big, ["10000", "99999"]) == ["99999"]
