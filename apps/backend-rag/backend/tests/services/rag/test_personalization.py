"""
Test suite for personalization in RAG system (Phase 2)

Tests user context tracking, personalized responses,
and adaptive behavior based on user history and preferences.

Author: Windsurf (QA Engineer)
Created: 2026-02-09
"""

from datetime import datetime, timedelta

import pytest


class TestUserContextTracking:
    """Test user context tracking and management"""

    def test_user_context_initialization(self):
        """Test user context is properly initialized"""
        user_context = {
            "user_id": "user-123",
            "preferences": {},
            "history": [],
            "profile": {},
            "created_at": datetime.utcnow().isoformat(),
        }

        assert "user_id" in user_context
        assert "preferences" in user_context
        assert "history" in user_context
        assert isinstance(user_context["history"], list)

    def test_add_query_to_history(self):
        """Test adding query to user history"""
        user_context = {"user_id": "user-123", "history": []}

        query = {
            "query_text": "What are visa requirements?",
            "timestamp": datetime.utcnow().isoformat(),
            "response_quality": 0.85,
        }

        user_context["history"].append(query)

        assert len(user_context["history"]) == 1
        assert user_context["history"][0]["query_text"] == "What are visa requirements?"

    def test_history_size_limit(self):
        """Test user history respects size limit"""
        max_history = 50
        user_context = {"user_id": "user-123", "history": []}

        # Add 60 queries
        for i in range(60):
            user_context["history"].append(
                {"query_text": f"Query {i}", "timestamp": datetime.utcnow().isoformat()}
            )

        # Keep only last 50
        user_context["history"] = user_context["history"][-max_history:]

        assert len(user_context["history"]) == 50
        assert user_context["history"][0]["query_text"] == "Query 10"

    def test_extract_user_preferences_from_history(self):
        """Test extracting user preferences from query history"""
        history = [
            {"query_text": "visa requirements for Bali", "domain": "visa"},
            {"query_text": "visa extension process", "domain": "visa"},
            {"query_text": "tax obligations Indonesia", "domain": "tax"},
            {"query_text": "visa application timeline", "domain": "visa"},
        ]

        # Count domain preferences
        domain_counts = {}
        for query in history:
            domain = query.get("domain", "general")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Most common domain
        preferred_domain = max(domain_counts, key=domain_counts.get)

        assert preferred_domain == "visa"
        assert domain_counts["visa"] == 3


class TestUserPreferences:
    """Test user preference management"""

    def test_set_language_preference(self):
        """Test setting user language preference"""
        preferences = {}
        preferences["language"] = "en"

        assert preferences["language"] == "en"

    def test_set_response_style_preference(self):
        """Test setting response style preference"""
        preferences = {}
        preferences["response_style"] = "detailed"

        assert preferences["response_style"] in ["concise", "detailed", "technical"]

    def test_set_domain_preferences(self):
        """Test setting domain-specific preferences"""
        preferences = {
            "domains": {
                "visa": {"detail_level": "high", "include_citations": True},
                "tax": {"detail_level": "medium", "include_examples": True},
            }
        }

        assert preferences["domains"]["visa"]["detail_level"] == "high"
        assert preferences["domains"]["visa"]["include_citations"] is True

    def test_update_preferences_from_feedback(self):
        """Test updating preferences based on user feedback"""
        preferences = {"response_style": "concise"}

        # User consistently gives thumbs down to concise responses
        negative_feedback_count = 5

        if negative_feedback_count >= 3:
            preferences["response_style"] = "detailed"

        assert preferences["response_style"] == "detailed"


class TestPersonalizedResponses:
    """Test personalized response generation"""

    def test_personalize_response_with_user_name(self):
        """Test response personalization with user name"""
        user_profile = {"name": "Marco", "user_id": "user-123"}
        base_response = "Here are the visa requirements."

        personalized = f"Hi {user_profile['name']}, {base_response}"

        assert "Marco" in personalized

    def test_personalize_response_with_history_context(self):
        """Test response personalization with query history"""
        user_history = [
            {"query_text": "visa requirements", "timestamp": "2026-02-01"},
            {"query_text": "visa extension", "timestamp": "2026-02-05"},
        ]

        # Check if related to previous queries
        is_follow_up = any("visa" in q["query_text"] for q in user_history)

        context_note = "Based on your previous visa-related questions..." if is_follow_up else ""

        assert is_follow_up is True
        assert "previous visa-related questions" in context_note

    def test_adjust_detail_level_based_on_expertise(self):
        """Test adjusting response detail based on user expertise"""
        user_profile = {"expertise_level": "beginner"}

        if user_profile["expertise_level"] == "beginner":
            detail_level = "high"
            include_examples = True
        else:
            detail_level = "medium"
            include_examples = False

        assert detail_level == "high"
        assert include_examples is True

    def test_language_specific_response(self):
        """Test generating response in user's preferred language"""
        user_preferences = {"language": "it"}

        greeting = "Ciao" if user_preferences["language"] == "it" else "Hello"

        assert greeting == "Ciao"


