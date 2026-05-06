# Bali Zero Price List 2026 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a 2026 Bali Zero price list as ONE versioned JSON source rendered into HTML + PDF + Markdown, with senior visual treatment (cover, hero photography, micro-icon set, batik ornaments) generated via `codex exec` + Image 2 (gpt-image-1).

**Architecture:** Single source `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json` → `scripts/pricelist_2026/generate.py` reads it → emits self-contained HTML (base64-embedded fonts + images) + PDF (Playwright headless print of the HTML) + Markdown (versioned in `docs/pricing/`). Image assets generated upfront in a separate, idempotent step via `scripts/pricelist_2026/generate_assets.py` which shells out to `codex exec`.

**Tech Stack:** Python 3.11+, Jinja2 (HTML template), Playwright (PDF render — already in `apps/backend-rag/requirements.txt:playwright>=1.57.0`), `qrcode` (Python, MIT, no API), `codex exec` CLI 0.128.0 (gpt-image-1 image gen via ChatGPT Plus OAuth — zero per-image cost).

**Spec:** `docs/superpowers/specs/2026-05-06-bali-zero-pricelist-2026-design.md` (commit `0060f6405`).

---

## File Structure

| Path                                                                | Responsibility                                                                                         | Status |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------ |
| `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json` | Single source of truth — all 80 services + metadata + contacts                                         | NEW    |
| `scripts/pricelist_2026/__init__.py`                                | Package marker                                                                                         | NEW    |
| `scripts/pricelist_2026/schema.py`                                  | Lightweight dataclasses + JSON validator (no Pydantic — stdlib only)                                   | NEW    |
| `scripts/pricelist_2026/generate_assets.py`                         | Idempotent CLI driver that calls `codex exec` for the 6 heros + ~25 icons; skips files already on disk | NEW    |
| `scripts/pricelist_2026/asset_briefs.py`                            | Brief strings (cover ornament, 6 hero prompts, ~25 icon prompts) — pure data, easy to edit             | NEW    |
| `scripts/pricelist_2026/generate.py`                                | Reads JSON + assets, renders HTML/PDF/MD via Jinja templates                                           | NEW    |
| `scripts/pricelist_2026/templates/pricelist.html.j2`                | Single-file HTML template (Jinja2)                                                                     | NEW    |
| `scripts/pricelist_2026/templates/pricelist.md.j2`                  | Markdown template                                                                                      | NEW    |
| `scripts/pricelist_2026/tests/test_schema.py`                       | Schema validation tests                                                                                | NEW    |
| `scripts/pricelist_2026/tests/test_generate.py`                     | Generator output tests                                                                                 | NEW    |
| `scripts/pricelist_2026/tests/fixtures/minimal_prices.json`         | 2-service fixture for fast tests                                                                       | NEW    |
| `docs/pricing/Bali_Zero_Price_List_2026.md`                         | Generated Markdown (committed in repo)                                                                 | NEW    |
| `docs/pricing/assets/2026/heros/*.png`                              | 6 hero images (committed)                                                                              | NEW    |
| `docs/pricing/assets/2026/icons/*.png`                              | ~25 micro-icons (committed)                                                                            | NEW    |
| `docs/pricing/assets/2026/logo_circle.png`                          | Copy of `~/Desktop/balizero_logo_circle.png` (committed for reproducibility)                           | NEW    |
| `~/Desktop/Bali_Zero_Price_List_2026.html`                          | Generated HTML deliverable (NOT committed)                                                             | OUTPUT |
| `~/Desktop/Bali_Zero_Price_List_2026.pdf`                           | Generated PDF deliverable (NOT committed)                                                              | OUTPUT |
| `~/Desktop/Bali_Zero_Price_List_2026_assets/`                       | Working dir for codex-generated PNGs before curation (NOT committed)                                   | OUTPUT |
| `.gitignore`                                                        | Append patterns for outputs above                                                                      | MODIFY |

**Why this layout:** the package structure (`scripts/pricelist_2026/`) keeps generator + templates + tests + briefs co-located. Existing patterns in this repo (e.g., `scripts/wr2_image_generator.py`) use flat `scripts/` files for one-shot helpers; for a multi-file deliverable a package is cleaner and lets us run `pytest scripts/pricelist_2026/tests/` cleanly.

**Why NOT update the backend RAG `PricingTool` here:** explicitly out of scope per spec §2 — the production chatbot keeps reading `_2025.json` until owner approves the swap. This plan ships content + visual deliverable, no production code change.

---

## Task 1: Author the 2026 JSON source

**Files:**

- Create: `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json`

This is content authoring, not code. Use 2025 JSON as starting point + tax dpt input + spec §8 conflict resolutions. Each service entry follows the schema in spec §4.

- [ ] **Step 1: Read the existing 2025 JSON for the entries we keep verbatim**

Run: `cat apps/backend-rag/backend/data/bali_zero_official_prices_2025.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(list(d['services'].keys()))"`

Expected output: `['single_entry_visas', 'visa_extensions', 'multiple_entry_visas', 'kitas_permits', 'kitap_permits', 'company_services', 'other_process', 'urgent_services']`

- [ ] **Step 2: Create the new JSON file with full content**

Write `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json` with this top-level shape:

```json
{
  "version": "2026.1",
  "effective_date": "2026-01-01",
  "metadata": {
    "currency": "IDR",
    "contact": {
      "email": "zero@balizero.com",
      "whatsapp": "+62 821 31 07 363",
      "wa_link": "https://wa.me/628213107363",
      "location": "Kerobokan, Bali, Indonesia",
      "website": "balizero.com"
    },
    "last_updated": "2026-05-06"
  },
  "services": {
    "single_entry_visas": { ... 6 entries ... },
    "visa_extensions": { ... 1 entry ... },
    "multiple_entry_visas": { ... 5 entries ... },
    "kitas_permits": { ... ~25 entries ... },
    "kitap_permits": { ... 5 entries; Investor=55M, Dependent=33M, NO ACC ... },
    "tax_accounting": {
      "monthly_tax_basic": { 4 tier entries },
      "monthly_tax_bundled": { 4 tier entries },
      "annual_basic_packages": { A, B, C, D, Zero Company },
      "annual_standalone": { LKPM yearly, Annual Tax Co., Annual Tax Personal, Personal additional }
    },
    "company_services": { 3 entries; Akta Perubahan unified ONE row },
    "consultant_services": { 7 entries: PMA close, NPWPD, BPJS Employee, BPJS Insurance, NPWP Personal+Coretax, Update Data, EFIN },
    "other_process": { ~21 entries copied verbatim from 2025 },
    "urgent_processing": { 1/2/3 hari }
  }
}
```

Each leaf entry (use this exact shape):

```json
{
  "name": "Working KITAS (Altus / Onshore)",
  "price": "36.000.000 IDR",
  "tier_range": null,
  "duration": "",
  "validity": "1 year",
  "notes": "",
  "description_en": "Standard work permit KITAS sponsored by Indonesian employer. Onshore process via Altus, suited to candidates already in Indonesia.",
  "icon_id": "kitas-working"
}
```

For TIER entries (tax monthly), `price` is the empty string and `tier_range` is the array:

```json
{
  "name": "Monthly Tax Report — 0 to 50 transactions (without LKPM & Annual)",
  "price": "",
  "tier_range": ["1.800.000 IDR", "2.000.000 IDR"],
  "duration": "",
  "validity": "monthly",
  "notes": "Bank + Cash transactions combined. LKPM and Annual Tax NOT included.",
  "description_en": "Monthly bookkeeping and tax filing for companies with low transaction volume. See section VI.4 for LKPM and Annual Tax stand-alone fees.",
  "icon_id": "tax-monthly"
}
```

Description text for the ~80 entries: write 1-2 sentences each, ENGLISH ONLY, factual, no marketing fluff. Source for descriptions:

- Visa entries: use `data/kb_sources/visa_imigrasi_list.txt` and `apps/backend-rag/backend/prompts/zantara_core.py` for accurate visa-type descriptions if available; otherwise concise standard definitions ("Tourist visa, single entry, valid 60 days. Cannot be used for work or business activities.")
- KITAS/KITAP: use existing JSON `notes` field where present + standard immigration definitions
- Tax: use the verbatim text the user provided in the brainstorming session (paraphrased into 1-2 sentence descriptions)
- Company / Consultant / Other: standard one-line definitions

