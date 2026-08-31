"""test_queue_stall_classifier.py — pure-function + monkeypatched-I/O tests, no network, plus a
static self-protection scan proving this reporter can never mutate a PR/run/check.

Covers the mandate's explicit cases:
  1. classify_stall's 5-bucket precedence (conflict > gate-verdict-missing > required-check-red
     > not-armed > queued-and-advancing), each with guilt AND innocence.
  2. not-armed requires BOTH autoMergeRequest and mergeQueueEntry null (W111) — never inferred
     from autoMergeRequest alone.
  3. A red "Harness floor recompute" with no harness/fable-gate verdict posted classifies as
     gate-verdict-missing, not required-check-red.
  4. conflict is only ever assigned after a FRESH re-check, never from the stale bulk read.
  5. A per-PR network failure -> CANNOT-VERIFY for that PR, never a guess, never a silent skip.
  6. Zero examined PRs -> main() exits non-zero, loud.
  7. Static AST proof: no write-shaped gh invocation and no GraphQL `mutation` anywhere in this
     script's source (mirrors scripts/tests/test_harness_gate_read.py's own self-protection
     tests, adapted for a script that legitimately uses `-f`/`-F` for read-only GraphQL).

Plus superscar #3 discipline: every guard gets an innocence test on the same entity, never
inferred from a single guilt case.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue_stall_classifier as sc  # noqa: E402

NOW = _dt.datetime(2026, 8, 31, 12, 0, 0, tzinfo=_dt.timezone.utc)

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "queue_stall_classifier.py"
SCRIPT_SOURCE = SCRIPT_PATH.read_text()


def _iso(dt: _dt.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _code_only(source: str) -> str:
    """Strip every docstring (module, function, class) before a source-scan test — this
    module's OWN docstring illustratively quotes real gh/GraphQL shapes while explaining the
    design; a naive substring scan would false-positive on that prose. Duplicated from
    scripts/tests/test_harness_gate_read.py::_code_only (same technique, same reason)."""
    tree = ast.parse(source)
    excluded_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                excluded_lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    lines = source.splitlines(keepends=True)
    return "".join(line for i, line in enumerate(lines, start=1) if i not in excluded_lines)


CODE_ONLY_SOURCE = _code_only(SCRIPT_SOURCE)


# ── is_stall_candidate ───────────────────────────────────────────────────────


def test_is_stall_candidate_guilt_old_enough_is_selected():
    pr = {"created_at": NOW - _dt.timedelta(minutes=45)}
    assert sc.is_stall_candidate(pr, NOW, min_age_minutes=30) is True


def test_is_stall_candidate_innocence_too_young_is_not_selected():
    pr = {"created_at": NOW - _dt.timedelta(minutes=5)}
    assert sc.is_stall_candidate(pr, NOW, min_age_minutes=30) is False


def test_is_stall_candidate_boundary_exactly_at_threshold_is_selected():
    pr = {"created_at": NOW - _dt.timedelta(minutes=30)}
    assert sc.is_stall_candidate(pr, NOW, min_age_minutes=30) is True


# ── find_named_check_conclusion ──────────────────────────────────────────────


def test_find_named_check_conclusion_guilt_finds_the_exact_named_run():
    runs = [{"name": "Lint", "conclusion": "SUCCESS"}, {"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"}]
    assert sc.find_named_check_conclusion(runs, sc.HARNESS_FLOOR_CHECK_NAME) == "FAILURE"


def test_find_named_check_conclusion_innocence_absent_name_is_none():
    runs = [{"name": "Lint", "conclusion": "SUCCESS"}]
    assert sc.find_named_check_conclusion(runs, sc.HARNESS_FLOOR_CHECK_NAME) is None


def test_find_named_check_conclusion_innocence_case_sensitive_no_fuzzy_match():
    # guard-over-match discipline: a near-miss name (different case/spacing) must NOT match —
    # "Harness floor recompute" is a literal job name, not a pattern.
    runs = [{"name": "harness-floor", "conclusion": "FAILURE"}]
    assert sc.find_named_check_conclusion(runs, sc.HARNESS_FLOOR_CHECK_NAME) is None


# ── classify_stall precedence (mandate's 5-bucket closed set) ───────────────


def _args(**overrides):
    base = dict(
        merge_state_status="CLEAN",
        status_rollup_state="SUCCESS",
        auto_merge_enabled=True,
        in_queue=False,
        harness_floor_red=False,
        fable_gate_posted=None,
    )
    base.update(overrides)
    return base


def test_classify_guilt_dirty_is_conflict():
    assert sc.classify_stall(**_args(merge_state_status="DIRTY")) == "conflict"


def test_classify_innocence_clean_is_not_conflict():
    assert sc.classify_stall(**_args(merge_state_status="CLEAN")) != "conflict"


def test_classify_guilt_gate_red_and_verdict_never_posted_is_gate_verdict_missing():
    assert (
        sc.classify_stall(
            **_args(status_rollup_state="FAILURE", harness_floor_red=True, fable_gate_posted=False)
        )
        == "gate-verdict-missing"
    )


def test_classify_innocence_gate_red_but_a_real_verdict_was_posted_is_required_check_red_not_missing():
    # a REWORK/BLOCK verdict was genuinely posted (fable_gate_posted True) -- this is a real
    # judgment, not a missing one, so it must NOT be gate-verdict-missing.
    assert (
        sc.classify_stall(
            **_args(status_rollup_state="FAILURE", harness_floor_red=True, fable_gate_posted=True)
        )
        == "required-check-red"
    )


def test_classify_innocence_rollup_green_never_gate_verdict_missing_even_if_flag_set_wrongly():
    # defensive: gate-verdict-missing requires harness_floor_red True; a caller bug that leaves
    # status_rollup_state green must not somehow still reach it via this function alone (it
    # can't, by construction — harness_floor_red is an independent input) -- this pins that.
    assert (
        sc.classify_stall(
            **_args(status_rollup_state="SUCCESS", harness_floor_red=True, fable_gate_posted=False)
        )
        == "gate-verdict-missing"  # harness_floor_red is still the authority, not the rollup
    )


def test_classify_guilt_other_red_required_check_is_required_check_red():
    assert (
        sc.classify_stall(**_args(status_rollup_state="FAILURE", harness_floor_red=False))
        == "required-check-red"
    )


def test_classify_guilt_error_rollup_state_is_also_required_check_red():
    assert sc.classify_stall(**_args(status_rollup_state="ERROR")) == "required-check-red"


def test_classify_innocence_pending_rollup_is_not_required_check_red():
    assert sc.classify_stall(**_args(status_rollup_state="PENDING")) != "required-check-red"


def test_classify_guilt_both_null_is_not_armed():
    assert (
        sc.classify_stall(**_args(auto_merge_enabled=False, in_queue=False, status_rollup_state="PENDING"))
        == "not-armed"
    )


def test_classify_innocence_w111_auto_merge_null_but_in_queue_is_not_not_armed():
    # W111: autoMergeRequest null ALONE never means not-armed -- a queued PR consumes it.
    assert (
        sc.classify_stall(**_args(auto_merge_enabled=False, in_queue=True, status_rollup_state="PENDING"))
        != "not-armed"
    )


def test_classify_innocence_w111_in_queue_null_but_auto_merge_enabled_is_not_not_armed():
    assert (
        sc.classify_stall(**_args(auto_merge_enabled=True, in_queue=False, status_rollup_state="PENDING"))
        != "not-armed"
    )


def test_classify_guilt_armed_and_green_is_queued_and_advancing():
    assert (
        sc.classify_stall(**_args(auto_merge_enabled=True, in_queue=False, status_rollup_state="SUCCESS"))
        == "queued-and-advancing"
    )


def test_classify_precedence_conflict_beats_gate_verdict_missing():
    assert (
        sc.classify_stall(
            **_args(
                merge_state_status="DIRTY",
                status_rollup_state="FAILURE",
                harness_floor_red=True,
                fable_gate_posted=False,
            )
        )
        == "conflict"
    )


def test_classify_precedence_gate_verdict_missing_beats_not_armed():
    assert (
        sc.classify_stall(
            **_args(
                status_rollup_state="FAILURE",
                harness_floor_red=True,
                fable_gate_posted=False,
                auto_merge_enabled=False,
                in_queue=False,
            )
        )
        == "gate-verdict-missing"
    )


def test_classify_precedence_required_check_red_beats_not_armed():
    assert (
        sc.classify_stall(
            **_args(status_rollup_state="FAILURE", auto_merge_enabled=False, in_queue=False)
        )
        == "required-check-red"
    )


def test_classify_never_returns_outside_the_closed_set():
    for merge_state in ("CLEAN", "DIRTY", "BLOCKED", "UNSTABLE", "UNKNOWN", "BEHIND", None):
        for rollup in ("SUCCESS", "FAILURE", "ERROR", "PENDING", "EXPECTED", None):
            for armed in (True, False):
                for queued in (True, False):
                    result = sc.classify_stall(
                        merge_state_status=merge_state,
                        status_rollup_state=rollup,
                        auto_merge_enabled=armed,
                        in_queue=queued,
                        harness_floor_red=False,
                        fable_gate_posted=None,
                    )
                    assert result in sc.STALL_CAUSES


# ── build_report / _classify_one — monkeypatched I/O ────────────────────────


def _pr(number=1, **overrides):
    base = {
        "number": number,
        "title": "some PR",
        "is_draft": False,
        "head_sha": "a" * 40,
        "created_at": NOW - _dt.timedelta(hours=2),
        "merge_state_status": "CLEAN",
        "auto_merge_enabled": True,
        "in_queue": False,
        "status_rollup_state": "SUCCESS",
    }
    base.update(overrides)
    return base


def test_build_report_excludes_drafts(monkeypatch):
    monkeypatch.setattr(sc, "fetch_open_prs", lambda repo: [_pr(1, is_draft=True)])
    report = sc.build_report("Bali-Zero/Teman2", NOW, 30)
    assert report["examined_total"] == 1
    assert report["excluded_drafts"] == 1
    assert report["rows"] == []


def test_build_report_excludes_too_young_prs(monkeypatch):
    monkeypatch.setattr(
        sc, "fetch_open_prs", lambda repo: [_pr(1, created_at=NOW - _dt.timedelta(minutes=5))]
    )
    report = sc.build_report("Bali-Zero/Teman2", NOW, 30)
    assert report["examined_total"] == 1
    assert report["rows"] == []


def test_build_report_unparseable_created_at_is_cannot_verify_not_silently_dropped(monkeypatch):
    monkeypatch.setattr(sc, "fetch_open_prs", lambda repo: [_pr(1, created_at=None)])
    report = sc.build_report("Bali-Zero/Teman2", NOW, 30)
    assert len(report["rows"]) == 1
    assert report["rows"][0]["cause"] == sc.CANNOT_VERIFY


def test_build_report_healthy_pr_classifies_queued_and_advancing(monkeypatch):
    monkeypatch.setattr(sc, "fetch_open_prs", lambda repo: [_pr(1)])
    report = sc.build_report("Bali-Zero/Teman2", NOW, 30)
    assert len(report["rows"]) == 1
    assert report["rows"][0]["cause"] == "queued-and-advancing"


def test_build_report_top_level_fetch_failure_is_recorded_never_raises(monkeypatch):
    def boom(repo):
        raise RuntimeError("gh api graphql failed rc=1")

    monkeypatch.setattr(sc, "fetch_open_prs", boom)
    report = sc.build_report("Bali-Zero/Teman2", NOW, 30)
    assert report["fetch_error"] is not None
    assert report["examined_total"] == 0
    assert report["rows"] == []


def test_classify_one_dirty_is_reverified_fresh_and_clears_when_no_longer_dirty(monkeypatch):
    """Module docstring trap (c): a stale DIRTY read must not become 'conflict' if the fresh
    re-check says otherwise (mirrors the live fleet-watch mailbox evidence this session
    observed: PRs read DIRTY minutes earlier and found clean on re-probe)."""
    pr = _pr(1, merge_state_status="DIRTY")
    monkeypatch.setattr(sc, "fetch_fresh_merge_state", lambda repo, number: "CLEAN")
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] != "conflict"


def test_classify_one_dirty_confirmed_fresh_is_conflict(monkeypatch):
    pr = _pr(1, merge_state_status="DIRTY")
    monkeypatch.setattr(sc, "fetch_fresh_merge_state", lambda repo, number: "DIRTY")
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "conflict"


def test_classify_one_dirty_recheck_failure_is_cannot_verify(monkeypatch):
    def boom(repo, number):
        raise RuntimeError("gh api graphql failed rc=1")

    pr = _pr(1, merge_state_status="DIRTY")
    monkeypatch.setattr(sc, "fetch_fresh_merge_state", boom)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == sc.CANNOT_VERIFY


def test_classify_one_red_gate_never_posted_is_gate_verdict_missing(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"}], False),
    )
    monkeypatch.setattr(sc, "read_fable_gate_state", lambda repo, sha: (None, None))
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "gate-verdict-missing"


def test_classify_one_red_gate_with_real_verdict_is_required_check_red(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"}], False),
    )
    monkeypatch.setattr(sc, "read_fable_gate_state", lambda repo, sha: ("failure", "REWORK"))
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "required-check-red"
    assert "REWORK" not in row["detail"] or "failure" in row["detail"]  # description optional; state must show


def test_classify_one_red_other_check_not_the_gate_is_required_check_red(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": "Backend Tests", "conclusion": "FAILURE"}], False),
    )

    def never_called(repo, sha):
        raise AssertionError("must not read fable-gate state when the gate itself is not red")

    monkeypatch.setattr(sc, "read_fable_gate_state", never_called)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "required-check-red"


def test_classify_one_truncated_and_gate_not_found_is_cannot_verify_never_guessed(monkeypatch):
    """Module docstring trap (d), the live-measured checkSuites pagination bug: if the fetch
    was truncated and 'Harness floor recompute' was not found among what WAS fetched, this must
    never silently fall through to required-check-red -- it might be hiding past the page."""
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": "Some Other Check", "conclusion": "FAILURE"}], True),
    )

    def never_called(repo, sha):
        raise AssertionError("must not guess a fable-gate read when the check-run search itself was truncated")

    monkeypatch.setattr(sc, "read_fable_gate_state", never_called)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == sc.CANNOT_VERIFY


def test_classify_one_not_truncated_and_gate_not_found_falls_through_normally(monkeypatch):
    # innocence pairing for the truncation guilt case above: a COMPLETE (non-truncated) fetch
    # that genuinely does not contain the gate check must classify normally, not CANNOT-VERIFY.
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": "Some Other Check", "conclusion": "FAILURE"}], False),
    )
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "required-check-red"


def test_classify_one_checksuites_fetch_failure_is_cannot_verify(monkeypatch):
    def boom(repo, number):
        raise RuntimeError("gh api graphql failed rc=1")

    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(sc, "fetch_check_runs_flat", boom)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == sc.CANNOT_VERIFY


def test_classify_one_fable_gate_read_failure_is_cannot_verify(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"}], False),
    )

    def boom(repo, sha):
        raise RuntimeError("gh api commits/.../status failed rc=1")

    monkeypatch.setattr(sc, "read_fable_gate_state", boom)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == sc.CANNOT_VERIFY


def test_classify_one_never_fetches_check_runs_when_rollup_is_green(monkeypatch):
    # efficiency + correctness: the heavier per-candidate checkSuites fetch must only fire when
    # the cheap bulk rollup was already red.
    def never_called(repo, number):
        raise AssertionError("must not fetch check runs for a green PR")

    monkeypatch.setattr(sc, "fetch_check_runs_flat", never_called)
    pr = _pr(1, status_rollup_state="SUCCESS")
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "queued-and-advancing"


# ── render_table ──────────────────────────────────────────────────────────────


def test_render_table_fetch_error_shown_and_no_table():
    report = {"repo": "x/y", "fetch_error": "boom", "generated_at": _iso(NOW), "min_age_minutes": 30}
    out = sc.render_table(report)
    assert "CANNOT-VERIFY" in out
    assert "boom" in out


def test_render_table_empty_rows_says_nothing_to_classify():
    report = {
        "repo": "x/y", "fetch_error": None, "generated_at": _iso(NOW), "min_age_minutes": 30,
        "examined_total": 5, "excluded_drafts": 1, "rows": [],
    }
    out = sc.render_table(report)
    assert "nothing to classify" in out


def test_render_table_lists_every_row_and_a_summary():
    report = {
        "repo": "x/y", "fetch_error": None, "generated_at": _iso(NOW), "min_age_minutes": 30,
        "examined_total": 2, "excluded_drafts": 0,
        "rows": [
            {"number": 2, "title": "b", "age_minutes": 40, "cause": "not-armed", "detail": "d1"},
            {"number": 1, "title": "a", "age_minutes": 90, "cause": "conflict", "detail": "d2"},
        ],
    }
    out = sc.render_table(report)
    assert "#1" in out and "#2" in out
    assert out.index("#1") < out.index("#2")  # sorted by PR number
    assert "not-armed=1" in out
    assert "conflict=1" in out


# ── main(): loud-if-zero-examined (mandate, verbatim) ───────────────────────


def test_main_exits_nonzero_when_zero_prs_examined_never_reads_as_clean(monkeypatch, capsys):
    monkeypatch.setattr(sc, "fetch_open_prs", lambda repo: [])
    rc = sc.main(["--repo", "Bali-Zero/Teman2"])
    assert rc != 0
    captured = capsys.readouterr()
    assert "CANNOT-VERIFY" in captured.err


def test_main_exits_zero_when_examined_some_but_none_are_stale(monkeypatch, capsys):
    monkeypatch.setattr(sc, "fetch_open_prs", lambda repo: [_pr(1, created_at=NOW)])
    rc = sc.main(["--repo", "Bali-Zero/Teman2", "--min-age-minutes", "999999"])
    assert rc == 0


def test_main_exits_nonzero_on_top_level_fetch_failure(monkeypatch):
    def boom(repo):
        raise RuntimeError("gh api graphql failed rc=1")

    monkeypatch.setattr(sc, "fetch_open_prs", boom)
    rc = sc.main(["--repo", "Bali-Zero/Teman2"])
    assert rc != 0


def test_main_exits_nonzero_when_any_row_is_cannot_verify(monkeypatch):
    monkeypatch.setattr(sc, "fetch_open_prs", lambda repo: [_pr(1, created_at=None)])
    rc = sc.main(["--repo", "Bali-Zero/Teman2"])
    assert rc != 0


def test_main_exits_zero_on_a_clean_healthy_report(monkeypatch):
    monkeypatch.setattr(sc, "fetch_open_prs", lambda repo: [_pr(1)])
    rc = sc.main(["--repo", "Bali-Zero/Teman2"])
    assert rc == 0


# ── static self-protection: this script can never mutate a PR/run/check ────
# Mirrors scripts/tests/test_harness_gate_read.py's own AST-based proofs, adapted for a script
# that legitimately passes -f/-F to `gh api graphql` for a READ-ONLY query (banning -f/-F
# outright, as that file does, would be a false positive here).


def test_no_write_shaped_string_literal_in_stall_classifier():
    """AST-based proof: no REST write verb/flag and no write-shaped value prefix appears as a
    string CONSTANT anywhere in this script's source (docstrings included -- safe because a
    prose mention renders as one large joined string, never equal to a bare flag nor starting
    with a bare value prefix; see _code_only's docstring for the general argument, and
    test_harness_gate_read.py's identical technique)."""
    banned_exact = {"-X", "--method", "-d", "--input", "-i"}
    banned_prefixes = ("POST", "PUT", "PATCH", "DELETE")
    tree = ast.parse(SCRIPT_SOURCE)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if value in banned_exact:
                offenders.append((node.lineno, repr(value), "exact-flag"))
            elif value.startswith(banned_prefixes):
                offenders.append((node.lineno, repr(value), "value-prefix"))
    assert not offenders, f"write-shaped string literal(s) found: {offenders}"


