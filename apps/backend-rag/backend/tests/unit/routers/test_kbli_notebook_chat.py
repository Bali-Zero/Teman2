"""
Unit tests for backend/app/routers/kbli_notebook_chat.py
Covers: helper functions, LLM gateway singleton, language detection,
non-business query check, multi-domain check, translate, explain,
parent doc fetch, known codes, keyword injection map.
Direct function calls (no TestClient) for maximum coverage.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# Module-level LLM gateway mock
# ============================================================

_mock_llm_gateway = MagicMock()
_mock_llm_gateway._available = True
_mock_llm_gateway.create_chat_with_history = MagicMock(return_value=MagicMock())
_mock_llm_gateway.send_message = AsyncMock(
    return_value=(
        "KBLI answer text",
        "gemini-flash",
        MagicMock(),
        {},
    )
)


@pytest.fixture(autouse=True)
def patch_llm_gateway():
    with patch(
        "backend.app.routers.kbli_notebook_chat._llm_gateway_instance",
        _mock_llm_gateway,
    ):
        yield


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


# ============================================================
# _detect_language — all branches
# ============================================================


def test_detect_language_english():
    from backend.app.routers.kbli_notebook_chat import _detect_language

    assert _detect_language("open a restaurant in Bali") == "English"


def test_detect_language_indonesian():
    from backend.app.routers.kbli_notebook_chat import _detect_language

    assert _detect_language("apa syarat usaha buka restoran") == "Indonesian"


def test_detect_language_italian():
    from backend.app.routers.kbli_notebook_chat import _detect_language

    assert _detect_language("voglio aprire una attivita") == "Italian"


def test_detect_language_french():
    from backend.app.routers.kbli_notebook_chat import _detect_language

    assert _detect_language("je veux ouvrir une entreprise") == "French"


def test_detect_language_spanish():
    from backend.app.routers.kbli_notebook_chat import _detect_language

    assert _detect_language("quiero abrir como negocio") == "Spanish"


def test_detect_language_default_english():
    from backend.app.routers.kbli_notebook_chat import _detect_language

    assert _detect_language("xyz abc 123") == "English"


# ============================================================
# _is_non_business_query
# ============================================================


def test_is_non_business_query_true():
    from backend.app.routers.kbli_notebook_chat import _is_non_business_query

    assert _is_non_business_query("How do I get a KITAS?") is True
    assert _is_non_business_query("visa requirements for Bali") is True
    assert _is_non_business_query("best restaurant in Seminyak") is True
    assert _is_non_business_query("KITAP renewal process") is True
    assert _is_non_business_query("agente immigrazione") is True


def test_is_non_business_query_false():
    from backend.app.routers.kbli_notebook_chat import _is_non_business_query

    assert _is_non_business_query("open a restaurant") is False
    assert _is_non_business_query("KBLI code for e-commerce") is False


# ============================================================
# _is_multi_domain_query
# ============================================================


def test_is_multi_domain_query_true():
    from backend.app.routers.kbli_notebook_chat import _is_multi_domain_query

    assert _is_multi_domain_query("Can I open a restaurant with retirement KITAS?") is True
    assert _is_multi_domain_query("PMA company visa requirements") is True


def test_is_multi_domain_query_false():
    from backend.app.routers.kbli_notebook_chat import _is_multi_domain_query

    assert _is_multi_domain_query("What is KBLI 56101?") is False
    assert _is_multi_domain_query("KITAS requirements for foreigners") is False


def test_is_multi_domain_query_business_plus_legal():
    from backend.app.routers.kbli_notebook_chat import _is_multi_domain_query

    assert _is_multi_domain_query("PMA company tax regulation requirements") is True


# ============================================================
# _get_llm_gateway singleton
# ============================================================


def test_get_llm_gateway_returns_cached():
    from backend.app.routers.kbli_notebook_chat import _get_llm_gateway

    gw = _get_llm_gateway()
    # Should return the mocked instance
    assert gw is _mock_llm_gateway


def test_get_llm_gateway_creates_new():
    with patch(
        "backend.app.routers.kbli_notebook_chat._llm_gateway_instance",
        None,
    ):
        with patch(
            "backend.services.rag.agentic.llm_gateway.LLMGateway",
            return_value=MagicMock(),
        ) as mock_cls:
            from backend.app.routers.kbli_notebook_chat import _get_llm_gateway

            gw = _get_llm_gateway()
            # Restores instance after test via autouse fixture


# ============================================================
# _translate_query_for_kbli
# ============================================================


@pytest.mark.asyncio
async def test_translate_query_for_kbli_success():
    from backend.app.routers.kbli_notebook_chat import _translate_query_for_kbli

    _mock_llm_gateway.send_message = AsyncMock(
        return_value=("restoran", "gemini-flash", MagicMock(), {})
    )

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _translate_query_for_kbli("restaurant")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_translate_query_gateway_unavailable():
    from backend.app.routers.kbli_notebook_chat import _translate_query_for_kbli

    _mock_llm_gateway._available = False
    try:
        with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
            result = await _translate_query_for_kbli("xyzrandomtranslatetest")
        # When gateway is unavailable, should return original query
        assert result == "xyzrandomtranslatetest"
    finally:
        _mock_llm_gateway._available = True


@pytest.mark.asyncio
async def test_translate_query_empty_response():
    from backend.app.routers.kbli_notebook_chat import _translate_query_for_kbli

    _mock_llm_gateway.send_message = AsyncMock(
        return_value=("", "gemini-flash", MagicMock(), {})
    )

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _translate_query_for_kbli("test")
    assert result == "test"


@pytest.mark.asyncio
async def test_translate_query_exception():
    from backend.app.routers.kbli_notebook_chat import _translate_query_for_kbli

    _mock_llm_gateway.send_message = AsyncMock(side_effect=Exception("API Error"))

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _translate_query_for_kbli("test query")
    assert result == "test query"


# ============================================================
# _generate_kbli_explanation — success, empty, fallback
# ============================================================


@pytest.mark.asyncio
async def test_generate_kbli_explanation_no_results():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _generate_kbli_explanation("test", [])
    assert "No matching" in result


@pytest.mark.asyncio
async def test_generate_kbli_explanation_success():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    _mock_llm_gateway.send_message = AsyncMock(
        return_value=("Detailed KBLI explanation", "gemini-flash", MagicMock(), {})
    )

    mock_result = MagicMock()
    mock_result.code = "56101"
    mock_result.title = "RESTORAN"
    mock_result.description = "Restaurant activities"
    mock_result.pma_status = "TERBUKA"
    mock_result.risk_category = "Rendah"
    mock_result.expert_legal = None

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _generate_kbli_explanation("restaurant", [mock_result])
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_kbli_explanation_with_parent_docs():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    _mock_llm_gateway.send_message = AsyncMock(
        return_value=("Detailed answer with parent docs", "gemini-flash", MagicMock(), {})
    )

    mock_result = MagicMock()
    mock_result.code = "56101"
    mock_result.title = "RESTORAN"
    mock_result.description = "Restaurant"
    mock_result.pma_status = "TERBUKA"
    mock_result.risk_category = "Rendah"
    mock_result.expert_legal = None

    parent_docs = {"56101": "Full parent document content for restaurant KBLI code 56101..."}

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _generate_kbli_explanation("restaurant", [mock_result], parent_docs)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_generate_kbli_explanation_with_expert_data():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    _mock_llm_gateway.send_message = AsyncMock(
        return_value=("Answer with expert data", "gemini-flash", MagicMock(), {})
    )

    mock_result = MagicMock()
    mock_result.code = "56101"
    mock_result.title = "RESTORAN"
    mock_result.description = "Restaurant"
    mock_result.pma_status = "TERBUKA"
    mock_result.risk_category = "Rendah"
    mock_result.expert_legal = {
        "bab": "III",
        "pasal": "12",
        "pb_umku": ["PB-001"],
        "pma_implications": "Full foreign ownership allowed",
    }

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _generate_kbli_explanation("restaurant", [mock_result])
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_generate_kbli_explanation_llm_error_fallback():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    _mock_llm_gateway._available = False

    mock_result = MagicMock()
    mock_result.code = "56101"
    mock_result.title = "RESTORAN"
    mock_result.description = "Restaurant"
    mock_result.pma_status = "TERBUKA"
    mock_result.risk_category = "Rendah"
    mock_result.expert_legal = None

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _generate_kbli_explanation("restaurant", [mock_result])
    assert "KBLI" in result or "56101" in result

    _mock_llm_gateway._available = True


@pytest.mark.asyncio
async def test_generate_kbli_explanation_empty_response():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    _mock_llm_gateway.send_message = AsyncMock(
        return_value=("", "gemini-flash", MagicMock(), {})
    )

    mock_result = MagicMock()
    mock_result.code = "56101"
    mock_result.title = "RESTORAN"
    mock_result.description = "Restaurant"
    mock_result.pma_status = "TERBUKA"
    mock_result.risk_category = "Rendah"
    mock_result.expert_legal = None

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _generate_kbli_explanation("restaurant", [mock_result])
    # Should still return something (fallback)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_generate_kbli_explanation_indonesian_fallback():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation

    _mock_llm_gateway.send_message = AsyncMock(
        side_effect=Exception("LLM failed")
    )

    mock_result = MagicMock()
    mock_result.code = "56101"
    mock_result.title = "RESTORAN"
    mock_result.description = "Restoran"
    mock_result.pma_status = "TERBUKA"
    mock_result.risk_category = "Rendah"
    mock_result.expert_legal = None

    with patch("backend.app.routers.kbli_notebook_chat.cached", lambda **kw: lambda f: f):
        result = await _generate_kbli_explanation("apa syarat usaha restoran", [mock_result])
    assert "Ditemukan" in result


# ============================================================
# _fetch_parent_documents_from_kbli_table
# ============================================================


@pytest.mark.asyncio
async def test_fetch_parent_documents_success(mock_db_pool):
    from backend.app.routers.kbli_notebook_chat import _fetch_parent_documents_from_kbli_table

    mock_db_pool._mock_conn.fetch.return_value = [
        {"kode_kbli": "56101", "content": "Full content for 56101"},
    ]

    result = await _fetch_parent_documents_from_kbli_table(["56101"], mock_db_pool)
    assert "56101" in result
    assert result["56101"] == "Full content for 56101"


@pytest.mark.asyncio
async def test_fetch_parent_documents_no_codes():
    from backend.app.routers.kbli_notebook_chat import _fetch_parent_documents_from_kbli_table

    result = await _fetch_parent_documents_from_kbli_table([], MagicMock())
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_parent_documents_no_pool():
    from backend.app.routers.kbli_notebook_chat import _fetch_parent_documents_from_kbli_table

    result = await _fetch_parent_documents_from_kbli_table(["56101"], None)
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_parent_documents_no_rows(mock_db_pool):
    from backend.app.routers.kbli_notebook_chat import _fetch_parent_documents_from_kbli_table

    mock_db_pool._mock_conn.fetch.return_value = []

    result = await _fetch_parent_documents_from_kbli_table(["99999"], mock_db_pool)
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_parent_documents_db_error(mock_db_pool):
    from backend.app.routers.kbli_notebook_chat import _fetch_parent_documents_from_kbli_table

    mock_db_pool._mock_conn.fetch.side_effect = Exception("DB error")

    result = await _fetch_parent_documents_from_kbli_table(["56101"], mock_db_pool)
    assert result == {}


# ============================================================
# KNOWN_KBLI_CODES and NON_BUSINESS_KEYWORDS
# ============================================================


def test_known_kbli_codes_structure():
    from backend.app.routers.kbli_notebook_chat import KNOWN_KBLI_CODES

    assert isinstance(KNOWN_KBLI_CODES, dict)
    assert "47911" in KNOWN_KBLI_CODES
    assert "56301" in KNOWN_KBLI_CODES
    for code, data in KNOWN_KBLI_CODES.items():
        assert "title" in data
        assert "description" in data
        assert "pma_status" in data
        assert "risk_category" in data


def test_non_business_keywords_list():
    from backend.app.routers.kbli_notebook_chat import NON_BUSINESS_KEYWORDS

    assert isinstance(NON_BUSINESS_KEYWORDS, list)
    assert "kitas" in NON_BUSINESS_KEYWORDS
    assert "visa" in NON_BUSINESS_KEYWORDS
    assert "best restaurant" in NON_BUSINESS_KEYWORDS


# ============================================================
# MIN_RELEVANCE_SCORE constant
# ============================================================


def test_min_relevance_score():
    from backend.app.routers.kbli_notebook_chat import MIN_RELEVANCE_SCORE

    assert MIN_RELEVANCE_SCORE == 0.40


# ============================================================
# _generate_kbli_explanation_gemini delegates
# ============================================================


@pytest.mark.asyncio
async def test_generate_kbli_explanation_gemini_delegates():
    from backend.app.routers.kbli_notebook_chat import _generate_kbli_explanation_gemini

    with patch(
        "backend.app.routers.kbli_notebook_chat._generate_kbli_explanation",
        new=AsyncMock(return_value="delegated answer"),
    ):
        result = await _generate_kbli_explanation_gemini("test", [])
    assert result == "delegated answer"
