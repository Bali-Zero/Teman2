"""
Agent API Router

Exposes LangGraph-based agentic RAG workflows.

Endpoints:
- POST /api/agent/invoke - Invoke the RAG workflow with a question
- GET /api/agent/health - Check agent system health
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.agents.graph import invoke_rag_workflow
from backend.app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ============================================================================
# Request/Response Models
# ============================================================================


class AgentInvokeRequest(BaseModel):
    """
    Request model for invoking the agent workflow.
    """

    question: str = Field(
        ...,
        description="User's question to be processed by the RAG workflow",
        min_length=1,
        max_length=2000,
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata (user_id, session_id, etc.)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the requirements for a KITAS visa in Bali?",
                "metadata": {
                    "user_id": "user_123",
                    "session_id": "session_456",
                    "language": "en",
                },
            },
        }


class AgentInvokeResponse(BaseModel):
    """
    Response model for agent workflow invocation.
    """

    success: bool = Field(..., description="Whether the workflow completed successfully")
    question: str = Field(..., description="The original question")
    generation: str = Field(..., description="The generated answer")
    execution_path: list[str] = Field(
        ...,
        description="List of nodes executed in the workflow",
    )
    step_count: int = Field(..., description="Number of steps executed")
    timestamp: datetime = Field(..., description="When the workflow completed")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Request metadata passed through",
    )
    errors: list[str] | None = Field(
        default=None,
        description="List of errors encountered (if any)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "question": "What are the requirements for a KITAS visa in Bali?",
                "generation": "Based on the documents, KITAS visa requirements include...",
                "execution_path": ["retrieve", "grade", "generate"],
                "step_count": 3,
                "timestamp": "2026-02-14T10:30:00",
                "metadata": {"user_id": "user_123"},
                "errors": None,
            },
        }


class AgentHealthResponse(BaseModel):
    """
    Response model for agent health check.
    """

    status: str = Field(..., description="Health status: healthy | degraded | unhealthy")
    graph_loaded: bool = Field(..., description="Whether the LangGraph is loaded")
    timestamp: datetime = Field(..., description="Health check timestamp")
    message: str | None = Field(default=None, description="Additional information")


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(
    request: AgentInvokeRequest,
    current_user: Any = Depends(get_current_user),
) -> AgentInvokeResponse:
    """
    Invoke the RAG workflow with a question.

    This endpoint orchestrates the full retrieval-augmented generation pipeline:
    1. **Retrieve**: Fetch relevant documents from vector store
    2. **Grade**: Filter documents by relevance
    3. **Generate**: Create answer using filtered documents

    **Authentication**: Required (JWT token)

    **Rate Limiting**: Recommended to add rate limiting in production

    **Example**:
    ```bash
    curl -X POST https://nuzantara-rag.fly.dev/api/agent/invoke \\
      -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "question": "What are the requirements for a KITAS visa?",
        "metadata": {"user_id": "user_123"}
      }'
    ```
    """
    logger.info(
        f"[AGENT_API] Received invoke request from user: {current_user.get('email', 'unknown')}",
    )
    logger.info(f"[AGENT_API] Question: {request.question[:100]}")

    try:
        # Enrich metadata with user context
        metadata = request.metadata or {}
        metadata.update(
            {
                "user_email": current_user.get("email"),
                "user_id": current_user.get("id"),
                "request_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

        # Invoke the workflow
        final_state = invoke_rag_workflow(
            question=request.question,
            metadata=metadata,
        )

        # Check for errors
        errors = final_state.get("errors")
        success = not bool(errors)

        if not success:
            logger.warning(f"[AGENT_API] Workflow completed with errors: {errors}")

        # Build response
        response = AgentInvokeResponse(
            success=success,
            question=request.question,
            generation=final_state.get("generation", "No generation produced"),
            execution_path=final_state.get("execution_path", []),
            step_count=final_state.get("step_count", 0),
            timestamp=final_state.get("timestamp", datetime.now(tz=timezone.utc)),
            metadata=request.metadata,
            errors=errors,
        )

        logger.info(
            f"[AGENT_API] Workflow completed. Success: {success}, Steps: {response.step_count}",
        )
        return response

    except Exception as e:
        logger.error(f"[AGENT_API] Error invoking workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to invoke agent workflow: {str(e)}",
        ) from e


@router.get("/health", response_model=AgentHealthResponse)
async def agent_health() -> AgentHealthResponse:
    """
    Check agent system health.

    This endpoint verifies that:
    - The LangGraph workflow is properly loaded
    - No critical errors are present

    **Authentication**: Not required (public health check)

    **Example**:
    ```bash
    curl https://nuzantara-rag.fly.dev/api/agent/health
    ```
    """
    logger.info("[AGENT_API] Health check requested")

    try:
        # Verify graph is loaded
        from backend.app.agents.graph import rag_graph

        graph_loaded = rag_graph is not None

        if not graph_loaded:
            return AgentHealthResponse(
                status="unhealthy",
                graph_loaded=False,
                timestamp=datetime.now(tz=timezone.utc),
                message="LangGraph workflow failed to load",
            )

        # All checks passed
        return AgentHealthResponse(
            status="healthy",
            graph_loaded=True,
            timestamp=datetime.now(tz=timezone.utc),
            message="Agent system is operational",
        )

    except ImportError as e:
        logger.error(f"[AGENT_API] Health check failed: {e}", exc_info=True)
        return AgentHealthResponse(
            status="unhealthy",
            graph_loaded=False,
            timestamp=datetime.now(tz=timezone.utc),
            message=f"Import error: {str(e)}",
        )

    except Exception as e:
        logger.error(f"[AGENT_API] Health check error: {e}", exc_info=True)
        return AgentHealthResponse(
            status="degraded",
            graph_loaded=False,
            timestamp=datetime.now(tz=timezone.utc),
            message=f"Error: {str(e)}",
        )
