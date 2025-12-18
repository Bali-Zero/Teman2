"""
Pydantic schemas for agent input validation
"""

from pydantic import BaseModel, Field


class ConversationTrainerRequest(BaseModel):
    """Request schema for ConversationTrainer"""

    days_back: int = Field(
        ge=1, le=365, default=7, description="Days to look back for conversations (1-365)"
    )


class KnowledgeGraphBuilderRequest(BaseModel):
    """Request schema for KnowledgeGraphBuilder"""

    days_back: int = Field(
        ge=1, le=365, default=30, description="Days to look back for conversations (1-365)"
    )
    init_schema: bool = Field(default=False, description="Initialize database schema")


class EntitySearchRequest(BaseModel):
    """Request schema for semantic entity search"""

    query: str = Field(min_length=1, max_length=200, description="Search query (1-200 characters)")
    top_k: int = Field(ge=1, le=100, default=10, description="Number of results to return (1-100)")










