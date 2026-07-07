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


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "secrets_permissions_audit", _MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
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
