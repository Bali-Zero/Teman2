"""Tests for cure_pr2b_source_rows_93114_43110.py (SAETTA-20260915 W-H PR-2b).

Fabricated in-memory records pin plan()'s structural logic, with an explicit
verdicts dict standing in for classify()'s premise judgement (guilt: a
malformed precondition refuses; innocence: the real shape produces the
spec's patch). TestPremisePinning uses the ACTUAL pre-cure field values —
copied from origin/main and `repr()`-round-tripped rather than hand-typed,
so a transcription slip can't silently produce a hash that happens to pass —
to exercise `classify()` against the spec's real pins. TestRealCatalogue
checks the actually-applied canonical, including that a second `--apply` is
a byte-identical no-op.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import cure_pr2b_source_rows_93114_43110 as cure  # noqa: E402
import _hardened_cure_io as H  # noqa: E402

SPEC = json.loads(cure.SPEC_PATH.read_text(encoding="utf-8"))
PATCH_BOTH = {"93114": "patch", "43110": "patch"}
GOLF_ROW = {"skala_usaha": ["Menengah", "Besar"], "kategori_risiko": "Tinggi"}
LEGACY_3 = [
    {"skala_usaha": ["Mikro", "Kecil", "Menengah"], "parameter": "BUJKN"},
    {"skala_usaha": ["Besar"], "parameter": "BUJK dan Kantor Perwakilan BUJKA"},
    {"skala_usaha": ["Mikro"], "perizinan": "NIB dan Sertifikat Standar 1", "parameter": "Usaha Orang Perseorangan"},
]

# Origin/main's EXACT pre-cure field values for both records, pinned by the
# spec's `old_sha256`. `repr()`-round-tripped from the live canonical rather
# than hand-typed so a copy/paste slip can't silently drift the hash these
# tests exercise. Confirmed to hash to the spec's pins in the PR review.
PRE_93114_PER_SKALA = [{'skala_usaha': ['Mikro', 'Kecil', 'Menengah'], 'kategori_risiko': 'Menengah Rendah', 'perizinan': 'NIB dan Sertifikat Standar', 'persyaratan': [], 'jangka_waktu': 'Otomatis', 'kewajiban': ['Menyampaikan laporan kegiatan secara berkala', 'Memiliki Sertifikat Laik Sehat', 'Menyampaikan dokumen penerapan standar'], 'pb_umku': ['Sertifikat Laik Sehat'], 'parameter': 'Seluruh', 'kewenangan': 'Bupati/Walikota', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True}]

PRE_93114_DISPUTED = [{'skala_usaha': ['Menengah', 'Besar'], 'kategori_risiko': 'Tinggi', 'perizinan': 'NIB dan Izin', 'persyaratan': ['Memiliki Penilaian Mandiri Kesiapan Penerapan Standar'], 'jangka_waktu': '14 Hari', 'kewajiban': ['Memiliki Sertifikat Standar Usaha Pariwisata yang diterbitkan oleh LSPr', 'Menerapkan standar usaha Fasilitas Lapangan Golf meliputi Sarana, Struktur Organisasi dan SDM, Pelayanan, Produk usaha dan Sistem Manajemen Usaha', 'Memiliki Sertifikat laik sehat'], 'pb_umku': ['Sertifikat Laik Sehat'], 'parameter': 'Seluruh', 'kewenangan': 'Menteri/ Kepala Badan', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True}]

PRE_93114_DATA_NOTE = "action: partial_detach — only the Tinggi-risk tier (Menengah/Besar scale, golf-course-specific 'Fasilitas Lapangan Golf' scope) is moved into the disputed key; the Menengah Rendah tier (Mikro/Kecil/Menengah scale) is left completely untouched in per_skala, byte-identical. Confirmed two-tier record (Lot 8 gate report §3.4): Tier 1 (Mikro/Kecil/Menengah, Menengah Rendah risk) is fully verified — own PP28 row (394946 p.182, no.47) matches verbatim, and that row's own text explicitly excludes golf facilities ('...dan sejenisnya KECUALI Lapangan Golf'). Tier 2 (Menengah/Besar, Tinggi risk, Menteri/Kepala Badan authority, 'Fasilitas Lapangan Golf' kewajiban scope) has zero PP28 backing captured anywhere in the dossier — Lot 8 held this code entirely un-cured because cure_canonical_collisions.py had no per-tier selector (Lot 8 PENDING-ARMS §3.4/§5.1b); that primitive now exists (PR #2921, action: partial_detach + tier_selector, 2026-07-21) and is applied here for the first time program-wide. Forcing a whole-array detach (the only option Lot 8 had) would have destroyed Tier 1's genuinely-sourced, verified data — the tier-scoped selector avoids that trade entirely. pp28_sources=['93114'] (self-referential, own-code) is untouched — only the per-tier CONTENT was disputed, not the source citation."

PRE_93114_L4_BALI = {'status': 'APERTO_BALI_RISCHIO_ALTO', 'reason': "[derivation under review] Nationally TERBUKA and the Besar scale is 'Tinggi' -> survives the Bali moratorium (which blocks only Rendah/Menengah Rendah). Registrable by a PT PMA in Bali. [NB-3 28 June 2026] — NOTE: the risk tier this verdict cites is no longer among this code's licensing rows — it was set aside as unverifiable while other rows were kept — so the verdict cannot be re-derived from what the record now holds; verdict pending re-derivation from the true risk tier (GARUDA-FILIERA).", 'confidence': 'LOW', 'needs_review': True, 'blocked': False, 'from_2020': None, 'moratorium': {'rule': 'Bali province blocks ALL Low + Medium-Low risk KBLI for PMA (island-wide, permanent)', 'effective': '2026-05-13', 'source': 'Gubernur letter B.27.000/642/PM/DPMPTSP', 'virtual_office': 'BANNED as PMA domicile in Bali'}, 'review_basis': 'nb3_2026_06_28_moratoria_risk_tier', 'verdict_state': 'provisional'}

PRE_43110_PER_SKALA = [{'skala_usaha': ['Mikro'], 'kategori_risiko': 'Menengah Rendah', 'jangka_waktu': 'Otomatis', 'scope_index': 0, 'scope_uraian': 'Kode Subklasifikasi Pembongkaran Bangunan: PL011', 'perizinan': [], 'persyaratan': [], 'kewajiban': ['Menyampaikan Laporan Kegiatan Usaha Tahunan', 'SKK masih berlaku', 'Melaksanakan ketentuan dalam peraturan perundang undangan di bidang jasa konstruksi'], 'kewenangan': ['Bupati/Walikota'], 'jangka_waktu_source': 'PP28_rule_risk_class', 'fiktif_positif': False}]

PRE_43110_LEGACY = [{'skala_usaha': ['Mikro', 'Kecil', 'Menengah'], 'kategori_risiko': 'Menengah Tinggi', 'perizinan': 'NIB dan Sertifikat Standar', 'persyaratan': ['Standar Penetapan Kemampuan Badan Usaha Jasa Konstruksi / Sertifikat Badan Usaha (SBU) Subklasifikasi: PL001', 'Merupakan BUJKN bukan usaha orang perseorangan'], 'jangka_waktu': '15 Hari', 'kewajiban': ['Menyampaikan Laporan Kegiatan Usaha Tahunan', 'SBU masih berlaku', 'Melaksanakan ketentuan dalam peraturan perundang-undangan di bidang jasa konstruksi'], 'pb_umku': [], 'parameter': 'BUJKN dengan skala usaha Mikro, Kecil, Menengah', 'kewenangan': 'Bupati/Walikota', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True}, {'skala_usaha': ['Besar'], 'kategori_risiko': 'Menengah Tinggi', 'perizinan': 'NIB dan Sertifikat Standar', 'persyaratan': ['Standar Penetapan Kemampuan Badan Usaha Jasa Konstruksi / Sertifikat Badan Usaha (SBU) Subklasifikasi: PL001', 'Untuk Kantor Perwakilan BUJKA: a. Merupakan badan usaha jasa konstruksi berbadan hukum di negara asal b. Membayar biaya administrasi perizinan berusaha per jenis usaha sesuai peraturan perundang-undangan yang berlaku', 'Untuk BUJK PMA: a. Penanam modal asing/ pemegang saham asing merupakan badan usaha jasa konstruksi berbadan hukum di negara asal yang dibuktikan dengan: 1) Akta pendirian yang dilegalisasi 2) Sertifikat perizinan bidang usaha jasa konstruksi berkualifikasi Besar di negara asal atau yang sejenis yang dilegalisasi b. Penanam modal dalam negeri/ pemegang saham dalam negeri merupakan badan usaha jasa konstruksi nasional berkualifikasi Besar yang dibuktikan dengan: 1) Perizinan berusaha subsektor jasa konstruksi 2) Sertifikat Badan Usaha subsektor jasa konstruksi'], 'jangka_waktu': '15 Hari', 'kewajiban': ['Menyampaikan Laporan Kegiatan Usaha Tahunan', 'SBU masih berlaku', 'Melaksanakan ketentuan dalam peraturan perundang-undangan di bidang jasa konstruksi', 'Untuk Kantor Perwakilan BUJKA: a. Melakukan perpanjangan Sertifikat Standar sesuai subklasifikasi setiap 3 tahun b. Melakukan Kerja Sama Operasi (KSO) dengan BUJKN berkualifikasi Besar dan memiliki klasifikasi/ subklasifikasi sejenis yang tercatat di lembaga pengembangan jasa konstruksi sebelum mengikuti proses pemilihan c. KSO untuk pelaksanaan Pekerjaan Konstruksi atau Pekerjaan Konstruksi Terintegrasi dilaksanakan dengan ketentuan kriteria teknis KSO sebagai berikut: 1) Paling rendah 50% (lima puluh persen) dari nilai biaya pekerjaan konstruksi dikerjakan di dalam negeri 2) Paling rendah 30% (tiga puluh persen) dari nilai biaya pekerjaan pelaksanaan konstruksi dikerjakan oleh BUJKN mitra KSO'], 'pb_umku': [], 'parameter': 'BUJK dan Kantor Perwakilan BUJKA', 'kewenangan': 'Menteri/ Kepala Badan', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True}, {'skala_usaha': ['Mikro'], 'kategori_risiko': 'Menengah Rendah', 'perizinan': 'NIB dan Sertifikat Standar 1', 'persyaratan': [], 'jangka_waktu': 'Otomatis', 'kewajiban': ['Menyampaikan Laporan Kegiatan Usaha Tahunan', 'SKK masih berlaku', 'Melaksanakan ketentuan dalam peraturan perundang-undangan di bidang jasa konstruksi'], 'pb_umku': [], 'parameter': 'Usaha Orang Perseorangan dengan skala usaha Mikro', 'kewenangan': 'Bupati/Walikota', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True}]

PRE_43110_L4_BALI = {'status': 'BLOCCATO_DIPENDE_SCOPE', 'reason': 'Reserved to Koperasi/UMKM only as to a NAMED sub-activity — Perpres 10/2021 Pasal 5(5) scopes a Lampiran II reservation to the activity named in the Bidang Usaha column, not to the whole KBLI code. Lampiran II p.10, entry 37 *"Pembongkaran yang menggunakan teknologi sederhana dan madya"*, KBLI 43110, *dialokasikan* — Pasal 5(5) scopes it to that segment. **PP 28/2025 Lampiran I.H entry 39 publishes a Besar row written expressly for "BUJK PMA"** The rest of the code is not reserved; the answer depends on the scope actually declared. [Perpres annex]', 'confidence': 'HIGH', 'needs_review': False, 'blocked': True, 'from_2020': None, 'moratorium': {'rule': 'Bali province blocks ALL Low + Medium-Low risk KBLI for PMA (island-wide, permanent)', 'effective': '2026-05-13', 'source': 'Gubernur letter B.27.000/642/PM/DPMPTSP', 'virtual_office': 'BANNED as PMA domicile in Bali'}, 'verdict': 'NO_BESAR', 'rule': 'per-scala-Besar (OSS risk at scale Besar; PMA is Besar by law)', 'review_basis': 'perpres_adjudication_2026_08_03', 'verdict_state': 'blocked'}


def _rec93114(**overrides) -> dict:
    rec = {
        "kode_kbli_2025": "93114",
        "per_skala": [{"skala_usaha": ["Mikro", "Kecil", "Menengah"], "kategori_risiko": "Menengah Rendah"}],
        "per_skala_disputed_pp28_collision": [copy.deepcopy(GOLF_ROW)],
        "_data_note": "stale",
        "l4_bali": {"status": "APERTO_BALI_RISCHIO_ALTO", "blocked": False, "review_basis": "x"},
    }
    rec.update(overrides)
    return rec


def _rec43110(legacy=None, **overrides) -> dict:
    rec = {
        "kode_kbli_2025": "43110",
        "per_skala": [{"skala_usaha": ["Mikro"], "kategori_risiko": "Menengah Rendah"}],
        "per_skala_legacy": legacy if legacy is not None else copy.deepcopy(LEGACY_3),
        "l4_bali": {"status": "BLOCCATO_DIPENDE_SCOPE", "blocked": True, "verdict": "NO_BESAR", "rule": "x", "review_basis": "y"},
    }
    rec.update(overrides)
    return rec


def _pre93114(**overrides) -> dict:
    rec = {
        "kode_kbli_2025": "93114",
        "per_skala": copy.deepcopy(PRE_93114_PER_SKALA),
        "per_skala_disputed_pp28_collision": copy.deepcopy(PRE_93114_DISPUTED),
        "_data_note": PRE_93114_DATA_NOTE,
        "l4_bali": copy.deepcopy(PRE_93114_L4_BALI),
    }
    rec.update(overrides)
    return rec


def _pre43110(**overrides) -> dict:
    rec = {
        "kode_kbli_2025": "43110",
        "per_skala": copy.deepcopy(PRE_43110_PER_SKALA),
        "per_skala_legacy": copy.deepcopy(PRE_43110_LEGACY),
        "l4_bali": copy.deepcopy(PRE_43110_L4_BALI),
    }
    rec.update(overrides)
    return rec


class TestGuilt:
    def test_missing_disputed_key_raises(self):
        rec = _rec93114()
        del rec["per_skala_disputed_pp28_collision"]
        with pytest.raises(H.CureError, match="nothing to restore"):
            cure.plan([rec, _rec43110()], SPEC, PATCH_BOTH)

    def test_legacy_wrong_count_raises(self):
        rec = _rec43110(legacy=[copy.deepcopy(LEGACY_3[0])])
        with pytest.raises(H.CureError, match="exactly 3 rows"):
            cure.plan([_rec93114(), rec], SPEC, PATCH_BOTH)

    def test_code_missing_raises(self):
        with pytest.raises(H.CureError, match="93114: not in canonical"):
            cure.plan([_rec43110()], SPEC, PATCH_BOTH)

    def test_noop_verdict_skips_structural_read(self):
        """A code classified "noop" is never read structurally — a second
        run on an already-cured record (disputed key long gone) must not
        raise "nothing to restore"; it must simply not be planned at all."""
        rec = _rec93114()
        del rec["per_skala_disputed_pp28_collision"]
        items = cure.plan([rec, _rec43110()], SPEC, {"93114": "noop", "43110": "patch"})
        assert "93114" not in items


class TestInnocence:
    def test_93114_gains_golf_row_and_drops_stale_keys(self):
        items = cure.plan([_rec93114(), _rec43110()], SPEC, PATCH_BOTH)
        item = items["93114"]
        assert len(item["per_skala"]) == 2
        assert item["per_skala"][1] == GOLF_ROW
        assert set(item["drop_keys"]) == {"per_skala_disputed_pp28_collision", "_data_note"}

    def test_43110_keeps_all_three_legacy_rows(self):
        items = cure.plan([_rec93114(), _rec43110()], SPEC, PATCH_BOTH)
        assert len(items["43110"]["per_skala"]) == 3

    def test_43110_row3_perizinan_artifact_is_fixed(self):
        items = cure.plan([_rec93114(), _rec43110()], SPEC, PATCH_BOTH)
        assert items["43110"]["per_skala"][2]["perizinan"] == "NIB dan Sertifikat Standar"

    def test_apply_item_flips_43110_blocked_and_drops_no_besar_vocabulary(self):
        rec = _rec43110()
        items = cure.plan([_rec93114(), rec], SPEC, PATCH_BOTH)
        cure.apply_item(rec, items["43110"])
        assert rec["l4_bali"]["blocked"] is False
        for stale in ("verdict", "rule", "review_basis"):
            assert stale not in rec["l4_bali"]
        assert rec["l4_bali"]["verdict_state"] == "provisional"

    def test_apply_item_93114_drops_data_note(self):
        rec = _rec93114()
        items = cure.plan([rec, _rec43110()], SPEC, PATCH_BOTH)
        cure.apply_item(rec, items["93114"])
        assert "_data_note" not in rec
        assert rec["l4_bali"]["blocked"] is False


class TestPremisePinning:
    """classify() against the spec's REAL pins, using origin/main's exact
    pre-cure field values — not a fabricated shape, the actual bytes the
    review's mutation probe was run against."""

    def test_exact_pre_cure_state_classifies_as_patch(self):
        assert cure.classify(_pre93114(), "93114", SPEC["93114"]["premises"]) == "patch"
        assert cure.classify(_pre43110(), "43110", SPEC["43110"]["premises"]) == "patch"

    def test_altered_cell_in_93114_disputed_source_row_refuses(self):
        """One altered cell in the disputed golf row the compiler reads —
        a RENDAH-MOVED-style mutation — matches neither pin: refuse."""
        rec = _pre93114()
        rec["per_skala_disputed_pp28_collision"][0]["kategori_risiko"] = "Rendah"
        with pytest.raises(H.CureError, match="drifted under this adjudication"):
            cure.classify(rec, "93114", SPEC["93114"]["premises"])

    def test_altered_cell_in_43110_legacy_source_row_refuses(self):
        rec = _pre43110()
        rec["per_skala_legacy"][1]["kategori_risiko"] = "Rendah"
        with pytest.raises(H.CureError, match="drifted under this adjudication"):
            cure.classify(rec, "43110", SPEC["43110"]["premises"])

    def test_drifted_current_per_skala_refuses(self):
        rec = _pre43110()
        rec["per_skala"][0]["kategori_risiko"] = "MUTATED"
        with pytest.raises(H.CureError, match="drifted under this adjudication"):
            cure.classify(rec, "43110", SPEC["43110"]["premises"])

    def test_partial_application_disagreement_refuses(self):
        """per_skala already cured (hashes to its own new_sha256 pin) but
        l4_bali still pre-cure — a partial, inconsistent application —
        refuses rather than picking a side."""
        rec = _pre93114()
        rec["per_skala"] = list(PRE_93114_PER_SKALA) + copy.deepcopy(PRE_93114_DISPUTED)
        with pytest.raises(H.CureError, match="premises disagree on state"):
            cure.classify(rec, "93114", SPEC["93114"]["premises"])