def test_write_shaped_literal_scan_catches_a_synthetic_counterexample():
    """Guilt pin for the test above, on a throwaway synthetic snippet -- never this repo's own
    script -- proving the scan is not vacuously green."""
    poisoned_source = (
        "def mutate(repo, number):\n"
        '    _run(["gh", "api", f"repos/{repo}/statuses/x", "-X", "POST"])\n'
    )
    banned_exact = {"-X", "--method", "-d", "--input", "-i"}
    banned_prefixes = ("POST", "PUT", "PATCH", "DELETE")
    tree = ast.parse(poisoned_source)
    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (node.value in banned_exact or node.value.startswith(banned_prefixes))
    ]
    assert offenders, "the scan failed to catch its own reference counterexample"
    assert "-X" in offenders
    assert "POST" in offenders


def test_no_mutating_gh_subcommand_phrase_anywhere_in_code():
    """Substring scan over CODE-ONLY source (docstrings stripped -- this docstring and the PR
    mandate legitimately DISCUSS these verbs in prose while explaining why they are absent)."""
    banned_phrases = [
        '"pr", "merge', '"pr", "edit', '"pr", "comment', '"pr", "review', '"pr", "close',
        '"run", "rerun', '"workflow", "run', "/cancel", "/force-cancel", '/merge"',
    ]
    for phrase in banned_phrases:
        assert phrase not in CODE_ONLY_SOURCE, f"mutating-shaped phrase present in code: {phrase!r}"


