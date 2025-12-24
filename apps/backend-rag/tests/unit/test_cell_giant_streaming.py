import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from services.rag.agentic.cell_giant import (
    synthesize_as_zantara_stream,
    cell_giant_pipeline_stream,
    giant_reason,
    cell_calibrate
)
from services.rag.agentic.orchestrator import AgenticRAGOrchestrator

@pytest.mark.asyncio
async def test_synthesize_as_zantara_stream():
    """Test real streaming synthesis."""
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.FLASH_MODEL = "flash-model"
    
    # Mock stream generator
    async def mock_stream(*args, **kwargs):
        tokens = ["Hello", " ", "I", " am", " Zantara"]
        for t in tokens:
            yield t
            
    mock_client.generate_content_stream = mock_stream
    
    giant_reasoning = {"reasoning": "Giant", "quality_score": 0.9}
    cell_calibration = {"corrections": [], "calibrations": {}}
    
    with patch("services.rag.agentic.cell_giant.zantara_synthesizer.get_genai_client", return_value=mock_client):
        chunks = []
        async for chunk in synthesize_as_zantara_stream("Query", giant_reasoning, cell_calibration):
            chunks.append(chunk)
            
        assert "".join(chunks) == "Hello I am Zantara"
        assert len(chunks) == 5

@pytest.mark.asyncio
async def test_cell_giant_pipeline_stream():
    """Test the full streaming pipeline with phases."""
    mock_giant_res = {"reasoning": "Deep thought", "quality_score": 0.95, "detected_domain": "legal"}
    mock_cell_res = {"corrections": [], "enhancements": [], "calibrations": {}}
    
    # Patch dependencies at their source since they are imported locally in the function
    with patch("services.rag.agentic.cell_giant.giant_reason", AsyncMock(return_value=mock_giant_res)), \
         patch("services.rag.agentic.cell_giant.cell_calibrate", AsyncMock(return_value=mock_cell_res)), \
         patch("services.rag.agentic.cell_giant.zantara_synthesizer.synthesize_as_zantara_stream") as mock_synth_stream:
        
        # Mock the synth stream generator
        async def mock_gen(*args, **kwargs):
            yield "Token 1"
            yield "Token 2"
        mock_synth_stream.return_value = mock_gen()
        
        events = []
        async for event in cell_giant_pipeline_stream("Query"):
            events.append(event)
            
        # Verify event sequence
        types = [e["type"] for e in events]
        assert "phase" in types
        assert "metadata" in types
        assert "chunk" in types
        assert "done" in types
        
        # Check specific phase markers
        phases = [e["name"] for e in events if e["type"] == "phase"]
        assert "giant" in phases
        assert "cell" in phases
        assert "zantara" in phases

@pytest.mark.asyncio
async def test_orchestrator_stream_query_cell_giant():
    """Test orchestrator integration of Cell-Giant streaming."""
    orchestrator = AgenticRAGOrchestrator(tools=[])
    
    mock_giant_res = {"reasoning": "Giant reasons", "key_points": ["P1"], "warnings": ["W1"]}
    mock_cell_res = {"corrections": ["C1"], "legal_sources": [{"title": "Source 1"}]}
    
    with patch.object(orchestrator, "_get_memory_orchestrator", AsyncMock(return_value=None)), \
         patch("services.rag.agentic.orchestrator.get_user_context", AsyncMock(return_value={})), \
         patch("services.rag.agentic.orchestrator.giant_reason", AsyncMock(return_value=mock_giant_res)), \
         patch("services.rag.agentic.orchestrator.cell_calibrate", AsyncMock(return_value=mock_cell_res)), \
         patch("services.rag.agentic.orchestrator.synthesize_as_zantara_stream") as mock_synth:
        
        async def mock_tokens(*args, **kwargs):
            yield "Final"
            yield " answer"
        mock_synth.return_value = mock_tokens()
        
        events = []
        async for event in orchestrator.stream_query_cell_giant("Complex query"):
            events.append(event)
            
        # Verify Intelligent SSE Events
        event_types = [e["type"] for e in events]
        assert "reasoning_step" in event_types
        assert "token" in event_types
        assert "sources" in event_types
        
        # Check reasoning_step details
        reasoning_events = [e for e in events if e["type"] == "reasoning_step"]
        assert any(r["data"]["phase"] == "giant" for r in reasoning_events)
        assert any(r["data"]["phase"] == "cell" for r in reasoning_events)
        
        # Check that metadata was yielded
        assert any(e["type"] == "metadata" for e in events)

@pytest.mark.asyncio
async def test_synthesize_as_zantara_stream_error_fallback():
    """Test that streaming synthesis falls back gracefully on error."""
    mock_client = MagicMock()
    mock_client.is_available = True
    
    # Mock error during stream
    async def mock_error_stream(*args, **kwargs):
        yield "Partial"
        raise RuntimeError("LLM Boom")
            
    mock_client.generate_content_stream = mock_error_stream
    
    giant_reasoning = {"reasoning": "Giant", "quality_score": 0.9}
    cell_calibration = {"corrections": [], "calibrations": {}}
    
    with patch("services.rag.agentic.cell_giant.zantara_synthesizer.get_genai_client", return_value=mock_client), \
         patch("services.rag.agentic.cell_giant.zantara_synthesizer._fallback_synthesis", return_value="Fallback"):
        
        chunks = []
        async for chunk in synthesize_as_zantara_stream("Query", giant_reasoning, cell_calibration):
            chunks.append(chunk)
            
        # Even with error, it should yield what it could or the fallback
        assert len(chunks) > 0
        assert "Fallback" in chunks or "Partial" in chunks
