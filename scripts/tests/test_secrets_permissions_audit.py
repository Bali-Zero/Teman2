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
        module.reachable_by = lambda path, cache=None: (True, True)
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
    # credentials.json, not .env.master: .env* is report-only by design
    # (T6/T8) and must never be chmod'ed by fix_findings.
    target = tmp_path / "credentials.json"
    target.write_text("{}\n")
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
    target = tmp_path / "credentials.json"
    target.write_text("{}\n")
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
        module,
        "_dir_traversal",
        lambda d, cache=None, _t=table: _t.get(d, (True, True)),
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
    secret.chmod(0o644)

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(module, "reachable_by", lambda p, cache=None: (False, False))
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
    secret.chmod(0o644)
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
    outside_secret.chmod(0o644)

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
    secret.chmod(0o644)
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
    secret.chmod(0o644)

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(module, "reachable_by", lambda p, cache=None: (True, True))
        findings = module.scan([tmp_path])
    finally:
        monkeypatch.undo()

    assert [f.path.name for f in findings] == ["credentials.env"]
    assert findings[0].mode == 0o644


# --------------------------------------------------------------------------
# Custody roots + report-only .env* (2026-09-10 incident):
# ~/nuzantara/.secrets was found loosened and restored by hand; the auditor
# never looked there (not a default root), and reachable_by() absolves a
# 0644 file whose chain is still closed — invisible until a SECOND mistake
# opens the directory. Custody judges the file's own mode.
# --------------------------------------------------------------------------


