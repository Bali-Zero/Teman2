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
import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from typing import Final

import pytest

REPO_ROOT: Final = pathlib.Path(__file__).resolve().parents[1]

PYTEST_TARGETS: Final[tuple[str, ...]] = (
    "apps/evaluator/nlm_deep_research/tests/test_run_verdict.py",
    "scripts/tests/test_launchd_liveness_expected_nonzero.py",
    "scripts/tests/test_proprioception_run_wrap_exit_code.py",
)
SHELL_TARGETS: Final[tuple[str, ...]] = (
    "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh",
)
SHELL_CASES: Final[dict[str, tuple[str, ...]]] = {
    "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh": (
        "pg_proxy_unreachable",
        "database_url_local_missing",
        "pg_proxy_reachable",
        "heartbeat_self_heal",
    ),
}
PYTEST_OPTIONS: Final[tuple[str, ...]] = ("-q", "--strict-markers")
WR2_WRAPPER_RELATIVE: Final = "scripts/wr2-cron-wrapper.sh"
WR2_HEARTBEAT_RELATIVE: Final = "scripts/lib/heartbeat.sh"
WR2_TEST_MODULE: Final = "some.module"
WR2_GUARD_ORGAN_ID: Final = f"pro.wr2_wrapper_guard.{WR2_TEST_MODULE}"

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
    xfail_by_file: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    xpass_by_file: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    collected_nodeids: set[str] = dataclasses.field(default_factory=set)
    executed_nodeids: set[str] = dataclasses.field(default_factory=set)
    skipped_reports: set[str] = dataclasses.field(default_factory=set)
    xfail_reports: set[str] = dataclasses.field(default_factory=set)
    xpass_reports: set[str] = dataclasses.field(default_factory=set)

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
            if report.skipped:
                self.xfail_reports.add(f"{report.when}:{report.nodeid}")
                self.xfail_by_file[relative_path] += 1
            else:
                self.xpass_reports.add(f"{report.when}:{report.nodeid}")
                self.xpass_by_file[relative_path] += 1


@dataclasses.dataclass(frozen=True)
class ShellCaseEvidence:
    """Outcome observed by the parent from wrapper exit state and sidecar state."""

    case_id: str
    exit_code: int
    expected_exit_code: int
    sidecar_status: str
    expected_sidecar_status: str
    precondition_exit_code: int | None = None
    expected_precondition_exit_code: int | None = None
    precondition_sidecar_status: str | None = None
    expected_precondition_sidecar_status: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.exit_code == self.expected_exit_code
            and self.sidecar_status == self.expected_sidecar_status
            and self.precondition_exit_code == self.expected_precondition_exit_code
            and self.precondition_sidecar_status
            == self.expected_precondition_sidecar_status
        )


