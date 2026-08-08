"""The organ must audit every payload it EXECUTES, not only the one it is.

TRAUMA (measured 2026-08-08): the previous PR taught `proprioception.py` to notice when
its OWN copy is behind origin/main. That closed one member of a class. Seven registry
entries are `wrap` probes that shell out to OTHER scripts in the same tree; six of them
are in m5's jurisdiction, and on m5 — whose checkout is deliberately never pulled
(W106b) — THREE of those six were behind: `launchagent_reconcile.py`,
`launchd_liveness_detector.py`, `organism_stale_detector.py`.

`arsenal_probe.py` is behind too, and is deliberately NOT counted: its wrap is scoped
`["mini", "pro"]`, so m5 never executes it, and the hosts that do measured 0/7 diverging
the same day. Counting it read 4-of-7 and was a finding no one on this host could act
on — the first draft did exactly that.

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
  - the repo-relative paths are found by SCANNING the whole target list for `{repo}/`
    tokens — ALL of them, not element 1 and not just the first match: position is a form,
    the token is the entity (#3), and stopping at the first is the same error inverted.
  - direction is decided per PATH against the merge-base blob, never by asking whether
    the BRANCH is an ancestor of origin/main. One unrelated local commit makes that proxy
    answer "not an ancestor", which the first draft read as "ahead, not stale" — a
    false-clean of exactly the class this probe exists to catch (W88).

Run:  python3 -m pytest scripts/tests/test_proprioception_executed_code_currency.py -q
"""
from __future__ import annotations

import hashlib
import json
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
    assert prop._wrap_repo_targets({"type": "wrap", "target": ["python3", "-u", "{repo}/a/b.py"]}) == ["a/b.py"]
    assert prop._wrap_repo_targets({"type": "wrap", "target": ["{repo}/x.py", "--flag"]}) == ["x.py"]


def test_every_repo_target_is_returned_not_only_the_first():
    """`["pytest", "{repo}/a.py", "{repo}/b.py"]` executes BOTH. Returning the first is
    the position mistake wearing the other sleeve: the second payload goes unaudited and
    the probe reads clean."""
    got = prop._wrap_repo_targets({"type": "wrap", "target": ["pytest", "{repo}/a.py", "{repo}/b.py"]})
    assert got == ["a.py", "b.py"]


def test_a_string_target_is_normalised_not_iterated_character_by_character():
    """`validate_registry` does not forbid a bare string, and iterating one yields single
    characters — none of which start with `{repo}/`, so the entry would drop out of the
    audit leaving no trace at all."""
    assert prop._wrap_repo_targets({"type": "wrap", "target": "{repo}/scripts/tool.py"}) == ["scripts/tool.py"]


def test_non_wrap_and_targetless_entries_are_skipped():
    assert prop._wrap_repo_targets({"type": "builtin", "target": "git_alignment"}) == []
    assert prop._wrap_repo_targets({"type": "wrap", "target": ["python3", "/abs/path.py"]}) == []
    assert prop._wrap_repo_targets({"type": "wrap", "target": {"not": "a list"}}) == []


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
    Calling the engine directly proves nothing about the twins, so this asserts that BOTH
    entry points route through it: reinstating a hand-written copy inside
    `_self_code_staleness` must turn this red."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)
    sha = _blob((repo / _TARGET).read_bytes())
    assert prop._version_vs_main(repo, _TARGET, sha) == (
        prop.STALE, _git(["rev-parse", f"origin/main:{_TARGET}"], repo))

    calls: list[tuple] = []
    real = prop._version_vs_main
    prop._version_vs_main = lambda r, rel, s: (calls.append((rel, s)), real(r, rel, s))[1]
    try:
        prop.probe_executed_code_currency(repo, {}, 30)
        payload_calls = len(calls)
        # The self-check can only reach the engine when the runner really sits inside the
        # root it is given, so hand it THIS worktree rather than the fixture.
        prop._self_code_staleness(_MODULE_PATH.parents[1])
    finally:
        prop._version_vs_main = real

    assert payload_calls >= 1, "the payload probe must reach the shared engine"
    assert len(calls) > payload_calls, (
        "_self_code_staleness did not call _version_vs_main — it is carrying its own copy "
        "of the comparison again, which is exactly how the twins drifted apart")
    assert calls[-1][0].endswith("proprioception.py"), calls[-1]


def test_a_stale_payload_on_a_diverged_branch_is_not_silenced_as_ahead(repo):
    """THE false-clean this probe exists to prevent, and the shape the first draft got
    wrong. One local commit touching an UNRELATED file makes `merge-base --is-ancestor
    HEAD origin/main` answer "no" — read as "ahead, not stale" — while the audited file
    is exactly the version main replaced. Direction is a question about the PATH."""
    _git(["checkout", "-q", "-b", "side", prop._TEST_OLD_SHA], repo)
    (repo / "UNRELATED.md").write_text("a local commit that touches nothing audited\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-qm", "unrelated local work"], repo)
    assert subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"],
                          cwd=repo, capture_output=True).returncode == 1, "premise: HEAD is NOT an ancestor"

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 1 and status == prop.DIVERGED, f"silenced as 'ahead': {ev}"
    assert ev[0].startswith("STALE PAYLOAD:")


