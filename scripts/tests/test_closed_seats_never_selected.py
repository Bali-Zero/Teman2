"""A closed Claude account is never selected, and every selector says so.

Zero closed A3, A4 and A5 (2026-10-17): in FLEET_TOPOLOGY.json they carry
status "retired". Retirement only holds if EVERY consumer that walks the numbered
OAuth slots skips them, so each consumer's own retired list is pinned to the
registry here, and no role chain may name a retired account. Behaviour (a closed
token that would answer is never spent) is exercised by test_claude_seat_pick.sh,
test_cron_agent_oauth_cascade.sh and test_claude_cascade_shell.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = json.loads((REPO_ROOT / "FLEET_TOPOLOGY.json").read_text(encoding="utf-8"))
SLOTS = REGISTRY["accounts"]["anthropic"]["slots"]


def _slot_number(seat: dict) -> str:
    return str(seat["oauth_token_slot"]).rsplit("_", 1)[-1]


RETIRED = {_slot_number(s) for s in SLOTS.values() if s.get("status") == "retired"}
LIVE = {_slot_number(s) for s in SLOTS.values() if s.get("status") != "retired"}


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def test_registry_closes_a3_a4_a5_and_leaves_a1_a2_az_live() -> None:
    assert {k for k, s in SLOTS.items() if s.get("status") == "retired"} == {"A3", "A4", "A5"}
    assert RETIRED == {"2", "3", "4"}
    assert LIVE == {"1", "5", "6"}


def test_az_is_a_live_numbered_seat_not_reserved() -> None:
    assert "status" not in SLOTS["AZ"]
    assert "LAUNCHABLE" in SLOTS["AZ"]["lane"]


def test_no_role_chain_names_a_retired_account() -> None:
    retired_names = {k for k, s in SLOTS.items() if s.get("status") == "retired"}
    named: list[str] = []

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "accounts" and isinstance(value, list):
                    named.extend(f"{path}:{a}" for a in value if a in retired_names)
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(REGISTRY["role_chains"], "role_chains")
    assert named == []


def test_cron_agent_retired_list_equals_registry() -> None:
    src = _read("infra/launchagents/wrappers/cron-agent.sh")
    declared = re.search(r"for retired_i in ([0-9 ]+); do", src)
    skipped = re.search(r'case " ([0-9 ]+) " in \*" \$i "\*\) continue', src)
    assert declared and skipped
    assert _numbers(declared.group(1)) == RETIRED
    assert _numbers(skipped.group(1)) == RETIRED


def test_ai_dispatch_retired_list_equals_registry() -> None:
    src = _read("scripts/ai-dispatch.sh")
    match = re.search(r"for retired_var in ((?:CLAUDE_CODE_OAUTH_TOKEN_\d+ ?)+); do", src)
    assert match
    assert _numbers(match.group(1)) == RETIRED


def test_claude_seat_lib_retired_list_equals_registry() -> None:
    src = _read("scripts/lib/claude_seat.sh")
    match = re.search(r'^_CLAUDE_SEAT_RETIRED_SLOTS="([0-9 ]+)"', src, re.M)
    assert match
    assert _numbers(match.group(1)) == RETIRED
