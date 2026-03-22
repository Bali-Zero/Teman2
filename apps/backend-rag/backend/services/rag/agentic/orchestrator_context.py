import logging
import time
from typing import Any, Dict, List, Optional

from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.services.misc.context_window_manager import ContextWindowManager
from backend.services.rag.agentic.context_manager import get_user_context

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
    ):
        self.db_pool = db_pool
        self.memory_handler = memory_handler
        self.context_window_manager = context_window_manager

    async def prepare_query_context(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        deep_think_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Recupera il profilo utente, i facts (personali/collettivi), valida e comprime
        la history della conversazione rispettando il budget di token.
        """
        with trace_span("orchestrator.prepare_query_context") as span:
            start_time = time.time()
            try:
                # 1. Recupero dati utente base (Profile, Facts, Episodic)
                context_data = await get_user_context(
                    db_pool=self.db_pool,
                    user_id=user_id,
                    memory_orchestrator=self.memory_handler.memory_orchestrator if hasattr(self.memory_handler, 'memory_orchestrator') else self.memory_handler,
                    query=query,
                    deep_think_mode=deep_think_mode,
                    session_id=session_id
                )

                # 2. Gestione History: diamo priorità a quella passata via API (es. streaming dal frontend)
                if conversation_history is not None:
                    context_data["history"] = conversation_history

                # 3. Context Window Management (Trimming/Summarization)
                if context_data.get("history"):
                    context_data["history"] = await self.context_window_manager.manage_context(
                        context_data["history"],
                        query=query
                    )

                # Metriche e tracciamento
                set_span_attribute("context.history_length", len(context_data.get("history", [])))
                set_span_attribute("context.facts_count", len(context_data.get("memory_facts", [])))
                set_span_attribute("execution_time", time.time() - start_time)
                set_span_status("OK")

                return context_data

            except Exception as e:
                # Fallback graceful: ritorna un contesto base vuoto per non far fallire l'intera RAG query
                logger.error(f"Errore critico durante il caricamento del contesto: {e}", exc_info=True)
                set_span_status("ERROR", str(e))
                return {
                    "profile": {},
                    "history": conversation_history or [],
                    "memory_facts": [],
                    "collective_facts": []
                }
