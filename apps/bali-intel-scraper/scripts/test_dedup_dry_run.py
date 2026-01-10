#!/usr/bin/env python3
"""
TEST DRY-RUN SEMANTIC DEDUPLICATION
====================================
Test della struttura senza chiamate reali a OpenAI/Qdrant.
Verifica che il codice sia corretto e pronto.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

def test_imports():
    """Test che tutti i moduli siano importabili"""
    logger.info("=" * 70)
    logger.info("🧪 TEST IMPORTS & STRUCTURE")
    logger.info("=" * 70)
    
    try:
        logger.info("\n1️⃣ Testing semantic_deduplicator import...")
        from semantic_deduplicator import SemanticDeduplicator, COLLECTION_NAME, SIMILARITY_THRESHOLD
        logger.success(f"   ✅ Import OK")
        logger.info(f"   Collection: {COLLECTION_NAME}")
        logger.info(f"   Threshold: {SIMILARITY_THRESHOLD}")
    except ImportError as e:
        logger.error(f"   ❌ Import failed: {e}")
        return False
    
    try:
        logger.info("\n2️⃣ Testing intel_pipeline import...")
        from intel_pipeline import IntelPipeline, PipelineArticle, PipelineStats
        logger.success(f"   ✅ Import OK")
    except ImportError as e:
        logger.error(f"   ❌ Import failed: {e}")
        return False
    
    try:
        logger.info("\n3️⃣ Testing init_news_collection import...")
        from init_news_collection import init_collection
        logger.success(f"   ✅ Import OK")
    except ImportError as e:
        logger.error(f"   ❌ Import failed: {e}")
        return False
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ TUTTI GLI IMPORTS OK")
    logger.info("=" * 70)
    
    logger.info("\n📋 PROSSIMI PASSI:")
    logger.info("   1. Configura OPENAI_API_KEY e QDRANT_API_KEY nel .env")
    logger.info("   2. Esegui: python init_news_collection.py")
    logger.info("   3. Esegui: python test_semantic_dedup.py")
    
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
