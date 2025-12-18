"""
Analytics Module
Specialized analytics services extracted from TeamAnalyticsService
"""

from .burnout_detector import BurnoutDetectorService
from .optimal_hours import OptimalHoursService
from .pattern_analyzer import PatternAnalyzerService
from .performance_trend import PerformanceTrendService
from .productivity_scorer import ProductivityScorerService
from .team_insights import TeamInsightsService
from .workload_balance import WorkloadBalanceService

__all__ = [
    "PatternAnalyzerService",
    "ProductivityScorerService",
    "BurnoutDetectorService",
    "PerformanceTrendService",
    "WorkloadBalanceService",
    "OptimalHoursService",
    "TeamInsightsService",
]
