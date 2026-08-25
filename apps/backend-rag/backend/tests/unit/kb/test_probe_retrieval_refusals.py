"""The probe must refuse to grade what it cannot grade.

An adversarial pass over `kb/ops/probe_retrieval.py` on 2026-08-25 found two ways to
make it report success without measuring anything:

  A. `verbatim_phrase` had no floor inside the probe. Run live, the phrases "", "a",
     "   ", "." and "dan" every one reported GREEN at rank 1. The mechanism is not
     corpus-dependent: "" is a substring of every string in Python, so such a journey
     greens against any collection, for any question. The G3 contract's 12-character
     minimum is real but lives in a different program, which a lane running the probe
     by hand never executes.

  B. `--collection this_collection_does_not_exist_zzz999` exited 0 "AT TARGET".
     `search_service.py:522-531` answers an unrecognised collection name by logging
     to stderr and searching `legal_unified` instead, so a typo does not error — it
     grades a corpus the caller never asked for.

Both are now refusals, and both predicates are pure so their guilt cases are provable
without a Qdrant connection. These tests exist to fail if either floor is removed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _probe():
    """Load kb/ops/probe_retrieval.py by path — it is a script, not a package."""
    root = Path(__file__).resolve()
    for parent in root.parents:
        if (parent / "kb" / "ops" / "probe_retrieval.py").exists():
            path = parent / "kb" / "ops" / "probe_retrieval.py"
            break
    else:  # pragma: no cover - the repo layout would have to change
        pytest.fail(f"kb/ops/probe_retrieval.py not found from {root}")
    spec = importlib.util.spec_from_file_location("_probe_retrieval", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_probe_retrieval", mod)
    spec.loader.exec_module(mod)
    return mod


PROBE = _probe()


# ── A. the phrase floor ──────────────────────────────────────────────────────

USABLE = [
    "izin tinggal terbatas berlaku paling lama",
    "modal disetor paling sedikit",
    "peraturan perundang-undangan",  # boilerplate, but long enough to be the file's problem
    "hak pakai di atas tanah",
]


@pytest.mark.parametrize("phrase", USABLE, ids=lambda p: p[:24])
def test_innocence_a_real_phrase_is_usable(phrase):
    """If these were refused, every guilt case below would be vacuous."""
    assert PROBE.unusable_phrase(phrase) is None


UNUSABLE = [
    ("empty string greens against everything", "", "substring of every string"),
    ("whitespace only normalises to empty", "   \n\t ", "substring of every string"),
    ("single character", "a", "matches by accident"),
    ("a single full stop", ".", "matches by accident"),
    ("a common Indonesian word", "dan", "matches by accident"),
    ("one character under the floor", "elevenchar", "matches by accident"),
    ("None where a string was expected", None, "substring of every string"),
]


@pytest.mark.parametrize("name,phrase,expected", UNUSABLE, ids=[c[0] for c in UNUSABLE])
def test_guilt_a_phrase_that_cannot_grade_is_refused(name, phrase, expected):
    why = PROBE.unusable_phrase(phrase)
    assert why is not None, f"{name}: the probe accepted {phrase!r} as gradeable"
    assert expected in why, f"{name}: refused for the wrong reason: {why}"


def test_the_floor_is_the_same_number_the_contract_gate_uses():
    """Two floors that can drift apart are one floor and one decoration."""
    assert PROBE.MIN_PHRASE_CHARS == 12


def test_the_empty_string_really_does_match_everything():
    """The premise behind rule A, asserted rather than assumed.

    If this ever stops being true of Python, the phrase floor is protecting against
    something that no longer exists and the comment above it is a lie.
    """
    assert "" in "any legal text whatsoever"
    assert PROBE.normalize("   ") == ""


# ── B. the collection floor ──────────────────────────────────────────────────

def test_innocence_the_collections_the_lanes_actually_use_are_known():
    """The registry names lane A and lane C were told to use must pass."""
    assert PROBE.unknown_collections(
        ["legal_unified", "visa_oracle", "immigration_circulars", "tax_genius_hybrid"]
    ) == []


STRANGERS = [
    ("the refuter's literal reproduction", "this_collection_does_not_exist_zzz999"),
    ("a plausible typo of the default", "legal_unifed"),
    ("a collection that sounds right but is not registered", "kbli_2025"),
    ("empty string", ""),
]


@pytest.mark.parametrize("name,collection", STRANGERS, ids=[c[0] for c in STRANGERS])
def test_guilt_an_unregistered_collection_is_refused(name, collection):
    assert PROBE.unknown_collections([collection]) == [collection], (
        f"{name}: {collection!r} was accepted, so a run against it would "
        f"silently grade legal_unified instead"
    )


def test_a_mixed_set_reports_only_the_strangers_and_sorts_them():
    assert PROBE.unknown_collections(
        ["legal_unified", "zzz_nope", "visa_oracle", "aaa_nope", "zzz_nope"]
    ) == ["aaa_nope", "zzz_nope"]


def test_the_predicate_agrees_with_the_registry_rather_than_a_copy_of_it():
    """A hardcoded allow-list would pass every test above and rot silently."""
    from backend.core.collection_registry import LOGICAL_TO_PHYSICAL_COLLECTIONS

    assert PROBE.unknown_collections(sorted(LOGICAL_TO_PHYSICAL_COLLECTIONS)) == []


# ── the refusals are wired, not merely defined ───────────────────────────────

def test_both_predicates_are_actually_consulted_by_the_run_path():
    """A predicate nobody calls is decoration. Read the source of run() and prove it.

    Deliberately a source check rather than a behavioural one: exercising run() needs
    a live Qdrant, and a test that needs production to prove a refusal is a test that
    gets skipped in CI and protects nothing.
    """
    import inspect

    src = inspect.getsource(PROBE.run)
    assert "unusable_phrase(" in src, "the phrase floor is defined but never called"
    assert "unknown_collections(" in src, "the collection floor is defined but never called"
    assert "unusable_phrase" in src.split("SearchService()")[0], (
        "the phrase floor runs AFTER production is touched — it must refuse first"
    )
    assert "collection_manager.get_collection" in src, (
        "nothing checks the exact predicate that triggers the silent substitution"
    )
