"""Build a conservative KBLI <-> TKA position correlation dataset.

This generator intentionally excludes permitted TKA positions until the official
Kepmenaker 228/2019 lampiran rows are locally available and re-extracted.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal


LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
KBLI_PATH = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
OUT_PATH = ROOT / "data/source_documents/tka_kbli_positions.json"
SECTOR_MAP_PATH = ROOT / "data/source_documents/tka_sector_map.json"
UNMAPPED_LOG_PATH = ROOT / "data/source_documents/tka_unmapped_log.json"
README_PATH = ROOT / "data/source_documents/tka_kbli_README.md"
VERIFY_PATH = ROOT / "data/source_documents/tka_kbli_verification.md"
SOURCE_DIR = ROOT / "data/kb_sources/tka"
LOCAL_PP34 = ROOT / "data/source_documents/t0_regulations/pp_34_2021_penggunaan_tka.pdf"
LOCAL_TKA_ARTICLE = ROOT / "research/content/articles/17-tka-can-you-hire-or-be-the-foreign-worker.md"
KEPMENAKER_349_PDF_URL = "https://jdih.kemnaker.go.id/asset/data_puu/Kepmen_349_2019.pdf"

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
POSITIVE_STATUS = "INSTRUMENT_LOCATED_LAMPIRAN_NOT_EXTRACTED"


@dataclass(frozen=True)
class Sector:
    code: str
    name: str
    prefix_ranges: tuple[range, ...]
    positive_list_status: str
    positive_basis: str
    notes: str


@dataclass(frozen=True)
class ForbiddenPosition:
    row: int
    jabatan_id: str
    jabatan_en: str
    basis: str


POSITIVE_BASIS = (
    "Kepmenaker 228/2019 tentang Jabatan Tertentu yang dapat Diduduki oleh "
    "Tenaga Kerja Asing; JDIH Kemnaker detail page status Berlaku and lists "
    "document Kepmen_228_2019_OK.pdf; lampiran rows not downloaded or "
    "extracted in this pass"
)

NO_POSITIVE_BASIS = (
    "NO ROW-LEVEL BASIS - no permitted-position row was verified in "
    "Kepmenaker 228/2019 during this pass"
)

SECTORS: tuple[Sector, ...] = (
    Sector("A", "Pertanian, Kehutanan, dan Perikanan", (range(1, 4),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("B", "Pertambangan dan Penggalian", (range(5, 10),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("C", "Industri Pengolahan", (range(10, 34),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("D", "Pengadaan Listrik, Gas, Uap/Air Panas dan Udara Dingin", (range(35, 36),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("E", "Pengelolaan Air, Limbah, dan Daur Ulang", (range(36, 40),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("F", "Konstruksi", (range(41, 44),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("G", "Perdagangan Besar dan Eceran; Reparasi Mobil dan Sepeda Motor", (range(45, 48),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("H", "Pengangkutan dan Pergudangan", (range(49, 54),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("I", "Penyediaan Akomodasi dan Penyediaan Makan Minum", (range(55, 57),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("J", "Informasi dan Komunikasi", (range(58, 64),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("K", "Aktivitas Keuangan dan Asuransi", (range(64, 67),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("L", "Real Estat", (range(68, 69),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("M", "Aktivitas Profesional, Ilmiah dan Teknis", (range(69, 76),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("N", "Aktivitas Penyewaan, Ketenagakerjaan, Agen Perjalanan dan Penunjang Usaha", (range(77, 83),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("O", "Administrasi Pemerintahan, Pertahanan dan Jaminan Sosial Wajib", (range(84, 85),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("P", "Pendidikan", (range(85, 86),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("Q", "Aktivitas Kesehatan Manusia dan Aktivitas Sosial", (range(86, 89),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("R", "Kesenian, Hiburan dan Rekreasi", (range(90, 94),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("S", "Aktivitas Jasa Lainnya", (range(94, 97),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("T", "Aktivitas Rumah Tangga sebagai Pemberi Kerja", (range(97, 99),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
    Sector("U", "Aktivitas Badan Internasional dan Badan Ekstra Internasional Lainnya", (range(99, 100),), POSITIVE_STATUS, POSITIVE_BASIS, "Positive-list umbrella instrument located; no sector row extracted."),
)

FORBIDDEN_POSITIONS: tuple[ForbiddenPosition, ...] = (
    ForbiddenPosition(1, "Direktur Personalia", "Personnel Director", "Kepmenaker 349/2019 Lampiran row 1"),
    ForbiddenPosition(2, "Manajer Hubungan Industrial", "Industrial Relations Manager", "Kepmenaker 349/2019 Lampiran row 2"),
    ForbiddenPosition(3, "Manajer Personalia", "Human Resource Manager", "Kepmenaker 349/2019 Lampiran row 3"),
    ForbiddenPosition(4, "Supervisor Pengembangan Personalia", "Personnel Development Supervisor", "Kepmenaker 349/2019 Lampiran row 4"),
    ForbiddenPosition(5, "Supervisor Perekrutan Personalia", "Personnel Recruitment Supervisor", "Kepmenaker 349/2019 Lampiran row 5"),
    ForbiddenPosition(6, "Supervisor Penempatan Personalia", "Personnel Placement Supervisor", "Kepmenaker 349/2019 Lampiran row 6"),
    ForbiddenPosition(7, "Supervisor Pembinaan Karir Pegawai", "Employee Career Development Supervisor", "Kepmenaker 349/2019 Lampiran row 7"),
    ForbiddenPosition(8, "Penata Usaha Personalia", "Personnel Administrator", "Kepmenaker 349/2019 Lampiran row 8"),
    ForbiddenPosition(9, "Pengembangan Personalia dan Karir", "Personnel and Careers Specialist", "Kepmenaker 349/2019 Lampiran row 9"),
    ForbiddenPosition(10, "Spesialis Personalia", "Personnel Specialist", "Kepmenaker 349/2019 Lampiran row 10"),
    ForbiddenPosition(11, "Penasehat Karir", "Career Advisor", "Kepmenaker 349/2019 Lampiran row 11"),
    ForbiddenPosition(12, "Penasehat Tenaga Kerja", "Job Advisor", "Kepmenaker 349/2019 Lampiran row 12"),
    ForbiddenPosition(13, "Pembimbing dan Konseling Jabatan", "Job Advisor and Counseling", "Kepmenaker 349/2019 Lampiran row 13"),
    ForbiddenPosition(14, "Perantara Tenaga Kerja", "Employee Mediator", "Kepmenaker 349/2019 Lampiran row 14"),
    ForbiddenPosition(15, "Pengadministrasi Pelatihan Pegawai", "Job Training Administrator", "Kepmenaker 349/2019 Lampiran row 15"),
    ForbiddenPosition(16, "Pewawancara Pegawai", "Job Interviewer", "Kepmenaker 349/2019 Lampiran row 16"),
    ForbiddenPosition(17, "Analisis Jabatan", "Job Analyst", "Kepmenaker 349/2019 Lampiran row 17"),
    ForbiddenPosition(18, "Penyelenggara Keselamatan Kerja Pegawai", "Occupational Safety Specialist", "Kepmenaker 349/2019 Lampiran row 18"),
)


def section_for_code(kbli_code: str) -> Sector:
    prefix = int(kbli_code[:2])
    for sector in SECTORS:
        if any(prefix in prefix_range for prefix_range in sector.prefix_ranges):
            return sector
    raise ValueError(f"Cannot map KBLI code to sector: {kbli_code}")


def tka_sector_label(row: dict[str, Any], section: Sector) -> str:
    source_sector = row.get("sektor_id")
    if isinstance(source_sector, str) and source_sector.strip():
        return (
            f"{source_sector} (source sektor_id); KBLI section fallback "
            f"{section.code} - {section.name}"
        )
    candidate_sectors = row.get("sektors")
    if isinstance(candidate_sectors, list) and candidate_sectors:
        candidates = ", ".join(str(candidate) for candidate in candidate_sectors)
        return (
            f"UNRESOLVED source sektor_id; candidate sektors {candidates}; "
            f"KBLI section fallback {section.code} - {section.name}"
        )
    return f"UNRESOLVED source sektor_id; KBLI section fallback {section.code} - {section.name}"


def load_kbli_rows() -> list[dict[str, Any]]:
    raw = json.loads(KBLI_PATH.read_text(encoding="utf-8"))
    rows = raw.get("data")
    if not isinstance(rows, list):
        raise ValueError("KBLI source must contain a top-level data array")
    return rows


def forbidden_payload() -> list[dict[str, str]]:
    return [
        {
            "jabatan_id": position.jabatan_id,
            "jabatan_en": position.jabatan_en,
            "basis": (
                f"{position.basis}; official PDF URL {KEPMENAKER_349_PDF_URL}; "
                "JDIH Kemnaker status Berlaku; local PDF not downloaded in this pass"
            ),
        }
        for position in FORBIDDEN_POSITIONS
    ]


def build_records(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    forbidden = forbidden_payload()
    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row["kode_kbli_2025"])
        sector = section_for_code(code)
        records[code] = {
            "kode_kbli_2025": code,
            "sector_tka": tka_sector_label(row, sector),
            "kepmenaker_basis": sector.positive_basis,
            "permitted_positions": [],
            "forbidden_positions": forbidden,
            "director_commissioner_exempt": True,
            "rptka_required": True,
            "confidence": "LOW",
            "provenance": (
                "KBLI row from data/source_documents/KBLI_2025_FINAL_CLEAN.json; "
                "TKA model from PP 34/2021 Pasal 4, 6, 7, 11, and 32; "
                "positive-list instrument identified as Kepmenaker 228/2019 via JDIH "
                "Kemnaker detail page, but lampiran rows were not extracted; "
                "forbidden positions from Kepmenaker 349/2019 Lampiran rows 1-18."
            ),
            "verified": (
                f"{date.today().isoformat()} via JDIH Kemnaker detail pages and "
                "official Kepmenaker 349/2019 PDF text; permitted lampiran rows "
                "not verified in this pass"
            ),
            "notes": (
                "No permitted jabatan asserted because the official Kepmenaker "
                "228/2019 lampiran rows were not locally downloaded/OCRed in this "
                "sandbox. The forbidden HR/personalia list is attached cross-sector. "
                "The source `sektor_id` taxonomy is not equivalent to KBLI section "
                "A-U; KBLI section is included only as a fallback grouping. "
                f"{sector.notes}"
            ),
        }
    return records


def build_sector_map(rows: list[dict[str, Any]]) -> dict[str, Any]:
    section_counts = Counter(section_for_code(str(row["kode_kbli_2025"])).code for row in rows)
    source_sector_counts = Counter(str(row.get("sektor_id") or "UNRESOLVED") for row in rows)
    candidate_sector_rows = sum(1 for row in rows if isinstance(row.get("sektors"), list) and row["sektors"])
    return {
        "generated_at": date.today().isoformat(),
        "kbli_source": str(KBLI_PATH.relative_to(ROOT)),
        "kbli_record_count": len(rows),
        "sector_mapping_warning": (
            "KBLI source `sektor_id` is not equivalent to KBLI section A-U. "
            "The `sectors` array below is a KBLI-section fallback for QA only; "
            "future positive-position joins must use the actual sector taxonomy "
            "from the extracted Kepmenaker 228/2019 lampiran."
        ),
        "source_sektor_id_taxonomy": {
            "resolved_count": len(rows) - source_sector_counts["UNRESOLVED"],
            "unresolved_count": source_sector_counts["UNRESOLVED"],
            "rows_with_candidate_sektors": candidate_sector_rows,
            "counts": dict(sorted(source_sector_counts.items())),
        },
        "positive_list_instrument": {
            "instrument": "Kepmenaker 228/2019",
            "title": "Jabatan Tertentu yang dapat di Duduki oleh Tenaga Kerja Asing",
            "official_detail_url": "https://jdih.kemnaker.go.id/peraturan/detail/1609/keputusan-menteri-ketenagakerjaan-nomor-228-tahun-2019",
            "official_document_label": "Kepmen_228_2019_OK.pdf",
            "status": "Berlaku on JDIH Kemnaker as read on 2026-07-01",
            "extraction_status": "NOT_EXTRACTED_IN_THIS_PASS",
        },
        "closed_list_instrument": {
            "instrument": "Kepmenaker 349/2019",
            "title": "Jabatan Tertentu yang Dilarang Diduduki oleh Tenaga Kerja Asing",
            "official_detail_url": "https://jdih.kemnaker.go.id/peraturan/detail/1636/keputusan-menteri-ketenagakerjaan-nomor-349-tahun-2019",
            "official_pdf_url": "https://jdih.kemnaker.go.id/asset/data_puu/Kepmen_349_2019.pdf",
            "status": "Berlaku on JDIH Kemnaker as read on 2026-07-01",
            "extracted_rows": len(FORBIDDEN_POSITIONS),
        },
        "sectors": [
            {
                "section": sector.code,
                "kbli_section_name": sector.name,
                "kbli_code_count": section_counts.get(sector.code, 0),
                "mapping_authority": "FALLBACK_ONLY_NOT_TKA_AUTHORITY",
                "positive_list_status": sector.positive_list_status,
                "kepmenaker_basis": sector.positive_basis,
                "notes": sector.notes,
            }
            for sector in SECTORS
        ],
    }


def build_unmapped_log(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_sector: dict[str, list[str]] = {sector.code: [] for sector in SECTORS}
    for row in rows:
        code = str(row["kode_kbli_2025"])
        by_sector[section_for_code(code).code].append(code)
    return {
        "generated_at": date.today().isoformat(),
        "purpose": "Positions excluded because no verified lampiran row basis was available.",
        "excluded_permitted_positions": {
            sector.code: {
                "sector_tka": sector.name,
                "kbli_code_count": len(by_sector[sector.code]),
                "code_samples": by_sector[sector.code][:10],
                "reason": (
                    "Kepmenaker 228/2019 instrument located, but official lampiran "
                    "rows were not extracted in this pass; no permitted jabatan "
                    "may be inferred from generated guides, KBLI section fallback, "
                    "or ISCO/KBJI proxies."
                ),
            }
            for sector in SECTORS
        },
        "excluded_forbidden_positions": {
            "count": 0,
            "reason": "Rows 1-18 from Kepmenaker 349/2019 were verified and included.",
        },
    }


def write_source_manifest() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    copied_pp34 = SOURCE_DIR / "pp_34_2021_penggunaan_tka.pdf"
    if LOCAL_PP34.exists():
        shutil.copy2(LOCAL_PP34, copied_pp34)
    manifest = {
        "generated_at": date.today().isoformat(),
        "sources": [
            {
                "instrument": "PP 34/2021",
                "title": "Penggunaan Tenaga Kerja Asing",
                "local_path": str(copied_pp34.relative_to(ROOT)) if copied_pp34.exists() else None,
                "status": "local_pdf_available",
            },
            {
                "instrument": "Article 17 local draft",
                "title": "TKA: Can You Hire (or Be) the Foreign Worker?",
                "local_path": (
                    str(LOCAL_TKA_ARTICLE.relative_to(ROOT))
                    if LOCAL_TKA_ARTICLE.exists()
                    else None
                ),
                "status": "local_markdown_available; regulatory model only; not used as jabatan source",
            },
            {
                "instrument": "Kepmenaker 228/2019",
                "title": "Jabatan Tertentu yang dapat di Duduki oleh Tenaga Kerja Asing",
                "official_detail_url": "https://jdih.kemnaker.go.id/peraturan/detail/1609/keputusan-menteri-ketenagakerjaan-nomor-228-tahun-2019",
                "official_download_url": "https://jdih.kemnaker.go.id/download.php?id=1609",
                "reported_pdf_redirect": "http://jdih.kemnaker.go.id/asset/data_puu/Kepmen_228_2019_OK.pdf",
                "official_document_label": "Kepmen_228_2019_OK.pdf",
                "local_path": None,
                "status": "official_page_verified; source-hunt sidecar found no later replacement positive-list instrument; PDF download blocked in this sandbox; lampiran not extracted",
            },
            {
                "instrument": "Kepmenaker 349/2019",
                "title": "Jabatan Tertentu yang Dilarang Diduduki oleh Tenaga Kerja Asing",
                "official_detail_url": "https://jdih.kemnaker.go.id/peraturan/detail/1636/keputusan-menteri-ketenagakerjaan-nomor-349-tahun-2019",
                "official_pdf_url": KEPMENAKER_349_PDF_URL,
                "local_path": None,
                "status": "official_pdf_text_read via web tool; local download blocked in this sandbox",
            },
        ],
    }
    (SOURCE_DIR / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_readme(records: dict[str, dict[str, Any]], sector_map: dict[str, Any]) -> None:
    confidence_counts = Counter(record["confidence"] for record in records.values())
    fallback_sections = sum(
        1
        for sector in sector_map["sectors"]
        if sector["positive_list_status"] == POSITIVE_STATUS
    )
    source_taxonomy = sector_map["source_sektor_id_taxonomy"]
    README_PATH.write_text(
        f"""# TKA KBLI Positions Dataset

