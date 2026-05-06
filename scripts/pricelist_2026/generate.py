"""Render HTML + Markdown for the 2026 Bali Zero price list.

Reads the JSON source + asset PNGs, runs them through Jinja2 templates,
emits self-contained HTML (base64 data URIs) and a clean Markdown that
links to repo-relative asset paths.

PDF generation is a separate concern (see scripts/pricelist_2026/render_pdf.py).
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scripts.pricelist_2026 import schema

TEMPLATE_DIR = Path(__file__).parent / "templates"


class SchemaError(Exception):
    """Raised when the JSON fails schema validation."""


class AssetMissingError(Exception):
    """Raised when a required hero or icon PNG is missing."""


# Maps category key → (roman, title, intro, hero_basename)
SECTION_META: dict[str, tuple[str, str, str, str]] = {
    "single_entry_visas": (
        "I", "Single Entry Visas",
        "Short-stay visas for a single entry to Indonesia.",
        "01_visas",
    ),
    "multiple_entry_visas": (
        "II", "Multiple Entry Visas",
        "Multi-entry visas for repeat travel.",
        "01_visas",
    ),
    "kitas_permits": (
        "III", "KITAS Permits",
        "Long-stay residence permits for foreign nationals.",
        "02_kitas_kitap",
    ),
    "kitap_permits": (
        "IV", "KITAP + MERP",
        "Permanent residence permits and multiple re-entry permits.",
        "02_kitas_kitap",
    ),
    "tax_accounting": (
        "V", "Tax & Accounting",
        "Monthly bookkeeping packages, annual filings and stand-alone fees.",
        "03_tax",
    ),
    "company_services": (
        "VI", "Company Services",
        "PT PMA setup, virtual office and corporate amendments.",
        "04_company",
    ),
    "consultant_services": (
        "VII", "Bali Zero Consultant Services",
        "Compliance and registration fees handled by Bali Zero.",
        "04_company",
    ),
    "other_process": (
        "VIII", "Other Process",
        "Passports, identity documents and miscellaneous immigration filings.",
        "05_other_process",
    ),
    "urgent_processing": (
        "IX", "Urgent Processing",
        "Express processing tiers for time-sensitive filings.",
        "06_urgent",
    ),
}

SUBSECTION_TITLES = {
    "monthly_tax_basic": "V.1 Monthly Tax Report — without LKPM & Annual",
    "monthly_tax_bundled": "V.2 Monthly Tax Report — including LKPM + Annual",
    "annual_basic_packages": "V.3 Annual Basic Packages",
    "annual_standalone": "V.4 Annual & Compliance Stand-alone Fees",
}


@dataclass
class Section:
    roman: str
    title: str
    anchor: str
    intro: str
    hero_basename: str
    page_ref: str = ""
    page_num: str = ""
    services: list[dict] = field(default_factory=list)
    subsections: list[dict] = field(default_factory=list)
    hero_data_uri: str = ""


def _data_uri_png(path: Path) -> str:
    if not path.exists():
        raise AssetMissingError(f"Missing PNG asset: {path}")
    blob = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(blob).decode("ascii")


def _make_qr_data_uri(wa_link: str) -> str:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(wa_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1d273b", back_color="#fbfaf6")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _build_sections(data: dict, assets_dir: Path | None, embed_assets: bool) -> list[Section]:
    sections: list[Section] = []
    services_root = data["services"]
    for category_key, (roman, title, intro, hero_basename) in SECTION_META.items():
        if category_key not in services_root:
            continue
        sec = Section(
            roman=roman,
            title=title,
            anchor=category_key.replace("_", "-"),
            intro=intro,
            hero_basename=hero_basename,
        )
        if embed_assets and assets_dir is not None:
            sec.hero_data_uri = _data_uri_png(
                assets_dir / "heros" / f"{hero_basename}.png"
            )

        if category_key == "tax_accounting":
            for sub_key, sub_entries in services_root[category_key].items():
                sub = {
                    "title": SUBSECTION_TITLES.get(sub_key, sub_key),
                    "services": [],
                }
                for _name, svc in sub_entries.items():
                    sub["services"].append(_decorate_svc(svc, assets_dir, embed_assets))
                sec.subsections.append(sub)
        else:
            for _name, svc in services_root[category_key].items():
                sec.services.append(_decorate_svc(svc, assets_dir, embed_assets))

        sections.append(sec)
    return sections


def _decorate_svc(svc: dict, assets_dir: Path | None, embed_assets: bool) -> dict:
    out = dict(svc)
    if embed_assets and assets_dir is not None:
        icon_id = svc.get("icon_id", "")
        out["icon_data_uri"] = _data_uri_png(assets_dir / "icons" / f"{icon_id}.png")
    return out


def _validate_or_raise(data: dict) -> None:
    result = schema.validate(data)
    if not result.ok:
        raise SchemaError("; ".join(result.errors[:5]))


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(data: dict, assets_dir: Path, out_path: Path) -> None:
    _validate_or_raise(data)
    sections = _build_sections(data, assets_dir, embed_assets=True)
    contact = data["metadata"]["contact"]
    env = _jinja_env()
    template = env.get_template("pricelist.html.j2")
    rendered = template.render(
        sections=sections,
        contact=contact,
        logo_data_uri=_data_uri_png(assets_dir / "logo_circle.png"),
        qr_data_uri=_make_qr_data_uri(contact["wa_link"]),
        font_face_block="",
    )
    out_path.write_text(rendered, encoding="utf-8")


def render_markdown(data: dict, out_path: Path) -> None:
    _validate_or_raise(data)
    sections = _build_sections(data, assets_dir=None, embed_assets=False)
    env = _jinja_env()
    template = env.get_template("pricelist.md.j2")
    rendered = template.render(
        sections=sections,
        contact=data["metadata"]["contact"],
        version=data["version"],
        effective_date=data["effective_date"],
        last_updated=data["metadata"]["last_updated"],
    )
    out_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"),
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path("docs/pricing/assets/2026"),
    )
    parser.add_argument(
        "--out-html",
        type=Path,
        default=Path.home() / "Desktop" / "Bali_Zero_Price_List_2026.html",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path("docs/pricing/Bali_Zero_Price_List_2026.md"),
    )
    args = parser.parse_args()

    data = json.loads(args.json.read_text())
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_html.parent.mkdir(parents=True, exist_ok=True)

    print(f"  -> Markdown: {args.out_md}")
    render_markdown(data, args.out_md)
    print(f"  -> HTML:     {args.out_html}")
    render_html(data, args.assets_dir, args.out_html)
    print("Done.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
