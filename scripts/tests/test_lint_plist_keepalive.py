"""Tests for scripts/lint_plist_keepalive.py (superscar #7 KeepAlive lint).

Every FAIL-class detector gets a GUILT case (the historical disease IS
caught) and an INNOCENCE case (the adjacent legitimate state is NOT
flagged) — same discipline lint_home_fork.py's tests apply to superscar #1.
No live ~/Library dependence — everything runs against tmp_path fixtures.
"""
from __future__ import annotations

import importlib.util
import json
import plistlib
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_plist_keepalive.py"
_spec = importlib.util.spec_from_file_location("lint_plist_keepalive", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
lpk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lpk)


# ---------------------------------------------------------------- helpers


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "infra" / "launchagents").mkdir(parents=True)
    (repo / "scripts" / "launchd").mkdir(parents=True)
    (repo / "apps").mkdir(parents=True)
    return repo


def write_plist(path: Path, keepalive, program_args: list[str], start_interval=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"Label": path.stem, "ProgramArguments": program_args}
    if keepalive is not None:
        payload["KeepAlive"] = keepalive
    if start_interval is not None:
        payload["StartInterval"] = start_interval
    path.write_bytes(plistlib.dumps(payload))


def default_roots(repo: Path) -> list[Path]:
    return [repo / r for r in lpk.DEFAULT_ROOTS]


# ---------------------------------------------------------------- KeepAlive truthiness


def test_is_keepalive_managed() -> None:
    assert lpk.is_keepalive_managed(True) is True
    assert lpk.is_keepalive_managed({"SuccessfulExit": False, "Crashed": True}) is True
    assert lpk.is_keepalive_managed(False) is False
    assert lpk.is_keepalive_managed(None) is False
    assert lpk.is_keepalive_managed({}) is False


# ---------------------------------------------------------------- classify_wrapper


def test_classify_exec_is_warn_class() -> None:
    # DEMOTED post day-1 calibration (#3 discipline): exec-into-server is the
    # legitimate daemon idiom; exec smells are WARN, elevated only by --strict.
    text = "#!/bin/bash\nset -euo pipefail\nexec python3 x.py\n"
    findings, exec_warns, warn = lpk.classify_wrapper(text)
    assert findings == []
    assert len(exec_warns) == 1
    line_no, smell = exec_warns[0]
    assert line_no == 3
    assert "exec" in smell
    assert warn is False


def test_classify_guilt_nohup_background() -> None:
    text = "#!/bin/bash\nnohup node server.js &\necho started\n"
    findings, exec_warns, warn = lpk.classify_wrapper(text)
    assert len(findings) == 1
    line_no, smell = findings[0]
    assert line_no == 2
    assert "nohup" in smell
    assert warn is False


def test_classify_innocence_blocking_loop() -> None:
    text = (
        "#!/bin/bash\n"
        "while true; do\n"
        "  ./do_thing.sh\n"
        "  sleep 60\n"
        "done\n"
    )
    findings, exec_warns, warn = lpk.classify_wrapper(text)
    assert findings == []
    assert warn is False


def test_classify_innocence_exec_fd_redirect() -> None:
    """The superscar #3 carve-out: `exec 9>lockfile` opens a file
    descriptor, it does not replace the process — a real line from this
    repo's own intake-worker-run.sh (a genuinely long-running KeepAlive
    worker) must NOT be flagged as a one-shot smell."""
    text = (
        "#!/bin/bash\n"
        'exec 9>"${LOCKFILE}"\n'
        "while true; do\n"
        "  do_work\n"
        "  sleep 5\n"
        "done\n"
    )
    findings, exec_warns, warn = lpk.classify_wrapper(text)
    assert findings == []
    assert warn is False


def test_classify_warn_short_wrapper_no_blocking_marker() -> None:
    text = "#!/bin/bash\necho hello\n"
    findings, exec_warns, warn = lpk.classify_wrapper(text)
    assert findings == []
    assert warn is True


def test_classify_innocence_long_wrapper_no_findings_no_warn() -> None:
    # 200+ lines, no exec/nohup, no recognized blocking marker: absence of
    # evidence in a large orchestrator is NOT flagged as WARN (spec: warn
    # only applies when < 200 lines).
    body = "\n".join(f"echo line-{i}" for i in range(250))
    text = f"#!/bin/bash\n{body}\n"
    findings, exec_warns, warn = lpk.classify_wrapper(text)
    assert findings == []
    assert warn is False


