"""
LangGraph Workflow Definitions

This module defines the core RAG workflow graph using LangGraph.

Flow: Start -> Retrieve -> Grade -> Generate -> End

Each node is a pure function that takes state and returns updated state.

PHASE 2: INTEGRATED WITH REAL SERVICES
- Retrieve node → SearchService.search()
- Grade node → LLMGateway.send_message() (relevance scoring)
- Generate node → LLMGateway.send_message() (answer generation)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph

from backend.app.agents.state import WorkflowState

logger = logging.getLogger(__name__)


# ============================================================================
# Service Dependencies (Injected at runtime)
# ============================================================================

# Global service instances (set by initialize_services)
_search_service = None
_llm_gateway = None
_db_pool = None


def set_search_service(service: Any) -> None:
    """Set SearchService instance for nodes to use."""
    global _search_service
    _search_service = service
    logger.info("[GRAPH] SearchService injected")


def set_llm_gateway(gateway: Any) -> None:
    """Set LLMGateway instance for nodes to use."""
    global _llm_gateway
    _llm_gateway = gateway
    logger.info("[GRAPH] LLMGateway injected")


def set_db_pool(pool: Any) -> None:
    """Set DB pool instance for conversation history queries."""
    global _db_pool
    _db_pool = pool
    logger.info("[GRAPH] DB pool injected")


async def _load_conversation_history(client_id: int | None, limit: int = 10) -> list[str]:
    """
    Load the last `limit` messages from conversation_messages for a given client_id.

    Returns a list of formatted strings: "[direction] content"
    Returns [] if db_pool is unavailable or client_id is None.
    """
    if _db_pool is None or client_id is None:
        return []
    try:
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT direction, content
                FROM conversation_messages
                WHERE client_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                client_id,
                limit,
            )
        # Rows are newest-first; reverse to chronological order
        return [f"[{row['direction']}] {row['content']}" for row in reversed(rows)]
    except Exception as e:
        logger.warning(f"[GRAPH] Failed to load conversation history for client {client_id}: {e}")
        return []


# ============================================================================
# Node Implementations (Real Service Integration)
# ============================================================================


async def retrieve_node(state: WorkflowState) -> WorkflowState:
    """
    Retrieval Node: Fetch relevant documents from vector store.

    INTEGRATED: Uses SearchService.search() with Qdrant
    """
    question = state.get("question", "")
    metadata = state.get("metadata") or {}
    client_id: int | None = metadata.get("client_id") or metadata.get("user_id")
    # Normalize: if it's a string int, cast it
    if isinstance(client_id, str) and client_id.isdigit():
        client_id = int(client_id)
    elif not isinstance(client_id, int):
        client_id = None

    logger.info(f"[RETRIEVE_NODE] Processing question: {question[:100]}")

    # Load conversation history from DB (non-blocking: returns [] on failure)
    conversation_history = await _load_conversation_history(client_id)
    if conversation_history:
        logger.info(f"[RETRIEVE_NODE] Loaded {len(conversation_history)} prior messages for client {client_id}")

    try:
        # Check if SearchService is available
        if _search_service is None:
            logger.warning("[RETRIEVE_NODE] SearchService not available, using mock data")
            mock_documents = [
                f"Document 1 related to: {question}",
                f"Document 2 related to: {question}",
                f"Document 3 related to: {question}",
            ]
            mock_scores = [0.95, 0.87, 0.72]
            if conversation_history:
                history_block = "=== Conversation History ===\n" + "\n".join(conversation_history)
                mock_documents = [history_block] + mock_documents
                mock_scores = [1.0] + mock_scores
            execution_path = state.get("execution_path", [])
            execution_path.append("retrieve_mock")
            return {
                **state,
                "documents": mock_documents,
                "retrieved_scores": mock_scores,
                "execution_path": execution_path,
                "step_count": state.get("step_count", 0) + 1,
            }

        # Real SearchService call
        search_result = await _search_service.search(
            query=question,
            user_level=2,  # B-tier access (most collections)
            limit=5,
            apply_filters=False,  # No tier filtering for agent workflow
        )

        # Extract documents and scores from search result
        results = search_result.get("results", [])
        documents = []
        scores = []

        for result in results:
            # Handle different result formats
            if isinstance(result, dict):
                text = result.get("text", result.get("content", ""))
                score = result.get("score", 0.0)

                # Also include metadata for context
                metadata = result.get("metadata", {})
                doc_with_meta = text
                if metadata:
                    # Add source information
                    source = metadata.get("source", metadata.get("collection", ""))
                    if source:
                        doc_with_meta = f"[Source: {source}]\n{text}"

                documents.append(doc_with_meta)
                scores.append(score)
            else:
                documents.append(str(result))
                scores.append(0.0)

        logger.info(f"[RETRIEVE_NODE] Retrieved {len(documents)} documents")
        logger.info(f"[RETRIEVE_NODE] Scores: {scores[:3]}...")

        # Prepend conversation history as context documents (score 1.0 = always keep)
        if conversation_history:
            history_block = "=== Conversation History ===\n" + "\n".join(conversation_history)
            documents = [history_block] + documents
            scores = [1.0] + scores

        # Update execution tracking
        execution_path = state.get("execution_path", [])
        execution_path.append("retrieve")

        return {
            **state,
            "documents": documents,
            "retrieved_scores": scores,
            "execution_path": execution_path,
            "step_count": state.get("step_count", 0) + 1,
        }

    except Exception as e:
        logger.error(f"[RETRIEVE_NODE] Error: {e}", exc_info=True)
        # Add error to state but don't fail the workflow
        errors = state.get("errors", [])
        errors.append(f"Retrieval error: {str(e)}")

        execution_path = state.get("execution_path", [])
        execution_path.append("retrieve_error")

        return {
            **state,
            "documents": [],
            "retrieved_scores": [],
            "errors": errors,
            "execution_path": execution_path,
            "step_count": state.get("step_count", 0) + 1,
        }


async def grade_node(state: WorkflowState) -> WorkflowState:
    """
    Grading Node: Assess document relevance to the question using LLM.

    INTEGRATED: Uses LLMGateway.send_message() for LLM-based grading
    """
    question = state.get("question", "")
    documents = state.get("documents", [])
    retrieved_scores = state.get("retrieved_scores", [])

    logger.info(f"[GRADE_NODE] Grading {len(documents)} documents for: {question[:100]}")

    try:
        # Check if LLMGateway is available
        if _llm_gateway is None:
            logger.warning("[GRADE_NODE] LLMGateway not available, using score-based filtering")
            # Fallback: filter by retrieval scores
            threshold = 0.7
            filtered_docs = []
            relevance_scores = []

            for doc, score in zip(documents, retrieved_scores, strict=False):
                if score >= threshold:
                    filtered_docs.append(doc)
                    relevance_scores.append(score)

            logger.info(
                f"[GRADE_NODE] Score-filtered {len(documents)} -> {len(filtered_docs)} documents",
            )

            execution_path = state.get("execution_path", [])
            execution_path.append("grade_score_based")

            return {
                **state,
                "filtered_documents": filtered_docs,
                "relevance_scores": relevance_scores,
                "execution_path": execution_path,
                "step_count": state.get("step_count", 0) + 1,
            }

        # Real LLM-based grading
        # Construct grading prompt
        doc_list = "\n\n".join(
            [
                f"Document {i + 1} (score: {score:.3f}):\n{doc[:500]}..."
                for i, (doc, score) in enumerate(zip(documents, retrieved_scores, strict=False))
            ],
        )

        grading_prompt = f"""You are a document relevance grader. Your task is to assess if documents are relevant to answer a question.

