"""Tests for legacy gap entry adapter — coerce_to_canonical()."""
from __future__ import annotations

from mata_garuda.workers.gap_legacy import (
    _TRANSLATION,
    coerce_to_canonical,
    is_legacy_shape,
)


# ── shape detection ────────────────────────────────────────────────────


def test_canonical_envelope_is_not_legacy():
    data = {
        "id": "abc",
        "type": "gap.missing_nip",
        "source": "gap_detector",
        "timestamp": "2026-04-16T05:00:00+08:00",
        "priority": "3",
        "payload": '{"x": 1}',
    }
    assert is_legacy_shape(data) is False


def test_legacy_entry_is_legacy():
    data = {
        "request_id": "abc",
        "gap_type": "missing_attribute",
        "attribute": "nip",
        "entity_name": "Foo",
        "priority": "2",
    }
    assert is_legacy_shape(data) is True


def test_partial_envelope_missing_source_is_legacy():
    """Defensive: treat half-canonical entries as legacy to avoid false routing."""
    data = {"id": "abc", "type": "gap.missing_nip"}  # no source
    assert is_legacy_shape(data) is True


# ── canonical pass-through ─────────────────────────────────────────────


def test_coerce_canonical_returns_data_unchanged():
    data = {
        "id": "abc",
        "type": "gap.missing_nip",
        "source": "gap_detector",
        "payload": '{"x": 1}',
    }
    result = coerce_to_canonical("0-0", data)
    assert result is not None
    gap_type, payload_seed = result
    assert gap_type == "gap.missing_nip"
    # Caller is responsible for JSON-decoding the payload string itself.
    assert payload_seed is data


# ── legacy translation: mapped cases ───────────────────────────────────


def test_coerce_legacy_missing_nip():
    data = {
        "gap_type": "missing_attribute",
        "attribute": "nip",
        "entity_name": "Felucia",
        "entity_type": "Official",
    }
    gap_type, payload = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.missing_nip"
    assert payload["entity_name"] == "Felucia"
    assert payload["_legacy_source"] == "nexus:gaps:pre-2026-04-14"


def test_coerce_legacy_missing_lhkpn():
    data = {"gap_type": "missing_attribute", "attribute": "lhkpn"}
    gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.missing_lhkpn"


def test_coerce_legacy_missing_angkatan():
    data = {"gap_type": "missing_attribute", "attribute": "angkatan"}
    gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.missing_angkatan"


def test_coerce_legacy_officials_struktur_to_kanim():
    data = {"gap_type": "missing_attribute", "attribute": "officials_struktur"}
    gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.kanim_struktur"


def test_coerce_legacy_procurement_link():
    data = {"gap_type": "missing_attribute", "attribute": "procurement_link"}
    gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.missing_procurement"


def test_coerce_legacy_stale_attribute_wildcard_attr():
    """stale_attribute maps to gap.stale_official regardless of attribute."""
    for attr in ("nip", "lhkpn", "profile", None, ""):
        data = {"gap_type": "stale_attribute"}
        if attr:
            data["attribute"] = attr
        result = coerce_to_canonical("1-0", data)
        assert result is not None, f"stale_attribute attr={attr!r} should map"
        assert result[0] == "gap.stale_official"


# ── legacy translation: drained cases ──────────────────────────────────


def test_coerce_legacy_profile_drained():
    data = {"gap_type": "missing_attribute", "attribute": "profile"}
    assert coerce_to_canonical("1-0", data) is None


def test_coerce_legacy_officials_or_documents_drained():
    data = {"gap_type": "missing_attribute", "attribute": "officials_or_documents"}
    assert coerce_to_canonical("1-0", data) is None


def test_coerce_legacy_missing_relation_drained():
    data = {"gap_type": "missing_relation", "from": "Foo", "to": "Bar"}
    assert coerce_to_canonical("1-0", data) is None


def test_coerce_legacy_works_at_relation_drained():
    """WORKS_AT:* attribute is a relation reference, not an attribute name."""
    data = {
        "gap_type": "missing_attribute",
        "attribute": "WORKS_AT:Kanim Kelas I Khusus TPI Ngurah Rai",
    }
    assert coerce_to_canonical("1-0", data) is None


def test_coerce_unknown_legacy_shape_drained():
    data = {"gap_type": "totally_invented", "attribute": "x"}
    assert coerce_to_canonical("1-0", data) is None


# ── translation table coverage ─────────────────────────────────────────


def test_translation_targets_are_in_dispatch_table():
    """Every canonical type we translate to must exist in GAP_DISPATCH."""
    from mata_garuda.workers.gap_consumer import GAP_DISPATCH
    for canonical in _TRANSLATION.values():
        assert canonical in GAP_DISPATCH, (
            f"_TRANSLATION points at {canonical!r} which is not in GAP_DISPATCH"
        )
