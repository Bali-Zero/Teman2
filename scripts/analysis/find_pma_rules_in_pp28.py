#!/usr/bin/env python3
"""
Cerca nel documento principale PP 28/2025 le regole generali su PMA
"""

import asyncio
import os
import sys
import re

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(backend_path, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from services.multimodal.pdf_vision_service import PDFVisionService

PP28_MAIN = "/Users/antonellosiano/Desktop/PP Nomor 28 Tahun 2025 (1).pdf"


async def find_pma_sections():
    if not os.path.exists(PP28_MAIN):
        print(f"❌ File principale non trovato: {PP28_MAIN}")
        return
    
    vision_service = PDFVisionService()
    if not vision_service._available:
        print("❌ Vision service non disponibile")
        return
    
    print("=" * 70)
    print("RICERCA REGOLE PMA NEL DOCUMENTO PRINCIPALE PP 28/2025")
    print("=" * 70)
    
    import pypdf
    reader = pypdf.PdfReader(PP28_MAIN)
    total_pages = len(reader.pages)
    
    print(f"\n📄 File: PP Nomor 28 Tahun 2025 (1).pdf")
    print(f"   Pagine totali: {total_pages}\n")
    
    # Prima cerca nel testo estratto con pypdf per trovare pagine con riferimenti PMA
    print("🔍 Fase 1: Ricerca riferimenti PMA nel testo estratto...\n")
    
    pma_pages = []
    for page_num in range(len(reader.pages)):
        try:
            text = reader.pages[page_num].extract_text() or ""
            text_upper = text.upper()
            
            # Cerca riferimenti a PMA, investimenti stranieri, percentuali
            if any(keyword in text_upper for keyword in [
                "PMA", "PENANAMAN MODAL ASING", "KEPEMILIKAN ASING", 
                "MODAL ASING", "INVESTASI ASING", "100%", "67%", "49%",
                "PERSENTASE", "PERCENTASE"
            ]):
                pma_pages.append(page_num + 1)
                # Mostra snippet
                lines = text.split('\n')
                relevant_lines = [l for l in lines if any(k in l.upper() for k in ["PMA", "ASING", "MODAL", "100", "67", "49"])]
                if relevant_lines:
                    print(f"   📄 Pagina {page_num + 1}: Trovato riferimento PMA")
                    print(f"      {relevant_lines[0][:100]}...")
        except Exception as e:
            continue
    
    print(f"\n✅ Trovate {len(pma_pages)} pagine con riferimenti PMA")
    print(f"   Pagine: {pma_pages[:20]}..." if len(pma_pages) > 20 else f"   Pagine: {pma_pages}")
    
    # Ora analizza le pagine più rilevanti con Vision
    print(f"\n🔍 Fase 2: Analisi dettagliata con Vision delle pagine più rilevanti...\n")
    
    # Analizza prime 5 pagine con riferimenti PMA
    for page_num in pma_pages[:5]:
        print(f"\n{'='*70}")
        print(f"PAGINA {page_num}")
        print(f"{'='*70}\n")
        
        prompt = f"""
        Analizza questa pagina del documento principale PP 28/2025.
        
        Questa pagina contiene riferimenti a PMA (Penanaman Modal Asing) o investimenti stranieri.
        
        Estrai e descrivi:
        1. Quali sono le regole generali su PMA menzionate?
        2. Ci sono percentuali specifiche menzionate (100%, 67%, 49%, ecc.)?
        3. Come si determina se un KBLI permette PMA?
        4. Ci sono riferimenti a liste negative (KBLI vietati per PMA) o liste positive (KBLI permessi)?
        5. Ci sono riferimenti ad altri documenti o regolamenti che contengono le regole PMA per KBLI?
        6. Qual è il contesto normativo? (es: articoli, sezioni, riferimenti legali)
        
        Rispondi in modo molto dettagliato, citando esattamente il testo rilevante.
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
    asyncio.run(find_pma_sections())
