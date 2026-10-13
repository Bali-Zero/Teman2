#!/usr/bin/env python3
"""e33_cards_rule_diff.py — the rule-id diff between each E33-family card and the active pack.

The seven doctrine cards research/visa/doctrine-factory/cards/E33*.md each carry a section
"## 2. Active rules (rulepack-prod-029)". The backticked rule ids in that section must be exactly
the rule ids the signed pack scopes to the card's product. This script prints one line per
difference and prints NOTHING when the cards and the pack agree (exit 0); any difference exits 1.

It takes no arguments: the pack, the cards directory and the registry are literal paths.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = (
    REPO_ROOT
    / "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-029.signed.json"
)
CARDS_DIR = REPO_ROOT / "research/visa/doctrine-factory/cards"
CODES = ("E33", "E33A", "E33B", "E33C", "E33E", "E33F", "E33G")
SECTION = "## 2. Active rules (rulepack-prod-029)"
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


def diff(pack: dict, cards: dict[str, str]) -> list[str]:
    """One line per card-vs-pack difference; empty list when they agree."""
    expected = pack_rules_by_code(pack)
    lines: list[str] = []
    for code in CODES:
        found = card_rule_ids(cards.get(code, ""))
        for rule_id in sorted(expected[code] - found):
            lines.append(f"{code}: in the pack, missing on the card: {rule_id}")
        for rule_id in sorted(found - expected[code]):
            lines.append(f"{code}: on the card, not in the pack: {rule_id}")
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
