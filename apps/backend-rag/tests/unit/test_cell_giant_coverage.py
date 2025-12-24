import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from services.rag.agentic.cell_giant import (
    giant_reason,
    cell_calibrate,
    synthesize_as_zantara,
    synthesize_as_zantara_stream,
    cell_giant_pipeline,
    cell_giant_pipeline_stream,
    GiantConfig,
    SynthesizerConfig,
    ResponseTone
)
from services.rag.agentic.cell_giant.giant_reasoner import (
    _detect_domain,
    _extract_key_points,
    _extract_warnings,
    _extract_suggestions,
    _extract_legal_refs,
    _extract_costs,
    _extract_steps,
    _calculate_quality_score,
    _fallback_reasoning
)
from services.rag.agentic.cell_giant.cell_conscience import (
    _detect_topics,
    _get_calibrations
)
from services.rag.agentic.cell_giant.zantara_synthesizer import (
    _detect_tone,
    _validate_response,
    _clean_response,
    _fallback_synthesis,
    _format_corrections,
    _format_calibrations,
    _format_enhancements,
    _format_user_memory,
    _format_legal_refs
)

# ============================================================================ 
# GIANT REASONER TESTS
# ============================================================================ 

@pytest.mark.asyncio
async def test_giant_reason_success():
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.PRO_MODEL = "pro-model"
    mock_client.FLASH_MODEL = "flash-model"
    
    mock_response = {
        "text": """
### 📋 Analisi Legale
- UU 6/2011: Regola i visti.
- PP 28/2025: Nuovo regolamento F&B.

### ⚠️ Rischi e Trappole
1. Rischio di overstay.
2. Agenti non autorizzati.

### 📝 Processo Step-by-Step
1. **Step 1** (Timeline: 5 giorni): Preparazione documenti.
2. **Step 2** (Timeline: 10 giorni): Sottomissione.

### 📦 Requisiti
| Categoria | Requisito |
|-----------|-----------|
| Capitale | 10 Miliardi |

### 💰 Costi Stimati
- Government fees: 10-15 juta
- Professional fees: 20-30 juta
- Total: 30-45 juta

### 🔄 Alternative
**Opzione A**: KITAS Investor.
"""
    }
    mock_client.generate_content = AsyncMock(return_value=mock_response)
    
    with patch("services.rag.agentic.cell_giant.giant_reasoner.get_genai_client", return_value=mock_client):
        result = await giant_reason("Come apro una PT PMA per un ristorante?")
        
        assert result["detected_domain"] in ["company", "f&b"]
        assert len(result["legal_refs"]) >= 2
        assert "UU 6/2011" in result["legal_refs"]
        assert len(result["warnings"]) >= 2
        assert len(result["steps"]) >= 2
        assert result["quality_score"] > 0.5

@pytest.mark.asyncio
async def test_giant_reason_unavailable():
    mock_client = MagicMock()
    mock_client.is_available = False
    
    with patch("services.rag.agentic.cell_giant.giant_reasoner.get_genai_client", return_value=mock_client):
        result = await giant_reason("Any query")
        assert "temporarily unavailable" in result["reasoning"]
        assert result["quality_score"] == 0.0

@pytest.mark.asyncio
async def test_giant_reason_retry_then_success():
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.PRO_MODEL = "pro-model"
    
    # First response too short, second one good
    mock_client.generate_content = AsyncMock(side_effect=[
        {"text": "Too short"},
        {"text": "Questo è un ragionamento molto lungo e dettagliato che supera i 500 caratteri richiesti per un punteggio di qualità decente. Parliamo di PT PMA e KITAS in Indonesia con riferimenti legali come UU 6/2011 e PP 28/2025. ### 📋 Analisi Legale - UU 6/2011. ### ⚠️ Rischi e Trappole 1. Rischio."}
    ])
    
    with patch("services.rag.agentic.cell_giant.giant_reasoner.get_genai_client", return_value=mock_client), \
         patch("asyncio.sleep", AsyncMock()):
        result = await giant_reason("Complex query")
        assert len(result["reasoning"]) > 100
        assert mock_client.generate_content.call_count == 2

def test_extract_functions_edge_cases():
    text = "Nessuna sezione specifica qui, ma parliamo di 10 milioni IDR e 5 giorni."
    assert _extract_key_points(text) == []
    assert _extract_warnings(text) == []
    # Flexible check for costs extraction
    costs = _extract_costs(text)
    assert "10 milioni IDR" in costs.get("estimated", "")
    assert _extract_steps(text) == []
    assert "UU 6/2011" in _extract_legal_refs("Vedi UU 6/2011 articolo 5.")

