"""
Agent Services - Modular services extracted from God Objects

Services:
- Client Scoring & Segmentation
- Nurturing & Notifications
- Knowledge Graph Operations
- Unified Coverage Collection
- Differential Coverage Analysis
"""

# Test Force Services
try:
    from .differential_coverage_analyzer import DifferentialCoverageAnalyzer, DifferentialReport
    from .unified_coverage_collector import UnifiedCoverageCollector, UnifiedCoverageReport

    __all__ = [
        "UnifiedCoverageCollector",
        "UnifiedCoverageReport",
        "DifferentialCoverageAnalyzer",
        "DifferentialReport",
    ]
except ImportError:
    # Services may not be available in all contexts
    pass
