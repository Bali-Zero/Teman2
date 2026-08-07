#!/usr/bin/env python3
"""Structural and execution contract for the Runtime Truth CI gauntlet."""

from __future__ import annotations

import ast
import os
import pathlib
import re
import shutil
import subprocess
from collections.abc import Mapping
from typing import Final

import pytest
import yaml

from scripts import runtime_truth_ci_gauntlet as gauntlet

REPO_ROOT: Final = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW_RELATIVE: Final = ".github/workflows/immune-enforcement.yml"
WORKFLOW: Final = REPO_ROOT / WORKFLOW_RELATIVE
RUNNER_RELATIVE: Final = "scripts/runtime_truth_ci_gauntlet.py"
RUNNER: Final = REPO_ROOT / RUNNER_RELATIVE
META_TEST: Final = "scripts/tests/test_runtime_truth_ci_gauntlet.py"
META_STEP_NAME: Final = "Runtime Truth meta-contract (external to runner)"
RUNNER_STEP_NAME: Final = "Runtime Truth CI gauntlet (four incident contracts)"
DETECTOR_STEP_NAME: Final = "Detect immune-relevant changes (sentinel path check)"

INCIDENT_CORPORA: Final[frozenset[str]] = frozenset(
    {
        "apps/evaluator/nlm_deep_research/tests/test_run_verdict.py",
        "scripts/tests/test_launchd_liveness_expected_nonzero.py",
        "scripts/tests/test_proprioception_run_wrap_exit_code.py",
        "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh",
    }
)
EXPECTED_PYTEST_TARGETS: Final[tuple[str, ...]] = (
    "apps/evaluator/nlm_deep_research/tests/test_run_verdict.py",
    "scripts/tests/test_launchd_liveness_expected_nonzero.py",
    "scripts/tests/test_proprioception_run_wrap_exit_code.py",
)
EXPECTED_SHELL_TARGETS: Final[tuple[str, ...]] = (
    "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh",
)
EXPECTED_SHELL_CASES: Final[dict[str, tuple[str, ...]]] = {
    "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh": (
        "pg_proxy_unreachable",
        "database_url_local_missing",
        "pg_proxy_reachable",
        "heartbeat_self_heal",
    ),
}
EXPECTED_META_STEP: Final[dict[str, object]] = {
    "name": META_STEP_NAME,
    "env": {
        "HOME": "${{ runner.temp }}/runtime-truth-home",
        "TMPDIR": "${{ runner.temp }}/runtime-truth-tmp",
    },
    "run": f"python -m pytest {META_TEST} -q",
}
EXPECTED_RUNNER_STEP: Final[dict[str, object]] = {
    "name": RUNNER_STEP_NAME,
    "if": "steps.paths.outputs.relevant == 'true'",
    "env": {
        "HOME": "${{ runner.temp }}/runtime-truth-home",
        "TMPDIR": "${{ runner.temp }}/runtime-truth-tmp",
    },
    "run": f"python {RUNNER_RELATIVE}",
}

TRIGGER_SUBJECTS: Final[frozenset[str]] = frozenset(
    {
        WORKFLOW_RELATIVE,
        RUNNER_RELATIVE,
        META_TEST,
        "apps/evaluator/nlm_deep_research/run_verdict.py",
        "apps/evaluator/nlm_deep_research/pipeline.py",
        "apps/evaluator/nlm_deep_research/nb3_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb4_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb5_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb6_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb7_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb8_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb10_pipeline.py",
        "apps/evaluator/nlm_deep_research/tests/test_run_verdict.py",
        "scripts/launchd_liveness_detector.py",
        "scripts/tests/test_launchd_liveness_expected_nonzero.py",
        "scripts/proprioception.py",
        "scripts/tests/test_proprioception_run_wrap_exit_code.py",
        "scripts/wr2-cron-wrapper.sh",
        "scripts/lib/heartbeat.sh",
        "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh",
    }
)

