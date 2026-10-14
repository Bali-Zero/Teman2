"""Client brochure price parity against canonical 2026 pricing JSON.

The public brochure is generated from ``brochure_en.html`` and
``bali_zero_official_prices_2026.json`` via ``scripts/generate_brochure.py``.
Every printed price must come from a canonical public row in the JSON, and rows
marked ``"internal": true`` must never reach the brochure.

Guilt: a stale hardcoded Rupiah figure, a drifted rendered price, or a mapping
pointed at an internal row must fail immediately.
Innocence: every rendered price cell in the brochure matches an independent
oracle over its canonical JSON row, and public rows like E33E (Rp 45.000.000),
E33F Offshore, and Retirement KITAP + MERP render accurately.
"""

from __future__ import annotations

import copy
import importlib.util
import re
import types
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path

import pytest
from pypdf import PdfReader

BACKEND_ROOT = Path(__file__).resolve().parents[4]
GENERATOR_PATH = BACKEND_ROOT / "scripts" / "generate_brochure.py"


def _load_generator() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("generate_brochure", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _load_generator()
MONEY_RE = re.compile(r"\d{1,3}(?:\.\d{3})+")
CURRENCY_DIGIT_RE = re.compile(r"(?i)(?:\brp\.?|\bidr)\s*\d")
MILLION_JUTA_RE = re.compile(r"(?i)\d\s*(?:million|juta)")

# Explicit named exemptions for CTA phone number and office postal code in text-node scans.
TEMPLATE_SCAN_EXEMPTIONS: tuple[str, ...] = ("+62 821 3454 721", "80361")

ExpectedRow = tuple[str, tuple[str, ...], int, tuple[str, ...], str]

# Committed oracle table binding every placeholder (all 50) to its printed row cells
# (label_cell, qualifier_cells, price_col_index, canonical_path, canonical_row_name).
EXPECTED_ROWS: dict[str, ExpectedRow] = {
    "PRICE_VOA": (
        "B1 Visa on Arrival",
        ("30 days",),
        2,
        ("single_entry_visas", "B1 Visa on Arrival (VOA)"),
        "B1 Visa on Arrival (VOA)",
    ),
    "PRICE_C1": (
        "C1 Tourism",
        ("60 days",),
        2,
        ("single_entry_visas", "C1 Tourism"),
        "C1 Tourism",
    ),
    "PRICE_C1_EXT": (
        "C1 Tourism — extension",
        ("+60 days",),
        2,
        ("single_entry_visas", "C1 Tourism Extension"),
        "C1 Tourism — Extension (+60 days)",
    ),
    "PRICE_C2": (
        "C2 Business",
        ("60 days",),
        2,
        ("single_entry_visas", "C2 Business"),
        "C2 Business",
    ),
    "PRICE_C18": (
        "C18 Work Trial",
        ("90 days",),
        2,
        ("single_entry_visas", "C18 Work Trial"),
        "C18 Work Trial",
    ),
    "PRICE_C22": (
        "C22A&B Internship",
        ("180 days",),
        2,
        ("single_entry_visas", "C22A&B Internship (180 Days)"),
        "C22A&B Internship (180 Days)",
    ),
    "PRICE_D1_1": (
        "D1 Tourism",
        ("1 year",),
        2,
        ("multiple_entry_visas", "D1 Tourism (1 Year)"),
        "D1 Tourism (1 Year)",
    ),
    "PRICE_D2_1": (
        "D2 Business",
        ("1 year",),
        2,
        ("multiple_entry_visas", "D2 Business (1 Year)"),
        "D2 Business (1 Year)",
    ),
    "PRICE_D12_1": (
        "D12 Business Investigation",
        ("1 year",),
        2,
        ("multiple_entry_visas", "D12 Business Investigation (1 Year)"),
        "D12 Business Investigation (1 Year)",
    ),
    "PRICE_D12_2": (
        "D12 Business Investigation",
        ("2 years",),
        2,
        ("multiple_entry_visas", "D12 Business Investigation (2 Years)"),
        "D12 Business Investigation (2 Years)",
    ),
    "PRICE_E33G_OFF": (
        "E33G Remote Worker",
        ("Offshore",),
        2,
        ("kitas_permits", "E33G Remote Worker (Offshore)"),
        "E33G Remote Worker (Offshore)",
    ),
    "PRICE_E33G_ALT": (
        "E33G Remote Worker",
        ("Onshore",),
        2,
        ("kitas_permits", "E33G Remote Worker (Altus/Onshore)"),
        "E33G Remote Worker (Altus/Onshore)",
    ),
    "PRICE_INV_OFF": (
        "Investor KITAS, 2 years",
        ("Offshore",),
        2,
        ("kitas_permits", "Investor KITAS 2 Years (Offshore)"),
        "Investor KITAS 2 Years (Offshore)",
    ),
    "PRICE_E23_OFF": (
        "Freelance E23",
        ("Offshore",),
        2,
        ("kitas_permits", "Freelance E23 (Offshore)"),
        "Freelance E23 (Offshore)",
    ),
    "PRICE_RET_OFF": (
        "Retirement 55+ (Second Home senior, E33F)",
        ("Offshore, 1 year",),
        2,
        ("kitas_permits", "E33F Second Home Senior (1 Year, Offshore)"),
        "E33F Second Home Senior (1 Year, Offshore)",
    ),
    "PRICE_SPOUSE_OFF": (
        "Spouse or dependent, 1 year",
        ("Offshore",),
        2,
        ("kitas_permits", "Spouse 1 Year (Offshore)"),
        "Spouse 1 Year (Offshore)",
    ),
    "PRICE_E33E": (
        "E33E Second Home Senior, 5 years",
        ("Offshore / onshore",),
        2,
        ("kitas_permits", "E33E Second Home Senior (5 Years)"),
        "E33E Second Home Senior (5 Years)",
    ),
    "PRICE_KITAP_INV": (
        "Investor KITAP — re-entry included",
        (),
        1,
        ("kitap_permits", "Investor KITAP + MERP"),
        "Investor KITAP + MERP",
    ),
    "PRICE_KITAP_RET": (
        "Retirement KITAP — re-entry included",
        (),
        1,
        ("kitap_permits", "Retirement KITAP + MERP"),
        "Retirement KITAP + MERP",
    ),
    "PRICE_NEWCO": (
        "New PT PMA — full package, including OSS, BKPM, NIB and notarial deed",
        (),
        1,
        ("company_services", "New Company (PT PMA)"),
        "New Company (PT PMA)",
    ),
    "PRICE_VO": (
        "Virtual office, 1 year",
        (),
        1,
        ("company_services", "Virtual Office"),
        "Virtual Office",
    ),
    "PRICE_CLOSE_PMA": (
        "Closing a PMA company",
        (),
        1,
        ("consultant_services", "Close PMA Company"),
        "Close PMA Company",
    ),
    "PRICE_WK_OFF": (
        "Working KITAS",
        ("Offshore",),
        2,
        ("kitas_permits", "Working KITAS (Offshore)"),
        "Working KITAS (Offshore)",
    ),
    "PRICE_WK_ALT": (
        "Working KITAS",
        ("Onshore",),
        2,
        ("kitas_permits", "Working KITAS (Altus/Onshore)"),
        "Working KITAS (Altus/Onshore)",
    ),
    "PRICE_WK_EXT": (
        "Working KITAS — renewal",
        ("In place",),
        2,
        ("kitas_permits", "Working KITAS (Extend)"),
        "Working KITAS (Extend)",
    ),
    "PRICE_NPWPD": (
        "NPWPD — regional tax registration",
        (),
        1,
        ("consultant_services", "NPWPD Registration"),
        "NPWPD Registration",
    ),
    "PRICE_BPJS_TK": (
        "BPJS Ketenagakerjaan — employee social security",
        (),
        1,
        ("consultant_services", "BPJS Employee (Tenaga Kerja)"),
        "BPJS Employee (Tenaga Kerja)",
    ),
    "PRICE_BPJS_KES": (
        "BPJS Kesehatan — health insurance",
        (),
        1,
        ("consultant_services", "BPJS Insurance (Kesehatan)"),
        "BPJS Insurance (Kesehatan)",
    ),
    "PRICE_TAX_M_0_50": (
        "Up to 50",
        (),
        1,
        ("tax_accounting", "monthly_tax_basic", "Tier 0-50"),
        "Monthly Tax Report — 0 to 50 transactions (without LKPM & Annual)",
    ),
    "PRICE_TAX_M_50_100": (
        "50 to 100",
        (),
        1,
        ("tax_accounting", "monthly_tax_basic", "Tier 50-100"),
        "Monthly Tax Report — 50 to 100 transactions (without LKPM & Annual)",
    ),
    "PRICE_TAX_M_100_200": (
        "100 to 200",
        (),
        1,
        ("tax_accounting", "monthly_tax_basic", "Tier 100-200"),
        "Monthly Tax Report — 100 to 200 transactions (without LKPM & Annual)",
    ),
    "PRICE_TAX_M_200": (
        "Over 200",
        (),
        1,
        ("tax_accounting", "monthly_tax_basic", "Tier 200+"),
        "Monthly Tax Report — more than 200 transactions (without LKPM & Annual)",
    ),
    "PRICE_TAX_B_0_50": (
        "Up to 50",
        (),
        2,
        ("tax_accounting", "monthly_tax_bundled", "Tier 0-50"),
        "Monthly Tax Report — 0 to 50 transactions (including LKPM & Annual)",
    ),
    "PRICE_TAX_B_50_100": (
        "50 to 100",
        (),
        2,
        ("tax_accounting", "monthly_tax_bundled", "Tier 50-100"),
        "Monthly Tax Report — 50 to 100 transactions (including LKPM & Annual)",
    ),
    "PRICE_TAX_B_100_200": (
        "100 to 200",
        (),
        2,
        ("tax_accounting", "monthly_tax_bundled", "Tier 100-200"),
        "Monthly Tax Report — 100 to 200 transactions (including LKPM & Annual)",
    ),
    "PRICE_TAX_B_200": (
        "Over 200",
        (),
        2,
        ("tax_accounting", "monthly_tax_bundled", "Tier 200+"),
        "Monthly Tax Report — more than 200 transactions (including LKPM & Annual)",
    ),
    "PRICE_ANNUAL_CO": (
        "Corporate annual return — SPT Tahunan Badan",
        (),
        1,
        ("tax_accounting", "annual_standalone", "Annual Tax Company"),
        "Annual Tax Company",
    ),
    "PRICE_ANNUAL_PERS": (
        "Personal annual return — SPT Tahunan Orang Pribadi",
        (),
        1,
        ("tax_accounting", "annual_standalone", "Annual Tax Personal"),
        "Annual Tax Personal",
    ),
    "PRICE_LKPM": (
        "LKPM investment report",
        (),
        1,
        ("tax_accounting", "annual_standalone", "LKPM Yearly Report"),
        "LKPM Yearly Report",
    ),
    "PRICE_ANNUAL_ZERO": (
        "Dormant company — yearly financial report",
        (),
        1,
        ("tax_accounting", "annual_basic_packages", "Annual Company ZERO"),
        "Annual Company ZERO",
    ),
    "PRICE_SKTT": (
        "SKTT — resident registration card",
        (),
        1,
        ("other_process", "SKTT"),
        "SKTT",
    ),
    "PRICE_SKCK": (
        "SKCK — police clearance certificate",
        (),
        1,
        ("other_process", "SKCK"),
        "SKCK",
    ),
    "PRICE_DOM": (
        "Domicile letter",
        (),
        1,
        ("other_process", "Domicilie Letter"),
        "Domicilie Letter",
    ),
    "PRICE_PP5": (
        "Passport, 5 years",
        (),
        1,
        ("other_process", "Passport 5 Years"),
        "Passport 5 Years",
    ),
    "PRICE_PP10": (
        "Passport, 10 years",
        (),
        1,
        ("other_process", "Passport 10 Years"),
        "Passport 10 Years",
    ),
    "PRICE_MUT_PP": (
        "Passport mutation — new passport, same permit",
        (),
        1,
        ("other_process", "Mutation Passport"),
        "Mutation Passport",
    ),
    "PRICE_MUT_ADDR": (
        "Address mutation",
        (),
        1,
        ("other_process", "Mutation Address"),
        "Mutation Address",
    ),
    "PRICE_SIM": (
        "Driving licence",
        (),
        1,
        ("other_process", "Driving License"),
        "Driving License",
    ),
    "PRICE_EPO": (
        "Exit permit (EPO) — filed in Indonesia, surrendering your stay permit",
        (),
        1,
        ("other_process", "EPO (Exit Permit Only)"),
        "EPO (Exit Permit Only)",
    ),
    "PRICE_ERP": (
        "Exit permit — filed from abroad, if you have already left for good",
        (),
        1,
        ("other_process", "ERP (Exit Re-entry Permit)"),
        "ERP (Exit Permit Only — Offshore)",
    ),
}

# Pairs of (monthly_tax_basic, monthly_tax_bundled) placeholders sharing one table row.
TAX_ROW_PAIRS: dict[str, tuple[str, str]] = {
    "PRICE_TAX_M_0_50": ("PRICE_TAX_M_0_50", "PRICE_TAX_B_0_50"),
    "PRICE_TAX_B_0_50": ("PRICE_TAX_M_0_50", "PRICE_TAX_B_0_50"),
    "PRICE_TAX_M_50_100": ("PRICE_TAX_M_50_100", "PRICE_TAX_B_50_100"),
    "PRICE_TAX_B_50_100": ("PRICE_TAX_M_50_100", "PRICE_TAX_B_50_100"),
    "PRICE_TAX_M_100_200": ("PRICE_TAX_M_100_200", "PRICE_TAX_B_100_200"),
    "PRICE_TAX_B_100_200": ("PRICE_TAX_M_100_200", "PRICE_TAX_B_100_200"),
    "PRICE_TAX_M_200": ("PRICE_TAX_M_200", "PRICE_TAX_B_200"),
    "PRICE_TAX_B_200": ("PRICE_TAX_M_200", "PRICE_TAX_B_200"),
}


class _TableRowParser(HTMLParser):
    """Extract table body rows as lists of stripped ``<td>`` cell strings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr":
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


class _TextNodeParser(HTMLParser):
    """Extract visible text nodes outside ``<style>`` and ``<script>`` elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self.nodes.append(stripped)


def _parse_rows(html: str) -> list[list[str]]:
    parser = _TableRowParser()
    parser.feed(html)
    return parser.rows


def _scan_template_money_literals(raw_template: str) -> list[str]:
    """Scan every text node of an HTML template for hardcoded currency/money literals."""
    uncommented = re.sub(r"<!--.*?-->", "", raw_template, flags=re.DOTALL)
    parser = _TextNodeParser()
    parser.feed(uncommented)
    hits: list[str] = []
    for node in parser.nodes:
        cleaned = node
        for exemption in TEMPLATE_SCAN_EXEMPTIONS:
            cleaned = cleaned.replace(exemption, "")
        for pattern in (CURRENCY_DIGIT_RE, MONEY_RE, MILLION_JUTA_RE):
            for match in pattern.finditer(cleaned):
                hits.append(match.group(0))
    return hits


def _walk_entry(pricing: dict, path: tuple[str, ...]) -> dict:
    node: dict = pricing["services"]
    for part in path:
        node = node[part]
    assert isinstance(node, dict)
    return node


def _oracle_price(entry: dict) -> str:
    """Format canonical JSON entry independently without calling generator helpers."""
    price = (entry.get("price") or "").strip()
    if price:
        amount = price.removesuffix("IDR").strip()
        return f"Rp {amount}"
    low, high = entry["tier_range"]
    return f"Rp {low.removesuffix('IDR').strip()} – Rp {high.removesuffix('IDR').strip()}"


def _iter_service_entries(
    node: dict, prefix: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], dict]]:
    for key, val in node.items():
        if isinstance(val, dict):
            if "name" in val:
                yield prefix + (key,), val
            else:
                yield from _iter_service_entries(val, prefix + (key,))


