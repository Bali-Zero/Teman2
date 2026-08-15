"""Pure contract tests for the read-only OSS twin verifier."""

from __future__ import annotations

from backend.scripts.build_kbli_oss_twin_v3 import build_chunks
from backend.scripts.verify_kbli_oss_twin import (
    audit_twin_points,
    expected_chunk_count,
    metadata_contract_problems,
)


def _record(code: str, *, located: bool, blocked: object = False) -> dict:
    record = {
        "kode_kbli_2025": code,
        "judul": f"Title {code}",
        "uraian": "Official BPS description",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "located" if located else "declared_gap",
        "pma_official_basis": "official locator" if located else None,
        "pma_source_vintage": "2021-05-25" if located else None,
        "l4_bali": {
            "status": "BLOCCATO_CLASSE_RISCHIO",
            "blocked": blocked,
            "needs_review": False,
            "reason": "moratorium",
        },
        "per_skala": [
            {
                "skala_usaha": ["Besar"],
                "kategori_risiko": "Rendah",
                "perizinan": "NIB",
            }
        ],
    }
    return record


def _points(records: list[dict]) -> list[dict]:
    return [
        {"id": chunk["id"], "payload": {"text": chunk["text"], "metadata": chunk["metadata"]}}
        for record in records
        for chunk in build_chunks(record)
    ]


def test_verifier_accepts_payloads_from_the_real_builder() -> None:
    records = [_record("01111", located=False), _record("73100", located=True, blocked=True)]
    canonical = {record["kode_kbli_2025"]: record for record in records}

    for point in _points(records):
        assert metadata_contract_problems(point["payload"], canonical) == []


def test_verifier_detects_raw_gap_status_cap_and_bali_text() -> None:
    record = _record("01111", located=False)
    point = _points([record])[1]
    point["payload"]["text"] += (
        "\nStatus PMA: TERBUKA (Max 100%)"
        "\nSTATUS PMA DI BALI (L4 - moratorium provinsi 2026-05-13):"
    )

    problems = metadata_contract_problems(point["payload"], {"01111": record})

    assert any("raw gap PMA status" in problem for problem in problems)
    assert any("raw gap PMA cap" in problem for problem in problems)
    assert any("neutral Bali disclosure" in problem for problem in problems)


def test_verifier_detects_malformed_bali_boolean_as_neutral() -> None:
    record = _record("86995", located=True, blocked="false")
    points = _points([record])

    assert all(point["payload"]["metadata"]["has_bali_l4"] is False for point in points)
    assert all("STATUS PMA DI BALI" not in point["payload"]["text"] for point in points)
    assert metadata_contract_problems(points[0]["payload"], {"86995": record}) == []


def test_full_audit_derives_counts_and_double_truth_from_input() -> None:
    records = [_record("01111", located=False), _record("73100", located=True, blocked=True)]
    points = _points(records)

    problems, metrics = audit_twin_points(points, records)

    assert problems == []
    assert metrics["expected_chunks"] == sum(expected_chunk_count(record) for record in records)
    assert metrics["actual_located_uraian"] == 1
    assert metrics["expected_double_truth_chunks"] == expected_chunk_count(records[1])
    assert metrics["actual_double_truth_chunks"] == expected_chunk_count(records[1])


def test_full_audit_rejects_missing_uraian_or_chunk() -> None:
    record = _record("73100", located=True, blocked=True)
    points = _points([record])
    points = [point for point in points if point["payload"]["metadata"]["chunk_type"] != "uraian"]

    problems, _ = audit_twin_points(points, [record])

    assert any("chunks, expected" in problem for problem in problems)
    assert any("uraian chunks, expected exactly 1" in problem for problem in problems)
