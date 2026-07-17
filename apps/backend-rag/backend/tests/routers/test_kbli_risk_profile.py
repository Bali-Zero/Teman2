"""Risk-profile resolution for inspect_kbli (Zero decision 2026-07-17).

An undefined risk must surface as an honest "Not classified" gap, never the old
false-reassuring "Low" default. A cured false-friend code (per_skala detached from
a cross-vintage collision) has NO risk basis, so "Low" would lie to the client.
"""

from backend.app.routers.kbli_notebook import KBLILicense, _resolve_risk_profile


def _lic(risk_level: str) -> KBLILicense:
    return KBLILicense(
        type="NIB dan Sertifikat Standar",
        scale=["Menengah"],
        risk_level=risk_level,
        sla="Otomatis",
        requirements=[],
    )


def test_qdrant_risk_takes_precedence() -> None:
    # Qdrant kategori_risiko is the primary source when present.
    assert _resolve_risk_profile("Menengah Tinggi", [_lic("Rendah")]) == "Menengah Tinggi"


def test_falls_back_to_first_license_risk_when_no_qdrant() -> None:
    assert _resolve_risk_profile(None, [_lic("Tinggi")]) == "Tinggi"


def test_not_classified_when_no_risk_anywhere() -> None:
    # Cured false-friend: Qdrant risk cleared AND no license rows → honest gap.
    assert _resolve_risk_profile(None, []) == "Not classified"


def test_regression_never_the_old_low_default() -> None:
    # The old fallback "Low" was a false reassurance — it must be gone.
    assert _resolve_risk_profile(None, []) != "Low"
    assert _resolve_risk_profile("", []) == "Not classified"
    # An empty license risk string is not a low reading either.
    assert _resolve_risk_profile(None, [_lic("")]) == "Not classified"