def _assert_parity(
    filled_html: str, raw_template: str, pricing: dict
) -> list[tuple[str, str]]:
    """Verify every printed price cell and its row label/qualifiers match EXPECTED_ROWS."""
    assert len(EXPECTED_ROWS) == 50
    template_placeholders = set(GEN.PLACEHOLDER_RE.findall(raw_template))
    assert template_placeholders == set(EXPECTED_ROWS.keys()) == set(GEN.PRICE_MAP.keys())

    template_rows = _parse_rows(raw_template)
    filled_rows = _parse_rows(filled_html)
    assert len(template_rows) == len(filled_rows)

    pairs: list[tuple[str, str]] = []
    seen_placeholders: set[str] = set()
    for t_row, f_row in zip(template_rows, filled_rows, strict=True):
        assert len(t_row) == len(f_row)
        label = f_row[0]
        for col_idx, (t_cell, f_cell) in enumerate(zip(t_row, f_row, strict=True)):
            match = GEN.PLACEHOLDER_RE.fullmatch(t_cell)
            if match is None:
                assert "Rp " not in f_cell and not MONEY_RE.search(f_cell), (
                    f"Unmapped price literal {f_cell!r} in row {label!r}"
                )
                continue
            placeholder = match.group(1)
            assert placeholder in EXPECTED_ROWS, f"Unmapped placeholder {placeholder}"
            assert placeholder in GEN.PRICE_MAP, f"Unmapped placeholder {placeholder}"

            exp_label, exp_qualifiers, exp_col, exp_path, exp_name = EXPECTED_ROWS[
                placeholder
            ]
            assert GEN.PRICE_MAP[placeholder] == (exp_path, exp_name), (
                f"PRICE_MAP[{placeholder!r}] drifted from EXPECTED_ROWS"
            )
            assert col_idx == exp_col, (
                f"Placeholder {placeholder} at col {col_idx}, expected col {exp_col}"
            )
            assert f_row[0] == exp_label and t_row[0] == exp_label, (
                f"Placeholder {placeholder} label {f_row[0]!r} != expected {exp_label!r}"
            )
            actual_qualifiers = tuple(
                f_row[i]
                for i in range(1, len(f_row))
                if GEN.PLACEHOLDER_RE.fullmatch(t_row[i]) is None
            )
            assert actual_qualifiers == exp_qualifiers, (
                f"Placeholder {placeholder} qualifiers {actual_qualifiers!r} "
                f"!= expected {exp_qualifiers!r}"
            )
            if placeholder in TAX_ROW_PAIRS:
                assert len(f_row) == 3 and exp_qualifiers == ()
            else:
                assert len(f_row) == 2 + len(exp_qualifiers)
                assert tuple(f_row[1:exp_col]) == exp_qualifiers

            path, pinned_name = GEN.PRICE_MAP[placeholder]
            entry = _walk_entry(pricing, path)
            assert entry.get("internal") is not True, f"Internal row mapped: {path}"
            assert entry["name"] == pinned_name == exp_name
            expected = _oracle_price(entry)
            assert f_cell == expected, (
                f"Row {label!r} ({placeholder}): printed {f_cell!r} != canonical {expected!r}"
            )
            seen_placeholders.add(placeholder)
            pairs.append((label, f_cell))

    assert seen_placeholders == set(EXPECTED_ROWS.keys()) == set(GEN.PRICE_MAP.keys())
    assert len(pairs) == len(GEN.PRICE_MAP)
    return pairs


