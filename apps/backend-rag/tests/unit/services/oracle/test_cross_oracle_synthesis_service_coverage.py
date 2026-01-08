import importlib.util
import sys
import types
from pathlib import Path

import pytest

services_pkg = types.ModuleType("services")
services_pkg.__path__ = []
oracle_pkg = types.ModuleType("services.oracle")
oracle_pkg.__path__ = []
sys.modules.update({"services": services_pkg, "services.oracle": oracle_pkg})

module_path = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "services"
    / "oracle"
    / "cross_oracle_synthesis_service.py"
)
spec = importlib.util.spec_from_file_location(
    "services.oracle.cross_oracle_synthesis_service", module_path
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
CrossOracleSynthesisService = module.CrossOracleSynthesisService
OracleQuery = module.OracleQuery


class DummySearchService:
    def __init__(self, results=None, error=None):
        self.results = results or {"results": [{"text": "doc"}]}
        self.error = error
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.results


class DummyZantaraClient:
    def __init__(self, text="synthesis", error=None):
        self.text = text
        self.error = error
        self.calls = []

    async def generate_text(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"text": self.text}


def test_classify_scenario_defaults():
    service = CrossOracleSynthesisService(
        DummySearchService(), zantara_ai_client=DummyZantaraClient()
    )
    scenario, confidence = service.classify_scenario("hello")
    assert scenario == "general"
    assert confidence == 0.0


def test_classify_scenario_business_setup():
    service = CrossOracleSynthesisService(
        DummySearchService(), zantara_ai_client=DummyZantaraClient()
    )
    scenario, confidence = service.classify_scenario("open a restaurant")
    assert scenario == "business_setup"
    assert confidence > 0.0


def test_determine_oracles_unknown():
    service = CrossOracleSynthesisService(
        DummySearchService(), zantara_ai_client=DummyZantaraClient()
    )
    oracles = service.determine_oracles("query", "unknown")
    assert len(oracles) == 1
    assert oracles[0].collection == "visa_oracle"


def test_determine_oracles_known():
    service = CrossOracleSynthesisService(
        DummySearchService(), zantara_ai_client=DummyZantaraClient()
    )
    oracles = service.determine_oracles("open a business", "business_setup")
    assert any(o.collection == "kbli_eye" for o in oracles)
    assert any(o.collection == "bali_zero_pricing" for o in oracles)


@pytest.mark.asyncio
async def test_query_oracle_success():
    search = DummySearchService(results={"results": [{"text": "a"}]})
    service = CrossOracleSynthesisService(search, zantara_ai_client=DummyZantaraClient())
    result = await service.query_oracle(OracleQuery(collection="visa_oracle", query="q"))
    assert result["success"] is True
    assert result["result_count"] == 1


@pytest.mark.asyncio
async def test_query_oracle_error():
    search = DummySearchService(error=RuntimeError("boom"))
    service = CrossOracleSynthesisService(search, zantara_ai_client=DummyZantaraClient())
    result = await service.query_oracle(OracleQuery(collection="visa_oracle", query="q"))
    assert result["success"] is False
    assert result["error"] == "boom"


@pytest.mark.asyncio
async def test_query_all_oracles():
    search = DummySearchService(results={"results": [{"text": "a"}]})
    service = CrossOracleSynthesisService(search, zantara_ai_client=DummyZantaraClient())
    queries = [
        OracleQuery(collection="visa_oracle", query="q"),
        OracleQuery(collection="tax_genius", query="q"),
    ]
    results = await service.query_all_oracles(queries)
    assert set(results.keys()) == {"visa_oracle", "tax_genius"}


@pytest.mark.asyncio
async def test_synthesize_with_zantara_success():
    search = DummySearchService()
    zantara = DummyZantaraClient(text="## Integrated Recommendation\nAnswer")
    service = CrossOracleSynthesisService(search, zantara_ai_client=zantara)
    oracle_results = {
        "visa_oracle": {"success": True, "results": [{"text": "doc"}]},
    }
    text = await service.synthesize_with_zantara("q", "visa_application", oracle_results)
    assert "Integrated Recommendation" in text


@pytest.mark.asyncio
async def test_synthesize_with_zantara_fallback():
    search = DummySearchService()
    zantara = DummyZantaraClient(error=RuntimeError("boom"))
    service = CrossOracleSynthesisService(search, zantara_ai_client=zantara)
    oracle_results = {
        "visa_oracle": {"success": True, "results": [{"text": "doc"}]},
    }
    text = await service.synthesize_with_zantara("q", "visa_application", oracle_results)
    assert "Results for: q" in text


def test_parse_synthesis():
    service = CrossOracleSynthesisService(
        DummySearchService(), zantara_ai_client=DummyZantaraClient()
    )
    text = (
        "## Integrated Recommendation\nAnswer\n\n"
        "## Timeline\n2 weeks\n\n"
        "## Investment Required\n$1000\n\n"
        "## Key Requirements\n- A\n- B\n\n"
        "## Potential Risks\n- R1\n- R2\n"
    )
    parsed = service._parse_synthesis(text)
    assert parsed["timeline"] == "2 weeks"
    assert parsed["investment"] == "$1000"
    assert parsed["key_requirements"] == ["A", "B"]
    assert parsed["risks"] == ["R1", "R2"]


@pytest.mark.asyncio
async def test_synthesize_full_flow_updates_stats():
    search = DummySearchService(results={"results": [{"text": "doc"}]})
    zantara = DummyZantaraClient(text="## Integrated Recommendation\nAnswer")
    service = CrossOracleSynthesisService(search, zantara_ai_client=zantara)
    result = await service.synthesize("open a restaurant")
    assert result.synthesis
    stats = service.get_synthesis_stats()
    assert stats["total_syntheses"] == 1


@pytest.mark.asyncio
async def test_synthesize_with_cache_and_golden_answers():
    """Test synthesize with use_cache=True and golden_answers (line 497)"""
    search = DummySearchService(results={"results": [{"text": "doc"}]})
    zantara = DummyZantaraClient(text="## Integrated Recommendation\nAnswer")
    golden_answers = object()  # Any truthy object to trigger the if condition
    service = CrossOracleSynthesisService(
        search, zantara_ai_client=zantara, golden_answer_service=golden_answers
    )
    result = await service.synthesize("open a restaurant", use_cache=True)
    assert result.synthesis
    assert result.cached is False  # Cache not implemented yet, but line 497 is covered