@dataclasses.dataclass(frozen=True)
class ShellEvidence:
    """Independent parent observations for every expected shell case."""

    target: str
    expected_cases: tuple[str, ...]
    cases: tuple[ShellCaseEvidence, ...]

    @property
    def collected(self) -> int:
        return len(self.expected_cases)

    @property
    def executed(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(case.passed for case in self.cases)

    @property
    def failed(self) -> int:
        return sum(not case.passed for case in self.cases)

    @property
    def skipped(self) -> int:
        return self.collected - self.executed


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
        errors.append(f"xfail={sorted(evidence.xfail_reports)}")
    if evidence.xpass_reports:
        errors.append(f"xpass={sorted(evidence.xpass_reports)}")

    for target in targets:
        collected = evidence.collected_by_file[target]
        executed = evidence.executed_by_file[target]
        skipped = evidence.skipped_by_file[target]
        xfailed = evidence.xfail_by_file[target]
        xpassed = evidence.xpass_by_file[target]
        if executed != collected or skipped or xfailed or xpassed:
            errors.append(
                f"per-file evidence {target}: collected={collected} "
                f"executed={executed} skipped={skipped} "
                f"xfail={xfailed} xpass={xpassed}"
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


def _write_executable(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _sidecar_status(path: pathlib.Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "<missing-or-invalid>"
    status = payload.get("status") if isinstance(payload, dict) else None
    return status if isinstance(status, str) else "<missing-or-invalid>"


def _set_nc_exit(world: pathlib.Path, exit_code: int) -> None:
    _write_executable(
        world / "bin/nc",
        f"#!/usr/bin/env sh\nexit {exit_code}\n",
    )


def _prepare_wr2_world(
    *,
    repo_root: pathlib.Path,
    world: pathlib.Path,
    nc_exit: int,
    database_url_present: bool,
) -> tuple[pathlib.Path, pathlib.Path, dict[str, str]]:
    """Create a hermetic wrapper world owned by the Python observer."""
    wrapper_source = repo_root / WR2_WRAPPER_RELATIVE
    heartbeat_source = repo_root / WR2_HEARTBEAT_RELATIVE
    missing = [
        path.relative_to(repo_root).as_posix()
        for path in (wrapper_source, heartbeat_source)
        if not path.is_file()
    ]
    if missing:
        raise GauntletContractError(f"mandatory WR2 subjects missing: {missing}")

    wrapper = world / "scripts/wr2-cron-wrapper.sh"
    heartbeat = world / "repo/scripts/lib/heartbeat.sh"
    fake_python = world / "repo/apps/backend-rag/.venv/bin/python"
    for directory in (
        wrapper.parent,
        heartbeat.parent,
        fake_python.parent,
        world / "bin",
        world / "logs",
        world / "organism",
        world / "tmp",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wrapper_source, wrapper)
    shutil.copy2(heartbeat_source, heartbeat)
    _write_executable(fake_python, "#!/usr/bin/env sh\nexit 0\n")
    _set_nc_exit(world, nc_exit)

    secrets = world / "secrets.env"
    secrets.write_text(
        (
            "DATABASE_URL_LOCAL=postgres://x@127.0.0.1:15432/y\n"
            if database_url_present
            else ""
        ),
        encoding="utf-8",
    )
    sidecar = world / f"organism/{WR2_GUARD_ORGAN_ID}.json"
    wrapper_env = os.environ.copy()
    wrapper_env.pop("RUNTIME_TRUTH_EVIDENCE_FD", None)
    wrapper_env.update(
        {
            "NUZANTARA_REPO_ROOT": str(world / "repo"),
            "NUZANTARA_SECRETS": str(secrets),
            "ORGANISM_LAST_SEEN_DIR": str(world / "organism"),
            "WR2_LOG_DIR": str(world / "logs"),
            "WR2_CRON_ALERT": "false",
            "PATH": os.pathsep.join((str(world / "bin"), wrapper_env.get("PATH", ""))),
            "HOME": str(world),
            "TMPDIR": str(world / "tmp"),
        }
    )
    return wrapper, sidecar, wrapper_env


def _run_process(
    argv: Sequence[str],
    *,
    cwd: pathlib.Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(argv),
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GauntletContractError(
            f"shell contract process could not start: {argv}: {exc}"
        ) from exc


def _observe_wr2_case(
    *,
    repo_root: pathlib.Path,
    case_id: str,
) -> ShellCaseEvidence:
    configurations: dict[str, tuple[int, bool, int, str]] = {
        "pg_proxy_unreachable": (1, True, 74, "error"),
        "database_url_local_missing": (0, False, 74, "error"),
        "pg_proxy_reachable": (0, True, 0, "ok"),
        "heartbeat_self_heal": (1, True, 0, "ok"),
    }
    if case_id not in configurations:
        raise GauntletContractError(f"unknown WR2 shell case: {case_id}")
    nc_exit, database_url_present, expected_exit, expected_status = configurations[
        case_id
    ]

    temp_parent = os.environ.get("TMPDIR")
    with tempfile.TemporaryDirectory(
        prefix=f"runtime-truth-{case_id}-",
        dir=temp_parent,
    ) as raw_world:
        world = pathlib.Path(raw_world)
        wrapper, sidecar, wrapper_env = _prepare_wr2_world(
            repo_root=repo_root,
            world=world,
            nc_exit=nc_exit,
            database_url_present=database_url_present,
        )
        precondition_exit: int | None = None
        expected_precondition_exit: int | None = None
        precondition_status: str | None = None
        expected_precondition_status: str | None = None
        if case_id == "heartbeat_self_heal":
            precondition = _run_process(
                ("bash", str(wrapper), WR2_TEST_MODULE),
                cwd=repo_root,
                env=wrapper_env,
            )
            precondition_exit = precondition.returncode
            expected_precondition_exit = 74
            precondition_status = _sidecar_status(sidecar)
            expected_precondition_status = "error"
            _set_nc_exit(world, 0)

        completed = _run_process(
            ("bash", str(wrapper), WR2_TEST_MODULE),
            cwd=repo_root,
            env=wrapper_env,
        )
        return ShellCaseEvidence(
            case_id=case_id,
            exit_code=completed.returncode,
            expected_exit_code=expected_exit,
            sidecar_status=_sidecar_status(sidecar),
            expected_sidecar_status=expected_status,
            precondition_exit_code=precondition_exit,
            expected_precondition_exit_code=expected_precondition_exit,
            precondition_sidecar_status=precondition_status,
            expected_precondition_sidecar_status=expected_precondition_status,
        )


def run_shell_contract(
    *,
    repo_root: pathlib.Path,
    relative_path: str,
    expected_cases: Sequence[str],
) -> ShellEvidence:
    """Observe four direct real-wrapper invocations in parent-owned fake worlds.

    ``relative_path`` remains the incident-corpus label and developer entrypoint,
    but its process is never invoked and cannot provide evidence.  The parent owns
    case configuration, directly launches the copied production wrapper, and reads
    only that wrapper's exit code and heartbeat sidecar.
    """
    contract_path = repo_root / relative_path
    if not contract_path.is_file():
        raise GauntletContractError(f"mandatory shell target missing: {relative_path}")
    if not expected_cases:
        raise GauntletContractError("shell case manifest is empty")
    if len(expected_cases) != len(set(expected_cases)):
        raise GauntletContractError("shell case manifest contains duplicates")

    cases = tuple(
        _observe_wr2_case(
            repo_root=repo_root,
            case_id=case_id,
        )
        for case_id in expected_cases
    )
    evidence = ShellEvidence(
        target=relative_path,
        expected_cases=tuple(expected_cases),
        cases=cases,
    )
    errors = [
        (
            f"{case.case_id}: rc={case.exit_code}/{case.expected_exit_code} "
            f"sidecar={case.sidecar_status}/{case.expected_sidecar_status} "
            f"pre_rc={case.precondition_exit_code}/"
            f"{case.expected_precondition_exit_code} "
            f"pre_sidecar={case.precondition_sidecar_status}/"
            f"{case.expected_precondition_sidecar_status}"
        )
        for case in evidence.cases
        if not case.passed
    ]
    if tuple(case.case_id for case in evidence.cases) != tuple(expected_cases):
        errors.append("observed shell case order differs from exact manifest")
    if not (
        evidence.collected == evidence.executed == evidence.passed
        and evidence.failed == 0
        and evidence.skipped == 0
    ):
        errors.append(
            f"collected={evidence.collected} executed={evidence.executed} "
            f"passed={evidence.passed} failed={evidence.failed} "
            f"skipped={evidence.skipped}"
        )
    if errors:
        raise GauntletContractError(
            f"shell contract failed: {relative_path}; " + "; ".join(errors)
        )
    return evidence


def run_shell_contracts(repo_root: pathlib.Path) -> tuple[ShellEvidence, ...]:
    if set(SHELL_CASES) != set(SHELL_TARGETS):
        raise GauntletContractError(
            "shell target manifest and case manifest do not match exactly"
        )
    return tuple(
        run_shell_contract(
            repo_root=repo_root,
            relative_path=relative_path,
            expected_cases=SHELL_CASES[relative_path],
        )
        for relative_path in SHELL_TARGETS
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
        shell_evidence = run_shell_contracts(REPO_ROOT)
    except GauntletContractError as exc:
        LOGGER.error("RUNTIME_TRUTH_FAIL %s", exc)
        return 1

    LOGGER.info(
        "RUNTIME_TRUTH_PASS files=%d collected=%d executed=%d skipped=0 "
        "xfail=0 xpass=0 "
        "shell_collected=%d shell_executed=%d shell_passed=%d "
        "shell_failed=0 shell_skipped=0",
        len(evidence.collected_by_file),
        len(evidence.collected_nodeids),
        len(evidence.executed_nodeids),
        sum(result.collected for result in shell_evidence),
        sum(result.executed for result in shell_evidence),
        sum(result.passed for result in shell_evidence),
    )
    for target in PYTEST_TARGETS:
        LOGGER.info(
            "RUNTIME_TRUTH_FILE path=%s collected=%d executed=%d skipped=%d "
            "xfail=%d xpass=%d",
            target,
            evidence.collected_by_file[target],
            evidence.executed_by_file[target],
            evidence.skipped_by_file[target],
            evidence.xfail_by_file[target],
            evidence.xpass_by_file[target],
        )
    for result in shell_evidence:
        LOGGER.info(
            "RUNTIME_TRUTH_SHELL path=%s collected=%d executed=%d passed=%d "
            "failed=%d skipped=%d",
            result.target,
            result.collected,
            result.executed,
            result.passed,
            result.failed,
            result.skipped,
        )
        for case in result.cases:
            LOGGER.info(
                "RUNTIME_TRUTH_SHELL_CASE id=%s rc=%d expected_rc=%d "
                "sidecar=%s expected_sidecar=%s pre_rc=%s "
                "expected_pre_rc=%s pre_sidecar=%s expected_pre_sidecar=%s",
                case.case_id,
                case.exit_code,
                case.expected_exit_code,
                case.sidecar_status,
                case.expected_sidecar_status,
                case.precondition_exit_code,
                case.expected_precondition_exit_code,
                case.precondition_sidecar_status,
                case.expected_precondition_sidecar_status,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
