import pytest

from backend.app.core.config import settings
from backend.services.response.standard_templates import (
    get_company_setup_template,
    get_tax_template,
    get_visa_template,
)


@pytest.mark.parametrize(
    ("language", "heading", "pricing_marker"),
    [
        ("en", "Visa Snapshot", "Official price from get_pricing"),
        ("it", "Scheda Visto", "Prezzo ufficiale da get_pricing"),
        ("id", "Detail Visa", "Harga resmi dari get_pricing"),
    ],
)
def test_get_visa_template_localizes_core_sections(
    language: str,
    heading: str,
    pricing_marker: str,
) -> None:
    template = get_visa_template(language)

    assert heading in template
    assert pricing_marker in template
    assert settings.COMPANY_NAME in template
    assert "[CODE]" in template or "[CODICE]" in template or "[KODE]" in template


@pytest.mark.parametrize(
    ("factory", "language", "expected"),
    [
        (get_tax_template, "en", "Tax Summary"),
        (get_tax_template, "it", "Riepilogo Fiscale"),
        (get_tax_template, "id", "Ringkasan Pajak"),
        (get_company_setup_template, "en", "Company Setup"),
        (get_company_setup_template, "it", "Setup Aziendale"),
        (get_company_setup_template, "id", "Pendirian Perusahaan"),
    ],
)
def test_templates_include_expected_domain_heading(
    factory: callable,
    language: str,
    expected: str,
) -> None:
    assert expected in factory(language)


def test_unknown_language_falls_back_to_english_templates() -> None:
    assert "Visa Snapshot" in get_visa_template("fr")
    assert "Tax Summary" in get_tax_template("fr")
    assert "Company Setup" in get_company_setup_template("fr")
