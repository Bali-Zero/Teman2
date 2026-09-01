"""Unit tests for kbli_documents_cure.py — pure decision/render logic.

No DB, no network — `plan_cure`, `build_cured_content`, `build_cured_metadata`,
`quarantined_codes`, and `archive_params` take plain dicts/lists and return
plain dicts/dataclasses. These tests pin the 4th-consumer-surface cure
(2026-07-19): `chat_kbli` injects `kbli_documents.content` verbatim into the
LLM context (see module docstring in
`backend/scripts/kbli_documents_cure.py`), and this script must never
synthesize a new licensing/risk/capital assertion for a code the canonical
dataset has declared an honest gap (rule #9).

Guilt/innocence corpus (scar #3 discipline — no guard ships on substring
matching alone):
  - GUILT: honest-gap codes (per_skala == []) must render ONLY the
    Codex-gated whatYouNeed prose in the licensing section — never a
    synthesized `- **[...]** — Risiko: ...` bullet row (the exact pattern
    this script's OWN renderer would produce for a non-empty per_skala).
  - INNOCENCE: 49213 (RESTORED, not detached — canonical per_skala is
    non-empty, real per-ancestor data) MUST render that data as structured
    bullets, including its real "Menengah Tinggi" / "NIB dan Sertifikat
    Standar" / "Bupati/Wali Kota" values — a guard that blindly denied those
    tokens everywhere would wrongly clobber this legitimate restored code
    (the guard-over-match trap catalogued as cicatrix superscar #3).
  - A narrow capital-figure deny-list ("Rp 10", "Modal Disetor", "paid-up
    capital", "Ten Billion") is checked with ZERO exceptions across every
    honest-gap code fixture below — verified clean against the real
    canonical `intel_2026.whatYouNeed` corpus for all 72 gap codes before
    this test was written (73 total quarantined codes minus 49213).
  - 68112's own whatYouNeed text legitimately mentions "Sertifikat Standar"
    and "risk level" IN NEGATED CORRECTION PROSE ("...were a code-number
    collision... do not apply to residential leasing") — a broad substring
    deny-list would misfire on this honest sentence (the exact guard-over-
    match failure mode this test suite is designed to avoid). This script
    does not re-author or filter that already-Codex-gated text; the
    regression guard here is structural (no synthesized bullet row), not a
    blind substring ban on externally-sourced honest prose.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.scripts.kbli_documents_cure import (
    SNAPSHOT_MAX_AGE_MINUTES,
    DocumentCurePlan,
    archive_params,
    build_cured_content,
    build_cured_metadata,
    build_perizinan_section,
    fetch_conformance_report,
    is_machine_template,
    licensing_absent_codes,
    plan_cure,
    quarantined_codes,
    rebuild_reason,
)

# Trimmed real canonical records (2026-07-19 dataset) — the two live-proof
# collision-detached codes (50113, 68112, both per_skala == []) plus the one
# RESTORED code (49213, per_skala non-empty, real per-ancestor data).
RECORD_50113 = {
    "kode_kbli_2025": "50113",
    "judul": "Angkutan Laut Dalam Negeri untuk Wisata",
    "uraian": (
        "Kelompok ini mencakup aktivitas pengangkutan untuk wisata atau untuk rekreasi "
        "di laut, dan/atau wisata bahari."
    ),
    "pma_status": "TERBATAS",
    "pma_max_asing": 49,
    "pma_verification_status": "located",
    "pma_official_basis": "Perpres 10/2021 Lampiran III located fixture",
    "pma_source_vintage": "2021-05-25",
    "pma_cap_verified": True,
    "per_skala": [],
    "per_skala_disputed_pp28_collision": [{"kategori_risiko": "Menengah Tinggi"}],
    "_data_note": (
        "KBLI 2025 code 50113 'Angkutan Laut Dalam Negeri untuk Wisata' ... per_skala detached."
    ),
    "intel_2026": {
        "whatYouNeed": (
            "This code covers domestic sea transport for tourism and recreation, such as "
            "dive charters, island-hopping cruises, and sightseeing cruises. The licensing "
            "rows shown here earlier cited a regulatory source we could not verify in the "
            "official document set, so they have been removed from this page pending "
            "re-verification; the correct licensing is not yet reliably confirmed in our "
            "verified sources. Before registering or investing, confirm the current "
            "requirements with the Bali Zero team."
        )
    },
}

RECORD_68112 = {
    "kode_kbli_2025": "68112",
    "judul": "Aktivitas Penyewaan Bangunan dan Lahan Hunian Milik Sendiri atau Sewa",
    "uraian": "Kelompok ini mencakup penyewaan dan pengoperasian real estat hunian.",
    "pma_status": "TERBUKA",
    "pma_max_asing": 100,
    "per_skala": [],
    "per_skala_disputed_pp28_mice": [{"kategori_risiko": "Menengah Rendah"}],
    "_data_note": "KBLI 2025 code 68112 = residential leasing ... per_skala detached.",
    "intel_2026": {
        "whatYouNeed": (
            "**Registration:** KBLI 2025 code 68112 covers long-term residential leasing — "
            "register the activity via NIB. **Licensing not yet defined in OSS for this new "
            "code:** OSS has not published a risk-based standard (Sertifikat Standar / "
            "standar usaha) for 68112 under KBLI 2025 (ruang-lingkup returns 404). The risk "
            'level and "Standard Certificate / LSPr self-assessment" shown here previously '
            "were a code-number collision — they belonged to a *different* activity, "
            "MICE-venue rental, which does **not** apply to residential leasing. Confirm "
            "current OSS requirements before filing."
        )
    },
}

RECORD_49213 = {
    "kode_kbli_2025": "49213",
    "judul": "Angkutan Perkotaan",
    "uraian": "Kelompok ini mencakup aktivitas transportasi ... dalam kawasan perkotaan.",
    "pma_status": "TERBUKA",
    "pma_max_asing": 100,
    "per_skala": [
        {
            "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
            "kategori_risiko": "Menengah Tinggi",
            "jangka_waktu": "5 Hari",
            "scope_uraian": "Angkutan Bus Kota",
            "perizinan": ["NIB dan Sertifikat Standar"],
            "kewenangan": ["Bupati/Wali Kota"],
        },
    ],
    "per_skala_disputed_pp28_collision": [
        {"kategori_risiko": "Menengah Tinggi", "kewenangan": ["Gubernur"]}
    ],
    "_data_note": "KBLI 2025 code 49213 ... per_skala restored from 3 per-ancestor rows.",
    "intel_2026": {
        "whatYouNeed": "This activity is open to foreign investment through a PMA company.",
    },
}

# A healthy, never-quarantined code — no per_skala_disputed_* key at all.
RECORD_HEALTHY = {
    "kode_kbli_2025": "56101",
    "judul": "Restoran",
    "uraian": "Aktivitas penyediaan makanan di bangunan tetap.",
    "pma_status": "TERBUKA",
    "per_skala": [
        {"skala_usaha": ["Besar"], "kategori_risiko": "Menengah Tinggi", "perizinan": ["NIB"]}
    ],
}

NARROW_CAPITAL_DENY_LIST = (
    "Rp 10",
    "Modal Disetor",
    "modal disetor",
    "paid-up capital",
    "Ten Billion",
)

# The exact synthesized-bullet pattern this script's own renderer produces
# for a non-empty per_skala — the ONLY thing a gap-code's Perizinan section
# must never contain.
_SYNTHESIZED_BULLET_PREFIX = "- **["


def _perizinan_section(content: str) -> str:
    return content.split("## Perizinan\n", 1)[1].split("\n\n## ", 1)[0]


# ---------------------------------------------------------------------------
# quarantined_codes
# ---------------------------------------------------------------------------


def test_quarantined_codes_computed_from_disputed_marker_only():
    dataset = [RECORD_50113, RECORD_68112, RECORD_49213, RECORD_HEALTHY]
    assert quarantined_codes(dataset) == ["49213", "50113", "68112"]


def test_quarantined_codes_healthy_code_never_included():
    dataset = [RECORD_HEALTHY]
    assert quarantined_codes(dataset) == []


def test_quarantined_codes_sorted_and_stringified():
    dataset = [
        {"kode_kbli_2025": "99999", "per_skala_disputed_x": []},
        {"kode_kbli_2025": "00001", "per_skala_disputed_y": []},
    ]
    assert quarantined_codes(dataset) == ["00001", "99999"]


# ---------------------------------------------------------------------------
# build_perizinan_section / build_cured_content — GUILT (honest-gap codes)
# ---------------------------------------------------------------------------


def test_gap_code_50113_perizinan_is_whatyouneed_verbatim_no_synthesized_bullet():
    section = build_perizinan_section(RECORD_50113)
    assert section == RECORD_50113["intel_2026"]["whatYouNeed"]
    assert _SYNTHESIZED_BULLET_PREFIX not in section


def test_gap_code_68112_withholds_editorial_without_a_located_pma_tuple():
    section = build_perizinan_section(RECORD_68112)
    assert "belum dapat diverifikasi" in section
    assert RECORD_68112["intel_2026"]["whatYouNeed"] not in section
    assert _SYNTHESIZED_BULLET_PREFIX not in section


def test_gap_code_50113_content_never_contains_capital_deny_tokens():
    content = build_cured_content("50113", RECORD_50113)
    for token in NARROW_CAPITAL_DENY_LIST:
        assert token not in content, f"unexpected capital-figure token {token!r} in cured content"


def test_gap_code_68112_content_never_contains_capital_deny_tokens():
    content = build_cured_content("68112", RECORD_68112)
    for token in NARROW_CAPITAL_DENY_LIST:
        assert token not in content, f"unexpected capital-figure token {token!r} in cured content"


def test_declared_pma_gap_withholds_raw_pma_editorial_and_audit_prose():
    content = build_cured_content("68112", RECORD_68112)
    metadata = build_cured_metadata("68112", RECORD_68112, old_metadata={})

    assert "Status PMA: NOT_VERIFIED" in content
    assert "Status PMA: TERBUKA" not in content
    assert "Maksimum Kepemilikan Asing: 100" not in content
    assert RECORD_68112["intel_2026"]["whatYouNeed"] not in content
    assert RECORD_68112["_data_note"] not in content
    assert metadata["pma_status"] == "NOT_VERIFIED"
    assert metadata["pma_max_asing"] is None
    assert metadata["pma_verification_status"] == "declared_gap"
    assert "_data_note" not in metadata


def test_located_special_cap_is_rendered_without_a_percentage_suffix():
    record = dict(
        RECORD_50113,
        pma_max_asing="special",
        pma_cap_special=True,
    )

    content = build_cured_content("47221", record)

    assert "Kepemilikan Asing: kondisi khusus non-persentase" in content
    assert "special%" not in content


def test_gap_code_content_never_contains_synthesized_bullet_line():
    """Structural guard: for ANY per_skala==[] code, no line in the cured
    content may match the synthesized-bullet pattern this script's own
    renderer emits for a non-empty per_skala — the actual guilty behavior
    (this script hallucinating a licensing row) this test exists to catch."""
    for record, code in ((RECORD_50113, "50113"), (RECORD_68112, "68112")):
        content = build_cured_content(code, record)
        for line in content.splitlines():
            assert not line.startswith(_SYNTHESIZED_BULLET_PREFIX), (
                f"{code}: synthesized bullet line leaked into gap-code content: {line!r}"
            )


def test_gap_code_content_falls_back_to_generic_gap_text_when_whatyouneed_missing():
    record = dict(RECORD_50113, intel_2026={})
    section = build_perizinan_section(record)
    assert "Bali Zero" in section
    assert _SYNTHESIZED_BULLET_PREFIX not in section


def test_gap_code_50113_old_fabricated_specifics_absent_from_cured_content():
    """Regression pin against the ACTUAL prod fabrication this cure fixes:
    the pre-cure kbli_documents row for 50113 asserted KSOP/BKI/STCW
    authorities and a Menengah Tinggi risk tier nowhere in canonical. None
    of that vocabulary is in RECORD_50113's fields, so it must not appear
    in cured content either — proves the cure doesn't leak the stale text
    from anywhere else in the builder."""
    content = build_cured_content("50113", RECORD_50113)
    for stale_token in ("KSOP", "BKI", "STCW", "Menengah Tinggi"):
        assert stale_token not in content


# ---------------------------------------------------------------------------
# build_cured_content — INNOCENCE (49213, restored, non-empty per_skala)
# ---------------------------------------------------------------------------


def test_restored_code_49213_renders_real_licensing_bullet():
    content = build_cured_content("49213", RECORD_49213)
    section = _perizinan_section(content)
    assert section.startswith(_SYNTHESIZED_BULLET_PREFIX)
    # the innocence check this suite exists for: these tokens are LEGITIMATE
    # here and must NOT be denied — a blind global deny-list would break this.
    assert "Menengah Tinggi" in section
    assert "NIB dan Sertifikat Standar" in section
    assert "Bupati/Wali Kota" in section


def test_restored_code_49213_never_renders_disputed_old_collision_values():
    """The DISPUTED pre-cure block (Gubernur authority, AKDP inter-city
    regime) must never leak into the cured content — only the restored
    per_skala (municipal Bupati/Wali Kota authority) may appear."""
    content = build_cured_content("49213", RECORD_49213)
    section = _perizinan_section(content)
    assert "Gubernur" not in section


def test_restored_code_never_flagged_as_gap_in_plan():
    plan = plan_cure(
        "49213",
        RECORD_49213,
        {"judul": "old", "content": "old", "metadata": {}},
    )
    assert plan.is_gap is False


def test_gap_code_flagged_as_gap_in_plan():
    plan = plan_cure(
        "50113",
        RECORD_50113,
        {"judul": "old", "content": "old", "metadata": {}},
    )
    assert plan.is_gap is True


# ---------------------------------------------------------------------------
# build_cured_metadata
# ---------------------------------------------------------------------------


def test_cured_metadata_gap_code_per_skala_replaced_with_empty_list():
    meta = build_cured_metadata(
        "50113", RECORD_50113, old_metadata={"per_skala": [{"fabricated": True}]}
    )
    assert meta["per_skala"] == []
    assert meta["licensing_status"] == "PENDING_REGULATION"


def test_cured_metadata_restored_code_per_skala_replaced_with_real_rows():
    meta = build_cured_metadata(
        "49213", RECORD_49213, old_metadata={"per_skala": [{"fabricated": True}]}
    )
    assert meta["per_skala"] == RECORD_49213["per_skala"]
    assert "fabricated" not in str(meta["per_skala"])


def test_cured_metadata_restored_code_preserves_existing_licensing_status():
    meta = build_cured_metadata("49213", RECORD_49213, old_metadata={"licensing_status": "N/A"})
    assert meta["licensing_status"] == "N/A"


def test_cured_metadata_carries_data_note_for_audit_parity():
    meta = build_cured_metadata("50113", RECORD_50113, old_metadata={})
    assert meta["_data_note"] == RECORD_50113["_data_note"]


def test_cured_metadata_omits_data_note_key_when_absent():
    record = dict(RECORD_50113)
    record.pop("_data_note")
    meta = build_cured_metadata("50113", record, old_metadata={})
    assert "_data_note" not in meta


# ---------------------------------------------------------------------------
# plan_cure — idempotency, skip reasons, scope discipline
# ---------------------------------------------------------------------------


def test_plan_cure_update_row_true_when_current_row_is_stale():
    stale_row = {"judul": "OLD TITLE", "content": "old fabricated content", "metadata": {}}
    plan = plan_cure("50113", RECORD_50113, stale_row)
    assert plan.update_row is True
    assert plan.new_content is not None
    assert plan.new_content == build_cured_content("50113", RECORD_50113)


def test_plan_cure_idempotent_second_run_is_noop():
    cured_content = build_cured_content("50113", RECORD_50113)
    cured_metadata = build_cured_metadata("50113", RECORD_50113, old_metadata={})
    already_cured_row = {
        "judul": RECORD_50113["judul"],
        "content": cured_content,
        "metadata": cured_metadata,
    }
    plan = plan_cure("50113", RECORD_50113, already_cured_row)
    assert plan.update_row is False
    assert plan.new_content is None
    assert plan.new_metadata is None
    assert plan.skip_reason is not None and "already cured" in plan.skip_reason


def test_plan_cure_skip_code_not_in_canonical():
    plan = plan_cure("99999", None, {"judul": "x", "content": "y", "metadata": {}})
    assert plan.skip_reason == "not in canonical dataset"
    assert plan.update_row is False
    assert plan.found_in_table is True


def test_plan_cure_skip_code_not_in_table():
    plan = plan_cure("50113", RECORD_50113, None)
    assert plan.skip_reason == "not in kbli_documents table"
    assert plan.update_row is False
    assert plan.found_in_canonical is True


def test_plan_cure_healthy_code_row_untouched_when_content_already_matches():
    """A code outside the quarantined scope, if ever passed through
    plan_cure with a row whose content coincidentally already equals what
    the builder would produce, is correctly reported as a no-op — proving
    `--only` scope discipline lives in main()'s code-list selection, not in
    an accidental mutation path inside plan_cure itself."""
    cured_content = build_cured_content("56101", RECORD_HEALTHY)
    cured_metadata = build_cured_metadata("56101", RECORD_HEALTHY, old_metadata={})
    row = {"judul": RECORD_HEALTHY["judul"], "content": cured_content, "metadata": cured_metadata}
    plan = plan_cure("56101", RECORD_HEALTHY, row)
    assert plan.update_row is False


def test_plan_cure_returns_dataclass_instance():
    plan = plan_cure("50113", RECORD_50113, {"judul": "x", "content": "y", "metadata": {}})
    assert isinstance(plan, DocumentCurePlan)


# ---------------------------------------------------------------------------
# archive_params — byte-exact preservation
# ---------------------------------------------------------------------------


def test_archive_params_preserves_content_byte_exact():
    current_row = {
        "judul": "STALE TITLE",
        "content": "stale fabricated markdown with risk tiers",
        "metadata": {"per_skala": [{"kategori_risiko": "Menengah Tinggi"}]},
        "created_at": "2026-02-17T23:20:37.967Z",
        "updated_at": "2026-02-17T23:20:37.967Z",
    }
    params = archive_params("50113", current_row)
    assert params[0] == "50113"
    assert params[1] == current_row["judul"]
    assert params[2] == current_row["content"]
    # metadata is JSON-serialized for the ::text::jsonb bind, but must
    # decode back to the exact same structure — nothing dropped or altered.
    import json as _json

    assert _json.loads(params[3]) == current_row["metadata"]
    assert params[4] == current_row["created_at"]
    assert params[5] == current_row["updated_at"]


def test_archive_params_handles_missing_metadata_gracefully():
    current_row = {
        "judul": "x",
        "content": "y",
        "metadata": None,
        "created_at": None,
        "updated_at": None,
    }
    params = archive_params("50113", current_row)
    import json as _json

    assert _json.loads(params[3]) == {}


# ---------------------------------------------------------------------------
# STATE-BASED SCOPE (--all-licensing-absent, 2026-08-02)
#
# The marker selector above reaches 73 codes; 1,423 of the table's 1,563 rows
# had never been touched by any cure because every run named its own --only
# list ("the selector is the disease", this corner's own meta-pattern, landing
# for the fourth time). This selector asks the conformance detector for STATE
# instead, so no list is authored anywhere.
#
# The guilt/innocence pair here is not decorative. `licensing_divergent` is
# SYMMETRIC — it reports both "canonical has rows, table has none" and its
# mirror. Only the first is this script's business; curing the mirror would
# rewrite a live row-set into a gap statement, i.e. destroy data while the run
# report says "cured". The innocence test is that mirror.
# ---------------------------------------------------------------------------


def test_licensing_absent_selects_canonical_rows_with_empty_channel():
    """GUILT: canonical holds verified rows, the channel serves none."""
    report = {"licensing_divergent": [{"code": "82400", "canonical_rows": 7, "table_rows": 0}]}
    assert licensing_absent_codes(report) == ["82400"]


def test_licensing_absent_never_selects_the_mirror_direction():
    """INNOCENCE — THE regression this selector exists to avoid.

    A code whose canonical record has DETACHED its rows while the table still
    serves them is the quarantine class. Selecting it here would flatten real
    licensing rows into a gap statement and report it as a cure."""
    report = {"licensing_divergent": [{"code": "50113", "canonical_rows": 0, "table_rows": 12}]}
    assert licensing_absent_codes(report) == []


def test_licensing_absent_keeps_only_its_own_direction_from_a_mixed_report():
    """Both directions in one report: exactly one is this selector's business."""
    report = {
        "licensing_divergent": [
            {"code": "50113", "canonical_rows": 0, "table_rows": 12},
            {"code": "82400", "canonical_rows": 7, "table_rows": 0},
            {"code": "01122", "canonical_rows": 8, "table_rows": 0},
        ]
    }
    assert licensing_absent_codes(report) == ["01122", "82400"]


