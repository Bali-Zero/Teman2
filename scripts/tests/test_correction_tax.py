"""Guilt + innocence for scripts/correction_tax.py.

Builds throwaway git repos under tmp_path with controlled commit messages/dates,
never touches the real repo. Loaded via importlib.util (scripts/ is not a
package), same pattern as test_baseline_debt_report.py.

GIT-WALK GOTCHA (found while writing these fixtures, not something correction_tax
can fix): `git log --since/--until` prunes its revision walk assuming roughly
date-monotonic history. Every fixture below therefore creates commits IN
ASCENDING date order (oldest first) — the same order a real, non-rewritten repo
is committed in. Building them out of order (verified empirically: a commit
dated inside the window, created BETWEEN two out-of-window commits in git's
walk order, was silently excluded by `git log --since/--until`) would make
these tests measure git's pruning behavior instead of correction_tax.py's own
logic — a footgun worth naming so nobody "fixes" the ordering later thinking
it's cosmetic.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "correction_tax.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("correction_tax", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    return repo


def _commit(repo: Path, message: str, date: str) -> None:
    """One empty commit dated `date` (e.g. "2026-08-15T10:00:00"). Caller is
    responsible for calling these in ascending-date order — see module docstring.
    """
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = date
    env["GIT_COMMITTER_DATE"] = date
    _git(repo, "commit", "--allow-empty", "-m", message, "-q", env=env)


def _commit_raw_bytes(repo: Path, raw_message: bytes, date: str) -> None:
    """One commit whose message is EXACTLY these raw bytes — bypassing git's
    own porcelain "fixup" of invalid UTF-8.

    Verified empirically: a plain `git commit -m`/`-F` (and even the lower
    `git commit-tree` porcelain) silently REPAIRS an invalid byte sequence
    into valid UTF-8 before it is ever stored (git reinterprets it as
    Latin-1 and re-encodes — a real, documented git behaviour, not a test
    artefact). The only way to land a genuinely malformed message is to
    write the raw commit object bytes directly via `git hash-object`,
    bypassing that repair path entirely — which is exactly what a commit
    authored by a non-git tool, or one from before this repair logic
    existed, would look like on disk. Requires an existing HEAD to parent
    onto — call `_commit()` at least once first.
    """
    tree = subprocess.run(["git", "-C", str(repo), "write-tree"],
                           check=True, capture_output=True, text=True).stdout.strip()
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", "HEAD"],
                           capture_output=True, text=True)
    parent_line = f"parent {head.stdout.strip()}\n" if head.returncode == 0 else ""
    ts = f"{int(datetime.datetime.fromisoformat(date).replace(tzinfo=datetime.timezone.utc).timestamp())} +0000"
    header = (
        f"tree {tree}\n"
        f"{parent_line}"
        f"author Test <test@example.com> {ts}\n"
        f"committer Test <test@example.com> {ts}\n"
        "\n"
    ).encode("ascii")
    obj = header + raw_message
    result = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "-t", "commit", "-w", "--stdin"],
        input=obj, check=True, capture_output=True,
    )
    sha = result.stdout.decode().strip()
    _git(repo, "update-ref", "HEAD", sha)


# The frozen window every fixture below uses. Both bounds are inside it by
# construction ("inside"), the out-of-window fixtures sit strictly before/after.
SINCE = "2026-08-14"
UNTIL = "2026-08-28"
INSIDE_DATE = "2026-08-20T10:00:00"
BEFORE_DATE = "2026-08-10T10:00:00"
AFTER_DATE = "2026-08-30T10:00:00"


def test_guilt_exact_k_of_n_reports_k_over_n_and_correct_share(tmp_path):
    """K=3 of N=7 messages carry a v1 token -> compute() reports 3/7 and the
    exactly-computed share, never a narrated/approximated one.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    corrections = [
        "fix: retract the wrong PMA cap claimed in #100",
        "docs: correction — the figure was wrong, correcting it now",
        "fix(gate): actually the check never ran, W142 stale claim",
    ]
    non_corrections = [
        "feat: add new endpoint",
        "chore: bump dependency",
        "docs: add usage example",
        "test: cover the happy path",
    ]
    for i, msg in enumerate(corrections + non_corrections):
        _commit(repo, msg, INSIDE_DATE.replace("10:00", f"{10 + i:02d}:00"))

    result = ct.compute(repo, SINCE, UNTIL, "v1")
    assert result["total"] == 7
    assert result["corrections"] == 3
    assert result["share"] == round(3 / 7, 3)
    assert result["heuristic"] == "v1"
    assert result["window"] == {"since": SINCE, "until": UNTIL}


