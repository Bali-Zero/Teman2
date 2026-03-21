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
from datetime import datetime
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


# ============================================================================
# Node Implementations (Real Service Integration)
# ============================================================================


async def retrieve_node(state: WorkflowState) -> WorkflowState:
    """
    Retrieval Node: Fetch relevant documents from vector store.

    INTEGRATED: Uses SearchService.search() with Qdrant
    """
    question = state.get("question", "")
    logger.info(f"[RETRIEVE_NODE] Processing question: {question[:100]}")

    try:
        # Check if SearchService is available
        if _search_service is None:
            logger.warning("[RETRIEVE_NODE] SearchService not available, using mock data")
            mock_documents = [
                f"Document 1 related to: {question}",
                f"Document 2 related to: {question}",
                f"Document 3 related to: {question}",
            ]
            execution_path = state.get("execution_path", [])
            execution_path.append("retrieve_mock")
            return {
                **state,
                "documents": mock_documents,
                "retrieved_scores": [0.95, 0.87, 0.72],
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
                f"[GRADE_NODE] Score-filtered {len(documents)} -> {len(filtered_docs)} documents"
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
            ]
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
                    f"[GRADE_NODE] Score count mismatch: {len(relevance_scores)} vs {len(documents)}"
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
            f"[GRADE_NODE] LLM-filtered {len(documents)} -> {len(filtered_docs)} documents (threshold: {threshold})"
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
                "timestamp": datetime.now(),
            }

        # Real LLM generation
        # Construct generation prompt with RAG context
        context = "\n\n---\n\n".join(
            [
                f"Context {i + 1}:\n{doc[:1000]}"  # Limit context length
                for i, doc in enumerate(filtered_docs[:5])  # Max 5 docs
            ]
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
            "timestamp": datetime.now(),
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
            "timestamp": datetime.now(),
        }


# ============================================================================
# Conditional Edges (Routing Logic)
# ============================================================================


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

    # Add nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("generate", generate_node)

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

    # Final edge: generate -> END
    workflow.add_edge("generate", END)

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
        "timestamp": datetime.now(),
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
