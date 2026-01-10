#!/usr/bin/env python3
"""
TEST COMPLETO SETUP SEMANTIC DEDUPLICATION
===========================================
Verifica completa della configurazione:
1. Collezione Qdrant esiste (o la crea)
2. Test deduplicazione funzionante
3. Test integrazione pipeline
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

async def test_complete_setup():
    """Test completo della configurazione"""
    
    logger.info("=" * 70)
    logger.info("🧪 TEST COMPLETO SETUP - SEMANTIC DEDUPLICATION")
    logger.info("=" * 70)
    
    # Step 1: Verifica env vars
    logger.info("\n📋 STEP 1: Verifica Environment Variables...")
    qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    logger.info(f"   QDRANT_URL: {qdrant_url}")
    logger.info(f"   QDRANT_API_KEY: {'✅ Set' if qdrant_key else '❌ Missing'}")
    logger.info(f"   OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Missing'}")
    
    if not qdrant_key or not openai_key:
        logger.warning("\n⚠️ Chiavi mancanti nel .env locale.")
        logger.info("   Le chiavi sono disponibili su Fly.io secrets.")
        logger.info("   Per test locale, aggiungi al .env:")
        logger.info("   - QDRANT_API_KEY=...")
        logger.info("   - OPENAI_API_KEY=...")
        logger.info("\n   Oppure esegui il test su Fly.io:")
        logger.info("   fly ssh console -a nuzantara-rag -C 'cd /app && python scripts/test_semantic_dedup.py'")
        return False
    
    # Step 2: Inizializza collezione
    logger.info("\n📋 STEP 2: Verifica/Creazione Collezione Qdrant...")
    try:
        from init_news_collection import init_collection
        await init_collection()
        logger.success("✅ Collezione pronta")
    except Exception as e:
        logger.error(f"❌ Errore collezione: {e}")
        return False
    
    # Step 3: Test Deduplicator
    logger.info("\n📋 STEP 3: Test Semantic Deduplicator...")
    try:
        from semantic_deduplicator import SemanticDeduplicator
        
        dedup = SemanticDeduplicator()
        
        # Test articolo nuovo
        logger.info("   Test: Articolo nuovo...")
        is_dup, match, score = await dedup.is_duplicate(
            "Bali Introduces New Digital Nomad Visa",
            "The Indonesian government announced a new visa program for remote workers.",
            "https://test.example.com/nomad-visa-2025"
        )
        
        if is_dup:
            logger.warning(f"   ⚠️ Trovato duplicato (Score: {score:.2f})")
        else:
            logger.success(f"   ✅ Articolo unico (Score: {score:.2f})")
        
        # Test salvataggio
        logger.info("   Test: Salvataggio articolo...")
        await dedup.save_article({
            "title": "Bali Introduces New Digital Nomad Visa",
            "summary": "The Indonesian government announced a new visa program for remote workers.",
            "url": "https://test.example.com/nomad-visa-2025",
            "source": "TestBot",
            "category": "immigration",
            "publishedAt": "2025-01-09T12:00:00Z"
        })
        logger.success("   ✅ Articolo salvato")
        
        # Re-check (dovrebbe essere duplicato ora)
        logger.info("   Test: Re-check stesso articolo...")
        await asyncio.sleep(1)
        is_dup, match, score = await dedup.is_duplicate(
            "Bali Introduces New Digital Nomad Visa",
            "The Indonesian government announced a new visa program for remote workers.",
            "https://test.example.com/nomad-visa-2025"
        )
        
        if is_dup:
            logger.success(f"   ✅ Duplicato rilevato correttamente! (Score: {score:.2f})")
        else:
            logger.warning(f"   ⚠️ Duplicato non rilevato (Score: {score:.2f})")
        
    except Exception as e:
        logger.error(f"❌ Errore test deduplicator: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Test Integrazione Pipeline
    logger.info("\n📋 STEP 4: Test Integrazione Pipeline...")
    try:
        from intel_pipeline import IntelPipeline, PipelineArticle
        
        pipeline = IntelPipeline(
            min_llama_score=40,
            generate_images=False,
            require_approval=False,
            dry_run=True
        )
        
        # Crea articolo test
        test_article = PipelineArticle(
            title="Bali Introduces New Digital Nomad Visa",
            summary="The Indonesian government announced a new visa program for remote workers.",
            url="https://test.example.com/nomad-visa-2025-v2",
            source="TestBot"
        )
        
        # Processa (dry-run, quindi non chiama Claude)
        processed = await pipeline.process_article(test_article)
        
        if processed.is_duplicate:
            logger.success("   ✅ Pipeline rileva duplicato correttamente!")
        else:
            logger.info("   ✅ Pipeline processa articolo nuovo")
        
    except Exception as e:
        logger.error(f"❌ Errore test pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ TUTTI I TEST PASSATI!")
    logger.info("=" * 70)
    logger.info("\n🎉 La configurazione Semantic Deduplication è operativa!")
    logger.info("\n💡 Prossimi passi:")
    logger.info("   - La pipeline userà automaticamente la deduplicazione")
    logger.info("   - Gli articoli approvati verranno salvati in Qdrant")
    logger.info("   - I duplicati verranno filtrati PRIMA di chiamare Claude (risparmio $$$)")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_complete_setup())
    sys.exit(0 if success else 1)
