"""Tests for scripts/ci/snapshot_required_contexts.py and its output,
infra/required.d/contexts.json.

Born 2026-08-27 alongside the PR that regenerated the snapshot after Zero's
ruling cut main's required status checks from 27 to 9, then the 30-day
reinstatement rule brought 2 back within the hour (11 live today — see
docs/runbooks/merge-queue-discipline.md §"Required vs advisory checks —
reinstatement rule"). Deliberately does NOT assert a specific count anywhere
(no `== 9`, `== 10`, `== 11`, `== 27`): this repo's own required-context list
has now demonstrably changed twice in one day, and a test pinned to today's
number would need editing on every future ruling — exactly the staleness
docs/runbooks/merge-queue-discipline.md §2 already warns about for hand-
copying the list into prose ("It was 25... and 26 one day later").

What this DOES pin:
  - the checked-in snapshot is well-formed and internally consistent
    (unique names, every context resolves to a real workflow file+job or
    carries a real allowlist reason, `generated_at` is a parseable date);
  - the exact bug this PR fixed — `build_snapshot()` used to hardcode
    `"generated_at": "2026-08-11"` as a Python string literal, so every
    regen silently kept claiming it was generated on 2026-08-11 no matter
    when it actually ran — cannot regress: the function must compute
    today's date, not echo a constant;
  - none of the known consumers of the required-context count hardcode last
    week's number (27) as an equality/inequality check against how many
    contexts exist. This is a targeted regression guard over the specific
    files scripts/probe_merge_gate_integrity.py, .github/workflows/tests.yml,
    .github/workflows/harness-floor.yml, and
    .github/workflows/runbook-section-numbers.yml were found to reference —
    NOT a repo-wide grep, deliberately: cicatrix-superscar.md family #3
    (guard-over-match) is exactly what a blind repo-wide numeric grep would
    become, since "27" and "11" are common integers with no relation to
    required-context counts everywhere else they appear in this repo.

Run:  python3 -m pytest scripts/tests/test_snapshot_required_contexts.py -q
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "snapshot_required_contexts.py"
_spec = importlib.util.spec_from_file_location("snapshot_required_contexts", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]

CONTEXTS_PATH = REPO_ROOT / "infra" / "required.d" / "contexts.json"

# The exact set of files this PR audited and aligned for the 27->9->11 change.
# Scoped deliberately (see module docstring) rather than a repo-wide sweep.
_KNOWN_CONSUMERS = [
    REPO_ROOT / "scripts" / "probe_merge_gate_integrity.py",
    REPO_ROOT / ".github" / "workflows" / "tests.yml",
    REPO_ROOT / ".github" / "workflows" / "harness-floor.yml",
    REPO_ROOT / ".github" / "workflows" / "runbook-section-numbers.yml",
    REPO_ROOT / ".github" / "workflows" / "immune-enforcement.yml",
    REPO_ROOT / ".github" / "workflows" / "merge-gate-integrity-watch.yml",
    REPO_ROOT / "scripts" / "ci" / "check_required_workflow_conformance.py",
    REPO_ROOT / "scripts" / "ci" / "required_context_map.py",
]

# A numeric equality/inequality against a required/context COUNT — the shape
# that goes stale the moment branch protection changes. Deliberately narrow:
# requires "context"/"required" within ~20 chars of a comparison operator and
# a bare integer, so it does not fire on unrelated numbers (timeouts, ports,
# line counts, ...) elsewhere in these same files.
_HARDCODED_COUNT_RE = re.compile(
    r"(?:len\([^)]*contexts?[^)]*\)|required[a-z_]*contexts?)\s*(?:==|>=|<=|>|<)\s*27\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------- snapshot file itself


def _load_snapshot() -> dict:
    assert CONTEXTS_PATH.exists(), f"missing {CONTEXTS_PATH} — run scripts/ci/snapshot_required_contexts.py"
    return json.loads(CONTEXTS_PATH.read_text(encoding="utf-8"))


def test_snapshot_has_the_documented_top_level_shape():
    snap = _load_snapshot()
    for key in ("_doc", "generated_at", "source", "repo", "branch", "regen_command", "contexts"):
        assert key in snap, f"snapshot missing top-level key {key!r}"
    assert snap["source"] in ("api", "derived")
    assert isinstance(snap["contexts"], list)
    assert len(snap["contexts"]) > 0, "an empty required-context list is fail-OPEN, not a valid snapshot (W84)"


def test_generated_at_is_a_real_parseable_date_not_a_placeholder():
    snap = _load_snapshot()
    generated_at = snap["generated_at"]
    assert generated_at and generated_at != "unknown"
    # Raises ValueError (failing the test) on a non-ISO-date placeholder.
    datetime.date.fromisoformat(generated_at)


def test_no_duplicate_context_names_in_snapshot():
    snap = _load_snapshot()
    names = [c["name"] for c in snap["contexts"]]
    assert len(names) == len(set(names)), f"duplicate context name(s) in snapshot: {names}"


def test_every_context_resolves_to_a_workflow_or_carries_a_real_allowlist_reason():
    snap = _load_snapshot()
    for c in snap["contexts"]:
        assert "name" in c and c["name"], f"context entry missing a name: {c}"
        if c.get("workflow_file") is None:
            reason = c.get("allowlist_reason", "")
            assert reason and "UNRESOLVED by scripts/ci/required_context_map.py" not in reason, (
                f"context {c['name']!r} has no workflow_file and no real allowlist reason — "
                "this is the placeholder check_required_workflow_conformance.py exists to reject"
            )
        else:
            assert (REPO_ROOT / c["workflow_file"]).exists(), (
                f"context {c['name']!r} points at {c['workflow_file']}, which does not exist on disk"
            )


# --------------------------------------------------------------- the generated_at bug (regression)


def test_build_snapshot_computes_generated_at_dynamically_not_a_hardcoded_constant(monkeypatch):
    """GUILT baseline this test would have caught: before this PR, build_snapshot()
    wrote the Python string literal "2026-08-11" as `generated_at` on every call,
    regardless of when it actually ran — so a snapshot regenerated today (or on
    any future date) silently claimed it was 16+ days stale. Two calls on two
    different simulated "todays" must produce two different generated_at values;
    a hardcoded constant would make them identical."""
    monkeypatch.setattr(mod, "repo_slug", lambda: "Bali-Zero/Teman2")
    monkeypatch.setattr(
        mod,
        "fetch_via_api",
        lambda repo, branch: [{"name": "Only Context", "app_id": None}],
    )

    class _FakeDate(datetime.date):
        _today = datetime.date(2026, 8, 27)

        @classmethod
        def today(cls):
            return cls._today

    monkeypatch.setattr(mod.datetime, "date", _FakeDate)
    snap_a = mod.build_snapshot("main", None)
    assert snap_a["generated_at"] == "2026-08-27"

    _FakeDate._today = datetime.date(2026, 9, 26)
    snap_b = mod.build_snapshot("main", None)
    assert snap_b["generated_at"] == "2026-09-26"

    assert snap_a["generated_at"] != snap_b["generated_at"], (
        "generated_at did not change between two different simulated dates — "
        "it is hardcoded again"
    )


# --------------------------------------------------------------- known consumers stay dynamic


@pytest.mark.parametrize("path", _KNOWN_CONSUMERS, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_known_consumer_does_not_hardcode_the_stale_27_count_as_a_comparison(path: Path):
    assert path.exists(), f"expected consumer file missing: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    match = _HARDCODED_COUNT_RE.search(text)
    assert match is None, (
        f"{path.relative_to(REPO_ROOT)} hardcodes a required-context count comparison "
        f"against 27 ({match.group(0)!r}) — main required 27 contexts only until Zero's "
        "2026-08-27 ruling; read infra/required.d/contexts.json or the live API instead "
        "of comparing against a fixed integer"
    )
