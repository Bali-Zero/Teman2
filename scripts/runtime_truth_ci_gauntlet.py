#!/usr/bin/env python3
"""Execute the four Runtime Truth incident contracts fail-closed.

The workflow delegates to this harness instead of invoking pytest directly so
the check can prove that tests were collected *and* executed.  Pytest returning
zero is insufficient: collection-only runs, skips, importorskip, and expected
failures all violate this contract.
"""

from __future__ import annotations

import collections
import dataclasses
import logging
import os
import pathlib
import subprocess
import sys
from collections.abc import Sequence
from typing import Final

import pytest

REPO_ROOT: Final = pathlib.Path(__file__).resolve().parents[1]

PYTEST_TARGETS: Final[tuple[str, ...]] = (
    "apps/evaluator/nlm_deep_research/tests/test_run_verdict.py",
    "scripts/tests/test_launchd_liveness_expected_nonzero.py",
    "scripts/tests/test_proprioception_run_wrap_exit_code.py",
    "scripts/tests/test_runtime_truth_ci_gauntlet.py",
)
SHELL_TARGETS: Final[tuple[str, ...]] = (
    "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh",
)
PYTEST_OPTIONS: Final[tuple[str, ...]] = ("-q", "--strict-markers")

LOGGER = logging.getLogger("runtime-truth-ci-gauntlet")


class GauntletContractError(RuntimeError):
    """The runner could not prove that every incident contract executed."""


@dataclasses.dataclass(eq=False)
class PytestEvidence:
    """Evidence captured from pytest hooks, independent of terminal text."""

    repo_root: pathlib.Path
    collected_by_file: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    executed_by_file: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    skipped_by_file: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    collected_nodeids: set[str] = dataclasses.field(default_factory=set)
    executed_nodeids: set[str] = dataclasses.field(default_factory=set)
    skipped_reports: set[str] = dataclasses.field(default_factory=set)
    xfail_reports: set[str] = dataclasses.field(default_factory=set)

    def _relative_path(self, path: pathlib.Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.repo_root.resolve()).as_posix()
        except ValueError:
            return resolved.as_posix()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Record the concrete files and node IDs pytest collected."""
        for item in session.items:
            relative_path = self._relative_path(pathlib.Path(item.path))
            self.collected_by_file[relative_path] += 1
            self.collected_nodeids.add(item.nodeid)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        """Capture module-level importorskip and other collection skips."""
        if report.skipped:
            self.skipped_reports.add(f"collection:{report.nodeid}")
            collection_path = report.nodeid.split("::", maxsplit=1)[0]
            if collection_path:
                path = pathlib.Path(collection_path)
                if not path.is_absolute():
                    path = self.repo_root / path
                self.skipped_by_file[self._relative_path(path)] += 1

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Record actual call phases and every runtime skip/xfail outcome."""
        report_path = pathlib.Path(report.location[0])
        if not report_path.is_absolute():
            report_path = self.repo_root / report_path
        relative_path = self._relative_path(report_path)
        if report.when == "call":
            self.executed_nodeids.add(report.nodeid)
            self.executed_by_file[relative_path] += 1
        if report.skipped:
            self.skipped_reports.add(f"{report.when}:{report.nodeid}")
            self.skipped_by_file[relative_path] += 1
        if getattr(report, "wasxfail", None):
            self.xfail_reports.add(f"{report.when}:{report.nodeid}")


def _validate_targets(repo_root: pathlib.Path, targets: Sequence[str]) -> None:
    if not targets:
        raise GauntletContractError("pytest target manifest is empty")
    if len(targets) != len(set(targets)):
        raise GauntletContractError("pytest target manifest contains duplicates")
    wildcard_targets = sorted(path for path in targets if "*" in path)
    if wildcard_targets:
        raise GauntletContractError(
            f"pytest target manifest contains wildcards: {wildcard_targets}"
        )
    missing = sorted(path for path in targets if not (repo_root / path).is_file())
    if missing:
        raise GauntletContractError(f"mandatory pytest targets missing: {missing}")


