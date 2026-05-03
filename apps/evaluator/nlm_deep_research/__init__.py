"""NLM Deep Research Pipeline for NotebookLM NB-2 (Immigration & Visa Indonesia).

Automated nightly intelligence pipeline that:
1. Queries NLM NB-2 with dual-language adversarial prompts
2. Extracts verifiable claims with confidence scoring
3. Manages source lifecycle (70 ACTIVE cap, SVS ranking)
4. Generates handoff packages for the intel scraper
5. Monitors Notebook Health Score (NHS)

Also provides T4 Social Media Monitor:
- Fetches immigration content from RSS, government websites, X/Twitter
- 3-layer relevance filter (keywords → embedding → Haiku LLM)
- SVS scoring and budget-aware NLM NB-2 ingest
- Runs every 6h on Air (cron: 0 */6 * * *)

Production schedule: 01:10-02:20 WITA daily (Mon-Fri)
"""

__version__ = "1.1.0"

from apps.evaluator.nlm_deep_research.t4_monitor import (
    Article,
    FilterResult,
    Post,
    T4Fetcher,
    T4Monitor,
    T4RunResult,
)
from apps.evaluator.nlm_deep_research.t4_state import T4State, T4StatePersistence

__all__ = [
    "Article",
    "FilterResult",
    "Post",
    "T4Fetcher",
    "T4Monitor",
    "T4RunResult",
    "T4State",
    "T4StatePersistence",
]