def _extract_normalised_pdf_text(pdf_path: Path = GEN.OUTPUT_PATH) -> str:
    reader = PdfReader(str(pdf_path))
    joined = " ".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", joined).strip()


def _anchored_pdf_sequence(placeholder: str, pricing: dict) -> str:
    label, qualifiers, _col, path, name = EXPECTED_ROWS[placeholder]
    if placeholder in TAX_ROW_PAIRS:
        m_key, b_key = TAX_ROW_PAIRS[placeholder]
        m_entry = _walk_entry(pricing, EXPECTED_ROWS[m_key][3])
        b_entry = _walk_entry(pricing, EXPECTED_ROWS[b_key][3])
        assert m_entry["name"] == EXPECTED_ROWS[m_key][4]
        assert b_entry["name"] == EXPECTED_ROWS[b_key][4]
        return f"{label} {_oracle_price(m_entry)} {_oracle_price(b_entry)}"
    entry = _walk_entry(pricing, path)
    assert entry["name"] == name
    return " ".join([label, *qualifiers, _oracle_price(entry)])


PDF_PARITY_CURE = (
    "Cure: cd apps/backend-rag && .venv/bin/python scripts/generate_brochure.py "
    "(no arguments; needs Playwright in the backend venv and network for the Montserrat font), "
    "then commit apps/mouth/public/static/brochure_balizero_en.pdf - that PDF is what clients receive."
)