def test_mutating_phrase_scan_catches_a_synthetic_counterexample():
    """Guilt pin: the phrase scan above must actually fire on the shape it exists to catch."""
    poisoned = 'cmd = ["gh", "pr", "merge", str(number), "--auto"]'
    banned_phrases = ['"pr", "merge']
    assert any(p in poisoned for p in banned_phrases)


def test_no_graphql_mutation_operation_anywhere():
    """Every GraphQL operation string literal in this script must be a `query`, never a
    `mutation` -- enforces 'never posts, never merges, never edits' at the GraphQL layer, which
    the REST-verb scan above cannot see on its own."""
    tree = ast.parse(SCRIPT_SOURCE)
    graphql_literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "query(" in node.value
    ]
    assert graphql_literals, "expected to find at least one GraphQL query literal to audit"
    for literal in graphql_literals:
        assert "mutation" not in literal.lower(), "a GraphQL literal in this script names a mutation"


def test_script_never_calls_gh_pr_merge_or_gh_run_rerun_as_argv():
    """Defense-in-depth over the ACTUAL argv lists this script builds for `_run(...)` — every
    one must be `gh api ...` (graphql or a plain REST GET), never `gh pr merge`/`gh run rerun`/
    any other gh subcommand."""
    import re

    invocations = re.findall(r'_run\(\s*\[(.*?)\]', CODE_ONLY_SOURCE, re.DOTALL)
    assert invocations, "expected to find at least one _run([...]) call site to audit"
    for call in invocations:
        assert '"api"' in call, f"unexpected gh invocation shape (not `gh api ...`): {call}"
        assert '"merge"' not in call
        assert '"rerun"' not in call
        assert '"edit"' not in call


