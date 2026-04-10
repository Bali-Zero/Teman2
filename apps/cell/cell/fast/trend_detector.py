# cell/fast/trend_detector.py
"""TrendDetector — thin bridge to cell-core.

Re-exports TrendDetector and TrendResult from cell_core.homeostasis.
"""
from cell_core.homeostasis import TrendDetector, TrendResult

__all__ = ["TrendDetector", "TrendResult"]
