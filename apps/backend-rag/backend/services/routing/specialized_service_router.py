"""
Specialized Service Router Module
Routes to autonomous research and cross-oracle synthesis services
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Autonomous Research keywords
AMBIGUOUS_KEYWORDS = [
    "crypto",
    "cryptocurrency",
    "blockchain",
    "nft",
    "web3",
    "new type",
    "nuovo",
    "baru",
    "innovative",
    "innovativo",
    "non standard",
    "uncommon",
    "rare",
    "unusual",
    "multiple",
    "several",
    "various",
    "diversi",
    "beberapa",
    "complete process",
    "percorso completo",
    "proses lengkap",
    "all requirements",
    "tutti requisiti",
    "semua syarat",
]

# Business setup keywords
BUSINESS_SETUP_KEYWORDS = [
    # Opening/starting
    "open",
    "start",
    "launch",
    "setup",
    "establish",
    "create",
    "aprire",
    "avviare",
    "lanciare",
    "creare",
    "buka",
    "mulai",
    "dirikan",
    # Business types
    "restaurant",
    "cafe",
    "shop",
    "store",
    "hotel",
    "villa",
    "ristorante",
    "negozio",
    "albergo",
    "restoran",
    "toko",
    "hotel",
    # Action-oriented
    "invest",
    "investire",
    "investasi",
    "business",
    "company",
    "azienda",
    "bisnis",
    "perusahaan",
]

# Comprehensive indicators
COMPREHENSIVE_INDICATORS = [
    "everything",
    "tutto",
    "semua",
    "complete",
    "completo",
    "lengkap",
    "full",
    "penuh",
    "timeline",
    "cronologia",
    "investment",
    "investimento",
    "investasi",
    "requirements",
    "requisiti",
    "persyaratan",
]

# How-to patterns
HOW_TO_PATTERNS = ["how to", "come si", "bagaimana cara"]

# Journey keywords
JOURNEY_KEYWORDS = [
    "start process",
    "begin application",
    "setup company",
    "avvia pratica",
    "inizia procedura",
    "mulai proses",
    "apply for",
    "richiedi",
    "ajukan",
]


class SpecializedServiceRouter:
    """
    Router for specialized services

    Routes complex queries to:
    - AutonomousResearchService: Ambiguous/complex multi-collection queries
    - CrossOracleSynthesisService: Business planning and comprehensive queries
    - ClientJourneyOrchestrator: Multi-step business workflows
    """

    def __init__(
        self,
        autonomous_research_service=None,
        cross_oracle_synthesis_service=None,
        client_journey_orchestrator=None,
    ):
        """
        Initialize specialized service router

        Args:
            autonomous_research_service: AutonomousResearchService instance
            cross_oracle_synthesis_service: CrossOracleSynthesisService instance
            client_journey_orchestrator: ClientJourneyOrchestrator instance
        """
        self.autonomous_research = autonomous_research_service
        self.cross_oracle = cross_oracle_synthesis_service
        self.client_journey = client_journey_orchestrator

        logger.info("🛣️ [SpecializedServiceRouter] Initialized")
        logger.info(f"   Autonomous Research: {'✅' if autonomous_research_service else '❌'}")
        logger.info(
            f"   Cross-Oracle Synthesis: {'✅' if cross_oracle_synthesis_service else '❌'}"
        )
        logger.info(f"   Client Journey: {'✅' if client_journey_orchestrator else '❌'}")

    def detect_autonomous_research(self, message: str, category: str) -> bool:
        """
        Detect if query needs autonomous research

        Args:
            message: User message
            category: Intent category

        Returns:
            True if autonomous research is needed
        """
        if not self.autonomous_research:
            return False

        if category not in ["business_complex", "business_simple"]:
            return False

        message_lower = message.lower()

        # Check for ambiguous terms
        has_ambiguous_term = any(kw in message_lower for kw in AMBIGUOUS_KEYWORDS)

        # Check for long/complex queries
        is_long_query = len(message.split()) > 15
        has_how_to = any(pattern in message_lower for pattern in HOW_TO_PATTERNS)

        needs_research = has_ambiguous_term or (is_long_query and has_how_to)

        if needs_research:
            logger.info("🛣️ [SpecializedServiceRouter] AUTONOMOUS RESEARCH detected")
            logger.info(
                f"   Ambiguous: {has_ambiguous_term}, Long: {is_long_query}, How-to: {has_how_to}"
            )

        return needs_research

    async def route_autonomous_research(
        self, query: str, user_level: int = 3
    ) -> dict[str, Any] | None:
        """
        Route to autonomous research service

        Args:
            query: User query
            user_level: User access level

        Returns:
            Response dict or None if failed
        """
        if not self.autonomous_research:
            return None

        try:
            # Perform autonomous research
            research_result = await self.autonomous_research.research(
                query=query, user_level=user_level
            )

            logger.info(
                f"🛣️ [SpecializedServiceRouter] AUTONOMOUS RESEARCH Complete: {research_result.total_steps} steps"
            )

            return {
                "response": research_result.final_answer,
                "ai_used": "zantara",
                "category": "autonomous_research",
                "model": "zantara-ai",
                "tokens": {"input": 0, "output": 0},
                "used_rag": True,
                "autonomous_research": {
                    "total_steps": research_result.total_steps,
                    "collections_explored": research_result.collections_explored,
                    "confidence": research_result.confidence,
                    "sources_consulted": research_result.sources_consulted,
                    "duration_ms": research_result.duration_ms,
                },
            }

        except Exception as e:
            logger.error(f"🛣️ [SpecializedServiceRouter] Error: {e}")
            return None

    def detect_cross_oracle(self, message: str, category: str) -> bool:
        """
        Detect if query needs cross-oracle synthesis

        Args:
            message: User message
            category: Intent category

        Returns:
            True if cross-oracle synthesis is needed
        """
        if not self.cross_oracle:
            return False

        if category not in ["business_complex", "business_simple"]:
            return False

        message_lower = message.lower()

        # Check for business setup terms
        has_business_setup_term = any(kw in message_lower for kw in BUSINESS_SETUP_KEYWORDS)

        # Check for comprehensive indicators
        wants_comprehensive_plan = any(ind in message_lower for ind in COMPREHENSIVE_INDICATORS)

        # Trigger: business setup term + (wants plan OR long query)
        needs_cross_oracle = has_business_setup_term and (
            wants_comprehensive_plan or len(message.split()) > 10
        )

        if needs_cross_oracle:
            logger.info("🛣️ [SpecializedServiceRouter] CROSS-ORACLE SYNTHESIS detected")
            logger.info(
                f"   Business setup: {has_business_setup_term}, Comprehensive: {wants_comprehensive_plan}"
            )

        return needs_cross_oracle

    async def route_cross_oracle(
        self, query: str, user_level: int = 3, use_cache: bool = True
    ) -> dict[str, Any] | None:
        """
        Route to cross-oracle synthesis service

        Args:
            query: User query
            user_level: User access level
            use_cache: Whether to use cache

        Returns:
            Response dict or None if failed
        """
        if not self.cross_oracle:
            return None

        try:
            # Perform cross-oracle synthesis
            synthesis_result = await self.cross_oracle.synthesize(
                query=query, user_level=user_level, use_cache=use_cache
            )

            logger.info(
                f"🛣️ [SpecializedServiceRouter] CROSS-ORACLE SYNTHESIS Complete: {synthesis_result.scenario_type}"
            )

            return {
                "response": synthesis_result.synthesis,
                "ai_used": "zantara",
                "category": "cross_oracle_synthesis",
                "model": "zantara-ai",
                "tokens": {"input": 0, "output": 0},
                "used_rag": True,
                "cross_oracle_synthesis": {
                    "scenario_type": synthesis_result.scenario_type,
                    "oracles_consulted": synthesis_result.oracles_consulted,
                    "confidence": synthesis_result.confidence,
                    "timeline": synthesis_result.timeline,
                    "investment": synthesis_result.investment,
                    "key_requirements": synthesis_result.key_requirements,
                    "risks": synthesis_result.risks,
                },
            }

        except Exception as e:
            logger.error(f"🛣️ [SpecializedServiceRouter] Error: {e}")
            return None

    def detect_client_journey(self, message: str, _category: str) -> bool:
        """
        Detect if query triggers a client journey
        """
        if not self.client_journey:
            return False

        message_lower = message.lower()

        # Check for explicit start keywords
        has_start_keyword = any(kw in message_lower for kw in JOURNEY_KEYWORDS)

        # Check for specific journey types mentioned
        journey_types = ["pt pma", "kitas", "visa", "property", "land"]
        has_journey_type = any(jt in message_lower for jt in journey_types)

        needs_journey = has_start_keyword and has_journey_type

        if needs_journey:
            logger.info("🛣️ [SpecializedServiceRouter] CLIENT JOURNEY detected")

        return needs_journey

    async def route_client_journey(self, query: str, user_id: str) -> dict[str, Any] | None:
        """
        Route to client journey orchestrator
        """
        if not self.client_journey:
            return None

        try:
            # Simple heuristic to determine type (in real app, use LLM extraction)
            query_lower = query.lower()
            journey_type = None

            if "pt pma" in query_lower or "company" in query_lower:
                journey_type = "pt_pma_setup"
            elif "kitas" in query_lower or "visa" in query_lower:
                journey_type = "kitas_application"
            elif "property" in query_lower or "land" in query_lower:
                journey_type = "property_purchase"

            if not journey_type:
                return None

            # Create the journey
            journey = self.client_journey.create_journey(
                journey_type=journey_type, client_id=user_id
            )

            response_text = (
                f"I have started the **{journey.title}** process for you.\n\n"
                f"**Journey ID:** `{journey.journey_id}`\n"
                f"**First Step:** {journey.steps[0].title}\n"
                f"**Description:** {journey.steps[0].description}\n\n"
                f"Please provide the required documents: {', '.join(journey.steps[0].required_documents)}"
            )

            return {
                "response": response_text,
                "ai_used": "zantara",
                "category": "client_journey",
                "model": "zantara-ai",
                "tokens": {"input": 0, "output": 0},
                "used_rag": False,
                "client_journey": {
                    "journey_id": journey.journey_id,
                    "status": journey.status.value,
                    "current_step": journey.steps[0].title,
                },
            }

        except Exception as e:
            logger.error(f"🛣️ [SpecializedServiceRouter] Error: {e}")
            return None
