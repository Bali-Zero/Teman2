"""Tests for the 2026 price list generator (HTML + Markdown only — PDF tested separately)."""
import base64
import json
from pathlib import Path

import pytest

from scripts.pricelist_2026 import generate

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_prices.json"


@pytest.fixture
def fixture_data():
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def stub_assets(tmp_path):
    """Build a directory of 1x1 transparent PNGs for every icon_id + hero used in fixture."""
    heros_dir = tmp_path / "heros"
    icons_dir = tmp_path / "icons"
    heros_dir.mkdir()
    icons_dir.mkdir()
    # 1x1 transparent PNG
    one_pixel = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    # Heros for sections used by the fixture
    # Fixture has only single_entry_visas + tax_accounting → maps to heros 01_visas + 03_tax
    for hero_name in ["01_visas.png", "03_tax.png"]:
        (heros_dir / hero_name).write_bytes(one_pixel)
    # Icons used by fixture
    for icon_id in ["visa-tourism", "tax-monthly"]:
        (icons_dir / f"{icon_id}.png").write_bytes(one_pixel)
    # Logo
    (tmp_path / "logo_circle.png").write_bytes(one_pixel)
    return tmp_path


def test_generate_html_smoke(fixture_data, stub_assets, tmp_path):
    out_html = tmp_path / "out.html"
    generate.render_html(
        data=fixture_data,
        assets_dir=stub_assets,
        out_path=out_html,
    )
    assert out_html.exists()
    html = out_html.read_text()
    # Cover content (h1 'BALI ZERO' removed 2026-05-06 — logo speaks for itself)
    assert "Price List 2026" in html
    assert "Bali Zero" in html  # appears in <title> + running header
    # Service rendered
    assert "C1 Tourism" in html
    assert "2.300.000 IDR" in html
    # Tier rendered
    assert "1.800.000 IDR" in html
    assert "2.000.000 IDR" in html
    # Contact rendered
    assert "zero@balizero.com" in html
    assert "+62 821 31 07 363" in html
    # Logo embedded as base64 data URI
    assert 'src="data:image/png;base64,' in html


def test_generate_markdown_smoke(fixture_data, tmp_path):
    out_md = tmp_path / "out.md"
    generate.render_markdown(
        data=fixture_data,
        out_path=out_md,
    )
    assert out_md.exists()
    md = out_md.read_text()
    assert "# Bali Zero — Price List 2026" in md
    assert "C1 Tourism" in md
    assert "1.800.000 IDR – 2.000.000 IDR" in md
    assert "wa.me/628213107363" in md


def test_generate_rejects_invalid_json(stub_assets, tmp_path):
    bad = {"version": "2026.1"}  # missing everything
    out_html = tmp_path / "out.html"
    with pytest.raises(generate.SchemaError):
        generate.render_html(data=bad, assets_dir=stub_assets, out_path=out_html)


def test_generate_rejects_missing_icon_asset(fixture_data, tmp_path):
    # No assets dir contents — only logo
    (tmp_path / "logo_circle.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # garbage but exists
    out_html = tmp_path / "out.html"
    with pytest.raises(generate.AssetMissingError) as exc:
        generate.render_html(data=fixture_data, assets_dir=tmp_path, out_path=out_html)
    err = str(exc.value)
    assert "visa-tourism" in err or "tax-monthly" in err or "01_visas" in err or "03_tax" in err


def test_generate_html_contains_qr_link(fixture_data, stub_assets, tmp_path):
    out_html = tmp_path / "out.html"
    generate.render_html(data=fixture_data, assets_dir=stub_assets, out_path=out_html)
    html = out_html.read_text()
    # Multiple base64 images embedded (logo + heros + icons + qr)
    assert html.count('src="data:image/png;base64,') >= 3
    # Closing section text
    assert "Get in touch" in html