Generated: {date.today().isoformat()}

This is a research-grade dataset, not a production-ready KBLI Navigator input.

## What is authoritative in this pass

- KBLI universe: `{KBLI_PATH.relative_to(ROOT)}` with {len(records)} records.
- Regulatory model: PP 34/2021, especially the RPTKA, jabatan tertentu, local-counterpart, and personnel-position prohibition model.
- Positive-list instrument identity: Kepmenaker 228/2019 is marked `Berlaku` on JDIH Kemnaker and appears to be the current umbrella positive-list instrument.
- Forbidden list: Kepmenaker 349/2019 Lampiran rows 1-18 were read from the official PDF text and included cross-sector.

## What is intentionally not asserted

`permitted_positions` is empty for every KBLI code. The official Kepmenaker 228/2019 lampiran PDF was not locally downloaded/OCRed in this sandbox, so no permitted jabatan row has a verified lampiran-row basis in this pass.

The source `sektor_id` taxonomy is not equivalent to KBLI section A-U. `sector_tka` records the source `sektor_id` when present, candidate `sektors` when present, and KBLI section only as a fallback label.

## Counts

- HIGH: {confidence_counts.get("HIGH", 0)}
- MEDIUM: {confidence_counts.get("MEDIUM", 0)}
- LOW: {confidence_counts.get("LOW", 0)}
- Positive-list row-level sections extracted: 0
- KBLI section fallback groups carried for QA only: {fallback_sections}
- KBLI records with resolved source `sektor_id`: {source_taxonomy["resolved_count"]}
- KBLI records with unresolved source `sektor_id`: {source_taxonomy["unresolved_count"]}
- Unresolved records with candidate `sektors`: {source_taxonomy["rows_with_candidate_sektors"]}
- Forbidden positions included: {len(FORBIDDEN_POSITIONS)}