def test_innocence_zero_matches_reports_zero_share_and_exit_zero(tmp_path, capsys):
    """A corpus with zero heuristic hits reports 0/N, share 0.0, and exit 0 —
    a clean window (with at least one commit in it) is a successful
    measurement, never an error. NOT the same case as zero commits (0/0) —
    see test_guilt_empty_window_refuses_instead_of_minting_zero below.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    for i, msg in enumerate(["feat: ship widget", "chore: rename file", "docs: typo fix in README"]):
        _commit(repo, msg, INSIDE_DATE.replace("10:00", f"{10 + i:02d}:00"))

    rc = ct.main(["--since", SINCE, "--until", UNTIL, "--repo", str(repo), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["corrections"] == 0
    assert out["total"] == 3
    assert out["share"] == 0.0


def test_window_excludes_commits_outside_since_until(tmp_path):
    """Sanity: a commit strictly before `--since` or strictly after `--until`
    is not counted at all, in either the denominator or the numerator.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "correct the stale claim from last week", BEFORE_DATE)
    _commit(repo, "feat: unrelated, inside window", INSIDE_DATE)
    _commit(repo, "retract the wrong number, after window", AFTER_DATE)

    result = ct.compute(repo, SINCE, UNTIL, "v1")
    assert result["total"] == 1
    assert result["corrections"] == 0


@pytest.mark.parametrize("missing", ["--since", "--until"])
def test_both_bounds_required_exits_nonzero(missing, tmp_path):
    """Omitting either --since or --until refuses (exit 2) — an open-ended
    window is unreproducible by design (see module docstring).
    """
    ct = _load_module()
    argv = ["--since", SINCE, "--until", UNTIL, "--repo", str(tmp_path)]
    # Drop the flag-and-value pair named by `missing`.
    idx = argv.index(missing)
    del argv[idx : idx + 2]

    with pytest.raises(SystemExit) as exc:
        ct.main(argv)
    assert exc.value.code == 2