Question: {question}

Documents to grade:
{doc_list}

For each document, rate its relevance on a scale of 0.0 to 1.0:
- 1.0: Highly relevant, directly answers the question
- 0.7-0.9: Relevant, contains useful information
- 0.4-0.6: Somewhat relevant, tangential information
- 0.0-0.3: Not relevant, off-topic

Respond with ONLY a JSON array of scores, one per document. Example: [0.9, 0.7, 0.3]

Your response (JSON array only):"""

        # Call LLM for grading (pass None for chat - LLMGateway will create new session)
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        response_text, model_used, _, token_usage = await _llm_gateway.send_message(
            chat=None,  # LLMGateway creates new session internally
            message=grading_prompt,
            tier=TIER_FLASH,  # Use fast model for grading
            enable_function_calling=False,
        )

        logger.info(f"[GRADE_NODE] LLM grading response: {response_text[:200]}")
        logger.info(f"[GRADE_NODE] Model: {model_used}, Cost: ${token_usage.cost_usd:.6f}")

        # Parse LLM response (extract JSON array)
        try:
            # Try to extract JSON array from response
            import re

            json_match = re.search(r"\[([\d\.,\s]+)\]", response_text)
            if json_match:
                relevance_scores = json.loads(json_match.group(0))
            else:
                # Fallback: try parsing entire response as JSON
                relevance_scores = json.loads(response_text)

            # Ensure we have the right number of scores
            if len(relevance_scores) != len(documents):
                logger.warning(
                    f"[GRADE_NODE] Score count mismatch: {len(relevance_scores)} vs {len(documents)}",
                )
                # Pad or truncate
                if len(relevance_scores) < len(documents):
                    relevance_scores.extend([0.5] * (len(documents) - len(relevance_scores)))
                else:
                    relevance_scores = relevance_scores[: len(documents)]

        except (json.JSONDecodeError, ValueError, AttributeError) as e:
            logger.warning(f"[GRADE_NODE] Failed to parse LLM scores: {e}")
            # Fallback to retrieval scores
            relevance_scores = retrieved_scores

        # Filter documents with score > 0.6
        threshold = 0.6
        filtered_docs = []
        filtered_scores = []

        for doc, score in zip(documents, relevance_scores, strict=False):
            if score >= threshold:
                filtered_docs.append(doc)
                filtered_scores.append(score)

        logger.info(
            f"[GRADE_NODE] LLM-filtered {len(documents)} -> {len(filtered_docs)} documents (threshold: {threshold})",
        )

        # Update execution tracking
        execution_path = state.get("execution_path", [])
        execution_path.append("grade")

        return {
            **state,
            "filtered_documents": filtered_docs,
            "relevance_scores": filtered_scores,
            "execution_path": execution_path,
            "step_count": state.get("step_count", 0) + 1,
        }

    except Exception as e:
        logger.error(f"[GRADE_NODE] Error: {e}", exc_info=True)
        # On error, pass through all documents (safe fallback)
        errors = state.get("errors", [])
        errors.append(f"Grading error: {str(e)}")

        execution_path = state.get("execution_path", [])
        execution_path.append("grade_error")

        return {
            **state,
            "filtered_documents": documents,  # Pass through all docs
            "relevance_scores": retrieved_scores,
            "errors": errors,
            "execution_path": execution_path,
            "step_count": state.get("step_count", 0) + 1,
        }


async def generate_node(state: WorkflowState) -> WorkflowState:
    """
    Generation Node: Create final answer using filtered documents.

    INTEGRATED: Uses LLMGateway.send_message() for answer generation
    """
    question = state.get("question", "")
    filtered_docs = state.get("filtered_documents", [])

    logger.info(f"[GENERATE_NODE] Generating answer for: {question[:100]}")
    logger.info(f"[GENERATE_NODE] Using {len(filtered_docs)} filtered documents")

    try:
        # Check if LLMGateway is available
        if _llm_gateway is None:
            logger.warning("[GENERATE_NODE] LLMGateway not available, using mock generation")
            mock_answer = f"""
