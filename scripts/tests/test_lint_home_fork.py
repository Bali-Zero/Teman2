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
import xml.parsers.expat
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
    repo = home / "nuzantara"
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
    repo = home / "nuzantara"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/canon.sh").write_text("x\n")
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.test.repo.plist", [str(repo / "scripts/canon.sh")])
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert findings == []


def test_discover_guilt_undeclared_json_hook_registry(tmp_path: Path) -> None:
    """W347: a *.json hook registry hardcoding a HOME path the plist/crontab
    scan never looks at — the shape that let `.codex/hooks.json` read
    "0 undeclared payloads" while running an untracked live copy."""
    home, repo = make_env(tmp_path)
    registry = home / ".codex" / "hooks.json"
    registry.parent.mkdir(parents=True)
    rogue = home / ".codex" / "hooks" / "codex-spalla-trigger.sh"
    registry.write_text(json.dumps({"hooks": [{"command": str(rogue)}]}))
    errors: list[str] = []
    findings = lhf.discover_undeclared(
        [], "", home, repo, set(), [], errors, json_registries=[registry]
    )
    assert len(findings) == 1
    assert "UNDECLARED" in findings[0] and "codex-spalla-trigger.sh" in findings[0]
    assert errors == []


def test_discover_innocence_json_hook_registry_declared_or_absent(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    registry = home / ".codex" / "hooks.json"
    registry.parent.mkdir(parents=True)
    declared = home / ".codex" / "hooks" / "declared.sh"
    registry.write_text(json.dumps({"hooks": [{"command": str(declared)}]}))
    errors: list[str] = []
    # Declared pair: innocent.
    findings = lhf.discover_undeclared(
        [], "", home, repo, {"~/.codex/hooks/declared.sh"}, [], errors,
        json_registries=[registry],
    )
    assert findings == []
    # Registry file simply absent (untracked, per-machine, most checkouts
    # won't have it): innocent, no error.
    findings2 = lhf.discover_undeclared(
        [], "", home, repo, set(), [], errors,
        json_registries=[home / ".codex" / "missing.json"],
    )
    assert findings2 == [] and errors == []


def test_discover_guilt_json_hook_registry_unparseable(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    registry = home / ".codex" / "hooks.json"
    registry.parent.mkdir(parents=True)
    registry.write_text("{not valid json")
    errors: list[str] = []
    findings = lhf.discover_undeclared(
        [], "", home, repo, set(), [], errors, json_registries=[registry]
    )
    assert findings == []
    assert len(errors) == 1 and "json hook registry unreadable" in errors[0]


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


def test_discover_innocence_double_dash_comment_plist_recovered(tmp_path: Path) -> None:
    """Guard against the 2026-08-07 Pro blind spot: strict Expat rejects a
    `<!-- ... -->` comment body containing a literal `--` (e.g. `--apply`),
    but macOS's own `plutil` accepts the exact same file (it's what launchd
    itself loads). The census must recover the payload via plutil, not lose
    the whole plist's coverage to `errors`."""
    if subprocess.run(["which", "plutil"], capture_output=True).returncode != 0:
        pytest.skip("plutil not available on this platform")
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "commented.plist").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!-- ENFORCING since 2026-05-30: --apply added after review -->\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\"><dict>\n"
        "  <key>Label</key><string>com.example.commented</string>\n"
        "  <key>ProgramArguments</key><array>\n"
        f"    <string>{home}/scripts/undeclared.sh</string>\n"
        "  </array>\n"
        "</dict></plist>\n"
    )
    with pytest.raises(xml.parsers.expat.ExpatError):  # sanity: really Expat-invalid
        plistlib.loads((agents / "commented.plist").read_bytes())
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert errors == []
    assert any("undeclared.sh" in f for f in findings)


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


