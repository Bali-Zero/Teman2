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

import pytest

from backend.scripts.kbli_documents_cure import (
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
            "level and \"Standard Certificate / LSPr self-assessment\" shown here previously "
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
    "per_skala_disputed_pp28_collision": [{"kategori_risiko": "Menengah Tinggi", "kewenangan": ["Gubernur"]}],
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
    "per_skala": [{"skala_usaha": ["Besar"], "kategori_risiko": "Menengah Tinggi", "perizinan": ["NIB"]}],
}

NARROW_CAPITAL_DENY_LIST = ("Rp 10", "Modal Disetor", "modal disetor", "paid-up capital", "Ten Billion")

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


def test_gap_code_68112_perizinan_is_whatyouneed_verbatim_no_synthesized_bullet():
    section = build_perizinan_section(RECORD_68112)
    assert section == RECORD_68112["intel_2026"]["whatYouNeed"]
    assert _SYNTHESIZED_BULLET_PREFIX not in section


def test_gap_code_50113_content_never_contains_capital_deny_tokens():
    content = build_cured_content("50113", RECORD_50113)
    for token in NARROW_CAPITAL_DENY_LIST:
        assert token not in content, f"unexpected capital-figure token {token!r} in cured content"


def test_gap_code_68112_content_never_contains_capital_deny_tokens():
    content = build_cured_content("68112", RECORD_68112)
    for token in NARROW_CAPITAL_DENY_LIST:
        assert token not in content, f"unexpected capital-figure token {token!r} in cured content"


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
    meta = build_cured_metadata("50113", RECORD_50113, old_metadata={"per_skala": [{"fabricated": True}]})
    assert meta["per_skala"] == []
    assert meta["licensing_status"] == "PENDING_REGULATION"


def test_cured_metadata_restored_code_per_skala_replaced_with_real_rows():
    meta = build_cured_metadata("49213", RECORD_49213, old_metadata={"per_skala": [{"fabricated": True}]})
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
    current_row = {"judul": "x", "content": "y", "metadata": None, "created_at": None, "updated_at": None}
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
    script = _pin_detector(monkeypatch, tmp_path, _Proc(4, stdout="CANNOT VERIFY: table snapshot unavailable"))
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
    assert _cure.find_conformance_script(_Path("/app/backend/scripts/kbli_documents_cure.py")) is None


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

    def _detector_down(_script):
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
