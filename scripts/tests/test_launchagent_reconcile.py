"""Unit tests for scripts/launchagent_reconcile.py (C3 — reconcile report).

Every category gets an innocence AND a guilt case (cicatrix #3). The --apply
protections mirror the red-team findings 2026-07-02: label≠filename, only-copy
backups, loaded-source files, lying mtimes, launchctl-unavailable degrade.

No launchctl, no Telegram, no real LaunchAgents dir — everything injected.
"""
from __future__ import annotations

import importlib.util
import plistlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
MOD_PATH = SCRIPTS_DIR / "launchagent_reconcile.py"

spec = importlib.util.spec_from_file_location("launchagent_reconcile", MOD_PATH)
lar = importlib.util.module_from_spec(spec)
sys.modules["launchagent_reconcile"] = lar
spec.loader.exec_module(lar)

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)


def write_plist(path: Path, label: str, program_args=None, extra=None):
    data = {"Label": label, "ProgramArguments": program_args or ["/bin/echo", "hi"]}
    if extra:
        data.update(extra)
    with path.open("wb") as f:
        plistlib.dump(data, f)


@pytest.fixture
def world(tmp_path):
    """A fake HOME with LaunchAgents dir + repo with infra/launchagents."""
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    repo = tmp_path / "repo"
    (repo / "infra" / "launchagents").mkdir(parents=True)
    return {"home": home, "agents": agents, "repo": repo}


def run_reconcile(world, loaded, **kw):
    return lar.reconcile(
        world["agents"], world["repo"], loaded, home=world["home"], now=NOW, **kw
    )


# ─────────────────────────────────────────────────────────────────────────
# Scope + label keying
# ─────────────────────────────────────────────────────────────────────────

def test_out_of_scope_ignored(world):
    write_plist(world["agents"] / "com.google.keystone.plist", "com.google.keystone")
    r = run_reconcile(world, loaded=set())
    assert r["live_count"] == 0


def test_keyed_by_parsed_label_not_filename(world):
    """Real drift: com.matagaruda.kita-feed.daily.plist carries
    Label=com.matagaruda.kita-feed. Loaded-state must match by LABEL."""
    write_plist(
        world["agents"] / "com.matagaruda.kita-feed.daily.plist",
        "com.matagaruda.kita-feed",
    )
    r = run_reconcile(world, loaded={"com.matagaruda.kita-feed"})
    assert r["present_not_loaded"] == []
    assert r["zombie_loaded"] == []


# ─────────────────────────────────────────────────────────────────────────
# Loaded-state categories
# ─────────────────────────────────────────────────────────────────────────

def test_zombie_loaded_detected(world):
    r = run_reconcile(world, loaded={"com.balizero.ghost"})
    assert r["zombie_loaded"] == ["com.balizero.ghost"]


def test_present_not_loaded_detected(world):
    write_plist(world["agents"] / "com.balizero.sleepy.plist", "com.balizero.sleepy")
    r = run_reconcile(world, loaded=set())
    assert r["present_not_loaded"] == ["com.balizero.sleepy"]


def test_launchctl_unavailable_skips_loaded_categories(world):
    """`launchctl list` empty/unavailable must NOT mass-classify every live
    plist as not-loaded (red-team finding #1)."""
    write_plist(world["agents"] / "com.balizero.alive.plist", "com.balizero.alive")
    r = run_reconcile(world, loaded=None)
    assert r["launchctl_available"] is False
    assert r["present_not_loaded"] == []
    assert r["zombie_loaded"] == []


# ─────────────────────────────────────────────────────────────────────────
# Target checks
# ─────────────────────────────────────────────────────────────────────────

def test_broken_target_flagged(world):
    write_plist(
        world["agents"] / "com.balizero.broken.plist",
        "com.balizero.broken",
        program_args=["/nonexistent/wrapper.sh"],
    )
    r = run_reconcile(world, loaded=None)
    assert [b["label"] for b in r["broken_target"]] == ["com.balizero.broken"]


