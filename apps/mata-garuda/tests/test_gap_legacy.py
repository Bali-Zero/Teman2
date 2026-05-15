"""Tests for legacy gap entry adapter — coerce_to_canonical()."""
from __future__ import annotations

import pytest

from mata_garuda.workers.gap_legacy import (
    _PREFIX_TRANSLATION,
    _TRANSLATION,
    consume_unmapped_counter,
    coerce_to_canonical,
    is_legacy_shape,
)


@pytest.fixture(autouse=True)
def _reset_unmapped_counter():
    """Each test gets a clean unmapped counter."""
    consume_unmapped_counter()
    yield
    consume_unmapped_counter()


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


def test_coerce_legacy_profile_routes_to_dlq():
    """profile attribute now routes to explicit DLQ (C.4 2026-05-16).

    Was previously drained silently — see brainstorm doc §C.4 reasoning.
    DLQ has GAP_DISPATCH[None] but the entry is visible in counters.
    """
    data = {"gap_type": "missing_attribute", "attribute": "profile"}
    result = coerce_to_canonical("1-0", data)
    assert result is not None
    gap_type, _ = result
    assert gap_type == "gap.dlq:profile"


def test_coerce_legacy_phone_routes_to_dlq():
    """phone attribute → DLQ (C.4)."""
    data = {"gap_type": "missing_attribute", "attribute": "phone"}
    gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.dlq:phone"


def test_coerce_legacy_officials_or_documents_on_missing_attribute_drained():
    """On `missing_attribute`, `officials_or_documents` has no canonical agent.

    The semantic shifted in 2026-05-08 OSINT refactor: the same attribute
    name now arrives under `missing_relation` (see test_coerce_missing_relation_*).
    """
    data = {"gap_type": "missing_attribute", "attribute": "officials_or_documents"}
    assert coerce_to_canonical("1-0", data) is None


def test_coerce_legacy_missing_relation_bare_drained():
    """Bare missing_relation without recognized attribute still drains."""
    data = {"gap_type": "missing_relation", "from": "Foo", "to": "Bar"}
    assert coerce_to_canonical("1-0", data) is None


def test_coerce_legacy_works_at_under_missing_attribute_drained():
    """WORKS_AT:* on `missing_attribute` (legacy pre-2026-05-08) → drained.

    The OSINT-Nexus refactor moved WORKS_AT:* under `missing_relation` where
    it IS mapped — see test_coerce_missing_relation_works_at_prefix.
    """
    data = {
        "gap_type": "missing_attribute",
        "attribute": "WORKS_AT:Kanim Kelas I Khusus TPI Ngurah Rai",
    }
    assert coerce_to_canonical("1-0", data) is None


def test_coerce_unknown_legacy_shape_drained():
    data = {"gap_type": "totally_invented", "attribute": "x"}
    assert coerce_to_canonical("1-0", data) is None


# ── 2026-05-16 schema extension: missing_relation taxonomy ──────────────


def test_coerce_missing_relation_officials_struktur_to_kanim():
    """missing_relation+officials_struktur → gap.kanim_struktur (116 entries live)."""
    data = {
        "gap_type": "missing_relation",
        "attribute": "officials_struktur",
        "entity_name": "Kanim Kelas I Khusus TPI Ngurah Rai",
    }
    result = coerce_to_canonical("1-0", data)
    assert result is not None
    gap_type, payload = result
    assert gap_type == "gap.kanim_struktur"
    assert payload["_legacy_source"] == "nexus:gaps:pre-2026-04-14"


def test_coerce_missing_relation_officials_or_documents_to_orphan_org():
    """missing_relation+officials_or_documents → gap.orphan_org (886 entries live)."""
    data = {
        "gap_type": "missing_relation",
        "attribute": "officials_or_documents",
        "entity_name": "Kementerian Keuangan",
    }
    gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.orphan_org"


def test_coerce_missing_relation_procurement_link():
    """missing_relation+procurement_link → gap.missing_procurement (580 entries live)."""
    data = {
        "gap_type": "missing_relation",
        "attribute": "procurement_link",
        "entity_name": "OJK",
    }
    gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
    assert gap_type == "gap.missing_procurement"


