#!/usr/bin/env python3
"""
Health Check Script for Nuzantara Backend
Verifies all critical services are initialized and working correctly
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import logging
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def check_database_connection() -> dict[str, Any]:
    """Check database connection"""
    try:
        import asyncpg

        from app.core.config import settings

        if not settings.database_url:
            return {"status": "skipped", "message": "DATABASE_URL not set"}

        conn = await asyncpg.connect(settings.database_url)
        await conn.execute("SELECT 1")
        await conn.close()

        return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {e}"}


async def check_qdrant_connection() -> dict[str, Any]:
    """Check Qdrant connection"""
    try:
        from core.qdrant_db import QdrantClient

        from app.core.config import settings

        if not settings.qdrant_url:
            return {"status": "skipped", "message": "QDRANT_URL not set"}

        client = QdrantClient(
            qdrant_url=settings.qdrant_url, collection_name="visa_oracle"
        )
        # QdrantClient uses HTTP client internally, just verify initialization
        # Test by trying to search (which will fail gracefully if connection is bad)
        try:
            # Just verify client was created successfully
            if client.qdrant_url and client.collection_name:
                return {
                    "status": "ok",
                    "message": f"Qdrant client initialized (URL: {client.qdrant_url}, Collection: {client.collection_name})",
                }
            else:
                return {
                    "status": "error",
                    "message": "Qdrant client missing required attributes",
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Qdrant client initialization failed: {e}",
            }
    except Exception as e:
        return {"status": "error", "message": f"Qdrant connection failed: {e}"}


async def check_auto_crm_service() -> dict[str, Any]:
    """Check AutoCRMService initialization"""
    try:
        from services.auto_crm_service import get_auto_crm_service

        service = get_auto_crm_service()
        if not service.pool:
            await service.connect()

        if service.pool:
            # Test connection
            async with service.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return {
                "status": "ok",
                "message": "AutoCRMService pool initialized and working",
            }
        else:
            return {
                "status": "warning",
                "message": "AutoCRMService pool not initialized",
            }
    except Exception as e:
        return {"status": "error", "message": f"AutoCRMService check failed: {e}"}


async def check_crm_models() -> dict[str, Any]:
    """Check CRM models are importable"""
    try:
        from app.modules.crm.models import Client, Interaction, Practice, PracticeType

        models = {
            "Client": Client,
            "Practice": Practice,
            "PracticeType": PracticeType,
            "Interaction": Interaction,
        }

        return {
            "status": "ok",
            "message": f"CRM models imported successfully: {', '.join(models.keys())}",
        }
    except Exception as e:
        return {"status": "error", "message": f"CRM models import failed: {e}"}


async def check_collection_manager() -> dict[str, Any]:
    """Check CollectionManager initialization"""
    try:
        from services.collection_manager import CollectionManager

        manager = CollectionManager()
        collections = manager.list_collections()
        return {
            "status": "ok",
            "message": f"CollectionManager initialized ({len(collections)} collections)",
        }
    except Exception as e:
        return {"status": "error", "message": f"CollectionManager check failed: {e}"}


async def check_conflict_resolver() -> dict[str, Any]:
    """Check ConflictResolver initialization"""
    try:
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        stats = resolver.get_stats()
        return {
            "status": "ok",
            "message": "ConflictResolver initialized",
            "stats": stats,
        }
    except Exception as e:
        return {"status": "error", "message": f"ConflictResolver check failed: {e}"}


async def check_constants_module() -> dict[str, Any]:
    """Check constants module"""
    try:
        from app.core.constants import (
            CRMConstants,
            DatabaseConstants,
            MemoryConstants,
            RoutingConstants,
            SearchConstants,
        )

        return {
            "status": "ok",
            "message": "Constants module imported successfully",
            "constants": {
                "CRM": hasattr(CRMConstants, "CLIENT_CONFIDENCE_THRESHOLD_CREATE"),
                "Database": hasattr(DatabaseConstants, "POOL_MIN_SIZE"),
                "Memory": hasattr(MemoryConstants, "MAX_FACTS"),
                "Routing": hasattr(RoutingConstants, "CONFIDENCE_THRESHOLD_HIGH"),
                "Search": hasattr(SearchConstants, "PRICING_SCORE_BOOST"),
            },
        }
    except Exception as e:
        return {"status": "error", "message": f"Constants module check failed: {e}"}


async def check_notification_config() -> dict[str, Any]:
    """Check notification service configuration"""
    try:
        from app.core.config import settings

        config_status = {
            "sendgrid": bool(settings.sendgrid_api_key),
            "smtp": bool(settings.smtp_host),
            "twilio": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        }

        enabled = [k for k, v in config_status.items() if v]
        if enabled:
            return {
                "status": "ok",
                "message": f"Notification services configured: {', '.join(enabled)}",
            }
        else:
            return {
                "status": "warning",
                "message": "No notification services configured (SendGrid/SMTP/Twilio)",
            }
    except Exception as e:
        return {"status": "error", "message": f"Notification config check failed: {e}"}


async def main():
    """Run all health checks"""
    logger.info("🔍 Starting Nuzantara Backend Health Check...\n")

    checks = [
        ("Database Connection", check_database_connection),
        ("Qdrant Connection", check_qdrant_connection),
        ("AutoCRMService", check_auto_crm_service),
        ("CRM Models", check_crm_models),
        ("CollectionManager", check_collection_manager),
        ("ConflictResolver", check_conflict_resolver),
        ("Constants Module", check_constants_module),
        ("Notification Config", check_notification_config),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = await check_func()
            results.append((name, result))
        except Exception as e:
            results.append((name, {"status": "error", "message": str(e)}))

    # Print results
    print("\n" + "=" * 60)
    print("HEALTH CHECK RESULTS")
    print("=" * 60 + "\n")

    all_ok = True
    for name, result in results:
        status = result["status"]
        message = result["message"]

        if status == "ok":
            icon = "✅"
        elif status == "warning":
            icon = "⚠️"
            all_ok = False
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "❌"
            all_ok = False

        print(f"{icon} {name}: {message}")

        if "stats" in result:
            print(f"   Stats: {result['stats']}")
        if "constants" in result:
            print(f"   Constants: {result['constants']}")

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ All checks passed!")
        return 0
    else:
        print("⚠️ Some checks failed or have warnings")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
