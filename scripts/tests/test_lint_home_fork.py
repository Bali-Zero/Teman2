"""Tests for scripts/lint_home_fork.py (superscar #1 HOME-fork lint).

W82 discipline applied to the lint itself: every detection arm gets a GUILT
case (the historical disease IS caught) and an INNOCENCE case (the adjacent
legitimate state is NOT flagged). No live-HOME dependence — everything runs
against tmp_path fixtures.
"""
from __future__ import annotations

import importlib.util
import json
import plistlib
import subprocess
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_home_fork.py"
_spec = importlib.util.spec_from_file_location("lint_home_fork", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
lhf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lhf)


# ---------------------------------------------------------------- helpers


def make_env(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    (home / "scripts").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    return home, repo


# ---------------------------------------------------------------- expand/label


def test_expand_home_variants(tmp_path: Path) -> None:
    home = tmp_path / "h"
    assert lhf.expand_home("~/x/y.sh", home) == home / "x/y.sh"
    assert lhf.expand_home("$HOME/x.sh", home) == home / "x.sh"
    assert lhf.expand_home("${HOME}/x.sh", home) == home / "x.sh"
    assert lhf.expand_home("/abs/path.sh", home) == Path("/abs/path.sh")


def test_machine_label_mapping() -> None:
    assert lhf.machine_label("Air-M5.local") == "m5"
    assert lhf.machine_label("Mini-Pro2.local") == "mini"
    assert lhf.machine_label("Nuzantara") == "pro"
    assert lhf.machine_label("weird-host") == "weird-host"


# ---------------------------------------------------------------- check arm


def test_check_guilt_diverged(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    (home / "scripts/run.sh").write_text("EXPECTED_BRANCH=deploy/main\n")
    (repo / "scripts/run.sh").write_text("EXPECTED_BRANCH=main\n")
    pairs = [{"live": "~/scripts/run.sh", "repo": "scripts/run.sh", "machines": ["all"]}]
    breaches = lhf.check_pairs(pairs, repo, home, "mini")
    assert len(breaches) == 1 and "DIVERGED" in breaches[0]


def test_check_innocence_identical_and_symlink(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    (repo / "scripts/run.sh").write_text("same\n")
    (home / "scripts/run.sh").write_text("same\n")
    (home / "scripts/link.sh").symlink_to(repo / "scripts/run.sh")
    pairs = [
        {"live": "~/scripts/run.sh", "repo": "scripts/run.sh", "machines": ["all"]},
        {"live": "~/scripts/link.sh", "repo": "scripts/run.sh", "machines": ["all"]},
    ]
    assert lhf.check_pairs(pairs, repo, home, "mini") == []


def test_check_guilt_no_repo_twin(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    (home / "scripts/orphan.sh").write_text("live only\n")
    pairs = [{"live": "~/scripts/orphan.sh", "repo": "scripts/orphan.sh", "machines": ["all"]}]
    breaches = lhf.check_pairs(pairs, repo, home, "mini")
    assert len(breaches) == 1 and "NO-REPO-TWIN" in breaches[0]


def test_check_machine_scope_and_absent_live(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    (home / "scripts/pro-only.sh").write_text("divergent\n")
    (repo / "scripts/pro-only.sh").write_text("other\n")
    pairs = [{"live": "~/scripts/pro-only.sh", "repo": "scripts/pro-only.sh", "machines": ["pro"]}]
    # INNOCENCE: pair scoped to pro is not probed on mini …
    assert lhf.check_pairs(pairs, repo, home, "mini") == []
    # … and an absent live copy on the right machine is a skip, not a breach.
    pairs2 = [{"live": "~/scripts/ghost.sh", "repo": "scripts/pro-only.sh", "machines": ["all"]}]
    assert lhf.check_pairs(pairs2, repo, home, "mini") == []


def test_merge_pairs_dedupes() -> None:
    a = [{"live": "~/a", "repo": "r/a", "machines": ["all"]}]
    b = [
        {"live": "~/a", "repo": "r/a", "machines": ["pro"]},
        {"live": "~/b", "repo": "r/b", "machines": ["all"]},
    ]
    merged = lhf.merge_pairs(a, b)
    assert len(merged) == 2
    assert merged[0]["machines"] == ["all"]  # first source wins


# ---------------------------------------------------------------- discover arm


def _write_plist(dir_: Path, name: str, program_args: list[str]) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_bytes(plistlib.dumps({"Label": name, "ProgramArguments": program_args}))


def test_extract_home_paths_sh_c_and_home_var(tmp_path: Path) -> None:
    home = tmp_path / "home"
    text = "/bin/bash -lc '~/scripts/job.sh --flag && ${HOME}/bin/other.sh'"
    found = lhf.extract_home_paths(text, home)
    assert "~/scripts/job.sh" in found
    assert "~/bin/other.sh" in found


def test_extract_home_paths_ignores_other_user(tmp_path: Path) -> None:
    home = tmp_path / "home"
    found = lhf.extract_home_paths("/Users/someoneelse/scripts/x.sh", home)
    assert found == set()


def test_discover_guilt_undeclared_plist(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.test.rogue.plist", ["/bin/bash", str(home / "scripts/rogue.sh")])
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert len(findings) == 1 and "UNDECLARED" in findings[0] and "rogue.sh" in findings[0]
    assert errors == []


def test_discover_innocence_declared_allowed_repo(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    (repo / "scripts/canon.sh").write_text("x\n")
    _write_plist(agents, "com.test.declared.plist", [str(home / "scripts/declared.sh")])
    _write_plist(agents, "com.test.allowed.plist", [str(home / "Library/Vendor/tool")])
    _write_plist(agents, "com.test.repo.plist", [str(repo / "scripts/canon.sh")])
    errors: list[str] = []
    findings = lhf.discover_undeclared(
        [agents], "", home, repo,
        declared_lives={"~/scripts/declared.sh"},
        allow=["~/Library/Vendor/*"],
        errors=errors,
    )
    # repo-resident payload is outside HOME here, so it never even enters scope;
    # declared + allowed are both innocently passed.
    assert findings == []
    assert errors == []


def test_discover_guilt_worktree_ref(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = home / "Desktop/nuzantara"
    wt = repo / ".worktrees/infra-task/scripts"
    wt.mkdir(parents=True)
    (wt / "job.sh").write_text("x\n")
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.test.wt.plist", [str(wt / "job.sh")])
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert len(findings) == 1 and "WORKTREE-REF" in findings[0]


def test_discover_innocence_repo_resident_under_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = home / "Desktop/nuzantara"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/canon.sh").write_text("x\n")
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.test.repo.plist", [str(repo / "scripts/canon.sh")])
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert findings == []


def test_discover_crontab_lines(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    crontab = "# comment ~/scripts/commented.sh\n*/5 * * * * ~/scripts/cronjob.sh\n"
    errors: list[str] = []
    findings = lhf.discover_undeclared([], crontab, home, repo, set(), [], errors)
    assert len(findings) == 1
    assert "cronjob.sh" in findings[0] and "crontab:line2" in findings[0]


def test_discover_innocence_crontab_redirect_target(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    crontab = "*/5 * * * * ~/scripts/job.sh >> ~/logs/job.log 2>&1\n"
    errors: list[str] = []
    findings = lhf.discover_undeclared([], crontab, home, repo, set(), [], errors)
    assert len(findings) == 1  # the script, never the log sink
    assert "job.sh" in findings[0] and "job.log" not in findings[0]


def test_discover_innocence_data_args_excluded(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    logs = home / "logs"
    logs.mkdir()
    (logs / "worker.log").write_text("")
    (home / ".secrets.env").write_text("")
    agents = home / "Library/LaunchAgents"
    _write_plist(
        agents, "com.test.worker.plist",
        ["/bin/echo", str(home / ".secrets.env"), str(logs / "worker.log"), str(logs)],
    )
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert findings == []  # env/log/dir arguments are data, not executed payloads


def test_discover_guilt_argv0_without_extension(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    (home / "tools").mkdir()
    (home / "tools/mybin").write_text("binary-ish")  # no ext, no exec bit
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.test.bin.plist", [str(home / "tools/mybin"), "--serve"])
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert len(findings) == 1 and "mybin" in findings[0]  # argv[0] IS executed


def test_discover_innocence_space_path_allowlisted(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    vendor = home / "Library/Application Support/Google/GoogleUpdater"
    vendor.mkdir(parents=True)
    (vendor / "updater").write_text("")
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.google.up.plist", [str(vendor / "updater"), "--wake"])
    errors: list[str] = []
    findings = lhf.discover_undeclared(
        [agents], "", home, repo, set(),
        allow=["~/Library/Application Support/Google/GoogleUpdater/*"],
        errors=errors,
    )
    assert findings == []  # space-containing vendor path matches the allow glob whole


def test_discover_unparseable_plist_is_error_not_finding(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "broken.plist").write_bytes(b"not a plist at all")
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert findings == []
    assert len(errors) == 1 and "broken.plist" in errors[0]


# ---------------------------------------------------------------- exit contract


def _write_config(tmp_path: Path, pairs: list[dict], allow: list[str] | None = None) -> Path:
    cfg = tmp_path / "declared-pairs.json"
    cfg.write_text(json.dumps({"pairs": pairs, "allow": allow or []}))
    return cfg


def test_main_exit_0_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home, repo = make_env(tmp_path)
    (repo / "scripts/run.sh").write_text("same\n")
    (home / "scripts/run.sh").write_text("same\n")
    cfg = _write_config(tmp_path, [{"live": "~/scripts/run.sh", "repo": "scripts/run.sh"}])
    monkeypatch.setattr(lhf.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    rc = lhf.main([
        "--config", str(cfg), "--home", str(home), "--repo-root", str(repo),
        "--plist-dir", str(home / "Library/LaunchAgents"), "--json",
    ])
    assert rc == 0


def test_main_exit_bitmask_diverged_plus_undeclared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    home, repo = make_env(tmp_path)
    (repo / "scripts/run.sh").write_text("repo\n")
    (home / "scripts/run.sh").write_text("live-divergent\n")
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.test.rogue.plist", [str(home / "scripts/rogue.sh")])
    cfg = _write_config(tmp_path, [{"live": "~/scripts/run.sh", "repo": "scripts/run.sh"}])
    monkeypatch.setattr(lhf.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    rc = lhf.main([
        "--config", str(cfg), "--home", str(home), "--repo-root", str(repo),
        "--plist-dir", str(agents), "--json",
    ])
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == 1
    assert len(payload["check_breaches"]) == 1
    assert len(payload["discover_undeclared"]) == 1


def test_main_exit_4_on_operational_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "broken.plist").write_bytes(b"garbage")
    cfg = _write_config(tmp_path, [])
    monkeypatch.setattr(
        lhf.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "crontab: permission denied"),
    )
    rc = lhf.main([
        "--config", str(cfg), "--home", str(home), "--repo-root", str(repo),
        "--plist-dir", str(agents), "--discover", "--json",
    ])
    assert rc == 4
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["errors"]) == 2  # broken plist + crontab failure
    assert payload["discover_undeclared"] == []


def test_main_no_crontab_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, repo = make_env(tmp_path)
    cfg = _write_config(tmp_path, [])
    monkeypatch.setattr(
        lhf.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "crontab: no crontab for nuzantara"),
    )
    rc = lhf.main([
        "--config", str(cfg), "--home", str(home), "--repo-root", str(repo),
        "--plist-dir", str(home / "Library/LaunchAgents"), "--discover",
    ])
    assert rc == 0
