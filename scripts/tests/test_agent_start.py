"""SOTA L1 (2026-05-24) — tests for scripts/agent_start.py (Worktree Broker).

Coverage matrix:
- create worktree happy path (branch + metadata + symlinks + stdout contract)
- list shows entries with WIP detection
- cleanup skips worktree with uncommitted WIP and emits WARN
- cleanup removes worktree past TTL when clean
- release fails gracefully when branch is not merged into base
- release succeeds when branch is merged
- kill-switch (AGENT_BROKER_ENABLED=false) blocks create/cleanup/release but not list
- input validation rejects malformed lane / task-id

Tests use a temporary git repo + temporary HOME via monkeypatch, so they never
touch the real ~/nuzantara checkout or ~/logs/.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "agent_start.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_module(repo_root: Path):
    """Reload agent_start under a fresh REPO_ROOT (overrides module constants)."""
    spec = importlib.util.spec_from_file_location("agent_start_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec_module so dataclass __module__ lookups succeed
    # (the @dataclass decorator does sys.modules[cls.__module__] in 3.11).
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = repo_root
    mod.WORKTREES_DIR = repo_root / ".worktrees"
    return mod


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect HOME so log handler init writes inside tmp."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_BROKER_ENABLED", raising=False)
    # RAM admission gate (2026-08-13) reads the REAL machine's swap/load by
    # default — and the dev machine this suite runs on is routinely the exact
    # memory-distressed state the gate exists to catch. Every pre-existing
    # cmd_create() test call in this file is about worktree/branch mechanics,
    # not the admission gate, so it must not be at the mercy of live machine
    # state. Bypass here; the gate's own tests (below) explicitly clear this
    # and inject sampler values instead of reading the real machine.
    monkeypatch.setenv("AGENT_RAM_ADMISSION_OVERRIDE", "1")
    return home


@pytest.fixture
def fake_repo(tmp_path, fake_home, monkeypatch):
    """Create a fresh git repo with a main branch + 1 commit, return module + path."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # git init + commit (need identity for the commit to work).
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"

    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    git("init", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n")
    git("add", "README.md")
    git("commit", "-m", "seed")

    # Model production reality: an `origin` remote with `main` pushed. The W80
    # reap-guard (`_branch_in_origin_main`) tests HEAD against `origin/main`, so
    # a fixture without a remote would make EVERY worktree read as "unmerged" —
    # masking real behaviour. A bare origin + pushed main is the minimal honest
    # model (a branch with no commits beyond what's pushed is an ancestor of
    # origin/main → reap-eligible; a branch with un-pushed commits → protected).
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    git("remote", "add", "origin", str(origin))
    git("push", "-u", "origin", "main")

    mod = _load_module(repo)
    # Patch the module's subprocess git wrapper cwd default to point at our repo.
    return mod, repo


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_happy_path_writes_metadata_and_branch(fake_repo):
    mod, repo = fake_repo
    out = mod.cmd_create("wr2", "happy-001", ttl_minutes=30)
    assert out.is_dir()
    assert out == repo / ".worktrees" / "wr2-happy-001"

    meta_path = out / mod.TASK_METADATA_FILENAME
    assert meta_path.is_file()
    data = json.loads(meta_path.read_text())
    assert data["task_id"] == "happy-001"
    assert data["lane"] == "wr2"
    assert data["branch"].endswith("/wr2/happy-001")
    assert data["branch"].startswith("agent/")
    assert data["ttl_minutes"] == 30
    assert data["base_branch"] == "main"

    # Branch exists.
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert data["branch"] in branches


def test_create_symlinks_only_when_targets_exist(fake_repo):
    mod, repo = fake_repo
    # Create one of the SYMLINK_TARGETS in main so the symlink is exercised.
    (repo / "apps" / "backend-rag").mkdir(parents=True)
    (repo / "apps" / "backend-rag" / ".env").write_text("FAKE=1\n")
    out = mod.cmd_create("infra", "sym-test")
    link = out / "apps" / "backend-rag" / ".env"
    assert link.is_symlink()
    # Resolves back to source.
    assert link.resolve() == (repo / "apps" / "backend-rag" / ".env").resolve()
    # Non-existent target (node_modules) is silently skipped (no broken link).
    assert not (out / "node_modules").exists()


def test_node_modules_symlink_not_counted_as_wip(fake_repo):
    """node_modules is a SYMLINK_TARGETS entry; .gitignore's `node_modules/`
    (directory-only pattern) does not match a symlink-to-a-directory, so the
    broker's own symlink read as `?? node_modules` (untracked) in every
    worktree — permanently tripping the WIP guard. Regression for a bug found
    live: 3 worktrees sat 5-14h past a 60min TTL because `--cleanup` always
    saw "WIP" and WARN-skipped (exit 0, never loud) every single run.
    """
    mod, repo = fake_repo
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "placeholder.txt").write_text("x\n")
    (repo / ".gitignore").write_text("node_modules/\n")
    _commit_in_worktree(repo, mod, ".gitignore", "add gitignore")
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("wr2", "nm-innocent", ttl_minutes=5)
    assert (wt / "node_modules").is_symlink()
    assert mod._worktree_has_wip(wt) is False


def test_node_modules_symlink_does_not_mask_real_wip(fake_repo):
    """Guilt case: the node_modules exemption must not swallow genuine WIP."""
    mod, repo = fake_repo
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "placeholder.txt").write_text("x\n")
    (repo / ".gitignore").write_text("node_modules/\n")
    _commit_in_worktree(repo, mod, ".gitignore", "add gitignore")
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("wr2", "nm-guilty", ttl_minutes=5)
    (wt / "real_work.py").write_text("# uncommitted\n")
    assert mod._worktree_has_wip(wt) is True


def _seed_mouth_workspace(repo, mod):
    """Give the fake repo a TRACKED file under apps/mouth, then the nested
    node_modules dir in main.

    The tracked file is not decoration — it is what makes the fixture
    representative, and leaving it out makes every assertion below vacuous.
    `git status --porcelain` COLLAPSES untracked directories to their shallowest
    untracked ancestor: with nothing tracked under apps/, git reports `?? apps/`
    and never `?? apps/mouth/node_modules`, so the BROKER_GENERATED_FILES entry
    can neither help (innocence fails) nor be needed (guilt passes for the wrong
    reason — `?? apps/` trips WIP no matter what the exemption says). Measured
    both worlds side by side on 2026-08-07 before writing this. The real repo
    tracks apps/mouth/src/**, so it is always the rich world.
    """
    (repo / "apps" / "mouth" / "src").mkdir(parents=True, exist_ok=True)
    (repo / "apps" / "mouth" / "src" / "page.tsx").write_text("export {}\n")
    (repo / ".gitignore").write_text("node_modules/\n")
    _commit_in_worktree(repo, mod, ".", "seed mouth workspace")
    subprocess.run(
        ["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True
    )
    nm = repo / "apps" / "mouth" / "node_modules"
    nm.mkdir(parents=True, exist_ok=True)
    (nm / "placeholder.txt").write_text("x\n")
    return nm


def test_mouth_node_modules_is_symlinked_into_worktree(fake_repo):
    """This is an npm WORKSPACE monorepo: a workspace package's own deps are
    installed NESTED (`apps/mouth/node_modules/<pkg>`), not hoisted to the root.
    Node resolves upward from the importing file, so symlinking ONLY the root
    node_modules leaves `recharts` unresolvable and `npm run typecheck` — the
    command the pre-commit hook runs on any staged apps/mouth TS/TSX — dies with
    TS2307. Measured 2026-08-07: 5 of 37 live worktrees had this directory, each
    because someone ran the install by hand.
    """
    mod, repo = fake_repo
    nm = _seed_mouth_workspace(repo, mod)

    wt = mod.cmd_create("mouth", "mouth-nm-link", ttl_minutes=5)
    link = wt / "apps" / "mouth" / "node_modules"
    assert link.is_symlink()
    assert link.resolve() == nm.resolve()


def test_mouth_node_modules_symlink_not_counted_as_wip(fake_repo):
    """Innocence, and it reproduces the MINI condition on purpose.

    On M5 and Pro this symlink reads as ignored only because a BARE
    `node_modules` line sits in their `.git/info/exclude` — a local, untracked,
    per-machine file. Mini has no such line (measured 2026-08-07: 0 matches),
    and the repo's own .gitignore carries only the directory-only
    `node_modules/`, which does not match a symlink-to-a-directory. This fake
    repo has no local exclude either, so it stands in for Mini: without the
    BROKER_GENERATED_FILES entry the worktree would read `?? apps/mouth/
    node_modules` forever and `--cleanup` would WARN-skip it on every run.
    """
    mod, repo = fake_repo
    _seed_mouth_workspace(repo, mod)

    wt = mod.cmd_create("mouth", "mouth-nm-innocent", ttl_minutes=5)
    assert (wt / "apps" / "mouth" / "node_modules").is_symlink()
    # Premise check: git must actually be reporting the FULL path here, not a
    # collapsed `?? apps/`. Without this the assertion below could pass in a
    # world where the exemption is never consulted.
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=wt, capture_output=True, text=True
    ).stdout
    assert "apps/mouth/node_modules" in porcelain or porcelain.strip() == "", porcelain
    assert mod._worktree_has_wip(wt) is False