def test_existing_target_innocent(world):
    r_ok = world["home"] / "Desktop" / "nuzantara" / "scripts"
    r_ok.mkdir(parents=True)
    # repo fixture lives elsewhere; use a real system binary as target
    write_plist(
        world["agents"] / "com.balizero.fine.plist",
        "com.balizero.fine",
        program_args=["/bin/echo", "ok"],
    )
    r = run_reconcile(world, loaded=None)
    assert r["broken_target"] == []


def test_home_fork_target_flagged(world):
    payload = world["home"] / "scripts" / "wrapper.sh"
    payload.parent.mkdir(parents=True)
    payload.write_text("#!/bin/sh\n")
    write_plist(
        world["agents"] / "com.balizero.fork.plist",
        "com.balizero.fork",
        program_args=[str(payload)],
    )
    r = run_reconcile(world, loaded=None)
    assert [h["label"] for h in r["home_fork_target"]] == ["com.balizero.fork"]


def test_interpreter_payload_under_home_flagged(world):
    """bash + $HOME script: the payload (argv[1]) is the fork, not /bin/bash."""
    payload = world["home"] / ".openclaw" / "bin" / "wr2-script-wrapper.sh"
    payload.parent.mkdir(parents=True)
    payload.write_text("#!/bin/bash\n")
    write_plist(
        world["agents"] / "com.balizero.bridge.plist",
        "com.balizero.bridge",
        program_args=["/bin/bash", str(payload), "scripts/foo.py"],
    )
    r = run_reconcile(world, loaded=None)
    assert [h["target"] for h in r["home_fork_target"]] == [str(payload)]


