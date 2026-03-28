"""
Orchestrator Routing Manager

Responsabilità singola: Intent classification e model tier selection.
Include:
- Intent classification tramite IntentClassifier
- Model tier selection (FLASH vs PRO vs DeepThink)
- AgentState initialization basato su intent
- Deep think mode detection

Questo modulo è testabile in isolamento mockando IntentClassifier.
"""

import logging
from typing import Any

from backend.services.classification.intent_classifier import IntentClassifier
from backend.services.rag.agentic.query_helpers import TIER_FLASH, TIER_PRO
from backend.services.tools.definitions import AgentState

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging for routing decisions


class OrchestratorRoutingManager:
    """
    Gestisce intent classification e routing decisions.

    Responsabilità:
    - Classifica intent della query
    - Seleziona model tier appropriato
    - Inizializza AgentState con parametri corretti
    - Determina se usare deep think mode
    """

    def __init__(self, intent_classifier: IntentClassifier | None = None) -> None:
        """
        Inizializza il routing manager.

        Args:
            intent_classifier: Optional classifier per intent detection
                Se None, crea nuova istanza
        """
        if intent_classifier is None:
            from backend.services.classification.intent_classifier import IntentClassifier

            self.intent_classifier = IntentClassifier()
        else:
            self.intent_classifier = intent_classifier

    async def classify_intent(self, query: str) -> dict[str, Any]:
        """
        Classifica l'intent della query.

        Args:
            query: Query string da classificare

        Returns:
            Dict con keys: suggested_ai, deep_think_mode, skip_rag, category
        """
        logger.debug("Calling verify_intent...")
        intent = await self.intent_classifier.classify_intent(query)
        logger.debug(f"Intent classified: {intent}")
        return intent

    def select_model_tier(
        self,
        intent: dict[str, Any],
    ) -> tuple[str, bool]:
        """
        Seleziona model tier basato su intent.

        Args:
            intent: Intent classification result

        Returns:
            Tuple di (model_tier, deep_think_mode)
        """
        suggested_ai = intent.get("suggested_ai", "FLASH")
        bool(intent.get("deep_think_mode", False))

        if suggested_ai == "deep_think":
            return TIER_PRO, True
        if suggested_ai == "pro":
            return TIER_PRO, False
        return TIER_FLASH, False

    def create_agent_state(
        self,
        query: str,
        intent: dict[str, Any],
    ) -> AgentState:
        """
        Crea AgentState inizializzato con parametri dall'intent.

        Args:
            query: Query string
            intent: Intent classification result

        Returns:
            AgentState inizializzato
        """
        skip_rag = intent.get("skip_rag", False)
        intent_category = intent.get("category", "simple")
        return AgentState(query=query, skip_rag=skip_rag, intent_type=intent_category)

    async def route_query(
        self,
        query: str,
    ) -> tuple[str, bool, AgentState]:
        """
        Route completo: classifica intent e prepara routing decisions.

        Questo è il metodo principale che combina tutti i passaggi:
        1. Classify intent
        2. Select model tier
        3. Create agent state

        Args:
            query: Query string da processare

        Returns:
            Tuple di (model_tier, deep_think_mode, agent_state)
        """
        # 1. Classify intent
        intent = await self.classify_intent(query)

        # 2. Select model tier
        model_tier, deep_think_mode = self.select_model_tier(intent)

        # 3. Create agent state
        agent_state = self.create_agent_state(query, intent)

        logger.debug(
            f"🎯 [Routing] Query routed: tier={model_tier}, "
            f"deep_think={deep_think_mode}, intent={intent.get('category')}",
        )

        return model_tier, deep_think_mode, agent_state
