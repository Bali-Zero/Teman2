"""Tests for base_worker._parse_xreadgroup — Redis stream parser.

Regression test bed for the empty-value bug discovered 2026-05-16 during
Pilastro 1 reflection-regression debug:
  research/symbiosis/2026-05-16-reflection-regression-2026-05-08.md
  research/symbiosis/2026-05-16-dispatch-alias-brainstorm.md (C.5)
"""
from __future__ import annotations

from mata_garuda.workers.base_worker import _is_msg_id, _parse_xreadgroup

# ── _is_msg_id ──────────────────────────────────────────────────────────


def test_is_msg_id_recognizes_redis_id():
    assert _is_msg_id("1778888945186-0") is True
    assert _is_msg_id("1-0") is True
    assert _is_msg_id("9999999999999-99") is True


def test_is_msg_id_rejects_empty():
    assert _is_msg_id("") is False


def test_is_msg_id_rejects_field_names():
    assert _is_msg_id("gap_type") is False
    assert _is_msg_id("entity_name") is False
    assert _is_msg_id("nexus:gaps") is False


def test_is_msg_id_rejects_values_with_dashes():
    """Field VALUES like ISO timestamps contain '-' but are not message IDs."""
    assert _is_msg_id("2026-05-16T07:49:04") is False
    assert _is_msg_id("WORKS_AT:Kanim Kelas I Khusus TPI Ngurah Rai") is False


def test_is_msg_id_rejects_pure_digits():
    """A bare integer like a priority value must NOT be parsed as an ID."""
    assert _is_msg_id("4") is False
    assert _is_msg_id("172800") is False


# ── _parse_xreadgroup empty-value preservation (C.5) ────────────────────


def test_parse_preserves_empty_field_value():
    """An empty entity_nip must NOT shift the rest of the key/value pairs.

    This is the exact regression that broke Pilastro 1 from 2026-05-08
    to 2026-05-16 — see commit message of C.5 fix.
    """
    raw = """nexus:gaps
1778888945186-0
request_id
fa4cb93d
entity_type
Organization
entity_name
PT BTID
entity_nip

gap_type
missing_relation
attribute
officials_or_documents
priority
4
ttl_seconds
172800
created_at
2026-05-16T07:49:04"""
    items = _parse_xreadgroup(raw, "nexus:gaps")
    assert len(items) == 1
    data = items[0]["data"]
    assert items[0]["id"] == "1778888945186-0"
    assert data["entity_nip"] == ""  # preserved, not skipped
    assert data["gap_type"] == "missing_relation"
    assert data["attribute"] == "officials_or_documents"
    assert data["priority"] == "4"
    assert data["ttl_seconds"] == "172800"
    assert data["created_at"] == "2026-05-16T07:49:04"


def test_parse_two_entries_with_empty_values_each():
    """Two consecutive entries each with their own empty entity_nip."""
    raw = """nexus:gaps
1-0
gap_type
missing_attribute
attribute
nip
entity_nip

entity_name
Foo
2-0
gap_type
stale_attribute
attribute

entity_nip
123
entity_name
Bar"""
    items = _parse_xreadgroup(raw, "nexus:gaps")
    assert len(items) == 2
    assert items[0]["id"] == "1-0"
    assert items[0]["data"]["entity_nip"] == ""
    assert items[0]["data"]["entity_name"] == "Foo"
    assert items[0]["data"]["gap_type"] == "missing_attribute"
    assert items[1]["id"] == "2-0"
    assert items[1]["data"]["attribute"] == ""
    assert items[1]["data"]["entity_nip"] == "123"


def test_parse_legacy_no_empty_values_still_works():
    """Pre-fix payload shape (no empty values) must still parse identically."""
    raw = """stream
1-0
key1
val1
key2
val2"""
    items = _parse_xreadgroup(raw, "stream")
    assert len(items) == 1
    assert items[0]["data"] == {"key1": "val1", "key2": "val2"}


def test_parse_empty_input_returns_empty_list():
    assert _parse_xreadgroup("", "stream") == []
    assert _parse_xreadgroup("nexus:gaps", "nexus:gaps") == []


def test_parse_iso_timestamp_value_not_treated_as_msg_id():
    """A field value of `2026-05-16T07:49:04` (digit-then-dash) must stay a value."""
    raw = """stream
100-0
created_at
2026-05-16T07:49:04
status
ok"""
    items = _parse_xreadgroup(raw, "stream")
    assert len(items) == 1  # NOT 2 — the timestamp is not an ID
    assert items[0]["data"]["created_at"] == "2026-05-16T07:49:04"
    assert items[0]["data"]["status"] == "ok"


def test_parse_empty_key_skipped():
    """Defensive: an empty key (malformed payload) is skipped, not dict-bombed."""
    raw = """stream
1-0

valueA
real_key
real_value"""
    items = _parse_xreadgroup(raw, "stream")
    assert len(items) == 1
    # Empty key skipped; real_key still parsed
    assert "real_key" in items[0]["data"]
    assert "" not in items[0]["data"]
