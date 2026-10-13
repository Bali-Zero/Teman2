#!/usr/bin/env python3
"""e33_cards_rule_diff.py — the diff between each E33-family card and the active signed pack.

Per card: rule ids, each rule's stage, effect, reason code, numeric thresholds and validity start,
and the product's pricing key with its catalog price. The active pack is the highest-numbered
rulepack-prod-NNN.signed.json on disk, so a newer pack the cards do not describe is named.
Takes no arguments; prints one line per difference and nothing when they agree (exit 0)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
PRICES = REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
PACK = max(PACKS_DIR.glob("rulepack-prod-[0-9][0-9][0-9].signed.json"), key=lambda p: p.name)
PACK_ID = PACK.name.removesuffix(".signed.json")
CARDS_DIR = REPO_ROOT / "research/visa/doctrine-factory/cards"
CODES = ("E33", "E33A", "E33B", "E33C", "E33E", "E33F", "E33G")
SECTION = f"## 2. Active rules ({PACK_ID})"
ROW = re.compile(r"\|\s*`((?:hf|el|review)\.[a-z0-9][a-z0-9.-]*)`\s*\|(.*)\|\s*$")


def pack_rules_by_code(pack: dict) -> dict[str, set[str]]:
    """Rule ids the pack scopes to each E33-family product."""
    payload = pack["payload"]
    code_of = {p["product_version_id"]: p["product_code"] for p in payload["products"]}
    out: dict[str, set[str]] = {code: set() for code in CODES}
    for rule in payload["rules"]:
        for version in rule.get("product_version_ids") or []:
            if code_of.get(version) in out:
                out[code_of[version]].add(rule["rule_id"])
    return out


def _section(text: str) -> str:
    """The text between the rules heading and the next `## ` heading ("" when absent)."""
    start = text.find(SECTION)
    body = text[start + len(SECTION) :] if start >= 0 else ""
    end = re.search(r"^## ", body, re.MULTILINE)
    return body[: end.start()] if end else body


def card_rows(text: str) -> dict[str, list[str]]:
    """rule_id -> table cells after the id, in the rules section."""
    matches = map(ROW.match, _section(text).splitlines())
    return {m.group(1): [c.strip() for c in m.group(2).split("|")] for m in matches if m}


def card_rule_ids(text: str) -> set[str]:
    """Backticked rule ids in the rules section, in or out of a table row."""
    return set(re.findall(r"`((?:hf|el|review)\.[a-z0-9][a-z0-9.-]*)`", _section(text)))


def _numbers(node) -> set[int | float]:
    """Every numeric threshold (not bool) in a predicate tree."""
    if isinstance(node, list):
        return set().union(*map(_numbers, node)) if node else set()
    if not isinstance(node, dict):
        return set()
    found: set[int | float] = set()
    for key, value in node.items():
        if key in ("value", "values", "lower", "upper"):
            found |= {v for v in (value if isinstance(value, list) else [value]) if isinstance(v, (int, float)) and not isinstance(v, bool)}
        else:
            found |= _numbers(value)
    return found


def _has_number(text: str, number: float) -> bool:
    forms = {str(int(number)), f"{int(number):,}"} if number == int(number) else {str(number)}
    return any(re.search(rf"(?<![\d,.]){re.escape(f)}(?!\d|[,.]\d)", text) for f in forms)


def rule_lines(code: str, rule: dict, cells: list[str]) -> list[str]:
    """Differences between one pack rule and its card row."""
    rid, (stage, effect_cell, what) = rule["rule_id"], (cells + ["", "", ""])[:3]
    effect = f"{rule['effect']['type']} / `{rule['effect']['reason_code']}`"
    lines = []
    if stage != rule["stage"]:
        lines.append(f"{code}: {rid}: stage on the card is {stage}, in the pack {rule['stage']}")
    if effect_cell != effect:
        lines.append(f"{code}: {rid}: effect on the card is {effect_cell}, in the pack {effect}")
    lines += [
        f"{code}: {rid}: pack threshold {n:g} is not stated on the card row"
        for n in sorted(_numbers(rule.get("when")))
        if not _has_number(what, n)
    ]
    start = rule["valid_period"]["from"][:10]
    if start != "2026-07-24" and f"valid from {start}" not in what:
        lines.append(f"{code}: {rid}: pack validity start {start} is not stated on the card row")
    return lines


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
    prices = prices if prices is not None else json.loads(PRICES.read_text(encoding="utf-8"))
    expected = pack_rules_by_code(pack)
    rules = {r["rule_id"]: r for r in pack["payload"]["rules"]}
    key_of = {p["product_code"]: (p["pricing_key"] or {}).get("item_key") for p in pack["payload"]["products"]}
    lines: list[str] = []
    for code in CODES:
        text = cards.get(code, "")
        found, rows = card_rule_ids(text), card_rows(text)
        lines += [f"{code}: in the pack, missing on the card: {r}" for r in sorted(expected[code] - found)]
        lines += [f"{code}: on the card, not in the pack: {r}" for r in sorted(found - expected[code])]
        for rid in sorted(expected[code] & found):
            lines += rule_lines(code, rules[rid], rows[rid]) if rid in rows else [f"{code}: {rid}: not in a table row"]
        if key_of.get(code):
            price = catalog_price(prices, key_of[code])
            if key_of[code] not in text:
                lines.append(f"{code}: pricing key {key_of[code]} is not stated on the card")
            if price is None:
                lines.append(f"{code}: pricing key {key_of[code]} is not in the catalog")
            elif price not in text:
                lines.append(f"{code}: catalog price {price} for {key_of[code]} is not stated on the card")
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