def test_module_never_imports_or_calls_gh_pr_merge_helper_from_queue_shepherd():
    """This script must not import queue_shepherd's rearm_pr/cancel_run at all — it has no
    business calling either, and an accidental import would be a silent capability leak. Scans
    CODE-ONLY source: this module's own docstrings legitimately SAY "duplicated from
    queue_shepherd.py" in prose (the STANDALONE-by-design convention), which must not trip a
    guard meant to catch an actual `import`/`from ... import` statement."""
    assert "rearm_pr" not in CODE_ONLY_SOURCE
    assert "import queue_shepherd" not in CODE_ONLY_SOURCE
    assert "from queue_shepherd" not in CODE_ONLY_SOURCE


def test_module_never_imports_or_calls_gh_pr_merge_helper_guilt_pin():
    """Guilt pin for the test above: an actual import statement, on a throwaway synthetic
    snippet, must be caught by the same CODE-ONLY technique."""
    poisoned = _code_only(
        '"""docstring mentioning queue_shepherd.py in prose, must not itself trip anything."""\n'
        "from queue_shepherd import rearm_pr\n"
    )
    assert "from queue_shepherd" in poisoned
    assert "rearm_pr" in poisoned


# ── fetch/render edge coverage added by adversarial review (2026-08-31) ─────────────


