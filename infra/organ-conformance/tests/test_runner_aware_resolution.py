"""Proof that content genes are resolved behind explicit generic runners."""

from __future__ import annotations

import importlib.util
import plistlib
import shutil
import subprocess
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

FLEET_CHECKOUT_ROOTS = (
    Path("/Users/nuzantara/nuzantara"),
    Path("/Users/balizero/nuzantara"),
)


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


def _write_runner_tree(repo: Path, payload_body: str = GOOD_WRAPPER) -> None:
    for relative in ("scripts", "apps/foo", "infra/launchagents"):
        (repo / relative).mkdir(parents=True, exist_ok=True)
    _write_script(repo, "scripts/cron-runner.sh", BAD_WRAPPER)
    _write_script(repo, "apps/foo/payload.sh", payload_body)


def _analyze(fixture_repo: Path, argv: list[str]) -> dict[str, Any]:
    plist_path = fixture_repo / "infra/launchagents/com.test.runner-aware.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
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


@pytest.mark.parametrize(
    "runner_token",
    [
        "scripts/cron-runner.sh",
        "./scripts/cron-runner.sh",
        pytest.param(None, id="absolute-inside-repo"),
    ],
)
def test_innocence_legitimate_runner_spellings_use_payload_genes(
    fixture_repo: Path,
    runner_token: str | None,
) -> None:
    runner = _write_script(fixture_repo, "scripts/cron-runner.sh", BAD_WRAPPER)
    payload = _write_script(fixture_repo, "apps/foo/payload.sh", GOOD_WRAPPER)

    organ = _analyze(
        fixture_repo,
        ["/bin/bash", runner_token or str(runner), str(payload)],
    )

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


def test_guilt_external_payload_basename_collision_stays_fail_closed(
    fixture_repo: Path,
    tmp_path: Path,
) -> None:
    runner = _write_script(fixture_repo, "scripts/cron-runner.sh", GOOD_WRAPPER)
    _write_script(fixture_repo, "apps/foo/run.sh", GOOD_WRAPPER)
    external_payload = tmp_path / "outside" / "run.sh"
    external_payload.parent.mkdir()
    external_payload.write_text(BAD_WRAPPER, encoding="utf-8")

    organ = _analyze(
        fixture_repo,
        ["/bin/bash", str(runner), str(external_payload)],
    )

    assert "wrapper" not in organ
    assert {"G2_heartbeat", "G5_kill_switch"} <= set(organ["missing"])
    assert any(
        f"known-runner payload not-resolvable-in-repo: {external_payload}" in note
        for note in organ["notes"]
    )


def test_guilt_duplicate_runner_basename_does_not_hide_real_runner(
    fixture_repo: Path,
) -> None:
    decoy = _write_script(
        fixture_repo,
        "apps/aaa/cron-runner.sh",
        GOOD_WRAPPER,
    )
    runner = _write_script(fixture_repo, "scripts/cron-runner.sh", GOOD_WRAPPER)
    payload = _write_script(fixture_repo, "apps/foo/payload.sh", BAD_WRAPPER)
    assert str(decoy) < str(runner)

    organ = _analyze(fixture_repo, ["/bin/bash", str(runner), str(payload)])

    assert organ["wrapper"] == "apps/foo/payload.sh"
    assert {"G2_heartbeat", "G5_kill_switch"} <= set(organ["missing"])


@pytest.mark.parametrize("via_symlink", [False, True])
def test_innocence_runner_normalizes_dotdot_and_symlinks(
    fixture_repo: Path,
    via_symlink: bool,
) -> None:
    _write_script(fixture_repo, "scripts/cron-runner.sh", BAD_WRAPPER)
    payload = _write_script(fixture_repo, "apps/foo/payload.sh", GOOD_WRAPPER)
    if via_symlink:
        runner_alias = fixture_repo / "apps/runner-link.sh"
        runner_alias.symlink_to("../scripts/cron-runner.sh")
        runner_token = "apps/runner-link.sh"
    else:
        runner_token = "apps/foo/../../scripts/cron-runner.sh"

    organ = _analyze(
        fixture_repo,
        ["/bin/bash", runner_token, str(payload)],
    )

    assert organ["wrapper"] == "apps/foo/payload.sh"
    assert "G2_heartbeat" not in organ["missing"]
    assert "G5_kill_switch" not in organ["missing"]


