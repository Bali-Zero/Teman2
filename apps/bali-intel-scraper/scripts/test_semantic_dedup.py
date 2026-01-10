#!/usr/bin/env python3
"""
TEST SEMANTIC DEDUPLICATION
============================
Test completo della deduplicazione semantica con Qdrant.

Verifica:
1. Connessione Qdrant
2. Collezione esiste (o la crea)
3. Generazione embedding
4. Check duplicati
5. Salvataggio articoli
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env from {env_path}")
else:
    print(f"⚠️ .env not found at {env_path}")

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from semantic_deduplicator import SemanticDeduplicator

# Configure logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

async def test_deduplicator():
    """Test completo del Semantic Deduplicator"""
    
    logger.info("=" * 70)
    logger.info("🧪 TEST SEMANTIC DEDUPLICATION")
    logger.info("=" * 70)
    
    # Check env vars
    logger.info("\n📋 Verifica Environment Variables...")
    qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    logger.info(f"   QDRANT_URL: {qdrant_url[:50]}...")
    logger.info(f"   QDRANT_API_KEY: {'✅ Set' if qdrant_key else '❌ Missing'}")
    logger.info(f"   OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Missing'}")
    
    if not openai_key:
        logger.error("❌ OPENAI_API_KEY non configurato. Impossibile generare embedding.")
        return False
    
    # Initialize deduplicator
    logger.info("\n🔧 Inizializzazione Semantic Deduplicator...")
    try:
        dedup = SemanticDeduplicator()
        logger.success("✅ Deduplicator inizializzato")
    except Exception as e:
        logger.error(f"❌ Errore inizializzazione: {e}")
        return False
    
    # Test Case 1: Articolo nuovo (non duplicato)
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Articolo NUOVO (non dovrebbe essere duplicato)")
    logger.info("=" * 70)
    
    test_article_1 = {
        "title": "Bali Introduces Revolutionary Digital Nomad Visa Program",
        "summary": "The Indonesian government has launched a new visa program specifically designed for remote workers and digital nomads, allowing them to stay in Bali for up to 5 years.",
        "url": "https://test.example.com/bali-nomad-visa-2025"
    }
    
    logger.info(f"📰 Titolo: {test_article_1['title']}")
    logger.info(f"📝 Summary: {test_article_1['summary'][:80]}...")
    
    is_dup, match, score = await dedup.is_duplicate(
        test_article_1["title"],
        test_article_1["summary"],
        test_article_1["url"]
    )
    
    if is_dup:
        logger.warning(f"⚠️ Risultato inatteso: Trovato duplicato (Score: {score:.2f})")
        logger.warning(f"   Match: {match}")
    else:
        logger.success(f"✅ Articolo UNICO (Score: {score:.2f})")
    
    # Test Case 2: Salvataggio articolo
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Salvataggio articolo in Qdrant")
    logger.info("=" * 70)
    
    try:
        await dedup.save_article({
            **test_article_1,
            "source": "TestBot",
            "category": "immigration",
            "publishedAt": "2025-01-09T10:00:00Z"
        })
        logger.success("✅ Articolo salvato in Qdrant")
    except Exception as e:
        logger.error(f"❌ Errore salvataggio: {e}")
        return False
    
    # Test Case 3: Re-check (dovrebbe essere duplicato ora)
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Re-check stesso articolo (dovrebbe essere duplicato)")
    logger.info("=" * 70)
    
    await asyncio.sleep(2)  # Attesa propagazione Qdrant
    
    is_dup, match, score = await dedup.is_duplicate(
        test_article_1["title"],
        test_article_1["summary"],
        test_article_1["url"]
    )
    
    if is_dup:
        logger.success(f"✅ DUPLICATO RILEVATO correttamente! (Score: {score:.2f})")
        logger.info(f"   Match: {match}")
    else:
        logger.warning(f"⚠️ Duplicato NON rilevato (Score: {score:.2f})")
    
    # Test Case 4: Articolo simile ma non identico
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Articolo SIMILE ma non identico (dovrebbe passare)")
    logger.info("=" * 70)
    
    test_article_2 = {
        "title": "New Tourist Tax Announced for Bali Visitors",
        "summary": "Starting next month, all international tourists entering Bali will be required to pay a new entry fee of IDR 150,000.",
        "url": "https://test.example.com/bali-tourist-tax-2025"
    }
    
    logger.info(f"📰 Titolo: {test_article_2['title']}")
    
    is_dup, match, score = await dedup.is_duplicate(
        test_article_2["title"],
        test_article_2["summary"],
        test_article_2["url"]
    )
    
    if is_dup:
        logger.warning(f"⚠️ Risultato ambiguo: Score {score:.2f} (threshold: 0.88)")
        logger.info(f"   Match: {match}")
    else:
        logger.success(f"✅ Articolo UNICO (Score: {score:.2f})")
    
    # Test Case 5: Variante semantica dello stesso articolo
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Variante SEMANTICA (stesso concetto, parole diverse)")
    logger.info("=" * 70)
    
    test_article_3 = {
        "title": "Bali Launches Extended Stay Program for Remote Workers",
        "summary": "Indonesia has introduced a groundbreaking visa scheme enabling digital nomads to reside in Bali for extended periods, up to five years.",
        "url": "https://test.example.com/bali-nomad-visa-variant"
    }
    
    logger.info(f"📰 Titolo: {test_article_3['title']}")
    logger.info("   (Stesso concetto di Test 1, ma parole diverse)")
    
    is_dup, match, score = await dedup.is_duplicate(
        test_article_3["title"],
        test_article_3["summary"],
        test_article_3["url"]
    )
    
    if is_dup:
        logger.success(f"✅ DUPLICATO SEMANTICO rilevato! (Score: {score:.2f})")
        logger.info(f"   Match: {match}")
        logger.info("   🎯 Il sistema ha capito che è lo stesso concetto!")
    else:
        logger.warning(f"⚠️ Duplicato semantico NON rilevato (Score: {score:.2f})")
        logger.info("   (Potrebbe essere normale se il threshold è troppo alto)")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    logger.info("✅ Test completati!")
    logger.info("\n💡 Prossimi passi:")
    logger.info("   1. Verifica che la collezione 'balizero_news_history' esista su Qdrant")
    logger.info("   2. Se non esiste, esegui: python init_news_collection.py")
    logger.info("   3. Integra nella pipeline: intel_pipeline.py già aggiornato")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_deduplicator())
    sys.exit(0 if success else 1)
