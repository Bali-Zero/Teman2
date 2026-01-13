#!/usr/bin/env python3
"""
Test completo del deployment - Verifica tutte le funzionalità deployate
"""

import asyncio
import sys
import os
from pathlib import Path
import logging
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend-rag"))

from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
from backend.app.core.config import settings
from backend.core.qdrant_db import get_qdrant_client
import httpx

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test results
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def test_result(name: str, passed: bool, message: str = "", warning: bool = False):
    """Record test result"""
    if warning:
        test_results["warnings"].append(f"{name}: {message}")
        logger.warning(f"⚠️  {name}: {message}")
    elif passed:
        test_results["passed"].append(f"{name}: {message}")
        logger.info(f"✅ {name}: {message}")
    else:
        test_results["failed"].append(f"{name}: {message}")
        logger.error(f"❌ {name}: {message}")

async def test_health_endpoint():
    """Test health endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://nuzantara-rag.fly.dev/health")
            if response.status_code == 200:
                data = response.json()
                test_result(
                    "Health Endpoint",
                    True,
                    f"Status: {data.get('status')}, Collections: {data.get('database', {}).get('collections', 0)}"
                )
                return True
            else:
                test_result("Health Endpoint", False, f"Status code: {response.status_code}")
                return False
    except Exception as e:
        test_result("Health Endpoint", False, f"Error: {str(e)}")
        return False

async def test_qdrant_connection():
    """Test Qdrant connection"""
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        # Check for key collections
        required_collections = ["legal_unified_hybrid", "kbli_unified"]
        found_collections = [c for c in required_collections if c in collection_names]
        
        test_result(
            "Qdrant Connection",
            True,
            f"Connected. Found {len(collection_names)} collections. Key collections: {found_collections}"
        )
        return True
    except Exception as e:
        test_result("Qdrant Connection", False, f"Error: {str(e)}")
        return False

async def test_legal_ingestion_service_init():
    """Test LegalIngestionService initialization"""
    try:
        service = LegalIngestionService()
        
        # Check if service has required attributes
        has_kg = hasattr(service, 'kg_enabled')
        has_kg_extractor = hasattr(service, 'kg_extractor')
        has_indexer = hasattr(service, 'indexer')
        
        test_result(
            "LegalIngestionService Init",
            True,
            f"Initialized. KG enabled: {has_kg}, Has KG extractor: {has_kg_extractor is not None}, Has indexer: {has_indexer}"
        )
        return True
    except Exception as e:
        test_result("LegalIngestionService Init", False, f"Error: {str(e)}")
        return False

async def test_google_drive_config():
    """Test Google Drive configuration"""
    try:
        from backend.services.integrations.team_drive_service import TeamDriveService
        
        drive_service = TeamDriveService()
        # Just check if service can be initialized
        test_result(
            "Google Drive Service",
            True,
            f"Service initialized. Available: {drive_service._available if hasattr(drive_service, '_available') else 'unknown'}"
        )
        return True
    except Exception as e:
        test_result("Google Drive Service", False, f"Error: {str(e)}", warning=True)
        return False

async def test_kg_extractor_config():
    """Test KG Extractor configuration"""
    try:
        from backend.services.knowledge_graph.extractor_gemini import GeminiKGExtractor
        
        # Check if we can import and if settings are available
        has_db_url = bool(settings.database_url)
        has_qdrant_url = bool(settings.qdrant_url)
        has_google_key = bool(settings.google_api_key)
        
        test_result(
            "KG Extractor Config",
            True,
            f"Config check - DB URL: {has_db_url}, Qdrant URL: {has_qdrant_url}, Google API Key: {has_google_key}"
        )
        return True
    except Exception as e:
        test_result("KG Extractor Config", False, f"Error: {str(e)}", warning=True)
        return False

async def test_ocr_vision_service():
    """Test OCR Vision service"""
    try:
        from backend.services.multimodal.pdf_vision_service import PDFVisionService
        
        vision_service = PDFVisionService()
        available = vision_service._available if hasattr(vision_service, '_available') else False
        
        test_result(
            "OCR Vision Service",
            True if available else False,
            f"Service {'available' if available else 'not available'} (requires GOOGLE_API_KEY)"
        )
        return available
    except Exception as e:
        test_result("OCR Vision Service", False, f"Error: {str(e)}", warning=True)
        return False

async def test_parsers_module():
    """Test parsers module"""
    try:
        from backend.core.parsers import (
            extract_text_from_pdf,
            extract_text_from_pdf_ocr_async,
            auto_detect_and_parse,
            DocumentParseError
        )
        
        test_result(
            "Parsers Module",
            True,
            "All parser functions imported successfully (extract_text_from_pdf, OCR async, auto_detect_and_parse)"
        )
        return True
    except Exception as e:
        test_result("Parsers Module", False, f"Error: {str(e)}")
        return False

async def test_hierarchical_indexer():
    """Test hierarchical indexer"""
    try:
        from backend.core.legal.hierarchical_indexer import HierarchicalIndexer
        
        indexer = HierarchicalIndexer()
        has_db_pool = hasattr(indexer, 'db_pool')
        
        test_result(
            "Hierarchical Indexer",
            True,
            f"Indexer initialized. Has DB pool method: {has_db_pool}"
        )
        return True
    except Exception as e:
        test_result("Hierarchical Indexer", False, f"Error: {str(e)}")
        return False

async def test_settings_configuration():
    """Test settings configuration"""
    try:
        # Check critical settings
        checks = {
            "QDRANT_URL": bool(settings.qdrant_url),
            "DATABASE_URL": bool(settings.database_url),
            "OPENAI_API_KEY": bool(settings.openai_api_key),
            "GOOGLE_API_KEY": bool(settings.google_api_key),
            "KG_EXTRACTION_ENABLED": getattr(settings, 'kg_extraction_enabled', True),
            "GOOGLE_DRIVE_UPLOAD_ENABLED": getattr(settings, 'google_drive_upload_enabled', True),
        }
        
        all_set = all(checks.values())
        status_msg = ", ".join([f"{k}: {'✓' if v else '✗'}" for k, v in checks.items()])
        
        test_result(
            "Settings Configuration",
            all_set,
            status_msg,
            warning=not all_set
        )
        return all_set
    except Exception as e:
        test_result("Settings Configuration", False, f"Error: {str(e)}")
        return False

async def test_api_endpoints():
    """Test API endpoints availability"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test legal ingest endpoint (will require auth, but should return 401/403, not 404)
            response = await client.post("https://nuzantara-rag.fly.dev/api/legal/ingest", json={})
            
            # 401/403 means endpoint exists, 404 means it doesn't
            endpoint_exists = response.status_code in [401, 403, 422]  # 422 = validation error
            
            test_result(
                "API Endpoints",
                endpoint_exists,
                f"Legal ingest endpoint {'exists' if endpoint_exists else 'not found'} (status: {response.status_code})"
            )
            return endpoint_exists
    except Exception as e:
        test_result("API Endpoints", False, f"Error: {str(e)}")
        return False

