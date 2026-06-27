"""Regression test for the restart_agent label resolver (A2 dead-letter cure).

THE BUG (2026-06-27): the supervisor's heartbeat_silent events carry
`agent_ref = "<node>.<organ>"` (organ id, e.g. `pro.dlq_autopilot`) — NOT a
launchd label. The old resolver saw the dot and used the ref as-is, so
`launchctl kickstart gui/<uid>/pro.dlq_autopilot` fired at a non-existent label
→ no-op → the organ stayed dead → re-flagged every tick (W2 restart loop with
zero effect). The genome carries the true label in recovery_params.label; the
fix reads it.

These tests pin the cure: organ_id -> genome label, real labels pass through,
unknown refs fall back to the legacy namespace. If someone reverts to the
"dot == label" heuristic, the GUILT case (pro.dlq_autopilot) fails loudly.
"""
import textwrap

import pytest

from organism.actuators.restart_agent import RestartAgent, _organ_label_map


_GENOME = textwrap.dedent(
    """\
    version: 1
    organs:
      - id: pro.dlq_autopilot
        runtime: pro_launchd
        recovery_action: launchctl_kickstart
        recovery_params:
          label: com.nuzantara.dlq-autopilot
      - id: pro.login_healthcheck
        runtime: pro_launchd
        recovery_params:
          label: com.nuzantara.login-healthcheck
      - id: pro.no_recovery
        runtime: pro_launchd
    """
)


@pytest.fixture()
def genome(tmp_path, monkeypatch):
    p = tmp_path / "organs_registry.yaml"
    p.write_text(_GENOME)
    monkeypatch.setenv("ORGANISM_GENOME_PATH", str(p))
    _organ_label_map.cache_clear()  # the map is lru_cached — clear per test
    yield p
    _organ_label_map.cache_clear()


def test_genome_label_map_loads(genome):
    m = _organ_label_map()
    assert m["pro.dlq_autopilot"] == "com.nuzantara.dlq-autopilot"
    assert m["pro.login_healthcheck"] == "com.nuzantara.login-healthcheck"
    # an organ without recovery_params.label is not in the map
    assert "pro.no_recovery" not in m


def test_organ_id_resolves_to_genome_label(genome):
    """GUILT: the exact bug — an organ id with a dot must NOT be used as-is."""
    ra = RestartAgent()
    assert ra._label("pro.dlq_autopilot") == "com.nuzantara.dlq-autopilot"
    assert ra._label("pro.login_healthcheck") == "com.nuzantara.login-healthcheck"


def test_real_launchd_label_passes_through(genome):
    """INNOCENCE: a genuine launchd label (reverse-DNS) is left untouched."""
    ra = RestartAgent()
    assert ra._label("com.third.party.foo") == "com.third.party.foo"
    assert ra._label("homebrew.mxcl.redis") == "homebrew.mxcl.redis"


def test_unknown_dotless_ref_uses_legacy_namespace(genome):
    """INNOCENCE: legacy convention preserved for bare names."""
    ra = RestartAgent()
    assert ra._label("standalone_agent") == "com.balizero.standalone_agent"


def test_unknown_dotted_ref_not_in_genome_passes_through(genome):
    """An organ-shaped ref absent from the genome and not reverse-DNS:
    falls back to legacy prefixing (defensive — better a wrong label that
    fails loudly than silently swallowing). It must NOT crash."""
    ra = RestartAgent()
    # 'pro.no_recovery' has no label in genome, not a reverse-DNS namespace
    assert ra._label("pro.no_recovery") == "com.balizero.pro.no_recovery"
