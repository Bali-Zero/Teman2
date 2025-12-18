"""
Team Work Analytics Service
7 Advanced Techniques for Team Performance Analysis

Provides intelligent insights on:
1. Pattern Recognition - Work hour patterns and habits
2. Productivity Scoring - Session productivity metrics
3. Burnout Detection - Early warning signs
4. Performance Trends - Long-term performance analysis
5. Workload Balance - Team workload distribution
6. Optimal Hours - Best performance time windows
7. Team Insights - Collaboration and synergy analysis

REFACTORED: Uses sub-services following Single Responsibility Principle
- PatternAnalyzerService: Work pattern analysis
- ProductivityScorerService: Productivity scoring
- BurnoutDetectorService: Burnout detection
- PerformanceTrendService: Trend analysis
- WorkloadBalanceService: Workload analysis
- OptimalHoursService: Optimal hours identification
- TeamInsightsService: Team insights generation
"""

import logging

import asyncpg

from services.analytics import (
    BurnoutDetectorService,
    OptimalHoursService,
    PatternAnalyzerService,
    PerformanceTrendService,
    ProductivityScorerService,
    TeamInsightsService,
    WorkloadBalanceService,
)

logger = logging.getLogger(__name__)


class TeamAnalyticsService:
    """
    Advanced analytics for team work sessions
    Provides 7 intelligent analysis techniques

    REFACTORED: Delegates to specialized sub-services.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

        # Initialize sub-services
        self.pattern_analyzer = PatternAnalyzerService(db_pool)
        self.productivity_scorer = ProductivityScorerService(db_pool)
        self.burnout_detector = BurnoutDetectorService(db_pool)
        self.performance_trend = PerformanceTrendService(db_pool)
        self.workload_balance = WorkloadBalanceService(db_pool)
        self.optimal_hours = OptimalHoursService(db_pool)
        self.team_insights = TeamInsightsService(db_pool)

    # ========================================
    # TECHNIQUE 1: PATTERN RECOGNITION
    # ========================================
    async def analyze_work_patterns(self, user_email: str | None = None, days: int = 30) -> dict:
        """
        Analyze work hour patterns and habits.

        REFACTORED: Delegates to PatternAnalyzerService.
        """
        """
        Analyze work hour patterns and habits.

        Returns:
        - Preferred start times
        - Typical session duration
        - Work day patterns (weekday vs weekend)
        - Consistency score
        """
        return await self.pattern_analyzer.analyze_work_patterns(user_email, days)

    # ========================================
    # TECHNIQUE 2: PRODUCTIVITY SCORING
    # ========================================
    async def calculate_productivity_scores(self, days: int = 7) -> list[dict]:
        """
        Calculate productivity score for each team member.

        REFACTORED: Delegates to ProductivityScorerService.
        """
        return await self.productivity_scorer.calculate_productivity_scores(days)

    # ========================================
    # TECHNIQUE 3: BURNOUT DETECTION
    # ========================================
    async def detect_burnout_signals(self, user_email: str | None = None) -> list[dict]:
        """
        Detect early warning signs of burnout.

        REFACTORED: Delegates to BurnoutDetectorService.
        """
        return await self.burnout_detector.detect_burnout_signals(user_email)

    # ========================================
    # TECHNIQUE 4: PERFORMANCE TRENDS
    # ========================================
    async def analyze_performance_trends(self, user_email: str, weeks: int = 4) -> dict:
        """
        Analyze performance trends over time.

        REFACTORED: Delegates to PerformanceTrendService.
        """
        return await self.performance_trend.analyze_performance_trends(user_email, weeks)

    # ========================================
    # TECHNIQUE 5: WORKLOAD BALANCE
    # ========================================
    async def analyze_workload_balance(self, days: int = 7) -> dict:
        """
        Analyze workload distribution across team.

        REFACTORED: Delegates to WorkloadBalanceService.
        """
        return await self.workload_balance.analyze_workload_balance(days)

    def _generate_workload_recommendations(self, team_stats: list[dict], ideal: float) -> list[str]:
        """
        Generate workload redistribution recommendations (backward compatibility).

        REFACTORED: Delegates to WorkloadBalanceService.
        """
        return self.workload_balance._generate_workload_recommendations(team_stats, ideal)

    def _generate_team_insights_text(
        self,
        members: int,
        hours: float,
        conversations: int,
        collab_windows: list[dict],
        health_score: float,
    ) -> list[str]:
        """
        Generate human-readable insights (backward compatibility).

        REFACTORED: Delegates to TeamInsightsService.
        """
        return self.team_insights._generate_team_insights_text(
            members, hours, conversations, collab_windows, health_score
        )

    # ========================================
    # TECHNIQUE 6: OPTIMAL HOURS
    # ========================================
    async def identify_optimal_hours(self, user_email: str | None = None, days: int = 30) -> dict:
        """
        Identify most productive time windows.

        REFACTORED: Delegates to OptimalHoursService.
        """
        return await self.optimal_hours.identify_optimal_hours(user_email, days)

    # ========================================
    # TECHNIQUE 7: TEAM INSIGHTS
    # ========================================
    async def generate_team_insights(self, days: int = 7) -> dict:
        """
        Generate comprehensive team collaboration insights.

        REFACTORED: Delegates to TeamInsightsService.
        """
        return await self.team_insights.generate_team_insights(days)
