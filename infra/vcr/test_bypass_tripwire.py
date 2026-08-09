"""Tests for infra/vcr/check_bypass.py — R7's bypass-rate tripwire.

Guilt: a planted direct-read file MUST be caught. Innocence: the accessor's
own internal read (and the declared pre-existing exemptions) must NOT be
caught. "0 found" without this pair is a probe that cannot fail
(final-gate-discipline Q4) — this is the pair that lets it fail.
"""

from __future__ import annotations

from infra.vcr.check_bypass import find_bypass_violations


def _make_repo(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "infra" / "vcr").mkdir(parents=True)
    (tmp_path / "infra" / "healer").mkdir(parents=True)
    return tmp_path


def test_guilt_a_new_consumer_reading_last_json_directly_is_caught(tmp_path):
    repo = _make_repo(tmp_path)
    bad = repo / "scripts" / "new_dashboard.py"
    bad.write_text('report = json.load(open(os.path.expanduser("~/.organism/arsenal/last.json")))\n')
    violations = find_bypass_violations(repo)
    assert "scripts/new_dashboard.py" in violations


def test_guilt_a_new_consumer_using_read_last_flag_is_caught(tmp_path):
    repo = _make_repo(tmp_path)
    bad = repo / "scripts" / "new_wrapper.sh"
    bad.write_text('python3 scripts/arsenal_probe.py --read-last --json\n')
    violations = find_bypass_violations(repo)
    assert "scripts/new_wrapper.sh" in violations


def test_innocence_accessor_own_internal_read_is_not_flagged(tmp_path):
    """The accessor package itself legitimately reads the raw report — it IS
    the enforcement point. infra/vcr/** must never self-flag."""
    repo = _make_repo(tmp_path)
    internal = repo / "infra" / "vcr" / "accessor.py"
    internal.write_text('ARSENAL_REPORT_PATH_DEFAULT = Path.home() / ".organism" / "arsenal" / "last.json"\n')
    violations = find_bypass_violations(repo)
    assert violations == []


def test_innocence_declared_allowlist_files_are_not_flagged(tmp_path):
    """organism_digest.py and healer-run.sh are pre-existing, declared,
    out-of-scope-for-this-pilot readers — not silently exempt, EXPLICITLY
    allowlisted (module docstring names the reason for each)."""
    repo = _make_repo(tmp_path)
    digest = repo / "scripts" / "organism_digest.py"
    digest.write_text('report = _home() / ".organism" / "arsenal" / "last.json"\n')
    healer = repo / "infra" / "healer" / "healer-run.sh"
    healer.write_text('ARSENAL_REPORT="$HOME/.organism/arsenal/last.json"\n')
    violations = find_bypass_violations(repo)
    assert violations == []


def test_guilt_pathlib_join_evasion_of_the_literal_path_is_caught(tmp_path):
    """Codex red-team, 2026-08-03: the original regex only matched the
    literal contiguous substring '.organism/arsenal/last.json' — a pathlib
    join spelling the SAME path (Path.home()/".organism"/"arsenal"/
    "last.json") evaded it entirely. This must now be caught."""
    repo = _make_repo(tmp_path)
    bad = repo / "scripts" / "sneaky_dashboard.py"
    bad.write_text(
        'REPORT = Path.home() / ".organism" / "arsenal" / "last.json"\n'
        "data = json.loads(REPORT.read_text())\n"
    )
    violations = find_bypass_violations(repo)
    assert "scripts/sneaky_dashboard.py" in violations


def test_guilt_string_concatenation_evasion_of_read_last_flag_is_caught(tmp_path):
    """Codex red-team, 2026-08-03: '--read' + '-last' (string concatenation)
    never appears as the contiguous substring '--read-last' in source text,
    so the original regex missed it."""
    repo = _make_repo(tmp_path)
    bad = repo / "scripts" / "sneaky_wrapper.sh"
    bad.write_text('FLAG = "--read" + "-last"\nsubprocess.run(["arsenal_probe.py", FLAG])\n')
    violations = find_bypass_violations(repo)
    assert "scripts/sneaky_wrapper.sh" in violations


def test_innocence_normalization_does_not_false_positive_on_unrelated_text(tmp_path):
    """The normalization (stripping quotes/whitespace/plus) must not fuse
    UNRELATED adjacent tokens into an accidental match."""
    repo = _make_repo(tmp_path)
    clean = repo / "scripts" / "unrelated.py"
    clean.write_text(
        'x = "--read" + "the docs at " + "organism" + "/" + "arsenal_health.md"\n'
        'y = "last" + "modified"\n'
    )
    violations = find_bypass_violations(repo)
    assert violations == []


def test_innocence_a_file_that_merely_mentions_arsenal_probe_by_name_is_clean(tmp_path):
    """A file that talks ABOUT arsenal_probe without reading its raw report
    or using --read-last must not false-positive (scar #3: match the
    entity/pattern, not an unrelated substring)."""
    repo = _make_repo(tmp_path)
    clean = repo / "scripts" / "docs_writer.py"
    clean.write_text('# See scripts/arsenal_probe.py --table for seat health detail.\n')
    violations = find_bypass_violations(repo)
    assert violations == []


def test_the_real_repo_has_zero_unaccounted_bypass_violations():
    """Live proof: run the checker against the REAL repo (this worktree).
    scripts/proprioception.py is allowlisted (it still legitimately carries
    ONE untouched, out-of-pilot-scope --read-last — see check_bypass.py's
    module docstring); this asserts there are no OTHER, undeclared bypasses."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    violations = find_bypass_violations(repo_root)
    assert violations == [], f"unexpected bypass(es): {violations}"


def test_the_new_proprioception_entry_actually_routes_through_the_accessor():
    """R7's real converted consumer, verified directly (not just inferred
    from the bypass scanner going quiet): proprioception's DEFAULT_REGISTRY
    must contain an m5-scoped entry whose target is infra/vcr/cli.py, and
    that target file must actually exist and be runnable."""
    import importlib.util
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "proprioception", repo_root / "scripts" / "proprioception.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    matches = [e for e in mod.DEFAULT_REGISTRY if e["id"] == "arsenal_seats_vcr_m5"]
    assert len(matches) == 1, "expected exactly one arsenal_seats_vcr_m5 entry"
    entry = matches[0]
    assert entry["machines"] == ["m5"]
    assert any("infra/vcr/cli.py" in part for part in entry["target"])

    cli_path = repo_root / "infra" / "vcr" / "cli.py"
    assert cli_path.is_file(), "the entry points at a file that doesn't exist"

    errors = mod.validate_registry(mod.DEFAULT_REGISTRY)
    assert errors == [], f"registry validation broke: {errors}"
