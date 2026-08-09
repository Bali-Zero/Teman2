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
