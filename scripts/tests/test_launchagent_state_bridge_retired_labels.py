"""Guilt test: retired launchd labels must not be bridged (2026-10-12).

yield-optimizer.weekly and the three codex-spark labels are unloaded. Bridging
an unloaded label writes a permanent false "failed" sidecar and keeps the
proprioception organs_heartbeat probe red. Same family as the redis-split-brain
and wa_viewer removals in launchagent-state-bridge.py.
"""
import importlib.util
import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

RETIRED_ORGANS = {
    "pro.yield_optimizer_weekly",
    "codex.spark_alarm",
    "codex.spark_harvester",
    "codex.spark_loop",
}
RETIRED_LABELS = {
    "com.balizero.yield-optimizer.weekly",
    "com.nuzantara.codex-spark-alarm",
    "com.nuzantara.codex-spark-harvester",
    "com.nuzantara.codex-spark-loop",
}


@pytest.fixture()
def bridge():
    spec = importlib.util.spec_from_file_location(
        "launchagent_state_bridge_retired_labels",
        os.path.join(_SCRIPTS_DIR, "launchagent-state-bridge.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_retired_organs_not_bridged(bridge):
    declared = {e.organ_id for e in bridge.BRIDGED_LABELS}
    assert not (declared & RETIRED_ORGANS)


def test_retired_labels_not_bridged(bridge):
    declared = {e.label for e in bridge.BRIDGED_LABELS}
    assert not (declared & RETIRED_LABELS)


def test_innocence_live_labels_still_bridged(bridge):
    declared = {e.organ_id for e in bridge.BRIDGED_LABELS}
    assert "infra.ollama_pro" in declared
    assert "codex.openclaw_analysis" in declared