def test_calculate_quality_score():
    config = GiantConfig(min_reasoning_length=100)
    # Low quality
    assert _calculate_quality_score("Short text", config) < 0.5
    # High quality
    high_qual_text = """
    Questo testo è lungo abbastanza per superare i controlli di qualità necessari per il sistema Zantara.
    Riferimenti legali: UU 6/2011, PP 28/2025.
    ### Analisi
    ### Rischi
    1. Pericolo critico rilevato nel sistema.
    2. Attenzione ai dettagli legali.
    ### Processo
    ### Requisiti
    10 miliardi IDR di investimento, 30 giorni lavorativi.
    """
    assert _calculate_quality_score(high_qual_text, config) >= 0.8

# ============================================================================ 
# CELL CONSCIENCE TESTS
# ============================================================================ 

@pytest.mark.asyncio
async def test_cell_calibrate_triggers_correction():
    giant_reasoning = {
        "reasoning": "Puoi aprire una PMA con KBLI 56102 e un capitale di solo 2.5 miliardi totale.",
        "quality_score": 0.8
    }
    
    # Removed incorrect patch
    result = await cell_calibrate("Query", giant_reasoning)
    
    # Should trigger KBLI 56102 correction and 2.5 miliardi totale correction
    corrections = [c["error_key"] for c in result["corrections"]]
    assert "kbli 56102" in corrections
    assert any("miliardi" in c for c in corrections)
    assert len(result["enhancements"]) > 0

def test_detect_topics():
    assert "kitas" in _detect_topics("Vorrei un kitas", "")
    assert "f&b" in _detect_topics("", "Parliamo di ristorante e food")
    assert "real_estate" in _detect_topics("Comprare casa", "Hak Pakai")

def test_get_calibrations():
    calibs = _get_calibrations("KITAS e33g", ["kitas"])
    assert "kitas_e33g" in calibs
    assert calibs["kitas_e33g"]["category"] == "visa"

# ============================================================================ 
# ZANTARA SYNTHESIZER TESTS
# ============================================================================ 

@pytest.mark.asyncio
async def test_synthesize_as_zantara_success():
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.FLASH_MODEL = "flash-model"
    mock_client.generate_content = AsyncMock(return_value={"text": "Hello, I am Zantara. Literally your best consultant in Jaksel. Basically, you need a KITAS. We are here to help you navigate the complex Indonesian regulations with style and grace. Trust us for your PT PMA and everything else."})
    
    giant_reasoning = {"reasoning": "Giant reasoning", "quality_score": 0.9, "legal_refs": ["UU 6/2011"]}
    cell_calibration = {
        "corrections": [{"error_key": "test", "correction": "Correct this", "severity": "medium"}],
        "calibrations": {"service": {"price": "10jt"}},
        "enhancements": ["Insight"],
        "user_memory": ["Fact"]
    }
    
    with patch("services.rag.agentic.cell_giant.zantara_synthesizer.get_genai_client", return_value=mock_client):
        response = await synthesize_as_zantara("Query", giant_reasoning, cell_calibration)
        assert "Zantara" in response
        assert any(word in response for word in ["Basically", "Literally", "Hello"])

def test_detect_tone():
    assert _detect_tone("urgent help", [{"severity": "critical"}]) == ResponseTone.URGENT
    assert _detect_tone("come si fa?", []) == ResponseTone.EDUCATIONAL
    assert _detect_tone("contratto legale", []) == ResponseTone.PROFESSIONAL
    assert _detect_tone("ciao", []) == ResponseTone.CASUAL

def test_validate_response():
    corrections = [{"error_key": "KBLI", "correction": "Use 56101 not 56102", "severity": "critical"}]
    
    # Too short
    is_valid, issues = _validate_response("Too short", corrections)
    assert not is_valid
    
    # Missing correction but long enough
    is_valid, issues = _validate_response("I love Bali very much and I want to stay here forever because the vibes are amazing and the people are so friendly and the food is delicious. Jaksel style is the best!" * 2, corrections)
    assert not is_valid
    
    # Has correction and long enough
    is_valid, issues = _validate_response("You should use 56101 for your restaurant setup instead of other codes because it is the standard for PT PMA in Indonesia." * 2, corrections)
    assert is_valid

def test_clean_response():
    dirty = "Secondo il ragionamento base e la calibrazione [INTERNO], devi fare X."
    clean = _clean_response(dirty)
    assert "ragionamento base" not in clean.lower()
    assert "[INTERNO]" not in clean

