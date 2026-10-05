"""`arsenal_seats` (mini/pro) must treat a BUSY seat as transient, not DIVERGED.

BUSY (arsenal_probe, #7882/#7892) means a probe timed out while sibling processes of the
same seat were running: contention, not death. The consumer's ok_values whitelist did
not know it, so one contended seat DIVERGED at internal severity P1. Drives the REAL
registry entry through run_wrap with a stubbed subprocess. The separate VCR entry
(`arsenal_seats_vcr_m5`) has its own contract and is asserted untouched.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)  # type: ignore[union-attr]

ENTRY = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "arsenal_seats")
VCR_ENTRY = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "arsenal_seats_vcr_m5")


def _run(findings: list[dict]) -> tuple[str, int, list[str]]:
    payload = json.dumps({"findings": findings})
    original_sh, original_exists = prop.sh, Path.exists
    prop.sh = lambda argv, timeout=None, cwd=None: (0, payload, "")  # type: ignore[assignment]
    Path.exists = lambda self: True  # type: ignore[method-assign]
    try:
        return prop.run_wrap(Path("/repo"), ENTRY, timeout=5)
    finally:
        prop.sh = original_sh  # type: ignore[assignment]
        Path.exists = original_exists  # type: ignore[method-assign]


def test_one_busy_seat_is_reconciled() -> None:
    status, n, _ = _run([{"seat": "codex", "status": "LIVE"}, {"seat": "kimi", "status": "BUSY"}])
    assert status == prop.RECONCILED
    assert n == 0


def test_busy_does_not_mask_a_genuinely_dead_seat() -> None:
    status, n, ev = _run([{"seat": "codex", "status": "BUSY"}, {"seat": "kimi", "status": "AUTH_DEAD"}])
    assert status == prop.DIVERGED
    assert n == 1
    assert "kimi" in ev[0] and "codex" not in ev[0]


def test_dead_seat_alone_still_diverges() -> None:
    assert _run([{"seat": "kimi", "status": "AUTH_DEAD"}])[0] == prop.DIVERGED


def test_vcr_registry_contract_is_untouched() -> None:
    assert VCR_ENTRY["ok_values"] == []
