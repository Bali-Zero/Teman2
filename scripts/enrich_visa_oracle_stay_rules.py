"""Enrich visa_oracle Qdrant collection with NB-2-validated stay/extension rules.

For each target visa code (C1, C2, C6, C7, C7A, C7B, C7C), fetch the existing
point, append a "Stay Permit & Extensions" section with verified durations,
re-embed dense (text-embedding-3-small) and sparse (BM25 via fastembed if
available, otherwise omit and rely on dense), and upsert with the SAME id
to overwrite.

Source of truth: NB-2 query 2026-04-16 (Permenkumham 22/2023 Pasal 81(5) +
Permenkumham 11/2024 Pasal 95(3)).

Run from repo root:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python ../../scripts/enrich_visa_oracle_stay_rules.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("enrich_visa_oracle")

def _load_env(key: str) -> str | None:
    """Load a key from apps/backend-rag/.env as a fallback."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "apps",
        "backend-rag",
        ".env",
    )
    try:
        with open(env_path) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


# --- Config ---
QDRANT_URL = os.environ.get(
    "QDRANT_URL",
    "https://5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333",
)
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or _load_env("QDRANT_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or _load_env("OPENAI_API_KEY")
COLLECTION = "visa_oracle"
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, FROZEN per CLAUDE.md


@dataclass
class StayRule:
    code: str
    visa_family: str  # "visit_single" | "visit_multi" | "kitas" | "visa_free" | "voa"
    initial_days: int
    extension_days: int
    max_extensions: int | str  # int or "0 (non-extendable)"
    max_total_days: int
    legal_basis: str
    # Multi-entry visas: visa validity window (e.g. "1, 2, or 5 years")
    visa_validity: str | None = None
    # KITAS/KITAP path
    kitap_eligible: bool = False
    kitap_years_required: int | None = None
    # Optional extras
    bali_warning: str | None = None
    notes: str | None = None


# --- General rule shortcut (Permen 11/2024 Pasal 95(3) — 60+60×2=180) ---
def _c_standard(code: str, notes: str | None = None) -> StayRule:
    return StayRule(
        code=code,
        visa_family="visit_single",
        initial_days=60,
        extension_days=60,
        max_extensions=2,
        max_total_days=180,
        legal_basis="Permenkumham 22/2023 Pasal 81(5); Permenkumham 11/2024 Pasal 95(3)",
        notes=notes,
    )


def _d_standard(code: str, notes: str | None = None) -> StayRule:
    """D-series standard: 60d per entry, NON-extendable (unless noted)."""
    return StayRule(
        code=code,
        visa_family="visit_multi",
        visa_validity="1 or 2 years (multi-entry)",
        initial_days=60,
        extension_days=0,
        max_extensions="0 (non-extendable per entry)",
        max_total_days=60,
        legal_basis="Permenkumham 11/2024 Pasal 16(1)",
        notes=notes or "Multi-entry visa: unlimited entries within validity window, but each stay is non-extendable.",
    )


# NB-2 validated 2026-04-16. All 86 visa codes.
RULES: dict[str, StayRule] = {
    # ========================================================================
    # A-series: Visa-Free (Bebas Visa)
    # ========================================================================
    "A1": StayRule(
        code="A1", visa_family="visa_free",
        initial_days=30, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=30,
        legal_basis="Permenkumham 22/2023 Pasal 84",
        notes="Visa-free tourism for eligible nationalities (list set by Menteri). Post-pandemic list reduced in favor of paid VoA (B1).",
    ),
    "A4": StayRule(
        code="A4", visa_family="visa_free",
        initial_days=30, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=30,
        legal_basis="Permenkumham 22/2023 Pasal 84",
        notes="Visa-free government duty. Requires official assignment documentation.",
    ),
    "A36": StayRule(
        code="A36", visa_family="visa_free",
        initial_days=60, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=60,
        legal_basis="Permenkumham 11/2024 Pasal 85(1)",
        notes="Visa-free for pilots/crew ON DUTY on transport vehicles. Must be in Crew List or General Declaration. NOTE: previous DB records showed 30 days — CORRECTED to 60 days per Permen 11/2024.",
    ),
    "A37": StayRule(
        code="A37", visa_family="visa_free",
        initial_days=60, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=60,
        legal_basis="Permenkumham 11/2024 Pasal 85(2)",
        notes="Visa-free for sea crew/experts on vessels in Indonesian waters (archipelagic, territorial, EEZ). NOTE: previous DB records showed 30 days — CORRECTED to 60 days.",
    ),
    # ========================================================================
    # B-series & F-series: Visa on Arrival (VoA)
    # ========================================================================
    "B1": StayRule(
        code="B1", visa_family="voa",
        initial_days=30, extension_days=30, max_extensions=1,
        max_total_days=60,
        legal_basis="Permenkumham 11/2024 Pasal 95(7)",
        notes="Standard VoA tourism for ~170 eligible nationalities. Available as eVoA (online) or at airport. NOT convertible to KITAS (Pasal 163(2)) — exit required for KITAS.",
    ),
    "B4": StayRule(
        code="B4", visa_family="voa",
        initial_days=30, extension_days=30, max_extensions=1,
        max_total_days=60,
        legal_basis="Permenkumham 11/2024 Pasal 95(7)",
        notes="VoA for government assignment officials. NOT convertible to KITAS.",
    ),
    "F1": StayRule(
        code="F1", visa_family="voa",
        initial_days=7, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=7,
        legal_basis="Permenkumham 11/2024 Pasal 82(2)",
        notes="VoA for Riau Islands ONLY (Batam, Bintan, Karimun seaports). NOT available at Bali Ngurah Rai airport. Used for border runs from Singapore/Malaysia.",
    ),
    "F4": StayRule(
        code="F4", visa_family="voa",
        initial_days=7, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=7,
        legal_basis="Permenkumham 11/2024 Pasal 82(2)",
        notes="VoA government duty Riau Islands ONLY (Batam/Bintan/Karimun). NOT Bali.",
    ),
    # ========================================================================
    # C-series: Visit Visa single-entry (already enriched C1/C2/C6/C7/C7A/C7B/C7C)
    # ========================================================================
    "C1": StayRule(
        code="C1", visa_family="visit_single",
        initial_days=60, extension_days=60, max_extensions=2, max_total_days=180,
        legal_basis="Permenkumham 22/2023 Pasal 81(5); Permenkumham 11/2024 Pasal 95(3)",
        bali_warning=(
            "Kanim Denpasar + Ngurah Rai (Circolare 31 March 2026): if the foreigner is "
            "a shareholder, director or commissioner of an Indonesian PT PMA, C1 extension "
            "applications are LOCALLY REJECTED. Effective max stay in Bali for PMA "
            "shareholders/directors = 60 days, no extension. Must do alih status to E28A or exit."
        ),
    ),
    "C2": _c_standard("C2", "Business visits, meetings, negotiations. Cannot generate income from Indonesia."),
    "C3": _c_standard("C3", "Medical care/treatment."),
    "C4": StayRule(
        code="C4", visa_family="visit_single",
        initial_days=60, extension_days=60, max_extensions="up to 12 months total",
        max_total_days=365,
        legal_basis="Permenkumham 11/2024 Pasal 95(5)",
        notes="Government duty — EXCEPTION: total max extended to 12 MONTHS (not 180 days like standard).",
    ),
    "C5": _c_standard("C5", "Media and press activities."),
    "C6": _c_standard("C6", "Social activities (Kegiatan Sosial)."),
    "C7": _c_standard("C7", "Art and culture activities."),
    "C7A": StayRule(
        code="C7A", visa_family="visit_single",
        initial_days=30, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=30,
        legal_basis="Permenkumham 22/2023 (music performance visa)",
        notes="Music performance. Strict 30 days, NON-EXTENDABLE. Compensation allowed with sponsor.",
    ),
    "C7B": StayRule(
        code="C7B", visa_family="visit_single",
        initial_days=30, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=30,
        legal_basis="Permenkumham 22/2023 (music crew visa)",
        notes="Music performance crew (technicians, roadies). Strict 30 days, NON-EXTENDABLE.",
    ),
    "C7C": _c_standard("C7C", "Art performance (pertunjukan seni) — non-music."),
    "C8A": _c_standard("C8A", "Sports athlete. For tournaments and competitions on calendar."),
    "C8B": _c_standard("C8B", "Sports officials."),
    "C9": _c_standard("C9", "Study visit, short course, short training."),
    "C9A": _c_standard("C9A", "Short course (religious field)."),
    "C9B": _c_standard("C9B", "Short course (Bahasa Indonesia language)."),
    "C10": _c_standard("C10", "Business meeting."),
    "C10A": _c_standard("C10A", "Religious speaker (pemuka agama). Extendable contrary to common belief."),
    "C11": _c_standard("C11", "Business exhibition (pameran)."),
    "C11A": _c_standard("C11A", "Exhibition for Calling Visa country nationals. Requires Dirjen approval first."),
    "C12": StayRule(
        code="C12", visa_family="visit_single",
        initial_days=180, extension_days=180, max_extensions=1,
        max_total_days=360,
        legal_basis="Permenkumham 11/2024 Pasal 81(4) + Pasal 95(4)",
        notes="Pre-investment — EXCEPTION: 180 days per entry, extendable once for 180 more = 12 months total. Natural path to E28A KITAS after PT PMA setup. Cannot generate income or conduct business transactions.",
    ),
    "C13": _c_standard("C13", "Transport crew (single-entry variant)."),
    "C14": _c_standard("C14", "Film production activity."),
    "C15": _c_standard("C15", "Emergency work."),
    "C16": _c_standard("C16", "Trainer/instructor."),
    "C17": _c_standard("C17", "Business audit/inspection. NOTE: DB previously showed 'extendable to 180' which matches standard rule."),
    "C18": StayRule(
        code="C18", visa_family="visit_single",
        initial_days=90, extension_days=0, max_extensions="0 (non-extendable)",
        max_total_days=90,
        legal_basis="SE Ditjen Imigrasi IMI-453.GR.01.01 (27 May 2025), effective 14 June 2025 00:01 WIB; Permenkumham 11/2024 (rewrote Pasal 95, removed the 60+60=120 day derogation of Permen 22/2023 Pasal 95(7))",
        notes="Work trial (uji coba keahlian TKA). 90 days NON-EXTENDABLE per SE Ditjen Imigrasi IMI-453.GR.01.01 (27 May 2025, effective 14 June 2025). Visa validity (masa berlaku visa): 90 days from issuance. SAME-SPONSOR PROHIBITION: 'orang asing dilarang menggunakan Visa C18 dengan penjamin perusahaan yang sama lebih dari satu kali' — cannot use C18 twice with the same Indonesian sponsor company. GRANDFATHER: applications filed before 14 June 2025 00:01 WIB retain the old 60-day extendable regime (120d max). Pre-step to E23 Working KITAS — can be converted onshore (dapat dikonversikan menjadi Izin Tinggal Terbatas dengan penjamin yang sama) with RPTKA approval from Kemnaker.",
    ),
    "C19": _c_standard("C19", "After-sales service."),
    "C20": _c_standard("C20", "Machinery installation and repair."),
    "C21": _c_standard("C21", "Judicial process."),
    "C22": StayRule(
        code="C22", visa_family="visit_single",
        initial_days=180, extension_days=180, max_extensions=1,
        max_total_days=365,
        legal_basis="Permenkumham 11/2024 Pasal 81(4) + Pasal 95(6)",
        notes="Internship (pemagangan) generic — EXCEPTION: 180 days initial, extendable once for 180 days = 12 months total. Sub-categories C22A/C22B follow standard 60+60+60=180 rule.",
    ),
    "C22A": _c_standard("C22A", "Academic internship (university exchange, research). Sub-category follows standard rule."),
    "C22B": _c_standard("C22B", "Industrial internship / skills development. Sub-category follows standard rule."),
    # ========================================================================
    # D-series: Multi-entry (Visa Kunjungan Beberapa Kali Perjalanan)
    # ========================================================================
    "D1": StayRule(
        code="D1", visa_family="visit_multi",
        visa_validity="1, 2, or 5 years (10 years possible if prior 5y visa used within last 3 years — Pasal 16(2))",
        initial_days=60, extension_days=60, max_extensions=2, max_total_days=180,
        legal_basis="Permenkumham 11/2024 Pasal 16(1) + Pasal 95(3)",
        notes="Multi-entry tourism. 10-year variant requires proof of prior 5-year D-visa use in last 3 years. Each stay extendable via standard rule.",
    ),
    "D2": StayRule(
        code="D2", visa_family="visit_multi",
        visa_validity="1, 2, or 5 years",
        initial_days=60, extension_days=60, max_extensions=2, max_total_days=180,
        legal_basis="Permenkumham 11/2024 Pasal 16(1) + Pasal 95(3)",
        notes="Multi-entry business. Each stay extendable.",
    ),
    "D3": _d_standard("D3", "Multi-entry medical treatment. Each stay NON-extendable per entry."),
    "D7": _d_standard("D7", "Multi-entry art/culture. Each stay NON-extendable."),
    "D7A": _d_standard("D7A", "Multi-entry music performance. Each stay NON-extendable (but 60d per entry vs C7A 30d)."),
    "D7B": _d_standard("D7B", "Multi-entry music crew. Each stay NON-extendable."),
    "D8A": _d_standard("D8A", "Multi-entry athletes."),
    "D8B": _d_standard("D8B", "Multi-entry sports officials."),
    "D12": StayRule(
        code="D12", visa_family="visit_multi",
        visa_validity="1 or 2 years",
        initial_days=180, extension_days=180, max_extensions=1, max_total_days=365,
        legal_basis="Permenkumham 11/2024 Pasal 81(4) + Pasal 95(4)",
        notes="Multi-entry pre-investment — SPECIAL: 180 days per entry, extendable once onshore to 360d total (12 months continuous). Longer per-entry stay than D1/D2.",
    ),
    "D14": _d_standard("D14", "Multi-entry film production."),
    "D17": _d_standard("D17", "Multi-entry audit/inspection."),
    # ========================================================================
    # E-series: KITAS / ITAS (long-stay)
    # ========================================================================
    # E28 — Investor
    "E28A": StayRule(
        code="E28A", visa_family="kitas",
        visa_validity="2 years",
        initial_days=730, extension_days=730, max_extensions="renewable up to 6 years cumulative",
        max_total_days=2190,
        legal_basis="Permenkumham 11/2024 Pasal 38-40",
        kitap_eligible=True, kitap_years_required=3,
        notes="Investor in existing PT PMA. KITAS threshold: Rp 10 billion shares. KITAP threshold INCREASED to Rp 15 billion (Pasal 176(2)(c)).",
    ),
    "E28B": StayRule(
        code="E28B", visa_family="kitas",
        visa_validity="5 or 10 years",
        initial_days=1825, extension_days=0, max_extensions="renewable at expiry",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 38-40",
        kitap_eligible=True, kitap_years_required=5,
        notes="Golden Visa Founder — PT PMA founder. USD 2.5M (5y) or USD 5M (10y) paid-up capital within 90 days. Direct KITAP-INV after 5y (no language test). 10y variant also requires proof of prior Indonesia entry.",
    ),
    "E28C": StayRule(
        code="E28C", visa_family="kitas",
        visa_validity="5 or 10 years",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 40",
        kitap_eligible=True, kitap_years_required=5,
        notes="Golden Visa Portfolio Investor — no company setup. USD 350k (5y) or USD 700k (10y) in government bonds, listed shares, or mutual funds within 90 days.",
    ),
    "E28D": StayRule(
        code="E28D", visa_family="kitas",
        visa_validity="5 or 10 years",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 39(4)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Investor Branch/Representative Office. Parent company commits USD 25M (5y) or USD 50M (10y).",
    ),
    "E28F": StayRule(
        code="E28F", visa_family="kitas",
        visa_validity="Varies",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="DB operational records",
        kitap_eligible=True, kitap_years_required=3,
        notes="Investor Real Estate (IKN Nusantara or property-based). Threshold Rp 5 billion+ property.",
    ),
    "E28G": StayRule(
        code="E28G", visa_family="kitas",
        visa_validity="10 years",
        initial_days=3650, extension_days=0, max_extensions="renewable",
        max_total_days=3650,
        legal_basis="DB operational records",
        kitap_eligible=True, kitap_years_required=5,
        notes="Golden 10Y Real Estate — Rp 5 billion+ property maintained for 10 years.",
    ),
    # E29 — Research
    "E29": StayRule(
        code="E29", visa_family="kitas",
        visa_validity="max 1 year per cycle",
        initial_days=365, extension_days=365, max_extensions="renewable annually for project duration",
        max_total_days=0,  # no fixed total, project-based
        legal_basis="Permenkumham 11/2024 Pasal 105",
        kitap_eligible=False,
        notes="Research visa — NOT eligible for KITAP conversion (Pasal 173 does not include research).",
    ),
    # E30 — Education
    "E30A": StayRule(
        code="E30A", visa_family="kitas",
        visa_validity="1, 2, or 4 years based on program",
        initial_days=365, extension_days=365, max_extensions="until graduation",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105",
        kitap_eligible=False,
        notes="Student visa (school). NOT eligible for KITAP.",
    ),
    "E30B": StayRule(
        code="E30B", visa_family="kitas",
        visa_validity="1, 2, or 4 years",
        initial_days=365, extension_days=365, max_extensions="until graduation",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105",
        kitap_eligible=False,
        notes="Education visa (general/university). NOT eligible for KITAP.",
    ),
    # E31 — Family
    "E31A": StayRule(
        code="E31A", visa_family="kitas",
        visa_validity="1 or 2 years",
        initial_days=365, extension_days=365, max_extensions="renewable",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(a)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Spouse of WNI (Indonesian citizen). NO penjamin required. KITAP requires 3y KITAS + marriage min 2 years registered (Pasal 179(3)).",
    ),
    "E31B": StayRule(
        code="E31B", visa_family="kitas",
        visa_validity="1, 2, 5, or 10 years",
        initial_days=365, extension_days=365, max_extensions="tied to sponsor permit residual",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(b)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Spouse of KITAS/KITAP holder. Duration cannot exceed sponsor's permit residual.",
    ),
    "E31C": StayRule(
        code="E31C", visa_family="kitas",
        visa_validity="1 or 2 years",
        initial_days=365, extension_days=365, max_extensions="renewable",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(c)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Child of Indonesian parent (WNI) — from legal marriage between foreigner and WNI.",
    ),
    "E31D": StayRule(
        code="E31D", visa_family="kitas",
        visa_validity="1 or 2 years",
        initial_days=365, extension_days=365, max_extensions="limited by age 18",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(d)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Child of foreigner married to WNI. Expires at age 18.",
    ),
    "E31E": StayRule(
        code="E31E", visa_family="kitas",
        visa_validity="1, 2, 5, or 10 years",
        initial_days=365, extension_days=365, max_extensions="tied to parent permit + age 18 max",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(e)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Biological child <18 unmarried joining KITAS/KITAP parent. Duration ≤ parent permit AND ≤ age 18.",
    ),
    "E31F": StayRule(
        code="E31F", visa_family="kitas",
        visa_validity="1 or 2 years",
        initial_days=365, extension_days=365, max_extensions="renewable",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(f)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Child joining WNI parent (alternative variant). Subcategory of family reunion.",
    ),
    "E31G": StayRule(
        code="E31G", visa_family="kitas",
        visa_validity="1 or 2 years",
        initial_days=365, extension_days=365, max_extensions="renewable",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(g)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Parent joining Indonesian child (WNI) — WNI child must be age 21+.",
    ),
    "E31H": StayRule(
        code="E31H", visa_family="kitas",
        visa_validity="1, 2, 5, or 10 years",
        initial_days=365, extension_days=365, max_extensions="tied to sponsor permit",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(h)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Parent joining KITAS/KITAP holder child.",
    ),
    "E31J": StayRule(
        code="E31J", visa_family="kitas",
        visa_validity="1, 2, 5, or 10 years",
        initial_days=365, extension_days=365, max_extensions="tied to sponsor permit",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(8)(i) — NEW in Permen 11/2024",
        kitap_eligible=True, kitap_years_required=3,
        notes="Sibling reunification. Sibling must be <18 unmarried. NEW category added in Permen 11/2024.",
    ),
    # E32 — Ex-WNI and descendants
    "E32A": StayRule(
        code="E32A", visa_family="kitas",
        visa_validity="1 or 2 years (with penjamin)",
        initial_days=365, extension_days=365, max_extensions="renewable",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(9)(a)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Ex-Indonesian citizen (self) with penjamin. Proof required: old Indonesian passport/KTP/birth cert.",
    ),
    "E32B": StayRule(
        code="E32B", visa_family="kitas",
        visa_validity="1 or 2 years",
        initial_days=365, extension_days=365, max_extensions="renewable",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(9)(a)",
        kitap_eligible=True, kitap_years_required=3,
        notes="2nd-degree descendants of ex-WNI (children, grandchildren).",
    ),
    "E32C": StayRule(
        code="E32C", visa_family="kitas",
        visa_validity="1 or 5 years (no penjamin)",
        initial_days=365, extension_days=365, max_extensions="renewable",
        max_total_days=0,
        legal_basis="Permenkumham 11/2024 Pasal 105(9)(b)",
        kitap_eligible=True, kitap_years_required=3,
        notes="Ex-WNI without penjamin — longer duration option (5 years).",
    ),
    "E32D": StayRule(
        code="E32D", visa_family="kitas",
        visa_validity="5 or 10 years (no penjamin)",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 105(9)(c)",
        kitap_eligible=True, kitap_years_required=3,
        notes="2nd-degree descendants of ex-WNI without penjamin.",
    ),
    # E33 — Long-stay specials
    "E33": StayRule(
        code="E33", visa_family="kitas",
        visa_validity="5 or 10 years",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 33; PP 40/2023",
        kitap_eligible=True, kitap_years_required=3,
        notes="Second Home Visa. Requires USD 130,000 bank deposit at BUMN bank OR property. Property min: Rp 2 billion national, Rp 5 billion Bali (Perda Bali 2/2025).",
    ),
    "E33A": StayRule(
        code="E33A", visa_family="kitas",
        visa_validity="5 or 10 years",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 33",
        kitap_eligible=True, kitap_years_required=3,
        notes="Special Skills with sponsor (penjamin required).",
    ),
    "E33B": StayRule(
        code="E33B", visa_family="kitas",
        visa_validity="5 or 10 years",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 33",
        kitap_eligible=True, kitap_years_required=3,
        notes="Special Skills WITHOUT sponsor. Requires top-100 university degree or equivalent + government cooperation agreement, documented within 90 days.",
    ),
    "E33C": StayRule(
        code="E33C", visa_family="kitas",
        visa_validity="5 or 10 years",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 33",
        kitap_eligible=True, kitap_years_required=3,
        notes="World Figure (Tokoh Dunia) — exclusively on formal Indonesian government invitation.",
    ),
    "E33E": StayRule(
        code="E33E", visa_family="kitas",
        visa_validity="5 years",
        initial_days=1825, extension_days=0, max_extensions="renewable",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 33",
        kitap_eligible=True, kitap_years_required=3,
        notes="Silver Hair Retiree. Age 60+. Requires ~USD 50,000 deposit at BUMN bank. NO agency sponsor required (bank acts as guarantor). NO work or business allowed.",
    ),
    "E33F": StayRule(
        code="E33F", visa_family="kitas",
        visa_validity="1 year renewable up to 5 years cumulative",
        initial_days=365, extension_days=365, max_extensions="up to 5 years total",
        max_total_days=1825,
        legal_basis="Permenkumham 11/2024 Pasal 33",
        kitap_eligible=True, kitap_years_required=3,
        notes="Standard Retiree. Age 55+. Licensed Indonesian sponsor agency REQUIRED. Monthly income/pension proof ~USD 1,500/month. NO work allowed.",
    ),
    "E33G": StayRule(
        code="E33G", visa_family="kitas",
        visa_validity="1 year renewable once",
        initial_days=365, extension_days=365, max_extensions=1,
        max_total_days=730,
        legal_basis="Permenkumham 11/2024 Pasal 33; PP 40/2023",
        kitap_eligible=False,
        notes="Remote Worker (Digital Nomad). Max 2 years total on this visa. Requires foreign employment contract + minimum USD 60,000/year foreign income. STRICTLY FORBIDDEN to earn local Indonesian income. After 2 years must switch category (e.g., E28A) to reach KITAP.",
    ),
    # E35 — Working Holiday
    "E35": StayRule(
        code="E35", visa_family="kitas",
        visa_validity="max 1 year",
        initial_days=365, extension_days=0, max_extensions="0 (not renewable beyond 1 year)",
        max_total_days=365,
        legal_basis="Permenkumham 11/2024 (Working Holiday Visa)",
        kitap_eligible=False,
        notes="Working Holiday Visa. Age 18-30. Only for citizens of countries with bilateral Working Holiday agreement with Indonesia (e.g., Australia E35A). NOT renewable. NOT eligible for KITAP.",
    ),
}


def _format_days(days: int) -> str:
    """Human-friendly day/year formatting."""
    if days == 0:
        return "not applicable"
    if days >= 365 and days % 365 == 0:
        y = days // 365
        return f"{days} days ({y} year{'s' if y > 1 else ''})"
    if days >= 30 and days % 30 == 0 and days < 365:
        m = days // 30
        return f"{days} days ({m} month{'s' if m > 1 else ''})"
    return f"{days} days"


def build_stay_section(rule: StayRule) -> str:
    """Build the canonical Stay Permit & Extensions block per visa family."""
    fam = rule.visa_family
    heading_map = {
        "visit_single": "## Stay Permit & Extensions (Izin Tinggal Kunjungan)",
        "visit_multi": "## Stay Permit per Entry (Multi-entry Visa)",
        "kitas": "## KITAS Duration, Renewal & KITAP Path",
        "visa_free": "## Stay Duration (Visa-Free / Bebas Visa)",
        "voa": "## Stay Permit & Extensions (Visa on Arrival)",
    }
    lines = ["", heading_map.get(fam, "## Stay Permit & Extensions"), ""]

    # Multi-entry visas show visa validity (entry window)
    if rule.visa_validity:
        lines.append(f"- **Visa validity (entry window)**: {rule.visa_validity}")

    lines.append(
        f"- **Initial stay**: {_format_days(rule.initial_days)} from Tanda Masuk (date of entry)"
    )

    is_extendable = isinstance(rule.max_extensions, int) and rule.max_extensions > 0
    non_ext_str = isinstance(rule.max_extensions, str)

    if is_extendable:
        lines.append(f"- **Extension duration**: {_format_days(rule.extension_days)} per extension")
        lines.append(f"- **Max extensions**: {rule.max_extensions}")
    elif non_ext_str and "renewable" in str(rule.max_extensions).lower():
        lines.append(f"- **Renewal**: {rule.max_extensions}")
    elif non_ext_str:
        lines.append(f"- **Extensions**: {rule.max_extensions}")
    else:
        lines.append("- **Extensions**: none (non-extendable)")

    if rule.max_total_days > 0:
        lines.append(f"- **Max total stay (cumulative)**: {_format_days(rule.max_total_days)}")

    # KITAP path
    if fam == "kitas":
        if rule.kitap_eligible and rule.kitap_years_required:
            lines.append(
                f"- **KITAP conversion**: eligible after {rule.kitap_years_required} consecutive years on this KITAS"
            )
        elif rule.kitap_eligible:
            lines.append("- **KITAP conversion**: eligible (standard 3 consecutive years)")
        else:
            lines.append("- **KITAP conversion**: NOT ELIGIBLE (this category cannot lead to permanent residence)")

    lines.append("")

    # Distinction reminder (visit/VoA/visa-free only)
    if fam in ("visit_single", "visit_multi", "voa", "visa_free"):
        lines.append("**Important distinction — visa validity vs stay permit**:")
        lines.append(
            "- *Visa validity (masa berlaku visa)*: window to ENTER Indonesia (not how long you can remain)"
        )
        lines.append(
            "- *Stay permit (izin tinggal)*: how long you can REMAIN in Indonesia after entering"
        )
        lines.append("- Example: a 90-day visa validity means you have 90 days to ENTER; once stamped in, your stay duration is what's listed above.")
        lines.append("")

    lines.append(f"**Legal basis**: {rule.legal_basis}")

    if rule.notes:
        lines.append("")
        lines.append(f"**Operational notes**: {rule.notes}")

    if rule.bali_warning:
        lines.append("")
        lines.append(f"**⚠️ Bali-specific warning**: {rule.bali_warning}")

    lines.append("")
    return "\n".join(lines)


# --- Global Procedural Notes (appended to every visa document) ---
PROCEDURAL_NOTES_BLOCK = """
## Procedural Notes (Indonesia Immigration 2024-2026)

### Extension procedure (2025-2026, applies to all Visit Visa extensions at Bali Kanim)
- **When to apply**: max 14 days before expiry (Permenkumham 11/2024 Pasal 97(2)).
- **Where**: online via eVisa portal (evisa.imigrasi.go.id), followed by mandatory in-person appointment at Kanim of declared domicile (for Bali: Kanim Denpasar or Kanim Ngurah Rai).
- **Physical presence MANDATORY**: 1-5 days after online submission, foreigner is summoned for biometric capture, photo, and interview. Do NOT travel outside the Kanim jurisdiction during this process.
- **Processing time**: 3 working days from PNBP payment (Pasal 99(2)).
- **Output**: e-ITK / e-ITAS (virtual document, legally binding per Pasal 161), delivered by email.

### MERP (Multiple Exit Re-entry Permit) — ABOLISHED
As of UU 63/2024, MERP is NO LONGER a separate document. Re-entry permission is automatically integrated into KITAS and KITAP from issuance date. No separate procedure, no extra fee, no office visit required.

### Overstay and deportation
- **≤60 days overstay**: administrative fine (Biaya Beban) Rp 1.000.000/day (PP 45/2024 Sec VI.A).
- **>60 days overstay**: MANDATORY deportation + blacklist (Penangkalan).
- **Blacklist removal fee**: Rp 90.000.000 per request (PP 45/2024 Sec VI.E).
- **UU 63/2024 escalation**: serious violations or crimes → blacklist up to 10 years or LIFE.

### Bali enforcement (Tim PORA)
Tim Pengawasan Orang Asing operates surprise inspections (Sidak) and joint operations with Polda Bali, Satpol PP, BNN, Bea Cukai. Primary zones: Canggu (digital nomads), Seminyak (hospitality), Ubud (wellness), Sanur (long-stay), Denpasar (offices).

Most common violations detected: (1) working on visit visa (C1/VoA/eVoA) — #1 violation, (2) overstay, (3) commercial activity without NIB, (4) teaching yoga/surf without E23 KITAS, (5) digital nomad (E33G) serving Indonesian clients (forbidden).

Hotel/villa/accommodation operators are LEGALLY OBLIGED (PP 31/2013 Pasal 187) to report foreign guest data. Citizen complaints trigger field investigations.
"""


def build_full_enriched_text(original_text: str, rule: StayRule) -> str:
    """Replace or insert stay block AND append procedural notes (idempotent)."""
    text = original_text

    # 1) Stay block — replace if exists, else insert before Base Legale / ---
    stay_block = build_stay_section(rule).lstrip("\n")
    stay_headings = [
        "## Stay Permit & Extensions",
        "## Stay Permit per Entry",
        "## KITAS Duration, Renewal",
        "## Stay Duration (Visa-Free",
    ]
    found_heading = None
    for h in stay_headings:
        if h in text:
            found_heading = h
            break
    if found_heading:
        before = text.split(found_heading, 1)[0].rstrip()
        rest = text.split(found_heading, 1)[1]
        next_h = rest.find("\n## ", 1)
        after = rest[next_h:] if next_h != -1 else ""
        text = f"{before}\n\n{stay_block}{after}"
    else:
        # insert before Base Legale or ---
        inserted = False
        for anchor in ("## Base Legale", "\n---\n"):
            idx = text.find(anchor)
            if idx != -1:
                text = text[:idx] + stay_block + "\n" + text[idx:]
                inserted = True
                break
        if not inserted:
            text = text + "\n" + stay_block

    # 2) Procedural notes — append once, replace if exists
    pnotes_header = "## Procedural Notes (Indonesia Immigration 2024-2026)"
    if pnotes_header in text:
        idx = text.find(pnotes_header)
        nxt = text.find("\n## ", idx + 1)
        end = text.find("\n---", idx + 1)
        # find the earliest terminator
        candidates = [c for c in (nxt, end) if c != -1]
        cut = min(candidates) if candidates else len(text)
        text = text[:idx] + PROCEDURAL_NOTES_BLOCK.lstrip("\n") + text[cut:]
    else:
        text = text.rstrip() + "\n\n" + PROCEDURAL_NOTES_BLOCK.lstrip("\n")

    return text


async def fetch_point(client: httpx.AsyncClient, point_id: str) -> dict[str, Any]:
    r = await client.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        json={"ids": [point_id], "with_payload": True, "with_vector": True},
        headers={"api-key": QDRANT_API_KEY},
        timeout=30.0,
    )
    r.raise_for_status()
    points = r.json()["result"]
    if not points:
        raise RuntimeError(f"point {point_id} not found")
    return points[0]


