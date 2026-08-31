"""Guilt/innocence for `kb/ops/probe_retrieval.py::resolve_collection`.

Lane A (immigration) needs journeys that deliberately target DIFFERENT collections —
a positive journey against `legal_unified` and a canary against the same collection
for a poisoned identity is the common case, but the mandate itself (MANDATE.md,
`kb/ops/probe_retrieval.py`'s own docstring) documents that production routes
"visa"/"kitas"/"imigrasi" questions to `visa_oracle` first, with `immigration_circulars`
as a fallback (`surface_router.py:63`). A probe pinned to one `--collection` flag
cannot express "this one journey means something different". `resolve_collection` is
the pure function that decides, per journey, which collection actually gets asked —
tested here with no live Qdrant connection required (import-and-call, same pattern as
`test_kb_topic_contract.py`'s `_probe()` loader for a sibling module that also lives
outside any Python package).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


ROOT = _repo_root()


def _load_probe_retrieval():
    cached = sys.modules.get("kb_probe_retrieval_under_test")
    if cached is not None:
        return cached
    path = ROOT / "kb" / "ops" / "probe_retrieval.py"
    assert path.is_file(), f"{path} is missing"
    spec = importlib.util.spec_from_file_location("kb_probe_retrieval_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_probe_retrieval_under_test"] = module
    spec.loader.exec_module(module)
    return module


probe_retrieval = _load_probe_retrieval()
resolve_collection = probe_retrieval.resolve_collection


def test_innocence_no_override_falls_back_to_the_default():
    journey = {"question": "x", "verbatim_phrase": "irrelevant but long enough"}
    assert resolve_collection(journey, "legal_unified") == "legal_unified"


def test_innocence_explicit_override_wins():
    journey = {"question": "x", "collection": "visa_oracle"}
    assert resolve_collection(journey, "legal_unified") == "visa_oracle"


BLANK_OVERRIDE_CASES = [
    ("collection key absent entirely", {}),
    ("collection is None", {"collection": None}),
    ("collection is an empty string", {"collection": ""}),
    ("collection is whitespace only", {"collection": "   "}),
]


@pytest.mark.parametrize("name,journey", BLANK_OVERRIDE_CASES, ids=[c[0] for c in BLANK_OVERRIDE_CASES])
def test_guilt_blank_or_missing_override_never_silently_wins(name, journey):
    """A falsy `collection:` must defer to the default, never resolve to itself.

    Reproduces the defect an inline `journey.get("collection") or args.collection`
    at the call site would NOT reproduce for one shape only (`collection: ""`, where
    `or` already falls through) — but a naive `journey.get("collection", default)`
    (no falsy-check) would return `None` or `""` for three of these four cases and
    hand that straight to `SearchService.search(collection_override=...)`, which is
    exactly the silent-misroute this function exists to prevent.
    """
    assert resolve_collection(journey, "legal_unified") == "legal_unified", name


def test_guilt_the_default_itself_is_never_hardcoded_inside_the_function():
    """Passing a different default must change the result — proves no hardcoding."""
    assert resolve_collection({}, "visa_oracle") == "visa_oracle"
    assert resolve_collection({}, "immigration_circulars") == "immigration_circulars"


def test_the_guilt_matrix_is_not_empty():
    assert len(BLANK_OVERRIDE_CASES) >= 4, len(BLANK_OVERRIDE_CASES)
