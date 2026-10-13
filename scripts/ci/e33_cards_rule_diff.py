#!/usr/bin/env python3
"""e33_cards_rule_diff.py — the diff between each E33-family card and the active pack.

The seven doctrine cards research/visa/doctrine-factory/cards/E33*.md each carry a section
"## 2. Active rules (rulepack-prod-NNN)". Three things must agree with the signed pack:
the rule ids scoped to the card's product, each rule's stage, effect type, reason code and every
numeric threshold in its predicate, and the product's pricing key with its all-inclusive catalog
price. The active pack is the highest-numbered rulepack-prod-NNN.signed.json on disk, so a newer
signed pack that the cards do not yet describe is named, never silently passed. This script prints
one line per difference and prints NOTHING when the cards and the pack agree (exit 0).

It takes no arguments: the pack, the cards directory and the registry are literal paths.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
PRICES = REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"


def active_pack_path() -> Path:
    """The highest-numbered signed production pack on disk."""
    found = [
        (int(m.group(1)), p)
        for p in PACKS_DIR.glob("rulepack-prod-*.signed.json")
        if (m := re.fullmatch(r"rulepack-prod-(\d+)\.signed\.json", p.name))
    ]
    return max(found)[1]


PACK = active_pack_path()
PACK_ID = PACK.name.removesuffix(".signed.json")
CARDS_DIR = REPO_ROOT / "research/visa/doctrine-factory/cards"
CODES = ("E33", "E33A", "E33B", "E33C", "E33E", "E33F", "E33G")
SECTION = f"## 2. Active rules ({PACK_ID})"
RULE_ID = re.compile(r"`((?:hf|el|review)\.[a-z0-9][a-z0-9.-]*)`")


def pack_rules_by_code(pack: dict) -> dict[str, set[str]]:
    """Rule ids the pack scopes to each E33-family product."""
    payload = pack["payload"]
    version_to_code = {
        p["product_version_id"]: p["product_code"]
        for p in payload["products"]
        if p["product_code"] in CODES
    }
    out: dict[str, set[str]] = {code: set() for code in CODES}
    for rule in payload["rules"]:
        for version in rule.get("product_version_ids") or []:
            if version in version_to_code:
                out[version_to_code[version]].add(rule["rule_id"])
    return out


def card_rule_ids(text: str) -> set[str]:
    """Backticked rule ids between the rules heading and the next `## ` heading."""
    start = text.find(SECTION)
    if start < 0:
        return set()
    body = text[start + len(SECTION) :]
    end = re.search(r"^## ", body, re.MULTILINE)
    if end:
        body = body[: end.start()]
    return set(RULE_ID.findall(body))


def card_rows(text: str) -> dict[str, list[str]]:
    """rule_id -> table cells after the id, for the rows of the rules section."""
    start = text.find(SECTION)
    if start < 0:
        return {}
    body = text[start + len(SECTION) :]
    end = re.search(r"^## ", body, re.MULTILINE)
    if end:
        body = body[: end.start()]
    rows: dict[str, list[str]] = {}
    for line in body.splitlines():
        m = re.match(r"\|\s*`((?:hf|el|review)\.[^`]+)`\s*\|(.*)\|\s*$", line)
        if m:
            rows[m.group(1)] = [c.strip() for c in m.group(2).split("|")]
    return rows


def _numbers(node) -> list[float]:
    """Every numeric threshold (not bool) in a predicate tree."""
    out: list[float] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("value", "values", "lower", "upper"):
                items = value if isinstance(value, list) else [value]
                out += [v for v in items if isinstance(v, (int, float)) and not isinstance(v, bool)]
            else:
                out += _numbers(value)
    elif isinstance(node, list):
        for item in node:
            out += _numbers(item)
    return out


def _has_number(text: str, number: float) -> bool:
    forms = {str(int(number)), f"{int(number):,}"} if number == int(number) else {str(number)}
    return any(re.search(rf"(?<![\d,.]){re.escape(f)}(?![\d]|[,.]\d)", text) for f in forms)


def rule_content_lines(code: str, rule: dict, cells: list[str]) -> list[str]:
    """Differences between one pack rule and its card row: stage, effect, reason, thresholds."""
    rid = rule["rule_id"]
    if len(cells) < 3:
        return [f"{code}: {rid}: the card row does not have stage, effect and description cells"]
    stage, effect_cell, what = cells[0], cells[1], cells[2]
    lines: list[str] = []
    effect = rule["effect"]
    if stage != rule["stage"]:
        lines.append(f"{code}: {rid}: stage on the card is {stage}, in the pack {rule['stage']}")
    expected_effect = f"{effect['type']} / `{effect['reason_code']}`"
    if effect_cell != expected_effect:
        lines.append(f"{code}: {rid}: effect on the card is {effect_cell}, in the pack {expected_effect}")
    for number in sorted(set(_numbers(rule.get("when")))):
        if not _has_number(what, number):
            lines.append(f"{code}: {rid}: pack threshold {number:g} is not stated on the card row")
    start = rule["valid_period"]["from"][:10]
    if start != "2026-07-24" and f"valid from {start}" not in what:
        lines.append(f"{code}: {rid}: pack validity start {start} is not stated on the card row")
    return lines


def pack_pricing_by_code(pack: dict) -> dict[str, str | None]:
    return {
        p["product_code"]: (p["pricing_key"] or {}).get("item_key")
        for p in pack["payload"]["products"]
        if p["product_code"] in CODES
    }


def catalog_price(prices: dict, item_key: str) -> str | None:
    """The catalog price of an item as 'N,NNN,NNN IDR'; None when the item is absent."""
    stack = [prices]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("name") == item_key and "price" in node:
                return str(node["price"]).replace(".", ",")
            stack += list(node.values())
        elif isinstance(node, list):
            stack += node
    return None


def diff(pack: dict, cards: dict[str, str], prices: dict | None = None) -> list[str]:
    """One line per card-vs-pack difference; empty list when they agree."""
    if prices is None:
        prices = json.loads(PRICES.read_text(encoding="utf-8"))
    expected = pack_rules_by_code(pack)
    rules = {r["rule_id"]: r for r in pack["payload"]["rules"]}
    pricing = pack_pricing_by_code(pack)
    lines: list[str] = []
    for code in CODES:
        text = cards.get(code, "")
        found = card_rule_ids(text)
        for rule_id in sorted(expected[code] - found):
            lines.append(f"{code}: in the pack, missing on the card: {rule_id}")
        for rule_id in sorted(found - expected[code]):
            lines.append(f"{code}: on the card, not in the pack: {rule_id}")
        rows = card_rows(text)
        for rule_id in sorted(expected[code] & found):
            if rule_id in rows:
                lines += rule_content_lines(code, rules[rule_id], rows[rule_id])
            else:
                lines.append(f"{code}: {rule_id}: named on the card outside a table row")
        item_key = pricing[code]
        if item_key:
            price = catalog_price(prices, item_key)
            if item_key not in text:
                lines.append(f"{code}: pricing key {item_key} is not stated on the card")
            if price is None:
                lines.append(f"{code}: pricing key {item_key} is not in the catalog")
            elif price not in text:
                lines.append(f"{code}: catalog price {price} for {item_key} is not stated on the card")
    return lines


def main() -> int:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    cards = {c: (CARDS_DIR / f"{c}.md").read_text(encoding="utf-8") for c in CODES}
    lines = diff(pack, cards)
    for line in lines:
        print(line)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
