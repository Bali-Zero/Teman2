#!/usr/bin/env python3
"""Structural and execution contract for the Runtime Truth CI gauntlet."""

from __future__ import annotations

import pathlib
import re
from collections.abc import Mapping
from typing import Final

import pytest
import yaml

from scripts import runtime_truth_ci_gauntlet as gauntlet

REPO_ROOT: Final = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW_RELATIVE: Final = ".github/workflows/immune-enforcement.yml"
WORKFLOW: Final = REPO_ROOT / WORKFLOW_RELATIVE
RUNNER_RELATIVE: Final = "scripts/runtime_truth_ci_gauntlet.py"
META_TEST: Final = "scripts/tests/test_runtime_truth_ci_gauntlet.py"
STEP_NAME: Final = "Runtime Truth CI gauntlet (four incident contracts)"

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
    META_TEST,
)
EXPECTED_SHELL_TARGETS: Final[tuple[str, ...]] = (
    "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh",
)
EXPECTED_STEP: Final[dict[str, object]] = {
    "name": STEP_NAME,
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


def parse_workflow(text: str) -> dict[str, object]:
    document = yaml.load(text, Loader=UniqueKeyLoader)
    if not isinstance(document, dict):
        raise WorkflowContractError("workflow root must be a mapping")
    return document


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise WorkflowContractError(f"{label} must be a mapping")
    return value


def runtime_truth_step(text: str) -> dict[str, object]:
    document = parse_workflow(text)
    jobs = _mapping(document.get("jobs"), "jobs")
    antidotes = _mapping(jobs.get("antidotes"), "jobs.antidotes")
    steps = antidotes.get("steps")
    if not isinstance(steps, list):
        raise WorkflowContractError("jobs.antidotes.steps must be a sequence")
    matches = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == STEP_NAME
    ]
    if len(matches) != 1:
        raise WorkflowContractError(
            f"expected one {STEP_NAME!r} step, found {len(matches)}"
        )
    return matches[0]


def validate_runtime_truth_step(step: Mapping[str, object]) -> None:
    if dict(step) != EXPECTED_STEP:
        raise WorkflowContractError(
            f"runtime truth step differs from exact contract: {dict(step)!r}"
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


def test_runner_manifest_is_exact_and_contains_four_incident_corpora() -> None:
    assert gauntlet.PYTEST_TARGETS == EXPECTED_PYTEST_TARGETS
    assert gauntlet.SHELL_TARGETS == EXPECTED_SHELL_TARGETS
    assert frozenset(gauntlet.PYTEST_TARGETS[:-1] + gauntlet.SHELL_TARGETS) == (
        INCIDENT_CORPORA
    )


def test_workflow_step_matches_exact_structural_contract() -> None:
    step = runtime_truth_step(_workflow_text())
    validate_runtime_truth_step(step)
    assert step == EXPECTED_STEP


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
        validate_runtime_truth_step(mutated_step)


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


def test_meta_test_is_run_and_self_triggered() -> None:
    assert META_TEST in gauntlet.PYTEST_TARGETS
    assert uncovered_subjects(
        frozenset({META_TEST}), sentinel_entries(_workflow_text())
    ) == []
