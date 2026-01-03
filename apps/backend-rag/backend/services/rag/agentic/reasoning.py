"""
ReAct Reasoning Engine - Thought → Action → Observation Loop

This component handles the core agentic reasoning loop using the ReAct pattern:
- Thought: LLM generates reasoning about what to do next
- Action: Execute a tool based on the thought
- Observation: Collect results from tool execution
- Repeat until final answer or max steps reached

Key features:
- Native function calling with regex fallback
- Early exit optimization for efficient queries
- Citation handling for vector search results
- Final answer generation if not provided
- Integration with response verification pipeline
"""

import json
import logging
import re
from typing import Any

from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from app.core.config import settings
from app.utils.tracing import add_span_event, set_span_attribute, set_span_status, trace_span
from services.llm_clients.pricing import TokenUsage
from services.tools.definitions import AgentState, AgentStep

from .response_processor import post_process_response
from .tool_executor import execute_tool, parse_tool_call

logger = logging.getLogger(__name__)


def is_valid_tool_call(tool_call: Any) -> bool:
    """
    Validate that a tool call has all required fields.

    FIX Edge Case 2: Prevents using partially parsed tool calls that could
    cause downstream errors when execute_tool is called with None arguments.

    Args:
        tool_call: ToolCall object or None

    Returns:
        True if tool_call is valid and complete, False otherwise
    """
    if tool_call is None:
        return False
    if not hasattr(tool_call, "tool_name") or not tool_call.tool_name:
        return False
    if not isinstance(tool_call.tool_name, str):
        return False
    if not hasattr(tool_call, "arguments"):
        return False
    # arguments can be empty dict {} but not None
    if tool_call.arguments is None:
        return False
    return True


def calculate_evidence_score(
    sources: list[dict] | None,
    context_gathered: list[str],
    query: str,
) -> float:
    """
    Calculate evidence score based on source quality and context relevance.

    Formula:
    - base_score = 0.0
    - If at least 1 source with score > 0.3 -> +0.5 (lowered: re-ranker gives low scores)
    - If > 3 total sources -> +0.2
    - If context contains query keywords -> +0.3
    - MAX Score = 1.0

    Args:
        sources: List of source dictionaries with 'score' field
        context_gathered: List of context strings from tool results
        query: Original user query

    Returns:
        Evidence score between 0.0 and 1.0
    """
    base_score = 0.0

    # Check for high-quality sources (score > 0.3, lowered because re-ranker gives low scores)
    if sources:
        high_quality_sources = [
            s for s in sources if isinstance(s, dict) and s.get("score", 0.0) > 0.3
        ]
        if len(high_quality_sources) >= 1:
            base_score += 0.5

        # Check for multiple sources (> 3)
        if len(sources) > 3:
            base_score += 0.2
    elif context_gathered:
        # Fallback: if no sources but we have context, check if context is substantial
        total_context_length = sum(len(ctx) for ctx in context_gathered)
        if total_context_length > 500:  # Substantial context
            base_score += 0.3

    # Check if context contains query keywords
    if context_gathered:
        query_lower = query.lower()
        # Extract meaningful keywords (words longer than 3 chars, excluding common words)
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "this", "that", "these",
            "those", "i", "you", "he", "she", "it", "we", "they", "what", "which",
            "who", "whom", "whose", "where", "when", "why", "how", "all", "each",
            "every", "both", "few", "more", "most", "other", "some", "such", "no",
            "nor", "not", "only", "own", "same", "so", "than", "too", "very",
            "il", "la", "lo", "gli", "le", "un", "una", "uno", "di", "da",
            "in", "con", "su", "per", "tra", "fra", "che", "chi", "cosa", "come",
            "dove", "quando", "perché", "quale", "quali",
        }
        query_keywords = [
            word.lower()
            for word in query.split()
            if len(word) > 3 and word.lower() not in stop_words
        ]

        if query_keywords:
            context_text = " ".join(context_gathered).lower()
            matching_keywords = sum(1 for kw in query_keywords if kw in context_text)
            # If at least 30% of keywords match, add score
            if matching_keywords / len(query_keywords) >= 0.3:
                base_score += 0.3

    # Cap at 1.0
    return min(base_score, 1.0)


def _validate_context_quality(
    query: str,
    context_items: list[str],
) -> float:
    """
    Validate context quality and return score (0.0-1.0).
    
    Args:
        query: Original user query
        context_items: List of context strings from tool results
        
    Returns:
        Quality score between 0.0 and 1.0
    """
    if not context_items:
        return 0.0

    # Check minimum items
    if len(context_items) < 1:
        return 0.0

    # Simple heuristic: check if context contains query keywords
    query_keywords = set(query.lower().split())
    quality_scores = []

    for item in context_items:
        item_lower = item.lower()
        matching_keywords = sum(1 for kw in query_keywords if kw in item_lower)
        relevance = matching_keywords / max(len(query_keywords), 1)
        quality_scores.append(relevance)

    # Average quality
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    # Penalize if too few items
    item_count_penalty = min(len(context_items) / 5.0, 1.0)  # Prefer 5+ items

    final_score = avg_quality * 0.7 + item_count_penalty * 0.3

    return min(final_score, 1.0)


