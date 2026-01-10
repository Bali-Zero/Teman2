#!/usr/bin/env python3
"""
Analizza struttura Lampiran II per capire come sono organizzate le informazioni PMA
"""

import asyncio
import os
import sys

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAMPIRAN_DIR = os.path.join(PROJECT_ROOT, "lampiran")
LAMPIRAN_II = os.path.join(LAMPIRAN_DIR, "PP Nomor 28 Tahun 2025 - Lampiran II.pdf")


async def analyze_lampiran_ii():
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("=" * 70)
    print("ANALISI STRUTTURA LAMPIRAN II")
    print("=" * 70)
    
    # Analizza prime 10 pagine per capire struttura
    for page_num in [1, 2, 3, 5, 10, 20, 50]:
        print(f"\n{'='*70}")
        print(f"PAGINA {page_num}")
        print(f"{'='*70}\n")
        
        prompt = f"""
        Analizza questa pagina del Lampiran II del PP 28/2025.
        
        Descrivi in dettaglio:
        1. Quante colonne ha la tabella?
        2. Quali sono le intestazioni delle colonne (tutte)?
        3. Ci sono codici KBLI nella tabella?
        4. Ci sono informazioni su PMA (Penanaman Modal Asing) o percentuali di investimento straniero?
        5. Come sono organizzate le informazioni? Le tabelle collegano KBLI a PMA?
        6. Mostra un esempio di riga completa della tabella se possibile
        
        Rispondi in modo molto dettagliato.
        """
        
        try:
            result = await vision_service.analyze_page(
                LAMPIRAN_II, page_num, prompt=prompt, is_drive_file=False
            )
            
            # Mostra risultato
            print(result[:1000])
            if len(result) > 1000:
                print("\n... (troncato)")
                
        except Exception as e:
            print(f"❌ Errore: {e}")


if __name__ == "__main__":
    asyncio.run(analyze_lampiran_ii())
