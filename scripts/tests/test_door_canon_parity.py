"""Guilt + innocence for the door-parity probe.

WHY IT EXISTS. The CI and repo layer already binds every model equally — a gate
does not ask which family opened the PR. The HARNESS layer did not: each CLI
auto-loads its own door (`CLAUDE.md` for Claude, `AGENTS.md` for Codex and Kimi,
`GEMINI.md` for agy, `QWEN.md` for the Token Plan wing) and nothing had ever
compared them. A seat that BUILDS started with whatever its own door said.

Measured on `origin/main` 2026-08-31, before this lane: `grep -c 'CANON:'`
returned 0 in all three existing doors, and `QWEN.md` was not tracked at all —
so the Qwen seat opened no door whatsoever.

Every case here builds a synthetic repo under tmp_path and `git init`s it. The
real doors are read by exactly ONE test, the live pin at the bottom, which is
the arming: it goes red if a future edit lets one door's block drift.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "proprioception", Path(__file__).resolve().parents[1] / "proprioception.py"
)
assert _SPEC and _SPEC.loader
pp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pp)

ROOT = Path(__file__).resolve().parents[2]
BLOCK = (
    "<!-- CANON:builder-contract -->\n"
    "\n"
    "One PR, one concern. Never merge your own work.\n"
    "\n"
    "<!-- /CANON:builder-contract -->\n"
)


def _repo(
    tmp_path: Path, doors: dict[str, str], *, untracked: tuple[str, ...] = ()
) -> Path:
    """A git repo holding `doors` (name -> full text). Names in `untracked` are
    written to disk but kept OUT of the index — the shape that matters on a
    case-insensitive volume, where the filesystem answers for a name git does
    not have."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, text in doors.items():
        (tmp_path / name).write_text(text)
    tracked = [n for n in doors if n not in untracked]
    if tracked:
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "--", *tracked],
            check=True,
            capture_output=True,
        )
    return tmp_path


def _door(body: str = "", *, block: str | None = BLOCK) -> str:
    return f"# a door\n\nsome preamble\n\n{block or ''}\n## section\n\n{body}\n"


def _probe(root: Path, **args):
    return pp.probe_door_canon_parity(root, args, 15)


ALL_FOUR = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md")


# --------------------------------------------------------------- innocence


def test_four_identical_blocks_are_silent(tmp_path: Path) -> None:
    root = _repo(tmp_path, {n: _door() for n in ALL_FOUR})
    status, n, ev = _probe(root)
    assert status == pp.RECONCILED, ev
    assert n == 0
    assert "identical across CLAUDE.md and 3 other door(s)" in "\n".join(ev)


def test_text_OUTSIDE_the_block_may_differ_freely(tmp_path: Path) -> None:
    """The doors are SUPPOSED to differ — each carries its own CLI's invocation,
    model roster and sandbox flags. A probe that alarmed on those would be
    switched off within a week, so only the marked region is compared."""
    root = _repo(
        tmp_path,
        {
            "CLAUDE.md": _door("claude-specific: /model, skills, hooks"),
            "AGENTS.md": _door("codex-specific: --sandbox workspace-write"),
            "GEMINI.md": _door("agy-specific: --effort high, 1M context"),
            "QWEN.md": _door("token-plan-specific: DashScope base url"),
        },
    )
    assert _probe(root)[0] == pp.RECONCILED


