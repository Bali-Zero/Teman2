#!/usr/bin/env python3
"""
Analizza pagine specifiche del PP 28/2025 che contengono riferimenti a PMA e KBLI
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

PP28_MAIN = "/Users/antonellosiano/Desktop/PP Nomor 28 Tahun 2025 (1).pdf"


async def analyze_specific_pages():
    vision_service = PDFVisionService()
    
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("=" * 70)
    print("ANALISI PAGINE SPECIFICHE CON RIFERIMENTI PMA E KBLI")
    print("=" * 70)
    
    # Pagine più promettenti basate sulla ricerca precedente
    target_pages = [84, 118, 119]
    
    for page_num in target_pages:
        print(f"\n{'='*70}")
        print(f"PAGINA {page_num}")
        print(f"{'='*70}\n")
        
        prompt = f"""
        Analizza questa pagina del documento principale PP 28/2025.
        
        Questa pagina contiene riferimenti sia a PMA che a KBLI.
        
        Estrai e descrivi in modo molto dettagliato:
        1. Quali sono le regole specifiche su PMA per KBLI menzionate?
        2. Come vengono determinate le regole PMA per ogni KBLI?
        3. Ci sono riferimenti espliciti a:
           - Daftar Positif Investasi (Lista Positiva degli Investimenti)
           - Perpres 10/2021 o altri regolamenti sugli investimenti
           - Come ottenere informazioni PMA per un KBLI specifico
        4. Il documento spiega dove trovare le informazioni PMA per ogni KBLI?
        5. Ci sono tabelle, liste o riferimenti a documenti esterni che contengono le regole PMA per KBLI?
        
        Cita esattamente il testo rilevante dalla pagina.
        """
        
        try:
            result = await vision_service.analyze_page(
                PP28_MAIN, page_num, prompt=prompt, is_drive_file=False
            )
            
            print(result)
            print("\n")
                
        except Exception as e:
            print(f"❌ Errore pagina {page_num}: {e}")


if __name__ == "__main__":
    asyncio.run(analyze_specific_pages())
