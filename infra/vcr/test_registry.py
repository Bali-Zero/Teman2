"""Tests for infra/vcr/registry.py — the expected-claim registry (R5).

Guilt AND innocence: a registered pair must resolve; an unregistered pair
must resolve to None (never silently match something close); a malformed
registry (missing required key) must raise loudly, not skip the entry.
"""

from __future__ import annotations

import pytest

from infra.vcr.registry import ExpectedClaim, load_registry, lookup, DEFAULT_REGISTRY_PATH


def test_default_registry_loads_and_has_the_three_pilot_seats():
    reg = load_registry()
    seats = {c.seat for c in reg}
    assert seats == {"claude", "codex", "kimi"}


def test_default_registry_every_entry_has_a_certified_hash():
    reg = load_registry()
    assert reg, "registry must not be empty"
    for c in reg:
        assert c.certified_hash, f"{c.seat}/{c.host}/{c.auth_context} has no certified_hash"
        assert len(c.certified_hash) == 64, "sha256 hex digest must be 64 chars"


def test_lookup_finds_registered_pair():
    reg = load_registry()
    found = lookup(reg, "claude", "m5", "interactive")
    assert found is not None
    assert found.seat == "claude"


def test_lookup_unregistered_pair_returns_none():
    reg = load_registry()
    assert lookup(reg, "claude", "pro", "interactive") is None
    assert lookup(reg, "ollama", "m5", "interactive") is None


def test_malformed_registry_missing_key_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("claims:\n  - seat: claude\n    host: m5\n")  # missing auth_context etc
    with pytest.raises(ValueError, match="missing required key"):
        load_registry(bad)


def test_claims_not_a_list_raises(tmp_path):
    bad = tmp_path / "bad2.yaml"
    bad.write_text("claims: not-a-list\n")
    with pytest.raises(ValueError, match="must be a list"):
        load_registry(bad)


def test_empty_registry_is_valid_but_lookup_always_none(tmp_path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("claims: []\n")
    reg = load_registry(empty)
    assert reg == []
    assert lookup(reg, "claude", "m5", "interactive") is None
