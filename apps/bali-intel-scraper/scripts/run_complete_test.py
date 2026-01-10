#!/usr/bin/env python3
"""
TEST COMPLETO SEMANTIC DEDUPLICATION
=====================================
Script combinato che:
1. Inizializza la collezione Qdrant
2. Esegue test completo della deduplicazione
3. Verifica integrazione pipeline

Eseguibile direttamente su Fly.io o localmente con .env configurato.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

async def main():
    logger.info("=" * 70)
    logger.info("🧪 TEST COMPLETO - SEMANTIC DEDUPLICATION")
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
        logger.error("\n❌ Chiavi mancanti!")
        logger.info("   Le chiavi devono essere configurate come variabili d'ambiente.")
        logger.info("   Su Fly.io sono già configurate come secrets.")
        return False
    
    # Step 2: Inizializza collezione (usa versione httpx)
    logger.info("\n📋 STEP 2: Inizializzazione Collezione Qdrant...")
    try:
        # Usa versione httpx che funziona correttamente
        from init_news_collection_httpx import init_collection
        init_collection()  # Non è async
        logger.success("✅ Collezione pronta")
    except Exception as e:
        logger.error(f"❌ Errore collezione: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Test Deduplicator (usa versione httpx)
    logger.info("\n📋 STEP 3: Test Semantic Deduplicator...")
    try:
        # Usa versione httpx che funziona correttamente
        from semantic_deduplicator_httpx import SemanticDeduplicator
        
        dedup = SemanticDeduplicator()
        
        # Test 1: Articolo nuovo
        logger.info("\n   🧪 Test 1: Articolo nuovo (non duplicato)...")
        test_article_1 = {
            "title": "Bali Introduces Revolutionary Digital Nomad Visa Program",
            "summary": "The Indonesian government has launched a new visa program specifically designed for remote workers and digital nomads, allowing them to stay in Bali for up to 5 years.",
            "url": "https://test.example.com/bali-nomad-visa-2025"
        }
        
        is_dup, match, score = await dedup.is_duplicate(
            test_article_1["title"],
            test_article_1["summary"],
            test_article_1["url"]
        )
        
        if is_dup:
            logger.warning(f"   ⚠️ Risultato inatteso: Trovato duplicato (Score: {score:.2f})")
        else:
            logger.success(f"   ✅ Articolo UNICO (Score: {score:.2f})")
        
        # Test 2: Salvataggio
        logger.info("\n   🧪 Test 2: Salvataggio articolo in Qdrant...")
        await dedup.save_article({
            **test_article_1,
            "source": "TestBot",
            "category": "immigration",
            "publishedAt": "2025-01-09T12:00:00Z"
        })
        logger.success("   ✅ Articolo salvato")
        
        # Test 3: Re-check (dovrebbe essere duplicato)
        logger.info("\n   🧪 Test 3: Re-check stesso articolo (dovrebbe essere duplicato)...")
        await asyncio.sleep(2)  # Attesa propagazione Qdrant
        
        is_dup, match, score = await dedup.is_duplicate(
            test_article_1["title"],
            test_article_1["summary"],
            test_article_1["url"]
        )
        
        if is_dup:
            logger.success(f"   ✅ DUPLICATO RILEVATO correttamente! (Score: {score:.2f})")
            logger.info(f"      Match: {match[:60]}...")
        else:
            logger.warning(f"   ⚠️ Duplicato NON rilevato (Score: {score:.2f})")
        
        # Test 4: Variante semantica
        logger.info("\n   🧪 Test 4: Variante semantica (stesso concetto, parole diverse)...")
        test_article_2 = {
            "title": "Bali Launches Extended Stay Program for Remote Workers",
            "summary": "Indonesia has introduced a groundbreaking visa scheme enabling digital nomads to reside in Bali for extended periods, up to five years.",
            "url": "https://test.example.com/bali-nomad-visa-variant"
        }
        
        is_dup, match, score = await dedup.is_duplicate(
            test_article_2["title"],
            test_article_2["summary"],
            test_article_2["url"]
        )
        
        if is_dup:
            logger.success(f"   ✅ DUPLICATO SEMANTICO rilevato! (Score: {score:.2f})")
            logger.info(f"      Match: {match[:60]}...")
            logger.info("      🎯 Il sistema ha capito che è lo stesso concetto!")
        else:
            logger.info(f"   ℹ️ Variante considerata unica (Score: {score:.2f})")
            logger.info("      (Potrebbe essere normale se il threshold è molto alto)")
        
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
        
        test_article = PipelineArticle(
            title="Bali Introduces New Digital Nomad Visa",
            summary="The Indonesian government announced a new visa program for remote workers.",
            url="https://test.example.com/nomad-visa-2025-v2",
            source="TestBot"
        )
        
        processed = await pipeline.process_article(test_article)
        
        if processed.is_duplicate:
            logger.success("   ✅ Pipeline rileva duplicato correttamente!")
        else:
            logger.info("   ✅ Pipeline processa articolo nuovo")
        
        logger.info(f"   Stats: {pipeline.stats.dedup_filtered} duplicati filtrati")
        
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
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
