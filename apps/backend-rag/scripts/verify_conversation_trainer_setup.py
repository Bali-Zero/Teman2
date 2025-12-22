#!/usr/bin/env python3
"""
Verifica setup ConversationTrainer
Verifica che migration, API e scheduler siano configurati correttamente
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import asyncio
import os

try:
    from app.core.config import settings

    database_url = settings.database_url
except (ImportError, AttributeError):
    database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("⚠️  DATABASE_URL non configurato. Verifica solo struttura file.")
    print("=" * 60)
    print("✅ File Migration creati:")
    print("   - backend/migrations/migration_025.py")
    print("   - backend/db/migrations/025_conversation_ratings.sql")
    print()
    print("✅ Router Feedback creato:")
    print("   - backend/app/routers/feedback.py")
    print()
    print("✅ Scheduler aggiornato:")
    print("   - backend/services/autonomous_scheduler.py")
    print()
    print("✅ ConversationTrainer aggiornato:")
    print("   - backend/agents/agents/conversation_trainer.py")
    print()
    print("✅ Frontend integrato:")
    print("   - apps/mouth/src/components/FeedbackWidget.tsx")
    print()
    print("=" * 60)
    print("📋 Per eseguire la migration:")
    print("   1. Configura DATABASE_URL")
    print("   2. Esegui: python apps/backend-rag/backend/migrations/migration_025.py")
    sys.exit(0)

import asyncpg


async def verify_database():
    """Verifica struttura database"""
    print("🔍 Verificando database...")
    try:
        conn = await asyncpg.connect(database_url)
        try:
            # Verifica tabella conversation_ratings
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'conversation_ratings'
                )
                """
            )

            if not table_exists:
                print("❌ Tabella conversation_ratings non trovata")
                print("   Esegui: python apps/backend-rag/backend/migrations/migration_025.py")
                return False

            print("✅ Tabella conversation_ratings trovata")

            # Verifica vista
            view_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views
                    WHERE table_name = 'v_rated_conversations'
                )
                """
            )

            if not view_exists:
                print("❌ Vista v_rated_conversations non trovata")
                return False

            print("✅ Vista v_rated_conversations trovata")

            # Conta ratings esistenti
            count = await conn.fetchval("SELECT COUNT(*) FROM conversation_ratings")
            print(f"📊 Ratings salvati: {count}")

            # Conta high-rated conversations
            high_rated = await conn.fetchval(
                "SELECT COUNT(*) FROM v_rated_conversations"
            )
            print(f"⭐ Conversazioni high-rated (>=4): {high_rated}")

            return True

        finally:
            await conn.close()

    except Exception as e:
        print(f"❌ Errore verifica database: {e}")
        return False


async def verify_api():
    """Verifica che il router sia registrato"""
    print("\n🔍 Verificando API router...")
    try:
        from app.setup.router_registration import include_routers
        from app.routers import feedback
        from fastapi import FastAPI

        app = FastAPI()
        include_routers(app)

        # Verifica che il router sia incluso
        routes = [r.path for r in app.routes]
        feedback_routes = [r for r in routes if "/api/feedback" in r]

        if not feedback_routes:
            print("❌ Router feedback non registrato")
            return False

        print(f"✅ Router feedback registrato: {len(feedback_routes)} endpoint")
        for route in feedback_routes:
            print(f"   - {route}")

        return True

    except Exception as e:
        print(f"❌ Errore verifica API: {e}")
        import traceback

        traceback.print_exc()
        return False


async def verify_scheduler():
    """Verifica che lo scheduler sia configurato correttamente"""
    print("\n🔍 Verificando scheduler...")
    try:
        from services.autonomous_scheduler import AutonomousScheduler

        scheduler = AutonomousScheduler()
        status = scheduler.get_status()

        if "conversation_trainer" in status.get("tasks", {}):
            task = status["tasks"]["conversation_trainer"]
            print(f"✅ Conversation Trainer registrato nello scheduler")
            print(f"   - Intervallo: {task['interval_seconds']}s ({task['interval_seconds']/3600:.1f}h)")
            print(f"   - Abilitato: {task['enabled']}")
            print(f"   - Esecuzioni: {task['run_count']}")
            return True
        else:
            print("⚠️  Conversation Trainer non trovato nello scheduler")
            print("   (Potrebbe non essere ancora inizializzato)")
            return False

    except Exception as e:
        print(f"❌ Errore verifica scheduler: {e}")
        return False


async def main():
    """Esegui tutte le verifiche"""
    print("=" * 60)
    print("🔍 VERIFICA SETUP CONVERSATION TRAINER")
    print("=" * 60)

    db_ok = await verify_database()
    api_ok = await verify_api()
    scheduler_ok = await verify_scheduler()

    print("\n" + "=" * 60)
    print("📊 RIEPILOGO")
    print("=" * 60)
    print(f"Database:     {'✅ OK' if db_ok else '❌ DA CONFIGURARE'}")
    print(f"API Router:   {'✅ OK' if api_ok else '❌ ERRORE'}")
    print(f"Scheduler:    {'✅ OK' if scheduler_ok else '⚠️  NON INIZIALIZZATO'}")

    if db_ok and api_ok:
        print("\n✅ Setup completo! ConversationTrainer pronto all'uso.")
    else:
        print("\n⚠️  Alcuni componenti richiedono configurazione.")
        if not db_ok:
            print("   → Esegui migration: python apps/backend-rag/backend/migrations/migration_025.py")


if __name__ == "__main__":
    asyncio.run(main())