class ReasoningEngine:
    """
    Executes the ReAct (Reasoning + Acting) loop for agentic RAG.

    The ReAct pattern combines reasoning and acting in an interleaved manner:
    1. Thought: The model reasons about the current state
    2. Action: Based on reasoning, selects and executes a tool
    3. Observation: Receives the result of the tool execution
    4. Repeat steps 1-3 until a final answer is reached

    This engine is responsible for:
    - Managing the reasoning loop state
    - Parsing tool calls (native + regex fallback)
    - Executing tools and collecting observations
    - Handling early exit conditions
    - Generating final answers when not provided
    - Processing responses through verification pipeline
    """

    def __init__(
        self,
        tool_map: dict[str, Any],
        response_pipeline: Any = None,
    ):
        """
        Initialize the ReAct reasoning engine.

        Args:
            tool_map: Dictionary mapping tool names to tool instances
            response_pipeline: Optional pipeline for response verification/cleaning
        """
        self.tool_map = tool_map
        self.response_pipeline = response_pipeline
        self._min_context_quality_score = 0.3
        self._min_context_items = 1

    def _validate_context_quality(
        self,
        query: str,
        context_items: list[str],
    ) -> float:
        """Validate context quality and return score (0.0-1.0)."""
        return _validate_context_quality(query, context_items)

    async def execute_react_loop(
        self,
        state: AgentState,
        llm_gateway: Any,
        chat: Any,
        initial_prompt: str,
        system_prompt: str,
        query: str,
        user_id: str,
        model_tier: int,
        tool_execution_counter: dict,
    ) -> tuple[AgentState, str, list[dict], TokenUsage]:
        """
        Execute the ReAct reasoning loop.

        Args:
            state: Current agent state with steps and context
            llm_gateway: LLM gateway for model interactions
            chat: Active chat session
            initial_prompt: First message to send to the model
            system_prompt: System instructions for the model
            query: Original user query
            user_id: User identifier for tracking
            model_tier: Model tier to use (TIER_FLASH, TIER_PRO, etc.)
            tool_execution_counter: Counter for tool usage tracking

        Returns:
            Tuple of (updated_state, model_name_used, conversation_messages, token_usage)
        """
        conversation_messages = []
        model_used_name = "unknown"
        accumulated_usage = TokenUsage()  # Track total token usage across ReAct loop

        # ==================== REACT LOOP ====================
        # 🔍 TRACING: Span for entire ReAct loop
        with trace_span("react.execute_loop", {
            "user_id": user_id,
            "max_steps": state.max_steps,
            "query_length": len(query),
        }):
            while state.current_step < state.max_steps:
                state.current_step += 1

                # 🔍 TRACING: Span for each step
                with trace_span(f"react.step.{state.current_step}", {
                    "step_number": state.current_step,
                }):
                    # Get model response with automatic fallback and native function calling
                    try:
                        if state.current_step == 1:
                            message = initial_prompt
                        else:
                            # Continue conversation with observation
                            last_observation = state.steps[-1].observation if state.steps else ""
                            message = f"Observation: {last_observation}\n\nContinue with your next thought or provide final answer."

                        text_response, model_used_name, response_obj, step_usage = await llm_gateway.send_message(
                            chat,
                            message,
                            system_prompt,
                            tier=model_tier,
                            enable_function_calling=True,
                        )

                        # Accumulate token usage
                        accumulated_usage = accumulated_usage + step_usage

                        set_span_attribute("model_used", model_used_name)
                        set_span_attribute("step_tokens", step_usage.total_tokens)
                        conversation_messages.append({"role": "user", "content": message})
                        conversation_messages.append({"role": "assistant", "content": text_response})

                    except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                        logger.error(f"Error during chat interaction: {e}", exc_info=True)
                        set_span_status("error", str(e))
                        break

                    # Parse for tool calls - try native function calling first, then regex fallback
                    tool_call = None

                    # Check for function call in response parts (native mode)
                    if hasattr(response_obj, "candidates") and response_obj.candidates:
                        for candidate in response_obj.candidates:
                            # FIX Edge Case 1: Proper None check for candidate.content
                            # The old check `hasattr(candidate.content, "parts")` fails when
                            # candidate.content is None because hasattr(None, "parts") = False
                            # but we still try to iterate. Now we explicitly check for None.
                            if (
                                hasattr(candidate, "content")
                                and candidate.content is not None
                                and hasattr(candidate.content, "parts")
                                and candidate.content.parts  # Ensure parts is not None/empty
                            ):
                                for part in candidate.content.parts:
                                    tool_call = parse_tool_call(part, use_native=True)
                                    if tool_call:
                                        logger.info("✅ [Native Function Call] Detected in response")
                                        set_span_attribute("function_call_mode", "native")
                                        break
                                if tool_call:
                                    break

                    # FIX Edge Case 2: Validate tool call before using
                    # A partially parsed tool_call (e.g., with None arguments) would
                    # pass the `if tool_call` check but fail in execute_tool.
                    # Use is_valid_tool_call to ensure all required fields are present.

                    # Fallback to regex parsing if no valid native function call found
                    if not is_valid_tool_call(tool_call):
                        tool_call = parse_tool_call(text_response, use_native=False)
                        if is_valid_tool_call(tool_call):
                            set_span_attribute("function_call_mode", "regex")
                        else:
                            # Neither native nor regex produced a valid tool call
                            tool_call = None

                    if is_valid_tool_call(tool_call):
                        set_span_attribute("tool_name", tool_call.tool_name)
                        add_span_event("tool.call", {"tool": tool_call.tool_name, "args": str(tool_call.arguments)[:200]})

                        logger.info(
                            f"🔧 [Agent] Calling tool: {tool_call.tool_name} with {tool_call.arguments}"
                        )
                        tool_result, tool_duration = await execute_tool(
                            self.tool_map,
                            tool_call.tool_name,
                            tool_call.arguments,
                            user_id,
                            tool_execution_counter,
                        )

                        # Store tool timing for metrics (attached to step later)
                        tool_call.execution_time = tool_duration
                        set_span_attribute("tool_result_length", len(tool_result) if tool_result else 0)
                        set_span_attribute("tool_duration_ms", int(tool_duration * 1000))

                        # --- CITATION HANDLING ---
                        # FIX Edge Case 3: Handle empty content from vector_search
                        # If content is empty but sources exist, we should:
                        # 1. Log a warning (sources without content are less useful)
                        # 2. Keep the original tool_result (JSON string) if content is empty
                        # 3. Only add non-empty content to context_gathered
                        if tool_call.tool_name == "vector_search":
                            try:
                                parsed_result = json.loads(tool_result)
                                if isinstance(parsed_result, dict) and "sources" in parsed_result:
                                    content = parsed_result.get("content", "")
                                    new_sources = parsed_result.get("sources", [])

                                    # Only extract content if it's meaningful (>10 chars after strip)
                                    if content and len(content.strip()) > 10:
                                        tool_result = content
                                        if not hasattr(state, "sources"):
                                            state.sources = []
                                        state.sources.extend(new_sources)
                                        set_span_attribute("sources_collected", len(new_sources))
                                        logger.info(
                                            f"📚 [Agent] Collected {len(new_sources)} sources from vector_search"
                                        )
                                    else:
                                        # Empty content - log warning and keep original result
                                        logger.warning(
                                            f"⚠️ [Agent] Vector search returned empty content with "
                                            f"{len(new_sources)} sources. Keeping original result."
                                        )
                                        set_span_attribute("empty_content_warning", "true")
                                        # Still collect sources for evidence scoring even if content is empty
                                        if new_sources:
                                            if not hasattr(state, "sources"):
                                                state.sources = []
                                            state.sources.extend(new_sources)
                            except json.JSONDecodeError:
                                pass
                            except (KeyError, ValueError, TypeError) as e:
                                logger.warning(f"Failed to parse vector_search result: {e}", exc_info=True)

                        # Handle image generation results
                        if tool_call.tool_name == "generate_image":
                            try:
                                parsed_result = json.loads(tool_result)
                                if isinstance(parsed_result, dict) and parsed_result.get("success"):
                                    # Extract image URL or base64 data
                                    image_url = parsed_result.get("image_url") or parsed_result.get("image_data")
                                    if image_url:
                                        logger.info(f"🖼️ [Agent] Image generated: {parsed_result.get('service')}")
                                        # Store in state for final response
                                        if not hasattr(state, "generated_images"):
                                            state.generated_images = []
                                        state.generated_images.append(image_url)
                            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                                logger.warning(f"Failed to parse generate_image result: {e}")

                        # Update the tool call with the result
                        tool_call.result = tool_result

                        step = AgentStep(
                            step_number=state.current_step,
                            thought=text_response,
                            action=tool_call,
                            observation=tool_result,
                        )
                        state.steps.append(step)

                        # FIX Edge Case 3: Only append non-empty context
                        # Empty strings pollute context_gathered and affect evidence scoring
                        if tool_result and len(tool_result.strip()) > 0:
                            state.context_gathered.append(tool_result)
                        else:
                            logger.warning("⚠️ [Agent] Skipping empty tool_result for context_gathered")

                        # Validate context quality before using
                        if state.context_gathered:
                            quality_score = self._validate_context_quality(
                                query=query,
                                context_items=state.context_gathered,
                            )

                            if quality_score < self._min_context_quality_score:
                                logger.warning(
                                    f"⚠️ Context quality too low ({quality_score:.2f} < {self._min_context_quality_score})",
                                    extra={
                                        "quality_score": quality_score,
                                        "context_items": len(state.context_gathered),
                                        "step": state.current_step,
                                    }
                                )
                                try:
                                    from app.metrics import reasoning_low_context_quality_total
                                    reasoning_low_context_quality_total.inc()
                                except ImportError:
                                    pass

                                # Try to gather more context if not at max steps
                                if state.current_step < state.max_steps:
                                    logger.info("🔄 [Agent] Low quality context, continuing to gather more...")
                                    continue  # Try another tool
                                else:
                                    # Last step - use what we have but warn
                                    logger.warning("Using low-quality context due to max steps reached")

                        # OPTIMIZATION: Early exit (only for simple queries)
                        # Complex queries (business_complex, business_strategic) may need KG tool
                        complex_intents = {"business_complex", "business_strategic", "devai_code"}
                        is_complex_query = getattr(state, "intent_type", "simple") in complex_intents

                        if (
                            tool_call.tool_name == "vector_search"
                            and len(tool_result) > 500
                            and "No relevant documents" not in tool_result
                            and not is_complex_query  # Allow complex queries to continue
                        ):
                            logger.info("🚀 [Early Exit] Sufficient context from retrieval.")
                            set_span_attribute("early_exit", "true")
                            set_span_status("ok")
                            break
                        elif is_complex_query and tool_call.tool_name == "vector_search":
                            logger.info("🔗 [Complex Query] Allowing multi-tool reasoning (KG may be needed)")

                        set_span_status("ok")

                    else:
                        # No tool call, assume final answer or just thought
                        set_span_attribute("has_tool_call", "false")
                        if "Final Answer:" in text_response or state.current_step >= state.max_steps:
                            if "Final Answer:" in text_response:
                                state.final_answer = text_response.split("Final Answer:")[-1].strip()
                            else:
                                state.final_answer = text_response

                            step = AgentStep(
                                step_number=state.current_step, thought=text_response, is_final=True
                            )
                            state.steps.append(step)
                            set_span_attribute("is_final_answer", "true")
                            set_span_status("ok")
                            break
                        else:
                            # Just a thought step
                            step = AgentStep(step_number=state.current_step, thought=text_response)
                            state.steps.append(step)
                            set_span_status("ok")

            # Set final loop attributes
            set_span_attribute("total_steps", state.current_step)
            set_span_attribute("tools_executed", tool_execution_counter.get("count", 0))

        # ==================== EVIDENCE SCORE CALCULATION ====================
        # 🔍 TRACING: Evidence score calculation
        sources_count = len(state.sources) if hasattr(state, "sources") and state.sources is not None else 0
        with trace_span("react.evidence_score", {"sources_count": sources_count}):
            # Calculate evidence score after ReAct loop
            sources = state.sources if hasattr(state, "sources") else None
            evidence_score = calculate_evidence_score(sources, state.context_gathered, query)
            logger.info(f"🛡️ [Uncertainty] Evidence Score: {evidence_score:.2f}")
            set_span_attribute("evidence_score", evidence_score)
            # Store evidence_score in state for downstream use
            if not hasattr(state, "evidence_score"):
                state.evidence_score = evidence_score
            else:
                state.evidence_score = evidence_score
            set_span_status("ok")

        # ==================== TRUSTED TOOLS CHECK ====================
        # Check if trusted tools (calculator, pricing, team) were used successfully
        # These tools provide their own evidence and don't need KB sources
        trusted_tools_used = False
        trusted_tool_names = {"calculator", "get_pricing", "search_team_member", "get_team_members_list", "team_knowledge"}
        for step in state.steps:
            if step.action and hasattr(step.action, "tool_name"):
                if step.action.tool_name in trusted_tool_names and step.observation:
                    # Tool was used and produced output
                    if "error" not in step.observation.lower():
                        trusted_tools_used = True
                        logger.info(f"🧮 [Trusted Tool] {step.action.tool_name} used successfully, bypassing evidence check")
                        break

        # ==================== POLICY ENFORCEMENT ====================
        # If final_answer already exists but evidence is weak, override it
        # Skip evidence check for general tasks (translation, summarization, etc.)
        # Also skip if trusted tools were used successfully
        if state.final_answer and evidence_score < 0.3 and not state.skip_rag and not trusted_tools_used:
            logger.warning(
                f"🛡️ [Uncertainty] Overriding existing answer due to low evidence (Score: {evidence_score:.2f})"
            )
            state.final_answer = (
                "Mi dispiace, non ho trovato informazioni verificate sufficienti "
                "nei documenti ufficiali per rispondere alla tua domanda specifica. "
                "Posso aiutarti con altro?"
            )
        elif state.skip_rag and evidence_score < 0.3:
            logger.info("🏷️ [General Task] Skipping evidence check (skip_rag=True)")
        elif trusted_tools_used and evidence_score < 0.3:
            logger.info("🧮 [Trusted Tool] Skipping evidence check (trusted_tools_used=True)")

        # ==================== FINAL ANSWER GENERATION ====================
        # Generate final answer if not present
        if not state.final_answer and state.context_gathered:
            # POLICY ENFORCEMENT: Check evidence score before generating answer
            # Skip for general tasks (translation, summarization, etc.)
            # Also skip if trusted tools were used successfully
            if evidence_score < 0.3 and not state.skip_rag and not trusted_tools_used:
                # ABSTAIN: Skip LLM generation, return uncertainty message
                logger.warning(f"🛡️ [Uncertainty] Triggered ABSTAIN (Score: {evidence_score:.2f})")
                state.final_answer = (
                    "Mi dispiace, non ho trovato informazioni verificate sufficienti "
                    "nei documenti ufficiali per rispondere alla tua domanda specifica. "
                    "Posso aiutarti con altro?"
                )
            else:
                # Generate answer with optional warning for weak evidence
                context = "\n\n".join(state.context_gathered)
                warning_note = ""
                if evidence_score >= 0.3 and evidence_score < 0.6:
                    warning_note = (
                        "\n\nWARNING: Evidence is weak. Use precautionary language "
                        "(e.g., 'Based on limited information...', 'It appears that...'). "
                        "Do NOT be definitive."
                    )
                    logger.info(f"🛡️ [Uncertainty] Weak evidence detected (Score: {evidence_score:.2f}), adding warning")

                final_prompt = f"""
Based on the information gathered:
{context}
{warning_note}

Provide a final, comprehensive answer to: {query}
"""
                try:
                    state.final_answer, model_used_name, _, final_usage = await llm_gateway.send_message(
                        chat,
                        final_prompt,
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
                    accumulated_usage = accumulated_usage + final_usage
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                    logger.error("Failed to generate final answer", exc_info=True)
                    state.final_answer = "I apologize, but I couldn't generate a final answer based on the gathered information."
        elif not state.final_answer:
            # No context gathered at all
            # For general tasks, this is OK - generate answer without RAG context
            if state.skip_rag:
                logger.info("🏷️ [General Task] No context needed, proceeding with LLM generation")
                # Generate answer directly for general tasks
                try:
                    state.final_answer, model_used_name, _, final_usage = await llm_gateway.send_message(
                        chat,
                        f"Please answer this request: {query}",
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
                    accumulated_usage = accumulated_usage + final_usage
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                    logger.error("Failed to generate answer for general task", exc_info=True)
                    state.final_answer = "Mi dispiace, non sono riuscito a completare la richiesta. Riprova."
            else:
                logger.warning("🛡️ [Uncertainty] No context gathered, triggering ABSTAIN")
                state.final_answer = (
                    "Mi dispiace, non ho trovato informazioni verificate sufficienti "
                    "nei documenti ufficiali per rispondere alla tua domanda specifica. "
                    "Posso aiutarti con altro?"
                )

        # Filter out stub responses
        if state.final_answer and (
            "no further action needed" in state.final_answer.lower()
            or "observation: none" in state.final_answer.lower()
        ):
            logger.warning("⚠️ Detected stub response, generating fallback")
            state.final_answer = "Mi dispiace, non ho capito bene la tua richiesta. Potresti riformularla? Posso aiutarti con visti, aziende e leggi in Indonesia."

        # ==================== RESPONSE PIPELINE PROCESSING ====================
        # 🔍 TRACING: Response pipeline processing
        with trace_span("react.pipeline", {"has_pipeline": bool(self.response_pipeline)}):
            # Process response through pipeline: verify, clean, format citations
            if state.final_answer and self.response_pipeline:
                try:
                    # Prepare pipeline data
                    pipeline_data = {
                        "response": state.final_answer,
                        "query": query,
                        "context_chunks": state.context_gathered,
                        "sources": state.sources if hasattr(state, "sources") else [],
                    }

                    # Run through pipeline
                    processed = await self.response_pipeline.process(pipeline_data)
                    set_span_attribute("verification_score", processed.get("verification_score", 0))

                    # Handle verification failure (self-correction)
                    if processed.get("verification_score", 1.0) < 0.7 and state.context_gathered:
                        verification = processed.get("verification", {})
                        logger.warning(
                            f"🛡️ [Pipeline] REJECTED draft (Score: {verification.get('score', 0)}). "
                            f"Reason: {verification.get('reasoning', 'unknown')}"
                        )
                        add_span_event("pipeline.self_correction", {"reason": verification.get('reasoning', 'unknown')})

                        # SELF-CORRECTION
                        rephrase_prompt = f"""
SYSTEM: Your previous answer was REJECTED by the fact-checker.

REASON: {verification.get('reasoning', 'Insufficient evidence')}
MISSING/WRONG: {', '.join(verification.get('missing_citations', []))}

TASK: Rewrite the answer using ONLY the provided context.
Do not invent information. If the context is insufficient, admit it.
"""

                        # Retry with same model (disable function calling for final answer)
                        corrected_answer, _, _, correction_usage = await llm_gateway.send_message(
                            chat,
                            rephrase_prompt,
                            system_prompt,
                            tier=model_tier,
                            enable_function_calling=False,
                        )
                        accumulated_usage = accumulated_usage + correction_usage
                        logger.info("🛡️ [Pipeline] Self-correction applied.")

                        # Re-run pipeline on corrected answer
                        pipeline_data["response"] = corrected_answer
                        processed = await self.response_pipeline.process(pipeline_data)

                    # Update state with processed results
                    state.final_answer = processed["response"]
                    if "citations" in processed:
                        state.sources = processed["citations"]

                    logger.info(
                        f"✅ [Pipeline] Response processed: "
                        f"verification={processed.get('verification_status', 'unknown')}, "
                        f"citations={processed.get('citation_count', 0)}"
                    )
                    set_span_attribute("citation_count", processed.get("citation_count", 0))
                    set_span_status("ok")

                except (ValueError, RuntimeError, KeyError) as e:
                    logger.error(f"❌ [Pipeline] Processing failed: {e}", exc_info=True)
                    set_span_status("error", str(e))
                    # Fallback to basic post-processing
                    state.final_answer = post_process_response(state.final_answer, query)

        # Log total token usage for the entire ReAct loop
        logger.info(
            f"📊 [ReAct] Total token usage: {accumulated_usage.prompt_tokens} prompt + "
            f"{accumulated_usage.completion_tokens} completion = {accumulated_usage.total_tokens} total "
            f"(${accumulated_usage.cost_usd:.6f})"
        )

        return state, model_used_name, conversation_messages, accumulated_usage

    async def execute_react_loop_stream(
        self,
        state: AgentState,
        llm_gateway: Any,
        chat: Any,
        initial_prompt: str,
        system_prompt: str,
        query: str,
        user_id: str,
        model_tier: int,
        tool_execution_counter: dict,
        images: list[dict] | None = None,  # Vision images: [{"base64": ..., "name": ...}]
    ):
        """
        Execute the ReAct reasoning loop with streaming output.

        This is the streaming version of execute_react_loop that yields events
        as they occur during the reasoning process.

        Yields:
            Events with types: "thinking", "tool_call", "observation", "token"
        """
        # ==================== REACT LOOP ====================
        while state.current_step < state.max_steps:
            state.current_step += 1

            # Get model response
            try:
                if state.current_step == 1:
                    message = initial_prompt
                else:
                    last_observation = state.steps[-1].observation if state.steps else ""
                    message = f"Observation: {last_observation}\n\nContinue with your next thought or provide final answer."

                # Yield thinking event
                yield {"type": "thinking", "data": f"Step {state.current_step}: Processing..."}

                # Images only on first step (initial query)
                step_images = images if state.current_step == 1 else None
                text_response, model_used_name, response_obj, _ = await llm_gateway.send_message(
                    chat,
                    message,
                    system_prompt,
                    tier=model_tier,
                    enable_function_calling=True,
                    images=step_images,
                )

            except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                logger.error(f"Error during chat interaction: {e}", exc_info=True)
                yield {"type": "error", "data": {"message": str(e)}}
                break

            # Parse for tool calls
            tool_call = None

            # Check for native function call
            if hasattr(response_obj, "candidates") and response_obj.candidates:
                for candidate in response_obj.candidates:
                    if hasattr(candidate, "content") and candidate.content and hasattr(candidate.content, "parts") and candidate.content.parts:
                        for part in candidate.content.parts:
                            tool_call = parse_tool_call(part, use_native=True)
                            if tool_call:
                                break
                        if tool_call:
                            break

            # FIX Edge Case 2 (streaming): Validate tool call before using
            # Fallback to regex parsing if no valid native function call found
            if not is_valid_tool_call(tool_call):
                tool_call = parse_tool_call(text_response, use_native=False)
                if not is_valid_tool_call(tool_call):
                    tool_call = None

            if is_valid_tool_call(tool_call):
                # Yield tool call event
                yield {"type": "tool_call", "data": {"tool": tool_call.tool_name, "args": tool_call.arguments}}

                logger.info(f"🔧 [Agent Stream] Calling tool: {tool_call.tool_name}")
                tool_result, tool_duration = await execute_tool(
                    self.tool_map,
                    tool_call.tool_name,
                    tool_call.arguments,
                    user_id,
                    tool_execution_counter,
                )
                tool_call.execution_time = tool_duration

                # Handle citation from vector_search
                # FIX Edge Case 3 (streaming): Handle empty content from vector_search
                if tool_call.tool_name == "vector_search":
                    try:
                        parsed_result = json.loads(tool_result)
                        if isinstance(parsed_result, dict) and "sources" in parsed_result:
                            content = parsed_result.get("content", "")
                            new_sources = parsed_result.get("sources", [])

                            # Only extract content if it's meaningful (>10 chars after strip)
                            if content and len(content.strip()) > 10:
                                tool_result = content
                                if not hasattr(state, "sources"):
                                    state.sources = []
                                state.sources.extend(new_sources)
                                logger.info(
                                    f"📚 [Agent Stream] Collected {len(new_sources)} sources"
                                )
                            else:
                                # Empty content - log warning, still collect sources
                                logger.warning(
                                    f"⚠️ [Agent Stream] Vector search returned empty content "
                                    f"with {len(new_sources)} sources"
                                )
                                if new_sources:
                                    if not hasattr(state, "sources"):
                                        state.sources = []
                                    state.sources.extend(new_sources)
                    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                        pass

                # Handle image generation results
                if tool_call.tool_name == "generate_image":
                    try:
                        parsed_result = json.loads(tool_result)
                        if isinstance(parsed_result, dict) and parsed_result.get("success"):
                            # Extract image URL or base64 data
                            image_url = parsed_result.get("image_url") or parsed_result.get("image_data")
                            if image_url:
                                # Yield special image event for frontend rendering
                                yield {
                                    "type": "image",
                                    "data": {
                                        "url": image_url,
                                        "service": parsed_result.get("service", "unknown"),
                                        "prompt": parsed_result.get("message", ""),
                                    }
                                }
                                logger.info(f"🖼️ [Agent Stream] Image generated: {parsed_result.get('service')}")
                                # Store in state for final response
                                if not hasattr(state, "generated_images"):
                                    state.generated_images = []
                                state.generated_images.append(image_url)
                    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse generate_image result: {e}")

                tool_call.result = tool_result

                step = AgentStep(
                    step_number=state.current_step,
                    thought=text_response,
                    action=tool_call,
                    observation=tool_result,
                )
                state.steps.append(step)

                # FIX Edge Case 3 (streaming): Only append non-empty context
                if tool_result and len(tool_result.strip()) > 0:
                    state.context_gathered.append(tool_result)

                # Yield observation event
                yield {"type": "observation", "data": tool_result[:500] if len(tool_result) > 500 else tool_result}

                # Early exit optimization (only for simple queries)
                # Complex queries (business_complex, business_strategic) may need KG tool
                complex_intents = {"business_complex", "business_strategic", "devai_code"}
                is_complex_query = getattr(state, "intent_type", "simple") in complex_intents

                if (
                    tool_call.tool_name == "vector_search"
                    and len(tool_result) > 500
                    and "No relevant documents" not in tool_result
                    and not is_complex_query  # Allow complex queries to continue
                ):
                    logger.info("🚀 [Stream Early Exit] Sufficient context from retrieval.")
                    break
                elif is_complex_query and tool_call.tool_name == "vector_search":
                    logger.info("🔗 [Stream Complex Query] Allowing multi-tool reasoning (KG may be needed)")

            else:
                # No tool call - check for final answer
                if "Final Answer:" in text_response or state.current_step >= state.max_steps:
                    if "Final Answer:" in text_response:
                        state.final_answer = text_response.split("Final Answer:")[-1].strip()
                    else:
                        state.final_answer = text_response

                    step = AgentStep(
                        step_number=state.current_step, thought=text_response, is_final=True
                    )
                    state.steps.append(step)
                    break
                else:
                    step = AgentStep(step_number=state.current_step, thought=text_response)
                    state.steps.append(step)

        # ==================== EVIDENCE SCORE CALCULATION ====================
        # Calculate evidence score after ReAct loop
        sources = state.sources if hasattr(state, "sources") else None
        evidence_score = calculate_evidence_score(sources, state.context_gathered, query)
        logger.info(f"🛡️ [Uncertainty Stream] Evidence Score: {evidence_score:.2f}")
        # Store evidence_score in state for downstream use
        if not hasattr(state, "evidence_score"):
            state.evidence_score = evidence_score
        else:
            state.evidence_score = evidence_score

        # Yield evidence score event
        yield {"type": "evidence_score", "data": {"score": evidence_score}}

        # ==================== TRUSTED TOOLS CHECK ====================
        # Check if trusted tools (calculator, pricing, team) were used successfully
        # These tools provide their own evidence and don't need KB sources
        trusted_tools_used = False
        trusted_tool_names = {"calculator", "get_pricing", "search_team_member", "get_team_members_list", "team_knowledge"}
        logger.info(f"🔍 [Trusted Tools Debug] Checking {len(state.steps)} steps for trusted tools")
        for step in state.steps:
            tool_name = step.action.tool_name if step.action and hasattr(step.action, "tool_name") else "no_action"
            obs_preview = step.observation[:50] if step.observation else "None"
            logger.info(f"🔍 [Step Debug] tool={tool_name}, obs={obs_preview}")
            if step.action and hasattr(step.action, "tool_name"):
                if step.action.tool_name in trusted_tool_names and step.observation:
                    # Tool was used and produced output
                    if "error" not in step.observation.lower():
                        trusted_tools_used = True
                        logger.info(f"🧮 [Trusted Tool Stream] {step.action.tool_name} used successfully, bypassing evidence check")
                        break

        # ==================== POLICY ENFORCEMENT ====================
        # If final_answer already exists but evidence is weak, override it
        # Skip evidence check for general tasks (translation, summarization, etc.)
        # Also skip if trusted tools were used successfully
        if state.final_answer and evidence_score < 0.3 and not state.skip_rag and not trusted_tools_used:
            logger.warning(
                f"🛡️ [Uncertainty Stream] Overriding existing answer due to low evidence (Score: {evidence_score:.2f})"
            )
            state.final_answer = (
                "Mi dispiace, non ho trovato informazioni verificate sufficienti "
                "nei documenti ufficiali per rispondere alla tua domanda specifica. "
                "Posso aiutarti con altro?"
            )
        elif state.skip_rag and evidence_score < 0.3:
            logger.info("🏷️ [General Task Stream] Skipping evidence check (skip_rag=True)")
        elif trusted_tools_used and evidence_score < 0.3:
            logger.info("🧮 [Trusted Tool Stream] Skipping evidence check (trusted_tools_used=True)")

        # ==================== FINAL ANSWER GENERATION ====================
        if not state.final_answer and state.context_gathered:
            # POLICY ENFORCEMENT: Check evidence score before generating answer
            # Skip for general tasks (translation, summarization, etc.)
            # Also skip if trusted tools were used successfully
            if evidence_score < 0.3 and not state.skip_rag and not trusted_tools_used:
                # ABSTAIN: Skip LLM generation, return uncertainty message
                logger.warning(f"🛡️ [Uncertainty Stream] Triggered ABSTAIN (Score: {evidence_score:.2f})")
                state.final_answer = (
                    "Mi dispiace, non ho trovato informazioni verificate sufficienti "
                    "nei documenti ufficiali per rispondere alla tua domanda specifica. "
                    "Posso aiutarti con altro?"
                )
            else:
                # Generate answer with optional warning for weak evidence
                context = "\n\n".join(state.context_gathered)
                warning_note = ""
                if evidence_score >= 0.3 and evidence_score < 0.6:
                    warning_note = (
                        "\n\nWARNING: Evidence is weak. Use precautionary language "
                        "(e.g., 'Based on limited information...', 'It appears that...'). "
                        "Do NOT be definitive."
                    )
                    logger.info(f"🛡️ [Uncertainty Stream] Weak evidence detected (Score: {evidence_score:.2f}), adding warning")

                final_prompt = f"""
Based on the information gathered:
{context}
{warning_note}

Provide a final, comprehensive answer to: {query}
"""
                try:
                    state.final_answer, _, _, _ = await llm_gateway.send_message(
                        chat,
                        final_prompt,
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                    state.final_answer = "I apologize, but I couldn't generate a final answer."
        elif not state.final_answer:
            # No context gathered at all
            # For general tasks, this is OK - generate answer without RAG context
            if state.skip_rag:
                logger.info("🏷️ [General Task Stream] No context needed, proceeding with LLM generation")
                try:
                    state.final_answer, _, _, _ = await llm_gateway.send_message(
                        chat,
                        f"Please answer this request: {query}",
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                    logger.error("Failed to generate answer for general task", exc_info=True)
                    state.final_answer = "Mi dispiace, non sono riuscito a completare la richiesta. Riprova."
            else:
                logger.warning("🛡️ [Uncertainty Stream] No context gathered, triggering ABSTAIN")
                state.final_answer = (
                    "Mi dispiace, non ho trovato informazioni verificate sufficienti "
                    "nei documenti ufficiali per rispondere alla tua domanda specifica. "
                    "Posso aiutarti con altro?"
                )

        # Filter stub responses
        if state.final_answer and (
            "no further action needed" in state.final_answer.lower()
            or "observation: none" in state.final_answer.lower()
        ):
            state.final_answer = "Mi dispiace, non ho capito bene la tua richiesta. Potresti riformularla?"

        # Process through pipeline
        if state.final_answer and self.response_pipeline:
            try:
                pipeline_data = {
                    "response": state.final_answer,
                    "query": query,
                    "context_chunks": state.context_gathered,
                    "sources": state.sources if hasattr(state, "sources") else [],
                }
                processed = await self.response_pipeline.process(pipeline_data)
                state.final_answer = processed["response"]
                if "citations" in processed:
                    state.sources = processed["citations"]
            except (ValueError, RuntimeError, KeyError) as e:
                logger.error(f"❌ [Pipeline Stream] Processing failed: {e}")
                state.final_answer = post_process_response(state.final_answer, query)

        # Stream final answer token by token
        if state.final_answer:
            # Stream in chunks for better UX
            chunk_size = 20  # characters per chunk
            answer = state.final_answer
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i:i + chunk_size]
                yield {"type": "token", "data": chunk}

        # Yield sources if available
        if hasattr(state, "sources") and state.sources:
            yield {"type": "sources", "data": state.sources}


def detect_team_query(query: str) -> tuple[bool, str, str]:
    """
    Heuristically detect if a user query is asking about the company team.

    This helper is used by the AgenticRAGOrchestrator to optionally pre-route to the
    `team_knowledge` tool (when available) before running the full ReAct loop.

    Returns:
        (is_team_query, query_type, search_term)

    Supported query_type values (expected by the `team_knowledge` tool):
        - "list_all": request to list all team members / employees
        - "search_by_role": request by role/title (CEO, founder, tax, visa, etc.)
        - "search_by_name": request by person name ("Chi è Zainal?", "Tell me about Zero")
        - "search_by_email": request containing an email address
    """
    if not isinstance(query, str):
        return False, "", ""

    q = query.strip()
    if not q:
        return False, "", ""

    ql = q.lower()

    # 1) List-all team requests
    # NOTE: "dipendenti" alone is TOO BROAD - matches tax questions like "PPh 21 per i dipendenti"
    # Only match when explicitly asking about Bali Zero team
    list_all_markers = (
        "list all team",
        "list team",
        "team members",
        "membri del team",
        "lista team",
        "elenco team",
        "tutti i membri",
        "quanti dipendenti",  # "how many employees" - team context
        "vostri dipendenti",  # "your employees" - explicit team context
        f"i dipendenti {settings.COMPANY_NAME.lower()}",  # "company employees" - explicit
        "dipendenti del team",  # "team employees" - explicit
        "tutto lo staff",
        "vostro staff",
        "il vostro personale",
    )
    if any(marker in ql for marker in list_all_markers):
        return True, "list_all", ""

    # 2) Email lookup
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", q)
    if email_match:
        return True, "search_by_email", email_match.group(0)

    # 3) Role/title lookup - ONLY if user is explicitly asking about TEAM MEMBERS
    # Must have team context like "chi si occupa", "who handles", "team", "staff", etc.
    team_context_markers = (
        "chi si occupa",
        "chi gestisce",
        "chi segue",
        "chi è il",
        "chi è la",
        "who handles",
        "who manages",
        "who is the",
        "who is your",
        "your team",
        "nel team",
        "del team",
        "in the team",
        "team member",
        "staff member",
        "il vostro",
        "la vostra",
        "avete qualcuno",
        "c'è qualcuno",
        "esperto di",
        "specialist",
        "manager",
        "responsabile",
    )
    has_team_context = any(marker in ql for marker in team_context_markers)

    # Only check roles if there's explicit team context
    if has_team_context:
        role_map: dict[str, tuple[str, ...]] = {
            "ceo": ("ceo", "chief executive", "amministratore delegato", "a.d.", "ad "),
            "founder": ("founder", "cofounder", "co-founder", "fondatore", "fondatrice"),
            "tax": ("tax", "tasse", "fiscale", "fiscal", "pajak"),
            "visa": ("visa", "visti", "immigrazione", "immigration"),
            "setup": ("setup", "set up", "onboarding"),
            "legal": ("legal", "legale", "law", "avvocato"),
            "property": ("property", "immobiliare", "real estate"),
            "marketing": ("marketing", "social", "content"),
            "support": ("support", "assistenza", "customer care"),
        }
        for role, keywords in role_map.items():
            if any(k in ql for k in keywords):
                return True, "search_by_role", role

    # 4) Name lookup patterns (keep original casing from the original query)
    # Handle Italian keyboard variations: è, e, e', e' (curly apostrophe)
    # IMPORTANT: Patterns must be specific to avoid matching casual questions like
    # "conosci qualche ristorante?" which should NOT route to team_knowledge
    name_patterns = (
        # Italian "chi è" with all keyboard variations (accented, apostrophe, plain)
        r"\bchi\s*[eè]['']?\s*(?P<term>[^?.,!;:\n]{1,64})",
        # English patterns
        r"\bwho\s+is\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\btell\s+me\s+about\s+(?P<term>[^?.,!;:\n]{1,64})",
        # Italian info/dimmi/parlami patterns - ONLY for people (with team context)
        r"\binfo(?:rmazioni)?\s+su\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\bdimmi\s+(?:di\s+)?(?P<term>[^?.,!;:\n]{1,64})",
        r"\bparlami\s+di\s+(?P<term>[^?.,!;:\n]{1,64})",
        # "conosci" ONLY for people - exclude casual words like ristorante, posto, luogo, etc.
        # Pattern: "conosci [Name]" but NOT "conosci qualche/un/una [place]"
        r"\bconosci\s+(?!qualche|qualcuno|qualcosa|un\s|una\s|il\s|la\s|dei\s|delle\s|alcuni|alcune|ristorante|posto|luogo|bar|cafe|hotel)(?P<term>[A-Z][a-zA-Zàèéìòù\s]{1,30})",
    )
    for pat in name_patterns:
        m = re.search(pat, q, flags=re.IGNORECASE)
        if not m:
            continue
        raw_term = (m.group("term") or "").strip()
        raw_term = re.sub(
            r"^(il|lo|la|i|gli|le|the|a|an|un|uno|una)\s+",
            "",
            raw_term,
            flags=re.IGNORECASE,
        ).strip()
        raw_term = raw_term.strip("\"'“”")
        raw_term = " ".join(raw_term.split()[:3])  # keep short, stable search term
        if raw_term:
            return True, "search_by_name", raw_term

    # 5) Generic "who handles X" / "chi si occupa di X"
    handler_patterns = (
        r"\bchi\s+si\s+occupa\s+di\s+(?P<term>[^?.,!;:\n]{1,64})",
        r"\bwho\s+handles\s+(?P<term>[^?.,!;:\n]{1,64})",
    )
    for pat in handler_patterns:
        m = re.search(pat, q, flags=re.IGNORECASE)
        if not m:
            continue
        raw_term = (m.group("term") or "").strip().strip("\"'“”")
        raw_term = " ".join(raw_term.split()[:3])
        if raw_term:
            return True, "search_by_role", raw_term.lower()

    return False, "", ""
