"""The guardian must notice when the code WRITING the report is not main's code.

TRAUMA (measured 2026-08-08, PROVE-LIVE of #3826): #3723 and #3826 replaced
`git_alignment`'s remedy — "interactive pull on this machine's main" — with an
explicit "do NOT pull it" plus a read-only path a session can actually run. Both
merged. Yet the report every session reads at boot
(`~/.nuzantara-proprioception/last.json`, surfaced by
`scripts/hooks/proprioception_sessionstart.sh`) still printed the forbidden
prescription, because it had been written by the m5 main checkout — 219 commits
behind, and left behind BY DESIGN (W106b: pulling it races live worktrees).

`probe_guardian_freshness` was watching and structurally could not see it: it asks
"did each guardian speak RECENTLY" (mtime vs max_age_h). That report was 6.7h old,
well inside the 48h gate, so the probe was silent and correct. Freshness of the
OUTPUT says nothing about the version of the WRITER — mtime is a proxy for "current"
and it lies when the writer is old (W88, superscar #9). The machine where that lie
is permanent is exactly the machine nobody was checking.

SECOND DEFECT, found by RUNNING the first cure rather than reading it: it accused any
copy that DIFFERED from origin/main, so the worktree that authored it was told its own
newer code was "OLD text". That is W106b — a comparison knows THAT two copies differ
and never WHICH is stale — re-committed one floor down by the cure for it. Stale is
now claimed only on positive evidence, and "ahead" and "being edited" each get an
innocence case.

THIRD, from an independent adversarial pass (generator != grader): the draft hashed
the FILE PATH at probe time while the claim is about the code that is RUNNING. The
version now comes from `_RUNNER_SHA`, the bytes read at import — pinned by
`test_verdict_follows_the_loaded_bytes_not_the_file_on_disk`, which is red against the
path-hashing draft. The same pass found three determinations being reported where none
had been made (git error read as "not ancestor", shallow clone read as "not ancestor",
a deleted file labelled "stdin"); each has a case below.

Guilt + innocence on every branch per superscar #3 discipline — a guard that reads
"cannot verify" as "clean" is the same disease one floor down (W84).

Run:  python3 -m pytest scripts/tests/test_proprioception_self_code_staleness.py -q
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)

_REL = "scripts/proprioception.py"
_OLD = "# the version a checkout left behind still runs\n"
_MAIN = "# the version main says this file should be\n"


def _blob(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def _git(args: list[str], cwd: Path) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, f"git {args} failed: {out.stderr}"
    return out.stdout.strip()


def test_blob_sha_agrees_with_git_hash_object(tmp_path):
    """The pure-Python hash replaced a `git hash-object` call. If the two ever disagree
    every verdict in this file is meaningless, so prove it against git itself."""
    f = tmp_path / "sample.txt"
    f.write_bytes(b"one line\nand another\n")
    _git(["init", "-q"], tmp_path)
    assert prop._blob_sha(f.read_bytes()) == _git(["hash-object", str(f)], tmp_path)


class Checkout:
    """A checkout with a real two-commit history and a real `refs/remotes/origin/main`.

    The ref is set directly — no network, no remote — but it is the SAME ref
    `git rev-parse origin/main:<path>` reads in production, and the history is real, so
    the ancestor test runs against git rather than a stand-in (W114: a fake at the wrong
    boundary confirms the reader's imagination, not the world).
    """

    def __init__(self, root: Path, old_sha: str, main_sha: str, monkeypatch) -> None:
        self.root, self.old_sha, self.main_sha = root, old_sha, main_sha
        self.script = root / "scripts" / "proprioception.py"
        self._mp = monkeypatch

    def load(self, text: str | None = None) -> None:
        """Set the bytes this 'process' is running — by default whatever is on disk."""
        data = (text.encode() if text is not None else self.script.read_bytes())
        self._mp.setattr(prop, "_RUNNER_SHA", _blob(data))
        self._mp.setattr(prop, "_RUNNER_NO_SHA_REASON", "")

    def go_behind(self) -> None:
        """What m5 looks like: HEAD parked on an older commit of main, tree clean."""
        _git(["checkout", "-q", self.old_sha], self.root)
        self.load()

    def go_ahead(self, text: str = "# a cure being authored in a worktree\n") -> None:
        """What a lane's worktree looks like once it has committed work on top of main."""
        self.script.write_text(text)
        _git(["add", "-A"], self.root)
        _git(["commit", "-qm", "work on top of main"], self.root)
        self.load()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch) -> Checkout:
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "corpus@test.local"], root)
    _git(["config", "user.name", "corpus"], root)
    script = root / "scripts" / "proprioception.py"
    script.write_text(_OLD)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "old version"], root)
    old_sha = _git(["rev-parse", "HEAD"], root)
    script.write_text(_MAIN)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "current version"], root)
    main_sha = _git(["rev-parse", "HEAD"], root)
    _git(["update-ref", "refs/remotes/origin/main", main_sha], root)
    monkeypatch.setattr(prop, "__file__", str(script))
    c = Checkout(root, old_sha, main_sha, monkeypatch)
    c.load()  # healthy default: running exactly what origin/main holds
    return c


