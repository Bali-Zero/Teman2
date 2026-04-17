"""Prime Nexus — Property tax (PBB/BPHTB) and foreigner eligibility."""

from __future__ import annotations

from typing import Any

from backend.services.prime.geo_service import NON_BUILDABLE_ZONES, RESTRICTED_ZONES

# =============================================================================
# PROPERTY TAX CALCULATOR (PBB + BPHTB)
# =============================================================================
_NPOPTKP_BY_KABUPATEN: dict[str, int] = {
    "Badung": 80_000_000,
    "Denpasar": 80_000_000,
    "Gianyar": 60_000_000,
    "Tabanan": 60_000_000,
    "Karangasem": 60_000_000,
    "Klungkung": 60_000_000,
    "Bangli": 60_000_000,
    "Buleleng": 60_000_000,
    "Jembrana": 60_000_000,
}
_DEFAULT_NPOPTKP = 60_000_000


def calculate_property_tax(
    njop_total_idr: float,
    kabupaten: str | None = None,
) -> dict[str, Any]:
    """Calculate Indonesian property taxes (PBB annual + BPHTB acquisition).

    PBB rates (Pajak Bumi dan Bangunan):
      - NJOP < 1B IDR: 0.1%
      - 1B <= NJOP < 10B: 0.2%
      - NJOP >= 10B: 0.3%

    BPHTB (Bea Perolehan Hak atas Tanah dan Bangunan):
      - 5% of (NJOP - NPOPTKP)
      - NPOPTKP varies by kabupaten (60-80M IDR)
    """
    notes: list[str] = []

    # PBB rate tiers
    if njop_total_idr < 1_000_000_000:
        pbb_rate = 0.001  # 0.1%
    elif njop_total_idr < 10_000_000_000:
        pbb_rate = 0.002  # 0.2%
    else:
        pbb_rate = 0.003  # 0.3%

    annual_pbb = njop_total_idr * pbb_rate

    # BPHTB
    kab_key = kabupaten.strip().title() if kabupaten else None
    npoptkp = _NPOPTKP_BY_KABUPATEN.get(kab_key or "", _DEFAULT_NPOPTKP)
    bphtb_base = max(0, njop_total_idr - npoptkp)
    acquisition_bphtb = bphtb_base * 0.05

    if kab_key and kab_key not in _NPOPTKP_BY_KABUPATEN:
        notes.append(f"Kabupaten '{kabupaten}' non riconosciuto — usato NPOPTKP default {_DEFAULT_NPOPTKP:,.0f} IDR")

    return {
        "annual_pbb": round(annual_pbb),
        "pbb_rate_pct": pbb_rate * 100,
        "acquisition_bphtb": round(acquisition_bphtb),
        "npoptkp_applied": npoptkp,
        "njop_used": njop_total_idr,
        "notes": notes,
    }


