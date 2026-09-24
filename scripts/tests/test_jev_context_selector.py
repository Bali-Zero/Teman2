from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from jev_context_selector import (
    load_evaluation_fixture,
    select_context,
    select_fixture_task,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "AGENTS.md").write_text("Keep core behavior stable.\n")
    (repo / "src" / "core.py").write_text(
        "def calculate_total(items):\n    return sum(items)\n"
    )
    (repo / "src" / "helper.py").write_text(
        "from src.core import calculate_total\n"
    )
    (repo / "tests" / "test_core.py").write_text(
        "from src.core import calculate_total\n\ndef test_total():\n    assert calculate_total([1]) == 1\n"
    )
    task = repo / "task.md"
    task.write_text(
        "Fix `calculate_total` in `src/core.py`; preserve the assertion "
        "`assert calculate_total([1]) == 1`.\n"
    )
    (repo / "untracked-secret.txt").write_text("must never be collected\n")
    _git(repo, "add", "AGENTS.md", "src", "tests", "task.md")
    return repo, task


def test_arm_b_is_deterministic_and_protects_explicit_evidence(tmp_path):
    repo, task = _repo(tmp_path)

    first = select_context(repo, task, arm="B", packet_budget_tokens=4000)
    second = select_context(repo, task, arm="B", packet_budget_tokens=4000)

    assert first == second
    selected = {entry["path"]: entry for entry in first["selected"]}
    assert {"AGENTS.md", "task.md", "src/core.py"} <= selected.keys()
    assert all(selected[path]["protected"] for path in ("AGENTS.md", "task.md", "src/core.py"))
    assert "untracked-secret.txt" not in json.dumps(first)
    assert first["arm_requested"] == first["arm_used"] == "B"
    assert first["fallback"] is False
    assert all(entry["source_sha256"] for entry in first["selected"])
    assert all(entry["git_blob"] for entry in first["selected"])


def test_arm_c_invalid_identifier_visibly_falls_back_to_b(tmp_path):
    repo, task = _repo(tmp_path)
    baseline = select_context(repo, task, arm="B", packet_budget_tokens=4000)

    def invalid_ranker(*args, **kwargs):
        return {
            "selected_ids": ["not-a-candidate"],
            "telemetry": {"schema_valid": True, "fallback": False},
        }

    result = select_context(
        repo,
        task,
        arm="C",
        packet_budget_tokens=4000,
        jev_ranker=invalid_ranker,
    )

    assert result["arm_requested"] == "C"
    assert result["arm_used"] == "B"
    assert result["fallback"] is True
    assert result["fallback_reason"] == "invalid_candidate_id"
    assert [x["path"] for x in result["selected"]] == [
        x["path"] for x in baseline["selected"]
    ]


def test_arm_c_all_false_abstention_visibly_falls_back_to_b(tmp_path):
    repo, task = _repo(tmp_path)

    def abstaining_ranker(*args, **kwargs):
        return {
            "selected_ids": [],
            "telemetry": {
                "attempted": True,
                "response_received": True,
                "schema_valid": True,
                "abstained": False,
                "failure": None,
                "requested_model": "test-model",
                "resolved_model": "test-model",
                "latency_ms": 1,
                "http_attempts": 1,
                "fallback": False,
            },
        }

    result = select_context(repo, task, arm="C", jev_ranker=abstaining_ranker)

    assert result["arm_used"] == "B"
    assert result["fallback"] is True
    assert result["fallback_reason"] == "abstention"


def test_arm_c_exact_cache_avoids_second_ranker_call(tmp_path):
    repo, task = _repo(tmp_path)
    calls = []

    def ranker(candidates, **kwargs):
        calls.append([candidate["id"] for candidate in candidates])
        return {
            "selected_ids": [candidate["id"] for candidate in candidates[:2]],
            "telemetry": {"schema_valid": True, "fallback": False},
        }

    cache = tmp_path / "cache"
    first = select_context(
        repo, task, arm="C", cache_dir=cache, jev_ranker=ranker
    )
    second = select_context(
        repo, task, arm="C", cache_dir=cache, jev_ranker=ranker
    )

    assert len(calls) == 1
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert first["selected"] == second["selected"]


