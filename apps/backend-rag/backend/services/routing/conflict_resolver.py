"""
Conflict Resolver Service
Detects and resolves conflicts between results from different collections

Extracted from SearchService to follow Single Responsibility Principle.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConflictResolver:
    """
    Resolves conflicts between results from different collections.

    REFACTORED: Extracted from SearchService to reduce complexity.
    """

    def __init__(self):
        """Initialize conflict resolver"""
        self.stats = {
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "timestamp_resolutions": 0,
            "semantic_resolutions": 0,
        }
        logger.info("✅ ConflictResolver initialized")

    def detect_conflicts(self, results_by_collection: dict[str, list[dict]]) -> list[dict]:
        """
        Detect conflicts between results from different collections.

        A conflict exists when:
        1. Multiple collections return results about the same topic
        2. The information differs (especially timestamps, values, etc.)

        Args:
            results_by_collection: Dict mapping collection_name -> list of results

        Returns:
            List of conflict dicts with details about each conflict
        """
        conflicts = []

        # Pairs that commonly conflict
        conflict_pairs = [
            ("tax_knowledge", "tax_updates"),
            ("legal_architect", "legal_updates"),
            ("property_knowledge", "property_listings"),
            ("tax_genius", "tax_updates"),
            ("legal_architect", "legal_updates"),
        ]

        for coll1, coll2 in conflict_pairs:
            if coll1 in results_by_collection and coll2 in results_by_collection:
                results1 = results_by_collection[coll1]
                results2 = results_by_collection[coll2]

                if results1 and results2:
                    # Simple conflict detection: if both have results, potential conflict
                    conflict = {
                        "collections": [coll1, coll2],
                        "type": "temporal" if "updates" in coll2 else "semantic",
                        "collection1_results": len(results1),
                        "collection2_results": len(results2),
                        "collection1_top_score": results1[0]["score"] if results1 else 0,
                        "collection2_top_score": results2[0]["score"] if results2 else 0,
                        "detected_at": datetime.now().isoformat(),
                    }

                    # Check for timestamp metadata
                    meta1 = results1[0]["metadata"] if results1 else {}
                    meta2 = results2[0]["metadata"] if results2 else {}

                    if "timestamp" in meta1 or "timestamp" in meta2:
                        conflict["timestamp1"] = meta1.get("timestamp", "unknown")
                        conflict["timestamp2"] = meta2.get("timestamp", "unknown")

                    conflicts.append(conflict)
                    self.stats["conflicts_detected"] += 1
                    logger.warning(
                        f"⚠️ [Conflict Detected] {coll1} vs {coll2} - "
                        f"scores: {conflict['collection1_top_score']:.2f} vs {conflict['collection2_top_score']:.2f}"
                    )

        return conflicts

    def resolve_conflicts(
        self, results_by_collection: dict[str, list[dict]], conflicts: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """
        Resolve conflicts using timestamp and relevance-based priority.

        Resolution strategy:
        1. Timestamp priority: *_updates collections win over base collections
        2. Recency: Newer timestamps win
        3. Relevance: Higher scores win if timestamps equal
        4. Transparency: Keep losing results flagged as "outdated" or "alternate"

        Args:
            results_by_collection: Dict mapping collection_name -> list of results
            conflicts: List of detected conflicts

        Returns:
            Tuple of (resolved_results, conflict_reports)
        """
        from app.core.constants import SearchConstants

        resolved_results = []
        conflict_reports = []

        for conflict in conflicts:
            coll1, coll2 = conflict["collections"]
            results1 = results_by_collection[coll1]
            results2 = results_by_collection[coll2]

            # Rule 1: "*_updates" collections always win over base collections
            if "updates" in coll2 and results2:
                winner_coll = coll2
                winner_results = results2
                loser_coll = coll1
                loser_results = results1
                resolution_reason = "temporal_priority (updates collection)"
                self.stats["timestamp_resolutions"] += 1
            elif "updates" in coll1 and results1:
                winner_coll = coll1
                winner_results = results1
                loser_coll = coll2
                loser_results = results2
                resolution_reason = "temporal_priority (updates collection)"
                self.stats["timestamp_resolutions"] += 1
            else:
                # Rule 2: Compare top scores
                score1 = results1[0]["score"] if results1 else 0
                score2 = results2[0]["score"] if results2 else 0

                if score2 > score1:
                    winner_coll = coll2
                    winner_results = results2
                    loser_coll = coll1
                    loser_results = results1
                else:
                    winner_coll = coll1
                    winner_results = results1
                    loser_coll = coll2
                    loser_results = results2

                resolution_reason = "relevance_score"
                self.stats["semantic_resolutions"] += 1

            # Mark winner results
            for result in winner_results:
                result["metadata"]["conflict_resolution"] = {
                    "status": "preferred",
                    "reason": resolution_reason,
                    "alternate_source": loser_coll,
                }
                resolved_results.append(result)

            # Keep loser results but flag them
            for result in loser_results:
                result["metadata"]["conflict_resolution"] = {
                    "status": "outdated" if "timestamp" in resolution_reason else "alternate",
                    "reason": resolution_reason,
                    "preferred_source": winner_coll,
                }
                # Lower score to deprioritize
                result["score"] = result["score"] * SearchConstants.CONFLICT_PENALTY_MULTIPLIER
                resolved_results.append(result)

            # Create conflict report
            conflict_report = {
                **conflict,
                "resolution": {
                    "winner": winner_coll,
                    "loser": loser_coll,
                    "reason": resolution_reason,
                },
            }
            conflict_reports.append(conflict_report)
            self.stats["conflicts_resolved"] += 1

            logger.info(
                f"✅ [Conflict Resolved] {winner_coll} (preferred) > {loser_coll} - "
                f"reason: {resolution_reason}"
            )

        return resolved_results, conflict_reports

    def get_stats(self) -> dict:
        """
        Get conflict resolution statistics.

        Returns:
            Dict with conflict resolution metrics
        """
        return self.stats.copy()
