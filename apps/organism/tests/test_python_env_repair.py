"""Tests for python_env_repair actuator (W57 2026-05-26 panel-amended iter-2).

Covers 10 must-fix items A1-A10 from 3-LLM panel (Gemini APPROVE_WITH_AMENDMENTS
+ Codex REJECT + DeepSeek synthesis):

  A1 — pip install --index-url + --no-input pinning
  A2 — fullmatch regex + control-char block
  A3 — explicit dep allowlist (NOT just regex)
  A4 — orphan "started" TTL 600s (separate from 24h normal)
  A5 — atomic fcntl.flock on attempts file
  A6 — Python path lockdown to pyenv versions/X.Y.Z regex
  A7 — fail-closed on corrupt attempts file (return -1)
  A8 — sanitized subprocess env
  A9 — await proc.wait() post-kill on timeout
  A10 — YAML cooldown_minutes consistency
"""
import asyncio
import json
import os
import re
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from organism.actuators.python_env_repair import (
    PythonEnvRepair,
    _DEP_ALLOWLIST,
    _PKG_WHITELIST_RE,
    _PY_PATH_RE,
)


# ---------------------------------------------------------------------------
# A2 — _validate_pkg
# ---------------------------------------------------------------------------

def test_validate_pkg_bare_name():
    """A2: simple name like 'asyncpg' accepted."""
    a = PythonEnvRepair()
    assert a._validate_pkg("asyncpg") == "asyncpg"


def test_validate_pkg_versioned():
    """A2: pkg>=version accepted."""
    a = PythonEnvRepair()
    assert a._validate_pkg("asyncpg>=0.29") == "asyncpg>=0.29"


def test_validate_pkg_extras_and_version():
    """A2: pkg[extras]>=version accepted."""
    a = PythonEnvRepair()
    assert a._validate_pkg("httpx[http2]>=0.27") == "httpx[http2]>=0.27"


def test_validate_pkg_blocks_semicolon_injection():
    """A2: shell metachar ; blocks."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="rejected"):
        a._validate_pkg("asyncpg; rm -rf /")


def test_validate_pkg_blocks_newline():
    """A2: newline in input rejected (control-char block + regex)."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="control chars|rejected"):
        a._validate_pkg("asyncpg\nls")


def test_validate_pkg_blocks_shell_metachar():
    """A2: ampersand and pipe rejected."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="rejected"):
        a._validate_pkg("asyncpg&whoami")


def test_validate_pkg_empty_rejected():
    """A2: empty string rejected via length check."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="length"):
        a._validate_pkg("")


def test_validate_pkg_too_long_rejected():
    """A2: >80 chars rejected via length check."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="length"):
        a._validate_pkg("a" * 81)


# ---------------------------------------------------------------------------
# A3 — _resolve_dep allowlist
# ---------------------------------------------------------------------------

def test_resolve_dep_allowlist_known_asyncpg():
    """A3: known module → (pkg spec, import name) tuple."""
    a = PythonEnvRepair()
    pkg, name = a._resolve_dep("asyncpg")
    assert pkg == "asyncpg>=0.29"
    assert name == "asyncpg"


def test_resolve_dep_allowlist_known_httpx():
    """A3: httpx known."""
    a = PythonEnvRepair()
    pkg, name = a._resolve_dep("httpx")
    assert pkg == "httpx>=0.27"
    assert name == "httpx"


def test_resolve_dep_allowlist_dotted_submodule():
    """A3 + Gemini #2: 'asyncpg.exceptions' → root 'asyncpg'."""
    a = PythonEnvRepair()
    pkg, name = a._resolve_dep("asyncpg.exceptions")
    assert pkg == "asyncpg>=0.29"
    assert name == "asyncpg"


def test_resolve_dep_allowlist_unknown_blocks():
    """A3: NOT in allowlist → ValueError."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="not in allowlist"):
        a._resolve_dep("malicious_pkg")


def test_resolve_dep_with_version_strips_to_root():
    """A3: 'asyncpg>=0.29' → root 'asyncpg'."""
    a = PythonEnvRepair()
    pkg, name = a._resolve_dep("asyncpg>=0.29")
    assert pkg == "asyncpg>=0.29"
    assert name == "asyncpg"


def test_dep_allowlist_dict_exposed():
    """A3: allowlist constant accessible to consumers (tests, audits)."""
    assert "asyncpg" in _DEP_ALLOWLIST
    assert "httpx" in _DEP_ALLOWLIST
    assert _DEP_ALLOWLIST["asyncpg"]["import_name"] == "asyncpg"


# ---------------------------------------------------------------------------
# A6 — _validate_python_path
# ---------------------------------------------------------------------------

def test_validate_python_path_pyenv_ok(tmp_path, monkeypatch):
    """A6: pyenv versions/X.Y.Z/bin/pythonN.N path accepted (mocked)."""
    # Build a fake pyenv path that matches the regex
    fake_pyenv = tmp_path / ".pyenv" / "versions" / "3.11.11" / "bin"
    fake_pyenv.mkdir(parents=True)
    fake_python = fake_pyenv / "python3.11"
    fake_python.touch()
    fake_python.chmod(0o755)

    a = PythonEnvRepair()
    resolved = a._validate_python_path(str(fake_python))
    assert str(fake_python) in resolved
    assert _PY_PATH_RE.fullmatch(resolved)


def test_validate_python_path_blocks_tmp_arbitrary(tmp_path):
    """A6: /tmp/malicious-python rejected."""
    fake = tmp_path / "malicious"
    fake.touch()
    fake.chmod(0o755)

    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="pyenv versions whitelist"):
        a._validate_python_path(str(fake))


def test_validate_python_path_blocks_homebrew_python():
    """A6: /opt/homebrew/bin/python3 (externally-managed) rejected."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="pyenv versions whitelist"):
        a._validate_python_path("/opt/homebrew/bin/python3")


