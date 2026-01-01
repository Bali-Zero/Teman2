"""
Tests for MemoryOrchestrator degraded mode and error handling.

Tests:
- Degraded mode activation on non-critical failures
- Unavailable status on critical failures
- Error classification for initialization failures
- Graceful degradation behavior
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.error_classification import ErrorClassifier, ErrorCategory
from services.memory.orchestrator import MemoryOrchestrator, MemoryServiceStatus


@pytest.fixture
def memory_orchestrator():
    """Create MemoryOrchestrator instance for testing."""
    return MemoryOrchestrator(db_pool=None, database_url="postgresql://test")


@pytest.mark.asyncio
async def test_degraded_mode_on_non_critical_failure(memory_orchestrator):
    """Test that degraded mode is activated on non-critical failures."""
    # Mock memory service to succeed
    mock_memory_service = MagicMock()
    mock_memory_service.get_memory = AsyncMock(return_value=MagicMock())
    mock_memory_service.pool = MagicMock()
    
    # Mock fact extractor to fail (non-critical)
    with patch('services.memory.orchestrator.MemoryServicePostgres', return_value=mock_memory_service), \
         patch('services.memory.orchestrator.MemoryFactExtractor', side_effect=Exception("Fact extractor failed")), \
         patch('services.memory.orchestrator.CollectiveMemoryService', return_value=MagicMock()):
        
        await memory_orchestrator.initialize()
        
        # Should be in degraded mode
        assert memory_orchestrator._status == MemoryServiceStatus.DEGRADED
        assert memory_orchestrator._is_initialized is True


@pytest.mark.asyncio
async def test_unavailable_on_critical_failure(memory_orchestrator):
    """Test that orchestrator is unavailable on critical failures."""
    # Mock memory service to fail (critical)
    with patch('services.memory.orchestrator.MemoryServicePostgres', side_effect=Exception("Memory service failed")):
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="initialization failed"):
            await memory_orchestrator.initialize()
        
        # Should be unavailable
        assert memory_orchestrator._status == MemoryServiceStatus.UNAVAILABLE
        assert memory_orchestrator._is_initialized is False


@pytest.mark.asyncio
async def test_healthy_status_on_success(memory_orchestrator):
    """Test that orchestrator is healthy when all services initialize."""
    # Mock all services to succeed
    mock_memory_service = MagicMock()
    mock_memory_service.get_memory = AsyncMock(return_value=MagicMock())
    mock_memory_service.pool = MagicMock()
    
    with patch('services.memory.orchestrator.MemoryServicePostgres', return_value=mock_memory_service), \
         patch('services.memory.orchestrator.MemoryFactExtractor', return_value=MagicMock()), \
         patch('services.memory.orchestrator.CollectiveMemoryService', return_value=MagicMock()):
        
        await memory_orchestrator.initialize()
        
        # Should be healthy
        assert memory_orchestrator._status == MemoryServiceStatus.HEALTHY
        assert memory_orchestrator._is_initialized is True


@pytest.mark.asyncio
async def test_error_classification_for_failures(memory_orchestrator):
    """Test that initialization failures are classified correctly."""
    # Transient error (connection)
    transient_error = ConnectionError("Connection failed")
    category, severity = ErrorClassifier.classify_error(transient_error)
    assert category == ErrorCategory.TRANSIENT
    
    # Permanent error (import)
    permanent_error = ImportError("Module not found")
    category, severity = ErrorClassifier.classify_error(permanent_error)
    assert category == ErrorCategory.PERMANENT


@pytest.mark.asyncio
async def test_degraded_mode_returns_limited_context(memory_orchestrator):
    """Test that degraded mode returns limited context."""
    # Set to degraded mode
    memory_orchestrator._status = MemoryServiceStatus.DEGRADED
    memory_orchestrator._is_initialized = True
    
    # Mock memory service
    mock_memory_service = MagicMock()
    mock_memory_service.get_memory = AsyncMock(return_value=MagicMock())
    memory_orchestrator._memory_service = mock_memory_service
    
    # Should return context even in degraded mode
    context = await memory_orchestrator.get_user_context("test@example.com", "test query")
    assert context is not None


@pytest.mark.asyncio
async def test_ensure_initialized_raises_on_unavailable(memory_orchestrator):
    """Test that _ensure_initialized raises error when unavailable."""
    memory_orchestrator._status = MemoryServiceStatus.UNAVAILABLE
    memory_orchestrator._is_initialized = False
    
    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="unavailable"):
        memory_orchestrator._ensure_initialized()


@pytest.mark.asyncio
async def test_ensure_initialized_raises_when_not_initialized(memory_orchestrator):
    """Test that _ensure_initialized raises error when not initialized."""
    memory_orchestrator._is_initialized = False
    
    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="not initialized"):
        memory_orchestrator._ensure_initialized()
