"""Proof that content genes are resolved behind explicit generic runners."""

from __future__ import annotations

import importlib.util
import plistlib
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parent.parent

_SPEC = importlib.util.spec_from_file_location(
    "check_organ_conformance_runner_tests", HERE / "check_organ_conformance.py"
)
assert _SPEC is not None and _SPEC.loader is not None
coc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(coc)

GOOD_WRAPPER = """#!/bin/bash
set -u
[ "${TEST_ORGAN_ENABLED:-true}" = "false" ] && exit 0
heartbeat() {
    :
}
"""

BAD_WRAPPER = """#!/bin/bash
echo "no content genes"
"""


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for relative in ("scripts", "apps/foo", "infra/launchagents"):
        (repo / relative).mkdir(parents=True)
    return repo


def _write_script(repo: Path, relative: str, content: str) -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _analyze(fixture_repo: Path, argv: list[str]) -> dict[str, Any]:
    plist_path = fixture_repo / "infra/launchagents/com.test.runner-aware.plist"
    label = "com.test.runner-aware"
    plist_path.write_bytes(plistlib.dumps({"Label": label, "ProgramArguments": argv}))
    ka_mod = coc._load_keepalive_module(REPO_ROOT)
    basename_index = ka_mod.build_basename_index(
        [fixture_repo / "scripts", fixture_repo / "apps", fixture_repo / "infra"],
        [],
    )
    return coc.analyze_plist(
        plist_path,
        fixture_repo,
        ka_mod,
        basename_index,
        registry_text=label,
        pairs={"pairs": []},
        keepalive_failed=set(),
    )


def test_guilt_runner_with_gene_less_payload_flags_payload(fixture_repo: Path) -> None:
    runner = _write_script(fixture_repo, "scripts/cron-runner.sh", GOOD_WRAPPER)
    payload = _write_script(fixture_repo, "apps/foo/payload.sh", BAD_WRAPPER)

    organ = _analyze(fixture_repo, ["/bin/bash", str(runner), str(payload)])

    assert organ["wrapper"] == "apps/foo/payload.sh"
    assert "cron-runner.sh" not in organ["wrapper"]
    assert {"G2_heartbeat", "G5_kill_switch"} <= set(organ["missing"])


def test_innocence_runner_with_compliant_payload_uses_payload(
    fixture_repo: Path,
) -> None:
    runner = _write_script(fixture_repo, "scripts/cron-runner.sh", BAD_WRAPPER)
    payload = _write_script(fixture_repo, "apps/foo/payload.sh", GOOD_WRAPPER)

    organ = _analyze(fixture_repo, ["/bin/bash", str(runner), str(payload)])

    assert organ["wrapper"] == "apps/foo/payload.sh"
    assert "G2_heartbeat" not in organ["missing"]
    assert "G5_kill_switch" not in organ["missing"]


def test_innocence_non_runner_wrapper_keeps_current_resolution(
    fixture_repo: Path,
) -> None:
    wrapper = _write_script(fixture_repo, "scripts/some-wrapper.sh", GOOD_WRAPPER)
    ignored = _write_script(fixture_repo, "apps/foo/ignored.sh", BAD_WRAPPER)

    organ = _analyze(fixture_repo, ["/bin/bash", str(wrapper), str(ignored)])

    assert organ["wrapper"] == "scripts/some-wrapper.sh"
    assert "G2_heartbeat" not in organ["missing"]
    assert "G5_kill_switch" not in organ["missing"]


def test_overmatch_same_basename_at_other_path_is_not_runner(
    fixture_repo: Path,
) -> None:
    wrapper = _write_script(fixture_repo, "apps/foo/cron-runner.sh", GOOD_WRAPPER)
    ignored = _write_script(fixture_repo, "apps/foo/ignored.sh", BAD_WRAPPER)

    organ = _analyze(fixture_repo, ["/bin/bash", str(wrapper), str(ignored)])

    assert organ["wrapper"] == "apps/foo/cron-runner.sh"
    assert "G2_heartbeat" not in organ["missing"]
    assert "G5_kill_switch" not in organ["missing"]


def test_runner_only_analyzes_runner_itself(fixture_repo: Path) -> None:
    runner = _write_script(fixture_repo, "scripts/cron-runner.sh", GOOD_WRAPPER)

    organ = _analyze(fixture_repo, ["/bin/bash", str(runner)])

    assert organ["wrapper"] == "scripts/cron-runner.sh"
    assert "G2_heartbeat" not in organ["missing"]
    assert "G5_kill_switch" not in organ["missing"]


def test_unresolvable_first_payload_after_runner_stays_fail_closed(
    fixture_repo: Path,
) -> None:
    runner = _write_script(fixture_repo, "scripts/cron-runner.sh", GOOD_WRAPPER)
    decoy = _write_script(fixture_repo, "apps/foo/decoy.sh", GOOD_WRAPPER)
    missing_payload = fixture_repo / "apps/foo/missing.sh"

    organ = _analyze(
        fixture_repo,
        ["/bin/bash", str(runner), str(missing_payload), str(decoy)],
    )

    assert "wrapper" not in organ
    assert {"G2_heartbeat", "G5_kill_switch"} <= set(organ["missing"])
    assert any("known-runner payload not-resolvable" in note for note in organ["notes"])
