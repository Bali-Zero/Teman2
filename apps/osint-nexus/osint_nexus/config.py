"""Central configuration — all tunables in one place."""

from __future__ import annotations

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DOSSIER_DIR = DATA_DIR / "dossiers"

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:17687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "osint-nexus-2026")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NER = os.getenv("OSINT_MODEL_NER", "qwen3.5:9b")
MODEL_REASONING = os.getenv("OSINT_MODEL_REASONING", "deepseek-r1:32b")

# Scraping
SCRAPE_MIN_DELAY = float(os.getenv("SCRAPE_MIN_DELAY", "2.0"))
SCRAPE_MAX_DELAY = float(os.getenv("SCRAPE_MAX_DELAY", "6.0"))
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "30"))
SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", "3"))

# Proxy (optional — set SCRAPE_PROXY=socks5://... if needed)
SCRAPE_PROXY = os.getenv("SCRAPE_PROXY")

# OPSEC
LOG_LEVEL = os.getenv("OSINT_LOG_LEVEL", "INFO")
# Never log PII or raw scraped content at INFO level