# --------------------------------------------------------------- guilt

def test_guilt_a_checkout_parked_behind_main_is_a_finding(repo):
    repo.go_behind()

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 1, "a copy committed at an older point of main IS stale"
    assert ev and ev[0].startswith("SELF STALE:"), ev


def test_guilt_evidence_names_both_sides_and_blames_the_timestamp(repo):
    """The 2026-08-08 report was FRESH and WRONG. The evidence has to say exactly that,
    or the reader trusts the timestamp again — which is the entire defect."""
    repo.go_behind()
    old_blob = _blob(_OLD.encode())
    main_blob = _git(["rev-parse", f"origin/main:{_REL}"], repo.root)

    _, ev = prop._self_code_staleness(repo.root)
    msg = ev[0]

    assert old_blob[:8] in msg and main_blob[:8] in msg, "name BOTH sides, not just 'differs'"
    assert _REL in msg, "name the file, repo-relative"
    assert "however fresh the timestamp" in msg, "the timestamp is what misled the reader"


def test_guilt_remedy_never_prescribes_touching_the_checkout(repo):
    """m5's checkout is deliberately behind (W106b) and #3826 removed the last remedy in
    this file that told a reader to repair it. A new remedy must not put it back."""
    repo.go_behind()

    _, ev = prop._self_code_staleness(repo.root)
    msg = ev[0].lower()

    for forbidden in ("git pull", "git checkout", "git reset", "git restore", "git merge"):
        assert forbidden not in msg, f"remedy prescribes {forbidden!r}: {ev[0]}"
    assert "show origin/main:" in msg, "name the read-only way to main's copy"


def test_verdict_follows_the_loaded_bytes_not_the_file_on_disk(repo):
    """THE TOCTOU PIN (independent review). The claim is about the code that WROTE the
    report, so the version must be the bytes this process loaded. Here a stale runner is
    still executing while the file on disk has already been replaced with main's — the
    path-hashing draft reported a clean bill for a genuinely stale writer."""
    repo.go_behind()                       # HEAD old, running old
    repo.script.write_text(_MAIN)          # disk now holds main's bytes; the process does not

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 1, "hashing the path instead of the loaded bytes hides a stale runner"
    assert _blob(_OLD.encode())[:8] in ev[0], "the running version is what must be named"


# ------------------------------------------------------------ innocence

def test_innocence_copy_identical_to_origin_main_is_silent(repo):
    """The overwhelmingly common case — every worktree freshly cut from main. A probe
    that chirped here would be furniture within a day."""
    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0
    assert ev == [], f"an up-to-date copy must produce no evidence at all, got {ev}"


def test_innocence_a_branch_ahead_of_main_is_never_called_stale(repo):
    """THE REGRESSION PIN. The first draft of this cure accused the very worktree that
    authored it: differing from origin/main is not being behind it (W106b)."""
    repo.go_ahead()

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0, "an AHEAD copy must never be reported as stale"
    assert "not an ancestor" in ev[0], ev
    assert "SELF STALE" not in ev[0]


def test_innocence_uncommitted_edits_are_work_not_staleness(repo):
    """Mid-edit is the normal state of the file a session is changing."""
    repo.script.write_text("# half-written change\n")
    repo.load()

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0
    assert "UNCOMMITTED edits" in ev[0], ev


def test_innocence_edited_back_to_mains_content_is_current(repo):
    """Judged by CONTENT, never by 'is the tree dirty' (W88): a file edited and edited
    back is current, whatever git status says."""
    repo.script.write_text("# scratch\n")
    repo.script.write_text(_MAIN)
    repo.load()

    assert prop._self_code_staleness(repo.root) == (0, [])


# --------------------------------------------- cannot-verify (evidence, never a finding)

def test_cannot_verify_copy_outside_the_checkout(repo, tmp_path, monkeypatch):
    """What an out-of-tree run looks like — including the very command this probe's own
    remedy prescribes (`git show origin/main:... > /tmp/x.py && python3 /tmp/x.py`).
    Calling that stale would be the probe accusing its own cure."""
    outside = tmp_path / "prop_main.py"
    outside.write_text("# main's copy, run from /tmp on purpose\n")
    monkeypatch.setattr(prop, "__file__", str(outside))
    repo.load("# main's copy, run from /tmp on purpose\n")

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0
    assert "outside the checkout" in ev[0], ev


