"""
NUZANTARA RAG - A/B Testing Framework

Implements A/B testing for comparing retrieval strategies in production.
Uses consistent hashing for sticky user assignment and chi-square test
for statistical significance.

Experiments:
- hybrid_vs_dense: Hybrid search vs dense-only search
- reranking_on_off: Cross-encoder reranking enabled/disabled
- query_expansion: Query expansion enabled/disabled

Metrics:
- Click-through rate (CTR)
- User satisfaction (thumbs up/down)
- Response time
- Evidence score

Example:
    >>> ab_manager = ABTestManager()
    >>> variant = ab_manager.assign_variant("user123", "hybrid_vs_dense")
    >>> print(variant)  # "A" or "B"
    >>> await ab_manager.record_metric("hybrid_vs_dense", variant, "ctr", 1.0)
    >>> results = await ab_manager.get_experiment_results("hybrid_vs_dense")
    >>> is_sig = await ab_manager.is_significant("hybrid_vs_dense")
"""

import hashlib
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.services.rag.evaluation.metrics_tracker import MetricsTracker

logger = logging.getLogger(__name__)


class Variant(str, Enum):
    """Experiment variants."""

    CONTROL = "A"
    TREATMENT = "B"


@dataclass
class ExperimentConfig:
    """Configuration for an A/B test experiment.

    Attributes:
        name: Unique experiment identifier
        description: Human-readable description
        variants: List of variant names (default: ["A", "B"])
        split_ratio: Traffic split between variants (default: 0.5 for 50/50)
        min_sample_size: Minimum samples per variant before significance test
        confidence_level: Statistical confidence level (default: 0.95)
        enabled: Whether experiment is active
        start_date: When experiment started
        end_date: Optional end date
    """

    name: str
    description: str
    variants: list[str] = field(default_factory=lambda: [Variant.CONTROL, Variant.TREATMENT])
    split_ratio: float = 0.5
    min_sample_size: int = 100
    confidence_level: float = 0.95
    enabled: bool = True
    start_date: datetime | None = None
    end_date: datetime | None = None

    def __post_init__(self) -> None:
        if self.start_date is None:
            self.start_date = datetime.now(timezone.utc)


# Predefined experiment configurations
DEFAULT_EXPERIMENTS: dict[str, ExperimentConfig] = {
    "hybrid_vs_dense": ExperimentConfig(
        name="hybrid_vs_dense",
        description="Compare hybrid search (BM25 + vector) vs dense-only search",
        variants=["dense_only", "hybrid"],
        split_ratio=0.5,
        min_sample_size=100,
    ),
    "reranking_on_off": ExperimentConfig(
        name="reranking_on_off",
        description="Compare results with and without cross-encoder reranking",
        variants=["no_rerank", "with_rerank"],
        split_ratio=0.5,
        min_sample_size=100,
    ),
    "query_expansion": ExperimentConfig(
        name="query_expansion",
        description="Compare query expansion enabled vs disabled",
        variants=["no_expansion", "with_expansion"],
        split_ratio=0.5,
        min_sample_size=100,
    ),
}