def test_whitespace_only_difference_is_not_drift(tmp_path: Path) -> None:
    """Line endings differ between editors and machines; treating CRLF as doctrine
    drift would bury the first real finding in a crowd of false ones.

    TWO BOUNDARIES this fixture had to learn, one of them a real cost:
    - Only TRAILING whitespace is normalised. Widening a gap INSIDE a sentence is
      a content change and stays a finding — the first draft inserted spaces
      mid-line and read DIVERGED, correctly.
    - DECLARED COST (codex gpt-5.6-sol, 2026-08-31): TWO trailing spaces are a
      Markdown hard line break, so the normaliser erases a difference that a
      renderer honours. This fixture deliberately uses CRLF rather than trailing
      spaces, so it cannot be read as blessing that case. Tightening the rule is
      not this lane's to make — `_canon_blocks` is shared with the fleet
      comparator and the publisher, and changing it here would change all three."""
    doors = {n: _door() for n in ALL_FOUR}
    doors["GEMINI.md"] = doors["GEMINI.md"].replace(
        "One PR, one concern. Never merge your own work.\n",
        "One PR, one concern. Never merge your own work.\r\n",
    )
    assert _probe(_repo(tmp_path, doors))[0] == pp.RECONCILED


# ----------------------------------------------------------------- guilt


def test_a_reworded_rule_in_ONE_door_is_a_finding(tmp_path: Path) -> None:
    doors = {n: _door() for n in ALL_FOUR}
    doors["AGENTS.md"] = doors["AGENTS.md"].replace(
        "One PR, one concern.", "One PR, several concerns."
    )
    status, n, ev = _probe(_repo(tmp_path, doors))
    assert status == pp.DIVERGED, ev
    assert n == len(ev) > 0, (
        n,
        ev,
    )  # the count must match the evidence, not merely be truthy
    joined = "\n".join(ev)
    assert "differs between AGENTS.md and CLAUDE.md" in joined, joined


def test_a_door_MISSING_the_block_is_a_finding(tmp_path: Path) -> None:
    doors = {n: _door() for n in ALL_FOUR}
    doors["GEMINI.md"] = _door(block=None)
    status, n, ev = _probe(_repo(tmp_path, doors))
    assert status == pp.DIVERGED, ev
    assert "ABSENT from GEMINI.md" in "\n".join(ev)


def test_a_rule_binding_ONE_SEAT_ONLY_is_a_finding(tmp_path: Path) -> None:
    """The comparison is not one-way. A block that exists in a peer and not in
    the reference is doctrine that binds one seat and not the others, which is
    the disease this probe is named after — not a peer being helpfully extra."""
    doors = {n: _door() for n in ALL_FOUR}
    doors["QWEN.md"] = doors["QWEN.md"].replace(
        "<!-- /CANON:builder-contract -->",
        "<!-- /CANON:builder-contract -->\n\n<!-- CANON:qwen-only -->\nextra rule\n<!-- /CANON:qwen-only -->",
    )
    status, n, ev = _probe(_repo(tmp_path, doors))
    assert status == pp.DIVERGED, ev
    assert "in QWEN.md but ABSENT from CLAUDE.md" in "\n".join(ev)


def test_a_door_GIT_DOES_NOT_TRACK_is_a_finding_even_though_the_shell_sees_it(
    tmp_path: Path,
) -> None:
    """THE CASE TRAP, and the reason this probe asks git instead of the
    filesystem. On the APFS default `[ -f QWEN.md ]`, `ls` and `wc` all answer
    for a lowercase `qwen.md`: measured 2026-08-31, the two names shared inode
    343120045 on this machine while git's index held only the lowercase one. A
    check written against the filesystem passes on every Mac in this fleet while
    the Qwen seat still opens no door on a Linux runner."""
    doors = {n: _door() for n in ALL_FOUR if n != "QWEN.md"}
    doors["qwen.md"] = _door()  # the LOWERCASE name is what git will track
    root = _repo(tmp_path, doors)

    # THE PREMISE, asserted rather than assumed — this is the whole test. On a
    # case-insensitive volume the uppercase lookup SUCCEEDS (it resolves to the
    # lowercase file), while git, asked for the uppercase name, has nothing.
    # A generic "is it tracked" check passes a fixture that merely leaves an
    # uppercase file untracked; only this shape proves the CASE fix.
    assert (root / "QWEN.md").is_file(), (
        "this volume is case-SENSITIVE, so the trap under test cannot occur here; "
        "the assertion below would pass for the wrong reason"
    )
    tracked = pp._git_tracked_names(root, ["QWEN.md", "qwen.md"], 15)
    assert tracked == {"qwen.md"}, tracked

    status, n, ev = _probe(root)
    assert status == pp.DIVERGED, ev
    assert n > 0, (status, n, ev)
    assert "QWEN.md is not tracked" in "\n".join(ev)