_SENTINEL_RE: Final = re.compile(
    r"^\s+([A-Za-z0-9_./*-]+\.(?:py|sh|md|json|txt|yml|yaml))(?:\|\\|\))$",
    re.MULTILINE,
)


class WorkflowContractError(RuntimeError):
    """The parsed workflow no longer matches the required runner contract."""


class UniqueKeyLoader(yaml.BaseLoader):
    """YAML loader that preserves `on` as text and refuses duplicate keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise WorkflowContractError(f"non-string workflow key: {key!r}")
        if key in mapping:
            raise WorkflowContractError(f"duplicate workflow key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def parse_workflow(text: str) -> dict[str, object]:
    document = yaml.load(text, Loader=UniqueKeyLoader)
    if not isinstance(document, dict):
        raise WorkflowContractError("workflow root must be a mapping")
    return document


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise WorkflowContractError(f"{label} must be a mapping")
    return value


def antidotes_steps(text: str) -> list[object]:
    document = parse_workflow(text)
    jobs = _mapping(document.get("jobs"), "jobs")
    antidotes = _mapping(jobs.get("antidotes"), "jobs.antidotes")
    steps = antidotes.get("steps")
    if not isinstance(steps, list):
        raise WorkflowContractError("jobs.antidotes.steps must be a sequence")
    return steps


def named_step(text: str, name: str) -> tuple[int, dict[str, object]]:
    steps = antidotes_steps(text)
    matches = [
        (index, step)
        for index, step in enumerate(steps)
        if isinstance(step, dict) and step.get("name") == name
    ]
    if len(matches) != 1:
        raise WorkflowContractError(f"expected one {name!r} step, found {len(matches)}")
    return matches[0]


def runtime_truth_step(text: str) -> dict[str, object]:
    return named_step(text, RUNNER_STEP_NAME)[1]


def detector_script(text: str) -> str:
    _, step = named_step(text, DETECTOR_STEP_NAME)
    script = step.get("run")
    if not isinstance(script, str):
        raise WorkflowContractError("path detector run must be a string")
    return script


def validate_exact_step(
    step: Mapping[str, object], expected: Mapping[str, object]
) -> None:
    if dict(step) != dict(expected):
        raise WorkflowContractError(
            f"runtime truth step differs from exact contract: {dict(step)!r}"
        )


def validate_runner_entrypoint(text: str) -> None:
    """Require the executable entrypoint to delegate to ``main`` structurally."""
    try:
        module = ast.parse(text)
    except SyntaxError as exc:
        raise WorkflowContractError(f"runner is not valid Python: {exc}") from exc

    expected = ast.parse(
        'if __name__ == "__main__":\n    raise SystemExit(main())\n'
    ).body[0]
    candidates = [
        node
        for node in module.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    if len(candidates) != 1:
        raise WorkflowContractError(
            f"expected one runner __name__ entrypoint, found {len(candidates)}"
        )
    entrypoint = candidates[0]
    if entrypoint is not module.body[-1] or ast.dump(entrypoint) != ast.dump(expected):
        raise WorkflowContractError(
            "runner entrypoint must end with raise SystemExit(main())"
        )


def sentinel_entries(text: str) -> tuple[str, ...]:
    return tuple(_SENTINEL_RE.findall(text))


def uncovered_subjects(
    subjects: frozenset[str], entries: tuple[str, ...]
) -> list[str]:
    return sorted(subjects - set(entries))


def _remove_sentinel_entry(text: str, relative_path: str) -> str:
    pattern = re.compile(
        rf"^\s+{re.escape(relative_path)}(?:\|\\|\))$\n?",
        re.MULTILINE,
    )
    mutated, replacements = pattern.subn("", text, count=1)
    if replacements != 1:
        raise WorkflowContractError(
            f"could not create sentinel mutation for {relative_path}"
        )
    return mutated


def _assert_main_runs_exact_contracts(
    monkeypatch: pytest.MonkeyPatch,
    namespace: dict[str, object],
) -> None:
    """External observer for ``main``: both contracts must run once, in order."""
    calls: list[tuple[object, ...]] = []
    pytest_evidence = gauntlet.PytestEvidence(repo_root=REPO_ROOT)
    shell_evidence = (
        gauntlet.ShellEvidence(
            target=EXPECTED_SHELL_TARGETS[0],
            expected_cases=EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]],
            cases=tuple(
                gauntlet.ShellCaseEvidence(
                    case_id=case_id,
                    exit_code=0,
                    expected_exit_code=0,
                    sidecar_status="ok",
                    expected_sidecar_status="ok",
                )
                for case_id in EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]]
            ),
        ),
    )

    def prepare() -> None:
        calls.append(("prepare",))

    def run_pytest(
        *,
        repo_root: pathlib.Path,
        targets: tuple[str, ...],
    ) -> gauntlet.PytestEvidence:
        calls.append(("pytest", repo_root, tuple(targets)))
        return pytest_evidence

    def run_shell(repo_root: pathlib.Path) -> tuple[gauntlet.ShellEvidence, ...]:
        calls.append(("shell", repo_root))
        return shell_evidence

    monkeypatch.setitem(namespace, "_prepare_hermetic_directories", prepare)
    monkeypatch.setitem(namespace, "run_pytest_contract", run_pytest)
    monkeypatch.setitem(namespace, "run_shell_contracts", run_shell)

    main = namespace["main"]
    assert callable(main)
    assert main(()) == 0
    assert calls == [
        ("prepare",),
        ("pytest", namespace["REPO_ROOT"], namespace["PYTEST_TARGETS"]),
        ("shell", namespace["REPO_ROOT"]),
    ]


def _runner_namespace(text: str) -> dict[str, object]:
    parsed = ast.parse(text)
    main_nodes = [
        node
        for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "main"
    ]
    assert len(main_nodes) == 1
    namespace = dict(gauntlet.__dict__)
    namespace["__name__"] = "runtime_truth_ci_gauntlet_mutant"
    exec(
        compile(ast.Module(body=main_nodes, type_ignores=[]), str(RUNNER), "exec"),
        namespace,
    )
    return namespace


def _insert_early_return_in_main(text: str) -> str:
    module = ast.parse(text)
    matches = [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "main"
    ]
    assert len(matches) == 1
    main_node = matches[0]
    assert main_node.body
    lines = text.splitlines(keepends=True)
    lines.insert(main_node.body[0].lineno - 1, "    return 0\n")
    return "".join(lines)


def _write_shell_mutant_repo(tmp_path: pathlib.Path, harness: str) -> pathlib.Path:
    """Build a complete fake repo so failure comes from observation, not missing files."""
    for relative_path in (
        "scripts/wr2-cron-wrapper.sh",
        "scripts/lib/heartbeat.sh",
    ):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative_path, destination)
    target = tmp_path / EXPECTED_SHELL_TARGETS[0]
    target.write_text(harness, encoding="utf-8")
    target.chmod(0o755)
    return target


def _detector_result(script: str, tmp_path: pathlib.Path) -> str:
    """Execute the workflow detector against a real two-commit local repository."""
    repo = tmp_path / "detector-repo"
    repo.mkdir()

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    git("init", "-q")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git("add", "README.md")
    git(
        "-c",
        "user.name=Runtime Truth",
        "-c",
        "user.email=runtime-truth@example.invalid",
        "commit",
        "-qm",
        "base",
    )
    base_sha = git("rev-parse", "HEAD")
    subject = repo / RUNNER_RELATIVE
    subject.parent.mkdir(parents=True)
    subject.write_text("# changed runtime truth subject\n", encoding="utf-8")
    git("add", RUNNER_RELATIVE)
    git(
        "-c",
        "user.name=Runtime Truth",
        "-c",
        "user.email=runtime-truth@example.invalid",
        "commit",
        "-qm",
        "head",
    )
    head_sha = git("rev-parse", "HEAD")
    output = tmp_path / "github-output"
    environment = os.environ.copy()
    environment.update(
        {
            "BASE_SHA": base_sha,
            "HEAD_SHA": head_sha,
            "GITHUB_OUTPUT": str(output),
        }
    )
    subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=repo,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    values = [
        line.removeprefix("relevant=")
        for line in output.read_text(encoding="utf-8").splitlines()
        if line.startswith("relevant=")
    ]
    assert len(values) == 1
    return values[0]


def test_runner_manifest_is_exact_and_contains_four_incident_corpora() -> None:
    assert gauntlet.PYTEST_TARGETS == EXPECTED_PYTEST_TARGETS
    assert gauntlet.SHELL_TARGETS == EXPECTED_SHELL_TARGETS
    assert gauntlet.SHELL_CASES == EXPECTED_SHELL_CASES
    assert frozenset(gauntlet.PYTEST_TARGETS + gauntlet.SHELL_TARGETS) == (
        INCIDENT_CORPORA
    )


def test_workflow_steps_match_exact_structural_contract_and_order() -> None:
    text = _workflow_text()
    meta_index, meta_step = named_step(text, META_STEP_NAME)
    runner_index, runner_step = named_step(text, RUNNER_STEP_NAME)
    validate_exact_step(meta_step, EXPECTED_META_STEP)
    validate_exact_step(runner_step, EXPECTED_RUNNER_STEP)
    assert meta_index < runner_index


def test_unconditional_meta_dynamically_proves_detector_relevant_path(
    tmp_path: pathlib.Path,
) -> None:
    text = _workflow_text()
    _, meta_step = named_step(text, META_STEP_NAME)
    assert "if" not in meta_step
    assert _detector_result(detector_script(text), tmp_path) == "true"


def test_guilt_detector_relevant_true_mutated_false_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    original = detector_script(_workflow_text())
    mutated, replacements = re.subn(
        r"^(\s+)RELEVANT=true$",
        r"\1RELEVANT=false",
        original,
        count=1,
        flags=re.MULTILINE,
    )
    assert replacements == 1
    assert _detector_result(mutated, tmp_path) == "false"


def test_runner_entrypoint_delegates_to_main_structurally() -> None:
    assert validate_runner_entrypoint(_runner_text()) is None


def test_external_observer_proves_main_runs_both_contracts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_main_runs_exact_contracts(monkeypatch, gauntlet.__dict__)


def test_guilt_early_return_inside_main_is_rejected_dynamically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mutated = _insert_early_return_in_main(_runner_text())
    namespace = _runner_namespace(mutated)
    with pytest.raises(AssertionError):
        _assert_main_runs_exact_contracts(monkeypatch, namespace)


@pytest.mark.parametrize(
    ("failing_contract", "expected_calls"),
    (("pytest", ["prepare", "pytest"]), ("shell", ["prepare", "pytest", "shell"])),
)
def test_main_fails_closed_when_either_contract_fails(
    monkeypatch: pytest.MonkeyPatch,
    failing_contract: str,
    expected_calls: list[str],
) -> None:
    calls: list[str] = []

    def prepare() -> None:
        calls.append("prepare")

    def run_pytest(
        *, repo_root: pathlib.Path, targets: tuple[str, ...]
    ) -> gauntlet.PytestEvidence:
        del targets
        calls.append("pytest")
        if failing_contract == "pytest":
            raise gauntlet.GauntletContractError("pytest mutant")
        return gauntlet.PytestEvidence(repo_root=repo_root)

    def run_shell(repo_root: pathlib.Path) -> tuple[gauntlet.ShellEvidence, ...]:
        del repo_root
        calls.append("shell")
        raise gauntlet.GauntletContractError("shell mutant")

    monkeypatch.setattr(gauntlet, "_prepare_hermetic_directories", prepare)
    monkeypatch.setattr(gauntlet, "run_pytest_contract", run_pytest)
    monkeypatch.setattr(gauntlet, "run_shell_contracts", run_shell)
    assert gauntlet.main(()) == 1
    assert calls == expected_calls


def test_guilt_runner_entrypoint_early_exit_is_rejected() -> None:
    original = _runner_text()
    mutated = original.replace("raise SystemExit(main())", "raise SystemExit(0)")
    assert mutated != original
    with pytest.raises(WorkflowContractError, match="SystemExit\\(main\\(\\)\\)"):
        validate_runner_entrypoint(mutated)


@pytest.mark.parametrize(
    "mutated_run",
    (
        "exit 0",
        f"python {RUNNER_RELATIVE} --collect-only",
    ),
)
def test_guilt_exit_zero_and_collect_only_break_step_contract(
    mutated_run: str,
) -> None:
    mutated_step = dict(runtime_truth_step(_workflow_text()))
    mutated_step["run"] = mutated_run
    with pytest.raises(WorkflowContractError):
        validate_exact_step(mutated_step, EXPECTED_RUNNER_STEP)


def test_runner_rejects_real_runtime_skip(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "test_runtime_skip_probe.py"
    target.write_text(
        "import pytest\n\ndef test_probe():\n    pytest.skip('mutant')\n",
        encoding="utf-8",
    )
    with pytest.raises(gauntlet.GauntletContractError, match="skipped="):
        gauntlet.run_pytest_contract(
            repo_root=tmp_path,
            targets=(target.name,),
        )


def test_runner_rejects_real_importorskip(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "test_importorskip_probe.py"
    target.write_text(
        "import pytest\n"
        "pytest.importorskip('runtime_truth_definitely_missing')\n\n"
        "def test_probe():\n    assert True\n",
        encoding="utf-8",
    )
    with pytest.raises(gauntlet.GauntletContractError, match="skipped="):
        gauntlet.run_pytest_contract(
            repo_root=tmp_path,
            targets=(target.name,),
        )


def test_runner_rejects_real_collect_only(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "test_collect_only_probe.py"
    target.write_text("def test_probe():\n    assert True\n", encoding="utf-8")
    with pytest.raises(
        gauntlet.GauntletContractError,
        match="collected but not executed",
    ):
        gauntlet.run_pytest_contract(
            repo_root=tmp_path,
            targets=(target.name,),
            extra_options=("--collect-only",),
        )


def test_runner_rejects_real_xfail(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "test_xfail_probe.py"
    target.write_text(
        "import pytest\n\n@pytest.mark.xfail(reason='mutant')\n"
        "def test_probe():\n    assert False\n",
        encoding="utf-8",
    )
    with pytest.raises(gauntlet.GauntletContractError, match="xfail="):
        gauntlet.run_pytest_contract(repo_root=tmp_path, targets=(target.name,))


def test_runner_rejects_real_xpass(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "test_xpass_probe.py"
    target.write_text(
        "import pytest\n\n@pytest.mark.xfail(reason='mutant')\n"
        "def test_probe():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    with pytest.raises(gauntlet.GauntletContractError, match="xpass="):
        gauntlet.run_pytest_contract(repo_root=tmp_path, targets=(target.name,))


def test_shell_contract_rejects_exit_zero_with_zero_structured_cases(
    tmp_path: pathlib.Path,
) -> None:
    target = _write_shell_mutant_repo(
        tmp_path,
        "#!/usr/bin/env bash\necho '0 passed, 0 failed'\nexit 0\n",
    )
    with pytest.raises(gauntlet.GauntletContractError):
        gauntlet.run_shell_contract(
            repo_root=tmp_path,
            relative_path=target.relative_to(tmp_path).as_posix(),
            expected_cases=EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]],
        )


def test_parent_observer_binds_exact_cases_to_real_wrapper_outcomes() -> None:
    expected_cases = EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]]
    evidence = gauntlet.run_shell_contract(
        repo_root=REPO_ROOT,
        relative_path=EXPECTED_SHELL_TARGETS[0],
        expected_cases=expected_cases,
    )
    assert tuple(case.case_id for case in evidence.cases) == expected_cases
    assert [
        (case.exit_code, case.sidecar_status)
        for case in evidence.cases
    ] == [(74, "error"), (74, "error"), (0, "ok"), (0, "ok")]
    self_heal = evidence.cases[-1]
    assert (
        self_heal.precondition_exit_code,
        self_heal.precondition_sidecar_status,
    ) == (74, "error")
    assert evidence.collected == evidence.executed == evidence.passed == 4
    assert evidence.failed == evidence.skipped == 0


def test_shell_contract_rejects_four_hardcoded_pass_receipts(
    tmp_path: pathlib.Path,
) -> None:
    receipts = "".join(
        f"printf 'runtime-truth-shell-v1\\t{case_id}\\tpassed\\n' >&\"$fd\"\n"
        for case_id in EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]]
    )
    target = _write_shell_mutant_repo(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "fd=\"${RUNTIME_TRUTH_EVIDENCE_FD:?}\"\n"
        f"{receipts}"
        "exit 0\n",
    )
    with pytest.raises(gauntlet.GauntletContractError):
        gauntlet.run_shell_contract(
            repo_root=tmp_path,
            relative_path=target.relative_to(tmp_path).as_posix(),
            expected_cases=EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]],
        )


def test_shell_contract_rejects_four_hardcoded_stdout_passes(
    tmp_path: pathlib.Path,
) -> None:
    receipts = "".join(
        f"printf 'runtime-truth-shell-v1\\t{case_id}\\tpassed\\n'\n"
        for case_id in EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]]
    )
    target = _write_shell_mutant_repo(
        tmp_path,
        f"#!/usr/bin/env bash\n{receipts}exit 0\n",
    )
    with pytest.raises(gauntlet.GauntletContractError, match="sidecar"):
        gauntlet.run_shell_contract(
            repo_root=tmp_path,
            relative_path=target.relative_to(tmp_path).as_posix(),
            expected_cases=EXPECTED_SHELL_CASES[EXPECTED_SHELL_TARGETS[0]],
        )


def test_every_corpus_subject_harness_and_workflow_are_exact_triggers() -> None:
    entries = sentinel_entries(_workflow_text())
    missing = uncovered_subjects(TRIGGER_SUBJECTS, entries)
    assert not missing, f"runtime-truth paths missing exact triggers: {missing}"
    assert entries.count(WORKFLOW_RELATIVE) == 1
    assert entries.count(RUNNER_RELATIVE) == 1


def test_workflow_self_trigger_survives_workflow_glob_removal() -> None:
    text = _workflow_text()
    without_globs = _remove_sentinel_entry(
        _remove_sentinel_entry(text, ".github/workflows/*.yml"),
        ".github/workflows/*.yaml",
    )
    assert uncovered_subjects(frozenset({WORKFLOW_RELATIVE}), sentinel_entries(without_globs)) == []


def test_guilt_removing_workflow_exact_self_trigger_is_detected() -> None:
    mutated = _remove_sentinel_entry(_workflow_text(), WORKFLOW_RELATIVE)
    assert uncovered_subjects(
        frozenset({WORKFLOW_RELATIVE}), sentinel_entries(mutated)
    ) == [WORKFLOW_RELATIVE]


def test_required_safe_events_are_structural_and_ungated() -> None:
    document = parse_workflow(_workflow_text())
    events = _mapping(document.get("on"), "on")
    for event in ("workflow_dispatch", "pull_request", "merge_group"):
        assert event in events
        event_config = events[event]
        if isinstance(event_config, Mapping):
            assert "paths" not in event_config
            assert "paths-ignore" not in event_config


def test_meta_test_is_external_to_runner_and_self_triggered() -> None:
    assert META_TEST not in gauntlet.PYTEST_TARGETS
    meta_index, meta_step = named_step(_workflow_text(), META_STEP_NAME)
    runner_index, _ = named_step(_workflow_text(), RUNNER_STEP_NAME)
    validate_exact_step(meta_step, EXPECTED_META_STEP)
    assert meta_index < runner_index
    assert uncovered_subjects(
        frozenset({META_TEST}), sentinel_entries(_workflow_text())
    ) == []
