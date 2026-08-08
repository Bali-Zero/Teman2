"""The organ must audit every payload it EXECUTES, not only the one it is.

TRAUMA (measured 2026-08-08): the previous PR taught `proprioception.py` to notice when
its OWN copy is behind origin/main. That closed one member of a class. Seven registry
entries are `wrap` probes that shell out to OTHER scripts in the same tree, and on m5 —
whose checkout is deliberately never pulled (W106b) — four of them were behind:
`arsenal_probe.py` (3 commits), `launchagent_reconcile.py` (2),
`launchd_liveness_detector.py` (1), `organism_stale_detector.py` (1).

One was demonstrably lying, and the A/B was controlled — same machine, same
~/Library/LaunchAgents, same minute: the checkout's reconciler reported
`repo_divergent: 1`, origin/main's reported `0`, and the single plist it named was the
one §5b of the handoff dossier had already closed. The organ executed the pre-cure
script and faithfully printed its pre-cure verdict.

Curing the runner and calling the disease closed is W107 — "I cured one wrapper of five,
and the cure went to the smallest one".

Two design rules this corpus pins:
  - judged by BLOB, never by running the target. An alarm that executes the code whose
    health it reports shares that code's failure mode (W108).
  - the repo-relative path is found by SCANNING the target list for the `{repo}/` token,
    not by indexing element 1 — position is a form, the token is the entity (#3).

Run:  python3 -m pytest scripts/tests/test_proprioception_executed_code_currency.py -q
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)

_TARGET = "scripts/tool_under_audit.py"
_OLD = "# the version a never-pulled checkout still executes\n"
_MAIN = "# the version origin/main holds\n"


def _blob(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def _git(args: list[str], cwd: Path) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, f"git {args} failed: {out.stderr}"
    return out.stdout.strip()


_ENTRY = {
    "id": "tool_probe", "type": "wrap",
    "target": ["python3", "{repo}/" + _TARGET, "--json"],
}


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch) -> Path:
    """A checkout whose origin/main holds a NEWER version of one wrap target."""
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "corpus@test.local"], root)
    _git(["config", "user.name", "corpus"], root)
    tool = root / _TARGET
    tool.write_text(_OLD)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "old"], root)
    old_sha = _git(["rev-parse", "HEAD"], root)
    tool.write_text(_MAIN)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "current"], root)
    _git(["update-ref", "refs/remotes/origin/main", _git(["rev-parse", "HEAD"], root)], root)
    monkeypatch.setattr(prop, "DEFAULT_REGISTRY", [_ENTRY])
    root_old = old_sha
    monkeypatch.setattr(prop, "_TEST_OLD_SHA", root_old, raising=False)
    return root


# ----------------------------------------------------- target resolution (entity, not position)

def test_target_is_found_by_token_not_by_position():
    """A wrap may carry flags before the path. Indexing element 1 would silently audit
    `--json` — or nothing — the moment someone reorders a target list."""
    assert prop._wrap_repo_target({"type": "wrap", "target": ["python3", "-u", "{repo}/a/b.py"]}) == "a/b.py"
    assert prop._wrap_repo_target({"type": "wrap", "target": ["{repo}/x.py", "--flag"]}) == "x.py"


def test_non_wrap_and_targetless_entries_are_skipped():
    assert prop._wrap_repo_target({"type": "builtin", "target": "git_alignment"}) is None
    assert prop._wrap_repo_target({"type": "wrap", "target": ["python3", "/abs/path.py"]}) is None


# --------------------------------------------------------------- guilt

def test_guilt_a_behind_payload_is_a_finding_that_names_the_probe(repo, monkeypatch):
    """The useful part is not "a file is old" — it is WHICH verdict on this report came
    from the old file."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert status == prop.DIVERGED and findings == 1
    assert ev[0].startswith("STALE PAYLOAD:")
    assert "tool_probe" in ev[0], "name the probe whose verdict is affected"
    assert _blob(_OLD.encode())[:8] in ev[0] and _blob(_MAIN.encode())[:8] in ev[0]
    assert "however fresh the report" in ev[0], "freshness is exactly what misleads here"


