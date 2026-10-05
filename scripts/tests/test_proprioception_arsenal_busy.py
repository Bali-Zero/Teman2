"""BUSY is a transient arsenal seat status, not persistent seat death.

arsenal_probe records a seat as BUSY when it timed out while another process of the
same binary was running. The mini/pro `arsenal_seats` reader whitelists the transient
statuses; BUSY missing from it made one contended seat read as DIVERGED (P1).
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
REPO_ROOT = Path(__file__).resolve().parents[2]


def _verdict(tmp_path: Path, status: str):
    payload = json.dumps({"findings": [{"seat": "agy", "status": status}]})
    reader = tmp_path / "fake_read_last.py"
    reader.write_text(f"print({payload!r})\n")
    entry = dict(ENTRY, target=["python3", str(reader)])
    return prop.run_wrap(REPO_ROOT, entry, 15)[0]


def test_arsenal_seats_whitelists_busy_as_transient():
    assert "BUSY" in ENTRY["ok_values"]


def test_a_busy_seat_reconciles(tmp_path):
    assert _verdict(tmp_path, "BUSY") == prop.RECONCILED


def test_a_dead_seat_still_diverges(tmp_path):
    assert _verdict(tmp_path, "AUTH_DEAD") == prop.DIVERGED
