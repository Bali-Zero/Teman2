"""NLM Deep Research Pipeline for NotebookLM NB-2 (Immigration & Visa Indonesia).

Automated nightly intelligence pipeline that:
1. Queries NLM NB-2 with dual-language adversarial prompts
2. Extracts verifiable claims with confidence scoring
3. Manages source lifecycle (70 ACTIVE cap, SVS ranking)
4. Generates handoff packages for the intel scraper
5. Monitors Notebook Health Score (NHS)

Production schedule: 01:10-02:20 WITA daily (Mon-Fri)
"""

__version__ = "1.0.0"