def test_mouth_node_modules_exemption_does_not_mask_real_wip(fake_repo):
    """Guilt: the new exemption must not swallow genuine WIP — including WIP
    that lives INSIDE apps/mouth, next to the exempted path rather than at the
    repo root, which is where a too-broad prefix match would go wrong."""
    mod, repo = fake_repo
    _seed_mouth_workspace(repo, mod)

    wt = mod.cmd_create("mouth", "mouth-nm-guilty", ttl_minutes=5)
    (wt / "apps" / "mouth" / "src" / "real_work.tsx").write_text("// uncommitted\n")
    assert mod._worktree_has_wip(wt) is True


def test_husky_shim_dir_symlinked_into_worktree(fake_repo):
    """`.husky/_` must reach every worktree or the pre-push gate is OFF there.

    `core.hooksPath` is the RELATIVE path `.husky/_`, resolved by git against
    each working tree. `_` is husky's generated shim dir — `npm install` makes
    it in the main checkout and `git worktree add` never carries it over. A
    worktree without it resolves hooksPath to nothing, so every push from it
    skips pre-push entirely: no banner, no suite, exit 0. Measured 2026-07-16:
    three probe pushes from two worktrees ran no gate; symlinking the dir in
    made the same push run the full suite.
    """
    mod, repo = fake_repo
    (repo / ".husky" / "_").mkdir(parents=True)
    (repo / ".husky" / "_" / "pre-push").write_text("#!/bin/sh\n")

    wt = mod.cmd_create("infra", "husky-shim")
    link = wt / ".husky" / "_"
    assert link.is_symlink(), "worktree has no .husky/_ — its pushes would be ungated"
    assert link.resolve() == (repo / ".husky" / "_").resolve()
    assert (wt / ".husky" / "_" / "pre-push").exists()


def test_husky_shim_symlink_not_counted_as_wip(fake_repo):
    """Innocence: the broker's own shim symlink is not user WIP.

    Same trap the node_modules note describes — `.husky/.gitignore` does not
    cover `_`, so without the BROKER_GENERATED_FILES entry this symlink would
    read as `?? .husky/_` in every worktree and make `--cleanup` a no-op
    forever. Curing the gate must not re-open the reaper bug.
    """
    mod, repo = fake_repo
    (repo / ".husky" / "_").mkdir(parents=True)
    (repo / ".husky" / "_" / "pre-push").write_text("#!/bin/sh\n")
    # A tracked file inside .husky/ is what the real repo has (pre-commit,
    # pre-push, post-commit are all committed). Without one git collapses the
    # whole untracked dir to `?? .husky/` and this test would pass or fail for
    # a reason that cannot happen in production.
    (repo / ".husky" / "pre-push").write_text("#!/bin/sh\necho gate\n")
    _commit_in_worktree(repo, mod, ".husky/pre-push", "add tracked hook")
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("infra", "husky-innocent", ttl_minutes=5)
    assert (wt / ".husky" / "_").is_symlink()
    # Pin the exact porcelain shape the exemption keys on: a symlink-to-a-dir
    # is reported WITHOUT a trailing slash (a real dir would be `.husky/_/`).
    porcelain = mod._run_git(["status", "--porcelain"], cwd=wt, check=False).stdout
    assert "?? .husky/_\n" in porcelain, porcelain
    assert mod._worktree_has_wip(wt) is False


def test_husky_exemption_does_not_swallow_real_work_in_husky_dir(fake_repo):
    """Guilt: the exemption is scoped to `_`, not to `.husky/` as a whole.

    An edit to a tracked hook (`.husky/pre-push` — a real file people change,
    and the subject of today's clone-owner fix) must still count as WIP.
    """
    mod, repo = fake_repo
    (repo / ".husky" / "_").mkdir(parents=True)
    (repo / ".husky" / "_" / "pre-push").write_text("#!/bin/sh\n")
    (repo / ".husky" / "pre-push").write_text("#!/bin/sh\necho gate\n")
    _commit_in_worktree(repo, mod, ".husky/pre-push", "add tracked hook")
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("infra", "husky-guilty", ttl_minutes=5)
    assert (wt / ".husky" / "_").is_symlink()
    (wt / ".husky" / "pre-push").write_text("#!/bin/sh\necho edited\n")
    assert mod._worktree_has_wip(wt) is True


def test_cleanup_reaps_expired_worktree_with_only_node_modules_symlink(fake_repo, capsys):
    """Integration-level: --cleanup must actually reap a TTL-expired worktree
    whose only 'dirty' porcelain entry is the broker's own node_modules
    symlink — this is the exact class that silently accumulated orphans."""
    mod, repo = fake_repo
    (repo / "node_modules").mkdir()
    (repo / ".gitignore").write_text("node_modules/\n")
    _commit_in_worktree(repo, mod, ".gitignore", "add gitignore")
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("wr2", "nm-cleanup", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    _backdate_worktree_mtime(wt, minutes=120)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert not wt.exists()
    out = capsys.readouterr().out
    assert "nm-cleanup" in out


def test_create_rejects_unknown_lane_by_default(fake_repo):
    mod, _ = fake_repo
    with pytest.raises(SystemExit) as exc:
        mod.cmd_create("notreal", "x")
    assert "unknown lane" in str(exc.value).lower()


def test_create_allows_unknown_lane_when_flagged(fake_repo):
    mod, _ = fake_repo
    out = mod.cmd_create("notreal", "x", allow_unknown_lane=True)
    assert out.is_dir()


def test_create_rejects_invalid_chars_in_task_id(fake_repo):
    mod, _ = fake_repo
    with pytest.raises(SystemExit):
        mod.cmd_create("wr2", "BAD/SLASH")
    with pytest.raises(SystemExit):
        mod.cmd_create("wr2", "_underscore")
    with pytest.raises(SystemExit):
        mod.cmd_create("wr2", "")


def test_create_refuses_duplicate_task_id(fake_repo):
    mod, _ = fake_repo
    mod.cmd_create("wr2", "dup-001")
    with pytest.raises(SystemExit) as exc:
        mod.cmd_create("wr2", "dup-001")
    assert "already exists" in str(exc.value).lower()


def test_create_blocked_by_kill_switch(fake_repo, monkeypatch):
    mod, _ = fake_repo
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "false")
    with pytest.raises(SystemExit) as exc:
        mod.cmd_create("wr2", "killed")
    assert "disabled" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# RAM admission gate (2026-08-13) — check_ram_admission() + its cmd_create hook
#
# The samplers are INJECTED via monkeypatch, never reading the real machine:
# the real machine's swap/load changes under our feet (it is, right now, the
# exact crisis this gate targets) and a test that reads it live would be
# flaky by construction. `fake_home` sets AGENT_RAM_ADMISSION_OVERRIDE=1 for
# every other test in this file; each test below explicitly clears it.
# ---------------------------------------------------------------------------


def _clear_ram_override(monkeypatch):
    monkeypatch.delenv("AGENT_RAM_ADMISSION_OVERRIDE", raising=False)


def test_ram_admission_refuses_when_swap_and_load_both_over_threshold(fake_repo, monkeypatch):
    """Guilt: the tonight-on-M5 shape — swap and load both far over threshold."""
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (10801.0, 11264.0))  # 95.9%
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (157.0, 10))  # 15.7x/core

    admit, reason = mod.check_ram_admission()
    assert admit is False
    assert "REFUSED" in reason
    assert "95.9" in reason
    assert "15.7" in reason


def test_ram_admission_admits_when_both_normal(fake_repo, monkeypatch):
    """Innocence: an ordinary-load machine (Pro-shaped: high swap floor, low
    load ratio) is admitted."""
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (500.0, 11264.0))  # 4.4%
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (2.0, 10))  # 0.2x/core

    admit, reason = mod.check_ram_admission()
    assert admit is True
    assert "OK" in reason


def test_ram_admission_swap_alone_over_threshold_still_admits(fake_repo, monkeypatch):
    """Innocence, AND not OR: measured live 2026-08-13 that Mini sits at ~94%
    swap while genuinely calm (load ~0.3x/core) — swap alone must never
    refuse, or every calm machine on this fleet would be rejected forever."""
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (10800.0, 11264.0))  # 95.9%
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (3.0, 10))  # 0.3x/core, calm

    admit, _reason = mod.check_ram_admission()
    assert admit is True


def test_ram_admission_load_alone_over_threshold_still_admits(fake_repo, monkeypatch):
    """Innocence, AND not OR, other side: high load with normal swap (e.g. a
    genuine CPU-bound burst with headroom in RAM) must not refuse either."""
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (500.0, 11264.0))  # 4.4%
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (60.0, 10))  # 6x/core

    admit, _reason = mod.check_ram_admission()
    assert admit is True


