"""
Unit tests for Collective Memory Workflow
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.collective_memory_workflow import (
    MemoryCategory,
    analyze_content_intent,
    assess_personal_importance,
    categorize_memory,
    check_existing_memories,
    consolidate_with_existing,
    detect_conflicts,
    extract_entities_and_relationships,
    extract_person_names,
    extract_preferences,
    merge_memories,
    store_collective_memory,
    update_member_profiles,
    update_team_relationships,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def base_state():
    """Base state for workflow"""
    return {
        "query": "Test query",
        "user_id": "user-123",
        "session_id": "session-123",
        "participants": [],
        "detected_category": None,
        "detected_type": None,
        "extracted_entities": [],
        "sentiment": None,
        "importance_score": 0.0,
        "personal_importance": 0.0,
        "existing_memories": [],
        "needs_consolidation": False,
        "consolidation_actions": [],
        "relationships_to_update": [],
        "new_relationships": [],
        "memory_to_store": None,
        "relationships_to_store": [],
        "profile_updates": [],
        "confidence": 0.0,
        "errors": [],
    }


@pytest.fixture
def mock_memory_service():
    """Mock memory service"""
    service = AsyncMock()
    service.add_fact = AsyncMock(return_value=True)
    return service


# ============================================================================
# Tests for extract_person_names
# ============================================================================


def test_extract_person_names_found():
    """Test extract_person_names finds names"""
    text = "I met antonello and maria yesterday"
    names = extract_person_names(text)

    assert len(names) > 0
    assert "antonello" in names or "maria" in names


def test_extract_person_names_not_found():
    """Test extract_person_names with no names"""
    text = "This is a test without names"
    names = extract_person_names(text)

    assert isinstance(names, list)


# ============================================================================
# Tests for merge_memories
# ============================================================================


def test_merge_memories_with_existing():
    """Test merge_memories with existing memories"""
    existing = [{"content": "Old memory", "memory_key": "key1"}]
    new_content = "New memory"

    result = merge_memories(existing, new_content)

    assert result["content"] is not None
    assert "New memory" in result["content"]
    assert result["updated"] is True


def test_merge_memories_no_existing():
    """Test merge_memories without existing memories"""
    existing = []
    new_content = "New memory"

    result = merge_memories(existing, new_content)

    assert result["content"] == "New memory"


# ============================================================================
# Tests for detect_conflicts
# ============================================================================


def test_detect_conflicts():
    """Test detect_conflicts"""
    existing = [{"content": "Old memory"}]
    new_content = "New memory"

    conflicts = detect_conflicts(existing, new_content)

    assert isinstance(conflicts, list)


# ============================================================================
# Tests for extract_preferences
# ============================================================================


def test_extract_preferences_espresso():
    """Test extract_preferences finds espresso"""
    text = "Preferisco espresso"
    prefs = extract_preferences(text)

    assert "coffee" in prefs
    assert prefs["coffee"] == "espresso"


def test_extract_preferences_americano():
    """Test extract_preferences finds americano"""
    text = "Preferisco americano"
    prefs = extract_preferences(text)

    assert "coffee" in prefs
    assert prefs["coffee"] == "americano"


def test_extract_preferences_no_match():
    """Test extract_preferences with no match"""
    text = "This is a test"
    prefs = extract_preferences(text)

    assert isinstance(prefs, dict)


# ============================================================================
# Tests for analyze_content_intent
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_content_intent_preference(base_state):
    """Test analyze_content_intent detects preference"""
    base_state["query"] = "Preferisco il caffè espresso"
    result = await analyze_content_intent(base_state)

    assert result["detected_category"] == MemoryCategory.PREFERENCE
    assert result["detected_type"] == "preference"


@pytest.mark.asyncio
async def test_analyze_content_intent_milestone(base_state):
    """Test analyze_content_intent detects milestone"""
    base_state["query"] = "È il mio compleanno"
    result = await analyze_content_intent(base_state)

    assert result["detected_category"] == MemoryCategory.MILESTONE
    assert result["detected_type"] == "milestone"


@pytest.mark.asyncio
async def test_analyze_content_intent_relationship(base_state):
    """Test analyze_content_intent detects relationship"""
    base_state["query"] = "Ho incontrato un amico"
    result = await analyze_content_intent(base_state)

    assert result["detected_category"] == MemoryCategory.RELATIONSHIP


@pytest.mark.asyncio
async def test_analyze_content_intent_cultural(base_state):
    """Test analyze_content_intent detects cultural"""
    base_state["query"] = "Tradizione locale"
    result = await analyze_content_intent(base_state)

    assert result["detected_category"] == MemoryCategory.CULTURAL


@pytest.mark.asyncio
async def test_analyze_content_intent_work(base_state):
    """Test analyze_content_intent defaults to work"""
    base_state["query"] = "Meeting di lavoro"
    result = await analyze_content_intent(base_state)

    assert result["detected_category"] == MemoryCategory.WORK


# ============================================================================
# Tests for extract_entities_and_relationships
# ============================================================================


@pytest.mark.asyncio
async def test_extract_entities_and_relationships(base_state):
    """Test extract_entities_and_relationships"""
    base_state["query"] = "I met antonello"
    result = await extract_entities_and_relationships(base_state)

    assert len(result["participants"]) > 0


@pytest.mark.asyncio
async def test_extract_entities_and_relationships_no_names(base_state):
    """Test extract_entities_and_relationships with no names"""
    base_state["query"] = "This is a test"
    result = await extract_entities_and_relationships(base_state)

    assert isinstance(result["participants"], list)


# ============================================================================
# Tests for check_existing_memories
# ============================================================================


@pytest.mark.asyncio
async def test_check_existing_memories(base_state, mock_memory_service):
    """Test check_existing_memories"""
    result = await check_existing_memories(base_state, mock_memory_service)

    assert isinstance(result["existing_memories"], list)
    assert isinstance(result["needs_consolidation"], bool)


# ============================================================================
# Tests for categorize_memory
# ============================================================================


@pytest.mark.asyncio
async def test_categorize_memory(base_state):
    """Test categorize_memory"""
    result = await categorize_memory(base_state)

    assert result == base_state


# ============================================================================
# Tests for assess_personal_importance
# ============================================================================


@pytest.mark.asyncio
async def test_assess_personal_importance_milestone(base_state):
    """Test assess_personal_importance for milestone"""
    base_state["detected_category"] = MemoryCategory.MILESTONE
    base_state["participants"] = ["user1"]
    result = await assess_personal_importance(base_state)

    assert result["importance_score"] > 0.0
    assert result["personal_importance"] > result["importance_score"]


@pytest.mark.asyncio
async def test_assess_personal_importance_relationship(base_state):
    """Test assess_personal_importance for relationship"""
    base_state["detected_category"] = MemoryCategory.RELATIONSHIP
    base_state["participants"] = ["user1"]
    result = await assess_personal_importance(base_state)

    assert result["importance_score"] > 0.0


@pytest.mark.asyncio
async def test_assess_personal_importance_preference(base_state):
    """Test assess_personal_importance for preference"""
    base_state["detected_category"] = MemoryCategory.PREFERENCE
    base_state["participants"] = ["user1"]
    result = await assess_personal_importance(base_state)

    assert result["importance_score"] > 0.0


@pytest.mark.asyncio
async def test_assess_personal_importance_work(base_state):
    """Test assess_personal_importance for work"""
    base_state["detected_category"] = MemoryCategory.WORK
    base_state["participants"] = ["user1"]
    result = await assess_personal_importance(base_state)

    assert result["importance_score"] >= 0.0


# ============================================================================
# Tests for consolidate_with_existing
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_with_existing(base_state):
    """Test consolidate_with_existing with existing memories"""
    base_state["existing_memories"] = [{"content": "Old memory"}]
    base_state["query"] = "New memory"
    result = await consolidate_with_existing(base_state)

    assert result["memory_to_store"] is not None


@pytest.mark.asyncio
async def test_consolidate_with_existing_no_existing(base_state):
    """Test consolidate_with_existing without existing memories"""
    base_state["existing_memories"] = []
    base_state["query"] = "New memory"
    result = await consolidate_with_existing(base_state)

    assert result["memory_to_store"] is not None
    assert result["memory_to_store"]["content"] == "New memory"


@pytest.mark.asyncio
async def test_consolidate_with_existing_conflicts(base_state):
    """Test consolidate_with_existing with conflicts"""
    base_state["existing_memories"] = [{"content": "Old memory"}]
    base_state["query"] = "New memory"
    # Mock detect_conflicts to return conflicts
    with patch("services.collective_memory_workflow.detect_conflicts", return_value=["Conflict 1"]):
        result = await consolidate_with_existing(base_state)

        assert len(result["consolidation_actions"]) > 0


# ============================================================================
# Tests for update_team_relationships
# ============================================================================


@pytest.mark.asyncio
async def test_update_team_relationships_multiple_participants(base_state):
    """Test update_team_relationships with multiple participants"""
    base_state["participants"] = ["user1", "user2", "user3"]
    base_state["detected_category"] = MemoryCategory.RELATIONSHIP
    result = await update_team_relationships(base_state)

    assert len(result["relationships_to_update"]) > 0


@pytest.mark.asyncio
async def test_update_team_relationships_single_participant(base_state):
    """Test update_team_relationships with single participant"""
    base_state["participants"] = ["user1"]
    base_state["detected_category"] = MemoryCategory.RELATIONSHIP
    result = await update_team_relationships(base_state)

    assert len(result["relationships_to_update"]) == 0


@pytest.mark.asyncio
async def test_update_team_relationships_work_category(base_state):
    """Test update_team_relationships with work category"""
    base_state["participants"] = ["user1", "user2"]
    base_state["detected_category"] = MemoryCategory.WORK
    result = await update_team_relationships(base_state)

    assert len(result["relationships_to_update"]) == 0


@pytest.mark.asyncio
async def test_update_team_relationships_milestone(base_state):
    """Test update_team_relationships with milestone"""
    base_state["participants"] = ["user1", "user2"]
    base_state["detected_category"] = MemoryCategory.MILESTONE
    result = await update_team_relationships(base_state)

    assert len(result["relationships_to_update"]) > 0


# ============================================================================
# Tests for update_member_profiles
# ============================================================================


@pytest.mark.asyncio
async def test_update_member_profiles_preference(base_state):
    """Test update_member_profiles with preference"""
    base_state["detected_category"] = MemoryCategory.PREFERENCE
    base_state["participants"] = ["user1"]
    base_state["query"] = "Preferisco espresso"
    result = await update_member_profiles(base_state)

    assert len(result["profile_updates"]) > 0


@pytest.mark.asyncio
async def test_update_member_profiles_non_preference(base_state):
    """Test update_member_profiles with non-preference"""
    base_state["detected_category"] = MemoryCategory.WORK
    base_state["participants"] = ["user1"]
    result = await update_member_profiles(base_state)

    assert len(result["profile_updates"]) == 0


# ============================================================================
# Tests for store_collective_memory
# ============================================================================


@pytest.mark.asyncio
async def test_store_collective_memory_success(base_state, mock_memory_service):
    """Test store_collective_memory successful"""
    base_state["memory_to_store"] = {"content": "Test memory"}
    base_state["user_id"] = "user-123"
    result = await store_collective_memory(base_state, mock_memory_service)

    assert result["memory_to_store"] is not None
    mock_memory_service.add_fact.assert_called_once()


@pytest.mark.asyncio
async def test_store_collective_memory_no_memory(base_state, mock_memory_service):
    """Test store_collective_memory without memory to store"""
    base_state["memory_to_store"] = None
    result = await store_collective_memory(base_state, mock_memory_service)

    mock_memory_service.add_fact.assert_not_called()


@pytest.mark.asyncio
async def test_store_collective_memory_no_service(base_state):
    """Test store_collective_memory without memory service"""
    base_state["memory_to_store"] = {"content": "Test memory"}
    result = await store_collective_memory(base_state, None)

    assert result["memory_to_store"] is not None


@pytest.mark.asyncio
async def test_store_collective_memory_exception(base_state, mock_memory_service):
    """Test store_collective_memory with exception"""
    base_state["memory_to_store"] = {"content": "Test memory"}
    base_state["user_id"] = "user-123"
    mock_memory_service.add_fact.side_effect = Exception("Storage error")

    result = await store_collective_memory(base_state, mock_memory_service)

    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_store_collective_memory_exception_no_errors_key(mock_memory_service):
    """Test store_collective_memory with exception when errors key doesn't exist"""
    # Create state without errors key to trigger line 262
    state = {
        "memory_to_store": {"content": "Test memory"},
        "user_id": "user-123",
    }
    mock_memory_service.add_fact.side_effect = Exception("Storage error")

    result = await store_collective_memory(state, mock_memory_service)

    assert "errors" in result
    assert len(result["errors"]) > 0


