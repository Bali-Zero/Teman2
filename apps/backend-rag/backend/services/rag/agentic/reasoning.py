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
import time
from typing import Any

from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from backend.app.core.constants import EvidenceScoreConstants
from backend.app.metrics import (
    abstain_decision_total,
    strict_abstain_critical_total,
    tier1_fallback_activated_total,
    tier1_fallback_failed_total,
    tier1_fallback_success_total,
    tier1_response_duration,
)
from backend.app.utils.tracing import (
    add_span_event,
    set_span_attribute,
    set_span_status,
    trace_span,
)
from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.query_helpers import detect_query_language
from backend.services.rag.agentic.reasoning_utils import (
    calculate_evidence_score,
    get_critical_domain_type,
    is_critical_domain,
    is_valid_tool_call,
)
from backend.services.rag.agentic.response_processor import post_process_response
from backend.services.rag.agentic.tool_executor import execute_tool, parse_tool_call
from backend.services.tools.definitions import AgentState, AgentStep

logger = logging.getLogger(__name__)

# Trusted tools bypass evidence scoring — tool output IS the evidence
_TRUSTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "calculator",
        "get_pricing",
        "team_knowledge",
        "timesheet",
        "vector_search",
    },
)


# NOTE: Deprecated local functions removed 2026-02-08 (System Audit).
# get_critical_domain_type, is_critical_domain, is_valid_tool_call,
# and calculate_evidence_score are now imported from reasoning_utils
# (see imports at top of file). This eliminates 350 lines of duplicated
# code and ensures a single source of truth for evidence scoring.


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
    item_count_penalty = min(
        len(context_items) / EvidenceScoreConstants.PREFERRED_CONTEXT_ITEMS, 1.0,
    )

    final_score = (
        avg_quality * EvidenceScoreConstants.CONTEXT_QUALITY_KEYWORD_WEIGHT
        + item_count_penalty * EvidenceScoreConstants.CONTEXT_QUALITY_COUNT_WEIGHT
    )

    return min(final_score, EvidenceScoreConstants.MAX_SCORE)


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
    ) -> None:
        """
        Initialize the ReAct reasoning engine.

        Args:
            tool_map: Dictionary mapping tool names to tool instances
            response_pipeline: Optional pipeline for response verification/cleaning
        """
        self.tool_map = tool_map
        self.response_pipeline = response_pipeline
        self._min_context_quality_score = EvidenceScoreConstants.ABSTAIN_THRESHOLD
        self._min_context_items = 1

    def _validate_context_quality(
        self,
        query: str,
        context_items: list[str],
    ) -> float:
        """Validate context quality and return score (0.0-1.0)."""
        return _validate_context_quality(query, context_items)

    def _get_localized_stub(self, key: str, language: str) -> str:
        """Get localized stub message for common scenarios."""
        stubs = {
            "abstain": {
                "ITALIAN": "Mi dispiace, non ho trovato informazioni rilevanti per questa domanda.",
                "INDONESIAN": "Maaf, saya tidak menemukan informasi yang relevan untuk pertanyaan ini.",
                "ENGLISH": "I'm sorry, I couldn't find relevant information for this question.",
            },
            "abstain_detailed": {
                "ITALIAN": (
                    "Per questa domanda specifica non ho informazioni verificate sufficienti nei documenti ufficiali.\n\n"
                    "Posso aiutarti con:\n"
                    "• Informazioni su visti e KITAS\n"
                    "• Setup aziendale (PT PMA)\n"
                    "• Questioni fiscali e legali\n"
                    "• Procedure e documentazione\n\n"
                    "Prova a riformulare la domanda o chiedi qualcosa di più specifico!"
                ),
                "INDONESIAN": (
                    "Untuk pertanyaan spesifik ini, saya tidak memiliki informasi terverifikasi yang cukup dalam dokumen resmi.\n\n"
                    "Saya dapat membantu Anda dengan:\n"
                    "• Informasi visa dan KITAS\n"
                    "• Pendirikan perusahaan (PT PMA)\n"
                    "• Masalah perpajakan dan hukum\n"
                    "• Prosedur dan dokumentasi\n\n"
                    "Coba reformulasikan pertanyaan atau tanyakan sesuatu yang lebih spesifik!"
                ),
                "ENGLISH": (
                    "For this specific question, I don't have sufficient verified information in the official documents.\n\n"
                    "I can help you with:\n"
                    "• Visa and KITAS information\n"
                    "• Company setup (PT PMA)\n"
                    "• Tax and legal matters\n"
                    "• Procedures and documentation\n\n"
                    "Try rephrasing the question or ask something more specific!"
                ),
            },
            "error": {
                "ITALIAN": "Mi dispiace, non sono riuscito a completare la richiesta. Riprova.",
                "INDONESIAN": "Maaf, saya tidak dapat menyelesaikan permintaan tersebut. Silakan coba lagi.",
                "ENGLISH": "I'm sorry, I couldn't complete the request. Please try again.",
            },
            "confused": {
                "ITALIAN": "Mi dispiace, non ho capito bene la tua richiesta. Potresti riformularla? Posso aiutarti con visti, aziende e leggi in Indonesia.",
                "INDONESIAN": "Maaf, saya tidak mengerti permintaan Anda. Bisakah Anda merumuskannya kembali? Saya dapat membantu Anda dengan visa, perusahaan, dan hukum di Indonesia.",
                "ENGLISH": "I'm sorry, I didn't quite understand your request. Could you rephrase it? I can help you with visas, companies, and laws in Indonesia.",
            },
        }
        # Fallback order: Requested Lang -> English -> Generic
        lang_stubs = stubs.get(key, {})
        return lang_stubs.get(
            language, lang_stubs.get("ENGLISH", "I'm sorry, I cannot fulfill this request."),
        )

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
        language = detect_query_language(query)
        conversation_messages = []
        model_used_name = "unknown"
        accumulated_usage = TokenUsage()  # Track total token usage across ReAct loop

        # ==================== REACT LOOP ====================
        # 🔍 TRACING: Span for entire ReAct loop
        with trace_span(
            "react.execute_loop",
            {
                "user_id": user_id,
                "max_steps": state.max_steps,
                "query_length": len(query),
            },
        ):
            while state.current_step < state.max_steps:
                state.current_step += 1

                # 🔍 TRACING: Span for each step
                with trace_span(
                    f"react.step.{state.current_step}",
                    {
                        "step_number": state.current_step,
                    },
                ):
                    # Get model response with automatic fallback and native function calling
                    try:
                        if state.current_step == 1:
                            message = initial_prompt
                        else:
                            # Continue conversation with observation
                            last_observation = state.steps[-1].observation if state.steps else ""
                            message = f"Observation: {last_observation}\n\nContinue with your next thought or provide final answer."

                        (
                            text_response,
                            model_used_name,
                            response_obj,
                            step_usage,
                        ) = await llm_gateway.send_message(
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
                        conversation_messages.append(
                            {"role": "assistant", "content": text_response},
                        )

                    except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                        logger.error(f"Error during chat interaction: {e}", exc_info=True)
                        set_span_status("error", str(e))
                        break

                    # Parse for tool calls - try native function calling first, then regex fallback
                    tool_calls = []

                    # Check for function call in response parts (native mode)
                    if hasattr(response_obj, "candidates") and response_obj.candidates:
                        for candidate in response_obj.candidates:
                            # FIX Edge Case 1: Proper None check for candidate.content
                            if (
                                hasattr(candidate, "content")
                                and candidate.content is not None
                                and hasattr(candidate.content, "parts")
                                and candidate.content.parts  # Ensure parts is not None/empty
                            ):
                                for part in candidate.content.parts:
                                    tc = parse_tool_call(part, use_native=True)
                                    if tc and is_valid_tool_call(tc):
                                        tool_calls.append(tc)

                                # If we found native calls, stop looking in this candidate
                                if tool_calls:
                                    logger.info(
                                        f"✅ [Native Function Call] Detected {len(tool_calls)} calls in response",
                                    )
                                    set_span_attribute("function_call_mode", "native")
                                    set_span_attribute("tool_calls_count", len(tool_calls))
                                    break

                    # Fallback to regex parsing if no valid native function call found
                    if not tool_calls:
                        tc = parse_tool_call(text_response, use_native=False)
                        if is_valid_tool_call(tc):
                            tool_calls.append(tc)
                            set_span_attribute("function_call_mode", "regex")
                            set_span_attribute("tool_calls_count", 1)
                        else:
                            # Neither native nor regex produced a valid tool call
                            pass

                    # EXECUTE TOOL CALLS (PARALLEL)
                    turn_observations = []

                    if tool_calls:
                        # Define async wrapper for parallel execution
                        async def _exec_tool_wrapper(tc, step_idx) -> Any:
                            try:
                                set_span_attribute("tool_name", tc.tool_name)
                                add_span_event(
                                    "tool.call",
                                    {"tool": tc.tool_name, "args": str(tc.arguments)[:200]},
                                )

                                logger.info(
                                    f"🔧 [Agent] Calling tool: {tc.tool_name} (Parallel)",
                                    extra={
                                        "context": {
                                            "tool": tc.tool_name,
                                            "arguments": tc.arguments,
                                            "step": state.current_step + step_idx,
                                            "user_id": user_id,
                                        },
                                    },
                                )
                                result, duration = await execute_tool(
                                    self.tool_map,
                                    tc.tool_name,
                                    tc.arguments,
                                    user_id,
                                    tool_execution_counter,
                                )
                                return tc, result, duration
                            except Exception as e:
                                logger.error(f"Error executing tool {tc.tool_name}: {e}")
                                return tc, f"Error: {str(e)}", 0.0

                        # Run all tools in parallel
                        import asyncio

                        results = await asyncio.gather(
                            *[_exec_tool_wrapper(tc, i) for i, tc in enumerate(tool_calls)],
                        )

                        # Process results
                        for i, (tool_call, tool_result, tool_duration) in enumerate(results):
                            # Store tool timing for metrics
                            tool_call.execution_time = tool_duration

                            # --- CITATION HANDLING ---
                            # FIX Edge Case 3: Handle empty content from vector_search
                            if tool_call.tool_name == "vector_search":
                                try:
                                    parsed_result = json.loads(tool_result)
                                    if (
                                        isinstance(parsed_result, dict)
                                        and "sources" in parsed_result
                                    ):
                                        content = parsed_result.get("content", "")
                                        new_sources = parsed_result.get("sources", [])

                                        # Only extract content if it's meaningful (>10 chars)
                                        if content and len(content.strip()) > 10:
                                            tool_result = content
                                            if not hasattr(state, "sources"):
                                                state.sources = []
                                            state.sources.extend(new_sources)
                                            set_span_attribute(
                                                "sources_collected", len(new_sources),
                                            )
                                        else:
                                            logger.warning(
                                                "⚠️ [Agent] Vector search empty content. Keeping original.",
                                            )
                                            if new_sources:
                                                if not hasattr(state, "sources"):
                                                    state.sources = []
                                                state.sources.extend(new_sources)
                                except json.JSONDecodeError as e:
                                    logger.debug(f"Vector search JSON decode skipped: {e}")
                                except (KeyError, ValueError, TypeError) as e:
                                    logger.warning(f"Failed to parse vector_search: {e}")

                            # Handle image generation
                            if tool_call.tool_name == "generate_image":
                                try:
                                    parsed_result = json.loads(tool_result)
                                    if isinstance(parsed_result, dict) and parsed_result.get(
                                        "success",
                                    ):
                                        image_url = parsed_result.get(
                                            "image_url",
                                        ) or parsed_result.get("image_data")
                                        if image_url:
                                            if not hasattr(state, "generated_images"):
                                                state.generated_images = []
                                            state.generated_images.append(image_url)
                                except Exception as e:
                                    logger.debug(f"Image URL parse skipped: {e}")

                            # Update tool call result
                            tool_call.result = tool_result

                            # Add Step
                            # For the first tool, use the actual thought. For others, indicate parallel exec.
                            step_thought = (
                                text_response
                                if i == 0
                                else f"(Parallel execution with {tool_calls[0].tool_name})"
                            )

                            step = AgentStep(
                                step_number=state.current_step + i,
                                thought=step_thought,
                                action=tool_call,
                                observation=tool_result,
                            )
                            state.steps.append(step)

                            # Add to accumulated context gathered
                            if tool_result and len(tool_result.strip()) > 0:
                                state.context_gathered.append(tool_result)

                            turn_observations.append(
                                f"Output from {tool_call.tool_name}: {tool_result}",
                            )

                        # Update step counter if we ran multiple tools
                        if len(tool_calls) > 1:
                            state.current_step += len(tool_calls) - 1

                        # Context Quality Validation (Aggregate)
                        if state.context_gathered:
                            quality_score = self._validate_context_quality(
                                query=query,
                                context_items=state.context_gathered,
                            )
                            if quality_score < self._min_context_quality_score:
                                logger.warning(
                                    f"⚠️ Context quality too low ({quality_score:.2f} < {self._min_context_quality_score})",
                                    extra={
                                        "context": {
                                            "quality_score": quality_score,
                                            "context_items": len(state.context_gathered),
                                            "step": state.current_step,
                                        },
                                    },
                                )
                                try:
                                    from backend.app.metrics import (
                                        reasoning_low_context_quality_total,
                                    )

                                    reasoning_low_context_quality_total.inc()
                                except ImportError:
                                    pass

                                # Try to gather more context if not at max steps
                                if state.current_step < state.max_steps:
                                    logger.info(
                                        "🔄 [Agent] Low quality context, continuing to gather more...",
                                    )
                                    continue  # Try another tool
                                # Last step - use what we have but warn
                                logger.warning(
                                    "Using low-quality context due to max steps reached",
                                )

                        # OPTIMIZATION: Early exit (only for simple queries)
                        # Complex queries (business_complex, business_strategic) may need KG tool
                        complex_intents = {"business_complex", "business_strategic", "devai_code"}
                        is_complex_query = (
                            getattr(state, "intent_type", "simple") in complex_intents
                        )

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
                        if is_complex_query and tool_call.tool_name == "vector_search":
                            logger.info(
                                "🔗 [Complex Query] Allowing multi-tool reasoning (KG may be needed)",
                            )

                        set_span_status("ok")

                    else:
                        # No tool call, assume final answer or just thought
                        set_span_attribute("has_tool_call", "false")
                        if (
                            "Final Answer:" in text_response
                            or state.current_step >= state.max_steps
                        ):
                            if "Final Answer:" in text_response:
                                state.final_answer = text_response.split("Final Answer:")[
                                    -1
                                ].strip()
                            else:
                                state.final_answer = text_response

                            step = AgentStep(
                                step_number=state.current_step, thought=text_response, is_final=True,
                            )
                            state.steps.append(step)
                            set_span_attribute("is_final_answer", "true")
                            set_span_status("ok")
                            break
                        # Just a thought step
                        step = AgentStep(step_number=state.current_step, thought=text_response)
                        state.steps.append(step)
                        set_span_status("ok")

            # Set final loop attributes
            set_span_attribute("total_steps", state.current_step)
            set_span_attribute("tools_executed", tool_execution_counter.get("count", 0))

        # ==================== TRUSTED TOOLS CHECK ====================
        # Check if trusted tools (calculator, pricing, team) were used successfully
        # These tools provide their own evidence and don't need KB sources
        # MOVED BEFORE EVIDENCE SCORE: If trusted tools used, skip keyword-based scoring
        trusted_tools_used = False
        trusted_tool_names = _TRUSTED_TOOL_NAMES
        for step in state.steps:
            if step.action and hasattr(step.action, "tool_name"):
                if step.action.tool_name in trusted_tool_names and step.observation:
                    # Tool was used and produced output
                    obs_lower = step.observation.lower()
                    # Check for actual content, not "no results" or errors
                    has_content = (
                        "error" not in obs_lower
                        and "not found" not in obs_lower
                        and "no relevant" not in obs_lower
                        and len(step.observation) > 50  # Must have substantial content
                    )
                    if has_content:
                        trusted_tools_used = True
                        logger.info(
                            f"🔧 [Trusted Tools] {step.action.tool_name} used successfully "
                            f"(obs_len={len(step.observation)}), bypassing keyword evidence check",
                        )
                        break

        # ==================== EVIDENCE SCORE CALCULATION ====================
        # 🔍 TRACING: Evidence score calculation
        sources_count = (
            len(state.sources) if hasattr(state, "sources") and state.sources is not None else 0
        )
        with trace_span(
            "react.evidence_score",
            {"sources_count": sources_count, "trusted_tools_used": trusted_tools_used},
        ):
            # If trusted tools used successfully, use high evidence score directly
            if trusted_tools_used:
                evidence_score = 0.85  # High confidence from trusted tool
                logger.info(f"🛡️ [Evidence] Trusted tools used: score={evidence_score:.2f}")
            else:
                # Calculate evidence score from sources and context (keyword-based)
                sources = state.sources if hasattr(state, "sources") else None
                evidence_score = calculate_evidence_score(sources, state.context_gathered, query)
                logger.info(f"🛡️ [Evidence] Keyword-based score: {evidence_score:.2f}")

            set_span_attribute("evidence_score", evidence_score)
            set_span_attribute("trusted_tools_used", trusted_tools_used)
            # Store evidence_score in state for downstream use
            if not hasattr(state, "evidence_score"):
                state.evidence_score = evidence_score
            else:
                state.evidence_score = evidence_score
            set_span_status("ok")

        # ==================== ANSWER CONTENT CHECK ====================
        # If the LLM produced an answer with specific factual data (prices, numbers),
        # it likely used tool results or system context. Don't override it.
        if not trusted_tools_used and state.final_answer:
            answer_lower = state.final_answer.lower()
            has_pricing_data = any(
                marker in answer_lower
                for marker in [
                    "rp ",
                    "rp.",
                    "idr ",
                    "usd ",
                    "$",
                    "20.000.000",
                    "15.000.000",
                    "10.000.000",
                    "5.000.000",
                    "juta",
                    "million",
                ]
            )
            if has_pricing_data:
                trusted_tools_used = True
                logger.info(
                    "🔍 [Answer Content] Final answer contains pricing data, "
                    "bypassing evidence check",
                )

        # ==================== POLICY ENFORCEMENT ====================
        # If final_answer already exists but evidence is weak, override it
        # Skip evidence check for general tasks (translation, summarization, etc.)
        # Also skip if trusted tools were used successfully
        #
        # FIX: Also skip if LLM had tools available — it was given the opportunity
        # to call tools and chose to answer directly. Trust its judgment.
        has_tools = hasattr(llm_gateway, "_gemini_tools") and bool(llm_gateway._gemini_tools)
        if has_tools and state.final_answer:
            logger.info(
                f"🔍 [Tools Available] LLM had {len(llm_gateway._gemini_tools)} tools "
                f"and produced answer, skipping strict evidence check",
            )
            trusted_tools_used = True

        state.trusted_tools_used = trusted_tools_used

        if (
            state.final_answer
            and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD
            and not state.skip_rag
            and not trusted_tools_used
        ):
            # TIER 1 vs STRICT ABSTAIN logic
            intent_type = getattr(state, "intent_type", "simple")
            is_critical = is_critical_domain(query, intent_type)

            if is_critical:
                domain_type = get_critical_domain_type(query)
                logger.warning(
                    f"🛡️ [Uncertainty] Overriding existing answer due to low evidence for critical domain "
                    f"(Score: {evidence_score:.2f}, Intent: {intent_type}, Domain: {domain_type})",
                )
                strict_abstain_critical_total.labels(
                    intent_type=intent_type, domain_type=domain_type,
                ).inc()
                abstain_decision_total.labels(decision_type="strict_abstain").inc()
                # Use localized ABSTAIN message
                state.final_answer = self._get_localized_stub("abstain_detailed", language)
            else:
                # TIER 1: Regenerate with Transparency Protocol
                has_context = bool(state.context_gathered)
                tier1_fallback_activated_total.labels(
                    intent_type=intent_type, has_context=str(has_context).lower(),
                ).inc()
                logger.info(
                    f"🌊 [Tier 1] Regenerating answer with Transparency Protocol "
                    f"(Score: {evidence_score:.2f}, Intent: {intent_type})",
                )
                transparency_instruction = """
[SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL]
CRITICAL INSTRUCTION: The internal search for verified documents yielded low or no results.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with: "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
"""

                context = "\n\n".join(state.context_gathered) if state.context_gathered else ""
                newline = "\n"
                context_section = (
                    f"Retrieved Context (limited):{newline}{context}"
                    if context
                    else "No verified documents found in internal knowledge base."
                )
                final_prompt = f"""
{transparency_instruction}

User Query: {query}
{context_section}

Provide a helpful answer using your general knowledge, but clearly state that this is not verified internal information.
"""

                tier1_start_time = time.time()
                try:
                    (
                        state.final_answer,
                        model_used_name,
                        _,
                        final_usage,
                    ) = await llm_gateway.send_message(
                        chat,
                        final_prompt,
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
                    accumulated_usage = accumulated_usage + final_usage
                    tier1_duration = time.time() - tier1_start_time
                    tier1_response_duration.observe(tier1_duration)
                    tier1_fallback_success_total.labels(intent_type=intent_type).inc()
                    logger.info(
                        f"🌊 [Tier 1] Answer regenerated with General Intelligence (duration: {tier1_duration:.2f}s)",
                    )
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                    tier1_duration = time.time() - tier1_start_time
                    tier1_response_duration.observe(tier1_duration)
                    error_type = type(e).__name__
                    tier1_fallback_failed_total.labels(
                        intent_type=intent_type, error_type=error_type,
                    ).inc()
                    logger.error(f"Failed to regenerate Tier 1 answer: {error_type}", exc_info=True)
                    state.final_answer = self._get_localized_stub("abstain", language)
        elif state.skip_rag and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD:
            logger.info("🏷️ [General Task] Skipping evidence check (skip_rag=True)")
        elif trusted_tools_used and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD:
            logger.info("🧮 [Trusted Tool] Skipping evidence check (trusted_tools_used=True)")

        # ==================== FINAL ANSWER GENERATION ====================
        # Generate final answer if not present
        if not state.final_answer and state.context_gathered:
            # POLICY ENFORCEMENT: Check evidence score before generating answer
            # Skip for general tasks (translation, summarization, etc.)
            # Also skip if trusted tools were used successfully
            if (
                evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD
                and not state.skip_rag
                and not trusted_tools_used
            ):
                # TIER 1: Fluid Fallback (General Intelligence) vs STRICT ABSTAIN
                intent_type = getattr(state, "intent_type", "simple")
                is_critical = is_critical_domain(query, intent_type)

                if is_critical:
                    # CRITICAL DOMAIN: Strict ABSTAIN (no fallback to general knowledge)
                    domain_type = get_critical_domain_type(query)
                    logger.warning(
                        f"🛡️ [Uncertainty] Triggered STRICT ABSTAIN for critical domain "
                        f"(Score: {evidence_score:.2f}, Intent: {intent_type}, Domain: {domain_type})",
                    )
                    strict_abstain_critical_total.labels(
                        intent_type=intent_type, domain_type=domain_type,
                    ).inc()
                    abstain_decision_total.labels(decision_type="strict_abstain").inc()
                    state.final_answer = (
                        "Per questa domanda specifica non ho informazioni verificate sufficienti nei documenti ufficiali. "
                        "Posso aiutarti con:\n"
                        "• Informazioni su visti e KITAS\n"
                        "• Setup aziendale (PT PMA)\n"
                        "• Questioni fiscali e legali\n"
                        "• Procedure e documentazione\n\n"
                        "Prova a riformulare la domanda o chiedi qualcosa di più specifico!"
                    )
                else:
                    # TIER 1: Fluid Fallback - Use General Intelligence with Transparency Protocol
                    has_context = bool(state.context_gathered)
                    tier1_fallback_activated_total.labels(
                        intent_type=intent_type, has_context=str(has_context).lower(),
                    ).inc()
                    abstain_decision_total.labels(decision_type="tier1_fallback").inc()
                    logger.info(
                        f"🌊 [Tier 1] Low evidence ({evidence_score:.2f}) for non-critical query, "
                        f"using General Intelligence fallback",
                    )
                    # Inject Transparency Protocol instruction into prompt
                    transparency_instruction = """
[SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL]
CRITICAL INSTRUCTION: The internal search for verified documents yielded low or no results.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with this EXACT phrase (translated to user's language):
   "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
5. If the question is about Bali Zero services, pricing, or specific procedures, suggest contacting the team for verified information.
"""

                    # Use minimal context (what we have) but allow LLM to use general knowledge
                    context = "\n\n".join(state.context_gathered) if state.context_gathered else ""
                    context_section = (
                        f"Retrieved Context (limited):\n{context}"
                        if context
                        else "No verified documents found in internal knowledge base."
                    )

                    final_prompt = f"""
{transparency_instruction}

User Query: {query}
{context_section}

Provide a helpful answer using your general knowledge, but clearly state that this is not verified internal information.
"""

                    tier1_start_time = time.time()
                    try:
                        (
                            state.final_answer,
                            model_used_name,
                            _,
                            final_usage,
                        ) = await llm_gateway.send_message(
                            chat,
                            final_prompt,
                            system_prompt,
                            tier=model_tier,
                            enable_function_calling=False,
                        )
                        accumulated_usage = accumulated_usage + final_usage
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        tier1_fallback_success_total.labels(intent_type=intent_type).inc()
                        logger.info(
                            f"🌊 [Tier 1] General Intelligence response generated (duration: {tier1_duration:.2f}s)",
                        )
                    except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        error_type = type(e).__name__
                        tier1_fallback_failed_total.labels(
                            intent_type=intent_type, error_type=error_type,
                        ).inc()
                        logger.error(
                            f"Failed to generate Tier 1 fallback answer: {error_type}",
                            exc_info=True,
                        )
                        # Fallback to ABSTAIN if LLM fails
                        state.final_answer = self._get_localized_stub("abstain", language)
            else:
                # Generate answer with optional warning for weak evidence
                context = "\n\n".join(state.context_gathered)
                warning_note = ""
                if (
                    evidence_score >= EvidenceScoreConstants.ABSTAIN_THRESHOLD
                    and evidence_score < 0.5
                ):
                    warning_note = (
                        "\n\nWARNING: Evidence is moderate. Use precautionary language "
                        "(e.g., 'Based on available information...', 'It appears that...'). "
                        "Still provide a helpful answer, but acknowledge limitations if needed."
                    )
                    logger.info(
                        f"🛡️ [Uncertainty] Moderate evidence detected (Score: {evidence_score:.2f}), adding warning",
                    )

                final_prompt = f"""
Based on the information gathered:
{context}
{warning_note}

Provide a final, comprehensive answer to: {query}

IMPORTANT: After your answer, naturally suggest 1-2 related topics or next steps that might be helpful.
Examples: "Vuoi sapere anche quanto costa?" / "Ti interessa anche il processo completo?" / "Posso spiegarti anche i requisiti documentali"
Make it feel natural and helpful, not forced.
"""
                try:
                    (
                        state.final_answer,
                        model_used_name,
                        _,
                        final_usage,
                    ) = await llm_gateway.send_message(
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
                    (
                        state.final_answer,
                        model_used_name,
                        _,
                        final_usage,
                    ) = await llm_gateway.send_message(
                        chat,
                        f"Please answer this request: {query}",
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
                    accumulated_usage = accumulated_usage + final_usage
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                    logger.error("Failed to generate answer for general task", exc_info=True)
                    state.final_answer = self._get_localized_stub("error", language)
            else:
                # No context gathered - apply same Tier 1 vs ABSTAIN logic
                intent_type = getattr(state, "intent_type", "simple")
                is_critical = is_critical_domain(query, intent_type)

                if is_critical:
                    domain_type = get_critical_domain_type(query)
                    logger.warning(
                        f"🛡️ [Uncertainty] No context gathered for critical domain, triggering ABSTAIN (Domain: {domain_type})",
                    )
                    strict_abstain_critical_total.labels(
                        intent_type=intent_type, domain_type=domain_type,
                    ).inc()
                    abstain_decision_total.labels(decision_type="strict_abstain").inc()
                    state.final_answer = self._get_localized_stub("abstain", language)
                else:
                    # TIER 1: No context but non-critical - use General Intelligence
                    tier1_fallback_activated_total.labels(
                        intent_type=intent_type, has_context="false",
                    ).inc()
                    abstain_decision_total.labels(decision_type="tier1_fallback").inc()
                    logger.info(
                        "🌊 [Tier 1] No context gathered for non-critical query, "
                        "using General Intelligence fallback",
                    )
                    transparency_instruction = """
[SYSTEM NOTICE: NO INTERNAL DOCUMENTS FOUND]
CRITICAL INSTRUCTION: No verified documents were found in the internal knowledge base.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with: "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
"""

                    final_prompt = f"""
{transparency_instruction}

User Query: {query}

Provide a helpful answer using your general knowledge, but clearly state that this is not verified internal information.
"""

                    tier1_start_time = time.time()
                    try:
                        (
                            state.final_answer,
                            model_used_name,
                            _,
                            final_usage,
                        ) = await llm_gateway.send_message(
                            chat,
                            final_prompt,
                            system_prompt,
                            tier=model_tier,
                            enable_function_calling=False,
                        )
                        accumulated_usage = accumulated_usage + final_usage
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        tier1_fallback_success_total.labels(intent_type=intent_type).inc()
                        logger.info(
                            f"🌊 [Tier 1] General Intelligence response generated (no context, duration: {tier1_duration:.2f}s)",
                        )
                    except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        error_type = type(e).__name__
                        tier1_fallback_failed_total.labels(
                            intent_type=intent_type, error_type=error_type,
                        ).inc()
                        logger.error(
                            f"Failed to generate Tier 1 fallback answer: {error_type}",
                            exc_info=True,
                        )
                        state.final_answer = self._get_localized_stub("abstain", language)

        # Filter out stub responses
        if state.final_answer and (
            "no further action needed" in state.final_answer.lower()
            or "observation: none" in state.final_answer.lower()
        ):
            logger.warning("⚠️ Detected stub response, generating fallback")
            state.final_answer = self._get_localized_stub("confused", language)

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
                            f"Reason: {verification.get('reasoning', 'unknown')}",
                        )
                        add_span_event(
                            "pipeline.self_correction",
                            {"reason": verification.get("reasoning", "unknown")},
                        )

                        # SELF-CORRECTION
                        rephrase_prompt = f"""
SYSTEM: Your previous answer was REJECTED by the fact-checker.

REASON: {verification.get("reasoning", "Insufficient evidence")}
MISSING/WRONG: {", ".join(verification.get("missing_citations", []))}

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
                        f"citations={processed.get('citation_count', 0)}",
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
            f"(${accumulated_usage.cost_usd:.6f})",
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
    ) -> None:
        """
        Execute the ReAct reasoning loop with streaming output.

        This is the streaming version of execute_react_loop that yields events
        as they occur during the reasoning process.

        Yields:
            Events with types: "thinking", "tool_call", "observation", "token"
        """
        language = detect_query_language(query)
        # ==================== REACT LOOP ====================
        while state.current_step < state.max_steps:
            state.current_step += 1

            # Get model response
            try:
                if state.current_step == 1:
                    message = initial_prompt
                else:
                    # CRITICAL: Include original query context to maintain conversation continuity
                    last_observation = state.steps[-1].observation if state.steps else ""
                    # Include original query to help Gemini maintain context
                    message = f"Original user query: {query}\n\nObservation: {last_observation}\n\nContinue with your next thought or provide final answer. Remember the conversation context from earlier messages."

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
                    if (
                        hasattr(candidate, "content")
                        and candidate.content
                        and hasattr(candidate.content, "parts")
                        and candidate.content.parts
                    ):
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
                yield {
                    "type": "tool_call",
                    "data": {"tool": tool_call.tool_name, "args": tool_call.arguments},
                }

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
                                    f"📚 [Agent Stream] Collected {len(new_sources)} sources",
                                )
                            else:
                                # Empty content - log warning, still collect sources
                                logger.warning(
                                    f"⚠️ [Agent Stream] Vector search returned empty content "
                                    f"with {len(new_sources)} sources",
                                )
                                if new_sources:
                                    if not hasattr(state, "sources"):
                                        state.sources = []
                                    state.sources.extend(new_sources)
                    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                        logger.debug(f"Streaming vector search parse skipped: {e}")

                # Handle image generation results
                if tool_call.tool_name == "generate_image":
                    try:
                        parsed_result = json.loads(tool_result)
                        if isinstance(parsed_result, dict) and parsed_result.get("success"):
                            # Extract image URL or base64 data
                            image_url = parsed_result.get("image_url") or parsed_result.get(
                                "image_data",
                            )
                            if image_url:
                                # Yield special image event for frontend rendering
                                yield {
                                    "type": "image",
                                    "data": {
                                        "url": image_url,
                                        "service": parsed_result.get("service", "unknown"),
                                        "prompt": parsed_result.get("message", ""),
                                    },
                                }
                                logger.info(
                                    f"🖼️ [Agent Stream] Image generated: {parsed_result.get('service')}",
                                )
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
                yield {
                    "type": "observation",
                    "data": tool_result[:500] if len(tool_result) > 500 else tool_result,
                }

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
                    logger.info(
                        "🔗 [Stream Complex Query] Allowing multi-tool reasoning (KG may be needed)",
                    )

            else:
                # No tool call - check for final answer
                if "Final Answer:" in text_response or state.current_step >= state.max_steps:
                    if "Final Answer:" in text_response:
                        state.final_answer = text_response.split("Final Answer:")[-1].strip()
                    else:
                        state.final_answer = text_response

                    step = AgentStep(
                        step_number=state.current_step, thought=text_response, is_final=True,
                    )
                    state.steps.append(step)
                    break
                else:
                    step = AgentStep(step_number=state.current_step, thought=text_response)
                    state.steps.append(step)

        # ==================== TRUSTED TOOLS CHECK (BEFORE EVIDENCE) ====================
        # Check if trusted tools were used successfully BEFORE calculating evidence score
        # This ensures RAG-native behavior: tool success = high evidence
        trusted_tools_used = False
        trusted_tool_names = _TRUSTED_TOOL_NAMES
        for step in state.steps:
            if step.action and hasattr(step.action, "tool_name"):
                if step.action.tool_name in trusted_tool_names and step.observation:
                    obs_lower = step.observation.lower()
                    has_content = (
                        "error" not in obs_lower
                        and "not found" not in obs_lower
                        and "no relevant" not in obs_lower
                        and len(step.observation) > 50
                    )
                    if has_content:
                        trusted_tools_used = True
                        logger.info(
                            f"🔧 [Trusted Tools - Stream] {step.action.tool_name} used successfully "
                            f"(obs_len={len(step.observation)}), using high evidence score",
                        )
                        break

        # ==================== EVIDENCE SCORE CALCULATION ====================
        # RAG-NATIVE: If trusted tools used, use high evidence score directly
        if trusted_tools_used:
            evidence_score = 0.85  # High confidence from trusted tool
            logger.info(f"🛡️ [Evidence Stream] Trusted tools used: score={evidence_score:.2f}")
        else:
            # Calculate evidence score from sources and context (keyword-based)
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

        # ==================== TRUSTED TOOLS FALLBACK CHECK ====================
        # Also check context_gathered for tool output patterns (fallback)
        if not trusted_tools_used and state.context_gathered:
            context_text = " ".join(state.context_gathered).lower()
            # Check for pricing tool output patterns
            if any(
                marker in context_text
                for marker in [
                    "bali_zero_official_prices",
                    "service_type",
                    "total_price",
                    "pricing",
                    "rp ",
                    "idr ",
                    "harga",
                ]
            ):
                trusted_tools_used = True
                logger.info("🔍 [Trusted Tools - Stream] Pricing data found in context_gathered")
            # Check for team knowledge tool output
            elif any(
                marker in context_text
                for marker in [
                    "team_member",
                    "specialties",
                    "role:",
                    "department",
                ]
            ):
                trusted_tools_used = True
                logger.info("🔍 [Trusted Tools - Stream] Team data found in context_gathered")
            # Check for KG tool output
            elif any(
                marker in context_text
                for marker in [
                    "subgraph",
                    "nodes,",
                    "edges)",
                    "focus]",
                    "knowledge graph",
                ]
            ):
                trusted_tools_used = True
                logger.info(
                    "🔍 [Trusted Tools] KG data found in context_gathered, bypassing evidence check",
                )

        # FIX: Also bypass evidence check when context_gathered has substantial content
        # from ANY tool. If the ReAct loop gathered context, the LLM had evidence to work with.
        if not trusted_tools_used and state.context_gathered:
            total_context_len = sum(len(c) for c in state.context_gathered)
            if total_context_len > 200:
                trusted_tools_used = True
                logger.info(
                    f"🔍 [Context Evidence] Substantial context gathered ({total_context_len} chars), "
                    f"bypassing strict evidence check",
                )

        # ==================== ANSWER CONTENT CHECK ====================
        # If the LLM produced an answer with specific factual data (prices, numbers),
        # it likely used tool results or system context. Don't override it.
        if not trusted_tools_used and state.final_answer:
            answer_lower = state.final_answer.lower()
            has_pricing_data = any(
                marker in answer_lower
                for marker in [
                    "rp ",
                    "rp.",
                    "idr ",
                    "usd ",
                    "$",
                    "20.000.000",
                    "15.000.000",
                    "10.000.000",
                    "5.000.000",
                    "juta",
                    "million",
                ]
            )
            if has_pricing_data:
                trusted_tools_used = True
                logger.info(
                    "🔍 [Answer Content] Final answer contains pricing data, "
                    "bypassing evidence check",
                )

        # ==================== POLICY ENFORCEMENT ====================
        # If final_answer already exists but evidence is weak, override it
        # Skip evidence check for general tasks (translation, summarization, etc.)
        # Also skip if trusted tools were used successfully
        #
        # FIX: Also skip if LLM had tools available — it was given the opportunity
        # to call tools and chose to answer directly. Trust its judgment.
        has_tools = hasattr(llm_gateway, "_gemini_tools") and bool(llm_gateway._gemini_tools)
        if has_tools and state.final_answer:
            logger.info(
                f"🔍 [Tools Available] LLM had {len(llm_gateway._gemini_tools)} tools "
                f"and produced answer, skipping strict evidence check",
            )
            trusted_tools_used = True

        state.trusted_tools_used = trusted_tools_used

        if (
            state.final_answer
            and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD
            and not state.skip_rag
            and not trusted_tools_used
        ):
            # TIER 1 vs STRICT ABSTAIN logic
            intent_type = getattr(state, "intent_type", "simple")
            is_critical = is_critical_domain(query, intent_type)

            if is_critical:
                domain_type = get_critical_domain_type(query)
                logger.warning(
                    f"🛡️ [Uncertainty Stream] Overriding existing answer due to low evidence for critical domain "
                    f"(Score: {evidence_score:.2f}, Intent: {intent_type}, Domain: {domain_type})",
                )
                strict_abstain_critical_total.labels(
                    intent_type=intent_type, domain_type=domain_type,
                ).inc()
                abstain_decision_total.labels(decision_type="strict_abstain").inc()
                state.final_answer = self._get_localized_stub("abstain", language)
            else:
                # TIER 1: Regenerate with Transparency Protocol (streaming)
                has_context = bool(state.context_gathered)
                tier1_fallback_activated_total.labels(
                    intent_type=intent_type, has_context=str(has_context).lower(),
                ).inc()
                abstain_decision_total.labels(decision_type="tier1_fallback").inc()
                logger.info(
                    f"🌊 [Tier 1 Stream] Regenerating answer with Transparency Protocol "
                    f"(Score: {evidence_score:.2f}, Intent: {intent_type})",
                )
                transparency_instruction = """
[SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL]
CRITICAL INSTRUCTION: The internal search for verified documents yielded low or no results.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with: "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
"""

                context = "\n\n".join(state.context_gathered) if state.context_gathered else ""
                context_section = (
                    f"Retrieved Context (limited):\n{context}"
                    if context
                    else "No verified documents found in internal knowledge base."
                )
                final_prompt = f"""
{transparency_instruction}

User Query: {query}
{context_section}

Provide a helpful answer using your general knowledge, but clearly state that this is not verified internal information.
"""

                tier1_start_time = time.time()
                try:
                    state.final_answer, _, _, _ = await llm_gateway.send_message(
                        chat,
                        final_prompt,
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
                    tier1_duration = time.time() - tier1_start_time
                    tier1_response_duration.observe(tier1_duration)
                    tier1_fallback_success_total.labels(intent_type=intent_type).inc()
                    logger.info(
                        f"🌊 [Tier 1 Stream] Answer regenerated with General Intelligence (duration: {tier1_duration:.2f}s)",
                    )
                except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                    tier1_duration = time.time() - tier1_start_time
                    tier1_response_duration.observe(tier1_duration)
                    error_type = type(e).__name__
                    tier1_fallback_failed_total.labels(
                        intent_type=intent_type, error_type=error_type,
                    ).inc()
                    logger.error(f"Failed to regenerate Tier 1 answer: {error_type}", exc_info=True)
                    state.final_answer = self._get_localized_stub("abstain", language)
        elif state.skip_rag and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD:
            logger.info("🏷️ [General Task Stream] Skipping evidence check (skip_rag=True)")
        elif trusted_tools_used and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD:
            logger.info(
                "🧮 [Trusted Tool Stream] Skipping evidence check (trusted_tools_used=True)",
            )

        # ==================== FINAL ANSWER GENERATION ====================
        if not state.final_answer and state.context_gathered:
            # POLICY ENFORCEMENT: Check evidence score before generating answer
            # Skip for general tasks (translation, summarization, etc.)
            # Also skip if trusted tools were used successfully
            if (
                evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD
                and not state.skip_rag
                and not trusted_tools_used
            ):
                # TIER 1: Fluid Fallback (General Intelligence) vs STRICT ABSTAIN
                intent_type = getattr(state, "intent_type", "simple")
                is_critical = is_critical_domain(query, intent_type)

                if is_critical:
                    # CRITICAL DOMAIN: Strict ABSTAIN (no fallback to general knowledge)
                    domain_type = get_critical_domain_type(query)
                    logger.warning(
                        f"🛡️ [Uncertainty Stream] Triggered STRICT ABSTAIN for critical domain "
                        f"(Score: {evidence_score:.2f}, Intent: {intent_type}, Domain: {domain_type})",
                    )
                    strict_abstain_critical_total.labels(
                        intent_type=intent_type, domain_type=domain_type,
                    ).inc()
                    abstain_decision_total.labels(decision_type="strict_abstain").inc()
                    state.final_answer = (
                        "Per questa domanda specifica non ho informazioni verificate sufficienti nei documenti ufficiali. "
                        "Posso aiutarti con:\n"
                        "• Informazioni su visti e KITAS\n"
                        "• Setup aziendale (PT PMA)\n"
                        "• Questioni fiscali e legali\n"
                        "• Procedure e documentazione\n\n"
                        "Prova a riformulare la domanda o chiedi qualcosa di più specifico!"
                    )
                else:
                    # TIER 1: Fluid Fallback - Use General Intelligence with Transparency Protocol
                    has_context = bool(state.context_gathered)
                    tier1_fallback_activated_total.labels(
                        intent_type=intent_type, has_context=str(has_context).lower(),
                    ).inc()
                    abstain_decision_total.labels(decision_type="tier1_fallback").inc()
                    logger.info(
                        f"🌊 [Tier 1 Stream] Low evidence ({evidence_score:.2f}) for non-critical query, "
                        f"using General Intelligence fallback",
                    )
                    # Inject Transparency Protocol instruction into prompt
                    transparency_instruction = """
[SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL]
CRITICAL INSTRUCTION: The internal search for verified documents yielded low or no results.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with this EXACT phrase (translated to user's language):
   "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
5. If the question is about Bali Zero services, pricing, or specific procedures, suggest contacting the team for verified information.
"""

                    # Use minimal context (what we have) but allow LLM to use general knowledge
                    context = "\n\n".join(state.context_gathered) if state.context_gathered else ""
                    context_section = (
                        f"Retrieved Context (limited):\n{context}"
                        if context
                        else "No verified documents found in internal knowledge base."
                    )

                    final_prompt = f"""
{transparency_instruction}

User Query: {query}
{context_section}

Provide a helpful answer using your general knowledge, but clearly state that this is not verified internal information.
"""

                    tier1_start_time = time.time()
                    try:
                        state.final_answer, _, _, _ = await llm_gateway.send_message(
                            chat,
                            final_prompt,
                            system_prompt,
                            tier=model_tier,
                            enable_function_calling=False,
                        )
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        tier1_fallback_success_total.labels(intent_type=intent_type).inc()
                        logger.info(
                            f"🌊 [Tier 1 Stream] General Intelligence response generated (duration: {tier1_duration:.2f}s)",
                        )
                    except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        error_type = type(e).__name__
                        tier1_fallback_failed_total.labels(
                            intent_type=intent_type, error_type=error_type,
                        ).inc()
                        logger.error(
                            f"Failed to generate Tier 1 fallback answer: {error_type}",
                            exc_info=True,
                        )
                        # Fallback to ABSTAIN if LLM fails
                        state.final_answer = self._get_localized_stub("abstain", language)
            else:
                # Generate answer with optional warning for weak evidence
                context = "\n\n".join(state.context_gathered)
                warning_note = ""
                if (
                    evidence_score >= EvidenceScoreConstants.ABSTAIN_THRESHOLD
                    and evidence_score < 0.5
                ):
                    warning_note = (
                        "\n\nWARNING: Evidence is moderate. Use precautionary language "
                        "(e.g., 'Based on available information...', 'It appears that...'). "
                        "Still provide a helpful answer, but acknowledge limitations if needed."
                    )
                    logger.info(
                        f"🛡️ [Uncertainty Stream] Moderate evidence detected (Score: {evidence_score:.2f}), adding warning",
                    )

                final_prompt = f"""
Based on the information gathered:
{context}
{warning_note}

Provide a final, comprehensive answer to: {query}

IMPORTANT: After your answer, naturally suggest 1-2 related topics or next steps that might be helpful.
Examples: "Vuoi sapere anche quanto costa?" / "Ti interessa anche il processo completo?" / "Posso spiegarti anche i requisiti documentali"
Make it feel natural and helpful, not forced.
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
                logger.info(
                    "🏷️ [General Task Stream] No context needed, proceeding with LLM generation",
                )
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
                    state.final_answer = self._get_localized_stub("error", language)
            else:
                # No context gathered - apply same Tier 1 vs ABSTAIN logic
                intent_type = getattr(state, "intent_type", "simple")
                is_critical = is_critical_domain(query, intent_type)

                if is_critical:
                    domain_type = get_critical_domain_type(query)
                    logger.warning(
                        f"🛡️ [Uncertainty Stream] No context gathered for critical domain, triggering ABSTAIN (Domain: {domain_type})",
                    )
                    strict_abstain_critical_total.labels(
                        intent_type=intent_type, domain_type=domain_type,
                    ).inc()
                    abstain_decision_total.labels(decision_type="strict_abstain").inc()
                    state.final_answer = self._get_localized_stub("abstain", language)
                else:
                    # TIER 1: No context but non-critical - use General Intelligence
                    tier1_fallback_activated_total.labels(
                        intent_type=intent_type, has_context="false",
                    ).inc()
                    abstain_decision_total.labels(decision_type="tier1_fallback").inc()
                    logger.info(
                        "🌊 [Tier 1 Stream] No context gathered for non-critical query, "
                        "using General Intelligence fallback",
                    )
                    transparency_instruction = """
[SYSTEM NOTICE: NO INTERNAL DOCUMENTS FOUND]
CRITICAL INSTRUCTION: No verified documents were found in the internal knowledge base.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with: "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
"""

                    final_prompt = f"""
{transparency_instruction}

User Query: {query}

Provide a helpful answer using your general knowledge, but clearly state that this is not verified internal information.
"""

                    tier1_start_time = time.time()
                    try:
                        state.final_answer, _, _, _ = await llm_gateway.send_message(
                            chat,
                            final_prompt,
                            system_prompt,
                            tier=model_tier,
                            enable_function_calling=False,
                        )
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        tier1_fallback_success_total.labels(intent_type=intent_type).inc()
                        logger.info(
                            f"🌊 [Tier 1 Stream] General Intelligence response generated (no context, duration: {tier1_duration:.2f}s)",
                        )
                    except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                        tier1_duration = time.time() - tier1_start_time
                        tier1_response_duration.observe(tier1_duration)
                        error_type = type(e).__name__
                        tier1_fallback_failed_total.labels(
                            intent_type=intent_type, error_type=error_type,
                        ).inc()
                        logger.error(
                            f"Failed to generate Tier 1 fallback answer: {error_type}",
                            exc_info=True,
                        )
                        state.final_answer = self._get_localized_stub("abstain", language)

        # Filter stub responses
        if state.final_answer and (
            "no further action needed" in state.final_answer.lower()
            or "observation: none" in state.final_answer.lower()
        ):
            state.final_answer = self._get_localized_stub("confused", language)

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
                chunk = answer[i : i + chunk_size]
                yield {"type": "token", "data": chunk}

        # Yield sources if available
        if hasattr(state, "sources") and state.sources:
            yield {"type": "sources", "data": state.sources}


# NOTE: detect_team_query has been moved to reasoning_utils.py
# It is imported at the top of this file from backend.services.rag.agentic.reasoning_utils
# The deprecated redefinition has been removed to avoid F811 linting error


# Build trigger: 1771635692