## Files

- `tka_kbli_positions.json` - one record per KBLI code.
- `tka_sector_map.json` - source `sektor_id` audit plus KBLI section fallback map.
- `tka_unmapped_log.json` - excluded permitted positions and reasons.
- `tka_kbli_verification.md` - adversarial verification result.
- `../kb_sources/tka/source_manifest.json` - source availability manifest.

## Next step

Run the extraction on Pro, where browser downloads and local OCR are available: download `Kepmen_228_2019_OK.pdf` from JDIH Kemnaker, extract every lampiran row into a per-sector table, then rerun this generator with those rows as the only source for `permitted_positions`.

When adding permitted positions, resolve against the actual sector taxonomy in the Kepmenaker lampiran. Do not treat KBLI section A-U as the authoritative TKA sector.

Do not promote this file into the KBLI Navigator until the Kepmenaker 228/2019 lampiran extraction and independent row-level verification are complete.
""",
        encoding="utf-8",
    )


def write_verification(records: dict[str, dict[str, Any]], sector_map: dict[str, Any]) -> None:
    confidence_counts = Counter(record["confidence"] for record in records.values())
    low_fallback_sections = [
        sector["section"]
        for sector in sector_map["sectors"]
        if sector["positive_list_status"] == POSITIVE_STATUS
    ]
    source_taxonomy = sector_map["source_sektor_id_taxonomy"]
    VERIFY_PATH.write_text(
        f"""# TKA KBLI Verification Report

