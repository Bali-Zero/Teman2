#!/usr/bin/env python3
"""scar_test for the WR2 reflexion layout-proposal routing gap (audit 2026-07-14, Wave-4 #16).

DISEASE: `wr2_reflexion_synthesis.py`'s synthesis prompt promised a `suggested_destination` of
"layouts/_proposed/<name>.md" for category="layout" lessons, but `write_lessons()` had no code
path that ever wrote there — the directory did not exist and no routing logic touched it. A
documented contract the code could not fulfil (research/operations/2026-07-14-wr2-deep-audit.md
§10 item 16).

ANTIBODY (this gate verifies it stays dead): `write_lessons()` now routes any lesson where
BOTH `category == "layout"` AND `suggested_destination` starts with "layouts/_proposed/" to
`_write_layout_proposal()`, which writes a proposal file into LAYOUTS_PROPOSED_DIR (the
repo-canonical `skills/bali-zero-brand/layouts/_proposed/` dir, not a HOME-fork target —
cicatrix-superscar #1).

Guilt+innocence corpus per cicatrix-superscar #3 (guard-over-match discipline — the routing
condition must match on the structured fields, never a bare substring of lesson_text):
  - guilty:   category="layout"  + dest="layouts/_proposed/x.md"  -> file written
  - innocent: category="voice"   + dest="voice/on-tone-examples.md" -> no layout file
  - innocent: category="layout"  + dest="voice/on-tone-examples.md" -> no layout file
              (category alone is not enough — the destination must agree)
  - innocent: category="voice"   + dest="layouts/_proposed/x.md"    -> no layout file
              (a stray destination string alone is not enough — category must agree)

Runnable both as a bare script (scar_test contract: `[sys.executable, this_file]`) and under
pytest. No real claude -p, no real DB: paths are env-overridden (WR2_SKILL_DIR /
WR2_LAYOUTS_PROPOSED_DIR), mirroring test_wr2_reflexion_cabling.py's pattern.
"""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "wr2_reflexion_synthesis.py"


def _load_target(env_overrides):
    """Import the target module fresh with env paths applied (module reads env at import)."""
    for k, v in env_overrides.items():
        os.environ[k] = str(v)
    sys.modules.pop("wr2_reflexion_synthesis_layout_test", None)
    spec = importlib.util.spec_from_file_location(
        "wr2_reflexion_synthesis_layout_test", str(TARGET)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lesson(category, dest, text="Lesson under test", addition="Body text"):
    return {
        "lesson_text": text,
        "category": category,
        "confidence": "medium",
        "motivating_run_ids": [1, 2, 3],
        "proposes_amendment": False,
        "suggested_destination": dest,
        "suggested_addition": addition,
    }


def _synthesis(*lessons):
    return {"week": "2026-W29", "lessons": list(lessons), "synthesis_notes": "test"}


def test_layout_lesson_writes_proposal_file():
    """Guilty case: category=layout + dest=layouts/_proposed/<name>.md writes a file there."""
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        layouts_proposed = Path(td) / "layouts-proposed"
        mod = _load_target({"WR2_SKILL_DIR": skill, "WR2_LAYOUTS_PROPOSED_DIR": layouts_proposed})

        lesson = _lesson("layout", "layouts/_proposed/dark-status-list-alt.md",
                          text="dark-status-list should default to 4 bullets not 5")
        n = mod.write_lessons(_synthesis(lesson))

        assert n == 1
        assert layouts_proposed.exists(), "layout _proposed dir must be created on write"
        files = list(layouts_proposed.glob("*.md"))
        assert len(files) == 1, f"expected exactly one proposal file, got {files!r}"
        assert files[0].name == "2026-W29-dark-status-list-alt.md"
        content = files[0].read_text()
        assert "dark-status-list should default to 4 bullets not 5" in content
        assert "operator review" in content
    print("PASS layout lesson (category=layout + layouts/_proposed dest) writes proposal file")


def test_non_layout_lesson_does_not_write_layout_proposal():
    """Innocent case: an ordinary voice lesson must not touch the layout _proposed dir at all."""
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        layouts_proposed = Path(td) / "layouts-proposed"
        mod = _load_target({"WR2_SKILL_DIR": skill, "WR2_LAYOUTS_PROPOSED_DIR": layouts_proposed})

        lesson = _lesson("voice", "voice/on-tone-examples.md")
        mod.write_lessons(_synthesis(lesson))

        assert not layouts_proposed.exists(), \
            "a non-layout lesson must never create the layout _proposed dir"
    print("PASS non-layout lesson (category=voice) never touches layout _proposed dir")


def test_mismatched_category_and_destination_do_not_route():
    """Innocent case: category and destination must BOTH agree — neither alone is sufficient.

    Guards against a bare substring/single-field match (cicatrix-superscar #3): a stray
    "layouts/_proposed/" string with the wrong category, or category="layout" pointing
    somewhere else, must not fire the layout routing.
    """
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        layouts_proposed = Path(td) / "layouts-proposed"
        mod = _load_target({"WR2_SKILL_DIR": skill, "WR2_LAYOUTS_PROPOSED_DIR": layouts_proposed})

        category_layout_wrong_dest = _lesson("layout", "voice/on-tone-examples.md")
        voice_category_layout_dest = _lesson("voice", "layouts/_proposed/stray.md")
        mod.write_lessons(_synthesis(category_layout_wrong_dest, voice_category_layout_dest))

        assert not layouts_proposed.exists(), \
            "routing must require category AND destination to agree, not either alone"
    print("PASS mismatched category/destination pairs do not route (guilt+innocence discipline)")


def test_placeholder_name_falls_back_to_slug():
    """If the LLM echoes the literal '<name>.md' placeholder, fall back to a lesson-text slug."""
    with tempfile.TemporaryDirectory() as td:
        skill = Path(td) / "skill"
        skill.mkdir()
        layouts_proposed = Path(td) / "layouts-proposed"
        mod = _load_target({"WR2_SKILL_DIR": skill, "WR2_LAYOUTS_PROPOSED_DIR": layouts_proposed})

        lesson = _lesson("layout", "layouts/_proposed/<name>.md",
                          text="Evidence-carved needs a citation footer on mobile crops")
        mod.write_lessons(_synthesis(lesson))

        files = list(layouts_proposed.glob("*.md"))
        assert len(files) == 1, f"expected exactly one proposal file, got {files!r}"
        assert "<name>" not in files[0].name, "literal placeholder must not leak into filename"
        assert files[0].name.startswith("2026-W29-evidence-carved-needs-a-citation")
    print("PASS literal '<name>.md' placeholder falls back to a slugged filename")


def main():
    tests = [
        test_layout_lesson_writes_proposal_file,
        test_non_layout_lesson_does_not_write_layout_proposal,
        test_mismatched_category_and_destination_do_not_route,
        test_placeholder_name_falls_back_to_slug,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}", file=sys.stderr)
            failed += 1
        except Exception as e:  # noqa: BLE001 — a crash is a failed scar gate
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}", file=sys.stderr)
            failed += 1
    total = len(tests)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