def test_main_json_includes_resolved_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The main-checkout resolution is deliberate (W81 worktree-hardening) but
    was previously silent — a caller could not tell which config/repo-root
    was actually read. `resolved_config`/`resolved_repo_root` make it visible
    without changing the resolution itself."""
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
    payload = json.loads(capsys.readouterr().out)
    assert payload["resolved_config"] == str(cfg.resolve())
    assert payload["resolved_repo_root"] == str(repo.resolve())


def test_main_text_prints_resolved_banner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A worktree-cwd invocation with an explicit --config/--repo-root must
    name THOSE paths in the banner, not the module-level default — the
    banner's whole purpose is to make the actually-resolved paths visible."""
    home, repo = make_env(tmp_path)
    (repo / "scripts/run.sh").write_text("same\n")
    (home / "scripts/run.sh").write_text("same\n")
    cfg = _write_config(tmp_path, [{"live": "~/scripts/run.sh", "repo": "scripts/run.sh"}])
    monkeypatch.setattr(lhf.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    rc = lhf.main([
        "--config", str(cfg), "--home", str(home), "--repo-root", str(repo),
        "--plist-dir", str(home / "Library/LaunchAgents"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    banner = next(line for line in out.splitlines() if line.startswith("[resolved]"))
    assert f"config={cfg.resolve()}" in banner
    assert f"repo-root={repo.resolve()}" in banner
    # Innocence: the banner must not silently name the module's own default
    # REPO_ROOT/DEFAULT_CONFIG when an explicit override was passed.
    assert str(lhf.REPO_ROOT) not in banner or repo.resolve() == lhf.REPO_ROOT
    assert str(lhf.DEFAULT_CONFIG) not in banner or cfg.resolve() == lhf.DEFAULT_CONFIG


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


# ---------------------------------------------------------------- mutation survivors
# Each test below killed a hand-checked mutant that the suite above let live
# (AST mutation sweep of scripts/lint_home_fork.py, 2026-10-12). Expected values
# are written from the CONTRACT in the docstrings/exit-code legend, not read back
# from the implementation. Each carries a guilt case and its innocence twin.


def _quiet_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        lhf.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", "")
    )


def _argv(tmp_path: Path, home: Path, repo: Path, *extra: str) -> list[str]:
    cfg = _write_config(tmp_path, [{"live": "~/scripts/run.sh", "repo": "scripts/run.sh"}])
    return [
        "--config", str(cfg), "--home", str(home), "--repo-root", str(repo),
        "--plist-dir", str(home / "Library/LaunchAgents"), "--no-fetch",
        "--json-hook-registry", str(tmp_path / "absent-registry.json"), *extra,
    ]


def test_strict_checkout_promotes_a_stale_notice_to_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Default: a checkout trailing origin/main is REPORTED with exit 0 (on M5 it
    is deliberately left behind). `--strict-checkout` is the opt-in that makes the
    same notice fail the run with bit 1."""
    home, repo = make_env(tmp_path)
    _quiet_subprocess(monkeypatch)

    def fake_check_pairs(pairs, repo_root, home_, label, notices=None, skipped=None):
        notices.append("scripts/run.sh trails origin/main")
        return []

    monkeypatch.setattr(lhf, "check_pairs", fake_check_pairs)
    assert lhf.main(_argv(tmp_path, home, repo, "--check", "--json")) == 0
    lenient = json.loads(capsys.readouterr().out)
    assert lenient["check_stale_checkout"] == ["scripts/run.sh trails origin/main"]
    assert lenient["check_breaches"] == []

    assert lhf.main(_argv(tmp_path, home, repo, "--check", "--json", "--strict-checkout")) == 1
    strict = json.loads(capsys.readouterr().out)
    assert strict["check_breaches"] == ["scripts/run.sh trails origin/main"]
    assert strict["check_stale_checkout"] == []


def test_strict_bak_is_exit_bit_8_and_default_is_advisory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    home, repo = make_env(tmp_path)
    (repo / "scripts/run.sh").write_text("same\n")
    (home / "scripts/run.sh").write_text("same\n")
    (home / "scripts/run.sh.bak").write_text("frozen fork\n")
    _quiet_subprocess(monkeypatch)

    assert lhf.main(_argv(tmp_path, home, repo, "--discover", "--json")) == 0
    advisory = json.loads(capsys.readouterr().out)
    assert len(advisory["discover_bak_shadows"]) == 1
    assert "run.sh.bak" in advisory["discover_bak_shadows"][0]

    assert lhf.main(_argv(tmp_path, home, repo, "--discover", "--strict-bak", "--json")) == 8
    capsys.readouterr()
    # INNOCENCE: --strict-bak with nothing to find stays green.
    (home / "scripts/run.sh.bak").unlink()
    assert lhf.main(_argv(tmp_path, home, repo, "--discover", "--strict-bak", "--json")) == 0
    assert json.loads(capsys.readouterr().out)["discover_bak_shadows"] == []


def test_system_flag_adds_the_system_launch_dirs_and_nothing_else_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, repo = make_env(tmp_path)
    _quiet_subprocess(monkeypatch)
    seen: list[dict] = []

    def spy_discover(plist_dirs, *a, **k):
        seen.append({"dirs": list(plist_dirs), "registries": k.get("json_registries")})
        return []

    def spy_bak(pairs, home_, label, errors, include_system=False):
        seen[-1]["bak_system"] = include_system
        return []

    monkeypatch.setattr(lhf, "discover_undeclared", spy_discover)
    monkeypatch.setattr(lhf, "discover_bak_shadows", spy_bak)

    lhf.main(_argv(tmp_path, home, repo, "--discover"))
    assert seen[-1]["dirs"] == [home / "Library/LaunchAgents"]
    assert seen[-1]["bak_system"] is False

    lhf.main(_argv(tmp_path, home, repo, "--discover", "--system"))
    assert seen[-1]["dirs"] == [
        home / "Library/LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
    ]
    assert seen[-1]["bak_system"] is True


def test_json_hook_registry_flag_replaces_the_default_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, repo = make_env(tmp_path)
    _quiet_subprocess(monkeypatch)
    seen: list = []
    monkeypatch.setattr(
        lhf, "discover_undeclared", lambda *a, **k: seen.append(k["json_registries"]) or []
    )
    full = _argv(tmp_path, home, repo, "--discover")
    at = full.index("--json-hook-registry")
    argv_no_reg = full[:at] + full[at + 2:]
    assert "--json-hook-registry" not in argv_no_reg
    lhf.main(argv_no_reg)
    assert seen[-1] == lhf.DEFAULT_JSON_HOOK_REGISTRIES
    lhf.main(_argv(tmp_path, home, repo, "--discover"))
    assert seen[-1] == [tmp_path / "absent-registry.json"]


def test_skipped_pair_listing_is_capped_at_ten_but_counts_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    home, repo = make_env(tmp_path)
    _quiet_subprocess(monkeypatch)
    pairs = [{"live": f"~/scripts/ghost{i}.sh", "repo": f"scripts/ghost{i}.sh"} for i in range(12)]
    cfg = _write_config(tmp_path, pairs)
    base = [
        "--config", str(cfg), "--home", str(home), "--repo-root", str(repo),
        "--plist-dir", str(home / "Library/LaunchAgents"), "--no-fetch", "--check",
    ]
    assert lhf.main(base) == 0  # a skipped pair never touches the exit code
    out = capsys.readouterr().out
    assert "12 pair(s) NOT checked" in out
    assert "showing 10 of 12" in out
    assert len([ln for ln in out.splitlines() if ln.startswith("    ? ")]) == 10
    # INNOCENCE: exactly 10 skipped lists all 10, not 9.
    cfg10 = _write_config(tmp_path, pairs[:10])
    assert lhf.main([*base[:1], str(cfg10), *base[2:]]) == 0
    out10 = capsys.readouterr().out
    assert "showing 10 of 10" in out10
    assert len([ln for ln in out10.splitlines() if ln.startswith("    ? ")]) == 10


def test_bak_shadow_summary_names_six_then_counts_the_rest(tmp_path: Path) -> None:
    home, _repo = make_env(tmp_path)
    (home / "scripts/run.sh").write_text("x\n")
    pairs = [{"live": "~/scripts/run.sh", "repo": "scripts/run.sh", "machines": ["all"]}]
    for i in range(6):
        (home / "scripts" / f"run.sh.bak{i}").write_text("b\n")
    errors: list[str] = []
    six = lhf.discover_bak_shadows(pairs, home, "pro", errors)
    assert errors == [] and len(six) == 1
    assert "6 .bak shadow(s)" in six[0] and "more)" not in six[0]
    (home / "scripts" / "run.sh.bak6").write_text("b\n")
    seven = lhf.discover_bak_shadows(pairs, home, "pro", errors)
    assert "7 .bak shadow(s)" in seven[0] and "(+1 more)" in seven[0]
    assert len(seven[0].split(" — ", 1)[1].split(": ", 1)[1].split(" (+")[0].split(", ")) == 6


def test_bak_scan_skips_malformed_live_entries_and_outside_home_without_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, _repo = make_env(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "stray.sh.bak").write_text("must not be scanned via an empty live path\n")
    monkeypatch.chdir(cwd)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "tool.sh").write_text("x\n")
    (outside / "tool.sh.bak").write_text("b\n")
    errors: list[str] = []
    malformed = [{"live": ""}, {"live": 5}, {"live": None}, {}]
    assert lhf.discover_bak_shadows(malformed, home, "pro", errors) == []
    assert errors == []
    # Outside HOME is vendor territory unless --system asks for it.
    pairs = [{"live": str(outside / "tool.sh"), "repo": "x", "machines": ["all"]}]
    assert lhf.discover_bak_shadows(pairs, home, "pro", errors) == []
    assert len(lhf.discover_bak_shadows(pairs, home, "pro", errors, include_system=True)) == 1


def test_allow_pattern_matches_the_expanded_form_as_well_as_the_literal(
    tmp_path: Path,
) -> None:
    home = tmp_path / "h"
    # literal norm vs absolute pattern: only the EXPANDED form can match
    assert lhf._is_allowed("~/tools/a.sh", home, [f"{home}/tools/*.sh"])
    # `$HOME` pattern vs literal `~/` norm: both sides expand to the same path
    assert lhf._is_allowed("~/tools/a.sh", home, ["$HOME/tools/*.sh"])
    # INNOCENCE: a pattern for another directory or an empty allow-list matches nothing
    assert not lhf._is_allowed("~/tools/a.sh", home, [f"{home}/other/*.sh"])
    assert not lhf._is_allowed("~/tools/a.sh", home, [])


def test_repo_root_hardening_resolves_a_worktree_to_the_main_checkout(
    tmp_path: Path,
) -> None:
    src = _MODULE_PATH.read_text()

    def load_from(path: Path):
        path.parent.mkdir(parents=True)
        path.write_text(src)
        spec = importlib.util.spec_from_file_location("lhf_probe_" + path.parent.parent.name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    main_root = (tmp_path / "main").resolve()
    in_worktree = load_from(main_root / ".worktrees" / "lane-x" / "scripts" / "lint_home_fork.py")
    assert in_worktree.REPO_ROOT == main_root  # never the ephemeral worktree itself
    plain = load_from((tmp_path / "plain").resolve() / "scripts" / "lint_home_fork.py")
    assert plain.REPO_ROOT == (tmp_path / "plain").resolve()  # INNOCENCE: untouched


def test_whole_path_arg_with_shell_metachars_is_split_not_glued(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    # one ProgramArguments entry that is a shell pipeline, starting with ~/
    _write_plist(agents, "com.test.pipe.plist", ["/bin/bash", "-c", "~/scripts/a.sh && ~/scripts/b.sh"])
    errors: list[str] = []
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], errors)
    assert errors == []
    joined = "\n".join(findings)
    assert "~/scripts/a.sh" in joined and "~/scripts/b.sh" in joined
    assert "a.sh && " not in joined  # never reported as one glued bogus path
    # INNOCENCE: a clean whole path containing a space stays ONE finding
    agents2 = tmp_path / "agents2"
    _write_plist(agents2, "com.test.space.plist", [f"{home}/Application Support/run job.sh"])
    spaced = lhf.discover_undeclared([agents2], "", home, repo, set(), [], [])
    assert len(spaced) == 1 and "~/Application Support/run job.sh" in spaced[0]


def test_embedded_data_paths_are_not_payloads_but_program_slot_always_is(
    tmp_path: Path,
) -> None:
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    # data read by a command inside a shell string: not executed code
    _write_plist(agents, "com.test.data.plist", ["/bin/bash", "-c", "cat ~/notes/todo.txt"])
    assert lhf.discover_undeclared([agents], "", home, repo, set(), [], []) == []
    # crontab: same rule for an embedded data argument ...
    cron = "0 * * * * /usr/bin/tail ~/logs/app.log"
    assert lhf.discover_undeclared([], cron, home, repo, set(), [], []) == []
    # ... and the executed script on the same kind of line IS found.
    cron2 = "0 * * * * ~/scripts/job.sh"
    assert len(lhf.discover_undeclared([], cron2, home, repo, set(), [], [])) == 1
    # The `Program` key is executed by construction: no extension, no exec bit needed.
    agents2 = tmp_path / "agents2"
    agents2.mkdir()
    (agents2 / "com.test.prog.plist").write_bytes(
        plistlib.dumps({"Label": "x", "Program": str(home / "bin" / "mytool")})
    )
    found = lhf.discover_undeclared([agents2], "", home, repo, set(), [], [])
    assert len(found) == 1 and "~/bin/mytool" in found[0]


def test_payload_candidate_fails_closed_when_the_filesystem_cannot_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "h"
    (home / "bin").mkdir(parents=True)
    tool = home / "bin" / "tool"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    assert lhf.is_payload_candidate("~/bin/tool", home) is True  # executable regular file

    def boom(*_a, **_k):
        raise OSError("EIO")

    monkeypatch.setattr(lhf.os, "access", boom)
    assert lhf.is_payload_candidate("~/bin/tool", home) is False


def test_fetch_origin_main_reports_each_failure_shape_without_claiming_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raises(exc):
        def _run(*_a, **_k):
            raise exc

        return _run

    monkeypatch.setattr(lhf.subprocess, "run", raises(subprocess.TimeoutExpired("git", 7)))
    assert lhf.fetch_origin_main(tmp_path, timeout=7) == (False, "timed out after 7s")
    monkeypatch.setattr(lhf.subprocess, "run", raises(FileNotFoundError()))
    assert lhf.fetch_origin_main(tmp_path) == (False, "FileNotFoundError")

    def returns(rc: int, err):
        return lambda *a, **k: subprocess.CompletedProcess(a, rc, b"", err)

    monkeypatch.setattr(lhf.subprocess, "run", returns(0, b""))
    assert lhf.fetch_origin_main(tmp_path) == (True, "ok")
    monkeypatch.setattr(lhf.subprocess, "run", returns(128, b"fatal: " + b"x" * 300))
    ok, detail = lhf.fetch_origin_main(tmp_path)
    assert ok is False and detail.startswith("fatal: ") and len(detail) == 120
    monkeypatch.setattr(lhf.subprocess, "run", returns(128, b""))
    assert lhf.fetch_origin_main(tmp_path) == (False, "rc=128")
    # str stderr (text-mode runner) is handled the same way
    monkeypatch.setattr(lhf.subprocess, "run", returns(1, "  boom  \n"))
    assert lhf.fetch_origin_main(tmp_path) == (False, "boom")


def test_proprioception_pairs_takes_only_the_home_fork_entry_and_well_formed_pairs(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    # no proprioception.py at all -> degraded to empty, never an error
    assert lhf.proprioception_pairs(repo) == []
    (repo / "scripts" / "proprioception.py").write_text(
        "DEFAULT_REGISTRY = [\n"
        "  {'id': 'something_else', 'machines': ['all'],\n"
        "   'args': {'pairs': [{'live': '~/no.sh', 'repo': 'no.sh'}]}},\n"
        "  {'id': 'home_fork_scripts', 'machines': ['pro'],\n"
        "   'args': {'pairs': [\n"
        "      {'live': '~/a.sh', 'repo': 'a.sh'},\n"
        "      {'live': '~/only-live.sh'},\n"
        "      {'repo': 'only-repo.sh'},\n"
        "   ]}},\n"
        "]\n"
    )
    assert lhf.proprioception_pairs(repo) == [
        {"live": "~/a.sh", "repo": "a.sh", "machines": ["pro"]}
    ]


def test_exit_code_legend_each_bit_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """1=diverged 2=undeclared 4=scan-error — each bit on its own, so a bit that
    drifted to another value cannot hide inside the combined-3 case."""
    home, repo = make_env(tmp_path)
    (repo / "scripts/run.sh").write_text("same\n")
    (home / "scripts/run.sh").write_text("same\n")
    agents = home / "Library/LaunchAgents"
    _write_plist(agents, "com.test.rogue.plist", [str(home / "scripts/rogue.sh")])
    _quiet_subprocess(monkeypatch)
    assert lhf.main(_argv(tmp_path, home, repo, "--discover", "--json")) == 2
    assert json.loads(capsys.readouterr().out)["exit"] == 2
    (home / "scripts/run.sh").write_text("diverged\n")
    assert lhf.main(_argv(tmp_path, home, repo, "--check", "--json")) == 1
    assert json.loads(capsys.readouterr().out)["exit"] == 1


def test_text_report_only_claims_clean_when_it_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    home, repo = make_env(tmp_path)
    (repo / "scripts/run.sh").write_text("same\n")
    (home / "scripts/run.sh").write_text("same\n")
    _quiet_subprocess(monkeypatch)
    assert lhf.main(_argv(tmp_path, home, repo)) == 0
    clean = capsys.readouterr().out
    assert "clean — every live copy matches its repo twin" in clean
    assert "clean — every HOME-executed payload is declared" in clean
    assert "HOME-FORK LINT FAIL" not in clean

    _write_plist(home / "Library/LaunchAgents", "com.test.rogue.plist", [str(home / "scripts/rogue.sh")])
    (home / "scripts/run.sh").write_text("diverged\n")
    assert lhf.main(_argv(tmp_path, home, repo)) == 3
    dirty = capsys.readouterr().out
    assert "clean — every live copy matches its repo twin" not in dirty
    assert "clean — every HOME-executed payload is declared" not in dirty
    assert "HOME-FORK LINT FAIL (exit 3:" in dirty


def test_a_stale_checkout_notice_is_not_reported_as_a_clean_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    home, repo = make_env(tmp_path)
    _quiet_subprocess(monkeypatch)
    monkeypatch.setattr(
        lhf, "check_pairs",
        lambda pairs, r, h, label, notices=None, skipped=None: notices.append("run.sh trails") or [],
    )
    assert lhf.main(_argv(tmp_path, home, repo, "--check")) == 0
    out = capsys.readouterr().out
    assert "  ~ run.sh trails" in out
    assert "no HOME-fork — but 1 pair(s) differ only because this checkout trails" in out
    assert "clean — every live copy matches" not in out


def test_unreadable_plist_dir_and_non_dict_plist_are_errors_not_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, repo = make_env(tmp_path)
    arr_dir = tmp_path / "arrdir"
    arr_dir.mkdir()
    (arr_dir / "list.plist").write_bytes(plistlib.dumps(["not", "a", "dict"]))
    errors: list[str] = []
    assert lhf.discover_undeclared([arr_dir], "", home, repo, set(), [], errors) == []
    assert errors == [f"plist root is not a dict: {arr_dir / 'list.plist'}"]

    def deny(self, pattern):  # noqa: ANN001
        raise PermissionError("denied")

    monkeypatch.setattr(lhf.Path, "glob", deny)
    errors2: list[str] = []
    assert lhf.discover_undeclared([arr_dir], "", home, repo, set(), [], errors2) == []
    assert errors2 == [f"plist-dir unreadable (PermissionError): {arr_dir}"]


def test_the_same_payload_named_twice_by_one_job_is_one_finding(tmp_path: Path) -> None:
    home, repo = make_env(tmp_path)
    agents = home / "Library/LaunchAgents"
    rogue = str(home / "scripts/rogue.sh")
    _write_plist(agents, "com.test.twice.plist", [rogue, "--flag", rogue])
    findings = lhf.discover_undeclared([agents], "", home, repo, set(), [], [])
    assert len(findings) == 1
