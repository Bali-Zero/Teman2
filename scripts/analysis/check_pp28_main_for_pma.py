#!/usr/bin/env python3
"""
Verifica se il documento principale PP 28/2025 contiene informazioni PMA per KBLI
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


async def check_pp28_main():
    if not os.path.exists(PP28_MAIN):
        print(f"❌ File principale non trovato: {PP28_MAIN}")
        return
    
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("=" * 70)
    print("VERIFICA DOCUMENTO PRINCIPALE PP 28/2025 PER INFORMAZIONI PMA")
    print("=" * 70)
    
    import pypdf
    reader = pypdf.PdfReader(PP28_MAIN)
    total_pages = len(reader.pages)
    
    print(f"\n📄 File: PP Nomor 28 Tahun 2025 (1).pdf")
    print(f"   Pagine totali: {total_pages}\n")
    
    # Cerca nelle prime 50 pagine (dove di solito ci sono le regole generali)
    for page_num in [1, 10, 20, 30, 40, 50]:
        if page_num > total_pages:
            break
            
        print(f"\n{'='*70}")
        print(f"PAGINA {page_num}")
        print(f"{'='*70}\n")
        
        prompt = f"""
        Analizza questa pagina del documento principale PP 28/2025.
        
        Cerca:
        1. Regole o tabelle su PMA (Penanaman Modal Asing) per KBLI
        2. Percentuali di investimento straniero (100%, 67%, 49%, ecc.)
        3. Tabelle che collegano codici KBLI a percentuali PMA
        4. Sezioni che spiegano come determinare se un KBLI permette PMA e con quale percentuale
        
        Se trovi informazioni PMA, descrivi in dettaglio cosa vedi e dove si trovano.
        """
        
        try:
            result = await vision_service.analyze_page(
                PP28_MAIN, page_num, prompt=prompt, is_drive_file=False
            )
            
            # Cerca riferimenti a PMA
            has_pma = any(keyword in result.upper() for keyword in ["PMA", "ASING", "FOREIGN", "100%", "67%", "49%", "PENANAMAN MODAL"])
            
            if has_pma:
                print("✅ TROVATO RIFERIMENTI A PMA!")
                print(f"\n{result[:800]}...")
            else:
                print("⏭️ Nessun riferimento PMA trovato")
                
        except Exception as e:
            print(f"❌ Errore: {e}")


if __name__ == "__main__":
    asyncio.run(check_pp28_main())