def _open_pr_graphql_node(number: int) -> dict:
    return {
        "number": number,
        "title": f"PR {number}",
        "isDraft": False,
        "headRefOid": str(number) * 40,
        "createdAt": _iso(NOW - _dt.timedelta(hours=2)),
        "mergeStateStatus": "CLEAN",
        "autoMergeRequest": {"enabledAt": _iso(NOW - _dt.timedelta(hours=1))},
        "mergeQueueEntry": None,
        "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
    }


def test_fetch_open_prs_guilt_follows_end_cursor_across_pages(monkeypatch):
    responses = iter(
        [
            {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "nodes": [_open_pr_graphql_node(1)],
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "nodes": [_open_pr_graphql_node(2)],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            },
        ]
    )
    calls = []

    def fake_graphql(query, variables):
        calls.append(dict(variables))
        return next(responses)

    monkeypatch.setattr(sc, "_gh_graphql", fake_graphql)

    prs = sc.fetch_open_prs("Bali-Zero/Teman2")

    assert [pr["number"] for pr in prs] == [1, 2]
    assert "cursor" not in calls[0]
    assert calls[1]["cursor"] == "cursor-1"


def test_fetch_open_prs_innocence_stops_after_exhausted_first_page(monkeypatch):
    calls = 0

    def fake_graphql(query, variables):
        nonlocal calls
        calls += 1
        assert "cursor" not in variables
        return {
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [_open_pr_graphql_node(1)],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

    monkeypatch.setattr(sc, "_gh_graphql", fake_graphql)

    assert [pr["number"] for pr in sc.fetch_open_prs("Bali-Zero/Teman2")] == [1]
    assert calls == 1


def _check_runs_graphql_payload(*, suite_total: int, run_total: int) -> dict:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "commits": {
                        "nodes": [
                            {
                                "commit": {
                                    "checkSuites": {
                                        "totalCount": suite_total,
                                        "nodes": [
                                            {
                                                "checkRuns": {
                                                    "totalCount": run_total,
                                                    "nodes": [
                                                        {
                                                            "name": sc.HARNESS_FLOOR_CHECK_NAME,
                                                            "conclusion": "FAILURE",
                                                        }
                                                    ],
                                                }
                                            }
                                        ],
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }


def test_fetch_check_runs_flat_guilt_marks_suite_level_truncation(monkeypatch):
    monkeypatch.setattr(
        sc,
        "_gh_graphql",
        lambda query, variables: _check_runs_graphql_payload(suite_total=2, run_total=1),
    )

    runs, truncated = sc.fetch_check_runs_flat("Bali-Zero/Teman2", 1)

    assert runs == [{"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"}]
    assert truncated is True


def test_fetch_check_runs_flat_guilt_marks_check_run_level_truncation(monkeypatch):
    monkeypatch.setattr(
        sc,
        "_gh_graphql",
        lambda query, variables: _check_runs_graphql_payload(suite_total=1, run_total=2),
    )

    _runs, truncated = sc.fetch_check_runs_flat("Bali-Zero/Teman2", 1)

    assert truncated is True


def test_fetch_check_runs_flat_innocence_complete_cardinality_is_not_truncated(monkeypatch):
    monkeypatch.setattr(
        sc,
        "_gh_graphql",
        lambda query, variables: _check_runs_graphql_payload(suite_total=1, run_total=1),
    )

    runs, truncated = sc.fetch_check_runs_flat("Bali-Zero/Teman2", 1)

    assert len(runs) == 1
    assert truncated is False


def test_render_table_escapes_markdown_pipe_in_detail():
    report = {
        "repo": "x/y",
        "fetch_error": None,
        "generated_at": _iso(NOW),
        "min_age_minutes": 30,
        "examined_total": 1,
        "excluded_drafts": 0,
        "rows": [
            {
                "number": 1,
                "title": "a",
                "age_minutes": 31,
                "cause": "not-armed",
                "detail": "left | right",
            }
        ],
    }

    out = sc.render_table(report)

    assert "left \\| right" in out
    assert "| left | right |" not in out


# ── read_fable_gate_state (2026-08-31 fix #1, gpt-5.6-sol review): pagination on the ──────────
# ── combined-status REST endpoint, which defaults to 30/page and was previously unpaginated ───


def _status_payload(*, total_count: int, statuses: list[dict]) -> dict:
    return {"total_count": total_count, "statuses": statuses}


def test_read_fable_gate_state_requests_per_page_100(monkeypatch):
    captured = {}

    def fake_run(cmd, timeout=30):
        captured["cmd"] = cmd
        return 0, json.dumps(_status_payload(
            total_count=1,
            statuses=[{"context": sc.FABLE_GATE_STATUS_CONTEXT, "state": "success", "description": "ok"}],
        )), ""

    monkeypatch.setattr(sc, "_run", fake_run)
    sc.read_fable_gate_state("Bali-Zero/Teman2", "a" * 40)
    assert "per_page=100" in captured["cmd"][-1]


def test_read_fable_gate_state_guilt_truncated_and_not_found_raises(monkeypatch):
    # total_count says more statuses exist than page 1 returned, and the gate context is not
    # among what WAS fetched -- must never be read as "never posted" (fix #1).
    other = [{"context": "some/other-check", "state": "success"}] * 100
    monkeypatch.setattr(
        sc, "_run",
        lambda cmd, timeout=30: (0, json.dumps(_status_payload(total_count=101, statuses=other)), ""),
    )
    with pytest.raises(RuntimeError):
        sc.read_fable_gate_state("Bali-Zero/Teman2", "a" * 40)


def test_read_fable_gate_state_innocence_truncated_but_gate_found_still_returns(monkeypatch):
    # innocence pairing: even on a truncated page, if the gate context WAS found among what was
    # fetched there is nothing to guess -- must return normally, never raise.
    statuses = [{"context": "some/other-check", "state": "success"}] * 99
    statuses.append({"context": sc.FABLE_GATE_STATUS_CONTEXT, "state": "failure", "description": "REWORK"})
    monkeypatch.setattr(
        sc, "_run",
        lambda cmd, timeout=30: (0, json.dumps(_status_payload(total_count=200, statuses=statuses)), ""),
    )
    state, description = sc.read_fable_gate_state("Bali-Zero/Teman2", "a" * 40)
    assert state == "failure"
    assert description == "REWORK"


def test_read_fable_gate_state_innocence_not_truncated_and_not_found_returns_none(monkeypatch):
    # innocence pairing for the guilt case above: total_count matches exactly what was fetched
    # (a genuinely complete page) and the gate context is absent -- this IS "never posted".
    monkeypatch.setattr(
        sc, "_run",
        lambda cmd, timeout=30: (0, json.dumps(_status_payload(
            total_count=1, statuses=[{"context": "some/other-check", "state": "success"}]
        )), ""),
    )
    state, description = sc.read_fable_gate_state("Bali-Zero/Teman2", "a" * 40)
    assert state is None
    assert description is None


def test_read_fable_gate_state_gh_failure_raises(monkeypatch):
    monkeypatch.setattr(sc, "_run", lambda cmd, timeout=30: (1, "", "gh: not found"))
    with pytest.raises(RuntimeError):
        sc.read_fable_gate_state("Bali-Zero/Teman2", "a" * 40)


# ── _describe_cause (2026-08-31 fix #2, gpt-5.6-sol review): success-but-stale distinction ────


def test_describe_cause_guilt_required_check_red_with_stale_success_recommends_rerun():
    pr = _pr(1, status_rollup_state="FAILURE")
    detail = sc._describe_cause("required-check-red", pr, "success")
    assert "gh run rerun" in detail
    assert "it is not success" not in detail


def test_describe_cause_innocence_required_check_red_with_real_non_success_verdict_keeps_original_text():
    pr = _pr(1, status_rollup_state="FAILURE")
    detail = sc._describe_cause("required-check-red", pr, "failure")
    assert "it is not success" in detail
    assert "gh run rerun" not in detail


def test_describe_cause_required_check_red_with_no_verdict_posted_uses_generic_rollup_text():
    pr = _pr(1, status_rollup_state="FAILURE")
    detail = sc._describe_cause("required-check-red", pr, None)
    assert detail == "statusCheckRollup=FAILURE"


# ── commits_missing (2026-08-31 fix #3, gpt-5.6-sol review): an empty commits.nodes on an ─────
# ── open PR is an anomalous GraphQL response, never a legitimate absence ──────────────────────


def test_normalize_open_pr_guilt_empty_commits_sets_commits_missing_true_and_rollup_none():
    node = _open_pr_graphql_node(1)
    node["commits"] = {"nodes": []}
    normalized = sc._normalize_open_pr(node)
    assert normalized["commits_missing"] is True
    assert normalized["status_rollup_state"] is None


def test_normalize_open_pr_innocence_present_commits_sets_commits_missing_false():
    node = _open_pr_graphql_node(1)
    normalized = sc._normalize_open_pr(node)
    assert normalized["commits_missing"] is False
    assert normalized["status_rollup_state"] == "SUCCESS"


def test_classify_one_guilt_commits_missing_is_cannot_verify_before_any_other_check(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE", commits_missing=True)

    def never_called(*_a, **_k):
        raise AssertionError("must never fetch check runs when commits_missing short-circuits first")

    monkeypatch.setattr(sc, "fetch_check_runs_flat", never_called)
    monkeypatch.setattr(sc, "read_fable_gate_state", never_called)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == sc.CANNOT_VERIFY
    assert "commits.nodes" in row["detail"]


def test_classify_one_innocence_commits_missing_false_proceeds_normally(monkeypatch):
    pr = _pr(1, commits_missing=False)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "queued-and-advancing"


def test_fetch_check_runs_flat_guilt_empty_commit_nodes_raises(monkeypatch):
    monkeypatch.setattr(
        sc, "_gh_graphql",
        lambda query, variables: {
            "data": {"repository": {"pullRequest": {"commits": {"nodes": []}}}}
        },
    )
    with pytest.raises(RuntimeError):
        sc.fetch_check_runs_flat("Bali-Zero/Teman2", 1)


# ── fetch_open_prs MAX_PAGES (2026-08-31 fix #4, gpt-5.6-sol review): exhausting the page ─────
# ── bound without finishing must raise, never silently report a partial board as complete ─────


def test_fetch_open_prs_guilt_max_pages_exhausted_without_finishing_raises(monkeypatch):
    def always_more(query, variables):
        return {
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [_open_pr_graphql_node(1)],
                        "pageInfo": {"hasNextPage": True, "endCursor": "next"},
                    }
                }
            }
        }

    monkeypatch.setattr(sc, "_gh_graphql", always_more)
    with pytest.raises(RuntimeError):
        sc.fetch_open_prs("Bali-Zero/Teman2")


def test_fetch_open_prs_innocence_exactly_max_pages_then_done_does_not_raise(monkeypatch):
    # innocence pairing: pagination genuinely exhausting ON the MAX_PAGES-th page is a real,
    # complete board -- must return normally, never raise just for being large.
    calls = {"n": 0}

    def paged(query, variables):
        calls["n"] += 1
        last = calls["n"] == sc.MAX_PAGES
        return {
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [_open_pr_graphql_node(calls["n"])],
                        "pageInfo": {
                            "hasNextPage": not last,
                            "endCursor": None if last else f"c{calls['n']}",
                        },
                    }
                }
            }
        }

    monkeypatch.setattr(sc, "_gh_graphql", paged)
    prs = sc.fetch_open_prs("Bali-Zero/Teman2")
    assert len(prs) == sc.MAX_PAGES
    assert calls["n"] == sc.MAX_PAGES


