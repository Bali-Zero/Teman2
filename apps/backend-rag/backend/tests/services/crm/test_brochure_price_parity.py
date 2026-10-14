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
from html.parser import HTMLParser
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
GENERATOR_PATH = BACKEND_ROOT / "scripts" / "generate_brochure.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_brochure", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _load_generator()
MONEY_RE = re.compile(r"\d{1,3}(?:\.\d{3})+")


class _TableRowParser(HTMLParser):
    """Extract table body rows as lists of stripped ``<td>`` cell strings."""

    def __init__(self) -> None:
        super().__init__()
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


def _parse_rows(html: str) -> list[list[str]]:
    parser = _TableRowParser()
    parser.feed(html)
    return parser.rows


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


def _iter_service_entries(node: dict, prefix: tuple[str, ...] = ()):
    for key, val in node.items():
        if isinstance(val, dict):
            if "name" in val:
                yield prefix + (key,), val
            else:
                yield from _iter_service_entries(val, prefix + (key,))


def _assert_parity(
    filled_html: str, raw_template: str, pricing: dict
) -> list[tuple[str, str]]:
    """Verify every printed price cell equals its canonical JSON entry."""
    template_rows = _parse_rows(raw_template)
    filled_rows = _parse_rows(filled_html)
    assert len(template_rows) == len(filled_rows)

    pairs: list[tuple[str, str]] = []
    for t_row, f_row in zip(template_rows, filled_rows, strict=True):
        assert len(t_row) == len(f_row)
        label = f_row[0]
        for t_cell, f_cell in zip(t_row, f_row, strict=True):
            match = GEN.PLACEHOLDER_RE.fullmatch(t_cell)
            if match is None:
                assert "Rp " not in f_cell and not MONEY_RE.search(f_cell), (
                    f"Unmapped price literal {f_cell!r} in row {label!r}"
                )
                continue
            placeholder = match.group(1)
            assert placeholder in GEN.PRICE_MAP, f"Unmapped placeholder {placeholder}"
            path, pinned_name = GEN.PRICE_MAP[placeholder]
            entry = _walk_entry(pricing, path)
            assert entry.get("internal") is not True, f"Internal row mapped: {path}"
            assert entry["name"] == pinned_name
            expected = _oracle_price(entry)
            assert f_cell == expected, (
                f"Row {label!r} ({placeholder}): printed {f_cell!r} != canonical {expected!r}"
            )
            pairs.append((label, f_cell))

    assert len(pairs) == len(GEN.PRICE_MAP)
    return pairs


def test_every_printed_price_equals_its_canonical_row():
    """INNOCENCE: every rendered price cell matches its canonical JSON row."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    filled_html, _ = GEN.fill_template(raw_template, pricing)
    pairs = _assert_parity(filled_html, raw_template, pricing)
    assert len(pairs) == len(GEN.PRICE_MAP)


def test_no_hardcoded_idr_literal_in_template():
    """Raw template carries no hardcoded Rupiah figures; price cells are bare placeholders."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    uncommented = re.sub(r"<!--.*?-->", "", raw_template, flags=re.DOTALL)
    assert re.search(r"Rp\s+\d", uncommented) is None
    for row in _parse_rows(uncommented):
        for cell in row:
            assert MONEY_RE.search(cell) is None, f"Money-shaped literal in cell: {cell!r}"
            if "{{" in cell or "}}" in cell:
                assert GEN.PLACEHOLDER_RE.fullmatch(cell) is not None


def test_e33e_prints_45_million_and_not_the_old_14_million():
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


def test_no_internal_row_is_printed():
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


def test_guilt_stale_literal_in_template_fails():
    """GUILT (a): replacing E33E placeholder with 'Rp 14.000.000' fails generator and parity."""
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


def test_guilt_internal_row_in_price_map_is_refused(monkeypatch: pytest.MonkeyPatch):
    """GUILT (b): repointing PRICE_RET_OFF at internal Retirement (Offshore) stops the build."""
    raw_template = GEN.TEMPLATE_PATH.read_text(encoding="utf-8")
    pricing = GEN.load_pricing()
    monkeypatch.setitem(
        GEN.PRICE_MAP,
        "PRICE_RET_OFF",
        (("kitas_permits", "Retirement (Offshore)"), "Retirement (Offshore)"),
    )
    with pytest.raises(SystemExit, match="INTERNAL PRICE ROW"):
        GEN.fill_template(raw_template, pricing)


def test_guilt_drifted_price_fails_parity_against_canon():
    """GUILT (c): rendering a mutated E33E price (46M) fails parity against canonical JSON."""
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
