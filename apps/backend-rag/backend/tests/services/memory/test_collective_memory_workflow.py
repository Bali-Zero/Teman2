"""
Tests for collective_memory_workflow.py

Covers: extract_person_names, detect_conflicts, extract_preferences,
assess_personal_importance, extract_entities_and_relationships,
check_existing_memories, LangGraph node functions, routing logic.
"""

import pytest

from backend.services.memory.collective_memory_workflow import (
    CollectiveMemoryState,
    MemoryCategory,
    analyze_content_intent,
    assess_personal_importance,
    check_existing_memories,
    consolidate_with_existing,
    create_collective_memory_workflow,
    detect_conflicts,
    extract_entities_and_relationships,
    extract_person_names,
    extract_preferences,
    merge_memories,
    route_by_existence,
    route_by_importance,
    update_member_profiles,
    update_team_relationships,
)


# ── Helpers ──────────────────────────────────────────────────────

def _make_state(**overrides) -> CollectiveMemoryState:
    """Create a minimal valid CollectiveMemoryState for testing."""
    base: CollectiveMemoryState = {
        "query": "",
        "user_id": "test@example.com",
        "session_id": "sess-001",
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
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════
# extract_person_names
# ═══════════════════════════════════════════════════════════════


class TestExtractPersonNames:
    def test_indonesian_balinese_names(self) -> None:
        names = extract_person_names("Wayan e Ketut sono andati al mercato")
        assert "Wayan" in names
        assert "Ketut" in names

    def test_indonesian_common_names(self) -> None:
        names = extract_person_names("Sari e Dewi lavorano insieme, Budi è il manager")
        assert "Sari" in names
        assert "Dewi" in names
        assert "Budi" in names

    def test_italian_names(self) -> None:
        names = extract_person_names("Ho parlato con Antonello e Francesca")
        assert "Antonello" in names
        assert "Francesca" in names

    def test_international_names(self) -> None:
        names = extract_person_names("David met Sarah at the conference")
        assert "David" in names
        assert "Sarah" in names

    def test_title_honorific_indonesian(self) -> None:
        names = extract_person_names("Pak Agung ci ha contattato")
        assert "Agung" in names

    def test_title_honorific_italian(self) -> None:
        names = extract_person_names("Il Sig. Rossi ha confermato")
        assert "Rossi" in names

    def test_empty_string(self) -> None:
        assert extract_person_names("") == []

    def test_no_names(self) -> None:
        names = extract_person_names("The weather is nice today")
        assert len(names) == 0

    def test_deduplication(self) -> None:
        names = extract_person_names("Wayan ha detto che wayan arriverà domani")
        assert names.count("Wayan") == 1

    def test_mixed_cultures(self) -> None:
        names = extract_person_names("Antonello, Wayan e David si incontrano a Bali")
        assert len(names) >= 3
        assert "Antonello" in names
        assert "Wayan" in names
        assert "David" in names


# ═══════════════════════════════════════════════════════════════
# detect_conflicts
# ═══════════════════════════════════════════════════════════════


class TestDetectConflicts:
    def test_no_conflicts_empty(self) -> None:
        assert detect_conflicts([], "new content") == []

    def test_no_conflicts_empty_new(self) -> None:
        assert detect_conflicts([{"content": "old"}], "") == []

    def test_key_overlap_conflict(self) -> None:
        existing = [{"content": "Likes espresso coffee in the morning", "memory_key": "drink"}]
        conflicts = detect_conflicts(existing, "Prefers americano coffee at lunch")
        assert len(conflicts) >= 1
        assert "drink" in conflicts[0].lower() or "Key" in conflicts[0]

    def test_negation_italian(self) -> None:
        existing = [{"content": "Mi piace il sushi"}]
        conflicts = detect_conflicts(existing, "Non mi piace il sushi adesso")
        assert len(conflicts) >= 1
        assert "Contradiction" in conflicts[0] or "negation" in conflicts[0].lower()

    def test_negation_english(self) -> None:
        existing = [{"content": "She loves working late"}]
        conflicts = detect_conflicts(existing, "She hates working late now")
        assert len(conflicts) >= 1

    def test_negation_indonesian(self) -> None:
        existing = [{"content": "Dia suka makan pedas"}]
        conflicts = detect_conflicts(existing, "Dia tidak suka makan pedas")
        assert len(conflicts) >= 1

    def test_no_conflict_unrelated(self) -> None:
        existing = [{"content": "Il progetto è in fase 2"}]
        conflicts = detect_conflicts(existing, "La riunione è domani alle 10")
        assert len(conflicts) == 0


# ═══════════════════════════════════════════════════════════════
# extract_preferences
# ═══════════════════════════════════════════════════════════════


class TestExtractPreferences:
    def test_drink_preference(self) -> None:
        prefs = extract_preferences("Preferisco il cappuccino al mattino")
        assert prefs.get("drink") == "cappuccino"

    def test_food_preference(self) -> None:
        prefs = extract_preferences("I love sushi, it's my favorite")
        assert prefs.get("food") == "sushi"

    def test_communication_email(self) -> None:
        prefs = extract_preferences("I prefer email for all communications")
        assert prefs.get("communication") == "email"

    def test_communication_whatsapp(self) -> None:
        prefs = extract_preferences("Preferisco WhatsApp per comunicare")
        assert prefs.get("communication") == "whatsapp"

    def test_work_hours_morning(self) -> None:
        prefs = extract_preferences("Mi piace lavorare la mattina presto")
        assert prefs.get("work_hours") == "morning"

    def test_work_hours_flexible(self) -> None:
        prefs = extract_preferences("I prefer flexible working hours")
        assert prefs.get("work_hours") == "flexible"

    def test_language_preference(self) -> None:
        prefs = extract_preferences("Preferisco comunicare in italiano")
        assert prefs.get("language") == "italian"

    def test_meeting_format_informal(self) -> None:
        prefs = extract_preferences("Preferisco riunioni informali")
        assert prefs.get("meeting_format") == "informal"

    def test_meeting_format_formal(self) -> None:
        prefs = extract_preferences("Mi piace un approccio formale")
        assert prefs.get("meeting_format") == "formal"

    def test_indonesian_preferences(self) -> None:
        prefs = extract_preferences("Saya lebih suka kopi di pagi hari")
        assert prefs.get("drink") == "coffee"
        assert prefs.get("work_hours") == "morning"

    def test_no_preference_trigger(self) -> None:
        prefs = extract_preferences("The weather is nice today in Bali")
        assert prefs == {}

    def test_empty_input(self) -> None:
        assert extract_preferences("") == {}

    def test_multiple_preferences(self) -> None:
        prefs = extract_preferences("I prefer email in the morning and love sushi")
        assert "communication" in prefs or "food" in prefs
        assert len(prefs) >= 1


# ═══════════════════════════════════════════════════════════════
# assess_personal_importance (LangGraph node)
# ═══════════════════════════════════════════════════════════════


class TestAssessPersonalImportance:
    @pytest.mark.asyncio
    async def test_milestone_high_importance(self) -> None:
        state = _make_state(
            query="È il compleanno di Wayan",
            detected_category=MemoryCategory.MILESTONE,
            participants=["Wayan"],
        )
        result = await assess_personal_importance(state)
        assert result["importance_score"] >= 0.85

    @pytest.mark.asyncio
    async def test_relationship_importance(self) -> None:
        state = _make_state(
            query="Antonello conosce Maria",
            detected_category=MemoryCategory.RELATIONSHIP,
            participants=["Antonello", "Maria"],
        )
        result = await assess_personal_importance(state)
        assert result["importance_score"] >= 0.75
        # 2 participants should boost personal importance
        assert result["personal_importance"] > result["importance_score"]

    @pytest.mark.asyncio
    async def test_participant_boost(self) -> None:
        state_one = _make_state(
            detected_category=MemoryCategory.WORK,
            participants=["Alice"],
        )
        state_many = _make_state(
            detected_category=MemoryCategory.WORK,
            participants=["Alice", "Bob", "Charlie"],
        )
        result_one = await assess_personal_importance(state_one)
        result_many = await assess_personal_importance(state_many)
        assert result_many["importance_score"] > result_one["importance_score"]

    @pytest.mark.asyncio
    async def test_conflict_boost(self) -> None:
        state = _make_state(
            detected_category=MemoryCategory.WORK,
            participants=["Alice"],
            consolidation_actions=["Conflict detected"],
        )
        result = await assess_personal_importance(state)
        assert result["importance_score"] >= 0.6  # base 0.5 + conflict 0.1

    @pytest.mark.asyncio
    async def test_importance_capped_at_one(self) -> None:
        state = _make_state(
            query="x" * 600,
            detected_category=MemoryCategory.MILESTONE,
            participants=["A", "B", "C", "D"],
            consolidation_actions=["conflict"],
        )
        result = await assess_personal_importance(state)
        assert result["importance_score"] <= 1.0
        assert result["personal_importance"] <= 1.0


# ═══════════════════════════════════════════════════════════════
# extract_entities_and_relationships (LangGraph node)
# ═══════════════════════════════════════════════════════════════


class TestExtractEntitiesAndRelationships:
    @pytest.mark.asyncio
    async def test_extracts_person_entities(self) -> None:
        state = _make_state(query="Wayan e David si incontrano a Seminyak")
        result = await extract_entities_and_relationships(state)
        person_names = [e["name"] for e in result["extracted_entities"] if e["type"] == "person"]
        assert "Wayan" in person_names
        assert "David" in person_names

    @pytest.mark.asyncio
    async def test_extracts_locations(self) -> None:
        state = _make_state(query="Meeting in Seminyak with the team")
        result = await extract_entities_and_relationships(state)
        locations = [e["name"] for e in result["extracted_entities"] if e["type"] == "location"]
        assert "Seminyak" in locations

    @pytest.mark.asyncio
    async def test_extracts_organizations(self) -> None:
        state = _make_state(query="Working with Sunrise Corp and Global Ltd")
        result = await extract_entities_and_relationships(state)
        orgs = [e["name"] for e in result["extracted_entities"] if e["type"] == "organization"]
        assert any("Corp" in o or "Ltd" in o for o in orgs)

    @pytest.mark.asyncio
    async def test_co_mention_relationships(self) -> None:
        state = _make_state(query="Wayan and David discussed the contract")
        result = await extract_entities_and_relationships(state)
        assert len(result["new_relationships"]) >= 1
        rel = result["new_relationships"][0]
        assert rel["relationship_type"] == "co_mentioned"

    @pytest.mark.asyncio
    async def test_fallback_to_user_id(self) -> None:
        state = _make_state(query="No names here", user_id="test@balizero.com")
        result = await extract_entities_and_relationships(state)
        assert "test@balizero.com" in result["participants"]


# ═══════════════════════════════════════════════════════════════
# check_existing_memories
# ═══════════════════════════════════════════════════════════════


class TestCheckExistingMemories:
    @pytest.mark.asyncio
    async def test_no_service(self) -> None:
        state = _make_state(query="Some query")
        result = await check_existing_memories(state, None)
        assert result["existing_memories"] == []
        assert result["needs_consolidation"] is False

    @pytest.mark.asyncio
    async def test_with_mock_service(self) -> None:
        """Mock memory service returning similar facts."""

        class MockMemoryService:
            async def search(self, query: str, limit: int = 5) -> list[dict]:
                if "coffee" in query.lower():
                    return [{"fact": "User likes espresso", "user_id": "test", "confidence": 0.8}]
                return []

            async def get_memory(self, user_id: str, force_refresh: bool = False):
                return None  # No user memory

        state = _make_state(query="I drink coffee every morning", user_id="test")
        result = await check_existing_memories(state, MockMemoryService())
        assert len(result["existing_memories"]) >= 1
        assert result["needs_consolidation"] is True


# ═══════════════════════════════════════════════════════════════
# analyze_content_intent (LangGraph node)
# ═══════════════════════════════════════════════════════════════


class TestAnalyzeContentIntent:
    @pytest.mark.asyncio
    async def test_preference_detected(self) -> None:
        state = _make_state(query="Preferisco il caffè espresso al mattino")
        result = await analyze_content_intent(state)
        assert result["detected_category"] == MemoryCategory.PREFERENCE
        assert result["detected_type"] == "preference"

    @pytest.mark.asyncio
    async def test_milestone_detected(self) -> None:
        state = _make_state(query="Oggi è il compleanno di Marco")
        result = await analyze_content_intent(state)
        assert result["detected_category"] == MemoryCategory.MILESTONE

    @pytest.mark.asyncio
    async def test_relationship_detected(self) -> None:
        state = _make_state(query="Ho incontrato un vecchio amico ieri")
        result = await analyze_content_intent(state)
        assert result["detected_category"] == MemoryCategory.RELATIONSHIP

    @pytest.mark.asyncio
    async def test_cultural_detected(self) -> None:
        state = _make_state(query="La tradizione locale prevede una cerimonia")
        result = await analyze_content_intent(state)
        assert result["detected_category"] == MemoryCategory.CULTURAL

    @pytest.mark.asyncio
    async def test_work_default(self) -> None:
        state = _make_state(query="Dobbiamo finire il report entro venerdì")
        result = await analyze_content_intent(state)
        assert result["detected_category"] == MemoryCategory.WORK


# ═══════════════════════════════════════════════════════════════
# merge_memories & consolidation
# ═══════════════════════════════════════════════════════════════


class TestMergeMemories:
    def test_merge_with_empty_existing(self) -> None:
        result = merge_memories([], "New memory content")
        assert result["content"] == "New memory content"
        assert "updated" not in result

    def test_merge_with_existing(self) -> None:
        existing = [{"content": "Old fact", "memory_key": "key1"}]
        result = merge_memories(existing, "New fact")
        assert "Old fact" in result["content"]
        assert "New fact" in result["content"]
        assert result["updated"] is True
        assert result["memory_key"] == "key1"


class TestConsolidateWithExisting:
    @pytest.mark.asyncio
    async def test_new_memory_no_existing(self) -> None:
        state = _make_state(
            query="Brand new information",
            existing_memories=[],
            consolidation_actions=[],
        )
        result = await consolidate_with_existing(state)
        assert result["memory_to_store"]["content"] == "Brand new information"

    @pytest.mark.asyncio
    async def test_consolidate_with_existing(self) -> None:
        state = _make_state(
            query="Updated preference",
            existing_memories=[{"content": "Old preference", "memory_key": "pref"}],
            consolidation_actions=[],
        )
        result = await consolidate_with_existing(state)
        assert "Old preference" in result["memory_to_store"]["content"]
        assert "Updated preference" in result["memory_to_store"]["content"]


# ═══════════════════════════════════════════════════════════════
# Routing functions
# ═══════════════════════════════════════════════════════════════


class TestRouting:
    def test_route_by_existence_new(self) -> None:
        state = _make_state(needs_consolidation=False, existing_memories=[])
        assert route_by_existence(state) == "new"

    def test_route_by_existence_exists(self) -> None:
        state = _make_state(
            needs_consolidation=False,
            existing_memories=[{"content": "something"}],
        )
        assert route_by_existence(state) == "exists"

    def test_route_by_existence_consolidate(self) -> None:
        state = _make_state(needs_consolidation=True)
        assert route_by_existence(state) == "consolidate"

    def test_route_by_importance_high(self) -> None:
        state = _make_state(personal_importance=0.9)
        assert route_by_importance(state) == "high"

    def test_route_by_importance_medium(self) -> None:
        state = _make_state(personal_importance=0.7)
        assert route_by_importance(state) == "medium"

    def test_route_by_importance_low(self) -> None:
        state = _make_state(personal_importance=0.4)
        assert route_by_importance(state) == "low"


# ═══════════════════════════════════════════════════════════════
# update_team_relationships
# ═══════════════════════════════════════════════════════════════


class TestUpdateTeamRelationships:
    @pytest.mark.asyncio
    async def test_creates_relationships(self) -> None:
        state = _make_state(
            query="Wayan e David sono amici",
            detected_category=MemoryCategory.RELATIONSHIP,
            participants=["Wayan", "David"],
            relationships_to_update=[],
        )
        result = await update_team_relationships(state)
        assert len(result["relationships_to_update"]) == 1
        rel = result["relationships_to_update"][0]
        assert rel["member_a"] == "Wayan"
        assert rel["member_b"] == "David"
        assert rel["relationship_type"] == "friendship"

    @pytest.mark.asyncio
    async def test_no_relationships_single_participant(self) -> None:
        state = _make_state(
            detected_category=MemoryCategory.RELATIONSHIP,
            participants=["Solo"],
            relationships_to_update=[],
        )
        result = await update_team_relationships(state)
        assert len(result["relationships_to_update"]) == 0


# ═══════════════════════════════════════════════════════════════
# update_member_profiles
# ═══════════════════════════════════════════════════════════════


class TestUpdateMemberProfiles:
    @pytest.mark.asyncio
    async def test_preference_profile_update(self) -> None:
        state = _make_state(
            query="Preferisco il cappuccino",
            detected_category=MemoryCategory.PREFERENCE,
            participants=["Antonello"],
            profile_updates=[],
        )
        result = await update_member_profiles(state)
        assert len(result["profile_updates"]) == 1
        update = result["profile_updates"][0]
        assert update["member_id"] == "Antonello"
        assert "drink" in update["preferences"]

    @pytest.mark.asyncio
    async def test_no_update_for_work(self) -> None:
        state = _make_state(
            query="Finish the report",
            detected_category=MemoryCategory.WORK,
            participants=["Bob"],
            profile_updates=[],
        )
        result = await update_member_profiles(state)
        assert len(result["profile_updates"]) == 0


# ═══════════════════════════════════════════════════════════════
# Workflow compilation
# ═══════════════════════════════════════════════════════════════


class TestWorkflowCompilation:
    def test_workflow_compiles(self) -> None:
        workflow = create_collective_memory_workflow()
        assert workflow is not None

    def test_workflow_with_services(self) -> None:
        class MockService:
            pass

        workflow = create_collective_memory_workflow(
            memory_service=MockService(),
            _mcp_client=MockService(),
        )
        assert workflow is not None
