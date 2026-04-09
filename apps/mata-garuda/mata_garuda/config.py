"""
Mata Garuda — Configuration constants.

Redis streams, NLM notebook IDs, source configs, TG settings.
All values here — no .env files (OSINT blindato, local only).
"""
from __future__ import annotations

# Redis Streams
STREAM_RAW = "garuda:raw"
STREAM_ENRICHED = "garuda:enriched"
STREAM_ALERTS = "garuda:alerts"
STREAM_DIGEST = "garuda:digest"
STREAM_OSINT = "garuda:osint"
STREAM_FEEDBACK = "garuda:feedback"

# Telegram — Zero only
TG_BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TG_ZERO_CHAT_ID = "1125336968"

# NLM Notebook IDs (to be populated as notebooks are created)
NLM_NOTEBOOKS = {
    "regulation": "",       # NB-INTEL-Regulation
    "ai_research": "",      # NB-INTEL-AIResearch
    "tax": "",              # NB-INTEL-Tax
    "immigration": "",      # NB-INTEL-Immigration
    "press": "",            # NB-INTEL-Press
}

# Relevance scoring weights for business context
RELEVANCE_WEIGHTS = {
    "immigration_visa": 5,
    "tax_fiscal": 5,
    "investment_licensing": 4,
    "labor_manpower": 4,
    "provincial_bali": 4,
    "financial_banking": 3,
    "property": 3,
    "environmental": 2,
    "ai_research": 4,
    "procurement": 1,
}

# Scoring thresholds
SCORE_SIGNAL = 4    # >= 4: alert to Zero
SCORE_WATCH = 2     # >= 2: store in KB, no alert
SCORE_NOISE = 1     # < 2: discard

# AI Intel Sentinel — YouTube channels
AI_YOUTUBE_CHANNELS = [
    "AndrejKarpathy",       # Andrej Karpathy
    "TwoMinutePapers",      # Two Minute Papers
    "YannicKilcher",        # Yannic Kilcher
    "AIExplained",          # AI Explained
    "3blue1brown",          # 3Blue1Brown (occasional AI)
    "Fireship",             # Fireship (AI trends)
]

# AI Intel Sentinel — arXiv categories
ARXIV_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.IR"]

# AI Intel Sentinel — RSS feeds
AI_RSS_FEEDS = [
    "https://www.deeplearning.ai/the-batch/feed/",       # The Batch
    "https://jack-clark.net/feed/",                        # Import AI
    "https://tldr.tech/ai/rss",                           # TLDR AI
    "https://paperswithcode.com/latest/feed",             # Papers With Code
]
