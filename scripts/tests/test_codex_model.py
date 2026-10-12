"""codex model pin: one resolver, and every production `codex exec` carries -m."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("codex_model", SCRIPTS / "codex_model.py")
codex_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex_model)


def _topology(tmp_path: Path, **kw) -> Path:
    p = tmp_path / "FLEET_TOPOLOGY.json"
    p.write_text(json.dumps(kw), encoding="utf-8")
    return p


def test_env_wins_over_topology(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_MODEL", "from-env")
    assert codex_model.resolve_codex_model(_topology(tmp_path, codex_model="from-topo")) == "from-env"


def test_topology_wins_over_default(monkeypatch, tmp_path):
    monkeypatch.delenv("CODEX_MODEL", raising=False)
    assert codex_model.resolve_codex_model(_topology(tmp_path, codex_model="from-topo")) == "from-topo"


def test_default_when_both_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("CODEX_MODEL", raising=False)
    assert codex_model.resolve_codex_model(_topology(tmp_path)) == codex_model.DEFAULT_MODEL
    assert codex_model.resolve_codex_model(tmp_path / "missing.json") == codex_model.DEFAULT_MODEL


def test_empty_env_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_MODEL", "  ")
    assert codex_model.resolve_codex_model(_topology(tmp_path, codex_model="from-topo")) == "from-topo"


def test_repo_topology_pins_the_default():
    topo = json.loads((SCRIPTS.parent / "FLEET_TOPOLOGY.json").read_text(encoding="utf-8"))
    assert topo["codex_model"] == codex_model.DEFAULT_MODEL


def test_every_codex_exec_in_production_callers_carries_pin():
    invocation = re.compile(r"""["']codex["'],\s*["']exec["']|\bcodex exec\b""")
    for name in ("auth_sentinel.py", "supervisor_autofix_tier2.sh"):
        lines = (SCRIPTS / name).read_text(encoding="utf-8").splitlines()
        calls = [i for i, ln in enumerate(lines)
                 if invocation.search(ln) and not ln.lstrip().startswith(("#", "log "))
                 and "DRY_RUN" not in ln and "tie-break" not in ln]
        assert calls, f"{name}: no codex exec invocation found"
        for i in calls:
            assert re.search(r"""["' ]-m["' ,]""", lines[i]), f"{name}:{i + 1} codex exec without -m"
