"""Tests for proprioception.py's run_wrap() exit_code parser (§5-docsync-underreport).

THE BUG (2026-08-07): a `parse: "exit_code"` registry entry (docs_sync is the only one
in DEFAULT_REGISTRY) hardcoded n_findings=1 on any non-zero rc and took only the LAST
line of the wrapped tool's combined output as evidence. docs_sync.py --check emits a
"DOCSYNC STALE — run: ..." header line followed by ONE detail line per stale target
file; with 2 stale files (README.md, docs/AI_ONBOARDING.md) this silently dropped the
first (README.md) and reported "1 finding" where there were 2 — the proprioception
report SessionStart and the healers read under-counted by construction.

The fix treats a multi-line failure as header + detail lines (header dropped, detail
lines counted and surfaced, capped at 5 with an explicit "N of M" note on truncation)
while preserving the original single-line / empty-output shapes exactly, per the
generator's own guilt/innocence spec.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)  # type: ignore[union-attr]


# ---------------------------------------------------------------- guilt: under-report

def test_multiline_failure_counts_detail_lines_not_hardcoded_one() -> None:
    """The bug's exact shape: header + 2 detail lines must yield 2 findings, BOTH
    detail lines present in evidence (not just the last one)."""
    out = "DOCSYNC STALE — run: python scripts/docs_sync.py\n" \
          "  README.md: aaaa -> bbbb\n" \
          "  docs/AI_ONBOARDING.md: cccc -> dddd\n"
    status, n, ev = prop._parse_exit_code(1, "", out)
    assert status == prop.DIVERGED
    assert n == 2
    assert any("README.md" in e for e in ev)
    assert any("AI_ONBOARDING.md" in e for e in ev)


def test_real_docs_sync_two_file_shape_matches_the_reported_bug() -> None:
    """Same case reproduced on stderr (docs_sync.py's real stream) — the wrapper reads
    (out or err), and docs_sync writes everything to stderr under --check."""
    err = "DOCSYNC STALE — run: python scripts/docs_sync.py\n" \
          "  README.md: 85d7e38416c6 -> 994993795a72\n" \
          "  docs/AI_ONBOARDING.md: 38e62b1fcd36 -> 24df2f705603\n"
    status, n, ev = prop._parse_exit_code(1, "", err)
    assert status == prop.DIVERGED
    assert n == 2  # was 1 before the fix
    assert len(ev) == 2
    assert "README.md" in ev[0]
    assert "AI_ONBOARDING.md" in ev[1]


def test_header_line_is_never_counted_as_a_finding() -> None:
    out = "SOME TOOL FAILED — run: fix-it\n  only-detail-line\n"
    status, n, ev = prop._parse_exit_code(1, out, "")
    assert n == 1
    assert ev == ["  only-detail-line"]
    assert not any("SOME TOOL FAILED" in e for e in ev)


def test_six_detail_lines_reports_full_count_and_truncation_note() -> None:
    header = "HEADER LINE\n"
    details = "".join(f"  detail-{i}\n" for i in range(1, 7))
    status, n, ev = prop._parse_exit_code(1, header + details, "")
    assert status == prop.DIVERGED
    assert n == 6
    # capped display, but the truncation is stated explicitly (W97: never a bare slice)
    assert len(ev) == prop._EXIT_CODE_EVIDENCE_CAP + 1
    assert any("5 of 6" in e for e in ev)
    for i in range(1, 6):
        assert any(f"detail-{i}" in e for e in ev)
    # the 6th detail line is the one that got truncated out of the capped display
    assert not any("detail-6" in e for e in ev[:5])


# ---------------------------------------------------------------- innocence

def test_rc_zero_is_zero_findings_even_with_chatty_output() -> None:
    """A successful tool that still prints something is not a finding."""
    status, n, ev = prop._parse_exit_code(0, "all good, nothing to see\nreally\n", "")
    assert status == prop.RECONCILED
    assert n == 0
    assert ev == []


def test_single_line_failure_keeps_original_shape() -> None:
    """No header to strip when there's only one line — today's exact behaviour."""
    status, n, ev = prop._parse_exit_code(1, "the one and only failure line", "")
    assert status == prop.DIVERGED
    assert n == 1
    assert ev == ["the one and only failure line"]


def test_empty_output_falls_back_to_exit_code_marker() -> None:
    status, n, ev = prop._parse_exit_code(1, "", "")
    assert status == prop.DIVERGED
    assert n == 1
    assert ev == ["exit 1"]


def test_empty_output_whitespace_only_also_falls_back() -> None:
    status, n, ev = prop._parse_exit_code(3, "   \n  \n", "")
    assert status == prop.DIVERGED
    assert n == 1
    assert ev == ["exit 3"]


def test_run_wrap_end_to_end_with_real_multiline_python_tool(tmp_path: Path) -> None:
    """Exercise the full run_wrap() path (not just the helper) against a real
    subprocess, so the fix is proven wired in, not just unit-correct in isolation."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    tool = repo / "scripts" / "fake_exit_code_tool.py"
    tool.write_text(
        "import sys\n"
        "print('TOOL STALE — run: fix-it', file=sys.stderr)\n"
        "print('  itemA: x -> y', file=sys.stderr)\n"
        "print('  itemB: x -> y', file=sys.stderr)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    entry = {"target": ["python3", "{repo}/scripts/fake_exit_code_tool.py"], "parse": "exit_code"}
    status, n, ev = prop.run_wrap(repo, entry, 10)
    assert status == prop.DIVERGED
    assert n == 2
    assert any("itemA" in e for e in ev)
    assert any("itemB" in e for e in ev)


# ---------------------------------------------------------------- mutation guard

def test_mutation_guilt_fails_without_the_fix() -> None:
    """Proves the guilt test actually distinguishes the fix from the pre-fix code:
    re-implement the OLD (buggy) behaviour inline and confirm it does NOT satisfy the
    guilt assertions — i.e. the guilt test goes red if the fix is reverted."""
    def _old_buggy_exit_code(rc: int, out: str, err: str) -> tuple[str, int, list[str]]:
        return (prop.RECONCILED if rc == 0 else prop.DIVERGED), (0 if rc == 0 else 1), \
            ([] if rc == 0 else [(out or err).strip().splitlines()[-1][:160]
                                  if (out or err).strip() else f"exit {rc}"])

    out = "DOCSYNC STALE — run: python scripts/docs_sync.py\n" \
          "  README.md: aaaa -> bbbb\n" \
          "  docs/AI_ONBOARDING.md: cccc -> dddd\n"
    status, n, ev = _old_buggy_exit_code(1, "", out)
    # the old code hardcoded n=1 and kept only the LAST line — assert that shape to
    # prove this is really the pre-fix behaviour, then assert it fails the new spec
    assert n == 1
    assert ev == ["  docs/AI_ONBOARDING.md: cccc -> dddd"]
    assert not any("README.md" in e for e in ev)  # the dropped line — this is the bug


# ================================================================ mutation round
# (lane 4, 2026-10-12). run_wrap's findings_list / category_counts parsers and its
# "could not look" exits were reachable by mutation without a red test. UNPROBEABLE is
# a third state: "could not look" is never RECONCILED and never DIVERGED, and carries
# ZERO findings.

import json  # noqa: E402

import pytest  # noqa: E402


def _cat(tmp_path: Path, payload: object, *, raw: str | None = None) -> list[str]:
    """argv that prints `payload` as JSON (or `raw` verbatim) and exits 0."""
    f = tmp_path / "payload.out"
    f.write_text(raw if raw is not None else json.dumps(payload), encoding="utf-8")
    return ["cat", str(f)]


def _wrap(tmp_path: Path, payload: object, **entry) -> tuple[str, int, list[str]]:
    raw = entry.pop("raw", None)
    e = {"target": _cat(tmp_path, payload, raw=raw), **entry}
    return prop.run_wrap(tmp_path, e, 10)


# ---------------------------------------------------------------- could not look

def test_missing_python_script_is_unprobeable_with_zero_findings(tmp_path: Path) -> None:
    status, n, ev = prop.run_wrap(
        tmp_path, {"target": ["python3", "{repo}/scripts/nope_tool.py"], "parse": "exit_code"}, 10)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("nope_tool.py" in e for e in ev)


def test_unknown_command_is_unprobeable_with_zero_findings(tmp_path: Path) -> None:
    status, n, ev = prop.run_wrap(
        tmp_path, {"target": ["no-such-binary-zz9", "--check"], "parse": "exit_code"}, 10)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("no-such-binary-zz9" in e for e in ev)


def test_python_prefixed_name_without_args_is_unprobeable_not_a_crash(tmp_path: Path) -> None:
    """argv[1] does not exist for a one-element argv; it must fall through to the
    which() check instead of indexing past the end."""
    status, n, ev = prop.run_wrap(
        tmp_path, {"target": ["python-no-such-interp-zz9"], "parse": "exit_code"}, 10)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("wrapped command not found" in e for e in ev)


def test_non_python_command_with_args_is_not_mistaken_for_a_missing_script(tmp_path: Path) -> None:
    """Innocence twin: `sh -c ...` has argv[1] == '-c', which is not a file. Only a
    python-prefixed argv0 is held to the 'script exists' check."""
    status, n, ev = prop.run_wrap(
        tmp_path, {"target": ["sh", "-c", "exit 0"], "parse": "exit_code"}, 10)
    assert (status, n, ev) == (prop.RECONCILED, 0, [])


def test_existing_python_script_runs(tmp_path: Path) -> None:
    tool = tmp_path / "ok_tool.py"
    tool.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    status, n, _ = prop.run_wrap(
        tmp_path, {"target": ["python3", "{repo}/ok_tool.py"], "parse": "exit_code"}, 10)
    assert (status, n) == (prop.RECONCILED, 0)


def test_timeout_is_unprobeable_with_zero_findings(tmp_path: Path) -> None:
    status, n, ev = prop.run_wrap(
        tmp_path, {"target": ["sh", "-c", "sleep 5"], "parse": "exit_code"}, 1)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("timed out" in e for e in ev)


def test_unusable_working_directory_is_unprobeable_with_zero_findings(tmp_path: Path) -> None:
    status, n, ev = prop.run_wrap(
        tmp_path / "does-not-exist", {"target": ["sh", "-c", "exit 0"], "parse": "exit_code"}, 10)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("missing" in e for e in ev)


# ---------------------------------------------------------------- non-JSON / unknown mode

@pytest.mark.parametrize("parse", ["findings_list", "category_counts"])
def test_non_json_output_is_unprobeable_not_clean(tmp_path: Path, parse: str) -> None:
    status, n, ev = _wrap(tmp_path, None, raw="Traceback (most recent call last)", parse=parse)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("non-JSON output" in e for e in ev)


def test_empty_output_is_unprobeable_not_clean(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, None, raw="", parse="findings_list")
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("expected JSON list" in e for e in ev)


def test_unknown_parse_mode_is_unprobeable(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, {"x": 1}, parse="made_up_mode")
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("unknown parse mode made_up_mode" in e for e in ev)


# ---------------------------------------------------------------- findings_list

_FL = {"parse": "findings_list", "verdict_key": "state", "ok_values": ["ok", "fresh"]}


def test_findings_list_items_outside_ok_values_are_the_findings(tmp_path: Path) -> None:
    data = [{"state": "ok", "id": "a"}, {"state": "STALE", "id": "b"},
            {"state": "fresh", "id": "c"}, {"state": "GONE", "id": "d"}]
    status, n, ev = _wrap(tmp_path, data, **_FL)
    assert (status, n) == (prop.DIVERGED, 2)
    assert len(ev) == 2
    assert '"id": "b"' in ev[0] and '"id": "d"' in ev[1]


def test_findings_list_all_ok_is_reconciled(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, [{"state": "ok"}, {"state": "fresh"}], **_FL)
    assert (status, n, ev) == (prop.RECONCILED, 0, [])


def test_findings_list_empty_list_is_reconciled_not_schema_drift(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, [], **_FL)
    assert (status, n, ev) == (prop.RECONCILED, 0, [])


def test_findings_list_items_without_the_verdict_key_are_schema_drift(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, [{"other": 1}, {"other": 2}], **_FL)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("no item carries key 'state'" in e for e in ev)


def test_findings_list_one_item_carrying_the_key_is_not_drift(tmp_path: Path) -> None:
    status, n, _ = _wrap(tmp_path, [{"state": "ok"}, {"state": "fresh", "x": 1}], **_FL)
    assert (status, n) == (prop.RECONCILED, 0)


def test_findings_list_without_verdict_key_every_item_is_a_finding(tmp_path: Path) -> None:
    """No verdict_key declared: the list IS the findings, and is not drift."""
    status, n, ev = _wrap(tmp_path, [{"a": 1}, {"b": 2}, {"c": 3}], parse="findings_list")
    assert (status, n) == (prop.DIVERGED, 3)
    assert len(ev) == 3


def test_findings_list_unwrap_key_present(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, {"meta": 1, "rows": [{"state": "BAD"}]},
                          unwrap_key="rows", **_FL)
    assert (status, n) == (prop.DIVERGED, 1)
    assert "BAD" in ev[0]


def test_findings_list_unwrap_key_absent_is_schema_drift_not_clean(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, {"meta": 1, "other": []}, unwrap_key="rows", **_FL)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("key 'rows' absent" in e for e in ev)


def test_findings_list_bare_list_with_unwrap_key_declared_is_still_read(tmp_path: Path) -> None:
    """Innocence: unwrap_key only applies to an object; a tool that emits the bare
    list is not drift."""
    status, n, _ = _wrap(tmp_path, [{"state": "BAD"}], unwrap_key="rows", **_FL)
    assert (status, n) == (prop.DIVERGED, 1)


def test_findings_list_object_without_unwrap_key_is_not_a_list(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, {"state": "ok"}, **_FL)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("expected JSON list, got dict" in e for e in ev)


def test_findings_list_scalar_is_not_a_list(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, 7, **_FL)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("expected JSON list, got int" in e for e in ev)


# ---------------------------------------------------------------- category_counts

_CC = {"parse": "category_counts", "bad_categories": ["stale", "missing"],
       "ok_categories": ["fresh"]}


def test_category_counts_bad_categories_with_members_are_findings(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, {"stale": ["a", "b"], "missing": ["c"], "fresh": ["d", "e", "f"]}, **_CC)
    assert (status, n) == (prop.DIVERGED, 3)
    assert sorted(ev) == ["missing: 1", "stale: 2"]


def test_category_counts_empty_bad_and_populated_ok_is_reconciled(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, {"stale": [], "missing": [], "fresh": ["d"]}, **_CC)
    assert (status, n, ev) == (prop.RECONCILED, 0, [])


def test_category_counts_populated_undeclared_category_is_not_a_finding(tmp_path: Path) -> None:
    status, n, _ = _wrap(tmp_path, {"fresh": ["d"], "novel": ["x", "y"]}, **_CC)
    assert (status, n) == (prop.RECONCILED, 0)


def test_category_counts_only_one_declared_category_present_is_not_drift(tmp_path: Path) -> None:
    status, n, _ = _wrap(tmp_path, {"fresh": ["d"]}, **_CC)
    assert (status, n) == (prop.RECONCILED, 0)


def test_category_counts_none_of_the_declared_categories_is_schema_drift(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, {"renamed_stale": ["a"]}, **_CC)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("none of the declared categories present" in e for e in ev)


def test_category_counts_nothing_declared_is_not_drift(tmp_path: Path) -> None:
    status, n, _ = _wrap(tmp_path, {"x": ["a"]}, parse="category_counts")
    assert (status, n) == (prop.RECONCILED, 0)


def test_category_counts_list_is_not_an_object(tmp_path: Path) -> None:
    status, n, ev = _wrap(tmp_path, ["stale"], **_CC)
    assert (status, n) == (prop.UNPROBEABLE, 0)
    assert any("expected JSON object, got list" in e for e in ev)


# ---------------------------------------------------------------- tri_state evidence cap

def _tri_wrap(tmp_path: Path, body: object) -> tuple[str, int, list[str]]:
    f = tmp_path / "tri.out"
    f.write_text(json.dumps(body), encoding="utf-8")
    return prop.run_wrap(
        tmp_path, {"target": ["sh", "-c", f"cat {f}; exit 1"], "parse": "tri_state_exit"}, 10)


@pytest.mark.parametrize("given,shown", [(4, 4), (5, 5), (6, 5), (9, 5)])
def test_tri_state_diverged_count_matches_the_capped_evidence(
        tmp_path: Path, given: int, shown: int) -> None:
    status, n, ev = _tri_wrap(tmp_path, {"evidence": [f"item-{i}" for i in range(given)]})
    assert status == prop.DIVERGED
    assert n == len(ev) == shown