def test_cannot_verify_no_origin_main_ref_is_not_silence(repo):
    """Offline is a natural state (Law 6), so it is not a finding. But it must still be
    SAID: 'could not check' read as 'clean' is the calm liar (W84)."""
    _git(["update-ref", "-d", "refs/remotes/origin/main"], repo.root)

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0, "unreachable origin must never be reported as drift (W106b)"
    assert ev and "cannot compare" in ev[0], f"cannot-verify must be stated, got {ev}"


def test_cannot_verify_running_from_stdin(repo, monkeypatch):
    """`git show origin/main:... | python3 -` leaves no `__file__` at all."""
    monkeypatch.setattr(prop, "_RUNNER_SHA", "")
    monkeypatch.setattr(prop, "_RUNNER_NO_SHA_REASON", "stdin")

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0
    assert "stdin" in ev[0] and "no source bytes" in ev[0], ev


def test_cannot_verify_unreadable_is_not_reported_as_stdin(repo, monkeypatch):
    """A source file that could not be read is a blind spot, not the deliberate
    run-main's-copy escape. Naming one for the other invents a state (W113)."""
    monkeypatch.setattr(prop, "_RUNNER_SHA", "")
    monkeypatch.setattr(prop, "_RUNNER_NO_SHA_REASON", "unreadable")

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0
    assert "unreadable" in ev[0] and "stdin" not in ev[0], ev


def test_cannot_verify_no_repo_root():
    findings, ev = prop._self_code_staleness(None)
    assert findings == 0
    assert "cannot be attributed" in ev[0], ev


def test_cannot_verify_file_not_readable_at_head(repo):
    """Present on disk but absent from HEAD: the direction is unknowable, and the draft
    asserted "UNCOMMITTED edits", a cause it had not established.

    The first version of this test used `git rm --cached` alone and did NOT reproduce it:
    that touches the index, while `rev-parse HEAD:<path>` reads the commit — so HEAD
    still had the file and "UNCOMMITTED edits" was the correct answer. The removal has to
    be committed."""
    repo.script.write_text(_OLD)
    repo.load()
    _git(["rm", "-q", "--cached", _REL], repo.root)
    _git(["commit", "-qm", "untrack the runner"], repo.root)

    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0
    assert "not readable at this HEAD" in ev[0], ev


def test_cannot_verify_shallow_clone_does_not_read_as_not_stale(repo, monkeypatch):
    """On a shallow clone a TRUE ancestor answers `1`, so "not an ancestor" would be a
    false clean for a genuinely behind copy — the dangerous direction."""
    repo.go_behind()
    real_sh = prop.sh

    def fake_sh(argv, **kw):
        if argv[:2] == ["git", "merge-base"]:
            return 1, "", ""                       # what a truncated history answers
        if argv[:2] == ["git", "rev-parse"] and "--is-shallow-repository" in argv:
            return 0, "true\n", ""
        return real_sh(argv, **kw)

    monkeypatch.setattr(prop, "sh", fake_sh)
    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0, "still not an accusation — but it must not read as clean either"
    assert "SHALLOW" in ev[0] and "direction unknown" in ev[0], ev


def test_cannot_verify_git_error_is_not_read_as_not_ancestor(repo, monkeypatch):
    """`--is-ancestor` returns 1 for a valid "no" and >1 for failure. Collapsing them
    reports a determination that was never made (W84)."""
    repo.go_behind()
    real_sh = prop.sh

    def fake_sh(argv, **kw):
        if argv[:2] == ["git", "merge-base"]:
            return 128, "", "fatal: bad object"
        return real_sh(argv, **kw)

    monkeypatch.setattr(prop, "sh", fake_sh)
    findings, ev = prop._self_code_staleness(repo.root)

    assert findings == 0
    assert "could not decide ancestry" in ev[0] and "exit 128" in ev[0], ev
    assert "not an ancestor" not in ev[0], "that is a verdict we did not reach"


# ------------------------------------------------- wiring into the probe's verdict

def test_stale_self_survives_the_no_guardians_shortcut(repo):
    """`seen == 0 and findings == 0 -> UNPROBEABLE` used to REPLACE the evidence list.
    A machine with no guardian outputs must still hear that its guardian is stale."""
    repo.go_behind()

    status, findings, ev = prop.probe_guardian_freshness(repo.root, {"items": []}, 30)

    assert status == prop.DIVERGED
    assert findings == 1
    assert ev[0].startswith("SELF STALE:")


def test_no_guardians_and_current_self_still_reports_unprobeable(repo):
    """Innocence for the branch above: nothing to see must read as 'I saw nothing', not
    as 'all clear'."""
    status, findings, ev = prop.probe_guardian_freshness(repo.root, {"items": []}, 30)

    assert status == prop.UNPROBEABLE
    assert findings == 0
    assert any("no guardian outputs found" in line for line in ev)