def test_guilt_does_not_execute_the_target(repo, monkeypatch):
    """W108: an alarm must not run the code whose staleness it reports. The target here
    would kill the test process if executed."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)
    (repo / _TARGET).write_text("import os, sys\nsys.exit(99)\nos._exit(99)\n")
    calls: list[list[str]] = []
    real_sh = prop.sh
    monkeypatch.setattr(prop, "sh", lambda a, **k: (calls.append(a), real_sh(a, **k))[1])

    prop.probe_executed_code_currency(repo, {}, 30)

    assert calls, "the probe must talk to git at all"
    assert all(a[0] == "git" for a in calls), f"the probe shelled out to a non-git command: {calls}"


# ------------------------------------------------------------ innocence

def test_innocence_a_current_checkout_is_completely_silent(repo):
    """pro/mini are 0 behind (measured 2026-08-08, 0/8 stale). A probe that spoke here
    would be a permanent P1 on two of the three machines."""
    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert status == prop.RECONCILED and findings == 0
    assert ev == [], f"a current tree must produce no evidence at all, got {ev}"


def test_innocence_uncommitted_edits_are_silent_here(repo):
    """DELIBERATE DIVERGENCE from the self-version check, which DOES print a line for an
    edited copy. There, one file means one line of context. Here, seven payloads means
    seven "someone is editing this" lines on every developer machine, every run — the
    kind of furniture that trains a reader to skip the whole probe. EDITED and AHEAD are
    positive determinations of "not stale", so silence states the truth; only
    UNVERIFIABLE (below) has to speak, because that is the one that must never read as
    clean (W84)."""
    (repo / _TARGET).write_text("# someone is editing this right now\n")

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 0 and status == prop.RECONCILED
    assert ev == [], f"an edited payload is not stale and must not chatter, got {ev}"


# --------------------------------------------- cannot-verify (evidence, never a finding)

def test_cannot_verify_missing_target_is_stated_not_swallowed(repo):
    """A wrap pointing at a path that is not on disk is armed to nothing (W81) — and
    reading that as "current" would be the calm liar (W84)."""
    (repo / _TARGET).unlink()

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 0
    assert "unreadable on disk" in ev[0] and "tool_probe" in ev[0], ev


def test_cannot_verify_no_origin_main_ref(repo):
    _git(["update-ref", "-d", "refs/remotes/origin/main"], repo)

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 0
    assert "cannot compare" in ev[0], ev


def test_registry_without_wrap_targets_reads_unprobeable_not_clean(repo, monkeypatch):
    monkeypatch.setattr(prop, "DEFAULT_REGISTRY", [{"type": "builtin", "target": "git_alignment"}])

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert status == prop.UNPROBEABLE, "nothing seen must not read as nothing wrong"
    assert findings == 0


# ------------------------------------------------- the shared engine, not a second copy

def test_self_and_payload_checks_use_the_same_engine(repo):
    """W106b's fourth layer was two 'twins with the same logic' where only one was cured.
    Both callers must reach the same verdict for the same inputs."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)
    sha = _blob((repo / _TARGET).read_bytes())

    state, detail = prop._version_vs_main(repo, _TARGET, sha)

    assert state == prop.STALE
    assert detail == _git(["rev-parse", f"origin/main:{_TARGET}"], repo)


def test_registry_entry_is_registered_and_valid():
    """The probe exists AND the registry admits it — built is not armed (W81). The
    selftest is the organ's own validator, so run it rather than re-implementing it."""
    ids = [e["id"] for e in prop.DEFAULT_REGISTRY]
    assert "executed_code_currency" in ids
    assert prop.validate_registry(prop.DEFAULT_REGISTRY) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
