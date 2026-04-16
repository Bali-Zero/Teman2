"""
Test — Topic Selector.

Tests topic creation from CLI, escalations, and MOS.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mata_garuda.council.topics import TopicSelector, _infer_category


class TestTopicFromCLI:
    """Test manual topic creation."""

    def test_creates_topic_with_fields(self):
        sel = TopicSelector()
        topic = sel.from_cli("Test Title", "Test description", "architecture")
        assert topic.title == "Test Title"
        assert topic.description == "Test description"
        assert topic.category == "architecture"
        assert topic.source == "cli"
        assert len(topic.id) == 12

    def test_default_category_operational(self):
        sel = TopicSelector()
        topic = sel.from_cli("Title", "Desc")
        assert topic.category == "operational"


class TestTopicFromEscalations:
    """Test escalation file reading."""

    def test_reads_pending_escalations(self):
        data = [
            {"title": "Fix auth", "description": "Auth is broken", "status": "pending"},
            {"title": "Done", "description": "Already fixed", "status": "resolved"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)

        sel = TopicSelector(escalations_path=path)
        topics = sel.from_escalations_file()
        path.unlink()

        assert len(topics) == 1
        assert topics[0].title == "Fix auth"

    def test_missing_file_returns_empty(self):
        sel = TopicSelector(escalations_path=Path("/nonexistent.json"))
        topics = sel.from_escalations_file()
        assert topics == []

    def test_dict_format_escalations(self):
        data = {"pending": [
            {"title": "Upgrade DB", "description": "Need migration", "status": "pending"},
        ]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)

        sel = TopicSelector(escalations_path=path)
        topics = sel.from_escalations_file()
        path.unlink()

        assert len(topics) == 1


class TestInferCategory:
    """Test category inference from escalation metadata."""

    def test_architecture_detected(self):
        assert _infer_category({"title": "Refactor database architecture"}) == "architecture"

    def test_strategic_detected(self):
        assert _infer_category({"title": "Revenue optimization strategy"}) == "strategic"

    def test_escalation_detected(self):
        assert _infer_category({"title": "Critical blocker in production"}) == "escalation"

    def test_default_operational(self):
        assert _infer_category({"title": "Update readme file"}) == "operational"


class TestAutoSelect:
    """Test auto-selection of highest-priority topic."""

    def test_escalations_prioritized(self):
        data = [{"title": "Urgent fix", "description": "broken", "status": "pending"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)

        sel = TopicSelector(escalations_path=path)
        with patch.object(sel, "from_mos_unresolved", return_value=[]):
            topic = sel.auto_select()

        path.unlink()
        assert topic is not None
        assert topic.title == "Urgent fix"

    def test_no_candidates_returns_none(self):
        sel = TopicSelector(escalations_path=Path("/nonexistent.json"))
        with patch.object(sel, "from_mos_unresolved", return_value=[]):
            topic = sel.auto_select()
        assert topic is None