STALE_E33E_14M_RE = re.compile(
    r"E33E Second Home Senior, 5 years[^R]{0,40}Rp 14\.000\.000"
)


def _pdf_prints_stale_e33e_14m(pdf_text: str) -> bool:
    """Return True if normalised PDF text prints Rp 14.000.000 on the E33E 5-year row."""
    return STALE_E33E_14M_RE.search(pdf_text) is not None


def _assert_pdf_parity(pdf_text: str, pricing: dict) -> None:
    """Assert every EXPECTED_ROWS entry is present as an anchored sequence in the PDF."""
    for placeholder in EXPECTED_ROWS:
        anchored = _anchored_pdf_sequence(placeholder, pricing)
        assert re.search(re.escape(anchored), pdf_text) is not None, (
            f"Missing anchored sequence in PDF for {placeholder}: {anchored!r}. "
            f"{PDF_PARITY_CURE}"
        )


def test_every_printed_price_equals_its_canonical_row() -> None:
    """INNOCENCE: every rendered price cell matches its canonical JSON row."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    filled_html, _ = GEN.fill_template(raw_template, pricing)
    pairs = _assert_parity(filled_html, raw_template, pricing)
    assert len(pairs) == len(GEN.PRICE_MAP)


def test_no_hardcoded_idr_literal_in_template() -> None:
    """Raw template carries no hardcoded Rupiah figures; price cells are bare placeholders."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert _scan_template_money_literals(raw_template) == []
    uncommented = re.sub(r"<!--.*?-->", "", raw_template, flags=re.DOTALL)
    for row in _parse_rows(uncommented):
        for cell in row:
            assert MONEY_RE.search(cell) is None, f"Money-shaped literal in cell: {cell!r}"
            if "{{" in cell or "}}" in cell:
                assert GEN.PLACEHOLDER_RE.fullmatch(cell) is not None