def test_ram_admission_fails_open_when_swap_sampler_raises(fake_repo, monkeypatch, caplog):
    """Guilt-of-the-gate/innocence-of-the-lane: an exception from the sampler
    (not just a returned None) must not crash cmd_create — it degrades to
    fail-open, and the degradation is logged."""
    import logging

    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)

    def _boom():
        raise RuntimeError("simulated sysctl explosion")

    monkeypatch.setattr(mod, "_sample_swap_usage", _boom)
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (500.0, 10))  # would refuse if reached

    with caplog.at_level(logging.WARNING, logger="agent_broker"):
        admit, reason = mod.check_ram_admission()
    assert admit is True
    assert "could not measure" in reason.lower()
    assert any("swap sampler raised" in r.message for r in caplog.records)


def test_ram_admission_fails_open_when_sampler_returns_none(fake_repo, monkeypatch):
    """The anticipated failure path (sysctl absent / bad output) also fails
    open, distinct from the exception path above."""
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: None)
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (500.0, 10))

    admit, reason = mod.check_ram_admission()
    assert admit is True
    assert "could not measure" in reason.lower()


def test_ram_admission_override_bypasses_even_when_distressed(fake_repo, monkeypatch):
    mod, _ = fake_repo
    monkeypatch.setenv("AGENT_RAM_ADMISSION_OVERRIDE", "1")
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (10801.0, 11264.0))
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (157.0, 10))

    admit, reason = mod.check_ram_admission()
    assert admit is True
    assert "bypassed" in reason.lower()


def test_ram_admission_thresholds_configurable_via_env(fake_repo, monkeypatch):
    """A caller can tighten or loosen the bar without touching code."""
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)
    # These values would PASS under the built-in defaults (swap 91% < ordinary
    # would need >=90 AND load must be >=5x — here load is only 1x) but a
    # tightened load threshold of 0.5x/core must catch it.
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (10250.0, 11264.0))  # 91.0%
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (10.0, 10))  # 1.0x/core
    monkeypatch.setenv("AGENT_RAM_ADMISSION_LOAD_RATIO_MAX", "0.5")

    admit, _reason = mod.check_ram_admission()
    assert admit is False


def test_ram_admission_malformed_threshold_env_falls_back_to_default(fake_repo, monkeypatch):
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (500.0, 11264.0))
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (2.0, 10))
    monkeypatch.setenv("AGENT_RAM_ADMISSION_SWAP_PCT_MAX", "not-a-number")

    # Must not raise; falls back to default and admits (values are calm).
    admit, _reason = mod.check_ram_admission()
    assert admit is True


def test_cmd_create_refused_by_ram_gate_raises_dedicated_exit_code(fake_repo, monkeypatch):
    """Integration: cmd_create itself raises SystemExit(RAM_ADMISSION_EXIT_CODE)
    — a distinct code from the generic exit-1 every other validation error in
    this file uses — and never reaches git/worktree creation."""
    mod, repo = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (10801.0, 11264.0))
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (157.0, 10))

    with pytest.raises(SystemExit) as exc:
        mod.cmd_create("wr2", "ram-refused")
    assert exc.value.code == mod.RAM_ADMISSION_EXIT_CODE
    assert not (repo / ".worktrees" / "wr2-ram-refused").exists()


def test_cmd_create_succeeds_when_ram_gate_admits(fake_repo, monkeypatch):
    """Integration innocence twin: a healthy-machine sample lets create proceed
    exactly as before this gate existed."""
    mod, repo = fake_repo
    _clear_ram_override(monkeypatch)
    monkeypatch.setattr(mod, "_sample_swap_usage", lambda: (500.0, 11264.0))
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (2.0, 10))

    out = mod.cmd_create("wr2", "ram-admitted")
    assert out.is_dir()
    assert out == repo / ".worktrees" / "wr2-ram-admitted"


def test_ram_admission_locale_comma_decimal_is_parsed_via_lc_all_c(fake_repo, monkeypatch):
    """Regression for the locale gotcha found writing this gate: under
    it_IT.UTF-8, `sysctl vm.swapusage` renders decimals with a COMMA
    ("used = 10858,38M"). `_sample_swap_usage` forces LC_ALL=C on the
    subprocess so the output is always period-decimal regardless of the
    caller's session locale — this proves it empirically against the REAL
    sysctl binary (only this one test touches the real machine; it asserts
    the PARSE succeeds and shape is sane, not any specific value).

    Guarded on the measured CAPABILITY, not on a proxy for it. Two proxies
    were tried and both lie. `shutil.which("sysctl") is None` lies because
    Linux ships a `sysctl` (procps) with no `vm.swapusage` key — on
    ubuntu-latest the guard let the test through, the probe returned rc=1, and
    it failed on `assert None is not None`. `sys.platform != "darwin"` lies the
    other way: it skips correctly on a runner but still runs on a Mac whose
    sysctl is unreachable for any other reason.

    So the guard asks the question the test actually depends on — "can this
    host produce vm.swapusage output at all?" — by running the raw command
    itself. That is NOT circular with the assertion below: the guard checks the
    command SUCCEEDS, the assertion checks our PARSE of its output succeeds,
    and the comma-locale regression lives exactly in the gap between the two.

    DECLARED consequence: this case never runs in CI; it can only be proved on
    a real Mac. What a runner must still cover is the other side — that a host
    which cannot read anything degrades to fail-open instead of blocking every
    lane — and that is the test immediately below."""
    mod, _ = fake_repo
    try:
        raw = subprocess.run(
            ["sysctl", "vm.swapusage"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"host cannot run `sysctl vm.swapusage` ({exc})")
    if raw.returncode != 0 or not raw.stdout.strip():
        pytest.skip(
            "host has no vm.swapusage reading to parse "
            f"(rc={raw.returncode}) — Darwin-only key"
        )

    sample = mod._sample_swap_usage()
    assert sample is not None
    used_mb, total_mb = sample
    assert 0.0 <= used_mb <= total_mb
    assert total_mb > 0.0


def test_ram_admission_fails_open_against_the_real_probe_on_this_host(fake_repo, monkeypatch):
    """The case that actually runs on a Linux runner, against the REAL probe.

    The sibling tests above prove fail-open with the sampler mocked. This one
    does not mock it: it calls `_sample_swap_usage()` for real and asserts that
    whatever this host answers — a reading on a Mac, None on a runner where
    `sysctl` exists but has no `vm.swapusage` — a lane is still admitted.

    A monitoring probe that cannot measure must never become a reason work
    stops (family #2), and that is exactly what a platform-specific probe is
    most likely to do on a platform nobody tested it on."""
    mod, _ = fake_repo
    _clear_ram_override(monkeypatch)

    if mod._sample_swap_usage() is not None:
        # A Mac: the probe CAN read, so this test's subject does not exist
        # here and the mocked siblings above already cover the logic. Do NOT
        # try to force the case by mocking load high — real swap on these
        # machines runs hot (Pro 84%, Mini 93% while both were calm), so an
        # assertion of "admit" would then be a coin toss on the machine's
        # pressure at that instant, i.e. a flake dressed as a guard.
        pytest.skip("this host can read swap — the blind-probe path is unreachable here")

    # A runner where `sysctl` exists but has no vm.swapusage. Load is mocked
    # to a value that WOULD refuse if the blind swap reading were mistakenly
    # treated as distress, so passing here cannot come from a calm load
    # short-circuiting the AND.
    monkeypatch.setattr(mod, "_sample_load_ratio", lambda: (500.0, 10))

    admit, reason = mod.check_ram_admission()
    assert admit is True, (
        f"a probe that cannot measure must not block admission, got: {reason}"
    )
    assert "could not measure" in reason.lower(), (
        "and it must SAY it could not measure, not imply the machine was healthy"
    )

    out = mod.cmd_create("wr2", "real-probe-fail-open", ttl_minutes=5)
    assert out.is_dir()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_empty(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "no active worktrees" in out.lower()


def test_list_shows_created_entries(fake_repo, capsys):
    mod, _ = fake_repo
    mod.cmd_create("wr2", "list-001")
    mod.cmd_create("infra", "list-002")
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "list-001" in out
    assert "list-002" in out
    assert "wr2" in out
    assert "infra" in out
    # Fresh worktree has only the metadata file (filtered) → WIP=no.
    assert "no" in out


def test_list_flags_wip(fake_repo, capsys):
    mod, _ = fake_repo
    out = mod.cmd_create("wr2", "wip-001")
    (out / "dirty.txt").write_text("uncommitted\n")
    mod.cmd_list()
    captured = capsys.readouterr().out
    assert "wip-001" in captured
    assert "yes" in captured  # WIP column


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


def _backdate_metadata(worktree: Path, mod, minutes: int) -> None:
    """Rewrite created_at to push the worktree past TTL."""
    meta_path = worktree / mod.TASK_METADATA_FILENAME
    data = json.loads(meta_path.read_text())
    backdated = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    data["created_at"] = backdated.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta_path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _commit_in_worktree(worktree: Path, mod, rel_path: str, msg: str) -> None:
    """Stage + commit a file inside the worktree so it reads as CLEAN."""
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    for args in (["add", rel_path], ["commit", "-m", msg]):
        subprocess.run(
            ["git", *args],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )


def _backdate_worktree_mtime(worktree: Path, minutes: int) -> None:
    """Push every file's mtime back so the worktree reads as idle (no recent
    activity). Covers both the worktree tree AND the linked-worktree gitdir
    (REPO_ROOT/.git/worktrees/<name>/index|HEAD), since the liveness probe
    inspects the real gitdir too."""
    past = time.time() - minutes * 60

    def _back(p: Path) -> None:
        try:
            os.utime(p, (past, past))
        except OSError:
            pass

    for path in worktree.rglob("*"):
        _back(path)
    _back(worktree)
    # Linked-worktree real gitdir (resolve `.git` file pointer).
    git_pointer = worktree / ".git"
    try:
        if git_pointer.is_file():
            text = git_pointer.read_text().strip()
            if text.startswith("gitdir:"):
                gitdir = Path(text.split(":", 1)[1].strip())
                for name in ("index", "HEAD"):
                    _back(gitdir / name)
                _back(gitdir)
        _back(git_pointer)
    except OSError:
        pass


def _merge_worktree_branch_to_origin_main(worktree: Path, mod) -> None:
    """Fast-forward origin/main to the worktree's branch tip so the W80 guard
    (`_branch_in_origin_main`) sees HEAD as an ancestor of origin/main — i.e.
    the work is consolidated upstream and the worktree is genuinely reapable.

    Done from the MAIN repo (REPO_ROOT) to avoid touching the linked worktree's
    checked-out branch: update local main to the branch commit, then push."""
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    # The worktree's HEAD commit.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=worktree,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    repo = mod.REPO_ROOT
    # Move local main to the branch tip (main is checked out in the main repo,
    # but `branch -f` on the *currently checked-out* branch is refused; main is
    # NOT checked out here because the test repo's working copy stays on main —
    # so update via update-ref which bypasses the checkout guard, then push).
    subprocess.run(
        ["git", "update-ref", "refs/heads/main", head],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cleanup_removes_expired_clean_worktree(fake_repo, capsys):
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "expired-001", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    _backdate_worktree_mtime(wt, minutes=120)  # idle, not a live session
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert not wt.exists()
    out = capsys.readouterr().out
    assert "expired-001" in out


def test_cleanup_skips_wip_with_warning(fake_repo, capsys):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "wip-keep", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "wip.txt").write_text("not committed\n")
    _backdate_worktree_mtime(wt, minutes=120)  # idle clock, but real WIP present
    rc = mod.cmd_cleanup()
    assert rc == 1  # signals at least one skip
    assert wt.exists()  # WIP-safe
    out = capsys.readouterr().out
    assert "wip-keep" in out
    assert "WIP" in out or "wip" in out.lower()


def test_cleanup_force_removes_wip(fake_repo):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "wip-force", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "wip.txt").write_text("not committed\n")
    rc = mod.cmd_cleanup(force=True)
    assert rc == 0
    assert not wt.exists()


def test_cleanup_leaves_fresh_worktrees_alone(fake_repo):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "fresh-001", ttl_minutes=60)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert wt.exists()


