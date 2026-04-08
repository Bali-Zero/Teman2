"""Tests for LHKPN PDF parser — dataclasses, parse_rp, properties, vehicles, full PDF.

TDD: tests written first, then implementation to make them pass.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from osint_nexus.parsers.lhkpn_parser import (
    LhkpnReport,
    PropertyItem,
    VehicleItem,
    parse_lhkpn_pdf,
    parse_rp,
    _parse_properties,
    _parse_vehicles,
)

# ---------------------------------------------------------------------------
# Fixtures — real text extracted from LHKPN PDFs
# ---------------------------------------------------------------------------

SECTION_A_TEXT = """\
A. TANAH DAN BANGUNAN Rp. 2.360.000.000
1. Tanah dan Bangunan Seluas 340 m2/250 m2 di KAB / KOTA DELI
SERDANG, HASIL SENDIRI Rp. 900.000.000
2. Tanah dan Bangunan Seluas 163 m2/90 m2 di KAB / KOTA KOTA
CIREBON , HASIL SENDIRI Rp. 560.000.000
3. Tanah dan Bangunan Seluas 100 m2/200 m2 di KAB / KOTA KOTA
BANDA ACEH , Rp. 700.000.000
4. Tanah Seluas 300 m2 di KAB / KOTA KOTA PALEMBANG , HASIL
SENDIRI Rp. 200.000.000"""

SECTION_A_EMPTY = "A. TANAH DAN BANGUNAN Rp. ----"

SECTION_B_TEXT = """\
B. ALAT TRANSPORTASI DAN MESIN Rp. 125.000.000
1. MOBIL, TOYOTA VIOS Tahun 2012, HASIL SENDIRI Rp.
100.000.000
2. MOTOR, KAWASAKI NINJA Tahun 2009, HASIL SENDIRI Rp.
25.000.000"""

SECTION_B_EMPTY = "B. ALAT TRANSPORTASI DAN MESIN Rp. ----"

PDF_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "lhkpn"
    / "pdfs"
    / "LHKPN_RAJA_ULUL_AZMI_SYAHWALI_2022.pdf"
)


# ===================================================================
# Task 2: parse_rp tests
# ===================================================================

class TestParseRp:
    """Tests for the Rupiah string parser."""

    def test_normal_value(self) -> None:
        assert parse_rp("Rp. 900.000.000") == 900_000_000

    def test_trailing_text_glitch(self) -> None:
        """PDF extraction glitch: year appended to value."""
        assert parse_rp("Rp. 404.000.0002019") == 404_000_000

    def test_zero_dashes(self) -> None:
        assert parse_rp("Rp. ----") == 0

    def test_empty_string(self) -> None:
        assert parse_rp("") == 0

    def test_no_rp_prefix(self) -> None:
        """Plain number without Rp. prefix."""
        assert parse_rp("900.000.000") == 900_000_000

    def test_small_value(self) -> None:
        assert parse_rp("Rp. 15.000.000") == 15_000_000

    def test_large_value(self) -> None:
        assert parse_rp("Rp. 2.409.000.000") == 2_409_000_000


# ===================================================================
# Task 2: Dataclass tests
# ===================================================================

class TestDataclasses:
    """Tests for PropertyItem, VehicleItem, LhkpnReport dataclasses."""

    def test_property_item_id_deterministic(self) -> None:
        """property_id is a sha256 hash of key fields — same input = same id."""
        p1 = PropertyItem(
            lokasi="DELI SERDANG",
            luas_tanah_m2=340,
            luas_bangunan_m2=250,
            tipe="tanah_bangunan",
            nilai=900_000_000,
            sumber="HASIL SENDIRI",
        )
        p2 = PropertyItem(
            lokasi="DELI SERDANG",
            luas_tanah_m2=340,
            luas_bangunan_m2=250,
            tipe="tanah_bangunan",
            nilai=900_000_000,
            sumber="HASIL SENDIRI",
        )
        assert p1.property_id == p2.property_id
        assert len(p1.property_id) == 16  # truncated sha256

    def test_property_item_id_differs_on_change(self) -> None:
        p1 = PropertyItem(
            lokasi="DELI SERDANG", luas_tanah_m2=340, luas_bangunan_m2=250,
            tipe="tanah_bangunan", nilai=900_000_000, sumber="HASIL SENDIRI",
        )
        p2 = PropertyItem(
            lokasi="KOTA CIREBON", luas_tanah_m2=163, luas_bangunan_m2=90,
            tipe="tanah_bangunan", nilai=560_000_000, sumber="HASIL SENDIRI",
        )
        assert p1.property_id != p2.property_id

    def test_vehicle_item_id_deterministic(self) -> None:
        v1 = VehicleItem(
            jenis="MOBIL", merk_model="TOYOTA VIOS",
            tahun_perolehan=2012, nilai=100_000_000, sumber="HASIL SENDIRI",
        )
        v2 = VehicleItem(
            jenis="MOBIL", merk_model="TOYOTA VIOS",
            tahun_perolehan=2012, nilai=100_000_000, sumber="HASIL SENDIRI",
        )
        assert v1.vehicle_id == v2.vehicle_id
        assert len(v1.vehicle_id) == 16

    def test_vehicle_item_id_differs_on_change(self) -> None:
        v1 = VehicleItem(
            jenis="MOBIL", merk_model="TOYOTA VIOS",
            tahun_perolehan=2012, nilai=100_000_000, sumber="HASIL SENDIRI",
        )
        v2 = VehicleItem(
            jenis="MOTOR", merk_model="KAWASAKI NINJA",
            tahun_perolehan=2009, nilai=25_000_000, sumber="HASIL SENDIRI",
        )
        assert v1.vehicle_id != v2.vehicle_id

    def test_lhkpn_report_defaults(self) -> None:
        report = LhkpnReport(
            nama="TEST", jabatan="TEST", nhk="123",
            tahun=2022, lembaga="", unit_kerja="",
            tanah_bangunan=[], kendaraan=[],
            kas=0, hutang=0, total_harta=0, source_file="test.pdf",
        )
        assert report.nama == "TEST"
        assert report.tanah_bangunan == []
        assert report.kendaraan == []


# ===================================================================
# Task 3: _parse_properties tests
# ===================================================================

class TestParseProperties:
    """Tests for property section parsing."""

    def test_parses_four_items(self) -> None:
        items = _parse_properties(SECTION_A_TEXT)
        assert len(items) == 4

    def test_item_0_tanah_bangunan(self) -> None:
        items = _parse_properties(SECTION_A_TEXT)
        p = items[0]
        assert p.lokasi == "DELI SERDANG"
        assert p.luas_tanah_m2 == 340
        assert p.luas_bangunan_m2 == 250
        assert p.tipe == "tanah_bangunan"
        assert p.nilai == 900_000_000
        assert p.sumber == "HASIL SENDIRI"

    def test_item_1_kota_cirebon(self) -> None:
        items = _parse_properties(SECTION_A_TEXT)
        p = items[1]
        assert p.lokasi == "KOTA CIREBON"
        assert p.luas_tanah_m2 == 163
        assert p.luas_bangunan_m2 == 90
        assert p.tipe == "tanah_bangunan"
        assert p.nilai == 560_000_000
        assert p.sumber == "HASIL SENDIRI"

    def test_item_2_no_sumber(self) -> None:
        """Item 3 has no 'HASIL SENDIRI' — sumber should be empty."""
        items = _parse_properties(SECTION_A_TEXT)
        p = items[2]
        assert p.lokasi == "KOTA BANDA ACEH"
        assert p.luas_tanah_m2 == 100
        assert p.luas_bangunan_m2 == 200
        assert p.sumber == ""
        assert p.nilai == 700_000_000

    def test_item_3_tanah_only(self) -> None:
        """Land only (no building) — luas_bangunan should be 0."""
        items = _parse_properties(SECTION_A_TEXT)
        p = items[3]
        assert p.lokasi == "KOTA PALEMBANG"
        assert p.luas_tanah_m2 == 300
        assert p.luas_bangunan_m2 == 0
        assert p.tipe == "tanah"
        assert p.nilai == 200_000_000
        assert p.sumber == "HASIL SENDIRI"

    def test_empty_section(self) -> None:
        items = _parse_properties(SECTION_A_EMPTY)
        assert items == []

    def test_all_have_property_id(self) -> None:
        items = _parse_properties(SECTION_A_TEXT)
        for item in items:
            assert item.property_id
            assert len(item.property_id) == 16


# ===================================================================
# Task 4: _parse_vehicles tests
# ===================================================================

class TestParseVehicles:
    """Tests for vehicle section parsing."""

    def test_parses_two_items(self) -> None:
        items = _parse_vehicles(SECTION_B_TEXT)
        assert len(items) == 2

    def test_item_0_mobil(self) -> None:
        items = _parse_vehicles(SECTION_B_TEXT)
        v = items[0]
        assert v.jenis == "MOBIL"
        assert v.merk_model == "TOYOTA VIOS"
        assert v.tahun_perolehan == 2012
        assert v.nilai == 100_000_000
        assert v.sumber == "HASIL SENDIRI"

    def test_item_1_motor(self) -> None:
        items = _parse_vehicles(SECTION_B_TEXT)
        v = items[1]
        assert v.jenis == "MOTOR"
        assert v.merk_model == "KAWASAKI NINJA"
        assert v.tahun_perolehan == 2009
        assert v.nilai == 25_000_000
        assert v.sumber == "HASIL SENDIRI"

    def test_empty_section(self) -> None:
        items = _parse_vehicles(SECTION_B_EMPTY)
        assert items == []

    def test_all_have_vehicle_id(self) -> None:
        items = _parse_vehicles(SECTION_B_TEXT)
        for item in items:
            assert item.vehicle_id
            assert len(item.vehicle_id) == 16


# ===================================================================
# Task 5: Full PDF parser tests
# ===================================================================

class TestParseLhkpnPdf:
    """Integration tests against the real 2022 PDF."""

    @pytest.fixture
    def report(self) -> LhkpnReport:
        if not PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {PDF_PATH}")
        return parse_lhkpn_pdf(PDF_PATH)

    def test_personal_data(self, report: LhkpnReport) -> None:
        assert report.nama == "RAJA ULUL AZMI SYAHWAL"
        assert report.jabatan == "PENYIDIK PEGAWAI NEGERI SIPIL (PPNS)"
        assert report.nhk == "496999"
        assert report.tahun == 2022

    def test_lembaga(self, report: LhkpnReport) -> None:
        assert "KEMENTERIAN HUKUM" in report.lembaga

    def test_unit_kerja(self, report: LhkpnReport) -> None:
        assert "SUMATERA SELATAN" in report.unit_kerja

    def test_properties_count(self, report: LhkpnReport) -> None:
        assert len(report.tanah_bangunan) == 4

    def test_vehicles_count(self, report: LhkpnReport) -> None:
        assert len(report.kendaraan) == 2

    def test_kas(self, report: LhkpnReport) -> None:
        assert report.kas == 15_000_000

    def test_hutang(self, report: LhkpnReport) -> None:
        assert report.hutang == 26_000_000

    def test_total_harta(self, report: LhkpnReport) -> None:
        assert report.total_harta == 2_409_000_000

    def test_source_file(self, report: LhkpnReport) -> None:
        assert report.source_file == str(PDF_PATH)

    def test_property_details(self, report: LhkpnReport) -> None:
        """Spot-check first property matches expected values."""
        p = report.tanah_bangunan[0]
        assert p.lokasi == "DELI SERDANG"
        assert p.luas_tanah_m2 == 340
        assert p.luas_bangunan_m2 == 250
        assert p.tipe == "tanah_bangunan"

    def test_vehicle_details(self, report: LhkpnReport) -> None:
        """Spot-check first vehicle matches expected values."""
        v = report.kendaraan[0]
        assert v.jenis == "MOBIL"
        assert v.merk_model == "TOYOTA VIOS"
        assert v.tahun_perolehan == 2012


# ---------------------------------------------------------------------------
# Cross-year consistency tests
# ---------------------------------------------------------------------------

_PDF_DIR = PDF_PATH.parent
ALL_PDFS = sorted(_PDF_DIR.glob("*.pdf")) if _PDF_DIR.exists() else []
# Filter to RAJA only for stable cross-year tests (dir may contain multiple persons)
RAJA_PDFS = [p for p in ALL_PDFS if "RAJA_ULUL" in p.name]


@pytest.mark.skipif(len(ALL_PDFS) < 2, reason="need multiple PDFs for cross-year test")
class TestCrossYear:
    def test_all_pdfs_parse_without_error(self) -> None:
        reports = [parse_lhkpn_pdf(p) for p in ALL_PDFS]
        assert len(reports) == len(ALL_PDFS)
        for r in reports:
            assert r.nama != ""
            assert r.tahun > 2000

    @pytest.mark.skipif(len(RAJA_PDFS) < 2, reason="need RAJA PDFs")
    def test_same_person_across_years(self) -> None:
        reports = [parse_lhkpn_pdf(p) for p in RAJA_PDFS]
        names = {r.nama for r in reports}
        assert len(names) == 1, f"Expected 1 person, got: {names}"

    @pytest.mark.skipif(len(RAJA_PDFS) < 2, reason="need RAJA PDFs")
    def test_property_ids_stable_across_years(self) -> None:
        """Same physical property should have same ID across years."""
        reports = [parse_lhkpn_pdf(p) for p in RAJA_PDFS]
        deli_serdang_ids: set[str] = set()
        for r in reports:
            for p in r.tanah_bangunan:
                if p.lokasi == "DELI SERDANG" and p.luas_tanah_m2 == 340:
                    deli_serdang_ids.add(p.property_id)
        assert len(deli_serdang_ids) == 1, f"Expected 1 ID, got: {deli_serdang_ids}"

    def test_total_harta_positive(self) -> None:
        reports = [parse_lhkpn_pdf(p) for p in ALL_PDFS]
        for r in reports:
            assert r.total_harta > 0, f"{r.tahun}: total_harta should be positive"