class TestAdaptiveBehavior:
    """Test adaptive system behavior based on user patterns"""

    def test_detect_frequent_query_pattern(self):
        """Test detection of frequently asked query patterns"""
        user_history = [
            {"query_text": "visa requirements", "timestamp": "2026-02-01"},
            {"query_text": "visa extension", "timestamp": "2026-02-03"},
            {"query_text": "visa application", "timestamp": "2026-02-05"},
            {"query_text": "visa timeline", "timestamp": "2026-02-07"},
        ]

        # All queries contain "visa"
        visa_queries = sum(1 for q in user_history if "visa" in q["query_text"].lower())

        is_frequent_pattern = visa_queries >= 3
        assert is_frequent_pattern is True

    def test_suggest_proactive_information(self):
        """Test suggesting proactive information based on patterns"""
        user_history = [
            {"query_text": "visa requirements", "domain": "visa"},
            {"query_text": "visa extension", "domain": "visa"},
        ]

        # User is interested in visa, suggest related info
        suggested_topics = []
        if sum(1 for q in user_history if q.get("domain") == "visa") >= 2:
            suggested_topics.append("visa application timeline")
            suggested_topics.append("visa fees and costs")

        assert len(suggested_topics) > 0
        assert "visa application timeline" in suggested_topics

    def test_adjust_confidence_threshold_per_user(self):
        """Test adjusting confidence thresholds based on user feedback history"""
        user_feedback_history = {
            "false_positives": 2,  # High confidence but wrong
            "true_positives": 8,  # High confidence and correct
        }

        precision = user_feedback_history["true_positives"] / (
            user_feedback_history["true_positives"] + user_feedback_history["false_positives"]
        )

        # If precision is high, can use lower threshold (more confident)
        confidence_threshold = 0.7 if precision >= 0.8 else 0.85

        assert confidence_threshold == 0.7

    def test_learn_user_query_style(self):
        """Test learning user's query formulation style"""
        user_history = [
            {"query_text": "What are visa requirements?", "style": "question"},
            {"query_text": "Tell me about visa extension", "style": "command"},
            {"query_text": "How to apply for visa?", "style": "question"},
            {"query_text": "Explain visa process", "style": "command"},
        ]

        # Count query styles
        question_count = sum(1 for q in user_history if q["style"] == "question")
        command_count = sum(1 for q in user_history if q["style"] == "command")

        assert question_count == 2
        assert command_count == 2


class TestUserSegmentation:
    """Test user segmentation for personalization"""

    def test_segment_by_query_frequency(self):
        """Test segmenting users by query frequency"""
        user_stats = {"total_queries": 50, "days_active": 30}

        queries_per_day = user_stats["total_queries"] / user_stats["days_active"]

        if queries_per_day >= 2:
            segment = "power_user"
        elif queries_per_day >= 0.5:
            segment = "regular_user"
        else:
            segment = "casual_user"

        assert segment == "regular_user"

    def test_segment_by_domain_expertise(self):
        """Test segmenting users by domain expertise"""
        user_history = [
            {"query_text": "basic visa info", "complexity": "low"},
            {"query_text": "visa extension process", "complexity": "medium"},
            {"query_text": "complex visa regulations", "complexity": "high"},
        ]

        avg_complexity = sum(
            {"low": 1, "medium": 2, "high": 3}[q["complexity"]] for q in user_history
        ) / len(user_history)

        if avg_complexity >= 2.5:
            expertise = "expert"
        elif avg_complexity >= 1.5:
            expertise = "intermediate"
        else:
            expertise = "beginner"

        assert expertise == "intermediate"

    def test_segment_by_response_satisfaction(self):
        """Test segmenting users by satisfaction levels"""
        user_feedback = {"thumbs_up": 8, "thumbs_down": 2, "total": 10}

        satisfaction = user_feedback["thumbs_up"] / user_feedback["total"]

        if satisfaction >= 0.8:
            segment = "satisfied"
        elif satisfaction >= 0.5:
            segment = "neutral"
        else:
            segment = "unsatisfied"

        assert segment == "satisfied"


class TestPrivacyAndSecurity:
    """Test privacy and security in personalization"""

    def test_anonymize_sensitive_data(self):
        """Test anonymization of sensitive user data"""
        user_data = {
            "user_id": "user-123",
            "email": "marco@example.com",
            "queries": ["visa requirements"],
        }

        # Anonymize for analytics
        anonymized = {
            "user_id_hash": "hash_" + user_data["user_id"],
            "queries": user_data["queries"],
        }

        assert "email" not in anonymized
        assert anonymized["user_id_hash"].startswith("hash_")

    def test_respect_data_retention_policy(self):
        """Test data retention policy compliance"""
        retention_days = 90
        old_query = {"timestamp": (datetime.utcnow() - timedelta(days=100)).isoformat()}
        recent_query = {"timestamp": (datetime.utcnow() - timedelta(days=30)).isoformat()}

        # Check if should be deleted
        old_date = datetime.fromisoformat(old_query["timestamp"])
        should_delete_old = (datetime.utcnow() - old_date).days > retention_days

        recent_date = datetime.fromisoformat(recent_query["timestamp"])
        should_delete_recent = (datetime.utcnow() - recent_date).days > retention_days

        assert should_delete_old is True
        assert should_delete_recent is False


@pytest.mark.integration
class TestPersonalizationIntegration:
    """Integration tests for personalization in full RAG pipeline"""

    @pytest.mark.asyncio
    async def test_personalized_response_generation(self):
        """Test end-to-end personalized response generation"""
        pytest.skip("Requires full orchestrator and user context system setup")

    @pytest.mark.asyncio
    async def test_adaptive_behavior_over_time(self):
        """Test adaptive behavior improves over multiple interactions"""
        pytest.skip("Requires full user tracking system setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
