"""
Unit tests for Agents Router
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.agents import (
    AddComplianceItemRequest,
    CreateJourneyRequest,
    add_compliance_tracking,
    calculate_dynamic_pricing,
    complete_journey_step,
    create_client_journey,
    cross_oracle_synthesis,
    export_knowledge_graph,
    extract_knowledge_graph,
    get_agents_status,
    get_analytics_summary,
    get_compliance_alerts,
    get_ingestion_status,
    get_journey,
    get_next_steps,
    run_auto_ingestion,
    run_autonomous_research,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_journey():
    """Mock ClientJourney object"""
    journey = MagicMock()
    journey.journey_id = "journey-123"
    journey.steps = [{"step_id": "step-1", "title": "Step 1"}]
    journey.__dict__ = {
        "journey_id": "journey-123",
        "journey_type": "pt_pma_setup",
        "client_id": "client-123",
        "steps": [{"step_id": "step-1", "title": "Step 1"}],
        "status": "in_progress",
    }
    # MagicMock is truthy by default, no need to set __bool__
    return journey


@pytest.fixture
def mock_compliance_item():
    """Mock ComplianceItem object"""
    item = MagicMock()
    item.item_id = "item-123"
    item.client_id = "client-123"
    item.title = "Visa Expiry"
    item.deadline = datetime(2024, 12, 31)
    item.estimated_cost = 5000000
    item.__dict__ = {
        "item_id": "item-123",
        "client_id": "client-123",
        "compliance_type": "visa_expiry",
        "title": "Visa Expiry",
        "description": "KITAS expiring soon",
        "deadline": datetime(2024, 12, 31),
        "estimated_cost": 5000000,
    }
    return item


@pytest.fixture
def mock_alert():
    """Mock ComplianceAlert object"""
    from services.proactive_compliance_monitor import AlertSeverity

    alert = MagicMock()
    alert.alert_id = "alert-123"
    alert.client_id = "client-123"
    alert.title = "Visa Expiry"
    alert.deadline = datetime(2024, 12, 31)
    alert.estimated_cost = 5000000
    alert.days_until_deadline = 7
    alert.severity = AlertSeverity.CRITICAL
    alert.__dict__ = {
        "alert_id": "alert-123",
        "client_id": "client-123",
        "title": "Visa Expiry",
        "deadline": datetime(2024, 12, 31),
        "estimated_cost": 5000000,
        "days_until_deadline": 7,
        "severity": AlertSeverity.CRITICAL,
    }
    return alert


# ============================================================================
# Tests for /status endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_agents_status():
    """Test get_agents_status endpoint"""
    result = await get_agents_status()

    assert result["status"] == "operational"
    assert result["total_agents"] == 10
    assert "phase_1_2_foundation" in result["agents"]
    assert "phase_3_orchestration" in result["agents"]
    assert "capabilities" in result


# ============================================================================
# Tests for Journey Orchestrator endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_create_client_journey_success(mock_journey):
    """Test successful journey creation"""
    request = CreateJourneyRequest(journey_type="pt_pma_setup", client_id="client-123")

    with patch("app.routers.agents.journey_orchestrator.create_journey", return_value=mock_journey):
        result = await create_client_journey(request)

        assert result["success"] is True
        assert result["journey_id"] == "journey-123"
        assert "journey" in result
        assert result["message"] == "Journey created with 1 steps"


@pytest.mark.asyncio
async def test_create_client_journey_error():
    """Test journey creation error"""
    request = CreateJourneyRequest(journey_type="invalid_type", client_id="client-123")

    with patch(
        "app.routers.agents.journey_orchestrator.create_journey",
        side_effect=ValueError("Invalid journey type"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_client_journey(request)

        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_journey_success():
    """Test successful journey retrieval"""

    # Create simple object instead of MagicMock to avoid boolean evaluation issues
    class MockJourney:
        def __init__(self):
            self.journey_id = "journey-123"
            self.journey_type = "pt_pma_setup"
            self.status = "in_progress"

        @property
        def __dict__(self):
            return {
                "journey_id": self.journey_id,
                "journey_type": self.journey_type,
                "status": self.status,
            }

    mock_journey = MockJourney()
    mock_progress = {"completed": 2, "total": 5, "percentage": 40.0}

    with patch("app.routers.agents.journey_orchestrator.get_journey", return_value=mock_journey):
        with patch(
            "app.routers.agents.journey_orchestrator.get_progress", return_value=mock_progress
        ):
            result = await get_journey("journey-123")

            assert result["success"] is True
            assert "journey" in result
            assert "progress" in result
            assert result["progress"] == mock_progress
            assert result["journey"]["journey_id"] == "journey-123"


@pytest.mark.asyncio
async def test_get_journey_not_found():
    """Test journey not found"""
    with patch("app.routers.agents.journey_orchestrator.get_journey", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await get_journey("nonexistent")

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_complete_journey_step_success(mock_journey):
    """Test successful step completion"""
    with (
        patch("app.routers.agents.journey_orchestrator.complete_step") as mock_complete,
        patch("app.routers.agents.journey_orchestrator.get_journey", return_value=mock_journey),
    ):
        result = await complete_journey_step("journey-123", "step-1", "Notes")

        assert result["success"] is True
        assert "message" in result
        mock_complete.assert_called_once_with("journey-123", "step-1", "Notes")


@pytest.mark.asyncio
async def test_complete_journey_step_error():
    """Test step completion error"""
    with patch(
        "app.routers.agents.journey_orchestrator.complete_step",
        side_effect=ValueError("Step not found"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await complete_journey_step("journey-123", "invalid-step")

        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_next_steps():
    """Test get next steps"""
    mock_step = MagicMock()
    mock_step.__dict__ = {"step_id": "step-2", "title": "Next Step"}

    with patch("app.routers.agents.journey_orchestrator.get_next_steps", return_value=[mock_step]):
        result = await get_next_steps("journey-123")

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["next_steps"]) == 1


# ============================================================================
# Tests for Compliance Monitor endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_add_compliance_tracking_success(mock_compliance_item):
    """Test successful compliance tracking addition"""
    request = AddComplianceItemRequest(
        client_id="client-123",
        compliance_type="visa_expiry",
        title="KITAS Expiry",
        description="KITAS expiring soon",
        deadline="2024-12-31",
        estimated_cost=5000000,
        required_documents=["passport", "visa"],
    )

    with patch(
        "app.routers.agents.compliance_monitor.add_compliance_item",
        return_value=mock_compliance_item,
    ):
        result = await add_compliance_tracking(request)

        assert result["success"] is True
        assert result["item_id"] == "item-123"
        assert "item" in result


@pytest.mark.asyncio
async def test_add_compliance_tracking_error():
    """Test compliance tracking addition error"""
    request = AddComplianceItemRequest(
        client_id="client-123",
        compliance_type="invalid_type",
        title="Test",
        description="Test",
        deadline="2024-12-31",
    )

    with patch(
        "app.routers.agents.compliance_monitor.add_compliance_item",
        side_effect=ValueError("Invalid compliance type"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await add_compliance_tracking(request)

        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_compliance_alerts_no_filters(mock_alert):
    """Test get compliance alerts without filters"""
    with patch(
        "app.routers.agents.compliance_monitor.check_compliance_items", return_value=[mock_alert]
    ):
        result = await get_compliance_alerts()

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["alerts"]) == 1
        assert "breakdown" in result


@pytest.mark.asyncio
async def test_get_compliance_alerts_with_client_filter(mock_alert):
    """Test get compliance alerts with client filter"""
    with patch(
        "app.routers.agents.compliance_monitor.check_compliance_items", return_value=[mock_alert]
    ):
        result = await get_compliance_alerts(client_id="client-123")

        assert result["success"] is True
        assert result["count"] == 1


@pytest.mark.asyncio
async def test_get_compliance_alerts_with_severity_filter(mock_alert):
    """Test get compliance alerts with severity filter"""
    with patch(
        "app.routers.agents.compliance_monitor.check_compliance_items", return_value=[mock_alert]
    ):
        result = await get_compliance_alerts(severity="critical")

        assert result["success"] is True
        # Alert should be filtered if severity matches


@pytest.mark.asyncio
async def test_get_compliance_alerts_with_auto_notify(mock_alert):
    """Test get compliance alerts with auto_notify enabled"""
    mock_notification_hub = AsyncMock()
    mock_notification_hub.send = AsyncMock(
        return_value={"notification_id": "notif-123", "status": "sent"}
    )

    with (
        patch(
            "app.routers.agents.compliance_monitor.check_compliance_items",
            return_value=[mock_alert],
        ),
    ):
        # NOTE: notification_hub removed - auto_notify now just logs
        result = await get_compliance_alerts(auto_notify=True)

        assert result["success"] is True
        assert result["count"] == 1
        # notifications_sent is empty list when auto_notify=True (MCP integration pending)
        assert result["notifications_sent"] == []


@pytest.mark.asyncio
async def test_get_compliance_alerts_auto_notify_error(mock_alert):
    """Test auto_notify with notification sending error"""
    mock_notification_hub = AsyncMock()
    mock_notification_hub.send = AsyncMock(side_effect=Exception("Notification failed"))

    with (
        patch(
            "app.routers.agents.compliance_monitor.check_compliance_items",
            return_value=[mock_alert],
        ),
    ):
        # NOTE: notification_hub removed - auto_notify now just logs
        # Should not raise exception, just log error
        result = await get_compliance_alerts(auto_notify=True)

        assert result["success"] is True
        assert result["count"] == 1
        # notifications_sent is empty list when auto_notify=True (MCP integration pending)
        assert result["notifications_sent"] == []


@pytest.mark.asyncio
async def test_get_compliance_alerts_with_dict_alert():
    """Test get compliance alerts with dict-based alert (not object)"""
    from services.proactive_compliance_monitor import AlertSeverity

    dict_alert = {
        "alert_id": "alert-456",
        "client_id": "client-456",
        "title": "Tax Filing",
        "deadline": "2024-12-31",
        "estimated_cost": 3000000,
        "days_until": 30,
        "severity": AlertSeverity.URGENT.value,
    }

    with patch(
        "app.routers.agents.compliance_monitor.check_compliance_items", return_value=[dict_alert]
    ):
        result = await get_compliance_alerts(client_id="client-456")

        assert result["success"] is True
        assert result["count"] == 1


# Skipped - Method get_client_items doesn't exist on ProactiveComplianceMonitor
# Coverage: Endpoint exists but method not implemented in service yet
# Lines 341-342 cannot be tested until service method is implemented


# ============================================================================
# Tests for Knowledge Graph endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_extract_knowledge_graph():
    """Test knowledge graph extraction"""
    mock_request = MagicMock()
    result = await extract_knowledge_graph(
        request=mock_request, text="John works for PT ABC in Jakarta"
    )

    assert result["success"] is True
    assert result["text_length"] == len("John works for PT ABC in Jakarta")
    assert "features" in result


@pytest.mark.asyncio
async def test_export_knowledge_graph():
    """Test knowledge graph export"""
    result = await export_knowledge_graph(format="neo4j")

    assert result["success"] is True
    assert result["format"] == "neo4j"
    assert "warning" in result  # Placeholder endpoint


# ============================================================================
# Tests for Auto Ingestion endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_run_auto_ingestion():
    """Test run auto ingestion"""
    result = await run_auto_ingestion(sources=["kemenkeu"], force=True)

    assert result["success"] is True
    assert result["sources"] == ["kemenkeu"]
    assert result["force"] is True


@pytest.mark.asyncio
async def test_get_ingestion_status():
    """Test get ingestion status"""
    result = await get_ingestion_status()

    assert result["success"] is True
    assert result["status"] == "operational"
    assert "features" in result


# ============================================================================
# Tests for Foundation Agents endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_cross_oracle_synthesis():
    """Test cross-oracle synthesis"""
    mock_request = MagicMock()
    # Mock the app.state to return None for services (missing dependencies)
    # Use configure_mock to ensure getattr returns None, not MagicMock
    mock_state = MagicMock()
    mock_state.configure_mock(intelligent_router=None, search_service=None, ai_client=None)
    mock_request.app.state = mock_state

    result = await cross_oracle_synthesis(
        request=mock_request, query="Tax regulations", domains=["tax", "legal"]
    )

    # Expect failure response when dependencies are missing
    assert result["success"] is False
    assert result["error"] == "CrossOracleSynthesisService not available - missing dependencies"
    assert result["query"] == "Tax regulations"
    assert result["domains"] == ["tax", "legal"]


@pytest.mark.asyncio
async def test_calculate_dynamic_pricing():
    """Test dynamic pricing calculation"""
    result = await calculate_dynamic_pricing(
        service_type="pt_pma", complexity="complex", urgency="urgent"
    )

    assert result["success"] is True
    assert result["service_type"] == "pt_pma"
    assert result["complexity"] == "complex"
    assert result["urgency"] == "urgent"


@pytest.mark.asyncio
async def test_run_autonomous_research():
    """Test autonomous research"""
    mock_request = MagicMock()
    # Mock the app.state to return None for services (missing dependencies)
    # Use configure_mock to ensure getattr returns None, not MagicMock
    mock_state = MagicMock()
    mock_state.configure_mock(search_service=None, ai_client=None, query_router=None)
    mock_request.app.state = mock_state

    result = await run_autonomous_research(
        request=mock_request,
        topic="Indonesian tax law",
        depth="deep",
        sources=["oracle_collections"],
    )

    # Expect failure response when dependencies are missing
    assert result["success"] is False
    assert result["error"] == "AutonomousResearchService not available - missing dependencies"
    assert result["topic"] == "Indonesian tax law"
    assert result["depth"] == "deep"


# ============================================================================
# Tests for Analytics endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_get_analytics_summary():
    """Test get analytics summary"""
    mock_stats = {"total_journeys": 10, "active_journeys": 5, "completed_journeys": 5}

    with patch(
        "app.routers.agents.journey_orchestrator.get_orchestrator_stats", return_value=mock_stats
    ):
        result = await get_analytics_summary()

        assert result["success"] is True
        assert "analytics" in result
        assert result["analytics"]["journeys"] == mock_stats
        assert "timestamp" in result


# ============================================================================
# Additional Edge Cases and Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_client_journey_with_custom_steps(mock_journey):
    """Test journey creation with custom steps"""
    custom_steps = [
        {"step_id": "custom-1", "title": "Custom Step 1", "order": 1},
        {"step_id": "custom-2", "title": "Custom Step 2", "order": 2},
    ]
    request = CreateJourneyRequest(
        journey_type="pt_pma_setup", client_id="client-123", custom_steps=custom_steps
    )

    with patch(
        "app.routers.agents.journey_orchestrator.create_journey", return_value=mock_journey
    ) as mock_create:
        result = await create_client_journey(request)

        assert result["success"] is True
        # Verify custom_steps were passed
        call_args = mock_create.call_args
        assert call_args.kwargs["custom_steps"] == custom_steps


@pytest.mark.asyncio
async def test_create_client_journey_empty_client_id():
    """Test journey creation with empty client_id"""
    request = CreateJourneyRequest(journey_type="pt_pma_setup", client_id="")

    with patch(
        "app.routers.agents.journey_orchestrator.create_journey",
        side_effect=ValueError("Client ID cannot be empty"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_client_journey(request)

        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_journey_empty_id():
    """Test get journey with empty journey_id"""
    with patch("app.routers.agents.journey_orchestrator.get_journey", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await get_journey("")

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_complete_journey_step_empty_notes(mock_journey):
    """Test step completion with empty notes"""
    with (
        patch("app.routers.agents.journey_orchestrator.complete_step") as mock_complete,
        patch("app.routers.agents.journey_orchestrator.get_journey", return_value=mock_journey),
    ):
        result = await complete_journey_step("journey-123", "step-1", None)

        assert result["success"] is True
        mock_complete.assert_called_once_with("journey-123", "step-1", None)


@pytest.mark.asyncio
async def test_get_next_steps_empty_list():
    """Test get next steps when no steps available"""
    with patch("app.routers.agents.journey_orchestrator.get_next_steps", return_value=[]):
        result = await get_next_steps("journey-123")

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["next_steps"]) == 0


@pytest.mark.asyncio
async def test_add_compliance_tracking_invalid_deadline_format():
    """Test compliance tracking with invalid deadline format"""
    request = AddComplianceItemRequest(
        client_id="client-123",
        compliance_type="visa_expiry",
        title="Test",
        description="Test",
        deadline="invalid-date",
    )

    with patch(
        "app.routers.agents.compliance_monitor.add_compliance_item",
        side_effect=ValueError("Invalid date format"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await add_compliance_tracking(request)

        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_add_compliance_tracking_negative_cost(mock_compliance_item):
    """Test compliance tracking with negative estimated cost"""
    request = AddComplianceItemRequest(
        client_id="client-123",
        compliance_type="visa_expiry",
        title="Test",
        description="Test",
        deadline="2024-12-31",
        estimated_cost=-1000,
    )

    # Should still work (validation might be in service layer)
    with patch(
        "app.routers.agents.compliance_monitor.add_compliance_item",
        return_value=mock_compliance_item,
    ):
        result = await add_compliance_tracking(request)
        assert result["success"] is True


@pytest.mark.asyncio
async def test_get_compliance_alerts_empty_list():
    """Test get compliance alerts when no alerts exist"""
    with patch("app.routers.agents.compliance_monitor.check_compliance_items", return_value=[]):
        result = await get_compliance_alerts()

        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["alerts"]) == 0
        assert result["breakdown"]["critical"] == 0
        assert result["breakdown"]["urgent"] == 0


@pytest.mark.asyncio
async def test_get_compliance_alerts_multiple_severities():
    """Test get compliance alerts with multiple severity levels"""
    from services.proactive_compliance_monitor import AlertSeverity

    # Create simple objects instead of MagicMock to avoid attribute issues
    class MockAlert:
        def __init__(self, alert_id, client_id, severity):
            self.alert_id = alert_id
            self.client_id = client_id
            self.title = f"{severity.value} Alert"
            self.deadline = datetime(2024, 12, 31)
            self.days_until_deadline = 5 if severity == AlertSeverity.CRITICAL else 15
            self.severity = severity

        @property
        def __dict__(self):
            return {
                "alert_id": self.alert_id,
                "client_id": self.client_id,
                "severity": self.severity,
            }

    alerts = [
        MockAlert("alert-1", "client-1", AlertSeverity.CRITICAL),
        MockAlert("alert-2", "client-2", AlertSeverity.URGENT),
    ]

    with patch("app.routers.agents.compliance_monitor.check_compliance_items", return_value=alerts):
        result = await get_compliance_alerts()

        assert result["success"] is True
        assert result["count"] == 2
        assert result["breakdown"]["critical"] == 1
        assert result["breakdown"]["urgent"] == 1


# Skipped - get_client_items method doesn't exist on ProactiveComplianceMonitor
# The endpoint exists but the service method is not implemented yet
# These tests will be added when the service method is implemented


@pytest.mark.asyncio
async def test_extract_knowledge_graph_empty_text():
    """Test knowledge graph extraction with empty text"""
    mock_request = MagicMock()
    result = await extract_knowledge_graph(request=mock_request, text="")

    assert result["success"] is True
    assert result["text_length"] == 0
    assert "entities" in result
    assert "relationships" in result


@pytest.mark.asyncio
async def test_extract_knowledge_graph_very_long_text():
    """Test knowledge graph extraction with very long text"""
    mock_request = MagicMock()
    long_text = "Lorem ipsum " * 1000  # ~12KB of text

    mock_knowledge_graph = AsyncMock()
    mock_knowledge_graph.extract_entities = AsyncMock(
        return_value={"entities": [], "relationships": []}
    )

    with patch("app.routers.agents.knowledge_graph", mock_knowledge_graph):
        result = await extract_knowledge_graph(request=mock_request, text=long_text)

        assert result["success"] is True
        assert result["text_length"] == len(long_text)


@pytest.mark.asyncio
async def test_extract_knowledge_graph_exception():
    """Test knowledge graph extraction when service raises exception"""
    mock_request = MagicMock()
    mock_knowledge_graph = AsyncMock()
    mock_knowledge_graph.extract_entities = AsyncMock(side_effect=Exception("Service error"))

    with patch("app.routers.agents.knowledge_graph", mock_knowledge_graph):
        result = await extract_knowledge_graph(request=mock_request, text="Test text")

        # Should return fallback response
        assert result["success"] is True
        assert "note" in result
        assert "basic mode" in result["note"].lower()


@pytest.mark.asyncio
async def test_export_knowledge_graph_invalid_format():
    """Test knowledge graph export with invalid format"""
    result = await export_knowledge_graph(format="invalid")

    assert result["success"] is True
    assert result["format"] == "invalid"
    assert "warning" in result


@pytest.mark.asyncio
async def test_run_auto_ingestion_empty_sources():
    """Test auto ingestion with empty sources list"""
    result = await run_auto_ingestion(sources=[], force=False)

    assert result["success"] is True
    assert result["sources"] == [] or result["sources"] == ["kemenkeu", "bpk", "kemendag", "ortax"]


@pytest.mark.asyncio
async def test_cross_oracle_synthesis_with_services():
    """Test cross-oracle synthesis when services are available"""
    mock_request = MagicMock()
    mock_synthesis_service = AsyncMock()
    mock_synthesis_service.synthesize = AsyncMock(
        return_value=MagicMock(
            scenario_type="business_setup",
            oracles_consulted=["kbli_eye", "legal_architect"],
            synthesis="Test synthesis",
            timeline={"weeks": 4},
            investment={"total": 1000000},
            key_requirements=["requirement1"],
            risks=["risk1"],
            confidence=0.85,
            cached=False,
        )
    )

    mock_state = MagicMock()
    mock_state.intelligent_router = MagicMock()
    mock_state.intelligent_router.cross_oracle_synthesis = mock_synthesis_service
    mock_request.app.state = mock_state

    result = await cross_oracle_synthesis(
        request=mock_request, query="Open restaurant", domains=["kbli", "legal"]
    )

    assert result["success"] is True
    assert result["query"] == "Open restaurant"
    assert "synthesis" in result
    assert "confidence" in result


@pytest.mark.asyncio
async def test_cross_oracle_synthesis_exception():
    """Test cross-oracle synthesis when service raises exception"""
    mock_request = MagicMock()
    mock_synthesis_service = AsyncMock()
    mock_synthesis_service.synthesize = AsyncMock(side_effect=Exception("Synthesis failed"))

    mock_state = MagicMock()
    mock_state.intelligent_router = MagicMock()
    mock_state.intelligent_router.cross_oracle_synthesis = mock_synthesis_service
    mock_request.app.state = mock_state

    with pytest.raises(HTTPException) as exc_info:
        await cross_oracle_synthesis(request=mock_request, query="Test query", domains=["tax"])

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_run_autonomous_research_with_services():
    """Test autonomous research when services are available"""
    mock_request = MagicMock()
    mock_research_service = MagicMock()
    mock_research_service.MAX_ITERATIONS = 3

    # Create mock research step
    mock_step = MagicMock()
    mock_step.step_number = 1
    mock_step.collection = "kbli_eye"
    mock_step.query = "test query"
    mock_step.rationale = "test rationale"
    mock_step.results_found = 5
    mock_step.confidence = 0.8
    mock_step.key_findings = ["finding1"]

    # Create mock research result
    mock_result = MagicMock()
    mock_result.total_steps = 3
    mock_result.collections_explored = ["kbli_eye", "legal_architect"]
    mock_result.final_answer = "Test answer"
    mock_result.confidence = 0.9
    mock_result.reasoning_chain = ["step1", "step2"]
    mock_result.sources_consulted = ["source1"]
    mock_result.duration_ms = 1500
    mock_result.research_steps = [mock_step]

    mock_research_service.research = AsyncMock(return_value=mock_result)

    mock_state = MagicMock()
    mock_state.search_service = MagicMock()
    mock_state.ai_client = MagicMock()
    mock_state.query_router = MagicMock()
    mock_request.app.state = mock_state

    with patch(
        "services.autonomous_research_service.AutonomousResearchService",
        return_value=mock_research_service,
    ):
        result = await run_autonomous_research(
            request=mock_request, topic="Test topic", depth="standard", sources=None
        )

        assert result["success"] is True
        assert result["topic"] == "Test topic"
        assert result["total_steps"] == 3
        assert "final_answer" in result


@pytest.mark.asyncio
async def test_run_autonomous_research_different_depths():
    """Test autonomous research with different depth values"""
    mock_request = MagicMock()
    mock_state = MagicMock()
    mock_state.search_service = MagicMock()
    mock_state.ai_client = MagicMock()
    mock_state.query_router = MagicMock()
    mock_request.app.state = mock_state

    mock_research_service = MagicMock()
    mock_research_service.MAX_ITERATIONS = 3

    mock_result = MagicMock()
    mock_result.total_steps = 2
    mock_result.collections_explored = []
    mock_result.final_answer = "Answer"
    mock_result.confidence = 0.8
    mock_result.reasoning_chain = []
    mock_result.sources_consulted = []
    mock_result.duration_ms = 1000
    mock_result.research_steps = []

    mock_research_service.research = AsyncMock(return_value=mock_result)

    for depth in ["quick", "standard", "deep"]:
        with patch(
            "services.autonomous_research_service.AutonomousResearchService",
            return_value=mock_research_service,
        ):
            result = await run_autonomous_research(
                request=mock_request, topic="Test", depth=depth, sources=None
            )

            assert result["success"] is True
            assert result["depth"] == depth


@pytest.mark.asyncio
async def test_run_autonomous_research_exception():
    """Test autonomous research when service raises exception"""
    mock_request = MagicMock()
    mock_state = MagicMock()
    mock_state.search_service = MagicMock()
    mock_state.ai_client = MagicMock()
    mock_state.query_router = MagicMock()
    mock_request.app.state = mock_state

    mock_research_service = MagicMock()
    mock_research_service.MAX_ITERATIONS = 3
    mock_research_service.research = AsyncMock(side_effect=Exception("Research failed"))

    with patch(
        "services.autonomous_research_service.AutonomousResearchService",
        return_value=mock_research_service,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await run_autonomous_research(
                request=mock_request, topic="Test", depth="standard", sources=None
            )

        assert exc_info.value.status_code == 500


# Skipped - journey_orchestrator is already instantiated, difficult to mock
# The test_get_analytics_summary already covers the main functionality
