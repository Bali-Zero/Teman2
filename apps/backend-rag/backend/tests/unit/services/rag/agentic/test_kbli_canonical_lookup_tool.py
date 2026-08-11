"""Contract tests for exact KBLI 2025 retrieval in the agentic RAG path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.rag.agentic import tools as tools_module
from backend.services.rag.agentic.tools import KBLICanonicalLookupTool

_REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "data/source_documents/KBLI_2025_FINAL_CLEAN.json").is_file()
)
_DATASET = _REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"


def test_default_dataset_path_tolerates_shallow_fly_layout(monkeypatch):
    monkeypatch.setattr(tools_module, "__file__", "/app/backend/services/rag/agentic/tools.py")
    assert tools_module._default_kbli_dataset_path() == Path(
        "/app/source_documents/KBLI_2025_FINAL_CLEAN.json"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "cap", "condition"),
    [
        ("51101", 49, "single majority"),
        ("79122", 0, "Islamic faith"),
        ("25200", 49, "Menteri Pertahanan"),
    ],
)
async def test_exact_lookup_returns_canonical_pma_fields(code, cap, condition):
    tool = KBLICanonicalLookupTool(dataset_path=_DATASET)

    payload = json.loads(await tool.execute(code=code))

    assert payload["found"] is True
    assert payload["code"] == code
    assert payload["pma"]["status"] == "TERBATAS"
    assert payload["pma"]["max_foreign_ownership_percent"] == cap
    assert condition in payload["pma"]["condition"]
    assert payload["pma"]["cap_verified"] is True
    assert payload["source"]["dataset"] == "KBLI_2025_FINAL_CLEAN.json"


@pytest.mark.asyncio
async def test_nonexistent_2025_code_is_explicitly_absent_not_semantically_mapped():
    tool = KBLICanonicalLookupTool(dataset_path=_DATASET)

    payload = json.loads(await tool.execute(code="68200"))

    assert payload == {
        "found": False,
        "code": "68200",
        "reason": "CODE_NOT_IN_KBLI_2025_CANONICAL",
        "source": {"dataset": "KBLI_2025_FINAL_CLEAN.json"},
    }


@pytest.mark.asyncio
async def test_missing_dataset_is_unavailable_not_a_false_code_absence(tmp_path):
    tool = KBLICanonicalLookupTool(dataset_path=tmp_path / "missing.json")

    payload = json.loads(await tool.execute(code="51101"))

    assert payload == {
        "found": False,
        "code": "51101",
        "error": "DATASET_UNAVAILABLE",
        "source": {"dataset": "KBLI_2025_FINAL_CLEAN.json"},
    }


@pytest.mark.asyncio
async def test_null_scale_list_is_tolerated(tmp_path):
    dataset = tmp_path / "kbli.json"
    dataset.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "kode_kbli_2025": "99999",
                        "judul": "Synthetic schema-edge record",
                        "per_skala": [
                            {"skala_usaha": None, "kategori_risiko": "Rendah"}
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    tool = KBLICanonicalLookupTool(dataset_path=dataset)

    payload = json.loads(await tool.execute(code="99999"))

    assert payload["found"] is True
    assert payload["risk_at_large_scale"] == []


@pytest.mark.asyncio
async def test_lookup_carries_bali_moratorium_verdict_verbatim():
    tool = KBLICanonicalLookupTool(dataset_path=_DATASET)

    payload = json.loads(await tool.execute(code="10211"))

    moratorium = payload["bali"]["moratorium"]
    assert payload["bali"]["blocked"] is True
    assert "Low + Medium-Low" in moratorium["rule"]
    assert "permanent" in moratorium["rule"]
    assert moratorium["effective"] == "2026-05-13"
    assert moratorium["source"] == "Gubernur letter B.27.000/642/PM/DPMPTSP"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["", "1234", "123456", "51A01"])
async def test_lookup_rejects_non_five_digit_input(code):
    tool = KBLICanonicalLookupTool(dataset_path=_DATASET)

    payload = json.loads(await tool.execute(code=code))

    assert payload["found"] is False
    assert payload["reason"] == "INVALID_KBLI_CODE_FORMAT"


def test_prompt_requires_exact_lookup_and_locks_curated_legal_traps():
    from backend.prompts.zantara_core_v4 import TOOL_USAGE_POLICY

    assert "CALL kbli_lookup(code=\"...\") FIRST" in TOOL_USAGE_POLICY
    assert "error=DATASET_UNAVAILABLE" in TOOL_USAGE_POLICY
    assert "Rp2.500.000.000" in TOOL_USAGE_POLICY
    assert "Rp10.000.000.000" in TOOL_USAGE_POLICY
    assert "NEVER describe Rp10.000.000.000 as paid-up capital" in TOOL_USAGE_POLICY
    assert "56101, 56210, 56290, 56103, 56303, 68120, 11052" in TOOL_USAGE_POLICY
    assert "does not state a fixed three-year SLHS validity" in TOOL_USAGE_POLICY
    assert "island-wide and permanent" in TOOL_USAGE_POLICY
