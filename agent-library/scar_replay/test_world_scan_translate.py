#!/usr/bin/env python3
"""Test the world-scan translator's deterministic grade WITHOUT network.

The whole anti-"plausible-wisdom" firewall lives in _grade(): an LLM saying
"ADOPT" is not enough — the draft must contain the structural ingredients of a
real executable probe. These tests pin that gate.
"""
from __future__ import annotations

import world_scan_translate as wt


def _good_dict():
    return {
        "applicable": True,
        "expressible": True,
        "family": "stale_lock_not_released",
        "incident_summary": (
            "A cron job acquires a file lock then crashes before releasing it; "
            "the next run blocks forever waiting on the orphaned lock."
        ),
        "contract": (
            "The antibody receives LOCK_PATH and MAX_AGE_SECONDS; it must ensure "
            "a lock older than MAX_AGE_SECONDS is treated as stale and reclaimed."
        ),
        "fixture_sketch": (
            "mktemp -d; create LOCK_PATH with an mtime 2h in the past via touch -t; "
            "run the job's lock-acquire step under the antibody."
        ),
        "assertion_sketch": (
            "after the antibody runs, exit code is 0 and the job proceeded "
            "(grep the run-log for 'acquired'); the stale lock file was removed."
        ),
        "baseline_fails_rationale": (
            "without the antibody the acquire blocks/aborts; exit code != 0."
        ),
    }


def test_good_pattern_is_adopt():
    cat, ok, reasons = wt._grade(_good_dict())
    assert cat == "ADOPT", f"a fully-specified executable probe must be ADOPT, reasons={reasons}"
    assert ok is True
    assert reasons == []


def test_not_applicable_is_reject():
    d = _good_dict()
    d["applicable"] = False
    cat, ok, reasons = wt._grade(d)
    assert cat == "REJECT" and ok is False


def test_not_expressible_is_observe():
    d = _good_dict()
    d["expressible"] = False
    cat, ok, reasons = wt._grade(d)
    assert cat == "OBSERVE", "a real-but-unsandboxable failure class is OBSERVE, not ADOPT"
    assert ok is False


def test_assertion_that_defers_to_llm_is_not_adopt():
    d = _good_dict()
    d["assertion_sketch"] = "an LLM reviews whether the output looks correct and reasonable"
    cat, ok, reasons = wt._grade(d)
    assert ok is False, "an assertion that defers to an LLM judgment must NOT be executable"
    assert cat == "OBSERVE"
    assert any("judgment" in r for r in reasons)


def test_assertion_without_executable_markers_is_not_adopt():
    d = _good_dict()
    d["assertion_sketch"] = "the system behaves better afterwards"  # vague, no markers
    cat, ok, reasons = wt._grade(d)
    assert ok is False
    assert any("executable markers" in r for r in reasons)


def test_thin_fixture_is_not_adopt():
    d = _good_dict()
    d["fixture_sketch"] = "do stuff"  # too short
    cat, ok, reasons = wt._grade(d)
    assert ok is False
    assert any("fixture_sketch too thin" in r for r in reasons)


def test_bad_family_id_flagged():
    d = _good_dict()
    d["family"] = "Stale Lock!"  # not snake_case
    cat, ok, reasons = wt._grade(d)
    assert ok is False
    assert any("family id not snake_case" in r for r in reasons)


def test_render_does_not_crash_and_shows_category():
    draft = wt.translate_pattern.__wrapped__ if hasattr(wt.translate_pattern, "__wrapped__") else None
    # build a DraftProbe directly to test rendering
    d = wt.DraftProbe(pattern_title="Test pattern", category="ADOPT", family="x_y_z",
                      incident_summary="s", contract="c", fixture_sketch="f",
                      assertion_sketch="exit code 0", baseline_fails_rationale="b",
                      executable=True)
    md = wt.render_draft_md(d)
    assert "ADOPT" in md and "Test pattern" in md
    assert "scar_probes.py" in md  # the human-promotion instruction is present


def test_extract_json_tolerates_fences():
    assert wt._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert wt._extract_json('prose before {"b": 2} prose after') == {"b": 2}
    assert wt._extract_json("no json here") is None


def _main() -> int:
    fails = []
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            fails.append(t.__name__)
        except Exception as e:  # noqa
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            fails.append(t.__name__)
    print(f"\n{len(tests)-len(fails)}/{len(tests)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(_main())