# ============================================================================
# Tests for routing functions
# ============================================================================


def test_route_by_existence_consolidate():
    """Test route_by_existence when consolidation needed"""
    from services.collective_memory_workflow import route_by_existence

    state = {"needs_consolidation": True, "existing_memories": []}
    result = route_by_existence(state)
    assert result == "consolidate"


def test_route_by_existence_exists():
    """Test route_by_existence when memories exist"""
    from services.collective_memory_workflow import route_by_existence

    state = {"needs_consolidation": False, "existing_memories": [{"id": 1}]}
    result = route_by_existence(state)
    assert result == "exists"


def test_route_by_existence_new():
    """Test route_by_existence when no existing memories"""
    from services.collective_memory_workflow import route_by_existence

    state = {"needs_consolidation": False, "existing_memories": []}
    result = route_by_existence(state)
    assert result == "new"


def test_route_by_importance_high():
    """Test route_by_importance for high importance"""
    from services.collective_memory_workflow import route_by_importance

    state = {"personal_importance": 0.9}
    result = route_by_importance(state)
    assert result == "high"


def test_route_by_importance_medium():
    """Test route_by_importance for medium importance"""
    from services.collective_memory_workflow import route_by_importance

    state = {"personal_importance": 0.7}
    result = route_by_importance(state)
    assert result == "medium"


def test_route_by_importance_low():
    """Test route_by_importance for low importance"""
    from services.collective_memory_workflow import route_by_importance

    state = {"personal_importance": 0.5}
    result = route_by_importance(state)
    assert result == "low"


# ============================================================================
# Tests for workflow creation
# ============================================================================


def test_create_collective_memory_workflow():
    """Test create_collective_memory_workflow"""
    from services.collective_memory_workflow import create_collective_memory_workflow

    workflow = create_collective_memory_workflow()
    assert workflow is not None


def test_create_collective_memory_workflow_with_services():
    """Test create_collective_memory_workflow with memory service"""
    from services.collective_memory_workflow import create_collective_memory_workflow

    mock_memory = MagicMock()
    workflow = create_collective_memory_workflow(memory_service=mock_memory)
    assert workflow is not None