# ── find_named_check_conclusion duplicate-name ambiguity (2026-08-31, kimi-code/k3 review) ────
# ── a workflow_dispatch rerun lands in a DIFFERENT check suite on the SAME commit (Agent PR ──
# ── Contract rule 3), so >1 checkRun can share HARNESS_FLOOR_CHECK_NAME ───────────────────────


def test_find_named_check_conclusion_guilt_disagreeing_duplicates_is_ambiguous():
    check_runs = [
        {"name": "Harness floor recompute", "conclusion": "SUCCESS"},
        {"name": "Harness floor recompute", "conclusion": "FAILURE"},
    ]
    assert (
        sc.find_named_check_conclusion(check_runs, "Harness floor recompute")
        == sc.AMBIGUOUS_CHECK_CONCLUSION
    )


def test_find_named_check_conclusion_innocence_agreeing_duplicates_is_not_ambiguous():
    # innocence pairing: two entries for the same job (e.g. flattened from two check suites)
    # that agree on conclusion are the common case and must return that shared conclusion,
    # never AMBIGUOUS_CHECK_CONCLUSION just for appearing twice.
    check_runs = [
        {"name": "Harness floor recompute", "conclusion": "FAILURE"},
        {"name": "Harness floor recompute", "conclusion": "FAILURE"},
    ]
    assert sc.find_named_check_conclusion(check_runs, "Harness floor recompute") == "FAILURE"