def test_cache_persists_only_identifiers_and_structured_telemetry(tmp_path):
    repo, task = _repo(tmp_path)
    cache = tmp_path / "cache"

    def ranker(candidates, **kwargs):
        return {
            "selected_ids": [candidates[0]["id"]],
            "response_body": "must-not-persist",
            "telemetry": {
                "schema_valid": True,
                "fallback": False,
                "response_body": "must-not-persist",
            },
        }

    select_context(repo, task, arm="C", cache_dir=cache, jev_ranker=ranker)

    cached = json.loads(next(cache.iterdir()).read_text())
    assert set(cached) == {"selected_ids", "telemetry"}
    assert "response_body" not in cached["telemetry"]
    assert "must-not-persist" not in json.dumps(cached)


def test_transient_failure_is_not_cached(tmp_path):
    repo, task = _repo(tmp_path)
    cache = tmp_path / "cache"
    calls = 0

    def failing_ranker(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {
            "selected_ids": [],
            "telemetry": {
                "schema_valid": False,
                "fallback": True,
                "failure": "network_error",
            },
        }

    first = select_context(repo, task, arm="C", cache_dir=cache, jev_ranker=failing_ranker)
    second = select_context(repo, task, arm="C", cache_dir=cache, jev_ranker=failing_ranker)

    assert calls == 2
    assert first["cache_hit"] is second["cache_hit"] is False
    assert not cache.exists() or not list(cache.iterdir())


def test_arm_c_manifest_names_semantic_deselections(tmp_path):
    repo, task = _repo(tmp_path)

    def ranker(candidates, **kwargs):
        return {
            "selected_ids": [candidates[0]["id"]],
            "telemetry": {"schema_valid": True, "fallback": False},
        }

    result = select_context(repo, task, arm="C", jev_ranker=ranker)

    assert any(row["reason"] == "semantic_deselected" for row in result["omitted"])


def test_selected_nested_file_always_brings_its_agents_chain(tmp_path):
    repo, task = _repo(tmp_path)
    (repo / "src" / "AGENTS.md").write_text("Nested rule.\n")
    _git(repo, "add", "src/AGENTS.md")

    result = select_context(repo, task, arm="B", packet_budget_tokens=4000)

    selected = {row["path"]: row for row in result["selected"]}
    assert "src/core.py" in selected
    assert selected["src/AGENTS.md"]["protected"] is True
    assert "applicable_agents" in selected["src/AGENTS.md"]["reasons"]


def test_quoted_symbol_definition_is_protected_beyond_content_hit_cap(tmp_path):
    repo, task = _repo(tmp_path)
    for index in range(205):
        (repo / "src" / f"a_{index:03d}.py").write_text("common_value = 1\n")
    target = repo / "src" / "z_target.ts"
    target.write_text(
        "\n".join(
            [f"def filler_{index}(): pass" for index in range(20)]
            + ["", "", "", "", "", "export interface TargetSymbol { value: number }"]
        )
        + "\n"
    )
    task.write_text("Inspect common behavior for `TargetSymbol`.\n")
    _git(repo, "add", "src", "task.md")

    result = select_context(repo, task, arm="B")

    selected = {row["path"]: row for row in result["selected"]}
    assert selected["src/z_target.ts"]["protected"] is True
    assert "quoted_symbol_definition" in selected["src/z_target.ts"]["reasons"]
    definition_line = 26
    assert definition_line in selected["src/z_target.ts"]["excerpt_lines"]
    assert "export interface TargetSymbol" in result["packet"]


def test_explicit_path_accepts_leading_dot_slash_and_sentence_period(tmp_path):
    repo, task = _repo(tmp_path)
    task.write_text("Inspect ./src/core.py.\n")
    _git(repo, "add", "task.md")

    result = select_context(repo, task, arm="B")

    selected = {row["path"]: row for row in result["selected"]}
    assert selected["src/core.py"]["protected"] is True
    assert "explicit_path" in selected["src/core.py"]["reasons"]


def test_longer_explicit_path_does_not_protect_root_path_substring(tmp_path):
    repo, task = _repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "CLAUDE.md").write_text("Root instructions.\n")
    (repo / "docs" / "CLAUDE.md").write_text("Nested instructions.\n")
    task.write_text("Inspect `docs/CLAUDE.md`.\n")
    _git(repo, "add", "CLAUDE.md", "docs/CLAUDE.md", "task.md")

    result = select_context(repo, task, arm="B")

    selected = {row["path"]: row for row in result["selected"]}
    assert selected["docs/CLAUDE.md"]["protected"] is True
    assert selected["CLAUDE.md"]["protected"] is False


