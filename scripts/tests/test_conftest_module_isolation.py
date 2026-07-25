"""Regression pin for the W96 module-identity isolation (conftest autouse
`_wr2_module_identity_isolation`, 2026-07-25).

12 WR2 test fixtures pop+reimport a `wr2_*` module WITHOUT restoring it (e.g.
`wdg` in test_wr2_draft_generator_cover_codex_detection.py), leaking a fresh
module instance. A LATER test's `patch("wr2_X.attr", ...)` then patches the
fresh instance while the test holds a reference (from its own collection) to the
OLD one — the patch silently misses and the real code path runs (observed live:
test_compose_slides_forwards_tier_into_prompt fell through to a real `claude` CLI
subprocess after cover_codex_detection ran, but ONLY mid-batch).

The conftest autouse fixture must restore the pre-test module identity after
EACH test. These two tests, run in file order, assert exactly that: test_a leaks
a swapped instance; test_b (a separate test) must see the ORIGINAL restored.
Without the fixture, test_b fails — guilt + innocence in one deterministic
sequence. (This repo's CI does not run pytest-randomly, so file order holds.)
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Imported at COLLECTION so it is present in the fixture's pre-test snapshot
# (a module first-imported *inside* a test is intentionally dropped, not restored).
import wr2_carousel_ir  # noqa: E402,F401

_SEEN: dict[str, int] = {}


def test_a_leaks_a_swapped_wr2_module() -> None:
    # guilt: mimic the `wdg`/`wig` pop+reimport that leaks a fresh instance.
    _SEEN["orig_id"] = id(sys.modules["wr2_carousel_ir"])
    sys.modules.pop("wr2_carousel_ir", None)
    import wr2_carousel_ir as _fresh  # noqa: F401 — a NEW module instance
    assert id(sys.modules["wr2_carousel_ir"]) != _SEEN["orig_id"], "expected a swapped instance"


def test_b_conftest_restored_the_original_module() -> None:
    # innocence: the autouse conftest fixture restored the original after test_a,
    # so this test (and any real patch("wr2_carousel_ir.attr")) sees the canonical one.
    assert "orig_id" in _SEEN, "test_a must run before test_b (file order)"
    assert id(sys.modules["wr2_carousel_ir"]) == _SEEN["orig_id"], (
        "conftest _wr2_module_identity_isolation did not restore the swapped module — "
        "a leaked instance would break the next test's patch()"
    )