# ---------------------------------------------------------------------------
# cleanup — skip-recent guard (W62 ANTIBODY #1)
# ---------------------------------------------------------------------------


def test_cleanup_skips_recently_active_expired_clean_worktree(fake_repo, capsys):
    """A clean, TTL-expired worktree that was touched <10min ago is an ACTIVE
    session — cleanup must NOT drop it (W62: avoid killing a live session that
    simply outran its TTL clock)."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "active-001", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)  # expired by the clock
    # Simulate live activity: a freshly written tracked file (recent mtime),
    # but committed so the worktree is CLEAN (no WIP).
    work_file = wt / "live.txt"
    work_file.write_text("active session output\n")
    _commit_in_worktree(wt, mod, "live.txt", "active work")
    rc = mod.cmd_cleanup()
    assert rc == 0  # not an error — just skipped a live session
    assert wt.exists()  # preserved because recently active
    out = capsys.readouterr().out
    assert "active-001" in out
    assert "recent" in out.lower() or "active" in out.lower()


def test_cleanup_removes_expired_clean_idle_worktree(fake_repo):
    """An expired, clean worktree with NO recent activity (mtime old) is a true
    orphan — cleanup removes it."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "idle-001", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    _backdate_worktree_mtime(wt, minutes=120)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert not wt.exists()


def test_cleanup_recent_AND_dirty_reports_wip_not_silent_skip(fake_repo, capsys):
    """A worktree that is BOTH recently active AND dirty must surface as a WIP
    failure (exit 1), never be silently swallowed as a live session (codex P2:
    WIP guard runs before the recent-activity guard)."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "recent-dirty", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)  # expired
    (wt / "uncommitted.txt").write_text("real WIP\n")  # dirty + fresh mtime
    rc = mod.cmd_cleanup()
    assert rc == 1  # WIP failure, NOT a silent exit-0 skip
    assert wt.exists()
    out = capsys.readouterr().out
    assert "recent-dirty" in out
    assert "WIP" in out


def test_cleanup_skip_recent_disabled_with_zero(fake_repo):
    """skip_recent_minutes=0 disables the recent-activity guard (operator
    escape for a forced sweep of even just-touched worktrees).

    The branch must be merged into origin/main for the W80 guard to allow the
    reap — so we land its commit on main upstream first. (skip_recent=0
    disables only the recent-activity guard; the W80 unmerged-protection is
    independent and still binds.)"""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "recent-002", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "fresh.txt").write_text("just now\n")
    _commit_in_worktree(wt, mod, "fresh.txt", "fresh")
    _merge_worktree_branch_to_origin_main(wt, mod)  # consolidate upstream
    rc = mod.cmd_cleanup(skip_recent_minutes=0)
    assert rc == 0
    assert not wt.exists()


# ---------------------------------------------------------------------------
# cleanup — W80 2-AND guard (no-live-process AND merged-into-origin/main)
# ---------------------------------------------------------------------------


def test_cleanup_skips_worktree_with_live_process(fake_repo, capsys, monkeypatch):
    """W80 case (1): an expired, CLEAN, mtime-IDLE worktree that still has a live
    OS process anchored to it (a session that commits-and-reasons without
    touching files) must NOT be reaped. The mtime-based recent-activity guard
    misses it (files are old); the lsof-based live-process guard catches it."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "live-proc", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    # Merge upstream so guard #2 (merged) would PASS — isolating that it's the
    # live-process guard #1 (not the unmerged guard) that protects it.
    _merge_worktree_branch_to_origin_main(wt, mod)
    _backdate_worktree_mtime(wt, minutes=120)  # mtime idle: recent-guard won't fire
    monkeypatch.setattr(mod, "_worktree_has_live_process", lambda p: True)
    rc = mod.cmd_cleanup()
    assert rc == 0  # protection, not a failure
    assert wt.exists()
    out = capsys.readouterr().out
    assert "live-proc" in out
    assert "live process" in out.lower()


def test_cleanup_skips_branch_not_in_origin_main(fake_repo, capsys, monkeypatch):
    """W80 case (2) — THE BUG: an expired, CLEAN, idle, no-live-process worktree
    whose branch has commits NOT in origin/main (pushed-but-not-merged, open PR)
    must NOT be reaped — it carries the only checkout of unmerged work.

    This is the real scenario that vanished the W79 worktree: commit-everything
    to satisfy stop_verify → clean+idle → reap-eligible by the OLD logic, but
    the branch was never merged."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "unmerged", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    # Real commit that is NOT pushed to origin/main → genuinely unmerged.
    (wt / "work.txt").write_text("unmerged work\n")
    _commit_in_worktree(wt, mod, "work.txt", "feature commit")
    _backdate_worktree_mtime(wt, minutes=120)  # idle on mtime
    monkeypatch.setattr(mod, "_worktree_has_live_process", lambda p: False)
    rc = mod.cmd_cleanup()
    assert rc == 0  # protection, not a failure (operator decides via PR merge)
    assert wt.exists()
    out = capsys.readouterr().out
    assert "unmerged" in out
    assert "origin/main" in out


def test_cleanup_reaps_when_no_process_and_merged(fake_repo, monkeypatch):
    """W80 case (3): the ONLY auto-reapable state — expired + clean + idle +
    NO live process AND branch merged into origin/main. Both W80 guards pass,
    so the worktree is removed."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "reapable", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "done.txt").write_text("shipped work\n")
    _commit_in_worktree(wt, mod, "done.txt", "shipped")
    _merge_worktree_branch_to_origin_main(wt, mod)  # consolidated upstream
    _backdate_worktree_mtime(wt, minutes=120)  # idle
    monkeypatch.setattr(mod, "_worktree_has_live_process", lambda p: False)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert not wt.exists()  # reaped — both guards cleared


def test_worktree_has_live_process_real_lsof(fake_repo):
    """Empirical (no-mock) test of `_worktree_has_live_process` against the REAL
    `lsof` (W64: prove the guard with the actual kernel call, not just bash -n).

    Spawns a child whose CWD is the worktree → lsof must report it LIVE; after
    the child dies → not live; a ghost dir → not live. Skips if lsof is absent
    (the guard fail-safes to True there, which we cannot assert as 'dead')."""
    import shutil

    if shutil.which("lsof") is None:
        pytest.skip("lsof not available on this host")

    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "lsof-real", ttl_minutes=5)

    # No process anchored yet → not live.
    assert mod._worktree_has_live_process(wt) is False

    # Child with cwd = worktree → lsof reports the cwd fd → LIVE.
    child = subprocess.Popen(["sleep", "30"], cwd=str(wt))
    try:
        time.sleep(0.3)
        assert mod._worktree_has_live_process(wt) is True
    finally:
        child.terminate()
        child.wait()

    # After the child is gone → not live again.
    time.sleep(0.3)
    assert mod._worktree_has_live_process(wt) is False

    # Non-existent directory → not live (nothing to anchor a process to).
    assert mod._worktree_has_live_process(mod.WORKTREES_DIR / "ghost") is False