def test_e33e_prints_45_million_and_not_the_old_14_million() -> None:
    """E33E row prints canonical Rp 45.000.000 (not Rp 14.000.000); E33F prints its canon."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    filled_html, _ = GEN.fill_template(raw_template, pricing)
    rows = _parse_rows(filled_html)

    kitas = pricing["services"]["kitas_permits"]
    e33e_expected = _oracle_price(kitas["E33E Second Home Senior (5 Years)"])
    assert e33e_expected == "Rp 45.000.000"
    e33e_rows = [r for r in rows if "E33E" in r[0]]
    assert len(e33e_rows) == 1
    assert e33e_rows[0][-1] == e33e_expected
    assert "Rp 14.000.000" not in " ".join(e33e_rows[0])

    e33f_expected = _oracle_price(kitas["E33F Second Home Senior (1 Year, Offshore)"])
    e33f_rows = [r for r in rows if "E33F" in r[0]]
    assert len(e33f_rows) == 1
    assert e33f_rows[0][-1] == e33f_expected


def test_no_internal_row_is_printed() -> None:
    """Rows marked internal in the JSON are absent from PRICE_MAP and rendered HTML."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    filled_html, _ = GEN.fill_template(raw_template, pricing)

    mapped_paths = {path for path, _ in GEN.PRICE_MAP.values()}
    mapped_names = {name for _, name in GEN.PRICE_MAP.values()}
    internal_entries = [
        (path, entry)
        for path, entry in _iter_service_entries(pricing["services"])
        if entry.get("internal") is True
    ]
    assert len(internal_entries) >= 1
    for path, entry in internal_entries:
        assert path not in mapped_paths
        assert entry["name"] not in mapped_names
        assert entry["name"] not in filled_html

    kitap_ret = pricing["services"]["kitap_permits"]["Retirement KITAP + MERP"]
    assert kitap_ret.get("internal") is not True
    assert ("kitap_permits", "Retirement KITAP + MERP") in mapped_paths
    assert "Retirement KITAP" in filled_html
    assert _oracle_price(kitap_ret) in filled_html


