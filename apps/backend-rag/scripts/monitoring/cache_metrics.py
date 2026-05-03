#!/usr/bin/env python3
"""
Embedding Cache Metrics Exporter
Tracks hit rate, size, and performance of the embedding cache
"""

import json
import logging
import sys
import time
from typing import Any

# Add project root to path
sys.path.insert(0, "/Users/antonellosiano/Projects/nuzantara/apps/backend-rag")

from backend.core.embeddings import _global_embedding_cache

logger = logging.getLogger(__name__)


class CacheMetricsExporter:
    """Export embedding cache metrics for monitoring"""

    def __init__(self):
        self.cache = _global_embedding_cache

    def get_metrics(self) -> dict[str, Any]:
        """Get current cache metrics"""
        stats = self.cache.get_stats()
        return {
            "timestamp": time.time(),
            "cache": {
                "hits": stats["hits"],
                "misses": stats["misses"],
                "hit_rate": round(stats["hit_rate"], 4),
                "size": stats["size"],
                "max_size": stats["max_size"],
                "utilization": round(stats["size"] / stats["max_size"], 4),
            },
            "performance": {
                "estimated_ms_saved": stats["hits"] * 100,  # ~100ms per cached embedding
            },
        }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        stats = self.cache.get_stats()
        lines = [
            "# HELP embedding_cache_hits Total number of cache hits",
            "# TYPE embedding_cache_hits counter",
            f'embedding_cache_hits{{cache="embedding_lru"}} {stats["hits"]}',
            "",
            "# HELP embedding_cache_misses Total number of cache misses",
            "# TYPE embedding_cache_misses counter",
            f'embedding_cache_misses{{cache="embedding_lru"}} {stats["misses"]}',
            "",
            "# HELP embedding_cache_hit_rate Cache hit rate (0-1)",
            "# TYPE embedding_cache_hit_rate gauge",
            f'embedding_cache_hit_rate{{cache="embedding_lru"}} {stats["hit_rate"]:.4f}',
            "",
            "# HELP embedding_cache_size Current cache size",
            "# TYPE embedding_cache_size gauge",
            f'embedding_cache_size{{cache="embedding_lru"}} {stats["size"]}',
            "",
            "# HELP embedding_cache_max_size Maximum cache size",
            "# TYPE embedding_cache_max_size gauge",
            f'embedding_cache_max_size{{cache="embedding_lru"}} {stats["max_size"]}',
        ]
        return "\n".join(lines)

    def print_dashboard(self):
        """Print metrics in a dashboard format"""
        metrics = self.get_metrics()
        c = metrics["cache"]
        p = metrics["performance"]

        logger.info("\n" + "=" * 60)
        logger.info("📊 EMBEDDING CACHE METRICS")
        logger.info("=" * 60)
        logger.info(
            f"  Hit Rate:     {c['hit_rate'] * 100:.2f}%  ({c['hits']} hits / {c['misses']} misses)"
        )
        logger.info(
            f"  Size:         {c['size']} / {c['max_size']} ({c['utilization'] * 100:.1f}% full)"
        )
        logger.info(f"  Est. Savings: ~{p['estimated_ms_saved']}ms total")
        logger.info("=" * 60)

        # Recommendations
        if c["hit_rate"] < 0.1:
            logger.info("⚠️  Low hit rate - consider increasing cache size")
        elif c["hit_rate"] > 0.8:
            logger.info("✅ Excellent hit rate!")

        if c["utilization"] > 0.9:
            logger.info("⚠️  Cache nearing capacity - consider increasing max_size")


def main():
    exporter = CacheMetricsExporter()

    if len(sys.argv) > 1 and sys.argv[1] == "--prometheus":
        logger.info(exporter.export_prometheus())
    elif len(sys.argv) > 1 and sys.argv[1] == "--json":
        logger.info(json.dumps(exporter.get_metrics(), indent=2))
    else:
        exporter.print_dashboard()


if __name__ == "__main__":
    main()
