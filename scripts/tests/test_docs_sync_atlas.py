"""Tests for live derived-state generation and protected stable pointers."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "docs_sync", REPO_ROOT / "scripts" / "docs_sync.py"
)
docs_sync = importlib.util.module_from_spec(_spec)
sys.modules["docs_sync"] = docs_sync
_spec.loader.exec_module(docs_sync)


def test_atlas_extractors_are_structural_and_deterministic():
    runbooks_a, runbooks_b = docs_sync.list_runbooks(), docs_sync.list_runbooks()
    workflows_a, workflows_b = docs_sync.list_workflows(), docs_sync.list_workflows()
    skills_a, skills_b = docs_sync.list_skills(), docs_sync.list_skills()
    coverage_a, coverage_b = docs_sync.automation_coverage(), docs_sync.automation_coverage()

    assert runbooks_a == runbooks_b
    assert workflows_a == workflows_b
    assert skills_a == skills_b
    assert coverage_a == coverage_b
    assert runbooks_a and all(row["title"] for row in runbooks_a)
    assert "README.md" not in {row["file"] for row in runbooks_a}
    assert "verify-template" in {row["name"] for row in workflows_a}
    assert "modus" in {row["name"] for row in skills_a}
    assert 0 <= coverage_a["documented"] <= coverage_a["plists"]


def test_templates_are_stable_pointers_not_volatile_values():
    assert set(docs_sync.TEMPLATES) == {
        key for keys in docs_sync.EXPECTED_MARKERS.values() for key in keys
    }
    for key, body in docs_sync.TEMPLATES.items():
        assert "scripts/docs_sync.py --json" in body, key
        assert "docs-derived-state CI artifact" in body, key
        assert not re.search(
            r"\b\d[\d,]*\s+(routers?|services?|tests?|documents?|nodes?|edges?|plists?)\b",
            body,
            re.IGNORECASE,
        ), key


def test_all_managed_files_are_canonical_after_regen():
    for target in docs_sync.TARGET_FILES:
        changed, _old, _new, errors = docs_sync.inject_markers(target)
        assert errors == [], (target, errors)
        assert not changed, target


def test_diff_local_innocence_ignores_unrelated_global_drift(tmp_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("apps/backend-rag/backend/services/new_service.py\n")
    assert docs_sync._targets_for_changed_file_list(changed) == []


def test_diff_local_guilt_selects_changed_doc_and_judge(tmp_path):
    changed_doc = tmp_path / "changed-doc.txt"
    changed_doc.write_text("README.md\n")
    assert docs_sync._targets_for_changed_file_list(changed_doc) == [
        docs_sync.REPO_ROOT / "README.md"
    ]

    changed_judge = tmp_path / "changed-judge.txt"
    changed_judge.write_text("scripts/docs_sync.py\n")
    assert docs_sync._targets_for_changed_file_list(changed_judge) == docs_sync.TARGET_FILES


def test_hand_edit_is_guilty_but_prose_edit_is_innocent():
    rel = "README.md"
    original = (REPO_ROOT / rel).read_text()
    pointer = docs_sync.TEMPLATES["TECH_STATS"]

    hand_edit = original.replace(pointer, "\n- Backend: 999 routers\n")
    restored, errors = docs_sync.canonicalize_content(rel, hand_edit)
    assert errors == []
    assert restored == original

    prose_edit = original + "\nProse outside the protected block.\n"
    unchanged, errors = docs_sync.canonicalize_content(rel, prose_edit)
    assert errors == []
    assert unchanged == prose_edit


def test_missing_marker_fails_closed():
    updated, errors = docs_sync.canonicalize_content("README.md", "# no marker\n")
    assert updated == "# no marker\n"
    assert errors == [
        "README.md: expected exactly one TECH_STATS marker pair, found 0"
    ]


def test_json_is_valid_and_does_not_write_tracked_targets():
    before = {path: path.read_bytes() for path in docs_sync.TARGET_FILES}
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "docs_sync.py"), "--json"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert {"routers", "services", "apps", "runbooks", "workflows", "skills"} <= payload.keys()
    assert payload["qdrant"]["status"] in {"live", "unavailable"}
    assert payload["kg"]["status"] in {"environment", "unavailable"}
    after = {path: path.read_bytes() for path in docs_sync.TARGET_FILES}
    assert before == after
