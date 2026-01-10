#!/usr/bin/env python3
"""
Test per capire la struttura delle tabelle in Lampiran II
"""

import asyncio
import os
import sys
from pathlib import Path

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")
LAMPIRAN_II = os.path.join(LAMPIRAN_DIR, "PP Nomor 28 Tahun 2025 - Lampiran II.pdf")


async def test_pages():
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("🔍 Test struttura Lampiran II\n")
    
    # Test pagine diverse per capire dove iniziano le tabelle
    test_pages = [1, 5, 10, 20, 50, 100, 200]
    
    for page_num in test_pages:
        print(f"\n{'='*60}")
        print(f"PAGINA {page_num}")
        print(f"{'='*60}\n")
        
        prompt = """
        Descrivi cosa vedi in questa pagina del Lampiran II del PP 28/2025.
        
        Indica:
        1. Ci sono tabelle? Quante colonne hanno?
        2. Ci sono codici numerici a 5 cifre (KBLI)?
        3. Ci sono parole come "Risiko", "PMA", "Skala"?
        4. Qual è la struttura generale della pagina?
        
        Rispondi in modo dettagliato.
        """
        
        try:
            result = await vision_service.analyze_page(
                LAMPIRAN_II, page_num, prompt=prompt, is_drive_file=False
            )
            print(result[:500] + "..." if len(result) > 500 else result)
        except Exception as e:
            print(f"❌ Errore: {e}")


if __name__ == "__main__":
    asyncio.run(test_pages())
