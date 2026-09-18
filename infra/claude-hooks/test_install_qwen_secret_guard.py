#!/usr/bin/env python3
"""test_install_qwen_secret_guard.py — guilt AND innocence for the installer.

The case that matters most is the one this installer exists because of: a guard
that denies EVERYTHING must be refused. `python3 <missing or broken file>` exits
2, which is DENY in the hook contract, so a wiring step that only checked "does
the guilty payload get denied" would have installed a hook that bricks every Bash
and Read call in every Qwen session — and reported success doing it.

Run: python3 infra/claude-hooks/test_install_qwen_secret_guard.py
Also: pytest infra/claude-hooks/test_install_qwen_secret_guard.py
"""
from __future__ import annotations

import json
import os
import pathlib
import stat
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
INSTALLER = HERE / "install_qwen_secret_guard.py"
REAL_HOOKS = HERE                      # the shipped guard + registry live here


def _run(tmp: pathlib.Path, *extra: str, settings: pathlib.Path | None = None,
         hooks: pathlib.Path | None = None, repo: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    s = settings if settings is not None else tmp / "settings.json"
    h = hooks if hooks is not None else tmp / "hooks"
    r = repo if repo is not None else REAL_HOOKS
    cmd = [sys.executable, str(INSTALLER), "--settings", str(s),
           "--hooks-dir", str(h), "--repo-hooks-dir", str(r), *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _write_settings(p: pathlib.Path, extra: dict | None = None) -> dict:
    d = {"model": {"name": "qwen3.8-max", "fastModel": "qwen3.6-flash"},
         "context": {"clearContextOnIdle": {"toolResultsTotalCharsThreshold": 150000}},
         "permissions": {"allow": ["Bash(git *)"], "deny": ["Bash(sudo *)"]}}
    if extra:
        d.update(extra)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2))
    os.chmod(p, 0o600)
    return d


def _stub_repo(tmp: pathlib.Path, body: str) -> pathlib.Path:
    """A fake repo-hooks dir whose guard always exits the given way."""
    d = tmp / "stubrepo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "secret_expansion_guard.py").write_text(body)
    (d / "secret-expansion-registry.json").write_text(
        json.dumps({"version": 1, "secret_env_vars": ["BAILIAN_TOKEN_PLAN_API_KEY"],
                    "secret_env_var_patterns": [], "secret_files": []}))
    return d


def test_installs_registers_and_verifies(tmp_path):
    before = _write_settings(tmp_path / "settings.json")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "verified" in r.stdout
    s = json.loads((tmp_path / "settings.json").read_text())
    pre = s["hooks"]["PreToolUse"]
    assert len(pre) == 1
    assert pre[0]["matcher"] == "Bash|Monitor|Read"
    cmd = pre[0]["hooks"][0]["command"]
    assert cmd.endswith("hooks/secret_expansion_guard.py")
    assert str(tmp_path) in cmd, "must point at the installed $HOME copy, not the repo"
    # everything else survived
    for k, v in before.items():
        assert s[k] == v, f"installer clobbered {k}"
    # the installed twin is byte-identical to the repo source, so lint_home_fork
    # --check (sha256 live vs repo twin) stays green instead of reporting drift
    a = (tmp_path / "hooks" / "secret_expansion_guard.py").read_bytes()
    b = (REAL_HOOKS / "secret_expansion_guard.py").read_bytes()
    assert a == b
    assert stat.S_IMODE((tmp_path / "hooks" / "secret_expansion_guard.py").stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "settings.json").stat().st_mode) == 0o600


def test_second_run_is_idempotent_and_does_not_rebackup(tmp_path):
    _write_settings(tmp_path / "settings.json")
    assert _run(tmp_path).returncode == 0
    r = _run(tmp_path)
    assert r.returncode == 0
    assert "already registered" in r.stdout
    s = json.loads((tmp_path / "settings.json").read_text())
    assert len(s["hooks"]["PreToolUse"]) == 1, "second run duplicated the hook"
    backups = list(tmp_path.glob("settings.json.bak-qwenguard-*"))
    assert len(backups) == 1, f"second run made another backup: {backups}"


def test_refuses_a_guard_whose_file_cannot_run(tmp_path):
    """THE literal near-miss: `python3 <missing or unrunnable file>` exits **2**
    with an empty stderr, and 2 is DENY in the hook contract. Wiring that would
    have blocked every Bash and Read call in every Qwen session — while a check
    that only tested guilt reported success. It is caught here by the reason-format
    half of _verify (rc 2 with no contract-conform DENY line), which is the
    signature that distinguishes "the guard denied this" from "python could not
    run the guard".
    """
    _write_settings(tmp_path / "settings.json")
    repo = _stub_repo(tmp_path, "import sys\nsys.exit(2)\n")
    r = _run(tmp_path, repo=repo)
    assert r.returncode == 4, f"expected refusal, got rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "contract-conform" in r.stderr
    s = json.loads((tmp_path / "settings.json").read_text())
    assert "hooks" not in s, "settings were modified despite the refusal"