# =============================================================================
# PROPERTY ELIGIBILITY FOR FOREIGNERS
# =============================================================================
def calculate_property_eligibility(
    nationality: str,
    zone_code: str | None = None,
    njop_total_idr: float | None = None,
) -> dict[str, Any]:
    """Determine property ownership eligibility based on nationality.

    Based on UUPA (Undang-Undang Pokok Agraria), PP 18/2021, and
    the Knowledge Graph property subgraph rules.
    """
    nat = nationality.strip().upper()
    is_foreigner = nat in ("WNA", "FOREIGNER", "FOREIGN", "ASING")

    bphtb_estimate = round(njop_total_idr * 0.05) if njop_total_idr else None

    if is_foreigner:
        allowed_types = [
            {
                "type": "hak_pakai",
                "label": "Hak Pakai (Right to Use)",
                "duration": "30 years (renewable +20 +30 years)",
                "requirements": [
                    "Valid KITAS or KITAP residence permit",
                    "Notary deed (Akta Notaris)",
                    "BPN certificate verification",
                    "BPHTB tax payment (5%)",
                ],
                "estimated_costs": {
                    "bphtb_5pct": bphtb_estimate,
                    "notary_fee_approx_idr": 5_000_000,
                    "bpn_registration_idr": 1_000_000,
                },
                "notes": "Most common path for foreign property ownership in Bali",
            },
            {
                "type": "hgb_via_pma",
                "label": "HGB via PT PMA (Building Rights via Foreign Company)",
                "duration": "30 years (renewable +20 +30 years)",
                "requirements": [
                    "Established PT PMA company",
                    "Minimum investment 10B IDR (company-level)",
                    "Company deed and KBLI registration",
                    "BPN certificate verification",
                    "BPHTB tax payment (5%)",
                ],
                "estimated_costs": {
                    "bphtb_5pct": bphtb_estimate,
                    "pma_setup_approx_idr": 50_000_000,
                },
                "notes": "For commercial property — requires PT PMA company (cross-domain: company setup)",
            },
            {
                "type": "rental",
                "label": "Rental / Leasehold (Sewa)",
                "duration": "1-25 years (negotiable)",
                "requirements": [
                    "Rental agreement (Surat Perjanjian Sewa)",
                    "Passport copy",
                    "Security deposit (typically 1-3 months)",
                ],
                "estimated_costs": {
                    "deposit_months": 3,
                },
                "notes": "Simplest option — no ownership transfer, no BPHTB",
            },
        ]
        blocked_types = [
            {
                "type": "hak_milik",
                "label": "Hak Milik (Full Ownership)",
                "reason": "Reserved for Indonesian citizens only (UUPA Art. 21)",
            },
        ]
        nationality_class = "WNA"
    else:
        allowed_types = [
            {
                "type": "hak_milik",
                "label": "Hak Milik (Full Ownership)",
                "duration": "Perpetual",
                "requirements": ["Indonesian citizenship (WNI)", "Notary deed", "BPN registration"],
                "estimated_costs": {
                    "bphtb_5pct": bphtb_estimate,
                    "notary_fee_approx_idr": 5_000_000,
                },
                "notes": "Strongest title — full ownership rights",
            },
            {
                "type": "hak_pakai",
                "label": "Hak Pakai (Right to Use)",
                "duration": "30 years (renewable)",
                "requirements": ["Notary deed", "BPN registration"],
                "estimated_costs": {"bphtb_5pct": bphtb_estimate},
                "notes": "Also available to Indonesian citizens",
            },
            {
                "type": "hgb",
                "label": "HGB (Building Rights)",
                "duration": "30 years (renewable)",
                "requirements": ["Notary deed", "BPN registration"],
                "estimated_costs": {"bphtb_5pct": bphtb_estimate},
                "notes": "For commercial/business property",
            },
            {
                "type": "rental",
                "label": "Rental / Leasehold (Sewa)",
                "duration": "1-25 years",
                "requirements": ["Rental agreement"],
                "estimated_costs": {"deposit_months": 1},
                "notes": "Simplest option",
            },
        ]
        blocked_types = []
        nationality_class = "WNI"

    result: dict[str, Any] = {
        "nationality_class": nationality_class,
        "allowed_types": allowed_types,
        "blocked_types": blocked_types,
    }

    # Zone-based warnings
    if zone_code and zone_code in RESTRICTED_ZONES:
        result["zone_warning"] = (
            f"Zone {zone_code} is restricted — property acquisition may face "
            "additional regulatory barriers or be prohibited entirely."
        )
    if zone_code and zone_code in NON_BUILDABLE_ZONES:
        result["zone_warning"] = (
            f"Zone {zone_code} is non-buildable — only land investment possible, "
            "no construction permits (IMB/PBG) will be issued."
        )

    if is_foreigner:
        result["cross_domain_note"] = (
            "HGB via PT PMA requires company formation — "
            "see company setup workflow for requirements and timeline."
        )

    return result
