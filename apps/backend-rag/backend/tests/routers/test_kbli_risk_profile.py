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


def test_placeholder_license_row_never_hides_a_real_risk() -> None:
    # KBLI 91300: a risk-less "Sertifikat Standar" row sat next to rows carrying
    # "Menengah Rendah"; the old licenses[0] read returned "Unknown" when it came first.
    rows = [_lic("Unknown"), _lic("Menengah Rendah"), _lic("Menengah Rendah")]
    assert _resolve_risk_profile(None, rows) == "Menengah Rendah"


def test_resolution_is_independent_of_row_order() -> None:
    rows = [_lic("Unknown"), _lic("Rendah"), _lic("Menengah Tinggi")]
    forward = _resolve_risk_profile(None, rows)
    assert forward == _resolve_risk_profile(None, list(reversed(rows))) == "Menengah Tinggi"


def test_only_placeholder_rows_is_an_honest_gap() -> None:
    assert _resolve_risk_profile(None, [_lic("Unknown"), _lic("unknown")]) == "Not classified"


def test_single_healthy_row_unchanged() -> None:
    assert _resolve_risk_profile(None, [_lic("Rendah")]) == "Rendah"