def test_worktree_has_live_process_resolves_macos_lsof_outside_path(
    fake_repo, monkeypatch
):
    """launchd PATH omits /usr/sbin on macOS; the broker must still find lsof."""
    mod, _ = fake_repo
    if not Path("/usr/sbin/lsof").exists():
        pytest.skip("/usr/sbin/lsof not available on this host")

    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin:/bin")
    wt = mod.cmd_create("wr2", "lsof-path", ttl_minutes=5)

    assert mod._resolve_lsof_path() == "/usr/sbin/lsof"
    assert mod._worktree_has_live_process(wt) is False


def test_branch_in_origin_main_real_resolver(fake_repo):
    """Load-bearing direct test of `_branch_in_origin_main` against a REAL git
    repo (the refuter-killed logic): it must use origin/main, return True only
    when HEAD is an ancestor of origin/main, and protect pushed-but-not-merged.

    This is the no-monkeypatch proof that the chosen `merge-base --is-ancestor
    HEAD origin/main` test discriminates merged from unmerged correctly."""
    mod, _ = fake_repo

    # Worktree with no commits beyond pushed main → ancestor of origin/main.
    wt_merged = mod.cmd_create("wr2", "rr-merged", ttl_minutes=5)
    assert mod._branch_in_origin_main(wt_merged) is True

    # Worktree with a local commit NOT pushed → NOT an ancestor of origin/main.
    wt_unmerged = mod.cmd_create("wr2", "rr-unmerged", ttl_minutes=5)
    (wt_unmerged / "x.txt").write_text("local only\n")
    _commit_in_worktree(wt_unmerged, mod, "x.txt", "local commit")
    assert mod._branch_in_origin_main(wt_unmerged) is False

    # After landing that commit on origin/main → now an ancestor → merged.
    _merge_worktree_branch_to_origin_main(wt_unmerged, mod)
    assert mod._branch_in_origin_main(wt_unmerged) is True

    # Missing/invalid origin ref → fail-safe FALSE (protect, never reap blind).
    missing = mod.WORKTREES_DIR / "does-not-exist"
    # A non-existent worktree dir short-circuits to True (nothing to protect);
    # the inconclusive-ref path is covered by the unmerged case above where
    # origin/main exists. Assert the directory-gone contract explicitly:
    assert mod._branch_in_origin_main(missing) is True


