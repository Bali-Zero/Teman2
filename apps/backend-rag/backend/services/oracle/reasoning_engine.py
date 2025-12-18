"""
Reasoning Engine Service
Responsibility: Gemini reasoning logic for query processing
"""

import logging
import time
from typing import Any, Optional

from llm.adapters.gemini import GeminiAdapter
from prompts.zantara_prompt_builder import PromptContext, ZantaraPromptBuilder

from services.oracle_google_services import google_services
from services.response.validator import ZantaraResponseValidator

logger = logging.getLogger(__name__)


class ReasoningEngineService:
    """
    Service for Gemini reasoning.

    Responsibility: Handle Gemini AI reasoning with context building and response validation.
    """

    def __init__(
        self,
        prompt_builder: ZantaraPromptBuilder | None = None,
        response_validator: ZantaraResponseValidator | None = None,
    ):
        """
        Initialize reasoning engine service.

        Args:
            prompt_builder: Optional ZantaraPromptBuilder instance
            response_validator: Optional ZantaraResponseValidator instance
        """
        self.prompt_builder = prompt_builder or ZantaraPromptBuilder(model_adapter=GeminiAdapter())
        self.response_validator = response_validator

    def build_context(
        self,
        documents: list[str],
        user_memory_facts: Optional[list[str]] = None,
        conversation_history: Optional[list[dict]] = None,
        use_full_docs: bool = False,
    ) -> str:
        """
        Build context string from documents, memory, and conversation history.

        Args:
            documents: List of document texts
            user_memory_facts: Optional list of user memory facts
            conversation_history: Optional conversation history
            use_full_docs: Whether to use full documents or excerpts

        Returns:
            Formatted context string
        """
        # RAG context
        if use_full_docs and documents:
            rag_context = (
                f"FULL DOCUMENT CONTEXT:\n{'-' * 80}\n" f"{chr(10).join(documents)}\n{'-' * 80}"
            )
        else:
            rag_context = (
                f"RELEVANT DOCUMENT EXCERPTS:\n{'-' * 80}\n"
                f"{chr(10).join([f'Document {i + 1}: {doc[:1500]}...' for i, doc in enumerate(documents)])}\n{'-' * 80}"
            )

        # Memory context
        memory_context = ""
        if user_memory_facts:
            memory_context = "\n\nUSER CONTEXT (Previous interactions):\n- " + "\n- ".join(
                user_memory_facts
            )

        # Conversation context
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            recent_history = (
                conversation_history[-10:]
                if len(conversation_history) > 10
                else conversation_history
            )
            history_lines = []
            for msg in recent_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if len(content) > 500:
                    content = content[:500] + "..."
                role_label = "User" if role == "user" else "Zantara"
                history_lines.append(f"{role_label}: {content}")
            conversation_context = (
                "\n\nCONVERSATION HISTORY (remember this context!):\n" + "\n".join(history_lines)
            )

        return f"{rag_context}{memory_context}{conversation_context}"

    async def reason_with_gemini(
        self,
        documents: list[str],
        query: str,
        context: PromptContext,
        use_full_docs: bool = False,
        user_memory_facts: Optional[list[str]] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """
        Advanced reasoning with Google Gemini 2.5 Flash using Zantara Identity Layer.

        Args:
            documents: List of document texts
            query: User query
            context: PromptContext instance
            use_full_docs: Whether to use full documents
            user_memory_facts: Optional user memory facts
            conversation_history: Optional conversation history

        Returns:
            Dictionary with reasoning result:
            - answer: Generated answer
            - model_used: Model identifier
            - reasoning_time_ms: Time taken
            - document_count: Number of documents
            - success: Success flag
        """
        start_reasoning = time.time()
        try:
            logger.info(
                f"🧠 Starting Gemini reasoning with {len(documents)} documents (Mode: {context.mode})"
            )

            model = google_services.get_gemini_model("models/gemini-2.5-flash")

            # Build context
            context_string = self.build_context(
                documents, user_memory_facts, conversation_history, use_full_docs
            )

            # Build system prompt
            system_prompt = self.prompt_builder.build(context)

            # Build user message
            user_message = f"""
QUERY: {query}
{context_string}

IMPORTANT: If the user mentioned their name, city, budget, or other personal details in the conversation history, remember and reference those details in your response. Answer the query based on the conversation context, user memory, documents, and your identity."""

            # Generation config
            generation_config = {
                "temperature": 0.3 if context.mode in ["legal_brief", "procedure_guide"] else 0.4,
                "top_p": 0.9,
                "top_k": 50,
                "max_output_tokens": 4096,
            }

            # Generate response
            response = model.generate_content(
                contents=[system_prompt, user_message], generation_config=generation_config
            )

            raw_answer = response.text

            # Validate response if validator available
            if self.response_validator:
                validation_result = self.response_validator.validate(raw_answer, context)
                final_answer = validation_result.validated

                if validation_result.violations:
                    logger.info(f"✨ Validator violations: {validation_result.violations}")
            else:
                final_answer = raw_answer

            reasoning_time = (time.time() - start_reasoning) * 1000

            return {
                "answer": final_answer,
                "model_used": "gemini-2.5-flash",
                "reasoning_time_ms": reasoning_time,
                "document_count": len(documents),
                "full_analysis": use_full_docs,
                "success": True,
                "mode_used": context.mode,
            }

        except Exception as e:
            error_time = (time.time() - start_reasoning) * 1000
            logger.error(f"❌ Error in Gemini reasoning after {error_time:.2f}ms: {e}")
            return {
                "answer": "I encountered an error while processing your request. The system has been notified. Please try again or contact support if the issue persists.",
                "model_used": "gemini-2.5-flash",
                "reasoning_time_ms": error_time,
                "document_count": len(documents),
                "full_analysis": False,
                "success": False,
                "error": str(e),
            }