def test_cannot_verify_survives_the_no_guardians_shortcut(repo):
    """The shortcut must APPEND to the evidence, not replace it — otherwise the one
    combination that matters most (no guardian outputs AND an unverifiable guardian
    version) prints only "no guardian outputs found" and reads as the tidy case."""
    _git(["update-ref", "-d", "refs/remotes/origin/main"], repo.root)

    status, findings, ev = prop.probe_guardian_freshness(repo.root, {"items": []}, 30)

    assert status == prop.UNPROBEABLE and findings == 0
    assert any("cannot compare" in line for line in ev), f"cannot-verify was swallowed: {ev}"


def test_self_finding_leads_the_evidence_ahead_of_item_findings(repo, tmp_path):
    """The receptor prints `evidence[0]`. Whichever line is first IS the message a
    session reads at boot — and "the whole report is old text" outranks any one item."""
    repo.go_behind()
    stale_output = tmp_path / "some-guardian.json"
    stale_output.write_text("{}")
    os.utime(stale_output, (0, 0))  # 1970: unambiguously past any max_age_h

    _, findings, ev = prop.probe_guardian_freshness(
        repo.root, {"items": [{"glob": str(stale_output), "max_age_h": 1, "label": "other"}]}, 30)

    assert findings == 2, "both the stale item and the stale self must count"
    assert ev[0].startswith("SELF STALE:"), f"self-version must lead, got {ev[0]!r}"


# ------------------------------------------- the remedy printed under the finding

_REGISTRY_HINT = "a stale guardian: run it by hand, read ITS log, then fix its scheduler"


def test_guilt_self_stale_does_not_get_the_scheduler_remedy():
    """Two diseases now share one probe id and their cures are opposite. A stale RUNNER
    ran perfectly on time — telling its reader to fix the scheduler is the handoff-§6
    defect verbatim: a remedy that contradicts its own finding."""
    entry = {"id": "guardian_freshness", "fix_hint": _REGISTRY_HINT}
    ev = ["SELF STALE: the copy that wrote this report (scripts/proprioception.py aaaaaaaa) …"]

    hint = prop._guardian_freshness_remedy(entry, ev)

    assert hint != _REGISTRY_HINT
    assert "schedule is not the problem" in hint.lower(), "must absolve the scheduler explicitly"
    assert "do not repair the checkout" in hint.lower()


def test_innocence_a_stale_output_still_gets_the_registry_remedy():
    """The original disease keeps its original cure, byte-identical — an override that
    swallows the case it was not written for is a guard over-matching (#3)."""
    entry = {"id": "guardian_freshness", "fix_hint": _REGISTRY_HINT}
    ev = ["proprioception (self): guardian last spoke 60.0h ago (max 48h) — a stale guardian is a lying guardian"]

    assert prop._guardian_freshness_remedy(entry, ev) == _REGISTRY_HINT


def test_innocence_no_evidence_at_all_gets_the_registry_remedy():
    entry = {"id": "guardian_freshness", "fix_hint": _REGISTRY_HINT}
    assert prop._guardian_freshness_remedy(entry, []) == _REGISTRY_HINT


# --------------------------------------------------------------- provenance field

def test_self_blob_is_the_loaded_bytes(repo, monkeypatch):
    monkeypatch.setattr(prop, "_RUNNER_SHA", _blob(b"whatever this process loaded\n"))
    assert prop._self_blob() == _blob(b"whatever this process loaded\n")[:12]


def test_self_blob_names_the_reason_rather_than_guessing(repo, monkeypatch):
    """"stdin" for a file that was merely deleted is a fabricated state — the reason has
    to be the one actually observed."""
    monkeypatch.setattr(prop, "_RUNNER_SHA", "")
    for reason in ("stdin", "unreadable"):
        monkeypatch.setattr(prop, "_RUNNER_NO_SHA_REASON", reason)
        assert prop._self_blob() == reason


def test_report_carries_the_blob_of_the_file_that_ran(repo):
    """End-to-end, and DISCRIMINATING: the earlier version of this test only asserted
    non-empty, which a constant would satisfy. It must equal the real hash of the real
    script the subprocess executed."""
    env = dict(os.environ, NUZ_REPO_ROOT=str(repo.root))
    out = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--json", "--no-report", "--no-fetch",
         "--probes", "guardian_freshness"],
        capture_output=True, text=True, timeout=120, cwd=str(repo.root), env=env)
    assert out.returncode == 0, out.stderr
    report = json.loads(out.stdout)

    assert report["runner_blob"] == _blob(_MODULE_PATH.read_bytes())[:12]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
