"""
Priority Override Service
Responsibility: Detect priority override patterns (identity, team, backend services)
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

CollectionName = Literal[
    "visa_oracle",
    "kbli_eye",
    "kbli_comprehensive",
    "tax_genius",
    "legal_architect",
    "zantara_books",
    "tax_updates",
    "tax_knowledge",
    "property_listings",
    "property_knowledge",
    "legal_updates",
    "bali_zero_pricing",
    "kb_indonesian",
    "cultural_insights",
    "bali_zero_team",
]

# Backend Services keywords (for technical/API queries)
BACKEND_SERVICES_KEYWORDS = [
    "backend",
    "api endpoint",
    "endpoint",
    "servizio backend",
    "backend service",
    "python tool",
    "tool python",
    "zantara tool",
    "get_pricing",
    "search_team_member",
    "tool executor",
    "handler",
    "typescript handler",
    "crm service",
    "conversation service",
    "memory service",
    "agentic function",
    "api documentation",
    "come posso chiamare",
    "how to call",
    "come accedere",
    "how to access",
    "quale endpoint",
    "which endpoint",
    "api disponibili",
    "available api",
    "servizi disponibili",
    "available services",
    "postgresql",
    "qdrant",
    "vector database",
    "database vettoriale",
    "auto-crm",
    "client journey",
    "compliance monitoring",
    "dynamic pricing",
    "cross-oracle synthesis",
    "crm",
    "conversazione",
    "conversation",
    "memoria",
    "memory",
    "semantic",
    "semantica",
    "salvare",
    "save",
    "caricare",
    "load",
    "database",
    "client information",
    "informazioni cliente",
    "pratica",
    "practice",
    "interazione",
    "interaction",
    "log interaction",
    "loggare",
]


class PriorityOverrideService:
    """
    Service for detecting priority override patterns.

    Responsibility: Check for special query patterns that override normal routing.
    """

    def __init__(self):
        """Initialize priority override service."""
        # Identity query patterns (highest priority)
        self.identity_patterns = [
            "chi sono",
            "who am i",
            "siapa saya",
            "mi conosci",
            "cosa sai di me",
            "il mio nome",
            "my name",
            "my role",
            "sai chi sono",
            "do you know me",
            "recognize me",
            "mi riconosci",
            "kenal saya",
            "chi sono io",
        ]

        # Team enumeration patterns
        self.team_patterns = [
            "membri",
            "team",
            "colleghi",
            "quanti siamo",
            "chi lavora",
            "team members",
            "colleagues",
            "who works",
            "conosci i membri",
            "know the members",
            "dipartimento",
            "department",
        ]

        self.backend_services_keywords = BACKEND_SERVICES_KEYWORDS

    def check_priority_overrides(self, query: str) -> CollectionName | None:
        """
        Check for priority override patterns (identity, team, founder, backend services).

        Args:
            query: User query text

        Returns:
            Collection name if override detected, None otherwise
        """
        query_lower = query.lower()

        # PRIORITY OVERRIDE: Identity queries (highest priority)
        if any(pattern in query_lower for pattern in self.identity_patterns):
            logger.info("🧭 Route: bali_zero_team (IDENTITY QUERY OVERRIDE)")
            return "bali_zero_team"

        # PRIORITY OVERRIDE: Team enumeration queries
        if any(pattern in query_lower for pattern in self.team_patterns):
            logger.info("🧭 Route: bali_zero_team (TEAM ENUMERATION OVERRIDE)")
            return "bali_zero_team"

        # EXPLICIT OVERRIDE: Force team routing for founder queries
        if "fondatore" in query_lower or "founder" in query_lower:
            logger.info("🧭 Route: bali_zero_team (EXPLICIT OVERRIDE: founder query detected)")
            return "bali_zero_team"

        # PRIORITY CHECK: Backend services queries
        backend_services_score = sum(
            1 for kw in self.backend_services_keywords if kw in query_lower
        )
        if backend_services_score > 0:
            logger.info(
                f"🧭 Route: zantara_books (BACKEND SERVICES QUERY: score={backend_services_score})"
            )
            return "zantara_books"

        return None

    def is_identity_query(self, query: str) -> bool:
        """
        Check if query is an identity query.

        Args:
            query: User query text

        Returns:
            True if identity query detected
        """
        query_lower = query.lower()
        return any(pattern in query_lower for pattern in self.identity_patterns)

    def is_team_query(self, query: str) -> bool:
        """
        Check if query is a team enumeration query.

        Args:
            query: User query text

        Returns:
            True if team query detected
        """
        query_lower = query.lower()
        return any(pattern in query_lower for pattern in self.team_patterns)

    def is_backend_services_query(self, query: str) -> bool:
        """
        Check if query is about backend services/API.

        Args:
            query: User query text

        Returns:
            True if backend services query detected
        """
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.backend_services_keywords)
