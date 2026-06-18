"""Tests for the deterministic intake validation stage (FASE 3 β).

Two layers:
  * Fast/CI: inject a fake KBLI ``fetch_fn`` (a frozenset) so KBLI existence is
    deterministic without hitting Qdrant — tests NIB/NPWP/passport/expiry format
    rules and the dynamic-KBLI membership logic.
  * ``slow``: hit the REAL Qdrant ``kbli_2025_final`` collection and prove the
    validator queries the LIVE catalogue (real code passes, fake code fails).
    Deselect with ``-m "not slow"``.
"""

from __future__ import annotations

import os

import pytest

from backend.services.intake import validate_rules as vr


def _fields(**kw):
    """Build extract-stage-shaped fields from plain kwargs."""
    return {k: {"value": v, "confidence": 0.85, "source_page": 1} for k, v in kw.items()}


def _fake_kbli(codes):
    fs = frozenset(codes)

    async def _fetch():
        return fs

    return _fetch


@pytest.fixture(autouse=True)
def _reset_kbli_cache():
    """Each test starts with a clean KBLI cache (it is process-global)."""
    vr._kbli_code_cache = None
    yield
    vr._kbli_code_cache = None


# --------------------------------------------------------------------------- #
# NIB format                                                                  #
# --------------------------------------------------------------------------- #

async def test_nib_valid_13_digits():
    out = await vr.validate_fields("nib", _fields(nib_number="1234567890123"),
                                   kbli_fetch_fn=_fake_kbli([]))
    assert out["valid"] is True
    assert "nib_format_13_digits" in out["checks_run"]
    assert out["rule_failures"] == []


async def test_nib_wrong_length_fails():
    out = await vr.validate_fields("nib", _fields(nib_number="12345"),
                                   kbli_fetch_fn=_fake_kbli([]))
    assert out["valid"] is False
    assert any("nib_number malformed" in f for f in out["rule_failures"])


async def test_nib_with_separators_cleaned_then_validated():
    # 13 digits with dots/spaces -> cleaned to 13 -> valid
    out = await vr.validate_fields("nib", _fields(nib_number="1234-5678-90123"),
                                   kbli_fetch_fn=_fake_kbli([]))
    assert out["valid"] is True


# --------------------------------------------------------------------------- #
# NPWP format (15 legacy / 16 NIK-based)                                       #
# --------------------------------------------------------------------------- #

async def test_npwp_15_digits_valid():
    out = await vr.validate_fields("npwp", _fields(npwp_number="123456789012345"))
    assert out["valid"] is True


async def test_npwp_16_digits_nik_valid():
    out = await vr.validate_fields("npwp", _fields(npwp_number="0123456789012345"))
    assert out["valid"] is True


async def test_npwp_malformed_fails():
    out = await vr.validate_fields("npwp", _fields(npwp_number="9999"))
    assert out["valid"] is False
    assert any("npwp_number malformed" in f for f in out["rule_failures"])


# --------------------------------------------------------------------------- #
# Passport + expiry                                                            #
# --------------------------------------------------------------------------- #

async def test_passport_valid():
    out = await vr.validate_fields(
        "passport", _fields(passport_no="A1234567", expiry="2030-01-01")
    )
    assert out["valid"] is True


async def test_passport_malformed_fails():
    out = await vr.validate_fields("passport", _fields(passport_no="!!"))
    assert out["valid"] is False
    assert any("passport_no malformed" in f for f in out["rule_failures"])


async def test_expiry_remote_past_fails():
    out = await vr.validate_fields("kitas", _fields(expiry="1990-01-01"))
    assert out["valid"] is False
    assert any("remote past" in f for f in out["rule_failures"])


async def test_expiry_unparseable_fails():
    out = await vr.validate_fields("passport", _fields(expiry="not a date"))
    assert out["valid"] is False
    assert any("unparseable as date" in f for f in out["rule_failures"])


async def test_dmy_date_format_accepted():
    out = await vr.validate_fields("passport", _fields(expiry="01-01-2030"))
    assert out["valid"] is True


# --------------------------------------------------------------------------- #
# Null fields are SKIPPED (golden rule already null-ed them)                   #
# --------------------------------------------------------------------------- #

