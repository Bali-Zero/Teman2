#!/usr/bin/env python3
"""Guilt + innocence for `probe_model_topology_drift` (scripts/proprioception.py).

Every case builds a synthetic MODEL_TOPOLOGY.json and a synthetic `ollama list`
stdout — never this machine's real topology or real daemon (superscar #1: a test
on real state passes and fails for the wrong reasons, and this machine has no
ollama at all).

Innocence matters as much as guilt here. A probe that reports drift for a role
naming another door (`agy/...`, `claude --print`) would fire on every run of a
correct fleet, and a probe that reports RECONCILED when ollama is missing would
tell M5 that roles it cannot even evaluate all resolve. Both are in the set.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve()
_SPEC = importlib.util.spec_from_file_location("proprioception", _HERE.parents[1] / "proprioception.py")
assert _SPEC and _SPEC.loader
pp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pp)

_OLLAMA_HEADER = "NAME                    ID              SIZE      MODIFIED\n"


def _fake_ollama(stdout: str, rc: int = 0, raises: type[BaseException] | None = None):
    def _run(cmd, **kw):
        if raises is not None:
            raise raises("synthetic")
        return subprocess.CompletedProcess(cmd, rc, stdout, "boom" if rc else "")
    return _run


def _root(tmp: Path, roles: dict) -> Path:
    (tmp / "MODEL_TOPOLOGY.json").write_text(json.dumps({"roles": roles}))
    return tmp


def _probe(monkey_run, root: Path, *, which: str | None = "/usr/bin/ollama"):
    """Both dependencies are injected: the binary lookup AND the daemon output.

    The lookup is not optional scaffolding — M5 has no ollama, so without it every
    guilt and innocence case here returns UNPROBEABLE and the set proves nothing.
    """
    real_run, real_which = pp.subprocess.run, pp.shutil.which
    pp.subprocess.run, pp.shutil.which = monkey_run, lambda _: which
    try:
        return pp.probe_model_topology_drift(root, {"topology": "MODEL_TOPOLOGY.json"}, 5)
    finally:
        pp.subprocess.run, pp.shutil.which = real_run, real_which


def _listing(*names: str) -> str:
    return _OLLAMA_HEADER + "".join(f"{n}    abc123    6.0 GB    3 months ago\n" for n in names)


def test_guilt_role_names_absent_model():
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), {"reasoning": "deepseek-r1:32b", "fast": "qwen3.5:9b"})
        status, n, ev = _probe(_fake_ollama(_listing("qwen3.5:9b")), root)
    assert status == pp.DIVERGED, ev
    assert n == 1, ev
    assert any("reasoning -> deepseek-r1:32b" in line for line in ev), ev


def test_guilt_counts_every_absent_role_not_just_the_first():
    roles = {f"role{i}": f"ghost{i}:7b" for i in range(5)}
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), roles)
        status, n, ev = _probe(_fake_ollama(_listing("qwen3.5:9b")), root)
    assert status == pp.DIVERGED
    assert n == 5, f"a count of {n} would let four absent roles hide behind one"


def test_guilt_evidence_truncation_says_how_many_it_hid():
    roles = {f"role{i:02d}": f"ghost{i}:7b" for i in range(12)}
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), roles)
        _, n, ev = _probe(_fake_ollama(_listing()), root)
    assert n == 12
    assert any("+4 more unresolvable" in line for line in ev), ev


def test_innocence_every_role_resolves():
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), {"fast": "qwen3.5:9b", "vision": "qwen2.5vl:7b"})
        status, n, ev = _probe(_fake_ollama(_listing("qwen3.5:9b", "qwen2.5vl:7b")), root)
    assert status == pp.RECONCILED, ev
    assert n == 0


def test_innocence_bare_name_resolves_against_latest_tag():
    """`bge-m3` in the topology, `bge-m3:latest` installed — ollama resolves it, so must we."""
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), {"embed": "bge-m3"})
        status, _, ev = _probe(_fake_ollama(_listing("bge-m3:latest")), root)
    assert status == pp.RECONCILED, ev


def test_innocence_roles_naming_other_doors_are_not_judged():
    roles = {
        "swarm_deep_review": "agy/Gemini 3.1 Pro (High)",
        "sentinel_classifier": "claude --print",
        "codex_fix": "codex --full-auto",
        "aider_fix": "openrouter/deepseek/deepseek-chat-v3-0324",
        "cloud_fallback": "google-gemini-cli/gemini-3-flash-preview",
    }
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), roles)
        status, n, ev = _probe(_fake_ollama(_listing()), root)
    assert status == pp.RECONCILED, ev
    assert n == 0, "a non-ollama door is not a missing model"
    assert any("5 roles name other doors" in line for line in ev), ev


def test_unprobeable_when_ollama_is_absent():
    """M5 has no ollama. 'No daemon here' must never be reported as 'all roles resolve'."""
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), {"fast": "qwen3.5:9b"})
        status, n, ev = _probe(_fake_ollama(_listing()), root, which=None)
    assert status == pp.UNPROBEABLE, ev
    assert n == 0


def test_unprobeable_when_ollama_errors():
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), {"fast": "qwen3.5:9b"})
        status, _, ev = _probe(_fake_ollama("", rc=1), root)
    assert status == pp.UNPROBEABLE, ev


def test_unprobeable_when_topology_is_absent_or_empty():
    with tempfile.TemporaryDirectory() as td:
        status, _, _ = _probe(_fake_ollama(_listing()), Path(td))
        assert status == pp.UNPROBEABLE
        root = _root(Path(td), {})
        status, _, _ = _probe(_fake_ollama(_listing()), root)
        assert status == pp.UNPROBEABLE


def test_registered_in_builtins_and_registry():
    assert pp.BUILTINS["model_topology_drift"] is pp.probe_model_topology_drift
    registry, _, _ = pp.load_registry(_HERE.parents[2])
    entry = [p for p in registry if p["id"] == "model_topology_drift"]
    assert entry, "probe not in the registry — it would never run"
    assert entry[0]["machines"] == ["pro", "mini"], "M5 has no ollama; scoping it there is noise"


def test_unprobeable_only_when_no_ollama_binary_exists_anywhere():
    """The PATH of a non-login shell (launchd, `ssh host cmd`) has no /opt/homebrew/bin.

    Found live on pro 2026-09-21: the probe called it absent on a machine holding
    five models. `shutil.which` alone reproduces that bug, so the fallback list is
    what this asserts.
    """
    real_exists = Path.exists
    Path.exists = lambda self: str(self) == "/opt/homebrew/bin/ollama" or real_exists(self)
    try:
        with tempfile.TemporaryDirectory() as td:
            root = _root(Path(td), {"fast": "qwen3.5:9b"})
            status, _, ev = _probe(_fake_ollama(_listing("qwen3.5:9b")), root, which=None)
        assert status == pp.RECONCILED, f"homebrew fallback not used: {ev}"
    finally:
        Path.exists = real_exists


def test_innocence_role_aliasing_another_role_is_not_a_missing_model():
    """`swarm_fast_review -> agy_gemini_flash_high -> agy/...` is an alias chain.

    Found live on mini 2026-09-21: both swarm roles were reported as missing models.
    Superscar #3 OVER-match — the guard judged a string that names a role, not a model.
    """
    roles = {
        "swarm_fast_review": "agy_gemini_flash_high",
        "agy_gemini_flash_high": "agy/Gemini 3.5 Flash (High)",
        "fast": "qwen3.5:9b",
    }
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), roles)
        status, n, ev = _probe(_fake_ollama(_listing("qwen3.5:9b")), root)
    assert status == pp.RECONCILED, ev
    assert n == 0, "an alias to a role that names another door is not a missing model"


def test_guilt_alias_to_an_absent_model_still_fires_and_shows_the_chain():
    """Resolving aliases must not become a way to launder an absent model."""
    roles = {"cell_tier1": "big_local", "big_local": "gemma4:26b"}
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), roles)
        status, n, ev = _probe(_fake_ollama(_listing("qwen3.5:9b")), root)
    assert status == pp.DIVERGED, ev
    assert any("cell_tier1 -> big_local -> gemma4:26b" in line for line in ev), ev


def test_alias_cycle_terminates():
    with tempfile.TemporaryDirectory() as td:
        root = _root(Path(td), {"a": "b", "b": "a"})
        status, _, _ = _probe(_fake_ollama(_listing()), root)
    assert status in (pp.DIVERGED, pp.RECONCILED)