def test_a_malformed_marker_in_the_REFERENCE_is_a_finding(tmp_path: Path) -> None:
    """A malformed marker in the reference silently removes that rule from every
    comparison at once — the cheapest possible way to stop comparing without
    deleting anything."""
    doors = {n: _door() for n in ALL_FOUR}
    doors["CLAUDE.md"] = doors["CLAUDE.md"].replace(
        "<!-- /CANON:builder-contract -->", ""
    )
    status, n, ev = _probe(_repo(tmp_path, doors))
    assert status == pp.DIVERGED, ev
    assert "malformed in CLAUDE.md" in "\n".join(ev)


def test_no_markers_anywhere_reads_UNPROBEABLE_not_agreement(tmp_path: Path) -> None:
    """Four doors containing zero blocks 'agreeing' would be the purest instance
    of the disease this probe exists to detect."""
    root = _repo(tmp_path, {n: _door(block=None) for n in ALL_FOUR})
    status, n, ev = _probe(root)
    assert status == pp.UNPROBEABLE, ev
    assert "no rule is declared binding across doors yet" in "\n".join(ev)


def test_a_reference_whose_markers_are_all_FENCED_says_so(tmp_path: Path) -> None:
    """'Nobody has marked the block' and 'you marked it inside a code fence' need
    different remedies and would otherwise produce the same sentence."""
    fenced = "# a door\n\n```markdown\n" + BLOCK + "```\n\n## section\n"
    root = _repo(tmp_path, {n: fenced for n in ALL_FOUR})
    status, n, ev = _probe(root)
    assert status == pp.UNPROBEABLE
    assert "inside fenced code blocks" in "\n".join(ev)


def test_an_absent_reference_door_is_UNPROBEABLE_not_agreement(tmp_path: Path) -> None:
    doors = {n: _door() for n in ALL_FOUR if n != "CLAUDE.md"}
    status, n, ev = _probe(_repo(tmp_path, doors))
    assert status == pp.UNPROBEABLE, ev
    assert "reference door CLAUDE.md is not tracked" in "\n".join(ev)


# --------------------------------------------------- the live pin (arming)


def test_THIS_REPO_S_FOUR_DOORS_AGREE() -> None:
    """THE ARMING. Everything above proves the probe can tell agreement from
    drift; this is the one case that makes it bite on the real files. If someone
    edits the builder contract in one door and not the others, this goes red at
    PR time rather than being discovered by a seat that built on the wrong rule.

    Deliberately reads the repo, not a fixture. That is the whole point.
    """
    entry = next(e for e in pp.DEFAULT_REGISTRY if e["id"] == "door_canon_parity")
    args = dict(entry.get("args") or {})

    # THE ARGS PRODUCTION USES, not the module constants. The runner passes the
    # registry entry's args; the constants are a second, independent copy of the
    # same configuration. A future PR narrowing the registry to one door would
    # leave a constants-based pin green while production compared nothing
    # (kimi-code/k3, 2026-08-31).
    assert set(args.get("doors") or ()) >= {
        "CLAUDE.md",
        "AGENTS.md",
        "GEMINI.md",
        "QWEN.md",
    }, args
    assert args.get("reference") == "CLAUDE.md", args

    status, n, ev = pp.probe_door_canon_parity(ROOT, args, entry.get("timeout_sec", 15))
    assert status == pp.RECONCILED, "\n".join(ev)
    assert n == 0, (n, ev)

    # Non-vacuity: RECONCILED must not be reachable by there being nothing to
    # compare. UNPROBEABLE is a different status, but assert the count too so a
    # future refactor cannot quietly satisfy this with an empty block set.
    blocks = pp._canon_blocks((ROOT / "CLAUDE.md").read_text())
    assert blocks, (
        "the reference door carries no canon block — this test would be vacuous"
    )
    assert "builder-contract" in blocks, blocks