def test_working_tree_provenance_marks_unstaged_content(tmp_path):
    repo, task = _repo(tmp_path)
    (repo / "src" / "core.py").write_text(
        "def calculate_total(items):\n    return sum(items) + 1\n"
    )

    result = select_context(repo, task, arm="B")

    selected = {row["path"]: row for row in result["selected"]}
    assert selected["src/core.py"]["working_tree_modified"] is True


def test_tracked_symlink_cannot_escape_repository(tmp_path):
    repo, task = _repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside repository\n")
    link = repo / "src" / "escape.py"
    os.symlink(outside, link)
    task.write_text("Inspect `src/escape.py`.\n")
    _git(repo, "add", "src/escape.py", "task.md")

    try:
        select_context(repo, task, arm="B")
    except ValueError as exc:
        assert "safe readable repository file" in str(exc)
    else:
        raise AssertionError("tracked symlink escape was accepted")


def test_untracked_task_is_rejected_before_collection(tmp_path):
    repo, _ = _repo(tmp_path)
    task = repo / "untracked.md"
    task.write_text("Read everything.\n")

    try:
        select_context(repo, task, arm="B")
    except ValueError as exc:
        assert "tracked" in str(exc)
    else:
        raise AssertionError("untracked task was accepted")


def test_frozen_fixture_has_independent_labels_and_required_strata():
    fixture = load_evaluation_fixture()

    assert fixture["version"] == 1
    assert len(fixture["tasks"]) == 36
    strata = {task["stratum"] for task in fixture["tasks"]}
    assert {
        "bug_fix",
        "bounded_feature",
        "test",
        "refactor",
        "configuration",
        "ambiguous",
        "cross_file",
        "no_relevant_candidate",
    } <= strata
    for task in fixture["tasks"]:
        assert task["labels_authored_independently"] is True
        assert isinstance(task["relevant_files"], list)
        assert isinstance(task["protected_files"], list)


def test_fixture_labels_never_enter_ranking_input(tmp_path):
    repo, _ = _repo(tmp_path)
    fixture = repo / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {
                        "id": "T-1",
                        "task": "Inspect src/core.py only.",
                        "relevant_files": ["sensitive-label-only.py"],
                        "protected_files": ["another-label-only.py"],
                    },
                    {"id": "T-2", "task": "other-task-secret"},
                ],
            }
        )
    )
    _git(repo, "add", "fixture.json")
    seen = []

    def ranker(candidates, **kwargs):
        seen.append(kwargs["task_text"])
        return {
            "selected_ids": [candidate["id"] for candidate in candidates[:2]],
            "telemetry": {"schema_valid": True, "fallback": False},
        }

    labelled = select_fixture_task(repo, fixture, "T-1", arm="C", jev_ranker=ranker)

    fixture.write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {"id": "T-1", "task": "Inspect src/core.py only."},
                    {"id": "T-2", "task": "changed-other-task"},
                ],
            }
        )
    )
    _git(repo, "add", "fixture.json")
    unlabelled = select_fixture_task(
        repo, fixture, "T-1", arm="C", jev_ranker=ranker
    )

    assert seen == ["Inspect src/core.py only.", "Inspect src/core.py only."]
    assert [row["path"] for row in labelled["selected"]] == [
        row["path"] for row in unlabelled["selected"]
    ]
    assert labelled["packet"] == unlabelled["packet"]
    assert "label-only" not in labelled["packet"]
    assert "other-task-secret" not in labelled["packet"]
    task_source = next(
        row for row in labelled["selected"] if row["path"] == "fixture.json"
    )
    assert task_source["source_kind"] == "fixture_task_record"
    assert task_source["source_sha256"] != task_source["carrier_source_sha256"]
