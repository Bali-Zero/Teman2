"""Shared fixtures for the autonomous-lab unit tests.

The npm seam lives here because more than one test file needs it and, before
this, each one resolved npm on its own by reading the ambient PATH. That made
them assert WHICH MACHINE they were running on: npm is present on M5 and absent
on Pro and Mini, so three tests failed on every push from the two machines that
have no node toolchain — and Pro is the fleet's overflow lane when M5's pre-push
suite is saturated. Pinning the seam here tests the policy on every machine
instead of skipping it on some.
"""

from __future__ import annotations

import pytest

from backend.services.autonomous_lab import command_policy

# A path, not a machine. The lint binary is never executed by these tests (the
# runner always receives a fake `run_func`), so a fixed string is everything the
# policy needs to plan and to validate an argv.
FAKE_NPM = "/fake/toolchain/bin/npm"


@pytest.fixture
def fake_npm(monkeypatch: pytest.MonkeyPatch) -> str:
    """Pin the one seam that answers "where is npm" for planner and validator."""
    monkeypatch.setattr(command_policy, "npm_executable", lambda: FAKE_NPM)
    return FAKE_NPM


@pytest.fixture
def absent_npm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reproduce Pro and Mini: no node toolchain anywhere on PATH."""
    monkeypatch.setattr(command_policy, "npm_executable", lambda: None)
