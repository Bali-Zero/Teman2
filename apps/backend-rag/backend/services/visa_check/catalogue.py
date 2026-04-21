"""Visa catalogue — the finite set of visa types our app knows about.

Single source of truth: VISA_META. DEFAULT_DURATION_DAYS and
EXTENSION_POLICY are derived for backwards compatibility with clock.py.

Every entry is traceable:
- name_en / name_id / category: seed_visa_types_complete_2026.py
- duration_days / extensions: MEMORY.md reference_visa_c_duration_rules.md
  for C-series; NB-2 NotebookLM for the rest (duration_source field)
- purposes: match_tree.Purpose tags — which branches surface this code
- min_budget_idr: Bali Zero commercial judgement, not a legal threshold
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# NOTE: match_tree.Purpose is imported lazily inside a TYPE_CHECKING block
# below to avoid a circular import (match_tree imports from this module).
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.visa_check.match_tree import Purpose


class VisaType(str, Enum):
    # ── Visit Visa (single entry, C-series) ──────────────────
    C1 = "C1"                     # Tourism
    C2 = "C2"                     # Business
    C6 = "C6"                     # Social activity
    C7 = "C7"                     # Art & culture performance
    C7A = "C7A"                   # Music performance
    C7B = "C7B"                   # Music crew
    C18 = "C18"                   # Work trial
    C22A = "C22A"                 # Internship 60d
    # ── Multiple Entry (D-series) ────────────────────────────
    D2 = "D2"                     # Multiple-entry business
    D12 = "D12"                   # Business investigation 1–2y
    # ── KITAS (E-series) ─────────────────────────────────────
    E23 = "E23"                   # Working KITAS
    E23_FREELANCE = "E23-FREELANCE"  # Freelance KITAS
    E28A = "E28A"                 # Investor KITAS 2y
    E30A = "E30A"                 # Education (basic & secondary)
    E31 = "E31"                   # Family KITAS
    E33E = "E33E"                 # Second Home Elder 5y (golden)
    E33F = "E33F"                 # Second Home Elder 1y
    E33G = "E33G"                 # Second Home Remote Worker / Digital Nomad


@dataclass(frozen=True)
class VisaMeta:
    name_en: str
    name_id: str
    category: str
    purposes: frozenset["Purpose"]
    duration_days: int
    extensions: tuple[int, int]      # (count, days_each); (0, 0) = non-extendable
    min_budget_idr: int | None       # None = no budget gate
    notes: str
    seed_source: str                 # "seed" | "seed+NB2"
    duration_source: str             # human-readable citation
    fit_tags: frozenset[str] = field(default_factory=frozenset)


class FitTag:
    """String constants for VisaMeta.fit_tags values. Single source of truth
    shared with match_tree.py so string renames are mechanical (grep + replace)
    rather than silent drift. Not an Enum because fit_tags values are used in
    plain-string comparisons inside frozensets and serialised to clients.
    """

    SHORT_TERM = "short_term"
    NO_BUDGET_GATE = "no_budget_gate"
    MIXED_PURPOSE = "mixed_purpose"
    SOCIAL_VISIT = "social_visit"
    MULTI_ENTRY = "multi_entry"
    FREQUENT_TRAVEL = "frequent_travel"
    PRE_PMA = "pre_pma"
    INVOICES_INDONESIAN_CLIENTS = "invoices_indonesian_clients"
    GOLDEN_VISA = "golden_visa"
    FOREIGN_EMPLOYER_SALARY = "foreign_employer_salary"


def _build_meta() -> dict[VisaType, VisaMeta]:
    """Construct VISA_META. Deferred to avoid circular import at module load."""
    from backend.services.visa_check.match_tree import Purpose

    SEED = "seed"
    SEED_NB2 = "seed+NB2"
    C_RULES = "MEMORY.md reference_visa_c_duration_rules.md"
    NB2 = "NB-2 NotebookLM immigration notebook"

    return {
        # ── C-series (Visit Visa, single entry) ──────────────
        VisaType.C1: VisaMeta(
            name_en="Visit Visa Tourism",
            name_id="Visa Kunjungan Wisata",
            category="Visit Visa",
            purposes=frozenset({Purpose.LONG_TOURISM, Purpose.WORK_REMOTE}),
            duration_days=60,
            extensions=(2, 60),              # 60 + 2×60 = 180 max
            min_budget_idr=None,
            notes="Pure tourism single entry. Extendable twice ×60d = 180d max.",
            seed_source=SEED,
            duration_source=C_RULES,
            fit_tags=frozenset({FitTag.SHORT_TERM, FitTag.NO_BUDGET_GATE}),
        ),
        # NOTE: C2 and D2 share name/name_id in the seed; disambiguated by `category`.
        VisaType.C2: VisaMeta(
            name_en="Visit Visa Business",
            name_id="Visa Kunjungan Bisnis",
            category="Visit Visa",
            purposes=frozenset({Purpose.LONG_TOURISM, Purpose.WORK_REMOTE}),
            duration_days=60,
            extensions=(2, 60),
            min_budget_idr=None,
            notes="Business meetings, no paid work. Extendable ×2.",
            seed_source=SEED,
            duration_source=C_RULES,
            fit_tags=frozenset({FitTag.MIXED_PURPOSE}),
        ),
        VisaType.C6: VisaMeta(
            name_en="Visit Visa Social Activity",
            name_id="Visa Kunjungan Kegiatan Sosial",
            category="Visit Visa",
            purposes=frozenset({Purpose.LONG_TOURISM}),
            duration_days=60,
            extensions=(2, 60),
            min_budget_idr=None,
            notes="Family visit / NGO / religious activity. Non-commercial.",
            seed_source=SEED,
            duration_source=C_RULES,
            fit_tags=frozenset({FitTag.SOCIAL_VISIT}),
        ),
        VisaType.C7: VisaMeta(
            name_en="Visit Visa Penampilan Seni dan Budaya",
            name_id="Visa Kunjungan Penampilan Seni dan Budaya",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=60,
            extensions=(2, 60),
            min_budget_idr=None,
            notes="Art / cultural performance. Paid per-event.",
            seed_source=SEED,
            duration_source=C_RULES,
        ),
        VisaType.C7A: VisaMeta(
            name_en="Visit Visa Music Performance",
            name_id="Visa Kunjungan Penampilan Musik",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=30,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="Single music event. Non-extendable.",
            seed_source=SEED,
            duration_source=C_RULES,
        ),
        VisaType.C7B: VisaMeta(
            name_en="Visit Visa Kru Music Performance",
            name_id="Visa Kunjungan Kru Penampilan Musik",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=30,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="Music crew accompanying C7A performer. Non-extendable.",
            seed_source=SEED,
            duration_source=C_RULES,
        ),
        VisaType.C18: VisaMeta(
            name_en="Visit Visa Foreign Worker Competency Test",
            name_id="Visa Kunjungan Uji Kemampuan Tenaga Kerja Asing",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=90,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="90-day work trial before committing to E23 KITAS.",
            seed_source=SEED_NB2,
            duration_source=NB2,
        ),
        VisaType.C22A: VisaMeta(
            name_en="Visit Visa Internship Akademik",
            name_id="Visa Kunjungan Pemagangan Akademik",
            category="Visit Visa",
            purposes=frozenset({Purpose.WORK_EMPLOYEE, Purpose.STUDENT}),
            duration_days=60,
            extensions=(0, 0),
            min_budget_idr=None,
            notes="Short internship hosted by an Indonesian entity.",
            seed_source=SEED_NB2,
            duration_source=NB2,
        ),
        # ── D-series (Multiple Entry) ─────────────────────────
        # NOTE: see C2 above — D2 shares the same name/name_id (Multiple Entry variant).
        VisaType.D2: VisaMeta(
            name_en="Visit Visa Business",
            name_id="Visa Kunjungan Bisnis",
            category="Multiple Entry",
            purposes=frozenset({Purpose.WORK_REMOTE, Purpose.INVESTOR}),
            duration_days=60,            # per entry
            extensions=(0, 0),           # re-enter instead of extending
            min_budget_idr=None,
            notes="1- or 2-year multiple-entry business. Users who travel in/out.",
            seed_source=SEED_NB2,
            duration_source=NB2,
            fit_tags=frozenset({FitTag.MULTI_ENTRY, FitTag.FREQUENT_TRAVEL}),
        ),
        VisaType.D12: VisaMeta(
            name_en="Visit Visa Pre-Investment",
            name_id="Visa Kunjungan Pra-Investasi",
            category="Multiple Entry",
            purposes=frozenset({Purpose.INVESTOR}),
            duration_days=365,
            extensions=(1, 365),         # 1 + 1 year = 2 years total
            min_budget_idr=None,
            notes="Scouting visa: evaluate market before committing to PT PMA.",
            seed_source=SEED_NB2,
            duration_source=NB2,
            fit_tags=frozenset({FitTag.PRE_PMA}),
        ),
        # ── E-series (KITAS / Limited Stay) ───────────────────
        VisaType.E23: VisaMeta(
            name_en="Working Visa",
            name_id="Visa Kerja",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.WORK_EMPLOYEE}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="Employer-sponsored. Requires RPTKA before application.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E23_FREELANCE: VisaMeta(
            name_en="Freelance KITAS (E23)",
            name_id="Freelance KITAS (E23)",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.WORK_REMOTE}),
            duration_days=180,
            extensions=(1, 180),
            min_budget_idr=25_800_000,   # Offshore fee lower bound
            notes="Freelance — for users invoicing Indonesian clients, not foreign employers.",
            seed_source=SEED_NB2,
            duration_source=NB2,
            fit_tags=frozenset({FitTag.INVOICES_INDONESIAN_CLIENTS}),
        ),
        VisaType.E28A: VisaMeta(
            name_en="Investor Visa",
            name_id="Visa Investor",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.INVESTOR}),
            duration_days=365 * 2,
            extensions=(1, 365 * 2),
            min_budget_idr=500_000_000,  # 500M IDR = high-budget threshold
            notes="Requires PT PMA + formal investment plan (~IDR 10bn capital).",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E30A: VisaMeta(
            name_en="Education Visa Dasar dan Menengah",
            name_id="Visa Pendidikan Dasar dan Menengah",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.STUDENT}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="University-sponsored. Valid for programme duration.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E31: VisaMeta(
            name_en="Family Visa",
            name_id="Visa Keluarga",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.FAMILY}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="Spouse/dependent of KITAS/KITAP holder.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E33E: VisaMeta(
            name_en="Second Home Visa Elderly for 5 Years Golden Visa",
            name_id="Visa Rumah Kedua Lansia Untuk 5 Tahun Golden Visa",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.RETIREMENT}),
            duration_days=365 * 5,
            extensions=(0, 0),
            min_budget_idr=500_000_000,
            notes="Golden visa for 55+ retirees. 5-year single block.",
            seed_source=SEED,
            duration_source=NB2,
            fit_tags=frozenset({FitTag.GOLDEN_VISA}),
        ),
        VisaType.E33F: VisaMeta(
            name_en="Second Home Visa Elderly for 1 Year",
            name_id="Visa Rumah Kedua Lansia Untuk 1 Tahun",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.RETIREMENT}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=None,
            notes="Standard 55+ retirement. >= USD 1,500/mo passive income.",
            seed_source=SEED,
            duration_source=NB2,
        ),
        VisaType.E33G: VisaMeta(
            name_en="Second Home Visa Remote Worker / Digital Nomad Golden Visa",
            name_id="Visa Rumah Kedua Pekerja Jarak Jauh Golden Visa",
            category="KITAS/Limited Stay",
            purposes=frozenset({Purpose.WORK_REMOTE, Purpose.INVESTOR}),
            duration_days=365,
            extensions=(1, 365),
            min_budget_idr=50_000_000,
            notes="Remote worker salaried by foreign employer. USD 60k savings proof.",
            seed_source=SEED,
            duration_source=NB2,
            fit_tags=frozenset({FitTag.FOREIGN_EMPLOYER_SALARY}),
        ),
    }


# VISA_META is built via a function so the Purpose import can be deferred
# (match_tree.py imports from this module → circular import otherwise).
VISA_META: dict[VisaType, VisaMeta] = _build_meta()


# ── Derived dicts — kept for clock.py backwards compatibility ────

DEFAULT_DURATION_DAYS: dict[VisaType, int] = {
    vt: meta.duration_days for vt, meta in VISA_META.items()
}

EXTENSION_POLICY: dict[VisaType, tuple[int, int]] = {
    vt: meta.extensions for vt, meta in VISA_META.items()
}


__all__ = [
    "VisaType",
    "VisaMeta",
    "FitTag",
    "VISA_META",
    "DEFAULT_DURATION_DAYS",
    "EXTENSION_POLICY",
]
