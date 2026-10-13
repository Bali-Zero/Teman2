"""E23 sub-codes without a priced product must not inherit the E23 price.

The seed copied E23's IDR amount onto every `inherited_from: E23` row. The active
RulePack (highest signed sequence) prices only products whose `pricing_key` is
non-null, so a sub-code with a null `pricing_key`, or no product at all, has no
price to show and must read 'Contact for quote'.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "apps").is_dir())
SEED_PATH = REPO_ROOT / "apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py"
PACKS_DIR = REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
PROD_PACK = re.compile(r"^rulepack-prod-(\d+)\.signed\.json$")
QUOTE = "contact for quote"


def _seed_rows() -> list[dict]:
    src = SEED_PATH.read_text()
    m = re.search(r"VISA_TYPES\s*=\s*(\[.*?\n\])\s*\n\nasync def", src, re.DOTALL)
    assert m, "cannot parse seed VISA_TYPES"
    return ast.literal_eval(m.group(1))


def _active_pack_pricing_keys() -> dict[str, object]:
    packs = [(int(m.group(1)), p) for p in PACKS_DIR.iterdir() if (m := PROD_PACK.match(p.name))]
    assert packs, "no signed prod pack found"
    _, path = max(packs)
    products = json.loads(path.read_text())["payload"]["products"]
    return {p["product_code"]: p["pricing_key"] for p in products}


def _e23_children() -> list[dict]:
    return [r for r in _seed_rows() if r.get("metadata", {}).get("inherited_from") == "E23"]


def test_e23_children_exist():
    assert {r["code"] for r in _e23_children()} >= {"E23U", "E23V"}


def test_unpriced_e23_children_carry_contact_for_quote():
    pricing = _active_pack_pricing_keys()
    unpriced = [r for r in _e23_children() if pricing.get(r["code"]) is None]
    assert {r["code"] for r in unpriced} >= {"E23U", "E23V"}
    for row in unpriced:
        cost = row["cost_visa"]
        assert cost.casefold() == QUOTE, f"{row['code']} carries {cost!r}, pack has no price for it"
        assert "idr" not in cost.casefold()


def test_priced_e23_children_are_not_downgraded():
    pricing = _active_pack_pricing_keys()
    for row in _e23_children():
        if pricing.get(row["code"]) is not None:
            assert "idr" in row["cost_visa"].casefold()