def test_licensing_absent_on_a_clean_report_is_empty():
    assert licensing_absent_codes({"licensing_divergent": []}) == []
    assert licensing_absent_codes({}) == []


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _pin_detector(monkeypatch, tmp_path, proc: _Proc):
    """Give the module a real file to find, and a canned detector result."""
    script = tmp_path / "kbli_surface_conformance.py"
    script.write_text("# stand-in\n", encoding="utf-8")
    monkeypatch.setattr(
        "backend.scripts.kbli_documents_cure.subprocess.run",
        lambda *a, **k: proc,
    )
    return script


def test_fetch_conformance_report_accepts_the_divergence_exit(monkeypatch, tmp_path):
    """POSITIVE CONTROL — without this, every refusal below would also pass on
    a guard that simply refuses everything. Exit 1 is the NORMAL path: the
    detector exits 1 precisely when there is something to cure."""
    body = '{"licensing_divergent": [{"code": "82400", "canonical_rows": 7, "table_rows": 0}]}'
    script = _pin_detector(monkeypatch, tmp_path, _Proc(1, stdout=body))
    report = fetch_conformance_report(script)
    assert licensing_absent_codes(report) == ["82400"]


def test_fetch_conformance_report_refuses_cannot_verify(monkeypatch, tmp_path):
    """Exit 4 carries an EMPTY divergence list — byte-identical to a healthy
    fleet. Reading it as 'nothing to cure' is how a cure becomes a silent
    no-op (W84: absence of a reading is not alignment)."""
    script = _pin_detector(
        monkeypatch, tmp_path, _Proc(4, stdout="CANNOT VERIFY: table snapshot unavailable")
    )
    with pytest.raises(RuntimeError, match="CANNOT-VERIFY"):
        fetch_conformance_report(script)


def test_fetch_conformance_report_refuses_an_unknown_exit(monkeypatch, tmp_path):
    """An exit outside the detector's declared vocabulary is not a verdict."""
    script = _pin_detector(monkeypatch, tmp_path, _Proc(2, stderr="Traceback ..."))
    with pytest.raises(RuntimeError, match="exited 2"):
        fetch_conformance_report(script)


def test_fetch_conformance_report_refuses_a_silent_success(monkeypatch, tmp_path):
    """Exit 0 with no body: judged on the OUTPUT, not on having survived."""
    script = _pin_detector(monkeypatch, tmp_path, _Proc(0, stdout="   "))
    with pytest.raises(RuntimeError, match="printed nothing"):
        fetch_conformance_report(script)


def test_fetch_conformance_report_refuses_a_missing_detector(monkeypatch, tmp_path):
    """No detector means no predicate — this script does not own one, and must
    not fall back to inventing a second answer to the same question (W105)."""
    monkeypatch.setattr(
        "backend.scripts.kbli_documents_cure.subprocess.run",
        lambda *a, **k: _Proc(0, stdout="{}"),
    )
    with pytest.raises(RuntimeError, match="not found"):
        fetch_conformance_report(tmp_path / "absent.py")