Based on the provided documents, here's the answer to: "{question}"

Relevant information found from {len(filtered_docs)} documents.

This is a mock answer. Real generation requires LLMGateway to be initialized.
"""
            execution_path = state.get("execution_path", [])
            execution_path.append("generate_mock")

            return {
                **state,
                "generation": mock_answer.strip(),
                "execution_path": execution_path,
                "step_count": state.get("step_count", 0) + 1,
                "timestamp": datetime.now(tz=timezone.utc),
            }

        # Real LLM generation
        # Construct generation prompt with RAG context
        context = "\n\n---\n\n".join(
            [
                f"Context {i + 1}:\n{doc[:1000]}"  # Limit context length
                for i, doc in enumerate(filtered_docs[:5])  # Max 5 docs
            ],
        )

        system_prompt = """You are Zantara, an expert AI assistant for Indonesian business and immigration matters.
Your role is to provide accurate, helpful answers based on the provided context documents.

Guidelines:
- Base your answer primarily on the provided context
- If the context doesn't fully answer the question, acknowledge this
- Be concise but thorough
- Use a professional yet friendly tone
- Cite specific information from the context when relevant"""

        generation_prompt = f"""Question: {question}

Context Documents:
{context}

Based on the context above, please provide a comprehensive answer to the question.
If the context is insufficient, clearly state what information is missing.