def test_branch_in_origin_main_squash_merged_is_reapable(fake_repo):
    """W88: A branch that was squash-merged into origin/main is NOT an ancestor,
    but its blob content matches origin/main. It must be recognized as merged
    and reap-eligible."""
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "squash", ttl_minutes=5)

    # Create work on branch
    (wt / "squash.txt").write_text("squash content\n")
    _commit_in_worktree(wt, mod, "squash.txt", "wip")

    # Assert not merged yet
    assert mod._branch_in_origin_main(wt) is False

    # Simulate squash merge: add the same exact file/content to main
    # directly, bypassing the regular merge commit, then push to origin.
    (repo / "squash.txt").write_text("squash content\n")
    subprocess.run(["git", "add", "squash.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "squash merge"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)

    # Fetch in worktree to update its known origin/main
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    # W88: it is not an ancestor, but content matches, so it IS merged.
    assert mod._branch_in_origin_main(wt) is True


def test_branch_in_origin_main_unmerged_content_refuses_reap(fake_repo):
    """W88: A branch where blob content differs from origin/main must NOT be
    reapable, even if some files match."""
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "unmerged", ttl_minutes=5)

    (wt / "file1.txt").write_text("content 1\n")
    _commit_in_worktree(wt, mod, "file1.txt", "commit 1")

    (wt / "file2.txt").write_text("content 2 branch\n")
    _commit_in_worktree(wt, mod, "file2.txt", "commit 2")

    # Simulate partial or conflicting changes on main
    # Ensure it happens in the main repo tree, not an uninitialized main_repo subdir
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    (repo / "file1.txt").write_text("content 1\n")  # matches
    (repo / "file2.txt").write_text("content 2 main\n")  # differs
    subprocess.run(["git", "add", "file1.txt", "file2.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "diff content"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)

    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    # Differing content must block reap
    assert mod._branch_in_origin_main(wt) is False


def test_branch_in_origin_main_mode_only_change_refuses_reap(fake_repo):
    """PENDING-ARMS 2026-08-09 (opened 'while curing two broker defects'):
    blob-only comparison (`git rev-parse <ref>:<path>`) is blind to a MODE
    change — `chmod +x` on a file whose bytes are unchanged reads as
    already-merged and gets reaped although the mode flip is the branch's
    only real change. The ls-tree entry (mode+type+blob) comparison must
    catch it."""
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "modeonly", ttl_minutes=5)

    (wt / "deploy.sh").write_text("echo hi\n")
    os.chmod(wt / "deploy.sh", 0o755)
    _commit_in_worktree(wt, mod, "deploy.sh", "chmod +x deploy.sh")

    # origin/main gets the SAME bytes, but non-executable — mode-only diff.
    (repo / "deploy.sh").write_text("echo hi\n")
    subprocess.run(["git", "add", "deploy.sh"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "add deploy.sh"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    # Guilt: blob matches, mode does not — must NOT read as merged.
    assert mod._branch_in_origin_main(wt) is False


def test_branch_in_origin_main_matching_mode_is_reapable(fake_repo):
    """Innocence twin of the mode-only guilt case: when origin/main's copy
    has the SAME mode (both executable) and the same content, the ls-tree
    entry comparison must not spuriously refuse — proving the fix targets
    mode DIVERGENCE, not the mere presence of an executable bit."""
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "modematch", ttl_minutes=5)

    (wt / "deploy.sh").write_text("echo hi\n")
    os.chmod(wt / "deploy.sh", 0o755)
    _commit_in_worktree(wt, mod, "deploy.sh", "chmod +x deploy.sh")

    (repo / "deploy.sh").write_text("echo hi\n")
    os.chmod(repo / "deploy.sh", 0o755)
    subprocess.run(["git", "add", "deploy.sh"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "add deploy.sh +x"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    assert mod._branch_in_origin_main(wt) is True


def _declare_union_ledger(repo: Path) -> None:
    """Commit a `.gitattributes` declaring LEDGER.md merge=union, plus a base
    LEDGER.md, to the main repo (pre-worktree) so a worktree created after
    this inherits both — mirrors `.claude/skills/modus/PENDING-ARMS.md`'s
    real declaration without coupling the test to that file's live content."""
    (repo / ".gitattributes").write_text("LEDGER.md merge=union\n")
    (repo / "LEDGER.md").write_text("- base line\n")
    subprocess.run(["git", "add", ".gitattributes", "LEDGER.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "declare union ledger"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)


def test_branch_in_origin_main_union_path_growing_superset_is_reapable(fake_repo):
    """PENDING-ARMS 2026-08-09 (the reaper's-16-of-36-worktrees finding): a
    branch that appended one line to a declared merge=union path must still
    read as merged once origin/main carries that line PLUS more lines other
    lanes appended after — exact blob equality can never hold again for an
    append-only ledger, so the right question is line-SUBSET, not equality."""
    mod, repo = fake_repo
    _declare_union_ledger(repo)
    wt = mod.cmd_create("wr2", "uniongrow", ttl_minutes=5)

    with (wt / "LEDGER.md").open("a") as f:
        f.write("- branch line\n")
    _commit_in_worktree(wt, mod, "LEDGER.md", "append branch line")

    # Not merged yet — blob genuinely differs (branch has a line main lacks).
    assert mod._branch_in_origin_main(wt) is False

    # Simulate: the branch's PR merged (its line lands on main), AND two more
    # lanes appended after it — main is now a strict superset.
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    with (repo / "LEDGER.md").open("a") as f:
        f.write("- branch line\n- other lane 1\n- other lane 2\n")
    subprocess.run(["git", "add", "LEDGER.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "3 more ledger lines"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    # Superset: every line the branch has is present on origin/main → reapable.
    assert mod._branch_in_origin_main(wt) is True


def test_branch_in_origin_main_union_path_missing_line_refuses_reap(fake_repo):
    """Innocence twin: if the branch's own ledger line is genuinely ABSENT
    from origin/main (its PR never actually landed — only OTHER lanes
    touched the ledger), the subset check must still refuse to reap."""
    mod, repo = fake_repo
    _declare_union_ledger(repo)
    wt = mod.cmd_create("wr2", "unionmissing", ttl_minutes=5)

    with (wt / "LEDGER.md").open("a") as f:
        f.write("- branch line never merged\n")
    _commit_in_worktree(wt, mod, "LEDGER.md", "append branch line")

    # Other lanes append DIFFERENT lines — the branch's own line is absent.
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    with (repo / "LEDGER.md").open("a") as f:
        f.write("- other lane 1\n- other lane 2\n")
    subprocess.run(["git", "add", "LEDGER.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "2 ledger lines, unrelated"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    assert mod._branch_in_origin_main(wt) is False


def test_branch_in_origin_main_union_path_stale_preexisting_row_is_reapable(fake_repo):
    """Live bug, 2026-08-29: a merged, content-on-main ledger-append branch
    was refused reap because a DIFFERENT, pre-existing row — one this branch
    never touched — was edited by a later lane on main. The old subset check
    compared the branch's FULL frozen snapshot against main, so any edit to
    a row that predates the branch's merge-base (append-only-in-name only:
    real healer ticks correct/close existing rows constantly) reads as the
    branch's own line missing. The fix scopes the subset check to the lines
    the branch itself ADDED since its own merge-base — that line survives
    the base-row edit untouched and must still pass."""
    mod, repo = fake_repo
    _declare_union_ledger(repo)
    wt = mod.cmd_create("wr2", "unionstalerow", ttl_minutes=5)

    with (wt / "LEDGER.md").open("a") as f:
        f.write("- branch's own new row\n")
    _commit_in_worktree(wt, mod, "LEDGER.md", "append branch's own row")

    # A later lane, on main, EDITS the pre-existing "base line" row (not an
    # append — a rewrite of a row that predates this branch's merge-base),
    # then applies the branch's own row on top, exactly as a real merge would.
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    (repo / "LEDGER.md").write_text("- base line EDITED by another lane\n- branch's own new row\n")
    subprocess.run(["git", "add", "LEDGER.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit",
         "-m", "edit base row + land branch's row"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    # The branch's own contribution IS on main — reapable, despite the
    # pre-existing row it never wrote no longer byte-matching its snapshot.
    assert mod._branch_in_origin_main(wt) is True


def test_branch_in_origin_main_union_path_pure_deletion_refuses_reap(fake_repo):
    """Innocence twin for the added-lines scoping: a branch whose only change
    to a union path is a DELETION (no added lines to check a subset of) must
    fail safe to False, never fall back to a full-snapshot comparison that
    could reintroduce the stale-row false-negative from the test above."""
    mod, repo = fake_repo
    _declare_union_ledger(repo)
    wt = mod.cmd_create("wr2", "uniondelete", ttl_minutes=5)

    (wt / "LEDGER.md").write_text("")
    _commit_in_worktree(wt, mod, "LEDGER.md", "delete base line, add nothing")

    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    with (repo / "LEDGER.md").open("a") as f:
        f.write("- other lane row\n")
    subprocess.run(["git", "add", "LEDGER.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "other lane append"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    assert mod._branch_in_origin_main(wt) is False


# ---------------------------------------------------------------------------
# list — orphan detection (W62 ANTIBODY #2)
# ---------------------------------------------------------------------------


def test_list_warns_on_orphan_worktree(fake_repo, capsys):
    """A worktree older than 2× its TTL is flagged ORPHAN with a summary line."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "orphan-001", ttl_minutes=30)
    _backdate_metadata(wt, mod, minutes=120)  # 120 > 2*30 = 60 → orphan
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "orphan-001" in out
    assert "ORPHAN" in out
    assert "1 orphan" in out.lower() or "orphan worktree" in out.lower()


def test_list_no_orphan_when_within_2x_ttl(fake_repo, capsys):
    """A worktree past TTL but under 2× TTL is NOT yet an orphan."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "young-001", ttl_minutes=30)
    _backdate_metadata(wt, mod, minutes=45)  # 30 < 45 < 60 → not orphan
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "young-001" in out
    # "ORPHAN" appears in the header column; assert the data row is NOT flagged.
    data_row = next(line for line in out.splitlines() if "young-001" in line)
    assert "ORPHAN" not in data_row
    assert "orphan worktree" not in out.lower()


def test_cleanup_blocked_by_kill_switch(fake_repo, monkeypatch):
    mod, _ = fake_repo
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "0")
    with pytest.raises(SystemExit):
        mod.cmd_cleanup()


# ---------------------------------------------------------------------------
# release
# ---------------------------------------------------------------------------


def test_release_fails_when_branch_not_merged(fake_repo):
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "rel-001")
    # Add a commit on the new branch so it diverges from main.
    (wt / "new.txt").write_text("on branch\n")
    subprocess.run(["git", "add", "new.txt"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "div"],
        cwd=wt,
        check=True,
    )
    with pytest.raises(SystemExit) as exc:
        mod.cmd_release("rel-001")
    msg = str(exc.value).lower()
    assert "not merged" in msg
    assert wt.exists()  # untouched


def test_release_succeeds_when_branch_merged(fake_repo):
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "rel-002")
    # No new commits → branch is already at HEAD of main → considered merged.
    rc = mod.cmd_release("rel-002")
    assert rc == 0
    assert not wt.exists()


def test_release_force_overrides_unmerged(fake_repo):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "rel-force")
    (wt / "new.txt").write_text("on branch\n")
    subprocess.run(["git", "add", "new.txt"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "div"],
        cwd=wt,
        check=True,
    )
    rc = mod.cmd_release("rel-force", force=True)
    assert rc == 0
    assert not wt.exists()


def test_release_reaps_squash_merged_branch(fake_repo):
    """W88 guilt: --release must recognize a squash-merged branch as merged via
    the blob-per-file content fallback — the ancestor proxy lies post-squash.
    Live case 2026-07-06: three squash-merged lanes (#2044/#2045/#2047) needed
    --force because cmd_release only asked rev-list."""
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "rel-squash")

    (wt / "squash.txt").write_text("squash content\n")
    subprocess.run(["git", "add", "squash.txt"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "wip"],
        cwd=wt,
        check=True,
    )

    # Simulate squash merge: same exact content lands on main as a NEW commit
    # (branch SHA never becomes an ancestor), then push to origin.
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    (repo / "squash.txt").write_text("squash content\n")
    subprocess.run(["git", "add", "squash.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "squash merge"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    rc = mod.cmd_release("rel-squash")  # no --force needed anymore
    assert rc == 0
    assert not wt.exists()


def test_release_refuses_branch_with_unmerged_content(fake_repo):
    """W88 innocence: a branch whose blob content differs from origin/main must
    still be refused by --release without --force (fail-safe preserved)."""
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "rel-unmg")

    (wt / "f.txt").write_text("branch content\n")
    subprocess.run(["git", "add", "f.txt"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "wip"],
        cwd=wt,
        check=True,
    )

    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    (repo / "f.txt").write_text("different on main\n")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "other"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "origin"], cwd=wt, check=True)

    with pytest.raises(SystemExit) as exc:
        mod.cmd_release("rel-unmg")
    assert "not merged" in str(exc.value).lower()
    assert wt.exists()  # untouched


def test_release_unknown_task_errors(fake_repo):
    mod, _ = fake_repo
    with pytest.raises(SystemExit) as exc:
        mod.cmd_release("does-not-exist")
    assert "no worktree metadata" in str(exc.value).lower()


def test_release_blocked_by_kill_switch(fake_repo, monkeypatch):
    mod, _ = fake_repo
    mod.cmd_create("wr2", "rel-killed")
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "off")
    with pytest.raises(SystemExit):
        mod.cmd_release("rel-killed")


# ---------------------------------------------------------------------------
# kill-switch + list still works
# ---------------------------------------------------------------------------


def test_list_works_under_kill_switch(fake_repo, monkeypatch, capsys):
    """--list is observational, must keep working when broker is disabled."""
    mod, _ = fake_repo
    mod.cmd_create("wr2", "ks-list")
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "false")
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "ks-list" in out


# ---------------------------------------------------------------------------
# Smoke: main() CLI entry
# ---------------------------------------------------------------------------


def test_main_create_writes_worktree_ready_line(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.main(["--lane", "wr2", "--task-id", "main-smoke"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("WORKTREE_READY ")
    assert "wr2-main-smoke" in out


def test_main_missing_args_returns_nonzero(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.main([])
    assert rc != 0


def test_main_conflicting_ops_rejected(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.main(["--list", "--cleanup"])
    assert rc != 0


# ---------------------------------------------------------------------------
# W105 upstream half — the broker must never CREATE a nested worktree
# ---------------------------------------------------------------------------


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30)


@pytest.fixture
def repo_with_worktree(tmp_path):
    """A real git repo carrying the broker's signature file, plus one linked worktree."""
    root = tmp_path / "main"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "agent_start.py").write_text("# signature\n")
    (root / ".gitignore").write_text(".worktrees/\n")
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t.t"], root)
    _git(["config", "user.name", "t"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "init"], root)
    wt = root / ".worktrees" / "ops-existing"
    _git(["worktree", "add", "-q", "-b", "b/existing", str(wt), "HEAD"], root)
    yield root, wt
    _git(["worktree", "prune"], root)


def test_repo_root_resolves_to_main_checkout_from_inside_a_worktree(repo_with_worktree):
    """THE SCAR. `Path(__file__).resolve().parents[1]` answered with the WORKTREE when the
    copy inside one was run — so `WORKTREES_DIR` pointed at `<worktree>/.worktrees` and the
    broker nested a worktree inside a worktree (W63). And the wrong copy is the CONVENIENT
    one: every lane cds into its worktree, where `python scripts/agent_start.py` is the
    documented quick-start.
    """
    root, wt = repo_with_worktree
    (wt / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT_PATH, wt / "scripts" / "agent_start.py")

    probe = (
        "import importlib.util,sys;"
        f"spec=importlib.util.spec_from_file_location('as_probe', r'{wt}/scripts/agent_start.py');"
        "m=importlib.util.module_from_spec(spec);sys.modules['as_probe']=m;"
        "spec.loader.exec_module(m);print(m.REPO_ROOT)"
    )
    out = subprocess.run([sys.executable, "-c", probe], cwd=str(wt),
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    derived = Path(out.stdout.strip())
    assert derived == root.resolve(), (
        f"the copy inside a worktree derived REPO_ROOT={derived}, not the main checkout "
        f"{root.resolve()} — this is exactly how W63 nesting happened"
    )
    assert ".worktrees" not in str(derived)


def test_refuses_a_target_inside_an_existing_worktree(repo_with_worktree, tmp_path):
    """GUILT for the REGISTRY arm, which is the only thing that can catch this shape.

    A worktree does not have to live under `.worktrees/` — `git worktree add` puts one
    wherever it is told. When it doesn't, the target inherits only ONE `.worktrees`
    segment, so the structural fallback is blind by construction and the verdict must
    come from asking git which paths are actually worktrees (entity, not shape — W105).
    """
    root, _wt = repo_with_worktree
    side = tmp_path / "side-wt"
    assert _git(["worktree", "add", "-q", "-b", "b/side", str(side), "HEAD"], root).returncode == 0
    target = side / ".worktrees" / "ops-nested"
    assert str(target.resolve()).count("/.worktrees/") == 1, "the structural check must NOT fire here"

    mod = _load_module(root)
    with pytest.raises(SystemExit) as exc:
        mod._refuse_if_nested(target)
    assert "inside an existing" in str(exc.value)


def test_refuses_a_doubled_worktrees_segment_even_with_a_dead_probe(repo_with_worktree, monkeypatch):
    """GUILT: a probe that cannot answer is not the same fact as "nothing is nested"
    (family #2). With `git worktree list` starved, the structural shape still refuses.

    The patch is scoped to that ONE invocation: `mod.subprocess` IS the global module, so
    replacing `.run` outright also kills the fixture's own teardown — a test harness that
    breaks what it did not intend to touch is the same over-match this lane keeps curing.
    """
    root, wt = repo_with_worktree
    mod = _load_module(root)
    real_run = subprocess.run

    def _probe_dead(*a, **k):
        argv = a[0] if a else k.get("args", [])
        if isinstance(argv, (list, tuple)) and "worktree" in argv and "list" in argv:
            raise OSError("probe dead")
        return real_run(*a, **k)

    monkeypatch.setattr(mod.subprocess, "run", _probe_dead)
    with pytest.raises(SystemExit) as exc:
        mod._refuse_if_nested(wt / ".worktrees" / "ops-nested")
    assert "inside another worktree" in str(exc.value)


def test_does_not_refuse_an_ordinary_target_under_the_main_checkout(repo_with_worktree):
    """INNOCENCE, and the one that matters: the main checkout contains EVERY worktree, so
    a rule that called that "nesting" would refuse every creation the broker exists for."""
    root, _wt = repo_with_worktree
    mod = _load_module(root)
    # returning at all IS the property: the refusal path exits, it never returns.
    assert mod._refuse_if_nested(root / ".worktrees" / "ops-brand-new") is None


def test_does_not_refuse_a_sibling_of_an_existing_worktree(repo_with_worktree):
    """INNOCENCE: sharing a parent directory with a worktree is not being inside one —
    the same entity-vs-shape distinction the removal guard needed (W105)."""
    root, _wt = repo_with_worktree
    mod = _load_module(root)
    assert mod._refuse_if_nested(root / ".worktrees" / "ops-existing-sibling") is None


# ---------------------------------------------------------------------------
# Root derivation from OUTSIDE the tree — the silent-empty-inventory scar
# (2026-08-08). The signature guard protected only the git-derived answer; the
# `return script_dir` fallback was bare, so a copy run from /tmp reported an
# EMPTY worktree inventory instead of failing. W84: cannot-verify read as clean.
# ---------------------------------------------------------------------------


def _seed_task_metadata(wt: Path, task_id: str = "existing") -> None:
    """Make a raw `git worktree add` directory VISIBLE to `--list`.

    `--list` enumerates worktrees that carry `.agent-task.json`, not directories.
    Without this the inventory reads empty for a CORRECT root too, and the whole
    probe measures the poverty of its own fixture rather than the defect (W108).
    """
    (wt / ".agent-task.json").write_text(json.dumps({
        "task_id": task_id,
        "lane": "ops",
        "branch": "b/existing",
        "host": "test-host",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl_minutes": 60,
        "pid": os.getpid(),
        "base_branch": "main",
        "worktree_path": str(wt),
    }, indent=2))


def _derive_probe(script: Path, *, cwd: Path, env_extra: dict | None = None):
    """Run a COPY of the broker out-of-process and report what it derived.

    A subprocess is the faithful oracle here: the defect is entirely about what
    `__file__`, the cwd and the environment look like to a fresh interpreter, and
    an in-process import cannot reproduce any of it.

    The env is built explicitly rather than inherited so a stray NUZ_REPO_ROOT —
    `infra/claude-hooks/test_hook_innocence.py` sets it via bare `os.environ`,
    not monkeypatch — can never decide the outcome of these tests.
    """
    env = {k: v for k, v in os.environ.items() if k != "NUZ_REPO_ROOT"}
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(script), "--list"],
        cwd=str(cwd), capture_output=True, text=True, timeout=60, env=env,
    )


@pytest.fixture
def out_of_tree_copy(repo_with_worktree, tmp_path):
    """The broker copied OUTSIDE any repo, plus a HOME that is not the checkout.

    Mirrors the real m5 invocation `git show origin/main:scripts/agent_start.py >
    /tmp/x.py && python3 /tmp/x.py` — the documented way to run CURRENT code on a
    machine whose main checkout is deliberately never pulled (W106b).

    The copy is nested one level down so `Path(__file__).resolve().parents[1]` is
    a signature-less temp dir, exactly as `/tmp/x.py` makes it `/`.
    """
    root, wt = repo_with_worktree
    _seed_task_metadata(wt)
    outside = tmp_path / "outside" / "pkg"
    outside.mkdir(parents=True)
    copy = outside / "agent_start.py"
    shutil.copy2(SCRIPT_PATH, copy)
    home = tmp_path / "elsewhere-home"
    home.mkdir()
    return copy, outside, home, root, wt


def test_an_out_of_tree_copy_refuses_instead_of_reporting_an_empty_inventory(out_of_tree_copy):
    """THE SCAR (guilt). Before the cure this exited 0 printing "(no active
    worktrees under .worktrees/)" while a real worktree sat in the real repo.

    That is the worst available failure for a safety organ: an empty inventory is
    indistinguishable from a clean one, so the reaper reports nothing to do and the
    reader believes it. Asserting only "non-zero exit" would be too weak — the
    point is that it must NOT emit the reassuring sentence.
    """
    copy, outside, home, _root, _wt = out_of_tree_copy
    res = _derive_probe(copy, cwd=outside, env_extra={"HOME": str(home)})

    assert res.returncode != 0, (
        "an out-of-tree copy that cannot find the checkout exited 0 — "
        f"stdout={res.stdout!r}"
    )
    assert "no active worktrees" not in res.stdout.lower(), (
        "it printed the CLEAN-inventory sentence while looking in the wrong place: "
        f"{res.stdout!r}"
    )
    combined = (res.stdout + res.stderr)
    assert "NUZ_REPO_ROOT" in combined, "the refusal must name the way out"


def test_an_out_of_tree_copy_finds_the_real_worktrees_via_the_escape_hatch(out_of_tree_copy):
    """The POSITIVE CONTROL, and the reason the cure is a cure rather than a louder
    failure: with NUZ_REPO_ROOT the /tmp invocation now WORKS.

    Without this assertion the test above is satisfied by a broker that always
    refuses. It also pins the escape hatch that previously stopped at
    `proprioception.py` and the two hooks and never reached this script.
    """
    copy, outside, home, root, _wt = out_of_tree_copy
    res = _derive_probe(
        copy, cwd=outside, env_extra={"HOME": str(home), "NUZ_REPO_ROOT": str(root)}
    )
    assert res.returncode == 0, res.stderr[-800:]
    assert "b/existing" in res.stdout, (
        f"the real worktree was not listed: stdout={res.stdout!r}"
    )


def test_an_out_of_tree_copy_falls_back_to_the_home_checkout(out_of_tree_copy, tmp_path):
    """Candidate 4. With HOME pointing at a directory that IS the checkout, a /tmp
    copy resolves with no env var at all — machine-agnostic (Pro /Users/nuzantara,
    m5 /Users/balizero), the same last resort the worktree hooks already use.
    """
    copy, outside, _home, root, _wt = out_of_tree_copy
    home = tmp_path / "home-with-repo"
    home.mkdir()
    (home / "nuzantara").symlink_to(root)

    res = _derive_probe(copy, cwd=outside, env_extra={"HOME": str(home)})
    assert res.returncode == 0, res.stderr[-800:]
    assert "b/existing" in res.stdout, res.stdout


def test_an_override_that_is_not_the_repo_is_named_not_silently_replaced(
    out_of_tree_copy, tmp_path
):
    """GUILT for the override branch. Run from a place where OTHER candidates would
    succeed, so "it worked" would hide the fact that it worked on a DIFFERENT repo
    than the one named. Silently retargeting is precisely what the signature guard
    exists to prevent — doing it to an explicit request is worse, not better.
    """
    copy, _outside, home, root, _wt = out_of_tree_copy
    bogus = tmp_path / "not-the-repo"
    bogus.mkdir()

    res = _derive_probe(
        copy, cwd=root, env_extra={"HOME": str(home), "NUZ_REPO_ROOT": str(bogus)}
    )
    assert res.returncode != 0, (
        f"a bogus override was silently ignored; stdout={res.stdout!r}"
    )
    assert str(bogus) in (res.stdout + res.stderr), "the refusal must name the bad root"


def test_innocence_an_in_repo_run_is_untouched_by_the_new_chain(repo_with_worktree):
    """INNOCENCE. The ordinary invocation — cwd inside the checkout, no env — must
    keep resolving via git exactly as before. The fail-loud branch is unreachable
    for every real consumer (they all `cd <root> && python3 scripts/agent_start.py`).
    """
    root, wt = repo_with_worktree
    _seed_task_metadata(wt)
    shutil.copy2(SCRIPT_PATH, root / "scripts" / "agent_start.py")
    res = _derive_probe(root / "scripts" / "agent_start.py", cwd=root)
    assert res.returncode == 0, res.stderr[-800:]
    assert "b/existing" in res.stdout, res.stdout


# ---------------------------------------------------------------------------
# release: the W88 content fallback must not be gated on base == "main"
# ---------------------------------------------------------------------------


def _commit_in(path: Path, name: str, body: str, msg: str):
    (path / name).write_text(body)
    subprocess.run(["git", "add", name], cwd=path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", msg],
        cwd=path, check=True, capture_output=True,
    )


def test_release_reaps_a_stacked_branch_whose_base_was_deleted(fake_repo):
    """GUILT. A branch created off `feature/x` — since squash-merged and its base
    DELETED — was refused even with every authored file byte-identical on
    origin/main, because the content fallback was gated on `base == "main"`.

    The harm is not the friction. The refusal's own suggested way out is --force,
    which deletes unconditionally AND skips the uncommitted-WIP guard — so an
    over-strict check hands you the nuclear option and turns a #3 into a #2 (W105).
    Content-on-origin/main is sufficient proof whatever the recorded base was.
    """
    mod, repo = fake_repo
    subprocess.run(["git", "checkout", "-b", "feature/x"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "feature/x"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("wr2", "rel-stacked", base_branch="feature/x")
    _commit_in(wt, "stacked.txt", "stacked content\n", "wip")

    # The stack lands on main by squash, then the base branch is deleted — the
    # ordinary end of a stacked PR.
    _commit_in(repo, "stacked.txt", "stacked content\n", "squash merge of the stack")
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-D", "feature/x"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "--delete", "feature/x"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "fetch", "origin", "--prune"], cwd=wt, check=True, capture_output=True)

    rc = mod.cmd_release("rel-stacked")  # must NOT need --force
    assert rc == 0
    assert not wt.exists()


def test_innocence_a_stacked_branch_with_real_work_is_still_refused(fake_repo):
    """INNOCENCE, and the one that matters: widening the content check must not
    turn --release into "delete anything whose base disappeared". Content that is
    NOT on origin/main is still protected, deleted base or not.
    """
    mod, repo = fake_repo
    subprocess.run(["git", "checkout", "-b", "feature/y"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "feature/y"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("wr2", "rel-stacked-live", base_branch="feature/y")
    _commit_in(wt, "live.txt", "work that never landed\n", "wip")

    subprocess.run(["git", "branch", "-D", "feature/y"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "--delete", "feature/y"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "fetch", "origin", "--prune"], cwd=wt, check=True, capture_output=True)

    with pytest.raises(SystemExit) as exc:
        mod.cmd_release("rel-stacked-live")
    assert wt.exists(), "a worktree holding unlanded work was removed"
    msg = str(exc.value)
    assert "feature/y" in msg and "no longer exists" in msg, (
        "the refusal must name the DELETED BASE as the cause; blaming the merge "
        f"sends the reader to fix something that is not broken (W106). Got: {msg}"
    )


# ---------------------------------------------------------------------------
# Round 2 — every test below exists because an independent refuter found the
# first cure incomplete. A cure written in answer to an objection is a NEW
# claim, and gets its own proof (W113).
# ---------------------------------------------------------------------------


def test_an_override_pointing_at_a_worktree_resolves_to_the_main_checkout(
    out_of_tree_copy,
):
    """A linked worktree carries `scripts/agent_start.py` — it IS a checkout of this
    repo. So the signature alone answers "is this a checkout", never "is this THE
    main one", and NUZ_REPO_ROOT=<worktree> would have been accepted, nesting
    `.worktrees` inside a worktree (W63 — the shape the signature was added to stop).
    """
    copy, outside, home, root, wt = out_of_tree_copy
    # The premise, asserted rather than assumed: the worktree really does carry
    # the signature, so the signature test alone CANNOT tell it from the main
    # checkout. Without this the test could pass for the wrong reason.
    assert (wt / "scripts" / "agent_start.py").is_file()

    res = _derive_probe(
        copy, cwd=outside, env_extra={"HOME": str(home), "NUZ_REPO_ROOT": str(wt)}
    )
    assert res.returncode == 0, res.stderr[-800:]
    # It resolved to the MAIN checkout, so it sees the main checkout's inventory.
    assert "b/existing" in res.stdout, (
        "pointing at a worktree did not resolve to the main checkout: "
        f"stdout={res.stdout!r}"
    )


def test_an_out_of_tree_script_uses_the_repo_the_caller_is_standing_in(out_of_tree_copy):
    """git was asked only where the SCRIPT sits, so `cd <repo> && python3 /tmp/x.py`
    answered about /tmp and raised — ignoring the repo the caller was standing in.
    That is the exact m5 invocation, and refusing it would have replaced a silent
    wrong answer with a loud wrong refusal.
    """
    copy, _outside, home, root, _wt = out_of_tree_copy
    res = _derive_probe(copy, cwd=root, env_extra={"HOME": str(home)})
    assert res.returncode == 0, (
        "an out-of-tree copy run from INSIDE the checkout refused; "
        f"stderr={res.stderr[-500:]}"
    )
    assert "b/existing" in res.stdout, res.stdout


def test_release_refuses_when_head_is_not_the_branch_being_deleted(fake_repo):
    """GUILT for the entity-vs-location hole. The content proof is read off the
    worktree's HEAD, but the command then runs `git branch -D <meta.branch>` — a
    different entity the moment HEAD is detached. Detach at origin/main and the
    proof passes instantly while the registered branch still holds unmerged work,
    so --release would DESTROY it. Cannot-ask must not read as proven (W84).
    """
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "rel-detached")
    _commit_in(wt, "unlanded.txt", "work that never landed\n", "wip")
    branch = [m for m in mod._iter_metadata() if m.task_id == "rel-detached"][0].branch

    subprocess.run(["git", "checkout", "--detach", "origin/main"], cwd=wt, check=True,
                   capture_output=True)

    with pytest.raises(SystemExit):
        mod.cmd_release("rel-detached")

    still = subprocess.run(["git", "branch", "--list", branch], cwd=repo,
                           capture_output=True, text=True, check=True)
    assert branch in still.stdout, f"the unmerged branch {branch} was deleted"
    assert wt.exists()


def test_innocence_a_stacked_branch_on_a_LIVE_base_is_not_judged_against_main(fake_repo):
    """INNOCENCE for the narrowing. The first draft dropped the `base == "main"` gate
    outright; the refuter produced the case that breaks: a child branch can match
    origin/main by content while its diff against its LIVE base is the whole point
    of its existence. main-relative proof is only meaningful when main is the
    integration target — i.e. base IS main, or base is GONE. A live non-main base
    keeps the strict ancestry rule.
    """
    mod, repo = fake_repo
    subprocess.run(["git", "checkout", "-b", "feature/live"], cwd=repo, check=True,
                   capture_output=True)
    _commit_in(repo, "flag.txt", "X\n", "base diverges from main")
    subprocess.run(["git", "push", "-u", "origin", "feature/live"], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    wt = mod.cmd_create("wr2", "rel-child", base_branch="feature/live")
    # The child restores what main has — content-identical to origin/main, yet its
    # real change (undoing the base's X) is nowhere upstream.
    subprocess.run(["git", "rm", "-q", "flag.txt"], cwd=wt, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "undo base"],
        cwd=wt, check=True, capture_output=True,
    )

    with pytest.raises(SystemExit) as exc:
        mod.cmd_release("rel-child")
    assert wt.exists()
    assert "feature/live" in str(exc.value)