# ---------------------------------------------------------------------------
# CONTENT-PRESERVATION GATE (2026-08-02)
#
# The 2026-02-18 seed left two document shapes in this table. One is machine-
# derived from the same canonical fields the rebuild reads (replacing it loses
# nothing); the other is hand-written client-facing prose — code disambiguation
# and local-market guidance — that canonical cannot regenerate.
#
# Recognition is POSITIVE and whole-document. An earlier draft searched for the
# known editorial headings, which judges FORM: prose under any other heading
# would have been classified disposable and destroyed. A cross-family review
# (Codex GPT-5.6, instructed to refute) named that and two more; the tests
# below are those objections turned into red-on-regression.
# ---------------------------------------------------------------------------

_MACHINE_ROW = """# KBLI 01122 - PERTANIAN PADI INBRIDA

## Informasi Umum
- **Kode KBLI 2025**: 01122

## Deskripsi Kegiatan Usaha
Kelompok ini mencakup kegiatan pertanian padi inbrida.

## Investasi Asing (PMA)
- Status PMA: TERBUKA
"""

_EDITORIAL_ROW = (
    "KBLI 86995: AKTIVITAS RUMAH PIJAT\n\nWHAT IT MEANS:\nMassage parlours — distinct from "
    "medical massage (86991) and spa treatments (96230).\n\nBALI CONTEXT:\nUbud, Sanur and "
    "Canggu all have thriving massage clusters."
)


def test_machine_template_recognised():
    assert is_machine_template("01122", _MACHINE_ROW) is True


def test_machine_template_rejects_a_hand_added_section():
    """THE regression a head-only check would miss (review objection C): the
    document opens machine-shaped and a human appended material below."""
    tampered = _MACHINE_ROW + "\n## Catatan Tim\nKlien harus cek zonasi Bali dulu.\n"
    assert is_machine_template("01122", tampered) is False


def test_machine_template_rejects_editorial_prose():
    assert is_machine_template("86995", _EDITORIAL_ROW) is False


def test_machine_template_rejects_a_heading_naming_another_code():
    """The heading must name THIS code — a row carrying another code's document
    is not a row whose shape we have verified."""
    assert is_machine_template("99999", _MACHINE_ROW) is False


def test_machine_template_rejects_prose_under_unknown_headings():
    """Valuable prose under headings nobody enumerated is REFUSED, not swept in
    — the whole point of recognising positively instead of keyword-hunting."""
    other = "# KBLI 01122 - X\n\n## Panduan Lokal\nCatatan tim tentang praktik di Bali.\n"
    assert is_machine_template("01122", other) is False


def test_rebuild_reason_machine_template():
    assert rebuild_reason("01122", _MACHINE_ROW, 8) == "machine-template"


def test_rebuild_reason_rebuilds_a_government_contradicted_claim():
    """Review objection B, answered in the direction that costs prose: a row
    telling a client licensing is minimal, on a code where canonical now holds
    government rows, is rebuilt — a false regulatory instruction outranks the
    market copy, which the archive keeps."""
    stale = _EDITORIAL_ROW + "\nSince there's no PP28 data yet, licensing is currently minimal."
    assert rebuild_reason("86995", stale, 2) == "contradicted-licensing-claim"


def test_rebuild_reason_preserves_editorial_prose_without_a_false_claim():
    """INNOCENCE: hand-written prose that contradicts nothing is kept. Without
    this, the gate would be a rebuild-everything switch wearing a gate's name."""
    assert rebuild_reason("86995", _EDITORIAL_ROW, 2) is None


def test_rebuild_reason_does_not_fire_when_canonical_has_no_rows():
    """The claim is only FALSE if canonical actually holds rows. With zero rows
    'licensing is minimal' may well be true, and rebuilding would trade prose
    for nothing."""
    stale = _EDITORIAL_ROW + "\nSince there's no PP28 data yet, licensing is currently minimal."
    assert rebuild_reason("86995", stale, 0) is None


def test_rebuild_reason_refuses_an_absent_row():
    assert rebuild_reason("01122", None, 8) is None


# ---------------------------------------------------------------------------
# Deployment-layout tolerance (2026-08-03)
#
# Found by RUNNING the tool where it actually cures, not by reading it: on the
# Fly machine this module died at IMPORT with `IndexError: 4`, because the
# 2026-08-02 selector added a module-level `parents[4]`. The same file lives at
# two depths — `apps/backend-rag/backend/scripts/` in the repo (4 levels under
# the root) and `/app/backend/scripts/` in the image (2) — so no fixed index is
# right in both. The blast radius was not the new selector: an import-time crash
# took `--only` down too, i.e. the ONLY path that can run in the container and
# the one the 2026-08-01 production cure actually used.
#
# Guilt = the real production layout resolves to None instead of raising.
# Innocence = the repo layout still finds the real detector (a "fix" that
# always returned None would silence the crash and disarm the selector).
# ---------------------------------------------------------------------------

import asyncio as _asyncio
import logging as _logging
import sys as _sys
from pathlib import Path as _Path

from backend.scripts import kbli_documents_cure as _cure


def test_repo_layout_resolves_to_the_real_detector():
    """INNOCENCE: where the repo exists, the selector must still find its owner."""
    found = _cure.find_conformance_script()
    assert found is not None
    assert found.is_file()
    assert found.name == "kbli_surface_conformance.py"
    assert found.parent.name == "kbli_filiera"


def test_container_layout_resolves_to_none_instead_of_raising():
    """GUILT: the exact path the deployed image uses. Must be a value, not a crash."""
    assert (
        _cure.find_conformance_script(_Path("/app/backend/scripts/kbli_documents_cure.py")) is None
    )


def test_a_fixed_parent_index_would_still_crash_on_the_container_layout():
    """SCAR PIN: this is WHY the walk-up exists. If a future refactor goes back
    to counting levels, this test states the cost in one line."""
    container = _Path("/app/backend/scripts/kbli_documents_cure.py").resolve()
    with pytest.raises(IndexError):
        _ = container.parents[4]


def test_module_level_constant_is_never_an_import_time_crash():
    """The defect was at MODULE level: importing was enough to die. Re-running
    the same resolution the module runs at import must be exception-free for
    any depth, including a file sitting at the filesystem root."""
    for probe in ("/x.py", "/a/b.py", "/app/backend/scripts/c.py"):
        found = _cure.find_conformance_script(_Path(probe))
        # Never a phantom path: either a detector that is really there, or None.
        # A resolver that returned a plausible-but-absent path would push the
        # failure down into fetch_conformance_report as a confusing "not found
        # at <made-up path>" instead of the honest "no repo layout here".
        assert found is None or found.is_file()


def test_detector_absent_refusal_names_the_path_that_still_works():
    """A refusal that does not say what to do instead reads as breakage."""
    with pytest.raises(RuntimeError) as exc:
        _cure.fetch_conformance_report(None)
    assert "--only" in str(exc.value)


def test_refusal_is_visible_to_a_caller_as_a_nonzero_exit(monkeypatch):
    """GUILT for the W104 shape: the refusal branch used a bare `return`, so
    `sys.exit(main())` exited 0 and 'I cured nothing' was indistinguishable
    from 'I cured everything'. Driven through main(), not asserted on the
    constant — a constant cannot regress, a branch can."""
    monkeypatch.setattr(_sys, "argv", ["cure", "--all-licensing-absent"])

    async def _no_network(_source):
        return []

    def _detector_down(_script, **_kwargs):
        raise RuntimeError("conformance detector not found")

    monkeypatch.setattr(_cure, "load_dataset", _no_network)
    monkeypatch.setattr(_cure, "fetch_conformance_report", _detector_down)

    rc = _asyncio.run(_cure.main())
    assert rc == _cure.EXIT_REFUSED
    assert rc != 0


def test_importing_this_module_under_the_deployed_layout_does_not_crash():
    """The one test that actually kills the regression.

    The three above exercise `find_conformance_script`; none of them binds the
    MODULE to using it. Proof: reverting the module-level constant to
    `parents[4]` left the whole suite green, because on a repo checkout that
    index resolves — the corpus was measuring the layout it happened to run on,
    not the property it claimed (W110: prove the binding took, not that the
    helper works).

    So execute this module's real source with `__file__` set to the deployed
    path. Under the walk-up it yields None; under any fixed index it raises,
    which is exactly how production died."""
    import types as _types

    source = _Path(_cure.__file__).read_text()
    deployed = "/app/backend/scripts/kbli_documents_cure.py"
    name = "kbli_documents_cure_container_probe"
    probe = _types.ModuleType(name)
    probe.__file__ = deployed
    _sys.modules[name] = probe  # dataclass resolves sys.modules[cls.__module__]
    try:
        exec(compile(source, deployed, "exec"), probe.__dict__)  # noqa: S102
        assert probe.CONFORMANCE_SCRIPT is None
    finally:
        _sys.modules.pop(name, None)


# --- `--only` bypasses the content-preservation gate: report it, never silently act ---


