"""Tests for launchagent-state-bridge's infra.ollama_pro label (2026-08-31).

Root cause this pins shut: BRIDGED_LABELS mapped organ_id="infra.ollama_pro"
to label="homebrew.mxcl.ollama" — a launchd job that was NOT loaded on Pro.
The live Ollama daemon actually runs under a different label,
"com.nuzantara.ollama" (ProgramArguments: ollama-single-manager.sh), which
exists to own the port-collision/two-program-paths problem the 2026-06-28
triage in organism_stale_detector.py describes. Verified live 2026-08-31:
`launchctl list "homebrew.mxcl.ollama"` -> "Could not find service", while
`launchctl list | grep -i ollama` showed only "com.nuzantara.ollama" running,
and `curl :11434/api/tags` answered 200 with a live model list.

Consequence of the stale mapping: infra.ollama_pro reported "failed" forever
(a false alarm, allow-listed in organism_stale_detector.KNOWN_BENIGN_FAILED
to suppress the noise) AND the actually-live daemon had zero organism
coverage under any name — a real future death of com.nuzantara.ollama would
have gone unreported. Repoint fixes both; this test pins the mapping so a
future edit cannot silently point it back at the retired label.

Reads the bridge's own declared BRIDGED_LABELS tuple rather than grepping
source text, so it fails if the mapping regresses regardless of how the
source line is formatted.

The module name is loaded via importlib (hyphenated filename), mirroring
test_launchagent_state_bridge_host_guard.py / _tcp_retry.py.
"""
import importlib.util
import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

RETIRED_HOMEBREW_LABEL = "homebrew.mxcl.ollama"
LIVE_LABEL = "com.nuzantara.ollama"
ORGAN_ID = "infra.ollama_pro"


@pytest.fixture()
def bridge():
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "launchagent_state_bridge_ollama_label",
        os.path.join(_SCRIPTS_DIR, "launchagent-state-bridge.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # dataclasses + `from __future__ import annotations` resolves string
    # annotations via sys.modules[cls.__module__] — the module must be
    # registered there before exec_module() runs the class bodies.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestOllamaProLabel:
    def test_infra_ollama_pro_entry_exists(self, bridge):
        matches = [e for e in bridge.BRIDGED_LABELS if e.organ_id == ORGAN_ID]
        assert len(matches) == 1, (
            f"expected exactly one BRIDGED_LABELS entry for {ORGAN_ID!r}, "
            f"found {len(matches)}"
        )

    def test_infra_ollama_pro_does_not_watch_the_retired_homebrew_label(self, bridge):
        """The regression this test exists for: BRIDGED_LABELS pointing
        infra.ollama_pro at a launchd label that is never loaded on Pro."""
        entry = next(e for e in bridge.BRIDGED_LABELS if e.organ_id == ORGAN_ID)
        assert entry.label != RETIRED_HOMEBREW_LABEL

    def test_infra_ollama_pro_watches_the_live_label(self, bridge):
        entry = next(e for e in bridge.BRIDGED_LABELS if e.organ_id == ORGAN_ID)
        assert entry.label == LIVE_LABEL

    def test_no_duplicate_coverage_of_the_live_label(self, bridge):
        """Only one BRIDGED_LABELS entry should watch the live ollama label —
        a second entry would mean this repoint created duplicate coverage
        instead of fixing the existing one."""
        matches = [e for e in bridge.BRIDGED_LABELS if e.label == LIVE_LABEL]
        assert len(matches) == 1