def test_innocence_a_locally_committed_change_to_the_payload_is_ahead_not_stale(repo):
    """The other side of the same coin: when THIS side is the one that moved the file,
    silence is the truth. Without this, the fix above would just invert the bug."""
    _git(["checkout", "-q", "-b", "mine"], repo)
    (repo / _TARGET).write_text("# our own newer code\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-qm", "local change to the payload itself"], repo)

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 0 and ev == [], f"our own committed code is not stale, got {ev}"


def test_a_wrap_outside_this_machines_jurisdiction_is_not_audited(repo, monkeypatch):
    """`arsenal_seats` is mini/pro-only, so on m5 its payload is never executed — a
    STALE finding there is a P1 nobody on that host can act on, and the host that DOES
    run it audits it itself. Measured: this alone moved the live m5 count from 4 to 3."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)
    monkeypatch.setattr(prop, "DEFAULT_REGISTRY", [{**_ENTRY, "machines": ["somewhere-else"]}])
    monkeypatch.setattr(prop, "machine_label", lambda: "m5")

    status, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 0
    assert not any("STALE PAYLOAD" in line for line in ev), ev
    assert status == prop.UNPROBEABLE, "nothing in jurisdiction must not read as nothing wrong"


def test_a_wrap_in_jurisdiction_by_explicit_name_is_audited(repo, monkeypatch):
    """Innocence for the jurisdiction filter itself — it must not swallow the entries it
    is supposed to keep. An exemption is a guard with the sign flipped (W91/W94)."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)
    monkeypatch.setattr(prop, "DEFAULT_REGISTRY", [{**_ENTRY, "machines": ["m5"]}])
    monkeypatch.setattr(prop, "machine_label", lambda: "m5")

    _s, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 1, f"an in-jurisdiction stale payload must still be named: {ev}"


def test_the_loaded_registry_is_audited_not_the_embedded_default(repo, monkeypatch):
    """`main()` runs whatever `config/boundaries.json` says. Auditing DEFAULT_REGISTRY
    would report on payloads nobody executes and stay silent about the ones they do."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)
    (repo / "config").mkdir(exist_ok=True)
    (repo / "config" / "boundaries.json").write_text(json.dumps(
        {"probes": [{"id": "from_config", "type": "wrap",
                     "target": ["python3", "{repo}/" + _TARGET]}]}))
    monkeypatch.setattr(prop, "DEFAULT_REGISTRY", [])

    _s, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 1 and "from_config" in ev[0], ev


def test_a_tracked_symlink_is_hashed_as_git_stores_it(repo):
    """git stores a symlink's LINK TEXT; `read_bytes()` follows it and hashes the
    referent. Comparing those two representations makes a genuinely stale symlink look
    like uncommitted edits — which this probe deliberately keeps silent."""
    link = repo / "scripts" / "linked_tool.py"
    (repo / "scripts" / "real_new.py").write_text("new\n")
    link.symlink_to("real_new.py")
    _git(["add", "scripts/linked_tool.py"], repo)
    # `git hash-object <path>` FOLLOWS the link, so it is not the oracle here; the index
    # holds what git actually stores for a symlink, which is the link text.
    stored = _git(["rev-parse", ":scripts/linked_tool.py"], repo)

    assert prop._disk_blob(link) == stored
    assert prop._disk_blob(link) != _blob(b"new\n"), "hashed the referent, not the link"


def test_cannot_verify_a_failed_shallow_probe_is_not_read_as_a_whole_history(repo, monkeypatch):
    """If git cannot say whether the clone is truncated, we have not established that the
    history is whole — and answering 'ahead, not stale' on that is the calm liar (W84)."""
    _git(["checkout", "-q", prop._TEST_OLD_SHA], repo)
    real_sh = prop.sh
    monkeypatch.setattr(prop, "sh", lambda a, **k: (
        (128, "", "boom") if a[:3] == ["git", "rev-parse", "--is-shallow-repository"] else real_sh(a, **k)))

    _s, findings, ev = prop.probe_executed_code_currency(repo, {}, 30)

    assert findings == 0, "an undecidable direction is never a finding"
    assert "shallow" in ev[0] and "direction unknown" in ev[0], ev


def test_registry_entry_is_registered_and_valid():
    """The probe exists AND the registry admits it — built is not armed (W81). The
    selftest is the organ's own validator, so run it rather than re-implementing it."""
    ids = [e["id"] for e in prop.DEFAULT_REGISTRY]
    assert "executed_code_currency" in ids
    assert prop.validate_registry(prop.DEFAULT_REGISTRY) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
