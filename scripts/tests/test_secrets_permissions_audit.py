"""Tests for scripts/secrets_permissions_audit.py (superscar #4 auditor).

Loaded via importlib.util.spec_from_file_location so the test does not
depend on `scripts` being an importable package on sys.path.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

_MODULE_PATH = Path(__file__).parents[1] / "secrets_permissions_audit.py"


def _load_module(open_chain: bool = True) -> ModuleType:
    """Load the auditor.

    `open_chain=True` (the default) declares that every directory above the
    file under test permits traversal. That is not decoration: macOS puts
    pytest's `tmp_path` under a 0700 `/var/folders/.../T`, so a file written
    there is unreachable BY CONSTRUCTION and `scan()` rightly ignores it.
    Tests about name matching, mode bits, depth caps or output shape are not
    tests about reachability — they say so here, rather than letting the
    machine's own filesystem quietly decide their result (which would make
    them pass in Linux CI and fail on every developer's Mac).

    The reachability tests themselves pass `open_chain=False` and exercise
    the real function.
    """
    spec = importlib.util.spec_from_file_location(
        "secrets_permissions_audit", _MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if open_chain:
        module.reachable_by = lambda path: (True, True)
    return module


audit = _load_module()


def _mode_of(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _paths(findings) -> set:
    return {f.path for f in findings}


# --------------------------------------------------------------------------
# 1. GUILT — world-readable .env.master is found
# --------------------------------------------------------------------------


def test_guilt_env_master_world_readable(tmp_path: Path) -> None:
    target = tmp_path / ".env.master"
    target.write_text("SECRET=deadbeef\n")
    target.chmod(0o644)

    findings = audit.scan([tmp_path], max_depth=4)

    assert target in _paths(findings)
    finding = next(f for f in findings if f.path == target)
    assert finding.mode == 0o644


# --------------------------------------------------------------------------
# 2. GUILT — backup inherits sensitivity of its base file
# --------------------------------------------------------------------------


def test_guilt_backup_token_inherits_sensitivity(tmp_path: Path) -> None:
    target = tmp_path / "service.token.bak-20260101"
    target.write_text("tok_deadbeef\n")
    target.chmod(0o644)

    findings = audit.scan([tmp_path], max_depth=4)

    assert target in _paths(findings)


# --------------------------------------------------------------------------
# 3. INNOCENCE — locked-down .env.master (0600) is not a finding
# --------------------------------------------------------------------------


def test_innocence_env_master_locked_down(tmp_path: Path) -> None:
    target = tmp_path / ".env.master"
    target.write_text("SECRET=deadbeef\n")
    target.chmod(0o600)

    findings = audit.scan([tmp_path], max_depth=4)

    assert target not in _paths(findings)


# --------------------------------------------------------------------------
# 4. INNOCENCE — public key and an ordinary doc are never findings
# --------------------------------------------------------------------------


def test_innocence_public_key_and_readme_excluded(tmp_path: Path) -> None:
    pub_key = tmp_path / "id_rsa.pub"
    pub_key.write_text("ssh-rsa AAAAB3NzaC1yc2E...\n")
    pub_key.chmod(0o644)

    readme = tmp_path / "README.md"
    readme.write_text("# hello world\n")
    readme.chmod(0o644)

    findings = audit.scan([tmp_path], max_depth=4)

    assert pub_key not in _paths(findings)
    assert readme not in _paths(findings)


# --------------------------------------------------------------------------
# 4b. INNOCENCE — tmp/jiti cache dirs are pruned (2026-07-05 Pro false-positive
# cluster: ~34 jiti *.cjs cache files under ~/.openclaw/tmp/jiti/), while a
# sibling secret-like file OUTSIDE those dirs is still caught (guilt preserved)
# --------------------------------------------------------------------------


def test_innocence_tmp_and_jiti_cache_dirs_are_pruned(tmp_path: Path) -> None:
    jiti_dir = tmp_path / "tmp" / "jiti"
    jiti_dir.mkdir(parents=True)
    cached_token_file = jiti_dir / "some-token-cache.cjs"
    cached_token_file.write_text("// jiti transpile cache\n")
    cached_token_file.chmod(0o644)

    real_secret = tmp_path / ".env.master"
    real_secret.write_text("SECRET=deadbeef\n")
    real_secret.chmod(0o644)

    findings = audit.scan([tmp_path], max_depth=4)

    assert cached_token_file not in _paths(findings)
    assert real_secret in _paths(findings)


# --------------------------------------------------------------------------
# 5. Symlink to a 0644 secret is skipped (never followed)
# --------------------------------------------------------------------------


def test_symlink_to_secret_is_skipped(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real_secret = real_dir / ".env.master"
    real_secret.write_text("SECRET=deadbeef\n")
    real_secret.chmod(0o644)

    link_dir = tmp_path / "link"
    link_dir.mkdir()
    symlink_path = link_dir / ".env.master"
    symlink_path.symlink_to(real_secret)

    findings = audit.scan([link_dir], max_depth=4)

    assert symlink_path not in _paths(findings)


# --------------------------------------------------------------------------
# 6. --fix: chmods to 0600, verified, and a re-scan is clean
# --------------------------------------------------------------------------


def test_fix_chmods_to_0600_and_rescan_is_clean(tmp_path: Path) -> None:
    target = tmp_path / ".env.master"
    target.write_text("SECRET=deadbeef\n")
    target.chmod(0o644)

    findings = audit.scan([tmp_path], max_depth=4)
    assert len(findings) == 1

    fixed, failed, failures = audit.fix_findings(findings)

    assert fixed == 1
    assert failed == 0
    assert failures == []
    assert _mode_of(target) == 0o600

    rescanned = audit.scan([tmp_path], max_depth=4)
    assert rescanned == []


def test_fix_via_main_cli_exit_codes(tmp_path: Path) -> None:
    target = tmp_path / ".env.master"
    target.write_text("SECRET=deadbeef\n")
    target.chmod(0o644)

    exit_code = audit.main(["--no-default-roots", "--root", str(tmp_path), "--fix"])

    assert exit_code == 0
    assert _mode_of(target) == 0o600


# --------------------------------------------------------------------------
# 7. Depth cap: a match 6 levels down is not found with default max-depth 4
# --------------------------------------------------------------------------


def test_depth_cap_excludes_depth_six_with_default_max_depth(tmp_path: Path) -> None:
    deep_dir = tmp_path
    for i in range(6):
        deep_dir = deep_dir / f"d{i}"
    deep_dir.mkdir(parents=True)
    target = deep_dir / ".env.master"
    target.write_text("SECRET=deadbeef\n")
    target.chmod(0o644)

    findings_default = audit.scan([tmp_path])  # default max_depth
    assert target not in _paths(findings_default)

    findings_deep = audit.scan([tmp_path], max_depth=6)
    assert target in _paths(findings_deep)


# --------------------------------------------------------------------------
# Extra coverage: report-mode exit codes, JSON shape, machine_label
# --------------------------------------------------------------------------


def test_main_report_mode_exit_codes(tmp_path: Path) -> None:
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    (clean_dir / "README.md").write_text("benign\n")  # empty dir would be BLIND (exit 2)
    assert audit.main(["--no-default-roots", "--root", str(clean_dir)]) == 0

    dirty_dir = tmp_path / "dirty"
    dirty_dir.mkdir()
    (dirty_dir / ".env.master").write_text("SECRET=1\n")
    (dirty_dir / ".env.master").chmod(0o644)
    assert audit.main(["--no-default-roots", "--root", str(dirty_dir)]) == 1


def test_json_output_shape(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    target = tmp_path / ".env.master"
    target.write_text("SECRET=1\n")
    target.chmod(0o644)

    exit_code = audit.main(["--no-default-roots", "--root", str(tmp_path), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 1
    import json

    payload = json.loads(captured.out)
    assert payload["count"] == 1
    assert payload["fixed"] is None
    assert payload["findings"][0]["mode"] == "0644"
    assert payload["findings"][0]["path"] == str(target)
    assert "machine" in payload


@pytest.mark.parametrize(
    "hostname,expected",
    [
        ("Air-M5", "m5"),
        ("Air-M5.local", "m5"),
        ("Mini-Pro2.local", "mini"),
        ("nuzantara", "pro"),
        ("some-other-host", "some-other-host"),
    ],
)
def test_machine_label(hostname: str, expected: str) -> None:
    assert audit.machine_label(hostname) == expected


def test_backup_of_pem_matches_via_stripped_name(tmp_path: Path) -> None:
    target = tmp_path / "server.pem.bak"
    target.write_text("-----BEGIN PRIVATE KEY-----\n")
    target.chmod(0o644)

    findings = audit.scan([tmp_path], max_depth=4)

    assert target in _paths(findings)


def test_backup_of_public_key_stays_excluded(tmp_path: Path) -> None:
    target = tmp_path / "id_rsa.pub.bak"
    target.write_text("ssh-rsa AAAA...\n")
    target.chmod(0o644)

    findings = audit.scan([tmp_path], max_depth=4)

    assert target not in _paths(findings)


# ---------------------------------------------------------------- blind-scan guard


def test_blind_scan_exits_2_never_clean(tmp_path, capsys):
    """W84 dead-green: roots exist but zero files traversed → exit 2, not 0."""
    empty_root = tmp_path / "blindroot"
    empty_root.mkdir()
    rc = audit.main(["--no-default-roots", "--root", str(empty_root), "--json"])
    assert rc == 2
    import json as _json

    payload = _json.loads(capsys.readouterr().out)
    assert payload["blind"] is True
    assert payload["files_traversed"] == 0


def test_non_blind_clean_scan_exits_0(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir()
    benign = root / "README.md"
    benign.write_text("hello")
    rc = audit.main(["--no-default-roots", "--root", str(root), "--json"])
    assert rc == 0
    import json as _json

    payload = _json.loads(capsys.readouterr().out)
    assert payload["blind"] is False
    assert payload["files_traversed"] >= 1


# --------------------------------------------------------------------------
# Effective reachability (2026-08-06): the mode says who MAY read, the
# directory chain says who can get there. Both must hold for exposure.
#
# These tests declare the chain instead of inheriting the machine's, on
# purpose: on macOS `/var/folders/.../T` is 0700, so anything written under
# pytest's tmp_path is unreachable by construction. A test built on it would
# pass its innocence case for a reason that has nothing to do with the code,
# and fail its guilt case on every developer machine.
# --------------------------------------------------------------------------


def _chain(module: ModuleType, monkeypatch: pytest.MonkeyPatch, table: dict) -> None:
    """Declare (group_x, other_x) per directory; anything absent is 0755."""
    monkeypatch.setattr(
        module, "_dir_traversal", lambda d, _t=table: _t.get(d, (True, True))
    )


def test_one_tight_directory_anywhere_in_the_chain_closes_the_path() -> None:
    """INNOCENCE: the walk must go all the way up, not one level."""
    module = _load_module(open_chain=False)
    monkeypatch = pytest.MonkeyPatch()
    try:
        # The file's own directory is wide open; its GRANDparent is not.
        _chain(module, monkeypatch, {"/a": (False, False)})
        monkeypatch.setattr(Path, "resolve", lambda self: self)
        group, other = module.reachable_by(Path("/a/b/c/creds.env"))
    finally:
        monkeypatch.undo()

    assert (group, other) == (False, False)


def test_a_fully_permissive_chain_stays_reachable() -> None:
    """GUILT: without this the innocence test above could pass vacuously."""
    module = _load_module(open_chain=False)
    monkeypatch = pytest.MonkeyPatch()
    try:
        _chain(module, monkeypatch, {})
        monkeypatch.setattr(Path, "resolve", lambda self: self)
        group, other = module.reachable_by(Path("/a/b/c/creds.env"))
    finally:
        monkeypatch.undo()

    assert (group, other) == (True, True)


def test_group_and_other_are_judged_separately() -> None:
    """A chain can admit the group and refuse everyone else."""
    module = _load_module(open_chain=False)
    monkeypatch = pytest.MonkeyPatch()
    try:
        _chain(module, monkeypatch, {"/a": (True, False)})
        monkeypatch.setattr(Path, "resolve", lambda self: self)
        group, other = module.reachable_by(Path("/a/b/creds.env"))
    finally:
        monkeypatch.undo()

    assert group is True
    assert other is False


def test_unstattable_directory_is_treated_as_reachable() -> None:
    """FAIL-CLOSED: cannot-verify is not clean (W106b).

    A guard that answers 'unreachable' when it simply could not look would
    absolve exactly the file it exists to catch.
    """
    module = _load_module(open_chain=False)

    assert module._dir_traversal("/definitely/not/a/real/directory/xyzzy") == (
        True,
        True,
    )


def test_scan_skips_a_readable_file_that_nobody_can_reach(tmp_path: Path) -> None:
    """INNOCENCE, end to end: 0644 under an unreachable chain is not a finding.

    This is the class that made every fleet run report the same documentation
    files forever, which is how a guard stops being read.
    """
    module = _load_module()
    secret = tmp_path / "credentials.env"
    secret.write_text("x")
    os.chmod(secret, 0o644)

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(module, "reachable_by", lambda p: (False, False))
        findings = module.scan([tmp_path])
    finally:
        monkeypatch.undo()

    assert findings == []


def test_a_symlinked_root_is_audited_not_silently_dropped(tmp_path: Path) -> None:
    """GUILT: the caller NAMED this root; auditing nothing is not 'clean'.

    Live case that found this: the memory directory every runbook cites,
    `~/.claude/projects/<project>/memory`, is reached through two symlinks.
    Auditing it returned count 0, roots_existing 0, exit 0 — a clean verdict
    over zero files, with the blind-scan guard unable to fire because it
    requires at least one root to exist.
    """
    module = _load_module()
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    secret = real_dir / "creds.env"
    secret.write_text("x")
    os.chmod(secret, 0o644)
    link = tmp_path / "link"
    link.symlink_to(real_dir)

    stats: dict = {}
    findings = module.scan([link], stats=stats)

    assert [f.path.name for f in findings] == ["creds.env"]
    assert stats["roots_existing"] == 1
    assert stats["files_traversed"] == 1


def test_a_symlink_met_during_the_walk_is_still_not_followed(tmp_path: Path) -> None:
    """INNOCENCE: resolving a NAMED root must not loosen the walk itself.

    Paired with the test above: a link the caller named is audited, a link
    the walk stumbles into is not — that asymmetry is the whole point, and
    without this test the fix could quietly become 'follow every symlink'.
    """
    module = _load_module()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_secret = outside / "creds.env"
    outside_secret.write_text("x")
    os.chmod(outside_secret, 0o644)

    root = tmp_path / "root"
    root.mkdir()
    (root / "escape").symlink_to(outside)

    findings = module.scan([root])

    assert findings == []


def test_a_broken_symlink_root_is_treated_as_a_missing_path(tmp_path: Path) -> None:
    """A link to nowhere is the documented missing-root case, not a crash."""
    module = _load_module()
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "does-not-exist")

    stats: dict = {}
    findings = module.scan([dangling], stats=stats)

    assert findings == []
    assert stats.get("roots_existing", 0) == 0


def test_the_real_root_and_its_symlink_are_walked_once(tmp_path: Path) -> None:
    """Naming a directory twice, once through a link, must not double-report."""
    module = _load_module()
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    secret = real_dir / "creds.env"
    secret.write_text("x")
    os.chmod(secret, 0o644)
    link = tmp_path / "link"
    link.symlink_to(real_dir)

    findings = module.scan([real_dir, link])

    assert len(findings) == 1


def test_scan_still_reports_the_same_file_when_the_chain_is_open(
    tmp_path: Path,
) -> None:
    """GUILT, end to end, same file: only the chain differs.

    Paired with the test above so that neither can pass because the file was
    never a candidate in the first place.
    """
    module = _load_module()
    secret = tmp_path / "credentials.env"
    secret.write_text("x")
    os.chmod(secret, 0o644)

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(module, "reachable_by", lambda p: (True, True))
        findings = module.scan([tmp_path])
    finally:
        monkeypatch.undo()

    assert [f.path.name for f in findings] == ["credentials.env"]
    assert findings[0].mode == 0o644
