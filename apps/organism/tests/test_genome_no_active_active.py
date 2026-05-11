"""W2-C: Guard against active-active enrollment regressions in
organs_registry.yaml (Innervation Genoma — file renamed 2026-05-08 IG-3
from `genome.yaml`).

Cicatrix ref: STRUCTURAL P1 in `.claude/rules/cicatrix-scars.md` line 8 —
13 launchd labels firing simultaneously on Pro + Mini. Once the cleanup PR
ships (this one), no `recovery_params.label` should appear with both
`host: pro` AND `host: mini`. An empty whitelist enforces that.

If a future organ legitimately requires active-active enrollment (e.g.
leader-election with explicit dedup), add the label to ACTIVE_ACTIVE_WHITELIST
with a justification comment. The current state is "no whitelist needed".
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest
import yaml

GENOME_YAML = (
    Path(__file__).resolve().parents[1] / "organism" / "organs_registry.yaml"
)


# Whitelist of labels intentionally enrolled active-active.
# Empty by design — anything sharing host: pro AND host: mini fails CI.
ACTIVE_ACTIVE_WHITELIST: set[str] = set()


def _load_organs() -> list[dict]:
    """Load the 'organs' list from organs_registry.yaml.

    We load the file as raw YAML (without the project's ``Genome.from_yaml``
    helper) to keep the test free of import-time dependencies and to make
    failures point at the YAML directly.
    """
    with GENOME_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        pytest.fail(
            f"organs_registry.yaml root is not a mapping: {type(data).__name__}"
        )

    organs = data.get("organs")
    if not isinstance(organs, list):
        pytest.fail("organs_registry.yaml missing 'organs' list at top level")

    return organs


def _label_host_pairs(organs: list[dict]) -> dict[str, set[str]]:
    """Return mapping of recovery_params.label -> set of hosts seen.

    Only entries that have BOTH ``recovery_params.label`` AND
    ``recovery_params.host`` are considered — those are the ones the
    Supervisor's launchctl_kickstart action consumes.
    """
    by_label: dict[str, set[str]] = defaultdict(set)
    for entry in organs:
        if not isinstance(entry, dict):
            continue
        rp = entry.get("recovery_params") or {}
        if not isinstance(rp, dict):
            continue
        label = rp.get("label")
        host = rp.get("host")
        if not isinstance(label, str) or not isinstance(host, str):
            continue
        by_label[label].add(host)
    return by_label


def test_genome_yaml_loads_cleanly():
    """Sanity guard: malformed YAML would silently skip the next test."""
    organs = _load_organs()
    assert organs, "expected non-empty organs list"


def test_no_active_active_enrollment_outside_whitelist():
    """Fail if any recovery_params.label appears with both pro and mini hosts.

    The 13 mata_garuda labels were ratified by Zero into single-host
    enrollment per W2-C decision matrix. Any regression (a future PR that
    re-introduces a ``host: mini`` entry for a Pro-canonical label, or vice
    versa) must surface here — that's the whole point of the test.
    """
    organs = _load_organs()
    by_label = _label_host_pairs(organs)

    offenders: list[tuple[str, set[str]]] = []
    for label, hosts in by_label.items():
        if "pro" in hosts and "mini" in hosts and label not in ACTIVE_ACTIVE_WHITELIST:
            offenders.append((label, hosts))

    if offenders:
        msg = (
            "Active-active enrollment detected (cicatrix STRUCTURAL P1 regression).\n"
            "Each label below has BOTH host:pro AND host:mini entries in "
            "organs_registry.yaml.\n"
            "Either drop one host or add the label to ACTIVE_ACTIVE_WHITELIST with "
            "a justification.\n\n"
            + "\n".join(f"  - {label}: hosts={sorted(hosts)}" for label, hosts in offenders)
        )
        pytest.fail(msg)


def test_whitelist_entries_are_actually_dual_host():
    """If a label is whitelisted, it must currently appear on BOTH hosts.

    Stale whitelist entries (label removed from organs_registry.yaml but
    kept in the whitelist) would silently mask future regressions. This
    test keeps the whitelist tight.
    """
    if not ACTIVE_ACTIVE_WHITELIST:
        pytest.skip("whitelist empty — nothing to validate")

    organs = _load_organs()
    by_label = _label_host_pairs(organs)

    stale = []
    for label in ACTIVE_ACTIVE_WHITELIST:
        hosts = by_label.get(label, set())
        if not ("pro" in hosts and "mini" in hosts):
            stale.append((label, sorted(hosts)))

    if stale:
        msg = (
            "Whitelist contains stale entries no longer dual-host in "
            "organs_registry.yaml:\n"
            + "\n".join(f"  - {label}: hosts={hosts}" for label, hosts in stale)
        )
        pytest.fail(msg)
