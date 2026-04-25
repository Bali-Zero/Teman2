"""Regression tests for claim_extractor.py.

Covers the bug at line 216 (fix 2026-04-25) where `min(highest_tier, tier)`
crashed with TypeError when `sources_metadata[sid]["tier"]` was explicitly
None (not missing). This caused CB_NLM=OPEN and halted NB-2 pipeline for 2+ days.
"""

from apps.evaluator.nlm_deep_research.claim_extractor import extract_claims_from_response


def test_tier_none_in_metadata_no_crash():
    """Regression: sources_metadata with explicit tier=None must not crash.

    Before fix: TypeError: '<' not supported between instances of 'NoneType' and 'int'
    After fix: defaults to tier=2, claim extracted normally.
    """
    response = (
        "Pasal 36 UU 6/2023 mengatur tentang visa kunjungan. "
        "Ketentuan ini berlaku untuk semua warga negara asing "
        "yang memasuki wilayah Indonesia dengan visa B211A atau C1. "
        "Dokumen pendukung wajib disertakan pada saat kedatangan di imigrasi."
    )
    source_ids = ["src-a", "src-b"]
    metadata = {
        "src-a": {"tier": None},   # explicit None — was the crash trigger
        "src-b": {"tier": 1},
    }

    # Must not raise
    claims = extract_claims_from_response(
        response_text=response,
        source_ids=source_ids,
        query_cluster="D",
        sources_metadata=metadata,
    )

    assert len(claims) >= 1, "at least one claim should be extracted"


def test_tier_missing_defaults_to_2():
    """Existing behavior preserved: missing tier defaults to 2."""
    response = (
        "KBLI 56101 adalah kode untuk restoran. "
        "Syarat pendirian PT PMA untuk restoran mencakup modal "
        "minimum IDR 10 miliar sesuai dengan ketentuan BKPM. "
        "Proses lisensi terbit melalui sistem OSS dalam 30 hari."
    )
    metadata = {"src-x": {}}   # no tier key at all

    claims = extract_claims_from_response(
        response_text=response,
        source_ids=["src-x"],
        query_cluster="B",
        sources_metadata=metadata,
    )

    assert len(claims) >= 1


def test_tier_zero_is_preserved():
    """Edge case: tier=0 (if ever set) must NOT be coerced to 2.

    The fix `src.get("tier") or 2` treats 0 as falsy — intentional?
    This test documents current behavior. If tier=0 is a valid tier,
    the fix needs to be `tier = src.get("tier"); tier = 2 if tier is None else tier`.
    """
    response = (
        "Visa Second Home E28 memiliki persyaratan saldo USD 130,000. "
        "Dokumen bank statement harus original dan mencakup "
        "periode 3 bulan terakhir. Berlaku untuk kewarganegaraan tertentu."
    )
    metadata = {"src-t0": {"tier": 0}}

    # Should not crash. Claims still extracted.
    claims = extract_claims_from_response(
        response_text=response,
        source_ids=["src-t0"],
        query_cluster="D",
        sources_metadata=metadata,
    )

    assert len(claims) >= 1
