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

import importlib.util
import json
import subprocess
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
    import os

    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = date
    env["GIT_COMMITTER_DATE"] = date
    _git(repo, "commit", "--allow-empty", "-m", message, "-q", env=env)


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
    a clean window is a successful measurement, never an error.
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


def test_heuristics_registry_is_additive_only_by_construction(tmp_path):
    """`HEURISTICS` is a plain dict keyed by version string — the additive-only
    rule is a documented human discipline (never edit v1 in place), not a
    runtime guard; this pins the *shape* (a dict, "v1" present, exactly one
    registered version today) so a future v2 lands beside it, not over it.
    """
    ct = _load_module()
    assert isinstance(ct.HEURISTICS, dict)
    assert "v1" in ct.HEURISTICS
    assert list(ct.HEURISTICS) == ["v1"], (
        "exactly one heuristic version is registered today; adding v2 should "
        "extend this list, never replace v1's entry"
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

    Zeroing every token count left the whole corpus green when this was first
    added — the feature existed and nothing defended it, which is the exact
    shape this repo keeps finding. So the breakdown is pinned on CONTENT, not
    on presence.
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
    assert top.get("actually", 0) >= 1, f"'actually' should have fired; got {result['top_tokens']}"
    assert top.get("claim", 0) >= 1, f"'claim' should have fired; got {result['top_tokens']}"


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
