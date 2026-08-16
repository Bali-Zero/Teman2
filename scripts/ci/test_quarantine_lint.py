#!/usr/bin/env python3
"""Guilt + innocence corpus for `quarantine_lint.py`.

Runs standalone (`python3 scripts/ci/test_quarantine_lint.py`) and under
pytest. Covers: (1) the pure judgment functions directly (no I/O), and
(2) `run_lint`/`main` end-to-end against real temp directories on disk, so
the YAML-loading + glob-matching + exit-code contract are exercised for
real, not mocked.

Team-lead's mandate (Merge-OS v3 step 6 slice 1) named these guilt cases
explicitly: entry without owner -> red; expiry passed -> red; quarantine of
a floor-protected test -> red; orphan floor pattern -> red; empty
quarantine + populated floor -> green. All five are here, plus the
additional structural checks the validator implements (14-day cap,
future first_seen, malformed sample_size/flake_rate, unparseable dates,
missing floor fields, malformed YAML, missing/empty floor dir).
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quarantine_lint import (  # noqa: E402
    main,
    node_id_path,
    path_matches_any_pattern,
    run_lint,
    validate_floor_entry,
    validate_quarantine_entry,
)

NOW = date(2026, 8, 15)


def _valid_quarantine_entry(**overrides):
    entry = {
        "node_id": "apps/backend-rag/backend/tests/unit/test_something_flaky.py::test_flaky_thing",
        "owner": "lane-c-security",
        "issue": "https://github.com/balizero/nuzantara/issues/9999",
        "failure_fingerprint": "AssertionError: timing race in test_flaky_thing",
        "first_seen": date(2026, 8, 10),
        "expires_at": date(2026, 8, 20),  # 10 days, within the 14-day cap
        "sample_size": 12,
        "observed_flake_rate": 0.25,
        "reason": "known timing race, ticket filed, fix in progress",
    }
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------
# Pure-function tests — no filesystem.
# ---------------------------------------------------------------------------

# --- node_id_path -------------------------------------------------------


def test_a_node_id_path_strips_the_pytest_nodeid_suffix():
    assert node_id_path("apps/x/test_y.py::TestClass::test_method") == "apps/x/test_y.py"


def test_a_node_id_path_bare_file_path_is_unchanged():
    assert node_id_path("apps/x/test_y.py") == "apps/x/test_y.py"


# --- path_matches_any_pattern -------------------------------------------


def test_a_glob_pattern_matches_a_real_nested_file(tmp_repo):
    assert path_matches_any_pattern(
        "apps/backend-rag/backend/tests/test_auth_flow.py",
        ["apps/backend-rag/**/test_*auth*.py"],
        tmp_repo,
    )


def test_b_glob_pattern_does_not_match_an_unrelated_lookalike_file(tmp_repo):
    """Innocence twin of the above: a file that merely lives in a sibling
    directory, and does not match the glob's own name-shape, must not be
    swept in by accident."""
    assert not path_matches_any_pattern(
        "apps/backend-rag/backend/tests/test_pricing_flow.py",
        ["apps/backend-rag/**/test_*auth*.py"],
        tmp_repo,
    )


def test_c_literal_pattern_matches_only_the_exact_path(tmp_repo):
    literal = "apps/backend-rag/backend/tests/db/test_backend_stability_gate.py"
    assert path_matches_any_pattern(literal, [literal], tmp_repo)
    assert not path_matches_any_pattern(
        "apps/backend-rag/backend/tests/db/test_backend_stability_gate_v2.py",
        [literal],
        tmp_repo,
    )


# --- validate_quarantine_entry (guilt) -----------------------------------


def test_guilt_missing_owner_is_a_violation():
    entry = _valid_quarantine_entry()
    del entry["owner"]
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("owner" in v.message for v in violations), violations


def test_guilt_expired_entry_is_a_violation():
    entry = _valid_quarantine_entry(
        first_seen=date(2026, 7, 20), expires_at=date(2026, 8, 1)
    )
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("EXPIRED" in v.message for v in violations), violations


def test_guilt_grant_longer_than_14_days_is_a_violation():
    entry = _valid_quarantine_entry(
        first_seen=date(2026, 8, 1), expires_at=date(2026, 8, 20)  # 19 days
    )
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("capped" in v.message for v in violations), violations


def test_guilt_first_seen_in_the_future_is_a_violation():
    entry = _valid_quarantine_entry(
        first_seen=date(2026, 8, 16), expires_at=date(2026, 8, 26)
    )
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("future" in v.message for v in violations), violations


def test_guilt_negative_sample_size_is_a_violation():
    entry = _valid_quarantine_entry(sample_size=0)
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("sample_size" in v.message for v in violations), violations


def test_guilt_out_of_range_flake_rate_is_a_violation():
    entry = _valid_quarantine_entry(observed_flake_rate=1.4)
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("observed_flake_rate" in v.message for v in violations), violations


def test_guilt_unparseable_first_seen_is_a_violation():
    entry = _valid_quarantine_entry(first_seen="not-a-date")
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("unparseable" in v.message for v in violations), violations


# --- validate_quarantine_entry (innocence) --------------------------------


def test_innocence_a_well_formed_entry_within_the_cap_and_not_expired_is_clean():
    entry = _valid_quarantine_entry()
    assert validate_quarantine_entry(entry, "f.yaml", NOW) == []


def test_innocence_expiry_exactly_equal_to_now_is_not_yet_expired():
    """Boundary the spalla-review flagged as untested: a grant expiring
    ON `now` is still valid THROUGH that day (strict `<` in the expired
    check) — pin the inequality direction so a future refactor that flips
    it goes red here first."""
    entry = _valid_quarantine_entry(
        first_seen=date(2026, 8, 5), expires_at=NOW
    )
    assert validate_quarantine_entry(entry, "f.yaml", NOW) == []


def test_innocence_expiry_exactly_14_days_out_is_not_capped():
    """Boundary: exactly 14 days is allowed, 15 is not (strictly-below and
    strictly-above tested, not the exact float/int edge alone — pinning
    W97's 'exactly-N-round' suspicion by testing both sides)."""
    entry = _valid_quarantine_entry(
        first_seen=date(2026, 8, 1), expires_at=date(2026, 8, 15)
    )
    assert validate_quarantine_entry(entry, "f.yaml", NOW) == []


def test_innocence_expiry_15_days_out_is_capped():
    entry = _valid_quarantine_entry(
        first_seen=date(2026, 8, 1), expires_at=date(2026, 8, 16)
    )
    violations = validate_quarantine_entry(entry, "f.yaml", NOW)
    assert any("capped" in v.message for v in violations), violations


# --- validate_floor_entry (guilt + innocence) -----------------------------


def test_guilt_floor_entry_missing_category_is_a_violation():
    entry = {"id": "x", "patterns": ["apps/**/test_x.py"]}
    violations = validate_floor_entry(entry, "f.yaml", Path("/nonexistent"))
    assert any("category" in v.message for v in violations), violations


def test_guilt_floor_entry_empty_patterns_list_is_a_violation():
    """An empty list is falsy, so it is caught by the missing/empty
    required-field guard (checked first) rather than the type guard below
    it — still a violation naming 'patterns', just via the earlier check."""
    entry = {"id": "x", "category": "X", "patterns": []}
    violations = validate_floor_entry(entry, "f.yaml", Path("/nonexistent"))
    assert any("patterns" in v.message for v in violations), violations


def test_guilt_floor_entry_non_list_patterns_is_a_violation():
    """Twin of the above for the type guard itself: a truthy `patterns`
    that isn't a list (e.g. a bare string) must still be rejected — this
    is the only way to reach the 'must be a non-empty list' branch, since
    an empty list is intercepted earlier by the missing-field guard."""
    entry = {"id": "x", "category": "X", "patterns": "apps/**/test_x.py"}
    violations = validate_floor_entry(entry, "f.yaml", Path("/nonexistent"))
    assert any("non-empty list" in v.message for v in violations), violations


def test_guilt_floor_orphan_pattern_is_a_violation(tmp_repo):
    entry = {
        "id": "x",
        "category": "X",
        "patterns": ["apps/backend-rag/**/test_*nonexistent_shape*.py"],
    }
    violations = validate_floor_entry(entry, "f.yaml", tmp_repo)
    assert any("orphan pattern" in v.message for v in violations), violations


def test_guilt_floor_non_string_pattern_element_is_a_violation_not_a_crash(tmp_repo):
    """spalla-review 2026-08-15: an unquoted non-string element in a
    `patterns` list (e.g. `patterns: [123]`) used to raise an unguarded
    TypeError from `"*" in pattern`. Must degrade to a Violation, never
    crash the linter itself."""
    entry = {"id": "x", "category": "X", "patterns": [123, "apps/backend-rag/**/test_*auth*.py"]}
    violations = validate_floor_entry(entry, "f.yaml", tmp_repo)
    assert any("non-string pattern" in v.message for v in violations), violations


def test_innocence_floor_pattern_matching_real_files_is_clean(tmp_repo):
    entry = {
        "id": "x",
        "category": "X",
        "patterns": ["apps/backend-rag/**/test_*auth*.py"],
    }
    assert validate_floor_entry(entry, "f.yaml", tmp_repo) == []


# ---------------------------------------------------------------------------
# End-to-end tests against real temp directories (run_lint / main).
# ---------------------------------------------------------------------------


class _TmpRepo:
    """Builds a throwaway repo tree with a handful of real test files so
    glob patterns have something genuine to match — never a mocked
    filesystem, per W65 (no phantom paths, verified against a real tree)."""

    def __init__(self, base: Path):
        self.root = base
        files = [
            "apps/backend-rag/backend/tests/test_auth_flow.py",
            "apps/backend-rag/backend/tests/test_pricing_flow.py",
            "apps/backend-rag/backend/tests/unit/test_something_flaky.py",
            "apps/backend-rag/backend/tests/db/test_backend_stability_gate.py",
        ]
        for rel in files:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("def test_x():\n    assert True\n", encoding="utf-8")


def _write_floor(root: Path, filename: str, body: str) -> None:
    d = root / "infra" / "merge-os" / "critical-floor.d"
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(body, encoding="utf-8")


def _write_quarantine(root: Path, filename: str, body: str) -> None:
    d = root / "infra" / "merge-os" / "quarantine.d"
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(body, encoding="utf-8")


_DEFAULT_FLOOR_YAML = """\
id: auth-authorization
category: Auth
patterns:
  - apps/backend-rag/**/test_*auth*.py
"""


def _e2e(tmp_path_factory_dir, floor_yaml=_DEFAULT_FLOOR_YAML, quarantine_files=None):
    root = tmp_path_factory_dir
    _TmpRepo(root)
    if floor_yaml is not None:
        _write_floor(root, "auth-authorization.yaml", floor_yaml)
    for filename, body in (quarantine_files or {}).items():
        _write_quarantine(root, filename, body)
    return run_lint(
        root,
        root / "infra" / "merge-os" / "quarantine.d",
        root / "infra" / "merge-os" / "critical-floor.d",
        NOW,
    )


def test_innocence_empty_quarantine_plus_populated_floor_is_clean():
    with tempfile.TemporaryDirectory() as td:
        result = _e2e(Path(td))
        assert result.ok, (result.violations, result.cannot_verify)


def test_innocence_a_well_formed_non_colliding_quarantine_entry_is_clean():
    with tempfile.TemporaryDirectory() as td:
        body = """\
node_id: "apps/backend-rag/backend/tests/unit/test_something_flaky.py::test_flaky_thing"
owner: lane-c-security
issue: "https://github.com/balizero/nuzantara/issues/9999"
failure_fingerprint: "AssertionError: timing race"
first_seen: 2026-08-10
expires_at: 2026-08-20
sample_size: 12
observed_flake_rate: 0.25
reason: "known timing race, ticket filed"
"""
        result = _e2e(Path(td), quarantine_files={"flaky-thing.yaml": body})
        assert result.ok, (result.violations, result.cannot_verify)


def test_guilt_quarantine_of_a_floor_protected_test_is_a_violation():
    with tempfile.TemporaryDirectory() as td:
        body = """\
node_id: "apps/backend-rag/backend/tests/test_auth_flow.py::test_login"
owner: lane-c-security
issue: "https://github.com/balizero/nuzantara/issues/9999"
failure_fingerprint: "AssertionError: flaky auth timing"
first_seen: 2026-08-10
expires_at: 2026-08-20
sample_size: 12
observed_flake_rate: 0.25
reason: "flaky, ticket filed"
"""
        result = _e2e(Path(td), quarantine_files={"auth-flake.yaml": body})
        assert not result.ok
        assert any("critical floor" in str(v) for v in result.violations), result.violations


def test_guilt_orphan_floor_pattern_is_cannot_verify_via_run_lint():
    orphan_floor = """\
id: auth-authorization
category: Auth
patterns:
  - apps/backend-rag/**/test_*totally_made_up_shape*.py
"""
    with tempfile.TemporaryDirectory() as td:
        result = _e2e(Path(td), floor_yaml=orphan_floor)
        assert not result.ok
        assert any("orphan pattern" in str(v) for v in result.violations), result.violations


def test_guilt_missing_floor_dir_is_cannot_verify():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _TmpRepo(root)
        # no critical-floor.d at all
        result = run_lint(
            root,
            root / "infra" / "merge-os" / "quarantine.d",
            root / "infra" / "merge-os" / "critical-floor.d",
            NOW,
        )
        assert not result.ok
        assert result.cannot_verify, "missing floor dir must be CANNOT VERIFY, not a silent clean pass"


def test_guilt_malformed_yaml_is_cannot_verify():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _TmpRepo(root)
        _write_floor(root, "auth-authorization.yaml", _DEFAULT_FLOOR_YAML)
        _write_quarantine(root, "broken.yaml", "node_id: [unclosed\n  owner: x")
        result = run_lint(
            root,
            root / "infra" / "merge-os" / "quarantine.d",
            root / "infra" / "merge-os" / "critical-floor.d",
            NOW,
        )
        assert not result.ok
        assert result.cannot_verify, result.violations


def test_innocence_main_cli_exits_zero_on_a_clean_real_tree():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _TmpRepo(root)
        _write_floor(root, "auth-authorization.yaml", _DEFAULT_FLOOR_YAML)
        rc = main(
            [
                "--repo-root", str(root),
                "--quarantine-dir", str(root / "infra" / "merge-os" / "quarantine.d"),
                "--floor-dir", str(root / "infra" / "merge-os" / "critical-floor.d"),
                "--now", NOW.isoformat(),
            ]
        )
        assert rc == 0


def test_guilt_main_cli_exits_one_on_a_floor_collision():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _TmpRepo(root)
        _write_floor(root, "auth-authorization.yaml", _DEFAULT_FLOOR_YAML)
        body = """\
node_id: "apps/backend-rag/backend/tests/test_auth_flow.py::test_login"
owner: lane-c-security
issue: "https://github.com/balizero/nuzantara/issues/9999"
failure_fingerprint: "x"
first_seen: 2026-08-10
expires_at: 2026-08-20
sample_size: 12
observed_flake_rate: 0.25
reason: "x"
"""
        _write_quarantine(root, "collide.yaml", body)
        rc = main(
            [
                "--repo-root", str(root),
                "--quarantine-dir", str(root / "infra" / "merge-os" / "quarantine.d"),
                "--floor-dir", str(root / "infra" / "merge-os" / "critical-floor.d"),
                "--now", NOW.isoformat(),
            ]
        )
        assert rc == 1


def test_guilt_main_cli_exits_two_on_malformed_now_flag_not_a_crash():
    """spalla-review 2026-08-15: `date.fromisoformat(args.now)` used to be
    unguarded — an operator typo in `--now` raised an unhandled ValueError
    traceback instead of routing through the documented exit-2 path."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _TmpRepo(root)
        _write_floor(root, "auth-authorization.yaml", _DEFAULT_FLOOR_YAML)
        rc = main(
            [
                "--repo-root", str(root),
                "--quarantine-dir", str(root / "infra" / "merge-os" / "quarantine.d"),
                "--floor-dir", str(root / "infra" / "merge-os" / "critical-floor.d"),
                "--now", "not-a-date",
            ]
        )
        assert rc == 2


def test_guilt_main_cli_exits_two_on_missing_floor_dir():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _TmpRepo(root)
        rc = main(
            [
                "--repo-root", str(root),
                "--quarantine-dir", str(root / "infra" / "merge-os" / "quarantine.d"),
                "--floor-dir", str(root / "infra" / "merge-os" / "critical-floor.d"),
                "--now", NOW.isoformat(),
            ]
        )
        assert rc == 2


# ---------------------------------------------------------------------------
# The shipped manifests, exercised against the REAL repo tree — pins that
# the actual infra/merge-os/critical-floor.d/*.yaml files shipped in this
# PR are themselves clean under this same validator (dogfooding).
# ---------------------------------------------------------------------------


def test_the_shipped_manifests_are_clean_against_the_real_repo():
    """Uses `date.today()`, NOT a frozen NOW: this is dogfooding against the
    LIVE quarantine.d, which today is empty but won't stay that way forever.
    A frozen date here would judge a future real grant against a stale
    'now' and could silently keep reporting clean past that grant's actual
    expiry (spalla-review finding, 2026-08-15) — the synthetic-entry tests
    above are correctly frozen (deterministic fixtures), this one must not
    be, because its subject is whatever is actually checked in."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    result = run_lint(
        repo_root,
        repo_root / "infra" / "merge-os" / "quarantine.d",
        repo_root / "infra" / "merge-os" / "critical-floor.d",
        date.today(),
    )
    assert result.ok, (result.violations, result.cannot_verify)


# ---------------------------------------------------------------------------
# pytest fixture (also usable as a plain callable by the standalone runner
# below, via the _tmp_repo_dir shim).
# ---------------------------------------------------------------------------

try:
    import pytest

    @pytest.fixture
    def tmp_repo(tmp_path):
        _TmpRepo(tmp_path)
        return tmp_path

except ImportError:  # pragma: no cover - standalone runner path
    pytest = None


if __name__ == "__main__":
    # Standalone runner: fixture-dependent tests (tmp_repo) are skipped here
    # since there is no pytest fixture machinery outside pytest itself — run
    # `pytest scripts/ci/test_quarantine_lint.py` for the full corpus. This
    # runner still covers every fixture-free test, which is the majority.
    fns = []
    for k, v in sorted(globals().items()):
        if not k.startswith("test_"):
            continue
        code = v.__code__
        if "tmp_repo" in code.co_varnames[: code.co_argcount]:
            continue
        fns.append(v)
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed ({len(fns)} fixture-free of {sum(1 for k in globals() if k.startswith('test_'))} total — run under pytest for full corpus)")
    sys.exit(1 if failed else 0)