Conflict resolutions (re-confirm against spec §8):

- `kitap_permits["Investor KITAP + MERP"].price` = `"55.000.000 IDR"`, no `ACC` text in `notes`
- `kitap_permits["Dependent KITAP + MERP"].price` = `"33.000.000 IDR"`, no `ACC` text in `notes`
- `company_services` has ONE entry "Akta Perubahan (Revision Company)" with `price: "Depend (Contact for quote)"` — drop the duplicate `Revision Company` entry that exists in 2025 JSON

Tax & Accounting reference (from user's 2026-05-06 message):

```
monthly_tax_basic (without LKPM/Annual):
  0-50 tx       → 1.8 - 2.0 mil/month
  50-100 tx     → 2.5 - 3.0 mil/month
  100-200 tx    → 3.5 - 4.5 mil/month
  >200 tx       → 5.0 mil/month (must do monthly OR get monthly fee for 1 year)

monthly_tax_bundled (including LKPM + Annual):
  0-50 tx       → 2.5 mil/month
  50-100 tx     → 3.5 mil/month
  100-200 tx    → 4.5 mil/month
  >200 tx       → 6.5 mil/month

annual_basic_packages:
  Package A     → ≤100 tx/year, 6 mil   — Income Tax only + Yearly Financial Report
  Package B     → 100-200 tx/year, 9 mil — Income Tax only + Yearly Financial Report
  Package C     → ≤100 tx/year, 12 mil  — Income Tax + (PPH 21 OR PPH Sewa, choose 1) + Yearly Financial Report
  Package D     → 100-200 tx/year, 15 mil — Income Tax + (PPH 21 OR PPH Sewa, choose 1) + Yearly Financial Report
  Annual Company ZERO → 3 mil — No transactions in/out, just Yearly Financial Report

annual_standalone:
  LKPM yearly                 → 4.000.000 IDR
  Annual Tax Company          → 4.000.000 IDR
  Annual Tax Personal         → 1.000.000 IDR
  Annual Tax Personal (each additional) → 1.500.000 IDR

consultant_services:
  Close PMA company           → 6.000.000 - 7.500.000 IDR (process max 1 year)
  NPWPD registration          → 2.500.000 IDR (per location)
  BPJS Employee (Tenaga Kerja) → 2.500.000 IDR
  BPJS Insurance (Kesehatan)  → 2.500.000 IDR
  NPWP Personal + Coretax activation → 1.000.000 IDR (per person)
  Update data (email/phone) or Coretax activation → 1.000.000 IDR
  EFIN application            → 1.000.000 IDR
```

Set `icon_id` for every service using kebab-case slugs that we'll map 1:1 to icon PNGs in Task 4 (e.g., `visa-c1`, `kitas-working`, `tax-monthly`, `company-pma`, `consultant-bpjs`, `other-passport`, `urgent-1day`). When two services would share the same visual concept (e.g., `kitas-working` for both Altus and Offshore variants), reuse the same `icon_id` — we generate ~25 unique icons, not one per service.

- [ ] **Step 3: Validate the JSON parses + count entries**

Run:

```bash
python3 -c "
import json
d = json.load(open('apps/backend-rag/backend/data/bali_zero_official_prices_2026.json'))
total = sum(len(v) for v in d['services'].values() if isinstance(v, dict) and not any(isinstance(x, dict) and 'name' not in x for x in v.values()))
# tax_accounting is nested 2 levels — count its grandchildren
tax_count = sum(len(sub) for sub in d['services']['tax_accounting'].values())
flat_total = sum(len(v) for k,v in d['services'].items() if k != 'tax_accounting')
print(f'Total services: {flat_total + tax_count}')
print(f'Categories: {list(d[\"services\"].keys())}')
print(f'Contact: {d[\"metadata\"][\"contact\"][\"whatsapp\"]}')
"
```

Expected: `Total services: 80` (give or take 2 — the count is approximate), all 10 categories listed, WhatsApp `+62 821 31 07 363`.

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/data/bali_zero_official_prices_2026.json
git commit -m "data(pricing): add 2026 Bali Zero price list JSON source

Single source of truth for the 2026 price list — 80 services across 10
categories, contacts updated to zero@balizero.com / +62 821 31 07 363 /
Kerobokan, KITAP conflicts resolved (Investor 55M, Dependent 33M, no
ACC), Akta Perubahan unified, new Tax & Accounting + Consultant Services
sections added.

Production RAG PricingTool continues reading the 2025 JSON; this file is
only consumed by scripts/pricelist_2026/ until owner approves the swap.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Schema validator (TDD)

**Files:**

- Create: `scripts/pricelist_2026/__init__.py` (empty file)
- Create: `scripts/pricelist_2026/schema.py`
- Create: `scripts/pricelist_2026/tests/__init__.py` (empty)
- Create: `scripts/pricelist_2026/tests/test_schema.py`
- Create: `scripts/pricelist_2026/tests/fixtures/minimal_prices.json`

The validator catches drift before render time: missing required fields, both `price` and `tier_range` empty, contact mismatch, etc. Stdlib only.

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p scripts/pricelist_2026/tests/fixtures
touch scripts/pricelist_2026/__init__.py
touch scripts/pricelist_2026/tests/__init__.py
```

- [ ] **Step 2: Create the test fixture**

Write `scripts/pricelist_2026/tests/fixtures/minimal_prices.json`:

```json
{
  "version": "2026.1",
  "effective_date": "2026-01-01",
  "metadata": {
    "currency": "IDR",
    "contact": {
      "email": "zero@balizero.com",
      "whatsapp": "+62 821 31 07 363",
      "wa_link": "https://wa.me/628213107363",
      "location": "Kerobokan, Bali, Indonesia",
      "website": "balizero.com"
    },
    "last_updated": "2026-05-06"
  },
  "services": {
    "single_entry_visas": {
      "C1 Tourism": {
        "name": "C1 Tourism",
        "price": "2.300.000 IDR",
        "tier_range": null,
        "duration": "",
        "validity": "60 days",
        "notes": "",
        "description_en": "Tourist visa, single entry, valid 60 days.",
        "icon_id": "visa-tourism"
      }
    },
    "tax_accounting": {
      "monthly_tax_basic": {
        "Tier 0-50": {
          "name": "Monthly Tax Report — 0 to 50 transactions",
          "price": "",
          "tier_range": ["1.800.000 IDR", "2.000.000 IDR"],
          "duration": "",
          "validity": "monthly",
          "notes": "",
          "description_en": "Monthly bookkeeping for low volume.",
          "icon_id": "tax-monthly"
        }
      }
    }
  }
}
```

- [ ] **Step 3: Write the failing tests**

Write `scripts/pricelist_2026/tests/test_schema.py`:

```python
"""Tests for the 2026 price list JSON schema validator."""
import json
from pathlib import Path

import pytest

from scripts.pricelist_2026 import schema

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_prices.json"


def _load_fixture():
    return json.loads(FIXTURE.read_text())


def test_valid_fixture_passes():
    data = _load_fixture()
    result = schema.validate(data)
    assert result.ok, f"Expected valid fixture to pass, got errors: {result.errors}"


def test_missing_top_level_version_fails():
    data = _load_fixture()
    del data["version"]
    result = schema.validate(data)
    assert not result.ok
    assert any("version" in e for e in result.errors)


def test_contact_whatsapp_must_match_canonical():
    data = _load_fixture()
    data["metadata"]["contact"]["whatsapp"] = "+62 813 3805 1876"
    result = schema.validate(data)
    assert not result.ok
    assert any("whatsapp" in e for e in result.errors)


def test_service_with_neither_price_nor_tier_range_fails():
    data = _load_fixture()
    data["services"]["single_entry_visas"]["C1 Tourism"]["price"] = ""
    data["services"]["single_entry_visas"]["C1 Tourism"]["tier_range"] = None
    result = schema.validate(data)
    assert not result.ok
    assert any("must have price or tier_range" in e for e in result.errors)


def test_service_with_both_price_and_tier_range_fails():
    data = _load_fixture()
    svc = data["services"]["single_entry_visas"]["C1 Tourism"]
    svc["price"] = "2.300.000 IDR"
    svc["tier_range"] = ["1 IDR", "2 IDR"]
    result = schema.validate(data)
    assert not result.ok
    assert any("not both" in e for e in result.errors)


def test_service_missing_description_en_fails():
    data = _load_fixture()
    del data["services"]["single_entry_visas"]["C1 Tourism"]["description_en"]
    result = schema.validate(data)
    assert not result.ok
    assert any("description_en" in e for e in result.errors)


def test_service_missing_icon_id_fails():
    data = _load_fixture()
    del data["services"]["single_entry_visas"]["C1 Tourism"]["icon_id"]
    result = schema.validate(data)
    assert not result.ok
    assert any("icon_id" in e for e in result.errors)


def test_tier_range_must_be_two_strings():
    data = _load_fixture()
    data["services"]["tax_accounting"]["monthly_tax_basic"]["Tier 0-50"]["tier_range"] = ["only one"]
    result = schema.validate(data)
    assert not result.ok
    assert any("tier_range" in e for e in result.errors)


def test_real_2026_json_validates():
    """Sanity check: the actual file we ship must validate."""
    real = Path("apps/backend-rag/backend/data/bali_zero_official_prices_2026.json")
    if not real.exists():
        pytest.skip("real JSON not yet authored")
    data = json.loads(real.read_text())
    result = schema.validate(data)
    assert result.ok, f"Real 2026 JSON failed validation: {result.errors}"
```

- [ ] **Step 4: Run tests to verify they fail (no schema.py yet)**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m pytest scripts/pricelist_2026/tests/test_schema.py -v 2>&1 | tail -20`

Expected: ALL tests FAIL with `ModuleNotFoundError: No module named 'scripts.pricelist_2026.schema'`.

- [ ] **Step 5: Implement schema.py minimally to pass**

Write `scripts/pricelist_2026/schema.py`:

```python
"""JSON schema validator for the 2026 Bali Zero price list.

Stdlib only. Returns a `ValidationResult` with .ok and .errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANONICAL_CONTACT = {
    "email": "zero@balizero.com",
    "whatsapp": "+62 821 31 07 363",
    "wa_link": "https://wa.me/628213107363",
    "location": "Kerobokan, Bali, Indonesia",
    "website": "balizero.com",
}

REQUIRED_TOP_LEVEL = ["version", "effective_date", "metadata", "services"]
REQUIRED_METADATA = ["currency", "contact", "last_updated"]
REQUIRED_CONTACT = list(CANONICAL_CONTACT.keys())
REQUIRED_SERVICE_FIELDS = [
    "name", "price", "tier_range", "duration", "validity",
    "notes", "description_en", "icon_id",
]


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)


def validate(data: dict[str, Any]) -> ValidationResult:
    result = ValidationResult()

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            result.fail(f"top-level: missing '{key}'")

    metadata = data.get("metadata", {})
    for key in REQUIRED_METADATA:
        if key not in metadata:
            result.fail(f"metadata: missing '{key}'")

    contact = metadata.get("contact", {})
    for key, expected in CANONICAL_CONTACT.items():
        actual = contact.get(key)
        if actual is None:
            result.fail(f"metadata.contact: missing '{key}'")
        elif actual != expected:
            result.fail(
                f"metadata.contact.{key} mismatch: expected '{expected}', got '{actual}'"
            )

    services = data.get("services", {})
    for category, entries in services.items():
        # tax_accounting has ONE extra level of nesting (sub-blocks)
        if category == "tax_accounting":
            for subblock, subentries in entries.items():
                for name, svc in subentries.items():
                    _validate_service(result, f"{category}.{subblock}.{name}", svc)
        else:
            for name, svc in entries.items():
                _validate_service(result, f"{category}.{name}", svc)

    return result


def _validate_service(result: ValidationResult, path: str, svc: dict) -> None:
    for field_name in REQUIRED_SERVICE_FIELDS:
        if field_name not in svc:
            result.fail(f"{path}: missing field '{field_name}'")

    price = svc.get("price", "")
    tier = svc.get("tier_range")

    has_price = bool(price and price.strip())
    has_tier = tier is not None and isinstance(tier, list) and len(tier) == 2

    if not has_price and not has_tier:
        result.fail(f"{path}: must have price or tier_range")
    if has_price and has_tier:
        result.fail(f"{path}: must have price or tier_range, not both")

    if tier is not None:
        if not isinstance(tier, list) or len(tier) != 2:
            result.fail(f"{path}: tier_range must be a list of exactly 2 strings")
        elif not all(isinstance(x, str) for x in tier):
            result.fail(f"{path}: tier_range entries must be strings")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m pytest scripts/pricelist_2026/tests/test_schema.py -v 2>&1 | tail -20`

Expected: ALL 9 tests PASS (including `test_real_2026_json_validates` since Task 1 already created the real file).

If `test_real_2026_json_validates` fails: the real JSON has a violation — fix the JSON, not the test.

- [ ] **Step 7: Commit**

```bash
git add scripts/pricelist_2026/__init__.py scripts/pricelist_2026/schema.py scripts/pricelist_2026/tests/
git commit -m "feat(pricelist-2026): add JSON schema validator

Stdlib-only validator for the 2026 price list JSON. Catches missing
required fields, contact drift (e.g. wrong WhatsApp number), services
with neither price nor tier_range, malformed tier_range arrays. 9 tests
including a smoke test against the real apps/backend-rag/backend/data/
bali_zero_official_prices_2026.json.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Asset briefs module

**Files:**

- Create: `scripts/pricelist_2026/asset_briefs.py`

Pure data — separates the brief strings from the generation logic so brand reviewers can edit prompts without touching the script. Each brief includes the constraints (palette hex, "no text, no logos, slow magazine photography aesthetic") inline.

- [ ] **Step 1: Write asset_briefs.py**

Write `scripts/pricelist_2026/asset_briefs.py`:

```python
"""Briefs for codex exec → Image 2 (gpt-image-1) generation.

Pure data, no I/O. Each entry is (output_basename, brief_text, size).
"""
from __future__ import annotations

# Shared style constraints injected into every brief
_STYLE_HEROS = (
    "Cinematic editorial still-life. Slow-magazine photography aesthetic, "
    "low-key chiaroscuro, shallow depth of field. Palette anchored on deep "
    "navy #1d273b, copper #d4845a, warm gold #c9a96e on cream paper #fbfaf6 "
    "highlights. NO TEXT, NO LOGOS, NO WATERMARKS, NO READABLE WRITING on "
    "any surface. 16:9 landscape composition."
)

_STYLE_ICONS = (
    "Single line-art icon, 2px stroke weight, copper color #d4845a only, "
    "transparent background, centered in 1024×1024 frame, minimalist "
    "editorial style, no fill, no shadows, single subject only. NO TEXT."
)

# 6 hero photographs, one per macro-section
HERO_BRIEFS: list[tuple[str, str, str]] = [
    (
        "01_visas",
        f"{_STYLE_HEROS} Subject: open passport with embossed Indonesian "
        "visa stamp resting on travertine marble surface, soft dawn light "
        "from upper left, brass key in soft focus background.",
        "1792x1024",
    ),
    (
        "02_kitas_kitap",
        f"{_STYLE_HEROS} Subject: tilt-shift Jakarta skyline at golden hour "
        "bokeh in background, foreground crisp printed Letter of Approval "
        "document with embossed seal partly visible (no readable text on "
        "document).",
        "1792x1024",
    ),
    (
        "03_tax",
        f"{_STYLE_HEROS} Subject: macro detail of a vintage fountain pen "
        "poised over a blank ledger page, Indonesian rupiah banknotes "
        "blurred at edge, copper highlights on metal pen body.",
        "1792x1024",
    ),
    (
        "04_company",
        f"{_STYLE_HEROS} Subject: notarial seal pressed into deep red "
        "sealing wax on cream Akta document, hand of notary partly visible "
        "holding brass seal (no readable text on document).",
        "1792x1024",
    ),
    (
        "05_other_process",
        f"{_STYLE_HEROS} Subject: top-down flat-lay of identity documents, "
        "immigration stamps, brass paperclips on cream linen surface, soft "
        "diffused window light (no readable text on documents).",
        "1792x1024",
    ),
    (
        "06_urgent",
        f"{_STYLE_HEROS} Subject: crystal hourglass with copper sand "
        "mid-flow, deep navy background, single beam of light from upper "
        "right, dramatic shadow.",
        "1792x1024",
    ),
]

# Micro-icons keyed by icon_id used in the JSON
ICON_BRIEFS: dict[str, str] = {
    "visa-tourism":      f"{_STYLE_ICONS} Subject: passport with palm tree.",
    "visa-business":     f"{_STYLE_ICONS} Subject: briefcase with passport corner.",
    "visa-art":          f"{_STYLE_ICONS} Subject: musical note inside circle.",
    "visa-internship":   f"{_STYLE_ICONS} Subject: graduation cap.",
    "visa-worktrial":    f"{_STYLE_ICONS} Subject: clipboard with checkmark.",
    "visa-extension":    f"{_STYLE_ICONS} Subject: calendar page with curved arrow.",
    "visa-multiple":     f"{_STYLE_ICONS} Subject: passport with two arrows in opposite directions.",
    "visa-investigation":f"{_STYLE_ICONS} Subject: magnifying glass over briefcase.",
    "kitas-working":     f"{_STYLE_ICONS} Subject: hard hat over document.",
    "kitas-investor":    f"{_STYLE_ICONS} Subject: rising bar chart with coin.",
    "kitas-freelance":   f"{_STYLE_ICONS} Subject: laptop with palm leaf.",
    "kitas-remote":      f"{_STYLE_ICONS} Subject: laptop with wifi waves.",
    "kitas-spouse":      f"{_STYLE_ICONS} Subject: two interlocking rings.",
    "kitas-dependent":   f"{_STYLE_ICONS} Subject: silhouettes of family of three.",
    "kitas-retirement":  f"{_STYLE_ICONS} Subject: lounge chair under palm tree.",
    "kitap-permanent":   f"{_STYLE_ICONS} Subject: house with key.",
    "kitap-merp":        f"{_STYLE_ICONS} Subject: airplane with re-entry arrows.",
    "tax-monthly":       f"{_STYLE_ICONS} Subject: calendar page with currency symbol.",
    "tax-annual":        f"{_STYLE_ICONS} Subject: ledger book with bookmark ribbon.",
    "tax-lkpm":          f"{_STYLE_ICONS} Subject: bar chart inside government building outline.",
    "tax-personal":      f"{_STYLE_ICONS} Subject: single person silhouette with document.",
    "company-pma":       f"{_STYLE_ICONS} Subject: Indonesian temple gate (candi bentar) outline.",
    "company-virtual":   f"{_STYLE_ICONS} Subject: cloud with building inside.",
    "company-akta":      f"{_STYLE_ICONS} Subject: scroll with notary seal.",
    "company-close":     f"{_STYLE_ICONS} Subject: building with X-mark over door.",
    "consultant-npwpd":  f"{_STYLE_ICONS} Subject: city map pin over document.",
    "consultant-bpjs-tk":f"{_STYLE_ICONS} Subject: hand over worker silhouette.",
    "consultant-bpjs-kes":f"{_STYLE_ICONS} Subject: medical cross inside shield.",
    "consultant-npwp":   f"{_STYLE_ICONS} Subject: ID card with hash symbol.",
    "consultant-update": f"{_STYLE_ICONS} Subject: pencil over document.",
    "consultant-efin":   f"{_STYLE_ICONS} Subject: digital fingerprint.",
    "other-passport":    f"{_STYLE_ICONS} Subject: passport icon.",
    "other-sktt":        f"{_STYLE_ICONS} Subject: ID card with house outline.",
    "other-skck":        f"{_STYLE_ICONS} Subject: shield with checkmark.",
    "other-domicile":    f"{_STYLE_ICONS} Subject: house with document.",
    "other-born":        f"{_STYLE_ICONS} Subject: stork.",
    "other-epo":         f"{_STYLE_ICONS} Subject: door with single right arrow exiting.",
    "other-erp":         f"{_STYLE_ICONS} Subject: door with two arrows (in and out).",
    "other-mutation":    f"{_STYLE_ICONS} Subject: passport with curved transfer arrow.",
    "other-cancel":      f"{_STYLE_ICONS} Subject: document with diagonal X-mark.",
    "other-molina":      f"{_STYLE_ICONS} Subject: refresh circular arrow.",
    "other-boarding":    f"{_STYLE_ICONS} Subject: airplane boarding pass.",
    "urgent-1day":       f"{_STYLE_ICONS} Subject: stopwatch showing 1.",
    "urgent-2day":       f"{_STYLE_ICONS} Subject: stopwatch showing 2.",
    "urgent-3day":       f"{_STYLE_ICONS} Subject: stopwatch showing 3.",
}
```

- [ ] **Step 2: Verify the module imports cleanly + count entries**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && python3 -c "
from scripts.pricelist_2026 import asset_briefs as ab
print(f'Heros: {len(ab.HERO_BRIEFS)}')
print(f'Icons: {len(ab.ICON_BRIEFS)}')
print(f'First hero brief len: {len(ab.HERO_BRIEFS[0][1])} chars')
"
```

Expected: `Heros: 6`, `Icons: 44` (one per icon_id used in the JSON — final count depends on how many distinct icon_ids you set in Task 1, adjust briefs to match).

If the count doesn't match `set(svc["icon_id"] for svc in <all entries>)`, add the missing brief entries. The generator in Task 5 will fail loudly if any `icon_id` is missing a brief.

- [ ] **Step 3: Commit**

```bash
git add scripts/pricelist_2026/asset_briefs.py
git commit -m "feat(pricelist-2026): add Image 2 briefs for hero + icon assets

6 cinematic hero briefs (one per macro-section) + ~44 line-art icon
briefs keyed by icon_id. All include explicit no-text/no-logo/palette
constraints to keep gpt-image-1 outputs on-brand.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Asset generation driver (codex exec wrapper)

**Files:**

- Create: `scripts/pricelist_2026/generate_assets.py`

Idempotent CLI: skips assets already present on disk, only generates missing ones. Uses `codex exec` non-interactively with explicit instructions to call gpt-image-1 and save to a known path.

- [ ] **Step 1: Verify codex exec is available**

Run: `which codex && codex --version`
Expected: `/opt/homebrew/bin/codex` and version `0.128.0` or higher.

If not found: STOP. Ask owner to install Codex CLI before continuing. Do NOT introduce a fallback that would call a paid Anthropic API.

- [ ] **Step 2: Write generate_assets.py**

Write `scripts/pricelist_2026/generate_assets.py`:

```python
"""Driver: generates hero + icon PNGs via `codex exec` → Image 2 (gpt-image-1).

Idempotent: skips files already present in the output dir. Use
--regenerate <basename> to force re-gen of a specific asset.
"""
from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.pricelist_2026 import asset_briefs

DEFAULT_OUT = Path.home() / "Desktop" / "Bali_Zero_Price_List_2026_assets"


def _check_codex() -> None:
    if shutil.which("codex") is None:
        sys.exit(
            "ERROR: `codex` CLI not found in PATH. Install Codex CLI before "
            "running this script. Do NOT introduce paid-API fallbacks."
        )


def _codex_image_prompt(brief: str, out_path: Path, size: str) -> str:
    """Wrap the brief in instructions Codex will follow non-interactively."""
    return (
        f"Generate ONE image using OpenAI gpt-image-1 (Image 2). "
        f"Brief: {brief} "
        f"Size: {size}. "
        f"Save the resulting PNG file at exactly this absolute path: "
        f"{out_path}. "
        f"Do not output anything else after generation. Do not explain. "
        f"Do not generate variants. Do not ask for confirmation."
    )


def _generate_one(brief: str, out_path: Path, size: str, *, dry_run: bool) -> bool:
    """Returns True if generated, False if skipped."""
    if out_path.exists():
        print(f"  ✓ skip (exists): {out_path.name}")
        return False
    prompt = _codex_image_prompt(brief, out_path, size)
    if dry_run:
        print(f"  [dry-run] would gen: {out_path.name}")
        print(f"           prompt: {prompt[:120]}...")
        return True
    print(f"  ⏳ generating: {out_path.name} ({size})")
    cmd = ["codex", "exec", "--full-auto", prompt]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired:
        print(f"  ✗ TIMEOUT: {out_path.name}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(
            f"  ✗ codex exec failed (exit {result.returncode}): "
            f"{result.stderr[:300]}",
            file=sys.stderr,
        )
        return False
    if not out_path.exists():
        print(
            f"  ✗ codex completed but file not at {out_path}", file=sys.stderr
        )
        print(f"     stdout: {result.stdout[:300]}", file=sys.stderr)
        return False
    print(f"  ✓ generated: {out_path.name} ({out_path.stat().st_size} bytes)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--only", choices=["heros", "icons", "all"], default="all"
    )
    parser.add_argument(
        "--regenerate", action="append", default=[],
        help="Force re-gen of basename (without .png). Repeatable."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _check_codex()

    heros_dir = args.out_dir / "heros"
    icons_dir = args.out_dir / "icons"
    heros_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Force re-gen by deleting the existing PNGs first
    for basename in args.regenerate:
        for d in (heros_dir, icons_dir):
            target = d / f"{basename}.png"
            if target.exists():
                print(f"  ✗ deleting for re-gen: {target}")
                target.unlink()

    n_gen = 0
    n_skip = 0

    if args.only in ("heros", "all"):
        print(f"=== Heros ({len(asset_briefs.HERO_BRIEFS)}) ===")
        for basename, brief, size in asset_briefs.HERO_BRIEFS:
            out = heros_dir / f"{basename}.png"
            if _generate_one(brief, out, size, dry_run=args.dry_run):
                n_gen += 1
            else:
                if out.exists():
                    n_skip += 1

    if args.only in ("icons", "all"):
        print(f"=== Icons ({len(asset_briefs.ICON_BRIEFS)}) ===")
        for icon_id, brief in sorted(asset_briefs.ICON_BRIEFS.items()):
            out = icons_dir / f"{icon_id}.png"
            if _generate_one(brief, out, "1024x1024", dry_run=args.dry_run):
                n_gen += 1
            else:
                if out.exists():
                    n_skip += 1

    print(f"\nDone. Generated: {n_gen}, Skipped (already exist): {n_skip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Dry-run to verify the driver wires up correctly**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m scripts.pricelist_2026.generate_assets --dry-run`

Expected output: lists 6 heros + ~44 icons that "would gen", no actual codex calls.

If `ModuleNotFoundError`: ensure `__init__.py` files exist (Task 2 step 1).

- [ ] **Step 4: Real run for ONE hero as a smoke test**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m scripts.pricelist_2026.generate_assets --only heros --regenerate 01_visas`

Expected: `codex exec` runs, outputs a PNG at `~/Desktop/Bali_Zero_Price_List_2026_assets/heros/01_visas.png`. Open it manually to verify it matches the brief (cinematic, no text, on-palette).

If output is off-brand or contains text: edit `asset_briefs.py:HERO_BRIEFS[0]`, re-run with `--regenerate 01_visas`. Iterate up to 3 times. If still bad, document in spec §13 Open Items and continue with manual sourcing later — don't block the plan.

- [ ] **Step 5: Full run for all assets**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m scripts.pricelist_2026.generate_assets`

Expected: ~50 codex exec calls, ~10-30 minutes wallclock total. Check output dir size: `du -sh ~/Desktop/Bali_Zero_Price_List_2026_assets/`.

- [ ] **Step 6: Curate — visually review every output**

Run: `open ~/Desktop/Bali_Zero_Price_List_2026_assets/heros/ && open ~/Desktop/Bali_Zero_Price_List_2026_assets/icons/`

For each hero or icon that is off-brand, contains text, or doesn't match the brief: regenerate via `--regenerate <basename>`. Continue until all assets are acceptable.

- [ ] **Step 7: Copy curated assets into the repo**

```bash
mkdir -p docs/pricing/assets/2026/heros docs/pricing/assets/2026/icons
cp ~/Desktop/Bali_Zero_Price_List_2026_assets/heros/*.png docs/pricing/assets/2026/heros/
cp ~/Desktop/Bali_Zero_Price_List_2026_assets/icons/*.png docs/pricing/assets/2026/icons/
cp ~/Desktop/balizero_logo_circle.png docs/pricing/assets/2026/logo_circle.png
ls docs/pricing/assets/2026/heros/ | wc -l
ls docs/pricing/assets/2026/icons/ | wc -l
```

Expected: `6` heros, ~44 icons.

- [ ] **Step 8: Commit assets + driver**

```bash
git add scripts/pricelist_2026/generate_assets.py docs/pricing/assets/2026/
git commit -m "feat(pricelist-2026): generate hero + icon assets via codex exec

Idempotent driver that calls codex exec → Image 2 (gpt-image-1) for the
6 cinematic heros + ~44 line-art icons. Skips existing files so reruns
are safe; --regenerate <basename> forces re-gen. Curated PNGs committed
under docs/pricing/assets/2026/ so the renderer is reproducible without
re-spending image-gen quota.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: HTML template (Jinja2)

**Files:**

- Create: `scripts/pricelist_2026/templates/pricelist.html.j2`

Single-file HTML template. All CSS inline. Loops over the JSON sections producing cover, ToC, section dividers (each with hero), service rows (each with icon), closing page (with QR code). Image src values use `data:image/png;base64,...` placeholders that the generator (Task 6) fills.

- [ ] **Step 1: Create templates dir + write the template**

```bash
mkdir -p scripts/pricelist_2026/templates
```

Write `scripts/pricelist_2026/templates/pricelist.html.j2` (this is the full template — engineers reading should not have to reconstruct CSS):

```jinja
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bali Zero — Price List 2026</title>
<style>
  /* Inlined fonts (base64 woff2 set by generator) */
  {{ font_face_block | safe }}

  :root {
    --paper: #fbfaf6;
    --navy: #1d273b;
    --navy-elevated: #243047;
    --copper: #d4845a;
    --gold: #c9a96e;
    --cool-blue: #5e7fb5;
    --cream: #edeae4;
    --muted: #8c8884;
    --subtle: #575350;
  }

  @page {
    size: A4 portrait;
    margin: 0;
  }

  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--paper); color: var(--navy); }
  body {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.5;
  }

  .page {
    width: 210mm;
    min-height: 297mm;
    padding: 80px 60px;
    position: relative;
    page-break-after: always;
    background: var(--paper);
  }
  .page.dark { background: var(--navy); color: var(--cream); }

  /* COVER */
  .cover {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    background: var(--navy);
    color: var(--cream);
    overflow: hidden;
  }
  .cover .batik {
    position: absolute; inset: 0; opacity: 0.08;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40'><path d='M0 20 L20 0 L40 20 L20 40 Z' fill='none' stroke='%23c9a96e' stroke-width='0.6'/></svg>");
    background-size: 40px 40px;
  }
  .cover img.logo { width: 200px; height: 200px; margin-bottom: 40px; z-index: 1; }
  .cover h1 {
    font-family: 'Cormorant Garamond', serif; font-weight: 600;
    font-size: 96px; letter-spacing: 0.04em; margin: 0; z-index: 1;
  }
  .cover .hairline {
    width: 80px; height: 2px; background: var(--copper);
    margin: 24px 0; z-index: 1;
  }
  .cover .subtitle {
    font-family: 'League Spartan', sans-serif; font-weight: 500;
    font-size: 28px; color: var(--gold); letter-spacing: 0.18em;
    text-transform: uppercase; z-index: 1;
  }
  .cover .tags {
    margin-top: 80px; color: var(--copper); letter-spacing: 0.1em; z-index: 1;
  }
  .cover .footer {
    position: absolute; bottom: 60px; font-size: 11px; color: var(--muted);
    z-index: 1;
  }

  /* RUNNING HEADER (page 2+) */
  .header {
    position: absolute; top: 30px; left: 60px; right: 60px;
    display: flex; justify-content: space-between; font-size: 10px;
    color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase;
    border-bottom: 0.5px solid var(--gold); padding-bottom: 8px;
  }

  /* PAGE NUMBER */
  .page-num {
    position: absolute; bottom: 30px; right: 60px;
    font-family: 'Cormorant Garamond', serif; font-size: 11px;
    color: var(--subtle);
  }

  /* TOC */
  .toc h1 {
    font-family: 'Cormorant Garamond', serif; font-size: 48px;
    font-weight: 600; margin: 0 0 40px;
  }
  .toc ul { list-style: none; padding: 0; margin: 0; }
  .toc li {
    display: flex; align-items: baseline; padding: 12px 0;
    border-bottom: 0.5px dotted var(--muted);
  }
  .toc .roman {
    font-family: 'Cormorant Garamond', serif; font-style: italic;
    color: var(--copper); width: 60px;
  }
  .toc .name { flex: 1; font-size: 16px; }
  .toc .pageref { color: var(--subtle); }

  /* SECTION DIVIDER */
  .divider {
    background: var(--navy); color: var(--cream);
    padding: 60px; min-height: 200px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: center;
    page-break-after: avoid;
  }
  .divider .left .roman {
    font-family: 'Cormorant Garamond', serif; font-style: italic;
    color: var(--copper); font-size: 28px; margin-bottom: 8px;
  }
  .divider .left h2 {
    font-family: 'Cormorant Garamond', serif; font-size: 48px;
    font-weight: 600; margin: 0 0 12px;
  }
  .divider .left .intro { color: var(--muted); font-size: 14px; }
  .divider .hero {
    width: 100%; aspect-ratio: 16 / 9; border-radius: 4px;
    object-fit: cover;
  }

  /* SUB-SECTION (tax_accounting) */
  .subsection-title {
    font-family: 'League Spartan', sans-serif; font-weight: 500;
    font-size: 18px; color: var(--copper); letter-spacing: 0.06em;
    text-transform: uppercase; margin: 32px 0 16px;
    border-bottom: 0.5px solid var(--gold); padding-bottom: 8px;
  }

  /* SERVICE ROW */
  .service {
    display: grid; grid-template-columns: 32px 1fr 180px;
    gap: 16px; padding: 18px 0 18px 18px;
    border-left: 3px solid var(--copper);
    margin-bottom: 12px;
    page-break-inside: avoid;
  }
  .service .icon { width: 28px; height: 28px; opacity: 0.85; }
  .service .name {
    font-weight: 600; font-size: 15px; color: var(--navy);
  }
  .service .desc {
    font-style: italic; font-size: 12px; color: var(--muted);
    margin-top: 4px;
  }
  .service .meta {
    font-size: 11px; color: var(--subtle); margin-top: 6px;
  }
  .service .price {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 600; font-size: 16px; color: var(--copper);
  }
  .service .tier { font-size: 14px; }
  .service .notes { font-size: 11px; color: var(--muted); margin-top: 4px; font-style: italic; }

  /* CLOSING */
  .closing {
    background: var(--navy); color: var(--cream);
    display: flex; flex-direction: column; justify-content: center;
    align-items: center; text-align: center;
  }
  .closing h2 {
    font-family: 'Cormorant Garamond', serif; font-size: 56px;
    margin: 0 0 32px; color: var(--gold);
  }
  .closing .qr {
    width: 200px; height: 200px; background: var(--cream);
    padding: 16px; border-radius: 4px; margin: 24px 0;
  }
  .closing .contact { font-size: 16px; line-height: 2; }
  .closing .contact a { color: var(--copper); text-decoration: none; }
</style>
</head>
<body>

<!-- COVER -->
<section class="page cover">
  <div class="batik"></div>
  <img class="logo" src="{{ logo_data_uri }}" alt="">
  <h1>BALI ZERO</h1>
  <div class="hairline"></div>
  <div class="subtitle">Price List 2026</div>
  <div class="tags">Visa · KITAS · Company<br>Tax · Accounting · Other</div>
  <div class="footer">{{ contact.website }} · {{ contact.location }}</div>
</section>

<!-- TOC -->
<section class="page toc">
  <div class="header"><span>Bali Zero · Price List 2026</span><span>Contents</span></div>
  <h1>Contents</h1>
  <ul>
    {% for section in sections %}
    <li>
      <span class="roman">{{ section.roman }}</span>
      <span class="name">{{ section.title }}</span>
      <span class="pageref">{{ section.page_ref }}</span>
    </li>
    {% endfor %}
  </ul>
  <div class="page-num">02</div>
</section>

<!-- SECTIONS -->
{% for section in sections %}
<section class="page divider">
  <div class="left">
    <div class="roman">{{ section.roman }}.</div>
    <h2>{{ section.title }}</h2>
    <div class="intro">{{ section.intro }}</div>
  </div>
  <img class="hero" src="{{ section.hero_data_uri }}" alt="">
</section>

<section class="page">
  <div class="header"><span>Bali Zero · Price List 2026</span><span>{{ section.title }}</span></div>

  {% if section.subsections %}
    {% for sub in section.subsections %}
      <div class="subsection-title">{{ sub.title }}</div>
      {% for svc in sub.services %}
        {% include 'service_row.html.j2' %}
      {% endfor %}
    {% endfor %}
  {% else %}
    {% for svc in section.services %}
      {% include 'service_row.html.j2' %}
    {% endfor %}
  {% endif %}

  <div class="page-num">{{ section.page_num }}</div>
</section>
{% endfor %}

<!-- CLOSING -->
<section class="page closing">
  <h2>Get in touch</h2>
  <img class="qr" src="{{ qr_data_uri }}" alt="WhatsApp QR">
  <div class="contact">
    <div><a href="https://{{ contact.website }}">{{ contact.website }}</a></div>
    <div>{{ contact.email }}</div>
    <div>{{ contact.whatsapp }}</div>
    <div>{{ contact.location }}</div>
  </div>
</section>

</body>
</html>
```

- [ ] **Step 2: Create the included service-row partial**

Write `scripts/pricelist_2026/templates/service_row.html.j2`:

```jinja
<div class="service">
  <img class="icon" src="{{ svc.icon_data_uri }}" alt="">
  <div>
    <div class="name">{{ svc.name }}</div>
    <div class="desc">{{ svc.description_en }}</div>
    {% if svc.validity or svc.duration %}
    <div class="meta">
      {% if svc.validity %}Validity: {{ svc.validity }}{% endif %}
      {% if svc.validity and svc.duration %} · {% endif %}
      {% if svc.duration %}Duration: {{ svc.duration }}{% endif %}
    </div>
    {% endif %}
    {% if svc.notes %}<div class="notes">{{ svc.notes }}</div>{% endif %}
  </div>
  <div class="price">
    {% if svc.tier_range %}
      <span class="tier">{{ svc.tier_range[0] }}<br>– {{ svc.tier_range[1] }}</span>
    {% else %}
      {{ svc.price }}
    {% endif %}
  </div>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add scripts/pricelist_2026/templates/
git commit -m "feat(pricelist-2026): add HTML/Jinja templates

Single-file HTML template with inline CSS, A4 portrait page model,
cover/ToC/section-divider/service-row/closing structure on the Bali Zero
brand palette (navy + copper + gold + cream). Service-row partial
handles both single price and tier_range. All images consumed via
data: URIs (filled by generator in Task 6).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Markdown template (Jinja2)

**Files:**

- Create: `scripts/pricelist_2026/templates/pricelist.md.j2`

Plain Markdown for the repo-versioned auditable record. Links to the asset files in `docs/pricing/assets/2026/` instead of base64 (Markdown renderers don't all handle base64).

- [ ] **Step 1: Write pricelist.md.j2**

Write `scripts/pricelist_2026/templates/pricelist.md.j2`:

```jinja
# Bali Zero — Price List 2026

**Effective:** {{ effective_date }}
**Version:** {{ version }}
**Last updated:** {{ last_updated }}

> {{ contact.email }} · {{ contact.whatsapp }} · {{ contact.website }} · {{ contact.location }}

![Bali Zero](./assets/2026/logo_circle.png)

---

## Contents

{% for section in sections -%}
- **{{ section.roman }}.** [{{ section.title }}](#{{ section.anchor }})
{% endfor %}

---

{% for section in sections %}
<a id="{{ section.anchor }}"></a>

## {{ section.roman }}. {{ section.title }}

![{{ section.title }}](./assets/2026/heros/{{ section.hero_basename }}.png)

_{{ section.intro }}_

{% if section.subsections %}
{% for sub in section.subsections %}
### {{ sub.title }}

| Service | Description | Price |
| --- | --- | --- |
{% for svc in sub.services -%}
| **{{ svc.name }}** | {{ svc.description_en }}{% if svc.notes %} _({{ svc.notes }})_{% endif %} | {% if svc.tier_range %}{{ svc.tier_range[0] }} – {{ svc.tier_range[1] }}{% else %}{{ svc.price }}{% endif %} |
{% endfor %}

{% endfor %}
{% else %}
| Service | Description | Price |
| --- | --- | --- |
{% for svc in section.services -%}
| **{{ svc.name }}** | {{ svc.description_en }}{% if svc.notes %} _({{ svc.notes }})_{% endif %} | {% if svc.tier_range %}{{ svc.tier_range[0] }} – {{ svc.tier_range[1] }}{% else %}{{ svc.price }}{% endif %} |
{% endfor %}
{% endif %}

---
{% endfor %}

## Get in touch

- Website: <https://{{ contact.website }}>
- Email: <{{ contact.email }}>
- WhatsApp: [{{ contact.whatsapp }}]({{ contact.wa_link }})
- Office: {{ contact.location }}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/pricelist_2026/templates/pricelist.md.j2
git commit -m "feat(pricelist-2026): add Markdown template

Repo-versioned auditable record of the price list. Tables per section,
hero image references via repo-relative paths (so GitHub renders them
inline). Same structural model as the HTML template — section, optional
subsections, service rows.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Generator script (TDD)

**Files:**

- Create: `scripts/pricelist_2026/generate.py`
- Create: `scripts/pricelist_2026/tests/test_generate.py`

The generator: reads JSON + assets + templates → emits HTML + Markdown. PDF is a separate step (Task 8).

- [ ] **Step 1: Write the failing test**

Write `scripts/pricelist_2026/tests/test_generate.py`:

```python
"""Tests for the 2026 price list generator (HTML + Markdown only — PDF tested separately)."""
import base64
import json
import re
from pathlib import Path

import pytest

from scripts.pricelist_2026 import generate, schema

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
    # Heros for each section the fixture uses (single_entry_visas + tax_accounting)
    for hero_name in ["01_visas.png", "03_tax.png"]:
        (heros_dir / hero_name).write_bytes(one_pixel)
    # Icons
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
    # Cover content
    assert "BALI ZERO" in html
    assert "Price List 2026" in html
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


def test_generate_markdown_smoke(fixture_data, stub_assets, tmp_path):
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
    assert "visa-tourism" in str(exc.value) or "tax-monthly" in str(exc.value)


def test_generate_html_contains_qr_link(fixture_data, stub_assets, tmp_path):
    out_html = tmp_path / "out.html"
    generate.render_html(data=fixture_data, assets_dir=stub_assets, out_path=out_html)
    html = out_html.read_text()
    # QR code image embedded
    assert html.count('src="data:image/png;base64,') >= 3  # logo + hero + icon + qr
    # Closing section text
    assert "Get in touch" in html
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m pytest scripts/pricelist_2026/tests/test_generate.py -v 2>&1 | tail -20`

Expected: import errors / fail because `generate.py` doesn't exist yet.

- [ ] **Step 3: Implement generate.py**

Write `scripts/pricelist_2026/generate.py`:

```python
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
    "visa_extensions": (
        "II", "Visa Extensions",
        "Extension fees for existing visas.",
        "01_visas",
    ),
    "multiple_entry_visas": (
        "III", "Multiple Entry Visas",
        "Multi-entry visas for repeat travel.",
        "01_visas",
    ),
    "kitas_permits": (
        "IV", "KITAS Permits",
        "Long-stay residence permits for foreign nationals.",
        "02_kitas_kitap",
    ),
    "kitap_permits": (
        "V", "KITAP + MERP",
        "Permanent residence permits and multiple re-entry permits.",
        "02_kitas_kitap",
    ),
    "tax_accounting": (
        "VI", "Tax & Accounting",
        "Monthly bookkeeping packages, annual filings and stand-alone fees.",
        "03_tax",
    ),
    "company_services": (
        "VII", "Company Services",
        "PT PMA setup, virtual office and corporate amendments.",
        "04_company",
    ),
    "consultant_services": (
        "VIII", "Bali Zero Consultant Services",
        "Compliance and registration fees handled by Bali Zero.",
        "04_company",
    ),
    "other_process": (
        "IX", "Other Process",
        "Passports, identity documents and miscellaneous immigration filings.",
        "05_other_process",
    ),
    "urgent_processing": (
        "X", "Urgent Processing",
        "Express processing tiers for time-sensitive filings.",
        "06_urgent",
    ),
}

SUBSECTION_TITLES = {
    "monthly_tax_basic": "VI.1 Monthly Tax Report — without LKPM & Annual",
    "monthly_tax_bundled": "VI.2 Monthly Tax Report — including LKPM + Annual",
    "annual_basic_packages": "VI.3 Annual Basic Packages",
    "annual_standalone": "VI.4 Annual & Compliance Stand-alone Fees",
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
        # Empty for now — Task 9 can add subset Google Fonts woff2 base64
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
    import argparse, json, sys
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

    print(f"  → Markdown: {args.out_md}")
    render_markdown(data, args.out_md)
    print(f"  → HTML:     {args.out_html}")
    render_html(data, args.assets_dir, args.out_html)
    print("✓ Done.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Install Python deps if missing**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && \
python3 -m pip install --quiet jinja2 qrcode pillow && cd /Users/nuzantara/Desktop/nuzantara
```

Expected: silent install (jinja2 may already be present; qrcode + pillow likely new).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/nuzantara/Desktop/nuzantara && source apps/backend-rag/.venv/bin/activate && python3 -m pytest scripts/pricelist_2026/tests/test_generate.py -v 2>&1 | tail -25`

Expected: ALL 5 tests PASS.

- [ ] **Step 6: Smoke run on the real JSON + assets**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && source apps/backend-rag/.venv/bin/activate && \
python3 -m scripts.pricelist_2026.generate
```

Expected output:

```
  → Markdown: docs/pricing/Bali_Zero_Price_List_2026.md
  → HTML:     /Users/nuzantara/Desktop/Bali_Zero_Price_List_2026.html
✓ Done.
```

Open the HTML in browser: `open ~/Desktop/Bali_Zero_Price_List_2026.html`. Verify cover, ToC, sections, prices, hero images, icons, QR all render.

- [ ] **Step 7: Commit**

```bash
git add scripts/pricelist_2026/generate.py scripts/pricelist_2026/tests/test_generate.py docs/pricing/Bali_Zero_Price_List_2026.md
git commit -m "feat(pricelist-2026): add HTML + Markdown generator

Reads bali_zero_official_prices_2026.json + asset PNGs + Jinja templates
→ emits self-contained HTML (base64-embedded images, generated WhatsApp
QR code) and a repo-versioned Markdown record. 5 tests covering smoke
render, schema rejection, missing-asset detection, QR embedding.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: PDF rendering via Playwright

**Files:**

- Create: `scripts/pricelist_2026/render_pdf.py`

PDF is a separate concern from HTML/MD generation: it requires Playwright + Chromium and runs slower. Keeping it isolated lets us iterate on the HTML without paying the PDF cost every time.

- [ ] **Step 1: Verify Playwright + Chromium are installed**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && \
python3 -c "from playwright.sync_api import sync_playwright; print('playwright ok')" && \
python3 -m playwright install chromium 2>&1 | tail -3
```

Expected: `playwright ok` followed by either an install confirmation or "is already installed".

- [ ] **Step 2: Write render_pdf.py**

Write `scripts/pricelist_2026/render_pdf.py`:

```python
"""Render the HTML output to a print-ready PDF via Playwright headless Chromium."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    if not html_path.exists():
        sys.exit(f"ERROR: HTML not found at {html_path}. Run generate.py first.")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    file_url = f"file://{html_path.resolve()}"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(file_url, wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            prefer_css_page_size=True,
        )
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--html",
        type=Path,
        default=Path.home() / "Desktop" / "Bali_Zero_Price_List_2026.html",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path.home() / "Desktop" / "Bali_Zero_Price_List_2026.pdf",
    )
    args = parser.parse_args()
    print(f"  → PDF: {args.pdf}")
    render_pdf(args.html, args.pdf)
    print(f"✓ Done ({args.pdf.stat().st_size:,} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the PDF render**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && source apps/backend-rag/.venv/bin/activate && \
python3 -m scripts.pricelist_2026.render_pdf
```

Expected: `✓ Done (NNN,NNN bytes)`. PDF size should be in the 5-15 MB range with all heros + icons embedded.

Open: `open ~/Desktop/Bali_Zero_Price_List_2026.pdf`.

- [ ] **Step 4: Visual QA**

Open the PDF and check, page by page:

- Cover renders centered, logo visible, palette correct
- ToC entries align with section dividers
- Each section divider has a hero image
- Service rows: name + description + price all visible, no overflow
- Page breaks fall between rows, not mid-row (`page-break-inside: avoid`)
- Closing page: contacts + QR code visible, QR scans (use phone camera) → opens WhatsApp to the right number
- Total pages ≈ 18-22 (acceptable range)

If any issue: edit `pricelist.html.j2`, re-run `generate.py`, then re-run `render_pdf.py`. Iterate until clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/pricelist_2026/render_pdf.py
git commit -m "feat(pricelist-2026): add Playwright PDF renderer

Headless Chromium prints the generated HTML to A4 portrait PDF with
full-bleed margins (page CSS controls section padding). Run after
generate.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: gitignore + final cleanup

**Files:**

- Modify: `.gitignore`

- [ ] **Step 1: Append patterns to .gitignore**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara && cat >> .gitignore << 'EOF'

# Bali Zero Price List 2026 — generated outputs (sources are in docs/pricing/ and apps/backend-rag/backend/data/)
/Users/nuzantara/Desktop/Bali_Zero_Price_List_2026.html
/Users/nuzantara/Desktop/Bali_Zero_Price_List_2026.pdf
/Users/nuzantara/Desktop/Bali_Zero_Price_List_2026_assets/
EOF
```

(Note: gitignore patterns do NOT need to start with `/Users/...` since git only sees repo-relative paths. The above is purely documentary — git will simply ignore the unmatched absolute paths. The actual generated outputs sit OUTSIDE the repo on `~/Desktop/`, so no gitignore is needed. Keep the comment block as documentation only.)

Better, simpler: just add a `# Bali Zero Price List 2026 — outputs live outside the repo on ~/Desktop/` comment marker for grep-ability.

```bash
cd /Users/nuzantara/Desktop/nuzantara && cat >> .gitignore << 'EOF'

# Bali Zero Price List 2026 — generated outputs live outside the repo on ~/Desktop/
# Source of truth: apps/backend-rag/backend/data/bali_zero_official_prices_2026.json
# Generator:       scripts/pricelist_2026/
# Versioned MD:    docs/pricing/Bali_Zero_Price_List_2026.md
EOF
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore(pricelist-2026): document generator output locations in gitignore"
```

---

## Task 10: End-to-end smoke test + handoff

- [ ] **Step 1: Full pipeline rerun from scratch**

```bash
cd /Users/nuzantara/Desktop/nuzantara && source apps/backend-rag/.venv/bin/activate

# 1. Validate JSON
python3 -m pytest scripts/pricelist_2026/tests/ -v

# 2. Generate HTML + Markdown
python3 -m scripts.pricelist_2026.generate

# 3. Generate PDF
python3 -m scripts.pricelist_2026.render_pdf

# 4. List outputs
ls -lh ~/Desktop/Bali_Zero_Price_List_2026.{html,pdf}
ls -lh docs/pricing/Bali_Zero_Price_List_2026.md
```

Expected:

- All tests pass
- HTML: ~3-8 MB (fonts + base64 images)
- PDF: ~5-15 MB
- MD: ~30-80 KB

- [ ] **Step 2: Open all three and review side-by-side**

```bash
open ~/Desktop/Bali_Zero_Price_List_2026.html
open ~/Desktop/Bali_Zero_Price_List_2026.pdf
code docs/pricing/Bali_Zero_Price_List_2026.md
```

Confirm:

- HTML and PDF are visually equivalent
- Markdown contains all 80 services in tables, hero links resolve in GitHub-style preview
- No "TBD", "fixme", or placeholder strings

- [ ] **Step 3: Test the QR code**

Scan the QR code on the PDF closing page with a phone camera. It should open WhatsApp to a chat with `+62 821 31 07 363` (the canonical contact).

- [ ] **Step 4: Final summary message to owner**

In the chat, summarize for Antonello:

- Pipeline runs: `python3 -m scripts.pricelist_2026.generate && python3 -m scripts.pricelist_2026.render_pdf`
- Source of truth: `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json`
- Outputs on Desktop: HTML + PDF
- Versioned in repo: `docs/pricing/Bali_Zero_Price_List_2026.md` + assets
- Backend RAG `PricingTool` was NOT touched — still reads `_2025.json`. Owner approval required to swap.
- Open items from spec §13: confirm WhatsApp number; consider bahasa Indonesia variant (future work).

---

## Self-Review (post-plan check)

**Spec coverage:**

- §1 Goal points 1-6 → covered by Task 1 (consolidation), Task 1 (new sections), Task 1 (3 conflicts), Task 1 (dedup), Tasks 5-7-8 (3 renders), Tasks 3-4 (visual treatment) ✅
- §3 Source-of-truth architecture → Task 1 (JSON) + Task 7-8 (renderers) ✅
- §4 JSON schema → Task 1 (authored) + Task 2 (validator) ✅
- §5 Document structure (12 sections) → Task 5 (HTML template SECTION_META) + Task 7 (`SECTION_META` dict) ✅
- §6 Visual / palette / typography / image strategy → Tasks 3-4 (assets) + Task 5 (HTML CSS palette hex inlined) ✅
- §6.5 Cover layout → Task 5 (`.cover` block in template) ✅
- §6.6 Senior touches: page numbers ✅, running header ✅, ToC leader dots ✅, QR code ✅. Color-coded edge tabs NOT explicitly implemented → ACCEPTED MISS, can be a v1.1 follow-up; the document is already acceptable without it.
- §7 Generator script → Task 7 (`generate.py`) + Task 8 (`render_pdf.py`) ✅
- §8 Conflicts resolved → Task 1 step 2 explicitly references each ✅
- §9 Build sequence → mirrored by Tasks 1-10 in order ✅
- §10 Testing → Task 2 (schema tests), Task 7 (generator tests), Task 10 (E2E smoke) ✅
- §11 Distribution → Task 10 step 4 handoff message ✅
- §12 Risks → addressed: codex availability (Task 4 step 1 hard-fail), font subsetting (font_face_block left empty in v1, can be filled in a future iteration without breaking the template — ACCEPTED MISS), page-break (CSS in Task 5) ✅
- §13 Open items → flagged in Task 10 step 4 ✅

**Placeholder scan:** No "TBD" / "TODO" / vague-handler-style steps. Each step has the actual code or command. ✅

**Type/name consistency:**

- `bali_zero_official_prices_2026.json` referenced consistently across Tasks 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 ✅
- `wa_link` field added to JSON contact (Task 1) and consumed by `_make_qr_data_uri` (Task 7) and Markdown template (Task 6) ✅
- `icon_id` field used in JSON (Task 1), enumerated in `asset_briefs.ICON_BRIEFS` (Task 3), looked up in `_decorate_svc` (Task 7), filename pattern `{icon_id}.png` (Task 4 + Task 7) ✅
- `tier_range` field defined as `list[str]` of 2 entries (Task 1) and validated in `schema._validate_service` (Task 2) and rendered in HTML/MD templates (Task 5/6) ✅
- `SchemaError` and `AssetMissingError` raised in `generate.py` (Task 7) and asserted in tests (Task 7 step 1) ✅
- Section count: 10 categories in JSON (Task 1) → 10 entries in `SECTION_META` (Task 7) → 10 sections rendered ✅

**Acceptance:** plan is self-contained, every step has code or a verifiable command, no leaks of "fix this later". The two ACCEPTED MISSES (color-coded edge tabs + font subsetting) are explicitly documented as v1.1 follow-ups and do not block the v1 deliverable.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-06-bali-zero-pricelist-2026.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
