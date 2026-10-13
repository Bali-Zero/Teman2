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
SEED_PATH = (
    REPO_ROOT / "apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py"
)
PACKS_DIR = REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
QUOTE = "contact for quote"


def _seed_rows() -> list[dict]:
    src = SEED_PATH.read_text()
    m = re.search(r"VISA_TYPES\s*=\s*(\[.*?\n\])\s*\n\nasync def", src, re.DOTALL)
    assert m, "cannot parse seed VISA_TYPES"
    return ast.literal_eval(m.group(1))


def _active_pack() -> dict:
    packs = []
    for path in PACKS_DIR.glob("rulepack-prod-*.signed.json"):
        pack = json.loads(path.read_text())
        if pack["protected"]["environment"] == "PRODUCTION":
            packs.append((pack["payload"]["sequence"], pack))
    assert packs, "no signed PRODUCTION pack found"
    return max(packs, key=lambda item: item[0])[1]


def _active_pack_pricing_keys() -> dict[str, object]:
    return {p["product_code"]: p["pricing_key"] for p in _active_pack()["payload"]["products"]}


def _e23_children() -> list[dict]:
    return [r for r in _seed_rows() if r.get("metadata", {}).get("inherited_from") == "E23"]


def test_e23_children_are_the_audited_set():
    assert {r["code"] for r in _e23_children()} == {"E23A", "E23U", "E23V", "E23X", "E23Y"}


def test_pack_declares_e23u_and_e23v_with_null_pricing_key():
    pricing = _active_pack_pricing_keys()
    assert pricing["E23"] is not None
    assert "E23U" in pricing and pricing["E23U"] is None
    assert "E23V" in pricing and pricing["E23V"] is None


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