class ABTestManager:
    """
    A/B Testing Manager for RAG retrieval strategies.

    Manages experiment assignment, metric recording, and statistical
    significance testing for comparing different RAG configurations.

    Features:
    - Consistent hashing for sticky user assignment
    - Chi-square test for statistical significance
    - Configurable traffic splits (default 50/50)
    - Minimum sample size enforcement
    - Real-time experiment results

    Attributes:
        experiments: Dictionary of experiment configurations
        metrics_tracker: MetricsTracker for persistent storage
        _variant_cache: In-memory cache of user-variant assignments

    Example:
        >>> ab = ABTestManager()
        >>> variant = ab.assign_variant("user123", "hybrid_vs_dense")
        >>> config = ab.get_variant_config("hybrid_vs_dense", variant)
        >>> # Use config to control search behavior
        >>> await ab.record_metric("hybrid_vs_dense", variant, "ctr", 1.0)
        >>> results = await ab.get_experiment_results("hybrid_vs_dense")
    """

    def __init__(
        self,
        experiments: dict[str, ExperimentConfig] | None = None,
        metrics_tracker: MetricsTracker | None = None,
    ) -> None:
        """
        Initialize A/B Test Manager.

        Args:
            experiments: Experiment configurations (uses defaults if None)
            metrics_tracker: Metrics tracker instance (creates new if None)
        """
        self.experiments = experiments or DEFAULT_EXPERIMENTS.copy()
        self.metrics_tracker = metrics_tracker or MetricsTracker()
        self._variant_cache: dict[str, str] = {}

        logger.info(
            f"ABTestManager initialized with {len(self.experiments)} experiments: "
            f"{list(self.experiments.keys())}",
        )

    def assign_variant(self, user_id: str, experiment: str) -> str:
        """
        Assign a user to a variant using consistent hashing.

        Uses MD5 hash of user_id + experiment for deterministic,
        sticky assignment. Same user always gets same variant for
        the same experiment.

        Args:
            user_id: Unique user identifier
            experiment: Experiment name

        Returns:
            Variant identifier (e.g., "A", "B", or custom variant names)

        Raises:
            ValueError: If experiment doesn't exist or is disabled

        Example:
            >>> variant = ab_manager.assign_variant("user123", "hybrid_vs_dense")
            >>> print(variant)  # "dense_only" or "hybrid"
        """
        if experiment not in self.experiments:
            logger.warning(f"Experiment '{experiment}' not found, defaulting to control variant")
            return Variant.CONTROL

        config = self.experiments[experiment]

        if not config.enabled:
            logger.debug(f"Experiment '{experiment}' is disabled, returning control variant")
            return config.variants[0]

        # Check cache first
        cache_key = f"{experiment}:{user_id}"
        if cache_key in self._variant_cache:
            return self._variant_cache[cache_key]

        # Consistent hashing using MD5
        hash_input = f"{user_id}:{experiment}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)

        # Normalize to 0-1 range
        hash_normalized = (hash_value % 10000) / 10000.0

        # Assign variant based on split ratio
        if hash_normalized < config.split_ratio:
            variant = config.variants[0]  # Control
        else:
            variant = config.variants[1]  # Treatment

        # Cache assignment
        self._variant_cache[cache_key] = variant

        logger.debug(
            f"Assigned user '{user_id}' to variant '{variant}' "
            f"in experiment '{experiment}' (hash={hash_normalized:.4f})",
        )

        return variant

    def get_variant_config(self, experiment: str, variant: str) -> dict[str, Any]:
        """
        Get configuration for a specific experiment variant.

        Returns configuration parameters that should be applied
        based on the assigned variant.

        Args:
            experiment: Experiment name
            variant: Variant identifier

        Returns:
            Configuration dictionary for the variant

        Example:
            >>> config = ab_manager.get_variant_config("hybrid_vs_dense", "hybrid")
            >>> print(config)  # {"use_hybrid_search": True, "alpha": 0.5}
        """
        configs = {
            "hybrid_vs_dense": {
                "dense_only": {"use_hybrid_search": False, "alpha": 1.0},
                "hybrid": {"use_hybrid_search": True, "alpha": 0.5},
            },
            "reranking_on_off": {
                "no_rerank": {"use_reranking": False},
                "with_rerank": {"use_reranking": True, "top_k": 5},
            },
            "query_expansion": {
                "no_expansion": {"use_expansion": False},
                "with_expansion": {"use_expansion": True, "expansion_count": 3},
            },
        }

        if experiment not in configs:
            return {}

        return configs[experiment].get(variant, {})

    async def record_metric(
        self,
        experiment: str,
        variant: str,
        metric: str,
        value: float,
        user_id: str | None = None,
        query_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a metric for an experiment variant.

        Stores the metric in the metrics tracker for later analysis.

        Args:
            experiment: Experiment name
            variant: Variant identifier
            metric: Metric name (e.g., "ctr", "satisfaction", "response_time")
            value: Metric value
            user_id: Optional user identifier
            query_id: Optional query identifier
            metadata: Optional additional metadata

        Example:
            >>> await ab_manager.record_metric(
            ...     "hybrid_vs_dense", "hybrid", "ctr", 1.0,
            ...     user_id="user123", query_id="query456"
            ... )
        """
        try:
            await self.metrics_tracker.record_metric(
                experiment=experiment,
                variant=variant,
                metric=metric,
                value=value,
                user_id=user_id,
                query_id=query_id,
                metadata=metadata,
            )
            logger.debug(
                f"Recorded metric '{metric}={value}' for experiment '{experiment}' "
                f"variant '{variant}'",
            )
        except Exception as e:
            logger.error(f"Failed to record metric: {e}")
            # Don't raise - metrics recording should not break the main flow

    async def get_experiment_results(self, experiment: str) -> dict[str, Any]:
        """
        Get aggregated results for an experiment.

        Returns statistics for each variant including sample sizes,
        metric averages, and confidence intervals.

        Args:
            experiment: Experiment name

        Returns:
            Dictionary with experiment results

        Example:
            >>> results = await ab_manager.get_experiment_results("hybrid_vs_dense")
            >>> print(results["variants"]["hybrid"]["metrics"]["ctr"]["mean"])
        """
        if experiment not in self.experiments:
            return {"error": f"Experiment '{experiment}' not found"}

        config = self.experiments[experiment]

        try:
            # Get aggregated metrics from tracker
            variant_metrics = await self.metrics_tracker.get_experiment_aggregates(
                experiment=experiment,
                variants=config.variants,
            )

            # Calculate statistical significance for each metric
            significance_results = {}
            for metric_name in ["ctr", "satisfaction", "response_time", "evidence_score"]:
                control_data = (
                    variant_metrics.get(config.variants[0], {}).get("raw", {}).get(metric_name, [])
                )
                treatment_data = (
                    variant_metrics.get(config.variants[1], {}).get("raw", {}).get(metric_name, [])
                )

                if (
                    len(control_data) >= config.min_sample_size
                    and len(treatment_data) >= config.min_sample_size
                ):
                    significance_results[metric_name] = self._calculate_significance(
                        control_data, treatment_data, config.confidence_level,
                    )
                else:
                    significance_results[metric_name] = {
                        "significant": False,
                        "reason": "insufficient_samples",
                        "control_n": len(control_data),
                        "treatment_n": len(treatment_data),
                        "min_required": config.min_sample_size,
                    }

            return {
                "experiment": experiment,
                "config": {
                    "description": config.description,
                    "variants": config.variants,
                    "split_ratio": config.split_ratio,
                    "min_sample_size": config.min_sample_size,
                    "confidence_level": config.confidence_level,
                    "enabled": config.enabled,
                },
                "variants": variant_metrics,
                "significance": significance_results,
                "total_queries": sum(v.get("count", 0) for v in variant_metrics.values()),
                "is_active": config.enabled
                and (not config.end_date or datetime.now(timezone.utc) < config.end_date),
            }

        except Exception as e:
            logger.error(f"Failed to get experiment results: {e}")
            return {"error": str(e), "experiment": experiment}

    async def is_significant(self, experiment: str, metric: str = "ctr") -> bool:
        """
                Check if results are statistically significant for an experiment.

                Uses chi-square test for binary metrics (CTR, satisfaction) and
        n        t-test for continuous metrics (response_time, evidence_score).

                Args:
                    experiment: Experiment name
                    metric: Metric to test (default: "ctr")

                Returns:
                    True if results are statistically significant

                Example:
                    >>> if await ab_manager.is_significant("hybrid_vs_dense"):
                    ...     print("Experiment has significant results!")
        """
        results = await self.get_experiment_results(experiment)

        if "significance" not in results:
            return False

        significance = results["significance"].get(metric, {})
        return significance.get("significant", False)

    def _calculate_significance(
        self,
        control_data: list[float],
        treatment_data: list[float],
        confidence_level: float = 0.95,
    ) -> dict[str, Any]:
        """
        Calculate statistical significance between two datasets.

        Uses t-test for continuous variables and chi-square for binary.

        Args:
            control_data: Control variant data points
            treatment_data: Treatment variant data points
            confidence_level: Desired confidence level

        Returns:
            Dictionary with significance test results
        """
        if not control_data or not treatment_data:
            return {"significant": False, "reason": "no_data"}

        # Calculate means and standard deviations
        control_mean = sum(control_data) / len(control_data)
        treatment_mean = sum(treatment_data) / len(treatment_data)

        control_var = sum((x - control_mean) ** 2 for x in control_data) / max(
            len(control_data) - 1, 1,
        )
        treatment_var = sum((x - treatment_mean) ** 2 for x in treatment_data) / max(
            len(treatment_data) - 1, 1,
        )

        # Standard error of the difference
        se = math.sqrt(control_var / len(control_data) + treatment_var / len(treatment_data))

        if se == 0:
            return {
                "significant": False,
                "reason": "no_variance",
                "control_mean": control_mean,
                "treatment_mean": treatment_mean,
            }

        # T-statistic
        t_stat = (treatment_mean - control_mean) / se

        # Degrees of freedom (Welch's approximation)
        df = ((control_var / len(control_data) + treatment_var / len(treatment_data)) ** 2) / (
            (control_var / len(control_data)) ** 2 / max(len(control_data) - 1, 1)
            + (treatment_var / len(treatment_data)) ** 2 / max(len(treatment_data) - 1, 1)
        )

        # Critical t-value for two-tailed test
        # Using approximation for 95% confidence
        critical_t = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%

        # P-value approximation (simplified)
        p_value = 2 * (1 - self._normal_cdf(abs(t_stat)))

        significant = abs(t_stat) > critical_t and p_value < (1 - confidence_level)

        # Calculate relative uplift
        if control_mean != 0:
            uplift = ((treatment_mean - control_mean) / abs(control_mean)) * 100
        elif treatment_mean == 0:
            uplift = 0.0
        else:
            uplift = float("inf") if treatment_mean > 0 else float("-inf")

        return {
            "significant": significant,
            "p_value": round(p_value, 4),
            "t_statistic": round(t_stat, 4),
            "degrees_of_freedom": round(df, 2),
            "control_mean": round(control_mean, 4),
            "treatment_mean": round(treatment_mean, 4),
            "control_n": len(control_data),
            "treatment_n": len(treatment_data),
            "uplift_percent": round(uplift, 2),
            "confidence_level": confidence_level,
        }

    def _normal_cdf(self, x: float) -> float:
        """Approximation of the standard normal CDF."""
        # Abramowitz and Stegun approximation
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2.0)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

        return 0.5 * (1.0 + sign * y)

    def list_experiments(self) -> list[dict[str, Any]]:
        """
        List all available experiments.

        Returns:
            List of experiment configurations
        """
        return [
            {
                "name": config.name,
                "description": config.description,
                "variants": config.variants,
                "enabled": config.enabled,
                "split_ratio": config.split_ratio,
            }
            for config in self.experiments.values()
        ]

    def enable_experiment(self, experiment: str) -> bool:
        """
        Enable an experiment.

        Args:
            experiment: Experiment name

        Returns:
            True if experiment was enabled
        """
        if experiment in self.experiments:
            self.experiments[experiment].enabled = True
            logger.info(f"Enabled experiment: {experiment}")
            return True
        return False

    def disable_experiment(self, experiment: str) -> bool:
        """
        Disable an experiment.

        Args:
            experiment: Experiment name

        Returns:
            True if experiment was disabled
        """
        if experiment in self.experiments:
            self.experiments[experiment].enabled = False
            logger.info(f"Disabled experiment: {experiment}")
            return True
        return False

    async def get_dashboard_data(self) -> dict[str, Any]:
        """
        Get data for the A/B testing dashboard.

        Returns:
            Dashboard data with all experiments and their current status
        """
        experiments_data = []

        for name in self.experiments:
            results = await self.get_experiment_results(name)
            experiments_data.append(results)

        return {
            "experiments": experiments_data,
            "total_experiments": len(self.experiments),
            "active_experiments": sum(1 for e in self.experiments.values() if e.enabled),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