async def find_point_id_by_code(client: httpx.AsyncClient, code: str) -> str | None:
    r = await client.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
        json={
            "limit": 1,
            "with_payload": False,
            "with_vector": False,
            "filter": {"must": [{"key": "metadata.code", "match": {"value": code}}]},
        },
        headers={"api-key": QDRANT_API_KEY},
        timeout=30.0,
    )
    r.raise_for_status()
    pts = r.json()["result"]["points"]
    return pts[0]["id"] if pts else None


async def embed_dense(client: httpx.AsyncClient, text: str) -> list[float]:
    r = await client.post(
        "https://api.openai.com/v1/embeddings",
        json={"model": EMBEDDING_MODEL, "input": text},
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


async def upsert_point(
    client: httpx.AsyncClient,
    point_id: str,
    vector_dict: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    body = {
        "points": [
            {
                "id": point_id,
                "vector": vector_dict,
                "payload": payload,
            }
        ]
    }
    r = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
        json=body,
        headers={"api-key": QDRANT_API_KEY},
        timeout=60.0,
    )
    if r.status_code >= 400:
        logger.error("upsert failed: %s", r.text)
    r.raise_for_status()


async def enrich_one(client: httpx.AsyncClient, code: str, rule: StayRule) -> None:
    point_id = await find_point_id_by_code(client, code)
    if not point_id:
        logger.warning("[%s] no existing point — SKIP", code)
        return
    point = await fetch_point(client, point_id)
    payload = point["payload"]
    text = payload.get("text", "")
    metadata = payload.get("metadata", {}) or {}

    new_text = build_full_enriched_text(text, rule)

    metadata = dict(metadata)
    metadata["visa_family"] = rule.visa_family
    metadata["stay_initial_days"] = rule.initial_days
    metadata["stay_extension_days"] = rule.extension_days
    metadata["stay_max_total_days"] = rule.max_total_days
    metadata["stay_max_extensions"] = (
        rule.max_extensions if isinstance(rule.max_extensions, int) else 0
    )
    metadata["stay_max_extensions_desc"] = str(rule.max_extensions)
    metadata["stay_rules_validated"] = "NB-2 2026-04-17"
    metadata["stay_legal_basis"] = rule.legal_basis
    if rule.visa_validity:
        metadata["visa_validity"] = rule.visa_validity
    metadata["kitap_eligible"] = bool(rule.kitap_eligible)
    if rule.kitap_years_required:
        metadata["kitap_years_required"] = rule.kitap_years_required
    if rule.bali_warning:
        metadata["bali_extension_restriction"] = "PMA shareholders/directors: extension rejected in Bali"
    if rule.notes:
        metadata["operational_notes"] = rule.notes[:500]

    new_payload = {"text": new_text, "metadata": metadata}

    logger.info("[%s] re-embedding %d chars (was %d)", code, len(new_text), len(text))
    dense = await embed_dense(client, new_text)

    existing_vec = point.get("vector")
    if isinstance(existing_vec, dict):
        new_vec: dict[str, Any] = dict(existing_vec)
        new_vec["dense"] = dense
    else:
        new_vec = {"dense": dense}

    await upsert_point(client, point_id, new_vec, new_payload)
    logger.info("[%s] upserted id=%s", code, point_id)


# --- Standalone concept nodes (not tied to a single visa code) ---
# These are injected as separate points so that queries like "bridging visa"
# or "overstay rules" return a dedicated authoritative answer without needing
# to match a visa-code document.

CONCEPT_DOCS: list[dict[str, Any]] = [
    {
        "concept_id": "nb2-bridging-visa",
        "title": "Bridging Visa — Izin Tinggal Peralihan",
        "text": """[CONTEXT: Indonesia Immigration 2024-2026 — Concept: Bridging Visa]

# Bridging Visa (Izin Tinggal Peralihan)

## What it is
A transitional stay permit introduced (re-formalized) by Permenkumham 11/2024 Pasal 86A and Pasal 94A. Serves as a bridge when a foreigner's current stay permit (ITK, ITB/KITAS, or ITP/KITAP) is about to expire and a new permit is pending approval.

## Who can apply
Per Pasal 94A(2):
- Holders of Izin Tinggal Kunjungan from Visa Kunjungan Saat Kedatangan (B1 VoA)
- Holders of Izin Tinggal Terbatas (KITAS)
- Holders of Izin Tinggal Tetap (KITAP)

## Duration and extension
- **Duration**: max 60 days from issuance
- **Extension**: NOT extendable

## How to apply
- Submit online via eVisa portal
- Maximum 3 days before current permit expires (Pasal 94A(4))
- Required documents: valid passport, existing permit, guarantor proof (if applicable), statement of purpose

## Overstay protection
Per Pasal 94A(5), if the application is submitted and PNBP paid BEFORE expiry, any processing delay does NOT count as overstay.

## Replaces previous practice
Before Permen 11/2024, bridging was done informally via new B211A visa runs. The "Izin Tinggal Peralihan" is now the ONLY legal onshore bridging mechanism.

## Common use cases
- Waiting for RPTKA approval from Kemnaker before KITAS E23 issuance
- Pending PT PMA setup (OSS/NIB) before E28A KITAS
- Sponsor change (alih penjamin) processing
- Any alih status in progress where old permit expires before new one is issued
""",
    },
    {
        "concept_id": "nb2-alih-status",
        "title": "Alih Status — Visa/KITAS/KITAP conversion",
        "text": """[CONTEXT: Indonesia Immigration 2024-2026 — Concept: Alih Status]

# Alih Status (Permit Conversion) — Onshore vs Offshore

## Visit Visa → KITAS (Permenkumham 11/2024 Pasal 163-172)

### NOT convertible to KITAS (Pasal 163(2)) — exit always required
- **B1 Visa on Arrival** (also B2/B3/B4)
- **A1/A4 Bebas Visa** (visa-free)
- **A36/A37 crew permits**

### Convertible onshore (no exit required)
- **C1 Tourism** → E28A (investor), E33G (remote worker), E31A (spouse WNI), others
- **C2 Business** → E23 (work, if RPTKA approved) or E28A
- **C12 Pre-investment** → E28A natural path (after PT PMA setup)
- **C18 Work Trial** → E23 (requires RPTKA approval from Kemnaker first, NOT automatic)
- **C22 Internship** → E30 student or E23 work
- **D1/D2 Multi-entry** → KITAS if visa still valid and requirements met

## Onshore (Alih Status) advantages (Pasal 168(2))
- NO 6-month minimum passport residual required
- NO biaya hidup (living funds) proof required
- NO overstay charge if application and payment completed before expiry (Pasal 169)

## Onshore processing timeline (~11-14 working days)
1. Kanim verification: 3 working days
2. Kanwil (regional office) review: 3 working days
3. Direktur Jenderal Imigrasi approval: 5 working days
4. Kanim issuance of new e-ITAS: 3 working days

## Offshore (exit + reenter) — required scenarios
1. Current visa is VoA/Bebas Visa/crew (Pasal 163(2))
2. Current visa expires BEFORE RPTKA/NIB approval is complete
3. **One Sponsor Policy violation** (SE Kemnaker 3/836/2026): if new RPTKA sponsor differs from ITK sponsor AND no corporate affiliation, alih status is REJECTED by system → foreigner must exit to Singapore/Malaysia, obtain new VITAS Telex, reenter

## Offshore wait times abroad
- Scenario A (RPTKA almost done): 3-7 working days
- Scenario B (RPTKA mid-process): 10-20 calendar days
- Scenario C (process just started): 3-6 weeks

## KITAS → KITAS (category change or sponsor change)
- Change of guarantor (alih penjamin) requires pernyataan pelepasan from previous sponsor (Pasal 167(3))
- Change of activity type (peralihan jenis kegiatan, e.g. E33G → E28A) allowed under Pasal 101(5)
- Approval: Dirjen in max 5 working days; new e-ITAS issued in 3 days

## Cost comparison
- Offshore: VITAS Telex USD 150 + KITAS Rp 2.5-3jt
- Onshore: Verifikasi Visa Cat I Rp 1jt OR Cat II Rp 2jt + KITAS fee

## Important: MERP is abolished (UU 63/2024)
Multiple Exit Re-entry Permit is now automatically integrated in KITAS and KITAP from issuance date. No separate procedure, no fee, no office visit needed.
""",
    },
    {
        "concept_id": "nb2-kitap-conversion",
        "title": "KITAP Conversion — Izin Tinggal Tetap",
        "text": """[CONTEXT: Indonesia Immigration 2024-2026 — Concept: KITAS to KITAP Alih Status]

# KITAS → KITAP Conversion (Permanent Residence)

## Who is eligible (Permenkumham 11/2024 Pasal 173)
- Workers (E23)
- Religious figures (rohaniwan)
- Investors (E28 series, all variants)
- Family reunification (E31 series, all variants)
- Repatriation / ex-WNI (E32 series)
- Second Home / Special Skills / World Figure / Retirees age 60+ (E33, E33A, E33B, E33C, E33E)
- Standard Retirees (E33F)

## Who is NOT eligible
- E29 Research — research does not qualify for permanent residence
- E30A/E30B Students — education does not qualify
- E33G Remote Worker — max 2-year cumulative cap prevents reaching 3-year requirement
- E35 Working Holiday — not a permanent residence category

## Standard requirement
3 consecutive years on the same KITAS. Application submitted max 30 days before KITAS expiry (Pasal 174(2)).

## Special exceptions
- **E28B/E28G Golden Visa**: direct KITAP-INV after 5 years (skip language test, maintain investment)
- **E31A spouse of WNI**: 3 years KITAS PLUS marriage must be ≥2 years officially registered (Pasal 179(3))
- **Ex-WNI direct KITAP without KITAS**: only if citizenship was lost WHILE physically in Indonesia (Pasal 120(2)+(4))

## E28A KITAS vs KITAP threshold (IMPORTANT)
- KITAS E28A requires: Rp 10 billion in shares
- KITAP E28A requires: **Rp 15 billion** in shares (Permenkumham 11/2024 Pasal 176(2)(c))

## Document checklist (Pasal 176)
- Valid KITAS (current, not expired)
- Passport — NO 6-month minimum residual required (exception for alih status)
- Pernyataan Integrasi (integration declaration, mandatory)
- Sponsor declaration (Jaminan Keimigrasian) if applicable
- Marriage certificate for E31A spouse cases
- NO biaya hidup (living funds) proof required (exception)

## SKK / SKLD / SKTT at Bali
These police/anagraphic documents (Surat Keterangan Kepolisian, Surat Lapor Diri, Surat Keterangan Tempat Tinggal) are NOT listed in Permen 11/2024 or Permen 29/2021 as central-law requirements. Where requested at Bali Kanim, they are LOCAL PRACTICE ("surat pengantar") and not derived from national immigration regulation.

## Processing timeline (~14 working days)
1. Kanim receives: 3 working days
2. Kanwil regional review: 3 working days
3. Dirjen Imigrasi approval: 5 working days
4. Kanim issues e-KITAP: 3 working days

## PNBP fees (PP 45/2024)
- KITAP 5 years: Rp 7,000,000
- KITAP 10 years: Rp 12,000,000
- KITAP unlimited (tidak terbatas): Rp 15,000,000

## Language and integration test
- Bahasa Indonesia at B1 level + Pancasila/UUD 1945 knowledge REQUIRED
- Exemption: Golden Visa investors (E28B, E28G)
- NB-2 has no documented age-based exemption (e.g., no special rule for age 60+/65+)

## KITAP duration and maintenance
- First KITAP: 5 years validity
- Subsequent renewals: unlimited (tidak terbatas)
- Lapor Diri obligation: every 5 years (FREE, Permen 29/2021 Pasal 144(1))

## KITAP revocation (Pasal 141)
- Crime against state or security
- Violation of Pernyataan Integrasi
- Hiring illegal foreign workers
- False data in application
- Divorce from WNI spouse — UNLESS marriage is already ≥10 years old (then KITAP protected)
- Absence from Indonesia >12 months continuously (automatic expiry)

## Path to citizenship
After 5 consecutive years on KITAP (or 10 years total legal residence including KITAS). Requirements:
- Bahasa Indonesia + Pancasila + UUD 1945 knowledge test
- Must renounce original citizenship (Indonesia does NOT allow dual citizenship for adults)
""",
    },
    {
        "concept_id": "nb2-overstay-deportation",
        "title": "Overstay, Deportation, Blacklist (Penangkalan)",
        "text": """[CONTEXT: Indonesia Immigration 2024-2026 — Concept: Overstay & Deportation]

# Overstay, Deportation, and Blacklist (Penangkalan)

## Overstay fine (Biaya Beban) — PP 45/2024 Section VI.A
- **Rate**: Rp 1,000,000 per day of overstay
- **Maximum allowed before deportation**: 60 days
- **Payable onshore**: at Kanim Imigrasi before exit

## ≤60 days overstay
Administrative fine only. Foreigner pays Biaya Beban at any Kanim Imigrasi, can leave Indonesia normally, and may re-enter in the future (no automatic blacklist for fine-paid overstay).

## >60 days overstay — MANDATORY consequences
- Deportation (deportasi) — forced removal from Indonesian territory
- Blacklist (penangkalan) — prohibition of future entry
- Possible administrative detention at Rumah Detensi Imigrasi (Rudenim) before deportation flight
- Repatriation cost borne by foreigner OR sponsor's immigration guarantee deposit

## Blacklist (Penangkalan) durations — UU 63/2024
- Standard administrative: 6 months renewable (historical practice)
- Serious violations or crimes in Indonesia: up to 10 years
- Most serious cases (major crime, national security threat): LIFETIME ban

## Blacklist removal (Pencabutan Penangkalan) — PP 45/2024 Section VI.E
- **Fee for removal after >60 days overstay or unpaid Biaya Beban**: Rp 90,000,000
- **Fee for removal due to lost/damaged KPP APEC card**: Rp 1,000,000
- Procedure: formal application to Direktur Jenderal Imigrasi with justification

## Other administrative actions (Permen 11/2024)
Imigrasi officials can impose (outside criminal proceedings):
- **Prevention (Pencegahan)**: temporary prohibition to leave Indonesia
- **Refusal (Penolakan)**: denial of entry at border
- **Deportation (Deportasi)**: forced removal
- **Cekal/exit ban**: during criminal proceedings
- **Administrative detention (Rudenim)**: pending removal

## Bali enforcement (Tim PORA operations)
Tim Pengawasan Orang Asing operates across Bali with surprise inspections (Sidak) and joint operations with Polda Bali, Satpol PP, BNN, Bea Cukai.

### Primary hotspot zones
- **Canggu** (Pererenan, Berawa, Echo Beach): digital nomads, remote workers
- **Seminyak/Kerobokan**: tourism, hospitality
- **Ubud** (Penestanan, Sayan): wellness, yoga retreats, artists
- **Sanur**: long-stay retirees
- **Denpasar**: offices, institutional
- **Kuta Selatan** (Nusa Dua): hospitality hubs

### Top violations detected
1. Working on visit visa (C1/VoA/eVoA) — #1 most common violation
2. Overstay
3. Commercial activity without NIB (business license)
4. Teaching yoga/surf/fitness/language without E23 Working KITAS
5. Digital nomads on E33G serving Indonesian clients (forbidden — E33G is foreign income only)
6. Expired KITAS without timely renewal
7. Failure to report address change (wajib lapor)

### Recent high-profile cases (2025-2026)
- 28 March 2025: British national SL (45) with Interpol Red Notice arrested at TPI Ngurah Rai
- 7 March 2026: Russian clandestine narcotics laboratory dismantled in Gianyar by Imigrasi + BNN + Bea Cukai
- Iraqi family intercepted attempting entry with fake Belgian passports

## Citizen surveillance network
Hotel, villa, and accommodation operators are LEGALLY OBLIGED (PP 31/2013 Pasal 187) to report foreign guest data on request. Required data includes full name, DOB, gender, phone, nationality, and passport number. Citizen complaints (competitors, neighbors) frequently trigger Tim PORA investigations.

## Bali Tourist Levy — NOT immigration enforcement
Perda Bali 2/2025 imposes Rp 150,000 per foreign tourist (payable at lovebali.baliprov.go.id). This is a PROVINCIAL tax for cultural/environmental preservation, NOT a national immigration fee and NOT an enforcement tool. KITAS/KITAP holders likely exempt (confirm via "Apply Exemption" on official portal).
""",
    },
]


async def upsert_concept_doc(client: httpx.AsyncClient, doc: dict[str, Any]) -> None:
    """Upsert a standalone concept document. ID is deterministic from concept_id."""
    import uuid
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nb2-concept:{doc['concept_id']}"))
    text = doc["text"].strip()

    dense = await embed_dense(client, text)

    payload = {
        "text": text,
        "metadata": {
            "code": doc["concept_id"].upper(),
            "title": doc["title"],
            "category": "Concept Note",
            "doc_type": "concept",
            "version": "2026-04-17",
            "source": f"NB-2 Concept: {doc['title']}",
            "is_concept": True,
            "stay_rules_validated": "NB-2 2026-04-17",
        },
    }

    body = {"points": [{"id": point_id, "vector": {"dense": dense}, "payload": payload}]}
    r = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
        json=body,
        headers={"api-key": QDRANT_API_KEY},
        timeout=60.0,
    )
    if r.status_code >= 400:
        logger.error("[concept:%s] upsert failed: %s", doc["concept_id"], r.text)
    r.raise_for_status()
    logger.info("[concept:%s] upserted id=%s (%d chars)", doc["concept_id"], point_id, len(text))


async def main() -> int:
    if not QDRANT_API_KEY:
        logger.error("QDRANT_API_KEY missing")
        return 1
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY missing")
        return 1

    success = 0
    failed = 0
    async with httpx.AsyncClient() as client:
        # 1) Enrich all visa-code documents
        for code, rule in RULES.items():
            try:
                await enrich_one(client, code, rule)
                success += 1
            except Exception:
                logger.exception("[%s] failed", code)
                failed += 1

        # 2) Upsert standalone concept documents
        for doc in CONCEPT_DOCS:
            try:
                await upsert_concept_doc(client, doc)
                success += 1
            except Exception:
                logger.exception("[concept:%s] failed", doc["concept_id"])
                failed += 1

    logger.info("DONE: %d success, %d failed", success, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
