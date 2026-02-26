#!/usr/bin/env python3
"""
Script per ingerire PDF dal desktop con KG extraction e Drive upload automatici.
Include reminder per documenti temporanei.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend-rag"))

import asyncpg
from backend.app.core.config import settings
from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_reminder_table_if_not_exists(conn):
    """Crea tabella per reminder se non esiste."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS document_reminders (
            id SERIAL PRIMARY KEY,
            document_id VARCHAR(255) NOT NULL,
            document_title VARCHAR(500) NOT NULL,
            reminder_date TIMESTAMP NOT NULL,
            reminder_message TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            confirmed_at TIMESTAMP,
            notes TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_reminder_date ON document_reminders(reminder_date);
        CREATE INDEX IF NOT EXISTS idx_status ON document_reminders(status);
    """)


async def create_reminder(
    conn, document_id: str, document_title: str, days: int = 30, message: str = None
):
    """Crea un reminder per un documento."""
    reminder_date = datetime.now() + timedelta(days=days)

    await conn.execute(
        """
        INSERT INTO document_reminders (document_id, document_title, reminder_date, reminder_message, status)
        VALUES ($1, $2, $3, $4, 'pending')
        ON CONFLICT DO NOTHING
    """,
        document_id,
        document_title,
        reminder_date,
        message or f"Verifica se confermare il documento: {document_title}",
    )

    logger.info(
        f"✅ Reminder creato per {document_title} - data: {reminder_date.strftime('%Y-%m-%d')}"
    )


async def ingest_pdf(file_path: str, service: LegalIngestionService) -> dict:
    """Ingerisce un singolo PDF."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Iniziando ingestione: {Path(file_path).name}")
    logger.info(f"{'=' * 60}")

    try:
        result = await service.ingest_legal_document(file_path)

        if result.get("success"):
            logger.info("✅ Successo!")
            logger.info(f"   - Titolo: {result.get('book_title')}")
            logger.info(f"   - Chunks: {result.get('chunks_created')}")

            # KG extraction stats
            kg_stats = result.get("kg_extraction", {})
            if kg_stats and not kg_stats.get("error"):
                logger.info(f"   - KG Entities: {kg_stats.get('entities', 0)}")
                logger.info(f"   - KG Relations: {kg_stats.get('relationships', 0)}")

            # Drive info
            if result.get("legal_metadata", {}).get("drive_file_id"):
                logger.info(
                    f"   - Drive ID: {result['legal_metadata']['drive_file_id']}"
                )

            return result
        else:
            logger.error(f"❌ Errore: {result.get('error')}")
            return result

    except Exception as e:
        logger.error(f"❌ Errore durante ingestione: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def main():
    """Main function."""
    desktop_path = Path.home() / "Desktop"

    # Lista PDF da ingerire con configurazioni
    pdfs_to_ingest = [
        {
            "file": desktop_path / "PP Nomor 28 Tahun 2025.pdf",
            "needs_reminder": False,
        },
        {
            "file": desktop_path / "peraturan-bps-no-7-tahun-2025.pdf",
            "needs_reminder": False,
        },
        {
            "file": desktop_path
            / "INGUB-6-TAHUN-2025-PENGHENTIAN-SEMENTARA-PEMBERIAN-IZIN-TOKO-MODERN-BERJEJARING.pdf",
            "needs_reminder": True,
            "reminder_days": 30,
            "reminder_message": "Verifica se confermare INGUB-6-TAHUN-2025 (PENGHENTIAN SEMENTARA PEMBERIAN IZIN TOKO MODERN BERJEJARING) - potrebbe essere temporaneo",
        },
    ]

    # Verifica file esistenti
    existing_pdfs = []
    for pdf_config in pdfs_to_ingest:
        pdf_path = pdf_config["file"]
        if pdf_path.exists():
            existing_pdfs.append(pdf_config)
        else:
            logger.warning(f"⚠️ File non trovato: {pdf_path}")

    if not existing_pdfs:
        logger.error("❌ Nessun file PDF trovato sul desktop")
        return

    logger.info(f"Trovati {len(existing_pdfs)} PDF da ingerire")

    # Connessione database per reminder (opzionale)
    db_pool = None
    try:
        db_url = settings.database_url
        if not db_url:
            logger.warning(
                "⚠️ DATABASE_URL non configurato - i reminder non saranno salvati"
            )
        else:
            db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
            logger.info("✅ Connessione database stabilita")
    except Exception as e:
        logger.warning(
            f"⚠️ Errore connessione database (i reminder non saranno salvati): {e}"
        )
        db_pool = None

    if db_pool:
        async with db_pool.acquire() as conn:
            await create_reminder_table_if_not_exists(conn)

    # Inizializza servizio ingestione
    service = LegalIngestionService(collection_name="legal_unified")

    # Ingerisci ogni PDF
    results = []
    for pdf_config in existing_pdfs:
        pdf_path = pdf_config["file"]
        result = await ingest_pdf(str(pdf_path), service)
        results.append({"file": pdf_path.name, "result": result})

        # Crea reminder se necessario
        if pdf_config.get("needs_reminder") and result.get("success") and db_pool:
            document_id = result.get("document_id") or result.get(
                "legal_metadata", {}
            ).get("legal_number", "unknown")
            document_title = result.get("book_title") or pdf_path.stem

            try:
                async with db_pool.acquire() as conn:
                    await create_reminder(
                        conn=conn,
                        document_id=document_id,
                        document_title=document_title,
                        days=pdf_config.get("reminder_days", 30),
                        message=pdf_config.get("reminder_message"),
                    )
            except Exception as e:
                logger.warning(f"⚠️ Errore creazione reminder: {e}")

    # Riepilogo
    logger.info(f"\n{'=' * 60}")
    logger.info("RIEPILOGO INGESTIONE")
    logger.info(f"{'=' * 60}")

    successful = sum(1 for r in results if r["result"].get("success"))
    failed = len(results) - successful

    logger.info(f"✅ Successi: {successful}/{len(results)}")
    logger.info(f"❌ Falliti: {failed}/{len(results)}")

    for r in results:
        status = "✅" if r["result"].get("success") else "❌"
        logger.info(f"{status} {r['file']}")

    # Mostra reminder creati
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                reminders = await conn.fetch("""
                    SELECT document_title, reminder_date, reminder_message
                    FROM document_reminders
                    WHERE status = 'pending'
                    ORDER BY reminder_date
                """)

                if reminders:
                    logger.info(f"\n📅 Reminder attivi: {len(reminders)}")
                    for rem in reminders:
                        logger.info(
                            f"   - {rem['document_title']}: {rem['reminder_date'].strftime('%Y-%m-%d')}"
                        )
        except Exception as e:
            logger.warning(f"⚠️ Errore lettura reminder: {e}")

        await db_pool.close()

    logger.info("\n✅ Processo completato!")


if __name__ == "__main__":
    asyncio.run(main())