def test_innocence_canonical_checkout_alias_maps_exact_paths_to_worktree(
    fixture_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_script(fixture_repo, "scripts/cron-runner.sh", BAD_WRAPPER)
    _write_script(fixture_repo, "apps/foo/payload.sh", GOOD_WRAPPER)
    canonical_checkout = tmp_path / "canonical-checkout"
    monkeypatch.setattr(
        coc,
        "_repo_alias_roots",
        lambda repo_root: (repo_root.resolve(), canonical_checkout.resolve()),
    )

    organ = _analyze(
        fixture_repo,
        [
            "/bin/bash",
            str(canonical_checkout / "scripts/cron-runner.sh"),
            str(canonical_checkout / "apps/foo/payload.sh"),
        ],
    )

    assert organ["wrapper"] == "apps/foo/payload.sh"
    assert "G2_heartbeat" not in organ["missing"]
    assert "G5_kill_switch" not in organ["missing"]


@pytest.mark.parametrize("canonical_checkout", FLEET_CHECKOUT_ROOTS)
def test_guilt_canonical_fleet_runner_uses_payload_under_synthetic_root(
    fixture_repo: Path,
    canonical_checkout: Path,
) -> None:
    """The old verdict inspected cron-runner under a non-alias root.

    fixture_repo is intentionally not a linked worktree of this repository,
    so no git-common-dir accident can make the canonical fleet path resolvable.
    """
    _write_runner_tree(fixture_repo)

    organ = _analyze(
        fixture_repo,
        [
            "/bin/bash",
            str(canonical_checkout / "scripts/cron-runner.sh"),
            str(canonical_checkout / "apps/foo/payload.sh"),
        ],
    )

    assert organ["wrapper"] == "apps/foo/payload.sh"
    assert "G2_heartbeat" not in organ["missing"]
    assert "G5_kill_switch" not in organ["missing"]


def test_innocence_fleet_alias_set_is_small_exact_and_auditable() -> None:
    assert coc.CANONICAL_FLEET_CHECKOUT_ROOTS == FLEET_CHECKOUT_ROOTS


def test_innocence_canonical_fleet_payload_without_gene_still_fails(
    fixture_repo: Path,
) -> None:
    _write_runner_tree(fixture_repo, payload_body=BAD_WRAPPER)

    organ = _analyze(
        fixture_repo,
        [
            "/bin/bash",
            "/Users/nuzantara/nuzantara/scripts/cron-runner.sh",
            "/Users/nuzantara/nuzantara/apps/foo/payload.sh",
        ],
    )

    assert organ["wrapper"] == "apps/foo/payload.sh"
    assert {"G2_heartbeat", "G5_kill_switch"} <= set(organ["missing"])


def test_guilt_missing_canonical_fleet_payload_stays_fail_closed_and_names_token(
    fixture_repo: Path,
) -> None:
    _write_runner_tree(fixture_repo)
    missing_token = "/Users/nuzantara/nuzantara/apps/foo/missing.sh"

    organ = _analyze(
        fixture_repo,
        [
            "/bin/bash",
            "/Users/nuzantara/nuzantara/scripts/cron-runner.sh",
            missing_token,
        ],
    )

    assert "wrapper" not in organ
    assert {"G2_heartbeat", "G5_kill_switch"} <= set(organ["missing"])
    assert any(missing_token in note for note in organ["notes"])


@pytest.mark.parametrize(
    "external_token",
    [
        "/opt/homebrew/bin/something",
        "/Users/nuzantara/other-repo/x.sh",
    ],
)
def test_innocence_external_absolute_tokens_are_not_fleet_aliases(
    fixture_repo: Path,
    external_token: str,
) -> None:
    _write_script(fixture_repo, f"apps/foo/{Path(external_token).name}", GOOD_WRAPPER)
    ka_mod = coc._load_keepalive_module(REPO_ROOT)

    resolved = coc._resolve_repo_file_strict(external_token, fixture_repo, ka_mod)

    assert resolved is None


def test_verdict_is_identical_from_main_linked_and_synthetic_roots(
    tmp_path: Path,
) -> None:
    """One closed fixture tree has one verdict, independent of git topology."""
    main_checkout = tmp_path / "main-checkout"
    _write_runner_tree(main_checkout)
    subprocess.run(["git", "init", "-q", str(main_checkout)], check=True)
    subprocess.run(
        ["git", "-C", str(main_checkout), "add", "-A"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(main_checkout),
            "-c",
            "user.name=Organ Conformance Test",
            "-c",
            "user.email=organ-conformance@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )

    linked_worktree = tmp_path / "linked-worktree"
    subprocess.run(
        [
            "git",
            "-C",
            str(main_checkout),
            "worktree",
            "add",
            "--detach",
            str(linked_worktree),
            "HEAD",
        ],
        check=True,
        capture_output=True,
    )

    synthetic_root = tmp_path / "synthetic-root"
    shutil.copytree(
        main_checkout,
        synthetic_root,
        ignore=shutil.ignore_patterns(".git"),
    )
    subprocess.run(["git", "init", "-q", str(synthetic_root)], check=True)

    argv = [
        "/bin/bash",
        "/Users/nuzantara/nuzantara/scripts/cron-runner.sh",
        "/Users/nuzantara/nuzantara/apps/foo/payload.sh",
    ]
    verdicts = [
        _analyze(root, argv)
        for root in (main_checkout, linked_worktree, synthetic_root)
    ]

    assert [
        (verdict.get("wrapper"), verdict["missing"], verdict["notes"])
        for verdict in verdicts
    ] == [("apps/foo/payload.sh", [], [])] * 3