def _touch(path: Path, mode: int, content: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(mode)
    return path


def _json_main(module, args: list, capsys) -> tuple:
    import json

    rc = module.main(args)
    return rc, json.loads(capsys.readouterr().out)


def test_t1_default_roots_include_main_checkout_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert tmp_path / "nuzantara" / ".secrets" in audit.default_roots()


def _custody_fixture(tmp_path: Path):
    """0644 probe.json behind a CLOSED chain (outer 0700), inside a
    `.secrets` dir left at mkdir default — the dir mode must NOT decide.
    Real reachability (open_chain=False): the whole point is the chain."""
    module = _load_module(open_chain=False)
    outer = tmp_path / "outer"
    outer.mkdir()
    outer.chmod(0o700)
    scr = outer / ".secrets"
    scr.mkdir()  # 0755 — deliberately NOT tightened
    probe = _touch(scr / "probe.json", 0o644, "{}\n")
    return module, outer, scr, probe


def test_t2_custody_guilt_behind_closed_chain(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    module, outer, scr, probe = _custody_fixture(tmp_path)
    args = ["--no-default-roots", "--root", str(scr), "--json"]

    rc, payload = _json_main(module, args, capsys)
    assert rc == 1
    assert payload["count"] == 1
    assert payload["findings"][0]["custody"] is True
    assert payload["findings"][0]["report_only"] is True
    report = payload["custody"][0]
    assert report["files_traversed"] == 1
    assert report["findings"] == 1
    assert report["dir_mode"] == "0755"

    # Same file, same chain, locked down: clean. Paired so neither case
    # can pass because the file was never a candidate.
    probe.chmod(0o600)
    rc, payload = _json_main(module, args, capsys)
    assert rc == 0
    assert payload["count"] == 0


def test_t3_custody_innocence_locked_files_and_dir_mode_not_a_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """0600/0400 inside a 0755 .secrets read clean; the dir mode is
    INFORMATIONAL only (mkdir -p makes a scratch .secrets 0755)."""
    module = _load_module(open_chain=False)
    scr = tmp_path / ".secrets"
    scr.mkdir()  # 0755 — must not itself be a finding
    _touch(scr / "a.json", 0o600, "{}\n")
    _touch(scr / "b.json", 0o400, "{}\n")
    # Named twice on purpose: one custody report, not two.
    args = ["--no-default-roots", "--root", str(scr), "--root", str(scr), "--json"]

    rc, payload = _json_main(module, args, capsys)
    assert rc == 0
    assert payload["count"] == 0
    assert len(payload["custody"]) == 1
    assert payload["custody"][0]["findings"] == 0
    assert payload["custody"][0]["dir_mode"] == "0755"


def test_t4_same_file_behind_closed_chain_outside_custody_is_absolved(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Paired with T2: only the directory NAME turns custody semantics on;
    reachability outside custody roots is untouched. A candidate NAME, so
    the innocence comes from the closed chain, not from the name filter —
    the open-chain control below proves it is the chain that absolves."""
    module = _load_module(open_chain=False)
    outer = tmp_path / "outer"
    outer.mkdir()
    outer.chmod(0o700)
    _touch(outer / "vault" / "credentials.json", 0o644, "{}\n")
    args = ["--no-default-roots", "--root", str(outer), "--json"]

    rc, payload = _json_main(module, args, capsys)
    assert rc == 0
    assert payload["count"] == 0

    rc, payload = _json_main(audit, args, capsys)  # chain declared open
    assert rc == 1
    assert payload["count"] == 1
    assert payload["findings"][0]["custody"] is False


def test_t5_env_templates_never_flagged_and_custody_report_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Live 2026-09-10 false positives: credential TEMPLATES shipped in
    repos at 0644 (.env.example, .env.sample) must never be flagged."""
    monkeypatch.setenv("HOME", str(tmp_path))
    secrets = tmp_path / "nuzantara" / ".secrets"
    secrets.mkdir(parents=True)
    _touch(secrets / "a.json", 0o600, "{}\n")
    _touch(tmp_path / "nuzantara" / "apps" / "web" / ".env.example", 0o644, "# t\n")
    for name in (".env.example", ".env.sample"):  # inside a default root
        _touch(tmp_path / ".claude" / "skills" / "x" / name, 0o644, "# t\n")

    rc, payload = _json_main(audit, ["--json"], capsys)
    assert rc == 0
    flagged = [f["path"] for f in payload["findings"]]
    assert not any(".example" in p or ".sample" in p for p in flagged)
    report = {c["root"]: c for c in payload["custody"]}[str(secrets)]
    assert report["files_traversed"] == 1
    assert report["findings"] == 0


def test_t6_fix_never_chmods_env_shaped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    target = _touch(tmp_path / ".env.master", 0o644, "SECRET=1\n")

    real_chmod = os.chmod
    calls: list = []

    def spy_chmod(path, mode, *args, **kwargs):
        calls.append(Path(path))
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", spy_chmod)

    rc = audit.main(["--no-default-roots", "--root", str(tmp_path), "--fix"])
    out = capsys.readouterr().out

    assert target not in calls
    assert _mode_of(target) == 0o644
    lines = [ln for ln in out.splitlines() if str(target) in ln]
    assert len(lines) == 1
    assert "REPORT-ONLY" in lines[0]
    assert rc == 1


@pytest.mark.parametrize("relpath", [".env.master", ".secrets/probe.json"])
def test_t8_fix_findings_ignores_credentials_even_when_hand_built(
    tmp_path: Path, relpath: str
) -> None:
    """Defense in depth: fix_findings re-checks the NAME, never the flag —
    a hand-built Finding for an .env* file or a file under .secrets must
    not get a chmod (credentials stay with the human)."""
    target = _touch(tmp_path / relpath, 0o644, "SECRET=1\n")

    result = audit.fix_findings([audit.Finding(path=target, mode=0o644)])

    assert result == (0, 0, [])
    assert _mode_of(target) == 0o644


def test_t9_live_false_positives_are_excluded_and_no_wider(tmp_path: Path) -> None:
    """2026-09-10 Pro scan: usage-accounting jsonl logs (same family as
    *token_count*) and `.env` templates are not findings. The exclusion is
    exactly that narrow: key/credential names that merely CONTAIN the
    excluded words, and non-.env templates, are still findings."""
    _touch(tmp_path / "token-usage-2026-09.jsonl", 0o644, "{}\n")
    _touch(tmp_path / "token_usage-2026-09.jsonl", 0o644, "{}\n")
    _touch(tmp_path / ".env.sample", 0o644, "# t\n")
    _touch(tmp_path / ".env.local.template", 0o644, "# t\n")
    real = {
        _touch(tmp_path / name, 0o644, "x\n")
        for name in (
            "service.token",
            "token-usage.pem",
            "token_usage.key",
            "id_rsa.example",
            "credentials.json.template",
            "credentials.json.template.bak",
        )
    }

    findings = audit.scan([tmp_path], max_depth=4)

    assert _paths(findings) == real


def test_t10_plugin_marketplace_checkouts_are_walked(tmp_path: Path) -> None:
    """A directory's name does not prove its contents public: a credential
    inside a plugin marketplace checkout is found like any other."""
    vendored = _touch(
        tmp_path / "plugins" / "marketplaces" / "vendor" / "id_rsa", 0o644, "k\n"
    )

    findings = audit.scan([tmp_path], max_depth=4)

    assert vendored in _paths(findings)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
def test_t11_custody_blind_directory_cannot_be_listed(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A custody dir that exists but cannot be listed (chmod 000) makes the
    whole audit BLIND — never certify 'clean' over zero files."""
    module = _load_module(open_chain=False)
    scr = tmp_path / ".secrets"
    scr.mkdir()
    _touch(scr / "a.json", 0o600, "{}\n")
    scr.chmod(0o000)
    try:
        rc, payload = _json_main(
            module, ["--no-default-roots", "--root", str(scr), "--json"], capsys
        )
    finally:
        scr.chmod(0o700)

    assert rc == 2
    assert payload["blind"] is True
    assert payload["custody"][0]["blind"] is True


def test_t12_fix_never_chmods_a_custody_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Credentials stay with the human: --fix reports a loosened file under a
    .secrets root and leaves its mode alone (S2 round-3 ruling, 2026-09-10)."""
    module, _outer, scr, probe = _custody_fixture(tmp_path)
    calls: list = []
    real_chmod = os.chmod

    def spy_chmod(path, mode, *args, **kwargs):
        calls.append(Path(path))
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", spy_chmod)
    rc = module.main(["--no-default-roots", "--root", str(scr), "--fix"])
    out = capsys.readouterr().out

    assert calls == []
    assert _mode_of(probe) == 0o644
    lines = [ln for ln in out.splitlines() if str(probe) in ln]
    assert len(lines) == 1
    assert "CUSTODY" in lines[0] and "REPORT-ONLY" in lines[0]
    assert "REPORT-ONLY: 1" in out
    assert rc == 1


def test_t13_fix_touches_exactly_what_it_touched_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """This change must not widen what --fix alters: its live consumer is
    Mini's com.nuzantara.secrets-perms-sweep (--fix on the default roots,
    every 6 h). Only the ordinary credential is chmod'ed; .env* and every file
    under a .secrets directory, named root or walked into, keep their mode."""
    root = tmp_path / "root"
    ordinary = _touch(root / "service.token", 0o644)
    env = _touch(root / ".env.master", 0o644)
    walked = _touch(root / "app" / ".secrets" / "walked.json", 0o644)
    named_root = tmp_path / "named" / ".secrets"
    named = _touch(named_root / "named.json", 0o644)
    calls: list = []
    real_chmod = os.chmod

    def spy_chmod(path, mode, *args, **kwargs):
        calls.append(Path(path))
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", spy_chmod)
    rc = audit.main(
        ["--no-default-roots", "--root", str(root), "--root", str(named_root), "--fix"]
    )
    out = capsys.readouterr().out

    assert calls == [ordinary]
    assert _mode_of(ordinary) == 0o600
    assert {_mode_of(p) for p in (env, walked, named)} == {0o644}
    assert "FIXED: 1  FAILED: 0  REPORT-ONLY: 3" in out
    assert rc == 1


def _spy_chmod(monkeypatch: pytest.MonkeyPatch) -> list:
    calls: list = []
    real_chmod = os.chmod

    def spy_chmod(path, mode, *args, **kwargs):
        calls.append(Path(path))
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", spy_chmod)
    return calls


def test_t14_symlinked_custody_root_is_judged_and_never_chmoded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Codex R1 BLOCKERs: `.secrets -> vault` resolves before the walk, so
    the path loses the name. Every file there is still a custody finding —
    no name filter, no exclusion — and --fix still leaves it alone."""
    module = _load_module(open_chain=False)
    vault = tmp_path / "vault"
    probe = _touch(vault / "probe.json", 0o644, "{}\n")
    pub = _touch(vault / "id_rsa.pub", 0o644, "k\n")
    link = tmp_path / ".secrets"
    link.symlink_to(vault)
    args = ["--no-default-roots", "--root", str(link)]

    rc, payload = _json_main(module, args + ["--json"], capsys)
    assert rc == 1
    assert {f["path"] for f in payload["findings"]} == {str(probe), str(pub)}
    assert all(f["custody"] and f["report_only"] for f in payload["findings"])

    calls = _spy_chmod(monkeypatch)
    rc = module.main(args + ["--fix"])
    out = capsys.readouterr().out
    assert calls == []
    assert {_mode_of(probe), _mode_of(pub)} == {0o644}
    assert "FIXED: 0  FAILED: 0  REPORT-ONLY: 2" in out
    assert rc == 1

    for path in (probe, pub):  # innocence on the same fixture
        path.chmod(0o600)
    rc, payload = _json_main(module, args + ["--json"], capsys)
    assert rc == 0
    assert payload["count"] == 0


def test_t15_custody_met_during_the_walk_any_case_is_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Naming the PARENT of a `.Secrets` directory behind a closed chain
    still reports its loosened file as custody, and --fix leaves it."""
    module = _load_module(open_chain=False)
    outer = tmp_path / "outer"
    outer.mkdir()
    outer.chmod(0o700)
    probe = _touch(outer / ".Secrets" / "probe.json", 0o644, "{}\n")
    args = ["--no-default-roots", "--root", str(outer)]

    rc, payload = _json_main(module, args + ["--json"], capsys)
    assert rc == 1
    assert payload["count"] == 1
    assert payload["findings"][0]["custody"] is True

    calls = _spy_chmod(monkeypatch)
    module.main(args + ["--fix"])
    capsys.readouterr()
    assert calls == []
    assert _mode_of(probe) == 0o644

    probe.chmod(0o600)
    rc, payload = _json_main(module, args + ["--json"], capsys)
    assert rc == 0
    assert payload["count"] == 0


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
@pytest.mark.parametrize("case", ["parent-closed", "dir-0400"])
def test_t16_custody_access_errors_are_blind_never_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture, case: str
) -> None:
    """A custody root that cannot be stat'ed (EACCES on its chain), or one
    that lists but cannot be traversed (0400), is BLIND — never 'clean'."""
    module = _load_module(open_chain=False)
    parent = tmp_path / "p"
    scr = parent / ".secrets"
    _touch(scr / "probe.json", 0o644, "{}\n")
    locked = parent if case == "parent-closed" else scr
    locked.chmod(0o000 if case == "parent-closed" else 0o400)
    try:
        rc, payload = _json_main(
            module, ["--no-default-roots", "--root", str(scr), "--json"], capsys
        )
    finally:
        locked.chmod(0o700)

    assert rc == 2
    assert payload["blind"] is True
    assert payload["custody"][0]["blind"] is True

    rc, payload = _json_main(  # innocence: same fixture, access restored
        module, ["--no-default-roots", "--root", str(scr), "--json"], capsys
    )
    assert rc == 1
    assert payload["blind"] is False


def test_t17_fix_findings_refuses_symlinks_and_custody_flags(tmp_path: Path) -> None:
    """A hand-built Finding on a symlink would hand the chmod to its target
    (here an .env file); a Finding flagged custody is skipped even when its
    path lost the name. An ordinary regular file is still fixed."""
    target = _touch(tmp_path / ".env.real", 0o644, "SECRET=1\n")
    link = tmp_path / "credentials.json"
    link.symlink_to(target)
    flagged = _touch(tmp_path / "vault" / "probe.json", 0o644, "{}\n")
    ordinary = _touch(tmp_path / "service.token", 0o644, "tok\n")

    fixed, failed, failures = audit.fix_findings(
        [
            audit.Finding(path=link, mode=0o644),
            audit.Finding(path=flagged, mode=0o644, custody=True, report_only=True),
            audit.Finding(path=ordinary, mode=0o644),
        ]
    )

    assert (fixed, failed) == (1, 1)
    assert failures == [f"{link}: NotARegularFile"]
    assert _mode_of(target) == 0o644
    assert _mode_of(flagged) == 0o644
    assert _mode_of(ordinary) == 0o600


# --------------------------------------------------------------------------
# S2/PR2 — credential-custody detector: the schedule (--notify). Every test
# points the gateway at a fake script in tmp_path (SECRETS_AUDIT_TG_NOTIFY);
# the real scripts/tg_notify.py is never invoked.
# --------------------------------------------------------------------------


def _fake_gateway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a tiny gateway script into tmp_path and point
    SECRETS_AUDIT_TG_NOTIFY at it. It appends json.dumps(argv[1:]) plus a
    newline to the file named by env FAKE_TG_LOG — never the real
    tg_notify.py, which sends real Telegram messages."""
    log_path = tmp_path / "fake_tg_log.jsonl"
    script = tmp_path / "fake_tg_notify.py"
    script.write_text(
        "import json, os, sys\n"
        "with open(os.environ['FAKE_TG_LOG'], 'a') as fh:\n"
        "    fh.write(json.dumps(sys.argv[1:]) + chr(10))\n"
        "sys.stderr.write('tg_notify: ' + os.environ.get('FAKE_TG_STATUS', 'sent') + chr(10))\n"
    )
    monkeypatch.setenv("FAKE_TG_LOG", str(log_path))
    monkeypatch.setenv("SECRETS_AUDIT_TG_NOTIFY", str(script))
    return log_path


def _read_fake_log(log_path: Path) -> list:
    import json as _json

    if not log_path.exists():
        return []
    return [_json.loads(line) for line in log_path.read_text().splitlines() if line]


def test_n1_custody_finding_notify_sends_one_p0_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    log_path = _fake_gateway(tmp_path, monkeypatch)
    scr = tmp_path / ".secrets"
    probe = _touch(scr / "probe.json", 0o644, "{}\n")

    module = _load_module(open_chain=False)
    monkeypatch.setattr(module, "machine_label", lambda *a, **k: "pro")
    rc = module.main(["--no-default-roots", "--root", str(scr), "--notify"])
    capsys.readouterr()

    calls = _read_fake_log(log_path)
    assert len(calls) == 1
    argv = calls[0]
    assert argv[:6] == [
        "--tier", "p0", "--source", "secrets-audit",
        "--dedup-key", "secrets-audit:secrets-dir",
    ]
    text = argv[-1]
    assert "[pro]" in text
    assert str(scr) in text
    assert "1 credential file(s)" in text
    assert "other-read" in text
    assert probe.name not in text
    assert rc == 0


def test_n2_env_report_only_notify_sends_one_digest_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    log_path = _fake_gateway(tmp_path, monkeypatch)
    monkeypatch.setattr(audit, "machine_label", lambda *a, **k: "pro")
    target = _touch(tmp_path / ".env.master", 0o644, "SECRET=1\n")

    rc = audit.main(["--no-default-roots", "--root", str(tmp_path), "--notify"])
    capsys.readouterr()

    calls = _read_fake_log(log_path)
    assert len(calls) == 1
    argv = calls[0]
    assert argv[:6] == [
        "--tier", "digest", "--source", "secrets-audit",
        "--dedup-key", "secrets-audit:env-modes",
    ]
    text = argv[-1]
    assert "[pro]" in text
    assert str(tmp_path) in text
    assert "1 file(s)" in text
    assert target.name not in text
    assert rc == 0


def test_n3_clean_root_notify_zero_calls_rc0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    log_path = _fake_gateway(tmp_path, monkeypatch)
    monkeypatch.setattr(audit, "machine_label", lambda *a, **k: "pro")
    (tmp_path / "README.md").write_text("benign\n")  # empty dir would be BLIND

    rc = audit.main(["--no-default-roots", "--root", str(tmp_path), "--notify"])
    out = capsys.readouterr().out

    assert _read_fake_log(log_path) == []
    assert rc == 0
    lines = out.splitlines()
    assert lines[0].startswith("RUN ")
    assert "machine=pro" in lines[0]
    assert lines[-1] == "RUN-END rc=0"


def test_n4_ordinary_finding_notify_zero_calls_path_in_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    log_path = _fake_gateway(tmp_path, monkeypatch)
    monkeypatch.setattr(audit, "machine_label", lambda *a, **k: "pro")
    target = _touch(tmp_path / "credentials.json", 0o644, "{}\n")

    rc = audit.main(["--no-default-roots", "--root", str(tmp_path), "--notify"])
    out = capsys.readouterr().out

    assert _read_fake_log(log_path) == []
    assert rc == 0
    assert str(target) in out


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
def test_n5_blind_custody_root_notify_one_p0_call_rc2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    log_path = _fake_gateway(tmp_path, monkeypatch)
    scr = tmp_path / ".secrets"
    scr.mkdir()
    _touch(scr / "a.json", 0o600, "{}\n")
    scr.chmod(0o000)
    module = _load_module(open_chain=False)
    monkeypatch.setattr(module, "machine_label", lambda *a, **k: "pro")
    try:
        rc = module.main(["--no-default-roots", "--root", str(scr), "--notify"])
    finally:
        scr.chmod(0o700)
    capsys.readouterr()

    calls = _read_fake_log(log_path)
    assert len(calls) == 1
    assert calls[0][:2] == ["--tier", "p0"]
    assert "cannot be listed" in calls[0][-1]
    assert rc == 2


def test_n6_missing_gateway_rc1_and_failed_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("SECRETS_AUDIT_TG_NOTIFY", str(tmp_path / "does-not-exist.py"))
    scr = tmp_path / ".secrets"
    _touch(scr / "probe.json", 0o644, "{}\n")

    module = _load_module(open_chain=False)
    monkeypatch.setattr(module, "machine_label", lambda *a, **k: "pro")
    rc = module.main(["--no-default-roots", "--root", str(scr), "--notify"])
    out = capsys.readouterr().out

    assert rc == 1
    assert any(
        line.startswith("NOTIFY ") and "failed=1" in line for line in out.splitlines()
    )


def test_n7_launcher_from_ppid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    _fake_gateway(tmp_path, monkeypatch)
    monkeypatch.setattr(audit, "machine_label", lambda *a, **k: "pro")
    (tmp_path / "README.md").write_text("benign\n")
    real_getppid = os.getppid

    monkeypatch.setattr(os, "getppid", lambda: 1)
    audit.main(["--no-default-roots", "--root", str(tmp_path), "--notify"])
    out1 = capsys.readouterr().out
    assert "launcher=launchd" in out1.splitlines()[0]

    monkeypatch.setattr(os, "getppid", real_getppid)
    audit.main(["--no-default-roots", "--root", str(tmp_path), "--notify"])
    out2 = capsys.readouterr().out
    assert "launcher=shell" in out2.splitlines()[0]


def test_n8_subprocess_notify_rc0_and_fake_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess as _subprocess

    log_path = _fake_gateway(tmp_path, monkeypatch)
    scr = tmp_path / ".secrets"
    _touch(scr / "probe.json", 0o644, "{}\n")
    stdout_file = tmp_path / "stdout.txt"

    with open(stdout_file, "w") as fh:
        _subprocess.run(
            [
                sys.executable,
                str(_MODULE_PATH),
                "--notify",
                "--no-default-roots",
                "--root",
                str(scr),
            ],
            stdout=fh,
            stderr=_subprocess.PIPE,
            timeout=30,
        )

    out_text = stdout_file.read_text()
    assert out_text.rstrip().splitlines()[-1] == "RUN-END rc=0"
    calls = _read_fake_log(log_path)
    assert len(calls) == 1
    assert calls[0][:2] == ["--tier", "p0"]


def test_n9_build_alerts_two_custody_findings_one_alert_union_classes(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".secrets"
    f1 = audit.Finding(path=root / "a.json", mode=0o644, custody=True, report_only=True)
    f2 = audit.Finding(path=root / "b.json", mode=0o640, custody=True, report_only=True)
    report = audit.CustodyRootReport(
        root=root, files_traversed=2, findings=2, dir_mode="0755", blind=False
    )
    result = audit.AuditResult(
        findings=[f1, f2], custody=[report], roots_existing=1, files_traversed=2, blind=False
    )

    alerts = audit.build_alerts(result, "nuzantara")

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.tier == "p0"
    assert alert.dedup_key == "secrets-audit:secrets-dir"
    assert "2 credential file(s)" in alert.text
    assert "group-read, other-read" in alert.text


def test_n10_notify_never_chmods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    _fake_gateway(tmp_path, monkeypatch)
    custody_root = tmp_path / "secroot"
    scr = custody_root / ".secrets"
    custody_file = _touch(scr / "probe.json", 0o644, "{}\n")
    env_root = tmp_path / "enviroot"
    env_file = _touch(env_root / ".env.master", 0o644, "SECRET=1\n")
    # An ORDINARY credential too: the one --fix would chmod, so a --notify
    # path that ever reached fix_findings() turns this test red.
    ordinary = _touch(env_root / "credentials.json", 0o644, "{}\n")
    log_path = tmp_path / "fake_tg_log.jsonl"

    chmod_calls: list = []
    fchmod_calls: list = []
    monkeypatch.setattr(os, "chmod", lambda *a, **k: chmod_calls.append(a))
    monkeypatch.setattr(os, "fchmod", lambda *a, **k: fchmod_calls.append(a))

    module = _load_module(open_chain=True)
    monkeypatch.setattr(module, "machine_label", lambda *a, **k: "pro")
    module.main(
        [
            "--no-default-roots",
            "--root", str(scr),
            "--root", str(env_root),
            "--notify",
        ]
    )
    capsys.readouterr()

    assert chmod_calls == []
    assert fchmod_calls == []
    assert _mode_of(custody_file) == 0o644
    assert _mode_of(env_file) == 0o644
    assert _mode_of(ordinary) == 0o644
    assert [call[:2] for call in _read_fake_log(log_path)] == [
        ["--tier", "p0"],
        ["--tier", "digest"],
    ]


def test_n11_notify_and_fix_together_exit_2_no_gateway_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    log_path = _fake_gateway(tmp_path, monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        audit.main(["--no-default-roots", "--root", str(tmp_path), "--notify", "--fix"])
    capsys.readouterr()

    assert exc_info.value.code == 2
    assert _read_fake_log(log_path) == []


def test_p1_plist_contract() -> None:
    import plistlib

    plist_path = (
        Path(__file__).parents[2]
        / "infra"
        / "launchagents"
        / "com.nuzantara.secrets-permissions-audit.plist"
    )
    with open(plist_path, "rb") as fh:
        data = plistlib.load(fh)

    assert data["Label"] == "com.nuzantara.secrets-permissions-audit"
    assert data["ProgramArguments"] == [
        "/opt/homebrew/bin/python3",
        "/Users/nuzantara/nuzantara/scripts/secrets_permissions_audit.py",
        "--notify",
    ]
    assert data["StartInterval"] == 3600
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] is False
    assert data["Umask"] == 63
    assert data["StandardOutPath"].startswith("/Users/nuzantara/logs/")
    assert data["StandardErrorPath"].startswith("/Users/nuzantara/logs/")
    assert set(data["EnvironmentVariables"].keys()) == {"HOME", "PATH"}


def test_n12_custody_alert_covers_symlinked_root_and_walked_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A custody finding whose path lies under no CustodyRootReport root — a
    `.secrets` symlink resolved to its target, or a `.secrets` met during an
    ordinary walk — still reaches the one p0 alert, by directory only."""
    module = _load_module(open_chain=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    vault = tmp_path / "vault"
    _touch(vault / "probe.json", 0o644, "{}\n")
    link = tmp_path / ".secrets"
    link.symlink_to(vault)
    outer = tmp_path / "outer"
    outer.mkdir()
    outer.chmod(0o700)
    _touch(outer / ".secrets" / "walked.json", 0o640, "{}\n")

    alerts = module.build_alerts(module.audit([link, outer]), "pro")

    assert [(a.tier, a.dedup_key) for a in alerts] == [
        ("p0", "secrets-audit:secrets-dir")
    ]
    text = alerts[0].text
    assert "~/vault — 1 credential file(s) open beyond the owner (group-read, other-read)" in text
    assert "~/outer/.secrets — 1 credential file(s) open beyond the owner (group-read)" in text
    assert "probe.json" not in text and "walked.json" not in text

    for path in (vault / "probe.json", outer / ".secrets" / "walked.json"):
        path.chmod(0o600)  # innocence on the same fixture
    assert module.build_alerts(module.audit([link, outer]), "pro") == []


@pytest.mark.parametrize(
    "status, handed, rc",
    [
        ("sent", 1, 0),
        ("deduped", 1, 0),
        ("internal error (boom) — best-effort spooled", 0, 1),
        ("p0_unsent_spooled", 0, 1),
    ],
)
def test_n13_gateway_status_decides_handed_not_its_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    status: str,
    handed: int,
    rc: int,
) -> None:
    """tg_notify.py exits 0 even when it could neither send nor spool; only
    its status line says whether the alert left. `deduped` is handed but
    reported as such, never as delivered."""
    _fake_gateway(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_TG_STATUS", status)
    module = _load_module(open_chain=False)
    monkeypatch.setattr(module, "machine_label", lambda *a, **k: "pro")
    scr = tmp_path / ".secrets"
    _touch(scr / "probe.json", 0o644, "{}\n")

    got = module.main(["--no-default-roots", "--root", str(scr), "--notify"])
    out = capsys.readouterr().out

    notify = [ln for ln in out.splitlines() if ln.startswith("NOTIFY ")][0]
    assert f"handed={handed}" in notify
    assert f"failed={1 - handed}" in notify
    if handed:
        assert f"outcomes=p0:{status}" in notify
    assert "boom" not in out
    assert got == rc
    assert out.rstrip().endswith(f"RUN-END rc={rc}")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
def test_n14_blind_without_a_custody_report_still_raises_p0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A `.secrets` met during an ordinary walk that lists but cannot be
    traversed (0400) makes the audit BLIND with no custody root report —
    the p0 alert must still say custody was not verified."""
    log_path = _fake_gateway(tmp_path, monkeypatch)
    module = _load_module(open_chain=False)
    monkeypatch.setattr(module, "machine_label", lambda *a, **k: "pro")
    root = tmp_path / "plain"
    _touch(root / "readme.txt", 0o600, "x\n")
    scr = root / ".secrets"
    _touch(scr / "probe.json", 0o600, "{}\n")
    scr.chmod(0o400)
    try:
        got = module.main(["--no-default-roots", "--root", str(root), "--notify"])
    finally:
        scr.chmod(0o700)
    capsys.readouterr()

    calls = _read_fake_log(log_path)
    assert got == 2
    assert len(calls) == 1 and calls[0][:2] == ["--tier", "p0"]
    assert "audit BLIND" in calls[0][-1] and "probe.json" not in calls[0][-1]

    got = module.main(["--no-default-roots", "--root", str(root), "--notify"])
    capsys.readouterr()
    assert got == 0  # innocence: same tree, access restored
    assert len(_read_fake_log(log_path)) == 1


def test_n15_alert_never_spells_out_a_symlinked_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HOME is a symlink; the custody root resolves into the real home. The
    alert collapses the real path to `~` as well, never printing its name."""
    module = _load_module(open_chain=False)
    real = tmp_path / "canonical-home-name"
    _touch(real / "vault" / "probe.json", 0o644, "{}\n")
    (real / ".secrets").symlink_to(real / "vault")
    alias = tmp_path / "home-alias"
    alias.symlink_to(real)
    monkeypatch.setenv("HOME", str(alias))

    alerts = module.build_alerts(module.audit([alias / ".secrets"]), "pro")

    assert len(alerts) == 1
    assert "~/vault — 1 credential file(s)" in alerts[0].text
    assert "canonical-home-name" not in alerts[0].text