def test_classify_innocence_nohup_without_background() -> None:
    text = "#!/bin/bash\nnohup ./foo.sh && echo done\n"
    findings, exec_warns, warn = lpk.classify_wrapper(text)
    assert findings == []


# ---------------------------------------------------------------- resolve_wrapper


def test_resolve_wrapper_repo_relative_direct(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "scripts" / "run.sh").write_text("exec foo\n")
    argv = ["/bin/bash", "scripts/run.sh"]
    index = lpk.build_basename_index(default_roots(repo), [])
    wrapper, reason = lpk.resolve_wrapper(argv, repo, index)
    assert reason is None
    assert wrapper == repo / "scripts" / "run.sh"


def test_resolve_wrapper_basename_bridge_lookup(tmp_path: Path) -> None:
    """HOME-fork bridge shape (superscar #1 W68/W72): the plist references
    an absolute ~nuzantara path that doesn't exist here, but a same-named
    file IS tracked somewhere under the scanned roots."""
    repo = make_repo(tmp_path)
    bridge = repo / "infra" / "openclaw" / "wr2"
    bridge.mkdir(parents=True)
    (bridge / "wr2-script-wrapper.sh").write_text("exec run-it\n")
    argv = ["/Users/nuzantara/.openclaw/bin/wr2/wr2-script-wrapper.sh", "scripts/wr2_supervisor.py"]
    index = lpk.build_basename_index(default_roots(repo), [])
    wrapper, reason = lpk.resolve_wrapper(argv, repo, index)
    assert reason is None
    assert wrapper == bridge / "wr2-script-wrapper.sh"