Generated: {date.today().isoformat()}

## Verdict

Research-grade, gaps documented. The dataset validates for all {len(records)} KBLI codes, but it is not production-ready because zero permitted jabatan rows have been extracted from the official Kepmenaker 228/2019 lampiran in this pass.

## Confirmed

- KBLI record count: {len(records)}.
- Confidence counts: HIGH={confidence_counts.get("HIGH", 0)}, MEDIUM={confidence_counts.get("MEDIUM", 0)}, LOW={confidence_counts.get("LOW", 0)}.
- JDIH Kemnaker marks Kepmenaker 228/2019 as `Berlaku` and lists document `Kepmen_228_2019_OK.pdf`.
- JDIH Kemnaker marks Kepmenaker 349/2019 as `Berlaku`.
- Kepmenaker 349/2019 Lampiran rows 1-18 were read from official PDF text and included as cross-sector forbidden positions.
- PP 34/2021 local PDF supports the model: TKA use is tied to `jabatan tertentu`, RPTKA approval, Indonesian counterpart/skill transfer, and prohibition on personnel-handling positions.
- KBLI source shape was independently checked: `data.length` is {len(records)}, source `sektor_id` is resolved on {source_taxonomy["resolved_count"]} records and unresolved on {source_taxonomy["unresolved_count"]}.