def test_committed_pdf_anchored_rows_match_canonical_prices() -> None:
    """INNOCENCE (F2): committed PDF contains every EXPECTED_ROWS anchored sequence."""
    pricing = GEN.load_pricing()
    pdf_text = _extract_normalised_pdf_text(GEN.OUTPUT_PATH)
    _assert_pdf_parity(pdf_text, pricing)


def test_guilt_stale_literal_in_template_fails() -> None:
    """GUILT: replacing E33E placeholder with 'Rp 14.000.000' fails generator and parity."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    mutated_template = raw_template.replace("{{PRICE_E33E}}", "Rp 14.000.000")

    with pytest.raises(SystemExit):
        GEN.fill_template(mutated_template, pricing)

    resolved = {k: GEN.get_price(pricing, p, n) for k, (p, n) in GEN.PRICE_MAP.items()}
    hand_filled = GEN.PLACEHOLDER_RE.sub(lambda m: resolved[m.group(1)], mutated_template)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, raw_template, pricing)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, mutated_template, pricing)


def test_guilt_internal_row_in_price_map_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """GUILT: repointing PRICE_RET_OFF at internal Retirement (Offshore) stops the build."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    monkeypatch.setitem(
        GEN.PRICE_MAP,
        "PRICE_RET_OFF",
        (("kitas_permits", "Retirement (Offshore)"), "Retirement (Offshore)"),
    )
    with pytest.raises(SystemExit, match="INTERNAL PRICE ROW"):
        GEN.fill_template(raw_template, pricing)