def test_resolve_wrapper_inline_shell_flag_unresolved(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    argv = ["/bin/bash", "-lc", "set -a; source ~/.env; set +a; exec ~/bin/python -m thing"]
    index = lpk.build_basename_index(default_roots(repo), [])
    wrapper, reason = lpk.resolve_wrapper(argv, repo, index)
    assert wrapper is None
    assert reason == "inline-shell(-c/-lc)"


def test_resolve_wrapper_direct_binary_unresolved(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    argv = ["/opt/homebrew/bin/fly", "proxy", "15432:5432"]
    index = lpk.build_basename_index(default_roots(repo), [])
    wrapper, reason = lpk.resolve_wrapper(argv, repo, index)
    assert wrapper is None
    assert reason == "not-resolvable-in-repo"


# ---------------------------------------------------------------- end-to-end run()


def test_run_guilt_exec_one_shot(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nexec python3 -m worker\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.worker.plist",
        keepalive=True,
        program_args=["/bin/bash", str(wrapper)],
    )
    result = lpk.run(default_roots(repo), repo, verbose=False)
    # exec smell is WARN-class by default (exit 0)…
    assert result["exit"] == 0
    assert result["findings"] == []
    assert len(result["warns"]) == 1
    assert "com.test.worker.plist" in result["warns"][0]
    assert "run.sh:2" in result["warns"][0]
    assert result["errors"] == []
    # …and --strict elevates it to a finding with exit 1.
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = lpk.main([
            "--repo-root", str(repo), "--strict",
            "--root", "infra/launchagents", "--root", "scripts/launchd",
            "--root", "infra", "--root", "apps",
        ])
    assert rc & 1 == 1
    assert "[strict]" in buf.getvalue()


def test_run_guilt_nohup(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nnohup node server.js &\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.nohup.plist",
        keepalive=True,
        program_args=["/bin/zsh", str(wrapper)],
    )
    result = lpk.run(default_roots(repo), repo, verbose=False)
    assert result["exit"] == 1
    assert len(result["findings"]) == 1
    assert "nohup" in result["findings"][0]


def test_run_innocence_blocking_loop_wrapper(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nwhile true; do\n  ./do.sh\n  sleep 30\ndone\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.clean.plist",
        keepalive=True,
        program_args=["/bin/bash", str(wrapper)],
    )
    result = lpk.run(default_roots(repo), repo, verbose=False)
    assert result["exit"] == 0
    assert result["findings"] == []
    assert result["warns"] == []


def test_run_innocence_keepalive_absent_exec_wrapper(tmp_path: Path) -> None:
    """A one-shot wrapper is only a problem UNDER KeepAlive — no KeepAlive
    key at all means launchd runs it once (StartInterval-style cron) and a
    plain `exec` inside is completely normal."""
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nexec python3 -m worker\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.nokeepalive.plist",
        keepalive=None,
        program_args=["/bin/bash", str(wrapper)],
    )
    result = lpk.run(default_roots(repo), repo, verbose=False)
    assert result == {
        "schema": 1, "findings": [], "warns": [], "unresolved": [], "errors": [], "exit": 0,
    }


def test_run_innocence_start_interval_cron_no_keepalive(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nexec python3 -m worker\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.cron.plist",
        keepalive=False,
        program_args=["/bin/bash", str(wrapper)],
        start_interval=900,
    )
    result = lpk.run(default_roots(repo), repo, verbose=False)
    assert result["exit"] == 0
    assert result["findings"] == []


def test_run_warn_c_short_wrapper(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\necho hello\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.warn.plist",
        keepalive=True,
        program_args=["/bin/bash", str(wrapper)],
    )
    result = lpk.run(default_roots(repo), repo, verbose=False)
    assert result["exit"] == 0  # WARN never fails the build
    assert result["findings"] == []
    assert len(result["warns"]) == 1
    assert "com.test.warn.plist" in result["warns"][0]


def test_run_unresolved_only_when_verbose(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_plist(
        repo / "infra" / "launchagents" / "com.test.proxy.plist",
        keepalive=True,
        program_args=["/opt/homebrew/bin/fly", "proxy", "15432:5432"],
    )
    quiet = lpk.run(default_roots(repo), repo, verbose=False)
    assert quiet["unresolved"] == []
    assert quiet["exit"] == 0
    verbose = lpk.run(default_roots(repo), repo, verbose=True)
    assert len(verbose["unresolved"]) == 1
    assert verbose["exit"] == 0  # unresolved is informational, never a failure


def test_run_unparseable_plist_is_error_not_finding(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "infra" / "launchagents" / "broken.plist").write_bytes(b"not a plist at all")
    result = lpk.run(default_roots(repo), repo, verbose=False)
    assert result["findings"] == []
    assert len(result["errors"]) == 1
    assert "broken.plist" in result["errors"][0]
    assert result["exit"] == 4


def test_run_bitmask_findings_plus_errors(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nnohup python3 -m worker &\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.worker.plist",
        keepalive=True,
        program_args=["/bin/bash", str(wrapper)],
    )
    (repo / "infra" / "launchagents" / "broken.plist").write_bytes(b"garbage")
    result = lpk.run(default_roots(repo), repo, verbose=False)
    assert result["exit"] == 5  # 1 (finding) | 4 (error)


# ---------------------------------------------------------------- main() / --json


def _write_config_free_env(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def test_main_json_shape_clean(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path)
    rc = lpk.main(["--repo-root", str(repo), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "schema": 1, "findings": [], "warns": [], "unresolved": [], "errors": [], "exit": 0,
    }


def test_main_json_shape_with_finding(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path)
    wrapper = repo / "apps" / "worker" / "run.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/bash\nnohup python3 -m worker &\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.worker.plist",
        keepalive=True,
        program_args=["/bin/bash", str(wrapper)],
    )
    rc = lpk.main(["--repo-root", str(repo), "--json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == 1
    assert len(payload["findings"]) == 1
    assert payload["exit"] == 1
    for key in ("schema", "findings", "warns", "unresolved", "errors", "exit"):
        assert key in payload


def test_main_custom_root_widens_coverage(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """--root lets a caller widen scope to bare scripts/ (documented scope
    limitation of the defaults)."""
    repo = make_repo(tmp_path)
    (repo / "scripts").mkdir(exist_ok=True)
    wrapper = repo / "scripts" / "job_run.sh"
    wrapper.write_text("#!/bin/bash\nnohup python3 -m job &\n")
    write_plist(
        repo / "infra" / "launchagents" / "com.test.job.plist",
        keepalive=True,
        program_args=["/bin/bash", str(wrapper)],
    )
    # Default roots: NOT resolvable (scripts/ bare is out of scope).
    rc_default = lpk.main(["--repo-root", str(repo), "--json"])
    assert rc_default == 0
    default_payload = json.loads(capsys.readouterr().out)
    assert default_payload["findings"] == []

    # Widened roots: resolvable, finding surfaces.
    rc_widened = lpk.main(["--repo-root", str(repo), "--root", "infra", "--root", "scripts", "--json"])
    assert rc_widened == 1
    widened_payload = json.loads(capsys.readouterr().out)
    assert len(widened_payload["findings"]) == 1
