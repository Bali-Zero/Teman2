#!/usr/bin/env python3
"""The Jev model version is pinned, and this is what keeps it pinned.

A pin applied once is an edit; a pin that cannot silently regress is a control.
`scripts/typesafe_client.py` feeds a CI lint whose 0.80 firing threshold was
calibrated against a specific model version — 15/17 recall on the grep-missed
cases, 0/20 false alarms. Under a moving alias the vendor can reissue the model
and invalidate that calibration with nothing in any diff to show it: the lint
would keep passing while meaning something else.

So the failure this guards is not "someone typed the wrong string". It is
"someone restored convenience and the evidence quietly stopped applying".
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_CLIENT = Path(__file__).resolve().parents[1] / "typesafe_client.py"

# A version, not an alias. `jev-latest` and `jev-preview` are the two the vendor
# documents as moving; anything without a version triplet is refused on the same
# ground rather than by name, so a third alias invented later is caught too.
_PINNED = re.compile(r"^jev-\d+\.\d+\.\d+$")


def _model() -> str:
    spec = importlib.util.spec_from_file_location("typesafe_client", _CLIENT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MODEL


def test_model_is_a_pinned_version_not_a_moving_alias():
    model = _model()
    assert _PINNED.match(model), (
        f"typesafe_client.MODEL is {model!r}. A CI gate whose threshold was calibrated "
        "against one model version cannot ride a moving alias: raising the version is a "
        "bench re-run, not an edit. Re-run scripts/test_lint_paid_llm_entity.py --bench "
        "with a live key, record the numbers, then pin the version you measured."
    )


def test_the_pin_is_the_version_the_bench_was_measured_against():
    """Recorded so a future bump has to confront the number it invalidates."""
    assert _model() == "jev-1.13.0", (
        "the calibration on record (15/17 grep-miss recall, 0/20 false alarms, "
        "reproduced 2026-09-21 from a seat outside the lane) was measured against "
        "jev-1.13.0. Changing this line without new bench numbers strands that evidence."
    )


def test_the_reason_travels_with_the_line():
    """A bare version string invites a silent revert to the alias."""
    src = _CLIENT.read_text()
    head = src[: src.index("MODEL = ")]
    assert "calibrat" in head.lower(), "the pin must carry why it is pinned, or it will not survive"