def test_the_probe_is_registered_and_never_writes() -> None:
    """A probe that is not in the registry does not run, and a proprioception
    probe that writes is no longer a read-only observer of its own boundary."""
    assert "door_canon_parity" in pp.BUILTINS
    ids = {e["id"] for e in pp.DEFAULT_REGISTRY}
    assert "door_canon_parity" in ids
    src = (ROOT / "scripts" / "proprioception.py").read_text()
    body = src[
        src.index("def probe_door_canon_parity") : src.index("def _git_tracked_names")
    ]
    for forbidden in ("write_text(", "open(", "unlink(", "mkdir("):
        assert forbidden not in body, f"the probe calls {forbidden} — it must only read"


# --- the adversarial round: what two blind cross-family seats found ---
# Codex sol and kimi-code/k3, each handed only the diff and told to refute. Every
# case below is a state the probe REACHED before the fix, reproduced on disk
# first — the reviewer's word was the lead, the probe was the evidence.


def test_a_tracked_door_DELETED_from_the_worktree_does_not_crash(
    tmp_path: Path,
) -> None:
    """Existence comes from git's index, content from the working tree, and those
    two disagree the moment anyone runs a plain `rm`. The name stays tracked, the
    read raises FileNotFoundError, and an uncaught raise here kills the whole
    proprioception run — every OTHER boundary goes dark because one door was
    deleted (kimi-code/k3, BLOCKER; reproduced before the fix)."""
    root = _repo(tmp_path, {n: _door() for n in ALL_FOUR})
    (root / "AGENTS.md").unlink()
    status, n, ev = _probe(root)
    assert status == pp.DIVERGED, ev
    assert "AGENTS.md is tracked but could not be read" in "\n".join(ev)


def test_an_unreadable_REFERENCE_is_UNPROBEABLE_not_a_crash(tmp_path: Path) -> None:
    root = _repo(tmp_path, {n: _door() for n in ALL_FOUR})
    (root / "CLAUDE.md").unlink()
    status, n, ev = _probe(root)
    assert status == pp.UNPROBEABLE, ev
    assert "could not be read" in "\n".join(ev)


def test_ONE_participating_door_is_UNPROBEABLE_not_agreement(tmp_path: Path) -> None:
    """A file compared to itself is not agreement. The probe used to answer
    'RECONCILED — 1 canon block identical across CLAUDE.md and 0 other door(s)',
    which is a guard reporting green while comparing nothing (kimi-code/k3)."""
    root = _repo(tmp_path, {n: _door() for n in ALL_FOUR})
    status, n, ev = _probe(root, doors=["CLAUDE.md"])
    assert status == pp.UNPROBEABLE, ev
    assert "only CLAUDE.md participates" in "\n".join(ev)


def test_the_reference_is_queried_even_when_the_args_omit_it(tmp_path: Path) -> None:
    """Querying git only for the names in `doors` and then reporting 'the
    reference is not tracked' is a false factual claim about a file nobody looked
    for — the probe lying in its own evidence line (kimi-code/k3)."""
    root = _repo(tmp_path, {n: _door() for n in ALL_FOUR})
    status, n, ev = _probe(root, doors=["AGENTS.md", "GEMINI.md"])
    joined = "\n".join(ev)
    assert "reference door CLAUDE.md is not tracked" not in joined, joined
    assert status == pp.RECONCILED, joined