# ============================================================================ 
# PIPELINE TESTS
# ============================================================================ 

@pytest.mark.asyncio
async def test_cell_giant_pipeline():
    # Patch dependencies at their source
    with patch("services.rag.agentic.cell_giant.giant_reason", AsyncMock(return_value={"reasoning": "...", "quality_score": 0.9})), \
         patch("services.rag.agentic.cell_giant.cell_calibrate", AsyncMock(return_value={})), \
         patch("services.rag.agentic.cell_giant.zantara_synthesizer.synthesize_as_zantara", AsyncMock(return_value="Zantara response")):
        
        result = await cell_giant_pipeline("Query")
        assert result == "Zantara response"

@pytest.mark.asyncio
async def test_cell_giant_pipeline_stream_slow():
    """Test streaming pipeline with a slow giant to trigger keepalive loop."""
    mock_giant = {"reasoning": "...", "quality_score": 0.9}
    mock_cell = {"corrections": [], "calibrations": {}, "enhancements": []}
    
    # We patch wait_for to return a TimeoutError once, then the result
    # This exercises the keepalive yield branch
    with patch("services.rag.agentic.cell_giant.giant_reason", AsyncMock(return_value=mock_giant)), \
         patch("services.rag.agentic.cell_giant.cell_calibrate", AsyncMock(return_value=mock_cell)), \
         patch("services.rag.agentic.cell_giant.zantara_synthesizer.synthesize_as_zantara_stream") as mock_synth, \
         patch("asyncio.wait_for") as mock_wait:
        
        mock_wait.side_effect = [asyncio.TimeoutError(), mock_giant]
        
        async def mock_stream(*args, **kwargs):
            yield "Token"
        mock_synth.return_value = mock_stream()
        
        events = []
        async for event in cell_giant_pipeline_stream("Query"):
            events.append(event)
            
        assert any(e["type"] == "keepalive" for e in events)
        assert any(e["type"] == "done" for e in events)

@pytest.mark.asyncio
async def test_synthesize_as_zantara_stream():
    """Test streaming synthesis."""
    mock_client = MagicMock()
    mock_client.is_available = True
    
    async def mock_gen(*args, **kwargs):
        yield "Chunk 1"
        yield "Chunk 2"
    mock_client.generate_content_stream = mock_gen
    
    with patch("services.rag.agentic.cell_giant.zantara_synthesizer.get_genai_client", return_value=mock_client):
        chunks = []
        async for c in synthesize_as_zantara_stream("Query", {}, {}):
            chunks.append(c)
        assert len(chunks) == 2

def test_formatting_functions():
    """Test internal formatting helpers for coverage."""
    # Format corrections with different severities and sources
    corrs = [
        {"correction": "C1", "severity": "critical", "source": "S1"},
        {"correction": "C2", "severity": "high"},
        {"correction": "C3", "severity": "medium"}
    ]
    formatted_corrs = _format_corrections(corrs)
    assert "🚨" in formatted_corrs
    assert "S1" in formatted_corrs
    assert "C3" in formatted_corrs
    assert _format_corrections([]) == "Nessuna correzione necessaria - il ragionamento e accurato."

    # Format calibrations with categories
    calibs = {
        "s1": {"price": "10jt", "timeline": "1d", "includes": "all", "consultant": "Zan", "category": "cat1"},
        "s2": {"price": "20jt", "timeline": "2d", "includes": "none", "consultant": "Adit", "category": "cat2"}
    }
    formatted_calibs = _format_calibrations(calibs)
    assert "💰" in formatted_calibs
    assert "CAT1" in formatted_calibs
    assert "CAT2" in formatted_calibs
    assert _format_calibrations({}) == "Contattaci per preventivo specifico su questo servizio."

    assert "💡" in _format_enhancements(["Insight"])
    assert "👤" in _format_user_memory(["Fact"])
    assert "UU" in _format_legal_refs(["UU 6/2011"])
    assert _format_legal_refs([]) == "Nessun riferimento legale specifico estratto."

@pytest.mark.asyncio
async def test_fallback_synthesis():
    giant = {"key_points": ["Point 1"], "steps": [{"step": "1", "name": "Step 1"}]}
    cell = {"corrections": [{"correction": "🚨 Critical!", "severity": "critical"}]}
    
    result = _fallback_synthesis(giant, cell)
    assert "Point 1" in result
    assert "Critical!" in result

@pytest.mark.asyncio
async def test_fallback_reasoning_data():
    res = _fallback_reasoning("kitas", "visa", "user")
    assert "Permen 22/2023" in res["reasoning"]
    assert res["detected_domain"] == "visa"