def validate_pytest_evidence(
    evidence: PytestEvidence,
    targets: Sequence[str],
    exit_code: int,
) -> None:
    """Reject any result that does not prove every collected test executed."""
    errors: list[str] = []
    expected_files = set(targets)
    collected_files = set(evidence.collected_by_file)

    if exit_code != 0:
        errors.append(f"pytest exit_code={exit_code}")
    if not evidence.collected_nodeids:
        errors.append("pytest collected zero tests")

    missing_files = sorted(expected_files - collected_files)
    if missing_files:
        errors.append(f"targets with zero collected tests={missing_files}")

    unexpected_files = sorted(collected_files - expected_files)
    if unexpected_files:
        errors.append(f"tests collected outside exact manifest={unexpected_files}")

    unexecuted = sorted(evidence.collected_nodeids - evidence.executed_nodeids)
    if unexecuted:
        errors.append(f"collected but not executed={unexecuted}")

    if evidence.skipped_reports:
        errors.append(f"skipped={sorted(evidence.skipped_reports)}")
    if evidence.xfail_reports:
        errors.append(f"xfail/xpass={sorted(evidence.xfail_reports)}")

    for target in targets:
        collected = evidence.collected_by_file[target]
        executed = evidence.executed_by_file[target]
        skipped = evidence.skipped_by_file[target]
        if executed != collected or skipped:
            errors.append(
                f"per-file evidence {target}: collected={collected} "
                f"executed={executed} skipped={skipped}"
            )

    if errors:
        raise GauntletContractError("; ".join(errors))


def run_pytest_contract(
    *,
    repo_root: pathlib.Path,
    targets: Sequence[str],
    extra_options: Sequence[str] = (),
) -> PytestEvidence:
    """Run pytest and return evidence only after the fail-closed contract passes."""
    _validate_targets(repo_root, targets)
    evidence = PytestEvidence(repo_root=repo_root)
    args = [
        *(str((repo_root / path).resolve()) for path in targets),
        "--rootdir",
        str(repo_root.resolve()),
        "-c",
        os.devnull,
        *PYTEST_OPTIONS,
        *extra_options,
    ]

    previous_addopts = os.environ.get("PYTEST_ADDOPTS")
    previous_autoload = os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
    previous_pythonpath = os.environ.get("PYTHONPATH")
    previous_sys_path = sys.path.copy()
    os.environ["PYTEST_ADDOPTS"] = ""
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (str(repo_root.resolve()), previous_pythonpath)
        if part
    )
    sys.path.insert(0, str(repo_root.resolve()))
    try:
        exit_code = int(pytest.main(args, plugins=[evidence]))
    finally:
        sys.path[:] = previous_sys_path
        if previous_addopts is None:
            os.environ.pop("PYTEST_ADDOPTS", None)
        else:
            os.environ["PYTEST_ADDOPTS"] = previous_addopts
        if previous_autoload is None:
            os.environ.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
        else:
            os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = previous_autoload
        if previous_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = previous_pythonpath

    validate_pytest_evidence(evidence, targets, exit_code)
    return evidence


def _prepare_hermetic_directories() -> None:
    missing_names = [name for name in ("HOME", "TMPDIR") if not os.environ.get(name)]
    if missing_names:
        raise GauntletContractError(
            f"workflow must provide hermetic environment variables: {missing_names}"
        )
    for name in ("HOME", "TMPDIR"):
        pathlib.Path(os.environ[name]).mkdir(parents=True, exist_ok=True)


def run_shell_contracts(repo_root: pathlib.Path) -> None:
    for relative_path in SHELL_TARGETS:
        target = repo_root / relative_path
        if not target.is_file():
            raise GauntletContractError(f"mandatory shell target missing: {relative_path}")
        completed = subprocess.run(
            ["bash", str(target)],
            cwd=repo_root,
            env=os.environ.copy(),
            check=False,
        )
        if completed.returncode != 0:
            raise GauntletContractError(
                f"shell contract failed: {relative_path} exit_code={completed.returncode}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if arguments:
            raise GauntletContractError(
                f"runner accepts no CLI arguments; exact manifest is internal: {arguments}"
            )
        _prepare_hermetic_directories()
        evidence = run_pytest_contract(
            repo_root=REPO_ROOT,
            targets=PYTEST_TARGETS,
        )
        run_shell_contracts(REPO_ROOT)
    except GauntletContractError as exc:
        LOGGER.error("RUNTIME_TRUTH_FAIL %s", exc)
        return 1

    LOGGER.info(
        "RUNTIME_TRUTH_PASS files=%d collected=%d executed=%d skipped=0 shell=%d",
        len(evidence.collected_by_file),
        len(evidence.collected_nodeids),
        len(evidence.executed_nodeids),
        len(SHELL_TARGETS),
    )
    for target in PYTEST_TARGETS:
        LOGGER.info(
            "RUNTIME_TRUTH_FILE path=%s collected=%d executed=%d skipped=%d",
            target,
            evidence.collected_by_file[target],
            evidence.executed_by_file[target],
            evidence.skipped_by_file[target],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
