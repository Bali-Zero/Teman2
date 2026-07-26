"""Unit tests for `scripts/intake_identity_backfill.py` (SSOT canonicalizers +
Fuel A pairing logic). All values below are SYNTHETIC — no real client PII.

No real DB access (W96): the module under test is loaded via importlib from the
`scripts/` tree, and the Fuel A pairing logic is exercised via the pure
`decide_pair`/`pair_by_unique_phone` functions on in-memory fake rows only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_backfill_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "intake_identity_backfill.py"
    assert script_path.exists(), f"script not found at {script_path}"
    spec = importlib.util.spec_from_file_location("intake_identity_backfill_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill = _load_backfill_module()


# ---------------------------------------------------------------------------
# canon_id
# ---------------------------------------------------------------------------


def test_canon_id_valid_passport_like_value() -> None:
    assert backfill.canon_id("AB 123-456") == "AB123456"


def test_canon_id_divergent_normalization_quarantined() -> None:
    # routing-norm strips only [\s.\-/] -> keeps '#'; full-norm strips ALL non-alnum.
    # The two disagree -> quarantine (None), never guessed (F11).
    assert backfill.canon_id("AB#123456") is None


def test_canon_id_too_short_rejected() -> None:
    assert backfill.canon_id("AB123") is None


def test_canon_id_int_input_rejected_leading_zero_guard() -> None:
    # A numeric-typed source for an all-digit id is untrustworthy (leading zeros
    # silently dropped upstream) -- only str inputs are accepted for all-digit ids.
    assert backfill.canon_id(123456) is None
    assert backfill.canon_id(123456.0) is None


def test_canon_id_str_all_digit_is_accepted() -> None:
    # A STRING that happens to be all-digit (e.g. a real all-numeric KITAS number)
    # is not penalized -- only the numeric *type* is suspect.
    assert backfill.canon_id("1234567") == "1234567"


def test_canon_id_none_and_empty() -> None:
    assert backfill.canon_id(None) is None
    assert backfill.canon_id("   ") is None


# ---------------------------------------------------------------------------
# canon_phone
# ---------------------------------------------------------------------------


def test_canon_phone_08_628_equivalence() -> None:
    a = backfill.canon_phone("0812-3456-789")
    b = backfill.canon_phone("628123456789")
    assert a == b == "628123456789"


def test_canon_phone_too_short_rejected() -> None:
    assert backfill.canon_phone("0812") is None


def test_canon_phone_none() -> None:
    assert backfill.canon_phone(None) is None


# ---------------------------------------------------------------------------
# canon_name / name_tokens / exact_token_set
# ---------------------------------------------------------------------------


def test_canon_name_junk_rejected() -> None:
    assert backfill.canon_name(None) is None
    assert backfill.canon_name("   ") is None
    assert backfill.canon_name("unknown") is None
    assert backfill.canon_name("Unknown") is None
    assert backfill.canon_name("Lead +6281200001111") is None
    assert backfill.canon_name("lead+6281200001111") is None
    assert backfill.canon_name("+62 812 0000 1111") is None


def test_canon_name_valid_value() -> None:
    assert backfill.canon_name("  Alpha   Beta  ") == "alpha beta"


def test_exact_token_set_subset_is_not_equal() -> None:
    # Spec example verbatim: 'ALPHA BETA' vs 'ALPHA BETA GAMMA' -> False (subset != equal).
    assert backfill.exact_token_set("ALPHA BETA", "ALPHA BETA GAMMA") is False


def test_exact_token_set_equal_sets_true() -> None:
    assert backfill.exact_token_set("Alpha Beta", "beta alpha") is True


def test_exact_token_set_requires_two_informative_tokens_each_side() -> None:
    assert backfill.exact_token_set("Alpha", "Alpha") is False


# ---------------------------------------------------------------------------
# canon_nationality
# ---------------------------------------------------------------------------


def test_canon_nationality_known_demonym() -> None:
    assert backfill.canon_nationality("italiana") == "IT"
    assert backfill.canon_nationality("ITALIAN") == "IT"


def test_canon_nationality_unknown_returns_none() -> None:
    assert backfill.canon_nationality("martian") is None
    assert backfill.canon_nationality(None) is None


# ---------------------------------------------------------------------------
# Fuel A pairing: pair_by_unique_phone + decide_pair (pure, synthetic rows only)
# ---------------------------------------------------------------------------


def _prod(id_: int, passport: str | None, phone: str, name: str, nationality: str | None) -> dict:
    return {"id": id_, "passport_number": passport, "phone_normalized": phone, "full_name": name, "nationality": nationality}


def _local(id_: int, passport: str | None, phone: str, name: str, nationality: str | None) -> dict:
    return {"id": id_, "passport_number": passport, "phone_normalized": phone, "full_name": name, "nationality": nationality}


_EMPTY_CONTEXT = {"excluded_local_ids": set(), "excluded_prod_ids": set()}


def test_pair_by_unique_phone_happy_path() -> None:
    prod_rows = [_prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")]
    local_rows = [_local(101, None, "62812 00000001", "alpha beta", "IT")]
    pairs = backfill.pair_by_unique_phone(prod_rows, local_rows)
    assert len(pairs) == 1
    assert pairs[0][0]["id"] == 1
    assert pairs[0][1]["id"] == 101


def test_pair_by_unique_phone_ambiguous_phone_excluded() -> None:
    # Same phone shared by TWO prod rows -> not unique on the prod side -> no pair.
    prod_rows = [
        _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana"),
        _prod(2, "CD654321", "081200000001", "Gamma Delta", "italiana"),
    ]
    local_rows = [_local(101, None, "62812 00000001", "alpha beta", "IT")]
    pairs = backfill.pair_by_unique_phone(prod_rows, local_rows)
    assert pairs == []


def test_pair_by_unique_phone_ambiguous_on_local_side_excluded() -> None:
    prod_rows = [_prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")]
    local_rows = [
        _local(101, None, "62812 00000001", "alpha beta", "IT"),
        _local(102, None, "62812 00000001", "someone else", "IT"),
    ]
    pairs = backfill.pair_by_unique_phone(prod_rows, local_rows)
    assert pairs == []


def test_decide_pair_happy_path_writes() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "IT")
    verdict, reason = backfill.decide_pair(prod, local, _EMPTY_CONTEXT)
    assert verdict == "WRITE", reason


def test_decide_pair_name_mismatch_excluded() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "totally different name", "IT")
    verdict, reason = backfill.decide_pair(prod, local, _EMPTY_CONTEXT)
    assert verdict == "SKIP"
    assert "name" in reason


def test_decide_pair_nationality_conflict_excluded() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "australian")
    verdict, reason = backfill.decide_pair(prod, local, _EMPTY_CONTEXT)
    assert verdict == "SKIP"
    assert "nationality" in reason


def test_decide_pair_local_already_filled_is_fill_only_skip() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, "ZZ999999", "62812 00000001", "alpha beta", "IT")
    verdict, reason = backfill.decide_pair(prod, local, _EMPTY_CONTEXT)
    assert verdict == "SKIP"
    assert "fill-only" in reason


def test_decide_pair_prod_passport_invalid_skips() -> None:
    prod = _prod(1, None, "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "IT")
    verdict, reason = backfill.decide_pair(prod, local, _EMPTY_CONTEXT)
    assert verdict == "SKIP"


def test_decide_pair_manifest_exclusion_local() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "IT")
    context = {"excluded_local_ids": {101}, "excluded_prod_ids": set()}
    verdict, reason = backfill.decide_pair(prod, local, context)
    assert verdict == "SKIP"
    assert "manifest" in reason


def test_decide_pair_manifest_exclusion_prod() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "IT")
    context = {"excluded_local_ids": set(), "excluded_prod_ids": {1}}
    verdict, reason = backfill.decide_pair(prod, local, context)
    assert verdict == "SKIP"
    assert "manifest" in reason


# ---------------------------------------------------------------------------
# queue-contradiction gate (council follow-up, 2026-07-18)
# ---------------------------------------------------------------------------


def test_decide_pair_queue_contradiction_skips() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "IT")
    context = {
        "excluded_local_ids": set(),
        "excluded_prod_ids": set(),
        # a queue doc names client 101 with a DIFFERENT passport than the one
        # we're about to backfill (AB123456) -> contradiction, must SKIP.
        "doc_passports_by_local_id": {101: frozenset({"ZZ999999"})},
    }
    verdict, reason = backfill.decide_pair(prod, local, context)
    assert verdict == "SKIP"
    assert "queue-contradiction" in reason


def test_decide_pair_doc_confirmed_still_writes_and_is_flagged() -> None:
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "IT")
    context = {
        "excluded_local_ids": set(),
        "excluded_prod_ids": set(),
        # a queue doc names client 101 with the SAME passport -> confirms,
        # never blocks; verdict stays WRITE and the reason says so.
        "doc_passports_by_local_id": {101: frozenset({"AB123456"})},
    }
    verdict, reason = backfill.decide_pair(prod, local, context)
    assert verdict == "WRITE"
    assert "doc-confirmed" in reason


def test_decide_pair_no_queue_doc_info_is_unaffected() -> None:
    # No entry for this client in the map at all (the common case) -> behaves
    # exactly as before the gate existed.
    prod = _prod(1, "AB123456", "081200000001", "Alpha Beta", "italiana")
    local = _local(101, None, "62812 00000001", "alpha beta", "IT")
    context = {"excluded_local_ids": set(), "excluded_prod_ids": set(), "doc_passports_by_local_id": {}}
    verdict, reason = backfill.decide_pair(prod, local, context)
    assert verdict == "WRITE"
    assert "doc-confirmed" not in reason