# ── 2026-05-16 prefix translation: WORKS_AT:<kanim_name> ────────────────


def test_coerce_missing_relation_works_at_prefix():
    """WORKS_AT:<any> on missing_relation → gap.kanim_struktur (177 entries live)."""
    data = {
        "gap_type": "missing_relation",
        "attribute": "WORKS_AT:Kanim Kelas I Khusus TPI Ngurah Rai",
        "entity_name": "Felucia Sengky Ratna",
    }
    result = coerce_to_canonical("1-0", data)
    assert result is not None
    gap_type, payload = result
    assert gap_type == "gap.kanim_struktur"
    # Suffix must reach the agent verbatim — it's the kanim identifier.
    assert payload["attribute"] == "WORKS_AT:Kanim Kelas I Khusus TPI Ngurah Rai"


def test_coerce_missing_relation_works_at_different_kanim():
    """Prefix match works for any kanim suffix, not just the live one."""
    for kanim in ("Kanim Denpasar", "Kanim Jakarta Selatan", "Kanim Surabaya"):
        data = {
            "gap_type": "missing_relation",
            "attribute": f"WORKS_AT:{kanim}",
        }
        gap_type, _ = coerce_to_canonical("1-0", data)  # type: ignore[misc]
        assert gap_type == "gap.kanim_struktur", f"prefix routing broke for {kanim}"


def test_coerce_prefix_does_not_match_unrelated_attribute():
    """Prefix WORKS_AT: must NOT match a bare 'WORKS_AT' attribute (no colon)."""
    data = {"gap_type": "missing_relation", "attribute": "WORKS_AT"}
    # "WORKS_AT" doesn't start with "WORKS_AT:" — should fall through to drain.
    assert coerce_to_canonical("1-0", data) is None


# ── Unmapped counter (C.2) ──────────────────────────────────────────────


def test_unmapped_counter_increments_on_drain():
    """Every drain must increment the in-process counter."""
    coerce_to_canonical("1-0", {"gap_type": "totally_invented", "attribute": "x"})
    coerce_to_canonical("1-1", {"gap_type": "totally_invented", "attribute": "x"})
    coerce_to_canonical("1-2", {"gap_type": "another_unknown"})
    snapshot = consume_unmapped_counter()
    assert snapshot[("totally_invented", "x")] == 2
    assert snapshot[("another_unknown", None)] == 1


def test_unmapped_counter_does_not_increment_on_mapped():
    """Mapped entries must NOT touch the counter."""
    coerce_to_canonical("1-0", {"gap_type": "missing_attribute", "attribute": "nip"})
    coerce_to_canonical("1-1", {"gap_type": "missing_relation", "attribute": "procurement_link"})
    snapshot = consume_unmapped_counter()
    assert snapshot == {}


def test_consume_resets_counter():
    """consume_unmapped_counter returns and clears in one atomic step."""
    coerce_to_canonical("1-0", {"gap_type": "totally_invented"})
    first = consume_unmapped_counter()
    second = consume_unmapped_counter()
    assert first[("totally_invented", None)] == 1
    assert second == {}


# ── translation table coverage ─────────────────────────────────────────


def test_translation_targets_are_in_dispatch_table():
    """Every canonical type we translate to must exist in GAP_DISPATCH."""
    from mata_garuda.workers.gap_consumer import GAP_DISPATCH
    for canonical in _TRANSLATION.values():
        assert canonical in GAP_DISPATCH, (
            f"_TRANSLATION points at {canonical!r} which is not in GAP_DISPATCH"
        )


def test_prefix_translation_targets_are_in_dispatch_table():
    """Every prefix-translation target must also exist in GAP_DISPATCH."""
    from mata_garuda.workers.gap_consumer import GAP_DISPATCH
    for canonical in _PREFIX_TRANSLATION.values():
        assert canonical in GAP_DISPATCH, (
            f"_PREFIX_TRANSLATION points at {canonical!r} which is not in GAP_DISPATCH"
        )