## Refuted or excluded

- No permitted jabatan from ISCO/KBJI proxy, generated guides, or existing internal mapping was included.
- No permitted jabatan from Kepmenaker 228/2019 was included, because no lampiran row was re-opened and extracted in this pass.
- The internal hint that the closed list contains more than 18 rows was not ingested; only rows visible in the official Kepmenaker 349/2019 PDF text were included.
- KBLI section A-U was not accepted as an authoritative TKA sector map; it is retained only as a fallback QA grouping.

## Downgraded

- All sectors are LOW for the full KBLI-to-permitted-position claim because permitted positions are not yet row-verified.
- All KBLI section fallback groups remain row-unverified against Kepmenaker 228/2019.
- {source_taxonomy["unresolved_count"]} KBLI records have unresolved source `sektor_id`; {source_taxonomy["rows_with_candidate_sektors"]} of those carry candidate `sektors`.

## LOW KBLI section fallback groups

{", ".join(low_fallback_sections)}

## Source URLs checked

- https://jdih.kemnaker.go.id/peraturan/detail/1609/keputusan-menteri-ketenagakerjaan-nomor-228-tahun-2019
- https://jdih.kemnaker.go.id/peraturan/detail/1636/keputusan-menteri-ketenagakerjaan-nomor-349-tahun-2019
- https://jdih.kemnaker.go.id/peraturan/detail/1722/peraturan-pemerintah-nomor-34-tahun-2021
- https://jdih.kemnaker.go.id/asset/data_puu/Kepmen_349_2019.pdf

