"""Guilt and innocence for the declared sector-law carve-out list itself
(item G, 2026-08-08 fix-pack).

`perpres_body_default_relation.py` and its own tests (`test_perpres_body_
default.py`) cover the RELATION module's use of this input — that it routes
the six codes to the right bucket/citation and never leaks onto anything
else. This file covers the DECLARED INPUT's own integrity, which is a
different failure mode: `write_sector_law_carveout.py`'s docstring makes one
explicit promise —

    "Kept in step by test_sector_law_carveout.py, which asserts this set
    matches that spec's `codes` keys exactly — one adjudication, cited from
    two files, must not silently diverge into two populations."

Nothing else in the repo enforces that promise; this file is where it is
kept. The second concern is the writer being a pure, reproducible function of
its own constant (the standard "declared, versioned input file" pattern this
module's docstring argues for over a third hardcoded dict) — the file on disk
must always equal what `build()` would write today, or a hand-edit or drift
between runs would go unnoticed until the relation module cites it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from perpres_body_default_relation import sector_law_carveout_codes  # noqa: E402
from write_sector_law_carveout import CODES, OUT_PATH, build  # noqa: E402

REPO_ROOT = Path(_FILIERA_DIR).parents[1]
ASURANSI_SPEC = (
    REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs"
    / "canonical_asuransi_pp14_cap_2026_08_08.json"
)


# --------------------------------------------------------------------------
# GUILT — the one invariant this file exists to hold
# --------------------------------------------------------------------------

def test_the_declared_six_match_the_pp14_adjudication_exactly():
    """One adjudication (PP 14/2018 Pasal 5(1) jo. PP 3/2020, 80% cap), cited
    from two files, must not silently diverge into two populations. If a
    future PR adjudicates a seventh insurance code in the PP14 spec and
    forgets this file, the relation module would keep citing Pasal 3(1)(d)
    for it — the exact defect item G exists to close, reopened for one code.
    """
    spec = json.loads(ASURANSI_SPEC.read_text())
    assert set(CODES) == set(spec["codes"].keys())
    assert len(CODES) == 6


# --------------------------------------------------------------------------
# INNOCENCE — the writer is a pure, reproducible function of its own input
# --------------------------------------------------------------------------

def test_the_written_file_on_disk_matches_the_declared_builder():
    """A hand-edit, a partial write, or a stale artifact from before a CODES
    change would all show up here as a mismatch — the file on disk is never
    trusted on its own, only as the output of `build()` run today.
    """
    assert OUT_PATH.is_file(), (
        "run: python scripts/kbli_filiera/write_sector_law_carveout.py --write"
    )
    on_disk = json.loads(OUT_PATH.read_text())
    assert on_disk == build()


def test_the_relation_modules_reader_returns_exactly_the_six_codes():
    """The consumer-facing contract: `sector_law_carveout_codes()` is what
    `perpres_body_default_relation.py` actually calls, so it is what must
    equal the declared six — not just the on-disk JSON in isolation.
    """
    assert sector_law_carveout_codes() == {
        "65111", "65112", "65121", "65122", "65201", "65202",
    }


def test_check_mode_matches_the_written_file_and_fails_on_drift(tmp_path, monkeypatch):
    """MUTATION PROOF for the writer's own `--check` flag: it must pass on a
    fresh write and fail on a drifted one, same discipline as the relation
    module's `--check-artifact` (W108 — a gate nobody has seen fail is
    decoration).
    """
    import write_sector_law_carveout as mod

    out = tmp_path / "sector-law-carveout.json"
    monkeypatch.setattr(mod, "OUT_PATH", out)

    assert mod.main(["--check"]) == 1, "a missing file must fail --check, not pass"
    assert mod.main(["--write"]) == 0
    assert mod.main(["--check"]) == 0, "a freshly written file must pass --check"

    payload = json.loads(out.read_text())
    payload["codes"].append("99999")
    out.write_text(json.dumps(payload, ensure_ascii=False))
    assert mod.main(["--check"]) == 1, "a drifted file must fail --check"
