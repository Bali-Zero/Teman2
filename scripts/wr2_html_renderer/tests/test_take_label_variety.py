"""take_label variety gate tests (evidence-carved, 2026-07-16 — kills the
single-example "OUR TAKE"/"OUR READ" anchor: ground-ourread audit found 6/6
evidence-carved carousels in the corpus used the same pair, because it was
the ONLY example anywhere in the doctrine).

Two layers, two test suites:
- composer._check_take_label_variety / _take_label_violation — WARN-only,
  never raises (composer has no queue/publish-state visibility).
- wr2_html_render_apply's pure helpers — the HARD gate for not-yet-published
  drafts, which DOES have that visibility via the review queue.

Guilt AND innocence per the guard-conformance doctrine (scar family #3 —
substring trapping): every guard needs a test that proves it fires on a real
violation and a test that proves it does NOT fire on a legitimate neighbor —
here, "TAKEAWAY FOR SELLERS" contains the substring "TAKE" but must not
trigger a whole-string banned-label match.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from wr2_html_renderer import composer as C  # noqa: E402


# --- GUILT: exact banned labels fire, case/whitespace-insensitive ----------


@pytest.mark.parametrize(
    "label",
    ["OUR TAKE", "OUR READ", "OUR VIEW", "TAKE", "FACT", "FACTS", "NOTE", "REALITY", "KEY FACT"],
)
def test_guilt_banned_label_exact_match_fires(label):
    assert C._take_label_violation({"take_label": label}) == label


@pytest.mark.parametrize("label", ["our take", "Our Read", "  OUR VIEW  ", "key fact"])
def test_guilt_banned_label_case_and_whitespace_insensitive(label):
    assert C._take_label_violation({"take_label": label}) is not None


def test_guilt_check_logs_warning_never_raises(caplog):
    import logging

    slide = {"take_label": "OUR TAKE", "take_line": "one month, one category."}
    with caplog.at_level(logging.WARNING, logger="wr2.composer"):
        result = C._check_take_label_variety(slide, index=2)
    assert result is None  # never raises
    assert any("take_label variety" in r.message for r in caplog.records)
    assert any("OUR TAKE" in r.message for r in caplog.records)


# --- INNOCENCE: substring-only match must NOT fire -------------------------


@pytest.mark.parametrize(
    "label",
    [
        "TAKEAWAY FOR SELLERS",
        "THE UPSHOT",
        "WHERE THIS LANDS",
        "THE VERDICT",
        "THE BOTTOM LINE",
        "WHAT WE'RE SEEING",
        "THE STAKES",
        "BETWEEN THE LINES",
        "THE SIGNAL",
        "THE TRADE-OFF",
        "WHAT CHANGES NOW",
    ],
)
def test_innocence_non_banned_kicker_does_not_fire(label):
    assert C._take_label_violation({"take_label": label}) is None


def test_innocence_no_take_label_field_does_not_fire():
    assert C._take_label_violation({"heading": "THE EVIDENCE"}) is None


def test_innocence_check_logs_nothing_for_legit_kicker(caplog):
    import logging

    slide = {"take_label": "THE VERDICT"}
    with caplog.at_level(logging.WARNING, logger="wr2.composer"):
        result = C._check_take_label_variety(slide, index=2)
    assert result is None
    assert not any("take_label variety" in r.message for r in caplog.records)


def test_wired_into_constitution_gate_never_raises_on_banned_label():
    """_check_slide_constitution_gates is the single call site compose_carousel
    and materialize_slide_html both use — confirm take_label is wired in and
    stays WARN-only there too (no accidental hard-fail regression)."""
    slide = {
        "headline": "SPT DEADLINE EXTENDED",
        "body": "New SPT Tahunan PPh Badan deadline moves to 31 May 2026 for "
        "PT, PT PMA, CV, and UD taxpayers, automatically, with no application "
        "or lampiran required from any registered taxpayer this filing year.",
        "take_label": "OUR TAKE",
        "take_line": "one month, one category, no application.",
    }
    # facts-stack body would exempt Article 6.1; this is prose in-range so it
    # also exercises that gate cleanly alongside take_label.
    result = C._check_slide_constitution_gates("<div>{{body}}</div>", slide, index=4, family="editorial-text")
    assert result is None
