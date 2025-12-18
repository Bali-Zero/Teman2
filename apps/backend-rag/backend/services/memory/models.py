"""
Memory Module Models - Pydantic models for memory operations

These models provide a unified interface for all memory operations,
replacing the scattered dataclasses and dicts used across services.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FactType(str, Enum):
    """Types of facts that can be extracted and stored"""

    IDENTITY = "identity"  # Name, age, nationality
    LOCATION = "location"  # Where user lives/works
    PROFESSION = "profession"  # Job, role, expertise
    PREFERENCE = "preference"  # Likes, dislikes
    BUSINESS = "business"  # Company, industry, investment
    TIMELINE = "timeline"  # Deadlines, events
    GOAL = "goal"  # What user wants to achieve
    CONCERN = "concern"  # Worries, pain points
    GENERAL = "general"  # Other facts


class MemoryFact(BaseModel):
    """
    A single fact extracted from a conversation.

    Examples:
    - "User's name is Roberto"
    - "User is 45 years old"
    - "User wants to open a law firm in Bali"
    """

    content: str = Field(..., min_length=1, description="The fact content")
    fact_type: FactType = Field(default=FactType.GENERAL, description="Type of fact")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")
    source: str = Field(default="user", description="Source: 'user' or 'ai'")
    created_at: datetime = Field(
        default_factory=datetime.now, description="When fact was extracted"
    )

    class Config:
        use_enum_values = True


class MemoryContext(BaseModel):
    """
    User context retrieved from memory for use in AI responses.

    This is passed to the LLM as system context to personalize responses.
    """

    user_id: str = Field(..., description="User identifier (email)")
    profile_facts: list[str] = Field(
        default_factory=list, description="List of profile facts (max 10)"
    )
    collective_facts: list[str] = Field(
        default_factory=list, description="Shared knowledge from collective memory"
    )
    timeline_summary: str = Field(
        default="", description="Formatted summary of recent episodic events"
    )
    kg_entities: list[dict] = Field(
        default_factory=list, description="Knowledge graph entities relevant to context"
    )
    summary: str = Field(default="", max_length=500, description="Conversation summary")
    counters: dict[str, int] = Field(
        default_factory=lambda: {"conversations": 0, "searches": 0, "tasks": 0},
        description="Activity counters",
    )
    has_data: bool = Field(default=False, description="Whether user has any stored data")
    last_activity: datetime | None = Field(default=None, description="Last activity timestamp")

    def is_empty(self) -> bool:
        """Check if context has any meaningful data"""
        # Consider collective facts, timeline, and KG entities when checking if empty
        return (
            not self.has_data
            and not self.collective_facts
            and not self.timeline_summary
            and not self.kg_entities
        )

    def to_system_prompt(self) -> str:
        """Format context as a system prompt section"""
        if self.is_empty():
            return ""

        lines = ["## User Context (from memory)"]

        if self.profile_facts:
            lines.append("\n### Personal Memory")
            lines.append("Known facts about this user:")
            for fact in self.profile_facts:
                lines.append(f"- {fact}")

        if self.timeline_summary:
            lines.append(f"\n{self.timeline_summary}")

        if self.collective_facts:
            lines.append("\n### Collective Knowledge (learned from experience)")
            for fact in self.collective_facts:
                lines.append(f"- {fact}")

        if self.kg_entities:
            lines.append("\n### Related Concepts (Knowledge Graph)")
            for entity in self.kg_entities[:5]:  # Limit to 5
                entity_type = entity.get("type", "unknown")
                name = entity.get("name", "Unknown")
                lines.append(f"- {entity_type.title()}: {name}")

        if self.summary:
            lines.append(f"\nConversation history summary: {self.summary}")

        return "\n".join(lines)


class MemoryStats(BaseModel):
    """
    Statistics about the memory system.

    Used for monitoring and debugging.
    """

    cached_users: int = Field(default=0, description="Users in memory cache")
    postgres_enabled: bool = Field(default=False, description="PostgreSQL connection active")
    total_users: int = Field(default=0, description="Total users in database")
    total_facts: int = Field(default=0, description="Total facts stored")
    total_conversations: int = Field(default=0, description="Total conversations")
    max_facts: int = Field(default=10, description="Max facts per user")
    max_summary_length: int = Field(default=500, description="Max summary length")


class ConversationTurn(BaseModel):
    """
    A single turn in a conversation for processing.

    Used when extracting facts from conversation.
    """

    user_message: str = Field(..., description="What the user said")
    ai_response: str = Field(..., description="What the AI responded")
    timestamp: datetime = Field(default_factory=datetime.now)


class MemoryProcessResult(BaseModel):
    """
    Result of processing a conversation for memory extraction.

    Returned by MemoryOrchestrator.process_conversation()
    """

    facts_extracted: int = Field(default=0, description="Number of facts extracted")
    facts_saved: int = Field(default=0, description="Number of facts saved to storage")
    facts: list[MemoryFact] = Field(default_factory=list, description="Extracted facts")
    error: str | None = Field(default=None, description="Error message if processing failed")
    processing_time_ms: float = Field(default=0.0, description="Processing time in milliseconds")

    @property
    def success(self) -> bool:
        """Check if processing was successful"""
        return self.error is None
