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
from typing import Any

from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from services.tools.definitions import AgentState, AgentStep

from .response_processor import post_process_response
from .tool_executor import execute_tool, parse_tool_call

logger = logging.getLogger(__name__)


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
    ) -> tuple[AgentState, str, list[dict]]:
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
            Tuple of (updated_state, model_name_used, conversation_messages)
        """
        conversation_messages = []
        model_used_name = "unknown"

        # ==================== REACT LOOP ====================
        while state.current_step < state.max_steps:
            state.current_step += 1

            # Get model response with automatic fallback and native function calling
            try:
                if state.current_step == 1:
                    message = initial_prompt
                else:
                    # Continue conversation with observation
                    last_observation = state.steps[-1].observation if state.steps else ""
                    message = f"Observation: {last_observation}\n\nContinue with your next thought or provide final answer."

                text_response, model_used_name, response_obj = await llm_gateway.send_message(
                    chat,
                    message,
                    system_prompt,
                    tier=model_tier,
                    enable_function_calling=True,
                )

                conversation_messages.append({"role": "user", "content": message})
                conversation_messages.append({"role": "assistant", "content": text_response})

            except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError) as e:
                logger.error(f"Error during chat interaction: {e}", exc_info=True)
                break

            # Parse for tool calls - try native function calling first, then regex fallback
            tool_call = None

            # Check for function call in response parts (native mode)
            if hasattr(response_obj, "candidates") and response_obj.candidates:
                for candidate in response_obj.candidates:
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            tool_call = parse_tool_call(part, use_native=True)
                            if tool_call:
                                logger.info("✅ [Native Function Call] Detected in response")
                                break
                        if tool_call:
                            break

            # Fallback to regex parsing if no native function call found
            if not tool_call:
                tool_call = parse_tool_call(text_response, use_native=False)

            if tool_call:
                logger.info(
                    f"🔧 [Agent] Calling tool: {tool_call.tool_name} with {tool_call.arguments}"
                )
                tool_result = await execute_tool(
                    self.tool_map,
                    tool_call.tool_name,
                    tool_call.arguments,
                    user_id,
                    tool_execution_counter,
                )

                # --- CITATION HANDLING ---
                if tool_call.tool_name == "vector_search":
                    try:
                        parsed_result = json.loads(tool_result)
                        if isinstance(parsed_result, dict) and "sources" in parsed_result:
                            tool_result = parsed_result.get("content", "")
                            new_sources = parsed_result.get("sources", [])
                            if not hasattr(state, "sources"):
                                state.sources = []
                            state.sources.extend(new_sources)
                            logger.info(
                                f"📚 [Agent] Collected {len(new_sources)} sources from vector_search"
                            )
                    except json.JSONDecodeError:
                        pass
                    except (KeyError, ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse vector_search result: {e}", exc_info=True)

                # Update the tool call with the result
                tool_call.result = tool_result

                step = AgentStep(
                    step_number=state.current_step,
                    thought=text_response,
                    action=tool_call,
                    observation=tool_result,
                )
                state.steps.append(step)
                state.context_gathered.append(tool_result)

                # OPTIMIZATION: Early exit
                if (
                    tool_call.tool_name == "vector_search"
                    and len(tool_result) > 500
                    and "No relevant documents" not in tool_result
                ):
                    logger.info("🚀 [Early Exit] Sufficient context from retrieval.")
                    break

            else:
                # No tool call, assume final answer or just thought
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
                    # Just a thought step
                    step = AgentStep(step_number=state.current_step, thought=text_response)
                    state.steps.append(step)

        # ==================== FINAL ANSWER GENERATION ====================
        # Generate final answer if not present
        if not state.final_answer and state.context_gathered:
            context = "\n\n".join(state.context_gathered)
            final_prompt = f"""
Based on the information gathered:
{context}

Provide a final, comprehensive answer to: {query}
"""
            try:
                state.final_answer, model_used_name, _ = await llm_gateway.send_message(
                    chat,
                    final_prompt,
                    system_prompt,
                    tier=model_tier,
                    enable_function_calling=False,
                )
            except (ResourceExhausted, ServiceUnavailable, ValueError, RuntimeError):
                logger.error("Failed to generate final answer", exc_info=True)
                state.final_answer = "I apologize, but I couldn't generate a final answer based on the gathered information."

        # Filter out stub responses
        if state.final_answer and (
            "no further action needed" in state.final_answer.lower()
            or "observation: none" in state.final_answer.lower()
        ):
            logger.warning("⚠️ Detected stub response, generating fallback")
            state.final_answer = "Mi dispiace, non ho capito bene la tua richiesta. Potresti riformularla? Posso aiutarti con visti, aziende e leggi in Indonesia."

        # ==================== RESPONSE PIPELINE PROCESSING ====================
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

                # Handle verification failure (self-correction)
                if processed.get("verification_score", 1.0) < 0.7 and state.context_gathered:
                    verification = processed.get("verification", {})
                    logger.warning(
                        f"🛡️ [Pipeline] REJECTED draft (Score: {verification.get('score', 0)}). "
                        f"Reason: {verification.get('reasoning', 'unknown')}"
                    )

                    # SELF-CORRECTION
                    rephrase_prompt = f"""
SYSTEM: Your previous answer was REJECTED by the fact-checker.

REASON: {verification.get('reasoning', 'Insufficient evidence')}
MISSING/WRONG: {', '.join(verification.get('missing_citations', []))}

TASK: Rewrite the answer using ONLY the provided context.
Do not invent information. If the context is insufficient, admit it.
"""

                    # Retry with same model (disable function calling for final answer)
                    corrected_answer, _, _ = await llm_gateway.send_message(
                        chat,
                        rephrase_prompt,
                        system_prompt,
                        tier=model_tier,
                        enable_function_calling=False,
                    )
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

            except (ValueError, RuntimeError, KeyError) as e:
                logger.error(f"❌ [Pipeline] Processing failed: {e}", exc_info=True)
                # Fallback to basic post-processing
                state.final_answer = post_process_response(state.final_answer, query)

        return state, model_used_name, conversation_messages