def test_canon_paired_home_target_not_a_fork(world):
    """A $HOME payload byte-identical to its repo canon (basename match in
    wrappers/ or scripts/) is the W84-safe placement, not a fork — it must
    land in canon_paired, NOT home_fork_target."""
    canon = world["repo"] / "infra" / "launchagents" / "wrappers" / "wrapper.sh"
    canon.parent.mkdir(parents=True, exist_ok=True)
    canon.write_text("#!/bin/sh\necho same\n")
    live = world["home"] / ".nuzantara-cron" / "wrapper.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\necho same\n")
    write_plist(
        world["agents"] / "com.balizero.paired.plist",
        "com.balizero.paired",
        program_args=[str(live)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["home_fork_target"] == []
    assert [c["label"] for c in r["canon_paired"]] == ["com.balizero.paired"]
    assert r["canon_paired"][0]["canon"] == "infra/launchagents/wrappers/wrapper.sh"


def test_canon_diverged_home_target_still_a_fork(world):
    """Same basename but DIFFERENT bytes = the real disease (drift). Must stay
    in home_fork_target, with the canon named in the detail."""
    canon = world["repo"] / "scripts" / "wrapper.sh"
    canon.parent.mkdir(parents=True, exist_ok=True)
    canon.write_text("#!/bin/sh\necho repo-version\n")
    live = world["home"] / ".nuzantara-cron" / "wrapper.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\necho drifted-version\n")
    write_plist(
        world["agents"] / "com.balizero.drifted.plist",
        "com.balizero.drifted",
        program_args=[str(live)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["canon_paired"] == []
    assert [h["label"] for h in r["home_fork_target"]] == ["com.balizero.drifted"]
    assert "DIVERGED from canon" in r["home_fork_target"][0]["detail"]


def test_canon_paired_home_target_found_nested_under_scripts(world):
    """Real 2026-07-07 miss: canon one level deeper than scripts/<name> (e.g.
    scripts/mini-migration/wrapper.sh) must still be found — a flat basename
    match at the top of scripts/ is not enough."""
    canon = world["repo"] / "scripts" / "mini-migration" / "wrapper.sh"
    canon.parent.mkdir(parents=True, exist_ok=True)
    canon.write_text("#!/bin/sh\necho same\n")
    live = world["home"] / ".nuzantara-cron" / "wrapper.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\necho same\n")
    write_plist(
        world["agents"] / "com.balizero.nested.plist",
        "com.balizero.nested",
        program_args=[str(live)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["home_fork_target"] == []
    assert [c["label"] for c in r["canon_paired"]] == ["com.balizero.nested"]
    assert r["canon_paired"][0]["canon"] == "scripts/mini-migration/wrapper.sh"


def test_canon_paired_home_target_found_nested_under_infra(world):
    """Same miss, infra/ side (e.g. infra/healer/wrapper.sh)."""
    canon = world["repo"] / "infra" / "healer" / "wrapper.sh"
    canon.parent.mkdir(parents=True, exist_ok=True)
    canon.write_text("#!/bin/sh\necho same\n")
    live = world["home"] / ".nuzantara-cron" / "wrapper.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\necho same\n")
    write_plist(
        world["agents"] / "com.balizero.infranested.plist",
        "com.balizero.infranested",
        program_args=[str(live)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["home_fork_target"] == []
    assert [c["label"] for c in r["canon_paired"]] == ["com.balizero.infranested"]
    assert r["canon_paired"][0]["canon"] == "infra/healer/wrapper.sh"


def test_canon_paired_home_target_found_under_apps_scripts(world):
    """Per-app scripts/ dirs (apps/backend-rag/scripts/) are indexed too —
    the real miss for run_local_livekit_server.sh — without walking all of
    apps/ (which holds ~36k unrelated source files)."""
    canon = world["repo"] / "apps" / "backend-rag" / "scripts" / "wrapper.sh"
    canon.parent.mkdir(parents=True, exist_ok=True)
    canon.write_text("#!/bin/sh\necho same\n")
    live = world["home"] / ".nuzantara-cron" / "wrapper.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\necho same\n")
    write_plist(
        world["agents"] / "com.balizero.appsnested.plist",
        "com.balizero.appsnested",
        program_args=[str(live)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["home_fork_target"] == []
    assert [c["label"] for c in r["canon_paired"]] == ["com.balizero.appsnested"]
    assert r["canon_paired"][0]["canon"] == "apps/backend-rag/scripts/wrapper.sh"


def test_canon_index_ignores_excluded_dirnames(world):
    """Innocence: a matching basename sitting only inside an excluded dir
    (node_modules) must NOT count as canon — the target stays a real fork,
    not a false-cured one."""
    decoy = world["repo"] / "scripts" / "node_modules" / "wrapper.sh"
    decoy.parent.mkdir(parents=True, exist_ok=True)
    decoy.write_text("#!/bin/sh\necho same\n")
    live = world["home"] / ".nuzantara-cron" / "wrapper.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\necho same\n")
    write_plist(
        world["agents"] / "com.balizero.decoyed.plist",
        "com.balizero.decoyed",
        program_args=[str(live)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["canon_paired"] == []
    assert [h["label"] for h in r["home_fork_target"]] == ["com.balizero.decoyed"]
    assert "no repo canon" in r["home_fork_target"][0]["detail"]


def test_repo_canon_prefers_byte_identical_among_multiple_candidates(world):
    """Two same-basename candidates in different dirs, only one identical —
    must pick the identical one (canon_paired), not whichever sorts first."""
    diverged = world["repo"] / "infra" / "aaa-first-alphabetically" / "wrapper.sh"
    diverged.parent.mkdir(parents=True, exist_ok=True)
    diverged.write_text("#!/bin/sh\necho old-version\n")
    identical = world["repo"] / "scripts" / "zzz-last-alphabetically" / "wrapper.sh"
    identical.parent.mkdir(parents=True, exist_ok=True)
    identical.write_text("#!/bin/sh\necho same\n")
    live = world["home"] / ".nuzantara-cron" / "wrapper.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\necho same\n")
    write_plist(
        world["agents"] / "com.balizero.multi.plist",
        "com.balizero.multi",
        program_args=[str(live)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["home_fork_target"] == []
    assert [c["label"] for c in r["canon_paired"]] == ["com.balizero.multi"]
    assert r["canon_paired"][0]["canon"] == "scripts/zzz-last-alphabetically/wrapper.sh"


def test_symlink_into_repo_not_a_fork(world):
    """A $HOME payload that is a symlink into the repo is the CURE for #1,
    not an instance of it."""
    repo_script = world["repo"] / "scripts" / "wrapper.sh"
    repo_script.parent.mkdir(parents=True)
    repo_script.write_text("#!/bin/sh\n")
    link = world["home"] / "scripts" / "wrapper.sh"
    link.parent.mkdir(parents=True)
    link.symlink_to(repo_script)
    write_plist(
        world["agents"] / "com.balizero.cured.plist",
        "com.balizero.cured",
        program_args=[str(link)],
    )
    r = run_reconcile(world, loaded=None)
    assert r["home_fork_target"] == []


# ─────────────────────────────────────────────────────────────────────────
# Repo divergence
# ─────────────────────────────────────────────────────────────────────────

def test_repo_divergent_on_structural_change(world):
    name = "com.balizero.thing.plist"
    write_plist(world["agents"] / name, "com.balizero.thing", program_args=["/bin/echo", "live"])
    write_plist(
        world["repo"] / "infra" / "launchagents" / name,
        "com.balizero.thing",
        program_args=["/bin/echo", "repo-changed"],
    )
    r = run_reconcile(world, loaded=None)
    assert [d["file"] for d in r["repo_divergent"]] == [name]


def test_env_specific_keys_do_not_diverge(world):
    """HOME-specific EnvironmentVariables / log paths differ per machine by
    design — no divergence cry-wolf (red-team finding #7)."""
    name = "com.balizero.envy.plist"
    write_plist(
        world["agents"] / name, "com.balizero.envy",
        extra={
            "EnvironmentVariables": {"HOME": "/Users/nuzantara"},
            "StandardOutPath": "/Users/nuzantara/logs/x.log",
        },
    )
    write_plist(
        world["repo"] / "infra" / "launchagents" / name, "com.balizero.envy",
        extra={
            "EnvironmentVariables": {"HOME": "/Users/balizero"},
            "StandardOutPath": "/Users/balizero/logs/x.log",
        },
    )
    r = run_reconcile(world, loaded=None)
    assert r["repo_divergent"] == []


def test_symlinked_repo_plist_never_divergent(world):
    name = "com.balizero.linked.plist"
    twin = world["repo"] / "infra" / "launchagents" / name
    write_plist(twin, "com.balizero.linked")
    (world["agents"] / name).symlink_to(twin)
    r = run_reconcile(world, loaded=None)
    assert r["repo_divergent"] == []
    assert r["repo_symlinked"] == [name]


# ─────────────────────────────────────────────────────────────────────────
# Junk + --apply protections
# ─────────────────────────────────────────────────────────────────────────

def _old(path: Path, days: int):
    import os as _os
    ts = (NOW - timedelta(days=days)).timestamp()
    _os.utime(path, (ts, ts))


def test_junk_detected_and_live_plist_never_junk(world):
    write_plist(world["agents"] / "com.balizero.live.plist", "com.balizero.live")
    bak = world["agents"] / "com.balizero.live.plist.bak-pre-x"
    write_plist(bak, "com.balizero.live")
    r = run_reconcile(world, loaded=None)
    assert [j["file"] for j in r["junk"]] == ["com.balizero.live.plist.bak-pre-x"]
    assert r["live_count"] == 1


def test_apply_eligible_superseded_old_backup(world):
    write_plist(world["agents"] / "com.balizero.live.plist", "com.balizero.live")
    bak = world["agents"] / "com.balizero.live.plist.bak-old"
    write_plist(bak, "com.balizero.live")
    _old(bak, 60)
    r = run_reconcile(world, loaded=None)
    verdicts = lar.junk_apply_eligibility(r, 30.0, loaded_labels=set())
    assert verdicts == [("com.balizero.live.plist.bak-old", True, "superseded backup")]


def test_apply_protects_young_files(world):
    write_plist(world["agents"] / "com.balizero.live.plist", "com.balizero.live")
    bak = world["agents"] / "com.balizero.live.plist.bak-young"
    write_plist(bak, "com.balizero.live")
    _old(bak, 5)
    r = run_reconcile(world, loaded=None)
    verdicts = lar.junk_apply_eligibility(r, 30.0, loaded_labels=set())
    assert verdicts[0][1] is False


def test_apply_protects_only_copy(world):
    """A backup that is the ONLY on-disk plist for its label may be the sole
    rollback copy of a dismantled (or still loaded!) job — operator decides
    (red-team finding #3)."""
    bak = world["agents"] / "com.balizero.orphan.plist.bak-x"
    write_plist(bak, "com.balizero.orphan")
    _old(bak, 90)
    r = run_reconcile(world, loaded=None)
    verdicts = lar.junk_apply_eligibility(r, 30.0, loaded_labels=set())
    assert verdicts[0][1] is False
    assert "only-copy" in verdicts[0][2]


def test_apply_protects_loaded_source(world):
    """Never delete the file launchd is actually running from (finding #4)."""
    write_plist(world["agents"] / "com.balizero.live.plist", "com.balizero.live")
    bak = world["agents"] / "com.balizero.live.plist.bak-but-loaded-from"
    write_plist(bak, "com.balizero.live")
    _old(bak, 90)
    r = run_reconcile(world, loaded=None)
    verdicts = lar.junk_apply_eligibility(
        r, 30.0,
        loaded_labels={"com.balizero.live"},
        loaded_path_fn=lambda label: str(bak),
    )
    assert verdicts[0][1] is False
    assert "loaded source" in verdicts[0][2]


def test_filename_stamp_beats_lying_old_mtime(world):
    """mtime says 100d old but the filename stamp says yesterday → the file is
    treated as YOUNG (min of the two ages) and protected (finding #9)."""
    write_plist(world["agents"] / "com.balizero.live.plist", "com.balizero.live")
    stamp = (NOW - timedelta(days=1)).strftime("%Y%m%d")
    bak = world["agents"] / f"com.balizero.live.plist.bak-{stamp}"
    write_plist(bak, "com.balizero.live")
    _old(bak, 100)
    r = run_reconcile(world, loaded=None)
    verdicts = lar.junk_apply_eligibility(r, 30.0, loaded_labels=set())
    assert verdicts[0][1] is False


# ─────────────────────────────────────────────────────────────────────────
# launchctl list parsing
# ─────────────────────────────────────────────────────────────────────────

def test_parse_loaded_labels():
    text = "PID\tStatus\tLabel\n123\t0\tcom.balizero.a\n-\t0\tcom.balizero.b\n"
    assert lar.parse_loaded_labels(text) == {"com.balizero.a", "com.balizero.b"}


def test_parse_loaded_labels_garbage_lines():
    assert lar.parse_loaded_labels("random\nnoise here\n") == set()


# ─────────────────────────────────────────────────────────────────────────
# Lenient plist parsing (launchd-parity)
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    __import__("shutil").which("plutil") is None,
    reason="plutil (macOS) not available",
)
def test_parse_plist_tolerates_double_dash_in_xml_comment(tmp_path):
    """Real fleet plists carry `--apply` inside XML comments; expat rejects
    them, launchd loads them. The plutil fallback must keep parity with
    launchd or 5 live agents misclassify as zombies (observed 2026-07-02)."""
    p = tmp_path / "com.balizero.commented.plist"
    p.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- kill switch: remove --apply from ProgramArguments -->\n"
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>'
        "<key>Label</key><string>com.balizero.commented</string>"
        "</dict></plist>\n"
    )
    data = lar.parse_plist(p)
    assert data is not None
    assert data["Label"] == "com.balizero.commented"


def test_parse_plist_genuinely_corrupt_returns_none(tmp_path):
    p = tmp_path / "corrupt.plist"
    p.write_text("this is not xml and not a plist")
    assert lar.parse_plist(p) is None