class _FakeConn:
    """Minimal asyncpg stand-in: enough to reach the selector-scoped warning."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, *_args, **_kwargs):
        return "OK"

    async def fetch(self, _sql, codes):
        return [r for r in self._rows if r["kode_kbli"] in codes]

    async def close(self):
        return None


def _row(code, content):
    return {
        "kode_kbli": code,
        "judul": f"KBLI {code}",
        "content": content,
        "metadata": {},
        "created_at": None,
        "updated_at": None,
    }


_HAND_WRITTEN = (
    "# KBLI 86995 - Aktivitas Pijat\n\n"
    "## Informasi Umum\nmachine-shaped head...\n\n"
    "## Bagaimana Membedakannya dari 86991\n"
    "Hand-written disambiguation canonical cannot regenerate.\n"
)
_MACHINE_SEED = (
    "# KBLI 74191 - Aktivitas Konsultasi\n\n"
    "## Informasi Umum\nx\n\n"
    "## Deskripsi Kegiatan Usaha\ny\n\n"
    "## Investasi Asing (PMA)\nz\n"
)


def _drive_only(monkeypatch, argv, rows, dataset=()):
    """Run main() with the DB faked, returning the log records it emitted.

    `dataset` defaults to empty, which is fine for `--only` (the scope comes
    from the flag). It is NOT fine for `--all-quarantined`, whose scope is
    DERIVED from the dataset: with no canonical records main() returns at
    "empty code list" long before the branch under test. That poverty let a
    real mutation (`elif not args.all_quarantined` → `else`) survive."""
    monkeypatch.setattr(_sys, "argv", argv)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")

    async def _dataset(_source):
        return list(dataset)

    async def _connect(_dsn):
        return _FakeConn(rows)

    monkeypatch.setattr(_cure, "load_dataset", _dataset)
    monkeypatch.setattr(_cure.asyncpg, "connect", _connect)
    return _asyncio.run(_cure.main())


def test_only_warns_that_it_will_overwrite_hand_written_prose(monkeypatch, caplog):
    """GUILT. The gate lives under `--all-licensing-absent`; handing the SAME
    population to `--only` cures every row the gate would have refused (25 of 80
    on 2026-08-02). Not blocked — the Perpres-cap lane legitimately replaces
    prose — but it must not be silent."""
    with caplog.at_level(_logging.WARNING, logger=_cure.logger.name):
        _drive_only(monkeypatch, ["cure", "--only", "86995"], [_row("86995", _HAND_WRITTEN)])
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= _logging.WARNING]
    assert any("bypasses the content-preservation gate" in m for m in warnings), warnings
    assert any("86995" in m for m in warnings), warnings


def test_only_is_silent_on_a_machine_seed_row(monkeypatch, caplog):
    """INNOCENCE. A 2026-02-18 machine-seed row loses nothing on rebuild —
    warning about it would train the reader to skip the line that matters."""
    with caplog.at_level(_logging.WARNING, logger=_cure.logger.name):
        _drive_only(monkeypatch, ["cure", "--only", "74191"], [_row("74191", _MACHINE_SEED)])
    assert not [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= _logging.WARNING and "content-preservation gate" in r.getMessage()
    ]


def test_only_does_not_claim_to_overwrite_a_row_that_does_not_exist(monkeypatch, caplog):
    """INNOCENCE. A code absent from `kbli_documents` has no stored prose, so
    naming it would be a fabricated casualty — `content=None` alone fails the
    machine-template predicate, which is why this needs its own branch."""
    with caplog.at_level(_logging.WARNING, logger=_cure.logger.name):
        _drive_only(monkeypatch, ["cure", "--only", "99999"], [])
    assert not [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= _logging.WARNING and "content-preservation gate" in r.getMessage()
    ]


def test_quarantine_scope_is_exempt_from_the_overwrite_warning(monkeypatch, caplog):
    """INNOCENCE. Under `--all-quarantined` the stored content is FABRICATED by
    definition, so 'hand-written prose will be overwritten' would be a false
    alarm about the very text the cure exists to destroy.

    The dataset is REQUIRED here: `--all-quarantined` derives its scope from
    the `per_skala_disputed_*` marker, so without a marked record the run ends
    at "empty code list" and this test proves nothing (mutation-verified)."""
    marked = [{"kode_kbli_2025": "86995", "per_skala_disputed_2026_02": True, "per_skala": []}]
    with caplog.at_level(_logging.WARNING, logger=_cure.logger.name):
        _drive_only(
            monkeypatch,
            ["cure", "--all-quarantined"],
            [_row("86995", _HAND_WRITTEN)],
            dataset=marked,
        )
    assert not [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= _logging.WARNING and "content-preservation gate" in r.getMessage()
    ]


# ── the snapshot pass-through ───────────────────────────────────────────────────
#
# Why it exists at all: reading the live table needs a Keychain password, and
# reading THAT needs an interactive session — over ssh the same lookup returns
# `errSecInteractionNotAllowed` (rc 36), i.e. the entry is PRESENT and merely
# unreadable, which is not the same as absent. The write DSN lives on a different
# machine than the readable Keychain, so no single non-interactive run holds both
# halves. The snapshot is captured where the table can be read and carried to
# where the write can happen.
#
# The risk it introduces is W106: a measurement of the world frozen into a file,
# still being trusted after the world moved. Hence a declared capture time.


def test_the_snapshot_path_is_handed_to_the_detector(monkeypatch, tmp_path):
    """POSITIVE CONTROL. Without this, the refusals below would all pass on a
    pass-through that quietly dropped the flag and queried the DB anyway."""
    snap = tmp_path / "snap.json"
    snap.write_text("[]", encoding="utf-8")
    seen: dict = {}
    body = '{"licensing_divergent": [{"code": "82400", "canonical_rows": 7, "table_rows": 0}]}'
    script = tmp_path / "kbli_surface_conformance.py"
    script.write_text("# detector", encoding="utf-8")

    def _run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _Proc(1, stdout=body)

    monkeypatch.setattr("backend.scripts.kbli_documents_cure.subprocess.run", _run)
    now = datetime.now(timezone.utc).isoformat()
    report = fetch_conformance_report(script, table_json=snap, snapshot_captured_at=now)
    assert licensing_absent_codes(report) == ["82400"]
    assert "--table-json" in seen["cmd"] and str(snap) in seen["cmd"], (
        f"the snapshot never reached the detector: {seen['cmd']}"
    )


def test_the_detector_still_owns_the_verdict(monkeypatch, tmp_path):
    """The pass-through supplies DATA, never a verdict. Exit 4 must still refuse
    even when a snapshot was handed in — otherwise 'I gave it a file' would read
    as 'therefore it could verify'."""
    snap = tmp_path / "snap.json"
    snap.write_text("[]", encoding="utf-8")
    script = tmp_path / "kbli_surface_conformance.py"
    script.write_text("# detector", encoding="utf-8")
    monkeypatch.setattr(
        "backend.scripts.kbli_documents_cure.subprocess.run",
        lambda *a, **k: _Proc(4, stdout="CANNOT VERIFY: canonical unreadable"),
    )
    with pytest.raises(RuntimeError, match="CANNOT-VERIFY"):
        fetch_conformance_report(
            script, table_json=snap, snapshot_captured_at=datetime.now(timezone.utc).isoformat()
        )


def test_refuses_a_snapshot_with_no_stated_capture_time(tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="requires --snapshot-captured-at"):
        fetch_conformance_report(tmp_path / "d.py", table_json=snap, snapshot_captured_at=None)


def test_refuses_a_stale_snapshot(tmp_path):
    """A snapshot from hours ago is a reading of a table that may have moved.
    The threshold is deliberately short: this drives a WRITE."""
    snap = tmp_path / "snap.json"
    snap.write_text("[]", encoding="utf-8")
    old = (datetime.now(timezone.utc) - timedelta(minutes=SNAPSHOT_MAX_AGE_MINUTES + 5)).isoformat()
    with pytest.raises(RuntimeError, match="minutes ago"):
        fetch_conformance_report(tmp_path / "d.py", table_json=snap, snapshot_captured_at=old)


def test_accepts_a_snapshot_captured_just_now(monkeypatch, tmp_path):
    """INNOCENCE for the freshness guard — a guard that refuses everything is
    indistinguishable from a broken pass-through."""
    snap = tmp_path / "snap.json"
    snap.write_text("[]", encoding="utf-8")
    script = tmp_path / "kbli_surface_conformance.py"
    script.write_text("# detector", encoding="utf-8")
    monkeypatch.setattr(
        "backend.scripts.kbli_documents_cure.subprocess.run",
        lambda *a, **k: _Proc(0, stdout='{"licensing_divergent": []}'),
    )
    fresh = (
        datetime.now(timezone.utc) - timedelta(minutes=SNAPSHOT_MAX_AGE_MINUTES - 5)
    ).isoformat()
    assert fetch_conformance_report(script, table_json=snap, snapshot_captured_at=fresh) == {
        "licensing_divergent": []
    }


def test_refuses_a_capture_time_in_the_future(tmp_path):
    """A clock that reads ahead is not evidence of freshness. Refusing beats
    accepting a timestamp that cannot be true."""
    snap = tmp_path / "snap.json"
    snap.write_text("[]", encoding="utf-8")
    ahead = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    with pytest.raises(RuntimeError, match="FUTURE"):
        fetch_conformance_report(tmp_path / "d.py", table_json=snap, snapshot_captured_at=ahead)


def test_refuses_an_unparseable_capture_time(tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not ISO8601"):
        fetch_conformance_report(
            tmp_path / "d.py", table_json=snap, snapshot_captured_at="yesterday"
        )


def test_refuses_a_snapshot_file_that_is_not_there(tmp_path):
    """Named but absent: the detector would fall back to querying the DB, which
    is exactly the thing that cannot work where this flag gets used."""
    with pytest.raises(RuntimeError, match="not found at"):
        fetch_conformance_report(
            tmp_path / "d.py",
            table_json=tmp_path / "absent.json",
            snapshot_captured_at=datetime.now(timezone.utc).isoformat(),
        )


def test_no_snapshot_means_the_detector_queries_the_db_as_before(monkeypatch, tmp_path):
    """INNOCENCE for the whole feature: the default path must be untouched, with
    no --table-json appended and no capture time demanded."""
    seen: dict = {}
    script = tmp_path / "kbli_surface_conformance.py"
    script.write_text("# detector", encoding="utf-8")

    def _run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _Proc(0, stdout='{"licensing_divergent": []}')

    monkeypatch.setattr("backend.scripts.kbli_documents_cure.subprocess.run", _run)
    fetch_conformance_report(script)
    assert "--table-json" not in seen["cmd"]


# ---------------------------------------------------------------------------
# THE OBLIGATIONS THE CHANNEL WAS DROPPING — and the cure that could not
# re-cure its own output (2026-08-05)
#
# Measured on canonical, 9,095 per-scale rows:
#     perizinan    non-empty in     17 rows  (0.19%)
#     persyaratan  non-empty in  5,369 rows  (59%)
#     kewajiban    non-empty in  8,951 rows  (98%)
#
# `## Perizinan` rendered `perizinan` and nothing else — the one field that is
# empty 99.8% of the time — so the channel answered `Perizinan: N/A` about a
# catalogue whose obligations we hold. The website already renders them.
# ---------------------------------------------------------------------------

import json as _json_obl
from pathlib import Path as _Path_obl

from backend.scripts.kbli_documents_cure import (  # noqa: E402
    KEWAJIBAN_BLOCK_MAX_CHARS,
    build_cured_content,
    build_kewajiban_section,
    is_machine_template,
    select_machine_template_rows,
)


def _repo_root_obl() -> _Path_obl:
    """Walk up to the checkout root rather than counting directories — a depth
    constant silently reads the wrong tree the day this file moves, and a
    missing canonical would turn the organ below into a green no-op."""
    here = _Path_obl(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").is_file():
            return parent
    raise AssertionError(f"canonical dataset not found walking up from {here}")


_CANONICAL_OBL = _repo_root_obl() / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


def _canonical_by_code():
    payload = _json_obl.loads(_CANONICAL_OBL.read_text(encoding="utf-8"))
    return {r["kode_kbli_2025"]: r for r in payload["data"]}


def _scale(skala, kewajiban, scope=None):
    entry = {"skala_usaha": [skala], "kategori_risiko": "Rendah", "kewajiban": kewajiban}
    if scope:
        entry["scope_uraian"] = scope
    return entry


def test_the_spa_obligation_the_channel_was_hiding_is_rendered():
    """96230 — canonical holds the SLHS and the channel said "requirements pending"."""
    record = _canonical_by_code()["96230"]
    block = "\n".join(build_kewajiban_section(record))
    assert "Sertifikat Laik Sehat" in block
    assert "Sertifikat Standar Usaha Pariwisata" in block


def test_scales_sharing_an_obligation_are_named_together_and_the_text_appears_once():
    record = {
        "per_skala": [
            _scale("Mikro", ["Lapor ke Menteri"]),
            _scale("Kecil", ["Lapor ke Menteri"]),
            _scale("Besar", ["Sertifikat Laik Sehat"]),
        ]
    }
    block = "\n".join(build_kewajiban_section(record))
    assert block.count("Lapor ke Menteri") == 1, "the same obligation rendered per scale again"
    assert "**Mikro, Kecil**" in block
    assert "**Besar**" in block


def test_a_record_with_no_obligations_gets_no_section_at_all():
    """INNOCENCE. An empty section headed `Kewajiban` would repeat the very
    defect this fixes — an absent field dressed up as an answer."""
    record = {"per_skala": [_scale("Mikro", []), {"skala_usaha": ["Besar"]}]}
    assert build_kewajiban_section(record) == []
    assert build_kewajiban_section({}) == []


def test_no_obligation_is_ever_rendered_as_not_available():
    for record in ({"per_skala": [_scale("Mikro", [])]}, {"per_skala": []}, {}):
        assert "N/A" not in "\n".join(build_kewajiban_section(record))


def test_markup_from_the_extraction_never_reaches_the_client():
    record = {"per_skala": [_scale("Besar", ["<strong>Sertifikat</strong> Laik Sehat"])]}
    block = "\n".join(build_kewajiban_section(record))
    assert "<strong>" not in block and "</strong>" not in block
    assert "Sertifikat Laik Sehat" in block


def test_an_oversized_block_declares_its_truncation_instead_of_being_cut_quietly():
    """W97 — a silent cut reads downstream as "this is everything"."""
    record = {"per_skala": [_scale(f"S{i}", ["x" * 900 + str(i)]) for i in range(40)]}
    block = "\n".join(build_kewajiban_section(record))
    assert "tidak ditampilkan di sini" in block
    assert len(block) <= KEWAJIBAN_BLOCK_MAX_CHARS + 2000, "the cap did not bound the block"


def test_the_whole_catalogue_stays_within_the_declared_bound():
    over = []
    for record in _canonical_by_code().values():
        block = "\n".join(build_kewajiban_section(record))
        if len(block) > KEWAJIBAN_BLOCK_MAX_CHARS + 2000:
            over.append(record["kode_kbli_2025"])
    assert over == [], f"obligation block exceeded its bound on: {over}"


def test_the_builders_own_output_is_recognised_by_the_recogniser():
    """THE ORGAN. `build_cured_content` writes sections the 2026-02-18 seed never
    had (`## Perizinan`, and now `## Kewajiban`), while `is_machine_template` —
    which decides whether a row may be rebuilt — listed only the seed's three.

    So the cure could not re-cure its own output: measured on the live table,
    of the 55 rows it wrote on 2026-08-03, ZERO were still recognised. Every one
    was frozen against any future licensing update, protected as "hand-written
    prose" that the machine itself had written.

    Adding a section to the builder without declaring it in
    MACHINE_TEMPLATE_SECTIONS fails HERE instead of silently freezing rows.
    """
    unrecognised = []
    for code, record in _canonical_by_code().items():
        if not is_machine_template(code, build_cured_content(code, record)):
            unrecognised.append(code)
    assert unrecognised == [], (
        "the cure writes content its own rebuild predicate refuses — those rows "
        f"can never be re-cured: {unrecognised[:10]} ({len(unrecognised)} total)"
    )


def test_scar_pin_a_row_shaped_like_the_2026_08_03_cure_is_still_rebuildable():
    """The exact live regression, pinned as a fixture: sections observed on the
    real row `01122` after that run — seed sections PLUS `## Perizinan`."""
    content = (
        "# KBLI 01122 — Something\n\n"
        "## Deskripsi Kegiatan Usaha\nx\n\n"
        "## Investasi Asing (PMA)\n- Status PMA: TERBUKA\n\n"
        "## Perizinan\n- **[Mikro] (Seluruh)** — Risiko: Rendah\n"
    )
    assert is_machine_template("01122", content) is True


def test_a_hand_added_section_is_still_refused():
    """INNOCENCE for the widening: declaring the builder's own sections must not
    turn the predicate into a blanket yes — editorial prose still refuses."""
    content = (
        "# KBLI 96230 — Spa\n\n"
        "## Deskripsi Kegiatan Usaha\nx\n\n"
        "## Perizinan\n- row\n\n"
        "## BALI CONTEXT\nBali is globally famous for spas.\n"
    )
    assert is_machine_template("96230", content) is False


def test_the_obligations_are_actually_wired_into_the_document_the_channel_reads():
    """`chat_kbli` injects `content` verbatim — so the section being CORRECT is
    worth nothing unless `build_cured_content` emits it.

    Added because mutation testing killed five of six mutants and this one
    SURVIVED: deleting the one line that appends the section left the whole
    corpus green, since every other test calls the renderer directly and the
    round-trip organ passes whether or not the section is there. Second time in
    one day that the surviving mutant was the WIRING, not the logic.
    """
    content = build_cured_content("96230", _canonical_by_code()["96230"])
    assert "## Kewajiban" in content
    assert "Sertifikat Laik Sehat" in content, (
        "the document the client is answered from does not carry the obligation"
    )


# ---------------------------------------------------------------------------
# --all-machine-template — the DELIVERY selector.
#
# Measured on the live table 2026-08-05: 1,563 rows, of which 299 are machine
# seeds, 316 are the 2026-02-17 editorial prose (`KBLI 55203: AKTIVITAS VILA` /
# `WHAT IT MEANS:` — no `#` heading, no `##` sections at all) and 948 carry a
# section outside the seed's. Without this selector the obligations builder
# reaches ZERO rows: the other three selectors together name a few dozen.
#
# The danger it must not have: a sectionless document makes
# "every `##` section is one of ours" VACUOUSLY TRUE, so a predicate written
# only as a subset test would classify all 316 pieces of hand-written editorial
# copy as machine template and destroy them.
# ---------------------------------------------------------------------------

_EDITORIAL_2026_02_17 = (
    "KBLI 55203: AKTIVITAS VILA\n\n"
    "WHAT IT MEANS:\n"
    "Villas - private houses exclusively rented out to tourists.\n\n"
    "BALI CONTEXT:\n"
    "The provincial moratorium applies.\n"
)


def test_the_sectionless_editorial_rows_are_not_swept_up_as_machine_template():
    """316 live rows look like this. A subset test alone says True on the empty
    set, so the predicate must ALSO require the machine heading — and these have
    `KBLI 55203:` with a colon and no `#`, which is not it."""
    assert is_machine_template("55203", _EDITORIAL_2026_02_17) is False
    assert rebuild_reason("55203", _EDITORIAL_2026_02_17, canonical_rows=4) is None


def test_a_document_with_the_heading_but_no_sections_is_still_refused():
    """The vacuous-truth case in isolation: right heading, zero sections.
    Nothing about it says the machine wrote it, so it is not rebuildable."""
    assert is_machine_template("55203", "# KBLI 55203 - Aktivitas Vila\n\nsome prose\n") is False


def test_the_delivery_selector_keeps_only_machine_seeds_and_names_the_rest():
    """The selector's whole job: pick the lossless population out of the table
    and leave the rest, rather than picking a code list by hand."""
    canonical = _canonical_by_code()
    machine = build_cured_content("96230", canonical["96230"])
    rows = {
        "96230": {"content": machine},
        "55203": {"content": _EDITORIAL_2026_02_17},
        "47401": {
            "content": "# KBLI 47401 - Retail\n\n## Informasi Umum\nx\n\n## Sejarah\nhand-written\n"
        },
    }
    kept, n_present = select_machine_template_rows(list(rows), rows)
    assert n_present == 3
    assert kept == ["96230"], (
        "the selector must keep the machine seed, refuse the sectionless editorial row, "
        "and refuse the row carrying a section outside the seed's"
    )


def test_the_delivered_document_is_the_one_that_carries_the_obligations():
    """Ties the selector to the point of the exercise: the rows this scope
    rebuilds are exactly the rows that gain `## Kewajiban`."""
    canonical = _canonical_by_code()
    content = build_cured_content("96230", canonical["96230"])
    assert is_machine_template("96230", content), "a delivered row must stay re-curable"
    assert "## Kewajiban" in content
    assert "Sertifikat Laik Sehat" in content


def test_a_code_the_table_does_not_hold_is_not_counted_as_present():
    """`--all-machine-template` queries every canonical code (1,559) against a
    table that holds 1,563 rows but not necessarily the same set. Counting a
    missing code as "present" both inflates the denominator the run reports and
    walks straight into a KeyError on the row lookup."""
    canonical = _canonical_by_code()
    rows = {"96230": {"content": build_cured_content("96230", canonical["96230"])}}
    kept, n_present = select_machine_template_rows(["96230", "00000", "99999"], rows)
    assert kept == ["96230"]
    assert n_present == 1, "only the row the table actually holds is present"


def test_main_uses_the_selector_rather_than_its_own_inline_filter():
    """A WIRING PIN, and labelled as one — not a behavioural test.

    `main()` opens a real asyncpg connection, so nothing in this suite executes
    it, and mutation testing proved the consequence: replacing the selector call
    in `main` with `list(codes)` — rebuild every row, editorial prose included —
    leaves all 81 tests green. This asserts, at the AST level, that the
    machine-template branch delegates to `select_machine_template_rows` instead
    of re-deriving the population inline, which is the only part of that
    mutation this suite can see.

    DECLARED GAP, measured not guessed: `main()` has no behavioural coverage, so
    this pin sees that the call EXISTS and not that its result is used. Mutation
    `if conflict:` -> `if False:` still SURVIVES the suite — the call remains,
    its verdict is dropped, and two scope selectors would silently be ranked
    instead of refused. Left as a declared gap rather than papered over with an
    AST rule about the shape of an `if`: what actually protects the rows is the
    selector's own tests plus this pin. Closing it needs `main` to take an
    injected connection, which is a refactor, not a test.
    """
    import ast

    src = _Path_obl(__file__).resolve()
    root = _repo_root_obl()
    tree = ast.parse(
        (root / "apps/backend-rag/backend/scripts/kbli_documents_cure.py").read_text(
            encoding="utf-8"
        )
    )
    main_fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "main"
    )
    called = {
        n.func.id
        for n in ast.walk(main_fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    for fn_name, what in (
        ("select_machine_template_rows", "an inline filter there is invisible to every test here"),
        ("selector_conflict", "an inline union check there is invisible to every test here"),
    ):
        assert fn_name in called, f"main() no longer calls {fn_name} ({src.name} pins this): {what}"


@pytest.mark.parametrize(
    "flags",
    [
        {"quarantined": True, "licensing_absent": True, "machine_template": False},
        {"quarantined": True, "licensing_absent": False, "machine_template": True},
        {"quarantined": False, "licensing_absent": True, "machine_template": True},
        {"quarantined": True, "licensing_absent": True, "machine_template": True},
    ],
)
def test_two_scope_selectors_together_are_refused_never_silently_ranked(flags):
    """They carry OPPOSITE duties — the quarantine scope destroys stored content
    on purpose, the table scope refuses to — so letting the if/elif chain pick a
    winner would destroy prose under a flag the operator thought was narrower."""
    from backend.scripts.kbli_documents_cure import selector_conflict

    msg = selector_conflict(**flags)
    assert msg is not None
    assert "refusing to union them" in msg
    for name, on in (
        ("--all-quarantined", flags["quarantined"]),
        ("--all-licensing-absent", flags["licensing_absent"]),
        ("--all-machine-template", flags["machine_template"]),
    ):
        assert (name in msg) is on, "the refusal must name exactly the selectors that were on"


@pytest.mark.parametrize(
    "flags",
    [
        {"quarantined": False, "licensing_absent": False, "machine_template": False},
        {"quarantined": True, "licensing_absent": False, "machine_template": False},
        {"quarantined": False, "licensing_absent": True, "machine_template": False},
        {"quarantined": False, "licensing_absent": False, "machine_template": True},
    ],
)
def test_one_selector_alone_is_never_refused(flags):
    from backend.scripts.kbli_documents_cure import selector_conflict

    assert selector_conflict(**flags) is None


# ---------------------------------------------------------------------------
# --cure-run CLI shape (round-2 fix, 2026-08-08): the pass id belongs to the
# invocation, not a script constant. A constant makes every pass share one
# cure_run, and a later pass's snapshot is silently skipped by ON CONFLICT.
#
# Round-3: tests import build_parser()/validate_args() from the SCRIPT so they
# exercise the REAL production parser + validation, never a copy rebuilt inside
# the test (which stays green if production validation is deleted).
# ---------------------------------------------------------------------------


from backend.scripts.kbli_documents_cure import build_parser as _cure_build_parser
from backend.scripts.kbli_documents_cure import validate_args as _cure_validate_args


def test_cure_run_required_when_apply_passed_cure():
    """GUILT: --apply without --cure-run must error out (validate_args → parser.error → exit 2)."""
    ap = _cure_build_parser()
    args = ap.parse_args(["--apply", "--only", "50113"])
    with pytest.raises(SystemExit) as exc:
        _cure_validate_args(ap, args)
    assert exc.value.code == 2


def test_cure_run_with_whitespace_rejected_cure():
    """GUILT: whitespace in --cure-run would corrupt the ON CONFLICT key."""
    ap = _cure_build_parser()
    args = ap.parse_args(["--cure-run", "has space", "--apply", "--only", "50113"])
    with pytest.raises(SystemExit) as exc:
        _cure_validate_args(ap, args)
    assert exc.value.code == 2


def test_dry_run_without_cure_run_is_fine_cure():
    """INNOCENCE: dry-run (no --apply) does not require --cure-run."""
    ap = _cure_build_parser()
    args = ap.parse_args(["--only", "50113"])
    assert args.cure_run is None
    assert args.apply is False
    assert _cure_validate_args(ap, args) == "dry-run"


def test_cure_run_strips_and_returns_clean_value_cure():
    """The resolved cure_run is the stripped value, not the raw arg."""
    ap = _cure_build_parser()
    args = ap.parse_args(["--apply", "--only", "50113", "--cure-run", "kbli_cure:2026-08-08"])
    assert _cure_validate_args(ap, args) == "kbli_cure:2026-08-08"


# ---------------------------------------------------------------------------
# CALL-SITE PIN (round-3): drive the apply path over one code and assert
# archive_row is invoked with the cure_run value passed on the CLI. The
# helper-level tests above cannot pin this — they exercise archive_row
# directly, not the script's call to it.
# ---------------------------------------------------------------------------


def test_apply_passes_cli_cure_run_to_archive_row_cure(monkeypatch):
    """The cure_run from --cure-run must reach archive_row verbatim."""
    monkeypatch.setattr(
        _sys,
        "argv",
        [
            "cure",
            "--only",
            "50113",
            "--apply",
            "--cure-run",
            "kbli_cure:2026-08-08",
        ],
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")

    async def _dataset(_source):
        return [RECORD_50113]

    class _ArchiveSpyConn:
        def __init__(self):
            self.archive_calls: list[tuple] = []

        async def execute(self, query: str, *args):
            return "OK"

        async def fetch(self, _sql, codes):
            return [
                {
                    "kode_kbli": "50113",
                    "judul": "STALE",
                    "content": "stale fabricated content",
                    "metadata": {},
                    "created_at": None,
                    "updated_at": None,
                }
            ]

        async def fetchval(self, _sql, *_a):
            return True  # has cure_run column + has composite constraint

        async def close(self):
            pass

    conn = _ArchiveSpyConn()

    async def _connect(_dsn):
        return conn

    monkeypatch.setattr(_cure, "load_dataset", _dataset)
    monkeypatch.setattr(_cure.asyncpg, "connect", _connect)

    # Spy on archive_row AS IMPORTED in the script module.
    archive_calls: list[dict] = []

    async def _spy_archive_row(_conn, _code, _params, cure_run, **kw):
        archive_calls.append({"cure_run": cure_run, **kw})

    monkeypatch.setattr(_cure, "archive_row", _spy_archive_row)

    _asyncio.run(_cure.main())

    assert len(archive_calls) == 1
    assert archive_calls[0]["cure_run"] == "kbli_cure:2026-08-08"


# ---------------------------------------------------------------------------
# --pma-only (2026-09-01). Measured on prod that day: the conformance detector
# named 11 `pma_status` divergences; 6 of the rows carried hand-written prose
# the full rebuild (`plan_cure`) would have replaced wholesale (and 03110 would
# have become a 55k-char document). Since v34 the channel never injects
# `content` — it reads the structured PMA tuple off `metadata` — so the honest
# cure for such a row is the tuple alone, with judul/content byte-identical.
from backend.scripts.kbli_documents_cure import (  # noqa: E402
    PMA_METADATA_KEYS,
    plan_pma_only,
    pma_tuple_delta,
)

HAND_WRITTEN_ROW_96210 = {
    "judul": "AKTIVITAS PENATAAN DAN PANGKAS RAMBUT",
    "content": (
        "KBLI 96210: AKTIVITAS PENATAAN DAN PANGKAS RAMBUT\n\nWHAT IT MEANS:\n"
        "Hair salon and barbershop — cutting, styling, coloring.\n\nBALI CONTEXT:\n"
        "Bali's expat areas are packed with premium salons."
    ),
    "metadata": {
        "judul": "AKTIVITAS PENATAAN DAN PANGKAS RAMBUT",
        "kode_kbli_2025": "96210",
        "licensing_status": "N/A",
        "per_skala": [{"skala": "Mikro", "kategori_risiko": "Rendah"}],
        "pma_status": "TERBUKA",
        "pp28_sources": ["96111"],
        "sektor_id": "S",
        "status_mapping": "MATCH_LANGSUNG",
    },
}

RECORD_96210_LOCATED = {
    "kode_kbli_2025": "96210",
    "judul": "Aktivitas Penataan dan Pangkas Rambut",
    "uraian": "Kelompok ini mencakup usaha jasa pelayanan penataan dan pangkas rambut.",
    "pma_status": "TERBATAS",
    "pma_max_asing": 0,
    "pma_verification_status": "located",
    "pma_official_basis": "Perpres 49/2021 Lampiran II (DIALOKASIKAN untuk Koperasi dan UMKM) fixture",
    "pma_source_vintage": "2021-05-25",
    "pma_cap_verified": True,
    # Deliberately DIFFERENT from the row's per_skala: a pma-only plan must not
    # touch it even when canonical disagrees — that is the full rebuild's job.
    "per_skala": [
        {"skala": "Mikro", "kategori_risiko": "Rendah"},
        {"skala": "Kecil", "kategori_risiko": "Rendah"},
    ],
}


def test_pma_only_guilt_syncs_the_tuple_and_nothing_else():
    plan = plan_pma_only("96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210)
    assert plan.pma_only is True
    assert plan.update_row is True
    # judul/content are never part of the plan — the apply path has nothing to write there.
    assert plan.new_judul is None
    assert plan.new_content is None
    old = HAND_WRITTEN_ROW_96210["metadata"]
    new = plan.new_metadata
    assert new["pma_status"] == "TERBATAS"
    assert new["pma_max_asing"] == 0
    assert new["pma_verification_status"] == "located"
    assert new["pma_official_basis"].startswith("Perpres 49/2021 Lampiran II")
    assert new["pma_source_vintage"] == "2021-05-25"
    assert new["pma_cap_verified"] is True
    assert new["pma_cap_special"] is False
    # Every key that is NOT in the tuple is carried over byte-identical —
    # including per_skala, which canonical disagrees with in this fixture.
    for key, value in old.items():
        if key not in PMA_METADATA_KEYS:
            assert new[key] == value, key
    assert set(new) - set(old) <= set(PMA_METADATA_KEYS)


def test_pma_only_writes_the_same_tuple_the_full_rebuild_would():
    """Two paths, one disclosure: a pma-only sync may never disagree with what
    `build_cured_metadata` writes for the same record (W105 — two tools that
    must agree about one fact)."""
    narrow = plan_pma_only("96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210).new_metadata
    full = build_cured_metadata("96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210["metadata"])
    assert {k: narrow[k] for k in PMA_METADATA_KEYS} == {k: full[k] for k in PMA_METADATA_KEYS}


def test_pma_only_really_differs_from_the_full_rebuild_on_a_hand_written_row():
    """The reason the mode exists: on this row the full rebuild REPLACES content."""
    full = plan_cure("96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210)
    assert full.update_row is True
    assert full.new_content is not None
    assert full.new_content != HAND_WRITTEN_ROW_96210["content"]
    assert full.new_metadata["per_skala"] == RECORD_96210_LOCATED["per_skala"]
    narrow = plan_pma_only("96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210)
    assert narrow.new_content is None
    assert narrow.new_metadata["per_skala"] == HAND_WRITTEN_ROW_96210["metadata"]["per_skala"]


def test_pma_only_innocence_is_idempotent():
    first = plan_pma_only("96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210)
    cured_row = {**HAND_WRITTEN_ROW_96210, "metadata": first.new_metadata}
    second = plan_pma_only("96210", RECORD_96210_LOCATED, cured_row)
    assert second.update_row is False
    assert second.new_metadata is None
    assert "already cured" in (second.skip_reason or "")


def test_pma_only_fails_closed_on_a_declared_gap_record():
    """A canonical record without a located basis+vintage must sync as
    NOT_VERIFIED / declared_gap — never as its raw working `pma_status`."""
    gap_record = {k: v for k, v in RECORD_96210_LOCATED.items() if k != "pma_official_basis"}
    plan = plan_pma_only("96210", gap_record, HAND_WRITTEN_ROW_96210)
    assert plan.update_row is True
    assert plan.new_metadata["pma_status"] == "NOT_VERIFIED"
    assert plan.new_metadata["pma_verification_status"] == "declared_gap"
    assert plan.new_metadata["pma_max_asing"] is None
    assert plan.new_metadata["pma_cap_verified"] is False


def test_pma_only_skips_when_canonical_or_table_is_missing():
    no_record = plan_pma_only("96210", None, HAND_WRITTEN_ROW_96210)
    assert no_record.update_row is False
    assert no_record.pma_only is True
    assert no_record.skip_reason == "not in canonical dataset"
    no_row = plan_pma_only("96210", RECORD_96210_LOCATED, None)
    assert no_row.update_row is False
    assert no_row.pma_only is True
    assert no_row.skip_reason == "not in kbli_documents table"


def test_pma_tuple_delta_names_only_the_keys_that_move():
    old = HAND_WRITTEN_ROW_96210["metadata"]
    new = plan_pma_only("96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210).new_metadata
    delta = pma_tuple_delta(old, new)
    assert delta.startswith("pma_status: 'TERBUKA' -> 'TERBATAS'")
    # The hand-written row never had the key: that is `<absent>`, not `None`.
    assert "pma_official_basis: <absent> -> " in delta
    # An unchanged tuple reports as empty, never as a list of no-ops.
    assert pma_tuple_delta(new, dict(new)) == ""


def test_parser_pma_only_requires_an_only_scope():
    ap = _cure_build_parser()
    args = ap.parse_args(["--pma-only"])
    with pytest.raises(SystemExit):
        _cure_validate_args(ap, args)


@pytest.mark.parametrize(
    "sweep", ["--all-quarantined", "--all-licensing-absent", "--all-machine-template"]
)
def test_parser_pma_only_refuses_every_sweep_selector(sweep):
    ap = _cure_build_parser()
    args = ap.parse_args(["--pma-only", "--only", "96210", sweep])
    with pytest.raises(SystemExit):
        _cure_validate_args(ap, args)


def test_parser_pma_only_with_only_is_accepted_in_both_modes():
    ap = _cure_build_parser()
    dry = ap.parse_args(["--pma-only", "--only", "96210,03110"])
    assert _cure_validate_args(ap, dry) == "dry-run"
    live = ap.parse_args(
        ["--pma-only", "--only", "96210", "--apply", "--cure-run", "kbli_cure:2026-09-01-pma-only"]
    )
    assert _cure_validate_args(ap, live) == "kbli_cure:2026-09-01-pma-only"


# --- refuter round 1 (Codex sol, 2026-09-01): the four findings, pinned ----------
from backend.scripts.kbli_documents_cure import pma_metadata_patch  # noqa: E402

_CURED_TUPLE_96210 = plan_pma_only(
    "96210", RECORD_96210_LOCATED, HAND_WRITTEN_ROW_96210
).new_metadata


def test_pma_only_reports_a_bool_int_confused_tuple_as_stale():
    """GUILT (MAJOR #2). `False == 0` and `1 == True` in Python, so a plain
    `!=` on the dicts called this row 'already cured' — while the channel's
    `_public_pma_cap` refuses a cap whose `pma_cap_verified` is not a real
    bool, i.e. the client was still told NOT_VERIFIED."""
    assert _CURED_TUPLE_96210 is not None
    coerced = dict(_CURED_TUPLE_96210)
    coerced["pma_max_asing"] = False  # canonical: 0
    coerced["pma_cap_special"] = 0  # canonical: False
    coerced["pma_cap_verified"] = 1  # canonical: True
    row = {**HAND_WRITTEN_ROW_96210, "metadata": coerced}
    plan = plan_pma_only("96210", RECORD_96210_LOCATED, row)
    assert plan.update_row is True, plan.skip_reason
    patch = pma_metadata_patch(plan.new_metadata)
    assert patch["pma_max_asing"] == 0 and type(patch["pma_max_asing"]) is int
    assert patch["pma_cap_special"] is False
    assert patch["pma_cap_verified"] is True
    # and the report names the three coercions, not an empty delta
    delta = pma_tuple_delta(coerced, plan.new_metadata)
    assert "pma_max_asing: False -> 0" in delta
    assert "pma_cap_special: 0 -> False" in delta
    assert "pma_cap_verified: 1 -> True" in delta


def test_pma_metadata_patch_binds_the_tuple_and_nothing_else():
    """BLOCKER #1. The UPDATE merges server-side; what crosses the wire is the
    seven keys, so `per_skala`, `pp28_sources`, ... are never re-encoded."""
    assert _CURED_TUPLE_96210 is not None
    patch = pma_metadata_patch(_CURED_TUPLE_96210)
    assert set(patch) == set(PMA_METADATA_KEYS)
    assert "per_skala" not in patch and "pp28_sources" not in patch


def test_pma_tuple_delta_names_an_absent_key_as_absent_not_as_none():
    """MINOR #4. A repair that only ADDS keys holding null used to render as an
    empty delta (`.get()` on both sides said None -> None). Absent -> null is a
    move; null -> null is not."""
    assert _CURED_TUPLE_96210 is not None
    without_basis = {k: v for k, v in _CURED_TUPLE_96210.items() if k != "pma_official_basis"}
    with_null_basis = {**_CURED_TUPLE_96210, "pma_official_basis": None}
    assert pma_tuple_delta(without_basis, with_null_basis) == (
        "pma_official_basis: <absent> -> None"
    )
    assert pma_tuple_delta(with_null_basis, dict(with_null_basis)) == ""


class _UpdateSpyConn:
    """asyncpg stand-in that RECORDS every execute() so the SQL the apply path
    really binds can be asserted — the plan-level tests cannot see it."""

    def __init__(self, rows):
        self._rows = rows
        self.executes: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args):
        self.executes.append((query, args))
        return "UPDATE 1"

    async def fetch(self, _sql, codes):
        return [r for r in self._rows if r["kode_kbli"] in codes]

    async def fetchval(self, _sql, *_a):
        return True  # archive schema already has cure_run + composite constraint

    async def close(self):
        return None

    def updates(self) -> list[tuple[str, tuple]]:
        return [
            (q, a)
            for q, a in self.executes
            if q.lstrip().upper().startswith("UPDATE KBLI_DOCUMENTS")
        ]


def _drive_apply(monkeypatch, argv, rows, dataset):
    monkeypatch.setattr(_sys, "argv", argv)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")
    conn = _UpdateSpyConn(rows)

    async def _dataset(_source):
        return list(dataset)

    async def _connect(_dsn):
        return conn

    archive_calls: list[dict] = []

    async def _spy_archive_row(_conn, code, params, cure_run, **kw):
        archive_calls.append({"code": code, "params": params, "cure_run": cure_run})

    monkeypatch.setattr(_cure, "load_dataset", _dataset)
    monkeypatch.setattr(_cure.asyncpg, "connect", _connect)
    monkeypatch.setattr(_cure, "archive_row", _spy_archive_row)
    rc = _asyncio.run(_cure.main())
    return rc, conn, archive_calls


_ROW_96210_IN_TABLE = {
    "kode_kbli": "96210",
    "created_at": None,
    "updated_at": None,
    **HAND_WRITTEN_ROW_96210,
}
_PMA_ONLY_APPLY_ARGV = [
    "cure",
    "--pma-only",
    "--only",
    "96210",
    "--apply",
    "--cure-run",
    "kbli_cure:2026-09-01-pma-only",
]


def test_main_pma_only_apply_merges_the_tuple_and_never_binds_judul_or_content(monkeypatch, caplog):
    """GUILT (MAJOR #3). Driven through main(): the mutation `if plan.pma_only`
    -> `if False` survived every plan-level test while the full UPDATE would
    have written `judul = NULL, content = NULL` on a hand-written row."""
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, archive_calls = _drive_apply(
            monkeypatch, _PMA_ONLY_APPLY_ARGV, [_ROW_96210_IN_TABLE], [RECORD_96210_LOCATED]
        )
    assert not rc  # main() returns None on success, a non-zero int on refusal
    updates = conn.updates()
    assert len(updates) == 1, [q for q, _ in conn.executes]
    sql, args = updates[0]
    # Left operand guarded by TYPE, not by coalesce: `'null'::jsonb || {..}`
    # builds an array, so an object-or-empty CASE is the only idempotent shape.
    assert (
        "(CASE WHEN jsonb_typeof(metadata) = 'object' THEN metadata ELSE '{}'::jsonb END) "
        "|| $2::text::jsonb"
    ) in sql
    assert "judul" not in sql and "content" not in sql
    # the predicate is pinned too: `<> $1` would cure every row but the target
    assert sql.rstrip().endswith("WHERE kode_kbli = $1")
    assert args[0] == "96210"
    bound = _json_obl.loads(args[1])
    assert set(bound) == set(PMA_METADATA_KEYS)
    assert bound["pma_status"] == "TERBATAS" and bound["pma_max_asing"] == 0
    assert bound["pma_verification_status"] == "located"
    # the snapshot is still taken, keyed by the CLI cure_run
    assert [c["cure_run"] for c in archive_calls] == ["kbli_cure:2026-09-01-pma-only"]
    assert archive_calls[0]["params"][2] == HAND_WRITTEN_ROW_96210["content"]
    messages = [r.getMessage() for r in caplog.records]
    assert not [m for m in messages if "content-preservation gate" in m], messages
    assert any("syncing metadata PMA tuple only" in m for m in messages), messages


def test_main_pma_only_dry_run_binds_no_update_and_takes_no_snapshot(monkeypatch, caplog):
    """INNOCENCE. Without --apply the same drive reports and writes nothing."""
    argv = [
        a
        for a in _PMA_ONLY_APPLY_ARGV
        if a not in ("--apply", "--cure-run", "kbli_cure:2026-09-01-pma-only")
    ]
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, archive_calls = _drive_apply(
            monkeypatch, argv, [_ROW_96210_IN_TABLE], [RECORD_96210_LOCATED]
        )
    assert not rc  # main() returns None on success, a non-zero int on refusal
    assert conn.updates() == []
    assert archive_calls == []
    assert any("would sync metadata PMA tuple only" in r.getMessage() for r in caplog.records)


def test_main_full_only_apply_still_rewrites_judul_and_content(monkeypatch):
    """INNOCENCE for the branch itself: the mutation `if plan.pma_only` ->
    `if True` would route every full rebuild through the merge and silently
    stop replacing prose. The plain `--only` apply must still bind all three."""
    argv = [a for a in _PMA_ONLY_APPLY_ARGV if a != "--pma-only"]
    rc, conn, _ = _drive_apply(monkeypatch, argv, [_ROW_96210_IN_TABLE], [RECORD_96210_LOCATED])
    assert not rc  # main() returns None on success, a non-zero int on refusal
    updates = conn.updates()
    assert len(updates) == 1
    sql, args = updates[0]
    assert "judul = $2, content = $3" in sql
    assert "||" not in sql
    assert sql.rstrip().endswith("WHERE kode_kbli = $1")
    assert args[1] is not None and args[2] is not None


# ---------------------------------------------------------------------------
# --licensing-only (2026-09-01, second narrow mode). Measured on prod that day:
# the detector's `licensing presence disagrees` class held 25 codes, every one
# a hand-written row (257-1,124 chars of prose) whose metadata carried
# `per_skala: []`, `licensing_status: "N/A"` and a seed-era `pp28_sources`
# array, while canonical holds real PP 28/2025 rows. The full rebuild would
# have replaced all 25 documents (up to 20k chars each); the content-
# preservation gate refuses exactly that. NOTE (grounded 2026-09-01): unlike the
# PMA tuple, NO runtime consumer reads these three keys off this table — the
# channel serves licensing from Qdrant text and `kg_nodes`. This mode buys
# table<->canonical agreement (detector class closes), not a channel change.
from backend.scripts.kbli_documents_cure import (  # noqa: E402
    LICENSING_METADATA_KEYS,
    licensing_metadata_from_canonical,
    licensing_metadata_patch,
    licensing_tuple_delta,
    metadata_patch,
    plan_licensing_only,
)

# The measured shape of the 25 rows: rows present-but-empty, a seed-era
# provenance list, no verdict — under hand-written prose.
HAND_WRITTEN_ROW_85510 = {
    "judul": "PENDIDIKAN OLAHRAGA DAN REKREASI",
    "content": (
        "KBLI 85510: PENDIDIKAN OLAHRAGA DAN REKREASI\n\nWHAT IT MEANS:\n"
        "Yoga studios, surf schools, dive instruction, retreat teaching.\n\n"
        "BALI CONTEXT:\nCanggu and Ubud are dense with them."
    ),
    "metadata": {
        "judul": "PENDIDIKAN OLAHRAGA DAN REKREASI",
        "kode_kbli_2025": "85510",
        "licensing_status": "N/A",
        "per_skala": [],
        "pma_status": "TERBUKA",
        "pp28_sources": ["seed-2026-02-18"],
        "sektor_id": "P",
        "status_mapping": "MATCH_LANGSUNG",
    },
}

RECORD_85510_SOURCED = {
    "kode_kbli_2025": "85510",
    "judul": "Pendidikan Olahraga dan Rekreasi",
    "uraian": "Kelompok ini mencakup kegiatan pendidikan olahraga dan rekreasi.",
    # Deliberately DIFFERENT from the row's PMA tuple: a licensing-only plan
    # must not touch it even when canonical disagrees — that is --pma-only's job.
    "pma_status": "TERBATAS",
    "pma_max_asing": 49,
    "pma_verification_status": "located",
    "pma_official_basis": "Perpres 10/2021 Lampiran III fixture",
    "pma_source_vintage": "2021-03-02",
    "pma_cap_verified": True,
    "per_skala": [
        {
            "skala": "Mikro",
            "kategori_risiko": "Rendah",
            "perizinan": "NIB",
            "kewenangan": "Bupati/Wali Kota",
        },
        {
            "skala": "Kecil",
            "kategori_risiko": "Menengah Rendah",
            "perizinan": "NIB dan Sertifikat Standar",
            "kewenangan": "Bupati/Wali Kota",
        },
    ],
    "pp28_sources": ["PP 28/2025 Lampiran I Sektor Pendidikan", "OSS RBA 2025"],
}


def test_licensing_only_guilt_syncs_the_tuple_and_nothing_else():
    plan = plan_licensing_only("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510)
    assert plan.licensing_only is True and plan.pma_only is False
    assert plan.partial_keys == LICENSING_METADATA_KEYS
    assert plan.update_row is True
    assert plan.new_judul is None and plan.new_content is None
    old = HAND_WRITTEN_ROW_85510["metadata"]
    new = plan.new_metadata
    assert new["per_skala"] == RECORD_85510_SOURCED["per_skala"]
    assert new["pp28_sources"] == RECORD_85510_SOURCED["pp28_sources"]
    # Non-empty canonical rows: the verdict is CARRIED OVER, never asserted.
    assert new["licensing_status"] == "N/A"
    # The PMA tuple canonical disagrees with is left exactly as stored.
    assert new["pma_status"] == "TERBUKA"
    assert "pma_official_basis" not in new
    for key, value in old.items():
        if key not in LICENSING_METADATA_KEYS:
            assert new[key] == value, key
    assert set(new) - set(old) <= set(LICENSING_METADATA_KEYS)


def test_licensing_only_writes_the_same_tuple_the_full_rebuild_would():
    """Two paths, one row-set (W105): the narrow sync and `build_cured_metadata`
    share ONE derivation, so they cannot disagree about these three keys."""
    narrow = plan_licensing_only("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510).new_metadata
    full = build_cured_metadata("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510["metadata"])
    assert {k: narrow[k] for k in LICENSING_METADATA_KEYS} == {
        k: full[k] for k in LICENSING_METADATA_KEYS
    }
    # and the shared derivation itself keeps the rebuild's gap rule
    gap = licensing_metadata_from_canonical({"per_skala": []}, {"licensing_status": "N/A"})
    assert gap == {"per_skala": [], "pp28_sources": None, "licensing_status": "PENDING_REGULATION"}


def test_licensing_only_really_differs_from_the_full_rebuild_on_a_hand_written_row():
    full = plan_cure("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510)
    assert full.update_row is True
    assert full.new_content != HAND_WRITTEN_ROW_85510["content"]
    assert full.new_metadata["pma_status"] == "TERBATAS"  # the rebuild moves the PMA tuple too
    narrow = plan_licensing_only("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510)
    assert narrow.new_content is None
    assert narrow.new_metadata["pma_status"] == "TERBUKA"


def test_licensing_only_innocence_is_idempotent():
    first = plan_licensing_only("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510)
    cured_row = {**HAND_WRITTEN_ROW_85510, "metadata": first.new_metadata}
    second = plan_licensing_only("85510", RECORD_85510_SOURCED, cured_row)
    assert second.update_row is False
    assert second.new_metadata is None
    assert "already cured" in (second.skip_reason or "")


def test_licensing_only_compares_row_content_not_row_count():
    """The detector measures `jsonb_array_length`; a same-length row-set with
    different content would satisfy it and still be stale. The plan compares
    the rows themselves."""
    same_count_other_rows = [
        {**row, "kategori_risiko": "Tinggi"} for row in RECORD_85510_SOURCED["per_skala"]
    ]
    row = {
        **HAND_WRITTEN_ROW_85510,
        "metadata": {
            **HAND_WRITTEN_ROW_85510["metadata"],
            "per_skala": same_count_other_rows,
            "pp28_sources": RECORD_85510_SOURCED["pp28_sources"],
        },
    }
    plan = plan_licensing_only("85510", RECORD_85510_SOURCED, row)
    assert plan.update_row is True
    assert plan.new_metadata["per_skala"] == RECORD_85510_SOURCED["per_skala"]


def test_licensing_only_refuses_to_empty_a_stored_row_set():
    """GUILT for the one-direction rule: canonical detached the rows (the
    quarantine class) while the table still serves them. Emptying them here
    would destroy a row-set while reporting a cure — the plan REFUSES."""
    detached = {**RECORD_85510_SOURCED, "per_skala": []}
    served = {
        **HAND_WRITTEN_ROW_85510,
        "metadata": {
            **HAND_WRITTEN_ROW_85510["metadata"],
            "per_skala": RECORD_85510_SOURCED["per_skala"],
        },
    }
    plan = plan_licensing_only("85510", detached, served)
    assert plan.update_row is False
    assert plan.new_metadata is None
    assert plan.licensing_only is True
    assert "--all-quarantined" in (plan.skip_reason or "")
    # and an honest gap on BOTH sides is equally not this mode's business —
    # no PENDING_REGULATION write sneaks in through the narrow door
    both_empty = plan_licensing_only("85510", detached, HAND_WRITTEN_ROW_85510)
    assert both_empty.update_row is False
    # INNOCENCE: a record whose per_skala key is missing entirely reads as
    # empty too — refused, not crashed, not emptied.
    no_key = {k: v for k, v in RECORD_85510_SOURCED.items() if k != "per_skala"}
    assert plan_licensing_only("85510", no_key, served).update_row is False


def test_licensing_only_skips_when_canonical_or_table_is_missing():
    no_record = plan_licensing_only("85510", None, HAND_WRITTEN_ROW_85510)
    assert no_record.update_row is False
    assert no_record.licensing_only is True
    assert no_record.skip_reason == "not in canonical dataset"
    no_row = plan_licensing_only("85510", RECORD_85510_SOURCED, None)
    assert no_row.update_row is False
    assert no_row.licensing_only is True
    assert no_row.skip_reason == "not in kbli_documents table"


def test_licensing_tuple_delta_shows_row_counts_not_the_blob():
    old = HAND_WRITTEN_ROW_85510["metadata"]
    new = plan_licensing_only("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510).new_metadata
    delta = licensing_tuple_delta(old, new)
    assert delta == "per_skala: <0 rows> -> <2 rows>, pp28_sources: <1 rows> -> <2 rows>"
    assert "Bupati" not in delta  # the rows themselves never reach the log line
    assert licensing_tuple_delta(new, dict(new)) == ""
    # the PMA delta helper is untouched by the generalisation
    assert pma_tuple_delta(old, new) == ""


def test_licensing_metadata_patch_binds_the_tuple_and_nothing_else():
    new = plan_licensing_only("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510).new_metadata
    patch = licensing_metadata_patch(new)
    assert set(patch) == set(LICENSING_METADATA_KEYS)
    assert "pma_status" not in patch and "judul" not in patch
    assert patch == metadata_patch(new, LICENSING_METADATA_KEYS)
    # a full-rebuild plan has no partial keys: the apply path must take the other branch
    assert plan_cure("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510).partial_keys is None


def test_parser_licensing_only_requires_an_only_scope():
    ap = _cure_build_parser()
    args = ap.parse_args(["--licensing-only"])
    with pytest.raises(SystemExit):
        _cure_validate_args(ap, args)


@pytest.mark.parametrize(
    "sweep", ["--all-quarantined", "--all-licensing-absent", "--all-machine-template"]
)
def test_parser_licensing_only_refuses_every_sweep_selector(sweep):
    ap = _cure_build_parser()
    args = ap.parse_args(["--licensing-only", "--only", "85510", sweep])
    with pytest.raises(SystemExit):
        _cure_validate_args(ap, args)


def test_parser_refuses_both_narrow_modes_at_once():
    ap = _cure_build_parser()
    args = ap.parse_args(["--licensing-only", "--pma-only", "--only", "85510"])
    with pytest.raises(SystemExit):
        _cure_validate_args(ap, args)


def test_parser_licensing_only_with_only_is_accepted_in_both_modes():
    ap = _cure_build_parser()
    dry = ap.parse_args(["--licensing-only", "--only", "85510,03231"])
    assert _cure_validate_args(ap, dry) == "dry-run"
    live = ap.parse_args(
        [
            "--licensing-only",
            "--only",
            "85510",
            "--apply",
            "--cure-run",
            "kbli_cure:2026-09-01-licensing-only",
        ]
    )
    assert _cure_validate_args(ap, live) == "kbli_cure:2026-09-01-licensing-only"


_ROW_85510_IN_TABLE = {
    "kode_kbli": "85510",
    "created_at": None,
    "updated_at": None,
    **HAND_WRITTEN_ROW_85510,
}
_LICENSING_ONLY_APPLY_ARGV = [
    "cure",
    "--licensing-only",
    "--only",
    "85510",
    "--apply",
    "--cure-run",
    "kbli_cure:2026-09-01-licensing-only",
]


def test_main_licensing_only_apply_merges_the_tuple_and_never_binds_judul_or_content(
    monkeypatch, caplog
):
    """GUILT, driven through main(): the dispatch `elif args.licensing_only`
    and the `partial_keys` branch of the apply path are what keep a hand-
    written row's judul/content out of the UPDATE."""
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, archive_calls = _drive_apply(
            monkeypatch, _LICENSING_ONLY_APPLY_ARGV, [_ROW_85510_IN_TABLE], [RECORD_85510_SOURCED]
        )
    assert not rc
    updates = conn.updates()
    assert len(updates) == 1, [q for q, _ in conn.executes]
    sql, args = updates[0]
    assert (
        "(CASE WHEN jsonb_typeof(metadata) = 'object' THEN metadata ELSE '{}'::jsonb END) "
        "|| $2::text::jsonb"
    ) in sql
    assert "judul" not in sql and "content" not in sql
    assert sql.rstrip().endswith("WHERE kode_kbli = $1")
    assert args[0] == "85510"
    bound = _json_obl.loads(args[1])
    assert set(bound) == set(LICENSING_METADATA_KEYS)
    assert bound["per_skala"] == RECORD_85510_SOURCED["per_skala"]
    assert bound["pp28_sources"] == RECORD_85510_SOURCED["pp28_sources"]
    assert bound["licensing_status"] == "N/A"
    assert [c["cure_run"] for c in archive_calls] == ["kbli_cure:2026-09-01-licensing-only"]
    assert archive_calls[0]["params"][2] == HAND_WRITTEN_ROW_85510["content"]
    messages = [r.getMessage() for r in caplog.records]
    assert not [m for m in messages if "content-preservation gate" in m], messages
    assert not [m for m in messages if "OVERWRITE" in m], messages
    assert any(
        "syncing metadata licensing tuple only" in m and "per_skala: <0 rows> -> <2 rows>" in m
        for m in messages
    ), messages


def test_main_licensing_only_dry_run_binds_no_update_and_takes_no_snapshot(monkeypatch, caplog):
    argv = [
        a
        for a in _LICENSING_ONLY_APPLY_ARGV
        if a not in ("--apply", "--cure-run", "kbli_cure:2026-09-01-licensing-only")
    ]
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, archive_calls = _drive_apply(
            monkeypatch, argv, [_ROW_85510_IN_TABLE], [RECORD_85510_SOURCED]
        )
    assert not rc
    assert conn.updates() == []
    assert archive_calls == []
    assert any("would sync metadata licensing tuple only" in r.getMessage() for r in caplog.records)


def test_main_licensing_only_refusal_on_a_detached_code_binds_nothing(monkeypatch, caplog):
    """The one-direction rule survives the drive: a detached canonical record
    under --apply produces no UPDATE, no snapshot, and a named SKIP."""
    detached = {**RECORD_85510_SOURCED, "per_skala": []}
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, archive_calls = _drive_apply(
            monkeypatch, _LICENSING_ONLY_APPLY_ARGV, [_ROW_85510_IN_TABLE], [detached]
        )
    assert not rc
    assert conn.updates() == []
    assert archive_calls == []
    assert any(
        "SKIP 85510" in r.getMessage() and "--all-quarantined" in r.getMessage()
        for r in caplog.records
    )


def test_main_pma_only_apply_still_binds_only_the_pma_tuple_after_the_generalisation(
    monkeypatch,
):
    """INNOCENCE for the shared apply branch: `partial_keys` must resolve to
    the SEVEN PMA keys under --pma-only, never to the licensing tuple."""
    rc, conn, _ = _drive_apply(
        monkeypatch, _PMA_ONLY_APPLY_ARGV, [_ROW_96210_IN_TABLE], [RECORD_96210_LOCATED]
    )
    assert not rc
    ((_, args),) = conn.updates()
    bound = _json_obl.loads(args[1])
    assert set(bound) == set(PMA_METADATA_KEYS)
    assert "per_skala" not in bound


# --- refuter round 1 (Codex sol, 2026-09-01) on --licensing-only: folded ------


@pytest.mark.parametrize(
    "malformed",
    ["NIB dan Sertifikat Standar", {"skala": "Mikro"}, 3],
    ids=["str", "dict", "int"],
)
def test_licensing_only_refuses_a_malformed_canonical_row_set(malformed):
    """MAJOR #3a. Truthiness alone would have WRITTEN a non-empty string or
    object as `per_skala` (and `jsonb_array_length` would then fail at the
    detector). Shape is refused, named, and never reaches the UPDATE."""
    record = {**RECORD_85510_SOURCED, "per_skala": malformed}
    plan = plan_licensing_only("85510", record, HAND_WRITTEN_ROW_85510)
    assert plan.update_row is False
    assert plan.new_metadata is None
    assert plan.is_gap is None
    assert "not a list" in (plan.skip_reason or "")


def test_main_licensing_only_malformed_canonical_binds_nothing(monkeypatch, caplog):
    record = {**RECORD_85510_SOURCED, "per_skala": "NIB"}
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, archive_calls = _drive_apply(
            monkeypatch, _LICENSING_ONLY_APPLY_ARGV, [_ROW_85510_IN_TABLE], [record]
        )
    assert not rc
    assert conn.updates() == [] and archive_calls == []
    assert any("not a list" in r.getMessage() for r in caplog.records)


def test_main_licensing_only_second_run_on_string_metadata_is_a_no_op(monkeypatch, caplog):
    """MINOR #5. asyncpg can hand `metadata` back as a JSON STRING; `main()`
    decodes it before planning. A cured row re-read that way must be a
    declared no-op — no snapshot, no UPDATE — or the mode is not idempotent
    against the real driver. (The mutant that drops the `json.loads` branch
    is what this catches: a str has no `.get`.)"""
    cured = plan_licensing_only("85510", RECORD_85510_SOURCED, HAND_WRITTEN_ROW_85510).new_metadata
    row = {**_ROW_85510_IN_TABLE, "metadata": _json_obl.dumps(cured, ensure_ascii=False)}
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, archive_calls = _drive_apply(
            monkeypatch, _LICENSING_ONLY_APPLY_ARGV, [row], [RECORD_85510_SOURCED]
        )
    assert not rc
    assert conn.updates() == [] and archive_calls == []
    assert any(
        "SKIP 85510" in r.getMessage() and "already cured" in r.getMessage() for r in caplog.records
    )


def test_main_summary_states_n_of_m(monkeypatch, caplog):
    """MINOR #6 (W97). Two codes asked, one cured, one not in the table: the
    summary must carry the denominator, not a bare count."""
    argv = [a if a != "85510" else "85510,03231" for a in _LICENSING_ONLY_APPLY_ARGV]
    record_03231 = {**RECORD_85510_SOURCED, "kode_kbli_2025": "03231"}
    with caplog.at_level(_logging.INFO, logger=_cure.logger.name):
        rc, conn, _ = _drive_apply(
            monkeypatch, argv, [_ROW_85510_IN_TABLE], [RECORD_85510_SOURCED, record_03231]
        )
    assert not rc
    assert len(conn.updates()) == 1
    messages = [r.getMessage() for r in caplog.records]
    assert any("APPLIED: 1 of 2 code(s) cured | 1 skipped" in m for m in messages), messages