class TestRealCatalogue:
    @classmethod
    @pytest.fixture(scope="class")
    def records(cls):
        payload = json.loads(cure.CANONICAL.read_text(encoding="utf-8"))
        return {r["kode_kbli_2025"]: r for r in payload["data"]}

    def test_93114_two_rows_no_disputed_key_no_data_note(self, records):
        rec = records["93114"]
        assert len(rec["per_skala"]) == 2
        assert "per_skala_disputed_pp28_collision" not in rec
        assert "_data_note" not in rec

    def test_43110_three_rows_and_fixed_perizinan(self, records):
        rows = records["43110"]["per_skala"]
        assert len(rows) == 3
        assert rows[2]["perizinan"] == "NIB dan Sertifikat Standar"

    def test_43110_blocked_false(self, records):
        assert records["43110"]["l4_bali"]["blocked"] is False

    def test_classify_both_codes_noop_on_the_live_canonical(self, records):
        for code in ("93114", "43110"):
            assert cure.classify(records[code], code, SPEC[code]["premises"]) == "noop"

    def test_second_apply_is_a_byte_identical_noop(self):
        before = cure.CANONICAL.read_bytes()
        exit_code = cure.main(["--apply"])
        after = cure.CANONICAL.read_bytes()
        assert exit_code == 0
        assert before == after
