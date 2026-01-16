"""
Orchestrator Context Manager

Responsabilità singola: Gestione del context loading per query processing.
Include:
- User context loading (profile, facts, collective facts)
- Conversation history loading e validazione
- Context window management (summarization per token budget)
- Error handling con fallback graceful

Questo modulo è testabile in isolamento mockando memory_handler e context_window_manager.
"""

import logging
from typing import Any

from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.services.misc.context_window_manager import ContextWindowManager
from backend.services.rag.agentic.memory_handler import MemoryHandler

from .context_manager import get_user_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging for context operations


class OrchestratorContextManager:
    """
    Gestisce il loading e la preparazione del context per query processing.

    Responsabilità:
    - Carica user context (profile, facts, collective facts)
    - Gestisce conversation history con validazione
    - Applica context window management per lunghe conversazioni
    - Fornisce fallback graceful in caso di errori
    """

    def __init__(
        self,
        memory_handler: MemoryHandler,
        context_window_manager: ContextWindowManager,
        db_pool: Any = None,
    ):
        """
        Inizializza il context manager.

        Args:
            memory_handler: Handler per memory orchestrator access
            context_window_manager: Manager per context window trimming/summarization
            db_pool: Optional database pool per context loading
        """
        self.memory_handler = memory_handler
        self.context_window_manager = context_window_manager
        self.db_pool = db_pool

    async def load_user_context(
        self,
        user_id: str | None,
        query: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Carica il context completo dell'utente.

        Args:
            user_id: User ID (può essere None per anonymous)
            query: Query string per context-aware loading
            session_id: Optional session ID

        Returns:
            Dict con keys: profile, facts, collective_facts, history
            In caso di errore, ritorna context vuoto con fallback graceful.
        """
        effective_user_id = user_id or "anonymous"
        with trace_span("context.load_user", {"user_id": effective_user_id}):
            try:
                memory_orchestrator = await self.memory_handler.get_memory_orchestrator()
                user_context = await get_user_context(
                    self.db_pool,
                    effective_user_id,
                    memory_orchestrator,
                    query=query,
                    session_id=session_id,
                )
                set_span_attribute("facts_count", len(user_context.get("facts", [])))
                set_span_status("ok")
                return user_context
            except Exception as e:
                logger.warning(
                    f"⚠️ [Context] Failed to load user context (degraded): {e}", exc_info=True
                )
                set_span_status("error", str(e))
                # Fallback graceful: ritorna context vuoto
                return {
                    "profile": None,
                    "facts": [],
                    "collective_facts": [],
                    "history": [],
                }

    def prepare_conversation_history(
        self,
        conversation_history: list[dict] | None,
        user_context: dict[str, Any],
    ) -> list[dict]:
        """
        Prepara e valida conversation history.

        Args:
            conversation_history: History esplicita passata come parametro
            user_context: User context che può contenere history

        Returns:
            Lista validata di messaggi conversazione
        """
        history_to_use = conversation_history or user_context.get("history", [])

        # Validazione: deve essere lista di dict
        if not isinstance(history_to_use, list) or (
            history_to_use and not isinstance(history_to_use[0], dict)
        ):
            return []

        return history_to_use

    async def apply_context_window_management(
        self,
        history: list[dict],
    ) -> list[dict]:
        """
        Applica context window management per lunghe conversazioni.

        Previene "lost in the middle" phenomenon summarizzando messaggi più vecchi
        quando la conversazione supera la soglia.

        Args:
            history: Lista di messaggi conversazione

        Returns:
            History ottimizzata con summarization se necessario
        """
        if len(history) == 0:
            return history

        trim_result = self.context_window_manager.trim_conversation_history(history)

        if trim_result["needs_summarization"]:
            logger.info(
                f"📊 [ContextWindow] Summarizing {len(trim_result['messages_to_summarize'])} older messages"
            )
            try:
                summary = await self.context_window_manager.generate_summary(
                    trim_result["messages_to_summarize"], trim_result["context_summary"]
                )
                optimized_history = self.context_window_manager.inject_summary_into_history(
                    trim_result["trimmed_messages"], summary
                )
                logger.info(
                    f"✅ [ContextWindow] Summarized to {len(optimized_history)} messages with summary"
                )
                return optimized_history
            except Exception as e:
                logger.warning(
                    f"⚠️ [ContextWindow] Summarization failed, using trimmed history: {e}"
                )
                return trim_result["trimmed_messages"]
        else:
            return trim_result["trimmed_messages"]

    async def get_full_context(
        self,
        user_id: str | None,
        query: str,
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict]]:
        """
        Carica e prepara context completo per query processing.

        Questo è il metodo principale che combina tutti i passaggi:
        1. Load user context
        2. Prepare conversation history
        3. Apply context window management

        Args:
            user_id: User ID (può essere None)
            query: Query string
            conversation_history: Optional explicit history
            session_id: Optional session ID

        Returns:
            Tuple di (user_context, optimized_history)
        """
        # 1. Load user context
        user_context = await self.load_user_context(user_id, query, session_id)

        # 2. Prepare conversation history
        history = self.prepare_conversation_history(conversation_history, user_context)

        # 3. Apply context window management
        optimized_history = await self.apply_context_window_management(history)

        logger.info(
            f"🧠 [Context] Loaded context for {user_id or 'anonymous'} "
            f"(Facts: {len(user_context.get('facts', []))}, History: {len(optimized_history)} msgs)"
        )

        return user_context, optimized_history
