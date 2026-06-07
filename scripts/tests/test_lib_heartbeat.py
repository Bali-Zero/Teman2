from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_heartbeat() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "lib" / "heartbeat.py"
    spec = importlib.util.spec_from_file_location("heartbeat_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_organism_heartbeat_writes_atomic_json(tmp_path: Path) -> None:
    module = _load_heartbeat()

    assert module.organism_heartbeat("pro.my_organ", "degraded", "rc=42", last_seen_dir=tmp_path)

    payload = json.loads((tmp_path / "pro.my_organ.json").read_text(encoding="utf-8"))
    assert payload["status"] == "degraded"
    assert payload["note"] == "rc=42"
    assert payload["ts"].endswith("Z")


def test_organism_heartbeat_refuses_path_traversal(tmp_path: Path) -> None:
    module = _load_heartbeat()

    assert not module.organism_heartbeat("../escape", "ok", last_seen_dir=tmp_path)
    assert not (tmp_path.parent / "escape.json").exists()
    assert not list(tmp_path.glob("*.json"))


def test_organism_heartbeat_normalises_unknown_status(tmp_path: Path) -> None:
    module = _load_heartbeat()

    assert module.organism_heartbeat("pro.my_organ", "surprised", last_seen_dir=tmp_path)

    payload = json.loads((tmp_path / "pro.my_organ.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ok"


def test_organism_heartbeat_truncates_note(tmp_path: Path) -> None:
    module = _load_heartbeat()

    assert module.organism_heartbeat("pro.my_organ", "ok", "x" * 800, last_seen_dir=tmp_path)

    payload = json.loads((tmp_path / "pro.my_organ.json").read_text(encoding="utf-8"))
    assert len(payload["note"]) == 500