def test_unknown_heuristic_version_exits_nonzero_naming_known_versions(tmp_path, capsys):
    """An unrecognised --heuristic value refuses (exit 2) and the error names
    every known version — argparse's own `choices=` mechanism, not a custom
    fallback (see module docstring's "additive-only" rule).
    """
    ct = _load_module()
    with pytest.raises(SystemExit) as exc:
        ct.main(["--since", SINCE, "--until", UNTIL, "--repo", str(tmp_path), "--heuristic", "v2"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    for known in ct.HEURISTICS:
        assert known in err, f"error message must name known heuristic {known!r}: {err!r}"


def test_ledger_append_twice_writes_one_row(tmp_path):
    """Appending the same window+heuristic twice is idempotent: one row, not
    two. A DIFFERENT window (or heuristic) appends a genuinely new row.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "retract the wrong claim", INSIDE_DATE)
    ledger = tmp_path / "correction-tax-ledger.jsonl"

    result = ct.compute(repo, SINCE, UNTIL, "v1")
    first = ct.append_ledger(ledger, result)
    second = ct.append_ledger(ledger, result)
    assert first is True
    assert second is False

    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["since"] == SINCE
    assert rows[0]["until"] == UNTIL
    assert rows[0]["heuristic"] == "v1"
    assert rows[0]["corrections"] == 1
    assert rows[0]["total"] == 1

    # A distinct window is NOT a duplicate — it must append a second row.
    other_result = dict(result)
    other_result["window"] = {"since": "2026-01-01", "until": "2026-01-31"}
    third = ct.append_ledger(ledger, other_result)
    assert third is True
    rows_after = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows_after) == 2


def test_ledger_append_via_cli_twice_is_still_one_row(tmp_path):
    """Same idempotency guarantee exercised through --ledger-append end-to-end,
    not just the append_ledger() function directly.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: unrelated", INSIDE_DATE)
    ledger = tmp_path / "cli-ledger.jsonl"
    argv = ["--since", SINCE, "--until", UNTIL, "--repo", str(repo), "--ledger-append", str(ledger)]

    assert ct.main(argv) == 0
    assert ct.main(argv) == 0

    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 1


def test_v1_known_limit_false_positive_mere_mention_is_counted(tmp_path):
    """DOCUMENTED LIMIT (spec requirement #6), asserted rather than hidden: a
    commit whose message merely MENTIONS a heuristic word while doing work
    that corrects nothing is still counted by v1. This is exactly the
    "measures wording, not work" limit the module docstring names — including
    its own example, that adding this script's docstring would itself count.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    # Genuinely unrelated work (renaming a variable); the ONLY reason it
    # matches is that the comment happens to use the word "correction".
    _commit(repo, "chore: rename `tmp` to `buf`, fix a typo (spelling correction) in a comment", INSIDE_DATE)

    result = ct.compute(repo, SINCE, UNTIL, "v1")
    assert result["total"] == 1
    assert result["corrections"] == 1, (
        "known v1 limit: a bare mention of a heuristic word on unrelated work "
        "is a false positive, and this asserts that it stays one (see docstring)"
    )


# F2: shape (additive-only registry) AND construction (v1's pattern text is
# not edited in place). Two DIFFERENT guarantees, kept as two assertions
# rather than folded into one, per the finding: a shape check alone (dict,
# "v1" present, exactly one key) stays green if v1's OWN pattern string is
# edited in place — the exact discipline the additive-only rule exists to
# enforce. The hash below is a LITERAL computed and written down once,
# outside this test's own reference to `ct.HEURISTICS` — comparing against a
# hash re-derived from the live pattern at test time would be tautological
# (it would always match itself); this compares against a fixed prior value.
_V1_PATTERN_LITERAL = (
    "recidiv|actually|was wrong|wrongly|false.positive|false.green|"
    "mislabel|mente|lied|stale claim|correct(s|ed|ion)|retract|"
    "W1[0-9][0-9]|claim"
)
_V1_PATTERN_SHA256 = "95bf7413fa890d904398826c22dd7a6fde8f62e044ef9461d486fa5dd19bdb2f"


def test_heuristics_registry_is_additive_only_by_construction(tmp_path):
    """`HEURISTICS` is a plain dict keyed by version string — the additive-only
    rule is a documented human discipline (never edit v1 in place), not a
    runtime guard; this pins BOTH the *shape* (a dict, "v1" present, exactly
    one registered version today, so a future v2 lands beside it, not over
    it) AND the *construction* (v1's own pattern text, via a hash literal
    computed once and pinned here — see comment above `_V1_PATTERN_SHA256`).
    A shape-only version of this test stays green if someone edits v1's
    pattern string in place; the hash check is what turns that red.
    """
    ct = _load_module()
    assert isinstance(ct.HEURISTICS, dict)
    assert "v1" in ct.HEURISTICS
    assert list(ct.HEURISTICS) == ["v1"], (
        "exactly one heuristic version is registered today; adding v2 should "
        "extend this list, never replace v1's entry"
    )
    assert ct.HEURISTICS["v1"].pattern == _V1_PATTERN_LITERAL, (
        "v1's pattern text has changed — this is the additive-only rule being "
        "violated (a version is edited in place instead of a v2 landing "
        "beside it), and this literal-string comparison is the guard"
    )
    live_hash = hashlib.sha256(ct.HEURISTICS["v1"].pattern.encode("utf-8")).hexdigest()
    assert live_hash == _V1_PATTERN_SHA256, (
        f"v1's pattern hash changed to {live_hash!r} — expected "
        f"{_V1_PATTERN_SHA256!r} (computed once from the literal above, not "
        "re-derived from the live pattern, so this is not tautological)"
    )


def test_json_output_matches_compute_result(tmp_path, capsys):
    """--json emits exactly compute()'s own dict — the share is computed, never
    separately narrated in a way that could drift from the number underneath.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    # Deliberately 1/3 (share 0.333...): a JSON path that re-rounds the share
    # to fewer decimals independently of compute() would still coincidentally
    # match on a "nice" fraction like 1/2 (0.5 == round(0.5, 1)) — 1/3 is the
    # fraction that actually distinguishes 3-decimal rounding from coarser
    # rounding, which is the divergence this test exists to catch.
    _commit(repo, "retract the wrong number", INSIDE_DATE)
    _commit(repo, "feat: unrelated one", INSIDE_DATE.replace("10:00", "11:00"))
    _commit(repo, "feat: unrelated two", INSIDE_DATE.replace("10:00", "12:00"))

    rc = ct.main(["--since", SINCE, "--until", UNTIL, "--repo", str(repo), "--json"])
    assert rc == 0
    emitted = json.loads(capsys.readouterr().out)
    expected = ct.compute(repo, SINCE, UNTIL, "v1")
    assert expected["share"] == round(1 / 3, 3)
    assert emitted == expected


def test_the_share_never_travels_without_its_composition(tmp_path: Path) -> None:
    """A bare share invites quotation; the breakdown is what makes it readable.

    Compares the FULL expected top_tokens dict for this fixture, not spot
    checks on two keys. A weaker `top.get("actually", 0) >= 1` version of
    this assertion stayed GREEN when `_token_contributions` was mutated to
    `counts.append([alt, len(messages)])` — crediting every alternative with
    every message regardless of whether it actually matched, i.e. pinning
    mere PRESENCE of a breakdown, not its CONTENT. Under that exact mutation
    every one of the three real messages below (2 unrelated, 1 corrective)
    would make every alternative report count=3 — completely different from
    the expected dict below, which is what turns this red on that mutation
    (verified: reverting `_token_contributions` to that mutation while
    running this exact test fails the assertion below; restored immediately
    after — see fix session notes).
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    for i, msg in enumerate([
        "fix: this actually was wrong",
        "feat: unrelated work",
        "docs: another claim corrected here",
    ]):
        _commit(repo, msg, f"2026-08-1{i + 5}T10:00:00")
    result = ct.compute(repo, "2026-08-14", "2026-08-28", "v1")
    top = dict(result["top_tokens"])
    assert any(v > 0 for v in top.values()), (
        "every token contribution is zero — the breakdown is not being computed, "
        "and the share would travel alone"
    )
    # The FULL top-5 dict, exact counts, not a subset spot check. `recidiv`
    # is the fifth slot deterministically: it is the first zero-count
    # alternative in HEURISTIC_TOKENS["v1"]'s own order, and ties break by
    # stable-sort original order (verified empirically before writing this).
    assert top == {
        "actually": 1,
        "was wrong": 1,
        "correct(s|ed|ion)": 1,
        "claim": 1,
        "recidiv": 0,
    }, f"expected exact top_tokens dict; got {result['top_tokens']}"


def test_v1_substring_collisions_are_real_and_the_breakdown_exposes_them(tmp_path: Path) -> None:
    """The finding that makes v1 unusable, pinned as a test rather than prose.

    `mente` and `lied` are BARE SUBSTRINGS in v1's pattern. On this repo's own
    frozen window they fire overwhelmingly on `implemented`/`documented`/
    `commented` and `applied`/`supplied`/`implied` — which is why v1 reports
    ~64% where the spec cites ~12%.

    This does NOT fix the pattern: v1 is pinned by the spec, and tuning a
    heuristic until it reproduces a target makes the number measure the tuning.
    It pins that the collisions are REAL, so a future v2 has a red test to turn
    green rather than an argument to have.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    for i, msg in enumerate([
        "feat: implemented the thing",     # matches `mente`, means nothing
        "docs: documented the thing",      # matches `mente`, means nothing
        "fix: applied the patch",          # matches `lied`, means nothing
        "chore: supplied the fixture",     # matches `lied`, means nothing
    ]):
        _commit(repo, msg, f"2026-08-1{i + 5}T10:00:00")
    result = ct.compute(repo, "2026-08-14", "2026-08-28", "v1")
    assert result["corrections"] == 4, (
        "all four of these commits are ordinary work and v1 counts every one of "
        f"them as a correction — that is the collision. got {result}"
    )
    top = dict(result["top_tokens"])
    assert top.get("mente", 0) == 2, f"expected `mente` to fire twice; got {result['top_tokens']}"
    assert top.get("lied", 0) == 2, f"expected `lied` to fire twice; got {result['top_tokens']}"


# ---------------------------------------------------------------------------
# F5: a closed window with zero commits is refused, never minted as 0/0.
# ---------------------------------------------------------------------------

def test_guilt_empty_window_refuses_instead_of_minting_zero(tmp_path):
    """Transposed --since/--until (the concrete example from the finding)
    makes `git log` return nothing with exit 0 — that is an unread window,
    not a measurement of zero, and compute() must refuse it rather than
    report a citable "0/0 = 0.000".
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: something, irrelevant to the transposed window", INSIDE_DATE)

    with pytest.raises(RuntimeError, match="zero commits"):
        ct.compute(repo, UNTIL, SINCE, "v1")  # since/until swapped


def test_guilt_empty_window_via_cli_exits_nonzero_and_never_writes_ledger(tmp_path, capsys):
    """Same refusal exercised through main() end-to-end: exit 1 (not 0), and
    critically, --ledger-append must NEVER receive a 0/0 row for this run —
    the ledger file must not even be created.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: something", INSIDE_DATE)
    ledger = tmp_path / "should-stay-absent.jsonl"

    rc = ct.main([
        "--since", UNTIL, "--until", SINCE,  # transposed -> zero commits
        "--repo", str(repo), "--ledger-append", str(ledger),
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "zero commits" in err
    assert not ledger.exists(), (
        "a 0/0 window must never reach append_ledger() at all — the ledger "
        "file must not even be created"
    )


def test_innocence_genuinely_empty_but_valid_window_also_refuses(tmp_path):
    """Not just transposed bounds: a correctly-ordered window with no commits
    at all (a quiet repo, or bounds before the repo's first commit) is the
    SAME 0/0 case and refuses the same way.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: only commit, far outside this window", "2020-01-01T00:00:00")

    with pytest.raises(RuntimeError, match="zero commits"):
        ct.compute(repo, SINCE, UNTIL, "v1")


# ---------------------------------------------------------------------------
# F6: decode and timeout crashes must not escape as tracebacks.
# ---------------------------------------------------------------------------

def test_guilt_invalid_utf8_commit_message_does_not_crash(tmp_path):
    """A message containing a byte sequence that is not valid UTF-8 must not
    raise UnicodeDecodeError out of compute() — it is decoded with
    replacement characters instead, and the count still includes that
    commit (measuring wording, not perfect encoding).

    Verified empirically before writing this fixture: a PLAIN `git commit
    -m`/`-F` silently repairs invalid UTF-8 on ingest (git reinterprets it as
    Latin-1 and re-encodes), so `_commit_raw_bytes` bypasses that porcelain
    path entirely via `git hash-object` to land a genuinely malformed
    message — this is what a commit authored by a foreign tool, or predating
    git's repair logic, looks like on disk.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: ordinary parent commit", INSIDE_DATE)
    # 0xe9 alone (no valid UTF-8 continuation byte) is not valid UTF-8.
    _commit_raw_bytes(repo, b"legacy commit \xe9 message\n", INSIDE_DATE.replace("10:00", "11:00"))
    _commit(repo, "chore: ordinary child commit", INSIDE_DATE.replace("10:00", "12:00"))

    result = ct.compute(repo, SINCE, UNTIL, "v1")  # must not raise
    assert result["total"] == 3


def test_guilt_git_log_timeout_is_treated_as_a_git_log_failure(tmp_path, monkeypatch):
    """A `subprocess.TimeoutExpired` from `git log` must land in the same
    "could not read history" bucket as any other git-log failure (exit 1
    via RuntimeError, caught by main()) — not escape as an uncaught
    exception. A real 120s timeout is too slow to exercise in a test, so
    `subprocess.run` is monkeypatched to raise it directly; this exercises
    the exact except clause in `_git_log_messages`, not a slow integration
    test standing in for it.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: irrelevant, subprocess.run never actually runs it", INSIDE_DATE)

    def _raise_timeout(*args, **kwargs):
        raise ct.subprocess.TimeoutExpired(cmd="git log", timeout=120)

    monkeypatch.setattr(ct.subprocess, "run", _raise_timeout)

    with pytest.raises(RuntimeError, match="git log could not run"):
        ct.compute(repo, SINCE, UNTIL, "v1")


# ---------------------------------------------------------------------------
# F7: the record parser must not split on a byte git commit messages CAN
# legally contain.
# ---------------------------------------------------------------------------

def test_guilt_old_record_separator_byte_inside_a_message_no_longer_inflates_total(tmp_path):
    """The OLD parser split `git log`'s output on `\\x1e`, and that byte is
    NOT forbidden in a commit message — verified empirically:
    `git commit -m "$(printf 'aa\\x1ebb')")` survives byte-for-byte into
    `%B`. A commit containing it would silently split into two records,
    inflating `total` by one. The current parser uses a NUL-prefixed
    terminator instead (NUL is the one byte git DOES forbid — verified: it
    silently truncates the message at that byte on ingest, so it can never
    appear mid-message the way `\\x1e` could).
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: ordinary commit one", INSIDE_DATE)
    _commit(repo, f"fix: contains the old separator byte {chr(0x1E)} inline, still ONE commit",
             INSIDE_DATE.replace("10:00", "11:00"))
    _commit(repo, "chore: ordinary commit two", INSIDE_DATE.replace("10:00", "12:00"))

    result = ct.compute(repo, SINCE, UNTIL, "v1")
    assert result["total"] == 3, (
        "a commit message containing the old 0x1e separator byte must still "
        f"count as exactly ONE record, not two; got total={result['total']}"
    )


# ---------------------------------------------------------------------------
# F3: the depth-aware splitter must also be aware of bracket character
# classes — a `|`, `(` or `)` inside `[...]` is a literal character.
# ---------------------------------------------------------------------------

def test_guilt_split_alternatives_handles_pipe_inside_bracket_class(tmp_path):
    """Reproduction #1 from the finding: `a[|]b|c` naively (depth-tracking
    with no class-awareness) yields `('a[', ']b', 'c')`, and `re.compile('a[')`
    raises `re.error: unterminated character set` — an uncaught crash, not a
    wrong number. The correct split treats `[|]` as one bracket class and
    produces exactly two alternatives, both valid regexes.
    """
    import re
    ct = _load_module()
    result = ct._split_alternatives("a[|]b|c")
    assert result == ("a[|]b", "c")
    for alt in result:
        re.compile(alt)  # must not raise


def test_guilt_split_alternatives_handles_paren_inside_bracket_class(tmp_path):
    """Reproduction #2 from the finding: `x[(]|y` naively yields
    `('x[(]|y',)` — ONE alternative where there are two, because the literal
    `(` inside the class inflated the group-depth counter and swallowed the
    top-level `|`. The correct split does not let a class's contents affect
    group depth at all.
    """
    ct = _load_module()
    result = ct._split_alternatives("x[(]|y")
    assert result == ("x[(]", "y")


def test_innocence_split_alternatives_handles_literal_close_bracket_forms(tmp_path):
    """The two POSIX bracket-expression positions where `]` is itself a
    literal rather than the class terminator: immediately after the opening
    `[` (`[]]`), and immediately after a negating `^` (`[^]]`). Both must
    round-trip as a SINGLE unsplit alternative (no top-level `|` inside
    either), and both must compile.
    """
    import re
    ct = _load_module()
    for pattern in ("[]]", "[^]]"):
        result = ct._split_alternatives(pattern)
        assert result == (pattern,), f"{pattern!r} split incorrectly: {result}"
        re.compile(result[0])  # must not raise


def test_innocence_v1_own_pattern_still_splits_correctly(tmp_path):
    """Regression guard: v1's own pattern (grouped alternation, no classes)
    must still split exactly as before the class-awareness was added — this
    is the ORIGINAL motivating case for `_split_alternatives` existing at all.
    """
    ct = _load_module()
    assert "correct(s|ed|ion)" in ct.HEURISTIC_TOKENS["v1"]
    assert len(ct.HEURISTIC_TOKENS["v1"]) == 14


# ---------------------------------------------------------------------------
# F8: --json must carry its own disclaimer, not just the human path.
# ---------------------------------------------------------------------------

def test_json_payload_carries_report_only_and_overlap_disclaimer_as_fields(tmp_path, capsys):
    """`--json`'s stdout must include the report-only statement and the
    "these overlap, do not sum" warning as FIELDS of the payload itself —
    not just as text printed alongside it that a machine consumer parsing
    stdout as JSON would never see. This is what makes the disclaimer
    TRAVEL with the number (see module docstring): a bare
    `{"share": 0.638}` invites exactly the kind of one-line gate the finding
    demonstrated (`jq -r '.share > 0.5'`), and this does not prevent that —
    it makes the context available alongside the number for whoever reads it.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "retract the wrong number", INSIDE_DATE)

    rc = ct.main(["--since", SINCE, "--until", UNTIL, "--repo", str(repo), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "report_only" in payload and payload["report_only"], (
        "the JSON payload must carry a non-empty report_only field"
    )
    assert "top_tokens_overlap_note" in payload and payload["top_tokens_overlap_note"], (
        "the JSON payload must carry a non-empty overlap-warning field"
    )
    assert "never a target" in payload["report_only"]
    assert "do not sum" in payload["top_tokens_overlap_note"].lower() or \
        "do NOT sum" in payload["top_tokens_overlap_note"]


def test_report_only_disclaimer_is_printed_on_stderr_even_under_json(tmp_path, capsys):
    """The human-readable REPORT ONLY line must still reach a terminal
    watching stderr even when --json is used (whose stdout must stay pure
    machine-parseable JSON) — printed unconditionally, not only on the
    human-output branch.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "retract the wrong number", INSIDE_DATE)

    rc = ct.main(["--since", SINCE, "--until", UNTIL, "--repo", str(repo), "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    # stdout must be ONLY the JSON line -- nothing else mixed in.
    assert json.loads(captured.out)
    assert "REPORT ONLY" in captured.err or "never a target" in captured.err


# ---------------------------------------------------------------------------
# F9: ledger conflicts (same key, different numbers) must fail loudly, and
# the append itself must be serialised under an exclusive lock.
# ---------------------------------------------------------------------------

def test_guilt_ledger_same_key_different_numbers_raises_instead_of_silently_skipping(tmp_path):
    """A re-run over an ALREADY-RECORDED window+heuristic that computes a
    DIFFERENT answer (e.g. a backdated merge landing inside a closed window
    — real git behaviour this module already documents) must not be treated
    as a harmless duplicate. append_ledger() raises, naming both sets of
    numbers, and the stale row is left untouched (never silently overwritten
    either).
    """
    ct = _load_module()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({
        "since": SINCE, "until": UNTIL, "heuristic": "v1",
        "corrections": 1, "total": 1, "share": 1.0,
    }) + "\n")

    conflicting_result = {
        "window": {"since": SINCE, "until": UNTIL}, "heuristic": "v1",
        "corrections": 2, "total": 2, "share": 1.0,  # same share, DIFFERENT corrections/total
        "top_tokens": [],
    }
    with pytest.raises(RuntimeError, match="ledger conflict"):
        ct.append_ledger(ledger, conflicting_result)

    # The stale row must survive untouched -- one line, the ORIGINAL numbers.
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["corrections"] == 1
    assert rows[0]["total"] == 1


def test_guilt_ledger_conflict_via_cli_exits_nonzero(tmp_path, capsys):
    """Same conflict exercised through main() end-to-end: a second run over
    the identical window that (somehow) computes a different answer must
    exit non-zero, not silently report "skipped (duplicate)".
    """
    ct = _load_module()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({
        "since": SINCE, "until": UNTIL, "heuristic": "v1",
        "corrections": 99, "total": 1, "share": 99.0,  # a value no real run will ever compute
    }) + "\n")
    repo = _init_repo(tmp_path)
    _commit(repo, "feat: unrelated single commit", INSIDE_DATE)

    rc = ct.main(["--since", SINCE, "--until", UNTIL, "--repo", str(repo),
                  "--ledger-append", str(ledger)])
    assert rc == 1
    assert "ledger conflict" in capsys.readouterr().err


def test_innocence_ledger_same_key_same_numbers_still_skips_as_duplicate(tmp_path):
    """The conflict check must not fire on a genuine re-run: identical
    numbers for the same key is still the ordinary idempotent skip, not a
    conflict.
    """
    ct = _load_module()
    repo = _init_repo(tmp_path)
    _commit(repo, "retract the wrong number", INSIDE_DATE)
    ledger = tmp_path / "ledger.jsonl"

    result = ct.compute(repo, SINCE, UNTIL, "v1")
    assert ct.append_ledger(ledger, result) is True
    assert ct.append_ledger(ledger, result) is False  # identical numbers -> skip, not raise

    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 1


def test_guilt_ledger_append_is_actually_serialised_under_a_lock(tmp_path):
    """A comment saying the append is locked is not proof the lock is taken
    — this holds an exclusive flock on the ledger file in a background
    thread, then measures how long append_ledger() blocks waiting for it.
    An implementation that does NOT actually take the lock would return
    almost immediately (well under the hold time); one that does must block
    for at least the hold time before it can proceed.
    """
    ct = _load_module()
    import fcntl

    ledger = tmp_path / "locked-ledger.jsonl"
    ledger.touch()
    hold_seconds = 0.4

    lock_acquired = threading.Event()
    release_lock = threading.Event()

    def _hold_lock():
        with open(ledger, "r+") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            lock_acquired.set()
            release_lock.wait(timeout=5)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    holder = threading.Thread(target=_hold_lock)
    holder.start()
    assert lock_acquired.wait(timeout=5), "background thread never acquired its lock"

    def _release_after_delay():
        time.sleep(hold_seconds)
        release_lock.set()

    releaser = threading.Thread(target=_release_after_delay)
    releaser.start()

    started = time.monotonic()
    result = {
        "window": {"since": SINCE, "until": UNTIL}, "heuristic": "v1",
        "corrections": 1, "total": 1, "share": 1.0, "top_tokens": [],
    }
    ct.append_ledger(ledger, result)
    elapsed = time.monotonic() - started

    holder.join(timeout=5)
    releaser.join(timeout=5)

    assert elapsed >= hold_seconds * 0.8, (
        f"append_ledger() returned after only {elapsed:.2f}s while another "
        f"process held an exclusive lock for {hold_seconds}s — it did not "
        "actually wait for the lock, so it is not serialised at all"
    )