Your answer:"""

        # Call LLM for generation (pass None for chat - LLMGateway will create new session)
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH

        response_text, model_used, _, token_usage = await _llm_gateway.send_message(
            chat=None,  # LLMGateway creates new session internally
            message=generation_prompt,
            system_prompt=system_prompt,
            tier=TIER_FLASH,
            enable_function_calling=False,
        )

        logger.info(f"[GENERATE_NODE] Generated {len(response_text)} chars")
        logger.info(f"[GENERATE_NODE] Model: {model_used}, Cost: ${token_usage.cost_usd:.6f}")

        # Update execution tracking
        execution_path = state.get("execution_path", [])
        execution_path.append("generate")

        return {
            **state,
            "generation": response_text.strip(),
            "execution_path": execution_path,
            "step_count": state.get("step_count", 0) + 1,
            "timestamp": datetime.now(tz=timezone.utc),
        }

    except Exception as e:
        logger.error(f"[GENERATE_NODE] Error: {e}", exc_info=True)
        # Return error message as generation
        errors = state.get("errors", [])
        errors.append(f"Generation error: {str(e)}")

        execution_path = state.get("execution_path", [])
        execution_path.append("generate_error")

        error_message = f"I apologize, but I encountered an error generating the answer: {str(e)}"

        return {
            **state,
            "generation": error_message,
            "errors": errors,
            "execution_path": execution_path,
            "step_count": state.get("step_count", 0) + 1,
            "timestamp": datetime.now(tz=timezone.utc),
        }


# ============================================================================
# Conditional Edges (Routing Logic)
# ============================================================================


# ============================================================================
# Self-RAG Reflection Nodes (activated for low confidence)
# ============================================================================

MAX_REFLECTION_RETRIES = 2  # Max query rewrites before accepting


async def check_hallucination_node(state: WorkflowState) -> WorkflowState:
    """
    Self-RAG: Check if generation is grounded in retrieved documents.

    Only activated when confidence is low (<0.30).
    If hallucination detected, rewrites query and retries.
    """
    generation = state.get("generation", "")
    filtered_docs = state.get("filtered_documents", [])
    retries = state.get("reflection_retries", 0)

    state["execution_path"] = state.get("execution_path", []) + ["check_hallucination"]

    # Skip reflection if no generation or max retries reached
    if not generation or retries >= MAX_REFLECTION_RETRIES:
        state["hallucination_check"] = "skipped"
        return state

    # Check if generation references content from documents
    doc_texts = " ".join(
        (d.get("content", d.get("text", ""))[:200] if isinstance(d, dict) else str(d)[:200])
        for d in filtered_docs
    )

    if not doc_texts:
        state["hallucination_check"] = "no_docs"
        return state

    # Simple grounding check: does the generation contain terms from the docs?
    doc_terms = set(doc_texts.lower().split())
    gen_terms = set(generation.lower().split())
    overlap = len(doc_terms & gen_terms)
    grounding_score = overlap / max(len(gen_terms), 1)

    state["grounding_score"] = grounding_score

    if grounding_score < 0.30:
        # Very low grounding — likely hallucination
        state["hallucination_check"] = "failed"
        logger.warning(
            f"[SELF-RAG] Low grounding score ({grounding_score:.2f}), "
            f"retry {retries + 1}/{MAX_REFLECTION_RETRIES}",
        )
    else:
        state["hallucination_check"] = "passed"
        logger.info(f"[SELF-RAG] Grounding check passed (score: {grounding_score:.2f})")

    return state


async def transform_query_node(state: WorkflowState) -> WorkflowState:
    """
    Self-RAG: Rewrite the query when hallucination is detected.

    Adds specificity to the query to improve retrieval on retry.
    """
    original_query = state.get("question", "")
    retries = state.get("reflection_retries", 0)

    state["execution_path"] = state.get("execution_path", []) + ["transform_query"]
    state["reflection_retries"] = retries + 1

    # Simple query transformation: add context from what we know
    filtered_docs = state.get("filtered_documents", [])
    if filtered_docs:
        first_doc = filtered_docs[0]
        doc_snippet = (first_doc.get("content", first_doc.get("text", ""))[:100] if isinstance(first_doc, dict) else str(first_doc)[:100])
        transformed = f"{original_query} specifically about {doc_snippet[:50]}"
    else:
        transformed = f"detailed information about {original_query}"

    state["question"] = transformed
    logger.info(
        f"[SELF-RAG] Query transformed (retry {retries + 1}): {transformed[:80]}...",
    )

    return state


def should_reflect_or_end(state: WorkflowState) -> str:
    """
    Decision: After hallucination check, retry or accept.

    Only retries if:
    - Hallucination check failed
    - Haven't exceeded max retries
    """
    check = state.get("hallucination_check", "passed")
    retries = state.get("reflection_retries", 0)

    if check == "failed" and retries < MAX_REFLECTION_RETRIES:
        return "transform_query"

    return END


def should_continue_to_generation(state: WorkflowState) -> str:
    """
    Decision function: Should we proceed to generation or end?

    If no relevant documents found, end early with explanation.
    Otherwise, proceed to generation.
    """
    filtered_docs = state.get("filtered_documents", [])

    if not filtered_docs:
        logger.warning("[ROUTING] No relevant documents found, ending workflow")
        return END

    logger.info(f"[ROUTING] {len(filtered_docs)} relevant docs found, proceeding to generation")
    return "generate"


# ============================================================================
# Graph Construction
# ============================================================================


def create_rag_graph() -> StateGraph:
    """
    Create the RAG workflow graph.

    Flow:
    1. Start
    2. Retrieve documents (SearchService)
    3. Grade documents (LLM relevance scoring)
    4. Conditional: If relevant docs exist -> Generate, else -> End
    5. End

    Returns:
        Compiled StateGraph ready for invocation
    """
    logger.info("[GRAPH] Building RAG workflow graph (integrated with real services)")

    # Initialize graph with WorkflowState schema
    workflow = StateGraph(WorkflowState)

    # Add nodes (including Self-RAG reflection)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("check_hallucination", check_hallucination_node)
    workflow.add_node("transform_query", transform_query_node)

    # Define edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade")

    # Conditional edge: grade -> generate OR END
    workflow.add_conditional_edges(
        "grade",
        should_continue_to_generation,
        {
            "generate": "generate",
            END: END,
        },
    )

    # generate -> check_hallucination (Self-RAG reflection)
    workflow.add_edge("generate", "check_hallucination")

    # Conditional: check_hallucination -> END or transform_query -> retrieve (retry)
    workflow.add_conditional_edges(
        "check_hallucination",
        should_reflect_or_end,
        {
            "transform_query": "transform_query",
            END: END,
        },
    )

    # transform_query loops back to retrieve
    workflow.add_edge("transform_query", "retrieve")

    # Compile the graph
    compiled_graph = workflow.compile()
    logger.info("[GRAPH] RAG workflow graph compiled successfully (real service integration)")

    return compiled_graph


# ============================================================================
# Public API
# ============================================================================

# Pre-compiled graph instance (singleton pattern)
rag_graph = create_rag_graph()


async def invoke_rag_workflow(question: str, metadata: dict[str, Any] = None) -> WorkflowState:
    """
    Invoke the RAG workflow with a question.

    Args:
        question: User's input question
        metadata: Optional context (user_id, session_id, etc.)

    Returns:
        Final workflow state with generation and execution path
    """
    logger.info(f"[WORKFLOW] Invoking RAG workflow for question: {question[:100]}")

    initial_state: WorkflowState = {
        "question": question,
        "metadata": metadata or {},
        "step_count": 0,
        "execution_path": [],
        "timestamp": datetime.now(tz=timezone.utc),
    }

    try:
        final_state = await rag_graph.ainvoke(initial_state)
        logger.info(f"[WORKFLOW] Completed successfully. Path: {final_state.get('execution_path')}")
        return final_state
    except Exception as e:
        logger.error(f"[WORKFLOW] Error during execution: {e}", exc_info=True)
        return {
            **initial_state,
            "errors": [str(e)],
            "generation": f"Error: {str(e)}",
        }
