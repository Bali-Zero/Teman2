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

# NLM Notebook IDs
NLM_NOTEBOOKS = {
    "ai_research": "dc5d01cd-e99f-4c8f-aae4-75060b43d0de",  # NB-INTEL-AIResearch
    "self_evolving": "305f5f2e-d2f4-4f77-a771-c2b7aa0867e4",  # Mata Garuda Self-Evolving Research
    "regulation": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76",  # NB-INTEL-Regulation
    "tax": "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f",         # NB-INTEL-Tax
    "immigration": "1ed02e54-542f-426a-94f8-53c5ffde4b7d", # NB-INTEL-Immigration
    "press": "9d262101-abeb-4e15-af9c-c38e028c62fe",       # NB-INTEL-Press
}

# Domain → NLM Notebook routing (for nlm_feeder)
# Enriched items with one of these topic/domain values flow to the mapped NB.
NLM_DOMAIN_ROUTING = {
    "immigration_visa": "immigration",
    "tax_fiscal": "tax",
    "investment_licensing": "regulation",
    "labor_manpower": "regulation",
    "property": "regulation",          # PBG/SHGB/Hak Pakai → regulation NB
    "financial_banking": "regulation", # banking compliance → regulation NB
    "political_risk": "press",
    "provincial_bali": "press",
    "ai_research": "ai_research",
    # "other" / "environmental" / "procurement" → skip — keep NBs focused.
}

# NLM rate limits
NLM_FEEDER_BATCH_SIZE = 10       # max items per run
NLM_FEEDER_SLEEP_BETWEEN_S = 5   # seconds between MCP/CLI calls

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

# AI Intel Sentinel — RSS feeds (verified 2026-04-10)
AI_RSS_FEEDS = [
    "https://jack-clark.net/feed/",                        # Import AI
    "https://huggingface.co/blog/feed.xml",               # Hugging Face Blog
    "https://www.technologyreview.com/feed/",             # MIT Technology Review
    "https://magazine.sebastianraschka.com/feed",         # Sebastian Raschka AI
    "https://thegradient.pub/rss/",                       # The Gradient
]


# ── Council (Consiglio v1) ────────────────────────────────────────────
STREAM_COUNCIL_TOPICS = "council:topics"
STREAM_COUNCIL_DECISIONS = "council:decisions"

# ── Phase 1 — Bridge & Nexus integration ──────────────────────────────
from pathlib import Path

# New streams
STREAM_BRIDGE_OUTBOUND = "bridge:outbound"
STREAM_BRIDGE_INBOUND = "bridge:inbound"
STREAM_NEXUS_GAPS = "nexus:gaps"

# Bridge config
BRIDGE_API_KEY_ENV = "BRIDGE_API_KEY"
BRIDGE_BACKEND_URL = "https://nuzantara-rag.fly.dev"
BRIDGE_CURSOR_PATH = Path.home() / ".agent" / "decisions" / "bridge_cursor.json"

# Polling cadence (seconds)
BRIDGE_POLL_INTERVAL_DAY_S = 30      # 08:00-18:00 WITA
BRIDGE_POLL_INTERVAL_NIGHT_S = 300   # 18:00-08:00 WITA
BRIDGE_PULL_LIMIT = 50
BRIDGE_PUSH_BATCH = 10
BRIDGE_HTTP_TIMEOUT_S = 15