# --- the NON-ANTHROPIC build lane (codex gpt-5.6-terra, workspace-write in a scratch
# tree with proprioception.py read-only to it). Given the one gap the conducting
# session had DECLARED rather than covered — every path through _git_tracked_names
# that returns None was untested, so a refactor could make git-failure mean 'no doors
# tracked' (four loud false findings on a healthy repo) or 'ask the filesystem
# instead' (silently reopening the case hole) and nothing would notice. Graded
# independently below by re-running its mutations; its own claims were not taken on
# trust.
def _doors_only_on_disk(root: Path) -> Path:
    """Put complete doors on disk without making the directory a git repository."""
    for name in ALL_FOUR:
        (root / name).write_text(_door())
    return root


def _assert_git_was_unaskable(status: str, n: int, ev: list[str]) -> None:
    """Keep failure-to-query distinct from a git answer of "no tracked doors"."""
    joined = "\n".join(ev)
    assert status == pp.UNPROBEABLE, ev
    assert n == 0
    assert "could not ask git which doors exist" in joined, joined
    assert "filesystem cannot be asked instead" in joined, joined


def test_a_non_repo_is_UNPROBEABLE_because_git_cannot_answer(tmp_path: Path) -> None:
    """A non-repository is a failed git query, never four apparently absent doors."""
    _assert_git_was_unaskable(*_probe(_doors_only_on_disk(tmp_path)))


def test_git_missing_from_PATH_is_UNPROBEABLE_on_an_otherwise_healthy_repo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Exercise subprocess lookup itself; do not stub the helper under test."""
    root = _repo(tmp_path, {name: _door() for name in ALL_FOUR})
    monkeypatch.setenv("PATH", "")
    _assert_git_was_unaskable(*_probe(root))


def test_git_failure_never_falls_back_to_door_files_on_disk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Disk-resident doors cannot stand in for git's exact tracked-name answer."""
    root = _doors_only_on_disk(tmp_path)
    assert all((root / name).is_file() for name in ALL_FOUR)

    # Force the real subprocess path to fail even if a git binary happens to be
    # available to the test runner.  A filesystem fallback would now falsely
    # see four equal doors and report RECONCILED.
    monkeypatch.setenv("PATH", "")
    _assert_git_was_unaskable(*_probe(root))


def test_a_root_that_is_not_the_repo_TOPLEVEL_is_refused(tmp_path: Path) -> None:
    """`git -C <any nested dir>` answers for the ENCLOSING repository. So a caller
    pointed at a subdirectory — or, worse, at a directory inside SOMEONE ELSE'S
    worktree that happens to hold four decoy doors — would get a confident
    verdict about a boundary it never named (codex gpt-5.6-sol, 2026-08-31).

    Found by mutation, not by review: removing the toplevel check left all
    twenty other cases green.
    """
    root = _repo(tmp_path, {n: _door() for n in ALL_FOUR})
    nested = root / "apps" / "somewhere"
    nested.mkdir(parents=True)

    status, n, ev = _probe(nested)
    assert status == pp.UNPROBEABLE, ev
    assert n == 0
    assert "is not a repository toplevel" in "\n".join(ev), ev

    # Non-vacuity: the SAME repo answers normally when asked at its toplevel, so
    # the refusal above is about the path and not about the fixture being broken.
    assert _probe(root)[0] == pp.RECONCILED


def test_DECOY_doors_in_an_enclosing_repo_cannot_certify_a_subtree(
    tmp_path: Path,
) -> None:
    """The dangerous shape is not a harmless subdirectory. An enclosing repo whose
    doors all AGREE would hand a nested directory a green verdict it did not earn
    — the probe would be certifying a boundary that is not the one it was pointed
    at, and the answer would look perfectly healthy."""
    outer = _repo(tmp_path, {n: _door() for n in ALL_FOUR})
    inner = outer / "vendored" / "project"
    inner.mkdir(parents=True)

    status, _n, ev = _probe(inner)
    assert status != pp.RECONCILED, (
        "an enclosing repo's agreeing doors certified a subtree that has none: "
        + "\n".join(ev)
    )