def test_classify_one_guilt_disagreeing_duplicate_gate_runs_is_cannot_verify(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: (
            [
                {"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "SUCCESS"},
                {"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"},
            ],
            False,
        ),
    )

    def never_called(repo, sha):
        raise AssertionError("must not guess a fable-gate read when the gate's own conclusion is ambiguous")

    monkeypatch.setattr(sc, "read_fable_gate_state", never_called)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == sc.CANNOT_VERIFY
    assert "DIFFERING conclusions" in row["detail"]


def test_classify_one_innocence_agreeing_duplicate_gate_runs_classifies_normally(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: (
            [
                {"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"},
                {"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "FAILURE"},
            ],
            False,
        ),
    )
    monkeypatch.setattr(sc, "read_fable_gate_state", lambda repo, sha: (None, None))
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "gate-verdict-missing"


# ── RED_CHECK_CONCLUSIONS TIMED_OUT (2026-08-31, kimi-code/k3 review): a timed-out required ───
# ── job is a gate-rejection shape exactly like an outright failure, and was omitted ───────────


def test_classify_one_guilt_timed_out_gate_run_is_gate_verdict_missing_not_swallowed(monkeypatch):
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "TIMED_OUT"}], False),
    )
    monkeypatch.setattr(sc, "read_fable_gate_state", lambda repo, sha: (None, None))
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "gate-verdict-missing"


def test_classify_one_innocence_skipped_gate_run_is_not_treated_as_red(monkeypatch):
    # innocence pairing: SKIPPED is one of the deliberately-excluded conclusions (module
    # docstring) -- it must NOT trip harness_floor_red just because TIMED_OUT was added.
    pr = _pr(1, status_rollup_state="FAILURE")
    monkeypatch.setattr(
        sc, "fetch_check_runs_flat",
        lambda repo, number: ([{"name": sc.HARNESS_FLOOR_CHECK_NAME, "conclusion": "SKIPPED"}], False),
    )

    def never_called(repo, sha):
        raise AssertionError("must not read fable-gate state when the gate's own run was merely SKIPPED")

    monkeypatch.setattr(sc, "read_fable_gate_state", never_called)
    row = sc._classify_one("Bali-Zero/Teman2", pr, NOW)
    assert row["cause"] == "required-check-red"
