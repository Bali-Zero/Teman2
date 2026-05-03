import logging
import time
from typing import Any

import backend.services.rag.agentic.context_manager as _context_manager_module
from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.services.misc.context_window_manager import ContextWindowManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging for context operations


class OrchestratorContextManager:
    """
    Gestisce il loading e la preparazione del context per query processing.
    Isola il caricamento del profilo, dei facts, e la gestione della window history.
    """

    def __init__(
        self,
        db_pool: Any,
        memory_handler: Any,
        context_window_manager: ContextWindowManager,
    ) -> None:
        self.db_pool = db_pool
        self.memory_handler = memory_handler
        self.context_window_manager = context_window_manager

    async def prepare_query_context(
        self,
        user_id: str,
        query: str,
        session_id: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        deep_think_mode: bool = False,
    ) -> dict[str, Any]:
        """
        Recupera il profilo utente, i facts (personali/collettivi), valida e comprime
        la history della conversazione rispettando il budget di token.
        """
        with trace_span("orchestrator.prepare_query_context"):
            start_time = time.time()
            try:
                # 1. Recupero dati utente base (Profile, Facts, Episodic)
                memory_orch = await self.memory_handler.get_memory_orchestrator()
                context_data = await _context_manager_module.get_user_context(
                    db_pool=self.db_pool,
                    user_id=user_id,
                    memory_orchestrator=memory_orch,
                    query=query,
                    deep_think_mode=deep_think_mode,
                    session_id=session_id,
                )

                # 2. Gestione History: diamo priorità a quella passata via API (es. streaming dal frontend)
                if conversation_history is not None:
                    context_data["history"] = conversation_history

                # 3. Context Window Management (Trimming/Summarization)
                if context_data.get("history"):
                    context_data["history"] = await self.context_window_manager.manage_context(
                        context_data["history"], query=query,
                    )

                # Metriche e tracciamento
                set_span_attribute("context.history_length", len(context_data.get("history", [])))
                set_span_attribute("context.facts_count", len(context_data.get("memory_facts", [])))
                set_span_attribute("execution_time", time.time() - start_time)
                set_span_status("OK")

                return context_data

            except Exception as e:
                # Fallback graceful: ritorna un contesto base vuoto per non far fallire l'intera RAG query
                logger.error(
                    f"Errore critico durante il caricamento del contesto: {e}", exc_info=True,
                )
                set_span_status("ERROR", str(e))
                return {
                    "profile": {},
                    "history": conversation_history or [],
                    "memory_facts": [],
                    "collective_facts": [],
                }

    async def get_full_context(
        self,
        user_id: str,
        query: str,
        conversation_history: list[dict[str, Any]] | None = None,
        session_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Load full user context and return (context_dict, optimized_history) tuple.

        This is the primary entry point used by OrchestratorCore.prepare_query_context().
        Combines profile/memory loading with context window management.

        Args:
            user_id: User identifier
            query: Current query string
            conversation_history: Optional conversation history from API
            session_id: Optional session identifier

        Returns:
            Tuple of (user_context_dict, optimized_history_list)
        """
        context_data = await self.prepare_query_context(
            user_id=user_id,
            query=query,
            session_id=session_id,
            conversation_history=conversation_history,
        )
        optimized_history = context_data.get("history", [])
        return context_data, optimized_history

    async def apply_context_window_management(
        self,
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Apply context window trimming and summarization to conversation history.

        Delegates to ContextWindowManager to trim/summarize long conversations.

        Args:
            history: Full conversation history

        Returns:
            Optimized history list (trimmed and/or with summary injected)
        """
        if not history:
            return history

        trim_result = self.context_window_manager.trim_conversation_history(history)

        if trim_result.get("needs_summarization"):
            messages_to_summarize = trim_result.get("messages_to_summarize", [])
            recent_messages = trim_result.get("trimmed_messages", [])
            try:
                summary = await self.context_window_manager.generate_summary(messages_to_summarize)
                optimized = self.context_window_manager.inject_summary_into_history(
                    recent_messages, summary,
                )
                logger.info(
                    f"📊 [Context] Summarized {len(messages_to_summarize)} messages → {len(optimized)} items",
                )
                return optimized
            except Exception as e:
                logger.warning(f"⚠️ [Context] Summarization failed, using trimmed: {e}")
                return recent_messages

        return trim_result.get("trimmed_messages", history)

    async def enrich_user_context(
        self,
        user_context: dict[str, Any],
        user_id: str,
        query: str,
    ) -> dict[str, Any]:
        """
        Enrich an existing basic user context with additional memory facts.

        Used in the fast-path (pre-loaded context) to add memory data without
        reloading the full profile.

        Args:
            user_context: Existing context dict to enrich
            user_id: User identifier for memory lookup
            query: Current query string

        Returns:
            Enriched context dict
        """
        try:
            memory_orchestrator = await self.memory_handler.get_memory_orchestrator()
            enriched = await _context_manager_module.get_user_context(
                db_pool=self.db_pool,
                user_id=user_id,
                memory_orchestrator=memory_orchestrator,
                query=query,
                deep_think_mode=False,
                session_id=None,
            )
            # Merge enriched data into existing context, preserving pre-loaded fields
            return {**enriched, **{k: v for k, v in user_context.items() if v is not None}}
        except Exception as e:
            logger.warning(f"⚠️ [Context] enrich_user_context failed: {e}")
            return user_context
