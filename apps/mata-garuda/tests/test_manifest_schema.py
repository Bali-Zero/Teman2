"""Tests that the bootstrap manifest JSON conforms to the expected schema."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


MANIFEST_PATH = (
    Path(__file__).parent.parent
    / "data"
    / "nb_round1_candidates_2026-05-07.json"
)


VALID_CLUSTERS = {
    "placeholder_empty",
    "playbook_artifact",
    "orphan_unclear",
    "research_heavy",
    "subhi_merge",
    "zero_value_orphan",
}

VALID_MATCH_STATUSES = {"exact", "fuzzy", "not_found"}
VALID_DRIFT_STATUSES = {"consistent", "drifted", "unknown_via_mcp_failure"}
# Initial cluster mapping (R1) + post-apply transitions (R1, R1.5).
# Same field doubles as transition record across rounds; enum widens each time.
VALID_PROPOSED_ACTIONS = {
    # R1 initial: cluster mapping
    "KILL", "EXPORT", "ORPHAN_REVIEW",
    # R1 transitions
    "APOPTOSIS_DONE", "RENAME_FAIL",
    # R1.5 transitions (Zero decision 2026-05-07: 19 ambigui resolved)
    "MERGED", "DELETED", "DELETE_BLOCKED", "DELETE_VERIFIED_NOT_LIVE",
}

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.fixture(scope="module")
def manifest():
    assert MANIFEST_PATH.exists(), f"manifest missing at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text())


def test_manifest_json_loads_valid(manifest):
    assert isinstance(manifest, dict)


def test_manifest_has_required_top_level_fields(manifest):
    for field in ("schema_version", "generated_at", "candidates_count", "candidates", "clusters_summary"):
        assert field in manifest, f"missing top-level field: {field}"


def test_candidates_count_matches_list_length(manifest):
    # R1 had 36 entries; R1.5 removed 9 orphan_unclear stub UUIDs after Zero
    # confirmed they were placeholder slots not corresponding to real NLM NBs.
    # Resulting size: 36 - 9 = 27 entries (post-R1.5).
    assert manifest["candidates_count"] == len(manifest["candidates"])
    assert manifest["candidates_count"] in (27, 36), (
        f"unexpected candidate count {manifest['candidates_count']} (expect 27 post-R1.5 or 36 pre-R1.5)"
    )


def test_each_candidate_has_required_fields(manifest):
    required = {
        "uuid", "name_snapshot", "name_live", "cluster",
        "source_count_snapshot", "source_count_live", "drift_status",
        "proposed_action", "match_status", "match_evidence",
        "peer_uuids", "notes",
    }
    for c in manifest["candidates"]:
        missing = required - set(c.keys())
        assert not missing, f"candidate {c.get('uuid')} missing: {missing}"


def test_each_candidate_uuid_format(manifest):
    for c in manifest["candidates"]:
        assert UUID_RE.match(c["uuid"]), f"bad UUID: {c['uuid']}"


def test_cluster_values_are_in_enum(manifest):
    for c in manifest["candidates"]:
        assert c["cluster"] in VALID_CLUSTERS, f"bad cluster: {c['cluster']}"


def test_match_status_values_are_in_enum(manifest):
    for c in manifest["candidates"]:
        assert c["match_status"] in VALID_MATCH_STATUSES
        assert c["drift_status"] in VALID_DRIFT_STATUSES
        assert c["proposed_action"] in VALID_PROPOSED_ACTIONS


def test_clusters_summary_matches_actual_counts(manifest):
    actual: dict[str, int] = {k: 0 for k in VALID_CLUSTERS}
    for c in manifest["candidates"]:
        actual[c["cluster"]] += 1
    expected = manifest["clusters_summary"]
    assert actual == expected, f"clusters_summary drift: actual={actual} declared={expected}"
