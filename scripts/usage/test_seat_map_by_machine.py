"""seat_map.json carries one measured map per machine, and the registry pins it.

Naga gap 1 (2026-10-05): cswap and the usage collector read ONLY seat_map.json,
whose single flat map was wrong on Air-M5 (e.g. `~/.claude-acct2` -> A1 while
the measured seat is A3). The collector runs from every host's main checkout,
so the cure cannot be "rewrite the flat map with M5's truth": Pro and Mini would
inherit it. A machine reads its own `by_machine` block, else the unmeasured
top-level fallback — and every block must equal the bindings FLEET_TOPOLOGY.json
records for that machine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seat_usage_collector as suc  # noqa: E402

_USAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _USAGE_DIR.parents[1]
SEAT_MAP = json.loads((_USAGE_DIR / "seat_map.json").read_text())
REGISTRY = json.loads((_REPO_ROOT / "FLEET_TOPOLOGY.json").read_text())


def registry_bindings(registry: dict, machine: str) -> tuple[dict, dict]:
    """(claude profile dir -> slot, codex home -> slot) the registry records on `machine`."""
    claude: dict[str, str] = {}
    for slot, seat in registry["accounts"]["anthropic"]["slots"].items():
        if seat.get("status") == "retired":
            continue
        bound = (seat.get("config_dir_by_machine") or {}).get(machine)
        for pdir in [bound] if isinstance(bound, str) else (bound or []):
            claude[pdir] = slot
    codex: dict[str, str] = {}
    openai = registry["accounts"]["openai"]
    for group in ("slots", "unrostered_seats"):
        for slot, seat in (openai.get(group) or {}).items():
            if seat.get("status") == "retired":
                continue
            home = (seat.get("codex_home_by_machine") or {}).get(machine)
            if home:
                codex[home] = slot
    return claude, codex


def registry_machines(registry: dict) -> set[str]:
    machines: set[str] = set()
    for seat in registry["accounts"]["anthropic"]["slots"].values():
        if seat.get("status") != "retired":
            machines |= set(seat.get("config_dir_by_machine") or {})
    openai = registry["accounts"]["openai"]
    for group in ("slots", "unrostered_seats"):
        for seat in (openai.get(group) or {}).values():
            machines |= set(seat.get("codex_home_by_machine") or {})
    return machines


def parity_errors(seat_map: dict, registry: dict) -> list[str]:
    errors = []
    blocks = seat_map.get("by_machine") or {}
    for machine in sorted(registry_machines(registry) - set(blocks)):
        errors.append(f"{machine}: registry records bindings but seat_map has no by_machine block")
    for machine, block in sorted(blocks.items()):
        claude, codex = registry_bindings(registry, machine)
        if block.get("claude_profiles") != claude:
            errors.append(f"{machine}: claude_profiles {block.get('claude_profiles')} != registry {claude}")
        if block.get("codex_homes") != codex:
            errors.append(f"{machine}: codex_homes {block.get('codex_homes')} != registry {codex}")
    return errors


# ------------------------------------------------------------ machine selection


def test_machine_block_is_selected_case_insensitively():
    block = suc.machine_seat_map(SEAT_MAP, "air-m5")
    assert block["claude_profiles"]["~/.claude-acct2"] == "A3"
    assert block["claude_profiles"]["~/.claude-a1"] == "A1"


def test_machine_without_block_never_inherits_another_machines_truth():
    for machine in ("Nuzantara", "Mini-Pro2", "unknown-host"):
        fallback = suc.machine_seat_map(SEAT_MAP, machine)
        assert fallback["claude_profiles"] == SEAT_MAP["claude_profiles"]
        assert fallback["codex_homes"] == SEAT_MAP["codex_homes"]
        assert "~/.claude-a1" not in fallback["claude_profiles"]


def test_flat_map_without_by_machine_is_returned_unchanged():
    flat = {"claude_profiles": {"~/.claude": "AZ"}, "codex_homes": {"~/.codex": "O1"}}
    assert suc.machine_seat_map(flat, "Air-M5") is flat


def test_default_machine_is_the_short_hostname(monkeypatch):
    monkeypatch.setattr(suc.socket, "gethostname", lambda: "Air-M5.local")
    assert suc.machine_seat_map(SEAT_MAP)["claude_profiles"]["~/.claude-kaiser"] == "A2"


# ------------------------------------------------------------ registry parity


def test_every_machine_block_equals_the_registry_bindings():
    assert parity_errors(SEAT_MAP, REGISTRY) == []


def test_parity_catches_the_flat_map_error_naga_found():
    drifted = json.loads(json.dumps(SEAT_MAP))
    drifted["by_machine"]["Air-M5"]["claude_profiles"]["~/.claude-acct2"] = "A1"
    assert any("claude_profiles" in e for e in parity_errors(drifted, REGISTRY))


def test_parity_catches_a_registry_machine_without_a_block():
    registry = json.loads(json.dumps(REGISTRY))
    registry["accounts"]["anthropic"]["slots"]["A2"]["config_dir_by_machine"]["Pro"] = "~/.claude-kaiser"
    assert any(e.startswith("Pro:") for e in parity_errors(SEAT_MAP, registry))


def test_retired_slot_binding_is_never_demanded():
    registry = json.loads(json.dumps(REGISTRY))
    retired = {"status": "retired", "config_dir_by_machine": {"Air-M5": "~/.claude-retired"}}
    registry["accounts"]["anthropic"]["slots"]["RX"] = retired
    claude, _ = registry_bindings(registry, "Air-M5")
    assert "~/.claude-retired" not in claude