def test_guilt_drifted_price_fails_parity_against_canon() -> None:
    """GUILT: rendering a mutated E33E price (46M) fails parity against canonical JSON."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    canonical_pricing = GEN.load_pricing()
    drifted = copy.deepcopy(canonical_pricing)
    drifted["services"]["kitas_permits"]["E33E Second Home Senior (5 Years)"]["price"] = (
        "46.000.000 IDR"
    )
    filled_html, _ = GEN.fill_template(raw_template, drifted)
    assert "Rp 46.000.000" in filled_html
    with pytest.raises(AssertionError, match="Rp 46.000.000"):
        _assert_parity(filled_html, raw_template, canonical_pricing)


def test_guilt_a_swap_voa_and_c1_ext_fails_parity() -> None:
    """GUILT (a): swapping {{PRICE_VOA}} and {{PRICE_C1_EXT}} fails row parity."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    mutated_template = (
        raw_template.replace("{{PRICE_VOA}}", "__TMP_SWAP__")
        .replace("{{PRICE_C1_EXT}}", "{{PRICE_VOA}}")
        .replace("__TMP_SWAP__", "{{PRICE_C1_EXT}}")
    )
    resolved = {k: GEN.get_price(pricing, p, n) for k, (p, n) in GEN.PRICE_MAP.items()}
    hand_filled = GEN.PLACEHOLDER_RE.sub(lambda m: resolved[m.group(1)], mutated_template)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, mutated_template, pricing)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, raw_template, pricing)


def test_guilt_b_swap_e33g_offshore_and_onshore_fails_parity() -> None:
    """GUILT (b): swapping {{PRICE_E33G_OFF}} and {{PRICE_E33G_ALT}} fails row parity."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    mutated_template = (
        raw_template.replace("{{PRICE_E33G_OFF}}", "__TMP_SWAP__")
        .replace("{{PRICE_E33G_ALT}}", "{{PRICE_E33G_OFF}}")
        .replace("__TMP_SWAP__", "{{PRICE_E33G_ALT}}")
    )
    resolved = {k: GEN.get_price(pricing, p, n) for k, (p, n) in GEN.PRICE_MAP.items()}
    hand_filled = GEN.PLACEHOLDER_RE.sub(lambda m: resolved[m.group(1)], mutated_template)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, mutated_template, pricing)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, raw_template, pricing)


def test_guilt_c_mutated_e33e_label_cell_fails_parity() -> None:
    """GUILT (c): changing only the E33E label cell to 'WRONG PRODUCT LABEL' fails parity."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    mutated_template = raw_template.replace(
        "<td>E33E Second Home Senior, 5 years</td>",
        "<td>WRONG PRODUCT LABEL</td>",
        1,
    )
    assert mutated_template != raw_template
    resolved = {k: GEN.get_price(pricing, p, n) for k, (p, n) in GEN.PRICE_MAP.items()}
    hand_filled = GEN.PLACEHOLDER_RE.sub(lambda m: resolved[m.group(1)], mutated_template)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, mutated_template, pricing)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, raw_template, pricing)