async def test_null_fields_are_not_failures():
    fields = {
        "nib_number": {"value": None, "confidence": 0.0, "source_page": None},
        "address": {"value": None, "confidence": 0.0, "source_page": None},
    }
    out = await vr.validate_fields("nib", fields, kbli_fetch_fn=_fake_kbli([]))
    assert out["valid"] is True
    assert "nib_format_13_digits" not in out["checks_run"]  # skipped, not run


# --------------------------------------------------------------------------- #
# KBLI dynamic membership (fake fetch -> deterministic)                        #
# --------------------------------------------------------------------------- #

async def test_kbli_existing_code_passes():
    out = await vr.validate_fields(
        "nib", _fields(nib_number="1234567890123", kbli_codes=["56101"]),
        kbli_fetch_fn=_fake_kbli({"56101", "70209"}),
    )
    assert out["valid"] is True
    assert "kbli_exists_in_live_catalogue" in out["checks_run"]


async def test_kbli_nonexistent_code_fails():
    out = await vr.validate_fields(
        "nib", _fields(kbli_codes=["99999"]),
        kbli_fetch_fn=_fake_kbli({"56101", "70209"}),
    )
    assert out["valid"] is False
    assert any("99999 does not exist" in f for f in out["rule_failures"])


async def test_kbli_malformed_code_fails():
    out = await vr.validate_fields(
        "nib", _fields(kbli_codes=["ABC"]),
        kbli_fetch_fn=_fake_kbli({"56101"}),
    )
    assert out["valid"] is False
    assert any("malformed" in f for f in out["rule_failures"])


async def test_kbli_cache_fetched_once():
    calls = {"n": 0}

    async def _fetch():
        calls["n"] += 1
        return frozenset({"56101"})

    await vr.validate_fields("nib", _fields(kbli_codes=["56101"]), kbli_fetch_fn=_fetch)
    await vr.validate_fields("nib", _fields(kbli_codes=["56101"]), kbli_fetch_fn=_fetch)
    assert calls["n"] == 1  # cached process-wide


# --------------------------------------------------------------------------- #
# Worker stage-handler contract                                               #
# --------------------------------------------------------------------------- #

async def test_validate_stage_reads_extract_output(monkeypatch):
    async def _fetch():
        return frozenset({"56101"})

    monkeypatch.setattr(vr, "_fetch_kbli_codes_from_qdrant", _fetch)
    job = {
        "id": 7,
        "stage_output": {
            "extract": {
                "doc_type": "nib",
                "fields": _fields(nib_number="1234567890123", kbli_codes=["56101"]),
            }
        },
    }
    out = await vr.validate_stage(job, "validate")
    assert out["valid"] is True


async def test_validate_stage_rejects_wrong_stage():
    with pytest.raises(ValueError):
        await vr.validate_stage({"id": 1}, "extract")


# --------------------------------------------------------------------------- #
# LIVE: real Qdrant KBLI catalogue (deselect with -m "not slow")              #
# --------------------------------------------------------------------------- #

@pytest.mark.slow
@pytest.mark.integration
async def test_live_kbli_dynamic_query_real_vs_fake():
    """Prove validation queries the LIVE KBLI catalogue (no hardcode).

    Real code 56101 must pass; fabricated code 99999 must fail — both decided
    by the live Qdrant ``kbli_2025_final`` scroll, not a static list.
    """
    qdrant_url = os.getenv("QDRANT_URL", "")
    if (
        os.getenv("RUN_LIVE_QDRANT_TESTS") != "1"
        or not qdrant_url
        or qdrant_url == "http://localhost:6333"
        or not os.getenv("QDRANT_API_KEY")
    ):
        pytest.skip("set RUN_LIVE_QDRANT_TESTS=1 with real Qdrant env")

    # real existing code -> live catalogue accepts it
    ok = await vr.validate_fields("nib", _fields(kbli_codes=["56101"]))
    assert ok["valid"] is True, ok["rule_failures"]

    # fabricated code -> live catalogue rejects it (same cached live set)
    bad = await vr.validate_fields("nib", _fields(kbli_codes=["99999"]))
    assert bad["valid"] is False
    assert any("99999 does not exist" in f for f in bad["rule_failures"])
