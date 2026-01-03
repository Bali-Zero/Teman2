"""
Routing Module
Specialized routing services extracted from QueryRouter
"""

# Import sub-services BEFORE QueryRouter to avoid circular imports
from .confidence_calculator import ConfidenceCalculatorService
from .conflict_resolver import ConflictResolver
from .fallback_manager import FallbackManagerService
from .keyword_matcher import KeywordMatcherService
from .priority_override import PriorityOverrideService
from .routing_stats import RoutingStatsService

# Import main routers AFTER sub-services
from .golden_router_service import GoldenRouterService
from .intelligent_router import IntelligentRouter
from .query_router import QueryRouter
from .query_router_integration import QueryRouterIntegration

__all__ = [
    "KeywordMatcherService",
    "ConfidenceCalculatorService",
    "FallbackManagerService",
    "PriorityOverrideService",
    "RoutingStatsService",
    "QueryRouter",
    "QueryRouterIntegration",
    "IntelligentRouter",
    "GoldenRouterService",
    "ConflictResolver",
]
