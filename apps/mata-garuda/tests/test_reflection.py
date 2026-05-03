"""Tests for reflection engine — JSON-based, not regex."""
import pytest


class TestReflectionPrompt:
    def test_build_reflection_prompt_success(self):
        from mata_garuda.runtime.reflection import build_reflection_prompt

        prompt = build_reflection_prompt(
            agent_name="Regulation Watcher",
            query="check latest regulations",
            outcome_success=True,
            messages_summary="Scraped 10 regs, published to garuda:raw",
            genome_snippet="Primary source: peraturan.go.id",
        )
        assert "Regulation Watcher" in prompt
        assert "SUCCESS" in prompt
        assert "```json" in prompt

    def test_build_reflection_prompt_failure(self):
        from mata_garuda.runtime.reflection import build_reflection_prompt

        prompt = build_reflection_prompt(
            agent_name="Regulation Watcher",
            query="check latest regulations",
            outcome_success=False,
            messages_summary="Source unreachable, HTTP 503",
            genome_snippet="Primary source: peraturan.go.id",
        )
        assert "FAILURE" in prompt
        assert "```json" in prompt


class TestParseReflection:
    def test_parse_json_reflection(self):
        from mata_garuda.runtime.reflection import parse_reflection

        raw = '''Here is my reflection:

```json
{
    "what_worked": "Fast source check",
    "what_didnt": "Nothing",
    "skill": "Check source availability before scraping",
    "insight": "peraturan.go.id responds fastest at 06:00 WITA"
}
```

That's my analysis.'''

        parsed = parse_reflection(raw)
        assert parsed["what_worked"] == "Fast source check"
        assert parsed["skill"] == "Check source availability before scraping"
        assert parsed["insight"] == "peraturan.go.id responds fastest at 06:00 WITA"

    def test_parse_fallback_on_bad_json(self):
        from mata_garuda.runtime.reflection import parse_reflection

        raw = "The run was successful. All 10 regulations published."
        parsed = parse_reflection(raw)
        assert parsed["raw"] == raw
        assert "what_worked" not in parsed

    def test_parse_json_without_fence(self):
        from mata_garuda.runtime.reflection import parse_reflection

        raw = '{"what_worked": "everything", "insight": "test"}'
        parsed = parse_reflection(raw)
        assert parsed["what_worked"] == "everything"


class TestReflectionStorage:
    def test_store_reflection_in_kb(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import store_reflection_in_kb

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        parsed = {
            "what_worked": "Fast scraping",
            "insight": "06:00 is best time",
            "skill": "Check HTTP before scraping",
        }
        ids = store_reflection_in_kb(kb, "Regulation Watcher", parsed)
        assert len(ids) >= 2

        skills = kb.get_by_type("skill")
        assert len(skills) == 1
        assert "Check HTTP" in skills[0]["content"]

        insights = kb.get_by_type("insight")
        assert len(insights) == 1
        kb.close()

    def test_store_raw_fallback(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import store_reflection_in_kb

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        parsed = {"raw": "Unstructured reflection text"}
        ids = store_reflection_in_kb(kb, "test_agent", parsed)
        assert len(ids) == 1  # only the reflection entry, no skill/insight
        kb.close()


class TestGetRecentReflections:
    def test_returns_latest_n_from_kb(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import get_recent_reflections

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        for i in range(5):
            kb.store("test_agent", "reflection", f"Reflection {i}", "run", 0.7)
        recent = get_recent_reflections(kb, "test_agent", n=3)
        assert len(recent) == 3
        kb.close()


class TestReflectionContext:
    def test_build_context_string(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import build_reflection_context

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        kb.store("agent1", "reflection", "Learned to check HTTP first", "run", 0.7)
        kb.store("agent1", "reflection", "Fallback URL works better", "run", 0.7)

        ctx = build_reflection_context(kb, "agent1", n=5)
        assert "PREVIOUS REFLECTIONS" in ctx
        assert "Learned to check HTTP" in ctx
        kb.close()

    def test_empty_when_no_reflections(self, tmp_path):
        from mata_garuda.runtime.knowledge import KnowledgeBase
        from mata_garuda.runtime.reflection import build_reflection_context

        kb = KnowledgeBase(db_path=tmp_path / "test.db")
        ctx = build_reflection_context(kb, "nonexistent", n=5)
        assert ctx == ""
        kb.close()
