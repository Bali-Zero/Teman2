"""Guilt + innocence for scripts/baseline_debt_report.py.

Builds a throwaway git repo under tmp_path with its own `.secrets.baseline`
and a minimal `detect_secrets_auto_triage.py` stand-in (one broad rule, one
content-keyed rule), then runs the report against it via module-attribute
monkeypatching (REPO_ROOT / BASELINE / AUTO_TRIAGE_MODULE). Never touches the
real repo's `.secrets.baseline`.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "baseline_debt_report.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("baseline_debt_report", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    return repo


AUTO_TRIAGE_STUB = '''
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

HARD_BLOCK_RULES = []

CONTENT_KEYED_RULES = [
    (re.compile(r"(^|/)narrow_pin\\.py$"), re.compile(r"PIN_SHA256"), "narrow content-keyed pin"),
]

AUTO_APPROVE_RULES = [
    (re.compile(r"(^|/)scripts/.*\\.py$"), "broad: scripts dir is dev-only (stub rule)"),
]


def _line_text(file_path, line_number):
    try:
        full = REPO_ROOT / file_path
        with full.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                if i == line_number:
                    return line
    except OSError:
        return None
    return None
'''


def _write_baseline(repo: Path, results: dict) -> None:
    (repo / ".secrets.baseline").write_text(
        json.dumps({"generated_at": "2026-01-01T00:00:00Z", "results": results}, indent=2)
    )


# Synthetic-by-construction OAuth-shaped fixtures for the guilt test below.
# Assembled via string concatenation rather than written as one contiguous
# literal, so this test file's own source text never matches the
# vendor-prefix shapes it exists to test -- the same self-catch class
# already fixed on lint_pg_dsn_credentials.py (PR #4484) and
# lint_google_oauth_credentials.py (PR #4489). Defined once and reused in
# both the fixture and the assertion below so the two copies cannot drift.
_SYNTHETIC_GOCSPX_SECRET = "GOCSPX-" + "abcdefghijklmnopqrstuvwx"
_SYNTHETIC_REFRESH_TOKEN = "1//" + ("a" * 40)


def test_broad_approved_live_file_with_oauth_shape_is_flagged(tmp_path):
    """GUILT: a file approved by the broad rule, still on HEAD, carrying a
    GOCSPX- literal must show up in high_confidence_shape_files and --strict
    must exit 1."""
    repo = _init_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "detect_secrets_auto_triage.py").write_text(AUTO_TRIAGE_STUB)
    leaky = repo / "scripts" / "leaky_oauth_script.py"
    leaky.write_text(
        f"CLIENT_SECRET = '{_SYNTHETIC_GOCSPX_SECRET}'\n"
        f"REFRESH_TOKEN = '{_SYNTHETIC_REFRESH_TOKEN}'\n"
    )
    _write_baseline(
        repo,
        {
            "scripts/leaky_oauth_script.py": [
                {"type": "Secret Keyword", "line_number": 1, "is_secret": False},
                {"type": "Base64 High Entropy String", "line_number": 2, "is_secret": False},
            ]
        },
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    mod = _load_module()
    mod.REPO_ROOT = repo
    mod.BASELINE = repo / ".secrets.baseline"
    mod.AUTO_TRIAGE_MODULE = repo / "scripts" / "detect_secrets_auto_triage.py"

    data = mod.analyze()
    assert data["high_confidence_shape_files_count"] == 1
    assert "scripts/leaky_oauth_script.py" in data["high_confidence_shape_files"]
    shapes = data["high_confidence_shape_files"]["scripts/leaky_oauth_script.py"]
    assert "google_oauth_client_secret" in shapes
    assert "google_oauth_refresh_token" in shapes

    # never leak the actual value into the report
    report = mod.render_markdown(data)
    assert _SYNTHETIC_GOCSPX_SECRET not in report
    assert _SYNTHETIC_REFRESH_TOKEN not in report


def test_broad_approved_live_file_without_credential_shape_is_innocent(tmp_path):
    """INNOCENCE: a file approved by the same broad rule, still on HEAD, but
    with no high-confidence shape must NOT be flagged — proves the check is
    on content, not merely on "broad rule + still exists"."""
    repo = _init_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "detect_secrets_auto_triage.py").write_text(AUTO_TRIAGE_STUB)
    clean = repo / "scripts" / "clean_dev_script.py"
    clean.write_text("DATABASE_URL = 'postgresql://nuzantara:nuzantara_local_dev@localhost:5432/nuzantara'\n")
    _write_baseline(
        repo,
        {
            "scripts/clean_dev_script.py": [
                {"type": "Basic Auth Credentials", "line_number": 1, "is_secret": False},
            ]
        },
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    mod = _load_module()
    mod.REPO_ROOT = repo
    mod.BASELINE = repo / ".secrets.baseline"
    mod.AUTO_TRIAGE_MODULE = repo / "scripts" / "detect_secrets_auto_triage.py"

    data = mod.analyze()
    assert data["high_confidence_shape_files_count"] == 0
    assert data["approval_buckets"].get("auto_approve_broad") == 1


def test_deleted_file_counted_as_stale_not_live(tmp_path):
    """A baseline entry for a file removed from HEAD must land in stale_files,
    never contribute to live_files or approval_buckets."""
    repo = _init_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "detect_secrets_auto_triage.py").write_text(AUTO_TRIAGE_STUB)
    _write_baseline(
        repo,
        {
            "scripts/long_gone.py": [
                {"type": "Secret Keyword", "line_number": 1, "is_secret": False},
            ]
        },
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    mod = _load_module()
    mod.REPO_ROOT = repo
    mod.BASELINE = repo / ".secrets.baseline"
    mod.AUTO_TRIAGE_MODULE = repo / "scripts" / "detect_secrets_auto_triage.py"

    data = mod.analyze()
    assert data["stale_files_count"] == 1
    assert "scripts/long_gone.py" in data["stale_files"]
    assert data["live_files"] == 0
    assert data["approval_buckets"] == {}


def test_content_keyed_approval_is_not_counted_as_broad(tmp_path):
    """A finding approved via CONTENT_KEYED_RULES (narrow) must land in the
    content_keyed bucket, never auto_approve_broad — the two buckets are the
    whole point of this script and must not collapse into each other."""
    repo = _init_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "detect_secrets_auto_triage.py").write_text(AUTO_TRIAGE_STUB)
    pinned = repo / "narrow_pin.py"
    pinned.write_text("PIN_SHA256 = 'deadbeef' * 8\n")
    _write_baseline(
        repo,
        {
            "narrow_pin.py": [
                {"type": "Hex High Entropy String", "line_number": 1, "is_secret": False},
            ]
        },
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    mod = _load_module()
    mod.REPO_ROOT = repo
    mod.BASELINE = repo / ".secrets.baseline"
    mod.AUTO_TRIAGE_MODULE = repo / "scripts" / "detect_secrets_auto_triage.py"

    data = mod.analyze()
    assert data["approval_buckets"].get("content_keyed") == 1
    assert data["approval_buckets"].get("auto_approve_broad") is None


def test_cli_strict_exit_code_reflects_high_confidence_findings(tmp_path):
    """End-to-end: invoke the script as a subprocess (the way CI would) and
    check --strict's exit code, not just the in-process function result."""
    repo = _init_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "detect_secrets_auto_triage.py").write_text(AUTO_TRIAGE_STUB)
    leaky = repo / "scripts" / "leaky.py"
    leaky.write_text("TOKEN = 'AKIAABCDEFGHIJKLMNOP'\n")
    _write_baseline(
        repo,
        {"scripts/leaky.py": [{"type": "Secret Keyword", "line_number": 1, "is_secret": False}]},
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    env_script = repo / "scripts" / "baseline_debt_report.py"
    env_script.write_text(SCRIPT.read_text().replace(
        'REPO_ROOT = Path(__file__).resolve().parent.parent',
        f'REPO_ROOT = Path({str(repo)!r})',
    ))

    r = subprocess.run(
        [sys.executable, str(env_script), "--strict"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "AKIAABCDEFGHIJKLMNOP" not in r.stdout
    assert "AKIAABCDEFGHIJKLMNOP" not in r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