def test_guilt_d_mutated_freelance_e23_qualifier_cell_fails_parity() -> None:
    """GUILT (d): changing the Freelance E23 qualifier 'Offshore' to 'Onshore' fails parity."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    mutated_template = raw_template.replace(
        "<tr><td>Freelance E23</td><td>Offshore</td><td>{{PRICE_E23_OFF}}</td></tr>",
        "<tr><td>Freelance E23</td><td>Onshore</td><td>{{PRICE_E23_OFF}}</td></tr>",
        1,
    )
    assert mutated_template != raw_template
    resolved = {k: GEN.get_price(pricing, p, n) for k, (p, n) in GEN.PRICE_MAP.items()}
    hand_filled = GEN.PLACEHOLDER_RE.sub(lambda m: resolved[m.group(1)], mutated_template)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, mutated_template, pricing)
    with pytest.raises(AssertionError):
        _assert_parity(hand_filled, raw_template, pricing)


def test_guilt_e_pdf_parity_fails_when_e33e_canonical_price_changed_to_14m() -> None:
    """GUILT (e): anchored PDF check fails against pricing copy with E33E set to 14M IDR."""
    pricing = copy.deepcopy(GEN.load_pricing())
    pricing["services"]["kitas_permits"]["E33E Second Home Senior (5 Years)"]["price"] = (
        "14.000.000 IDR"
    )
    pdf_text = _extract_normalised_pdf_text(GEN.OUTPUT_PATH)
    with pytest.raises(AssertionError, match="PRICE_E33E"):
        _assert_pdf_parity(pdf_text, pricing)


def test_pdf_parity_failure_message_carries_the_cure() -> None:
    """PDF parity failure message explains how to regenerate and commit the brochure PDF."""
    pricing = copy.deepcopy(GEN.load_pricing())
    pricing["services"]["kitas_permits"]["E33E Second Home Senior (5 Years)"]["price"] = (
        "14.000.000 IDR"
    )
    pdf_text = _extract_normalised_pdf_text(GEN.OUTPUT_PATH)
    with pytest.raises(AssertionError, match="PRICE_E33E") as exc_info:
        _assert_pdf_parity(pdf_text, pricing)
    err_msg = str(exc_info.value)
    assert PDF_PARITY_CURE in err_msg
    assert "generate_brochure.py" in err_msg
    assert "brochure_balizero_en.pdf" in err_msg


def test_guilt_f_pdf_does_not_print_14m_for_e33e() -> None:
    """INNOCENCE (f): committed PDF does not print Rp 14.000.000 on the E33E 5-year row."""
    pdf_text = _extract_normalised_pdf_text(GEN.OUTPUT_PATH)
    assert _pdf_prints_stale_e33e_14m(pdf_text) is False


def test_guilt_f_helper_bites_on_the_pre_8506_pdf_row() -> None:
    """GUILT (f): qualifier-tolerant helper flags both pre-#8506 and onshore/offshore 14M E33E rows."""
    pre_8506_row = (
        "Spouse or dependent, 1 year Offshore Rp 11.000.000 "
        "E33E Second Home Senior, 5 years Offshore Rp 14.000.000 "
        "KITAP — permanent Permit Bali Zero fee Investor KITAP — re-entry included Rp 55.000.000"
    )
    onshore_variant_row = (
        "Spouse or dependent, 1 year Offshore Rp 11.000.000 "
        "E33E Second Home Senior, 5 years Offshore / onshore Rp 14.000.000 "
        "KITAP — permanent Permit Bali Zero fee Investor KITAP — re-entry included Rp 55.000.000"
    )
    current_row = (
        "Spouse or dependent, 1 year Offshore Rp 11.000.000 "
        "E33E Second Home Senior, 5 years Offshore / onshore Rp 45.000.000 "
        "KITAP — permanent Permit Bali Zero fee Investor KITAP — re-entry included Rp 55.000.000"
    )
    assert _pdf_prints_stale_e33e_14m(pre_8506_row) is True
    assert _pdf_prints_stale_e33e_14m(onshore_variant_row) is True
    assert _pdf_prints_stale_e33e_14m(current_row) is False


def test_guilt_g_hardcoded_idr_in_paragraph_is_flagged() -> None:
    """GUILT (g): template copy with '<p>from Rp14.000.000 - E33E for IDR 14.000.000.</p>' fails."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    mutated = raw_template + "\n<p>from Rp14.000.000 - E33E for IDR 14.000.000.</p>\n"
    hits = _scan_template_money_literals(mutated)
    assert len(hits) >= 2
    assert any("rp" in h.lower() for h in hits)
    assert any("idr" in h.lower() for h in hits)