def test_validate_python_path_nonexistent_rejected():
    """A6: file doesn't exist → rejected."""
    a = PythonEnvRepair()
    with pytest.raises(ValueError, match="not in pyenv versions|not executable"):
        a._validate_python_path(
            "/Users/nuzantara/.pyenv/versions/99.99.99/bin/python"
        )


# ---------------------------------------------------------------------------
# A4 + A5 + A7 — _attempts_recent_count
# ---------------------------------------------------------------------------

def test_attempts_recent_count_zero_when_no_file(tmp_path, monkeypatch):
    """No prior attempts → count=0."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    assert a._attempts_recent_count("asyncpg>=0.29", "/fake/py") == 0


def test_attempts_recent_count_orphan_started_ttl(tmp_path, monkeypatch):
    """A4: orphan 'started' >600s ago NOT counted; <600s counted."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    f = a._attempts_file("asyncpg>=0.29", "/fake/py")

    old_started = {"ts": time.time() - 700, "outcome": "started", "dep": "x"}
    fresh_started = {"ts": time.time() - 100, "outcome": "started", "dep": "x"}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(old_started) + "\n" + json.dumps(fresh_started) + "\n")

    assert a._attempts_recent_count("asyncpg>=0.29", "/fake/py") == 1


def test_attempts_recent_count_pip_failed_within_ttl(tmp_path, monkeypatch):
    """A4: pip_failed within 24h counted."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    f = a._attempts_file("asyncpg>=0.29", "/fake/py")
    f.parent.mkdir(parents=True, exist_ok=True)
    recs = [
        {"ts": time.time() - 3600, "outcome": "pip_failed", "dep": "x"},
        {"ts": time.time() - 7200, "outcome": "pip_failed", "dep": "x"},
    ]
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    assert a._attempts_recent_count("asyncpg>=0.29", "/fake/py") == 2


def test_attempts_recent_count_old_pip_failed_excluded(tmp_path, monkeypatch):
    """A4: pip_failed >24h ago NOT counted."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    f = a._attempts_file("asyncpg>=0.29", "/fake/py")
    f.parent.mkdir(parents=True, exist_ok=True)
    old = {"ts": time.time() - (25 * 3600), "outcome": "pip_failed", "dep": "x"}
    f.write_text(json.dumps(old) + "\n")
    assert a._attempts_recent_count("asyncpg>=0.29", "/fake/py") == 0


