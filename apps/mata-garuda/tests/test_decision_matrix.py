"""Tests for the decision matrix doc generator."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


def _fake_review_entries():
    """Mock 19 ORPHAN_REVIEW entries spanning 4 clusters."""
    apo = _import_apo()
    out = []
    counts = {"orphan_unclear": 8, "research_heavy": 5, "subhi_merge": 4, "zero_value_orphan": 2}
    i = 0
    for cluster, n in counts.items():
        for _ in range(n):
            out.append({
                "uuid": f"uuid-{i:02d}",
                "name": f"NB-{i}",
                "cluster": cluster,
                "source_count_live": 1,
                "peer_uuids": [],
            })
            i += 1
    return out


def test_decision_matrix_groups_by_cluster(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    assert "orphan_unclear" in content
    assert "research_heavy" in content
    assert "subhi_merge" in content
    assert "zero_value_orphan" in content


def test_decision_matrix_lists_all_19_orphan_review(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    for i in range(19):
        assert f"uuid-{i:02d}" in content


def test_decision_matrix_includes_callsite_followup_section(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    assert "Follow-up" in content or "follow-up" in content
    assert "sentinel_actor.py" in content
    assert "nlm_feeder.py" in content
    assert "nlm_expander_agent.py" in content
    assert "health_tools.py" in content


def test_decision_matrix_zero_decision_marker_present_per_nb(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    # 19 NB → at least 19 occurrences of the placeholder line.
    assert content.count("Zero decision (") >= 19
