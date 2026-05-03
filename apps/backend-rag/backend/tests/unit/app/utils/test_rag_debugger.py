"""
Unit tests for app/utils/rag_debugger.py
Target: >95% coverage
"""

import sys
import time
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.utils.rag_debugger import RAGPipelineDebugger, RAGPipelineStep, RAGPipelineTrace


class TestRAGPipelineStep:
    """Tests for RAGPipelineStep"""

    def test_init(self):
        """Test RAGPipelineStep initialization"""
        step = RAGPipelineStep(step_name="test_step", start_time=time.time())
        assert step.step_name == "test_step"
        assert step.start_time > 0
        assert step.end_time is None
        assert step.duration_ms is None
        assert step.input_data is None
        assert step.output_data is None
        assert step.error is None

    def test_finish_success(self):
        """Test finishing step with success"""
        step = RAGPipelineStep(step_name="test", start_time=time.time())
        time.sleep(0.01)
        step.finish(output_data={"result": "success"})

        assert step.end_time is not None
        assert step.duration_ms is not None
        assert step.duration_ms > 0
        assert step.output_data == {"result": "success"}
        assert step.error is None

    def test_finish_with_error(self):
        """Test finishing step with error"""
        step = RAGPipelineStep(step_name="test", start_time=time.time())
        step.finish(error="Test error")

        assert step.error == "Test error"
        assert step.output_data is None


class TestRAGPipelineTrace:
    """Tests for RAGPipelineTrace"""

    def test_init(self):
        """Test RAGPipelineTrace initialization"""
        trace = RAGPipelineTrace(query="test query")
        assert trace.query == "test query"
        assert trace.correlation_id is None
        assert trace.steps == []
        assert trace.documents_retrieved == []
        assert trace.documents_reranked == []
        assert trace.final_response is None

    def test_add_step(self):
        """Test adding step to trace"""
        trace = RAGPipelineTrace(query="test")
        # Pass model as a kwarg (not inside metadata dict)
        step = trace.add_step("embedding", model="test")

        assert len(trace.steps) == 1
        assert step.step_name == "embedding"
        assert step.metadata == {"model": "test"}

    def test_finish(self):
        """Test finishing trace"""
        trace = RAGPipelineTrace(query="test")
        time.sleep(0.01)
        trace.finish(final_response="Test response")

        assert trace.end_time is not None
        assert trace.total_duration_ms is not None
        assert trace.total_duration_ms > 0
        assert trace.final_response == "Test response"

    def test_to_dict(self):
        """Test converting trace to dictionary"""
        trace = RAGPipelineTrace(query="test", correlation_id="corr-123")
        step = trace.add_step("test_step")
        step.finish(output_data={"result": "ok"})
        trace.finish(final_response="Done")

        result = trace.to_dict()

        assert result["query"] == "test"
        assert result["correlation_id"] == "corr-123"
        assert len(result["steps"]) == 1
        assert result["final_response"] == "Done"


class TestRAGPipelineDebugger:
    """Tests for RAGPipelineDebugger"""

    def test_init(self):
        """Test RAGPipelineDebugger initialization"""
        debugger = RAGPipelineDebugger(query="test query", correlation_id="test-123")
        # query is stored in trace, not on debugger directly
        assert debugger.trace.query == "test query"
        assert debugger.trace.correlation_id == "test-123"
        assert debugger.trace is not None

    def test_init_without_correlation_id(self):
        """Test initialization without correlation ID"""
        debugger = RAGPipelineDebugger(query="test")
        assert debugger.trace.query == "test"
        assert debugger.trace.correlation_id is None

    def test_step_context_manager(self):
        """Test using step as context manager"""
        debugger = RAGPipelineDebugger(query="test")

        with debugger.step("embedding") as step:
            assert step.step_name == "embedding"
            time.sleep(0.01)

        assert step.end_time is not None
        assert step.duration_ms is not None

    def test_step_context_manager_with_exception(self):
        """Test step context manager with exception"""
        debugger = RAGPipelineDebugger(query="test")

        with pytest.raises(ValueError), debugger.step("test_step"):
            raise ValueError("Test error")

        # Step should still be finished
        assert len(debugger.trace.steps) == 1

    def test_finish(self):
        """Test finishing debugger"""
        debugger = RAGPipelineDebugger(query="test")
        # Parameter is 'response', not 'final_response'
        trace = debugger.finish(response="Done")

        assert trace.final_response == "Done"
        assert trace.total_duration_ms is not None

    def test_get_trace(self):
        """Test getting trace as dict"""
        debugger = RAGPipelineDebugger(query="test")
        # get_trace returns a dict, not RAGPipelineTrace
        trace_dict = debugger.get_trace()

        assert trace_dict["query"] == "test"
        assert isinstance(trace_dict, dict)

    def test_add_documents_retrieved(self):
        """Test adding retrieved documents"""
        debugger = RAGPipelineDebugger(query="test")
        docs = [{"id": 1, "text": "doc1"}, {"id": 2, "text": "doc2"}]
        # Method is add_documents with stage parameter
        debugger.add_documents(docs, stage="retrieved")

        assert len(debugger.trace.documents_retrieved) == 2

    def test_add_documents_reranked(self):
        """Test adding reranked documents"""
        debugger = RAGPipelineDebugger(query="test")
        docs = [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.8}]
        debugger.add_documents(docs, stage="reranked")

        assert len(debugger.trace.documents_reranked) == 2

    def test_add_confidence_scores(self):
        """Test adding confidence scores"""
        debugger = RAGPipelineDebugger(query="test")
        scores = [0.9, 0.8, 0.7]
        debugger.add_confidence_scores(scores)

        assert debugger.trace.confidence_scores == scores

    def test_add_fallback(self):
        """Test adding fallback activation"""
        debugger = RAGPipelineDebugger(query="test")
        debugger.add_fallback("model_fallback")

        assert "model_fallback" in debugger.trace.fallbacks_activated