def test_refuses_a_guard_that_denies_everything(tmp_path):
    """The subtler version: a guard that emits a perfectly contract-conform DENY
    for everything passes the guilt half, so ONLY the innocence half can catch it.
    This is why both halves are mandatory on every run."""
    _write_settings(tmp_path / "settings.json")
    repo = _stub_repo(
        tmp_path,
        "import sys\n"
        "sys.stdin.read()\n"
        "sys.stderr.write('[secret-expansion-guard] DENY X9 always\\n')\n"
        "sys.exit(2)\n",
    )
    r = _run(tmp_path, repo=repo)
    assert r.returncode == 4, f"expected refusal, got rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "innocence" in r.stderr
    assert "hooks" not in json.loads((tmp_path / "settings.json").read_text())


def test_refuses_a_guard_that_allows_everything(tmp_path):
    """The mirror image: a guard that never denies is a check that exists, carries
    the right name, and enforces nothing."""
    _write_settings(tmp_path / "settings.json")
    repo = _stub_repo(tmp_path, "import sys\nsys.exit(0)\n")
    r = _run(tmp_path, repo=repo)
    assert r.returncode == 4
    assert "guilt" in r.stderr
    assert "hooks" not in json.loads((tmp_path / "settings.json").read_text())


def test_refuses_a_guard_that_denies_without_a_reason(tmp_path):
    """Exit 2 with no stderr line violates the hook contract — the session gets
    blocked with nothing to correct itself against."""
    _write_settings(tmp_path / "settings.json")
    repo = _stub_repo(tmp_path, "import sys\nsys.stderr.write('nope\\n')\nsys.exit(2)\n")
    r = _run(tmp_path, repo=repo)
    assert r.returncode == 4
    assert "contract-conform" in r.stderr


def test_refuses_when_the_repo_source_is_missing(tmp_path):
    _write_settings(tmp_path / "settings.json")
    empty = tmp_path / "norepo"
    empty.mkdir()
    r = _run(tmp_path, repo=empty)
    assert r.returncode == 3
    assert "repo source missing" in r.stderr
    assert "hooks" not in json.loads((tmp_path / "settings.json").read_text())


def test_refuses_to_create_a_missing_settings_file(tmp_path):
    r = _run(tmp_path)                       # no settings.json written
    assert r.returncode == 5
    assert not (tmp_path / "settings.json").exists()


def test_refuses_invalid_settings_json(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json")
    r = _run(tmp_path)
    assert r.returncode == 5
    assert p.read_text() == "{ not json", "invalid settings were overwritten"


def test_dry_run_writes_nothing(tmp_path):
    before = _write_settings(tmp_path / "settings.json")
    text_before = (tmp_path / "settings.json").read_text()
    r = _run(tmp_path, "--dry-run")
    assert r.returncode == 0
    assert "dry-run" in r.stdout
    assert (tmp_path / "settings.json").read_text() == text_before
    assert json.loads((tmp_path / "settings.json").read_text()) == before


def test_never_prints_a_credential_value(tmp_path):
    """The installer runs against the real registry, whose names are real. Its own
    output must carry variable NAMES and paths, never a value (W106 class)."""
    _write_settings(tmp_path / "settings.json")
    r = _run(tmp_path)
    vault = pathlib.Path(os.path.expanduser("~/.nuzantara-secrets.env"))
    if vault.is_file():
        import re
        for line in vault.read_text(errors="replace").splitlines():
            m = re.match(r"^\s*export\s+[A-Za-z_][A-Za-z0-9_]*='([^']{12,})'", line)
            if m:
                assert m.group(1) not in r.stdout + r.stderr, "installer printed a secret value"


def _main() -> int:
    import tempfile
    fails = 0
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        with tempfile.TemporaryDirectory() as d:
            try:
                argcount = fn.__code__.co_argcount
                fn(pathlib.Path(d)) if argcount else fn()
                print(f"  PASS  {fn.__name__}")
            except AssertionError as e:
                fails += 1
                print(f"  FAIL  {fn.__name__}: {str(e)[:220]}")
            except Exception as e:
                fails += 1
                print(f"  ERR   {fn.__name__}: {type(e).__name__}: {str(e)[:180]}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_main())