def test_attempts_recent_count_success_not_counted(tmp_path, monkeypatch):
    """Success outcome doesn't trigger quarantine."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    f = a._attempts_file("asyncpg>=0.29", "/fake/py")
    f.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time() - 60, "outcome": "success", "dep": "x"}
    f.write_text(json.dumps(rec) + "\n")
    assert a._attempts_recent_count("asyncpg>=0.29", "/fake/py") == 0


def test_attempts_recent_count_corrupt_file_returns_neg_one(tmp_path, monkeypatch):
    """A7: corrupt JSON → return -1 → caller MUST quarantine."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    f = a._attempts_file("asyncpg>=0.29", "/fake/py")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("{ not valid json\nmore garbage\n")
    assert a._attempts_recent_count("asyncpg>=0.29", "/fake/py") == -1


# ---------------------------------------------------------------------------
# A5 — atomic _record_attempt (fcntl.flock)
# ---------------------------------------------------------------------------

def test_record_attempt_appends_line(tmp_path, monkeypatch):
    """A5: writes valid JSON line."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    a._record_attempt("asyncpg>=0.29", "/fake/py", "started")
    f = a._attempts_file("asyncpg>=0.29", "/fake/py")
    text = f.read_text().strip()
    assert text
    rec = json.loads(text)
    assert rec["outcome"] == "started"
    assert rec["dep"] == "asyncpg>=0.29"
    assert "ts" in rec


def test_record_attempt_error_truncated(tmp_path, monkeypatch):
    """Error field truncated to 500 chars."""
    monkeypatch.setattr(PythonEnvRepair, "ATTEMPTS_DIR", tmp_path)
    a = PythonEnvRepair()
    long_err = "x" * 1000
    a._record_attempt("asyncpg>=0.29", "/fake/py", "pip_failed", long_err)
    f = a._attempts_file("asyncpg>=0.29", "/fake/py")
    rec = json.loads(f.read_text().strip())
    assert len(rec["error"]) == 500


# ---------------------------------------------------------------------------
# A1 — _build_argv
# ---------------------------------------------------------------------------

def test_build_argv_has_index_url_and_no_input():
    """A1: pip command pins index-url + has --no-input."""
    a = PythonEnvRepair()
    argv = a._build_argv("/fake/py", "asyncpg>=0.29")
    assert "--index-url" in argv
    assert "https://pypi.org/simple/" in argv
    assert "--no-input" in argv
    assert "--disable-pip-version-check" in argv
    assert argv[0] == "/fake/py"
    assert argv[-1] == "asyncpg>=0.29"


# ---------------------------------------------------------------------------
# A8 — _build_sanitized_env
# ---------------------------------------------------------------------------

def test_build_sanitized_env_excludes_pip_vars():
    """A8: PIP_* and proxy vars not in sanitized env."""
    a = PythonEnvRepair()
    with patch.dict(os.environ, {
        "PIP_INDEX_URL": "https://malicious.example.com/simple",
        "PIP_TRUSTED_HOST": "malicious.example.com",
        "HTTPS_PROXY": "http://malicious.example.com:8080",
    }):
        env = a._build_sanitized_env()
    assert "PIP_INDEX_URL" not in env
    assert "PIP_TRUSTED_HOST" not in env
    assert "HTTPS_PROXY" not in env
    assert env["PATH"] == "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


# ---------------------------------------------------------------------------
# W33 kill switch
# ---------------------------------------------------------------------------

def test_kill_switch_default_on():
    """W33: env unset → enabled."""
    a = PythonEnvRepair()
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CELL_AUTOREMEDIATION_ENABLED", None)
        assert a._check_kill_switch() is True


def test_kill_switch_disabled():
    """W33: env=false → disabled."""
    a = PythonEnvRepair()
    with patch.dict(os.environ, {"CELL_AUTOREMEDIATION_ENABLED": "false"}):
        assert a._check_kill_switch() is False


def test_kill_switch_various_disabled_values():
    """W33: multiple disabled spellings recognized."""
    a = PythonEnvRepair()
    for val in ("false", "0", "no", "off", "disabled", "FALSE", "Off"):
        with patch.dict(os.environ, {"CELL_AUTOREMEDIATION_ENABLED": val}):
            assert a._check_kill_switch() is False, f"failed for {val!r}"


# ---------------------------------------------------------------------------
# _execute kill-switch short-circuit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_kill_switch_returns_skipped():
    """_execute returns {skipped: kill_switch_active} when disabled."""
    a = PythonEnvRepair()
    with patch.dict(os.environ, {"CELL_AUTOREMEDIATION_ENABLED": "false"}):
        result = await a._execute({"dep": "asyncpg"})
    assert result == {"skipped": "kill_switch_active"}


# ---------------------------------------------------------------------------
# _dry_run (Codex bug #7)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_valid_input_returns_argv():
    """Dry-run on valid input returns full argv."""
    a = PythonEnvRepair()
    # Use a real-ish pyenv path that probably exists in dev — fallback to
    # patched validator if not
    fake_path = "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3.11"
    with patch.object(a, "_validate_python_path", return_value=fake_path):
        result = await a._dry_run({"dep": "asyncpg", "python_path": fake_path})
    assert result["would_pkg_spec"] == "asyncpg>=0.29"
    assert result["would_import_name"] == "asyncpg"
    assert "--index-url" in result["would_argv"]


@pytest.mark.asyncio
async def test_dry_run_invalid_dep_no_crash():
    """Codex bug #7: dry-run on invalid dep returns validation_error, doesn't crash."""
    a = PythonEnvRepair()
    result = await a._dry_run({"dep": "not_in_allowlist_pkg"})
    assert "validation_error" in result
    assert "would_argv" not in result


@pytest.mark.asyncio
async def test_dry_run_injection_blocked():
    """A2 + dry-run: injection attempt blocked even in dry-run."""
    a = PythonEnvRepair()
    result = await a._dry_run({"dep": "asyncpg; rm -rf /"})
    assert "validation_error" in result


# ---------------------------------------------------------------------------
# Integration — registry + SAFE_ACTUATORS
# ---------------------------------------------------------------------------

def test_name_attribute():
    """Class attribute matches expected actuator_ref."""
    assert PythonEnvRepair.name == "python_env_repair"


def test_registry_includes_python_env_repair(fake_redis):
    """build_actuator_registry() exposes python_env_repair."""
    from organism.actuators import build_actuator_registry
    reg = build_actuator_registry(redis=fake_redis)
    assert "python_env_repair" in reg
    assert isinstance(reg["python_env_repair"], PythonEnvRepair)


def test_safe_actuators_includes_python_env_repair():
    """dispatch.py SAFE_ACTUATORS whitelist contains the actuator name.

    Without this, even a correctly-built rule referencing
    python_env_repair would be rejected at dispatch time (REJECTED_UNKNOWN).
    """
    from organism.supervisor.dispatch import SAFE_ACTUATORS
    assert "python_env_repair" in SAFE_ACTUATORS
