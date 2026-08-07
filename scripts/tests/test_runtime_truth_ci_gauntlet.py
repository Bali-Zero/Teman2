#!/usr/bin/env python3
"""Fail-closed wiring contract for the Runtime Truth CI gauntlet.

The incident corpora are useful only if the required-safe workflow both runs
them and wakes when either a corpus or one of its subjects changes.  This file
pins both halves and pins itself, so a future edit cannot make the gate green by
construction through an omitted runner path, sentinel path, or PR trigger.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "immune-enforcement.yml"
STEP_NAME = "Runtime Truth CI gauntlet (four incident contracts)"

CORPORA = frozenset(
    {
        "apps/evaluator/nlm_deep_research/tests/test_run_verdict.py",
        "scripts/tests/test_launchd_liveness_expected_nonzero.py",
        "scripts/tests/test_proprioception_run_wrap_exit_code.py",
        "scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh",
    }
)
META_TEST = "scripts/tests/test_runtime_truth_ci_gauntlet.py"
RUNNER_PATHS = CORPORA | {META_TEST}

# Every file whose semantics are asserted by the four corpora, plus the wiring
# contract itself. A wildcard may cover a subject, but every subject must match
# at least one sentinel pattern.
TRIGGER_SUBJECTS = frozenset(
    {
        "apps/evaluator/nlm_deep_research/run_verdict.py",
        "apps/evaluator/nlm_deep_research/pipeline.py",
        "apps/evaluator/nlm_deep_research/nb3_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb4_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb5_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb6_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb7_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb8_pipeline.py",
        "apps/evaluator/nlm_deep_research/nb10_pipeline.py",
        "scripts/launchd_liveness_detector.py",
        "scripts/proprioception.py",
        "scripts/wr2-cron-wrapper.sh",
        "scripts/lib/heartbeat.sh",
    }
) | RUNNER_PATHS

_SENTINEL_RE = re.compile(
    r"^\s+([A-Za-z0-9_./*-]+\.(?:py|sh|md|json|txt|yml|yaml))\|?\\?$",
    re.MULTILINE,
)
_RUNNER_LINE_RE = re.compile(
    r"^\s+(?:bash\s+)?((?:apps|scripts)/[A-Za-z0-9_./-]+\.(?:py|sh))\s*\\?$",
    re.MULTILINE,
)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def gauntlet_block(text: str) -> str:
    """Return the one named step, refusing missing or duplicate runners."""
    marker = f"      - name: {STEP_NAME}\n"
    assert text.count(marker) == 1, (
        f"expected exactly one {STEP_NAME!r} step, found {text.count(marker)}"
    )
    start = text.index(marker)
    next_step = text.find("\n      - name:", start + len(marker))
    assert next_step != -1, "gauntlet must be followed by another named step"
    return text[start:next_step]


def event_block(text: str) -> str:
    """Return the top-level event block without a YAML parser dependency."""
    start = text.index("\non:\n") + 1
    end = text.index("\nconcurrency:\n", start)
    return text[start:end]


def sentinel_patterns(text: str) -> frozenset[str]:
    return frozenset(_SENTINEL_RE.findall(text))


def runner_path_mentions(text: str) -> tuple[str, ...]:
    """Active path-only command lines, never paths hidden in comments."""
    return tuple(_RUNNER_LINE_RE.findall(gauntlet_block(text)))


def runner_paths(text: str) -> frozenset[str]:
    return frozenset(runner_path_mentions(text))


def uncovered_subjects(
    subjects: frozenset[str], patterns: frozenset[str]
) -> list[str]:
    """Subjects not named exactly by the in-job sentinel."""
    return sorted(subjects - patterns)


def test_apparatus_finds_one_non_vacuous_runner_and_sentinel() -> None:
    text = _workflow_text()
    assert runner_paths(text) == RUNNER_PATHS
    assert len(runner_path_mentions(text)) == len(RUNNER_PATHS)
    assert len(sentinel_patterns(text)) >= 50


def test_gauntlet_runs_exactly_the_four_corpora_and_its_meta_test() -> None:
    text = _workflow_text()
    assert runner_paths(text) == RUNNER_PATHS
    assert len(runner_path_mentions(text)) == len(RUNNER_PATHS)
    assert all("*" not in path for path in runner_path_mentions(text))


def test_gauntlet_is_fail_closed_and_uses_only_runner_temp_state() -> None:
    block = gauntlet_block(_workflow_text())
    assert "if: steps.paths.outputs.relevant == 'true'" in block
    assert 'HOME: ${{ runner.temp }}/runtime-truth-home' in block
    assert 'TMPDIR: ${{ runner.temp }}/runtime-truth-tmp' in block
    assert "set -euo pipefail" in block
    assert "python -m pytest \\\n" in block
    assert "bash scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh" in block
    for green_by_construction in (
        "if [ -f",
        "continue-on-error",
        "|| true",
        "|| :",
        "pytest.skip",
    ):
        assert green_by_construction not in block


def test_every_corpus_and_subject_wakes_the_gauntlet() -> None:
    text = _workflow_text()
    missing = uncovered_subjects(TRIGGER_SUBJECTS, sentinel_patterns(text))
    assert not missing, (
        "runtime-truth subjects missing from the sentinel path check; edits "
        f"to them would skip the gauntlet: {missing}"
    )


def test_required_safe_events_run_on_every_pr_and_merge_group() -> None:
    events = event_block(_workflow_text())
    assert "  pull_request:\n" in events
    assert "  merge_group:\n" in events
    assert "  workflow_dispatch:\n" in events
    assert not re.search(r"^\s{4}paths(?:-ignore)?:", events, re.MULTILINE)


def test_meta_test_is_itself_run_and_triggered() -> None:
    text = _workflow_text()
    assert META_TEST in runner_paths(text)
    assert uncovered_subjects(
        frozenset({META_TEST}), sentinel_patterns(text)
    ) == []


def test_corpora_have_no_skip_or_xfail_escape_hatches() -> None:
    for relative_path in RUNNER_PATHS:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for escape_hatch in (
            "pytest." + "skip(",
            "pytest." + "xfail(",
            "@pytest.mark." + "skip",
            "@pytest.mark." + "xfail",
        ):
            assert escape_hatch not in source, (
                f"{relative_path} contains {escape_hatch!r}; the gauntlet must "
                "report zero skipped/xfail contracts"
            )


def test_guilt_missing_runner_path_is_detected() -> None:
    text = _workflow_text().replace(
        f"            {META_TEST} \\\n", "", 1
    )
    assert META_TEST not in runner_paths(text)
    assert runner_paths(text) != RUNNER_PATHS


def test_guilt_missing_trigger_path_is_detected() -> None:
    patterns = frozenset({"scripts/proprioception.py"})
    missing = uncovered_subjects(
        frozenset({"scripts/lib/heartbeat.sh"}), patterns
    )
    assert missing == ["scripts/lib/heartbeat.sh"]