## Most important next verification gate

Download and OCR/parse `Kepmen_228_2019_OK.pdf` on Pro, then perform an independent row-level verification pass before adding any permitted position to `tka_kbli_positions.json`.
""",
        encoding="utf-8",
    )


def validate_records(records: dict[str, dict[str, Any]], expected_count: int) -> None:
    required_keys = {
        "kode_kbli_2025",
        "sector_tka",
        "kepmenaker_basis",
        "permitted_positions",
        "forbidden_positions",
        "director_commissioner_exempt",
        "rptka_required",
        "confidence",
        "provenance",
        "verified",
        "notes",
    }
    if len(records) != expected_count:
        raise ValueError(f"Expected {expected_count} records, got {len(records)}")
    for code, record in records.items():
        missing = required_keys.difference(record)
        if missing:
            raise ValueError(f"{code} missing keys: {sorted(missing)}")
        if record["kode_kbli_2025"] != code:
            raise ValueError(f"{code} key/code mismatch")
        if record["confidence"] not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError(f"{code} invalid confidence")
        if not isinstance(record["permitted_positions"], list):
            raise ValueError(f"{code} permitted_positions must be a list")
        if not record["forbidden_positions"]:
            raise ValueError(f"{code} forbidden_positions cannot be empty")
        for position in record["forbidden_positions"]:
            if not position.get("basis"):
                raise ValueError(f"{code} forbidden position missing basis")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rows = load_kbli_rows()
    records = build_records(rows)
    sector_map = build_sector_map(rows)
    unmapped_log = build_unmapped_log(rows)
    validate_records(records, len(rows))

    OUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SECTOR_MAP_PATH.write_text(json.dumps(sector_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    UNMAPPED_LOG_PATH.write_text(json.dumps(unmapped_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_source_manifest()
    write_readme(records, sector_map)
    write_verification(records, sector_map)

    confidence_counts = Counter(record["confidence"] for record in records.values())
    fallback_sections = sum(
        1
        for sector in sector_map["sectors"]
        if sector["positive_list_status"] == POSITIVE_STATUS
    )
    source_taxonomy = sector_map["source_sektor_id_taxonomy"]
    LOGGER.info(
        "Generated %s records: HIGH=%s MEDIUM=%s LOW=%s; positive row sections extracted=0; fallback sections=%s; unresolved source sektor_id=%s",
        len(records),
        confidence_counts.get("HIGH", 0),
        confidence_counts.get("MEDIUM", 0),
        confidence_counts.get("LOW", 0),
        fallback_sections,
        source_taxonomy["unresolved_count"],
    )


if __name__ == "__main__":
    main()