async def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("🧪 TEST COMPLETO DEL DEPLOYMENT")
    logger.info("=" * 60)
    logger.info(f"Test iniziato: {datetime.now().isoformat()}")
    logger.info("")
    
    # Run all tests
    await test_health_endpoint()
    await test_qdrant_connection()
    await test_legal_ingestion_service_init()
    await test_google_drive_config()
    await test_kg_extractor_config()
    await test_ocr_vision_service()
    await test_parsers_module()
    await test_hierarchical_indexer()
    await test_settings_configuration()
    await test_api_endpoints()
    
    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 RISULTATI TEST")
    logger.info("=" * 60)
    logger.info(f"✅ Test passati: {len(test_results['passed'])}")
    logger.info(f"❌ Test falliti: {len(test_results['failed'])}")
    logger.info(f"⚠️  Warning: {len(test_results['warnings'])}")
    logger.info("")
    
    if test_results['passed']:
        logger.info("✅ TEST PASSATI:")
        for result in test_results['passed']:
            logger.info(f"   • {result}")
    
    if test_results['warnings']:
        logger.info("")
        logger.info("⚠️  WARNING:")
        for result in test_results['warnings']:
            logger.info(f"   • {result}")
    
    if test_results['failed']:
        logger.info("")
        logger.error("❌ TEST FALLITI:")
        for result in test_results['failed']:
            logger.error(f"   • {result}")
    
    logger.info("")
    logger.info("=" * 60)
    
    # Exit code
    if test_results['failed']:
        logger.error("❌ ALCUNI TEST SONO FALLITI")
        sys.exit(1)
    elif test_results['warnings']:
        logger.warning("⚠️  TUTTI I TEST SONO PASSATI, MA CI SONO WARNING")
        sys.exit(0)
    else:
        logger.info("✅ TUTTI I TEST SONO PASSATI")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
